from blockchain import Blockchain
from wallet import Wallet


def make_chain(tmp_path, name="chain.json", difficulty=1, reward=50):
    return Blockchain(
        difficulty=difficulty,
        mining_reward=reward,
        storage_path=str(tmp_path / name),
        auto_load=False,
    )


def test_mining_reward_is_added_to_miner_balance(tmp_path):
    chain = make_chain(tmp_path)
    miner = Wallet.generate()

    mined = chain.mine_pending_transactions(miner_address=miner.address)

    assert mined is True
    assert chain.get_balance(miner.address) == 50
    assert len(chain.chain) == 2
    assert chain.is_valid()


def test_transaction_amount_fee_and_miner_reward(tmp_path):
    chain = make_chain(tmp_path)

    alice = Wallet.generate()
    bob = Wallet.generate()
    miner = Wallet.generate()

    chain.mine_pending_transactions(miner_address=alice.address)
    assert chain.get_balance(alice.address) == 50

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=2)

    assert chain.add_transaction(tx) is True
    assert len(chain.mempool) == 1

    chain.mine_pending_transactions(miner_address=miner.address)

    assert chain.get_balance(alice.address) == 38
    assert chain.get_balance(bob.address) == 10
    assert chain.get_balance(miner.address) == 52
    assert len(chain.mempool) == 0
    assert chain.is_valid()


def test_rejects_transaction_with_invalid_signature(tmp_path):
    chain = make_chain(tmp_path)

    alice = Wallet.generate()
    bob = Wallet.generate()

    chain.mine_pending_transactions(miner_address=alice.address)

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=1)
    tx.amount = 999

    assert chain.add_transaction(tx) is False
    assert len(chain.mempool) == 0


def test_rejects_transaction_with_insufficient_balance(tmp_path):
    chain = make_chain(tmp_path)

    alice = Wallet.generate()
    bob = Wallet.generate()

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=1)

    assert chain.add_transaction(tx) is False
    assert len(chain.mempool) == 0


def test_rejects_replayed_nonce_in_mempool(tmp_path):
    chain = make_chain(tmp_path)

    alice = Wallet.generate()
    bob = Wallet.generate()

    chain.mine_pending_transactions(miner_address=alice.address)

    tx1 = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=1)
    tx2 = alice.create_transaction(receiver_address=bob.address, amount=5, nonce=1, fee=1)

    assert chain.add_transaction(tx1) is True
    assert chain.add_transaction(tx2) is False
    assert len(chain.mempool) == 1


def test_invalid_chain_is_detected_after_tampering(tmp_path):
    chain = make_chain(tmp_path)

    alice = Wallet.generate()
    bob = Wallet.generate()
    miner = Wallet.generate()

    chain.mine_pending_transactions(miner_address=alice.address)

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=2)
    assert chain.add_transaction(tx) is True

    chain.mine_pending_transactions(miner_address=miner.address)
    assert chain.is_valid()

    chain.chain[1].transactions[0]["amount"] = 999

    assert not chain.is_valid()


def test_replace_chain_if_better_adopts_heavier_valid_chain(tmp_path):
    short_chain = make_chain(tmp_path, name="short.json")
    long_chain = make_chain(tmp_path, name="long.json")

    miner = Wallet.generate()

    short_chain.mine_pending_transactions(miner_address=miner.address)

    long_chain.mine_pending_transactions(miner_address=miner.address)
    long_chain.mine_pending_transactions(miner_address=miner.address)

    assert long_chain.calculate_cumulative_work() > short_chain.calculate_cumulative_work()

    replaced = short_chain.replace_chain_if_better(long_chain.chain)

    assert replaced is True
    assert short_chain.latest_block().hash == long_chain.latest_block().hash
    assert short_chain.calculate_cumulative_work() == long_chain.calculate_cumulative_work()
