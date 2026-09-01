#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall -q src tests
python3 -m pytest -q
git diff --check
