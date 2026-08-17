#!/usr/bin/env python3
"""Verify the publishable source/CAD/artifact contract without network or hardware."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = ROOT / "hardware" / "tic-tac-toe"
MAX_FILE_BYTES = 50 * 1024 * 1024

REQUIRED_PATHS = (
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "README.md",
    "README_TR.md",
    "config/artifacts.lock.json",
    "config/ttt-hardware.example.json",
    "hardware/LICENSE",
    "hardware/NOTICE",
    "hardware/README.md",
    "hardware/tic-tac-toe/README.md",
    "hardware/tic-tac-toe/PRINTING.md",
    "hardware/tic-tac-toe/ASSEMBLY.md",
    "hardware/tic-tac-toe/BOM.md",
    "hardware/tic-tac-toe/manifest.json",
    "hardware/tic-tac-toe/checksums.sha256",
    "hardware/camera-tower/README.md",
    "hardware/camera-tower/README_TR.md",
    "hardware/camera-tower/BOM.csv",
    "training/README.md",
    "training/03_train_games_1_15_colab_a100.ipynb",
    "scripts/load_ttt_checkpoint.py",
)

SECRET_PATTERNS = {
    "Hugging Face token": re.compile(rb"hf_[A-Za-z0-9]{20,}"),
    "API key with sk prefix": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

FORBIDDEN_INTEGRATIONS = {
    "forbidden private integration phrase": re.compile(
        bytes.fromhex("636f646578") + rb"[\s_-]*" + bytes.fromhex("70726f7879"),
        re.IGNORECASE,
    ),
    "forbidden private integration probe": re.compile(
        bytes.fromhex("70726f62655f636f6465785f70726f7879")
    ),
    "forbidden private launcher environment": re.compile(bytes.fromhex("54494e595f4d4f44454c5f")),
    "forbidden private provider key setting": re.compile(
        bytes.fromhex("484153485441475f4147454e545f4150495f4b4559")
    ),
    "forbidden non-standard provider spec": re.compile(
        bytes.fromhex("6f70656e61693a"), re.IGNORECASE
    ),
    "forbidden non-standard Strands provider": re.compile(
        bytes.fromhex("737472616e64732e6d6f64656c732e6f70656e6169")
    ),
    "forbidden non-standard provider dependency": re.compile(
        bytes.fromhex("6e616d65203d20226f70656e616922")
    ),
}


class ReleaseError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError(f"Invalid JSON: {path.relative_to(ROOT)}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"Expected a JSON object: {path.relative_to(ROOT)}")
    return value


def candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8")
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def require_release_files() -> None:
    missing = [relative for relative in REQUIRED_PATHS if not (ROOT / relative).is_file()]
    if missing:
        raise ReleaseError(f"Required release files are missing: {', '.join(missing)}")


def verify_artifact_contract() -> None:
    lock = read_json(ROOT / "config" / "artifacts.lock.json")
    full = read_json(ROOT / "src" / "hashtag_robotics" / "ttt_checkpoint_sweep.json")
    baseline = read_json(ROOT / "src" / "hashtag_robotics" / "ttt_games_1_5_80k.json")

    dataset = lock["dataset"]
    policy = lock["default_policy"]
    earlier = lock["baseline_policy"]
    expected_pairs = (
        (policy["repo_id"], full["model_repo_id"], "default model repo"),
        (policy["revision"], full["model_revision"], "default model revision"),
        (policy["checkpoint"], full["default_checkpoint"], "default checkpoint"),
        (dataset["repo_id"], full["dataset_repo_id"], "dataset repo"),
        (dataset["revision"], full["dataset_revision"], "dataset revision"),
        (policy["camera_mapping"], full["camera_mapping"], "camera mapping"),
        (
            policy["declared_visual_inputs"],
            full["declared_visual_inputs"],
            "declared visual inputs",
        ),
        (policy["action_shape"], full["action_shape"], "action shape"),
        (earlier["repo_id"], baseline["model_repo_id"], "baseline model repo"),
        (earlier["revision"], baseline["model_revision"], "baseline model revision"),
    )
    mismatches = [label for actual, expected, label in expected_pairs if actual != expected]
    if mismatches:
        raise ReleaseError(f"Artifact lock mismatch: {', '.join(mismatches)}")
    if policy["checkpoint"] not in full["checkpoints"]:
        raise ReleaseError("Default checkpoint is not present in the allowed sweep")
    if dataset["camera_features"] != [
        "observation.images.top",
        "observation.images.wrist",
    ]:
        raise ReleaseError("Dataset camera order changed")
    if dataset["expected_episodes"] != 195 or dataset["expected_frames"] != 144723:
        raise ReleaseError("Dataset count contract changed")
    if dataset["fps"] != 30 or dataset["state_shape"] != [6] or dataset["action_shape"] != [6]:
        raise ReleaseError("Dataset control schema changed")
    if full["expected_training_steps"] != 120000 or full["expected_batch_size"] != 16:
        raise ReleaseError("Published 120K training contract changed")

    notebook = (ROOT / "training" / "03_train_games_1_15_colab_a100.ipynb").read_text(
        encoding="utf-8"
    )
    for marker in (
        f'DATASET_REVISION = \\"{dataset["revision"]}\\"',
        "BATCH_SIZE = 16",
        "STEPS = 120_000",
    ):
        if marker not in notebook:
            raise ReleaseError(f"Training notebook is missing pinned marker: {marker}")


def verify_checksums() -> None:
    checksum_file = GAME_ROOT / "checksums.sha256"
    checked = 0
    for line_number, raw_line in enumerate(
        checksum_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError as error:
            raise ReleaseError(f"Invalid checksum line {line_number}") from error
        path = GAME_ROOT / relative
        if not path.is_file():
            raise ReleaseError(f"Checksum target is missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ReleaseError(f"Checksum mismatch: {relative}")
        checked += 1
    if checked != 16:
        raise ReleaseError(f"Expected 16 manufacturing checksums, found {checked}")


def stl_dimensions(path: Path) -> tuple[float, float, float]:
    payload = path.read_bytes()
    vertices: list[tuple[float, float, float]] = []
    if len(payload) >= 84:
        triangle_count = struct.unpack_from("<I", payload, 80)[0]
        if 84 + triangle_count * 50 == len(payload):
            for index in range(triangle_count):
                offset = 84 + index * 50 + 12
                for vertex in range(3):
                    vertices.append(struct.unpack_from("<fff", payload, offset + vertex * 12))
    if not vertices:
        text = payload.decode("ascii", errors="ignore")
        vertices = [
            tuple(float(value) for value in match.groups())
            for match in re.finditer(
                r"\bvertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text
            )
        ]
    if not vertices:
        raise ReleaseError(f"No STL vertices found: {path.relative_to(ROOT)}")
    return tuple(
        max(vertex[axis] for vertex in vertices) - min(vertex[axis] for vertex in vertices)
        for axis in range(3)
    )


def verify_manufacturing_manifest() -> None:
    manifest = read_json(GAME_ROOT / "manifest.json")
    if manifest.get("units") != "mm":
        raise ReleaseError("Manufacturing manifest units must be millimetres")
    for part in manifest.get("parts", []):
        path = GAME_ROOT / part["stl"]
        actual = stl_dimensions(path)
        expected = tuple(float(value) for value in part["dimensions"])
        if any(abs(got - wanted) > 0.05 for got, wanted in zip(actual, expected, strict=True)):
            raise ReleaseError(
                f"STL dimensions changed for {part['id']}: {actual!r} != {expected!r}"
            )
    declared_archives = {GAME_ROOT / relative for relative in manifest.get("p2s_3mf", [])}
    all_archives = set((ROOT / "hardware").rglob("*.3mf"))
    if not declared_archives.issubset(all_archives):
        raise ReleaseError("Manufacturing manifest references a missing 3MF archive")
    for path in sorted(all_archives):
        relative = path.relative_to(ROOT)
        try:
            with zipfile.ZipFile(path) as archive:
                corrupt = archive.testzip()
        except (OSError, zipfile.BadZipFile) as error:
            raise ReleaseError(f"Invalid 3MF archive: {relative}") from error
        if corrupt:
            raise ReleaseError(f"Corrupt member in {relative}: {corrupt}")


def verify_publishable_tree() -> None:
    files = candidate_files()
    forbidden_names = {".env", ".DS_Store"}
    forbidden_parts = {".local-data", "dist", "node_modules", "__pycache__"}
    forbidden_extensions = {".safetensors", ".parquet", ".mp4"}
    problems: list[str] = []

    for path in files:
        relative = path.relative_to(ROOT)
        if path.name in forbidden_names or forbidden_parts.intersection(relative.parts):
            problems.append(f"private/generated path: {relative}")
        if path.suffix.lower() in forbidden_extensions:
            problems.append(f"large artifact type: {relative}")
        if path.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"file exceeds 50 MiB: {relative}")
        if path.stat().st_size > 5 * 1024 * 1024:
            continue
        payload = path.read_bytes()
        if b"\0" in payload:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(payload):
                problems.append(f"possible {label}: {relative}")
        for label, pattern in FORBIDDEN_INTEGRATIONS.items():
            if pattern.search(payload):
                problems.append(f"{label}: {relative}")

    portable_paths = (
        ROOT / "config" / "ttt-hardware.example.json",
        ROOT / "scripts" / "run_ttt_recorded_rollout.zsh",
        ROOT / "scripts" / "return_ttt_arm_home.py",
        ROOT / "src" / "hashtag_robotics" / "ttt_strands_agent.py",
        ROOT / "TTT_STRANDS_AGENT.md",
    )
    local_home = b"/Users/" + b"macmert"
    physical_identifiers = {
        "developer home path": re.compile(re.escape(local_home)),
        "hard-coded macOS follower port": re.compile(rb"/dev/cu\.usbmodem[A-Za-z0-9]+"),
        "hard-coded AVFoundation UID": re.compile(rb"0x[0-9A-Fa-f]{12,}"),
    }
    for path in portable_paths:
        payload = path.read_bytes()
        for label, pattern in physical_identifiers.items():
            if pattern.search(payload):
                problems.append(f"{label}: {path.relative_to(ROOT)}")

    if problems:
        raise ReleaseError("Publishable-tree checks failed:\n- " + "\n- ".join(problems))


def main() -> int:
    checks = (
        ("required files", require_release_files),
        ("pinned dataset/model contract", verify_artifact_contract),
        ("manufacturing checksums", verify_checksums),
        ("STL dimensions and 3MF integrity", verify_manufacturing_manifest),
        ("secrets, local paths and file sizes", verify_publishable_tree),
    )
    try:
        for label, check in checks:
            check()
            print(f"PASS  {label}")
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"FAIL  malformed release contract: {error}", file=sys.stderr)
        return 1
    except ReleaseError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1
    print("WARN  Hugging Face dataset license metadata is currently NOASSERTION.")
    print("Public release contract passed; no network or hardware was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
