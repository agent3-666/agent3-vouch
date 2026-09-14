"""Write the public manifest the rebuild script needs: addresses, labels, quotes, start block.

Addresses only. Keys stay in .env and never appear here.
"""

from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
SEEDED = ROOT / "data" / "sepolia-seeded.json"
OUT = ROOT / "data" / "seeded-addresses.json"

ROLE_OF_LABEL = {
    "DateHound": "datehound",
    "PaperTrail": "papertrail",
    "Quill": "quill",
    "Margin": "margin",
    "Circle 1": "circle1",
    "Circle 2": "circle2",
    "Circle 3": "circle3",
    "Stranger A": "stranger1",
    "Stranger B": "stranger2",
    "Stranger C": "stranger3",
    "Stranger D": "stranger4",
    "Big customer": "bigcustomer",
    "Small customer": "smallcustomer",
}


def main() -> int:
    data = json.loads(SEEDED.read_text())
    w3 = Web3(Web3.HTTPProvider("https://ethereum-sepolia-rpc.publicnode.com", request_kwargs={"timeout": 60}))

    wallets, labels, quotes = {}, {}, {}
    first_block = None
    for agent in data["agents"]:
        role = ROLE_OF_LABEL.get(agent["label"], agent["label"].lower().replace(" ", ""))
        wallets[role] = Web3.to_checksum_address(agent["wallet"])
        labels[role] = agent["label"]
        if agent.get("quote"):
            quotes[role] = agent["quote"]
        tx = agent.get("register_tx")
        if tx:
            block = w3.eth.get_transaction(tx)["blockNumber"]
            first_block = block if first_block is None else min(first_block, block)

    manifest = {
        "chain": "ethereum-sepolia",
        "chain_id": 11155111,
        "job": data["source"]["job"],
        "from_block": first_block,
        "wallets": wallets,
        "labels": labels,
        "quotes": quotes,
    }
    OUT.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {OUT}, first block {first_block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
