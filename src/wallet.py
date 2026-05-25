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