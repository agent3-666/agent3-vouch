"""Who gets hired, or why nobody does.

The rule is boring on purpose: among the candidates that survived the background check and quote
within budget, take the cheapest. Refusing is a normal outcome, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import Check, Policy
from .evidence import Dataset


@dataclass
class Outcome:
    hired: Check | None
    quote: float
    rejected: list[tuple[Check, str]]
    reason: str

    @property
    def is_hire(self) -> bool:
        return self.hired is not None


def decide(data: Dataset, checks: list[Check], policy: Policy) -> Outcome:
    eligible: list[tuple[Check, float]] = []
    rejected: list[tuple[Check, str]] = []

    for check in checks:
        agent = data.by_id[check.agent_id]
        if not check.passed:
            rejected.append((check, "; ".join(f.detail for f in check.failures)))
            continue
        if agent.quote > policy.budget:
            rejected.append((check, f"quotes {agent.quote:.0f}, above the budget of {policy.budget:.0f}"))
            continue
        eligible.append((check, agent.quote))

    if not eligible:
        return Outcome(
            hired=None,
            quote=0.0,
            rejected=rejected,
            reason="No candidate passed the background check within budget. Nobody was hired and no money moved.",
        )

    eligible.sort(key=lambda pair: (pair[1], -pair[0].verified_volume))
    winner, quote = eligible[0]
    return Outcome(
        hired=winner,
        quote=quote,
        rejected=rejected,
        reason=f"{winner.label} passed every check and quotes {quote:.0f}, within the budget.",
    )
