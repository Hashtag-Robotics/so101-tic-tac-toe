"""A build gate is only worth having if it fails when it should.

The old one asked whether `web/index.html` was in the wheel. It always is, so
it stayed green through two rounds of changes that never reached the wheel and
a version string that kept claiming 0.1.0. These tests make the new gate prove
it can go red -- each one builds a wheel that is wrong in exactly one way.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_wheel import find_wheels, inspect, source_version  # noqa: E402

import hashtag_robotics  # noqa: E402

INDEX_HTML = """<!doctype html>
<html>
  <head><link rel="stylesheet" href="/assets/index-abc.css"></head>
  <body><script type="module" src="/assets/index-abc.js"></script></body>
</html>
"""


@pytest.fixture
def source_tree(tmp_path: Path) -> Path:
    """A miniature src/hashtag_robotics to build fake wheels against."""
    root = tmp_path / "src" / "hashtag_robotics"
    (root / "web" / "assets").mkdir(parents=True)
    (root / "__init__.py").write_text('__version__ = "0.2.0"\n')
    (root / "safety.py").write_text("def stop() -> None: ...\n")
    (root / "identify.py").write_text("def identify() -> None: ...\n")
    return root


def build_wheel(
    tmp_path: Path,
    source_root: Path,
    *,
    name: str = "hashtag_robotics-0.2.0-py3-none-any.whl",
    skip: set[str] | None = None,
    rewrite: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
    assets: tuple[str, ...] = ("index-abc.css", "index-abc.js"),
) -> Path:
    skip = skip or set()
    rewrite = rewrite or {}
    wheel = tmp_path / name
    with zipfile.ZipFile(wheel, "w") as archive:
        for path in sorted(source_root.rglob("*.py")):
            relative = path.relative_to(source_root).as_posix()
            if relative in skip:
                continue
            archive.writestr(
                f"hashtag_robotics/{relative}",
                rewrite.get(relative, path.read_text()),
            )
        archive.writestr("hashtag_robotics/web/index.html", INDEX_HTML)
        for asset in assets:
            archive.writestr(f"hashtag_robotics/web/assets/{asset}", "/* built */")
        for extra_name, body in (extra or {}).items():
            archive.writestr(extra_name, body)
    return wheel


def test_a_wheel_that_matches_the_tree_passes(tmp_path: Path, source_tree: Path) -> None:
    report = inspect(build_wheel(tmp_path, source_tree), source_tree)

    assert report.ok, report.problems
    assert report.modules_checked == 3
    assert report.assets_checked == 2


def test_a_module_that_never_reached_the_wheel_is_caught(
    tmp_path: Path,
    source_tree: Path,
) -> None:
    """This is the failure that actually shipped: identify.py was never in the wheel."""
    report = inspect(build_wheel(tmp_path, source_tree, skip={"identify.py"}), source_tree)

    assert not report.ok
    assert any("missing from the wheel" in problem for problem in report.problems)
    assert any("identify.py" in problem for problem in report.problems)


def test_a_module_whose_bytes_drifted_is_caught(tmp_path: Path, source_tree: Path) -> None:
    wheel = build_wheel(tmp_path, source_tree, rewrite={"safety.py": "def stop(): pass\n"})

    report = inspect(wheel, source_tree)

    assert not report.ok
    assert any("stale in the wheel" in problem for problem in report.problems)


def test_a_version_the_filename_does_not_back_up_is_caught(
    tmp_path: Path,
    source_tree: Path,
) -> None:
    """The shipped wheel kept the name 0.1.0 while the code moved on."""
    wheel = build_wheel(
        tmp_path,
        source_tree,
        name="hashtag_robotics-0.1.0-py3-none-any.whl",
    )

    report = inspect(wheel, source_tree)

    assert not report.ok
    assert any("the source says 0.2.0" in problem for problem in report.problems)


def test_a_wheel_that_reports_a_different_version_at_runtime_is_caught(
    tmp_path: Path,
    source_tree: Path,
) -> None:
    wheel = build_wheel(
        tmp_path,
        source_tree,
        rewrite={"__init__.py": '__version__ = "0.1.0"\n'},
    )

    report = inspect(wheel, source_tree)

    assert not report.ok
    assert any("reports 0.1.0 at runtime" in problem for problem in report.problems)


def test_a_dashboard_pointing_at_an_absent_asset_is_caught(
    tmp_path: Path,
    source_tree: Path,
) -> None:
    """The old assets were deleted from the tree while the wheel still shipped them."""
    wheel = build_wheel(tmp_path, source_tree, assets=("index-abc.css",))

    report = inspect(wheel, source_tree)

    assert not report.ok
    assert any("index-abc.js" in problem for problem in report.problems)


def test_a_module_the_wheel_invented_is_caught(tmp_path: Path, source_tree: Path) -> None:
    wheel = build_wheel(
        tmp_path,
        source_tree,
        extra={"hashtag_robotics/ghost.py": "# left over from an older tree\n"},
    )

    report = inspect(wheel, source_tree)

    assert not report.ok
    assert any("not in the source tree" in problem for problem in report.problems)


def test_two_wheels_in_dist_are_refused(tmp_path: Path, source_tree: Path) -> None:
    """`uv pip install dist/*.whl` installs both, and which one wins is luck."""
    build_wheel(tmp_path, source_tree)
    build_wheel(tmp_path, source_tree, name="hashtag_robotics-0.1.0-py3-none-any.whl")

    assert len(find_wheels(tmp_path)) == 2


def test_the_real_package_has_one_version_not_two() -> None:
    """pyproject reads the version from __init__, so these cannot drift apart."""
    root = Path(hashtag_robotics.__file__).parent

    assert source_version(root / "__init__.py") == hashtag_robotics.__version__
