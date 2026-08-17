#!/usr/bin/env python3
"""Refuse to ship a wheel that disagrees with the tree it was supposedly built from.

The old gate asked one question -- "is `web/index.html` in the wheel?" -- and
`index.html` is always in the wheel, so the gate was always green. It stayed
green while two whole modules were added and never shipped, and while the
version string kept saying 0.1.0. A wheel like that is worse than no wheel:
installing it silently reverts the machine to an older program under the same
name.

So this asks the three questions that would have caught it:

  1. Does the wheel contain every module in the source tree, byte for byte?
  2. Does its version match what the package will report at runtime?
  3. Does the dashboard it carries reference only assets it also carries?

Usable as a script (`python scripts/check_wheel.py`) or as a library; the tests
use the functions directly.
"""

from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = "hashtag_robotics"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "src" / PACKAGE

# src/hashtag_robotics/web/index.html loads its bundle with plain
# <script src="..."> / <link href="..."> tags; anything starting with a scheme
# is somebody else's problem.
ASSET_REFERENCE = re.compile(r'(?:src|href)="(?P<path>[^"]+)"')


@dataclass
class WheelReport:
    wheel: Path
    version: str = ""
    modules_checked: int = 0
    assets_checked: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_version(init_path: Path) -> str:
    match = re.search(r'^__version__ = "(?P<version>[^"]+)"', init_path.read_text(), re.M)
    if match is None:
        raise ValueError(f"No __version__ found in {init_path}")
    return match.group("version")


def wheel_version(wheel: Path) -> str:
    """`hashtag_robotics-0.2.0-py3-none-any.whl` -> `0.2.0`."""
    return wheel.name.split("-")[1]


def check_modules(archive: zipfile.ZipFile, source_root: Path, report: WheelReport) -> None:
    """Every .py in the source tree must be in the wheel with the same bytes."""
    shipped = {name for name in archive.namelist() if name.endswith(".py")}
    for path in sorted(source_root.rglob("*.py")):
        name = f"{PACKAGE}/{path.relative_to(source_root).as_posix()}"
        if name not in shipped:
            report.problems.append(f"missing from the wheel: {name}")
            continue
        shipped.discard(name)
        if digest(archive.read(name)) != digest(path.read_bytes()):
            report.problems.append(f"stale in the wheel: {name} differs from the source tree")
        report.modules_checked += 1
    for orphan in sorted(shipped):
        report.problems.append(f"in the wheel but not in the source tree: {orphan}")


def check_version(
    archive: zipfile.ZipFile,
    wheel: Path,
    expected: str,
    report: WheelReport,
) -> None:
    report.version = wheel_version(wheel)
    if report.version != expected:
        report.problems.append(
            f"the wheel is named {report.version} but the source says {expected}"
        )
    init = f"{PACKAGE}/__init__.py"
    if init in archive.namelist():
        shipped = re.search(r'__version__ = "([^"]+)"', archive.read(init).decode())
        if shipped and shipped.group(1) != report.version:
            report.problems.append(
                f"the wheel is named {report.version} but reports {shipped.group(1)} at runtime"
            )


def check_dashboard(archive: zipfile.ZipFile, report: WheelReport) -> None:
    """The built dashboard must not reference an asset the wheel does not carry."""
    index = f"{PACKAGE}/web/index.html"
    contents = set(archive.namelist())
    if index not in contents:
        report.problems.append(f"missing from the wheel: {index}")
        return
    for match in ASSET_REFERENCE.finditer(archive.read(index).decode()):
        reference = match.group("path")
        if "://" in reference or reference.startswith("data:"):
            continue
        name = f"{PACKAGE}/web/{reference.lstrip('/')}"
        report.assets_checked += 1
        if name not in contents:
            report.problems.append(f"the dashboard loads {reference}, which is not in the wheel")


def inspect(wheel: Path, source_root: Path = SOURCE_ROOT) -> WheelReport:
    report = WheelReport(wheel=wheel)
    with zipfile.ZipFile(wheel) as archive:
        check_version(archive, wheel, source_version(source_root / "__init__.py"), report)
        check_modules(archive, source_root, report)
        check_dashboard(archive, report)
    return report


def find_wheels(dist: Path) -> list[Path]:
    return sorted(dist.glob("hashtag_robotics-*.whl"))


def main() -> int:
    dist = PROJECT_ROOT / "dist"
    wheels = find_wheels(dist)
    if not wheels:
        print(f"No wheel in {dist}.", file=sys.stderr)
        return 1
    if len(wheels) > 1:
        # Two wheels means `uv pip install dist/*.whl` installs both, and which
        # one wins is alphabetical luck.
        names = ", ".join(wheel.name for wheel in wheels)
        print(f"More than one wheel in {dist}: {names}. Clean it first.", file=sys.stderr)
        return 1

    report = inspect(wheels[0])
    if not report.ok:
        print(f"{report.wheel.name} does not match the source tree:", file=sys.stderr)
        for problem in report.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        f"{report.wheel.name} matches the source tree "
        f"({report.modules_checked} modules, {report.assets_checked} dashboard assets)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
