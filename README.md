# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.
The native coin is **QCOIN**.

QChain is designed as an educational and research-oriented blockchain prototype.
It explores Proof-of-Work, distributed systems, fork handling, persistent node storage, and future post-quantum cryptography directions.

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
replay protection
mining rewards and transaction fees
mempool
fee-aware transaction selection
persistent main chain storage
persistent block index
persistent orphan block pool
persistent side-branch block pool
HTTP nodes
block broadcasting
transaction broadcasting
header-first synchronization
heaviest-chain rule
orphan block pool
side-branch fork management
automatic reorganization
Docker-based 3-node local testnet
pytest test suite
GitHub Actions CI
```

Current test suite:

```text
31 tests passing
```

---

## Storage Layer

Each node stores its state in its own data directory.

Example:

```text
data/nodes/node_5001/
├── chain.json
├── peers.json
├── block_index.json
├── orphan_blocks.json
└── side_branch_blocks.json
```

Meaning:

```text
chain.json
    active main chain

peers.json
    known peers

block_index.json
    all known blocks by hash

orphan_blocks.json
    persisted orphan block pool

side_branch_blocks.json
    persisted side-branch fork pool
```

---

## Useful Node Endpoints

```text
GET  /status
GET  /chain
GET  /headers
GET  /blocks/<hash>
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

## Quick Start

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner

bash scripts/start_docker_testnet.sh

python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mine 5002 miner

python3 src/qchain.py node-status 5001
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

---

## Documentation

```text
docs/core-concepts.md
docs/usage.md
docs/docker-testnet.md
```

---

## Roadmap

```text
persistent mempool
better reorg diagnostics
peer discovery
network protocol improvements
post-quantum signatures
ML-DSA integration
SLH-DSA integration
useful Proof-of-Work research
STARK-based privacy layer
whitepaper
```
