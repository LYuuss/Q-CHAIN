from node import create_app
from wallet import Wallet


def test_headers_endpoint_returns_headers(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()
    miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": miner.address,
        },
    )

    response = client.get("/headers")

    assert response.status_code == 200

    data = response.get_json()

    assert "headers" in data
    assert len(data["headers"]) == 2

    genesis_header = data["headers"][0]
    mined_header = data["headers"][1]

    assert genesis_header["index"] == 0
    assert mined_header["index"] == 1
    assert mined_header["previous_hash"] == genesis_header["hash"]
    assert mined_header["hash"].startswith("0" * mined_header["difficulty"])


def test_get_block_by_hash_endpoint_returns_block(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()
    miner = Wallet.generate()

    client.post(
        "/mine",
        json={
            "miner_address": miner.address,
        },
    )

    headers_data = client.get("/headers").get_json()
    latest_hash = headers_data["headers"][-1]["hash"]

    response = client.get(f"/blocks/{latest_hash}")

    assert response.status_code == 200

    data = response.get_json()

    assert data["found"] is True
    assert data["block"]["hash"] == latest_hash
    assert data["block"]["header"]["index"] == 1


def test_get_block_by_hash_returns_404_for_unknown_hash(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    response = client.get("/blocks/" + "f" * 64)

    assert response.status_code == 404

    data = response.get_json()

    assert data["found"] is False