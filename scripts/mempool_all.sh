#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

for port in 5001 5002 5003; do
  echo
  echo "=============================="
  echo "Node ${port} mempool"
  echo "=============================="
  python3 src/qchain.py node-mempool "${port}"
done
