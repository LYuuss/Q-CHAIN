# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.  
The native coin is **QCOIN**.

QChain explores Proof-of-Work, distributed systems, persistent node storage, fork handling, reorg behavior, mempool recovery, transaction indexing, and safer local JSON storage.

QChain is not production-ready and must not be used with real funds.

---

## Current Status

```text
Proof-of-Work mining
dynamic difficulty adjustment
block headers
Merkle roots
signed transactions
encrypted wallets
balances and nonces
transaction fees
persistent mempool
persistent block index
persistent orphan pool
persistent side-branch pool
persistent transaction index
atomic JSON storage
safe JSON reads
HTTP nodes
header-first synchronization
heaviest-chain rule
side-branch fork management
automatic reorganization
mempool transaction recovery after reorg
transaction lookup by hash
address transaction history
Docker-based 3-node local testnet
GitHub Actions CI
```

Current test suite:

```text
46 tests passing
```

---

## Persistent Node Storage

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

## Atomic JSON Storage

QChain uses safer JSON storage utilities:

```text
atomic_write_json(path, data)
read_json_or_default(path, default)
```

`atomic_write_json` writes to a temporary file first, flushes it, then replaces the target file atomically.

This avoids leaving a partially written JSON file if the node is interrupted during a save.

`read_json_or_default` safely loads JSON and returns a default value when the file is missing or malformed.

Protected files:

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

## Useful Endpoints

```text
GET  /status
GET  /chain
GET  /headers
GET  /blocks/<hash>
GET  /transactions/<tx_hash>
GET  /addresses/<address>/transactions
GET  /mempool
GET  /orphans
GET  /side-branches
GET  /balances/<address>
GET  /peers

POST /transactions
POST /blocks
POST /mine
POST /peers
POST /sync
```

---

## Tests

```bash
python3 -m pytest
```

Expected:

```text
46 passed
```

---

## Roadmap

```text
atomic wallet storage
peer discovery
better explorer output
network protocol improvements
post-quantum signatures
useful Proof-of-Work research
whitepaper
```
