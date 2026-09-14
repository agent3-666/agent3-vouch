"""Turning the numbers into something a person reads in ten seconds."""

from __future__ import annotations

from .checks import Check, Policy
from .decision import Outcome
from .evidence import Dataset

TICK = "PASS"
CROSS = "FAIL"


def _bar(label: str, value: int, width: int = 24) -> str:
    filled = min(value, width)
    return f"{label:<9}{'#' * filled}{'.' * (width - filled)} {value}"


def candidate_block(data: Dataset, check: Check) -> str:
    agent = data.by_id[check.agent_id]
    lines = [
        f"{check.label}   (agent #{check.agent_id}, operator {agent.operator[:10]}…, quote {agent.quote:.0f})",
        "  " + _bar("claimed", check.raw_praise),
        "  " + _bar("verified", check.verified_praise),
        f"  paid by {check.distinct_funders} independent operators, {check.verified_volume:.0f} in verified volume",
    ]
    for finding in check.findings:
        mark = TICK if finding.passed else CROSS
        lines.append(f"  [{mark}] {finding.rule}: {finding.detail}")
    return "\n".join(lines)


def render(data: Dataset, checks: list[Check], outcome: Outcome, policy: Policy) -> str:
    source = data.source
    out = [
        "Agent3 Vouch",
        "=" * 72,
        f"Job: {source.get('job', 'a task')}",
        f"Budget: {policy.budget:.0f}   Required: praise backed by paid work, "
        f"{policy.min_distinct_funders}+ independent payers, no single payer above {policy.max_share_per_funder:.0%}",
        f"Evidence: {source.get('description', 'public reputation records')}",
        "",
    ]
    for check in checks:
        out.append(candidate_block(data, check))
        out.append("")

    out.append("-" * 72)
    if outcome.is_hire:
        out.append(f"HIRED: {outcome.hired.label} for {outcome.quote:.0f}")
        out.append(outcome.reason)
    else:
        out.append("NOBODY HIRED")
        out.append(outcome.reason)
        for check, why in outcome.rejected:
            out.append(f"  {check.label}: {why}")
    return "\n".join(out)
