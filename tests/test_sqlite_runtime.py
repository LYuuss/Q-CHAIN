"""Mission 002-C4: explicit runtime activation and complete node checkpoints."""
from threading import Thread

import pytest

import node
import qchain
from blockchain import Blockchain
from runtime_storage import STATE_FILES
from sqlite_repository import SQLiteChainRepository, SQLiteStateRepository
from state_repository import NodeSnapshot
from storage_utils import StatePersistenceError
from wallet import Wallet


@pytest.fixture(autouse=True)
def easy_mining(monkeypatch):
    monkeypatch.setattr(node, "DEFAULT_DIFFICULTY", 1)
    monkeypatch.setattr(qchain, "DEFAULT_DIFFICULTY", 1)


def open_node(directory, backend="sqlite"):
    return node.create_app(directory, storage_backend=backend).test_client()


def test_backend_selection_refuses_mixed_state(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    open_node(legacy, "json")
    original = (legacy / "chain.json").read_bytes()
    with pytest.raises(StatePersistenceError, match="Legacy JSON"):
        open_node(legacy)
    assert (legacy / "chain.json").read_bytes() == original
    assert not (legacy / "state.db").exists()

    directory = tmp_path / "db"
    open_node(directory)
    repo = SQLiteStateRepository(directory / "state.db")
    before = repo.load_node()
    with pytest.raises(StatePersistenceError, match="SQLite state"):
        open_node(directory, "json")
    monkeypatch.setattr(qchain, "CHAIN_PATH", directory / "chain.json")
    with pytest.raises(StatePersistenceError, match="SQLite state"):
        qchain.load_chain()
    assert repo.load_node() == before
    assert not any((directory / name).exists() for name in STATE_FILES)

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "state.db-wal").touch()
    with pytest.raises(StatePersistenceError, match="Incomplete"):
        open_node(incomplete)
    assert not (incomplete / "state.db").exists()


def test_local_cli_sqlite_mine_send_restart_and_no_mirrors(tmp_path, monkeypatch):
    alice, bob = Wallet.generate(), Wallet.generate()
    monkeypatch.setattr(qchain, "CHAIN_PATH", tmp_path / "chain.json")
    monkeypatch.setattr(qchain, "load_wallet_metadata", lambda name: {"address": alice.address})
    monkeypatch.setattr(qchain, "load_wallet_for_signing", lambda name: alice)
    monkeypatch.setattr(qchain, "resolve_receiver_address", lambda name: bob.address)

    def cli(*args):
        monkeypatch.setattr("sys.argv", ["qchain.py", "--storage-backend", "sqlite", *args])
        assert qchain.main() == 0

    cli("mine", "alice")
    cli("send", "alice", "bob", "5")
    loaded = qchain.load_chain("sqlite")
    assert len(loaded.mempool) == 1 and loaded.get_balance(alice.address) == 50
    cli("mine", "alice")
    loaded = qchain.load_chain("sqlite")
    assert loaded.get_balance(bob.address) == 5 and not loaded.mempool
    assert not any((tmp_path / name).exists() for name in STATE_FILES)
    # Opening a chain-only database as a node rebuilds its derived explorer.
    client = open_node(tmp_path)
    assert client.get(f"/balances/{bob.address}").json["balance"] == 5
    client.post("/peers", json={"peer": "http://node2:5000"})
    with pytest.raises(StatePersistenceError, match="auxiliary"):
        qchain.load_chain("sqlite")


def test_chain_adapter_rejects_stale_owner(tmp_path):
    repo = SQLiteChainRepository(tmp_path / "state.db")
    first = Blockchain(difficulty=1, repository=repo)
    second = Blockchain(difficulty=1, repository=SQLiteChainRepository(repo.state.path))
    assert first.mine_pending_transactions(Wallet.generate().address)
    before = repo.state.load_node()
    with pytest.raises(StatePersistenceError, match="stale"):
        second.mine_pending_transactions(Wallet.generate().address)
    assert repo.state.load_node() == before


def test_json_sqlite_same_blocks_transactions_fork_reorg_restart(tmp_path):
    alice, bob, miner = Wallet.generate(), Wallet.generate(), Wallet.generate()
    main = Blockchain(difficulty=1, storage_path=tmp_path / "main.json")
    assert main.mine_pending_transactions(alice.address)
    tx = alice.create_transaction(bob.address, 10, 1, fee=2)
    other = Blockchain(difficulty=1, storage_path=tmp_path / "other.json")
    assert other.add_external_block(main.latest_block())[0]
    assert main.add_transaction(tx)
    assert main.mine_pending_transactions(miner.address)
    assert other.mine_pending_transactions(miner.address)
    assert other.mine_pending_transactions(miner.address)
    # A fork's child arrives before its parent; a subsequent parent reorg
    # attaches the orphan, restores a disconnected transaction and archives both.
    for backend in ("json", "sqlite"):
        directory = tmp_path / backend
        client = open_node(directory, backend)
        for block in main.chain[1:2]:
            assert client.post("/blocks", json={"block": block.to_dict()}).status_code == 201
        assert client.post("/transactions", json={"transaction": tx.to_dict()}).status_code == 201
        client = open_node(directory, backend)
        assert client.get("/mempool").json["size"] == 1
        assert client.post("/blocks", json={"block": main.chain[2].to_dict()}).status_code == 201
        assert client.get(f"/transactions/{tx.transaction_hash()}").json["transaction"]["confirmations"] == 1
        assert client.post("/blocks", json={"block": other.chain[3].to_dict()}).status_code == 202
        assert client.get("/orphans").json["size"] == 1
        client = open_node(directory, backend)
        assert client.get("/orphans").json["size"] == 1
        assert client.post("/blocks", json={"block": other.chain[2].to_dict()}).status_code == 202
        client = open_node(directory, backend)
        assert client.get("/status").json["latest_hash"] == other.latest_block().hash
        assert client.get("/orphans").json["size"] == 0
        assert client.get("/side-branches").json["size"] == 1
        assert client.get("/mempool").json["size"] == 1
        assert client.get(f"/balances/{bob.address}").json["balance"] == 0
        assert client.get("/reorgs").json["reorgs"][0]["old_tip"] == main.latest_block().hash
        assert client.get(f"/blocks/{main.latest_block().hash}").json["location"] == "side_branch_pool"
        if backend == "sqlite":
            revision, snapshot = SQLiteStateRepository(directory / "state.db").load_node()
            assert revision >= 5
            assert snapshot.side_branches == [main.latest_block().hash]
            assert snapshot.chain["mempool"] == [tx.to_dict()]
            assert not snapshot.orphans
            assert snapshot.reorgs[0]["revision"] == revision
            assert not any((directory / name).exists() for name in STATE_FILES)


@pytest.mark.parametrize("after_commit", [False, True])
def test_mining_commit_failure_quarantines_before_broadcast(tmp_path, monkeypatch, after_commit):
    directory = tmp_path / "node"
    client = open_node(directory)
    client.post("/peers", json={"peer": "http://node2:5000"})
    repo = SQLiteStateRepository(directory / "state.db")
    before = repo.load_node()
    real_commit = SQLiteStateRepository.commit_node

    def fail(self, *args, **kwargs):
        if after_commit:
            real_commit(self, *args, **kwargs)
        raise StatePersistenceError("injected failure")

    monkeypatch.setattr(SQLiteStateRepository, "commit_node", fail)
    monkeypatch.setattr(node, "post_json", lambda *a, **k: pytest.fail("broadcast before successful checkpoint"))
    response = client.post("/mine", json={"miner_address": Wallet.generate().address})
    assert response.status_code == 503
    assert client.get("/status").status_code == 503
    revision, actual = repo.load_node()
    if after_commit:
        assert revision == before[0] + 1
        assert len(actual.chain["chain"]) == 2
        assert len(actual.archive) == 2
    else:
        assert (revision, actual) == before

    monkeypatch.setattr(SQLiteStateRepository, "commit_node", real_commit)
    restarted = open_node(directory)
    assert restarted.get("/status").json["height"] == int(after_commit)


def test_broadcast_reads_committed_revision_and_callback(tmp_path, monkeypatch):
    client = open_node(tmp_path)
    repo = SQLiteStateRepository(tmp_path / "state.db")
    client.post("/peers", json={"peer": "http://node2:5000"})
    observed = []

    def open_callback_status():
        return client.application.test_client().get("/status").json

    def post(url, payload):
        revision, snapshot = repo.load_node()
        assert snapshot.chain["chain"][-1] == payload["block"]
        # A separate request thread must be able to acquire the state lock.
        statuses = []
        callback = Thread(target=lambda: statuses.append(open_callback_status()), daemon=True)
        callback.start()
        callback.join(timeout=5)
        assert not callback.is_alive(), "state lock held during network callback"
        assert statuses[0]["latest_hash"] == payload["block"]["hash"]
        observed.append(revision)
        return {"accepted": True}

    monkeypatch.setattr(node, "post_json", post)
    response = client.post("/mine", json={"miner_address": Wallet.generate().address})
    assert response.status_code == 200
    assert observed == [2]
    assert repo.load_node()[0] == 2
    assert client.get("/status").status_code == 200
    assert repo.load_node()[0] == 2


def test_reorg_checkpoint_failure_keeps_previous_complete_revision(tmp_path, monkeypatch):
    client = open_node(tmp_path / "node")
    assert client.post("/mine", json={"miner_address": Wallet.generate().address}).status_code == 200
    fork = Blockchain(difficulty=1, storage_path=tmp_path / "fork.json")
    miner = Wallet.generate()
    assert fork.mine_pending_transactions(miner.address)
    assert fork.mine_pending_transactions(miner.address)
    assert client.post("/blocks", json={"block": fork.chain[1].to_dict()}).status_code == 202
    repo = SQLiteStateRepository(tmp_path / "node" / "state.db")
    before = repo.load_node()
    real_write = SQLiteStateRepository._write_snapshot

    def fail(connection_self, connection, *args):
        real_write(connection_self, connection, *args)
        connection.execute("INSERT INTO active_chain VALUES (0, 'invalid')")

    monkeypatch.setattr(SQLiteStateRepository, "_write_snapshot", fail)
    assert client.post("/blocks", json={"block": fork.chain[2].to_dict()}).status_code == 503
    assert repo.load_node() == before
    assert client.get("/reorgs").status_code == 503
    monkeypatch.setattr(SQLiteStateRepository, "_write_snapshot", real_write)
    restarted = open_node(tmp_path / "node")
    assert restarted.get("/status").json["height"] == 1
    assert restarted.get("/side-branches").json["size"] == 1
    assert restarted.get("/reorgs").json["total"] == 0
    assert restarted.post("/blocks", json={"block": fork.chain[2].to_dict()}).status_code == 202
    assert restarted.get("/reorgs").json["total"] == 1


def test_imported_database_can_start_and_export_latest_state(tmp_path):
    from storage_migration import import_json, export_json

    legacy = tmp_path / "legacy"
    db_dir = tmp_path / "migrated"
    client = open_node(legacy, "json")
    miner = Wallet.generate()
    assert client.post("/mine", json={"miner_address": miner.address}).status_code == 200
    import_json(legacy, db_dir / "state.db")
    migrated = open_node(db_dir)
    assert migrated.get("/status").json["height"] == 1
    assert migrated.post("/mine", json={"miner_address": miner.address}).status_code == 200
    export_json(db_dir / "state.db", tmp_path / "recovered")
    restored = open_node(tmp_path / "recovered", "json")
    assert restored.get("/status").json["latest_hash"] == migrated.get("/status").json["latest_hash"]
    assert restored.get(f"/balances/{miner.address}").json["balance"] == 100
    assert client.get("/status").json["height"] == 1


def test_corrupt_database_does_not_initialize_or_fall_back(tmp_path):
    (tmp_path / "state.db").write_bytes(b"corrupt db")
    with pytest.raises(StatePersistenceError):
        open_node(tmp_path)
    assert (tmp_path / "state.db").read_bytes() == b"corrupt db"
    assert not (tmp_path / "chain.json").exists()


def test_unexpected_auxiliary_error_does_not_commit_staged_chain(tmp_path, monkeypatch):
    client = open_node(tmp_path)
    repo = SQLiteStateRepository(tmp_path / "state.db")
    before = repo.load_node()

    def fail(*args, **kwargs):
        raise ValueError("unexpected derived index failure")

    monkeypatch.setattr(node.TransactionIndex, "rebuild_from_chain", fail)
    response = client.post("/mine", json={"miner_address": Wallet.generate().address})
    assert response.status_code == 503
    assert client.get("/health").status_code == 503
    assert repo.load_node() == before
