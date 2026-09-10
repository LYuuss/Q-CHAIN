"""Wire-format checks shared by consensus, wallets, and the HTTP boundary."""

import math
import re

MAX_INTEGER = 2**63 - 1
MAX_BLOCK_TRANSACTIONS = 1000  # Includes the coinbase.
MAX_MEMPOOL_TRANSACTIONS = 1000
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_FUTURE_BLOCK_SECONDS = 120


def is_integer(value, minimum=0, maximum=MAX_INTEGER):
    # bool is a subclass of int in Python, but is not a protocol integer.
    return type(value) is int and minimum <= value <= maximum


def is_hex(value, length):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def is_address(value):
    return is_hex(value, 40)


def validate_header(header):
    if not isinstance(header, dict):
        raise ValueError("Block header must be an object.")
    for field in ("index", "nonce"):
        if not is_integer(header.get(field)):
            raise ValueError(f"Block {field} must be a nonnegative integer.")
    if not is_integer(header.get("difficulty"), 1, 8):
        raise ValueError("Block difficulty must be an integer between 1 and 8.")
    timestamp = header.get("timestamp")
    if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Block timestamp must be finite and nonnegative.")
    previous = header.get("previous_hash")
    if not (header["index"] == 0 and previous == "0") and not is_hex(previous, 64):
        raise ValueError("Invalid previous block hash.")
    if not is_hex(header.get("merkle_root"), 64):
        raise ValueError("Invalid Merkle root.")
