import json
import os

from block import Block
from transaction import Transaction
from config import (
    COIN_NAME,
    TARGET_BLOCK_TIME_SECONDS,
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    MIN_DIFFICULTY,
    MAX_DIFFICULTY,
)

class Blockchain:
    def __init__(
        self,
        difficulty: int = 4,
        mining_reward: int = 50,
        storage_path: str = "../data/chain.json",
        auto_load: bool = True,
    ):
        self.difficulty = difficulty
        self.initial_difficulty = difficulty
        self.mining_reward = mining_reward
        self.storage_path = storage_path

        self.target_block_time = TARGET_BLOCK_TIME_SECONDS
        self.difficulty_adjustment_interval = DIFFICULTY_ADJUSTMENT_INTERVAL
        self.min_difficulty = MIN_DIFFICULTY
        self.max_difficulty = MAX_DIFFICULTY

        self.chain: list[Block] = []
        self.balances: dict[str, int] = {}
        self.nonces: dict[str, int] = {}
        self.mempool: list[Transaction] = []

        if auto_load and os.path.exists(self.storage_path):
            self.load_from_disk()
        else:
            self.chain = [self.create_genesis_block()]
            self.save_to_disk()

    def create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            previous_hash="0",
            transactions=[],
            difficulty=self.difficulty,
        )
        genesis.mine()
        return genesis

    def latest_block(self) -> Block:
        return self.chain[-1]

    def get_state(self) -> tuple[dict[str, int], dict[str, int]]:
        return self.balances.copy(), self.nonces.copy()

    def get_balance(self, address: str) -> int:
        return self.balances.get(address, 0)

    def get_next_nonce(self, address: str) -> int:
        return self.nonces.get(address, 0) + 1

    def save_to_disk(self) -> None:
        directory = os.path.dirname(self.storage_path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        data = {
            "difficulty": self.difficulty,
            "mining_reward": self.mining_reward,
            "target_block_time": self.target_block_time,
            "difficulty_adjustment_interval": self.difficulty_adjustment_interval,
            "chain": [block.to_dict() for block in self.chain],
            "mempool": [tx.to_dict() for tx in self.mempool],
        }

        with open(self.storage_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    def load_from_disk(self) -> None:
        with open(self.storage_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.difficulty = data.get("difficulty", self.difficulty)
        self.mining_reward = data.get("mining_reward", self.mining_reward)
        
        self.initial_difficulty = data.get(
            "initial_difficulty",
            data.get("difficulty", self.initial_difficulty),
        )

        self.target_block_time = data.get(
            "target_block_time",
            self.target_block_time,
        )

        self.difficulty_adjustment_interval = data.get(
            "difficulty_adjustment_interval",
            self.difficulty_adjustment_interval,
        )

        self.chain = [
            Block.from_dict(block_data)
            for block_data in data.get("chain", [])
        ]

        if len(self.chain) == 0:
            self.chain = [self.create_genesis_block()]

        self.mempool = [
            Transaction.from_dict(tx_data)
            for tx_data in data.get("mempool", [])
        ]

        self.rebuild_state()

        if not self.is_valid():
            raise ValueError("Loaded blockchain is invalid.")

        self.clean_mempool()

        self.difficulty = self.calculate_next_difficulty()

        self.save_to_disk()

    def rebuild_state(self) -> None:
        balances: dict[str, int] = {}
        nonces: dict[str, int] = {}

        for block in self.chain[1:]:
            if not self._apply_block_transactions(block, balances, nonces):
                raise ValueError("Cannot rebuild state: invalid block detected.")

        self.balances = balances
        self.nonces = nonces

    def clean_mempool(self) -> None:
        valid_transactions: list[Transaction] = []

        temp_balances = self.balances.copy()
        temp_nonces = self.nonces.copy()

        for tx in self.mempool:
            test_balances = temp_balances.copy()
            test_nonces = temp_nonces.copy()

            if self._apply_regular_transaction(tx, test_balances, test_nonces):
                valid_transactions.append(tx)
                temp_balances = test_balances
                temp_nonces = test_nonces

        removed = len(self.mempool) - len(valid_transactions)

        if removed > 0:
            print(f"Removed {removed} invalid transaction(s) from mempool.")

        self.mempool = valid_transactions

    def add_transaction(self, transaction: Transaction) -> bool:
        if transaction.is_coinbase():
            print("Coinbase transactions cannot be added to the mempool.")
            return False

        temp_balances = self.balances.copy()
        temp_nonces = self.nonces.copy()

        for pending_tx in self.mempool:
            if not self._apply_regular_transaction(
                pending_tx,
                temp_balances,
                temp_nonces,
            ):
                print("Current mempool contains an invalid transaction.")
                return False

        if not self._apply_regular_transaction(
            transaction,
            temp_balances,
            temp_nonces,
        ):
            print("Invalid transaction. Rejected from mempool.")
            return False

        self.mempool.append(transaction)
        self.save_to_disk()

        print("Transaction added to mempool.")
        return True

    def mine_pending_transactions(
        self,
        miner_address: str,
        max_transactions: int | None = None,
    ) -> bool:
        selected_transactions = self._select_mempool_transactions(max_transactions)

        block_added = self._add_block(
            transactions=selected_transactions,
            miner_address=miner_address,
        )

        if block_added:
            selected_ids = {id(tx) for tx in selected_transactions}

            self.mempool = [
                tx for tx in self.mempool
                if id(tx) not in selected_ids
            ]

            self.save_to_disk()

        return block_added

    def _select_mempool_transactions(
        self,
        max_transactions: int | None,
    ) -> list[Transaction]:
        selected: list[Transaction] = []

        temp_balances = self.balances.copy()
        temp_nonces = self.nonces.copy()

        remaining = sorted(
            self.mempool,
            key=lambda tx: tx.fee,
            reverse=True,
        )

        progress = True

        while remaining and progress:
            progress = False
            next_remaining: list[Transaction] = []

            for tx in remaining:
                if max_transactions is not None and len(selected) >= max_transactions:
                    next_remaining.append(tx)
                    continue

                test_balances = temp_balances.copy()
                test_nonces = temp_nonces.copy()

                if self._apply_regular_transaction(
                    tx,
                    test_balances,
                    test_nonces,
                ):
                    selected.append(tx)
                    temp_balances = test_balances
                    temp_nonces = test_nonces
                    progress = True
                else:
                    next_remaining.append(tx)

            remaining = next_remaining

        return selected

    def _add_block(
        self,
        transactions: list[Transaction],
        miner_address: str,
    ) -> bool:
        block_index = len(self.chain)
        total_fees = sum(tx.fee for tx in transactions)

        coinbase = Transaction.create_coinbase(
            receiver=miner_address,
            amount=self.mining_reward + total_fees,
            block_index=block_index,
        )

        all_transactions = [coinbase] + transactions

        temp_balances = self.balances.copy()
        temp_nonces = self.nonces.copy()

        next_difficulty = self.calculate_next_difficulty()

        new_block = Block(
            index=block_index,
            previous_hash=self.latest_block().hash,
            transactions=[tx.to_dict() for tx in all_transactions],
            difficulty=next_difficulty,
        )

        if not self._apply_block_transactions(
            new_block,
            temp_balances,
            temp_nonces,
        ):
            print("Invalid block. Rejected.")
            return False

        print(
            f"Mining block {block_index} with "
            f"{len(transactions)} transaction(s), "
            f"{total_fees} {COIN_NAME} fee(s), "
            f"difficulty={next_difficulty}..."
        )

        new_block.mine()
        print(f"Block mined: {new_block.hash}")

        self.chain.append(new_block)
        self.balances = temp_balances
        self.nonces = temp_nonces
        self.difficulty = self.calculate_next_difficulty()

        return True

    def _apply_block_transactions(
        self,
        block: Block,
        balances: dict[str, int],
        nonces: dict[str, int],
    ) -> bool:
        if not block.verify_merkle_root():
            return False

        if block.index == 0:
            return len(block.transactions) == 0

        if len(block.transactions) == 0:
            return False

        transactions = [
            Transaction.from_dict(tx_data)
            for tx_data in block.transactions
        ]

        coinbase = transactions[0]
        regular_transactions = transactions[1:]

        if any(tx.fee < 0 for tx in regular_transactions):
            return False

        total_fees = sum(tx.fee for tx in regular_transactions)
        expected_coinbase_amount = self.mining_reward + total_fees

        if not self._apply_coinbase_transaction(
            coinbase,
            balances,
            expected_block_index=block.index,
            expected_amount=expected_coinbase_amount,
        ):
            return False

        for tx in regular_transactions:
            if tx.is_coinbase():
                return False

            if not self._apply_regular_transaction(tx, balances, nonces):
                return False

        return True

    def _apply_coinbase_transaction(
        self,
        tx: Transaction,
        balances: dict[str, int],
        expected_block_index: int,
        expected_amount: int,
    ) -> bool:
        if not tx.is_coinbase():
            return False

        if not tx.verify():
            return False

        if tx.amount != expected_amount:
            return False

        if tx.amount <= 0:
            return False

        if tx.nonce != expected_block_index:
            return False

        if not tx.receiver:
            return False

        balances[tx.receiver] = balances.get(tx.receiver, 0) + tx.amount
        return True

    def _apply_regular_transaction(
        self,
        tx: Transaction,
        balances: dict[str, int],
        nonces: dict[str, int],
    ) -> bool:
        if tx.amount <= 0:
            return False

        if tx.fee < 0:
            return False

        if not tx.receiver:
            return False

        if not tx.verify():
            return False

        sender_address = tx.sender_address()

        if sender_address is None:
            return False

        expected_nonce = nonces.get(sender_address, 0) + 1

        if tx.nonce != expected_nonce:
            return False

        total_cost = tx.amount + tx.fee

        if balances.get(sender_address, 0) < total_cost:
            return False

        balances[sender_address] = balances.get(sender_address, 0) - total_cost
        balances[tx.receiver] = balances.get(tx.receiver, 0) + tx.amount
        nonces[sender_address] = tx.nonce

        return True

    def is_valid(self) -> bool:
        if len(self.chain) == 0:
            return False

        genesis = self.chain[0]

        if genesis.index != 0:
            return False

        if genesis.previous_hash != "0":
            return False

        if genesis.hash != genesis.compute_hash():
            return False

        if not genesis.hash.startswith("0" * genesis.difficulty):
            return False

        balances: dict[str, int] = {}
        nonces: dict[str, int] = {}

        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            expected_difficulty = self._calculate_expected_difficulty_for_index(
                block_index=i,
                chain=self.chain,
            )

            if current.difficulty != expected_difficulty:
                return False

            if current.index != i:
                return False

            if current.hash != current.compute_hash():
                return False

            if current.previous_hash != previous.hash:
                return False

            if not current.hash.startswith("0" * current.difficulty):
                return False

            if not self._apply_block_transactions(current, balances, nonces):
                return False

        return True

    def print_mempool(self) -> None:
        print(f"\nMempool: {len(self.mempool)} pending transaction(s)")

        for index, tx in enumerate(self.mempool, start=1):
            sender_address = tx.sender_address()
            total_cost = tx.amount + tx.fee

            print(
                f"{index}. {sender_address} -> {tx.receiver} | "
                f"amount={tx.amount} {COIN_NAME} | "
                f"fee={tx.fee} {COIN_NAME} | "
                f"total_cost={total_cost} {COIN_NAME} | "
                f"nonce={tx.nonce}"
            )

    def _clamp_difficulty(self, difficulty: int) -> int:
        return max(
            self.min_difficulty,
            min(self.max_difficulty, difficulty),
        )

    def _calculate_expected_difficulty_for_index(
        self,
        block_index: int,
        chain: list[Block],
        ) -> int:
        if block_index == 0:
            return self.initial_difficulty

        previous_difficulty = chain[block_index - 1].difficulty

        if block_index <= self.difficulty_adjustment_interval:
            return previous_difficulty

        if (block_index - 1) % self.difficulty_adjustment_interval != 0:
            return previous_difficulty

        start_index = block_index - self.difficulty_adjustment_interval
        end_index = block_index - 1

        start_block = chain[start_index]
        end_block = chain[end_index]

        actual_duration = end_block.timestamp - start_block.timestamp

        expected_duration = (
            self.difficulty_adjustment_interval - 1
        ) * self.target_block_time

        if actual_duration <= 0:
            return self._clamp_difficulty(previous_difficulty + 1)

        if actual_duration < expected_duration / 2:
            return self._clamp_difficulty(previous_difficulty + 1)

        if actual_duration > expected_duration * 2:
            return self._clamp_difficulty(previous_difficulty - 1)

        return previous_difficulty
    
    def calculate_next_difficulty(self) -> int:
        return self._calculate_expected_difficulty_for_index(
            block_index=len(self.chain),
            chain=self.chain,
        )