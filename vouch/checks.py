"""The background check itself: arithmetic and rules, no model anywhere.

A judgement about whether to trust a stranger with your money should not depend on a language
model being available, or in a good mood. Every number below is counted from public chain data and
can be recomputed by anyone. The model's only job, elsewhere, is to read this out loud.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Dataset, Feedback


@dataclass
class Finding:
    rule: str
    passed: bool
    detail: str
    numbers: dict = field(default_factory=dict)


@dataclass
class Check:
    agent_id: int
    label: str
    raw_praise: int
    raw_score: int
    verified_praise: int
    verified_volume: float
    distinct_funders: int
    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return all(f.passed for f in self.findings)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.passed]


@dataclass
class Policy:
    """What the owner asks of anyone who wants to be paid. Published, not hidden in code."""

    budget: float
    min_distinct_funders: int = 3
    min_verified_volume_ratio: float = 1.0
    max_share_per_funder: float = 0.5
    min_settlement_amount: float = 1.0


def _backed(data: Dataset, agent_id: int, f: Feedback) -> bool:
    """Is this praise attached to a job that was completed and paid to this agent?"""
    if not f.ref:
        return False
    s = data.settlement(f.ref)
    if s is None or not s.completed or s.payee_agent != agent_id:
        return False
    payer = data.by_id.get(s.payer_agent)
    if payer is None:
        return False
    # The author of the praise has to be the side that paid for it.
    return data.operator_of_address(f.author) == payer.operator


def circular_payers(data: Dataset, agent_id: int) -> set[str]:
    """Operators whose payment to this agent came back to them.

    Stated only as what the chain shows: this operator paid the agent, and the agent's side paid at
    least as much back. A payment that returns is not evidence that somebody outside was willing to
    part with money for the work. It says nothing about who these operators are, and nothing here
    claims they are one person or that their praise is untrue.
    """
    subject = data.by_id[agent_id]
    subject_agents = {a.agent_id for a in data.agents if a.operator == subject.operator}

    authors = {data.operator_of_address(f.author) for f in data.feedback_for(agent_id)}
    circular: set[str] = set()

    for author in authors:
        author_agents = {a.agent_id for a in data.agents if a.operator == author}
        paid_in = sum(
            s.amount
            for s in data.settlements
            if s.completed and s.payer_agent in author_agents and s.payee_agent in subject_agents
        )
        came_back = sum(
            s.amount
            for s in data.settlements
            if s.completed and s.payer_agent in subject_agents and s.payee_agent in author_agents
        )
        if paid_in > 0 and came_back >= paid_in:
            circular.add(author)

    return circular


def check_agent(data: Dataset, agent_id: int, policy: Policy) -> Check:
    agent = data.by_id[agent_id]
    all_feedback = data.feedback_for(agent_id)
    raw_praise = len([f for f in all_feedback if f.value > 0])
    raw_score = sum(f.value for f in all_feedback)

    findings: list[Finding] = []

    # 1. Praise that is attached to a completed, paid job.
    #
    # Each rule's condition sits on its own line marked GUARD. scripts/mutation_check.py deletes one
    # at a time, leaving the permissive default above it, and requires the matching test to fail.
    # A rule whose test still passes without it is a rule nobody is really checking.
    backed = [f for f in all_feedback if f.value > 0 and _backed(data, agent_id, f)]
    backed_ok = True
    backed_ok = len(backed) > 0  # GUARD:praise-is-backed-by-paid-work
    findings.append(
        Finding(
            rule="praise-is-backed-by-paid-work",
            passed=backed_ok,
            detail=f"{len(backed)} of {raw_praise} pieces of praise point at a job that was completed and paid",
            numbers={"backed": len(backed), "raw": raw_praise},
        )
    )

    # 2. Drop anything written by the operator about its own agents.
    independent = [f for f in backed if data.operator_of_address(f.author) != agent.operator]
    self_written = len(backed) - len(independent)
    self_ok = True
    self_ok = self_written == 0 or len(independent) > 0  # GUARD:not-written-by-itself
    findings.append(
        Finding(
            rule="not-written-by-itself",
            passed=self_ok,
            detail=f"{self_written} pieces of praise came from the same operator that runs this agent",
            numbers={"self_written": self_written},
        )
    )

    # 3. Drop praise whose payment came back to the payer.
    circular = circular_payers(data, agent_id)
    outside_ring = [f for f in independent if data.operator_of_address(f.author) not in circular]
    dropped_by_ring = len(independent) - len(outside_ring)
    circular_ok = True
    circular_ok = len(outside_ring) > 0  # GUARD:the-money-did-not-come-back
    findings.append(
        Finding(
            rule="the-money-did-not-come-back",
            passed=circular_ok,
            detail=(
                f"{dropped_by_ring} pieces of praise rest on payments that returned to the payer, "
                f"across {len(circular)} operators"
            ),
            numbers={"dropped": dropped_by_ring, "circular_operators": len(circular)},
        )
    )

    # 4. Enough different people, counted by who is behind them, not by wallet.
    funders: dict[str, float] = {}
    for f in outside_ring:
        s = data.settlement(f.ref)
        if s is None or s.amount < policy.min_settlement_amount:
            continue
        payer = data.by_id[s.payer_agent]
        funders[payer.operator] = funders.get(payer.operator, 0.0) + s.amount

    funders_ok = True
    funders_ok = len(funders) >= policy.min_distinct_funders  # GUARD:paid-by-enough-different-people
    findings.append(
        Finding(
            rule="paid-by-enough-different-people",
            passed=funders_ok,
            detail=f"{len(funders)} independent operators have paid this agent for completed work, {policy.min_distinct_funders} required",
            numbers={"funders": len(funders), "required": policy.min_distinct_funders},
        )
    )

    # 5. One big customer is not a track record.
    verified_volume = sum(funders.values())
    top_share = (max(funders.values()) / verified_volume) if verified_volume else 0.0
    spread_ok = True
    spread_ok = verified_volume > 0 and top_share <= policy.max_share_per_funder  # GUARD:not-carried-by-a-single-customer
    findings.append(
        Finding(
            rule="not-carried-by-a-single-customer",
            passed=spread_ok,
            detail=f"the largest single payer accounts for {top_share:.0%} of verified volume, limit is {policy.max_share_per_funder:.0%}",
            numbers={"top_share": round(top_share, 4)},
        )
    )

    # 6. Has handled at least as much money as we are about to hand over.
    needed = policy.budget * policy.min_verified_volume_ratio
    volume_ok = True
    volume_ok = verified_volume >= needed  # GUARD:has-handled-this-much-money-before
    findings.append(
        Finding(
            rule="has-handled-this-much-money-before",
            passed=volume_ok,
            detail=f"verified volume {verified_volume:.0f} against {needed:.0f} required for a budget of {policy.budget:.0f}",
            numbers={"verified_volume": verified_volume, "required": needed},
        )
    )

    return Check(
        agent_id=agent_id,
        label=agent.label,
        raw_praise=raw_praise,
        raw_score=raw_score,
        verified_praise=len(outside_ring),
        verified_volume=verified_volume,
        distinct_funders=len(funders),
        findings=findings,
    )


def check_all(data: Dataset, policy: Policy) -> list[Check]:
    # Only the agents actually offering to do this job.
    checks = [check_agent(data, a.agent_id, policy) for a in data.agents if a.quote > 0]
    # Best raw reputation first, which is the order a naive buyer would see.
    return sorted(checks, key=lambda c: (-c.raw_score, -c.raw_praise))
