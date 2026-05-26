from pathlib import Path

from blockchain import Blockchain
from wallet import Wallet


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WALLETS_DIR = DATA_DIR / "wallets"


def print_balances(chain: Blockchain, wallets: dict[str, Wallet]) -> None:
    balances, nonces = chain.get_state()

    print("\nBalances:")
    for name, wallet in wallets.items():
        balance = balances.get(wallet.address, 0)
        nonce = nonces.get(wallet.address, 0)
        print(f"- {name}: {balance} QCOIN | nonce={nonce}")


def print_wallets(wallets: dict[str, Wallet]) -> None:
    print("\nWallets:")
    for name, wallet in wallets.items():
        print(f"- {name}: {wallet.address}")


def main():
    chain = Blockchain(
        difficulty=4,
        mining_reward=50,
        storage_path=str(DATA_DIR / "chain.json"),
        auto_load=True,
    )

    alice = Wallet.load_or_create(str(WALLETS_DIR / "alice.json"))
    bob = Wallet.load_or_create(str(WALLETS_DIR / "bob.json"))
    miner = Wallet.load_or_create(str(WALLETS_DIR / "miner.json"))

    wallets = {
        "Alice": alice,
        "Bob": bob,
        "Miner": miner,
    }

    print("Blockchain loaded.")
    print(f"Current height: {len(chain.chain) - 1}")
    print(f"Latest hash: {chain.latest_block().hash}")

    print_wallets(wallets)
    print_balances(chain, wallets)

    print("\nAlice mines a block to receive funds.")
    chain.mine_pending_transactions(miner_address=alice.address)
    print_balances(chain, wallets)

    print("\nAlice creates a transaction to Bob.")
    tx = alice.create_transaction(
        receiver_address=bob.address,
        amount=10,
        nonce=chain.get_next_nonce(alice.address),
        fee=2,
    )

    chain.add_transaction(tx)
    chain.print_mempool()

    print("\nMiner mines pending transactions.")
    chain.mine_pending_transactions(miner_address=miner.address)

    print_balances(chain, wallets)
    chain.print_mempool()

    print("\nBlockchain valid:", chain.is_valid())


if __name__ == "__main__":
    main()