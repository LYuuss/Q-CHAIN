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
```

---

## Restart Behavior

Persistent storage means a node can restart without losing:

```text
known blocks
orphan blocks
side-branch fork blocks
pending mempool transactions
```

---

## Reorg Mempool Recovery

If a side branch becomes the main chain, QChain can recover valid non-coinbase transactions from disconnected old-chain blocks into the mempool.

The recovered mempool is persisted to:

```text
mempool.json
```

---

## Useful Commands

```bash
bash scripts/start_docker_testnet.sh
bash scripts/status_all.sh

python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
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
