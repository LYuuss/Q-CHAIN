import json

from storage_utils import atomic_write_json, read_json_or_default


def test_atomic_write_json_creates_file(tmp_path):
    path = tmp_path / "data.json"

    atomic_write_json(
        path,
        {
            "name": "QChain",
            "tests": 37,
        },
    )

    assert path.exists()

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["name"] == "QChain"
    assert data["tests"] == 37


def test_atomic_write_json_replaces_existing_file(tmp_path):
    path = tmp_path / "data.json"

    atomic_write_json(
        path,
        {
            "version": 1,
        },
    )

    atomic_write_json(
        path,
        {
            "version": 2,
        },
    )

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["version"] == 2


def test_read_json_or_default_returns_default_when_file_is_missing(tmp_path):
    path = tmp_path / "missing.json"

    data = read_json_or_default(
        path,
        default={
            "items": [],
        },
    )

    assert data == {
        "items": [],
    }


def test_read_json_or_default_returns_default_when_file_is_invalid(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ broken json", encoding="utf-8")

    data = read_json_or_default(
        path,
        default={
            "safe": True,
        },
    )

    assert data == {
        "safe": True,
    }