# QChain API Reference

This document summarizes the HTTP API exposed by QChain nodes.

---

## GET /

Returns a basic index of available endpoints.

---

## GET /status

Returns node status.

Typical fields:

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

## GET /chain

Returns the active main chain.

---

## GET /headers

Returns block headers for the active main chain.

Used by header-first sync.

---

## GET /blocks/<hash>

Looks up a block by hash.

Possible locations:

```text
main_chain
orphan_pool
side_branch_pool
block_store
unknown
```

---

## GET /transactions/<tx_hash>

Looks up a transaction by hash.

Lookup order:

```text
mempool
transaction index
```

Possible locations:

```text
mempool
confirmed
```

Returns `404` if the transaction is unknown.

---

## GET /addresses/<address>/transactions

Returns transaction history for an address.

The response includes both confirmed and pending transactions:

```text
count
confirmed_count
pending_count
transactions
```

---

## GET /mempool

Returns pending transactions.

---

## GET /orphans

Returns the orphan block pool.

---

## GET /side-branches

Returns side-branch fork information.

---

## GET /balances/<address>

Returns the balance for an address.

---

## GET /peers

Returns known peers.

---

## POST /transactions

Submits a signed transaction to the node mempool.

The node validates:

```text
signature
nonce
balance
fee
receiver
transaction format
```

---

## POST /blocks

Submits a block received from another node.

Possible outcomes:

```text
accepted into main chain
stored as orphan
stored as side-branch
rejected as invalid
```

---

## POST /mine

Mines a block.

The block includes:

```text
coinbase transaction
selected mempool transactions
transaction fees
Proof-of-Work
```

---

## POST /peers

Adds a peer to the known peer list.

Peers are persisted in:

```text
peers.json
```

---

## POST /sync

Runs header-first synchronization with known peers.

The sync process can:

```text
download missing blocks
adopt a heavier chain
process orphan blocks
process side branches
recover mempool transactions after reorg
```

If a reorg happens, the response can include:

```text
mempool_recovery_results
```
