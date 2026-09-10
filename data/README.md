# Local runtime data

QChain creates chains, node indexes, pools, peers, and wallets here on first use.
These generated files are ignored by Git. Never commit private keys or keystores.

Use `QCHAIN_DATA_DIR=/absolute/path` to change the default data root, or pass
`--data-dir` to the CLI or node. Stop the node before copying its entire directory
for a consistent backup. Wallets live separately under `wallets/`.

Historical demo data and example wallets were removed from tracking in
v0.2.3-alpha. Any keys present in earlier commits are public demo keys.
Create new wallets for your own experiments.
