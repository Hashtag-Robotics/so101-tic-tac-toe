from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_release_contract() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_release.py")],
        cwd=ROOT,
        check=True,
    )
