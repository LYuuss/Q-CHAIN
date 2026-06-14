from blockchain import Blockchain
from config import DEFAULT_DIFFICULTY, DEFAULT_MINING_REWARD
from node import create_app
from wallet import Wallet


def make_chain(tmp_path, name="source_chain.json"):
    return Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(tmp_path / name),
        auto_load=False,
    )


def test_orphan_block_is_stored_when_parent_is_missing(tmp_path):
    source_chain = make_chain(tmp_path)
    miner = Wallet.generate()

    source_chain.mine_pending_transactions(miner_address=miner.address)
    source_chain.mine_pending_transactions(miner_address=miner.address)

    block_2 = source_chain.chain[2]

    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    response = client.post(
        "/blocks",
        json={
            "block": block_2.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert response.status_code == 202

    data = response.get_json()

    assert data["orphan_stored"] is True
    assert data["orphan_pool_size"] == 1

    orphan_data = client.get("/orphans").get_json()

    assert orphan_data["size"] == 1
    assert orphan_data["blocks"][0]["hash"] == block_2.hash

    status = client.get("/status").get_json()

    assert status["height"] == 0
    assert status["orphan_pool_size"] == 1


def test_orphan_block_is_attached_after_parent_arrives(tmp_path):
    source_chain = make_chain(tmp_path)
    miner = Wallet.generate()

    source_chain.mine_pending_transactions(miner_address=miner.address)
    source_chain.mine_pending_transactions(miner_address=miner.address)

    block_1 = source_chain.chain[1]
    block_2 = source_chain.chain[2]

    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    orphan_response = client.post(
        "/blocks",
        json={
            "block": block_2.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert orphan_response.status_code == 202
    assert client.get("/orphans").get_json()["size"] == 1

    parent_response = client.post(
        "/blocks",
        json={
            "block": block_1.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert parent_response.status_code == 201

    parent_data = parent_response.get_json()

    assert parent_data["accepted"] is True
    assert parent_data["orphan_result"]["attached_count"] == 1
    assert parent_data["orphan_pool_size"] == 0

    status = client.get("/status").get_json()

    assert status["height"] == 2
    assert status["latest_hash"] == block_2.hash
    assert status["orphan_pool_size"] == 0

    orphan_data = client.get("/orphans").get_json()

    assert orphan_data["size"] == 0