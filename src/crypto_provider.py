from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)


class CryptoProvider:
    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )

        public_bytes = public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )

        return private_bytes.hex(), public_bytes.hex()

    @staticmethod
    def sign(private_key_hex: str, message: bytes) -> str:
        private_key = Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(private_key_hex)
        )

        signature = private_key.sign(message)
        return signature.hex()

    @staticmethod
    def verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        try:
            public_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(public_key_hex)
            )

            public_key.verify(
                bytes.fromhex(signature_hex),
                message,
            )

            return True

        except Exception:
            return False