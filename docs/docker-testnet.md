# QChain Docker Testnet

QChain includes a Docker-based local testnet with three nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Inside Docker, nodes communicate through:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

---

## Persistent Node Files

Docker node data is stored under:

```text
data/docker/
```

Each node can persist:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

These files are protected by safer JSON storage utilities.

---

## Atomic Storage Behavior

QChain writes critical JSON files using a temporary file and atomic replacement.

This protects against partially written files when a node is interrupted during save operations.

---

## Useful Commands

```bash
bash scripts/start_docker_testnet.sh
bash scripts/status_all.sh

python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
python3 src/qchain.py node-sync 5001
```

---

## Stop

```bash
bash scripts/stop_docker_testnet.sh
```

or:

```bash
docker compose down
```

---

## Reset

```bash
bash scripts/reset_docker_testnet.sh
```
