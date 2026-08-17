from __future__ import annotations

import contextlib
import errno
import json
import os
import pty
import re
import select
import signal
import subprocess
import sys
import termios
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from hashtag_robotics.tic_tac_toe import (
    TIC_TAC_TOE_CELLS,
    TIC_TAC_TOE_PIECES,
    task_for_move,
)

CHECKPOINTS = ("020000", "040000", "060000", "080000", "100000", "120000")
MODEL_VARIANTS = ("games-1-5-80k", "games-1-15")
DEFAULT_MODEL_VARIANT = "games-1-15"
CAMERA_TO_MODEL_CELL = {camera_cell: 10 - camera_cell for camera_cell in range(1, 10)}
MODEL_TO_CAMERA_CELL = {model_cell: 10 - model_cell for model_cell in range(1, 10)}
WINNING_LINES = (
    (1, 2, 3),
    (4, 5, 6),
    (7, 8, 9),
    (1, 4, 7),
    (2, 5, 8),
    (3, 6, 9),
    (1, 5, 9),
    (3, 5, 7),
)
MOVE_OUTCOMES = {
    "success",
    "wrong_cell",
    "wrong_piece",
    "no_motion",
    "dropped_piece",
    "unclear",
}
RETRYABLE_MOVE_OUTCOMES = {"no_motion", "dropped_piece", "unclear"}
HUMAN_POLL_SECONDS = 5.0
WORKSPACE_CLEAR_SECONDS = 2.0
WORKSPACE_CLEAR_CONFIRMATIONS = 2
EMPTY_BOARD = ".../.../..."


class TicTacToeAgentError(RuntimeError):
    pass


class BoardError(TicTacToeAgentError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _bounded_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise TicTacToeAgentError(f"Expected a number, got {raw!r}.") from error
    if not minimum <= value <= maximum:
        raise TicTacToeAgentError(f"Value {value} must be between {minimum} and {maximum}.")
    return value


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise TicTacToeAgentError(f"Expected an integer, got {raw!r}.") from error
    if not minimum <= value <= maximum:
        raise TicTacToeAgentError(f"Value {value} must be between {minimum} and {maximum}.")
    return value


def _profile_path(repo_root: Path) -> Path:
    configured = os.environ.get("HASHTAG_TTT_HARDWARE_CONFIG", "").strip()
    path = (
        Path(configured).expanduser()
        if configured
        else repo_root / ".local-data" / "ttt-hardware.json"
    )
    return path if path.is_absolute() else (repo_root / path).resolve()


def _load_hardware_profile(repo_root: Path) -> tuple[Path, dict[str, Any]]:
    path = _profile_path(repo_root)
    if not path.is_file():
        return path, {}
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TicTacToeAgentError(f"Cannot read hardware profile {path}: {error}") from error
    if not isinstance(decoded, dict) or decoded.get("schema_version") != 1:
        raise TicTacToeAgentError(f"Hardware profile {path} must use schema_version 1.")
    return path, decoded


def _profile_value(profile: dict[str, Any], key: str, env_name: str) -> str:
    override = os.environ.get(env_name, "").strip()
    return override or str(profile.get(key, "")).strip()


def _profile_file_path(repo_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (repo_root / path).resolve()


@dataclass(frozen=True)
class BoardState:
    cells: tuple[str, ...]

    @classmethod
    def parse(cls, raw: str) -> BoardState:
        normalized = str(raw).strip().upper().replace(" ", "")
        rows = normalized.split("/")
        if len(rows) != 3 or any(len(row) != 3 for row in rows):
            raise BoardError("board_camera must be a 3x3 board such as .../.../....")
        cells = tuple("".join(rows))
        if any(cell not in {"X", "O", "."} for cell in cells):
            raise BoardError("board_camera may contain only X, O, . and / characters.")
        return cls(cells)

    def __str__(self) -> str:
        return "/".join("".join(self.cells[index : index + 3]) for index in (0, 3, 6))

    def value(self, camera_cell: int) -> str:
        if camera_cell not in range(1, 10):
            raise BoardError("camera cell must be between 1 and 9.")
        return self.cells[camera_cell - 1]

    def with_value(self, camera_cell: int, piece: str) -> BoardState:
        if self.value(camera_cell) != ".":
            raise BoardError(f"TOP CAMERA cell {camera_cell} is already occupied.")
        cells = list(self.cells)
        cells[camera_cell - 1] = piece
        return BoardState(tuple(cells))

    @property
    def winner(self) -> str | None:
        for line in WINNING_LINES:
            values = {self.value(cell) for cell in line}
            if len(values) == 1 and "." not in values:
                return values.pop()
        return None

    @property
    def full(self) -> bool:
        return "." not in self.cells

    @property
    def next_piece(self) -> str:
        x_count = self.cells.count("X")
        o_count = self.cells.count("O")
        if x_count == o_count:
            return "X"
        if x_count == o_count + 1:
            return "O"
        raise BoardError(
            f"Impossible turn count in camera board: X={x_count}, O={o_count}. "
            "Do not actuate until the board is corrected."
        )

    def assert_playable(self) -> None:
        if self.winner:
            raise BoardError(f"The game already has winner {self.winner}.")
        if self.full:
            raise BoardError("The board is full.")
        # Evaluate the count even when the caller only cares that the board is playable.
        _ = self.next_piece


def piece_and_model_cell(move_id: str) -> tuple[str, int]:
    normalized = move_id.strip().upper()
    try:
        piece, raw_cell = normalized.split("-", 1)
        model_cell = int(raw_cell)
    except ValueError as error:
        raise BoardError("move_id must be X-1..X-9 or O-1..O-9.") from error
    if piece not in TIC_TAC_TOE_PIECES or model_cell not in TIC_TAC_TOE_CELLS:
        raise BoardError("move_id must be X-1..X-9 or O-1..O-9.")
    return piece, model_cell


def expected_camera_board(board_camera: str, move_id: str) -> str:
    board = BoardState.parse(board_camera)
    board.assert_playable()
    piece, model_cell = piece_and_model_cell(move_id)
    if board.next_piece != piece:
        raise BoardError(
            f"It is {board.next_piece}'s turn, but tool {move_id} would place {piece}."
        )
    camera_cell = MODEL_TO_CAMERA_CELL[model_cell]
    return str(board.with_value(camera_cell, piece))


def tool_name_for_move(move_id: str) -> str:
    piece, model_cell = piece_and_model_cell(move_id)
    object_slug = "red_x" if piece == "X" else "white_o"
    cell_slug = TIC_TAC_TOE_CELLS[model_cell].replace(" ", "_")
    return f"put_{object_slug}_in_model_{cell_slug}"


@dataclass(frozen=True)
class TicTacToeAgentConfig:
    repo_root: Path
    checkpoint: str
    physical_enabled: bool
    explicit_physical_opt_in: bool
    model_variant: str = DEFAULT_MODEL_VARIANT
    hardware_profile_path: Path | None = None
    robot_port: str = ""
    robot_id: str = ""
    calibration_dir: Path | None = None
    camera_helper_path: Path | None = None
    top_camera_uid: str = ""
    wrist_camera_uid: str = ""
    inference_device: str = ""
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_warmup_frames: int = 4
    observation_stale_seconds: float = 3.0
    move_start_timeout_seconds: float = 300.0
    move_run_timeout_seconds: float = 120.0
    move_save_timeout_seconds: float = 120.0
    max_observations_per_move: int = 24
    max_moves: int = 9
    max_retries_per_move: int = 3
    max_agent_turns: int = 96
    forced_agent_symbol: str = "X"

    @classmethod
    def from_environment(
        cls,
        repo_root: Path,
        checkpoint: str,
        *,
        physical_enabled: bool,
        explicit_physical_opt_in: bool,
        model_variant: str = DEFAULT_MODEL_VARIANT,
    ) -> TicTacToeAgentConfig:
        if checkpoint not in CHECKPOINTS:
            raise TicTacToeAgentError(
                f"Unsupported checkpoint {checkpoint!r}; choose one of {', '.join(CHECKPOINTS)}."
            )
        if model_variant not in MODEL_VARIANTS:
            raise TicTacToeAgentError(
                f"Unsupported model variant {model_variant!r}; "
                f"choose one of {', '.join(MODEL_VARIANTS)}."
            )
        forced_agent_symbol = os.environ.get("HASHTAG_TTT_AGENT_SYMBOL", "X").strip().upper()
        if forced_agent_symbol not in {"X", "O"}:
            raise TicTacToeAgentError("HASHTAG_TTT_AGENT_SYMBOL must be X or O.")
        resolved_root = repo_root.resolve()
        hardware_profile_path, hardware_profile = _load_hardware_profile(resolved_root)
        inference_device = _profile_value(
            hardware_profile, "inference_device", "HASHTAG_TTT_DEVICE"
        ).lower()
        if inference_device and inference_device not in {"mps", "cuda", "cpu"}:
            raise TicTacToeAgentError("Hardware profile inference_device must be mps, cuda or cpu.")
        return cls(
            repo_root=resolved_root,
            checkpoint=checkpoint,
            physical_enabled=physical_enabled,
            explicit_physical_opt_in=explicit_physical_opt_in,
            model_variant=model_variant,
            hardware_profile_path=hardware_profile_path,
            robot_port=_profile_value(hardware_profile, "robot_port", "HASHTAG_TTT_ROBOT_PORT"),
            robot_id=_profile_value(hardware_profile, "robot_id", "HASHTAG_TTT_ROBOT_ID"),
            calibration_dir=_profile_file_path(
                resolved_root,
                _profile_value(hardware_profile, "calibration_dir", "HASHTAG_TTT_CALIBRATION_DIR"),
            ),
            camera_helper_path=_profile_file_path(
                resolved_root,
                _profile_value(hardware_profile, "camera_helper", "HASHTAG_TTT_CAMERA_HELPER"),
            ),
            top_camera_uid=(
                _profile_value(hardware_profile, "top_camera_uid", "HASHTAG_TTT_TOP_CAMERA_UID")
                or os.environ.get("HASHTAG_TTT_AGENT_TOP_CAMERA_UID", "").strip()
            ),
            wrist_camera_uid=(
                _profile_value(hardware_profile, "wrist_camera_uid", "HASHTAG_TTT_WRIST_CAMERA_UID")
                or os.environ.get("HASHTAG_TTT_AGENT_WRIST_CAMERA_UID", "").strip()
            ),
            inference_device=inference_device,
            camera_warmup_frames=_bounded_int(
                os.environ.get("HASHTAG_TTT_AGENT_CAMERA_WARMUP_FRAMES"), 4, 1, 30
            ),
            observation_stale_seconds=_bounded_float(
                os.environ.get("HASHTAG_TTT_AGENT_STALE_FRAME_SECONDS"), 3.0, 0.5, 15.0
            ),
            move_start_timeout_seconds=_bounded_float(
                os.environ.get("HASHTAG_TTT_AGENT_START_TIMEOUT_SECONDS"),
                300.0,
                30.0,
                900.0,
            ),
            move_run_timeout_seconds=_bounded_float(
                os.environ.get("HASHTAG_TTT_AGENT_MOVE_TIMEOUT_SECONDS"),
                120.0,
                15.0,
                600.0,
            ),
            move_save_timeout_seconds=_bounded_float(
                os.environ.get("HASHTAG_TTT_AGENT_SAVE_TIMEOUT_SECONDS"),
                120.0,
                15.0,
                600.0,
            ),
            max_observations_per_move=_bounded_int(
                os.environ.get("HASHTAG_TTT_AGENT_MAX_MOVE_OBSERVATIONS"), 24, 2, 100
            ),
            max_moves=_bounded_int(os.environ.get("HASHTAG_TTT_AGENT_MAX_MOVES"), 9, 1, 9),
            max_retries_per_move=_bounded_int(
                os.environ.get("HASHTAG_TTT_AGENT_MAX_RETRIES_PER_MOVE"), 3, 0, 5
            ),
            max_agent_turns=_bounded_int(
                os.environ.get("HASHTAG_TTT_AGENT_MAX_TURNS"), 96, 12, 256
            ),
            forced_agent_symbol=forced_agent_symbol,
        )

    @property
    def manifest_path(self) -> Path:
        manifest_name = (
            "ttt_games_1_5_80k.json"
            if self.model_variant == "games-1-5-80k"
            else "ttt_checkpoint_sweep.json"
        )
        return self.repo_root / "src" / "hashtag_robotics" / manifest_name

    @property
    def helper_path(self) -> Path:
        return self.camera_helper_path or (
            self.repo_root / ".local-data" / "bin" / "avfoundation-uid-capture"
        )

    @property
    def session_root(self) -> Path:
        return self.repo_root / ".local-data" / "ttt-agent-sessions"

    def checkpoint_path(self) -> Path:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if self.checkpoint not in manifest.get("checkpoints", []):
            raise TicTacToeAgentError(
                f"Checkpoint {self.checkpoint} is not allowed by {self.manifest_path}."
            )
        relative = str(manifest["checkpoint_path_template"]).replace(
            "{checkpoint}", self.checkpoint
        )
        slug = str(manifest["model_repo_id"]).replace("/", "--")
        root = self.repo_root / ".local-data" / "policies" / slug / str(manifest["model_revision"])
        return root if relative == "." else root / relative

    def static_preflight(self) -> dict[str, Any]:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        launchers = [
            self.repo_root / "ttt-rollouts" / f"{piece}-{cell}"
            for piece in "XO"
            for cell in range(1, 10)
        ]
        missing_launchers = [str(path) for path in launchers if not path.is_file()]
        non_executable = [
            str(path) for path in launchers if path.is_file() and not os.access(path, os.X_OK)
        ]
        checkpoint_path = self.checkpoint_path()
        calibration_file = (
            self.calibration_dir / f"{self.robot_id}.json"
            if self.calibration_dir is not None and self.robot_id
            else None
        )
        return {
            "model_variant": self.model_variant,
            "model_repo_id": manifest["model_repo_id"],
            "model_revision": manifest["model_revision"],
            "checkpoint": self.checkpoint,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_present": checkpoint_path.is_dir(),
            "launcher_count": len(launchers) - len(missing_launchers),
            "missing_launchers": missing_launchers,
            "non_executable_launchers": non_executable,
            "hardware_profile": str(self.hardware_profile_path)
            if self.hardware_profile_path
            else None,
            "hardware_profile_present": bool(
                self.hardware_profile_path and self.hardware_profile_path.is_file()
            ),
            "robot_port": self.robot_port or None,
            "robot_port_present": bool(self.robot_port and Path(self.robot_port).exists()),
            "robot_id": self.robot_id or None,
            "calibration_dir": str(self.calibration_dir) if self.calibration_dir else None,
            "calibration_present": bool(calibration_file and calibration_file.is_file()),
            "top_camera_uid_configured": bool(self.top_camera_uid),
            "wrist_camera_uid_configured": bool(self.wrist_camera_uid),
            "inference_device": self.inference_device or None,
            "camera_helper": str(self.helper_path),
            "camera_helper_executable": self.helper_path.is_file()
            and os.access(self.helper_path, os.X_OK),
            "physical_env_enabled": self.physical_enabled,
            "physical_cli_opt_in": self.explicit_physical_opt_in,
        }

    def assert_physical_ready(self) -> None:
        preflight = self.static_preflight()
        if not self.physical_enabled:
            raise TicTacToeAgentError(
                "Physical execution is disabled. Set HASHTAG_ENABLE_PHYSICAL=true."
            )
        if not self.explicit_physical_opt_in:
            raise TicTacToeAgentError("Pass --physical for this exact agent invocation.")
        if preflight["missing_launchers"] or preflight["non_executable_launchers"]:
            raise TicTacToeAgentError("The 18 tic-tac-toe launchers are incomplete.")
        if not preflight["hardware_profile_present"]:
            raise TicTacToeAgentError(
                "Create .local-data/ttt-hardware.json from config/ttt-hardware.example.json."
            )
        if not preflight["robot_port_present"]:
            raise TicTacToeAgentError("The configured follower serial port is unavailable.")
        if not preflight["robot_id"] or not preflight["calibration_present"]:
            raise TicTacToeAgentError(
                "The configured follower ID does not have a calibration file in calibration_dir."
            )
        if (
            not preflight["top_camera_uid_configured"]
            or not preflight["wrist_camera_uid_configured"]
        ):
            raise TicTacToeAgentError("Configure distinct top and wrist camera UIDs.")
        if self.top_camera_uid == self.wrist_camera_uid:
            raise TicTacToeAgentError("Top and wrist cameras must use different UIDs.")
        if not preflight["inference_device"]:
            raise TicTacToeAgentError("Configure inference_device as mps, cuda or cpu.")
        if not preflight["checkpoint_present"]:
            raise TicTacToeAgentError(
                "The pinned checkpoint is not present locally. Fetch it before starting the agent: "
                f"scripts/fetch_ttt_checkpoint.py --manifest {self.manifest_path} "
                f"--policy-root {self.repo_root / '.local-data' / 'policies'} "
                f"--checkpoint {self.checkpoint}"
            )
        if not preflight["camera_helper_executable"]:
            raise TicTacToeAgentError(
                f"AVFoundation UID camera helper is unavailable: {self.helper_path}"
            )


class TerminalOperatorGate:
    """A model cannot approve its own bounded physical game session."""

    def __init__(
        self,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        # Strands executes decorated synchronous tools with asyncio.to_thread.
        # Opening /dev/tty from that worker loses the macOS controlling terminal
        # even when the runner was launched from Terminal.app. Capture the
        # human-owned streams on the main thread instead.
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stderr
        self._lock = threading.Lock()
        self._session_authorized = False

    def __call__(self, move_id: str, task: str, checkpoint: str) -> None:
        with self._lock:
            if self._session_authorized:
                return
            self._authorize_session(move_id, task, checkpoint)

    def _authorize_session(self, move_id: str, task: str, checkpoint: str) -> None:
        if not self.input_stream.isatty() or not self.output_stream.isatty():
            raise TicTacToeAgentError("A physical game requires an interactive operator terminal.")
        approval = "Bu oyun boyunca denetimli otomatik robot hamlelerini onaylıyorum"
        try:
            self.output_stream.write(
                "\n"
                f"FİZİKSEL OYUN OTURUMU | checkpoint {checkpoint}\n"
                f"İlk SmolVLA hamlesi: {move_id} — {task}\n"
                "Tahtayı, boş süpürme alanını, parça haznesini ve E-STOP'u kontrol et.\n"
                "Bu onay yalnızca bu oyun oturumu bitene veya durdurulana kadar geçerlidir.\n"
                f"'{approval}' yaz: "
            )
            self.output_stream.flush()
            answer = self.input_stream.readline().strip().casefold()
        except OSError as error:
            raise TicTacToeAgentError(
                "The interactive operator terminal became unavailable."
            ) from error
        if answer != approval.casefold():
            raise TicTacToeAgentError("Operator did not authorize the physical game session.")
        self._session_authorized = True


@dataclass
class ActiveRollout:
    attempt_id: str
    move_id: str
    task: str
    board_before: str
    expected_board_after: str
    live_dir: Path
    transcript_path: Path
    process: subprocess.Popen[bytes]
    master_fd: int
    started_at: float
    ready_for_inference: threading.Event = field(default_factory=threading.Event)
    inference_started: threading.Event = field(default_factory=threading.Event)
    process_exited: threading.Event = field(default_factory=threading.Event)
    stop_watchdog: threading.Event = field(default_factory=threading.Event)
    output_tail: deque[str] = field(default_factory=lambda: deque(maxlen=240))
    observations: int = 0
    marker_buffer: str = ""
    reader_thread: threading.Thread | None = None
    watchdog_thread: threading.Thread | None = None


class TicTacToeRolloutController:
    def __init__(
        self,
        config: TicTacToeAgentConfig,
        *,
        operator_gate: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self.config = config
        self.operator_gate = operator_gate or TerminalOperatorGate()
        self.lock = threading.RLock()
        self.active: ActiveRollout | None = None
        self.completed_moves: list[dict[str, Any]] = []
        self.observation_index = 0
        self.phase = "awaiting_symbol"
        self.agent_symbol: str | None = None
        self.human_symbol: str | None = None
        self.confirmed_board = EMPTY_BOARD
        self.human_wait_started_observation: int | None = None
        self.last_human_poll_at: float | None = None
        self.workspace_clear_started_observation: int | None = None
        self.workspace_clear_last_observation: int | None = None
        self.workspace_clear_streak = 0
        self.workspace_clear_last_confirmed_at: float | None = None
        self.last_workspace_clear_poll_at: float | None = None
        self.pending_retry_move_id: str | None = None
        self.pending_retry_count = 0
        session_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"ttt-agent-{session_tag}-{uuid.uuid4().hex[:8]}"
        self.session_dir = self.config.session_root / self.session_id
        self.observation_dir = self.session_dir / "observations"
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self.observation_dir.mkdir(parents=True)
        self.audit_path = self.session_dir / "audit.jsonl"
        self._audit(
            "session_created",
            checkpoint=config.checkpoint,
            model_repo_id=config.static_preflight()["model_repo_id"],
        )

    def _audit(self, event: str, **payload: Any) -> None:
        entry = {"at": utc_now(), "event": event, **payload}
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def inspect(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "audit_path": str(self.audit_path),
            "preflight": self.config.static_preflight(),
            "tool_names": [
                tool_name_for_move(f"{piece}-{cell}") for piece in "XO" for cell in range(1, 10)
            ],
            "camera_to_model_cell": CAMERA_TO_MODEL_CELL,
            "model_to_camera_cell": MODEL_TO_CAMERA_CELL,
            "game": self.game_state(),
        }

    def game_state(self) -> dict[str, Any]:
        with self.lock:
            board = BoardState.parse(self.confirmed_board)
            return {
                "phase": self.phase,
                "agent_symbol": self.agent_symbol,
                "human_symbol": self.human_symbol,
                "forced_agent_symbol": self.config.forced_agent_symbol,
                "confirmed_board_camera": self.confirmed_board,
                "winner": board.winner,
                "board_full": board.full,
                "required_human_poll_seconds": HUMAN_POLL_SECONDS,
                "workspace_clear_confirmations_required": WORKSPACE_CLEAR_CONFIRMATIONS,
                "workspace_clear_confirmations": self.workspace_clear_streak,
                "pending_retry_move_id": self.pending_retry_move_id,
                "pending_retry_count": self.pending_retry_count,
                "max_retries_per_move": self.config.max_retries_per_move,
            }

    def choose_agent_symbol(
        self,
        symbol: str,
        board_camera: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Lock the agent to X or O for one new, empty-board game."""

        selected = symbol.strip().upper()
        if selected not in {"X", "O"}:
            raise BoardError("symbol must be X or O.")
        if selected != self.config.forced_agent_symbol:
            raise BoardError(
                f"This session locks the agent to {self.config.forced_agent_symbol}; "
                f"symbol {selected} is forbidden."
            )
        board = str(BoardState.parse(board_camera))
        if board != EMPTY_BOARD:
            raise BoardError("A new agent-first game requires a visibly empty board.")
        if len(rationale.strip()) < 3 or len(rationale) > 600:
            raise TicTacToeAgentError("Symbol rationale must contain 3..600 characters.")
        with self.lock:
            if self.phase != "awaiting_symbol":
                raise TicTacToeAgentError(
                    f"The game symbol is already locked to {self.agent_symbol}; it cannot change."
                )
            if self.observation_index < 1:
                raise TicTacToeAgentError(
                    "Observe both cameras before selecting a symbol or moving the robot."
                )
            if self.active is not None or self.completed_moves:
                raise TicTacToeAgentError("A symbol cannot be selected after a rollout starts.")
            self.agent_symbol = selected
            self.human_symbol = "O" if selected == "X" else "X"
            self.confirmed_board = board
            self.phase = "agent_turn"
            result = self.game_state()
        self._audit("agent_symbol_locked", rationale=rationale.strip(), **result)
        return result

    def acknowledge_human_move(self, board_camera: str, diagnosis: str) -> dict[str, Any]:
        """Advance only when one newly observed cell contains the human symbol."""

        observed = BoardState.parse(board_camera)
        if not diagnosis.strip() or len(diagnosis) > 1_000:
            raise TicTacToeAgentError("diagnosis must contain 1..1000 characters.")
        with self.lock:
            if self.phase != "waiting_for_human":
                raise TicTacToeAgentError(
                    f"A human move is not expected while game phase is {self.phase}."
                )
            if self.human_symbol is None or self.human_wait_started_observation is None:
                raise TicTacToeAgentError("Human-turn state is incomplete; stop the session.")
            if self.observation_index <= self.human_wait_started_observation:
                raise TicTacToeAgentError(
                    "Observe both cameras after the agent move before acknowledging a human move."
                )
            before = BoardState.parse(self.confirmed_board)
            changes = [cell for cell in range(1, 10) if before.value(cell) != observed.value(cell)]
            if len(changes) != 1:
                raise BoardError(
                    "A human turn must change exactly one cell; keep polling or stop if ambiguous."
                )
            changed_cell = changes[0]
            if (
                before.value(changed_cell) != "."
                or observed.value(changed_cell) != self.human_symbol
            ):
                raise BoardError(
                    f"The only allowed human change is . -> {self.human_symbol}; "
                    f"camera cell {changed_cell} does not match."
                )
            self.confirmed_board = str(observed)
            if observed.winner or observed.full:
                self.phase = "game_over"
            else:
                self.phase = "waiting_for_workspace_clear"
                self.workspace_clear_started_observation = self.observation_index
                self.workspace_clear_last_observation = None
                self.workspace_clear_streak = 0
                self.workspace_clear_last_confirmed_at = None
                self.last_workspace_clear_poll_at = None
            self.human_wait_started_observation = None
            self.last_human_poll_at = None
            result = {
                **self.game_state(),
                "changed_camera_cell": changed_cell,
                "changed_model_cell": CAMERA_TO_MODEL_CELL[changed_cell],
                "diagnosis": diagnosis.strip(),
            }
        self._audit("human_move_acknowledged", **result)
        return result

    def confirm_workspace_clear(
        self,
        board_camera: str,
        workspace_clear: bool,
        evidence: str,
    ) -> dict[str, Any]:
        """Require two distinct, spaced observations before an automatic response move."""

        observed_board = str(BoardState.parse(board_camera))
        if not evidence.strip() or len(evidence) > 1_000:
            raise TicTacToeAgentError("evidence must contain 1..1000 characters.")
        with self.lock:
            if self.phase != "waiting_for_workspace_clear":
                raise TicTacToeAgentError(
                    f"Workspace clearance is not expected while game phase is {self.phase}."
                )
            if self.workspace_clear_started_observation is None:
                raise TicTacToeAgentError("Workspace-clear state is incomplete; stop the session.")
            if self.observation_index <= self.workspace_clear_started_observation:
                raise TicTacToeAgentError(
                    "Take a new camera observation after acknowledging the human move."
                )
            if self.workspace_clear_last_observation == self.observation_index:
                raise TicTacToeAgentError(
                    "Each workspace-clear confirmation requires a new camera observation."
                )
            if observed_board != self.confirmed_board:
                raise BoardError(
                    "Workspace-clear board does not match the controller's confirmed board: "
                    f"{self.confirmed_board}. Do not retry or actuate."
                )

            now = time.monotonic()
            self.workspace_clear_last_observation = self.observation_index
            if not workspace_clear:
                self.workspace_clear_streak = 0
                self.workspace_clear_last_confirmed_at = None
            else:
                if (
                    self.workspace_clear_last_confirmed_at is not None
                    and now - self.workspace_clear_last_confirmed_at < WORKSPACE_CLEAR_SECONDS
                ):
                    raise TicTacToeAgentError(
                        "Wait at least two seconds and take another observation before confirming."
                    )
                self.workspace_clear_streak += 1
                self.workspace_clear_last_confirmed_at = now
                if self.workspace_clear_streak >= WORKSPACE_CLEAR_CONFIRMATIONS:
                    self.phase = "agent_turn"
                    self.workspace_clear_started_observation = None
                    self.last_workspace_clear_poll_at = None

            result = {
                **self.game_state(),
                "board_camera": observed_board,
                "workspace_clear": bool(workspace_clear),
                "evidence": evidence.strip(),
            }
        self._audit("workspace_clear_checked", **result)
        return result

    def _assert_no_external_camera_owner(self) -> None:
        for pattern, message in (
            ("[h]ashtag-lerobot-rollout", "Another LeRobot rollout is already running."),
            (
                "[a]vfoundation-uid-capture",
                "A camera preview or capture helper is already running.",
            ),
        ):
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                raise TicTacToeAgentError(message)

    def _capture_camera(self, role: str, unique_id: str, destination: Path) -> bytes:
        from hashtag_robotics.avfoundation_uid import AVFoundationUIDCamera
        from hashtag_robotics.config_avfoundation_uid import AVFoundationUIDCameraConfig

        config = AVFoundationUIDCameraConfig(
            unique_id=unique_id,
            helper_path=self.config.helper_path,
            fps=self.config.camera_fps,
            width=self.config.camera_width,
            height=self.config.camera_height,
            preview_name=None,
        )
        camera = AVFoundationUIDCamera(config)
        try:
            camera.connect()
            frame = None
            for _ in range(self.config.camera_warmup_frames):
                frame = camera.async_read(timeout_ms=2_000)
            if frame is None:
                raise TicTacToeAgentError(f"Camera {role} produced no observation frame.")
            import cv2

            # AVFoundationUIDCamera is configured as RGB; OpenCV encodes BGR.
            encoded, buffer = cv2.imencode(
                ".jpg", frame[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            if not encoded:
                raise TicTacToeAgentError(f"Camera {role} frame could not be encoded.")
            payload = buffer.tobytes()
        finally:
            with contextlib.suppress(Exception):
                camera.disconnect()
        temporary = destination.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        return payload

    def _copy_live_frame(self, role: str, destination: Path) -> bytes:
        active = self.active
        if active is None:
            raise TicTacToeAgentError("No rollout is active.")
        source = active.live_dir / f"{role}.jpg"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not source.is_file():
            if active.process.poll() is not None:
                break
            time.sleep(0.05)
        if not source.is_file():
            raise TicTacToeAgentError(f"Live {role} camera relay has not produced a frame.")
        age = time.time() - source.stat().st_mtime
        if age > self.config.observation_stale_seconds:
            raise TicTacToeAgentError(
                f"Live {role} camera frame is stale ({age:.1f}s); do not infer a move."
            )
        payload = source.read_bytes()
        temporary = destination.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        return payload

    def observe(self, wait_seconds: float = 0.0) -> dict[str, Any]:
        wait_seconds = max(0.0, min(float(wait_seconds), 5.0))
        with self.lock:
            if self.phase == "waiting_for_human" and self.last_human_poll_at is not None:
                elapsed = time.monotonic() - self.last_human_poll_at
                wait_seconds = max(wait_seconds, HUMAN_POLL_SECONDS - elapsed)
            elif (
                self.phase == "waiting_for_workspace_clear"
                and self.last_workspace_clear_poll_at is not None
            ):
                elapsed = time.monotonic() - self.last_workspace_clear_poll_at
                wait_seconds = max(wait_seconds, WORKSPACE_CLEAR_SECONDS - elapsed)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        with self.lock:
            active = self.active
            if active is not None:
                if active.observations >= self.config.max_observations_per_move:
                    raise TicTacToeAgentError(
                        "Observation budget exhausted for this move. "
                        "Finish it as no_motion or unclear."
                    )
                active.observations += 1
            else:
                self._assert_no_external_camera_owner()
            self.observation_index += 1
            tag = f"observation-{self.observation_index:03d}"
            top_path = self.observation_dir / f"{tag}-top.jpg"
            wrist_path = self.observation_dir / f"{tag}-wrist.jpg"
            if active is None:
                top = self._capture_camera("top", self.config.top_camera_uid, top_path)
                wrist = self._capture_camera("wrist", self.config.wrist_camera_uid, wrist_path)
                source = "direct-camera"
                move_id = None
                move_elapsed = None
            else:
                top = self._copy_live_frame("top", top_path)
                wrist = self._copy_live_frame("wrist", wrist_path)
                source = "active-rollout-relay"
                move_id = active.move_id
                move_elapsed = round(time.monotonic() - active.started_at, 3)
            metadata = {
                "observation": self.observation_index,
                "source": source,
                "active_move": move_id,
                "move_elapsed_seconds": move_elapsed,
                "top_path": str(top_path),
                "wrist_path": str(wrist_path),
                "coordinate_contract": (
                    "Report board_camera from TOP CAMERA as row-major .../.../...; "
                    "model cell = 10 - camera cell."
                ),
                "game": self.game_state(),
            }
            if self.phase == "waiting_for_human":
                self.last_human_poll_at = time.monotonic()
            elif self.phase == "waiting_for_workspace_clear":
                self.last_workspace_clear_poll_at = time.monotonic()
            self._audit("board_observed", **metadata)
            return {"metadata": metadata, "top": top, "wrist": wrist}

    def _configure_child_terminal(self, slave_fd: int) -> None:
        with contextlib.suppress(OSError):
            attributes = termios.tcgetattr(slave_fd)
            attributes[3] &= ~termios.ECHO
            termios.tcsetattr(slave_fd, termios.TCSANOW, attributes)

    def _reader_loop(self, active: ActiveRollout) -> None:
        try:
            with active.transcript_path.open("ab", buffering=0) as transcript:
                while True:
                    try:
                        readable, _, _ = select.select([active.master_fd], [], [], 0.2)
                    except OSError as error:
                        if error.errno == errno.EBADF and (
                            active.stop_watchdog.is_set() or active.process.poll() is not None
                        ):
                            break
                        self._audit(
                            "move_reader_error",
                            attempt_id=active.attempt_id,
                            move_id=active.move_id,
                            error=f"{type(error).__name__}: {error}",
                        )
                        break
                    if readable:
                        try:
                            payload = os.read(active.master_fd, 8192)
                        except OSError:
                            payload = b""
                        if payload:
                            transcript.write(payload)
                            text = payload.decode(errors="replace")
                            active.output_tail.extend(text.splitlines())
                            active.marker_buffer = (active.marker_buffer + text)[-12_000:]
                            marker = active.marker_buffer
                            if (
                                "Hazır olunca sağ ok veya n" in marker
                                or "Başlatmak için sağ ok" in marker
                            ):
                                active.ready_for_inference.set()
                            if "model inference başlıyor" in marker:
                                active.inference_started.set()
                    if active.process.poll() is not None:
                        break
        finally:
            active.process_exited.set()

    def _send(self, active: ActiveRollout, payload: bytes) -> None:
        if active.process.poll() is not None:
            raise TicTacToeAgentError(
                f"Rollout {active.move_id} exited with code {active.process.returncode}."
            )
        try:
            os.write(active.master_fd, payload)
        except OSError as error:
            raise TicTacToeAgentError("Could not send a control key to the rollout PTY.") from error

    def _terminate(self, active: ActiveRollout, grace_seconds: float = 4.0) -> str:
        active.stop_watchdog.set()
        if active.process.poll() is not None:
            return "already-exited"
        try:
            process_group = os.getpgid(active.process.pid)
        except ProcessLookupError:
            return "already-exited"
        for current_signal, wait_seconds in (
            (signal.SIGINT, grace_seconds),
            (signal.SIGTERM, 2.0),
            (signal.SIGKILL, 1.0),
        ):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process_group, current_signal)
            try:
                active.process.wait(timeout=wait_seconds)
                return current_signal.name
            except subprocess.TimeoutExpired:
                continue
        return "signal-escalation-exhausted"

    def _watchdog_loop(self, active: ActiveRollout) -> None:
        if active.stop_watchdog.wait(self.config.move_run_timeout_seconds):
            return
        with self.lock:
            if self.active is not active or active.process.poll() is not None:
                return
            self._audit(
                "move_watchdog_expired",
                attempt_id=active.attempt_id,
                move_id=active.move_id,
                timeout_seconds=self.config.move_run_timeout_seconds,
            )
            with contextlib.suppress(Exception):
                self._send(active, b"q")
        if not active.process_exited.wait(5.0):
            self._terminate(active)

    def start_move(self, move_id: str, board_camera: str, rationale: str) -> dict[str, Any]:
        normalized = move_id.strip().upper()
        board = BoardState.parse(board_camera)
        piece, model_cell = piece_and_model_cell(normalized)
        camera_cell = MODEL_TO_CAMERA_CELL[model_cell]
        task = task_for_move(normalized)
        if len(rationale.strip()) < 3:
            raise TicTacToeAgentError("Provide a short move rationale for the diagnostic log.")
        if len(rationale) > 600:
            raise TicTacToeAgentError("Move rationale is limited to 600 characters.")

        with self.lock:
            self.config.assert_physical_ready()
            if self.phase != "agent_turn":
                raise TicTacToeAgentError(
                    f"The robot may not move while game phase is {self.phase}."
                )
            if self.agent_symbol is None or piece != self.agent_symbol:
                raise TicTacToeAgentError(
                    f"The agent is locked to {self.agent_symbol}; tool {normalized} is forbidden."
                )
            if self.pending_retry_move_id is not None and normalized != self.pending_retry_move_id:
                raise TicTacToeAgentError(
                    f"A controlled retry is locked to {self.pending_retry_move_id}; "
                    f"tool {normalized} is forbidden."
                )
            if str(board) != self.confirmed_board:
                raise BoardError(
                    "Reported board_camera does not match the controller's last confirmed board: "
                    f"{self.confirmed_board}. Observe and reconcile before actuation."
                )
            if board.winner:
                raise BoardError(f"The game already has winner {board.winner}.")
            if board.full:
                raise BoardError("The board is full.")
            expected = str(board.with_value(camera_cell, piece))
            if self.active is not None:
                raise TicTacToeAgentError(
                    f"Move {self.active.move_id} is still active; observe or finish it first."
                )
            successful_moves = sum(item["outcome"] == "success" for item in self.completed_moves)
            if successful_moves >= self.config.max_moves:
                raise TicTacToeAgentError("This agent session reached its maximum move count.")

        # This blocks on a human-owned /dev/tty. It is intentionally outside the
        # controller lock so an operator can still interrupt the parent process.
        self.operator_gate(normalized, task, self.config.checkpoint)

        with self.lock:
            if self.active is not None:
                raise TicTacToeAgentError("Another move became active while awaiting approval.")
            self._assert_no_external_camera_owner()
            attempt_id = f"{len(self.completed_moves) + 1:02d}-{normalized}-{uuid.uuid4().hex[:8]}"
            attempt_dir = self.session_dir / "moves" / attempt_id
            live_dir = attempt_dir / "live"
            live_dir.mkdir(parents=True)
            transcript_path = attempt_dir / "terminal.log"
            launcher = self.config.repo_root / "ttt-rollouts" / normalized
            environment = {
                **os.environ,
                "TTT_MODEL_VARIANT": self.config.model_variant,
                "TTT_MODEL_CHECKPOINT": self.config.checkpoint,
                "HASHTAG_RECORDING_LIVE_DIR": str(live_dir),
                "HASHTAG_TTT_AGENT_GAME_MODE": "1",
            }
            master_fd, slave_fd = pty.openpty()
            self._configure_child_terminal(slave_fd)
            try:
                process = subprocess.Popen(
                    [str(launcher)],
                    cwd=self.config.repo_root,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    start_new_session=True,
                    env=environment,
                )
            finally:
                os.close(slave_fd)
            active = ActiveRollout(
                attempt_id=attempt_id,
                move_id=normalized,
                task=task,
                board_before=str(board),
                expected_board_after=expected,
                live_dir=live_dir,
                transcript_path=transcript_path,
                process=process,
                master_fd=master_fd,
                started_at=time.monotonic(),
            )
            self.active = active
            active.reader_thread = threading.Thread(
                target=self._reader_loop,
                args=(active,),
                name=f"ttt-agent-reader-{attempt_id}",
                daemon=True,
            )
            active.reader_thread.start()
            self._audit(
                "move_process_started",
                attempt_id=attempt_id,
                move_id=normalized,
                task=task,
                checkpoint=self.config.checkpoint,
                board_camera_before=str(board),
                expected_board_camera_after=expected,
                model_cell=model_cell,
                camera_cell=camera_cell,
                rationale=rationale.strip(),
                pid=process.pid,
                transcript_path=str(transcript_path),
                live_dir=str(live_dir),
            )
            # The operator already approved this one move. HOME answers the
            # launcher's duplicate terminal gate; it does not skip the model-side
            # target/turn validation above.
            self._send(active, b"HOME\r")

        if not active.ready_for_inference.wait(self.config.move_start_timeout_seconds):
            tail = " | ".join(active.output_tail)[-2_000:]
            outcome = self._terminate(active)
            with self.lock:
                self.active = None
                self.phase = "halted"
            raise TicTacToeAgentError(
                "Rollout did not reach its post-homing inference gate. "
                f"Termination={outcome}. Tail={tail}"
            )
        with self.lock:
            self._send(active, b"n")
        if not active.inference_started.wait(10.0):
            tail = " | ".join(active.output_tail)[-2_000:]
            outcome = self._terminate(active)
            with self.lock:
                self.active = None
                self.phase = "halted"
            raise TicTacToeAgentError(
                f"Rollout did not acknowledge inference start. Termination={outcome}. Tail={tail}"
            )
        active.watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            args=(active,),
            name=f"ttt-agent-watchdog-{attempt_id}",
            daemon=True,
        )
        active.watchdog_thread.start()
        self._audit("move_inference_started", attempt_id=attempt_id, move_id=normalized)
        return {
            "state": "active",
            "attempt_id": attempt_id,
            "move_id": normalized,
            "task": task,
            "checkpoint": self.config.checkpoint,
            "board_camera_before": str(board),
            "expected_board_camera_after": expected,
            "retry_number": self.pending_retry_count,
            "instruction": (
                "Call observe_board every 2-3 seconds. When the result is clear, "
                "call finish_active_move exactly once."
            ),
            "game": self.game_state(),
        }

    def _rollout_paths(self, active: ActiveRollout) -> dict[str, str | None]:
        text = "\n".join(active.output_tail)
        dataset = re.findall(r"Rollout tamamlandı\. Dataset: (.+)", text)
        rollout_log = re.findall(r"Terminal logu kaydedildi: (.+)", text)
        return {
            "dataset_path": dataset[-1].strip() if dataset else None,
            "rollout_log_path": rollout_log[-1].strip() if rollout_log else None,
        }

    def finish_move(
        self,
        board_camera_after: str,
        outcome: str,
        diagnosis: str,
    ) -> dict[str, Any]:
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome not in MOVE_OUTCOMES:
            raise TicTacToeAgentError(f"outcome must be one of {', '.join(sorted(MOVE_OUTCOMES))}.")
        board_after = str(BoardState.parse(board_camera_after))
        if not diagnosis.strip() or len(diagnosis) > 1_000:
            raise TicTacToeAgentError("diagnosis must contain 1..1000 characters.")
        with self.lock:
            active = self.active
            if active is None:
                raise TicTacToeAgentError("No rollout is active.")
            if normalized_outcome == "success" and board_after != active.expected_board_after:
                raise TicTacToeAgentError(
                    "A success result must exactly match expected board_camera "
                    f"{active.expected_board_after}; observed {board_after}."
                )
            active.stop_watchdog.set()
            if active.process.poll() is None:
                self._send(active, b"n")

        timed_out = False
        try:
            active.process.wait(timeout=self.config.move_save_timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            termination = self._terminate(active)
        else:
            termination = "normal-exit"
        active.process_exited.wait(2.0)
        active.stop_watchdog.set()
        with contextlib.suppress(OSError):
            os.close(active.master_fd)
        if active.reader_thread is not None:
            active.reader_thread.join(timeout=1.0)
        paths = self._rollout_paths(active)
        error_lines = [
            line
            for line in active.output_tail
            if re.search(
                r"\b(ERROR|CRITICAL|FATAL)\b|Traceback|RTC inference error|camera incident",
                line,
                flags=re.IGNORECASE,
            )
        ][-40:]
        result = {
            "attempt_id": active.attempt_id,
            "move_id": active.move_id,
            "task": active.task,
            "checkpoint": self.config.checkpoint,
            "outcome": normalized_outcome,
            "board_camera_before": active.board_before,
            "expected_board_camera_after": active.expected_board_after,
            "board_camera_after": board_after,
            "diagnosis": diagnosis.strip(),
            "duration_seconds": round(time.monotonic() - active.started_at, 3),
            "observation_count": active.observations,
            "return_code": active.process.returncode,
            "save_timed_out": timed_out,
            "termination": termination,
            "terminal_transcript": str(active.transcript_path),
            "error_lines": error_lines,
            **paths,
        }
        with self.lock:
            self.completed_moves.append(result)
            self.active = None
            if normalized_outcome == "success":
                self.confirmed_board = board_after
                self.pending_retry_move_id = None
                self.pending_retry_count = 0
                self.workspace_clear_started_observation = None
                self.workspace_clear_last_observation = None
                self.workspace_clear_streak = 0
                self.workspace_clear_last_confirmed_at = None
                self.last_workspace_clear_poll_at = None
                if BoardState.parse(board_after).winner or BoardState.parse(board_after).full:
                    self.phase = "game_over"
                    self.human_wait_started_observation = None
                    self.last_human_poll_at = None
                else:
                    self.phase = "waiting_for_human"
                    self.human_wait_started_observation = self.observation_index
                    self.last_human_poll_at = time.monotonic()
                result["retry_scheduled"] = False
            elif (
                normalized_outcome in RETRYABLE_MOVE_OUTCOMES
                and board_after == active.board_before
                and self.pending_retry_count < self.config.max_retries_per_move
            ):
                self.pending_retry_move_id = active.move_id
                self.pending_retry_count += 1
                self.phase = "waiting_for_workspace_clear"
                self.workspace_clear_started_observation = self.observation_index
                self.workspace_clear_last_observation = None
                self.workspace_clear_streak = 0
                self.workspace_clear_last_confirmed_at = None
                self.last_workspace_clear_poll_at = None
                result["retry_scheduled"] = True
                result["retry_number"] = self.pending_retry_count
                result["retry_limit"] = self.config.max_retries_per_move
            else:
                self.phase = "halted"
                result["retry_scheduled"] = False
                result["retry_exhausted"] = (
                    normalized_outcome in RETRYABLE_MOVE_OUTCOMES
                    and board_after == active.board_before
                    and self.pending_retry_count >= self.config.max_retries_per_move
                )
            result["game"] = self.game_state()
        self._audit("move_finished", **result)
        return result

    def emergency_stop(self, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise TicTacToeAgentError("An emergency-stop reason is required.")
        with self.lock:
            active = self.active
            if active is None:
                self.phase = "halted"
                self._audit("emergency_stop_requested", reason=reason.strip(), active_move=None)
                return {
                    "stopped": False,
                    "message": "No agent-owned rollout process was active.",
                    "physical_estop_required": True,
                }
            with contextlib.suppress(Exception):
                self._send(active, b"q")
        if not active.process_exited.wait(3.0):
            termination = self._terminate(active, grace_seconds=2.0)
        else:
            termination = "terminal-q"
        if active.reader_thread is not None:
            active.reader_thread.join(timeout=1.0)
        with contextlib.suppress(OSError):
            os.close(active.master_fd)
        result = {
            "stopped": True,
            "attempt_id": active.attempt_id,
            "move_id": active.move_id,
            "reason": reason.strip(),
            "termination": termination,
            "terminal_transcript": str(active.transcript_path),
            "physical_estop_required": True,
        }
        with self.lock:
            self.active = None
            self.phase = "halted"
        self._audit("emergency_stop", **result)
        return result

    def close(self) -> None:
        with self.lock:
            active = self.active
        if active is not None:
            self.emergency_stop("Agent process is closing while a rollout is active.")
        self._audit(
            "session_closed",
            completed_moves=len(self.completed_moves),
            phase=self.phase,
            agent_symbol=self.agent_symbol,
        )


def _image_tool_result(tool_context: Any, observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "toolUseId": tool_context.tool_use["toolUseId"],
        "status": "success",
        "content": [
            {"text": json.dumps(observation["metadata"], ensure_ascii=False, sort_keys=True)},
            {"text": "TOP CAMERA — authoritative 3x3 board view:"},
            {"image": {"format": "jpeg", "source": {"bytes": observation["top"]}}},
            {"text": "WRIST CAMERA — manipulation diagnostic view:"},
            {"image": {"format": "jpeg", "source": {"bytes": observation["wrist"]}}},
        ],
    }


def build_tic_tac_toe_tools(controller: TicTacToeRolloutController) -> list[Any]:
    """Build a narrow Strands surface: game lifecycle and 18 exact moves."""
    try:
        from strands import tool
    except ImportError as error:  # pragma: no cover - only a base install hits this
        raise TicTacToeAgentError("Install the project's 'agents' feature pack.") from error

    configured_agent_symbol = controller.config.forced_agent_symbol
    configured_human_symbol = "O" if configured_agent_symbol == "X" else "X"

    @tool(
        name="observe_board",
        description=(
            "Capture both cameras without moving the robot. TOP CAMERA is authoritative. "
            "Return board_camera as three top-camera rows such as .../.../.... During an "
            "active rollout this reads its live relay and never opens a second camera handle."
        ),
        context=True,
    )
    def observe_board(wait_seconds: float = 0.0, tool_context: Any = None) -> Any:
        """Observe the current board and arm.

        Args:
            wait_seconds: Wait 0..5 seconds before taking the next observation.
        """
        if tool_context is None:  # pragma: no cover - Strands always injects this
            raise TicTacToeAgentError("Strands tool context is missing.")
        return _image_tool_result(tool_context, controller.observe(wait_seconds))

    @tool(
        name="choose_game_symbol",
        description=(
            f"After observing a visibly empty board, lock {configured_agent_symbol} for the "
            f"agent. The human is {configured_human_symbol} and the agent still moves first. "
            f"Any attempt to choose {configured_human_symbol} is rejected by the controller."
        ),
    )
    def choose_game_symbol(symbol: str, board_camera: str, rationale: str) -> dict[str, Any]:
        """Choose and lock the agent's symbol.

        Args:
            symbol: The controller-configured agent symbol.
            board_camera: Empty TOP CAMERA board, exactly .../.../....
            rationale: Short reason for the symbol choice.
        """
        return controller.choose_agent_symbol(symbol, board_camera, rationale)

    @tool(
        name="acknowledge_human_move",
        description=(
            "After a 5-second camera poll shows the human's response, acknowledge exactly one "
            "new opponent symbol. This deterministically rejects unchanged, multi-cell, removed "
            "or wrong-symbol boards and then enters workspace-clearance checks."
        ),
    )
    def acknowledge_human_move(board_camera: str, diagnosis: str) -> dict[str, Any]:
        """Confirm one observed human move.

        Args:
            board_camera: Latest TOP CAMERA board as .../.../....
            diagnosis: Visual evidence for the one-cell human change.
        """
        return controller.acknowledge_human_move(board_camera, diagnosis)

    @tool(
        name="confirm_workspace_clear",
        description=(
            "After acknowledging the human move or scheduling a controlled retry, report the "
            "unchanged board and whether both camera views show that hands and temporary "
            "obstructions have left the immediate arm/gripper path. Two clear observations "
            "at least two seconds apart are required automatically."
        ),
    )
    def confirm_workspace_clear(
        board_camera: str,
        workspace_clear: bool,
        evidence: str,
    ) -> dict[str, Any]:
        """Confirm a clear workspace before the robot's automatic response.

        Args:
            board_camera: Current TOP CAMERA board, which must remain unchanged.
            workspace_clear: True only when hands are no longer in the immediate motion path.
            evidence: Short visual evidence from both current camera images.
        """
        return controller.confirm_workspace_clear(board_camera, workspace_clear, evidence)

    @tool(
        name="finish_active_move",
        description=(
            "Finish and save the one active SmolVLA rollout after visually classifying it. "
            "For success, board_camera_after must exactly equal the tool's expected board. "
            "An unchanged no_motion, dropped_piece or unclear result can schedule a bounded "
            "same-move retry after fresh board and workspace checks. This tool has no unsafe, "
            "aborted or emergency-stop outcome."
        ),
    )
    def finish_active_move(
        board_camera_after: str,
        outcome: str,
        diagnosis: str,
    ) -> dict[str, Any]:
        """Finish the active move.

        Args:
            board_camera_after: TOP CAMERA board as .../.../....
            outcome: success, wrong_cell, wrong_piece, no_motion, dropped_piece or unclear.
            diagnosis: Short visual explanation of what happened.
        """
        return controller.finish_move(board_camera_after, outcome, diagnosis)

    tools: list[Any] = [
        observe_board,
        choose_game_symbol,
        acknowledge_human_move,
        confirm_workspace_clear,
        finish_active_move,
    ]
    for piece in "XO":
        for model_cell in range(1, 10):
            move_id = f"{piece}-{model_cell}"
            model_cell_name = TIC_TAC_TOE_CELLS[model_cell]
            camera_cell = MODEL_TO_CAMERA_CELL[model_cell]
            description = (
                f"Start launcher {move_id} with the exact trained SmolVLA task: "
                f"'{task_for_move(move_id)}'. This targets MODEL/ROBOT cell {model_cell} "
                f"({model_cell_name}), which is TOP CAMERA cell {camera_cell} after the "
                "required 180-degree coordinate transform. It refuses occupied targets, the "
                "human's symbol, out-of-phase turns, concurrent rollouts and unapproved physical "
                "execution."
            )

            def make_invoke_move(bound_move_id: str) -> Callable[[str, str], dict[str, Any]]:
                def invoke_move(board_camera: str, rationale: str) -> dict[str, Any]:
                    """Start one exact SmolVLA move.

                    Args:
                        board_camera: Current TOP CAMERA board as .../.../....
                        rationale: Why this is a legal and strategically selected move.
                    """
                    return controller.start_move(bound_move_id, board_camera, rationale)

                return invoke_move

            tools.append(
                tool(name=tool_name_for_move(move_id), description=description)(
                    make_invoke_move(move_id)
                )
            )
    return tools


def tic_tac_toe_system_prompt(
    checkpoint: str,
    model_variant: str = DEFAULT_MODEL_VARIANT,
    agent_symbol: str = "X",
) -> str:
    normalized_agent_symbol = agent_symbol.strip().upper()
    if normalized_agent_symbol not in {"X", "O"}:
        raise TicTacToeAgentError("agent_symbol must be X or O.")
    human_symbol = "O" if normalized_agent_symbol == "X" else "X"
    mapping = ", ".join(
        f"camera {camera}=model {model}" for camera, model in CAMERA_TO_MODEL_CELL.items()
    )
    return "\n".join(
        [
            "You are the vision-guided tic-tac-toe operator for Hashtag Robotics.",
            f"You are evaluating SmolVLA {model_variant} checkpoint {checkpoint},",
            "not controlling joints yourself.",
            "Speak naturally in Turkish with the human. Do not expose tool names, command syntax",
            "or internal schemas unless you are reporting a technical diagnosis.",
            "Begin a game only after the human explicitly asks you to play.",
            "You play against the human, and you always make the first move.",
            f"You are {normalized_agent_symbol} for the entire game and the human is "
            f"{human_symbol}.",
            f"Lock {normalized_agent_symbol} with choose_game_symbol and make the first move.",
            f"Never call an {human_symbol} move tool or play the human's turns.",
            "Your robot moves use exactly one of the 18 fixed SmolVLA tools; each contains the",
            "exact training prompt.",
            "Never invent a prompt, shell command, joint command, coordinate or extra tool.",
            "",
            "Observation contract:",
            "- First call observe_board and verify BOTH camera images are current and usable.",
            "- A new game requires the TOP CAMERA board to be visibly empty: .../.../....",
            f"- Then call choose_game_symbol exactly once with {normalized_agent_symbol}.",
            "- After symbol lock, independently choose the opening cell from all nine legal",
            "  empty cells using your own tic-tac-toe strategy and the current camera view.",
            "- No opening cell is predetermined. Do not assume center and do not use a default",
            "  move merely because it appeared in an example, previous game or diagnostic log.",
            "- TOP CAMERA is authoritative; wrist is only for grasp/drop diagnosis.",
            "- Transcribe TOP CAMERA as board_camera='row/row/row' using X, O and . only.",
            "- If any cell is unclear, observe again. If still unclear, stop without actuation.",
            "- The TOP CAMERA is rotated 180 degrees from the model/robot task coordinates.",
            f"- Exact mapping: {mapping}.",
            "",
            "Game contract:",
            "- Agent-first role order is authoritative. Do not let conventional symbol order",
            "  override the configured agent-first diagnostic game.",
            "- Once selected, never change your symbol and never call the opponent's move tools.",
            "- Never call a move tool whose TOP CAMERA target is occupied.",
            "- Stop when X or O has three in a row, or when the board is full.",
            "- Choose a winning move first, block an opponent win second, then play strategically.",
            (
                "- A failed physical move does not advance the turn unless the camera proves "
                "a new piece"
            ),
            (
                "  was actually placed. Never retry after a wrong cell, wrong piece, changed "
                "board or unsafe event."
            ),
            "- For no_motion, grasp failure, dropped_piece or unclear with an unchanged board,",
            "  finish_active_move may return retry_scheduled=true. Do not end the game then.",
            "  Re-scan the board and workspace, then invoke the SAME locked move tool again.",
            "  The controller allows at most three automatic retries for one logical move.",
            "",
            "Move lifecycle:",
            (
                "1. Call exactly one fixed move tool with your board_camera transcription "
                "and rationale."
            ),
            "2. Before the first physical move only, the human approves this bounded game session",
            "   in the terminal. Later moves in the same session need no repeated typed approval.",
            "3. While it is active, call observe_board with wait_seconds=2 or 3 repeatedly.",
            "4. Classify success only when the exact expected board is visually present.",
            "5. Call finish_active_move exactly once for success or ordinary failure.",
            "   If retry_scheduled=true, observe and transcribe the full board again, then call",
            "   confirm_workspace_clear with that board on two clear observations two seconds",
            "   apart. When phase=agent_turn, call only pending_retry_move_id; do not re-plan.",
            "   If retry_exhausted=true, report the failed attempts and halt.",
            "6. After success, do not make another robot move. You are waiting for the human.",
            "7. Call observe_board with wait_seconds=5. If the board is unchanged, repeat with",
            "   wait_seconds=5. Never poll the human faster than once every five seconds.",
            "8. When exactly one empty cell changes to the human's locked symbol, call",
            "   acknowledge_human_move once. This enters waiting_for_workspace_clear.",
            "9. Observe with wait_seconds=2 and call confirm_workspace_clear. A hand is expected",
            "   during the human turn. Do not emergency-stop merely because it is visible.",
            "   Obtain two clear observations at least two seconds apart. Only after the tool",
            "   returns phase=agent_turn may you calculate and execute the response move.",
            "10. If cells disappear, several cells change, the wrong symbol appears, or the view",
            "   is ambiguous, do not acknowledge a human turn or start a new move; report it.",
            "- You have no emergency_stop tool and no dashboard stop permission. Never attempt",
            "  to stop or terminate an active rollout because a hand or held object is visible.",
            "- Human presence and manual piece assistance are diagnostic observations only.",
            "  Continue monitoring the active rollout and classify its board result normally.",
            "- Dashboard stop, Ctrl-C/Ctrl-D and the physical E-STOP belong only to the human",
            "  operator and are outside your tool surface.",
            "",
            "Diagnostic duty:",
            "- Mention no_motion, wrong_piece, wrong_cell, dropped_piece, repeated oscillation,",
            "  grasp failure and camera ambiguity explicitly when seen.",
            (
                "- Do not hide failed attempts. The purpose is checkpoint diagnosis, "
                "not a perfect score."
            ),
            "- At game end summarize each attempted move and its observed result.",
        ]
    )


def sanitize_strands_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist the agent trace without embedding megabytes of camera bytes."""

    def clean(value: Any) -> Any:
        if isinstance(value, bytes):
            return {"binary_bytes": len(value)}
        if isinstance(value, dict):
            return {str(key): clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, tuple):
            return [clean(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    return clean(messages)
