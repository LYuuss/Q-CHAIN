# QChain Usage Guide

This guide focuses on the safer storage layer and persisted node state.

---

## Run Tests

```bash
python3 -m pytest
```

Expected:

```text
46 passed
```

---

## Inspect Node Status

```bash
python3 src/qchain.py node-status 5001
```

Status can include:

```text
storage_path
block_store_path
orphan_blocks_path
side_branch_blocks_path
mempool_path
transaction_index_path
block_store_size
orphan_pool_size
side_branch_pool_size
mempool_size
transaction_index_size
```

---

## Persistent Files

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

These files are written through safer JSON storage helpers.

---

## Useful Commands

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
python3 src/qchain.py node-sync 5001
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

---

## Address History

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
