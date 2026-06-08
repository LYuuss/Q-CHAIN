# QChain Core Concepts

QChain is an experimental Proof-of-Work blockchain built from scratch in Python.

This document explains the main concepts implemented in the project: blocks, Proof of Work, Merkle roots, wallets, signed transactions, mempool, forks, dynamic difficulty adjustment, node synchronization, and the heaviest-chain rule.

QChain is an educational prototype. It is not production-ready and must not be used with real funds.

---

## 1. Blockchain

A blockchain is a sequence of blocks where each block references the hash of the previous block.

In QChain, each block contains:

```text
Block
├── header
│   ├── index
│   ├── previous_hash
│   ├── merkle_root
│   ├── difficulty
│   ├── timestamp
│   └── nonce
├── hash
└── transactions
```

The block hash is computed from the block header.

The transactions are represented inside the header through the Merkle root. If a transaction is modified, the Merkle root changes, the block hash changes, and the chain becomes invalid unless Proof of Work is recomputed.

---

## 2. Genesis Block

The genesis block is the first block of the chain.

In QChain, the genesis block is deterministic. This is important because multiple nodes must share the exact same genesis hash. If two nodes have different genesis blocks, they cannot safely synchronize with each other.

---

## 3. Proof of Work

QChain uses Proof of Work as its consensus mechanism.

A miner must find a nonce such that the block hash starts with a given number of zeroes.

Example:

```text
difficulty = 4
valid hash = 0000a93f...
```

Mining is a loop:

```text
compute block hash
if hash starts with enough zeroes:
    block is valid
else:
    increment nonce and retry
```

Proof of Work gives the chain a measurable computational cost.

---

## 4. Dynamic Difficulty Adjustment

QChain includes a simple dynamic difficulty adjustment mechanism.

Current values:

```text
target block time = 10 seconds
difficulty adjustment interval = 5 blocks
minimum difficulty = 1
maximum difficulty = 8
```

If blocks are mined too quickly, the difficulty increases.

If blocks are mined too slowly, the difficulty decreases.

This is a simplified educational version of the difficulty adjustment logic used in real Proof-of-Work blockchains.

---

## 5. Merkle Root

A Merkle root summarizes all transactions in a block.

Process:

```text
transactions
-> transaction hashes
-> pairwise hashing
-> Merkle tree
-> Merkle root
```

The Merkle root is stored in the block header.

This allows QChain to detect any transaction tampering. If a transaction changes, its hash changes, the Merkle root changes, and the block becomes invalid.

---

## 6. Transactions

A QChain transaction contains:

```text
sender
receiver
amount
nonce
fee
signature
```

The sender pays:

```text
amount + fee
```

The receiver gets:

```text
amount
```

The miner gets:

```text
block reward + total transaction fees
```

Example:

```text
Alice sends 10 QCOIN to Bob with a 2 QCOIN fee.

Alice pays: 12 QCOIN
Bob receives: 10 QCOIN
Miner receives: 2 QCOIN fee, plus the block reward
```

---

## 7. Coinbase Transactions

A coinbase transaction is created by the protocol when a miner mines a block.

It has:

```text
sender = COINBASE
receiver = miner address
amount = block reward + total fees
```

Coinbase transactions are not signed because they are not created by a wallet. They are protocol-generated rewards.

The current default mining reward is:

```text
50 QCOIN
```

---

## 8. Wallets

A QChain wallet contains:

```text
private key
public key
address
```

The address is derived from the public key.

Wallet files are stored in:

```text
data/wallets/
```

Private keys are encrypted locally using a password-based key derivation function and symmetric encryption.

The password is not stored. If the password is lost, the wallet cannot be unlocked.

---

## 9. Signatures

Transactions are signed by the sender wallet.

Current implementation uses Ed25519 through the `cryptography` Python package.

This is a classical signature scheme used as a placeholder while the project evolves toward post-quantum signatures.

Long-term direction:

```text
Ed25519 placeholder
-> ML-DSA or SLH-DSA research
-> quantum-resistant transaction signatures
```

---

## 10. Nonces and Replay Protection

Each sender has a nonce.

The nonce prevents replay attacks and enforces transaction order.

Example:

```text
Alice confirmed nonce = 0
Alice next transaction nonce = 1
```

If Alice tries to send two conflicting transactions with the same nonce, QChain rejects the invalid one.

The mempool also considers pending transactions when computing the next available nonce.

---

## 11. Mempool

The mempool stores valid pending transactions before they are mined.

When a transaction is sent to a node:

```text
node receives transaction
node verifies signature
node checks balance and nonce
node adds transaction to mempool
node broadcasts transaction to peers
```

When a block is mined, included transactions are removed from the mempool.

---

## 12. Transaction Fees

Each transaction can include a fee.

The miner receives:

```text
block reward + total fees from included transactions
```

QChain includes fee-aware transaction selection. Higher-fee transactions can be prioritized when mining.

---

## 13. Multiple Nodes

QChain supports local HTTP nodes.

Each node has its own local chain, mempool, and peer list.

Example Docker testnet:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Inside Docker, nodes communicate through internal service names:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

---

## 14. Block Broadcasting

When a node mines a block, it broadcasts the block to its peers.

Peers validate the block before accepting it.

A peer accepts a block only if:

```text
the block hash is valid
the Proof of Work is valid
the previous_hash matches the local latest block
the Merkle root is valid
the transactions are valid
```

If the block is already known, the peer returns a neutral success response.

---

## 15. Transaction Broadcasting

When a node accepts a transaction into its mempool, it broadcasts the transaction to its peers.

Peers ignore already known transactions.

This allows pending transactions to propagate through the local testnet before being mined.

---

## 16. Forks

A fork happens when two valid blocks compete at the same height.

Example:

```text
0 -> 1 -> 2 -> 3A
          └-> 3B
```

In a real blockchain, temporary forks are expected. Nodes eventually converge toward the branch with the most accumulated work.

---

## 17. Heaviest-Chain Rule

QChain uses cumulative work to decide which chain is better.

The best chain is not necessarily the longest chain. It is the chain with the most accumulated Proof of Work.

Simplified idea:

```text
higher cumulative work = more computational effort = stronger chain
```

When synchronizing, a node validates candidate chains and adopts a valid chain only if it has more cumulative work.

---

## 18. Node Synchronization

Nodes can synchronize with peers.

The sync process:

```text
ask peers for status
compare cumulative work
download candidate chains
validate candidate chains
adopt the heaviest valid chain
```

If a node receives a block but is missing previous blocks, it can trigger synchronization.

If a node detects a possible fork, it can also synchronize to discover the heaviest valid chain.

---

## 19. Docker Testnet

QChain includes a Docker-based local testnet.

The testnet runs three nodes:

```text
node1
node2
node3
```

Each node has its own blockchain storage under:

```text
data/docker/
```

This allows realistic local testing of:

```text
block propagation
transaction propagation
mempool synchronization
mining rewards
transaction fees
chain synchronization
heaviest-chain behavior
```

---

## 20. Long-Term Research Direction

QChain is intended as a research-oriented blockchain prototype.

Possible future directions:

```text
post-quantum transaction signatures
ML-DSA integration
SLH-DSA integration
signature benchmarking
quantum-resistant Proof-of-Work analysis
STARK-based privacy layer
zero-knowledge transaction experiments
better fork management
block header synchronization
orphan block pool
real peer discovery
network protocol improvements
```

---

## 21. Security Warning

QChain is experimental software.

Do not use it with real funds.

The current implementation is designed for learning, prototyping, and research experiments.