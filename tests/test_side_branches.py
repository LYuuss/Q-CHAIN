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


def test_side_branch_block_is_stored_when_it_forks_from_main_chain(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
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

    side_block_1 = source_chain.chain[1]

    response = client.post(
        "/blocks",
        json={
            "block": side_block_1.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert response.status_code == 202

    data = response.get_json()

    assert data["side_branch_stored"] is True
    assert data["side_branch_pool_size"] == 1

    side_branches = client.get("/side-branches").get_json()

    assert side_branches["size"] == 1
    assert side_branches["blocks"][0]["hash"] == side_block_1.hash


def test_side_branch_is_adopted_when_it_becomes_heavier(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
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

    first_data = first_response.get_json()

    assert first_data["side_branch_stored"] is True
    assert first_data["side_branch_result"]["adopted_count"] == 0

    second_response = client.post(
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

    status = client.get("/status").get_json()

    assert status["height"] == 2
    assert status["latest_hash"] == side_block_2.hash
    assert status["side_branch_pool_size"] == 0

    side_branches = client.get("/side-branches").get_json()

    assert side_branches["size"] == 0