import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import node
from block import Block
from blockchain import Blockchain
from wallet import Wallet


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(node, "DEFAULT_DIFFICULTY", 1)
    app = node.create_app(tmp_path / "node", "http://node1:5000")
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("endpoint", ["/transactions", "/blocks", "/mine", "/peers", "/peers/discover", "/sync"])
@pytest.mark.parametrize("payload", [[], [1], "text", 12, True, None])
def test_non_object_request_is_a_client_error(client, endpoint, payload):
    response = client.post(endpoint, data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json
    assert client.get("/status").json["height"] == 0


@pytest.mark.parametrize("field,value", [
    ("amount", True), ("amount", 1.5), ("amount", float("nan")),
    ("fee", "1"), ("fee", -1), ("nonce", False), ("nonce", 1.0),
    ("receiver", []), ("receiver", "z" * 40), ("signature", "00"),
])
def test_malformed_transaction_cannot_change_state(client, field, value):
    alice, bob = Wallet.generate(), Wallet.generate()
    client.post("/mine", json={"miner_address": alice.address})
    tx = alice.create_transaction(bob.address, 10, 1).to_dict()
    tx[field] = value
    response = client.post("/transactions", json={"transaction": tx})
    assert response.status_code == 400
    assert client.get("/mempool").json["size"] == 0
    assert client.get(f"/balances/{alice.address}").json["balance"] == 50


@pytest.mark.parametrize("limit", [-1, True, 1.2, "1", 1000])
def test_invalid_mining_limit_is_rejected(client, limit):
    response = client.post("/mine", json={"miner_address": Wallet.generate().address, "max_transactions": limit})
    assert response.status_code == 400
    assert client.get("/status").json["height"] == 0


@pytest.mark.parametrize("url", [
    "ftp://node2", "http://user:secret@node2:5000", "http://node2:bad",
    "http://node2:0", "http://node2:65536", "http://node2:5000/path",
    "http://node2?url=other", "http://node2#fragment", "http://[bad",
])
def test_bad_peer_url_is_rejected(client, url):
    assert client.post("/peers", json={"peer": url}).status_code == 400
    assert client.get("/peers").json["count"] == 0


def test_broadcast_source_cannot_poison_peer_set(client):
    for source in ["not-a-url", [], "http://node1:5000", "http://unknown:5000"]:
        assert client.post("/transactions", json={"source": source, "transaction": {}}).status_code == 400
    assert client.get("/peers").json["peers"] == []


def test_peer_normalization_and_self_without_advertisement(tmp_path):
    assert node.normalize_peer_url("HTTP://EXAMPLE.COM:80/") == "http://example.com"
    assert node.normalize_peer_url("http://[::1]:5000/") == "http://[::1]:5000"
    local = node.create_app(tmp_path / "self").test_client()
    assert local.post("/peers", json={"peer": "http://localhost"}).status_code == 400


def test_discovery_isolates_bad_peer_responses(client, monkeypatch):
    client.post("/peers", json={"peer": "http://node2:5000"})
    monkeypatch.setattr(node, "fetch_json", lambda *a, **kw: ["not-an-object"])
    response = client.post("/peers/discover")
    assert response.status_code == 200
    assert response.json["failed_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("difficulty", -1), ("difficulty", 0), ("difficulty", 9),
    ("difficulty", True), ("index", 1.0), ("nonce", False),
    ("timestamp", float("nan")), ("timestamp", float("inf")),
])
def test_malformed_block_header_cannot_enter_any_pool(client, field, value):
    genesis = client.get("/chain").json["chain"][0]
    block = copy.deepcopy(genesis)
    block["header"][field] = value
    response = client.post("/blocks", json={"block": block})
    assert response.status_code == 400
    assert client.get("/orphans").json["size"] == 0
    assert client.get("/side-branches").json["size"] == 0


def test_future_block_and_wrong_genesis_are_invalid(client, tmp_path):
    chain = Blockchain(difficulty=1, storage_path=tmp_path / "source.json")
    chain.mine_pending_transactions(Wallet.generate().address)
    block = chain.latest_block()
    block.header.timestamp = time.time() + 3600
    block.mine()
    assert client.post("/blocks", json={"block": block.to_dict()}).status_code == 400
    chain.chain[0].header.timestamp = 1.0
    chain.chain[0].mine()
    assert not chain.is_valid()


@pytest.mark.parametrize("mirror", [None, {"transactions": []}, {"transactions": [{"bad": "entry"}]}])
def test_authoritative_mempool_survives_missing_or_stale_mirror(client, tmp_path, mirror):
    alice, bob = Wallet.generate(), Wallet.generate()
    client.post("/mine", json={"miner_address": alice.address})
    tx = alice.create_transaction(bob.address, 10, 1)
    client.post("/transactions", json={"transaction": tx.to_dict()})
    path = tmp_path / "node" / "mempool.json"
    if mirror is None:
        path.unlink()
    else:
        path.write_text(json.dumps(mirror))
    restarted = node.create_app(tmp_path / "node").test_client()
    assert restarted.get("/mempool").json["transactions"][0]["hash"] == tx.transaction_hash()


def test_reorg_preserves_pending_nonce_dependencies_and_losing_branch(client, tmp_path):
    alice, bob, miner = Wallet.generate(), Wallet.generate(), Wallet.generate()
    client.post("/mine", json={"miner_address": alice.address})
    prefix = [Block.from_dict(b) for b in client.get("/chain").json["chain"]]
    fork = Blockchain(difficulty=1, storage_path=tmp_path / "fork.json")
    assert fork.replace_chain_if_better(prefix)
    tx1 = alice.create_transaction(bob.address, 10, 1, fee=1)
    tx2 = alice.create_transaction(bob.address, 10, 2, fee=2)
    assert client.post("/transactions", json={"transaction": tx1.to_dict()}).status_code == 201
    client.post("/mine", json={"miner_address": miner.address})
    old_chain = [Block.from_dict(b) for b in client.get("/chain").json["chain"]]
    assert client.post("/transactions", json={"transaction": tx2.to_dict()}).status_code == 201
    for _ in range(2):
        fork.mine_pending_transactions(miner.address)
        client.post("/blocks", json={"block": fork.latest_block().to_dict()})
    pending = client.get("/mempool").json["transactions"]
    assert [tx["hash"] for tx in pending] == [tx1.transaction_hash(), tx2.transaction_hash()]
    assert client.get(f"/transactions/{tx1.transaction_hash()}").json["transaction"]["confirmations"] == 0
    history = client.get("/reorgs").json
    assert history["total"] == 1
    assert history["reorgs"][0]["recovered_transaction_count"] == 1
    assert history["reorgs"][0]["common_ancestor_height"] == 1

    restarted = node.create_app(tmp_path / "node").test_client()
    assert restarted.get("/reorgs").json["total"] == 1
    assert restarted.get("/mempool").json["size"] == 2
    # Extend the previously disconnected chain. Its parent must remain attachable.
    old = Blockchain(difficulty=1, storage_path=tmp_path / "old.json")
    assert old.replace_chain_if_better(old_chain)
    for _ in range(2):
        old.mine_pending_transactions(miner.address)
        restarted.post("/blocks", json={"block": old.latest_block().to_dict()})
    assert restarted.get("/status").json["latest_hash"] == old.latest_block().hash
    assert restarted.get("/reorgs").json["total"] == 2
    assert restarted.get("/mempool").json["transactions"][0]["hash"] == tx2.transaction_hash()


def test_explorer_pagination_and_confirmations(client):
    miner = Wallet.generate()
    for _ in range(3):
        assert client.post("/mine", json={"miner_address": miner.address}).status_code == 200
    page = client.get("/blocks?limit=2&offset=1").json
    assert page["total"] == 4 and page["count"] == 2 and page["has_more"]
    assert [block["index"] for block in page["blocks"]] == [2, 1]
    block = client.get("/blocks/height/1").json
    assert block["confirmations"] == 3
    assert client.get(f"/blocks/{block['block']['hash']}").json["confirmations"] == 3
    transactions = client.get("/transactions?limit=1").json
    assert transactions["total"] == 3 and transactions["count"] == 1
    history = client.get(f"/addresses/{miner.address}/transactions?limit=1&offset=1").json
    assert history["total"] == 3 and history["count"] == 1
    assert client.get("/blocks/height/99").status_code == 404
    for query in ["limit=0", "limit=101", "offset=-1", "limit=x"]:
        assert client.get(f"/blocks?{query}").status_code == 400


def test_concurrent_mining_serializes_state(client, tmp_path):
    miner = Wallet.generate()
    def mine(_):
        with client.application.test_client() as local:
            return local.post("/mine", json={"miner_address": miner.address}).status_code
    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(mine, range(4))) == [200] * 4
    restarted = node.create_app(tmp_path / "node").test_client()
    assert restarted.get("/status").json["height"] == 4
    assert restarted.get("/status").json["valid"]
    assert restarted.get(f"/balances/{miner.address}").json["balance"] == 200


def test_invalid_download_is_not_cached(client, tmp_path, monkeypatch):
    source = Blockchain(difficulty=1, storage_path=tmp_path / "remote.json")
    source.mine_pending_transactions(Wallet.generate().address)
    headers = [{**block.to_dict()["header"], "hash": block.hash} for block in source.chain]
    body = source.latest_block().to_dict()
    body["header"]["nonce"] += 1
    def fetch(url, **kwargs):
        if url.endswith("/status"):
            return {"height": 1, "cumulative_work": 32, "valid": True, "genesis_hash": source.chain[0].hash}
        if url.endswith("/headers"):
            return {"headers": headers}
        return {"block": body}
    monkeypatch.setattr(node, "fetch_json", fetch)
    client.post("/peers", json={"peer": "http://node2:5000"})
    response = client.post("/sync")
    assert response.status_code == 200
    assert not response.json["adopted_new_chain"]
    assert client.get(f"/blocks/{source.latest_block().hash}").status_code == 404


def test_request_size_limit(client):
    response = client.post("/transactions", data=b"x" * (2 * 1024 * 1024 + 1), content_type="application/json")
    assert response.status_code == 413 and "error" in response.json
