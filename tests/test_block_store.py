from block_store import BlockStore
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


def test_block_store_persists_blocks_by_hash(tmp_path):
    chain = make_chain(tmp_path, "chain.json")
    miner = Wallet.generate()

    chain.mine_pending_transactions(miner_address=miner.address)

    block_store_path = tmp_path / "block_index.json"

    store = BlockStore(block_store_path)
    store.put_many(chain.chain)

    reloaded_store = BlockStore(block_store_path)

    assert reloaded_store.count() == len(chain.chain)

    latest_block = chain.latest_block()
    loaded_block = reloaded_store.get(latest_block.hash)

    assert loaded_block is not None
    assert loaded_block.hash == latest_block.hash
    assert loaded_block.index == latest_block.index


def test_node_block_lookup_uses_persistent_block_store_for_orphan_after_restart(tmp_path):
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

    lookup_before_restart = client.get(f"/blocks/{orphan_block.hash}").get_json()

    assert lookup_before_restart["found"] is True
    assert lookup_before_restart["location"] == "orphan_pool"
    assert lookup_before_restart["block"]["hash"] == orphan_block.hash

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    lookup_after_restart = restarted_client.get(f"/blocks/{orphan_block.hash}").get_json()

    assert lookup_after_restart["found"] is True
    assert lookup_after_restart["location"] == "block_store"
    assert lookup_after_restart["block"]["hash"] == orphan_block.hash

    status_after_restart = restarted_client.get("/status").get_json()

    assert status_after_restart["height"] == 0
    assert status_after_restart["block_store_size"] >= 2