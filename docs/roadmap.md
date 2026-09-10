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

## Research tracks

Post-quantum signatures (ML-DSA, SLH-DSA, or hybrid schemes), useful Proof of Work,
verifiable computation, compute purchasing in QCOIN, and STARK-based privacy are
separate research tracks. None is implemented in this milestone. Each requires
a threat model, protocol design, reference implementation, and evaluation before
being described as a QChain capability.
