# QChain Core Concepts

QChain implements Proof-of-Work blocks, signed transactions, persistent node storage, mempool recovery, fork handling, and a persistent transaction index.

---

## Persistent Storage Layer

A node can store:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

---

## Transaction Index

The transaction index is stored in:

```text
tx_index.json
```

It maps transaction hashes to confirmed transaction metadata.

Each indexed transaction contains:

```text
hash
location
block_hash
block_index
position
sender
receiver
amount
fee
nonce
is_coinbase
transaction
```

The index is rebuilt from the active main chain whenever the main chain changes.

---

## Confirmed vs Pending Transactions

QChain distinguishes:

```text
confirmed transaction:
    included in the active main chain
    indexed in tx_index.json

pending transaction:
    currently in the mempool
    stored in mempool.json
```

`GET /transactions/<tx_hash>` first checks the mempool, then the persistent transaction index.

This means a transaction can be found whether it is still pending or already confirmed.

---

## Address Transaction History

QChain can list transactions related to a given address.

Endpoint:

```text
GET /addresses/<address>/transactions
```

The response includes:

```text
confirmed_count
pending_count
transactions
```

This creates a first mini block-explorer layer.

---

## Reorg and Transaction Index

When a reorg happens, QChain replaces the active main chain with a heavier chain.

After the reorg:

```text
tx_index.json is rebuilt from the new main chain
transactions from disconnected old blocks can be recovered into the mempool
mempool.json is persisted
```

This keeps confirmed transaction lookup consistent with the selected main chain.

---

## Mempool Recovery

During a reorg, transactions from disconnected blocks are recovered only if:

```text
they are not coinbase transactions
they are not already included in the new main chain
they are not already in the mempool
they are still valid after the reorg
```

---

## Useful Endpoints

```text
GET /transactions/<tx_hash>
GET /addresses/<address>/transactions
GET /mempool
GET /blocks/<hash>
GET /status
```

---

## Security Warning

QChain is experimental software. Do not use it with real funds.
