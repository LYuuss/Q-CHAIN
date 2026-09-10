import json
from pathlib import Path
from typing import Any

from block import Block
from transaction import Transaction
from storage_utils import atomic_write_json, read_json_or_default

class TransactionIndex:
    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        self.transactions: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.storage_path.exists():
            self.save()
            return

        data = read_json_or_default(
            self.storage_path,
            default={
                "transactions": {},
            },
        )

        self.transactions = data.get("transactions", {})

    def save(self) -> None:
        data = {
            "transactions": dict(sorted(self.transactions.items()))
        }

        atomic_write_json(self.storage_path, data)

    def rebuild_from_chain(self, chain: list[Block], save: bool = True) -> None:
        self.transactions = {}

        for block in chain:
            for position, tx_data in enumerate(block.transactions):
                transaction = Transaction.from_dict(tx_data)
                tx_hash = transaction.transaction_hash()

                self.transactions[tx_hash] = {
                    "hash": tx_hash,
                    "location": "confirmed",
                    "block_hash": block.hash,
                    "block_index": block.index,
                    "position": position,
                    "sender": transaction.sender_address(),
                    "receiver": transaction.receiver,
                    "amount": transaction.amount,
                    "fee": transaction.fee,
                    "nonce": transaction.nonce,
                    "is_coinbase": transaction.is_coinbase(),
                    "transaction": transaction.to_dict(),
                }

        if save:
            self.save()

    def get(self, tx_hash: str) -> dict[str, Any] | None:
        return self.transactions.get(tx_hash)

    def has(self, tx_hash: str) -> bool:
        return tx_hash in self.transactions

    def count(self) -> int:
        return len(self.transactions)

    def find_by_address(self, address: str) -> list[dict[str, Any]]:
        results = []

        for tx in self.transactions.values():
            if tx["sender"] == address or tx["receiver"] == address:
                results.append(tx)

        results.sort(
            key=lambda item: (
                item["block_index"],
                item["position"],
            )
        )

        return results