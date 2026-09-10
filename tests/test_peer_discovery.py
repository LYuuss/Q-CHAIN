import pytest

import node
from node import create_app


def test_node_rejects_self_peer(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node1",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    response = client.post(
        "/peers",
        json={
            "peer": "http://node1:5000",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["added"] is False
    assert data["peer"] == "http://node1:5000"
    assert data["count"] == 0


def test_duplicate_peer_is_not_added_twice(tmp_path):
    app = create_app(
        data_dir=tmp_path / "node1",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    first = client.post(
        "/peers",
        json={
            "peer": "http://node2:5000/",
        },
    )

    second = client.post(
        "/peers",
        json={
            "peer": "http://node2:5000",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 200

    data = second.get_json()

    assert data["added"] is False
    assert data["count"] == 1
    assert data["peers"] == ["http://node2:5000"]


def test_peer_discovery_imports_remote_peers(tmp_path, monkeypatch):
    app = create_app(
        data_dir=tmp_path / "node1",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    add_response = client.post(
        "/peers",
        json={
            "peer": "http://node2:5000",
        },
    )

    assert add_response.status_code == 201

    def fake_get(url, timeout):
        assert timeout == 3

        if url == "http://node2:5000/peers":
            return (
                {
                    "count": 1,
                    "peers": [
                        "http://node3:5000",
                    ],
                }
            )

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(node, "fetch_json", fake_get)

    discover_response = client.post("/peers/discover")

    assert discover_response.status_code == 200

    data = discover_response.get_json()

    assert data["discovered_count"] == 1
    assert "http://node2:5000" in data["peers"]
    assert "http://node3:5000" in data["peers"]


def test_peer_discovery_skips_invalid_remote_peer_urls(tmp_path, monkeypatch):
    app = create_app(
        data_dir=tmp_path / "node1",
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    client.post(
        "/peers",
        json={
            "peer": "http://node2:5000",
        },
    )

    def fake_get(url, timeout):
        return (
            {
                "peers": [
                    "not-a-url",
                    "ftp://node3:5000",
                    "",
                ],
            }
        )

    monkeypatch.setattr(node, "fetch_json", fake_get)

    discover_response = client.post("/peers/discover")

    assert discover_response.status_code == 200

    data = discover_response.get_json()

    assert data["discovered_count"] == 0
    assert data["count"] == 1
    assert data["peers"] == ["http://node2:5000"]


def test_peer_discovery_persists_new_peers(tmp_path, monkeypatch):
    node_data_dir = tmp_path / "node1"

    app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    client = app.test_client()

    client.post(
        "/peers",
        json={
            "peer": "http://node2:5000",
        },
    )

    def fake_get(url, timeout):
        return (
            {
                "peers": [
                    "http://node3:5000",
                ],
            }
        )

    monkeypatch.setattr(node, "fetch_json", fake_get)

    client.post("/peers/discover")

    restarted_app = create_app(
        data_dir=node_data_dir,
        advertised_url="http://node1:5000",
    )

    restarted_client = restarted_app.test_client()

    peers_response = restarted_client.get("/peers")
    peers_data = peers_response.get_json()

    assert peers_data["count"] == 2
    assert "http://node2:5000" in peers_data["peers"]
    assert "http://node3:5000" in peers_data["peers"]