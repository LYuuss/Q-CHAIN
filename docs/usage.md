# QChain Usage Guide

This guide explains how to use QChain from the command line.

---

## Requirements

Recommended environment:

```text
Python 3.11+
Docker Desktop
pytest
```

Install dependencies according to the project requirements.

---

## Run Tests

```bash
python3 -m pytest
```

Expected:

```text
50 passed
```

---

## Wallet Commands

Create wallets:

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

List wallets:

```bash
python3 src/qchain.py wallets
```

Wallet files are stored under:

```text
data/wallets/
```

Wallet files are encrypted and written atomically.

---

## Local Blockchain Commands

Show status:

```bash
python3 src/qchain.py status
```

Mine locally:

```bash
python3 src/qchain.py mine alice
```

Send locally:

```bash
python3 src/qchain.py send alice bob 10 --fee 2
```

Show balance:

```bash
python3 src/qchain.py balance bob
```

Show mempool:

```bash
python3 src/qchain.py mempool
```

Validate chain:

```bash
python3 src/qchain.py validate
```

---

## Docker Testnet

Start:

```bash
bash scripts/start_docker_testnet.sh
```

Stop:

```bash
bash scripts/stop_docker_testnet.sh
```

Reset Docker node state:

```bash
bash scripts/reset_docker_testnet.sh
```

---

## Node Status

```bash
python3 src/qchain.py node-status 5001
```

Status can include:

```text
height
latest_hash
genesis_hash
cumulative_work
mempool_size
orphan_pool_size
side_branch_pool_size
block_store_size
transaction_index_size
storage_path
block_store_path
orphan_blocks_path
side_branch_blocks_path
mempool_path
transaction_index_path
next_block_difficulty
peers
advertised_url
valid
```

---

## Node Mining

```bash
python3 src/qchain.py node-mine 5001 alice
```

This asks node `5001` to mine a block for Alice.

---

## Node Transactions

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

This creates, signs, and broadcasts a transaction through node `5001`.

---

## Mempool

```bash
python3 src/qchain.py node-mempool 5001
```

The mempool is persisted in:

```text
mempool.json
```

---

## Transaction Lookup

```bash
python3 src/qchain.py node-transaction 5001 <tx_hash>
```

The node checks:

```text
mempool first
tx_index.json second
```

Possible locations:

```text
mempool
confirmed
```

---

## Address Transaction History

```bash
python3 src/qchain.py node-address-transactions 5001 <address>
```

The response includes:

```text
count
confirmed_count
pending_count
transactions
```

---

## Balance Lookup

```bash
python3 src/qchain.py node-balance 5001 <address>
```

---

## Orphan Pool

```bash
python3 src/qchain.py node-orphans 5001
```

This inspects:

```text
orphan_blocks.json
```

---

## Side Branch Pool

```bash
python3 src/qchain.py node-side-branches 5001
```

This inspects:

```text
side_branch_blocks.json
```

---

## Header-First Sync

```bash
python3 src/qchain.py node-sync 5001
```

If already synchronized, the response can include:

```text
downloaded_block_count = 0
```

If a sync triggers a reorg, the response can include:

```text
mempool_recovery_results
```

---

## Suggested Development Workflow

```bash
git checkout dev/v0.2
python3 -m pytest
git status
git add .
git commit -m "<message>"
git push
```

Recommended stable branch strategy:

```text
main       stable release branch
dev/v0.2   active development branch
```
