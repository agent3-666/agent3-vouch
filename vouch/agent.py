"""The Strands agent that does the reference check.

The agent drives the work: it looks at who is offering, checks each one, asks for the hiring
decision, and reports back. The tools it calls are the six rules, and those return numbers counted
from public records, so what the agent reports is what the records say.

A model is what makes the agent able to explain itself and to work through candidates one at a time.
What it cannot do is decide who passes. That comes back from `hiring_decision`, which is arithmetic,
so the same control still works on a day the model is unreachable. `run.py` without `--agent` runs
exactly those tools directly.

Default model provider is Bedrock, so a judge with AWS credentials runs this unchanged.
"""

from __future__ import annotations

import os

from strands import Agent

from .tools import background_check, hiring_decision, list_candidates

SYSTEM = """You check out agents before your owner's money is spent on one of them.

Work in this order:
1. call list_candidates to see who is offering to do the job
2. call background_check on every single candidate, one at a time
3. call hiring_decision to get the result
4. report: for each candidate, what was claimed against what stands up, then who was hired, or that
   nobody was and why

Rules you must keep:
- the tools decide, you do not. Never overturn a finding, never call a candidate acceptable when its
  check failed, and never invent a number that did not come from a tool.
- say only what the findings say. A failed check means no completed, paid job could be pointed at, or
  that the money behind the praise went back to whoever sent it. It does not mean the accounts belong
  to one person, and it does not mean anyone lied. Do not speculate about who anyone is.
- be brief and concrete. Give counts and amounts, not adjectives.
"""


def build_agent(model=None) -> Agent:
    """A Strands agent with the background check wired in as tools.

    model=None uses the Strands default (Amazon Bedrock). Set VOUCH_MODEL_HOST to point at a local
    Ollama instead, which is how this runs without an AWS account.
    """
    if model is None:
        host = os.environ.get("VOUCH_MODEL_HOST")
        if host:
            from strands.models.ollama import OllamaModel

            model = OllamaModel(host=host, model_id=os.environ.get("VOUCH_MODEL", "q38fn"))

    kwargs = {"tools": [list_candidates, background_check, hiring_decision], "system_prompt": SYSTEM}
    if model is not None:
        kwargs["model"] = model
    return Agent(**kwargs)


def check_out_the_candidates(agent: Agent, job: str, budget: float) -> str:
    """Ask the agent to do the whole job and hand back what it said."""
    return str(
        agent(
            f"The job is: {job}. The budget is {budget:.0f}. "
            "Check out every candidate and tell me who to hire, or that nobody qualifies."
        )
    )
