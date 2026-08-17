#!/usr/bin/env python3
"""Build the macOS AVFoundation unique-ID capture helper without opening a camera."""

from __future__ import annotations

import argparse
from pathlib import Path

from hashtag_robotics_ttt.macos_capture import MacOSCaptureError, ensure_avfoundation_uid_helper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(".local-data"),
        help="Local runtime directory (default: .local-data).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        helper = ensure_avfoundation_uid_helper(args.data_dir.expanduser().resolve())
    except MacOSCaptureError as error:
        raise SystemExit(f"Camera helper build failed: {error}") from error
    print(helper)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
