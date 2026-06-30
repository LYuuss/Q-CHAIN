# QChain Usage Guide

This guide focuses on safer wallet and storage behavior.

---

## Run Tests

```bash
python3 -m pytest
```

Expected:

```text
50 passed
```

---

## Wallet Creation

```bash
python3 src/qchain.py wallet-create alice
```

Wallet files are stored under:

```text
data/wallets/
```

Wallet JSON files are now written atomically.

---

## Wallet Loading

Wallet loading rejects missing or invalid wallet JSON.

This is intentional.

A corrupted wallet file should not be silently replaced by a new wallet because it may contain an encrypted private key.

---

## Useful Commands

```bash
python3 src/qchain.py wallet-create alice
python3 src/qchain.py wallets

python3 src/qchain.py node-status 5001
python3 src/qchain.py node-mempool 5001
python3 src/qchain.py node-transaction 5001 <tx_hash>
python3 src/qchain.py node-address-transactions 5001 <address>
python3 src/qchain.py node-sync 5001
```
