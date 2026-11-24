"""Opt-in SQLite node snapshot repository (Mission 002-C2).

No node/CLI activation or legacy migration occurs here. Callers own the
directory and validate consensus before commit. Each connection is private
to one operation and closes before returning.
"""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from block import Block
from transaction import Transaction
from state_repository import ChainSnapshot, NodeSnapshot
from storage_utils import StatePersistenceError
from validation import MAX_MEMPOOL_TRANSACTIONS

SCHEMA_VERSION = 1
# Matches docs/storage-schema-v1.sql. Execute statements individually so schema
# creation and the initial snapshot share the same explicit transaction.
SCHEMA = """CREATE TABLE blocks (
    hash TEXT PRIMARY KEY NOT NULL CHECK(length(hash) = 64),
    height INTEGER NOT NULL CHECK(height >= 0),
    parent_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE chain_meta (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    consensus_json TEXT NOT NULL,
    genesis_hash TEXT NOT NULL REFERENCES blocks(hash),
    revision INTEGER NOT NULL CHECK(revision >= 0)
);

CREATE TABLE active_chain (
    height INTEGER PRIMARY KEY CHECK(height >= 0),
    block_hash TEXT NOT NULL UNIQUE REFERENCES blocks(hash)
);

CREATE TABLE mempool (
    position INTEGER PRIMARY KEY CHECK(position >= 0),
    tx_hash TEXT NOT NULL UNIQUE CHECK(length(tx_hash) = 64),
    payload_json TEXT NOT NULL
);

CREATE TABLE fork_pool (
    block_hash TEXT PRIMARY KEY NOT NULL REFERENCES blocks(hash),
    kind TEXT NOT NULL CHECK(kind IN ('orphan', 'side_branch')),
    arrival_order INTEGER NOT NULL CHECK(arrival_order >= 0),
    UNIQUE(kind, arrival_order)
);

CREATE TABLE peers (
    origin TEXT PRIMARY KEY NOT NULL
);

CREATE TABLE reorg_history (
    sequence INTEGER PRIMARY KEY CHECK(sequence >= 0),
    revision INTEGER CHECK(revision >= 0),
    old_tip TEXT NOT NULL REFERENCES blocks(hash),
    new_tip TEXT NOT NULL REFERENCES blocks(hash),
    event_json TEXT NOT NULL
);

CREATE INDEX blocks_parent ON blocks(parent_hash);
CREATE INDEX fork_pool_order ON fork_pool(kind, arrival_order);"""


def _encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _decode(value):
    def reject_constant(constant):
        raise ValueError(f"Invalid JSON constant: {constant}")
    return json.loads(value, parse_constant=reject_constant)


def _block_record(payload):
    block = Block.from_dict(payload)
    if not block.has_valid_proof():
        raise ValueError("Invalid archived block proof.")
    return block.hash, block.index, block.previous_hash, _encode(payload)


def _prepare(snapshot: NodeSnapshot):
    """Validate storage invariants before opening a write transaction."""
    chain = snapshot.chain
    active = chain["chain"]
    pending = chain["mempool"]
    if not isinstance(active, list) or not active:
        raise ValueError("Empty active chain.")
    if not isinstance(pending, list) or len(pending) > MAX_MEMPOOL_TRANSACTIONS:
        raise ValueError("Invalid mempool size.")
    meta = {key: value for key, value in chain.items() if key not in ("chain", "mempool")}
    blocks = {}
    active_rows = []
    confirmed = set()
    for payload in snapshot.archive + active:
        row = _block_record(payload)
        if row[0] in blocks and blocks[row[0]] != row:
            raise ValueError("Conflicting block payloads.")
        blocks[row[0]] = row
    for height, payload in enumerate(active):
        row = blocks[payload["hash"]]
        parent = "0" if height == 0 else active[height - 1]["hash"]
        if row[1] != height or row[2] != parent:
            raise ValueError("Noncontiguous active chain.")
        active_rows.append((height, row[0]))
        for data in payload["transactions"]:
            confirmed.add(Transaction.from_dict(data).transaction_hash())
    active_hashes = {row[1] for row in active_rows}
    if len(active_hashes) != len(active_rows):
        raise ValueError("Duplicate active block.")
    pending_rows = []
    seen = set()
    for position, payload in enumerate(pending):
        tx = Transaction.from_dict(payload)
        tx_hash = tx.transaction_hash()
        if tx.is_coinbase() or tx_hash in confirmed or tx_hash in seen:
            raise ValueError("Invalid or duplicate pending transaction.")
        seen.add(tx_hash)
        pending_rows.append((position, tx_hash, _encode(payload)))
    pool_rows = []
    seen = set()
    for kind, hashes in (("orphan", snapshot.orphans), ("side_branch", snapshot.side_branches)):
        for position, block_hash in enumerate(hashes):
            if block_hash not in blocks or block_hash in active_hashes or block_hash in seen:
                raise ValueError("Invalid or overlapping fork pool membership.")
            seen.add(block_hash)
            pool_rows.append((block_hash, kind, position))
    if len(snapshot.peers) > 32 or len(set(snapshot.peers)) != len(snapshot.peers):
        raise ValueError("Invalid peer set.")
    if any(not isinstance(peer, str) or not peer for peer in snapshot.peers):
        raise ValueError("Invalid peer origin.")
    if len(snapshot.reorgs) > 100:
        raise ValueError("Reorg history exceeds retention limit.")
    for event in snapshot.reorgs:
        if event["old_tip"] not in blocks or event["new_tip"] not in blocks:
            raise ValueError("Reorg history references an unknown block.")
    # Serialize before locking SQLite; non-JSON values fail without writes.
    return (_encode(meta), list(blocks.values()), active_rows, pending_rows, pool_rows,
            sorted(snapshot.peers), [_encode(event) for event in snapshot.reorgs])


class SQLiteStateRepository:
    """Versioned full-node snapshots with optimistic revision checks.

    expected_revision=None means initial creation only. Never silently
    initialize an existing empty/corrupt/unknown database. A failed first
    creation may leave a file requiring explicit operator inspection.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()

    def exists(self) -> bool:
        return self.path.exists()

    def _connect(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                     isolation_level=None, timeout=5)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except BaseException:
            connection.close()
            raise

    def _check_schema(self, connection):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported SQLite schema version: {version}.")

    def _require_wal(self, connection, *, creating=False):
        command = "PRAGMA journal_mode=WAL" if creating else "PRAGMA journal_mode"
        mode = connection.execute(command).fetchone()[0]
        if mode.lower() != "wal":
            raise ValueError("SQLite WAL journal mode is required.")

    def _initialize_schema(self, connection):
        for statement in SCHEMA.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("PRAGMA user_version=1")

    def _write_snapshot(self, connection, rows, snapshot, revision):
        meta, blocks, active, pending, pools, peers, events = rows
        # Replacing the snapshot is deliberately simple, not an incremental
        # indexing strategy. All deletes/inserts are within one transaction.
        for table in ("reorg_history", "fork_pool", "active_chain", "mempool",
                      "chain_meta", "peers", "blocks"):
            connection.execute(f"DELETE FROM {table}")
        connection.executemany("INSERT INTO blocks VALUES (?, ?, ?, ?)", blocks)
        connection.execute("INSERT INTO chain_meta VALUES (1, ?, ?, ?)",
                           (meta, active[0][1], revision))
        connection.executemany("INSERT INTO active_chain VALUES (?, ?)", active)
        connection.executemany("INSERT INTO mempool VALUES (?, ?, ?)", pending)
        connection.executemany("INSERT INTO fork_pool VALUES (?, ?, ?)", pools)
        connection.executemany("INSERT INTO peers VALUES (?)", [(peer,) for peer in peers])
        # Historical JSON events have no original revision. Preserve that
        # absence instead of inventing a revision; payload order is authoritative.
        connection.executemany(
            "INSERT INTO reorg_history VALUES (?, ?, ?, ?, ?)",
            [(i, event.get("revision"), event["old_tip"], event["new_tip"], events[i])
             for i, event in enumerate(snapshot.reorgs)],
        )

    def commit_node(self, snapshot: NodeSnapshot, *, expected_revision: int | None) -> int:
        try:
            rows = _prepare(snapshot)
            creating = expected_revision is None
            if creating:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive reservation: never overwrite an existing DB.
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            with closing(self._connect()) as connection:
                self._require_wal(connection, creating=creating)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    if creating:
                        self._initialize_schema(connection)
                        revision = 0
                    else:
                        self._check_schema(connection)
                        row = connection.execute("SELECT revision FROM chain_meta WHERE singleton=1").fetchone()
                        if row is None or type(expected_revision) is not int or row[0] != expected_revision:
                            raise ValueError("Missing or stale SQLite state revision.")
                        revision = row[0] + 1
                    self._write_snapshot(connection, rows, snapshot, revision)
                    connection.execute("COMMIT")
                except BaseException:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                    raise
            return revision
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, OverflowError) as error:
            raise StatePersistenceError(f"SQLite state commit failed: {error}") from error

    def load_node(self) -> tuple[int, NodeSnapshot]:
        # mode=rw prevents accidental creation on read; BEGIN gives a coherent
        # view even if another cooperating reader/writer is active.
        try:
            with closing(self._connect()) as connection:
                self._require_wal(connection)
                connection.execute("BEGIN")
                self._check_schema(connection)
                row = connection.execute(
                    "SELECT consensus_json, genesis_hash, revision FROM chain_meta WHERE singleton=1"
                ).fetchone()
                if row is None:
                    raise ValueError("Missing authoritative SQLite state.")
                meta, genesis, revision = row
                chain = _decode(meta)
                if not isinstance(chain, dict) or "chain" in chain or "mempool" in chain:
                    raise ValueError("Invalid consensus metadata.")
                archive = []
                by_hash = {}
                for block_hash, height, parent, payload in connection.execute(
                    "SELECT hash, height, parent_hash, payload_json FROM blocks ORDER BY hash"
                ):
                    data = _decode(payload)
                    if _block_record(data)[:3] != (block_hash, height, parent):
                        raise ValueError("Block metadata mismatch.")
                    archive.append(data)
                    by_hash[block_hash] = data
                active = list(connection.execute("SELECT height, block_hash FROM active_chain ORDER BY height"))
                if not active or active[0][1] != genesis or [r[0] for r in active] != list(range(len(active))):
                    raise ValueError("Invalid active chain mapping.")
                chain["chain"] = [by_hash[r[1]] for r in active]
                chain["mempool"] = []
                for position, tx_hash, payload in connection.execute(
                    "SELECT position, tx_hash, payload_json FROM mempool ORDER BY position"
                ):
                    data = _decode(payload)
                    if position != len(chain["mempool"]) or Transaction.from_dict(data).transaction_hash() != tx_hash:
                        raise ValueError("Mempool metadata mismatch.")
                    chain["mempool"].append(data)
                pools = {"orphan": [], "side_branch": []}
                for kind, position, block_hash in connection.execute(
                    "SELECT kind, arrival_order, block_hash FROM fork_pool ORDER BY kind, arrival_order"
                ):
                    if position != len(pools[kind]):
                        raise ValueError("Invalid fork pool order.")
                    pools[kind].append(block_hash)
                events = []
                for sequence, event_revision, old_tip, new_tip, payload in connection.execute(
                    "SELECT sequence, revision, old_tip, new_tip, event_json FROM reorg_history ORDER BY sequence"
                ):
                    event = _decode(payload)
                    if (sequence != len(events) or event.get("revision") != event_revision
                            or event["old_tip"] != old_tip or event["new_tip"] != new_tip):
                        raise ValueError("Invalid reorg metadata.")
                    events.append(event)
                peers = [r[0] for r in connection.execute("SELECT origin FROM peers ORDER BY origin")]
                snapshot = NodeSnapshot(chain, archive, pools["orphan"], pools["side_branch"], peers, events)
                _prepare(snapshot)
                if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("SQLite foreign key check failed.")
                connection.execute("COMMIT")
                return revision, snapshot
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, OverflowError) as error:
            raise StatePersistenceError(f"SQLite state load failed: {error}") from error


class SQLiteChainRepository:
    """ChainRepository adapter for isolated chain-only experiments.

    Never use this adapter to mutate a DB containing node auxiliary state.
    Node integration must use commit_node for complete snapshots.
    """
    def __init__(self, path: str | Path):
        self.state = SQLiteStateRepository(path)

    def exists(self) -> bool:
        return self.state.exists()

    def load(self) -> ChainSnapshot:
        _, snapshot = self.state.load_node()
        self._require_chain_only(snapshot)
        return snapshot.chain

    @staticmethod
    def _require_chain_only(snapshot):
        if snapshot.orphans or snapshot.side_branches or snapshot.peers or snapshot.reorgs:
            raise StatePersistenceError("Node auxiliary state requires full-node commits.")

    def commit(self, snapshot: ChainSnapshot) -> None:
        revision, archive = None, []
        if self.exists():
            revision, previous = self.state.load_node()
            self._require_chain_only(previous)
            archive = previous.archive
        self.state.commit_node(NodeSnapshot(snapshot, archive), expected_revision=revision)
