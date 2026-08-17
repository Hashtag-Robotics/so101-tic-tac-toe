#!/usr/bin/env python3
"""Verify that the game wheel contains only the standalone tic-tac-toe package."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

PACKAGE = "hashtag_robotics_ttt"
DISTRIBUTION = "hashtag_robotics_tic_tac_toe"
REQUIRED = {
    f"{PACKAGE}/__init__.py",
    f"{PACKAGE}/ttt_checkpoint_sweep.json",
    f"{PACKAGE}/ttt_games_1_5_80k.json",
    f"{PACKAGE}/ttt_training_presets.json",
    f"{PACKAGE}/avfoundation_uid_capture.swift",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wheels = sorted(args.directory.glob(f"{DISTRIBUTION}-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected one {DISTRIBUTION} wheel, found {len(wheels)}.")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        missing = sorted(REQUIRED - names)
        if missing:
            raise SystemExit(f"Wheel is missing required files: {', '.join(missing)}")
        if any(name.startswith("hashtag_robotics/") or "/web/" in name for name in names):
            raise SystemExit("Wheel still contains the dashboard package or web assets.")
        init = archive.read(f"{PACKAGE}/__init__.py").decode()
    source_version = re.search(r'^__version__ = "([^"]+)"', init, re.M)
    wheel_version = wheel.name.split("-")[1]
    if source_version is None or source_version.group(1) != wheel_version:
        raise SystemExit("Wheel filename and runtime version do not match.")
    print(f"{wheel.name} contains the standalone tic-tac-toe runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
