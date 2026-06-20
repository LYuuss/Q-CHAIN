# QChain Docker Testnet

QChain includes a Docker-based local testnet with three nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Inside Docker, nodes communicate through:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

---

## Start

```bash
bash scripts/start_docker_testnet.sh
```

Manual start:

```bash
docker compose up -d --build
bash scripts/connect_docker_nodes.sh
```

---

## Node Storage

Docker node data is stored under:

```text
data/docker/
```

A node directory can contain:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
```

---

## Status

```bash
bash scripts/status_all.sh
```

or:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-status 5002
python3 src/qchain.py node-status 5003
```

---

## Inspect Persistent Pools

```bash
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
```

The orphan pool is stored in:

```text
orphan_blocks.json
```

The side-branch pool is stored in:

```text
side_branch_blocks.json
```

---

## Restart Behavior

Persistent storage means a node can restart without losing:

```text
known blocks
orphan blocks
side-branch fork blocks
```

After restart:

```text
GET /blocks/<hash>
GET /orphans
GET /side-branches
```

still reflect persisted state.

---

## Header-First Sync

```bash
python3 src/qchain.py node-sync 5001
```

If already synchronized:

```json
{
  "downloaded_block_count": 0
}
```

---

## Stop

```bash
bash scripts/stop_docker_testnet.sh
```

or:

```bash
docker compose down
```

---

## Reset

```bash
bash scripts/reset_docker_testnet.sh
```

This removes Docker node data under:

```text
data/docker/
```

It does not delete wallets in:

```text
data/wallets/
```

---

## Docker Networking Note

Inside Docker, `127.0.0.1` means the current container.

Use internal service names:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```
