# QChain Core Concepts

This document explains the core ideas behind QChain.

---

## QCOIN

QCOIN is the native coin of QChain.

It is used for:

```text
mining rewards
transaction amounts
transaction fees
balances
```

---

## Blocks

A block contains:

```text
index
previous_hash
transactions
timestamp
difficulty
nonce
hash
merkle_root
```

The block hash is computed from the block header.

A block is valid only if:

```text
its hash matches its content
its hash satisfies the Proof-of-Work difficulty
its previous_hash points to the previous block
its transactions are valid
its Merkle root is valid
its difficulty matches the expected difficulty
```

---

## Block Headers

QChain supports block headers so nodes can synchronize more efficiently.

Headers allow a node to inspect the structure of a remote chain before downloading missing full blocks.

This supports the header-first sync strategy.

---

## Merkle Root

Each block stores a Merkle root of its transactions.

This allows the block to commit to the exact transaction list.

If the transactions change, the Merkle root changes, and the block becomes invalid.

---

## Proof of Work

Mining means finding a nonce that produces a block hash with enough leading zeroes.

Example:

```text
difficulty = 4
valid hash = 0000a93f...
```

The higher the difficulty, the harder it is to mine a block.

---

## Dynamic Difficulty

QChain adjusts mining difficulty based on previous block timestamps.

The goal is to keep block production close to the configured target block time.

Difficulty is bounded by:

```text
MIN_DIFFICULTY
MAX_DIFFICULTY
```

---

## Transactions

A regular transaction contains:

```text
sender
receiver
amount
nonce
fee
signature
```

A transaction is valid only if:

```text
the amount is positive
the fee is non-negative
the receiver exists
the signature is valid
the sender address can be derived from the public key
the nonce is correct
the sender has enough balance
```

---

## Coinbase Transactions

A coinbase transaction is created by the protocol when a miner mines a block.

It pays:

```text
mining_reward + total_fees
```

Coinbase transactions are not accepted into the mempool.

They are also ignored during reorg mempool recovery, because rewards from disconnected blocks are no longer valid.

---

## Wallets

A wallet contains a keypair.

QChain uses wallets to:

```text
derive addresses
sign transactions
verify ownership
```

Wallet files are encrypted and stored as JSON.

QChain now writes wallet JSON files atomically to reduce the risk of corrupted keystore files.

---

## Balances and Nonces

QChain uses an account-style model.

For every address, QChain tracks:

```text
balance
next expected nonce
```

The nonce prevents replay attacks and ensures transaction ordering for each sender.

---

## Mempool

The mempool contains valid pending transactions that have not yet been mined.

QChain supports:

```text
persistent mempool storage
fee-aware transaction selection
mempool cleanup after mining
mempool cleanup after external block acceptance
mempool transaction recovery after reorg
```

---

## Fees and Mining Rewards

When a block is mined:

```text
miner reward = mining_reward + sum(transaction fees)
```

Transactions with higher fees are prioritized during block construction.

---

## Forks

A fork happens when multiple valid branches exist.

QChain distinguishes:

```text
orphan blocks
side-branch blocks
main-chain blocks
```

---

## Orphan Blocks

An orphan block is a block whose parent is not known locally.

QChain stores orphans in:

```text
orphan_blocks.json
```

If the missing parent arrives later, the orphan can be processed.

---

## Side Branches

A side branch is a valid competing branch whose parent is known, but which does not currently extend the main chain tip.

QChain stores side-branch blocks in:

```text
side_branch_blocks.json
```

If a side branch becomes heavier than the current main chain, QChain can reorganize to it.

---

## Heaviest-Chain Rule

QChain selects the chain with the highest cumulative work.

Cumulative work is based on block difficulty.

A candidate chain is adopted only if:

```text
it has the same genesis block
it is valid
it has more cumulative work than the current chain
```

---

## Reorganization

A reorg happens when QChain replaces its active main chain with a better candidate chain.

During a reorg:

```text
the old chain is saved temporarily
the candidate chain is validated
the active chain is replaced
balances and nonces are rebuilt
mempool is cleaned
transaction index is rebuilt
valid disconnected transactions can return to the mempool
```

---

## Reorg Mempool Recovery

When a block is disconnected during a reorg, its regular transactions may become unconfirmed.

QChain recovers transactions into the mempool if they are:

```text
not coinbase transactions
not already included in the new main chain
not already known in the mempool
still valid after the reorg
```

This reduces the risk of user transactions disappearing after a fork switch.

---

## Transaction Index

QChain maintains a persistent transaction index:

```text
tx_index.json
```

It enables:

```text
GET /transactions/<tx_hash>
GET /addresses/<address>/transactions
```

The lookup layer can return:

```text
pending transaction from the mempool
confirmed transaction from tx_index.json
404 if unknown
```

---

## Atomic Storage

QChain uses atomic JSON writes for critical files.

Instead of writing directly to the target file, QChain:

```text
writes to a temporary file
flushes the temporary file
fsyncs it
atomically replaces the target file
fsyncs the parent directory when possible
```

This helps avoid partially written JSON files.

---

## Security Warning

QChain is experimental software and is not production-ready.
