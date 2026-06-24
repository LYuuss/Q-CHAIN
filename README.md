# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.  
The native coin is **QCOIN**.

QChain is an educational and research-oriented prototype exploring Proof-of-Work, distributed systems, persistent node storage, fork handling, reorg behavior, and future post-quantum cryptography directions.

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
HTTP nodes
header-first synchronization
heaviest-chain rule
side-branch fork management
automatic reorganization
mempool transaction recovery after reorg
Docker-based 3-node local testnet
GitHub Actions CI
```

QChain now includes persistent storage for known blocks, orphan blocks, side branches, and mempool transactions.

Current test suite:

```text
34 tests passing
```

Persistent files used by a node:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
```


---

## Reorg Mempool Recovery

When QChain reorganizes from an old main chain to a heavier side chain, transactions from disconnected old-chain blocks can become unconfirmed.

QChain now tries to recover those transactions into the mempool when they are:

```text
non-coinbase
not included in the new main chain
not already in the mempool
still valid after the reorg
```

The recovered mempool is saved to:

```text
mempool.json
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
python3 src/qchain.py node-mempool 5001
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
34 passed
```
