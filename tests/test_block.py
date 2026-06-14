from block import Block, compute_merkle_root


def test_block_mining_respects_difficulty():
    block = Block(index=1, previous_hash="0" * 64, transactions=[], difficulty=2)
    block.mine()

    assert block.hash.startswith("00")
    assert block.hash == block.compute_hash()


def test_merkle_root_changes_when_transaction_changes():
    tx_a = [{"sender": "alice", "receiver": "bob", "amount": 10, "nonce": 1, "fee": 2, "signature": "sig"}]
    tx_b = [{"sender": "alice", "receiver": "bob", "amount": 11, "nonce": 1, "fee": 2, "signature": "sig"}]

    assert compute_merkle_root(tx_a) != compute_merkle_root(tx_b)


def test_block_rejects_tampered_transactions_on_load():
    transactions = [{"sender": "alice", "receiver": "bob", "amount": 10, "nonce": 1, "fee": 2, "signature": "sig"}]

    block = Block(index=1, previous_hash="0" * 64, transactions=transactions, difficulty=1)
    block.mine()

    block_data = block.to_dict()
    block_data["transactions"][0]["amount"] = 999

    try:
        Block.from_dict(block_data)
        assert False, "Tampered block should not load successfully."
    except ValueError:
        assert True
