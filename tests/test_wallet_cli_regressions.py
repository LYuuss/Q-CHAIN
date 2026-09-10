import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import qchain
import storage_utils
from wallet import Wallet


def test_mismatched_private_key_is_rejected(tmp_path):
    alice, bob = Wallet.generate(), Wallet.generate()
    path = tmp_path / "wallet.json"
    path.write_text(json.dumps({"private_key": bob.private_key, "public_key": alice.public_key, "address": alice.address}))
    with pytest.raises(ValueError, match="do not match"):
        Wallet.load(str(path))


@pytest.mark.parametrize("name", ["../other", "/tmp/private", "a/b", "", "a.b", "a" * 65])
def test_wallet_names_cannot_escape_directory(name):
    with pytest.raises(ValueError):
        qchain.wallet_path(name)


def test_backup_import_and_password_change(tmp_path, monkeypatch):
    monkeypatch.setattr(qchain, "WALLETS_DIR", tmp_path / "wallets")
    wallet = Wallet.generate()
    wallet.save(str(qchain.wallet_path("alice")), "old-password")
    backup = tmp_path / "alice-backup.json"
    qchain.command_wallet_backup(Namespace(name="alice", destination=backup))
    original = backup.read_bytes()
    with pytest.raises(FileExistsError):
        qchain.command_wallet_backup(Namespace(name="alice", destination=backup))
    assert backup.read_bytes() == original
    assert wallet.private_key not in backup.read_text()
    if os.name == "posix":
        assert backup.stat().st_mode & 0o777 == 0o600
    monkeypatch.setattr(qchain, "prompt_password", lambda *a, **kw: "old-password")
    qchain.command_wallet_import(Namespace(source=backup, name="restored"))
    assert Wallet.load(str(qchain.wallet_path("restored")), "old-password").address == wallet.address
    with pytest.raises(ValueError, match="already exists"):
        qchain.command_wallet_import(Namespace(source=backup, name="restored"))
    passwords = iter(["old-password", "new-password"])
    monkeypatch.setattr(qchain, "prompt_password", lambda *a, **kw: next(passwords))
    qchain.command_wallet_password(Namespace(name="restored"))
    with pytest.raises(ValueError, match="Invalid wallet password"):
        Wallet.load(str(qchain.wallet_path("restored")), "old-password")
    assert Wallet.load(str(qchain.wallet_path("restored")), "new-password").address == wallet.address


def test_failed_atomic_write_preserves_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    storage_utils.atomic_write_json(path, {"height": 7})
    original = path.read_bytes()
    def fail_replace(*args):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(storage_utils.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        storage_utils.atomic_write_json(path, {"height": 8})
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_reports_failure_with_nonzero_exit_and_isolated_data(tmp_path):
    script = Path(qchain.__file__)
    result = subprocess.run([sys.executable, str(script), "--data-dir", str(tmp_path), "balance", "missing"], capture_output=True, text=True)
    assert result.returncode == 1 and "does not exist" in result.stderr
    assert (tmp_path / "chain.json").exists()


def test_invalid_encrypted_wallet_kdf_is_bounded(tmp_path):
    wallet = Wallet.generate()
    path = tmp_path / "wallet.json"
    wallet.save(str(path), "password")
    data = json.loads(path.read_text())
    data["kdf_iterations"] = 10**12
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="iteration count"):
        Wallet.load(str(path), "password")
