# QChain

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.

The project is designed as an educational and research-oriented blockchain prototype. Its long-term goal is to explore how a blockchain can evolve toward post-quantum cryptography, quantum-resistant signatures, and STARK-based privacy mechanisms.

The native coin of the network is called **QCOIN**.

QChain is not production-ready and must not be used with real funds.

---

## Current Status

QChain currently supports:

```text
Proof-of-Work mining
dynamic difficulty adjustment
block headers
Merkle roots
transaction hashing
signed transactions
encrypted wallets
balances
nonces
replay protection
mining rewards
transaction fees
mempool
fee-aware transaction selection
persistent chain storage
persistent wallet storage
HTTP nodes
block broadcasting
transaction broadcasting
node synchronization
heaviest-chain rule
Docker-based 3-node local testnet
CLI tools for local and node usage
testnet helper scripts
```

---

## Project Structure

```text
qchain/
├── data/
│   ├── chain.json
│   ├── wallets/
│   └── docker/
│
├── docs/
│   ├── core-concepts.md
│   ├── usage.md
│   └── docker-testnet.md
│
├── scripts/
│   ├── connect_docker_nodes.sh
│   ├── start_docker_testnet.sh
│   ├── stop_docker_testnet.sh
│   ├── reset_docker_testnet.sh
│   ├── status_all.sh
│   ├── mempool_all.sh
│   └── balance_all.sh
│
├── src/
│   ├── block.py
│   ├── blockchain.py
│   ├── config.py
│   ├── crypto_provider.py
│   ├── node.py
│   ├── qchain.py
│   ├── transaction.py
│   └── wallet.py
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

Current dependencies:

```text
cryptography
flask
```

---

## Quick Start

Create wallets:

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner
```

Start the Docker testnet:

```bash
bash scripts/start_docker_testnet.sh
```

Mine a block:

```bash
python3 src/qchain.py node-mine 5001 alice
```

Send QCOIN from Alice to Bob:

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

Check mempools:

```bash
bash scripts/mempool_all.sh
```

Mine the transaction:

```bash
python3 src/qchain.py node-mine 5002 miner
```

Check balances:

```bash
bash scripts/balance_all.sh bob
bash scripts/balance_all.sh miner
```

Stop the testnet:

```bash
bash scripts/stop_docker_testnet.sh
```

---

## Local CLI Commands

```bash
python3 src/qchain.py status
python3 src/qchain.py wallets
python3 src/qchain.py balance alice
python3 src/qchain.py mine alice
python3 src/qchain.py send alice bob 10 --fee 2
python3 src/qchain.py mempool
python3 src/qchain.py validate
```

These commands use the local chain:

```text
data/chain.json
```

---

## HTTP Node Commands

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-sync 5001
python3 src/qchain.py node-connect 5001 5002
```

When using Docker, prefer the helper scripts for connecting and checking all nodes.

---

## Documentation

More detailed documentation is available in:

```text
docs/core-concepts.md
docs/usage.md
docs/docker-testnet.md
```

Recommended reading order:

1. `docs/core-concepts.md`
2. `docs/usage.md`
3. `docs/docker-testnet.md`

---

## Docker Testnet

The Docker testnet runs three nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Inside Docker, nodes communicate through:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

Each node has its own chain storage under:

```text
data/docker/
```

---

## Security Warning

QChain is experimental software.

Do not use it with real funds.

The current implementation is intended for learning, research, and prototyping only.

---

## Roadmap

Planned research and development directions:

```text
post-quantum signatures
ML-DSA integration
SLH-DSA integration
signature benchmarks
quantum-resistant Proof-of-Work analysis
orphan block pool
better fork management
block header synchronization
peer discovery
network protocol improvements
STARK-based privacy layer
zero-knowledge experiments
whitepaper
```