"""Optional: a Strands agent reads the finished report out loud.

It is handed the findings and asked to phrase them. It is never asked what the verdict is, and it
cannot change one: by the time this runs, the decision has already been made by arithmetic. A trust
judgement that stops working when a model is unavailable is not a trust judgement.
"""

from __future__ import annotations

import os

SYSTEM = (
    "You explain the result of a background check to the person who asked for it. "
    "You are given findings that are already decided. Restate them in plain language, in at most "
    "six sentences. Never change a verdict, never add a number that is not in the findings, and "
    "never guess at anything you were not given."
)


def available() -> bool:
    """A model is configured only when someone has explicitly pointed us at one."""
    return bool(os.environ.get("VOUCH_MODEL_HOST") or os.environ.get("AWS_REGION"))


def narrate(findings_json: str) -> str | None:
    """Return a spoken-language summary, or None when no model is configured."""
    if not available():
        return None

    from strands import Agent

    host = os.environ.get("VOUCH_MODEL_HOST")
    if host:
        # A local OpenAI-compatible endpoint, so the demo needs no cloud account.
        from strands.models.litellm import LiteLLMModel

        model = LiteLLMModel(
            client_args={"api_key": os.environ.get("VOUCH_MODEL_KEY", "not-needed"), "api_base": host},
            model_id=os.environ.get("VOUCH_MODEL", "openai/gpt-oss"),
        )
        agent = Agent(model=model, system_prompt=SYSTEM)
    else:
        # Bedrock, for judges who would rather run it on AWS.
        agent = Agent(system_prompt=SYSTEM)

    return str(agent(f"Findings:\n{findings_json}"))
