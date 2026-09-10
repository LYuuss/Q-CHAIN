# Usage

Run from the repository root with Python 3.11 or 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python scripts/smoke_testnet.py
```

The smoke scenario creates temporary data and real local HTTP servers. It exits
on a failed assertion and prints a JSON `PASS` summary on success.

## Wallet lifecycle

```bash
python src/qchain.py wallet-create alice
python src/qchain.py wallet-create bob
python src/qchain.py wallet-create miner
python src/qchain.py wallets
python src/qchain.py wallet-info alice
```

Creation prompts for a password twice. Existing wallets are loaded without
being replaced. Names are normalized to lowercase and contain 1–64 letters,
digits, underscores, or hyphens, beginning with a letter or digit.

Metadata inspection shows address, public key, encryption state, and format
version. It does not unlock or expose the private key.

```bash
python src/qchain.py wallet-password alice
python src/qchain.py wallet-backup alice ./backups/alice.json
python src/qchain.py wallet-import ./backups/alice.json alice-restored
```

Password changes first unlock the wallet, then request the new password twice.
The address remains the same. Backup keeps the encrypted keystore; import
verifies the password and matching key pair. Neither backup nor import
replaces an existing destination. Backups encrypted with an old password remain
protected by that old password after the original wallet's password changes.

For a legacy plaintext keystore already stored in your wallet directory:

```bash
python src/qchain.py wallet-encrypt alice
```

Use new wallets instead of historical repository demo keys. Wallets are not
recoverable from a node's chain, transaction history, or a forgotten password.

## Local chain

```bash
python src/qchain.py mine alice
python src/qchain.py send alice bob 10 --fee 2
python src/qchain.py mempool
python src/qchain.py mine miner --max-tx 10
python src/qchain.py balance alice
python src/qchain.py balance bob
python src/qchain.py status
python src/qchain.py validate
```

Local commands use `data/chain.json`. Sending checks balance, fee, signature,
and the next nonce, including pending transfers. Mining is synchronous. Its
limit counts transfers, excluding the reward transaction; zero mines only the
reward. Difficulty can increase after repeated fast blocks.

Choose a separate local data directory by placing the option before the command:

```bash
python src/qchain.py --data-dir ./experiments/demo wallet-create alice
python src/qchain.py --data-dir ./experiments/demo mine alice
```

Alternatively, set `QCHAIN_DATA_DIR` to an absolute path. The local CLI and nodes
use separate default chain files even when they share the same data root.
Do not run concurrent local CLI writers against one chain file.

## Standalone HTTP nodes

Open separate terminals and activate the environment in each:

```bash
python src/node.py --port 5001 --advertised-url http://127.0.0.1:5001
```

```bash
python src/node.py --port 5002 --advertised-url http://127.0.0.1:5002
```

Then connect them from another terminal:

```bash
python src/qchain.py node-connect 5001 5002
python src/qchain.py node-peers 5001
python src/qchain.py node-mine 5001 alice
python src/qchain.py node-send 5001 alice bob 10 --fee 2
python src/qchain.py node-mine 5002 miner
python src/qchain.py node-balance 5001 bob
```

`node-connect` registers both directions. Adding more peers and running
`node-discover-peers` imports the peers they know. Discovery does not itself
synchronize a chain; use `node-sync` after reconnecting an out-of-date node.

A node's `--data-dir` is its entire state directory. One process must own each
writable directory. The default bind host is loopback. An advertised URL must
be reachable by the peers; it is not necessarily the same hostname the user
uses to access the node.

## Exploration and synchronization

```bash
python src/qchain.py node-status 5001
python src/qchain.py node-chain 5001
python src/qchain.py node-headers 5001
python src/qchain.py node-blocks 5001 --limit 10 --offset 0
python src/qchain.py node-block 5001 1
python src/qchain.py node-transactions 5001 --limit 10
python src/qchain.py node-mempool 5001
python src/qchain.py node-orphans 5001
python src/qchain.py node-side-branches 5001
python src/qchain.py node-reorgs 5001
python src/qchain.py node-discover-peers 5001
python src/qchain.py node-sync 5001
```

For a specific transaction, pass its hash from the send response to
`node-transaction NODE HASH`. For an address's history, run
`node-address-transactions NODE ADDRESS`. `node-balance` accepts either a local
wallet name or a raw address. `node-block` accepts a height or full block hash.

`node-blocks`, `node-transactions`, and `node-reorgs` accept `--limit` and
`--offset`. Address history supports those parameters through the HTTP API.

## Exit codes and troubleshooting

The CLI returns 0 on success, 1 for operation/HTTP failures, 2 for invalid
command arguments, and 130 for an interrupted password prompt or command.
Read a sync response's `errors` and `adopted_new_chain` fields: a completed sync
request can find no valid heavier chain.

- Connection refused: start the node and check the port.
- Insufficient funds: mine on the same chain/node you are sending through.
- Missing wallet: create it in the selected local wallet directory.
- Wrong password: use the password for that particular original or backup file.
- Invalid stored chain: stop and follow [recovery instructions](storage-layer.md).
- Mining timeout: inspect `/status` before retrying; timeout does not cancel mining.
- Stale node: verify its peers, then run `node-sync`.

`src/main.py` is a compatibility entry point for the same CLI.

See `python src/qchain.py --help` and `python src/node.py --help` for arguments.
