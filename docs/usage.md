# QChain Usage Guide

This document explains how to use QChain from the command line.

QChain provides two main modes:

```text
local CLI mode
HTTP node mode
```

Local CLI mode uses:

```text
data/chain.json
```

HTTP node mode uses a running node, for example:

```text
http://127.0.0.1:5001
```

When using the Docker testnet, prefer the `node-*` commands.

---

## 1. Requirements

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

---

## 2. Wallets

Create wallets:

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

List wallets:

```bash
python3 src/qchain.py wallets
```

Wallets are stored in:

```text
data/wallets/
```

Private keys are encrypted locally. The password is required to sign transactions.

---

# Local CLI Mode

Local CLI mode is useful for simple single-chain testing.

It uses:

```text
data/chain.json
```

It does not interact with Docker nodes.

## Local Status

```bash
python3 src/qchain.py status
```

## Local Mining

```bash
python3 src/qchain.py mine alice
```

## Local Balance

```bash
python3 src/qchain.py balance alice
```

Important: this checks the local CLI chain only. It does not check Docker node balances.

## Local Send

```bash
python3 src/qchain.py send alice bob 10 --fee 2
```

## Local Mempool

```bash
python3 src/qchain.py mempool
```

## Validate Local Chain

```bash
python3 src/qchain.py validate
```

---

# HTTP Node Mode

HTTP node mode communicates with running QChain nodes.

This is the recommended mode for the Docker testnet.

## Node Status

```bash
python3 src/qchain.py node-status 5001
```

The status includes:

```text
height
latest_hash
genesis_hash
cumulative_work
mempool_size
orphan_pool_size
next_block_difficulty
peers
advertised_url
valid
```

## Node Headers

```bash
python3 src/qchain.py node-headers 5001
```

This displays compact block headers from a node.

Equivalent endpoint:

```text
GET /headers
```

## Node Orphans

```bash
python3 src/qchain.py node-orphans 5001
```

This displays the orphan block pool of a node.

Equivalent endpoint:

```text
GET /orphans
```

Expected normal result:

```json
{
  "blocks": [],
  "max_size": 100,
  "size": 0
}
```

## Node Balance

```bash
python3 src/qchain.py node-balance 5001 bob
```

To compare all nodes:

```bash
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-balance 5002 bob
python3 src/qchain.py node-balance 5003 bob
```

## Node Mining

```bash
python3 src/qchain.py node-mine 5001 alice
```

With a maximum number of transactions:

```bash
python3 src/qchain.py node-mine 5001 miner --max-tx 5
```

## Node Send

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

This does the following:

```text
loads Alice wallet
asks for Alice password
signs the transaction
sends it to node 5001
node 5001 validates it
node 5001 adds it to its mempool
node 5001 broadcasts it to peers
```

## Node Mempool

```bash
python3 src/qchain.py node-mempool 5001
```

## Node Sync

```bash
python3 src/qchain.py node-sync 5001
```

The node:

```text
checks peer status
compares cumulative work
downloads headers
validates headers
finds the latest common ancestor
downloads only missing blocks
validates the reconstructed candidate chain
adopts the chain if it is heavier
processes orphan blocks
```

If the node is already up to date, the response should include:

```json
{
  "downloaded_block_count": 0
}
```

## Node Connect

For non-Docker local nodes, connect two nodes with:

```bash
python3 src/qchain.py node-connect 5001 5002
```

For Docker nodes, use the Docker-specific script because containers must use internal service names such as `http://node1:5000`.

---

# Complete Example: Alice Sends QCOIN to Bob

Mine funds to Alice:

```bash
python3 src/qchain.py node-mine 5001 alice
```

Send QCOIN from Alice to Bob:

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

Check mempools:

```bash
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-mempool 5002
python3 src/qchain.py node-mempool 5003
```

Mine the transaction:

```bash
python3 src/qchain.py node-mine 5002 miner
```

Check Bob's balance:

```bash
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-balance 5002 bob
python3 src/qchain.py node-balance 5003 bob
```

Check miner reward:

```bash
python3 src/qchain.py node-balance 5001 miner
```

Expected economics for one transaction:

```text
Alice pays: 10 QCOIN + 2 QCOIN fee
Bob receives: 10 QCOIN
Miner receives: 50 QCOIN reward + 2 QCOIN fee
```

---

# Tests

Run the full test suite:

```bash
python3 -m pytest
```

or:

```bash
bash scripts/run_tests.sh
```

Expected current result:

```text
23 passed
```
