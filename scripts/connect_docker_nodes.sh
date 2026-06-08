#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

wait_node() {
  local port="$1"

  echo "Waiting for node on port ${port}..."

  for _ in {1..30}; do
    if curl -fsS "http://127.0.0.1:${port}/status" > /dev/null; then
      echo "Node ${port} is ready."
      return 0
    fi

    sleep 1
  done

  echo "Node ${port} is not ready."
  exit 1
}

add_peer() {
  local from_port="$1"
  local peer_url="$2"

  echo
  echo "Connecting node ${from_port} -> ${peer_url}"

  curl -fsS -X POST "http://127.0.0.1:${from_port}/peers" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"${peer_url}\"}"

  echo
}

wait_node 5001
wait_node 5002
wait_node 5003

add_peer 5001 "http://node2:5000"
add_peer 5001 "http://node3:5000"

add_peer 5002 "http://node1:5000"
add_peer 5002 "http://node3:5000"

add_peer 5003 "http://node1:5000"
add_peer 5003 "http://node2:5000"

echo
echo "Docker nodes connected successfully."
