#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Run setup_mac.command first."
  read -r -p "Press Return to close…"
  exit 1
fi
.venv/bin/python app.py
