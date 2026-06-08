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

Install dependencies:

```bash
pip install -r requirements.txt
```

Current requirements:

```text
cryptography
flask
```

---

## 2. Create Wallets

Create wallets:

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

Each wallet is stored in:

```text
data/wallets/
```

Wallet private keys are encrypted locally. The password is required to sign transactions.

---

## 3. List Wallets

```bash
python3 src/qchain.py wallets
```

Example output:

```text
alice: 41e34b96bb3907870ff91f55b3f7f5b2ee44d1aa | encrypted
bob: b36df18622f1e635d6c6374ff0f7ea058cc3bc1c | encrypted
miner: 10efef8e846429f93fdab087978fa6018deda59e | encrypted
```

---

# Local CLI Mode

Local CLI mode is useful for simple single-chain testing.

It uses:

```text
data/chain.json
```

It does not interact with Docker nodes.

---

## 4. Local Status

```bash
python3 src/qchain.py status
```

Shows:

```text
height
latest hash
next difficulty
cumulative work
mempool size
chain validity
```

---

## 5. Local Mining

```bash
python3 src/qchain.py mine alice
```

This mines on the local chain and rewards Alice.

---

## 6. Local Balance

```bash
python3 src/qchain.py balance alice
```

Important: this checks the local CLI chain only.

It does not check Docker node balances.

---

## 7. Local Send

```bash
python3 src/qchain.py send alice bob 10 --fee 2
```

This creates a signed transaction and adds it to the local mempool.

---

## 8. Local Mempool

```bash
python3 src/qchain.py mempool
```

---

## 9. Validate Local Chain

```bash
python3 src/qchain.py validate
```

---

# HTTP Node Mode

HTTP node mode communicates with running QChain nodes.

This is the recommended mode for the Docker testnet.

---

## 10. Node Status

```bash
python3 src/qchain.py node-status 5001
```

Equivalent URL:

```text
http://127.0.0.1:5001/status
```

You can also use a full URL:

```bash
python3 src/qchain.py node-status http://127.0.0.1:5001
```

---

## 11. Node Balance

```bash
python3 src/qchain.py node-balance 5001 bob
```

This checks Bob's balance on node `5001`.

To compare all nodes:

```bash
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-balance 5002 bob
python3 src/qchain.py node-balance 5003 bob
```

This is useful to verify that all nodes have the same state.

---

## 12. Node Mining

```bash
python3 src/qchain.py node-mine 5001 alice
```

This asks node `5001` to mine a block and pay the block reward to Alice.

With a maximum number of transactions:

```bash
python3 src/qchain.py node-mine 5001 miner --max-tx 5
```

---

## 13. Node Send

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

---

## 14. Node Mempool

```bash
python3 src/qchain.py node-mempool 5001
```

To check all three Docker nodes:

```bash
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-mempool 5002
python3 src/qchain.py node-mempool 5003
```

---

## 15. Node Sync

```bash
python3 src/qchain.py node-sync 5001
```

This asks node `5001` to synchronize with its peers.

The node compares cumulative work and adopts the heaviest valid chain if needed.

---

## 16. Node Connect

For non-Docker local nodes, you can connect two nodes with:

```bash
python3 src/qchain.py node-connect 5001 5002
```

This connects the nodes in both directions.

For Docker nodes, use the Docker-specific script instead because containers must use internal service names such as `http://node1:5000`.

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

# Useful Notes

## Local balance vs node balance

This command:

```bash
python3 src/qchain.py balance bob
```

checks the local CLI chain.

This command:

```bash
python3 src/qchain.py node-balance 5001 bob
```

checks the Docker or HTTP node chain.

Do not confuse them when testing the Docker testnet.

---

## Restarting Docker

If the Docker testnet is already built:

```bash
docker compose up -d
```

If source code used by Docker changed:

```bash
docker compose up -d --build
```

If only `src/qchain.py` changed, Docker does not need to be rebuilt because the CLI runs locally on your machine.

---

## Stop Docker

```bash
docker compose down
```

---

## View Logs

```bash
docker compose logs -f
```

For one node:

```bash
docker compose logs -f node1
```