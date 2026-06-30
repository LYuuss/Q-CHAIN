# QChain Core Concepts

QChain implements Proof-of-Work blocks, signed transactions, persistent node storage, fork handling, mempool recovery, transaction indexing, and safer atomic JSON storage.

---

## Atomic JSON Storage

QChain provides:

```text
atomic_write_json(path, data)
read_json_or_default(path, default)
```

`atomic_write_json` writes JSON data to a temporary file first, flushes it, then atomically replaces the target file.

This avoids leaving partially written JSON files if the process is interrupted during save operations.

---

## Atomic Wallet Storage

Wallet files are critical because they can contain encrypted private keys.

They are stored under:

```text
data/wallets/*.json
```

Wallet saving now uses atomic JSON writes.

Wallet loading uses safe JSON reads, but invalid wallet files are rejected explicitly.

This prevents dangerous behavior such as:

```text
silently replacing a corrupted wallet
creating a new wallet when an old encrypted wallet is unreadable
masking a broken keystore
```

---

## Wallet File Behavior

When saving:

```text
QChain encrypts the private key
builds the wallet JSON object
writes it through atomic_write_json
```

When loading:

```text
QChain reads the wallet JSON safely
rejects missing or malformed wallet data
decrypts the private key only with the correct password
checks that the address matches the loaded keys
```

---

## Protected Storage Files

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

## Security Warning

QChain is experimental software. Do not use it with real funds.
