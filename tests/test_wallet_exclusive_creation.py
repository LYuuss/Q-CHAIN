"""Regression coverage for Mission 002-A (audit finding A04)."""

import json
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import qchain
import storage_utils
from wallet import Wallet, save_wallet_json


def test_save_is_exclusive_by_default(tmp_path):
    path = tmp_path / "alice.json"
    first, second = Wallet.generate(), Wallet.generate()
    first.save(str(path), "first-password")
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        second.save(str(path), "second-password")
    assert path.read_bytes() == original
    assert Wallet.load(str(path), "first-password").address == first.address
    with pytest.raises(ValueError, match="Invalid wallet password"):
        Wallet.load(str(path), "second-password")
    assert not list(tmp_path.glob("*.tmp"))


def test_json_helper_does_not_replace_existing_file(tmp_path):
    path = tmp_path / "wallet.json"
    save_wallet_json(path, {"version": 1})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_wallet_json(path, {"version": 2})
    assert path.read_bytes() == original


def test_load_or_create_loads_existing_wallet(tmp_path):
    path = str(tmp_path / "wallet.json")
    original = Wallet.load_or_create(path, "password")
    assert Wallet.load_or_create(path, "password").address == original.address


def test_load_or_create_never_replaces_corrupt_wallet(tmp_path):
    path = tmp_path / "wallet.json"
    path.write_text("{ broken", encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        Wallet.load_or_create(str(path), "password")
    assert path.read_bytes() == original


@pytest.mark.parametrize("entrypoint", ["load_or_create", "cli"])
def test_concurrent_creation_preserves_winning_keystore(tmp_path, monkeypatch, entrypoint):
    path = tmp_path / "alice.json"
    # Both callers must reach publication before either can win. The barrier
    # coordinates the actual atomic link, not a timing-dependent sleep.
    barrier = Barrier(2)
    real_link = storage_utils.os.link

    def synchronized_link(source, destination, *args, **kwargs):
        if destination == path:
            barrier.wait(timeout=10)
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(storage_utils.os, "link", synchronized_link)
    monkeypatch.setattr(qchain, "WALLETS_DIR", tmp_path)
    monkeypatch.setattr(qchain, "prompt_password", lambda *a, **kw: "password")

    def create():
        try:
            wallet = (
                Wallet.load_or_create(str(path), "password")
                if entrypoint == "load_or_create"
                else qchain.create_wallet("alice")
            )
            return wallet.address
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    winners = [address for address in results if address is not None]
    assert len(winners) == 1
    assert Wallet.load(str(path), "password").address == winners[0]
    assert json.loads(path.read_text())["address"] == winners[0]
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_exclusive_publication_leaves_no_wallet_or_temp(tmp_path, monkeypatch):
    path = tmp_path / "alice.json"

    def fail_link(*args, **kwargs):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(storage_utils.os, "link", fail_link)
    with pytest.raises(OSError, match="publication failure"):
        Wallet.generate().save(str(path), "password")
    assert not path.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_legacy_encryption_and_password_change_are_explicit_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(qchain, "WALLETS_DIR", tmp_path)
    path = tmp_path / "alice.json"
    wallet = Wallet.generate()
    # Synthetic legacy fixture only; no real key material leaves tmp_path.
    path.write_text(json.dumps({
        "address": wallet.address,
        "public_key": wallet.public_key,
        "private_key": wallet.private_key,
    }), encoding="utf-8")
    monkeypatch.setattr(qchain, "prompt_password", lambda *a, **kw: "old-password")
    qchain.command_wallet_encrypt(Namespace(name="alice"))
    assert Wallet.is_encrypted(str(path))
    assert Wallet.load(str(path), "old-password").address == wallet.address

    passwords = iter(["old-password", "new-password"])
    monkeypatch.setattr(qchain, "prompt_password", lambda *a, **kw: next(passwords))
    qchain.command_wallet_password(Namespace(name="alice"))
    assert Wallet.load(str(path), "new-password").address == wallet.address
    with pytest.raises(ValueError, match="Invalid wallet password"):
        Wallet.load(str(path), "old-password")
