import json

import pytest

from wallet import load_wallet_json, save_wallet_json


def test_save_wallet_json_creates_valid_json(tmp_path):
    wallet_path = tmp_path / "alice.json"

    data = {
        "version": 2,
        "encrypted": True,
        "address": "alice-address",
        "public_key": "alice-public-key",
        "private_key_encrypted": "encrypted-private-key",
        "salt": "00" * 16,
        "kdf": "PBKDF2HMAC-SHA256",
        "kdf_iterations": 390000,
    }

    save_wallet_json(wallet_path, data)

    assert wallet_path.exists()

    with open(wallet_path, "r", encoding="utf-8") as file:
        loaded = json.load(file)

    assert loaded == data


def test_load_wallet_json_reads_valid_wallet_file(tmp_path):
    wallet_path = tmp_path / "alice.json"

    data = {
        "version": 2,
        "encrypted": True,
        "address": "alice-address",
        "public_key": "alice-public-key",
        "private_key_encrypted": "encrypted-private-key",
        "salt": "00" * 16,
        "kdf": "PBKDF2HMAC-SHA256",
        "kdf_iterations": 390000,
    }

    save_wallet_json(wallet_path, data)

    loaded = load_wallet_json(wallet_path)

    assert loaded == data


def test_load_wallet_json_rejects_missing_file(tmp_path):
    wallet_path = tmp_path / "missing.json"

    with pytest.raises(ValueError):
        load_wallet_json(wallet_path)


def test_load_wallet_json_rejects_invalid_json(tmp_path):
    wallet_path = tmp_path / "broken.json"
    wallet_path.write_text("{ broken json", encoding="utf-8")

    with pytest.raises(ValueError):
        load_wallet_json(wallet_path)