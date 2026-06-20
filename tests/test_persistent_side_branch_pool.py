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


def test_side_branch_pool_survives_node_restart(tmp_path):
    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    main_miner = Wallet.generate()
    side_miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": main_miner.address,
        },
    )

    source_chain = make_chain(tmp_path, "source_chain.json")
    source_chain.mine_pending_transactions(miner_address=side_miner.address)

    side_block = source_chain.chain[1]

    response = client.post(
        "/blocks",
        json={
            "block": side_block.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert response.status_code == 202

    data = response.get_json()

    assert data["side_branch_stored"] is True
    assert data["side_branch_pool_size"] == 1

    side_branch_file = node_data_dir / "side_branch_blocks.json"

    assert side_branch_file.exists()

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    side_branch_data = restarted_client.get("/side-branches").get_json()

    assert side_branch_data["size"] == 1
    assert side_branch_data["blocks"][0]["hash"] == side_block.hash
    assert side_block.hash in side_branch_data["tip_hashes"]

    lookup_data = restarted_client.get(f"/blocks/{side_block.hash}").get_json()

    assert lookup_data["found"] is True
    assert lookup_data["location"] == "side_branch_pool"
    assert lookup_data["block"]["hash"] == side_block.hash

    status = restarted_client.get("/status").get_json()

    assert status["side_branch_pool_size"] == 1


def test_persisted_side_branch_can_reorg_after_restart(tmp_path):
    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    main_miner = Wallet.generate()
    side_miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": main_miner.address,
        },
    )

    source_chain = make_chain(tmp_path, "source_chain.json")
    source_chain.mine_pending_transactions(miner_address=side_miner.address)
    source_chain.mine_pending_transactions(miner_address=side_miner.address)

    side_block_1 = source_chain.chain[1]
    side_block_2 = source_chain.chain[2]

    first_response = client.post(
        "/blocks",
        json={
            "block": side_block_1.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert first_response.status_code == 202
    assert first_response.get_json()["side_branch_stored"] is True
    assert client.get("/side-branches").get_json()["size"] == 1

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    assert restarted_client.get("/side-branches").get_json()["size"] == 1

    second_response = restarted_client.post(
        "/blocks",
        json={
            "block": side_block_2.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert second_response.status_code == 202

    second_data = second_response.get_json()

    assert second_data["side_branch_stored"] is True
    assert second_data["side_branch_result"]["adopted_count"] == 1
    assert second_data["side_branch_pool_size"] == 0

    status = restarted_client.get("/status").get_json()

    assert status["height"] == 2
    assert status["latest_hash"] == side_block_2.hash
    assert status["side_branch_pool_size"] == 0

    final_side_branches = restarted_client.get("/side-branches").get_json()

    assert final_side_branches["size"] == 0

    reloaded_after_reorg_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    reloaded_after_reorg_client = reloaded_after_reorg_app.test_client()

    final_status_after_restart = reloaded_after_reorg_client.get("/status").get_json()
    final_side_branches_after_restart = reloaded_after_reorg_client.get("/side-branches").get_json()

    assert final_status_after_restart["height"] == 2
    assert final_status_after_restart["latest_hash"] == side_block_2.hash
    assert final_status_after_restart["side_branch_pool_size"] == 0
    assert final_side_branches_after_restart["size"] == 0