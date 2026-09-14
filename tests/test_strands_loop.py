"""Proof that the Strands agent loop really runs our tools.

A scripted model stands in for a real one: it asks for a tool by name, and then, once it has been
handed the result, finishes. That is enough to show the machinery is wired up, that the tool was
dispatched, that its output came back into the conversation, and that the loop terminates.

What this does not show is anything about a real model's behaviour. Those are separate claims and
nothing here should be read as evidence for them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterable

import pytest
from strands.models.model import Model

from vouch.agent import build_agent
from vouch.tools import load_dataset

DATA = Path(__file__).parent.parent / "data" / "candidates.json"
PAPERTRAIL = 102


class ScriptedModel(Model):
    """Asks for background_check once, then stops. Records what it was given."""

    def __init__(self) -> None:
        self.calls = 0
        self.tool_specs_seen: list[str] = []
        self.messages_seen: list[Any] = []

    def get_config(self) -> dict:
        return {}

    def update_config(self, **kwargs: Any) -> None:
        return None

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("the scripted model only drives the tool loop")
        yield  # pragma: no cover - makes this an async generator, as the interface expects

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict]:
        self.calls += 1
        self.messages_seen = list(messages)
        if tool_specs:
            self.tool_specs_seen = [spec["name"] for spec in tool_specs]

        if self.calls == 1:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "call-1", "name": "background_check"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({"agent_id": PAPERTRAIL})}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockDelta": {"delta": {"text": "Checked one candidate and stopped."}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


@pytest.fixture
def dataset():
    return load_dataset(str(DATA), budget=120)


def test_the_agent_loop_dispatches_our_tools(dataset):
    model = ScriptedModel()
    agent = build_agent(model=model)

    result = agent("Check out the candidates.")

    # the checking tools were offered to the model by Strands
    assert {"list_candidates", "background_check", "hiring_decision"} <= set(model.tool_specs_seen)

    # the loop went round: one turn asking for a tool, one turn finishing
    assert model.calls == 2

    # the tool really ran, and its result went back into the conversation
    blob = json.dumps([m for m in agent.messages], default=str)
    assert "toolResult" in blob
    assert "PaperTrail" in blob
    assert "praise-is-backed-by-paid-work" in blob

    assert "stopped" in str(result)


def test_tools_return_the_same_numbers_the_check_does(dataset):
    """Whatever route the numbers travel, they are the same numbers."""
    from vouch.checks import Policy, check_agent
    from vouch.tools import background_check

    direct = check_agent(dataset, PAPERTRAIL, Policy(budget=120))
    through_tool = json.loads(background_check(PAPERTRAIL))

    assert through_tool["verified_praise"] == direct.verified_praise
    assert through_tool["distinct_funders"] == direct.distinct_funders
    assert through_tool["passed"] == direct.passed
