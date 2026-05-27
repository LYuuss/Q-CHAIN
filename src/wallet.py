import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from crypto_provider import CryptoProvider
from transaction import Transaction


KDF_ITERATIONS = 390_000


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
    def _derive_encryption_key(
        password: str,
        salt_hex: str,
        iterations: int = KDF_ITERATIONS,
    ) -> bytes:
        salt = bytes.fromhex(salt_hex)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )

        return base64.urlsafe_b64encode(
            kdf.derive(password.encode("utf-8"))
        )

    @staticmethod
    def _encrypt_private_key(private_key: str, password: str) -> dict[str, Any]:
        salt_hex = os.urandom(16).hex()
        key = Wallet._derive_encryption_key(password, salt_hex)
        fernet = Fernet(key)

        encrypted_private_key = fernet.encrypt(
            private_key.encode("utf-8")
        ).decode("utf-8")

        return {
            "private_key_encrypted": encrypted_private_key,
            "salt": salt_hex,
            "kdf": "PBKDF2HMAC-SHA256",
            "kdf_iterations": KDF_ITERATIONS,
        }

    @staticmethod
    def _decrypt_private_key(data: dict[str, Any], password: str) -> str:
        salt_hex = data["salt"]
        iterations = data.get("kdf_iterations", KDF_ITERATIONS)

        key = Wallet._derive_encryption_key(
            password=password,
            salt_hex=salt_hex,
            iterations=iterations,
        )

        fernet = Fernet(key)

        try:
            return fernet.decrypt(
                data["private_key_encrypted"].encode("utf-8")
            ).decode("utf-8")
        except InvalidToken as error:
            raise ValueError("Invalid wallet password.") from error

    @staticmethod
    def load_metadata(path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {
            "address": data["address"],
            "public_key": data["public_key"],
            "encrypted": data.get("encrypted", False),
            "version": data.get("version", 1),
        }

    @staticmethod
    def is_encrypted(path: str) -> bool:
        return Wallet.load_metadata(path)["encrypted"]

    @staticmethod
    def load(path: str, password: str | None = None) -> "Wallet":
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        encrypted = data.get("encrypted", False)

        if encrypted:
            if password is None:
                raise ValueError("Password required to unlock encrypted wallet.")

            private_key = Wallet._decrypt_private_key(data, password)
        else:
            # Backward compatibility with old plaintext wallet files.
            private_key = data["private_key"]

        wallet = Wallet(
            private_key=private_key,
            public_key=data["public_key"],
        )

        expected_address = data.get("address")

        if expected_address is not None and wallet.address != expected_address:
            raise ValueError("Wallet file is corrupted: address does not match keys.")

        return wallet

    def save(self, path: str, password: str) -> None:
        if not password:
            raise ValueError("Password cannot be empty.")

        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        encryption_data = self._encrypt_private_key(
            private_key=self.private_key,
            password=password,
        )

        data = {
            "version": 2,
            "encrypted": True,
            "address": self.address,
            "public_key": self.public_key,
            **encryption_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    @staticmethod
    def load_or_create(path: str, password: str) -> "Wallet":
        if os.path.exists(path):
            return Wallet.load(path, password=password)

        wallet = Wallet.generate()
        wallet.save(path, password=password)
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