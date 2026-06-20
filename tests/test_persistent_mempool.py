from node import create_app
from wallet import Wallet


def make_signed_transaction(sender_wallet, receiver_address, amount, nonce, fee):
    return sender_wallet.create_transaction(
        receiver_address=receiver_address,
        amount=amount,
        nonce=nonce,
        fee=fee,
    )


def test_mempool_survives_node_restart(tmp_path):
    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
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

    response = client.post(
        "/transactions",
        json={
            "transaction": transaction.to_dict(),
        },
    )

    assert response.status_code == 201

    mempool_file = node_data_dir / "mempool.json"

    assert mempool_file.exists()

    mempool_before_restart = client.get("/mempool").get_json()

    assert mempool_before_restart["size"] == 1
    assert mempool_before_restart["transactions"][0]["hash"] == transaction.transaction_hash()

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    mempool_after_restart = restarted_client.get("/mempool").get_json()

    assert mempool_after_restart["size"] == 1
    assert mempool_after_restart["transactions"][0]["hash"] == transaction.transaction_hash()

    status_after_restart = restarted_client.get("/status").get_json()

    assert status_after_restart["mempool_size"] == 1


def test_persisted_mempool_transaction_is_removed_when_mined_after_restart(tmp_path):
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

    response = client.post(
        "/transactions",
        json={
            "transaction": transaction.to_dict(),
        },
    )

    assert response.status_code == 201
    assert client.get("/mempool").get_json()["size"] == 1

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    assert restarted_client.get("/mempool").get_json()["size"] == 1

    mine_response = restarted_client.post(
        "/mine",
        json={
            "miner_address": miner.address,
        },
    )

    assert mine_response.status_code == 200

    mempool_after_mining = restarted_client.get("/mempool").get_json()

    assert mempool_after_mining["size"] == 0

    final_restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    final_restarted_client = final_restarted_app.test_client()

    final_mempool = final_restarted_client.get("/mempool").get_json()

    assert final_mempool["size"] == 0

    bob_balance = final_restarted_client.get(f"/balances/{bob.address}").get_json()
    miner_balance = final_restarted_client.get(f"/balances/{miner.address}").get_json()

    assert bob_balance["balance"] == 10
    assert miner_balance["balance"] == 52