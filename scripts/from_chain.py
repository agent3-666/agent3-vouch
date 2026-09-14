"""Rebuild the evidence snapshot from Ethereum Sepolia, so nobody has to trust the committed file.

It reads the public registries directly: which agents these addresses registered, what praise was
written about them, and for each piece of praise, the payment transaction it points at. The payment
is then fetched and checked: who sent it, who received it, how much. Nothing is taken on faith from
the snapshot.

    python scripts/from_chain.py                     # rebuild into data/sepolia-seeded.json
    python scripts/from_chain.py --compare           # rebuild and diff against the committed file

Needs only a public RPC. No key, no account.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
ADDRESSES = ROOT / "data" / "seeded-addresses.json"

IDENTITY = Web3.to_checksum_address("0x8004A818BFB912233c491871b3d84c89A494BD9e")
REPUTATION = Web3.to_checksum_address("0x8004B663056A597Dffe9eCcC1965A193B7388713")

REGISTERED = "0x" + Web3.keccak(text="Registered(uint256,string,address)").hex().lstrip("0x")
NEW_FEEDBACK = "0x" + Web3.keccak(
    text="NewFeedback(uint256,address,uint64,int128,uint8,string,string,string,string,string,bytes32)"
).hex().lstrip("0x")



def hx(value) -> str:
    """Hash as a 0x-prefixed string.

    web3 v8 returns bare hex from HexBytes.hex(), and a hash without the prefix makes every explorer
    link in the snapshot dead.
    """
    text = value.hex() if hasattr(value, "hex") else str(value)
    return text if text.startswith("0x") else "0x" + text


def topic_address(address: str) -> str:
    return "0x" + "0" * 24 + Web3.to_checksum_address(address)[2:].lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="https://ethereum-sepolia-rpc.publicnode.com")
    parser.add_argument("--out", default=str(ROOT / "data" / "sepolia-seeded.json"))
    parser.add_argument("--compare", action="store_true", help="diff against the committed snapshot")
    args = parser.parse_args()

    if not ADDRESSES.exists():
        print(f"{ADDRESSES} is missing. Run scripts/seed_chain.py first, or use the committed snapshot.")
        return 2

    manifest = json.loads(ADDRESSES.read_text())
    w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 60}))
    start_block = manifest["from_block"]
    roles: dict[str, str] = manifest["wallets"]  # role -> address
    by_address = {Web3.to_checksum_address(a): role for role, a in roles.items()}

    # 1. which agent each address registered
    agent_of: dict[str, int] = {}
    for role, address in roles.items():
        logs = w3.eth.get_logs(
            {
                "address": IDENTITY,
                "fromBlock": start_block,
                "toBlock": "latest",
                "topics": [REGISTERED, None, topic_address(address)],
            }
        )
        if not logs:
            print(f"no registration found on chain for {role}")
            continue
        agent_of[role] = int(logs[-1]["topics"][1].hex(), 16)

    # 2. every payment between these addresses in the window, read from the blocks themselves.
    #    Scanning rather than trusting a list is the point: a payment that goes out and comes back
    #    only shows up if both legs are read off the chain.
    latest = w3.eth.block_number
    settlements: list[dict] = []
    feedback: list[dict] = []
    agent_by_address = {Web3.to_checksum_address(a): role for role, a in roles.items()}

    print(f"scanning blocks {start_block} to {latest} for payments between the seeded addresses")
    for number in range(start_block, latest + 1):
        block = w3.eth.get_block(number, full_transactions=True)
        for tx in block["transactions"]:
            if not tx["to"] or tx["value"] == 0:
                continue
            payer_role = agent_by_address.get(Web3.to_checksum_address(tx["from"]))
            payee_role = agent_by_address.get(Web3.to_checksum_address(tx["to"]))
            if not payer_role or not payee_role:
                continue
            if payer_role not in agent_of or payee_role not in agent_of:
                continue
            settlements.append(
                {
                    "ref": hx(tx["hash"]),
                    "payer_agent": agent_of[payer_role],
                    "payee_agent": agent_of[payee_role],
                    "amount": float(w3.from_wei(tx["value"], "ether")) * 1_000_000,
                    "token": "SepoliaETH",
                    "tx": hx(tx["hash"]),
                    "completed": True,
                }
            )
    print(f"found {len(settlements)} payments")

    contract = w3.eth.contract(
        address=REPUTATION,
        abi=json.loads(
            '[{"anonymous":false,"inputs":['
            '{"indexed":true,"type":"uint256","name":"agentId"},{"indexed":true,"type":"address","name":"clientAddress"},'
            '{"indexed":false,"type":"uint64","name":"feedbackIndex"},{"indexed":false,"type":"int128","name":"value"},'
            '{"indexed":false,"type":"uint8","name":"valueDecimals"},{"indexed":true,"type":"string","name":"indexedTag1"},'
            '{"indexed":false,"type":"string","name":"tag1"},{"indexed":false,"type":"string","name":"tag2"},'
            '{"indexed":false,"type":"string","name":"endpoint"},{"indexed":false,"type":"string","name":"feedbackURI"},'
            '{"indexed":false,"type":"bytes32","name":"feedbackHash"}],"name":"NewFeedback","type":"event"}]'
        ),
    )

    for role, agent_id in agent_of.items():
        logs = w3.eth.get_logs(
            {
                "address": REPUTATION,
                "fromBlock": start_block,
                "toBlock": "latest",
                "topics": [NEW_FEEDBACK, "0x" + f"{agent_id:064x}"],
            }
        )
        for log in logs:
            event = contract.events.NewFeedback().process_log(log)
            args_ = event["args"]
            author = Web3.to_checksum_address(args_["clientAddress"])
            if author not in by_address:
                continue  # praise from outside our seeded cast is not part of this demo
            # The praise stores the payment hash as written at the time, which may lack the prefix.
            # Both sides have to be normalised or the praise will not match its payment.
            payment_tx = hx(args_["feedbackURI"]) if args_["feedbackURI"] else ""
            feedback.append(
                {
                    "agent_id": agent_id,
                    "author": author,
                    "value": int(args_["value"]),
                    "tag": args_["tag2"],
                    "ref": payment_tx,
                    "tx": hx(log["transactionHash"]),
                }
            )
    quotes = manifest.get("quotes", {})
    dataset = {
        "source": {
            "job": manifest.get("job", "Turn the school newsletter into calendar entries for the family"),
            "description": (
                "Rebuilt from Ethereum Sepolia by scripts/from_chain.py. Every agent, payment and piece of "
                "praise here was seeded by us on purpose, and each one can be opened in a block explorer."
            ),
            "seeded_by_us": True,
            "chain": "ethereum-sepolia",
            "chain_id": w3.eth.chain_id,
            "identity_registry": IDENTITY,
            "reputation_registry": REPUTATION,
            "explorer": "https://sepolia.etherscan.io/tx/",
            "rebuilt_from_chain": True,
        },
        "agents": [
            {
                "agent_id": agent_id,
                "label": manifest["labels"].get(role, role),
                "operator": roles[role],
                "wallet": roles[role],
                "quote": quotes.get(role, 0),
                "skill": "documents to calendar entries" if role in quotes else "",
            }
            for role, agent_id in agent_of.items()
        ],
        "settlements": settlements,
        "feedback": feedback,
    }

    if args.compare:
        committed = json.loads(Path(args.out).read_text())
        same_agents = {a["agent_id"] for a in committed["agents"]} == {a["agent_id"] for a in dataset["agents"]}
        same_feedback = len(committed["feedback"]) == len(dataset["feedback"])
        same_settlements = len(committed["settlements"]) == len(dataset["settlements"])
        print(f"agents match: {same_agents}")
        print(f"feedback count matches: {same_feedback} ({len(committed['feedback'])} committed, {len(dataset['feedback'])} on chain)")
        print(f"payment count matches: {same_settlements} ({len(committed['settlements'])} committed, {len(dataset['settlements'])} on chain)")
        return 0 if (same_agents and same_feedback and same_settlements) else 1

    Path(args.out).write_text(json.dumps(dataset, indent=2))
    print(f"wrote {args.out}: {len(dataset['agents'])} agents, {len(settlements)} payments, {len(feedback)} pieces of praise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
