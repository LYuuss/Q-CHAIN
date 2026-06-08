#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Stopping Docker testnet..."
docker compose down

echo "Removing Docker node data..."
rm -rf data/docker

echo "Rebuilding and starting Docker testnet..."
docker compose up -d --build

echo "Connecting Docker nodes..."
bash scripts/connect_docker_nodes.sh

echo
echo "QChain Docker testnet reset complete."
echo "Warning: previous Docker chain data and balances were deleted."
