# QChain

![QChain Tests](https://github.com/LYuuss/Q-CHAIN/actions/workflows/tests.yml/badge.svg?branch=dev%2Fv0.2)

**An educational blockchain for studying consensus, persistence, and distributed systems.**
Built from scratch in Python; its native coin is **QCOIN**.

QChain implements an account model, Ed25519 signatures, SHA3-256 Proof of Work,
HTTP peers, and recovery from forks. It is an experimental local testnet, with no
real financial value and no production security guarantees.

## Current milestone: v0.2.3-alpha

This milestone completes the operational v0.2 prototype on top of `dev/v0.2`.

- Signed transfers, integer amounts and fees, sequential nonces, encrypted wallets.
- Merkle commitments, bounded difficulty adjustment, heaviest-chain selection.
- Durable chain and mempool, atomic JSON writes, strict authoritative-state loading.
- Persistent orphan and competing-branch pools, recovery of transactions after reorgs.
- Peer discovery, bounded HTTP transport, duplicate handling, thread-safe node state.
- Paginated block and transaction exploration, confirmations, persistent reorg history.
- Wallet metadata, password changes, encrypted backup and import commands.
- Three-node Docker testnet, a standalone HTTP smoke scenario, automated tests and CI.

Post-quantum signatures, useful Proof of Work, and zero-knowledge privacy remain
research directions; they are not implemented. See the [roadmap](docs/roadmap.md).

## Install

Use Python **3.11 or 3.12**. Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
The runtime dependencies are `cryptography` and `Flask`; networking uses the
Python standard library. No extra `requests` installation is required.

## Try it without Docker

Run a complete, disposable scenario with real HTTP servers:

```bash
python scripts/smoke_testnet.py
```

It starts three nodes on random loopback ports, discovers peers, broadcasts a
transfer, restarts a node, mines the transfer, and synchronizes a fourth node.
It prints `"result": "PASS"` and removes its temporary data. This scenario uses
a separate low-difficulty test network; it does not use your wallets or chains.

For an interactive local chain:

```bash
python src/qchain.py wallet-create alice
python src/qchain.py wallet-create bob
python src/qchain.py wallet-create miner
python src/qchain.py mine alice
python src/qchain.py send alice bob 10 --fee 2
python src/qchain.py mine miner
python src/qchain.py balance bob
python src/qchain.py validate
```

Wallet creation prompts for a password. Signing prompts for the sender's
password; mining only needs the recipient's public address. A fresh example
leaves Bob with **10 QCOIN**, Alice with **38 QCOIN**, and the miner with **52 QCOIN**.

## Run the Docker testnet

Install Docker with Compose, then:

```bash
bash scripts/start_docker_testnet.sh
python src/qchain.py node-mine 5001 alice
python src/qchain.py node-send 5001 alice bob 10 --fee 2
python src/qchain.py node-mine 5002 miner
python src/qchain.py node-status 5003
python src/qchain.py node-balance 5003 bob
```

The script builds and connects three nodes. Ports `5001`, `5002`, and `5003` are
bound to `127.0.0.1`. Wallets stay on the host, and only signed transactions are
sent to nodes. Local CLI state and Docker node state are separate chains.

```bash
bash scripts/stop_docker_testnet.sh
```

See [Docker operations](docs/docker-testnet.md) for backups and resets.

## Inspect and manage

```bash
python src/qchain.py node-blocks 5001 --limit 10
python src/qchain.py node-block 5001 1
python src/qchain.py node-transactions 5001 --limit 10
python src/qchain.py node-reorgs 5001
python src/qchain.py node-peers 5001
python src/qchain.py node-discover-peers 5001
python src/qchain.py node-sync 5001
python src/qchain.py wallet-info alice
python src/qchain.py wallet-backup alice ./backups/alice.json
python src/qchain.py wallet-import ./backups/alice.json alice-restored
python src/qchain.py wallet-password alice-restored
```

Use `python src/qchain.py --help` for all commands. Failures return a nonzero exit
status. Set `QCHAIN_DATA_DIR` or use `python src/qchain.py --data-dir PATH COMMAND`
to select an isolated local chain and wallet directory.

## Repository map

| Location | Purpose |
| --- | --- |
| `src/block.py`, `src/blockchain.py`, `src/transaction.py` | Blocks, consensus, account state, mempool |
| `src/node.py`, `src/http_client.py` | HTTP API, peers, broadcast, sync, fork pools |
| `src/explorer.py`, `src/transaction_index.py` | Paginated queries and transaction index |
| `src/storage_utils.py`, `src/block_store.py` | Atomic files and block lookup |
| `src/wallet.py`, `src/crypto_provider.py` | Encrypted keys and Ed25519 signing |
| `src/qchain.py` | CLI |
| `tests/`, `scripts/` | Regression suite, smoke scenario, testnet operations |
| `data/` | Ignored local runtime data; created on first use |

## Documentation

- [Usage and wallet commands](docs/usage.md)
- [Architecture and consensus](docs/core-concepts.md)
- [HTTP API reference](docs/api-reference.md)
- [Storage and recovery](docs/storage-layer.md)
- [Docker testnet](docs/docker-testnet.md)
- [Completed milestone and future research](docs/roadmap.md)
- [Validation and release notes](docs/validation.md)

The node is intended for a trusted local network. It has no authentication,
public-network abuse protection, or cross-process data locking. Run one node
process per data directory. Existing demo keys in Git history are public; create
your own experiment wallets. Never put real funds or production keys in QChain.

Licensed under [MIT](LICENSE).
