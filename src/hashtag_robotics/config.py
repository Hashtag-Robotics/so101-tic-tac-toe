from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HASHTAG_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Hashtag Robotics"
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    enable_physical: bool = False
    # Carries its provider: 'ollama:qwen2.5:7b', 'anthropic:claude-...'. A bare
    # string keeps Strands' own meaning, which is a Bedrock model id -- and that
    # is a trap on a machine with no AWS credentials, because naming a model
    # that is running locally then fails with an authentication error for a
    # service nobody mentioned.
    agent_model: str | None = None
    # Where a self-hosted planning model listens. Only read for providers that
    # have a host; the default is Ollama's.
    agent_model_host: str = "http://localhost:11434"
    # Passed to the provider as its own options bag. On this board the one that
    # matters is `{"num_gpu": 0}`: the Orin shares one pool between CPU and GPU,
    # and a browser plus an editor is enough that Ollama cannot allocate its
    # CUDA buffer. Answering slowly beats not answering.
    agent_model_options: dict[str, Any] = Field(default_factory=dict)
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".hashtag-robotics")
    frontend_dev_url: str | None = None
    simulation_step_seconds: float = 0.08
    # Point at a scene.xml to simulate a different arm; the mesh-accurate
    # SO-101 is found automatically when robot_descriptions has fetched it.
    simulation_model_path: Path | None = None
    max_job_seconds: int = 900
    input_min_interval_ms: int = 120
    default_max_relative_target: float = 10.0
    max_relative_target_ceiling: float = 30.0
    # A page that resolves its own domain to 127.0.0.1 would otherwise be
    # same-origin with this server, so the Host header is checked too.
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "::1"])

    @property
    def binds_to_loopback(self) -> bool:
        return self.host in {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"}

    @property
    def sim_live_frame_path(self) -> Path:
        """Where a running simulated session publishes what it is drawing.

        One path, not one per job: the leader is leased, so there is never more
        than one simulated session at a time.
        """
        return self.data_dir / "sim-live.jpg"

    @property
    def recording_live_root(self) -> Path:
        """Transient camera frames relayed by a physical recording process."""
        return self.data_dir / "recording-live"

    def recording_live_frame_path(self, job_id: str, camera_role: str) -> Path:
        """Resolve one job-scoped relay frame without accepting path segments."""
        safe = re.compile(r"^[A-Za-z0-9_-]+$")
        if not safe.fullmatch(job_id) or not safe.fullmatch(camera_role):
            raise ValueError("Recording live-frame identifiers contain unsafe characters.")
        return self.recording_live_root / job_id / f"{camera_role}.jpg"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def diagnostics_dir(self) -> Path:
        return self.data_dir / "diagnostics"

    @property
    def lerobot_home(self) -> Path:
        return self.data_dir / "lerobot-data"

    @property
    def calibration_dir(self) -> Path:
        return self.lerobot_home / "calibration"

    @property
    def calibration_archive_dir(self) -> Path:
        return self.data_dir / "calibration-archive"

    @property
    def policy_dir(self) -> Path:
        """Pinned Hugging Face policy snapshots managed by the control plane."""
        return self.data_dir / "policies"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        self.lerobot_home.mkdir(parents=True, exist_ok=True)
        self.calibration_archive_dir.mkdir(parents=True, exist_ok=True)
        self.policy_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
