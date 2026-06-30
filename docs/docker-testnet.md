# QChain Docker Testnet

QChain includes a Docker-based local testnet with three nodes:

```text
node1 -> http://127.0.0.1:5001
node2 -> http://127.0.0.1:5002
node3 -> http://127.0.0.1:5003
```

---

## Persistent Node Files

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

## Wallet Files

Wallet files are stored outside the Docker node state by default:

```text
data/wallets/*.json
```

Wallet files are also written atomically.

This protects encrypted keystore JSON files from partial writes.

---

## Useful Commands

```bash
bash scripts/start_docker_testnet.sh
bash scripts/status_all.sh

python3 src/qchain.py wallet-create alice
python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
python3 src/qchain.py node-sync 5001
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

It does not delete wallets stored under:

```text
data/wallets/
```
