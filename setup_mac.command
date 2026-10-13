#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Motion Studio setup for macOS"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install it from https://brew.sh, then run this script again."
  read -r -p "Press Return to close…"
  exit 1
fi
brew install python@3.11
brew install cairo pango pkg-config ffmpeg node
PYTHON="$(brew --prefix python@3.11)/bin/python3.11"
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip wheel
.venv/bin/python -m pip install -r requirements.txt
chmod +x start.command setup_code_motion.command
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  ./setup_code_motion.command
else
  echo "For Code Motion: install/start Docker Desktop, then run setup_code_motion.command."
fi
echo
echo "Setup complete. Next, install/open Ollama and pull a small coding model, then double-click start.command."
read -r -p "Press Return to close…"
