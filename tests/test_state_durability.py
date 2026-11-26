"""Mission 002-B: state ownership, quarantine and restart recovery."""

import json
import os
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

import node
import storage_utils
from blockchain import Blockchain
from state_lock import StateDirectoryBusyError, state_directory_lock
from storage_utils import StatePersistenceError
from wallet import Wallet

SRC = Path(node.__file__).resolve().parent


def test_directory_lock_rejects_second_owner_and_releases(tmp_path):
    with state_directory_lock(tmp_path):
        with pytest.raises(StateDirectoryBusyError, match="already in use"):
            with state_directory_lock(tmp_path / "."):
                pytest.fail("second owner acquired lock")
        with state_directory_lock(tmp_path / "other"):
            pass
    assert (tmp_path / ".qchain-state.lock").exists()
    with state_directory_lock(tmp_path):
        pass


@pytest.mark.parametrize("entrypoint", [
    ["node.py", "--port", "0"],
    ["qchain.py", "status"],
])
def test_second_process_cannot_open_owned_directory(tmp_path, entrypoint):
    script, *args = entrypoint
    if script == "node.py":
        command = [sys.executable, str(SRC / script), "--data-dir", str(tmp_path), *args]
    else:
        command = [sys.executable, str(SRC / script), "--data-dir", str(tmp_path), *args]
    with state_directory_lock(tmp_path):
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert "already in use" in result.stderr
        assert not (tmp_path / "chain.json").exists()


def test_os_releases_lock_after_process_death(tmp_path):
    ready = tmp_path / "ready"
    code = (
        "import sys,time; from pathlib import Path; "
        "from state_lock import state_directory_lock\n"
        "with state_directory_lock(sys.argv[1]):\n"
        " Path(sys.argv[2]).touch()\n"
        " time.sleep(60)\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    process = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), str(ready)], env=env)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "child did not acquire lock"
        with pytest.raises(StateDirectoryBusyError):
            with state_directory_lock(tmp_path):
                pass
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    with state_directory_lock(tmp_path):
        pass


def test_failed_startup_releases_directory(tmp_path):
    (tmp_path / "chain.json").write_text("{ corrupt", encoding="utf-8")
    with pytest.raises(ValueError):
        with node.owned_app(tmp_path):
            pass
    with state_directory_lock(tmp_path):
        pass
    assert (tmp_path / "chain.json").read_text() == "{ corrupt"


def test_existing_chain_load_does_not_rewrite(tmp_path, monkeypatch):
    path = tmp_path / "chain.json"
    original = Blockchain(difficulty=1, storage_path=path)
    before = path.read_bytes()

    def unexpected_replace(*args):
        pytest.fail("existing chain load rewrote the snapshot")

    monkeypatch.setattr(storage_utils.os, "replace", unexpected_replace)
    loaded = Blockchain(difficulty=1, storage_path=path)
    assert loaded.latest_block().hash == original.latest_block().hash
    assert path.read_bytes() == before


def fail_target(monkeypatch, filename):
    replace = storage_utils.os.replace

    def fail(source, destination):
        if Path(destination).name == filename:
            raise OSError("simulated write failure")
        return replace(source, destination)

    monkeypatch.setattr(storage_utils.os, "replace", fail)


def test_failed_authoritative_mutation_quarantines_chain(tmp_path, monkeypatch):
    path = tmp_path / "chain.json"
    chain = Blockchain(difficulty=1, storage_path=path)
    alice, bob = Wallet.generate(), Wallet.generate()
    assert chain.mine_pending_transactions(alice.address)
    original = path.read_bytes()
    tx = alice.create_transaction(bob.address, 10, 1)
    with monkeypatch.context() as patch:
        fail_target(patch, "chain.json")
        with pytest.raises(StatePersistenceError):
            chain.add_transaction(tx)
        with pytest.raises(StatePersistenceError):
            chain.get_balance(alice.address)
        with pytest.raises(StatePersistenceError):
            chain.save_to_disk()
        with pytest.raises(StatePersistenceError):
            chain.mine_pending_transactions(alice.address)
    assert path.read_bytes() == original
    recovered = Blockchain(difficulty=1, storage_path=path)
    assert recovered.get_balance(alice.address) == 50
    assert recovered.get_next_nonce(alice.address) == 1
    assert not recovered.mempool


@pytest.mark.parametrize("target,committed", [
    ("chain.json", False),
    ("tx_index.json", True),
    ("mempool.json", True),
])
def test_node_quarantines_and_recovers_after_failed_mining_write(tmp_path, monkeypatch, target, committed):
    monkeypatch.setattr(node, "DEFAULT_DIFFICULTY", 1)
    miner = Wallet.generate()
    with node.owned_app(tmp_path) as app:
        client = app.test_client()
        with monkeypatch.context() as patch:
            fail_target(patch, target)
            response = client.post("/mine", json={"miner_address": miner.address})
            assert response.status_code == 503
            assert response.get_json()["status"] == "persistence_failed"
        # Even if the disk works again, a quarantined process cannot resume.
        before = (tmp_path / "chain.json").read_bytes()
        for endpoint in ["/health", "/status", "/chain", "/mempool", "/transactions"]:
            assert client.get(endpoint).status_code == 503
        assert client.post("/mine", json={"miner_address": miner.address}).status_code == 503
        assert (tmp_path / "chain.json").read_bytes() == before
    with node.owned_app(tmp_path) as app:
        client = app.test_client()
        assert client.get("/health").status_code == 200
        assert client.get("/status").get_json()["height"] == int(committed)
        balance = client.get(f"/balances/{miner.address}").get_json()
        assert balance["balance"] == (50 if committed else 0)
        tx_index = json.loads((tmp_path / "tx_index.json").read_text())["transactions"]
        assert len(tx_index) == int(committed)
        assert json.loads((tmp_path / "mempool.json").read_text())["transactions"] == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory fsync guarantee")
def test_directory_fsync_failure_has_uncertain_commit(tmp_path, monkeypatch):
    path = tmp_path / "chain.json"
    chain = Blockchain(difficulty=1, storage_path=path)
    miner = Wallet.generate()
    real_fsync = storage_utils.os.fsync

    def fail_directory(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("simulated directory fsync failure")
        return real_fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(storage_utils.os, "fsync", fail_directory)
        with pytest.raises(StatePersistenceError):
            chain.mine_pending_transactions(miner.address)
        with pytest.raises(StatePersistenceError):
            chain.latest_block()
    # Replacement happened before the failed fsync; do not claim rollback.
    recovered = Blockchain(difficulty=1, storage_path=path)
    assert recovered.get_balance(miner.address) == 50


def test_inflight_discovery_cannot_mutate_after_quarantine(tmp_path, monkeypatch):
    monkeypatch.setattr(node, "DEFAULT_DIFFICULTY", 1)
    entered, resume = Event(), Event()

    def fetch(*args, **kwargs):
        entered.set()
        assert resume.wait(timeout=10)
        return {"peers": ["http://new-peer:5000"]}

    monkeypatch.setattr(node, "fetch_json", fetch)
    with node.owned_app(tmp_path) as app:
        client = app.test_client()
        assert client.post("/peers", json={"peer": "http://peer:5000"}).status_code == 201
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: app.test_client().post("/peers/discover"))
            try:
                assert entered.wait(timeout=10)
                with monkeypatch.context() as patch:
                    fail_target(patch, "chain.json")
                    assert client.post("/mine", json={"miner_address": Wallet.generate().address}).status_code == 503
            finally:
                resume.set()
            assert future.result(timeout=10).status_code == 503
        assert json.loads((tmp_path / "peers.json").read_text())["peers"] == ["http://peer:5000"]


def test_closed_app_cannot_write_after_owner_released(tmp_path, monkeypatch):
    monkeypatch.setattr(node, "DEFAULT_DIFFICULTY", 1)
    with node.owned_app(tmp_path) as app:
        old_client = app.test_client()
    with node.owned_app(tmp_path) as replacement:
        assert old_client.get("/health").status_code == 503
        assert old_client.post("/mine", json={"miner_address": Wallet.generate().address}).status_code == 503
        assert replacement.test_client().get("/status").get_json()["height"] == 0
