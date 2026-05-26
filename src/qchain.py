import argparse
from pathlib import Path

from blockchain import Blockchain
from wallet import Wallet


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WALLETS_DIR = DATA_DIR / "wallets"
CHAIN_PATH = DATA_DIR / "chain.json"


def load_chain() -> Blockchain:
    return Blockchain(
        difficulty=4,
        mining_reward=50,
        storage_path=str(CHAIN_PATH),
        auto_load=True,
    )


def wallet_path(name: str) -> Path:
    clean_name = name.lower().strip()
    return WALLETS_DIR / f"{clean_name}.json"


def wallet_exists(name: str) -> bool:
    return wallet_path(name).exists()


def load_wallet(name: str) -> Wallet:
    path = wallet_path(name)

    if not path.exists():
        raise ValueError(
            f"Wallet '{name}' does not exist. "
            f"Create it with: python3 src/qchain.py wallet-create {name}"
        )

    return Wallet.load(str(path))


def create_wallet(name: str) -> Wallet:
    path = wallet_path(name)
    wallet = Wallet.load_or_create(str(path))
    return wallet


def list_wallets() -> list[tuple[str, Wallet]]:
    WALLETS_DIR.mkdir(parents=True, exist_ok=True)

    wallets = []

    for path in sorted(WALLETS_DIR.glob("*.json")):
        name = path.stem
        wallet = Wallet.load(str(path))
        wallets.append((name, wallet))

    return wallets


def resolve_receiver_address(receiver: str) -> str:
    """
    Receiver can be either:
    - a wallet name, like 'bob'
    - a raw address
    """
    if wallet_exists(receiver):
        return load_wallet(receiver).address

    # Very simple raw address check for our current address format.
    if len(receiver) == 40:
        return receiver

    raise ValueError(
        f"Unknown receiver '{receiver}'. "
        f"Use an existing wallet name or a raw address."
    )


def get_next_available_nonce(chain: Blockchain, address: str) -> int:
    """
    Normal chain.get_next_nonce(address) only looks at confirmed transactions.

    This function also checks pending mempool transactions,
    so you can create multiple transactions before mining.
    """
    current_nonce = chain.nonces.get(address, 0)

    for tx in chain.mempool:
        if tx.sender_address() == address and tx.nonce > current_nonce:
            current_nonce = tx.nonce

    return current_nonce + 1


def print_status(chain: Blockchain) -> None:
    print("QCHAIN status")
    print("-----------------")
    print(f"Height: {len(chain.chain) - 1}")
    print(f"Latest hash: {chain.latest_block().hash}")
    print(f"Difficulty: {chain.difficulty}")
    print(f"Mining reward: {chain.mining_reward} QCOIN")
    print(f"Mempool size: {len(chain.mempool)}")
    print(f"Valid chain: {chain.is_valid()}")


def command_status(args) -> None:
    chain = load_chain()
    print_status(chain)


def command_wallet_create(args) -> None:
    wallet = create_wallet(args.name)

    print(f"Wallet '{args.name}' ready.")
    print(f"Address: {wallet.address}")
    print()
    print("Private key saved locally in data/wallets/.")
    print("Do not share that file if this were real money.")


def command_wallets(args) -> None:
    wallets = list_wallets()

    if not wallets:
        print("No wallets found.")
        print("Create one with: python3 src/qchain.py wallet-create alice")
        return

    print("Wallets")
    print("-------")

    for name, wallet in wallets:
        print(f"{name}: {wallet.address}")


def command_balance(args) -> None:
    chain = load_chain()
    wallet = load_wallet(args.name)

    balance = chain.get_balance(wallet.address)
    nonce = chain.nonces.get(wallet.address, 0)

    print(f"Wallet: {args.name}")
    print(f"Address: {wallet.address}")
    print(f"Balance: {balance} QCOIN")
    print(f"Confirmed nonce: {nonce}")
    print(f"Next available nonce: {get_next_available_nonce(chain, wallet.address)}")


def command_mine(args) -> None:
    chain = load_chain()
    miner = load_wallet(args.miner)

    chain.mine_pending_transactions(
        miner_address=miner.address,
        max_transactions=args.max_tx,
    )

    print()
    print(f"Miner: {args.miner}")
    print(f"Miner address: {miner.address}")
    print(f"New balance: {chain.get_balance(miner.address)} QCOIN")
    print(f"Chain height: {len(chain.chain) - 1}")


def command_send(args) -> None:
    chain = load_chain()

    sender_wallet = load_wallet(args.sender)
    receiver_address = resolve_receiver_address(args.receiver)

    if args.amount <= 0:
        raise ValueError("Amount must be positive.")

    if args.fee < 0:
        raise ValueError("Fee cannot be negative.")

    nonce = get_next_available_nonce(chain, sender_wallet.address)

    tx = sender_wallet.create_transaction(
        receiver_address=receiver_address,
        amount=args.amount,
        nonce=nonce,
        fee=args.fee,
    )

    added = chain.add_transaction(tx)

    if added:
        print("Transaction created and added to mempool.")
        print(f"From: {args.sender}")
        print(f"Sender address: {sender_wallet.address}")
        print(f"To: {args.receiver}")
        print(f"Receiver address: {receiver_address}")
        print(f"Amount: {args.amount} QCOIN")
        print(f"Fee: {args.fee} QCOIN")
        print(f"Nonce: {nonce}")
    else:
        print("Transaction rejected.")


def command_mempool(args) -> None:
    chain = load_chain()
    chain.print_mempool()


def command_validate(args) -> None:
    chain = load_chain()

    if chain.is_valid():
        print("Blockchain is valid.")
    else:
        print("Blockchain is invalid.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QCHAIN command line interface"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show blockchain status",
    )
    status_parser.set_defaults(func=command_status)

    wallet_create_parser = subparsers.add_parser(
        "wallet-create",
        help="Create or load a wallet",
    )
    wallet_create_parser.add_argument("name")
    wallet_create_parser.set_defaults(func=command_wallet_create)

    wallets_parser = subparsers.add_parser(
        "wallets",
        help="List saved wallets",
    )
    wallets_parser.set_defaults(func=command_wallets)

    balance_parser = subparsers.add_parser(
        "balance",
        help="Show wallet balance",
    )
    balance_parser.add_argument("name")
    balance_parser.set_defaults(func=command_balance)

    mine_parser = subparsers.add_parser(
        "mine",
        help="Mine pending transactions",
    )
    mine_parser.add_argument("miner")
    mine_parser.add_argument(
        "--max-tx",
        type=int,
        default=None,
        help="Maximum number of transactions to include",
    )
    mine_parser.set_defaults(func=command_mine)

    send_parser = subparsers.add_parser(
        "send",
        help="Send QCOIN from one wallet to another",
    )
    send_parser.add_argument("sender")
    send_parser.add_argument("receiver")
    send_parser.add_argument("amount", type=int)
    send_parser.add_argument(
        "--fee",
        type=int,
        default=1,
        help="Transaction fee",
    )
    send_parser.set_defaults(func=command_send)

    mempool_parser = subparsers.add_parser(
        "mempool",
        help="Show pending transactions",
    )
    mempool_parser.set_defaults(func=command_mempool)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate the blockchain",
    )
    validate_parser.set_defaults(func=command_validate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()