# QChain Storage Layer

QChain uses persistent JSON files to keep node and wallet state across restarts.

---

## Node Storage Files

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

## Wallet Storage Files

```text
data/wallets/*.json
```

Wallet files contain encrypted private key material and metadata.

---

## Atomic JSON Writes

QChain uses:

```text
atomic_write_json(path, data)
```

This helper:

```text
creates the parent directory
writes JSON to a temporary file
flushes the file
fsyncs the file
replaces the target file with os.replace
fsyncs the parent directory when possible
```

This helps ensure files are not left half-written.

---

## Safe JSON Reads

QChain uses:

```text
read_json_or_default(path, default)
```

This helper returns the default when:

```text
the file does not exist
the file contains invalid JSON
the loaded object is not a dictionary
```

---

## chain.json

Stores the active blockchain state.

Includes:

```text
difficulty
initial_difficulty
mining_reward
target_block_time
difficulty_adjustment_interval
min_difficulty
max_difficulty
chain
mempool
```

If `chain.json` is missing or malformed, QChain can recreate a valid genesis chain.

If it is valid JSON but contains an invalid blockchain, QChain rejects it.

---

## peers.json

Stores known peers.

Used for:

```text
broadcasting
sync
peer persistence after restart
```

---

## block_index.json

Stores all known blocks by hash.

Can include:

```text
main-chain blocks
orphan blocks
side-branch blocks
downloaded sync blocks
```

---

## orphan_blocks.json

Stores orphan blocks whose parents are currently unknown.

---

## side_branch_blocks.json

Stores valid competing fork blocks.

These blocks may later become part of a heavier chain.

---

## mempool.json

Stores valid pending transactions.

The node reloads and revalidates pending transactions on startup.

Invalid, duplicate, or coinbase transactions are not kept.

---

## tx_index.json

Stores confirmed transaction metadata from the active main chain.

It is rebuilt when the main chain changes.

Used for:

```text
GET /transactions/<tx_hash>
GET /addresses/<address>/transactions
```

---

## data/wallets/*.json

Stores encrypted wallet files.

Wallet loading behavior is intentionally strict:

```text
missing wallet file -> error
invalid wallet JSON -> error
wrong password -> error
address/key mismatch -> error
```

QChain does not silently replace invalid wallet files.

---

## Reorg Storage Effects

When a reorg happens:

```text
chain.json is updated
tx_index.json is rebuilt
mempool.json is updated with recovered transactions
block_index.json keeps known blocks
side_branch_blocks.json is cleaned when needed
orphan_blocks.json may be processed if parents arrive
```

---

## Recommended Debugging Commands

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
```
