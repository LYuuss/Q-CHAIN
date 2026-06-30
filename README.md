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
atomic wallet storage
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
50 tests passing
```

---

## Persistent Storage

Node files:

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

---

## Atomic Wallet Storage

Wallet files are now written atomically.

This protects encrypted wallet files from being left in a corrupted half-written state during save operations.

QChain does not silently recreate an empty wallet when a wallet file is missing or invalid. Instead, wallet loading fails explicitly.

This is intentional because wallet files may contain encrypted private keys and must not be replaced silently.

---

## Protected Files

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
data/wallets/*.json
```

---

## Tests

```bash
python3 -m pytest
```

Expected:

```text
50 passed
```

---

## Roadmap

```text
peer discovery
better explorer output
network protocol improvements
post-quantum signatures
useful Proof-of-Work research
whitepaper
```
