"""Explicit runtime backend selection and a private node working snapshot.

All node workspace access is serialized by the node lock. The chain repository
below is deliberately a staging adapter, not durable storage: its caller must
commit the entire workspace before releasing the lock or acknowledging state.
"""
from copy import deepcopy
from pathlib import Path

from block import Block
from blockchain import Blockchain
from sqlite_repository import SQLiteStateRepository
from state_repository import NodeSnapshot
from storage_utils import StatePersistenceError

DATABASE_NAME = "state.db"
STATE_FILES = ("chain.json", "mempool.json", "block_index.json", "orphan_blocks.json",
               "side_branch_blocks.json", "peers.json", "reorg_history.json", "tx_index.json")


def require_backend(directory: Path, backend: str) -> Path:
    """Reject ambiguous activation before creating or modifying any state."""
    def present(name):
        path = directory / name
        return path.exists() or path.is_symlink()

    database = directory / DATABASE_NAME
    sidecars = (DATABASE_NAME + "-wal", DATABASE_NAME + "-shm", DATABASE_NAME + "-journal")
    if backend == "json":
        if any(present(name) for name in (DATABASE_NAME, *sidecars)):
            raise StatePersistenceError("SQLite state is present; explicitly select sqlite or export to a new directory.")
    elif backend == "sqlite":
        if any(present(name) for name in STATE_FILES):
            raise StatePersistenceError("Legacy JSON state is present; migrate offline to a separate directory.")
        if not database.exists() and (database.is_symlink() or any(present(name) for name in sidecars)):
            raise StatePersistenceError("Incomplete SQLite state; inspect storage before restarting.")
        if any((directory / name).is_symlink() for name in (DATABASE_NAME, *sidecars)):
            raise StatePersistenceError("SQLite state and sidecars must not be symbolic links.")
    else:
        raise ValueError("Unknown storage backend.")
    return database


class _WorkingChain:
    """Private chain staging area; never exposed outside a node unit of work."""

    def __init__(self, snapshot):
        self.data = deepcopy(snapshot)

    def exists(self):
        return self.data is not None

    def load(self):
        return deepcopy(self.data)

    def commit(self, snapshot):
        self.data = deepcopy(snapshot)


class SQLiteNodeWorkspace:
    def __init__(self, path):
        self.repository = SQLiteStateRepository(path)
        self.revision = None
        self.previous = None
        if self.repository.exists():
            self.revision, self.previous = self.repository.load_node()
        self.staging = _WorkingChain(self.previous.chain if self.previous else None)

    def open_chain(self, **kwargs):
        chain = Blockchain(repository=self.staging, **kwargs)
        if self.previous and chain.snapshot() != self.previous.chain:
            raise StatePersistenceError("SQLite authoritative chain/mempool differs after replay.")
        return chain

    def commit(self, chain, archive, orphans, side_branches, peers, reorgs):
        candidate = NodeSnapshot(
            chain.snapshot(),
            [archive[key].to_dict() for key in sorted(archive)],
            list(orphans), list(side_branches), sorted(peers), deepcopy(reorgs),
        )
        if candidate == self.previous:
            return
        # Pin the revision loaded by this owner, never silently refresh a stale lease.
        self.revision = self.repository.commit_node(candidate, expected_revision=self.revision)
        self.previous = candidate

    def archive(self):
        return {data["hash"]: Block.from_dict(data) for data in self.previous.archive} if self.previous else {}
