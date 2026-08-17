#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$project_root"
.venv/bin/python scripts/check_english.py
.venv/bin/python scripts/verify_release.py
.venv/bin/ruff check src tests scripts agent.py
.venv/bin/ruff format --check src tests scripts agent.py
.venv/bin/pytest -q

build_dir="$(mktemp -d "${TMPDIR:-/tmp}/hashtag-ttt-build.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT
uv build --out-dir "$build_dir"
.venv/bin/python scripts/check_package.py "$build_dir"

echo "All software-only verification gates passed."
