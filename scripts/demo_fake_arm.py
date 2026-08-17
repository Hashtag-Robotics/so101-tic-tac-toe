"""Run the control plane against a fake SO-101 so the physical UI can be seen.

Two arms are faked at the pyserial layer, a generated clip stands in for a USB
camera, and `lerobot-calibrate` is replaced by a script that prints the real
range table and waits for ENTER, so the dashboard shows genuine parsed
telemetry instead of a mock.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import uvicorn

SCRATCH = Path(__file__).parent.parent / ".demo"
DATA_DIR = SCRATCH / "demo-state"
BIN_DIR = SCRATCH / "demo-bin"

FAKE_CALIBRATE = """#!{interpreter}
import sys, time

print("Connected to follower01.", flush=True)
print("-------------------------------------------", flush=True)
print("NAME            |    MIN |    POS |    MAX", flush=True)
print("shoulder_pan    |   1114 |   2000 |   3027", flush=True)
print("shoulder_lift   |    800 |   1900 |   3168", flush=True)
print("elbow_flex      |    955 |   2100 |   3168", flush=True)
print("wrist_flex      |    930 |   1500 |   3232", flush=True)
print("wrist_roll      |      0 |   2048 |   4095", flush=True)
print("gripper         |    209 |   1000 |   2100", flush=True)
sys.stdout.write("Move follower01 to the middle of its range of motion and press ENTER....")
sys.stdout.flush()
input()
time.sleep(30)
print("Calibration saved to follower01.json", flush=True)
"""


class FakePort:
    def __init__(self, device: str, serial_number: str, product: str) -> None:
        self.device = device
        self.vid = 0x1A86
        self.pid = 0x7523
        self.serial_number = serial_number
        self.manufacturer = "QinHeng Electronics"
        self.product = product
        self.description = product
        self.hwid = f"USB VID:PID=1A86:7523 SER={serial_number}"


PORTS = [
    FakePort("/dev/ttyACM0", "SO101FOLLOWER", "SO-101 Follower"),
    FakePort("/dev/ttyACM1", "SO101LEADER", "SO-101 Leader"),
]


def write_camera_clip(root: Path) -> None:
    """A moving pattern under a /dev/v4l/by-id style symlink."""
    import cv2
    import numpy

    root.mkdir(parents=True, exist_ok=True)
    clip = root / "front.avi"
    if not clip.is_file():
        writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 30, (640, 480))
        try:
            for index in range(300):
                frame = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
                frame[:, :] = (18, 24, 20)
                offset = (index * 6) % 600
                frame[180:300, offset : offset + 40] = (74, 243, 184)
                cv2.putText(
                    frame,
                    f"SO-101 FRONT  frame {index:03d}",
                    (18, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (232, 237, 232),
                    1,
                )
                writer.write(frame)
        finally:
            writer.release()

    link = root / "usb-SO101_Front_Camera_0001-video-index0"
    if not link.exists():
        link.symlink_to(clip)


def main() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    shim = BIN_DIR / "lerobot-calibrate"
    shim.write_text(FAKE_CALIBRATE.format(interpreter=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    os.environ["PATH"] = f"{BIN_DIR}{os.pathsep}{os.environ['PATH']}"

    camera_root = SCRATCH / "demo-cameras"
    write_camera_clip(camera_root)

    from hashtag_robotics.api import create_app
    from hashtag_robotics.config import Settings

    settings = Settings(
        data_dir=DATA_DIR,
        open_browser=False,
        enable_physical=True,
        port=8799,
        simulation_step_seconds=0.01,
    )
    with (
        patch("hashtag_robotics.discovery.list_ports.comports", lambda: list(PORTS)),
        patch("hashtag_robotics.discovery.CAMERA_BY_ID", camera_root),
    ):
        uvicorn.run(create_app(settings), host="127.0.0.1", port=8799, log_level="warning")


if __name__ == "__main__":
    main()
