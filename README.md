# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.  
The native coin is **QCOIN**.

QChain is an educational and research-oriented prototype exploring Proof-of-Work, distributed systems, persistent node storage, fork handling, reorg behavior, mempool recovery, and transaction indexing.

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
37 tests passing
```

---

## Persistent Node Storage

Each node stores its state in its own data directory.

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

Meaning:

```text
chain.json
    active main chain

block_index.json
    all known blocks by hash

orphan_blocks.json
    persisted orphan block pool

side_branch_blocks.json
    persisted side-branch fork pool

mempool.json
    persisted pending transactions

tx_index.json
    persisted confirmed transaction index
```

---

## Transaction Index

QChain now includes a persistent transaction index.

It allows the node to answer:

```text
GET /transactions/<tx_hash>
GET /addresses/<address>/transactions
```

The transaction lookup can return:

```text
confirmed transaction from tx_index.json
pending transaction from the mempool
404 if unknown
```

The address history endpoint returns both confirmed and pending transactions related to an address.

---

## Useful Node Endpoints

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

## Useful CLI Commands

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
```

---

## Tests

```bash
python3 -m pytest
```

Expected:

```text
37 passed
```

---

## Roadmap

```text
better explorer output
transaction index after deeper reorg scenarios
peer discovery
network protocol improvements
post-quantum signatures
ML-DSA integration
SLH-DSA integration
useful Proof-of-Work research
STARK-based privacy layer
whitepaper
```
