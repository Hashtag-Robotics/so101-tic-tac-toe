#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$project_root"
npm --prefix frontend run build

# A previous build's wheel is not overwritten when the version changes, and two
# wheels in dist/ means `uv pip install dist/*.whl` installs both.
rm -rf dist
uv build

python_bin="${PYTHON:-}"
if [[ -z "$python_bin" ]]; then
  if [[ -x .venv/bin/python ]]; then python_bin=.venv/bin/python; else python_bin=python3; fi
fi

# Checks the wheel against the tree it claims to come from: every module byte
# for byte, the version, and the assets the dashboard actually loads.
"$python_bin" scripts/check_wheel.py

wheel_path="$(find dist -maxdepth 1 -name 'hashtag_robotics-*.whl' -print -quit)"
echo "Package ready: $wheel_path"
