#!/usr/bin/env python3
"""Print the native Strands Robots contract without touching hardware."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hashtag_robotics.ttt_strands_robots import inspect_strands_robots_runtime  # noqa: E402


def main() -> int:
    print(
        json.dumps(
            inspect_strands_robots_runtime(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
