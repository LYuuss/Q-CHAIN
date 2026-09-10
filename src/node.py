import argparse
import json
import re
import time
import urllib.error
from pathlib import Path
from typing import Any
from threading import RLock
from urllib.parse import urlparse

from flask import Flask, g, has_request_context, jsonify, request

from explorer import register_explorer, paginate, with_confirmations
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
from storage_utils import atomic_write_json, read_json_or_default, read_json_strict
from http_client import fetch_json, post_json, HttpJsonError
from validation import (
    is_address,
    is_hex,
    is_integer,
    validate_header,
    MAX_JSON_BYTES,
    MAX_BLOCK_TRANSACTIONS,
    MAX_FUTURE_BLOCK_SECONDS,
)

MAX_ORPHAN_BLOCKS = 100
MAX_SIDE_BRANCH_BLOCKS = 200

def load_peers(peers_path: Path) -> set[str]:
    data = read_json_or_default(
        peers_path,
        default={
            "peers": [],
        },
    )

    values = data.get("peers", [])
    return {value for value in values if isinstance(value, str)} if isinstance(values, list) else set()


def save_peers(peers_path: Path, peers: set[str]) -> None:
    data = {
        "peers": sorted(peers),
    }

    atomic_write_json(peers_path, data)

def load_block_pool(pool_path: Path) -> dict[str, Block]:
    data = read_json_or_default(
        pool_path,
        default={
            "blocks": {},
        },
    )

    blocks = {}

    entries = data.get("blocks", {})
    if not isinstance(entries, dict):
        return blocks
    for block_hash, block_data in entries.items():
        try:
            block = Block.from_dict(block_data)
            if block.hash == block_hash and block.has_valid_proof():
                blocks[block_hash] = block
        except (ValueError, TypeError, KeyError):
            continue

    return blocks


def save_block_pool(pool_path: Path, blocks: dict[str, Block]) -> None:
    data = {
        "blocks": {
            block_hash: block.to_dict()
            for block_hash, block in sorted(blocks.items())
        }
    }

    atomic_write_json(pool_path, data)

def load_transaction_pool(pool_path: Path) -> list[Transaction]:
    data = read_json_or_default(
        pool_path,
        default={
            "transactions": [],
        },
    )

    transactions = []

    entries = data.get("transactions", [])
    if not isinstance(entries, list):
        return transactions
    for tx_data in entries:
        try:
            transaction = Transaction.from_dict(tx_data)
            transactions.append(transaction)
        except (ValueError, TypeError, KeyError):
            continue

    return transactions

def save_transaction_pool(pool_path: Path, transactions: list[Transaction]) -> None:
    data = {
        "transactions": [
            transaction.to_dict()
            for transaction in transactions
        ]
    }

    atomic_write_json(pool_path, data)

def should_trigger_sync(message: str) -> bool:
    lower_message = message.lower()

    return (
        "missing previous blocks" in lower_message
        or "possible fork" in lower_message
        or "does not extend current chain" in lower_message
        or "run sync" in lower_message
    )

def normalize_peer_url(peer_url: str) -> str | None:
    if not isinstance(peer_url, str) or len(peer_url) > 2048:
        return None
    peer_url = peer_url.strip()
    if any(char.isspace() for char in peer_url) or "\\" in peer_url:
        return None
    try:
        parsed = urlparse(peer_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return None
        host = parsed.hostname.lower()
        if not re.fullmatch(r"[a-z0-9.:-]+", host):
            return None
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            return None
        if ":" in host:
            host = f"[{host}]"
        if port is not None and port != (80 if parsed.scheme == "http" else 443):
            host += f":{port}"
        return f"{parsed.scheme}://{host}"
    except ValueError:
        return None


def extract_peer_url(payload: dict) -> str | None:
    peer_url = payload.get("peer")

    if peer_url is None:
        peer_url = payload.get("url")

    if peer_url is None:
        peer_url = payload.get("peer_url")

    return normalize_peer_url(peer_url)

def create_app(data_dir: Path, advertised_url: str | None = None) -> Flask:
    normalized_advertised_url = normalize_peer_url(advertised_url)
    if advertised_url is not None and normalized_advertised_url is None:
        raise ValueError("Invalid advertised URL: expected an HTTP(S) origin.")
    data_dir.mkdir(parents=True, exist_ok=True)

    chain_path = data_dir / "chain.json"
    peers_path = data_dir / "peers.json"
    block_store_path = data_dir / "block_index.json"
    orphan_blocks_path = data_dir / "orphan_blocks.json"
    side_branch_blocks_path = data_dir / "side_branch_blocks.json"
    mempool_path = data_dir / "mempool.json"
    transaction_index_path = data_dir / "tx_index.json"
    reorg_history_path = data_dir / "reorg_history.json"
    reorg_data = read_json_or_default(reorg_history_path, {"reorgs": []})
    reorg_history = reorg_data.get("reorgs", [])
    if not isinstance(reorg_history, list):
        reorg_history = []
    reorg_history = [entry for entry in reorg_history if isinstance(entry, dict)][-100:]
    # chain.json is authoritative. Only import the old mirror during migration.
    migrate_mempool = chain_path.exists() and "mempool" not in read_json_strict(chain_path)

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

    loaded_peers = load_peers(peers_path)

    peers = {
        normalized_peer
        for peer in sorted(loaded_peers)[:32]
        if (normalized_peer := normalize_peer_url(peer)) is not None
        and normalized_peer != normalized_advertised_url
    }

    save_peers(peers_path, peers)

    orphan_blocks = load_block_pool(orphan_blocks_path)
    block_store.put_many(list(orphan_blocks.values()))

    side_branch_blocks = load_block_pool(side_branch_blocks_path)
    block_store.put_many(list(side_branch_blocks.values()))

    if migrate_mempool:
        chain.mempool = load_transaction_pool(mempool_path)
        chain.clean_mempool()
        chain.save_to_disk()
    save_transaction_pool(mempool_path, chain.mempool)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_JSON_BYTES
    state_lock = RLock()

    @app.before_request
    def lock_state():
        if request.method == "POST" and (request.content_length or request.is_json):
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify({"error": "Request body must be a JSON object."}), 400
        state_lock.acquire()
        g.state_locked = True

    @app.teardown_request
    def unlock_state(error=None):
        if g.pop("state_locked", False):
            state_lock.release()

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": error.description}), 400

    @app.errorhandler(413)
    def request_too_large(error):
        return jsonify({"error": "Request body exceeds the size limit."}), 413

    def network_call(function, *args, **kwargs):
        # Commit local state before I/O; peers must be able to call back while
        # this request waits on their response (including triangle broadcasts).
        locked = has_request_context() and g.get("state_locked", False)
        if locked:
            state_lock.release()
        try:
            return function(*args, **kwargs)
        finally:
            if locked:
                state_lock.acquire()

    def add_peer(peer_url: str) -> tuple[bool, str, str | None]:
        normalized_peer = normalize_peer_url(peer_url)

        if normalized_peer is None:
            return False, "Invalid peer URL.", None

        self_urls = {normalized_advertised_url}
        if has_request_context():
            self_urls.add(normalize_peer_url(request.host_url))
        if normalized_peer in self_urls:
            return False, "Cannot add self as peer.", normalized_peer

        if normalized_peer in peers:
            return False, "Peer already known.", normalized_peer

        if len(peers) >= 32:
            return False, "Peer limit reached.", normalized_peer
        peers.add(normalized_peer)
        save_peers(peers_path, peers)

        return True, "Peer added.", normalized_peer

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
            return normalized_advertised_url

        return request.host_url.rstrip("/")

    def chain_summary() -> dict[str, Any]:
        return {
            "project": PROJECT_NAME,
            "version": "0.2.3-alpha",
            "reorg_count": len(reorg_history),
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

    def recover_mempool_after_reorg(old_chain, new_chain, reason="side_branch"):
        result = chain.last_reorg_recovery
        save_mempool()
        current_hashes = {block.hash for block in new_chain}
        disconnected = [block for block in old_chain if block.hash not in current_hashes]
        # Keep the losing chain attachable: it can become the heaviest again.
        remove_side_branch_blocks_present_in_main_chain()
        for block in disconnected:
            add_side_branch_block(block)
        if disconnected:
            common_height = next(
                (block.index for block in reversed(old_chain) if block.hash in current_hashes), 0
            )
            reorg_history.append({
                "old_tip": old_chain[-1].hash, "new_tip": new_chain[-1].hash,
                "old_height": old_chain[-1].index, "new_height": new_chain[-1].index,
                "common_ancestor_height": common_height,
                "disconnected_block_count": len(disconnected),
                "connected_block_count": len(new_chain) - common_height - 1,
                "recovered_transaction_count": result["recovered_count"],
                "rejected_transaction_count": result["rejected_count"],
                "reason": reason, "timestamp": time.time(),
            })
            del reorg_history[:-100]
            atomic_write_json(reorg_history_path, {"reorgs": reorg_history})
        return result

    def get_sorted_peers_by_work() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        peer_statuses = []
        errors = []

        for peer in sorted(peers):
            try:
                status = network_call(fetch_json, f"{peer}/status")
                if not is_integer(status.get("cumulative_work")) or not is_integer(status.get("height")):
                    raise ValueError("Peer status contains invalid height or cumulative work.")

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
                headers_data = network_call(fetch_json, f"{peer}/headers")
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

                local_prefix = list(chain.chain[: common_index + 1])
                missing_blocks = []

                for header in missing_headers:
                    block_hash = header["hash"]
                    block_data = network_call(fetch_json, f"{peer}/blocks/{block_hash}")
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

                candidate_chain = local_prefix + missing_blocks

                old_chain = list(chain.chain)

                replaced = chain.replace_chain_if_better(candidate_chain)

                if replaced:
                    block_store.put_many(chain.chain)
                    refresh_transaction_index()

                    mempool_recovery_result = recover_mempool_after_reorg(
                        old_chain=old_chain,
                        new_chain=chain.chain,
                        reason=f"sync:{peer}",
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
        side_branch_result = try_adopt_side_branches()

        return {
            "side_branch_result": side_branch_result,
            "adopted_new_chain": adopted or side_branch_result["adopted_count"] > 0,
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
                response = network_call(post_json,
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
                response = network_call(post_json,
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
                "peers_endpoint": "/peers",
                "peer_discovery_endpoint": "/peers/discover",
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

    @app.get("/addresses/<address>/balance")
    @app.get("/balances/<address>")
    def get_balance(address: str):
        if not is_address(address):
            return jsonify({"error": "Invalid address."}), 400
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
                    "transaction": with_confirmations(pending_transaction, chain),
                }
            )

        indexed_transaction = transaction_index.get(tx_hash)

        if indexed_transaction is not None:
            return jsonify(
                {
                    "found": True,
                    "transaction": with_confirmations(indexed_transaction, chain),
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
        if not is_address(address):
            return jsonify({"error": "Invalid address."}), 400
        confirmed_transactions = transaction_index.find_by_address(address)
        pending_transactions = pending_transactions_for_address(address)

        transactions, pagination = paginate([
            with_confirmations(tx, chain) for tx in confirmed_transactions + pending_transactions
        ])

        return jsonify(
            {
                "address": address,
                **pagination,
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

        source_url = normalize_peer_url(source_url)

        tx_data = payload.get("transaction", payload)

        try:
            transaction = Transaction.from_dict(tx_data)
        except (KeyError, ValueError, TypeError) as error:
            return jsonify({"error": f"Invalid transaction: {error}"}), 400

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

        source_url = normalize_peer_url(source_url)

        if block_data is None:
            return jsonify({"error": "Missing block field."}), 400

        try:
            block = Block.from_dict(block_data)
        except (KeyError, ValueError, TypeError) as error:
            return jsonify({"accepted": False, "error": str(error)}), 400

        if not block_has_basic_validity(block):
            return jsonify({"accepted": False, "error": "Invalid block structure or proof."}), 400
        if block.hash in orphan_blocks or block.hash in side_branch_blocks:
            return jsonify({"accepted": False, "already_known": True,
                            "location": get_block_location(block.hash)}), 200
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

        if not is_address(miner_address):
            return jsonify({"error": "miner_address must be a 40-character address."}), 400

        if max_transactions is not None and not is_integer(max_transactions, 0, MAX_BLOCK_TRANSACTIONS - 1):
            return jsonify({"error": f"max_transactions must be between 0 and {MAX_BLOCK_TRANSACTIONS - 1}."}), 400

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
                "count": len(peers),
                "peers": sorted(peers),
            }
        )

    @app.post("/peers")
    def add_peer_endpoint():
        payload = request.get_json(silent=True) or {}

        peer_url = extract_peer_url(payload)

        if peer_url is None:
            return jsonify(
                {
                    "added": False,
                    "error": "Missing or invalid peer URL.",
                }
            ), 400

        added, message, normalized_peer = add_peer(peer_url)

        status_code = 201 if added else 200

        if not added and message in {"Invalid peer URL.", "Cannot add self as peer."}:
            status_code = 400

        return jsonify(
            {
                "added": added,
                "message": message,
                "peer": normalized_peer,
                "count": len(peers),
                "peers": sorted(peers),
            }
        ), status_code

    @app.post("/peers/discover")
    def discover_peers():
        discovered_peers = []
        skipped_peers = []
        failed_peers = []

        current_peers = sorted(peers)

        for peer in current_peers:
            try:
                data = network_call(fetch_json, f"{peer}/peers", timeout=3)
                if not isinstance(data, dict):
                    raise ValueError("Peer response must be an object.")
            except (urllib.error.URLError, TimeoutError, ValueError, HttpJsonError) as error:
                failed_peers.append(
                    {
                        "peer": peer,
                        "error": str(error),
                    }
                )
                continue

            remote_peers = data.get("peers", [])

            if not isinstance(remote_peers, list):
                skipped_peers.append(
                    {
                        "peer": peer,
                        "reason": "Remote peer list is invalid.",
                    }
                )
                continue

            for remote_peer in remote_peers[:32]:
                added, message, normalized_peer = add_peer(remote_peer)

                result = {
                    "source_peer": peer,
                    "peer": normalized_peer,
                    "message": message,
                }

                if added:
                    discovered_peers.append(result)
                else:
                    skipped_peers.append(result)

        return jsonify(
            {
                "discovered_count": len(discovered_peers),
                "skipped_count": len(skipped_peers),
                "failed_count": len(failed_peers),
                "discovered_peers": discovered_peers,
                "skipped_peers": skipped_peers,
                "failed_peers": failed_peers,
                "count": len(peers),
                "peers": sorted(peers),
            }
        )

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
        if not block.has_valid_proof() or block.timestamp > time.time() + MAX_FUTURE_BLOCK_SECONDS:
            return False
        if block.index == 0:
            return block.hash == chain.chain[0].hash and not block.transactions
        try:
            txs = [Transaction.from_dict(tx) for tx in block.transactions]
            return bool(txs) and txs[0].is_coinbase() and txs[0].nonce == block.index and all(
                tx.verify() and not tx.is_coinbase() for tx in txs[1:]
            ) and txs[0].amount == chain.mining_reward + sum(tx.fee for tx in txs[1:])
        except (ValueError, KeyError, TypeError):
            return False

    def can_remain_orphan(block: Block, message: str) -> bool:
        if not block_has_basic_validity(block):
            return False

        return (
            block.index > 0
            and block.previous_hash not in known_block_hashes()
            and block.previous_hash not in side_branch_blocks
        )
    
    def should_store_as_orphan(block: Block, message: str) -> bool:
        if block_is_known(block.hash) or block.hash in side_branch_blocks:
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

                    # The original sender or the next explicit sync propagates it.
                    broadcast_results = []

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

        parent_index = find_chain_index_by_hash(block.previous_hash)
        if parent_index is not None:
            prefix = chain.chain[:parent_index + 1]
        elif block.previous_hash in side_branch_blocks:
            prefix, _ = build_side_branch_candidate(block.previous_hash)
            if prefix is None:
                return False
        else:
            return False
        return chain.is_valid_chain(prefix + [block])

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
                checked_branches[-1]["mempool_recovery_result"] = mempool_recovery_result

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
        if not isinstance(headers, list) or not headers or len(headers) > 10000:
            return False, "Header list is empty, invalid, or exceeds 10000 entries."

        for position, header in enumerate(headers):
            try:
                validate_header(header)
            except ValueError as error:
                return False, str(error)
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

            if not is_hex(header["hash"], 64):
                return False, "Invalid header hash format."
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
                    "confirmations": len(chain.chain) - block.index if block_hash in known_block_hashes() else 0,
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
    
    register_explorer(app, chain, transaction_index, reorg_history)
    process_orphans()
    try_adopt_side_branches()
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

    advertised_url = args.advertised_url

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