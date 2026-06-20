# QChain Usage Guide

QChain can be used in two modes:

```text
local CLI mode
HTTP node mode
```

Local mode uses `data/chain.json`.

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
block_store_size
storage_path
block_store_path
orphan_blocks_path
side_branch_blocks_path
next_block_difficulty
peers
advertised_url
valid
```

---

## Node Block Lookup

```text
GET /blocks/<hash>
```

Possible locations:

```text
main_chain
orphan_pool
side_branch_pool
block_store
unknown
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

---

## Node Side Branches

```bash
python3 src/qchain.py node-side-branches 5001
```

Equivalent endpoint:

```text
GET /side-branches
```

---

## Node Sync

```bash
python3 src/qchain.py node-sync 5001
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

## Tests

```bash
python3 -m pytest
```

Expected:

```text
31 passed
```
