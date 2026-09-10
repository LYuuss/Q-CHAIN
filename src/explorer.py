"""Paginated views over the node's current, validated chain."""

from flask import jsonify, request
from werkzeug.exceptions import BadRequest


def paginate(items):
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError as error:
        raise BadRequest("limit and offset must be integers.") from error
    if not 1 <= limit <= 100 or offset < 0:
        raise BadRequest("limit must be 1–100 and offset must be nonnegative.")
    page = items[offset:offset + limit]
    return page, {
        "count": len(page), "total": len(items), "limit": limit,
        "offset": offset, "has_more": offset + len(page) < len(items),
    }


def with_confirmations(transaction, chain):
    record = dict(transaction)
    height = record.get("block_index")
    record["confirmations"] = len(chain.chain) - height if height is not None else 0
    return record


def register_explorer(app, chain, transaction_index, reorg_history):
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "height": len(chain.chain) - 1})

    @app.get("/blocks")
    def blocks():
        rows = [
            {"hash": block.hash, **block.to_dict()["header"],
             "transaction_count": len(block.transactions),
             "confirmations": len(chain.chain) - block.index}
            for block in reversed(chain.chain)
        ]
        page, metadata = paginate(rows)
        return jsonify({**metadata, "blocks": page})

    @app.get("/blocks/height/<int:height>")
    def block_by_height(height):
        if height >= len(chain.chain):
            return jsonify({"found": False, "error": "Block height not found."}), 404
        return jsonify({
            "found": True, "location": "main_chain",
            "confirmations": len(chain.chain) - height,
            "block": chain.chain[height].to_dict(),
        })

    @app.get("/transactions")
    def transactions():
        records = [with_confirmations(tx, chain) for tx in transaction_index.transactions.values()]
        records.sort(key=lambda tx: (tx["block_index"], tx["position"]), reverse=True)
        pending = []
        for tx in chain.mempool:
            pending.append({
                "hash": tx.transaction_hash(), "location": "mempool",
                "block_index": None, "block_hash": None, "confirmations": 0,
                "sender": tx.sender_address(), "receiver": tx.receiver,
                "amount": tx.amount, "fee": tx.fee, "nonce": tx.nonce,
                "is_coinbase": False, "transaction": tx.to_dict(),
            })
        page, metadata = paginate(pending + records)
        return jsonify({**metadata, "transactions": page})

    @app.get("/reorgs")
    def reorgs():
        page, metadata = paginate(list(reversed(reorg_history)))
        return jsonify({**metadata, "reorgs": page})
