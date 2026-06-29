import json

from blockchain import Blockchain


def test_blockchain_save_to_disk_creates_valid_json(tmp_path):
    chain_path = tmp_path / "chain.json"

    blockchain = Blockchain(storage_path=chain_path)
    blockchain.save_to_disk()

    assert chain_path.exists()

    with open(chain_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assert "chain" in data
    assert "mempool" in data
    assert "difficulty" in data
    assert isinstance(data["chain"], list)
    assert isinstance(data["mempool"], list)
    assert len(data["chain"]) >= 1


def test_blockchain_load_from_disk_handles_missing_file(tmp_path):
    chain_path = tmp_path / "missing_chain.json"

    blockchain = Blockchain(storage_path=chain_path)

    assert chain_path.exists()
    assert len(blockchain.chain) >= 1
    assert blockchain.is_valid()


def test_blockchain_load_from_disk_handles_invalid_json_gracefully(tmp_path):
    chain_path = tmp_path / "broken_chain.json"
    chain_path.write_text("{ broken json", encoding="utf-8")

    blockchain = Blockchain(storage_path=chain_path)

    assert len(blockchain.chain) >= 1
    assert blockchain.is_valid()

    with open(chain_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assert "chain" in data
    assert "mempool" in data
    assert isinstance(data["chain"], list)
    assert isinstance(data["mempool"], list)
    assert len(data["chain"]) >= 1