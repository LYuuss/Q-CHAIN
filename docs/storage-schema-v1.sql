-- Draft reference schema, Mission 002-C. Not a production migration.
-- Connection-level foreign_keys must be enabled before the transaction.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE blocks (
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
    revision INTEGER NOT NULL UNIQUE CHECK(revision >= 0),
    old_tip TEXT NOT NULL REFERENCES blocks(hash),
    new_tip TEXT NOT NULL REFERENCES blocks(hash),
    event_json TEXT NOT NULL
);

CREATE INDEX blocks_parent ON blocks(parent_hash);
CREATE INDEX fork_pool_order ON fork_pool(kind, arrival_order);

-- Cross-table invariants and consensus replay are enforced by the repository.
PRAGMA user_version = 1;
COMMIT;
