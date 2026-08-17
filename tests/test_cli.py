from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

import hashtag_robotics.cli as cli_module


def frontend_checkout(tmp_path: Path) -> Path:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"scripts":{"build":"vite build"}}')
    return frontend


def test_source_checkout_builds_dashboard_before_serving(tmp_path: Path, monkeypatch) -> None:
    frontend = frontend_checkout(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/usr/local/bin/npm")

    def fake_run(command, *, cwd, check):
        calls.append((command, cwd))
        assert check is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    assert cli_module._build_dashboard_from_checkout(tmp_path) is True
    assert calls == [(["/usr/local/bin/npm", "--prefix", str(frontend), "run", "build"], tmp_path)]


def test_installed_package_does_not_require_frontend_toolchain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cli_module.shutil,
        "which",
        lambda _name: pytest.fail("npm lookup should not run without frontend source"),
    )

    assert cli_module._build_dashboard_from_checkout(tmp_path) is False


def test_failed_checkout_build_refuses_to_serve_stale_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    frontend_checkout(tmp_path)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/usr/local/bin/npm")
    monkeypatch.setattr(
        cli_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1),
    )

    with pytest.raises(typer.Exit) as refusal:
        cli_module._build_dashboard_from_checkout(tmp_path)

    assert refusal.value.exit_code == 2
