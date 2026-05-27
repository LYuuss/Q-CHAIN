import argparse
import getpass

from blockchain import Blockchain
from wallet import Wallet
from config import (
    PROJECT_NAME,
    COIN_NAME,
    DEFAULT_DIFFICULTY,
    DEFAULT_MINING_REWARD,
    WALLETS_DIR,
    CHAIN_PATH,
)


def load_chain() -> Blockchain:
    return Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(CHAIN_PATH),
        auto_load=True,
    )


def wallet_path(name: str):
    clean_name = name.lower().strip()
    return WALLETS_DIR / f"{clean_name}.json"


def wallet_exists(name: str) -> bool:
    return wallet_path(name).exists()


def prompt_password(name: str, confirm: bool = False) -> str:
    password = getpass.getpass(f"Password for wallet '{name}': ")

    if not password:
        raise ValueError("Password cannot be empty.")

    if confirm:
        confirmation = getpass.getpass("Confirm password: ")

        if password != confirmation:
            raise ValueError("Passwords do not match.")

    return password


def load_wallet_metadata(name: str) -> dict:
    path = wallet_path(name)

    if not path.exists():
        raise ValueError(
            f"Wallet '{name}' does not exist. "
            f"Create it with: python3 src/qchain.py wallet-create {name}"
        )

    return Wallet.load_metadata(str(path))


def load_wallet_for_signing(name: str) -> Wallet:
    path = wallet_path(name)

    if not path.exists():
        raise ValueError(
            f"Wallet '{name}' does not exist. "
            f"Create it with: python3 src/qchain.py wallet-create {name}"
        )

    if Wallet.is_encrypted(str(path)):
        password = prompt_password(name)
        return Wallet.load(str(path), password=password)

    print(
        f"Warning: wallet '{name}' is not encrypted. "
        f"Run: python3 src/qchain.py wallet-encrypt {name}"
    )

    return Wallet.load(str(path))


def create_wallet(name: str) -> Wallet:
    path = wallet_path(name)

    if path.exists():
        if Wallet.is_encrypted(str(path)):
            password = prompt_password(name)
            return Wallet.load(str(path), password=password)

        return Wallet.load(str(path))

    password = prompt_password(name, confirm=True)

    wallet = Wallet.generate()
    wallet.save(str(path), password=password)

    return wallet


def list_wallets() -> list[tuple[str, dict]]:
    WALLETS_DIR.mkdir(parents=True, exist_ok=True)

    wallets = []

    for path in sorted(WALLETS_DIR.glob("*.json")):
        name = path.stem
        metadata = Wallet.load_metadata(str(path))
        wallets.append((name, metadata))

    return wallets


def resolve_receiver_address(receiver: str) -> str:
    if wallet_exists(receiver):
        return load_wallet_metadata(receiver)["address"]

    if len(receiver) == 40:
        return receiver

    raise ValueError(
        f"Unknown receiver '{receiver}'. "
        f"Use an existing wallet name or a raw address."
    )


def get_next_available_nonce(chain: Blockchain, address: str) -> int:
    current_nonce = chain.nonces.get(address, 0)

    for tx in chain.mempool:
        if tx.sender_address() == address and tx.nonce > current_nonce:
            current_nonce = tx.nonce

    return current_nonce + 1


def print_status(chain: Blockchain) -> None:
    print(f"{PROJECT_NAME} status")
    print("-" * (len(PROJECT_NAME) + 7))
    print(f"Height: {len(chain.chain) - 1}")
    print(f"Latest hash: {chain.latest_block().hash}")
    print(f"Next block difficulty: {chain.calculate_next_difficulty()}")
    print(f"Target block time: {chain.target_block_time}s")
    print(f"Difficulty adjustment interval: {chain.difficulty_adjustment_interval} blocks")
    print(f"Mining reward: {chain.mining_reward} {COIN_NAME}")
    print(f"Mempool size: {len(chain.mempool)}")
    print(f"Valid chain: {chain.is_valid()}")


def command_status(args) -> None:
    chain = load_chain()
    print_status(chain)


def command_wallet_create(args) -> None:
    path = wallet_path(args.name)
    already_exists = path.exists()

    wallet = create_wallet(args.name)

    if already_exists:
        print(f"Wallet '{args.name}' already exists.")
    else:
        print(f"Wallet '{args.name}' created.")

    print(f"Address: {wallet.address}")
    print()
    print("Wallet private key is encrypted locally in data/wallets/.")
    print("Keep your password safe. If you lose it, the wallet cannot be unlocked.")


def command_wallet_encrypt(args) -> None:
    path = wallet_path(args.name)

    if not path.exists():
        raise ValueError(
            f"Wallet '{args.name}' does not exist. "
            f"Create it with: python3 src/qchain.py wallet-create {args.name}"
        )

    if Wallet.is_encrypted(str(path)):
        print(f"Wallet '{args.name}' is already encrypted.")
        return

    wallet = Wallet.load(str(path))
    password = prompt_password(args.name, confirm=True)

    wallet.save(str(path), password=password)

    print(f"Wallet '{args.name}' encrypted successfully.")
    print(f"Address: {wallet.address}")


def command_wallets(args) -> None:
    wallets = list_wallets()

    if not wallets:
        print("No wallets found.")
        print("Create one with: python3 src/qchain.py wallet-create alice")
        return

    print("Wallets")
    print("-------")

    for name, metadata in wallets:
        status = "encrypted" if metadata["encrypted"] else "plaintext"
        print(f"{name}: {metadata['address']} | {status}")


def command_balance(args) -> None:
    chain = load_chain()
    metadata = load_wallet_metadata(args.name)

    address = metadata["address"]
    balance = chain.get_balance(address)
    nonce = chain.nonces.get(address, 0)

    print(f"Wallet: {args.name}")
    print(f"Address: {address}")
    print(f"Balance: {balance} {COIN_NAME}")
    print(f"Confirmed nonce: {nonce}")
    print(f"Next available nonce: {get_next_available_nonce(chain, address)}")


def command_mine(args) -> None:
    chain = load_chain()
    metadata = load_wallet_metadata(args.miner)

    miner_address = metadata["address"]

    chain.mine_pending_transactions(
        miner_address=miner_address,
        max_transactions=args.max_tx,
    )

    print()
    print(f"Miner: {args.miner}")
    print(f"Miner address: {miner_address}")
    print(f"New balance: {chain.get_balance(miner_address)} {COIN_NAME}")
    print(f"Chain height: {len(chain.chain) - 1}")


def command_send(args) -> None:
    chain = load_chain()

    sender_wallet = load_wallet_for_signing(args.sender)
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
        print(f"Amount: {args.amount} {COIN_NAME}")
        print(f"Fee: {args.fee} {COIN_NAME}")
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
        description=f"{PROJECT_NAME} command line interface"
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

    wallet_encrypt_parser = subparsers.add_parser(
        "wallet-encrypt",
        help="Encrypt an old plaintext wallet",
    )
    wallet_encrypt_parser.add_argument("name")
    wallet_encrypt_parser.set_defaults(func=command_wallet_encrypt)

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