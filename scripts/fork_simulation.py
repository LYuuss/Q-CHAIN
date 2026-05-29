import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))

from blockchain import Blockchain
from wallet import Wallet


def configure_simulation_chain(chain: Blockchain) -> None:
    """
    For this simulation, we disable frequent difficulty changes by using
    a very large adjustment interval.

    This keeps all branches at the same difficulty, so the heavier chain
    will simply be the one with more valid mined blocks.
    """
    chain.initial_difficulty = 3
    chain.difficulty = 3
    chain.target_block_time = 10
    chain.difficulty_adjustment_interval = 1000
    chain.min_difficulty = 1
    chain.max_difficulty = 8


def create_chain(storage_path: Path) -> Blockchain:
    chain = Blockchain(
        difficulty=3,
        mining_reward=50,
        storage_path=str(storage_path),
        auto_load=False,
    )

    configure_simulation_chain(chain)
    chain.save_to_disk()

    return chain


def clone_chain(source: Blockchain, storage_path: Path) -> Blockchain:
    clone = Blockchain(
        difficulty=source.initial_difficulty,
        mining_reward=source.mining_reward,
        storage_path=str(storage_path),
        auto_load=False,
    )

    configure_simulation_chain(clone)

    clone.chain = deepcopy(source.chain)
    clone.balances, clone.nonces = clone.compute_state_for_chain(clone.chain)
    clone.mempool = []
    clone.difficulty = clone.calculate_next_difficulty()
    clone.save_to_disk()

    return clone


def print_chain_summary(name: str, chain: Blockchain) -> None:
    print(f"\n{name}")
    print("-" * len(name))
    print(f"Height: {len(chain.chain) - 1}")
    print(f"Latest hash: {chain.latest_block().hash}")
    print(f"Next difficulty: {chain.calculate_next_difficulty()}")
    print(f"Cumulative work: {chain.calculate_cumulative_work()}")
    print(f"Valid: {chain.is_valid()}")


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="qchain_fork_simulation_"))

    try:
        print("QChain local fork simulation")
        print("============================")
        print()
        print(f"Temporary simulation data: {temp_dir}")

        alice = Wallet.generate()
        miner_a = Wallet.generate()
        miner_b = Wallet.generate()

        base_chain = create_chain(temp_dir / "base_chain.json")

        print("\nCreating base chain...")
        base_chain.mine_pending_transactions(miner_address=alice.address)
        base_chain.mine_pending_transactions(miner_address=alice.address)

        print_chain_summary("Base chain before fork", base_chain)

        branch_a = clone_chain(base_chain, temp_dir / "branch_a.json")
        branch_b = clone_chain(base_chain, temp_dir / "branch_b.json")

        print("\nFork created.")
        print("Branch A and Branch B start from the same history.")

        print("\nMining 1 block on Branch A...")
        branch_a.mine_pending_transactions(miner_address=miner_a.address)

        print("\nMining 2 blocks on Branch B...")
        branch_b.mine_pending_transactions(miner_address=miner_b.address)
        branch_b.mine_pending_transactions(miner_address=miner_b.address)

        print_chain_summary("Branch A", branch_a)
        print_chain_summary("Branch B", branch_b)

        lighter_candidate = deepcopy(branch_a.chain)

        print("\nTrying to replace Branch A with Branch B...")
        accepted = branch_a.replace_chain_if_better(deepcopy(branch_b.chain))

        print()
        print(f"Replacement accepted: {accepted}")
        print_chain_summary("Branch A after replacement attempt", branch_a)

        print("\nTrying to replace the current chain with the old lighter Branch A...")
        accepted_lighter = branch_a.replace_chain_if_better(lighter_candidate)

        print()
        print(f"Replacement accepted: {accepted_lighter}")
        print_chain_summary("Final selected chain", branch_a)

        print("\nSimulation result")
        print("-----------------")

        if accepted and not accepted_lighter:
            print("Success: QChain selected the valid chain with higher cumulative work.")
        else:
            print("Unexpected result: check chain validation or cumulative work logic.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()