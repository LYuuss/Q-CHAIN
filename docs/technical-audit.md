# QChain technical audit — Mission 001

Audit date: 2026-11-25. Baseline: [4f6e2ca](https://github.com/LYuuss/Q-CHAIN/commit/4f6e2ca6a25cf0e338c89522da14ff289bcebcee), dev/v0.2, v0.2.3-alpha implementation.

## Executive assessment

QChain is a functional educational account-based PoW blockchain with a mature local-testnet workflow. It is not ready for untrusted public peers or real funds. The immediate goal should be bounded, recoverable and observable node operation, not additional explorer features or novel cryptography.

Scope: static inspection of consensus, wire validation, peer transport, node orchestration, storage, wallet/CLI, explorer, deployment and representative regression tests. Findings are code-derived; no live exploitation, fuzzing, process-kill testing or independent cryptographic audit was performed. Line references below refer to the baseline, not future revisions. No runtime code is modified by this mission.

Severity: High = plausible major availability, integrity or key-loss impact; Medium = significant correctness, scaling or operational risk; Low = maintainability. Priority P0 blocks an untrusted-network release; P1 targets reliable local operation; P2 improves maintainability or scale. No claim of exhaustive vulnerability discovery.

## Baseline and strengths

- Consensus validates canonical genesis, SHA3-256 PoW, Merkle commitments, expected difficulty, timestamps, sequential nonces, balances, Ed25519 signatures and coinbase rewards.
- Fork choice requires strictly greater cumulative work and a validated candidate, not merely peer-reported height.
- Reorg recovery retries transaction dependencies and retains losing blocks. The chain snapshot is authoritative for pending transactions; a stale mirror no longer silently overrides it.
- Atomic file replacement, strict chain reads, encrypted wallets, key-pair validation and no-overwrite backup/import are already present.
- Peer discovery, bounded request/response bodies, pool limits, RLock state access and network callbacks outside the lock already exist.
- Explorer pagination, confirmations and persistent reorg diagnostics are implemented.
- Docker host ports bind to loopback. Existing README explicitly limits deployment to a trusted testnet.

## Findings and acceptance criteria

| ID | Severity | Priority | Finding |
| --- | --- | --- | --- |
| A01 | High | P0 | Untrusted peer destinations and unauthenticated administrative actions |
| A02 | High | P0 | Synchronous unbounded mining and expensive operations under state lock |
| A03 | High | P1 | Partial commits across files and uncertain behavior after persistence failure |
| A04 | High | P1 | Concurrent wallet creation can overwrite keys |
| A05 | Medium | P1 | Consensus identity omits parameters and signed network domain |
| A06 | Medium | P1 | Header sync lacks incremental protocol and early contextual checks |
| A07 | Medium | P1 | Archive grows despite bounded pools |
| A08 | Medium | P1 | Reorg/sync interleavings and propagation require stronger invariants |
| A09 | Medium | P1 | Numeric limits and mempool selection need aggregate policy |
| A10 | Medium | P1 | Multiple writers are not coordinated |
| A11 | Medium | P2 | Wallet schema and import snapshot validation |
| A12 | Medium | P2 | Repeated full validation, indexing and JSON rewrites |
| A13 | Low | P2 | Node module size and reproducibility gaps |

### A01 — Network trust boundary

Evidence: src/node.py:136–162, 272–292, 1151–1244; src/http_client.py:_request.
URL normalization is syntactic, not an outbound destination policy. Peer registration/discovery can accept destinations outside the intended network; standard urllib follows redirects by default. Administration (peer changes, discovery, sync and mining) has no authentication. This is an acknowledged trusted-testnet limitation, but a blocker for public deployment.

Remediation: separate authenticated operator actions from peer protocol; explicit testnet allowlist or deployment-aware destination policy including resolution and redirects; bounded concurrency, request budget and total deadlines. Preserve intentional Docker/loopback connectivity in a dedicated trusted mode. Test rejection using mocked resolution/transport only; never probe third-party endpoints. Test authorization, redirect policy, peer limits and normal three-node operation.

### A02 — Mining and lock contention

Evidence: src/node.py:238–270, 1085–1114; src/block.py:mine; src/blockchain.py:319–371.
Mining executes a potentially long nonce search while holding the shared request lock. Other reads and writes wait; a client timeout does not cancel the server operation. At maximum difficulty the expected work is substantial. Status validation also runs under this lock.

Remediation: cancellable bounded mining jobs using immutable snapshots; release the lock during computation; on completion verify the parent tip and transaction assumptions before committing. Restrict outstanding work. Tests: health/status stay responsive, competing tip invalidates stale work, cancellation leaves no partial state, simultaneous submissions preserve consensus.

### A03 — Crash consistency

Follow-up (Mission 002-B): state snapshot errors propagate and quarantine the
node; the local CLI exits nonzero. Restart reloads authoritative state and
rebuilds derived indexes. The commit outcome can be uncertain if an auxiliary
write or post-replacement directory fsync fails; multi-file transactionality
and complete crash reconciliation remain open in Mission 002-C. The
[transactional storage design](transactional-storage-design.md) specifies
the proposed boundary and migration gates; no runtime SQLite migration is
claimed.

Evidence: src/blockchain.py:211–270, 426–432, 717–736; src/node.py:423–447, 597–605, 967–970; src/storage_utils.py:atomic_write_json.
Atomicity applies to each file separately. In-memory mutations precede saves; failures can leave a running node with state that was not durably committed. A crash after authoritative chain save but before derived indexes, fork pools or reorg history updates can leave inconsistent auxiliary state. Startup rebuilds the transaction index and mempool mirror, which mitigates part of this risk.

Remediation: define commit boundary and failure policy; transactional storage (SQLite is a candidate, not a mandated choice), schema migrations and restart reconciliation. Before migration, fail closed on authoritative commit errors or roll back complete mutations. Test injected write failures and process interruption between persistence stages; compare chain, balances, nonces, mempool and indexes after restart. Preserve existing data and verify migration on copies.

### A04 — Wallet creation race

Follow-up (Mission 002-A): implementation addresses the creation race by
defaulting wallet saves to exclusive publication and making authorized updates
explicit. Coordinated regression tests cover concurrent creation, preservation
of the winning keystore, and injected publication failure. This is a follow-up
to the baseline finding below, not a rewrite of the historical audit.
Concurrent intentional updates and strict import snapshot validation are out
of scope; validation results are reported in the implementation PR.

Evidence: src/wallet.py:save, load_or_create; src/qchain.py:113–128; src/storage_utils.py:atomic_write_json.
Creation checks existence before generating and saving, but normal save uses overwrite=True. Concurrent creators targeting the same name can replace a newly published wallet. Backup/import already use atomic no-overwrite semantics; creation should do the same.

Remediation: distinguish exclusive creation from explicitly authorized password/encryption updates. Use atomic no-overwrite publishing; second creator fails safely or opens the existing wallet via normal password flow. Coordinated concurrent-creation test must demonstrate the first key remains recoverable and unchanged. Do not print keys.

### A05 — Network identity and consensus parameters

Evidence: src/blockchain.py:63–73, 102–146, 677–688; src/transaction.py:payload; src/node.py:496–523.
Genesis identity depends on initial difficulty, not the full consensus parameter set. Nodes with the same genesis but divergent reward/retarget settings may disagree on validity. Transactions sign payload fields without an explicit network domain; across compatible networks with matching account state, replay is possible. Local nonces do not provide cross-network isolation.

Remediation: specify an immutable network manifest and versioned network identifier, verify compatibility on handshake/startup and domain-separate signatures in a deliberate protocol upgrade. Preserve existing v0.2 compatibility or document migration/reset; do not silently alter genesis or signed bytes. Tests for mismatched manifests and signature domains, deterministic vectors.

### A06 — Header synchronization

Evidence: src/node.py:486–623, 1640–1683, 1713–1724.
Full header lists are fetched with a 10,000-entry validation limit; there is no paginated locator-based sync. Preliminary header checks validate shape, hash, PoW and linkage but not expected retarget/timestamp context. Final full-chain validation prevents invalid adoption, but unnecessary downloads remain possible. Peer status is a hint rather than proof, which is appropriate.

Remediation: bounded header batches, common-ancestor locator, contextual header validation before downloading bodies, reuse validated local blocks where appropriate, aggregate deadlines and recomputed work. Test synchronization beyond one batch, false advertised work, malformed headers, interrupted download and a concurrent tip change.

### A07 — Unbounded block archive

Evidence: src/node.py:1299–1310, 1449–1459; src/block_store.py:put, save.
Evicting a block from an orphan/side-branch pool does not evict its copy from BlockStore. Archive size and full-file rewrite cost can grow even when pool counts remain bounded. Persisted pools are loaded without applying the runtime count caps at startup.

Remediation: explicit retention policy, bounded startup loading, parent-aware eviction and archive pruning or disk quotas. Preserve active chain and necessary branch ancestry. Test sustained synthetic valid block intake, restart under caps, and fork adoption after pruning.

### A08 — Interleavings, fork pool and propagation

Evidence: src/node.py:260–270, 493–615, 999–1021, 1321–1409, 1453–1503, 1527–1595.
Releasing the lock during network calls avoids callback deadlock; state can change before control resumes. Final fork-choice revalidation mitigates stale candidates, but peer ranking and responses may reflect different snapshots. Pool eviction can detach descendants; attached orphans are intentionally not rebroadcast, and side-branch adoption may depend on later explicit sync.

Remediation: explicit operation epochs or tip checks, coherent response semantics, ancestor-aware retention, and eventual convergence tests under out-of-order delivery, parallel sync, partitions and restarts. Define which propagation guarantees are intended; do not change fork choice without protocol review.

### A09 — Aggregate numeric and mempool policy

Evidence: src/validation.py:MAX_INTEGER; src/blockchain.py:211–270, 319–331, 462–470, 538–545.
Individual transaction fields are bounded, but sums and account balances use unbounded Python integers. A set of individually valid high-fee transactions can exceed the allowed coinbase field range; a mining attempt then fails validation. This is a long-horizon boundary case rather than an observed current-testnet failure. Mempool admission also replays pending transactions and does not define replacement/expiry.

Remediation: specify monetary range invariants, fee aggregation and deterministic selection that produces a valid coinbase. Add boundary tests with synthetic funded state; define mempool eviction/replacement as separate policy, not consensus.

### A10 — Cross-process state ownership

Follow-up (Mission 002-B): supported node and local-chain CLI entry points
hold a non-blocking OS directory lock over their lifetime. Embedded servers
use the owned-app context; low-level library callers must coordinate ownership.
Existing chain loads are read-only. Locks are cooperative and local-filesystem
scoped; wallet update coordination is not part of this finding.

Evidence: src/node.py:236–250; src/qchain.py:45–51; src/storage_utils.py:atomic_write_json.
RLock is process-local. Two processes using the same state directory can overwrite independent snapshots. README correctly warns against this.

Remediation: enforce exclusive writer ownership or transactional concurrency; refuse duplicate writers with a clear diagnostic. Test two processes on isolated data; ensure read-only tools do not accidentally rewrite authoritative state.

### A11 — Wallet schema and import

Evidence: src/wallet.py:load_wallet_json, load_metadata, load, _decrypt_private_key; src/qchain.py:744–761.
Key pair and KDF constraints are validated, but encrypted/version fields are not strictly typed; missing fields can cause generic errors. Import validates a source and then reads it again for publishing, leaving a potential local time-of-check/time-of-use gap. Legacy plaintext support is intentional.

Remediation: strict versioned schema, validate and publish the exact same snapshot, actionable errors, retain explicit legacy migration. Tests for malformed metadata, replaced source, and unchanged destination on failure. Existing historic demo keys are public per README; do not reuse or attempt to recover them.

### A12 — Scalability

Evidence: src/node.py:312–342, 294–295; src/block_store.py:save; src/transaction_index.py:rebuild_from_chain, find_by_address; src/explorer.py:register_explorer.
Status revalidates the whole chain; block writes rewrite the archive; index rebuilds scan the chain; explorer pagination materializes and sorts complete collections before slicing. Limits on response count do not bound computation.

Remediation: profile synthetic chains before selecting incremental indexing/database changes. Keep full validation as an explicit diagnostic; add indexed pagination and benchmark throughput, p95 latency, memory and disk growth at documented sizes. Verify incremental state equals clean replay.

### A13 — Maintainability and build reproducibility

Evidence: src/node.py (~1,816 lines), src/qchain.py (~817 lines), requirements*.txt, .github/workflows/tests.yml, Dockerfile.
Large closure-based orchestration makes isolated testing and invariants harder to reason about. Dependencies are compatible ranges, not a lock; image and action tags are mutable. Existing CI is valuable.

Remediation: extract peer manager, sync service, fork manager and persistence interface incrementally, after tests pin behavior. Add dependency locking and vulnerability checks, consider immutable CI/image references and least privilege. No large rewrite in one PR.

## Validation evidence

- [Baseline GitHub Actions run 34517644938](https://github.com/LYuuss/Q-CHAIN/actions/runs/34517644938): completed successfully for the audited SHA. Job metadata confirms Python 3.11 and 3.12 pytest + real HTTP smoke steps succeeded, and Docker startup/connect/cleanup succeeded.
- docs/validation.md records 146 pytest cases on Python 3.12.13 from the previous development validation. This is a documented historical count, not an independently rerun count in this audit.
- Representative regression tests inspected: completion regressions, wallet CLI regressions, peer discovery, blockchain, reorg recovery. The tree includes 21 test modules. No coverage percentage is available from this review.
- No local execution, load benchmark, fault injection or independent security verification was performed during Mission 001. PR CI must be checked separately.

## Proposed next missions

1. **002 — State durability and wallet creation:** A03/A04/A10. First fix wallet exclusive creation and failure semantics; design transactional migration as a separate PR. Acceptance: failure/restart and two-writer regressions.
2. **003 — Trusted-network hardening:** A01/A02. Operator authorization, explicit outbound policy and cancellable mining; split into independently reviewed PRs. Acceptance: bounded operations and local network smoke tests.
3. **004 — Sync and fork resilience:** A06/A07/A08. Bounded sync and archive policy; deterministic multi-node fault scenarios.
4. **005 — Protocol identity:** A05/A09. Written protocol proposal, network manifest, monetary limits and migration approval before code changes.
5. **006 — Performance and maintainability:** A11/A12/A13. Wallet schema, metrics, incremental indexes, modular boundaries, dependency reproducibility.

These are proposed priorities, not implemented changes. A01/A02 must be resolved before any public-network deployment; QChain remains loopback/trusted-network only. Research tracks (post-quantum, useful PoW, ZK) remain separate from reliability work.

## Release gate

Keep main untouched. Before a stable v0.2 merge: agree on trusted-testnet scope, resolve or explicitly accept relevant findings, run Python and Docker CI plus crash/concurrency scenarios, review migration and backup procedures, and obtain maintainer approval. Public-network readiness requires a separate threat model, security review and protocol validation.
