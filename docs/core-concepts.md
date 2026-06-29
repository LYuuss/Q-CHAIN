# QChain Core Concepts

QChain implements Proof-of-Work blocks, signed transactions, persistent node storage, fork handling, mempool recovery, transaction indexing, and safer atomic JSON storage.

---

## Atomic JSON Writes

Writing JSON directly with `json.dump(...)` can leave a corrupted file if the process stops during the write.

QChain now writes to a temporary file first, then replaces the target file atomically.

Conceptually:

```text
1. write data to a temporary file in the same directory
2. flush the file
3. fsync the file descriptor
4. atomically replace the target file
5. fsync the parent directory when possible
```

This means a persisted file should be either the previous complete version or the new complete version, not a half-written file.

---

## Safe JSON Reads

QChain provides:

```text
read_json_or_default(path, default)
```

It returns the provided default when:

```text
the file does not exist
the file contains malformed JSON
the loaded value is not a JSON object
```

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
```

---

## chain.json

`chain.json` is the most critical file because it stores the active blockchain state.

It includes:

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

QChain now writes this file atomically.

If the file is missing or malformed, the node can fall back to a safe default and recreate a valid genesis chain.

If the file is valid JSON but contains an invalid blockchain, QChain rejects it.

---

## Reorg Consistency

After a reorg:

```text
the active chain is replaced if the candidate has higher cumulative work
tx_index.json is rebuilt from the new main chain
valid transactions from disconnected blocks can return to mempool.json
affected JSON files are saved through safer storage helpers
```

---

## Security Warning

QChain is experimental software. Do not use it with real funds.
