#!/usr/bin/env python3
"""Exercise three real HTTP nodes in temporary directories, without Docker."""

import json
import logging
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from werkzeug.serving import make_server

import node
from http_client import fetch_json, post_json
from wallet import Wallet


class LocalNode:
    def __init__(self, directory):
        self.directory = directory
        self.port = 0

    def start(self):
        self.server = make_server("127.0.0.1", self.port, node.create_app(self.directory), threaded=True)
        self.port = self.server.server_port
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def get(self, path):
        return fetch_json(self.url + path)

    def post(self, path, data=None):
        return post_json(self.url + path, {} if data is None else data, timeout=15)


def run():
    # A separate deterministic test network, never the user's default data.
    node.DEFAULT_DIFFICULTY = 1
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    with TemporaryDirectory(prefix="qchain-smoke-") as directory, ExitStack() as stack:
        nodes = []
        for index in range(3):
            server = LocalNode(Path(directory) / str(index)).start()
            stack.callback(server.stop)
            nodes.append(server)
        a, b, c = nodes
        for first, second in ((a, b), (b, a), (b, c), (c, b)):
            first.post("/peers", {"peer": second.url})
        assert a.post("/peers/discover")["discovered_count"] == 1
        assert c.post("/peers/discover")["discovered_count"] == 1
        alice, bob, miner = Wallet.generate(), Wallet.generate(), Wallet.generate()
        result = a.post("/mine", {"miner_address": alice.address})
        assert all(item["success"] for item in result["broadcast_results"])
        assert {server.get("/status")["height"] for server in nodes} == {1}

        transaction = alice.create_transaction(bob.address, 10, 1, fee=2)
        a.post("/transactions", {"transaction": transaction.to_dict()})
        assert all(server.get("/mempool")["size"] == 1 for server in nodes)
        b.stop()
        b.start()
        assert b.get("/mempool")["size"] == 1
        b.post("/mine", {"miner_address": miner.address})
        assert all(server.get(f"/balances/{bob.address}")["balance"] == 10 for server in nodes)
        assert all(server.get(f"/balances/{miner.address}")["balance"] == 52 for server in nodes)

        # A new node downloads actual headers and missing block bodies over HTTP.
        newcomer = LocalNode(Path(directory) / "newcomer").start()
        stack.callback(newcomer.stop)
        newcomer.post("/peers", {"peer": a.url})
        synced = newcomer.post("/sync")
        assert synced["adopted_new_chain"] and synced["downloaded_block_count"] == 2
        assert newcomer.get(f"/balances/{bob.address}")["balance"] == 10
        tips = {server.get("/status")["latest_hash"] for server in nodes + [newcomer]}
        assert len(tips) == 1
        assert all(server.get("/status")["valid"] for server in nodes + [newcomer])
        result = {
            "result": "PASS", "nodes": 3, "additional_sync_node": 1,
            "height": 2, "bob_balance": 10, "miner_balance": 52, "coin": "QCOIN",
            "checks": ["peer discovery", "triangle block broadcast", "transaction broadcast",
                       "pending transaction restart", "mining and balances", "header-first sync"],
        }
        print(json.dumps(result, indent=2))
        return result


if __name__ == "__main__":
    run()
