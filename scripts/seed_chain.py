"""Put the demo's evidence on a public chain, so a judge can check it instead of trusting us.

Everything this writes is ours: we register the agents, we make the payments, we write the praise.
That is stated wherever the data appears. The point is not that this is wild data, it is that every
claim the check makes can be opened in a block explorer and recomputed by anyone.

    python scripts/seed_chain.py --plan     # what it would send, no transactions
    python scripts/seed_chain.py            # send them

Keys live in .env, which is gitignored, and are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from eth_account import Account
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"

IDENTITY = Web3.to_checksum_address("0x8004A818BFB912233c491871b3d84c89A494BD9e")
REPUTATION = Web3.to_checksum_address("0x8004B663056A597Dffe9eCcC1965A193B7388713")

IDENTITY_ABI = json.loads(
    '[{"inputs":[],"name":"register","outputs":[{"type":"uint256"}],"stateMutability":"nonpayable","type":"function"},'
    '{"anonymous":false,"inputs":[{"indexed":true,"type":"uint256","name":"agentId"},{"indexed":false,"type":"string","name":"agentURI"},'
    '{"indexed":true,"type":"address","name":"owner"}],"name":"Registered","type":"event"}]'
)
REPUTATION_ABI = json.loads(
    '[{"inputs":[{"type":"uint256","name":"agentId"},{"type":"int128","name":"value"},{"type":"uint8","name":"valueDecimals"},'
    '{"type":"string","name":"tag1"},{"type":"string","name":"tag2"},{"type":"string","name":"endpoint"},'
    '{"type":"string","name":"feedbackURI"},{"type":"bytes32","name":"feedbackHash"}],'
    '"name":"giveFeedback","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
)

# Who exists in the story. Roles, not identities.
CAST = [
    ("datehound", "DateHound"),
    ("papertrail", "PaperTrail"),
    ("quill", "Quill"),
    ("margin", "Margin"),
    ("circle1", "Circle 1"),
    ("circle2", "Circle 2"),
    ("circle3", "Circle 3"),
    ("stranger1", "Stranger A"),
    ("stranger2", "Stranger B"),
    ("stranger3", "Stranger C"),
    ("stranger4", "Stranger D"),
    ("bigcustomer", "Big customer"),
    ("smallcustomer", "Small customer"),
]

FUND_EACH = Web3.to_wei(0.004, "ether")
PAY_SMALL = Web3.to_wei(0.0002, "ether")


def read_env() -> dict:
    values = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def write_env(values: dict) -> None:
    ENV.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    ENV.chmod(0o600)


def wallets(env: dict) -> dict[str, Account]:
    """Load this project's throwaway wallets, creating them on first use. Never printed."""
    raw = env.get("SEED_WALLETS", "")
    keys = json.loads(raw) if raw else {}
    changed = False
    for role, _ in CAST:
        if role not in keys:
            keys[role] = Account.create().key.hex()
            changed = True
    if changed:
        env["SEED_WALLETS"] = json.dumps(keys)
        write_env(env)
    return {role: Account.from_key(k) for role, k in keys.items()}


class Chain:
    def __init__(self, rpc: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 60}))
        self.identity = self.w3.eth.contract(address=IDENTITY, abi=IDENTITY_ABI)
        self.reputation = self.w3.eth.contract(address=REPUTATION, abi=REPUTATION_ABI)
        self.chain_id = self.w3.eth.chain_id
        # The node's count lags for a moment after a transaction lands, so the next one would reuse
        # a nonce and be rejected. Keep our own count and take whichever is higher.
        self._nonces: dict[str, int] = {}

    def next_nonce(self, address: str) -> int:
        reported = self.w3.eth.get_transaction_count(address, "pending")
        nonce = max(reported, self._nonces.get(address, 0))
        self._nonces[address] = nonce + 1
        return nonce

    def send(self, account: Account, tx: dict) -> str:
        tx.setdefault("chainId", self.chain_id)
        tx["nonce"] = self.next_nonce(account.address)
        tx.setdefault("maxFeePerGas", self.w3.eth.gas_price * 2)
        tx.setdefault("maxPriorityFeePerGas", self.w3.to_wei(1, "gwei"))
        if "gas" not in tx:
            tx["gas"] = int(self.w3.eth.estimate_gas({**tx, "from": account.address}) * 1.3)
        signed = account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=240)
        if receipt.status != 1:
            raise RuntimeError(f"transaction failed: {h.hex()}")
        return h.hex() if str(h.hex()).startswith("0x") else "0x" + h.hex()

    def transfer(self, sender: Account, to: str, value: int) -> str:
        return self.send(sender, {"to": Web3.to_checksum_address(to), "value": value, "gas": 21000})

    def register(self, account: Account) -> tuple[int, str]:
        tx = self.identity.functions.register().build_transaction(
            {"from": account.address, "nonce": 0}
        )
        h = self.send(account, tx)
        receipt = self.w3.eth.get_transaction_receipt(h)
        events = self.identity.events.Registered().process_receipt(receipt)
        return int(events[0]["args"]["agentId"]), h

    def praise(self, author: Account, agent_id: int, payment_tx: str, tag2: str) -> str:
        tx = self.reputation.functions.giveFeedback(
            agent_id, 100, 0, "agent3-vouch", tag2, "", payment_tx, bytes(32)
        ).build_transaction({"from": author.address, "nonce": 0})
        return self.send(author, tx)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="print what would be sent and stop")
    parser.add_argument("--out", default=str(ROOT / "data" / "sepolia-seeded.json"))
    args = parser.parse_args()

    env = read_env()
    rpc = env.get("SEPOLIA_RPC") or os.environ.get("SEPOLIA_RPC") or "https://ethereum-sepolia-rpc.publicnode.com"
    funder_key = env.get("SEED_FUNDER_KEY") or os.environ.get("SEED_FUNDER_KEY", "")
    if not funder_key:
        print("SEED_FUNDER_KEY is not set in .env. Nothing was sent.")
        return 2

    chain = Chain(rpc)
    funder = Account.from_key(funder_key)
    cast = wallets(env)

    balance = chain.w3.eth.get_balance(funder.address)
    print(f"chain {chain.chain_id}, funder {funder.address[:10]}… holds {chain.w3.from_wei(balance, 'ether'):.4f} ETH")
    print(f"{len(cast)} wallets to fund at {chain.w3.from_wei(FUND_EACH, 'ether')} ETH each")

    if args.plan:
        for role, label in CAST:
            print(f"  {role:<14} {cast[role].address}")
        return 0

    # 1. gas for everyone
    for role, _ in CAST:
        account = cast[role]
        if chain.w3.eth.get_balance(account.address) >= FUND_EACH // 2:
            continue
        chain.transfer(funder, account.address, FUND_EACH)
        print(f"funded {role}", flush=True)

    # 2. everyone registers an agent identity
    agents: dict[str, dict] = {}
    for role, label in CAST:
        agent_id, tx = chain.register(cast[role])
        agents[role] = {"agent_id": agent_id, "label": label, "address": cast[role].address, "register_tx": tx}
        print(f"registered {role} as agent {agent_id}", flush=True)

    settlements: list[dict] = []
    feedback: list[dict] = []

    def paid_job(payer_role: str, payee_role: str, value: int, tag: str) -> None:
        tx = chain.transfer(cast[payer_role], cast[payee_role].address, value)
        settlements.append(
            {
                "ref": tx,
                "payer_agent": agents[payer_role]["agent_id"],
                "payee_agent": agents[payee_role]["agent_id"],
                "amount": float(chain.w3.from_wei(value, "ether")) * 1_000_000,
                "token": "SepoliaETH",
                "tx": tx,
                "completed": True,
            }
        )
        praise_tx = chain.praise(cast[payer_role], agents[payee_role]["agent_id"], tx, tag)
        feedback.append(
            {
                "agent_id": agents[payee_role]["agent_id"],
                "author": cast[payer_role].address,
                "value": 100,
                "tag": tag,
                "ref": tx,
                "tx": praise_tx,
            }
        )
        print(f"  {payer_role} paid {payee_role} and wrote praise", flush=True)

    # 3. PaperTrail: four separate operators paid it for completed work
    for stranger, amount in [("stranger1", 90), ("stranger2", 90), ("stranger3", 90), ("stranger4", 90)]:
        paid_job(stranger, "papertrail", PAY_SMALL, "settled")

    # 4. Quill: nearly all of its money came from one customer
    paid_job("bigcustomer", "quill", PAY_SMALL * 5, "settled")
    paid_job("smallcustomer", "quill", PAY_SMALL, "settled")

    # 5. DateHound: payments that go out and come back, plus praise attached to nothing
    for circle in ["circle1", "circle2", "circle3"]:
        paid_job(circle, "datehound", PAY_SMALL, "settled")
        back = chain.transfer(cast["datehound"], cast[circle].address, PAY_SMALL)
        # The return leg is a payment like any other and has to be recorded as one. Leaving it out
        # would hide exactly what the check is looking for.
        settlements.append(
            {
                "ref": back,
                "payer_agent": agents["datehound"]["agent_id"],
                "payee_agent": agents[circle]["agent_id"],
                "amount": float(chain.w3.from_wei(PAY_SMALL, "ether")) * 1_000_000,
                "token": "SepoliaETH",
                "tx": back,
                "completed": True,
            }
        )
        print(f"  datehound paid {circle} back", flush=True)
    for circle in ["circle1", "circle2", "circle3"]:
        for _ in range(3):
            tx = chain.praise(cast[circle], agents["datehound"]["agent_id"], "", "praise")
            feedback.append(
                {"agent_id": agents["datehound"]["agent_id"], "author": cast[circle].address, "value": 100, "tag": "praise", "ref": "", "tx": tx}
            )
    print("  circle wrote praise with no payment attached")

    # 6. Margin: praise with nothing behind it at all
    for stranger in ["stranger1", "stranger2", "stranger3"]:
        tx = chain.praise(cast[stranger], agents["margin"]["agent_id"], "", "praise")
        feedback.append(
            {"agent_id": agents["margin"]["agent_id"], "author": cast[stranger].address, "value": 100, "tag": "praise", "ref": "", "tx": tx}
        )

    quotes = {"datehound": 40, "papertrail": 65, "quill": 55, "margin": 35}
    dataset = {
        "source": {
            "job": "Turn the school newsletter into calendar entries for the family",
            "description": (
                "Seeded by us on Ethereum Sepolia on purpose: we registered every agent, made every payment and "
                "wrote every piece of praise. None of it is wild data. Every transaction below can be opened in a "
                "block explorer and the check recomputed from it."
            ),
            "seeded_by_us": True,
            "chain": "ethereum-sepolia",
            "chain_id": chain.chain_id,
            "identity_registry": IDENTITY,
            "reputation_registry": REPUTATION,
            "explorer": "https://sepolia.etherscan.io/tx/",
        },
        "agents": [
            {
                "agent_id": a["agent_id"],
                "label": a["label"],
                "operator": a["address"],
                "wallet": a["address"],
                "quote": quotes.get(role, 0),
                "skill": "documents to calendar entries" if role in quotes else "",
                "register_tx": a["register_tx"],
            }
            for role, a in agents.items()
        ],
        "settlements": settlements,
        "feedback": feedback,
    }
    Path(args.out).write_text(json.dumps(dataset, indent=2))
    print(f"\nwrote {args.out}: {len(dataset['agents'])} agents, {len(settlements)} payments, {len(feedback)} pieces of praise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
