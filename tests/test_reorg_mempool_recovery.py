from block import Block
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


def make_chain_from_node_prefix(tmp_path, client, name, prefix_height):
    chain_data = client.get("/chain").get_json()["chain"]

    prefix_blocks = [
        Block.from_dict(block_data)
        for block_data in chain_data[: prefix_height + 1]
    ]

    source_chain = make_chain(tmp_path, name)
    replaced = source_chain.replace_chain_if_better(prefix_blocks)

    assert replaced is True

    return source_chain


def test_reorg_recovers_disconnected_transaction_to_mempool(tmp_path):
    node_data_dir = tmp_path / "node"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    alice = Wallet.generate()
    bob = Wallet.generate()
    main_miner = Wallet.generate()
    side_miner = Wallet.generate()

    # Block 1: common ancestor. Alice receives funds.
    funding_response = client.post(
        "/mine",
        json={
            "miner_address": alice.address,
        },
    )

    assert funding_response.status_code == 200

    # Alice creates a transaction to Bob.
    transaction = alice.create_transaction(
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
    assert client.get("/mempool").get_json()["size"] == 1

    # Block 2A: main chain includes Alice -> Bob.
    main_mine_response = client.post(
        "/mine",
        json={
            "miner_address": main_miner.address,
        },
    )

    assert main_mine_response.status_code == 200
    assert client.get("/mempool").get_json()["size"] == 0

    bob_balance_before_reorg = client.get(f"/balances/{bob.address}").get_json()

    assert bob_balance_before_reorg["balance"] == 10

    # Build a competing side chain from block 1.
    source_chain = make_chain_from_node_prefix(
        tmp_path=tmp_path,
        client=client,
        name="side_chain.json",
        prefix_height=1,
    )

    source_chain.mine_pending_transactions(miner_address=side_miner.address)
    source_chain.mine_pending_transactions(miner_address=side_miner.address)

    side_block_2 = source_chain.chain[2]
    side_block_3 = source_chain.chain[3]

    # First side block has same height as current main block.
    # It is stored as a side branch, but not adopted yet.
    first_side_response = client.post(
        "/blocks",
        json={
            "block": side_block_2.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert first_side_response.status_code == 202

    first_side_data = first_side_response.get_json()

    assert first_side_data["side_branch_stored"] is True
    assert first_side_data["side_branch_result"]["adopted_count"] == 0
    assert client.get("/mempool").get_json()["size"] == 0

    # Second side block makes the side branch heavier.
    # The node should reorg and recover Alice -> Bob into the mempool.
    second_side_response = client.post(
        "/blocks",
        json={
            "block": side_block_3.to_dict(),
            "source": "http://node2:5000",
        },
    )

    assert second_side_response.status_code == 202

    second_side_data = second_side_response.get_json()
    side_branch_result = second_side_data["side_branch_result"]

    assert side_branch_result["adopted_count"] == 1

    adopted_branch = side_branch_result["adopted_branches"][0]
    recovery_result = adopted_branch["mempool_recovery_result"]

    assert recovery_result["candidate_count"] == 1
    assert recovery_result["recovered_count"] == 1
    assert recovery_result["recovered_transactions"][0]["hash"] == tx_hash

    status_after_reorg = client.get("/status").get_json()

    assert status_after_reorg["height"] == 3
    assert status_after_reorg["latest_hash"] == side_block_3.hash

    bob_balance_after_reorg = client.get(f"/balances/{bob.address}").get_json()

    assert bob_balance_after_reorg["balance"] == 0

    mempool_after_reorg = client.get("/mempool").get_json()

    assert mempool_after_reorg["size"] == 1
    assert mempool_after_reorg["transactions"][0]["hash"] == tx_hash

    # Persistent mempool should keep the recovered transaction after restart.
    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    restarted_mempool = restarted_client.get("/mempool").get_json()

    assert restarted_mempool["size"] == 1
    assert restarted_mempool["transactions"][0]["hash"] == tx_hash