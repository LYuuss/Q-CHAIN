# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.

The native coin of the network is **QCOIN**.

QChain is designed as an educational and research-oriented blockchain prototype. It explores Proof-of-Work, signed transactions, encrypted wallets, distributed nodes, persistent storage, fork handling, reorganization behavior, transaction indexing, and safer local JSON storage.

QChain is not production-ready and must not be used with real funds.

---

## Current Version

```text
v0.2.2-alpha
```

Current test suite:

```text
50 tests passing
```

---

## Current Features

```text
Proof-of-Work mining
dynamic difficulty adjustment
block headers
Merkle roots
signed transactions
encrypted wallets
wallet password protection
balances and nonces
replay protection
transaction fees
mining rewards
fee-aware mempool selection
persistent mempool
persistent block index
persistent orphan block pool
persistent side-branch block pool
persistent transaction index
atomic JSON storage
atomic wallet storage
safe JSON reads
HTTP nodes
Docker-based 3-node local testnet
peer connections
block broadcasting
transaction broadcasting
header-first synchronization
heaviest-chain rule
orphan handling
side-branch fork management
automatic reorganization
mempool transaction recovery after reorg
transaction lookup by hash
address transaction history
GitHub Actions CI
pytest test suite
```

---

## Repository Structure

```text
Q-CHAIN/
├── src/
│   ├── block.py
│   ├── blockchain.py
│   ├── block_store.py
│   ├── config.py
│   ├── crypto_provider.py
│   ├── node.py
│   ├── qchain.py
│   ├── storage_utils.py
│   ├── transaction.py
│   ├── transaction_index.py
│   └── wallet.py
├── tests/
├── docs/
├── scripts/
├── data/
├── Dockerfile
├── docker-compose.yml
├── README.md
└── .github/workflows/tests.yml
```

---

## Persistent Storage

Each node stores its state in JSON files.

Typical node files:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

Wallet files:

```text
data/wallets/*.json
```

QChain uses atomic JSON writes for critical storage files to reduce the risk of corrupted partial writes.

---

## Quick Start

Create wallets:

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

Start the Docker testnet:

```bash
bash scripts/start_docker_testnet.sh
```

Mine and send QCOIN:

```bash
python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mine 5002 miner
```

Inspect state:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-address-transactions 5001 <bob_address>
```

---

## Useful CLI Commands

```bash
python3 src/qchain.py status
python3 src/qchain.py wallets
python3 src/qchain.py wallet-create alice
python3 src/qchain.py balance alice
python3 src/qchain.py mine alice
python3 src/qchain.py send alice bob 10 --fee 2
python3 src/qchain.py mempool
python3 src/qchain.py validate
```

Node commands:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-chain 5001
python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
python3 src/qchain.py node-balance 5001 <address>
python3 src/qchain.py node-mine 5001 miner
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-sync 5001
```

---

## HTTP API Overview

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

See:

```text
docs/api-reference.md
```

---

## Documentation

```text
docs/core-concepts.md
docs/usage.md
docs/docker-testnet.md
docs/api-reference.md
docs/storage-layer.md
docs/roadmap.md
```

---

## Tests

Run:

```bash
python3 -m pytest
```

Expected:

```text
50 passed
```

---

## Versioning Strategy

Recommended branch model:

```text
main       stable public branch
dev/v0.2   active v0.2 development branch
tags       frozen release snapshots
```

Recommended alpha tag:

```bash
git tag -a v0.2.2-alpha -m "QChain v0.2.2-alpha"
git push origin v0.2.2-alpha
```

---

## Security Warning

QChain is experimental software.

Do not use it with real funds, private production keys, or production workloads.
