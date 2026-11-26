# Storage and recovery

Each node owns a directory. The local CLI uses `data/chain.json`; standalone
nodes default to `data/nodes/node_<port>/`; Docker nodes use `data/docker/nodeN/`
on the host. `QCHAIN_DATA_DIR` changes the default root. Runtime files and wallets
are ignored by Git.

## Files and authority

| File | Contents and startup behavior |
| --- | --- |
| `chain.json` | Authoritative active chain, consensus parameters, and mempool. Validated before use. |
| `mempool.json` | Compatibility/inspection mirror. Regenerated from `chain.json`; never overrides its current mempool. |
| `block_index.json` | Known blocks keyed by hash. Structurally damaged entries are skipped; active blocks are reinserted. |
| `tx_index.json` | Confirmed transaction metadata. Rebuilt from the active chain at startup and after chain changes. |
| `orphan_blocks.json` | Pending blocks with missing parents, subject to the orphan pool limit. |
| `side_branch_blocks.json` | Competing blocks, including recently disconnected main-chain blocks. |
| `peers.json` | Normalized configured/discovered peers; invalid URLs and advertised self URLs are removed. |
| `reorg_history.json` | Most recent 100 fork-switch diagnostics; newest entries are returned first by the API. |
| `wallets/*.json` | Encrypted private keys and public metadata, stored separately from nodes. |

The legacy `mempool.json` is imported only when an existing chain snapshot has
no `mempool` field. Its transactions are revalidated. A missing or stale mirror
cannot erase accepted transactions in the authoritative snapshot.

## Atomic writes

`atomic_write_json` writes a temporary file in the destination directory,
flushes and fsyncs it, replaces the destination with `os.replace`, and attempts
to fsync the directory. Temporary files have owner-only permissions on POSIX.
A failed serialization or replacement leaves the previous destination intact.
NaN and infinite JSON numbers cannot be written.

Wallet creation, backup and import use an atomic, non-overwriting publication
via a hard link in the destination filesystem. They fail if a concurrent writer
has already published the destination, preserving its bytes. The filesystem
must support hard links; unsupported publication fails rather than falling back
to an unsafe replacement. Explicit password changes and legacy encryption use
atomic replacement after loading the wallet. Python callers of
`Wallet.save(path, password)` and `save_wallet_json(path, data)` now get exclusive
creation by default; an intentional replacement must pass `overwrite=True`.
`Wallet.load_or_create` loads an existing wallet normally and propagates
`FileExistsError` if a competing creator wins. This is not a compare-and-swap
protocol for concurrent password changes or imports; writer coordination and
strict import snapshot validation remain separate work.

Atomicity applies **per file**, not across all node files. The active chain and
mempool share one snapshot, but caches, pools, and diagnostics may lag if the
process or disk fails between writes. Restart rebuilds the transaction index,
refreshes active block lookup, revalidates the mempool, and processes stored
orphans and side branches. A journal entry or recent pool change can still be
lost during an interrupted multi-file update.

## Writer ownership and persistence failures (Mission 002-B)

Supported node and local-chain CLI entry points acquire a non-blocking OS lock
on `.qchain-state.lock` before initialization and hold it until the server or
command finishes. A second owner fails with a nonzero exit status. The lock
file is intentionally retained; its presence alone does not indicate an active
owner. OS handle closure, including process death, releases the lock. Never
delete the lock file to bypass an active owner. Use a local filesystem supporting
POSIX flock or Windows byte-range locking; these are cooperative locks, not a
defense against unrelated programs or unsupported network filesystems.

Embedded server hosts must use `node.owned_app` for the entire serving lifetime
(or hold `state_directory_lock` themselves). The low-level `create_app` and
`Blockchain` constructors are not independent lock owners; direct callers
must coordinate access. Existing chain loads no longer rewrite the snapshot.
Local CLI read commands still acquire ownership because they can initialize a
missing chain. Wallet-only and remote-node client commands do not take this lock.

Node state writes use `write_state_json`: file fsync and atomic replacement,
plus directory fsync on POSIX with errors propagated. Windows directory fsync
is best effort. A state write failure raises `StatePersistenceError`.
An authoritative chain object becomes unusable for normal reads/mutations after
such a failure; discard it rather than saving stale memory. The HTTP node
quarantines all routes (including health) with 503 until restarted; in-flight
network calls recheck quarantine after reacquiring the state lock. The local
CLI exits nonzero. Check storage and restart only after resolving the error.

A failed response does not guarantee the operation was rolled back: the chain
snapshot may already have been committed before an auxiliary write or directory
fsync failed. Restart validates the authoritative chain and reconstructs derived
indexes and the mempool mirror. Check the resulting tip/transaction before
retrying. No successful local mutation is reported after quarantine; previously
sent network messages cannot be recalled. Multi-file transactions, durable
reorg diagnostics and complete crash reconciliation remain Mission 002-C.
See the [transactional storage design](transactional-storage-design.md) for the
proposed migration. The JSON backend remains active.

## Chain repository boundary (Mission 002-C1)

`Blockchain` accepts an optional `ChainRepository` with exists/load/commit.
The default `JsonChainRepository` preserves the existing chain.json format.
`Blockchain.snapshot()` returns a detached copy of the persisted representation.
Transaction admission, mining, external block acceptance and chain replacement
stage changes in separate containers, commit the candidate snapshot, then
publish the candidate in memory. A rejected transition does not commit; a
persistence failure quarantines the original object without publishing the
candidate. A commit failure may still have an uncertain durable outcome.
Existing block/transaction objects are treated as read-only during staging.

This is the authoritative chain/mempool boundary only. Node archive, pools,
indexes, peers and reorg diagnostics still use the existing JSON writes and
quarantine behavior. A node-wide transaction and SQLite activation are not
implemented by C1. The same cooperative writer ownership is required.

## SQLite snapshot repository (Mission 002-C2)

`SQLiteStateRepository` stores a complete `NodeSnapshot` (chain/mempool,
archive, fork membership, peers and reorg history) in one explicit SQL
transaction. Initial creation reserves an exclusive new file; an existing
invalid or unsupported database is never initialized automatically.
Subsequent writes require the expected committed revision. Each operation
uses a private connection, WAL, foreign keys, bounded busy timeout and FULL
synchronous writes. Reads use a consistent transaction. Storage-level
invariants are checked; callers still validate consensus and own the directory.
A failed commit raises StatePersistenceError and callers must recover from disk.

`SQLiteChainRepository` adapts the C1 contract for isolated library
experiments. It refuses databases with nonempty node auxiliary state.
It is used by the local CLI; the full node uses a separate workspace with
complete SQLite commits. JSON remains the runtime default; offline conversion
and explicit SQLite activation are available as described below. Whole-snapshot
replacement and replay are intentionally simple; performance and crash validation remain follow-up work.
Use only isolated temporary databases at this stage.

## Offline migration and recovery export (Mission 002-C3)

Stop all writers and take a verified backup of the entire state directory
first (wallets are backed up separately). Run against that stopped copy:

```bash
python src/storage_migration.py import-json ./backup-node ./sqlite-copy/state.db
python src/storage_migration.py export-json ./sqlite-copy/state.db ./recovered-json
```

Both commands take cooperative source and destination-parent locks and require
a new destination outside the source directory. Import verifies consensus
replay, state parity, SQLite integrity and source checksums before publishing
the database with an exclusive hard link. Export validates the committed
snapshot and reconstructs the JSON files and derived transaction index in a
temporary directory before publishing it. The export includes a report with
revision and file checksums; import prints a JSON report to stdout (redirect
it to a separate file if desired). Missing or damaged auxiliary entries and
legacy mempool reconciliation are reported. An invalid authoritative chain or
changed authoritative mempool is rejected. Original state files are untouched.

Use a local filesystem and cooperative processes; do not run unrelated
programs against the destination parent during export. A failure after
publication but during directory fsync may leave a complete destination:
inspect it before retrying. A killed process can leave a hidden staging
directory; it is not an active backend. No wallets are copied. A verified
export of the latest SQLite revision is needed for rollback after new writes;
the original JSON copy may be stale. Do not activate a database or replace a
live directory using these commands. Use the explicit runtime option below.

## Explicit SQLite runtime (Mission 002-C4)

On an isolated empty directory, or a separate reviewed C3 import named
`state.db`, opt in explicitly:

```bash
python src/node.py --port 5001 --data-dir ./sqlite-copy --storage-backend sqlite
python src/qchain.py --data-dir ./local-sqlite --storage-backend sqlite status
```

Use the same option on every local chain command (status, balance, mine,
send, mempool, validate). Wallet files and remote HTTP CLI commands are
unchanged. The CLI chain-only adapter rejects databases containing peers,
fork pools or reorg diagnostics; inspect those via the node's HTTP APIs
instead. Both entry points retain the directory ownership
lock. The JSON default rejects a directory containing `state.db` or its
sidecars; SQLite rejects legacy state JSON files and orphaned sidecars.
Do not rename the database or use a mixed directory to bypass these checks.
An invalid database or authoritative replay mismatch fails startup.

In SQLite mode, the node uses a private working snapshot under the existing
state lock. Chain staging and auxiliary archive, pools, peers and reorg
events are committed as one complete revision before releasing that lock
for a peer call, or before returning a local mutation response. No SQL
transaction spans peer I/O. Multiple local transitions may share a revision.
The working state is not visible to another HTTP request before a successful
checkpoint. Confirmed transaction indexes are rebuilt in memory; no JSON
mirrors are written. Reorg events created in this backend include their local
commit revision; imported history retains whatever revision was present.

A failure quarantines the node instead of publishing a partially staged
state. Stop, inspect storage and restart from disk. A failure after SQLite
commit may leave a complete new revision without a successful response or
broadcast; inspect the committed transaction or block before retrying.
This does not make distributed requests atomic or guarantee delivery.

SQLite is an opt-in educational backend, not the new default. Use a supported
local filesystem, cooperative writers and verified stopped backups. After
SQLite writes, use C3 export for recovery to JSON rather than reopening a stale
copy. Whole-snapshot commits and replay are intentionally simple; C5 further
process-kill, operational recovery, and performance validation remains pending.

## Corrupt or missing chain files

A missing `chain.json` creates a new genesis chain. An existing malformed,
empty, or consensus-invalid chain causes startup to fail. QChain preserves the
file instead of silently resetting balances. Do not delete a broken chain as
an automatic repair step.

Recovery procedure:

1. Stop the affected node and preserve its entire directory for investigation.
2. Restore a consistent backup into a separate directory and start with
   `--data-dir /path/to/restored-node`.
3. Check `/status`, then reconnect trusted peers and run `/sync`.
4. If no backup exists, start a separate empty node and synchronize confirmed
   history from a trusted peer. Pending transactions, private keys, and local
   diagnostics cannot be recovered from confirmed chain history alone.

Auxiliary caches use tolerant reads and can be reconstructed in part from the
active chain. Tolerance for a cache must not be confused with safe recovery of
an authoritative chain or wallet.

## Backups and upgrades

Stop a node before copying its entire directory. Independently running nodes
need independent copies. A live directory copy can mix files from different
moments despite atomic writes to individual files.

```bash
python src/qchain.py wallet-backup alice ./backups/alice.json
python src/qchain.py wallet-import ./backups/alice.json alice-restored
```

The backup remains encrypted. Keep its password separately; there is no password
reset or key recovery service. Import verifies the password and key pair.

Before adopting v0.2.3-alpha, stop existing nodes and copy their data and wallets
outside the checkout. The update removes historical demo files from Git
tracking; applying that deletion in an older checkout can remove unchanged
tracked demo files. Valid old integer-based chains and v2 encrypted wallets are
supported. Old chains that violate the stricter validation rules are rejected
and left intact; there is no automatic consensus-data repair.
