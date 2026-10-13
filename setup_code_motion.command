#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v node >/dev/null 2>&1; then
  echo "Installing Node.js with Homebrew…"
  brew install node
fi
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) throw Error("Node.js 22 or newer required")'
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Install and start Docker Desktop (https://www.docker.com/products/docker-desktop/), then run this script again."
  exit 1
fi
npm ci --prefix code-motion
npm test --prefix code-motion
docker build -t motion-studio-remotion:1 code-motion
echo "Code Motion ready. Choose ChatGPT subscription and sign in, or set OPENAI_API_KEY and OPENAI_MODEL for API use, then launch Motion Studio."
