# AGENTS.md — QChain engineering instructions

These instructions apply only to QChain. QChain is an experimental Python
blockchain and trusted local testnet. QCOIN has no real financial value.
Never describe it as a production-ready or audited cryptocurrency.

## Collaboration and Git

- The maintainer defines goals, approves protocol decisions and controls releases.
  An authorized agent may implement an agreed specification autonomously.
- Read the actual target branch, relevant tests and documentation before editing.
  Use the repository, not conversation history, as the source of truth.
- Base each task on the current `dev/v0.2` (or the explicitly designated
  development branch). Create a dedicated `feature/`, `fix/`, `test/`,
  `docs/` or `chore/` branch. Keep changes narrowly scoped.
- Never push directly to `main` or the development branch, merge a PR, change
  branch protection, publish/move tags, force-push or rewrite history without
  explicit maintainer authorization. Do not bypass branch protections.
- Open a PR against the designated development branch. Include the problem,
  approach, trade-offs, files affected, compatibility, test evidence, and
  remaining risks. Leave merging to the maintainer.
- Do not include credentials, private keys, generated state, personal data,
  wallet backups or unrelated changes. Never print secret key material.

## Architecture and correctness

- `block.py`, `transaction.py`, `blockchain.py`: deterministic validation,
  account transitions and fork choice. Keep consensus independent of HTTP.
- `node.py`, `http_client.py`: transport, peer management, synchronization and
  orchestration. Preserve the shared bounded transport; do not add undeclared
  dependencies.
- `validation.py`: shared protocol and boundary checks; reject malformed data
  before expensive work. Do not trust peer-reported state or work as proof.
- `storage_utils.py`, `block_store.py`, `transaction_index.py`: persistence
  and derived indexes. Preserve authoritative chain/mempool state and rebuild
  derived data when necessary. Never silently reset corrupt authoritative data.
- `wallet.py`, `crypto_provider.py`: wallet and signing operations; never
  invent cryptographic primitives. Preserve existing encrypted-wallet access.
  Use explicit no-overwrite semantics for new wallets and backup/import paths.
- `explorer.py`, `qchain.py`: read APIs and CLI. Keep public API compatibility
  or explicitly document and approve breaking changes.
- Consensus or wire-format changes (genesis, signatures, transaction IDs,
  difficulty, rewards, timestamps) require a separate specification and
  explicit migration/network-version decision. Add deterministic test vectors.
- Protect shared state, never hold the state lock during unbounded network I/O,
  recheck state after releasing the lock, and do not treat individual atomic
  file writes as multi-file transactions. One writer per data directory until
  cross-process coordination is implemented.
- Keep the trusted-local-network deployment boundary. Changes affecting
  authentication, outbound requests, key management or protocol safety require
  explicit security review. Do not test against third-party/live systems.

## Testing and delivery

Use Python 3.11/3.12 in a clean environment:
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python scripts/smoke_testnet.py
docker compose up -d --build --wait
bash scripts/connect_docker_nodes.sh
docker compose down
```
Use isolated temporary data and low difficulty for deterministic tests.
Add regression tests for every behavior fix; cover failure paths, invalid
input and state invariants. Concurrency changes need coordinated-thread tests;
storage changes need failure injection and restart tests; networking changes
need bounded mock tests plus real HTTP smoke coverage when feasible.
Avoid weakening assertions or skipping existing tests to obtain a green build.

The above are validation targets, not proof of execution. Report exactly which
commands ran, environment, outcomes, CI links and which checks remain pending.
Never invent passing test counts. For documentation-only changes, run applicable
doc checks and report whether full CI was run. CI is not a security certification.

## Documentation

English for source documentation and PRs; use clear Markdown. Update only
relevant sections of existing README/docs, preserving installation, examples,
API references, previous features and warnings. Prefer small diffs; keep
implementation status separate from planned work. Record protocol/storage
compatibility, new configuration and operational limits. Update the roadmap
when completing or reprioritizing a milestone; do not claim research features
are implemented. See [technical audit](docs/technical-audit.md) and
[roadmap](docs/roadmap.md).

## Definition of done

- Scope and acceptance criteria met; no unrelated refactoring.
- Existing behavior preserved unless the approved specification changes it.
- New regression coverage and truthful validation evidence.
- Documentation aligned with code and known limitations.
- PR open for maintainer review; no unauthorized merge or release.
