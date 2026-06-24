# QChain Usage Guide

This guide focuses on the transaction index and mini block explorer commands.

---

## Transaction Lookup

Use:

```bash
python3 src/qchain.py node-transaction 5001 <tx_hash>
```

Equivalent endpoint:

```text
GET /transactions/<tx_hash>
```

The result can be:

```text
location = mempool
location = confirmed
404 if unknown
```

---

## Address Transaction History

Use:

```bash
python3 src/qchain.py node-address-transactions 5001 <address>
```

Equivalent endpoint:

```text
GET /addresses/<address>/transactions
```

The response includes:

```text
count
confirmed_count
pending_count
transactions
```

---

## Example Workflow

```bash
bash scripts/start_docker_testnet.sh

python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallet-create bob
python3 src/qchain.py wallet-create miner

python3 src/qchain.py node-mine 5001 alice
python3 src/qchain.py node-send 5001 alice bob 10 --fee 2
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-mine 5002 miner
python3 src/qchain.py node-address-transactions 5001 <bob_address>
```

---

## Persistent Files

Transaction-related files:

```text
mempool.json
tx_index.json
```

`mempool.json` stores pending transactions.

`tx_index.json` stores confirmed transaction metadata from the active main chain.

---

## Tests

```bash
python3 -m pytest
```

Expected:

```text
37 passed
```
