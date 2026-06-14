from node import create_app
from wallet import Wallet


def test_node_mine_status_and_balance(tmp_path):
    app = create_app(data_dir=tmp_path / "node1", advertised_url="http://node1:5000")
    client = app.test_client()
    miner = Wallet.generate()

    response = client.post("/mine", json={"miner_address": miner.address})

    assert response.status_code == 200

    data = response.get_json()
    assert data["mined"] is True
    assert data["miner_balance"] == 50
    assert data["new_height"] == 1

    status = client.get("/status").get_json()

    assert status["height"] == 1
    assert status["valid"] is True
    assert status["advertised_url"] == "http://node1:5000"

    balance = client.get(f"/balances/{miner.address}").get_json()

    assert balance["balance"] == 50


def test_node_accepts_signed_transaction_into_mempool(tmp_path):
    app = create_app(data_dir=tmp_path / "node1", advertised_url="http://node1:5000")
    client = app.test_client()

    alice = Wallet.generate()
    bob = Wallet.generate()

    client.post("/mine", json={"miner_address": alice.address})

    tx = alice.create_transaction(receiver_address=bob.address, amount=10, nonce=1, fee=2)

    response = client.post("/transactions", json={"transaction": tx.to_dict()})

    assert response.status_code == 201

    data = response.get_json()
    assert data["accepted"] is True
    assert data["mempool_size"] == 1

    mempool = client.get("/mempool").get_json()

    assert mempool["size"] == 1
    assert mempool["transactions"][0]["receiver"] == bob.address
