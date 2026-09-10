"""Compatibility entry point for the QChain CLI.

Use `python src/main.py --help` or the canonical `python src/qchain.py --help`.
"""

from qchain import main


if __name__ == "__main__":
    raise SystemExit(main())
