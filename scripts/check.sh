#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ -x ".venv/bin/python" ]]; then
    python_bin=".venv/bin/python"
elif command -v python >/dev/null 2>&1; then
    python_bin="python"
else
    python_bin="python3"
fi

"$python_bin" app.py --help >/dev/null
"$python_bin" -m ruff format --check .
"$python_bin" -m ruff check .
"$python_bin" -m py_compile app.py src/youtube_study/*.py
"$python_bin" -m coverage erase
"$python_bin" -m coverage run -m pytest
"$python_bin" -m coverage combine
"$python_bin" -m coverage report
