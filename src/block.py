import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Block:
    index: int
    previous_hash: str
    transactions: List[Dict[str, Any]]
    difficulty: int
    timestamp: float = field(default_factory=time.time)
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        block_data = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": self.transactions,
            "difficulty": self.difficulty,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

        encoded = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha3_256(encoded).hexdigest()

    def mine(self) -> None:
        target = "0" * self.difficulty

        while True:
            self.hash = self.compute_hash()

            if self.hash.startswith(target):
                break

            self.nonce += 1
            