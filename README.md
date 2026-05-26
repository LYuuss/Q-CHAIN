# QChain

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.

The long-term goal of QChain is to explore the design of a blockchain that can evolve toward:

- Proof of Work consensus
- Post-quantum cryptography
- Quantum-resistant transaction signatures
- STARK-based privacy features
- A research-oriented blockchain architecture

The native coin of the network is called **QCOIN**.

---

## Current Status

QChain is currently an educational prototype.

It already supports:

- Blocks
- Proof of Work mining
- Block headers
- Merkle roots
- Transaction hashing
- Wallets
- Signed transactions
- Balances
- Nonces
- Replay protection
- Mining rewards
- Transaction fees
- Mempool
- Fee-aware transaction selection
- Persistent blockchain storage
- Persistent wallets
- Command-line interface

It is not production-ready and should not be used with real funds.

---

## Current Limitations

QChain is still a prototype.

Missing features include:

- P2P networking
- Multiple nodes
- Block broadcasting
- Transaction broadcasting
- Fork handling
- Heaviest-chain rule
- Dynamic difficulty adjustment
- Encrypted wallet files
- Proper address format
- Post-quantum signatures
- ML-DSA or SLH-DSA support
- Signature benchmarks
- Quantum-resistant Proof-of-Work analysis
- STARK-based privacy layer
- Docker-based local testnet
- Full whitepaper

---

## Project Structure

```text
qchain/
├── data/
│   ├── chain.json
│   └── wallets/
│       ├── alice.json
│       ├── bob.json
│       └── miner.json
│
└── src/
    ├── block.py
    ├── blockchain.py
    ├── crypto_provider.py
    ├── transaction.py
    ├── wallet.py
    ├── qchain.py
    └── main.py
```  


## Requirements

QChain currently uses Python.

Install the required dependency:

pip install cryptography