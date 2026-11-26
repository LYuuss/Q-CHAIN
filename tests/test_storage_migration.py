"""Mission 002-C3: offline conversion and non-destructive recovery."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import storage_migration as migration
from blockchain import Blockchain
from sqlite_repository import SQLiteStateRepository
from state_lock import state_directory_lock, StateDirectoryBusyError
from storage_utils import write_state_json, StatePersistenceError
from wallet import Wallet


def fixture_state(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    chain = Blockchain(difficulty=1, storage_path=source / "chain.json")
    alice, bob = Wallet.generate(), Wallet.generate()
    assert chain.mine_pending_transactions(alice.address)
    assert chain.add_transaction(alice.create_transaction(bob.address, 10, 1))
    return source, chain, alice, bob


def source_bytes(source):
    return {p.name: p.read_bytes() for p in source.iterdir()
            if p.is_file() and p.name != ".qchain-state.lock"}


def test_import_export_preserves_state_and_source(tmp_path):
    source, chain, alice, bob = fixture_state(tmp_path)
    other = Blockchain(difficulty=1, storage_path=tmp_path / "other.json")
    assert other.mine_pending_transactions(bob.address)
    fork = other.latest_block()
    write_state_json(source / "side_branch_blocks.json", {"blocks": {fork.hash: fork.to_dict()}})
    write_state_json(source / "reorg_history.json", {"reorgs": [
        {"old_tip": fork.hash, "new_tip": chain.latest_block().hash, "reason": "test"}]})
    write_state_json(source / "peers.json", {"peers": ["http://node2:5000"]})
    # The stale mirror must not supersede authoritative pending transactions.
    write_state_json(source / "mempool.json", {"transactions": []})
    (source / "wallets").mkdir()
    before = source_bytes(source)
    target = tmp_path / "sqlite" / "state.db"
    report = migration.import_json(source, target)
    assert report["height"] == 1 and report["mempool"] == 1
    assert report["side_branches"] == 1 and report["reorgs"] == 1
    assert report["source_sha256"]["chain.json"] == migration._checksum(source / "chain.json")
    assert source_bytes(source) == before
    revision, snapshot = SQLiteStateRepository(target).load_node()
    assert revision == 0 and snapshot.chain == chain.snapshot()
    assert snapshot.side_branches == [fork.hash]
    # Advance the DB so exporting old JSON would be observably incorrect.
    chain = Blockchain(difficulty=1, storage_path=tmp_path / "advanced.json")
    assert chain.replace_chain_if_better(migration.replay(snapshot.chain).chain)
    for pending in snapshot.chain["mempool"]:
        from transaction import Transaction
        assert chain.add_transaction(Transaction.from_dict(pending))
    assert chain.mine_pending_transactions(bob.address)
    snapshot.chain = chain.snapshot()
    snapshot.archive.append(chain.latest_block().to_dict())
    SQLiteStateRepository(target).commit_node(snapshot, expected_revision=0)
    destination = tmp_path / "restored"
    result = migration.export_json(target, destination)
    assert result["revision"] == 1 and result["height"] == 2
    loaded = Blockchain(difficulty=1, storage_path=destination / "chain.json")
    assert loaded.snapshot() == chain.snapshot()
    assert loaded.get_state() == chain.get_state()
    assert loaded.calculate_cumulative_work() == chain.calculate_cumulative_work()
    assert not (destination / "wallets").exists()
    assert json.loads((destination / "migration-report.json").read_text()) == result
    assert len(json.loads((destination / "tx_index.json").read_text())["transactions"]) == 3


def test_legacy_mempool_mirror_only_when_missing(tmp_path):
    source, chain, _, _ = fixture_state(tmp_path)
    data = chain.snapshot()
    pending = data.pop("mempool")
    write_state_json(source / "chain.json", data)
    write_state_json(source / "mempool.json", {"transactions": pending + [{"bad": True}]})
    before = source_bytes(source)
    target = tmp_path / "sqlite" / "state.db"
    report = migration.import_json(source, target)
    assert report["mempool"] == 1
    assert any("legacy mempool" in warning.lower() for warning in report["warnings"])
    assert any("revalidated" in warning for warning in report["warnings"])
    assert source_bytes(source) == before
    assert SQLiteStateRepository(target).load_node()[1].chain == chain.snapshot()


@pytest.mark.parametrize("kind", ["corrupt_chain", "invalid_pending", "missing_chain"])
def test_invalid_authoritative_state_never_published(tmp_path, kind):
    source, chain, _, _ = fixture_state(tmp_path)
    path = source / "chain.json"
    if kind == "corrupt_chain":
        path.write_text("{ broken")
    elif kind == "invalid_pending":
        data = chain.snapshot()
        data["mempool"].append({"bad": True})
        write_state_json(path, data)
    else:
        path.unlink()
    before = source_bytes(source)
    target = tmp_path / "sqlite" / "state.db"
    with pytest.raises((ValueError, StatePersistenceError)):
        migration.import_json(source, target)
    assert not target.exists()
    assert source_bytes(source) == before


def test_auxiliary_reconciliation_report(tmp_path):
    source, chain, _, _ = fixture_state(tmp_path)
    active = chain.latest_block()
    write_state_json(source / "orphan_blocks.json", {"blocks": {
        active.hash: active.to_dict(), "bad": {"bad": True}}})
    write_state_json(source / "peers.json", {"peers": ["invalid", "http://NODE2:80/"]})
    write_state_json(source / "reorg_history.json", {"reorgs": [{"old_tip": "unknown"}]})
    target = tmp_path / "sqlite" / "state.db"
    report = migration.import_json(source, target)
    assert report["orphans"] == 0 and report["reorgs"] == 0 and report["peers"] == 1
    assert any("reconciled" in warning for warning in report["warnings"])
    assert any("skipped" in warning for warning in report["warnings"])
    assert SQLiteStateRepository(target).load_node()[1].peers == ["http://node2"]


def test_existing_destinations_and_sidecars_never_overwritten(tmp_path):
    source, _, _, _ = fixture_state(tmp_path)
    target = tmp_path / "sqlite" / "state.db"
    target.parent.mkdir()
    sidecar = Path(str(target) + "-wal")
    sidecar.write_bytes(b"old sidecar")
    with pytest.raises(FileExistsError):
        migration.import_json(source, target)
    assert sidecar.read_bytes() == b"old sidecar"
    sidecar.unlink()
    migration.import_json(source, target)
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        migration.import_json(source, target)
    assert target.read_bytes() == before
    destination = tmp_path / "restored"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        migration.export_json(target, destination)
    assert not list(destination.iterdir())


def test_active_source_owner_refused(tmp_path):
    source, _, _, _ = fixture_state(tmp_path)
    target = tmp_path / "sqlite" / "state.db"
    with state_directory_lock(source):
        with pytest.raises(StateDirectoryBusyError):
            migration.import_json(source, target)
    assert not target.exists()


def test_import_failure_before_publication_preserves_source(tmp_path, monkeypatch):
    source, _, _, _ = fixture_state(tmp_path)
    before = source_bytes(source)
    target = tmp_path / "sqlite" / "state.db"

    def fail(*args):
        raise ValueError("injected verification failure")

    monkeypatch.setattr(migration, "_verify", fail)
    with pytest.raises(ValueError, match="injected"):
        migration.import_json(source, target)
    assert not target.exists()
    assert source_bytes(source) == before
    assert not list(target.parent.glob(".qchain-import-*"))


def test_export_failure_before_publication(tmp_path, monkeypatch):
    source, _, _, _ = fixture_state(tmp_path)
    target = tmp_path / "sqlite" / "state.db"
    migration.import_json(source, target)
    before = SQLiteStateRepository(target).load_node()

    def fail(*args):
        raise StatePersistenceError("injected export failure")

    monkeypatch.setattr(migration, "_write_legacy", fail)
    destination = tmp_path / "restored"
    with pytest.raises(StatePersistenceError):
        migration.export_json(target, destination)
    assert not destination.exists()
    assert SQLiteStateRepository(target).load_node() == before


def test_killed_import_does_not_publish(tmp_path):
    source, _, _, _ = fixture_state(tmp_path)
    before = source_bytes(source)
    target = tmp_path / "sqlite" / "state.db"
    ready = tmp_path / "ready"
    src = Path(migration.__file__).resolve().parent
    code = """
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import storage_migration as m
original=m._verify
def pause(*args):
    original(*args)
    Path(sys.argv[4]).touch()
    time.sleep(60)
m._verify=pause
m.import_json(sys.argv[2],sys.argv[3])
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(src), str(source), str(target), str(ready)])
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "child did not reach verified staging"
        assert not target.exists()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    assert source_bytes(source) == before
    assert not target.exists()
    # Staging left by the dead process cannot be activated; retry uses a new directory.
    assert migration.import_json(source, target)["revision"] == 0
