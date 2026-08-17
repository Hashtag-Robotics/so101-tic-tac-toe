#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$project_root"
.venv/bin/python scripts/verify_release.py
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/pytest -q
npm --prefix frontend run typecheck
bash scripts/build-package.sh

echo "All software-only verification gates passed."
