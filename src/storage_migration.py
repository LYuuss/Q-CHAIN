"""Offline, non-destructive storage migration (Mission 002-C3).

Run against stopped state directories on a supported local filesystem.
Never activates a backend. Wallets are deliberately outside this boundary.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import ExitStack, closing, contextmanager
from copy import deepcopy
from pathlib import Path

from block import Block
from blockchain import Blockchain
from node import normalize_peer_url, MAX_ORPHAN_BLOCKS, MAX_SIDE_BRANCH_BLOCKS
from sqlite_repository import SQLiteStateRepository
from state_lock import state_directory_lock
from state_repository import NodeSnapshot
from storage_utils import StatePersistenceError, read_json_strict, write_state_json
from transaction import Transaction
from transaction_index import TransactionIndex
from validation import MAX_MEMPOOL_TRANSACTIONS

STATE_FILES = ("chain.json", "mempool.json", "block_index.json", "orphan_blocks.json",
               "side_branch_blocks.json", "peers.json", "reorg_history.json", "tx_index.json")


class ReadOnlySnapshot:
    def __init__(self, data):
        self.data = data

    def exists(self):
        return True

    def load(self):
        return deepcopy(self.data)

    def commit(self, snapshot):
        raise StatePersistenceError("Migration validation is read-only.")


def replay(data):
    return Blockchain(difficulty=1, repository=ReadOnlySnapshot(data))


def _checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checksums(directory):
    return {name: _checksum(directory / name) for name in STATE_FILES
            if (directory / name).is_file()}


def _aux(directory, filename, key, expected, warnings):
    path = directory / filename
    if not path.exists():
        warnings.append(f"{filename}: missing; using empty auxiliary state")
        return expected()
    try:
        data = read_json_strict(path)
        value = data.get(key)
        if not isinstance(value, expected):
            raise ValueError("invalid auxiliary structure")
        return value
    except (ValueError, OSError):
        warnings.append(f"{filename}: invalid/unreadable; using empty auxiliary state")
        return expected()


def read_legacy(directory):
    """Read only; preserve the legacy authority rule and report reconciliation."""
    warnings = []
    raw = read_json_strict(directory / "chain.json")
    legacy = "mempool" not in raw
    if legacy:
        raw["mempool"] = _aux(directory, "mempool.json", "transactions", list, warnings)
        warnings.append("Imported legacy mempool mirror because chain.json lacked mempool.")
    chain = replay(raw)
    canonical = chain.snapshot()
    # Do not silently discard an authoritative pending transaction. The legacy
    # mirror can be stale, so normalize/revalidate it and report any changes.
    if raw["mempool"] != canonical["mempool"]:
        if not legacy:
            raise ValueError("Authoritative mempool changes during replay; inspect source before migration.")
        warnings.append(f"Legacy mempool revalidated: {len(raw['mempool'])} entries -> {len(canonical['mempool'])}.")
    active = {block["hash"]: block for block in canonical["chain"]}
    archive = dict(active)

    def read_blocks(filename):
        valid = []
        for key, payload in _aux(directory, filename, "blocks", dict, warnings).items():
            try:
                block = Block.from_dict(payload)
                if key != block.hash or not block.has_valid_proof():
                    raise ValueError("invalid proof or key")
                normalized = block.to_dict()
                if block.hash in archive and archive[block.hash] != normalized:
                    raise ValueError("conflicting block payload")
                archive[block.hash] = normalized
                valid.append(block.hash)
            except (ValueError, TypeError, KeyError, OverflowError):
                warnings.append(f"{filename}: skipped invalid block entry")
        return valid

    read_blocks("block_index.json")
    orphans = []
    sides = []
    seen = set(active)
    for filename, pool, cap in (("orphan_blocks.json", orphans, MAX_ORPHAN_BLOCKS),
                                ("side_branch_blocks.json", sides, MAX_SIDE_BRANCH_BLOCKS)):
        for block_hash in read_blocks(filename):
            if block_hash in seen or len(pool) >= cap:
                warnings.append(f"{filename}: reconciled active/duplicate/over-limit membership")
                continue
            seen.add(block_hash)
            pool.append(block_hash)
    peers = set()
    for value in _aux(directory, "peers.json", "peers", list, warnings):
        normalized = normalize_peer_url(value)
        if normalized is None or (normalized not in peers and len(peers) >= 32):
            warnings.append("peers.json: skipped invalid/over-limit peer")
        else:
            peers.add(normalized)
    events = []
    for event in _aux(directory, "reorg_history.json", "reorgs", list, warnings):
        if (not isinstance(event, dict) or not isinstance(event.get("old_tip"), str)
                or not isinstance(event.get("new_tip"), str)
                or event["old_tip"] not in archive or event["new_tip"] not in archive
                or (event.get("revision") is not None and
                    (type(event["revision"]) is not int or event["revision"] < 0))):
            warnings.append("reorg_history.json: skipped invalid event or missing archive reference")
            continue
        events.append(event)
    if len(events) > 100:
        warnings.append("reorg_history.json: retained most recent 100 valid events")
    return NodeSnapshot(canonical, list(archive.values()), orphans, sides, sorted(peers), events[-100:]), chain, warnings


def _same_snapshot(left, right):
    # Archive ordering is not authoritative; pool and mempool ordering are.
    return (left.chain == right.chain
            and {b["hash"]: b for b in left.archive} == {b["hash"]: b for b in right.archive}
            and left.orphans == right.orphans and left.side_branches == right.side_branches
            and left.peers == right.peers and left.reorgs == right.reorgs)


def _verify(snapshot, loaded, original):
    rebuilt = replay(loaded.chain)
    if (not _same_snapshot(snapshot, loaded) or rebuilt.snapshot() != loaded.chain
            or rebuilt.get_state() != original.get_state()
            or rebuilt.calculate_cumulative_work() != original.calculate_cumulative_work()):
        raise ValueError("Migration verification failed: state mismatch.")
    return rebuilt


def _summary(chain, snapshot):
    return {"genesis": chain.chain[0].hash, "height": len(chain.chain) - 1,
            "tip": chain.latest_block().hash, "work": chain.calculate_cumulative_work(),
            "mempool": len(snapshot.chain["mempool"]), "archive": len(snapshot.archive),
            "orphans": len(snapshot.orphans), "side_branches": len(snapshot.side_branches),
            "peers": len(snapshot.peers), "reorgs": len(snapshot.reorgs)}


@contextmanager
def _own(*directories):
    with ExitStack() as stack:
        for directory in sorted(set(directories), key=str):
            stack.enter_context(state_directory_lock(directory))
        yield


def _sync_dir(directory):
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _require_new_database(path):
    if any(os.path.lexists(str(path) + suffix) for suffix in ("", "-wal", "-shm", "-journal")):
        raise FileExistsError("Destination database or sidecar already exists.")


def import_json(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir() or not (source / "chain.json").is_file():
        raise ValueError("Source must contain an existing chain.json.")
    if destination.parent == source or source in destination.parents:
        raise ValueError("Choose a separate destination directory outside the source.")
    _require_new_database(destination)
    with _own(source, destination.parent):
        _require_new_database(destination)
        checksums = _checksums(source)
        snapshot, chain, warnings = read_legacy(source)
        with tempfile.TemporaryDirectory(prefix=".qchain-import-", dir=destination.parent) as work:
            candidate = Path(work) / "candidate.db"
            repository = SQLiteStateRepository(candidate)
            revision = repository.commit_node(snapshot, expected_revision=None)
            actual_revision, loaded = repository.load_node()
            if actual_revision != revision:
                raise ValueError("Unexpected initial revision.")
            _verify(snapshot, loaded, chain)
            with closing(sqlite3.connect(candidate)) as connection:
                if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("SQLite integrity check failed.")
                if connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("SQLite foreign key check failed.")
                if connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                    raise ValueError("SQLite checkpoint busy.")
            if any(Path(str(candidate) + suffix).exists() for suffix in ("-wal", "-shm")):
                raise ValueError("Temporary SQLite sidecars remain after close.")
            if _checksums(source) != checksums:
                raise ValueError("Source changed during migration.")
            # Atomic no-overwrite publication, on the same destination filesystem.
            _require_new_database(destination)
            os.link(candidate, destination)
            _sync_dir(destination.parent)
        return {"operation": "import", "destination": str(destination), "revision": revision,
                "source_sha256": checksums, "warnings": warnings, **_summary(chain, loaded)}


def _write_legacy(directory, snapshot, chain):
    blocks = {b["hash"]: b for b in snapshot.archive}
    write_state_json(directory / "block_index.json", {"blocks": blocks})
    write_state_json(directory / "orphan_blocks.json", {"blocks": {h: blocks[h] for h in snapshot.orphans}})
    write_state_json(directory / "side_branch_blocks.json", {"blocks": {h: blocks[h] for h in snapshot.side_branches}})
    write_state_json(directory / "peers.json", {"peers": snapshot.peers})
    write_state_json(directory / "reorg_history.json", {"reorgs": snapshot.reorgs})
    write_state_json(directory / "mempool.json", {"transactions": snapshot.chain["mempool"]})
    index = TransactionIndex(directory / "tx_index.json")
    index.rebuild_from_chain(chain.chain)
    write_state_json(directory / "chain.json", snapshot.chain)


def export_json(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Source must be an existing SQLite database.")
    if destination == source.parent or destination in source.parents or source.parent in destination.parents:
        raise ValueError("Choose a separate destination directory outside the source.")
    if destination.exists():
        raise FileExistsError("Destination directory already exists.")
    with _own(source.parent, destination.parent):
        if destination.exists():
            raise FileExistsError("Destination directory already exists.")
        revision, snapshot = SQLiteStateRepository(source).load_node()
        chain = replay(snapshot.chain)
        if chain.snapshot() != snapshot.chain:
            raise ValueError("SQLite authoritative snapshot changes during consensus replay.")
        with tempfile.TemporaryDirectory(prefix=".qchain-export-", dir=destination.parent) as work:
            staged = Path(work) / "export"
            staged.mkdir(mode=0o700)
            _write_legacy(staged, snapshot, chain)
            loaded, _, warnings = read_legacy(staged)
            _verify(snapshot, loaded, chain)
            report = {"operation": "export", "destination": str(destination), "revision": revision,
                      "export_sha256": _checksums(staged), "warnings": warnings, **_summary(chain, snapshot)}
            write_state_json(staged / "migration-report.json", report)
            _sync_dir(staged)
            # Cooperating publishers hold the destination parent lock. Refuse
            # any preexisting target; never export into a live node directory.
            if destination.exists():
                raise FileExistsError("Destination directory already exists.")
            os.rename(staged, destination)
            _sync_dir(destination.parent)
        return report


def main():
    parser = argparse.ArgumentParser(description="Offline QChain storage conversion (no backend activation)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("import-json", "export-json"):
        command = sub.add_parser(name)
        command.add_argument("source", type=Path)
        command.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        report = (import_json if args.command == "import-json" else export_json)(args.source, args.destination)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, StatePersistenceError, sqlite3.Error, TypeError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
