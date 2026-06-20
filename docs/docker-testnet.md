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

## Status

```bash
bash scripts/status_all.sh
```

Or:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-status 5002
python3 src/qchain.py node-status 5003
```

Status includes:

```text
height
latest_hash
cumulative_work
mempool_size
orphan_pool_size
side_branch_pool_size
peers
valid
```

---

## Mine

```bash
python3 src/qchain.py node-mine 5001 alice
```

---

## Send Transaction

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

---

## Check Mempools

```bash
bash scripts/mempool_all.sh
```

---

## Mine Transaction

```bash
python3 src/qchain.py node-mine 5002 miner
```

---

## Check Balances

```bash
bash scripts/balance_all.sh bob
bash scripts/balance_all.sh miner
```

---

## Inspect Headers

```bash
python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-headers 5002
python3 src/qchain.py node-headers 5003
```

Equivalent endpoint:

```text
GET /headers
```

---

## Inspect Orphan Pools

```bash
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-orphans 5002
python3 src/qchain.py node-orphans 5003
```

Equivalent endpoint:

```text
GET /orphans
```

---

## Inspect Side Branches

```bash
python3 src/qchain.py node-side-branches 5001
python3 src/qchain.py node-side-branches 5002
python3 src/qchain.py node-side-branches 5003
```

Equivalent endpoint:

```text
GET /side-branches
```

Normal result:

```json
{
  "blocks": [],
  "max_size": 200,
  "size": 0,
  "tip_hashes": []
}
```

---

## Header-First Sync

```bash
python3 src/qchain.py node-sync 5001
```

The node:

```text
checks peers
compares cumulative work
downloads headers
validates headers
finds common ancestor
downloads only missing blocks
rebuilds candidate chain
adopts if heavier
processes orphans
processes side branches
```

If already synchronized:

```json
{
  "downloaded_block_count": 0
}
```

---

## Fork and Reorg Behavior

QChain now distinguishes:

```text
direct extension:
    accepted into main chain

missing parent:
    stored in orphan pool

known parent but not current tip:
    stored in side-branch pool
```

If a side branch becomes heavier, QChain can automatically reorganize.

Example:

```text
current main chain:
0 -> 1A

side branch:
0 -> 1B -> 2B

after reorg:
0 -> 1B -> 2B
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

## Logs

```bash
docker compose logs -f
```

For one node:

```bash
docker compose logs -f node1
```

---

## Common Docker Issue

Inside Docker, `127.0.0.1` means the current container.

Use internal service names:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

The `--advertised-url` option makes each node announce the correct Docker-internal URL.
