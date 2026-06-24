# QChain Usage Guide

## Node Status

```bash
python3 src/qchain.py node-status 5001
```

Status includes:

```text
height
latest_hash
genesis_hash
cumulative_work
mempool_size
orphan_pool_size
side_branch_pool_size
block_store_size
mempool_path
block_store_path
orphan_blocks_path
side_branch_blocks_path
valid
```

---

## Node Mempool

```bash
python3 src/qchain.py node-mempool 5001
```

The mempool is persisted in:

```text
mempool.json
```

Pending transactions survive node restart and are removed after mining.

---

## Node Sync

```bash
python3 src/qchain.py node-sync 5001
```

If a sync triggers a reorg, QChain can recover disconnected transactions into the mempool.

The sync response can include:

```text
mempool_recovery_results
```

---

## Inspect Fork State

```bash
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
```

---

## Complete Example

```bash
bash scripts/start_docker_testnet.sh

python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mine 5002 miner

python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-side-branches 5001
```

---

## Tests

```bash
python3 -m pytest
```

Expected:

```text
34 passed
```
