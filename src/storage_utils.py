import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: str | Path, data: dict[str, Any], indent: int = 2) -> None:
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target_path.parent,
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            json.dump(data, temp_file, indent=indent)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, target_path)

        try:
            directory_fd = os.open(target_path.parent, os.O_RDONLY)

            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

        except OSError:
            pass

    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

        raise


def read_json_or_default(path: str | Path, default: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(path)

    if not source_path.exists():
        return default

    try:
        with open(source_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return default

        return data

    except json.JSONDecodeError:
        return default