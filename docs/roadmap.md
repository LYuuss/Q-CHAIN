# QChain Roadmap

This roadmap describes possible next steps after v0.2.2-alpha.

---

## Current Stable Development State

```text
v0.2.2-alpha
```

Implemented:

```text
persistent storage layer
orphan pool
side-branch pool
persistent mempool
reorg mempool recovery
transaction index
atomic node storage
atomic wallet storage
Docker testnet
header-first sync
50 passing tests
```

---

## Recommended Next Step: Peer Discovery

The next major feature should be peer discovery.

Current peer handling is manual.

A better network layer could include:

```text
GET /peers
POST /peers
peer exchange
deduplication
self-peer rejection
unreachable peer cleanup
bootstrap peers
periodic peer sync
```

Suggested tests:

```text
test_peer_exchange_between_nodes
test_node_rejects_self_peer
test_duplicate_peer_not_added_twice
test_unreachable_peer_can_be_ignored
```

---

## Block Explorer Improvements

The transaction index creates a first mini block explorer.

Possible next improvements:

```text
GET /addresses/<address>/balance
GET /blocks
GET /blocks/<height>
GET /transactions
pagination
transaction confirmations
block confirmations
pretty CLI output
```

---

## Reorg Diagnostics

Add persistent reorg history:

```text
reorg_history.json
GET /reorgs
node-reorgs CLI command
old_tip
new_tip
old_height
new_height
recovered_transaction_count
rejected_transaction_count
reason
timestamp
```

---

## Network Protocol Improvements

Possible improvements:

```text
peer discovery
peer scoring
request timeouts
broadcast deduplication
block inventory messages
transaction inventory messages
anti-spam limits
```

---

## Consensus Improvements

Possible improvements:

```text
better cumulative work model
difficulty retarget refinements
checkpoint support
block size / transaction count limits
timestamp validation
```

---

## Wallet Improvements

Possible improvements:

```text
wallet export
wallet import
password change
keystore backup command
wallet metadata inspection
```

---

## Post-Quantum Cryptography Research

Possible future direction:

```text
ML-DSA signatures
SLH-DSA signatures
hybrid classical + post-quantum signatures
post-quantum wallet format
```

---

## Useful Proof-of-Work Research

Long-term research direction:

```text
useful Proof-of-Work
verifiable computation
compute marketplace
recycled mining rewards
QCOIN-based compute purchasing
```

---

## Privacy / ZK Research

Possible long-term research direction:

```text
STARK-based proofs
private transaction metadata
validity proofs
zk-friendly transaction model
```

---

## Whitepaper

A future whitepaper could cover:

```text
motivation
architecture
consensus
transaction model
wallet model
networking
fork handling
storage layer
security limitations
roadmap
```
