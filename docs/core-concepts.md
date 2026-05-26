# Core Concepts
## Blockchain

Each block is linked to the previous block through its hash.

A block contains:

BlockHeader:
  index
  previous_hash
  merkle_root
  timestamp
  difficulty
  nonce

Block:
  header
  transactions

The block hash is computed from the block header.  

## Proof of Work

QChain uses a simple Proof-of-Work mechanism.

To mine a block, the miner must find a nonce such that the block hash starts with a certain number of zeroes.

Example:

difficulty = 4
valid hash = 0000a93f...

The difficulty is currently fixed.  

## Merkle Root

Transactions are not directly placed inside the block header.

Instead:

transactions -> transaction hashes -> Merkle tree -> Merkle root

The Merkle root is stored inside the block header.

This makes it possible to detect transaction tampering. 

## Wallets

Each wallet contains:

a private key
a public key
an address

Wallets are stored locally in:

data/wallets/

Example:

data/wallets/alice.json

For now, wallet private keys are stored in plaintext JSON.

This is acceptable for a local prototype, but not secure for real-world usage.  

## Transactions

A transaction contains:

sender
receiver
amount
fee
nonce
signature

The sender pays:

amount + fee

The receiver receives:

amount

The miner receives:

block reward + total transaction fees

## QCOIN

QCOIN is the native coin of QChain.

It is used for:

wallet balances
transaction amounts
transaction fees
mining rewards

Current default mining reward:

50 QCOIN