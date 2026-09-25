#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Wan MLX requires an Apple silicon Mac."
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Install Homebrew first: https://brew.sh"
  exit 1
fi
brew install python@3.11
PYTHON311="$(brew --prefix python@3.11)/bin/python3.11"
mkdir -p vendor
"$PYTHON311" -m venv vendor/mlx-video-env
vendor/mlx-video-env/bin/python -m pip install --upgrade pip
vendor/mlx-video-env/bin/python -m pip install 'git+https://github.com/Blaizzy/mlx-video.git' 'huggingface_hub[hf_xet]'
echo "Downloading Wan 2.2 TI2V 5B MLX Q8 weights (~20 GB). Keep at least 25 GB free."
vendor/mlx-video-env/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id="Anes1032/Wan2.2-TI2V-5B-mlx-q8", local_dir="vendor/wan2.2-ti2v-5b-mlx-q8")'
echo "Wan MLX installed. Restart Motion Studio; select Wan 2.2 · MLX and Preview."
