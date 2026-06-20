# QChain Core Concepts

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.

It implements blocks, headers, Merkle roots, wallets, signed transactions, a mempool, transaction fees, dynamic difficulty adjustment, persistent block storage, orphan blocks, side-branch fork management, automatic reorganization, header-first synchronization, and the heaviest-chain rule.

---

## Block Structure

```text
Block
├── header
│   ├── index
│   ├── previous_hash
│   ├── merkle_root
│   ├── difficulty
│   ├── timestamp
│   └── nonce
├── hash
└── transactions
```

The block hash is computed from the header. Transactions are summarized through the Merkle root.

---

## Proof of Work

A miner must find a nonce such that the block hash starts with a number of zeroes.

```text
difficulty = 4
valid hash = 0000a93f...
```

---

## Transactions

A transaction contains:

```text
sender
receiver
amount
nonce
fee
signature
```

The sender pays `amount + fee`, the receiver gets `amount`, and the miner gets the block reward plus fees.

---

# Persistent Storage Layer

QChain separates the active chain from the broader set of known blocks.

A node can store:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
```

---

## chain.json

`chain.json` stores the active main chain selected by the heaviest-chain rule.

---

## block_index.json

`block_index.json` stores all known blocks by hash.

It can include:

```text
main chain blocks
orphan blocks
side-branch blocks
blocks downloaded during sync
```

This allows:

```text
GET /blocks/<hash>
```

to return known blocks even if they are not part of the current main chain.

---

## orphan_blocks.json

An orphan block is a block whose parent is missing locally.

```text
local node knows:
0 -> 1

node receives:
block 3

but block 2 is missing
```

QChain stores this in `orphan_blocks.json`.

Endpoint:

```text
GET /orphans
```

CLI:

```bash
python3 src/qchain.py node-orphans 5001
```

After restart, the node reloads the orphan pool and can still attach the orphan if its parent arrives later.

---

## side_branch_blocks.json

A side branch is a valid competing branch whose parent is known, but which does not extend the current main chain tip.

```text
main chain:
0 -> 1A -> 2A

side branch:
0 -> 1B
```

QChain stores this in `side_branch_blocks.json`.

Endpoint:

```text
GET /side-branches
```

CLI:

```bash
python3 src/qchain.py node-side-branches 5001
```

After restart, the node reloads side branches and can still perform a reorg if the branch becomes heavier.

---

## Automatic Reorganization

A reorg happens when a side branch becomes better than the current main chain.

```text
current main chain:
0 -> 1A

side branch:
0 -> 1B -> 2B
```

If the side branch has more cumulative work, QChain can adopt it.

Process:

```text
find side-branch tip
walk backward through side-branch blocks
find common ancestor
build candidate chain
validate candidate chain
compare cumulative work
adopt if better
remove adopted side-branch blocks from side_branch_blocks.json
```

---

## Block Reception Cases

```text
direct extension:
    accepted into main chain

missing parent:
    stored as orphan

known parent but not current tip:
    stored as side branch
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
```

If already synchronized:

```text
downloaded_block_count = 0
```

---

## Security Warning

QChain is experimental software. Do not use it with real funds.
