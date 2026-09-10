# Docker testnet

The Compose configuration runs three HTTP nodes on an isolated Docker network.
Install Docker with the Compose plugin. The host CLI still requires the Python
runtime dependencies from the root README.

| Node | Host URL | URL announced to Docker peers | Host state directory |
| --- | --- | --- | --- |
| node1 | `http://127.0.0.1:5001` | `http://node1:5000` | `data/docker/node1/` |
| node2 | `http://127.0.0.1:5002` | `http://node2:5000` | `data/docker/node2/` |
| node3 | `http://127.0.0.1:5003` | `http://node3:5000` | `data/docker/node3/` |

The host ports bind only to loopback. Inside each container, the server listens
on `0.0.0.0:5000`. Its health check queries the lightweight `/health` endpoint.

## Start and use

```bash
bash scripts/start_docker_testnet.sh
docker compose ps
python src/qchain.py wallet-create alice
python src/qchain.py wallet-create bob
python src/qchain.py wallet-create miner
python src/qchain.py node-mine 5001 alice
python src/qchain.py node-send 5001 alice bob 10 --fee 2
python src/qchain.py node-mine 5002 miner
python src/qchain.py node-balance 5003 bob
```

The start script builds the image, starts containers, waits for node readiness,
and connects all six directed peer links. The connect script uses Docker DNS
names in the peer set; host `127.0.0.1:5002` would refer to the wrong process from
inside another container.

Wallets stay on the host under `data/wallets/`. Signing happens locally. Nodes
receive public addresses and signed transactions, never wallet files or passwords.
The local CLI chain (`mine`, `send`) is separate from the Docker testnet
(`node-mine`, `node-send`).

## Inspect and restart

```bash
bash scripts/status_all.sh
bash scripts/mempool_all.sh
python src/qchain.py node-blocks 5001 --limit 10
python src/qchain.py node-transactions 5001
python src/qchain.py node-reorgs 5001
docker compose logs --tail=100 node1
docker compose restart node2
python src/qchain.py node-sync 5002
```

Chain state, pending transactions, peers, forks, and reorg diagnostics survive
normal restarts through bind-mounted directories. Sync remains an explicit
operation; restarting a stale node does not start a background sync loop.

```bash
bash scripts/stop_docker_testnet.sh
```

Stopping containers preserves the bind-mounted data and host wallets.

## Back up or reset

Stop the testnet before copying `data/docker/` to a separate backup location.
Back up host wallets independently with `wallet-backup`.

For an intentionally fresh Docker chain:

```bash
bash scripts/reset_docker_testnet.sh
```

**This deletes `data/docker/`, including all three nodes' chains, balances,
pending transactions, pools, and journals.** It rebuilds/restarts/reconnects the
nodes. Host wallets under `data/wallets/` and the local CLI chain remain separate.

Do not use reset to repair valuable experimental history: preserve the files
and follow [storage recovery](storage-layer.md) instead.

## Validation

GitHub Actions builds the image, starts healthy nodes, and connects their peers.
The standalone `python scripts/smoke_testnet.py` exercises real HTTP discovery,
broadcasts, restart, balances, and header-first synchronization without Docker.
See [validation notes](validation.md) for what was actually run for this milestone.
