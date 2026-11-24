"""Mission 002-C2: SQLite snapshots, parity, rollback and schema gates."""

import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from copy import deepcopy
from pathlib import Path

import pytest

from blockchain import Blockchain
from sqlite_repository import SQLiteChainRepository, SQLiteStateRepository
from state_repository import NodeSnapshot
from storage_utils import StatePersistenceError
from wallet import Wallet


def make_snapshot(tmp_path):
    chain = Blockchain(difficulty=1, storage_path=tmp_path / "chain.json")
    alice, bob = Wallet.generate(), Wallet.generate()
    assert chain.mine_pending_transactions(alice.address)
    assert chain.add_transaction(alice.create_transaction(bob.address, 10, 1))
    return chain, alice, bob, NodeSnapshot(chain.snapshot())


def test_chain_adapter_roundtrip_and_parity(tmp_path):
    path = tmp_path / "state.db"
    repository = SQLiteChainRepository(path)
    sql = Blockchain(difficulty=1, repository=repository)
    legacy = Blockchain(difficulty=1, storage_path=tmp_path / "chain.json")
    alice, bob = Wallet.generate(), Wallet.generate()
    assert sql.mine_pending_transactions(alice.address)
    assert legacy.add_external_block(sql.latest_block())[0]
    tx = alice.create_transaction(bob.address, 10, 1)
    assert sql.add_transaction(tx)
    assert legacy.add_transaction(tx)
    reopened = Blockchain(difficulty=1, repository=repository)
    assert reopened.snapshot() == legacy.snapshot()
    assert reopened.get_state() == legacy.get_state()
    assert reopened.mine_pending_transactions(bob.address)
    assert legacy.add_external_block(reopened.latest_block())[0]
    assert reopened.snapshot() == legacy.snapshot()
    assert reopened.get_state() == legacy.get_state()
    assert reopened.calculate_cumulative_work() == legacy.calculate_cumulative_work()
    assert reopened.get_balance(bob.address) == 61


def test_full_node_snapshot_roundtrip(tmp_path):
    chain, alice, bob, snapshot = make_snapshot(tmp_path)
    other = Blockchain(difficulty=1, storage_path=tmp_path / "other.json")
    assert other.mine_pending_transactions(bob.address)
    fork = other.latest_block()
    snapshot.archive = [fork.to_dict()]
    snapshot.side_branches = [fork.hash]
    snapshot.peers = ["http://node2:5000"]
    snapshot.reorgs = [{"old_tip": fork.hash, "new_tip": chain.latest_block().hash,
                        "reason": "test", "timestamp": 10}]
    repository = SQLiteStateRepository(tmp_path / "state.db")
    assert repository.commit_node(snapshot, expected_revision=None) == 0
    revision, loaded = SQLiteStateRepository(repository.path).load_node()
    assert revision == 0
    assert loaded.chain == snapshot.chain
    assert loaded.side_branches == snapshot.side_branches
    assert loaded.peers == snapshot.peers
    assert loaded.reorgs == snapshot.reorgs
    assert {block["hash"] for block in loaded.archive} == {
        fork.hash, *[block.hash for block in chain.chain]}
    assert repository.commit_node(loaded, expected_revision=0) == 1
    with closing(sqlite3.connect(repository.path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT revision FROM reorg_history").fetchone() == (None,)
    with pytest.raises(StatePersistenceError, match="auxiliary"):
        SQLiteChainRepository(repository.path).load()


def test_no_overwrite_or_stale_revision(tmp_path):
    _, _, _, snapshot = make_snapshot(tmp_path)
    repository = SQLiteStateRepository(tmp_path / "state.db")
    repository.commit_node(snapshot, expected_revision=None)
    snapshot.peers = ["http://node2:5000"]
    repository.commit_node(snapshot, expected_revision=0)
    snapshot.peers = ["http://node3:5000"]
    with pytest.raises(StatePersistenceError, match="stale"):
        repository.commit_node(snapshot, expected_revision=0)
    with pytest.raises(StatePersistenceError):
        repository.commit_node(snapshot, expected_revision=None)
    revision, loaded = repository.load_node()
    assert revision == 1
    assert loaded.peers == ["http://node2:5000"]


def test_sql_failure_rolls_back_whole_snapshot(tmp_path, monkeypatch):
    chain, _, bob, snapshot = make_snapshot(tmp_path)
    repository = SQLiteStateRepository(tmp_path / "state.db")
    repository.commit_node(snapshot, expected_revision=None)
    before = repository.load_node()
    assert chain.mine_pending_transactions(bob.address)
    candidate = NodeSnapshot(chain.snapshot(), peers=["http://node2:5000"])
    real_write = repository._write_snapshot

    def fail_after_writes(connection, *args):
        real_write(connection, *args)
        # Real SQL failure after the candidate rows have been replaced.
        connection.execute("INSERT INTO active_chain VALUES (0, 'invalid')")

    monkeypatch.setattr(repository, "_write_snapshot", fail_after_writes)
    with pytest.raises(StatePersistenceError):
        repository.commit_node(candidate, expected_revision=0)
    assert SQLiteStateRepository(repository.path).load_node() == before


@pytest.mark.parametrize("kind", ["unknown_version", "empty", "corrupt"])
def test_invalid_database_never_reinitialized(tmp_path, kind):
    _, _, _, snapshot = make_snapshot(tmp_path)
    path = tmp_path / "state.db"
    repository = SQLiteStateRepository(path)
    if kind == "unknown_version":
        repository.commit_node(snapshot, expected_revision=None)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("PRAGMA user_version=99")
    elif kind == "empty":
        path.touch()
    else:
        path.write_bytes(b"invalid database")
    before = path.read_bytes()
    with pytest.raises(StatePersistenceError):
        repository.load_node()
    with pytest.raises(StatePersistenceError):
        repository.commit_node(snapshot, expected_revision=None)
    assert path.read_bytes() == before


def test_missing_read_does_not_create_db(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(StatePersistenceError):
        SQLiteStateRepository(path).load_node()
    assert not path.exists()


@pytest.mark.parametrize("kind", ["active_in_pool", "duplicate_pending", "missing_event_tip"])
def test_invalid_snapshot_rejected_without_revision_change(tmp_path, kind):
    _, _, _, snapshot = make_snapshot(tmp_path)
    repository = SQLiteStateRepository(tmp_path / "state.db")
    repository.commit_node(snapshot, expected_revision=None)
    before = repository.load_node()
    if kind == "active_in_pool":
        snapshot.orphans = [snapshot.chain["chain"][0]["hash"]]
    elif kind == "duplicate_pending":
        snapshot.chain["mempool"] *= 2
    else:
        snapshot.reorgs = [{"old_tip": "f" * 64, "new_tip": snapshot.chain["chain"][-1]["hash"]}]
    with pytest.raises(StatePersistenceError):
        repository.commit_node(snapshot, expected_revision=0)
    assert repository.load_node() == before


def test_process_death_before_commit_recovers_previous_revision(tmp_path):
    chain, _, bob, snapshot = make_snapshot(tmp_path)
    repository = SQLiteStateRepository(tmp_path / "state.db")
    repository.commit_node(snapshot, expected_revision=None)
    before = repository.load_node()
    assert chain.mine_pending_transactions(bob.address)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(chain.snapshot()))
    ready = tmp_path / "ready"
    src = Path(__file__).resolve().parents[1] / "src"
    code = """
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sqlite_repository import SQLiteStateRepository
from state_repository import NodeSnapshot
repo = SQLiteStateRepository(sys.argv[2])
original = repo._write_snapshot
def pause(connection, *args):
    original(connection, *args)
    Path(sys.argv[4]).touch()
    time.sleep(60)
repo._write_snapshot = pause
repo.commit_node(NodeSnapshot(json.loads(Path(sys.argv[3]).read_text())), expected_revision=0)
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(src), str(repository.path),
                                str(candidate), str(ready)])
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "child did not reach uncommitted SQL writes"
        assert repository.load_node() == before
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    assert SQLiteStateRepository(repository.path).load_node() == before


def test_runtime_schema_matches_reference(tmp_path):
    _, _, _, snapshot = make_snapshot(tmp_path)
    repository = SQLiteStateRepository(tmp_path / "state.db")
    repository.commit_node(snapshot, expected_revision=None)
    reference = Path(__file__).resolve().parents[1] / "docs" / "storage-schema-v1.sql"
    with closing(sqlite3.connect(":memory:")) as expected, closing(sqlite3.connect(repository.path)) as actual:
        expected.executescript(reference.read_text())
        query = "SELECT name, type, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
        assert actual.execute(query).fetchall() == expected.execute(query).fetchall()
