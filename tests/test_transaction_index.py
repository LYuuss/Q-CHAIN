from node import create_app
from wallet import Wallet


def make_signed_transaction(sender_wallet, receiver_address, amount, nonce, fee):
    return sender_wallet.create_transaction(
        receiver_address=receiver_address,
        amount=amount,
        nonce=nonce,
        fee=fee,
    )


def test_transaction_index_finds_confirmed_transaction_after_mining_and_restart(tmp_path):
    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    alice = Wallet.generate()
    bob = Wallet.generate()
    miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": alice.address,
        },
    )

    transaction = make_signed_transaction(
        sender_wallet=alice,
        receiver_address=bob.address,
        amount=10,
        nonce=1,
        fee=2,
    )

    tx_hash = transaction.transaction_hash()

    tx_response = client.post(
        "/transactions",
        json={
            "transaction": transaction.to_dict(),
        },
    )

    assert tx_response.status_code == 201

    mine_response = client.post(
        "/mine",
        json={
            "miner_address": miner.address,
        },
    )

    assert mine_response.status_code == 200

    lookup = client.get(f"/transactions/{tx_hash}")

    assert lookup.status_code == 200

    lookup_data = lookup.get_json()

    assert lookup_data["found"] is True
    assert lookup_data["transaction"]["hash"] == tx_hash
    assert lookup_data["transaction"]["location"] == "confirmed"
    assert lookup_data["transaction"]["sender"] == alice.address
    assert lookup_data["transaction"]["receiver"] == bob.address
    assert lookup_data["transaction"]["amount"] == 10
    assert lookup_data["transaction"]["fee"] == 2

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    restarted_lookup = restarted_client.get(f"/transactions/{tx_hash}")

    assert restarted_lookup.status_code == 200

    restarted_lookup_data = restarted_lookup.get_json()

    assert restarted_lookup_data["found"] is True
    assert restarted_lookup_data["transaction"]["hash"] == tx_hash
    assert restarted_lookup_data["transaction"]["location"] == "confirmed"

    status = restarted_client.get("/status").get_json()

    assert status["transaction_index_size"] >= 2


def test_transaction_index_finds_pending_transaction_in_mempool(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    alice = Wallet.generate()
    bob = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": alice.address,
        },
    )

    transaction = make_signed_transaction(
        sender_wallet=alice,
        receiver_address=bob.address,
        amount=10,
        nonce=1,
        fee=2,
    )

    tx_hash = transaction.transaction_hash()

    tx_response = client.post(
        "/transactions",
        json={
            "transaction": transaction.to_dict(),
        },
    )

    assert tx_response.status_code == 201

    lookup = client.get(f"/transactions/{tx_hash}")

    assert lookup.status_code == 200

    lookup_data = lookup.get_json()

    assert lookup_data["found"] is True
    assert lookup_data["transaction"]["hash"] == tx_hash
    assert lookup_data["transaction"]["location"] == "mempool"


def test_address_transaction_history_includes_confirmed_and_pending(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    alice = Wallet.generate()
    bob = Wallet.generate()
    charlie = Wallet.generate()
    miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": alice.address,
        },
    )

    confirmed_transaction = make_signed_transaction(
        sender_wallet=alice,
        receiver_address=bob.address,
        amount=10,
        nonce=1,
        fee=2,
    )

    confirmed_hash = confirmed_transaction.transaction_hash()

    tx_response = client.post(
        "/transactions",
        json={
            "transaction": confirmed_transaction.to_dict(),
        },
    )

    assert tx_response.status_code == 201

    client.post(
        "/mine",
        json={
            "miner_address": miner.address,
        },
    )

    pending_transaction = make_signed_transaction(
        sender_wallet=bob,
        receiver_address=charlie.address,
        amount=5,
        nonce=1,
        fee=1,
    )

    pending_hash = pending_transaction.transaction_hash()

    pending_response = client.post(
        "/transactions",
        json={
            "transaction": pending_transaction.to_dict(),
        },
    )

    assert pending_response.status_code == 201

    history_response = client.get(f"/addresses/{bob.address}/transactions")

    assert history_response.status_code == 200

    history = history_response.get_json()

    assert history["address"] == bob.address
    assert history["count"] == 2
    assert history["confirmed_count"] == 1
    assert history["pending_count"] == 1

    hashes = {
        tx["hash"]
        for tx in history["transactions"]
    }

    assert confirmed_hash in hashes
    assert pending_hash in hashes 