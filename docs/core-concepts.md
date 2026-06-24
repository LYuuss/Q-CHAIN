# QChain Core Concepts

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

## Persistent Mempool

The mempool stores valid pending transactions before they are mined.

QChain persists it in:

```text
mempool.json
```

This allows pending transactions to survive node restarts. When transactions are mined, they are removed from both the in-memory mempool and `mempool.json`.

---

## Reorg Mempool Recovery

A reorganization happens when a node replaces its current main chain with a heavier competing branch.

Example:

```text
old main chain:
0 -> 1 -> 2A

new heavier chain:
0 -> 1 -> 2B -> 3B
```

If block `2A` contained a normal transaction that is not present in the new chain, that transaction is no longer confirmed.

QChain now attempts to recover such transactions into the mempool.

---

## Recovery Rules

A transaction from a disconnected block is recovered only if:

```text
it is not a coinbase transaction
it is not already included in the new main chain
it is not already in the mempool
it is still valid after the reorg
```

Coinbase transactions are ignored because mining rewards from disconnected blocks are not valid anymore.

---

## Recovery Process

```text
save the old chain before reorg
adopt the heavier candidate chain
scan disconnected old blocks
collect non-coinbase transactions
remove transactions already present in the new chain
validate each transaction against the new state
reinsert valid transactions into the mempool
persist mempool.json
```

---

## Block Reception Cases

```text
direct extension:
    accepted into main chain

missing parent:
    stored in orphan_blocks.json

known parent but not current tip:
    stored in side_branch_blocks.json
```

---

## Header-First Sync

```text
GET /status
GET /headers
validate headers
find common ancestor
GET /blocks/<hash> for missing blocks
rebuild candidate chain
adopt if heavier
process orphan blocks
process side branches
recover mempool transactions after reorg
```
