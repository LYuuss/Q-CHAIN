"""Persistence boundary for the authoritative chain and ordered mempool.

The contract is limited to one chain snapshot in C1. A future node-level
unit of work must include fork pools and reorg history; this contract alone
does not give multi-record atomicity.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from storage_utils import read_json_strict, write_state_json

ChainSnapshot = dict[str, Any]


class ChainRepository(Protocol):
    """A cooperating single writer supplies detached, consensus-validated snapshots.

    load returns a detached snapshot and never initializes missing state.
    commit must either durably publish the snapshot or raise
    StatePersistenceError (including an uncertain commit outcome).
    Repository implementations must not mutate caller-owned snapshots.
    """

    def exists(self) -> bool: ...
    def load(self) -> ChainSnapshot: ...
    def commit(self, snapshot: ChainSnapshot) -> None: ...


class JsonChainRepository:
    """Legacy chain.json representation; no schema or wire-format changes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> ChainSnapshot:
        return read_json_strict(self.path)

    def commit(self, snapshot: ChainSnapshot) -> None:
        write_state_json(self.path, snapshot)


@dataclass
class NodeSnapshot:
    """Detached node state; ordered lists retain pool and history semantics.

    The caller validates consensus and normalizes peers before commit.
    Balances, nonces and the confirmed transaction index are derived on replay.
    """
    chain: ChainSnapshot
    archive: list[dict[str, Any]] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    side_branches: list[str] = field(default_factory=list)
    peers: list[str] = field(default_factory=list)
    reorgs: list[dict[str, Any]] = field(default_factory=list)


class NodeStateRepository(Protocol):
    def exists(self) -> bool: ...
    def load_node(self) -> tuple[int, NodeSnapshot]: ...
    def commit_node(self, snapshot: NodeSnapshot, *, expected_revision: int | None) -> int: ...
