import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any

from crypto_provider import CryptoProvider


COINBASE_SENDER = "COINBASE"


@dataclass
class Transaction:
    sender: str
    receiver: str
    amount: int
    nonce: int
    fee: int = 0
    signature: Optional[str] = None

    @staticmethod
    def address_from_public_key(public_key: str) -> str:
        return hashlib.sha3_256(public_key.encode()).hexdigest()[:40]

    @staticmethod
    def create_coinbase(receiver: str, amount: int, block_index: int) -> "Transaction":
        return Transaction(
            sender=COINBASE_SENDER,
            receiver=receiver,
            amount=amount,
            nonce=block_index,
            fee=0,
            signature=None,
        )

    def is_coinbase(self) -> bool:
        return self.sender == COINBASE_SENDER

    def sender_address(self) -> Optional[str]:
        if self.is_coinbase():
            return None

        return self.address_from_public_key(self.sender)

    def payload(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "nonce": self.nonce,
            "fee": self.fee,
        }

    def payload_bytes(self) -> bytes:
        return json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def transaction_hash(self) -> str:
        """
        Unique transaction identifier.

        The signature is included, so two transactions with the same payload
        but different signatures would have different hashes.
        """
        return hashlib.sha3_256(
            json.dumps(
                self.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def sign(self, private_key_hex: str) -> None:
        if self.is_coinbase():
            raise ValueError("Coinbase transactions are not signed.")

        self.signature = CryptoProvider.sign(
            private_key_hex,
            self.payload_bytes(),
        )

    def verify(self) -> bool:
        if self.is_coinbase():
            return self.signature is None

        if self.signature is None:
            return False

        return CryptoProvider.verify(
            self.sender,
            self.payload_bytes(),
            self.signature,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = self.payload()
        data["signature"] = self.signature
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Transaction":
        return Transaction(
            sender=data["sender"],
            receiver=data["receiver"],
            amount=data["amount"],
            nonce=data["nonce"],
            fee=data.get("fee", 0),
            signature=data.get("signature"),
        )