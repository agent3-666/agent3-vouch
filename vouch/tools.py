"""The background check, exposed as Strands tools.

The same functions run whether or not a model is present. With a model, a Strands agent calls them
and writes the summary. Without one, `run.py` calls them directly and prints the numbers. The
verdict is identical either way, because the verdict is arithmetic.
"""

from __future__ import annotations

import json

from strands import tool

from .checks import Policy, check_agent, check_all
from .decision import decide
from .evidence import Dataset, load

_state: dict[str, object] = {}


def use(dataset: Dataset, policy: Policy) -> None:
    """Point the tools at a dataset and a hiring policy."""
    _state["data"] = dataset
    _state["policy"] = policy


def _data() -> Dataset:
    data = _state.get("data")
    if data is None:
        raise RuntimeError("no dataset loaded; call use(dataset, policy) first")
    return data  # type: ignore[return-value]


def _policy() -> Policy:
    policy = _state.get("policy")
    if policy is None:
        raise RuntimeError("no policy loaded; call use(dataset, policy) first")
    return policy  # type: ignore[return-value]


@tool
def list_candidates() -> str:
    """List the agents offering to do the job, with what they are asking to be paid."""
    data = _data()
    rows = [
        {
            "agent_id": a.agent_id,
            "label": a.label,
            "skill": a.skill,
            "quote": a.quote,
            "claimed_praise": len([f for f in data.feedback_for(a.agent_id) if f.value > 0]),
        }
        for a in data.agents
        if a.quote > 0
    ]
    return json.dumps(rows, indent=2)


@tool
def background_check(agent_id: int) -> str:
    """Run the full background check on one agent and return every number behind the result."""
    check = check_agent(_data(), agent_id, _policy())
    return json.dumps(
        {
            "agent_id": check.agent_id,
            "label": check.label,
            "claimed_praise": check.raw_praise,
            "verified_praise": check.verified_praise,
            "verified_volume": check.verified_volume,
            "distinct_funders": check.distinct_funders,
            "passed": check.passed,
            "findings": [
                {"rule": f.rule, "passed": f.passed, "detail": f.detail, "numbers": f.numbers}
                for f in check.findings
            ],
        },
        indent=2,
    )


@tool
def hiring_decision() -> str:
    """Check every candidate and report who, if anyone, should be hired."""
    data, policy = _data(), _policy()
    checks = check_all(data, policy)
    outcome = decide(data, checks, policy)
    return json.dumps(
        {
            "hired": outcome.hired.label if outcome.hired else None,
            "quote": outcome.quote,
            "reason": outcome.reason,
            "rejected": [{"label": c.label, "why": why} for c, why in outcome.rejected],
        },
        indent=2,
    )


def load_dataset(path: str, budget: float) -> Dataset:
    data = load(path)
    use(data, Policy(budget=budget))
    return data
