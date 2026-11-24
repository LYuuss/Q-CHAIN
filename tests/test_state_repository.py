"""Mission 002-C1: repository injection and commit-before-publish invariants."""

from copy import deepcopy
import json

import pytest

from blockchain import Blockchain
from state_repository import JsonChainRepository
from storage_utils import StatePersistenceError
from wallet import Wallet


class MemoryRepository:
    def __init__(self):
        self.data = None
        self.commits = 0
        self.before_commit = None

    def exists(self):
        return self.data is not None

    def load(self):
        return deepcopy(self.data)

    def commit(self, snapshot):
        if self.before_commit:
            self.before_commit(snapshot)
        self.data = deepcopy(snapshot)
        self.commits += 1


def test_json_repository_round_trip_and_detached_snapshot(tmp_path):
    path = tmp_path / "chain.json"
    repository = JsonChainRepository(path)
    chain = Blockchain(difficulty=1, storage_path=path, repository=repository)
    miner = Wallet.generate()
    assert chain.mine_pending_transactions(miner.address)
    snapshot = chain.snapshot()
    assert snapshot == json.loads(path.read_text())
    snapshot["chain"][1]["transactions"][0]["amount"] = 0
    assert chain.get_balance(miner.address) == 50
    assert chain.snapshot() == repository.load()
    reopened = Blockchain(difficulty=1, repository=repository)
    assert reopened.snapshot() == chain.snapshot()
    assert reopened.get_state() == chain.get_state()


def test_repository_injection_and_rejection_no_commit():
    repository = MemoryRepository()
    chain = Blockchain(difficulty=1, repository=repository)
    alice, bob = Wallet.generate(), Wallet.generate()
    assert repository.commits == 1
    assert not chain.add_transaction(alice.create_transaction(bob.address, 1, 1))
    assert repository.commits == 1
    assert not chain.replace_chain_if_better(chain.chain)
    assert repository.commits == 1
    assert chain.add_external_block(chain.latest_block())[0] is False
    assert repository.commits == 1


@pytest.mark.parametrize("operation", ["mine", "transaction", "external", "reorg"])
@pytest.mark.parametrize("fail", [False, True])
def test_transition_commits_before_publishing(operation, fail):
    repository = MemoryRepository()
    chain = Blockchain(difficulty=1, repository=repository)
    alice, bob = Wallet.generate(), Wallet.generate()
    assert chain.mine_pending_transactions(alice.address)

    if operation in {"external", "reorg"}:
        peer_repo = MemoryRepository()
        peer_repo.data = chain.snapshot()
        peer = Blockchain(difficulty=1, repository=peer_repo)
        assert peer.mine_pending_transactions(bob.address)

    before = chain.snapshot()
    state_before = chain.get_state()
    commits_before = repository.commits
    observations = []

    def observe(candidate):
        assert chain.snapshot() == before
        assert chain.get_state() == state_before
        assert candidate != before
        observations.append(deepcopy(candidate))
        if fail:
            raise StatePersistenceError("injected repository failure")

    repository.before_commit = observe

    def execute():
        if operation == "mine":
            return chain.mine_pending_transactions(bob.address)
        if operation == "transaction":
            return chain.add_transaction(alice.create_transaction(bob.address, 10, 1))
        if operation == "external":
            return chain.add_external_block(peer.latest_block())[0]
        return chain.replace_chain_if_better(peer.chain)

    if fail:
        with pytest.raises(StatePersistenceError, match="injected"):
            execute()
        assert chain.persistence_failed
        assert [block.to_dict() for block in chain.chain] == before["chain"]
        assert [tx.to_dict() for tx in chain.mempool] == before["mempool"]
        assert (chain.balances, chain.nonces) == state_before
        assert repository.data == before
        assert repository.commits == commits_before
        with pytest.raises(StatePersistenceError):
            chain.snapshot()
    else:
        assert execute()
        assert chain.snapshot() == observations[0] == repository.data
        assert repository.commits == commits_before + 1
        reopened = Blockchain(difficulty=1, repository=repository)
        assert reopened.snapshot() == chain.snapshot()
        assert reopened.get_state() == chain.get_state()
    assert len(observations) == 1


def test_corrupt_json_is_not_reinitialized(tmp_path):
    path = tmp_path / "chain.json"
    path.write_text("{ broken", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid state file"):
        Blockchain(difficulty=1, repository=JsonChainRepository(path))
    assert path.read_text() == "{ broken"
