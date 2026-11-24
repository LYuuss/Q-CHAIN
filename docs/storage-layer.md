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
