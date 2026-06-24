import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from block import Block
from blockchain import Blockchain
from config import (
    PROJECT_NAME,
    COIN_NAME,
    DEFAULT_DIFFICULTY,
    DEFAULT_MINING_REWARD,
    DATA_DIR,
)
from transaction import Transaction
from block_store import BlockStore
from transaction_index import TransactionIndex

MAX_ORPHAN_BLOCKS = 100
MAX_SIDE_BRANCH_BLOCKS = 200

class HttpJsonError(Exception):
    def __init__(self, status_code: int, body: dict[str, Any] | None, raw_body: str):
        self.status_code = status_code
        self.body = body
        self.raw_body = raw_body

        message = f"HTTP {status_code}"

        if body is not None:
            message += f": {body}"
        elif raw_body:
            message += f": {raw_body}"

        super().__init__(message)


def normalize_peer_url(url: str) -> str:
    clean_url = url.strip().rstrip("/")

    if not clean_url.startswith(("http://", "https://")):
        clean_url = "http://" + clean_url

    return clean_url


def load_peers(peers_path: Path) -> set[str]:
    if not peers_path.exists():
        return set()

    with open(peers_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return set(data.get("peers", []))


def save_peers(peers_path: Path, peers: set[str]) -> None:
    peers_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "peers": sorted(peers),
    }

    with open(peers_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def load_block_pool(pool_path: Path) -> dict[str, Block]:
    if not pool_path.exists():
        return {}

    with open(pool_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    blocks = {}

    for block_hash, block_data in data.get("blocks", {}).items():
        block = Block.from_dict(block_data)
        blocks[block_hash] = block

    return blocks


def save_block_pool(pool_path: Path, blocks: dict[str, Block]) -> None:
    pool_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "blocks": {
            block_hash: block.to_dict()
            for block_hash, block in sorted(blocks.items())
        }
    }

    with open(pool_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def load_transaction_pool(pool_path: Path) -> list[Transaction]:
    if not pool_path.exists():
        return []

    with open(pool_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    transactions = []

    for tx_data in data.get("transactions", []):
        transaction = Transaction.from_dict(tx_data)
        transactions.append(transaction)

    return transactions


def save_transaction_pool(pool_path: Path, transactions: list[Transaction]) -> None:
    pool_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "transactions": [
            transaction.to_dict()
            for transaction in transactions
        ]
    }

    with open(pool_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

def parse_json_body(raw_body: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return None


def fetch_json(url: str, timeout: int = 5) -> dict[str, Any]:
    request_obj = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    except urllib.error.HTTPError as error:
        raw_body = error.read().decode("utf-8")
        json_body = parse_json_body(raw_body)
        raise HttpJsonError(error.code, json_body, raw_body) from error


def post_json(url: str, payload: dict[str, Any], timeout: int = 5) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")

    request_obj = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except urllib.error.HTTPError as error:
        raw_body = error.read().decode("utf-8")
        json_body = parse_json_body(raw_body)
        raise HttpJsonError(error.code, json_body, raw_body) from error


def should_trigger_sync(message: str) -> bool:
    lower_message = message.lower()

    return (
        "missing previous blocks" in lower_message
        or "possible fork" in lower_message
        or "does not extend current chain" in lower_message
        or "run sync" in lower_message
    )


def create_app(data_dir: Path, advertised_url: str | None = None) -> Flask:
    data_dir.mkdir(parents=True, exist_ok=True)

    chain_path = data_dir / "chain.json"
    peers_path = data_dir / "peers.json"
    block_store_path = data_dir / "block_index.json"
    orphan_blocks_path = data_dir / "orphan_blocks.json"
    side_branch_blocks_path = data_dir / "side_branch_blocks.json"
    mempool_path = data_dir / "mempool.json"
    transaction_index_path = data_dir / "tx_index.json"

    chain = Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(chain_path),
        auto_load=True,
    )

    block_store = BlockStore(block_store_path)
    block_store.put_many(chain.chain)

    transaction_index = TransactionIndex(transaction_index_path)
    transaction_index.rebuild_from_chain(chain.chain)

    peers = load_peers(peers_path)

    orphan_blocks = load_block_pool(orphan_blocks_path)
    block_store.put_many(list(orphan_blocks.values()))

    side_branch_blocks = load_block_pool(side_branch_blocks_path)
    block_store.put_many(list(side_branch_blocks.values()))

    persisted_mempool = load_transaction_pool(mempool_path)
    chain.mempool = []

    seen_transaction_hashes = set()

    for transaction in persisted_mempool:
        transaction_hash = transaction.transaction_hash()

        if transaction_hash in seen_transaction_hashes:
            continue

        if transaction.is_coinbase():
            continue

        added = chain.add_transaction(transaction)

        if added:
            seen_transaction_hashes.add(transaction_hash)

    save_transaction_pool(mempool_path, chain.mempool)

    app = Flask(__name__)

    def refresh_transaction_index() -> None:
        transaction_index.rebuild_from_chain(chain.chain)

    def save_orphan_pool() -> None:
        save_block_pool(orphan_blocks_path, orphan_blocks)

    def save_side_branch_pool() -> None:
        save_block_pool(side_branch_blocks_path, side_branch_blocks)

    def save_mempool() -> None:
        save_transaction_pool(mempool_path, chain.mempool)

    def get_local_node_url() -> str:
        if advertised_url is not None:
            return advertised_url

        return request.host_url.rstrip("/")

    def chain_summary() -> dict[str, Any]:
        return {
            "project": PROJECT_NAME,
            "coin": COIN_NAME,
            "height": len(chain.chain) - 1,
            "latest_hash": chain.latest_block().hash,
            "genesis_hash": chain.chain[0].hash,
            "next_block_difficulty": chain.calculate_next_difficulty(),
            "cumulative_work": chain.calculate_cumulative_work(),
            "target_block_time": chain.target_block_time,
            "difficulty_adjustment_interval": chain.difficulty_adjustment_interval,
            "mining_reward": chain.mining_reward,
            "mempool_path": str(mempool_path),
            "mempool_size": len(chain.mempool),
            "orphan_blocks_path": str(orphan_blocks_path),
            "orphan_pool_size": len(orphan_blocks),
            "max_orphan_blocks": MAX_ORPHAN_BLOCKS,
            "side_branch_pool_size": len(side_branch_blocks),
            "max_side_branch_blocks": MAX_SIDE_BRANCH_BLOCKS,
            "side_branch_blocks_path": str(side_branch_blocks_path),
            "valid": chain.is_valid(),
            "peers": sorted(peers),
            "advertised_url": get_local_node_url(),
            "storage_path": str(chain_path),
            "block_store_size": block_store.count(),
            "block_store_path": str(block_store_path),
            "transaction_index_size": transaction_index.count(),
            "transaction_index_path": str(transaction_index_path),
        }

    def transaction_is_known(transaction: Transaction) -> bool:
        tx_hash = transaction.transaction_hash()

        for pending_tx in chain.mempool:
            if pending_tx.transaction_hash() == tx_hash:
                return True

        for block in chain.chain:
            for tx_data in block.transactions:
                existing_tx = Transaction.from_dict(tx_data)

                if existing_tx.transaction_hash() == tx_hash:
                    return True

        return False

    def transaction_hashes_from_blocks(blocks: list[Block]) -> set[str]:
        transaction_hashes = set()

        for block in blocks:
            for tx_data in block.transactions:
                transaction = Transaction.from_dict(tx_data)

                if transaction.is_coinbase():
                    continue

                transaction_hashes.add(transaction.transaction_hash())

        return transaction_hashes

    def find_transaction_in_mempool(tx_hash: str) -> dict[str, Any] | None:
        for transaction in chain.mempool:
            current_hash = transaction.transaction_hash()

            if current_hash == tx_hash:
                return {
                    "hash": current_hash,
                    "location": "mempool",
                    "sender": transaction.sender_address(),
                    "receiver": transaction.receiver,
                    "amount": transaction.amount,
                    "fee": transaction.fee,
                    "nonce": transaction.nonce,
                    "is_coinbase": transaction.is_coinbase(),
                    "transaction": transaction.to_dict(),
                }

        return None

    def pending_transactions_for_address(address: str) -> list[dict[str, Any]]:
        results = []

        for position, transaction in enumerate(chain.mempool):
            sender_address = transaction.sender_address()

            if sender_address != address and transaction.receiver != address:
                continue

            tx_hash = transaction.transaction_hash()

            results.append(
                {
                    "hash": tx_hash,
                    "location": "mempool",
                    "block_hash": None,
                    "block_index": None,
                    "position": position,
                    "sender": transaction.sender_address(),
                    "receiver": transaction.receiver,
                    "amount": transaction.amount,
                    "fee": transaction.fee,
                    "nonce": transaction.nonce,
                    "is_coinbase": transaction.is_coinbase(),
                    "transaction": transaction.to_dict(),
                }
            )

        return results

    def collect_disconnected_transactions(
        old_chain: list[Block],
        new_chain: list[Block],
    ) -> list[Transaction]:
        new_block_hashes = {
            block.hash
            for block in new_chain
        }

        new_transaction_hashes = transaction_hashes_from_blocks(new_chain)

        disconnected_transactions = []
        seen_transaction_hashes = set()

        for old_block in old_chain:
            if old_block.hash in new_block_hashes:
                continue

            for tx_data in old_block.transactions:
                transaction = Transaction.from_dict(tx_data)

                if transaction.is_coinbase():
                    continue

                transaction_hash = transaction.transaction_hash()

                if transaction_hash in new_transaction_hashes:
                    continue

                if transaction_hash in seen_transaction_hashes:
                    continue

                seen_transaction_hashes.add(transaction_hash)
                disconnected_transactions.append(transaction)

        return disconnected_transactions

    def recover_mempool_after_reorg(
        old_chain: list[Block],
        new_chain: list[Block],
    ) -> dict[str, Any]:
        disconnected_transactions = collect_disconnected_transactions(
            old_chain=old_chain,
            new_chain=new_chain,
        )

        recovered_transactions = []
        rejected_transactions = []
        skipped_transactions = []

        for transaction in disconnected_transactions:
            transaction_hash = transaction.transaction_hash()

            if transaction_is_known(transaction):
                skipped_transactions.append(
                    {
                        "hash": transaction_hash,
                        "sender": transaction.sender,
                        "receiver": transaction.receiver,
                        "amount": transaction.amount,
                        "fee": transaction.fee,
                        "reason": "Transaction already known in current chain or mempool.",
                    }
                )
                continue

            added = chain.add_transaction(transaction)

            if added:
                recovered_transactions.append(
                    {
                        "hash": transaction_hash,
                        "sender": transaction.sender,
                        "receiver": transaction.receiver,
                        "amount": transaction.amount,
                        "fee": transaction.fee,
                    }
                )
            else:
                rejected_transactions.append(
                    {
                        "hash": transaction_hash,
                        "sender": transaction.sender,
                        "receiver": transaction.receiver,
                        "amount": transaction.amount,
                        "fee": transaction.fee,
                        "reason": "Transaction is no longer valid after reorg.",
                    }
                )

        save_mempool()

        return {
            "candidate_count": len(disconnected_transactions),
            "recovered_count": len(recovered_transactions),
            "rejected_count": len(rejected_transactions),
            "skipped_count": len(skipped_transactions),
            "recovered_transactions": recovered_transactions,
            "rejected_transactions": rejected_transactions,
            "skipped_transactions": skipped_transactions,
            "mempool_size": len(chain.mempool),
        }

    def get_sorted_peers_by_work() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        peer_statuses = []
        errors = []

        for peer in sorted(peers):
            try:
                status = fetch_json(f"{peer}/status")

                peer_statuses.append(
                    {
                        "peer": peer,
                        "height": status.get("height", 0),
                        "latest_hash": status.get("latest_hash"),
                        "genesis_hash": status.get("genesis_hash"),
                        "cumulative_work": status.get("cumulative_work", 0),
                        "valid": status.get("valid", False),
                    }
                )

            except (urllib.error.URLError, TimeoutError, ValueError, HttpJsonError) as error:
                errors.append(
                    {
                        "peer": peer,
                        "error": str(error),
                    }
                )

        peer_statuses.sort(
            key=lambda item: item["cumulative_work"],
            reverse=True,
        )

        return peer_statuses, errors

    def sync_with_peers() -> dict[str, Any]:
        adopted = False
        checked_peers = []
        errors = []
        downloaded_blocks = []
        mempool_recovery_results = []

        peer_statuses, status_errors = get_sorted_peers_by_work()
        errors.extend(status_errors)

        current_work = chain.calculate_cumulative_work()
        local_genesis_hash = chain.chain[0].hash

        for peer_status in peer_statuses:
            peer = peer_status["peer"]
            peer_work = peer_status["cumulative_work"]
            peer_genesis_hash = peer_status["genesis_hash"]
            peer_valid = peer_status["valid"]

            checked_peers.append(peer)

            if not peer_valid:
                errors.append(
                    {
                        "peer": peer,
                        "error": "Peer chain is not valid according to its status.",
                    }
                )
                continue

            if peer_genesis_hash != local_genesis_hash:
                errors.append(
                    {
                        "peer": peer,
                        "error": "Peer has a different genesis block.",
                    }
                )
                continue

            if peer_work <= current_work:
                continue

            try:
                headers_data = fetch_json(f"{peer}/headers")
                peer_headers = headers_data.get("headers", [])

                headers_valid, headers_message = validate_headers(peer_headers)

                if not headers_valid:
                    errors.append(
                        {
                            "peer": peer,
                            "error": headers_message,
                        }
                    )
                    continue

                if peer_headers[0]["hash"] != local_genesis_hash:
                    errors.append(
                        {
                            "peer": peer,
                            "error": "Peer headers have a different genesis block.",
                        }
                    )
                    continue

                common_index = find_common_header_index(peer_headers)

                if common_index is None:
                    errors.append(
                        {
                            "peer": peer,
                            "error": "No common ancestor found.",
                        }
                    )
                    continue

                missing_headers = peer_headers[common_index + 1 :]

                if not missing_headers:
                    continue

                missing_blocks = []

                for header in missing_headers:
                    block_hash = header["hash"]
                    block_data = fetch_json(f"{peer}/blocks/{block_hash}")
                    block = Block.from_dict(block_data["block"])

                    if block.hash != block_hash:
                        raise ValueError(
                            f"Downloaded block hash mismatch: {block_hash}"
                        )

                    missing_blocks.append(block)

                    downloaded_blocks.append(
                        {
                            "peer": peer,
                            "index": block.index,
                            "hash": block.hash,
                        }
                    )

                block_store.put_many(missing_blocks)
                candidate_chain = chain.chain[: common_index + 1] + missing_blocks

                old_chain = list(chain.chain)

                replaced = chain.replace_chain_if_better(candidate_chain)

                if replaced:
                    block_store.put_many(chain.chain)
                    refresh_transaction_index()

                    mempool_recovery_result = recover_mempool_after_reorg(
                        old_chain=old_chain,
                        new_chain=chain.chain,
                    )

                    mempool_recovery_results.append(
                        {
                            "peer": peer,
                            "result": mempool_recovery_result,
                        }
                    )

                    adopted = True
                    current_work = chain.calculate_cumulative_work()

            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, HttpJsonError) as error:
                errors.append(
                    {
                        "peer": peer,
                        "error": str(error),
                    }
                )

        orphan_result = process_orphans()

        return {
            "adopted_new_chain": adopted,
            "height": len(chain.chain) - 1,
            "latest_hash": chain.latest_block().hash,
            "cumulative_work": chain.calculate_cumulative_work(),
            "checked_peers": checked_peers,
            "peer_statuses": peer_statuses,
            "downloaded_blocks": downloaded_blocks,
            "downloaded_block_count": len(downloaded_blocks),
            "mempool_recovery_results": mempool_recovery_results,
            "orphan_result": orphan_result,
            "errors": errors,
        }

    def broadcast_block(block: Block, exclude_peer: str | None = None) -> list[dict[str, Any]]:
        results = []

        payload = {
            "block": block.to_dict(),
            "source": get_local_node_url(),
        }

        for peer in sorted(peers):
            if exclude_peer is not None and peer == exclude_peer:
                continue

            try:
                response = post_json(
                    url=f"{peer}/blocks",
                    payload=payload,
                )

                results.append(
                    {
                        "peer": peer,
                        "success": True,
                        "response": response,
                    }
                )

            except HttpJsonError as error:
                results.append(
                    {
                        "peer": peer,
                        "success": False,
                        "status_code": error.status_code,
                        "response": error.body,
                        "error": str(error),
                    }
                )

            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                results.append(
                    {
                        "peer": peer,
                        "success": False,
                        "error": str(error),
                    }
                )

        return results

    def broadcast_transaction(
        transaction: Transaction,
        exclude_peer: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []

        payload = {
            "transaction": transaction.to_dict(),
            "source": get_local_node_url(),
        }

        for peer in sorted(peers):
            if exclude_peer is not None and peer == exclude_peer:
                continue

            try:
                response = post_json(
                    url=f"{peer}/transactions",
                    payload=payload,
                )

                results.append(
                    {
                        "peer": peer,
                        "success": True,
                        "response": response,
                    }
                )

            except HttpJsonError as error:
                results.append(
                    {
                        "peer": peer,
                        "success": False,
                        "status_code": error.status_code,
                        "response": error.body,
                        "error": str(error),
                    }
                )

            except (urllib.error.URLError, TimeoutError, ValueError) as error:
                results.append(
                    {
                        "peer": peer,
                        "success": False,
                        "error": str(error),
                    }
                )

        return results

    @app.get("/")
    def index():
        return jsonify(
            {
                "message": f"{PROJECT_NAME} node is running",
                "status_endpoint": "/status",
                "chain_endpoint": "/chain",
                "headers_endpoint": "/headers",
                "mempool_endpoint": "/mempool",
                "blocks_endpoint": "/blocks",
                "block_by_hash_endpoint": "/blocks/<hash>",
                "transaction_by_hash_endpoint": "/transactions/<hash>",
                "address_transactions_endpoint": "/addresses/<address>/transactions",
                "transactions_endpoint": "/transactions",
                "orphans_endpoint": "/orphans",
                "side_branches_endpoint": "/side-branches",
                "advertised_url": get_local_node_url(),
            }
        )

    @app.get("/status")
    def status():
        return jsonify(chain_summary())

    @app.get("/chain")
    def get_chain():
        return jsonify(
            {
                "summary": chain_summary(),
                "chain": [block.to_dict() for block in chain.chain],
            }
        )

    @app.get("/mempool")
    def get_mempool():
        return jsonify(
            {
                "size": len(chain.mempool),
                "transactions": [
                    {
                        "hash": tx.transaction_hash(),
                        **tx.to_dict(),
                    }
                    for tx in chain.mempool
                ],
            }
        )

    @app.get("/balances/<address>")
    def get_balance(address: str):
        return jsonify(
            {
                "address": address,
                "balance": chain.get_balance(address),
                "coin": COIN_NAME,
                "confirmed_nonce": chain.nonces.get(address, 0),
            }
        )

    @app.get("/transactions/<tx_hash>")
    def get_transaction_by_hash(tx_hash: str):
        pending_transaction = find_transaction_in_mempool(tx_hash)

        if pending_transaction is not None:
            return jsonify(
                {
                    "found": True,
                    "transaction": pending_transaction,
                }
            )

        indexed_transaction = transaction_index.get(tx_hash)

        if indexed_transaction is not None:
            return jsonify(
                {
                    "found": True,
                    "transaction": indexed_transaction,
                }
            )

        return jsonify(
            {
                "found": False,
                "hash": tx_hash,
                "error": "Transaction not found.",
            }
        ), 404

    @app.get("/addresses/<address>/transactions")
    def get_address_transactions(address: str):
        confirmed_transactions = transaction_index.find_by_address(address)
        pending_transactions = pending_transactions_for_address(address)

        transactions = confirmed_transactions + pending_transactions

        return jsonify(
            {
                "address": address,
                "count": len(transactions),
                "confirmed_count": len(confirmed_transactions),
                "pending_count": len(pending_transactions),
                "transactions": transactions,
            }
        )
    
    @app.post("/transactions")
    def add_transaction():
        payload = request.get_json(silent=True)

        if payload is None:
            return jsonify({"error": "Missing JSON body."}), 400

        source_url = payload.get("source")

        if source_url:
            source_url = normalize_peer_url(source_url)
            peers.add(source_url)
            save_peers(peers_path, peers)

        tx_data = payload.get("transaction", payload)

        try:
            transaction = Transaction.from_dict(tx_data)
        except KeyError as error:
            return jsonify({"error": f"Invalid transaction field: {error}"}), 400

        if transaction.is_coinbase():
            return jsonify(
                {
                    "accepted": False,
                    "error": "Coinbase transactions cannot be broadcast.",
                }
            ), 400

        tx_hash = transaction.transaction_hash()

        if transaction_is_known(transaction):
            return jsonify(
                {
                    "accepted": True,
                    "already_known": True,
                    "transaction_hash": tx_hash,
                    "message": "Transaction already known.",
                    "mempool_size": len(chain.mempool),
                }
            ), 200

        added = chain.add_transaction(transaction)

        if not added:
            return jsonify(
                {
                    "accepted": False,
                    "transaction_hash": tx_hash,
                    "error": "Transaction rejected.",
                }
            ), 400
        
        save_mempool()

        broadcast_results = broadcast_transaction(
            transaction=transaction,
            exclude_peer=source_url,
        )

        return jsonify(
            {
                "accepted": True,
                "already_known": False,
                "message": "Transaction added to mempool.",
                "transaction_hash": tx_hash,
                "mempool_size": len(chain.mempool),
                "broadcast_results": broadcast_results,
            }
        ), 201
    
    @app.post("/blocks")
    def receive_block():
        payload = request.get_json(silent=True)

        if payload is None:
            return jsonify({"error": "Missing JSON body."}), 400

        block_data = payload.get("block")
        source_url = payload.get("source")

        if source_url:
            source_url = normalize_peer_url(source_url)
            peers.add(source_url)
            save_peers(peers_path, peers)

        if block_data is None:
            return jsonify({"error": "Missing block field."}), 400

        try:
            block = Block.from_dict(block_data)
        except (KeyError, ValueError) as error:
            return jsonify({"accepted": False, "error": str(error)}), 400

        accepted, message = chain.add_external_block(block)

        if message == "Block already known.":
            return jsonify(
                {
                    "accepted": True,
                    "already_known": True,
                    "message": message,
                    "sync_triggered": False,
                    "orphan_stored": False,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                    "orphan_pool_size": len(orphan_blocks),
                }
            ), 200

        if accepted:
            block_store.put(block)
            save_mempool()
            refresh_transaction_index()

            orphan_result = process_orphans()
            side_branch_result = try_adopt_side_branches()

            broadcast_results = broadcast_block(
                block=block,
                exclude_peer=source_url,
            )

            return jsonify(
                {
                    "accepted": True,
                    "already_known": False,
                    "message": message,
                    "sync_triggered": False,
                    "orphan_stored": False,
                    "side_branch_stored": False,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                    "orphan_pool_size": len(orphan_blocks),
                    "side_branch_pool_size": len(side_branch_blocks),
                    "orphan_result": orphan_result,
                    "side_branch_result": side_branch_result,
                    "broadcast_results": broadcast_results,
                }
            ), 201

        if can_store_side_branch_block(block):
            stored, side_branch_message = add_side_branch_block(block)

            orphan_result = process_orphans()
            side_branch_result = try_adopt_side_branches()

            return jsonify(
                {
                    "accepted": False,
                    "message": message,
                    "sync_triggered": False,
                    "orphan_stored": False,
                    "side_branch_stored": stored,
                    "side_branch_message": side_branch_message,
                    "orphan_result": orphan_result,
                    "side_branch_result": side_branch_result,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                    "orphan_pool_size": len(orphan_blocks),
                    "side_branch_pool_size": len(side_branch_blocks),
                }
            ), 202
                
        if should_store_as_orphan(block, message):
            stored, orphan_message = add_orphan_block(block)

            sync_result = None

            if should_trigger_sync(message):
                sync_result = sync_with_peers()

            orphan_result = process_orphans()

            return jsonify(
                {
                    "accepted": False,
                    "message": message,
                    "sync_triggered": sync_result is not None,
                    "sync_result": sync_result,
                    "orphan_stored": stored,
                    "orphan_message": orphan_message,
                    "orphan_result": orphan_result,
                    "orphan_pool_size": len(orphan_blocks),
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                }
            ), 202

        if should_trigger_sync(message):
            sync_result = sync_with_peers()
            orphan_result = process_orphans()

            status_code = 202 if sync_result["adopted_new_chain"] else 409

            return jsonify(
                {
                    "accepted": False,
                    "message": message,
                    "sync_triggered": True,
                    "sync_result": sync_result,
                    "orphan_stored": False,
                    "orphan_result": orphan_result,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                    "orphan_pool_size": len(orphan_blocks),
                    "side_branch_pool_size": len(side_branch_blocks),
                }
            ), status_code

        return jsonify(
            {
                "accepted": False,
                "message": message,
                "sync_triggered": False,
                "orphan_stored": False,
                "height": len(chain.chain) - 1,
                "latest_hash": chain.latest_block().hash,
                "cumulative_work": chain.calculate_cumulative_work(),
                "orphan_pool_size": len(orphan_blocks),
                    "side_branch_pool_size": len(side_branch_blocks),
            }
        ), 409

    @app.post("/mine")
    def mine():
        payload = request.get_json(silent=True) or {}

        miner_address = payload.get("miner_address")
        max_transactions = payload.get("max_transactions")

        if not miner_address:
            return jsonify({"error": "Missing miner_address."}), 400

        if not isinstance(miner_address, str) or len(miner_address) != 40:
            return jsonify({"error": "miner_address must be a 40-character address."}), 400

        if max_transactions is not None and not isinstance(max_transactions, int):
            return jsonify({"error": "max_transactions must be an integer."}), 400

        old_height = len(chain.chain) - 1

        added = chain.mine_pending_transactions(
            miner_address=miner_address,
            max_transactions=max_transactions,
        )

        if not added:
            return jsonify({"mined": False, "error": "Mining failed."}), 400

        latest_block = chain.latest_block()
        block_store.put(latest_block)
        save_mempool()
        refresh_transaction_index()

        broadcast_results = broadcast_block(
            block=latest_block,
            exclude_peer=None,
        )

        orphan_result = process_orphans()
        side_branch_result = try_adopt_side_branches()

        return jsonify(
            {
                "mined": True,
                "old_height": old_height,
                "new_height": len(chain.chain) - 1,
                "block_hash": latest_block.hash,
                "difficulty": latest_block.difficulty,
                "miner_address": miner_address,
                "miner_balance": chain.get_balance(miner_address),
                "coin": COIN_NAME,
                "broadcast_results": broadcast_results,
                "orphan_result": orphan_result,
                "orphan_pool_size": len(orphan_blocks),
                "side_branch_result": side_branch_result,
                "side_branch_pool_size": len(side_branch_blocks),
            }
        )

    @app.get("/peers")
    def get_peers():
        return jsonify(
            {
                "peers": sorted(peers),
                "count": len(peers),
                "advertised_url": get_local_node_url(),
            }
        )

    @app.post("/peers")
    def add_peer():
        payload = request.get_json(silent=True)

        if payload is None:
            return jsonify({"error": "Missing JSON body."}), 400

        url = payload.get("url")

        if not url:
            return jsonify({"error": "Missing peer url."}), 400

        peer_url = normalize_peer_url(url)

        if peer_url == get_local_node_url():
            return jsonify(
                {
                    "added": False,
                    "message": "Refusing to add self as peer.",
                    "peer": peer_url,
                    "peers": sorted(peers),
                    "advertised_url": get_local_node_url(),
                }
            ), 200

        peers.add(peer_url)
        save_peers(peers_path, peers)

        return jsonify(
            {
                "added": True,
                "peer": peer_url,
                "peers": sorted(peers),
                "advertised_url": get_local_node_url(),
            }
        ), 201

    @app.post("/sync")
    def sync():
        return jsonify(sync_with_peers())

    def known_block_hashes() -> set[str]:
        return {block.hash for block in chain.chain}

    def block_is_known(block_hash: str) -> bool:
        if block_hash in orphan_blocks:
            return True

        return block_hash in known_block_hashes()
    
    def get_block_location(block_hash: str) -> str:
        if block_hash in known_block_hashes():
            return "main_chain"

        if block_hash in orphan_blocks:
            return "orphan_pool"

        if block_hash in side_branch_blocks:
            return "side_branch_pool"

        if block_store.has(block_hash):
            return "block_store"

        return "unknown"
    
    def block_has_basic_validity(block: Block) -> bool:
        if block.hash != block.compute_hash():
            return False

        if not block.verify_merkle_root():
            return False

        if not block.hash.startswith("0" * block.difficulty):
            return False

        return True

    def can_remain_orphan(block: Block, message: str) -> bool:
        if not block_has_basic_validity(block):
            return False

        known_hashes = known_block_hashes()

        if block.previous_hash not in known_hashes and block.index > 0:
            return True

        lower_message = message.lower()

        return (
            "missing previous blocks" in lower_message
            or "parent" in lower_message
        )
    
    def should_store_as_orphan(block: Block, message: str) -> bool:
        if block_is_known(block.hash):
            return False

        return can_remain_orphan(block, message)

    def add_orphan_block(block: Block) -> tuple[bool, str]:
        if block_is_known(block.hash):
            return False, "Block already known or already stored as orphan."

        if len(orphan_blocks) >= MAX_ORPHAN_BLOCKS:
            oldest_hash = next(iter(orphan_blocks))
            del orphan_blocks[oldest_hash]

        orphan_blocks[block.hash] = block
        block_store.put(block)
        save_orphan_pool()
        return True, "Orphan block stored."

    def orphan_summary(block: Block) -> dict[str, Any]:
        return {
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "difficulty": block.difficulty,
            "transaction_count": len(block.transactions),
        }

    def process_orphans() -> dict[str, Any]:
        moved_to_side_branch_blocks = []
        attached_blocks = []
        removed_blocks = []
        progress = True
        orphan_pool_changed = False
        mempool_changed = False

        while progress:
            progress = False

            for orphan_hash, orphan_block in list(orphan_blocks.items()):
                accepted, message = chain.add_external_block(orphan_block)

                if accepted:
                    block_store.put(orphan_block)
                    refresh_transaction_index()
                    mempool_changed = True

                    del orphan_blocks[orphan_hash]
                    orphan_pool_changed = True
                    progress = True

                    broadcast_results = broadcast_block(
                        block=orphan_block,
                        exclude_peer=None,
                    )

                    attached_blocks.append(
                        {
                            "hash": orphan_block.hash,
                            "index": orphan_block.index,
                            "message": message,
                            "broadcast_results": broadcast_results,
                        }
                    )

                elif message == "Block already known.":
                    del orphan_blocks[orphan_hash]
                    orphan_pool_changed = True
                    progress = True

                    removed_blocks.append(
                        {
                            "hash": orphan_block.hash,
                            "index": orphan_block.index,
                            "reason": message,
                        }
                    )
                elif can_store_side_branch_block(orphan_block):
                    stored, side_branch_message = add_side_branch_block(orphan_block)

                    del orphan_blocks[orphan_hash]
                    orphan_pool_changed = True
                    progress = True

                    moved_to_side_branch_blocks.append(
                        {
                            "hash": orphan_block.hash,
                            "index": orphan_block.index,
                            "stored": stored,
                            "message": side_branch_message,
                        }
                    )
                
                elif not can_remain_orphan(orphan_block, message):
                    del orphan_blocks[orphan_hash]
                    orphan_pool_changed = True
                    progress = True

                    removed_blocks.append(
                        {
                            "hash": orphan_block.hash,
                            "index": orphan_block.index,
                            "reason": message,
                        }
                    )
        if orphan_pool_changed:
            save_orphan_pool()

        if mempool_changed:
            save_mempool()

        return {
            "attached_count": len(attached_blocks),
            "removed_count": len(removed_blocks),
            "moved_to_side_branch_count": len(moved_to_side_branch_blocks),
            "remaining_count": len(orphan_blocks),
            "attached_blocks": attached_blocks,
            "removed_blocks": removed_blocks,
            "moved_to_side_branch_blocks": moved_to_side_branch_blocks,
        }
    
    def side_branch_summary(block: Block) -> dict[str, Any]:
        return {
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "difficulty": block.difficulty,
            "transaction_count": len(block.transactions),
        }

    def find_chain_index_by_hash(block_hash: str) -> int | None:
        for index, block in enumerate(chain.chain):
            if block.hash == block_hash:
                return index

        return None

    def side_branch_block_is_known(block_hash: str) -> bool:
        return block_hash in side_branch_blocks or block_hash in known_block_hashes()

    def can_store_side_branch_block(block: Block) -> bool:
        if side_branch_block_is_known(block.hash):
            return False

        if not block_has_basic_validity(block):
            return False

        parent_is_in_main_chain = find_chain_index_by_hash(block.previous_hash) is not None
        parent_is_in_side_branch = block.previous_hash in side_branch_blocks

        return parent_is_in_main_chain or parent_is_in_side_branch

    def add_side_branch_block(block: Block) -> tuple[bool, str]:
        if side_branch_block_is_known(block.hash):
            return False, "Block already known or already stored as side branch."

        if len(side_branch_blocks) >= MAX_SIDE_BRANCH_BLOCKS:
            oldest_hash = next(iter(side_branch_blocks))
            del side_branch_blocks[oldest_hash]

        side_branch_blocks[block.hash] = block
        block_store.put(block)
        save_side_branch_pool()

        return True, "Side-branch block stored."

    def get_side_branch_tip_hashes() -> list[str]:
        referenced_hashes = {
            block.previous_hash
            for block in side_branch_blocks.values()
        }

        return [
            block_hash
            for block_hash in side_branch_blocks.keys()
            if block_hash not in referenced_hashes
        ]

    def build_side_branch_candidate(tip_hash: str) -> tuple[list[Block] | None, str]:
        if tip_hash not in side_branch_blocks:
            return None, "Unknown side-branch tip."

        branch_blocks = []
        current_hash = tip_hash
        seen_hashes = set()

        while current_hash in side_branch_blocks:
            if current_hash in seen_hashes:
                return None, "Cycle detected in side branch."

            seen_hashes.add(current_hash)

            current_block = side_branch_blocks[current_hash]
            branch_blocks.append(current_block)

            parent_index = find_chain_index_by_hash(current_block.previous_hash)

            if parent_index is not None:
                branch_blocks.reverse()

                candidate_chain = chain.chain[: parent_index + 1] + branch_blocks

                return candidate_chain, "Candidate side branch built."

            current_hash = current_block.previous_hash

        return None, "Missing common ancestor."

    def remove_side_branch_blocks_present_in_main_chain() -> int:
        main_hashes = known_block_hashes()
        removed_count = 0

        for block_hash in list(side_branch_blocks.keys()):
            if block_hash in main_hashes:
                del side_branch_blocks[block_hash]
                removed_count += 1

        if removed_count > 0:
            save_side_branch_pool()

        return removed_count

    def cleanup_side_branch_pool() -> dict[str, Any]:
        removed_count = remove_side_branch_blocks_present_in_main_chain()

        return {
            "removed_count": removed_count,
            "remaining_count": len(side_branch_blocks),
        }

    def try_adopt_side_branches() -> dict[str, Any]:
        checked_branches = []
        adopted_branches = []

        for tip_hash in get_side_branch_tip_hashes():
            candidate_chain, message = build_side_branch_candidate(tip_hash)

            if candidate_chain is None:
                checked_branches.append(
                    {
                        "tip_hash": tip_hash,
                        "adopted": False,
                        "message": message,
                    }
                )
                continue

            old_chain = list(chain.chain)
            old_height = len(chain.chain) - 1
            old_latest_hash = chain.latest_block().hash

            replaced = chain.replace_chain_if_better(candidate_chain)
            mempool_recovery_result = None

            checked_branches.append(
                {
                    "tip_hash": tip_hash,
                    "adopted": replaced,
                    "message": message,
                    "candidate_height": len(candidate_chain) - 1,
                    "old_height": old_height,
                    "old_latest_hash": old_latest_hash,
                    "new_height": len(chain.chain) - 1,
                    "new_latest_hash": chain.latest_block().hash,
                    "mempool_recovery_result": mempool_recovery_result,
                }
            )

            if replaced:
                block_store.put_many(chain.chain)
                refresh_transaction_index()

                mempool_recovery_result = recover_mempool_after_reorg(
                    old_chain=old_chain,
                    new_chain=chain.chain,
                )

                removed_count = remove_side_branch_blocks_present_in_main_chain()

                adopted_branches.append(
                    {
                        "tip_hash": tip_hash,
                        "old_height": old_height,
                        "new_height": len(chain.chain) - 1,
                        "old_latest_hash": old_latest_hash,
                        "new_latest_hash": chain.latest_block().hash,
                        "removed_side_branch_blocks": removed_count,
                        "mempool_recovery_result": mempool_recovery_result,
                    }
                )

        return {
            "checked_count": len(checked_branches),
            "adopted_count": len(adopted_branches),
            "remaining_count": len(side_branch_blocks),
            "checked_branches": checked_branches,
            "adopted_branches": adopted_branches,
        }
    
    @app.get("/orphans")
    def get_orphans():
        return jsonify(
            {
                "size": len(orphan_blocks),
                "max_size": MAX_ORPHAN_BLOCKS,
                "blocks": [
                    orphan_summary(block)
                    for block in orphan_blocks.values()
                ],
            }
        )
    
    def block_header_summary(block: Block) -> dict[str, Any]:
        return {
            "index": block.index,
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "difficulty": block.difficulty,
            "timestamp": block.timestamp,
            "nonce": block.nonce,
            "hash": block.hash,
            "transaction_count": len(block.transactions),
        }

    def compute_header_hash(header: dict[str, Any]) -> str:
        header_data = {
            "index": header["index"],
            "previous_hash": header["previous_hash"],
            "merkle_root": header["merkle_root"],
            "difficulty": header["difficulty"],
            "timestamp": header["timestamp"],
            "nonce": header["nonce"],
        }

        return __import__("hashlib").sha3_256(
            json.dumps(
                header_data,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def validate_headers(headers: list[dict[str, Any]]) -> tuple[bool, str]:
        if not headers:
            return False, "Header list is empty."

        for position, header in enumerate(headers):
            required_fields = {
                "index",
                "previous_hash",
                "merkle_root",
                "difficulty",
                "timestamp",
                "nonce",
                "hash",
            }

            missing_fields = required_fields - set(header.keys())

            if missing_fields:
                return False, f"Header is missing fields: {sorted(missing_fields)}"

            expected_hash = compute_header_hash(header)

            if header["hash"] != expected_hash:
                return False, f"Invalid header hash at position {position}."

            if not header["hash"].startswith("0" * header["difficulty"]):
                return False, f"Invalid Proof of Work at position {position}."

            if header["index"] != position:
                return False, f"Invalid header index at position {position}."

            if position > 0:
                previous_header = headers[position - 1]

                if header["previous_hash"] != previous_header["hash"]:
                    return False, f"Broken header link at position {position}."

        return True, "Headers are valid."

    def find_common_header_index(peer_headers: list[dict[str, Any]]) -> int | None:
        local_hash_to_index = {
            block.hash: index
            for index, block in enumerate(chain.chain)
        }

        for peer_header in reversed(peer_headers):
            peer_hash = peer_header["hash"]

            if peer_hash in local_hash_to_index:
                return local_hash_to_index[peer_hash]

        return None
    
    @app.get("/side-branches")
    def get_side_branches():
        return jsonify(
            {
                "size": len(side_branch_blocks),
                "max_size": MAX_SIDE_BRANCH_BLOCKS,
                "tip_hashes": get_side_branch_tip_hashes(),
                "blocks": [
                    side_branch_summary(block)
                    for block in side_branch_blocks.values()
                ],
            }
        )
    
    @app.get("/headers")
    def get_headers():
        return jsonify(
            {
                "summary": chain_summary(),
                "headers": [
                    block_header_summary(block)
                    for block in chain.chain
                ],
            }
        )
    
    @app.get("/blocks/<block_hash>")
    def get_block_by_hash(block_hash: str):
        block = block_store.get(block_hash)

        if block is not None:
            return jsonify(
                {
                    "found": True,
                    "location": get_block_location(block_hash),
                    "block": block.to_dict(),
                }
            )

        return jsonify(
            {
                "found": False,
                "error": "Block not found.",
                "hash": block_hash,
            }
        ), 404
    
    return app

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Run a local {PROJECT_NAME} HTTP node"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the node to",
    )

    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port to run the node on",
    )

    parser.add_argument(
        "--data-dir",
        default=None,
        help="Node data directory. Default: data/nodes/node_<port>",
    )

    parser.add_argument(
        "--advertised-url",
        default=None,
        help="URL this node announces to peers, example: http://node1:5000",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.data_dir is None:
        data_dir = DATA_DIR / "nodes" / f"node_{args.port}"
    else:
        data_dir = Path(args.data_dir)

    advertised_url = None

    if args.advertised_url is not None:
        advertised_url = normalize_peer_url(args.advertised_url)

    app = create_app(
        data_dir=data_dir,
        advertised_url=advertised_url,
    )

    print(f"{PROJECT_NAME} node")
    print("-" * (len(PROJECT_NAME) + 5))
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Advertised URL: {advertised_url}")
    print(f"Data directory: {data_dir}")
    print(f"Status: http://{args.host}:{args.port}/status")

    app.run(
        host=args.host,
        port=args.port,
        debug=False,
    )


if __name__ == "__main__":
    main()