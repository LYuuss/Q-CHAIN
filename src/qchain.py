import argparse
import getpass
import json
import urllib.error
import re
import sys
from pathlib import Path
from typing import Any

from blockchain import Blockchain
from wallet import Wallet
from transaction import Transaction
from config import (
    PROJECT_NAME,
    COIN_NAME,
    DEFAULT_DIFFICULTY,
    DEFAULT_MINING_REWARD,
    WALLETS_DIR,
    CHAIN_PATH,
)


from http_client import fetch_json, post_json, HttpJsonError
from storage_utils import atomic_write_json
from wallet import load_wallet_json
from validation import is_address


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def normalize_node_url(node: str) -> str:
    clean_node = str(node).strip().rstrip("/")

    if clean_node.isdigit():
        return f"http://127.0.0.1:{clean_node}"

    if not clean_node.startswith(("http://", "https://")):
        return "http://" + clean_node

    return clean_node


def load_chain() -> Blockchain:
    return Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(CHAIN_PATH),
        auto_load=True,
    )


def wallet_path(name: str):
    clean_name = name.lower().strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", clean_name):
        raise ValueError("Wallet names must contain 1–64 letters, digits, underscores, or hyphens.")
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
    if is_address(receiver):
        return receiver
    if wallet_exists(receiver):
        return load_wallet_metadata(receiver)["address"]

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


def get_next_available_nonce_from_node(node_url: str, address: str) -> int:
    balance_data = fetch_json(f"{node_url}/balances/{address}")
    current_nonce = balance_data.get("confirmed_nonce", 0)

    mempool_data = fetch_json(f"{node_url}/mempool")

    for tx_data in mempool_data.get("transactions", []):
        try:
            transaction = Transaction.from_dict(tx_data)

            if transaction.sender_address() == address and transaction.nonce > current_nonce:
                current_nonce = transaction.nonce

        except (KeyError, ValueError):
            continue

    return current_nonce + 1


def print_status(chain: Blockchain) -> None:
    print(f"{PROJECT_NAME} status")
    print("-" * (len(PROJECT_NAME) + 7))
    print(f"Height: {len(chain.chain) - 1}")
    print(f"Latest hash: {chain.latest_block().hash}")
    print(f"Next block difficulty: {chain.calculate_next_difficulty()}")
    print(f"Cumulative work: {chain.calculate_cumulative_work()}")
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

    added = chain.mine_pending_transactions(
        miner_address=miner_address,
        max_transactions=args.max_tx,
    )
    if not added:
        raise ValueError("Mining failed.")

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
        print("Transaction created and added to local mempool.")
        print(f"From: {args.sender}")
        print(f"Sender address: {sender_wallet.address}")
        print(f"To: {args.receiver}")
        print(f"Receiver address: {receiver_address}")
        print(f"Amount: {args.amount} {COIN_NAME}")
        print(f"Fee: {args.fee} {COIN_NAME}")
        print(f"Nonce: {nonce}")
    else:
        raise ValueError("Transaction rejected.")


def command_mempool(args) -> None:
    chain = load_chain()
    chain.print_mempool()


def command_validate(args) -> None:
    chain = load_chain()

    if chain.is_valid():
        print("Blockchain is valid.")
    else:
        raise ValueError("Blockchain is invalid.")


def command_node_status(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/status")
    print_json(response)


def command_node_mempool(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/mempool")
    print_json(response)

def command_node_orphans(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/orphans")
    print_json(response)

def command_node_sync(args) -> None:
    node_url = normalize_node_url(args.node)
    response = post_json(f"{node_url}/sync", {}, timeout=300)
    print_json(response)

def command_node_connect(args) -> None:
    node_a_url = normalize_node_url(args.node_a)
    node_b_url = normalize_node_url(args.node_b)

    response_a = post_json(
        url=f"{node_a_url}/peers",
        payload={
            "url": node_b_url,
        },
    )

    response_b = post_json(
        url=f"{node_b_url}/peers",
        payload={
            "url": node_a_url,
        },
    )

    print("Nodes connected successfully.")
    print()
    print(f"Node A: {node_a_url}")
    print(f"Node B: {node_b_url}")
    print()
    print("Node A response:")
    print_json(response_a)
    print()
    print("Node B response:")
    print_json(response_b)

def command_node_mine(args) -> None:
    node_url = normalize_node_url(args.node)
    miner_metadata = load_wallet_metadata(args.miner)

    payload = {
        "miner_address": miner_metadata["address"],
    }

    if args.max_tx is not None:
        payload["max_transactions"] = args.max_tx

    response = post_json(f"{node_url}/mine", payload, timeout=300)
    print_json(response)


def command_node_send(args) -> None:
    node_url = normalize_node_url(args.node)

    sender_wallet = load_wallet_for_signing(args.sender)
    receiver_address = resolve_receiver_address(args.receiver)

    if args.amount <= 0:
        raise ValueError("Amount must be positive.")

    if args.fee < 0:
        raise ValueError("Fee cannot be negative.")

    nonce = get_next_available_nonce_from_node(
        node_url=node_url,
        address=sender_wallet.address,
    )

    transaction = sender_wallet.create_transaction(
        receiver_address=receiver_address,
        amount=args.amount,
        nonce=nonce,
        fee=args.fee,
    )

    response = post_json(
        url=f"{node_url}/transactions",
        payload={
            "transaction": transaction.to_dict(),
        },
    )

    print("Transaction sent to node.")
    print(f"Node: {node_url}")
    print(f"From: {args.sender}")
    print(f"Sender address: {sender_wallet.address}")
    print(f"To: {args.receiver}")
    print(f"Receiver address: {receiver_address}")
    print(f"Amount: {args.amount} {COIN_NAME}")
    print(f"Fee: {args.fee} {COIN_NAME}")
    print(f"Nonce: {nonce}")
    print()
    print_json(response)

def command_node_balance(args) -> None:
    node_url = normalize_node_url(args.node)
    address = resolve_receiver_address(args.wallet)

    response = fetch_json(f"{node_url}/balances/{address}")

    print(f"Node: {node_url}")
    print(f"Wallet: {args.wallet}")
    print(f"Address: {address}")
    print(f"Balance: {response['balance']} {response['coin']}")
    print(f"Confirmed nonce: {response['confirmed_nonce']}")

def command_node_headers(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/headers")

    headers = response.get("headers", [])

    print(f"Node: {node_url}")
    print(f"Header count: {len(headers)}")
    print()

    for header in headers:
        print(
            f"#{header['index']} "
            f"hash={header['hash']} "
            f"prev={header['previous_hash']} "
            f"difficulty={header['difficulty']} "
            f"txs={header.get('transaction_count', '?')}"
        )

def build_parser() -> argparse.ArgumentParser:

    
    parser = argparse.ArgumentParser(
        description=f"{PROJECT_NAME} command line interface"
    )
    parser.add_argument("--data-dir", type=Path, help="Local chain and wallet directory (before the command)")

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show local blockchain status",
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
        help="Show local wallet balance",
    )
    balance_parser.add_argument("name")
    balance_parser.set_defaults(func=command_balance)

    mine_parser = subparsers.add_parser(
        "mine",
        help="Mine pending transactions on the local chain",
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
        help="Send QCOIN on the local chain",
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
        help="Show local pending transactions",
    )
    mempool_parser.set_defaults(func=command_mempool)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate the local blockchain",
    )
    validate_parser.set_defaults(func=command_validate)

    node_status_parser = subparsers.add_parser(
        "node-status",
        help="Show HTTP node status",
    )
    node_status_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_status_parser.set_defaults(func=command_node_status)

    node_headers_parser = subparsers.add_parser(
        "node-headers",
        help="Show HTTP node block headers",
    )
    node_headers_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_headers_parser.set_defaults(func=command_node_headers)
    
    node_mempool_parser = subparsers.add_parser(
        "node-mempool",
        help="Show HTTP node mempool",
    )
    node_mempool_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_mempool_parser.set_defaults(func=command_node_mempool)

    node_orphans_parser = subparsers.add_parser(
        "node-orphans",
        help="Show HTTP node orphan block pool",
    )
    node_orphans_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_orphans_parser.set_defaults(func=command_node_orphans)

    node_sync_parser = subparsers.add_parser(
        "node-sync",
        help="Synchronize an HTTP node with its peers",
    )
    node_sync_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_sync_parser.set_defaults(func=command_node_sync)
    
    node_connect_parser = subparsers.add_parser(
        "node-connect",
        help="Connect two HTTP nodes together",
    )
    node_connect_parser.add_argument("node_a", help="First node port or URL, example: 5001")
    node_connect_parser.add_argument("node_b", help="Second node port or URL, example: 5002")
    node_connect_parser.set_defaults(func=command_node_connect)
    node_mine_parser = subparsers.add_parser(
        "node-mine",
        help="Mine pending transactions on an HTTP node",
    )
    node_mine_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_mine_parser.add_argument("miner", help="Wallet name receiving the reward")
    node_mine_parser.add_argument(
        "--max-tx",
        type=int,
        default=None,
        help="Maximum number of transactions to include",
    )
    node_mine_parser.set_defaults(func=command_node_mine)

    node_send_parser = subparsers.add_parser(
        "node-send",
        help="Send QCOIN through an HTTP node",
    )
    node_send_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_send_parser.add_argument("sender", help="Sender wallet name")
    node_send_parser.add_argument("receiver", help="Receiver wallet name or raw address")
    node_send_parser.add_argument("amount", type=int)
    node_send_parser.add_argument(
        "--fee",
        type=int,
        default=1,
        help="Transaction fee",
    )
    node_send_parser.set_defaults(func=command_node_send)

    node_balance_parser = subparsers.add_parser(
        "node-balance",
        help="Show wallet balance on an HTTP node",
    )
    node_balance_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_balance_parser.add_argument("wallet", help="Wallet name")
    node_balance_parser.set_defaults(func=command_node_balance)

    node_side_branches_parser = subparsers.add_parser(
        "node-side-branches",
        help="Show HTTP node side-branch pool",
    )
    node_side_branches_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_side_branches_parser.set_defaults(func=command_node_side_branches)

    node_transaction_parser = subparsers.add_parser(
        "node-transaction",
        help="Show a transaction by hash from an HTTP node",
    )
    node_transaction_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_transaction_parser.add_argument("transaction_hash", help="Transaction hash")
    node_transaction_parser.set_defaults(func=command_node_transaction)

    node_address_transactions_parser = subparsers.add_parser(
        "node-address-transactions",
        help="Show transaction history for an address from an HTTP node",
    )
    node_address_transactions_parser.add_argument("node", help="Node port or URL, example: 5001")
    node_address_transactions_parser.add_argument("address", help="Address to inspect")
    node_address_transactions_parser.set_defaults(func=command_node_address_transactions)

    node_discover_peers_parser = subparsers.add_parser(
        "node-discover-peers",
        help="Discover peers known by this node's current peers",
    )
    node_discover_peers_parser.add_argument(
        "node",
        help="Node port or URL, example: 5001",
    )
    node_discover_peers_parser.set_defaults(func=command_node_discover_peers)
    
    for name, endpoint, description in (
        ("node-chain", "/chain", "Show the full node chain"),
        ("node-peers", "/peers", "Show connected peers"),
        ("node-blocks", "/blocks", "List confirmed blocks"),
        ("node-transactions", "/transactions", "List pending and confirmed transactions"),
        ("node-reorgs", "/reorgs", "Show persistent reorganization history"),
    ):
        command = subparsers.add_parser(name, help=description)
        command.add_argument("node", help="Node port or URL")
        command.add_argument("--limit", type=int, default=50)
        command.add_argument("--offset", type=int, default=0)
        command.set_defaults(func=command_node_list, endpoint=endpoint)

    block_command = subparsers.add_parser("node-block", help="Look up a block by height or hash")
    block_command.add_argument("node")
    block_command.add_argument("identifier")
    block_command.set_defaults(func=command_node_block)

    for name, function, help_text in (
        ("wallet-info", command_wallet_info, "Show public wallet metadata"),
        ("wallet-password", command_wallet_password, "Change the wallet password"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("name")
        command.set_defaults(func=function)
    backup = subparsers.add_parser("wallet-backup", help="Back up an encrypted wallet without overwriting files")
    backup.add_argument("name")
    backup.add_argument("destination", type=Path)
    backup.set_defaults(func=command_wallet_backup)
    restore = subparsers.add_parser("wallet-import", help="Validate and import an encrypted wallet backup")
    restore.add_argument("source", type=Path)
    restore.add_argument("name")
    restore.set_defaults(func=command_wallet_import)
    return parser


def command_node_list(args):
    endpoint = f"{args.endpoint}?limit={args.limit}&offset={args.offset}"
    print_json(fetch_json(normalize_node_url(args.node) + endpoint))


def command_node_block(args):
    if args.identifier.isdigit() and len(args.identifier) < 64:
        endpoint = f"/blocks/height/{int(args.identifier)}"
    elif re.fullmatch(r"[0-9a-f]{64}", args.identifier):
        endpoint = f"/blocks/{args.identifier}"
    else:
        raise ValueError("Expected a block height or 64-character hexadecimal hash.")
    print_json(fetch_json(normalize_node_url(args.node) + endpoint))


def command_wallet_info(args):
    print_json(load_wallet_metadata(args.name))


def command_wallet_password(args):
    wallet = load_wallet_for_signing(args.name)
    password = prompt_password("new password", confirm=True)
    wallet.save(str(wallet_path(args.name)), password=password)
    print("Wallet password changed.")


def command_wallet_backup(args):
    source = wallet_path(args.name)
    if not Wallet.is_encrypted(str(source)):
        raise ValueError("Encrypt the wallet with wallet-encrypt before backing it up.")
    atomic_write_json(args.destination, load_wallet_json(source), overwrite=False)
    print(f"Encrypted wallet backup saved to {args.destination}.")


def command_wallet_import(args):
    destination = wallet_path(args.name)
    if destination.exists():
        raise ValueError("A wallet with this name already exists.")
    if not Wallet.is_encrypted(str(args.source)):
        raise ValueError("Only encrypted wallet backups can be imported.")
    password = prompt_password(args.name)
    wallet = Wallet.load(str(args.source), password=password)
    atomic_write_json(destination, load_wallet_json(args.source), overwrite=False)
    print(f"Wallet imported. Address: {wallet.address}")

def command_node_side_branches(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/side-branches")
    print_json(response)

def command_node_transaction(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/transactions/{args.transaction_hash}")
    print_json(response)


def command_node_address_transactions(args) -> None:
    node_url = normalize_node_url(args.node)
    response = fetch_json(f"{node_url}/addresses/{args.address}/transactions")
    print_json(response)

def command_node_discover_peers(args) -> None:
    node_url = normalize_node_url(args.node)

    print_json(post_json(f"{node_url}/peers/discover", {}, timeout=120))


def main() -> int:
    global WALLETS_DIR, CHAIN_PATH
    parser = build_parser()
    args = parser.parse_args()
    if args.data_dir is not None:
        directory = args.data_dir.expanduser().resolve()
        WALLETS_DIR = directory / "wallets"
        CHAIN_PATH = directory / "chain.json"

    try:
        args.func(args)

    except HttpJsonError as error:
        print(f"HTTP error: {error.status_code}")

        if error.body is not None:
            print_json(error.body)
        elif error.raw_body:
            print(error.raw_body)
        return 1

    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
