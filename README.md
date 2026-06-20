# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg)

QChain is an experimental Proof-of-Work blockchain built from scratch in Python. The native coin is **QCOIN**.

QChain is designed as an educational and research-oriented blockchain prototype. Its long-term direction is to explore post-quantum cryptography, useful Proof-of-Work, distributed systems, and privacy mechanisms such as STARKs.

QChain is not production-ready and must not be used with real funds.

---

## Current Status

QChain currently supports:

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
persistent chain storage
HTTP nodes
block broadcasting
transaction broadcasting
node synchronization
heaviest-chain rule
orphan block pool
side-branch fork management
automatic reorganization when a side branch becomes heavier
header-first synchronization
block lookup by hash
Docker-based 3-node local testnet
CLI tools
pytest test suite
GitHub Actions CI
```

Current test suite:

```text
25 tests passing
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

## CLI Commands

Local commands:

```bash
python3 src/qchain.py status
python3 src/qchain.py wallets
python3 src/qchain.py balance alice
python3 src/qchain.py mine alice
python3 src/qchain.py send alice bob 10 --fee 2
python3 src/qchain.py mempool
python3 src/qchain.py validate
```

HTTP node commands:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-sync 5001
python3 src/qchain.py node-connect 5001 5002
```

---

## Tests

```bash
python3 -m pytest
```

Expected current result:

```text
25 passed
```

---

## Documentation

Detailed documentation:

```text
docs/core-concepts.md
docs/usage.md
docs/docker-testnet.md
```

---

## Roadmap

```text
side-branch persistence
orphan pool persistence
better reorg diagnostics
peer discovery
post-quantum signatures
ML-DSA integration
SLH-DSA integration
useful Proof-of-Work research
STARK-based privacy layer
whitepaper
```
