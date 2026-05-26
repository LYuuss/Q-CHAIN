import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha3_256_hex(data: str) -> str:
    return hashlib.sha3_256(data.encode()).hexdigest()


def compute_transaction_hash(transaction: dict[str, Any]) -> str:
    return sha3_256_hex(canonical_json(transaction))


def compute_merkle_root(transactions: list[dict[str, Any]]) -> str:
    if len(transactions) == 0:
        return hashlib.sha3_256(b"").hexdigest()

    layer = [
        compute_transaction_hash(transaction)
        for transaction in transactions
    ]

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        next_layer = []

        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1]
            parent_hash = sha3_256_hex(left + right)
            next_layer.append(parent_hash)

        layer = next_layer

    return layer[0]


@dataclass
class BlockHeader:
    index: int
    previous_hash: str
    merkle_root: str
    difficulty: int
    timestamp: float
    nonce: int = 0

    def compute_hash(self) -> str:
        header_data = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "difficulty": self.difficulty,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

        return sha3_256_hex(canonical_json(header_data))


class Block:
    def __init__(
        self,
        index: int,
        previous_hash: str,
        transactions: list[dict[str, Any]],
        difficulty: int,
        timestamp: float | None = None,
        nonce: int = 0,
        hash: str = "",
    ):
        self.transactions = transactions

        self.header = BlockHeader(
            index=index,
            previous_hash=previous_hash,
            merkle_root=compute_merkle_root(transactions),
            difficulty=difficulty,
            timestamp=timestamp if timestamp is not None else time.time(),
            nonce=nonce,
        )

        self.hash = hash

    @property
    def index(self) -> int:
        return self.header.index

    @property
    def previous_hash(self) -> str:
        return self.header.previous_hash

    @property
    def merkle_root(self) -> str:
        return self.header.merkle_root

    @property
    def difficulty(self) -> int:
        return self.header.difficulty

    @property
    def timestamp(self) -> float:
        return self.header.timestamp

    @property
    def nonce(self) -> int:
        return self.header.nonce

    @nonce.setter
    def nonce(self, value: int) -> None:
        self.header.nonce = value

    def compute_hash(self) -> str:
        return self.header.compute_hash()

    def verify_merkle_root(self) -> bool:
        return self.merkle_root == compute_merkle_root(self.transactions)

    def mine(self) -> None:
        if not self.verify_merkle_root():
            self.header.merkle_root = compute_merkle_root(self.transactions)

        target = "0" * self.difficulty

        while True:
            self.hash = self.compute_hash()

            if self.hash.startswith(target):
                break

            self.nonce += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": {
                "index": self.index,
                "previous_hash": self.previous_hash,
                "merkle_root": self.merkle_root,
                "difficulty": self.difficulty,
                "timestamp": self.timestamp,
                "nonce": self.nonce,
            },
            "hash": self.hash,
            "transactions": self.transactions,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Block":
        header = data["header"]

        block = Block(
            index=header["index"],
            previous_hash=header["previous_hash"],
            transactions=data["transactions"],
            difficulty=header["difficulty"],
            timestamp=header["timestamp"],
            nonce=header["nonce"],
            hash=data["hash"],
        )

        expected_merkle_root = header["merkle_root"]

        if block.merkle_root != expected_merkle_root:
            raise ValueError("Invalid block: Merkle root does not match transactions.")

        return block