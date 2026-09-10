# v0.2.3-alpha validation and release notes

## Base and scope

Changes are based on `origin/dev/v0.2` at `0c99df7` (Add peer discovery).
The clean baseline could not collect 11 test modules because `requests` was
imported but absent from the requirements. Both networking callers now use a
shared standard-library JSON client.

## Verification performed

- **146 pytest cases passed** on Python 3.12.13.
- The standalone smoke scenario passed with three real threaded HTTP nodes and
  a fourth joining node. It covered peer discovery, triangle broadcasts,
  transaction propagation, restart with a pending transaction, confirmed
  balances, and downloading missing blocks through header-first sync.
- Fresh imports and the CLI help entry point succeeded using only the declared
  runtime dependencies. Python sources compiled successfully.

The tested environment had Flask 3.1.3, cryptography 50.0.1, and pytest 9.1.1.
The dependency files specify compatible ranges rather than a complete frozen
transitive lockfile.

Regression coverage includes malformed JSON/transactions/headers, integer and
address checks, future timestamps, foreign genesis, invalid downloaded blocks,
peer URL handling, authoritative mempool recovery, concurrent mining, two
successive fork switches, transaction confirmations, pagination, encrypted
wallet backup/import/password change, and simulated atomic-write failure.

Existing tests were updated where the intended behavior changed: a corrupt
chain must remain untouched, and a disconnected main-chain block must remain
in the competing-branch pool instead of disappearing after adoption.

## Gates prepared but not run here

Docker was not available in the development container, so the Docker image and
Compose startup were not executed locally. CI now includes those checks plus
the Python suite and real HTTP scenario on Python 3.11 and 3.12. Remote GitHub
Actions results require the branch to be published; they are not claimed here.

## Compatibility and limits

The stricter numeric, genesis, timestamp, and address rules can reject old
invalid experimental chains that earlier versions accepted. Preserve a backup
before upgrading. Existing valid integer-based chains and encrypted v2 wallets
continue to use their existing file formats.

The node remains a trusted-network prototype: unauthenticated administration,
synchronous mining, one process per state directory, whole-chain in-memory
validation, per-file atomicity rather than multi-file transactions, no pruning
of the complete historical block archive, and no production security audit.

The repository no longer tracks generated state, historical demo wallets, or
the obsolete documentation ZIP. This does not remove keys from Git history;
those keys must continue to be treated as public demo material.

## Reproduce

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python scripts/smoke_testnet.py
```
