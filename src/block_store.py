import json
from pathlib import Path

from block import Block


class BlockStore:
    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        self.blocks: dict[str, Block] = {}
        self.load()

    def load(self) -> None:
        if not self.storage_path.exists():
            self.save()
            return

        with open(self.storage_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.blocks = {}

        for block_data in data.get("blocks", {}).values():
            block = Block.from_dict(block_data)
            self.blocks[block.hash] = block

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "blocks": {
                block_hash: block.to_dict()
                for block_hash, block in sorted(self.blocks.items())
            }
        }

        with open(self.storage_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    def put(self, block: Block, save: bool = True) -> None:
        self.blocks[block.hash] = block

        if save:
            self.save()

    def put_many(self, blocks: list[Block], save: bool = True) -> None:
        for block in blocks:
            self.blocks[block.hash] = block

        if save:
            self.save()

    def get(self, block_hash: str) -> Block | None:
        return self.blocks.get(block_hash)

    def has(self, block_hash: str) -> bool:
        return block_hash in self.blocks

    def count(self) -> int:
        return len(self.blocks)

    def summaries(self) -> list[dict]:
        return [
            {
                "index": block.index,
                "hash": block.hash,
                "previous_hash": block.previous_hash,
                "difficulty": block.difficulty,
                "transaction_count": len(block.transactions),
            }
            for block in self.blocks.values()
        ]