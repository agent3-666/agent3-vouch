"""Agent3 Vouch: check out the agents who want your money, then hire one, or hire nobody.

Runs with no model, no API key and no account. A trust judgement that depends on a model being
available is not a trust judgement, so the checking is arithmetic and the model, when there is one,
only puts the result into words.

    python run.py
    python run.py --budget 40
    python run.py --data data/sepolia-seeded.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vouch.checks import Policy
from vouch.evidence import load
from vouch.narrate import narrate
from vouch.pipeline import run as run_pipeline
from vouch.report import render
from vouch.worker import do_the_job

ROOT = Path(__file__).parent


def run_as_agent(args) -> int:
    """The Strands agent path: the agent calls the tools and reports what they returned."""
    from vouch.agent import build_agent, check_out_the_candidates
    from vouch.tools import load_dataset

    data = load_dataset(args.data, args.budget)
    job = data.source.get("job", "a task")
    print(f"Job: {job}\nBudget: {args.budget:.0f}\n")
    print("Running the Strands agent. It calls the checking tools itself.\n")

    agent = build_agent()
    answer = check_out_the_candidates(agent, job, args.budget)
    print(answer)

    # The agent reports; the verdict comes from the same tools either way.
    result = run_pipeline(data, Policy(budget=args.budget))
    if result.outcome.is_hire:
        events = do_the_job(args.newsletter, args.out)
        print(f"\n{result.outcome.hired.label} did the job: {len(events)} events written to {args.out}")
    return 0 if result.outcome.is_hire else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Check out agents before letting one spend your money.")
    parser.add_argument("--data", default=str(ROOT / "data" / "sepolia-seeded.json"), help="evidence to check against")
    parser.add_argument("--budget", type=float, default=120.0, help="what the job is worth to you")
    parser.add_argument("--newsletter", default=str(ROOT / "data" / "newsletter.txt"), help="the job input")
    parser.add_argument("--out", default=str(ROOT / "out" / "school-events.ics"), help="where the finished work goes")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--explain", action="store_true", help="also have a model put the result into words")
    parser.add_argument(
        "--agent",
        action="store_true",
        help="run it as the Strands agent: the agent calls the checking tools itself and reports back",
    )
    args = parser.parse_args()

    if args.agent:
        return run_as_agent(args)

    data = load(args.data)
    policy = Policy(budget=args.budget)
    result = run_pipeline(data, policy, narrator=narrate if args.explain else None)
    checks, outcome, findings = result.checks, result.outcome, result.findings

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print(render(data, checks, outcome, policy))

    if outcome.is_hire:
        events = do_the_job(args.newsletter, args.out)
        if not args.json:
            print("")
            print(f"{outcome.hired.label} did the job: {len(events)} events written to {args.out}")
            for event in events:
                where = f" at {event.location}" if event.location else ""
                print(f"  {event.start:%a %d %b %H:%M}  {event.title}{where}")
            print("")
            print("Open that file to put them in your calendar.")

    if args.explain:
        if result.narration:
            print("")
            print(result.narration)
        elif not args.json:
            print("")
            print("(No model configured, so nothing to read aloud. The result above is unchanged.)")

    return 0 if outcome.is_hire else 1


if __name__ == "__main__":
    raise SystemExit(main())
