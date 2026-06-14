from transaction import Transaction
from wallet import Wallet


def test_signed_transaction_is_valid():
    alice = Wallet.generate()
    bob = Wallet.generate()

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=2)

    assert tx.verify()
    assert tx.sender_address() == alice.address
    assert tx.receiver == bob.address
    assert tx.amount == 10
    assert tx.fee == 2
    assert tx.nonce == 1


def test_tampered_transaction_signature_is_invalid():
    alice = Wallet.generate()
    bob = Wallet.generate()

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=2)
    assert tx.verify()

    tx.amount = 999

    assert not tx.verify()


def test_coinbase_transaction_is_valid_without_signature():
    miner = Wallet.generate()

    tx = Transaction.create_coinbase(receiver=miner.address, amount=50, block_index=1)

    assert tx.is_coinbase()
    assert tx.verify()
    assert tx.signature is None
