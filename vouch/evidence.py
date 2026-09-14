"""The facts a background check is made of, and where they come from.

Everything here is data that exists on a public chain: who registered an agent, who paid whom,
and who wrote praise about whom. Nothing is a score handed to us by a platform.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Agent:
    agent_id: int
    label: str
    operator: str
    wallet: str
    # What this agent wants to be paid for the job we are hiring for.
    quote: float = 0.0
    skill: str = ""
    # Where its identity was registered, when the evidence came from a chain.
    register_tx: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator", self.operator.lower())
        object.__setattr__(self, "wallet", self.wallet.lower())


@dataclass(frozen=True)
class Settlement:
    """Money that actually moved for a job that was actually completed."""

    ref: str
    payer_agent: int
    payee_agent: int
    amount: float
    token: str
    tx: str
    completed: bool


@dataclass(frozen=True)
class Feedback:
    """Praise or complaint written into the public reputation registry."""

    agent_id: int
    author: str
    value: int
    tag: str
    tx: str
    # The settlement this feedback claims to be about. Empty when it claims nothing.
    ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "author", self.author.lower())


@dataclass
class Dataset:
    source: dict
    agents: list[Agent]
    settlements: list[Settlement]
    feedback: list[Feedback]
    by_id: dict[int, Agent] = field(init=False)
    by_address: dict[str, Agent] = field(init=False)

    def __post_init__(self) -> None:
        self.by_id = {a.agent_id: a for a in self.agents}
        self.by_address = {}
        for a in self.agents:
            self.by_address[a.wallet] = a
            self.by_address.setdefault(a.operator, a)

    def operator_of_address(self, address: str) -> str:
        """Who is behind this address. Falls back to the address itself when unknown."""
        agent = self.by_address.get(address.lower())
        return agent.operator if agent else address.lower()

    def feedback_for(self, agent_id: int) -> list[Feedback]:
        return [f for f in self.feedback if f.agent_id == agent_id]

    def settlement(self, ref: str) -> Settlement | None:
        return next((s for s in self.settlements if s.ref == ref), None)

    def settlements_paid_to(self, agent_id: int) -> list[Settlement]:
        return [s for s in self.settlements if s.payee_agent == agent_id and s.completed]

    def settlements_paid_by_operator(self, operator: str) -> list[Settlement]:
        out = []
        for s in self.settlements:
            payer = self.by_id.get(s.payer_agent)
            if payer and payer.operator == operator.lower() and s.completed:
                out.append(s)
        return out


def load(path: str | Path) -> Dataset:
    raw = json.loads(Path(path).read_text())
    return Dataset(
        source=raw.get("source", {}),
        agents=[Agent(**a) for a in raw["agents"]],
        settlements=[Settlement(**s) for s in raw["settlements"]],
        feedback=[Feedback(**f) for f in raw["feedback"]],
    )
