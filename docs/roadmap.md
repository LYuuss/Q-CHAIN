# QChain roadmap

## Completed operational milestone: v0.2.3-alpha

The `dev/v0.2` implementation already supplied persistent indexes, fork pools,
reorg transaction recovery, atomic JSON storage, encrypted wallets, and peer
discovery. This milestone completes and tests their operational integration:

- Remove the undeclared networking dependency and share bounded JSON transport.
- Validate transaction/header types, numeric limits, addresses, timestamps, genesis, and proofs.
- Reject a damaged authoritative chain without overwriting it.
- Recover the mempool from its authoritative snapshot despite a missing/stale mirror.
- Preserve nonce dependencies and losing branches across reorganizations and restarts.
- Serialize node state access while permitting peer callbacks during HTTP waits.
- Add block-height lookup, pagination, confirmations, and persistent reorg diagnostics.
- Complete missing CLI inspection commands and meaningful failure exit codes.
- Add wallet metadata, encrypted backup/import, password change, and key-pair validation.
- Exclude generated state/demo wallets from Git and add Docker health checks.
- Exercise real HTTP nodes and run CI for development branches as well as main.

This completes a demonstrable educational v0.2 testnet. It is not a production
cryptocurrency launch or completion of every long-term research idea.

## Next engineering work

| Area | Candidate work | Why it needs its own milestone |
| --- | --- | --- |
| Persistence | Transactional database, schema migrations, crash-injection recovery | Atomic JSON files do not provide a transaction across all node state. |
| Execution | Cancellable background mining, optimistic tip checks | Synchronous mining holds the node's state lock. |
| Networking | Authenticated administration, explicit network identity, peer lifecycle/scoring | Current peers and HTTP API assume a trusted testnet. |
| Scale | Incremental indexes, bounded archive pruning, paginated header/inventory sync | Full-chain validation and JSON rewrites are intentionally simple. |
| Consensus | Versioned protocol upgrades and retarget experiments | New rules need compatibility planning and independent validation. |
| Testing | Process-kill fault injection and longer adversarial network simulations | The current suite covers specified regressions and controlled HTTP integration. |

## Prioritized follow-up after Mission 001

See the [technical audit](technical-audit.md) for the baseline, evidence,
severity, and acceptance criteria. The following sequence is proposed for
maintainer review; it does not mark any additional feature as implemented.

| Mission | Scope | Acceptance focus |
| --- | --- | --- |
| 002 | State durability, exclusive wallet creation, writer ownership (A03/A04/A10) | No silent key replacement; failure/restart invariants; transactional migration plan |
| 003 | Network trust boundary and cancellable mining (A01/A02) | Operator authorization, bounded outbound requests, responsive node |
| 004 | Sync and fork resilience (A06/A07/A08) | Bounded batches/archive, convergence through partitions and restarts |
| 005 | Protocol identity and numeric policy (A05/A09) | Reviewed versioned manifest and migration; deterministic consensus tests |
| 006 | Wallet schema, performance, maintainability (A11/A12/A13) | Strict wallet snapshots, measured indexing performance, modular boundaries and reproducible builds |

Mission 002-A addresses A04: exclusive wallet creation reuses atomic
non-overwriting publication, with regression tests for competing creators and
publication failures. Intentional password/encryption updates remain explicit.
Mission 002-B addresses A10 for supported process entry points and mitigates
A03 with explicit fail-closed persistence handling and restart recovery.
Mission 002-C design: see [transactional storage design](transactional-storage-design.md)
for the proposed SQLite boundary, draft schema, reversible migration and
acceptance gates. This is a design milestone, not a backend switch. Runtime
multi-file transactionality (A03) and A11 (wallet schema/import snapshot
validation) remain open. See the audit for the original finding.

Mission 002-C1 introduces an injectable chain/mempool repository and staged
commit-before-publish transitions. JSON remains the default; the node-wide
unit of work and SQLite implementation follow in C2–C4.
Mission 002-C2 adds the opt-in SQLite full-node snapshot repository and a
chain-only adapter, with version/revision and rollback regression coverage.
C3 provides offline non-destructive import and verified JSON export; runtime
activation is implemented in C4 using explicit JSON/SQLite selection,
complete node checkpoints before network effects or acknowledgment, and
chain-only CLI integration. C5 operational validation remains pending; JSON
is still the default and A03 is not closed.

A01/A02 block deployment to an untrusted network. Until then, keep the
trusted local testnet boundary. Each mission may be split into small PRs
against the development branch; protocol changes require separate approval.
The maintainer controls the stable release and merge to main. Authorized
agents may merge their own approved-scope PRs into dev/v0.2 under AGENTS.md's
CI and review gate.

## Research tracks

Post-quantum signatures (ML-DSA, SLH-DSA, or hybrid schemes), useful Proof of Work,
verifiable computation, compute purchasing in QCOIN, and STARK-based privacy are
separate research tracks. None is implemented in this milestone. Each requires
a threat model, protocol design, reference implementation, and evaluation before
being described as a QChain capability.
