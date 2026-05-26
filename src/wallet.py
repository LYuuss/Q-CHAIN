import json
import os
from datetime import datetime, timezone

from crypto_provider import CryptoProvider
from transaction import Transaction


class Wallet:
    def __init__(self, private_key: str, public_key: str):
        self.private_key = private_key
        self.public_key = public_key
        self.address = Transaction.address_from_public_key(public_key)

    @staticmethod
    def generate() -> "Wallet":
        private_key, public_key = CryptoProvider.generate_keypair()
        return Wallet(private_key, public_key)

    @staticmethod
    def load(path: str) -> "Wallet":
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        wallet = Wallet(
            private_key=data["private_key"],
            public_key=data["public_key"],
        )

        expected_address = data.get("address")

        if expected_address is not None and wallet.address != expected_address:
            raise ValueError("Wallet file is corrupted: address does not match keys.")

        return wallet

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        data = {
            "address": self.address,
            "public_key": self.public_key,
            "private_key": self.private_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    @staticmethod
    def load_or_create(path: str) -> "Wallet":
        if os.path.exists(path):
            return Wallet.load(path)

        wallet = Wallet.generate()
        wallet.save(path)
        return wallet

    def create_transaction(
        self,
        receiver_address: str,
        amount: int,
        nonce: int,
        fee: int = 1,
    ) -> Transaction:
        transaction = Transaction(
            sender=self.public_key,
            receiver=receiver_address,
            amount=amount,
            nonce=nonce,
            fee=fee,
        )

        transaction.sign(self.private_key)
        return transaction