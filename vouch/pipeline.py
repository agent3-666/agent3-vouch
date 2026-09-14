"""One way through the work, used by the command line and by the tests.

The narrator is injected rather than imported, so a test can hand in a model that lies and show the
verdict does not move.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol

from .checks import Check, Policy, check_all
from .decision import Outcome, decide
from .evidence import Dataset


class Narrator(Protocol):
    def __call__(self, findings_json: str) -> str | None: ...


@dataclass
class Result:
    checks: list[Check]
    outcome: Outcome
    findings: dict
    narration: str | None


def findings_of(data: Dataset, checks: list[Check], outcome: Outcome, policy: Policy) -> dict:
    return {
        "job": data.source.get("job"),
        "budget": policy.budget,
        "candidates": [
            {
                "label": c.label,
                "claimed_praise": c.raw_praise,
                "verified_praise": c.verified_praise,
                "verified_volume": c.verified_volume,
                "distinct_funders": c.distinct_funders,
                "passed": c.passed,
                "findings": [{"rule": f.rule, "passed": f.passed, "detail": f.detail} for f in c.findings],
            }
            for c in checks
        ],
        "hired": outcome.hired.label if outcome.hired else None,
        "quote": outcome.quote,
        "reason": outcome.reason,
    }


def run(data: Dataset, policy: Policy, narrator: Narrator | Callable[[str], str | None] | None = None) -> Result:
    """Check every candidate, decide, and only then let a narrator describe what was decided.

    The order is the point: by the time a narrator sees anything, `outcome` already exists and is
    never passed back in. Nothing a narrator returns can change a verdict.
    """
    checks = check_all(data, policy)
    outcome = decide(data, checks, policy)
    findings = findings_of(data, checks, outcome, policy)

    narration: str | None = None
    if narrator is not None:
        narration = narrator(json.dumps(findings))

    return Result(checks=checks, outcome=outcome, findings=findings, narration=narration)
