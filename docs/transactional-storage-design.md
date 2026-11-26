# Mission 002-C — Transactional storage design

Status: proposed architecture and implementation plan; no runtime backend
change or migration performed. Baseline: dev/v0.2 at 5e66cae (Mission 002-B).
Scope: A03, preserving the behavior and wire formats of v0.2.3-alpha. The
maintainer must approve irreversible data changes or a breaking protocol
decision; this document authorizes neither.

## 1. Problem and decision

The chain snapshot is authoritative for active blocks, consensus parameters and
pending transactions. Node code then writes the block archive, transaction
index, fork pools, peers and reorg diagnostics in separate files. Mission 002-B
provides single-writer ownership and quarantine, but a process death between
files can lose branch membership or diagnostics. Rebuilding derived indexes
cannot reconstruct all lost history.

Use Python's standard-library SQLite as the proposed embedded transactional
store, not a new network service. One database per existing node or local-chain
directory; wallets remain separate encrypted files. PostgreSQL would require an
extra service and deployment/credential management; a custom JSON journal
would require implementing crash recovery and transaction semantics ourselves.
SQLite is a good fit for the current single-writer educational node. Its
durability still depends on the filesystem and OS; it does not solve network
consensus or cross-node atomicity.

Initial backend goals are correctness and compatibility, not high throughput.
Retain complete block dictionaries in JSON (no wire re-encoding, no changes to
hashing). Store active-chain membership separately. Rebuild balances, nonces
and the confirmed transaction index from validated active blocks initially;
incremental SQL query indexes and archive pruning are follow-up work (A07/A12).
Avoid a large rewrite of node.py in a single PR.

## 2. Proposed model and invariants

Reference DDL: [storage-schema-v1.sql](storage-schema-v1.sql). It is a draft for
review and development, not an executable production migration.

| Record | Authority and constraints |
| --- | --- |
| chain_meta | Singleton, consensus parameters JSON, genesis hash, monotonic local revision |
| blocks | Full block dictionaries keyed by hash, height and parent metadata; archive may include proof-valid orphans |
| active_chain | Height-to-hash mapping; exactly one block per height; contiguous from genesis |
| mempool | Ordered canonical transactions, unique hash; validated against active account state |
| fork_pool | Orphan/side-branch membership, FK to blocks; disjoint from active chain |
| peers | Normalized configured origins, at most the existing cap |
| reorg_history | Ordered event records with old/new tip, reason and diagnostics; retain the current 100-event policy |
| confirmed transactions / balances / nonces | Derived by replay; not a second authoritative copy |

Application validation still enforces genesis, expected difficulty, block links,
Merkle roots, signatures, rewards, nonces, balances and work-based fork choice.
Database constraints do not establish consensus validity. An orphan's missing
parent is intentional, so there is no FK from blocks.parent_hash to blocks.
The same transaction may appear in competing blocks; never enforce global
uniqueness of transaction hashes across the archive. Preserve Python's integer
semantics: amounts/balances/work must not be narrowed to SQLite signed 64-bit
arithmetic (A09 is a separate protocol-policy decision). Canonical JSON
payloads retain original integers and timestamp representations. Validate
metadata against parsed payloads; hashes are recomputed, not trusted.

Active chain and mempool must replay to the same state as the legacy backend.
No acknowledged state revision may contain an active block in a fork pool, a
confirmed transaction still pending, or a reorg event for a transition that
never committed. Historical archive retention and pool eviction must be
explicit, not an incidental cascade.

## 3. Transaction boundaries and concurrency

Refactor persistence behind a narrow state repository / unit-of-work boundary.
The current Blockchain methods save internally; separate their deterministic
state-transition logic from persistence before enabling SQLite. Otherwise
wrapping existing per-file writes in an SQL transaction would provide no
additional atomicity. Use staged state/snapshots, not independently committing
BlockStore or TransactionIndex methods.

| Operation | One local commit includes |
| --- | --- |
| Submit transaction | Validated ordered mempool + revision |
| Mine or receive extending block | Archive block, active membership, mempool cleanup, pool changes + revision |
| Adopt heavier chain | New active mapping, disconnected block membership, recovered mempool, reorg event, archive + revision |
| Store/attach orphan or side branch | Archive and membership changes; any resulting chain adoption as an explicit complete unit |
| Peer registration/discovery | Validated peer-set change + revision |
| Bootstrap/migration | Complete validated initial snapshot, schema version and revision |

A single request can contain several complete local transitions (e.g. attaching
multiple orphans). Each must be consistent independently; do not claim the
entire distributed request is atomic. Startup must reconcile stale pool
membership using the committed revision and validate the active chain.

Proposed execution order:
1. Own the state directory using Mission 002-B's OS lock. Acquire the node
   state lock and capture the current revision/tip.
2. Compute a candidate state without publishing it; validate against current
   state. For future out-of-lock mining or peer downloads, recheck the
   revision/tip and recompute on conflict before starting a write.
3. Begin a short SQL write transaction (BEGIN IMMEDIATE). Apply all changes,
   increment the revision, and COMMIT. No network I/O, unbounded mining or
   callback under the database transaction.
4. Publish the committed in-memory state under the node state lock. Only
   then return local success or broadcast. If COMMIT or post-commit memory
   publication fails, quarantine; reload from disk rather than attempting an
   unverified rollback.
5. Release the state lock before peer calls; recheck lifecycle/revision on
   return. Broadcast is an external side effect and cannot be rolled back.

A failure before commit should leave the previous revision visible; a failure
after commit may leave the new revision durable without a successful response.
Retries must inspect the transaction hash, block hash and current tip rather
than blindly repeat mining. Exactly-once delivery is not promised. A durable
outbox is a separate networking design if required.

## 4. SQLite operating policy

Use a local filesystem with supported SQLite locking. Retain directory ownership
even though SQLite serializes writes: the lock protects the in-memory node
state and migration/backup operations. Configure every connection explicitly:
foreign_keys=ON, a bounded busy_timeout (proposed 5 seconds), synchronous=FULL.
Propose WAL journal mode for concurrent read snapshots; verify the returned
mode and fail startup if the required mode cannot be established. Do not claim
WAL is a backup mechanism. Use one explicit write transaction at a time;
avoid implicit sqlite3 transaction behavior across Python 3.11/3.12 by choosing
a documented explicit transaction mode. Readers use committed snapshots or
the validated in-memory revision. Never share one connection concurrently
without synchronization; keep connection ownership and lifetimes explicit.

Use PRAGMA user_version for schema compatibility and reject unknown newer
schemas. Run migrations in a transaction under ownership; no destructive
automatic migration. Validate database integrity and foreign keys at import,
and validate consensus state at startup. A failed validation is an error, not
a reason to create a new genesis. Back up using SQLite's backup API or a
documented stopped/checkpointed database procedure; never copy only the main
database file while WAL writers are active.

## 5. Reversible migration (C3 offline prototype)

The C3 implementation is opt-in, offline and non-destructive. See
[storage and recovery](storage-layer.md) for commands and limitations. The
operator takes a stopped verified backup before conversion; the converter
never copies wallets or activates a backend.
Keep JSON as default until integration and migration gates are met.

1. Stop the node/local CLI writer. Acquire the same canonical directory lock.
   Make a verified complete backup to a separate directory; keep wallet
   backups independent. Refuse to proceed if an existing target DB is present
   unless a separately approved recovery procedure applies.
2. Load chain.json strictly and replay the chain. Import legacy mempool.json
   only if the authoritative snapshot lacks the mempool field, matching
   current migration semantics. Validate pending transactions in order.
3. Read auxiliary files, normalize peers, validate block archive entries and
   reconcile pool membership using the active chain. Report skipped invalid
   entries and missing historical diagnostics; do not silently invent history.
   Reject an invalid authoritative chain. Do not import tx_index.json as
   authority; rebuild it from active blocks. Preserve full original files.
4. Build a temporary SQLite database under exclusive ownership. Import one
   coherent initial revision transactionally; run integrity_check,
   foreign_key_check and full consensus replay. Compare genesis, height, tip,
   cumulative work, balances, nonces, ordered mempool, archive/pool membership
   and available reorg history with the validated JSON view. Produce a migration
   report with counts and source checksums, no private keys.
5. Close/checkpoint the temporary database and publish the verified result
   without overwriting an existing target. Keep JSON untouched. Activate the
   new backend only through an explicit backend choice after successful review;
   never implicitly choose a backend merely because a DB exists. Refuse mixed
   writers or ambiguous backend activation.
6. Before any SQLite writes, reverting to the untouched JSON snapshot is safe.
   After SQLite accepts new state, old JSON is stale: a rollback requires a
   separately verified export of the latest committed revision or explicit
   data-loss approval. Do not simply start the old backend against stale JSON.

Migration interruption must leave the original authoritative files unchanged;
an incomplete temporary DB cannot be selected as active. Re-running must not
overwrite a valid target. The backend switch and export/rollback contract must
be tested before making SQLite the default. No existing user's data will be
migrated by an agent without separate authorization for any irreversible step.

## 6. Implementation slices and release gates

| Slice | Deliverable and acceptance criteria |
| --- | --- |
| 002-C1 | State repository contract and transition snapshots; JSON remains default; all existing regression tests pass without changes to consensus semantics |
| 002-C2 | SQLite repository, explicit transactions, schema/version checking, reopen and injected SQL failure tests; opt-in only |
| 002-C3 | Offline JSON import/verification and export/rollback prototype; interrupted migration, corrupt input, existing destination and legacy mempool tests |
| 002-C4 | Integrate node and local CLI opt-in; parity tests for mining, send, sync, forks, restart and explorer; no uncommitted network effects |
| 002-C5 | Fault injection and operational validation; evaluate default switch only after review of compatibility and recovery |

Mandatory additional tests:
- Compare identical deterministic histories on JSON and SQLite: block hashes,
  active tip, cumulative work, balances/nonces, mempool order and confirmations.
- Inject failures before and after COMMIT, between chain and pool changes,
  during reorg and after COMMIT before broadcast. Reopen and verify that only
  complete revisions are visible. Test process kill using a coordinated
  subprocess and temporary directories, not timing-dependent sleeps.
- Reorg A->B->A with disconnected transaction recovery, preserved branch
  ancestry and consistent diagnostics; no duplicate active transaction records.
- Writer contention, startup failure, corrupted DB, unknown schema,
  unavailable journal mode, failed integrity validation, interrupted import,
  repeat import, and a verified restore including WAL state.
- Run Python 3.11/3.12 suite, real HTTP testnet and Docker checks; add opt-in
  SQLite scenarios before claiming feature complete. Measure performance on
  synthetic chains, but set no invented benchmark targets.

## 7. Open decisions and non-goals

The proposed default after implementation is SQLite, conditional on parity and
migration results. Until then the runtime remains JSON. No change to consensus,
network identity, transaction signatures, wallet formats, reward policy,
genesis, difficulty, public HTTP routes or QCOIN semantics. No live migration,
automatic deletion of JSON, public deployment, pruning policy, or claimed
performance gain in this design milestone.

A03 remains open until the transactional backend is integrated and verified.
A10's cooperative lock and A04's exclusive wallet creation remain in force.
C1 implementation introduces the chain/mempool repository contract and
commit-before-publish staging. It deliberately does not yet coordinate
auxiliary files. C2 extends the contract with NodeSnapshot and a transactional SQLite
implementation. The draft reorg revision is nullable: imported legacy events
have no historical revision and must not be assigned invented values.
C3 adds offline conversion and verification; the node/CLI still use JSON and
runtime integration remains C4. Any major architectural change or
irreversible migration must stop for the maintainer.
