#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This optional backend requires an Apple silicon Mac."
  exit 1
fi
mkdir -p vendor
if [[ ! -f vendor/LTX-Video/inference.py ]]; then
  git clone https://github.com/Lightricks/LTX-Video.git vendor/LTX-Video
fi
cd vendor/LTX-Video
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install 'torch>=2.6' 'torchvision>=0.21'
.venv/bin/python -m pip install -e '.[inference]'
echo "LTX 2B backend installed. Model weights download on the first render."
echo "Restart Motion Studio with start.command and check the backend status."
