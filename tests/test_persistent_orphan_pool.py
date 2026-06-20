from blockchain import Blockchain
from config import DEFAULT_DIFFICULTY, DEFAULT_MINING_REWARD
from node import create_app
from wallet import Wallet


def make_chain(tmp_path, name):
    return Blockchain(
        difficulty=DEFAULT_DIFFICULTY,
        mining_reward=DEFAULT_MINING_REWARD,
        storage_path=str(tmp_path / name),
        auto_load=False,
    )


def test_orphan_pool_survives_node_restart(tmp_path):
    source_chain = make_chain(tmp_path, "source_chain.json")
    miner = Wallet.generate()

    source_chain.mine_pending_transactions(miner_address=miner.address)
    source_chain.mine_pending_transactions(miner_address=miner.address)

    orphan_block = source_chain.chain[2]

    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    response = client.post(
        "/blocks",
        json={
            "block": orphan_block.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert response.status_code == 202
    assert response.get_json()["orphan_stored"] is True

    orphan_file = node_data_dir / "orphan_blocks.json"

    assert orphan_file.exists()

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    orphan_data = restarted_client.get("/orphans").get_json()

    assert orphan_data["size"] == 1
    assert orphan_data["blocks"][0]["hash"] == orphan_block.hash

    lookup_data = restarted_client.get(f"/blocks/{orphan_block.hash}").get_json()

    assert lookup_data["found"] is True
    assert lookup_data["location"] == "orphan_pool"
    assert lookup_data["block"]["hash"] == orphan_block.hash

    status = restarted_client.get("/status").get_json()

    assert status["orphan_pool_size"] == 1


def test_persisted_orphan_attaches_after_restart_when_parent_arrives(tmp_path):
    source_chain = make_chain(tmp_path, "source_chain.json")
    miner = Wallet.generate()

    source_chain.mine_pending_transactions(miner_address=miner.address)
    source_chain.mine_pending_transactions(miner_address=miner.address)

    parent_block = source_chain.chain[1]
    orphan_block = source_chain.chain[2]

    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    orphan_response = client.post(
        "/blocks",
        json={
            "block": orphan_block.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert orphan_response.status_code == 202
    assert client.get("/orphans").get_json()["size"] == 1

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    assert restarted_client.get("/orphans").get_json()["size"] == 1

    parent_response = restarted_client.post(
        "/blocks",
        json={
            "block": parent_block.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert parent_response.status_code == 201

    parent_data = parent_response.get_json()

    assert parent_data["accepted"] is True
    assert parent_data["orphan_result"]["attached_count"] == 1
    assert parent_data["orphan_pool_size"] == 0

    status = restarted_client.get("/status").get_json()

    assert status["height"] == 2
    assert status["latest_hash"] == orphan_block.hash
    assert status["orphan_pool_size"] == 0

    final_orphans = restarted_client.get("/orphans").get_json()

    assert final_orphans["size"] == 0