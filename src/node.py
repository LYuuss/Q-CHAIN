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


def create_app(data_dir: Path) -> Flask:
    data_dir.mkdir(parents=True, exist_ok=True)

    chain_path = data_dir / "chain.json"
    peers_path = data_dir / "peers.json"

    chain = Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(chain_path),
        auto_load=True,
    )

    peers = load_peers(peers_path)

    app = Flask(__name__)

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
            "mempool_size": len(chain.mempool),
            "valid": chain.is_valid(),
            "peers": sorted(peers),
            "storage_path": str(chain_path),
        }

    def get_local_node_url() -> str:
        return request.host_url.rstrip("/")

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
                data = fetch_json(f"{peer}/chain")

                candidate_chain = [
                    Block.from_dict(block_data)
                    for block_data in data.get("chain", [])
                ]

                replaced = chain.replace_chain_if_better(candidate_chain)

                if replaced:
                    adopted = True
                    current_work = chain.calculate_cumulative_work()

            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, HttpJsonError) as error:
                errors.append(
                    {
                        "peer": peer,
                        "error": str(error),
                    }
                )

        return {
            "adopted_new_chain": adopted,
            "height": len(chain.chain) - 1,
            "latest_hash": chain.latest_block().hash,
            "cumulative_work": chain.calculate_cumulative_work(),
            "checked_peers": checked_peers,
            "peer_statuses": peer_statuses,
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
                "mempool_endpoint": "/mempool",
                "blocks_endpoint": "/blocks",
                "transactions_endpoint": "/transactions",
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
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                }
            ), 200
        
        broadcast_results = []
        sync_result = None

        if accepted:
            broadcast_results = broadcast_block(
                block=block,
                exclude_peer=source_url,
            )

            return jsonify(
                {
                    "accepted": True,
                    "message": message,
                    "sync_triggered": False,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                    "broadcast_results": broadcast_results,
                }
            ), 201

        if should_trigger_sync(message):
            sync_result = sync_with_peers()

            status_code = 202 if sync_result["adopted_new_chain"] else 409

            return jsonify(
                {
                    "accepted": False,
                    "message": message,
                    "sync_triggered": True,
                    "sync_result": sync_result,
                    "height": len(chain.chain) - 1,
                    "latest_hash": chain.latest_block().hash,
                    "cumulative_work": chain.calculate_cumulative_work(),
                }
            ), status_code

        return jsonify(
            {
                "accepted": False,
                "message": message,
                "sync_triggered": False,
                "height": len(chain.chain) - 1,
                "latest_hash": chain.latest_block().hash,
                "cumulative_work": chain.calculate_cumulative_work(),
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

        broadcast_results = broadcast_block(
            block=latest_block,
            exclude_peer=None,
        )

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
            }
        )

    @app.get("/peers")
    def get_peers():
        return jsonify(
            {
                "peers": sorted(peers),
                "count": len(peers),
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

        peers.add(peer_url)
        save_peers(peers_path, peers)

        return jsonify(
            {
                "added": True,
                "peer": peer_url,
                "peers": sorted(peers),
            }
        ), 201

    @app.post("/sync")
    def sync():
        return jsonify(sync_with_peers())

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

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.data_dir is None:
        data_dir = DATA_DIR / "nodes" / f"node_{args.port}"
    else:
        data_dir = Path(args.data_dir)

    app = create_app(data_dir)

    print(f"{PROJECT_NAME} node")
    print("-" * (len(PROJECT_NAME) + 5))
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Data directory: {data_dir}")
    print(f"Status: http://{args.host}:{args.port}/status")

    app.run(
        host=args.host,
        port=args.port,
        debug=False,
    )


if __name__ == "__main__":
    main()