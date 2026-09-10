# HTTP API reference

JSON API for trusted local testnets. Default standalone binding is
`127.0.0.1`; Docker publishes ports 5001–5003 on loopback. There is no
credential-based authorization on administration or mining endpoints.

## Read endpoints

| Method and path | Result |
| --- | --- |
| `GET /` | Endpoint discovery and node URL |
| `GET /health` | Lightweight process readiness and active height |
| `GET /status` | Version, active tip, genesis, work, validity, pools, peers, storage diagnostics |
| `GET /chain` | `summary` and full active `chain` |
| `GET /headers` | `summary` and full active `headers`, oldest first |
| `GET /blocks` | Paginated active block summaries, newest first |
| `GET /blocks/height/<height>` | Active block and confirmations at an integer height |
| `GET /blocks/<hash>` | Known block, `location`, and active-chain confirmations |
| `GET /transactions` | Paginated pending transfers first, then confirmed transactions newest first |
| `GET /transactions/<hash>` | Pending or confirmed transaction record and confirmations |
| `GET /addresses/<address>/transactions` | Paginated confirmed history oldest first, followed by pending transfers |
| `GET /balances/<address>` | Confirmed `balance`, `confirmed_nonce`, address, and coin |
| `GET /addresses/<address>/balance` | Alias for the balance endpoint |
| `GET /mempool` | `size` and pending signed transactions including their `hash` |
| `GET /orphans` | Orphan summaries, `size`, and `max_size` |
| `GET /side-branches` | Competing block summaries and `tip_hashes` |
| `GET /peers` | Configured peer URLs and count |
| `GET /reorgs` | Paginated reorganization history, newest first |

Unknown block and transaction lookups return 404 with `found: false`.
Balance/history queries require a 40-character lowercase hexadecimal address.
An address without activity has balance 0 and confirmed nonce 0.

### Pagination and confirmations

The paginated endpoints accept `?limit=50&offset=0`. Limit must be 1–100; offset
must be a nonnegative integer. Responses include `count` (page size), `total`,
`limit`, `offset`, and `has_more`, plus `blocks`, `transactions`, or `reorgs`.
Address history also includes unpaginated `confirmed_count` and `pending_count`.

```bash
curl -fsS 'http://127.0.0.1:5001/blocks?limit=10&offset=0'
curl -fsS http://127.0.0.1:5001/blocks/height/1
curl -fsS 'http://127.0.0.1:5001/transactions?limit=10'
```

Confirmations are `tip_height - block_height + 1` for the active chain and 0
for pending transactions or inactive blocks. They are computed from current
state, so a reorganization can reduce them. Pagination is a view of the state
at each request, not a stable snapshot across multiple requests.

## Write endpoints

All nonempty request bodies must be JSON objects. Malformed types return 400;
bodies over 2 MiB return 413. Payload integers must be actual integers, not
JSON booleans or floats.

### POST /transactions

Send a signed transaction object directly or in `{"transaction": {...}}`.
An optional `source` URL excludes that peer from rebroadcast. It never adds a
new peer. Build and sign transfers with `Wallet.create_transaction` or the CLI;
never send private keys or passwords to the node.

A transaction has `sender`, `receiver`, `amount`, `nonce`, `fee`, and `signature`.
The sender is a public key, while the receiver is an address. `fee` defaults to
0 for legacy payloads. Coinbase transactions cannot be broadcast.

- **201:** accepted into the mempool; includes `transaction_hash` and broadcast results.
- **200:** the exact transaction is already known.
- **400:** invalid fields/signature, nonce, funds, coinbase, or full mempool.

### POST /mine

```json
{"miner_address": "<40 lowercase hex characters>", "max_transactions": 10}
```

`max_transactions` is optional and defaults to 999. It counts regular transfers,
not the mandatory coinbase. Zero mines a reward-only block. The response includes
`mined`, `block_hash`, `old_height`, `new_height`, `miner_balance`, and broadcast,
orphan, and side-branch results. Invalid input returns 400.

Mining is synchronous and can exceed normal HTTP timeouts as difficulty rises.
The CLI allows 300 seconds for a node-mining response. A client timeout does not
cancel a server operation; inspect the node before retrying.

### POST /blocks

Body: `{"block": <serialized block>, "source": "http://peer:port"}`.
Serialized blocks contain `header`, `hash`, and `transactions`.

| Status | Meaning |
| --- | --- |
| 201 | Block appended to the active chain |
| 200 | Already known in the active chain or a pool |
| 202 | Valid block buffered as an orphan/side branch, or synchronization performed |
| 400 | Malformed block or invalid basic proof/transaction structure |
| 409 | Block rejected after contextual validation |

A 202 response can report `accepted: false` because the individual block was
buffered rather than directly appended. Check `side_branch_result`, `sync_result`,
and `/status` to determine whether a heavier chain was adopted.

### POST /peers

```json
{"peer": "http://node2:5000"}
```

`url` and `peer_url` are supported aliases. HTTP and HTTPS origins are accepted;
credentials, paths other than `/`, query strings, fragments, and invalid ports
are rejected. Scheme/host and default ports are normalized. Duplicates return
200; a newly added peer returns 201. Invalid/self peers return 400. At the
32-peer limit, the response says `added: false`. DNS aliases of the same node
are not guaranteed to be recognized as self.

### POST /peers/discover

No body required. Queries the currently known peers, validates up to 32 entries
per peer, and returns `discovered_count`, `skipped_count`, `failed_count`, and
per-peer details. Unreachable/malformed peers are reported individually. They
are retained in the configured peer set; discovery does not run periodically.

### POST /sync

No body required. Performs header-first synchronization and local candidate
validation. Returns `adopted_new_chain`, current height/work, checked peers,
downloaded block count, mempool recovery details, pool results, and errors.
A successful request can report no adoption if no valid heavier chain exists.

## Reorg journal fields

Entries contain old/new tips and heights, common ancestor height, disconnected
and connected block counts, recovered/rejected transaction counts, reason, and
Unix timestamp. `reason` is `side_branch` or `sync:<peer URL>`. Only actual fork
switches are recorded, with the most recent 100 entries retained.

## Transport limits

Peer GET/POST calls normally have a 5-second socket timeout; discovery uses
3 seconds. Response bodies are capped at 16 MiB. Header sync accepts at most
10,000 headers. These bounds suit a small prototype and are not a scalable
public-network protocol.
