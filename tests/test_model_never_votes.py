"""The central claim: the verdict is arithmetic, and a model cannot move it.

Saying so is cheap. These tests hand the pipeline a model that actively lies, and require the
verdict to come out identical, while also proving the liar was really called. Without that second
half the test would pass in an environment with no model at all, having checked nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from vouch.checks import Policy
from vouch.evidence import load
from vouch.pipeline import run

DATA = Path(__file__).parent.parent / "data" / "candidates.json"


class LyingNarrator:
    """Reports the opposite of whatever it is given, and counts how often it was asked."""

    def __init__(self) -> None:
        self.calls = 0
        self.saw: list[dict] = []

    def __call__(self, findings_json: str) -> str:
        self.calls += 1
        findings = json.loads(findings_json)
        self.saw.append(findings)
        flipped = "nobody" if findings["hired"] else "DateHound"
        return (
            f"Every candidate passed. Hire {flipped} for 1 unit. "
            "The claimed praise counts were all verified and no payments returned to anyone."
        )


def test_verdict_is_identical_with_and_without_a_model():
    data = load(DATA)
    policy = Policy(budget=120)

    silent = run(data, policy, narrator=None)
    liar = LyingNarrator()
    narrated = run(data, policy, narrator=liar)

    # The liar was really called. Without this, the test would pass by simply not having a model.
    assert liar.calls >= 1
    assert liar.saw and liar.saw[0]["hired"] == silent.findings["hired"]

    # And the verdict did not move, field for field.
    assert narrated.findings == silent.findings
    assert narrated.outcome.hired is not None
    assert narrated.outcome.hired.label == silent.outcome.hired.label
    assert narrated.outcome.quote == silent.outcome.quote


def test_the_liar_really_did_contradict_the_result():
    """Guards the fixture itself: if the narrator stopped lying, the test above would prove less."""
    data = load(DATA)
    policy = Policy(budget=120)
    liar = LyingNarrator()
    result = run(data, policy, narrator=liar)

    assert result.narration is not None
    assert result.outcome.hired is not None
    # the narration names a different outcome than the one that was decided
    assert result.outcome.hired.label not in result.narration


def test_refusal_also_survives_a_lying_model():
    """A budget nobody can meet must still end in nobody being hired, whatever the model says."""
    data = load(DATA)
    policy = Policy(budget=5)

    silent = run(data, policy, narrator=None)
    liar = LyingNarrator()
    narrated = run(data, policy, narrator=liar)

    assert silent.outcome.hired is None
    assert liar.calls >= 1
    assert narrated.findings == silent.findings
    assert narrated.outcome.hired is None
