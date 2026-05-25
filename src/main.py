from blockchain import Blockchain
from wallet import Wallet


def print_balances(chain: Blockchain, wallets: dict[str, Wallet]) -> None:
    balances, nonces = chain.get_state()

    print("\nBalances:")
    for name, wallet in wallets.items():
        balance = balances.get(wallet.address, 0)
        nonce = nonces.get(wallet.address, 0)
        print(f"- {name}: {balance} QPOW | nonce={nonce}")


def main():
    chain = Blockchain(difficulty=4, mining_reward=50)

    alice = Wallet.generate()
    bob = Wallet.generate()
    charlie = Wallet.generate()
    miner = Wallet.generate()

    wallets = {
        "Alice": alice,
        "Bob": bob,
        "Charlie": charlie,
        "Miner": miner,
    }

    print("Genesis block created.")
    print(f"Genesis hash: {chain.latest_block().hash}")

    print("\nWallets created:")
    for name, wallet in wallets.items():
        print(f"{name} address: {wallet.address}")

    print_balances(chain, wallets)

    print("\nAlice mines first empty block.")
    chain.mine_pending_transactions(miner_address=alice.address)
    print_balances(chain, wallets)

    print("\nAlice creates transaction to Bob with low fee.")
    tx1 = alice.create_transaction(
        receiver_address=bob.address,
        amount=10,
        nonce=1,
        fee=1,
    )

    chain.add_transaction(tx1)

    print("\nAlice creates transaction to Charlie with higher fee.")
    tx2 = alice.create_transaction(
        receiver_address=charlie.address,
        amount=15,
        nonce=2,
        fee=5,
    )

    chain.add_transaction(tx2)

    chain.print_mempool()

    print("\nTrying invalid transaction: Alice sends more than she owns.")
    invalid_tx = alice.create_transaction(
        receiver_address=bob.address,
        amount=999,
        nonce=3,
        fee=10,
    )

    chain.add_transaction(invalid_tx)
    chain.print_mempool()

    print("\nMiner mines pending transactions.")
    chain.mine_pending_transactions(miner_address=miner.address)

    print_balances(chain, wallets)
    chain.print_mempool()

    print("\nTrying replay attack: reusing Alice's first transaction.")
    chain.add_transaction(tx1)
    chain.print_mempool()

    print("\nBlockchain valid:", chain.is_valid())


if __name__ == "__main__":
    main()