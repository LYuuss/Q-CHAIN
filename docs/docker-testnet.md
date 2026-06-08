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

This document explains how to start, connect, test, stop, and reset the Docker testnet.

---

## 1. Files Required

At the root of the project:

```text
Dockerfile
docker-compose.yml
requirements.txt
scripts/
src/
data/
```

The Docker testnet uses:

```text
docker-compose.yml
Dockerfile
scripts/connect_docker_nodes.sh
scripts/start_docker_testnet.sh
scripts/stop_docker_testnet.sh
scripts/reset_docker_testnet.sh
scripts/status_all.sh
scripts/mempool_all.sh
scripts/balance_all.sh
```

---

## 2. Docker Compose Services

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

## 3. Advertised URL

Each node uses an advertised URL.

Example:

```text
node1 advertises http://node1:5000
node2 advertises http://node2:5000
node3 advertises http://node3:5000
```

This is important because `127.0.0.1` inside a Docker container means the container itself, not the host machine.

Without advertised URLs, a node may incorrectly broadcast to:

```text
http://127.0.0.1:5001
```

from inside Docker, which can cause connection errors.

---

## 4. Start the Testnet

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

## 5. Check Running Containers

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

## 6. Check Node Status

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

---

## 7. Connect Docker Nodes

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

## 8. Mine a Block

```bash
python3 src/qchain.py node-mine 5001 alice
```

This asks node1 to mine a block and reward Alice.

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

## 9. Send a Transaction

```bash
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
```

This sends a signed transaction from Alice to Bob through node1.

The transaction is broadcast to the other nodes.

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

---

## 10. Mine the Transaction

```bash
python3 src/qchain.py node-mine 5002 miner
```

This asks node2 to mine a block containing the pending transaction.

After mining, the block is broadcast to the other nodes.

Check mempools:

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

## 11. Check Balances

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

## 12. Stop the Testnet

```bash
bash scripts/stop_docker_testnet.sh
```

Equivalent:

```bash
docker compose down
```

This stops containers but keeps Docker node data.

---

## 13. Restart the Testnet

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

## 14. Reset the Testnet

```bash
bash scripts/reset_docker_testnet.sh
```

This removes:

```text
data/docker/
```

It deletes Docker node chains, balances, mempools, and peer files.

It does not delete wallets in:

```text
data/wallets/
```

---

## 15. View Logs

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

## 16. Common Issues

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

---

### Connection refused to 127.0.0.1 from Docker

Inside Docker, `127.0.0.1` means the current container.

Use internal service names:

```text
http://node1:5000
http://node2:5000
http://node3:5000
```

The `--advertised-url` option solves this by making each node announce the correct Docker-internal URL.

---

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

## 17. Full Test Scenario

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

Stop testnet:

```bash
bash scripts/stop_docker_testnet.sh
```
