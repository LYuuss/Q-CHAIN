# QChain Docker Testnet

QChain includes a Docker-based local testnet.

The testnet runs three independent QChain nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Inside Docker, the nodes communicate through internal service names:

```text
node1 -> http://node1:5000
node2 -> http://node2:5000
node3 -> http://node3:5000
```

This document explains how to start, connect, test, stop, reset, and debug the Docker testnet.

---

## 1. Docker Compose Services

The testnet contains three services:

```text
node1
node2
node3
```

Each container runs QChain on port `5000` internally.

The ports exposed on the host machine are:

```text
5001 -> node1:5000
5002 -> node2:5000
5003 -> node3:5000
```

---

## 2. Advertised URL

Each node uses an advertised URL.

Example:

```text
node1 advertises http://node1:5000
node2 advertises http://node2:5000
node3 advertises http://node3:5000
```

This is important because `127.0.0.1` inside a Docker container means the container itself, not the host machine.

The `--advertised-url` option makes each node announce the correct Docker-internal URL.

---

## 3. Start the Testnet

Recommended command:

```bash
bash scripts/start_docker_testnet.sh
```

This script:

```text
builds the Docker image
starts node1, node2, and node3
waits for the nodes to be ready
connects the nodes together using Docker internal URLs
```

Manual command:

```bash
docker compose up -d --build
```

Then connect peers manually or with:

```bash
bash scripts/connect_docker_nodes.sh
```

---

## 4. Check Running Containers

```bash
docker compose ps
```

You should see:

```text
qchain-node1
qchain-node2
qchain-node3
```

---

## 5. Check Node Status

```bash
bash scripts/status_all.sh
```

Or manually:

```bash
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-status 5002
python3 src/qchain.py node-status 5003
```

All nodes should have:

```text
valid = true
same genesis_hash
same latest_hash after synchronization
same cumulative_work after synchronization
```

The status also includes:

```text
mempool_size
orphan_pool_size
advertised_url
peers
```

---

## 6. Connect Docker Nodes

Recommended:

```bash
bash scripts/connect_docker_nodes.sh
```

This connects:

```text
node1 -> node2
node1 -> node3
node2 -> node1
node2 -> node3
node3 -> node1
node3 -> node2
```

The script uses Docker internal URLs:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

---

## 7. Mine a Block

```bash
python3 src/qchain.py node-mine 5001 alice
```

Check all nodes:

```bash
bash scripts/status_all.sh
```

Expected result:

```text
all nodes have the same height
all nodes have the same latest_hash
all nodes have the same cumulative_work
```

---

## 8. Send and Mine a Transaction

Send a signed transaction from Alice to Bob:

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

Check mempools:

```bash
bash scripts/mempool_all.sh
```

Expected result:

```text
node1 mempool size = 1
node2 mempool size = 1
node3 mempool size = 1
```

Mine the transaction:

```bash
python3 src/qchain.py node-mine 5002 miner
```

Check mempools again:

```bash
bash scripts/mempool_all.sh
```

Expected result:

```text
node1 mempool size = 0
node2 mempool size = 0
node3 mempool size = 0
```

---

## 9. Check Balances

Check Bob on all nodes:

```bash
bash scripts/balance_all.sh bob
```

Expected after one transaction:

```text
Bob = 10 QCOIN
```

Expected after two transactions of 10 QCOIN:

```text
Bob = 20 QCOIN
```

Check miner:

```bash
bash scripts/balance_all.sh miner
```

If the miner mined two transaction blocks with 2 QCOIN fee each:

```text
Miner = 104 QCOIN
```

because:

```text
2 × (50 reward + 2 fee) = 104 QCOIN
```

---

## 10. Inspect Headers

```bash
python3 src/qchain.py node-headers 5001
python3 src/qchain.py node-headers 5002
python3 src/qchain.py node-headers 5003
```

Equivalent endpoint:

```text
GET /headers
```

Headers are used by header-first sync.

---

## 11. Inspect Orphan Pools

```bash
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-orphans 5002
python3 src/qchain.py node-orphans 5003
```

Equivalent endpoint:

```text
GET /orphans
```

Normal expected result:

```json
{
  "blocks": [],
  "max_size": 100,
  "size": 0
}
```

If a node receives a block before its parent, the block can be temporarily stored here.

---

## 12. Header-First Sync

Synchronize a node:

```bash
python3 src/qchain.py node-sync 5001
```

The sync process:

```text
checks peers
compares cumulative work
downloads headers
validates headers
finds a common ancestor
downloads only missing blocks
reconstructs a candidate chain
adopts it if heavier and valid
processes orphan blocks
```

If the node is already up to date:

```json
{
  "downloaded_block_count": 0
}
```

This confirms that the node did not download full blocks unnecessarily.

---

## 13. Stop the Testnet

```bash
bash scripts/stop_docker_testnet.sh
```

Equivalent:

```bash
docker compose down
```

This stops containers but keeps Docker node data.

---

## 14. Restart the Testnet

If the Docker image does not need rebuilding:

```bash
docker compose up -d
```

If source code used inside Docker changed:

```bash
docker compose up -d --build
```

Or use:

```bash
bash scripts/start_docker_testnet.sh
```

---

## 15. Reset the Testnet

```bash
bash scripts/reset_docker_testnet.sh
```

This removes:

```text
data/docker/
```

It deletes Docker node chains, balances, mempools, orphan pools, and peer files.

It does not delete wallets in:

```text
data/wallets/
```

---

## 16. View Logs

All nodes:

```bash
docker compose logs -f
```

One node:

```bash
docker compose logs -f node1
docker compose logs -f node2
docker compose logs -f node3
```

---

## 17. Common Issues

### Docker says no configuration file provided

Make sure you are in the project root where `docker-compose.yml` exists.

Check:

```bash
ls docker-compose.yml
```

Then run:

```bash
docker compose up -d --build
```

### Connection refused to 127.0.0.1 from Docker

Inside Docker, `127.0.0.1` means the current container.

Use internal service names:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

### balance shows zero but node-balance shows funds

This command checks the local CLI chain:

```bash
python3 src/qchain.py balance bob
```

This command checks the Docker node:

```bash
python3 src/qchain.py node-balance 5001 bob
```

When testing Docker, use `node-balance`.

---

## 18. Full Test Scenario

Start testnet:

```bash
bash scripts/start_docker_testnet.sh
```

Mine funds to Alice:

```bash
python3 src/qchain.py node-mine 5001 alice
```

Send from Alice to Bob:

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

Check mempools:

```bash
bash scripts/mempool_all.sh
```

Mine transaction:

```bash
python3 src/qchain.py node-mine 5002 miner
```

Check balances:

```bash
bash scripts/balance_all.sh bob
bash scripts/balance_all.sh miner
```

Inspect headers:

```bash
python3 src/qchain.py node-headers 5001
```

Inspect orphan pool:

```bash
python3 src/qchain.py node-orphans 5001
```

Stop testnet:

```bash
bash scripts/stop_docker_testnet.sh
```
