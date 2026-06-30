# QChain Docker Testnet

QChain includes a Docker-based local testnet with three nodes.

---

## Nodes

Host URLs:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

Internal Docker URLs:

```text
node1 -> http://node1:5000
node2 -> http://node2:5000
node3 -> http://node3:5000
```

Inside Docker, nodes must use the internal service names instead of `127.0.0.1`.

---

## Start

```bash
bash scripts/start_docker_testnet.sh
```

Manual equivalent:

```bash
docker compose up -d --build
bash scripts/connect_docker_nodes.sh
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

This removes Docker node state under:

```text
data/docker/
```

It does not delete wallets under:

```text
data/wallets/
```

---

## Inspect All Nodes

```bash
bash scripts/status_all.sh
bash scripts/mempool_all.sh
bash scripts/balance_all.sh <address>
```

---

## Docker Node Storage

Docker node data is stored under:

```text
data/docker/
```

Each node can persist:

```text
chain.json
peers.json
block_index.json
orphan_blocks.json
side_branch_blocks.json
mempool.json
tx_index.json
```

---

## Wallet Storage

Wallet files are stored outside the Docker node state by default:

```text
data/wallets/*.json
```

Wallet files are encrypted and written atomically.

---

## Testnet Example

```bash
bash scripts/start_docker_testnet.sh

python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner

python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-mine 5002 miner

python3 src/qchain.py node-balance 5001 bob
python3 src/qchain.py node-address-transactions 5001 <bob_address>
```

---

## Sync

```bash
python3 src/qchain.py node-sync 5001
```

Header-first sync flow:

```text
GET /status
GET /headers
validate headers
find common ancestor
download missing blocks
build candidate chain
adopt if heavier
recover mempool transactions if reorg occurs
```

---

## Fork Inspection

```bash
python3 src/qchain.py node-orphans 5001
python3 src/qchain.py node-side-branches 5001
```

---

## Notes

The Docker testnet is intended for local development only.
