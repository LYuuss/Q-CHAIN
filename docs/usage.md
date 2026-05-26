# Usage

## Show Blockchain Status
python3 src/qchain.py status

Example output:

QChain status
-------------
Height: 0
Latest hash: 0000...
Difficulty: 4
Mining reward: 50 QCOIN
Mempool size: 0
Valid chain: True  

## Create Wallets
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner  

## List Wallets
python3 src/qchain.py wallets

Example output:

Wallets
-------
alice: a1b2c3...
bob: d4e5f6...
miner: 789abc...  

## Check Wallet Balance
python3 src/qchain.py balance alice

Example output:

Wallet: alice
Address: a1b2c3...
Balance: 50 QCOIN
Confirmed nonce: 0
Next available nonce: 1  

## Mine a Block

A wallet must mine a block to receive QCOIN.

python3 src/qchain.py mine alice

This gives Alice the mining reward.

Default reward:

50 QCOIN  

## Send QCOIN
python3 src/qchain.py send alice bob 10 --fee 2

This creates a transaction where:

Alice sends 10 QCOIN to Bob
Alice pays a 2 QCOIN fee
Bob receives 10 QCOIN
The miner receives the 2 QCOIN fee after mining

The transaction is first added to the mempool.  

## Show Mempool
python3 src/qchain.py mempool

Example output:

Mempool: 1 pending transaction(s)

alice_address -> bob_address | amount=10 | fee=2 | total_cost=12 | nonce=1  

## Mine Pending Transactions
python3 src/qchain.py mine miner

If the mempool contains Alice's transaction to Bob, the miner receives:

50 QCOIN block reward + 2 QCOIN fee = 52 QCOIN  

## Validate the Blockchain
python3 src/qchain.py validate

Example output:

Blockchain is valid.