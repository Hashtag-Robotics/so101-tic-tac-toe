from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lerobot.cameras.configs import CameraConfig, ColorMode, Cv2Rotation


@CameraConfig.register_subclass("avfoundation_uid")
@dataclass(kw_only=True)
class AVFoundationUIDCameraConfig(CameraConfig):
    """LeRobot camera selected by Apple's persistent AVCaptureDevice uniqueID."""

    unique_id: str
    helper_path: Path
    color_mode: ColorMode = ColorMode.RGB
    rotation: Cv2Rotation = Cv2Rotation.NO_ROTATION
    warmup_s: float = 1.0
    # Optional dashboard-only relay name. It does not change the dataset key;
    # the robot camera mapping remains the source of truth for that.
    preview_name: str | None = None

    def __post_init__(self) -> None:
        if not self.unique_id.strip():
            raise ValueError("AVFoundation camera unique_id cannot be empty.")
        self.helper_path = Path(self.helper_path)
        self.color_mode = ColorMode(self.color_mode)
        self.rotation = Cv2Rotation(self.rotation)
        safe_preview_name = (
            self.preview_name is None
            or self.preview_name.replace("_", "").replace("-", "").isalnum()
        )
        if not safe_preview_name:
            raise ValueError("AVFoundation preview_name contains unsafe characters.")
        if self.fps is None or self.width is None or self.height is None:
            raise ValueError("AVFoundation uniqueID cameras require fps, width and height.")
