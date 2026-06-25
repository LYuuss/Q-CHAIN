from block_store import BlockStore
from transaction_index import TransactionIndex


def test_block_store_creates_valid_json_file(tmp_path):
    path = tmp_path / "block_index.json"

    store = BlockStore(path)

    assert path.exists()

    data = path.read_text(encoding="utf-8")

    assert '"blocks"' in data


def test_transaction_index_creates_valid_json_file(tmp_path):
    path = tmp_path / "tx_index.json"

    index = TransactionIndex(path)

    assert path.exists()

    data = path.read_text(encoding="utf-8")

    assert '"transactions"' in data