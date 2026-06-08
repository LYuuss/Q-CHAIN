#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$#" -ne 1 ]; then
  echo "Usage: bash scripts/balance_all.sh <wallet_name>"
  echo "Example: bash scripts/balance_all.sh bob"
  exit 1
fi

wallet="$1"

for port in 5001 5002 5003; do
  echo
  echo "=============================="
  echo "Node ${port} balance for ${wallet}"
  echo "=============================="
  python3 src/qchain.py node-balance "${port}" "${wallet}"
done
