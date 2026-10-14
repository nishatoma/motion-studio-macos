#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python code_motion_setup.py
fi
exec python3 code_motion_setup.py
