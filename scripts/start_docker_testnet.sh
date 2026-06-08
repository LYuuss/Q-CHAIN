#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose up -d --build

bash scripts/connect_docker_nodes.sh

echo
echo "QChain Docker testnet started."
echo "Nodes:"
echo "- node1: http://127.0.0.1:5001"
echo "- node2: http://127.0.0.1:5002"
echo "- node3: http://127.0.0.1:5003"
