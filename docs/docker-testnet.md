# QChain Docker Testnet

QChain includes a Docker-based local testnet with three nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

---

## Persistent Node Files

Each Docker node can persist:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

---

## Inspect Transaction State

Pending transactions:

```bash
python3 src/qchain.py node-mempool 5001
```

Transaction by hash:

```bash
python3 src/qchain.py node-transaction 5001 <tx_hash>
```

Address history:

```bash
python3 src/qchain.py node-address-transactions 5001 <address>
```

---

## Restart Behavior

After restart, QChain keeps:

```text
known blocks
orphan blocks
side-branch blocks
pending transactions
confirmed transaction index
```

So these remain usable:

```text
GET /blocks/<hash>
GET /mempool
GET /transactions/<tx_hash>
GET /addresses/<address>/transactions
GET /orphans
GET /side-branches
```

---

## Reorg Behavior

If a side branch becomes the main chain:

```text
tx_index.json is rebuilt from the new main chain
valid disconnected transactions can return to mempool.json
```

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
