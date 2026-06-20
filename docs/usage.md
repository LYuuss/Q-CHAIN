# QChain Usage Guide

QChain can be used in two modes:

```text
local CLI mode
HTTP node mode
```

Local mode uses:

```text
data/chain.json
```

HTTP node mode communicates with a running node, for example:

```text
http://127.0.0.1:5001
```

---

## Create Wallets

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

---

## Local Commands

```bash
python3 src/qchain.py status
python3 src/qchain.py wallets
python3 src/qchain.py balance alice
python3 src/qchain.py mine alice
python3 src/qchain.py send alice bob 10 --fee 2
python3 src/qchain.py mempool
python3 src/qchain.py validate
```

---

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
next_block_difficulty
peers
advertised_url
valid
```

---

## Node Headers

```bash
python3 src/qchain.py node-headers 5001
```

Equivalent endpoint:

```text
GET /headers
```

---

## Node Orphans

```bash
python3 src/qchain.py node-orphans 5001
```

Equivalent endpoint:

```text
GET /orphans
```

Normal result:

```json
{
  "blocks": [],
  "max_size": 100,
  "size": 0
}
```

---

## Node Side Branches

```bash
python3 src/qchain.py node-side-branches 5001
```

Equivalent endpoint:

```text
GET /side-branches
```

Normal result:

```json
{
  "blocks": [],
  "max_size": 200,
  "size": 0,
  "tip_hashes": []
}
```

This is useful for debugging forks and reorg behavior.

---

## Node Balance

```bash
python3 src/qchain.py node-balance 5001 bob
```

---

## Node Mining

```bash
python3 src/qchain.py node-mine 5001 alice
```

With a transaction limit:

```bash
python3 src/qchain.py node-mine 5001 miner --max-tx 5
```

---

## Node Send

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

The command signs a transaction locally, sends it to the node, and the node broadcasts it to peers.

---

## Node Mempool

```bash
python3 src/qchain.py node-mempool 5001
```

---

## Node Sync

```bash
python3 src/qchain.py node-sync 5001
```

The node:

```text
checks peer status
compares cumulative work
downloads headers
validates headers
finds common ancestor
downloads only missing blocks
validates candidate chain
adopts if heavier
processes orphan blocks
processes side branches
```

If already up to date:

```json
{
  "downloaded_block_count": 0
}
```

---

## Complete Example

```bash
bash scripts/start_docker_testnet.sh

python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mine 5002 miner

python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-balance 5001 miner

python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
```

---

## Local Balance vs Node Balance

This checks the local CLI chain:

```bash
python3 src/qchain.py balance bob
```

This checks a running node:

```bash
python3 src/qchain.py node-balance 5001 bob
```

When testing Docker, use `node-balance`.

---

## Tests

```bash
python3 -m pytest
```

Expected result:

```text
25 passed
```
