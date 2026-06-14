from wallet import Wallet


def test_wallet_save_and_load_with_correct_password(tmp_path):
    wallet_path = tmp_path / "alice.json"

    original = Wallet.generate()
    original.save(str(wallet_path), password="strong-password")

    loaded = Wallet.load(str(wallet_path), password="strong-password")

    assert loaded.address == original.address
    assert loaded.public_key == original.public_key
    assert loaded.private_key == original.private_key


def test_wallet_load_rejects_wrong_password(tmp_path):
    wallet_path = tmp_path / "alice.json"

    wallet = Wallet.generate()
    wallet.save(str(wallet_path), password="correct-password")

    try:
        Wallet.load(str(wallet_path), password="wrong-password")
        assert False, "Wallet should not unlock with a wrong password."
    except ValueError:
        assert True


def test_wallet_metadata_does_not_expose_private_key(tmp_path):
    wallet_path = tmp_path / "alice.json"

    wallet = Wallet.generate()
    wallet.save(str(wallet_path), password="secret")

    metadata = Wallet.load_metadata(str(wallet_path))

    assert metadata["address"] == wallet.address
    assert metadata["public_key"] == wallet.public_key
    assert metadata["encrypted"] is True
    assert "private_key" not in metadata
