"""Render the page from the same pipeline the command line uses.

The page is generated, never hand-written, so what a visitor reads cannot drift away from what the
checker actually decided.

    python scripts/build_site.py                      # uses data/candidates.json
    python scripts/build_site.py --data data/sepolia-seeded.json
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vouch.checks import Policy
from vouch.evidence import load
from vouch.pipeline import run
from vouch.worker import do_the_job

ROOT = Path(__file__).resolve().parent.parent

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0a0a0a; color: #f2f2f2;
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif; }
.wrap { max-width: 980px; margin: 0 auto; padding: 40px 20px 72px; }
h1 { font-size: 30px; margin: 0 0 6px; letter-spacing: -0.4px; }
.sub { color: #9a9a9a; margin: 0 0 28px; }
.job { border: 1px solid #262626; border-radius: 12px; padding: 18px 20px; margin-bottom: 26px; background: #0e0e0e; }
.job b { color: #d4e85a; }
.card { border: 1px solid #262626; border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; background: #0e0e0e; }
.card.win { border-color: #d4e85a; }
.card.out { opacity: .82; }
.head { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; justify-content: space-between; }
.name { font-size: 19px; font-weight: 600; }
.quote { color: #9a9a9a; font-size: 13px; }
.bars { margin: 14px 0 10px; }
.bar { display: flex; align-items: center; gap: 10px; margin: 5px 0; font-size: 13px; }
.bar .label { width: 78px; color: #9a9a9a; }
.bar .track { flex: 1; height: 12px; background: #1b1b1b; border-radius: 6px; overflow: hidden; }
.bar .fill { height: 100%; }
.bar .claimed { background: #4a4a4a; }
.bar .verified { background: #d4e85a; }
.bar .n { width: 30px; text-align: right; color: #cfcfcf; }
ul.rules { list-style: none; padding: 0; margin: 10px 0 0; }
ul.rules li { padding: 5px 0; border-top: 1px solid #1b1b1b; font-size: 13.5px; color: #cfcfcf; }
.tag { display: inline-block; width: 46px; font-weight: 600; font-size: 11px; letter-spacing: .06em; }
.pass .tag { color: #d4e85a; }
.fail .tag { color: #ff8b6b; }
.verdict { border: 1px solid #d4e85a; border-radius: 12px; padding: 20px; margin: 26px 0 16px; background: #10120a; }
.verdict h2 { margin: 0 0 6px; font-size: 20px; }
.events { margin: 10px 0 0; padding-left: 18px; color: #cfcfcf; }
.note { color: #9a9a9a; font-size: 13px; border-top: 1px solid #1b1b1b; margin-top: 30px; padding-top: 16px; }
a { color: #d4e85a; }
code { background: #1b1b1b; padding: 1px 6px; border-radius: 4px; font-size: 12.5px; }
.evidence-h { font-size: 18px; margin: 30px 0 10px; }
table.evidence { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.evidence th { text-align: left; color: #9a9a9a; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #262626; }
table.evidence td { padding: 7px 8px; border-bottom: 1px solid #1b1b1b; color: #cfcfcf; }
"""


def bar(label: str, value: int, of: int, kind: str) -> str:
    width = 0 if of == 0 else round(100 * value / of)
    return (
        f'<div class="bar"><span class="label">{label}</span>'
        f'<span class="track"><span class="fill {kind}" style="width:{width}%"></span></span>'
        f'<span class="n">{value}</span></div>'
    )


def build(data_path: Path, budget: float, out: Path) -> Path:
    data = load(data_path)
    policy = Policy(budget=budget)
    result = run(data, policy)
    checks, outcome = result.checks, result.outcome
    explorer = data.source.get("explorer", "")
    most_claimed = max((c.raw_praise for c in checks), default=1) or 1

    cards = []
    for check in checks:
        agent = data.by_id[check.agent_id]
        hired = outcome.hired is not None and outcome.hired.agent_id == check.agent_id
        rules = "".join(
            f'<li class="{"pass" if f.passed else "fail"}"><span class="tag">'
            f'{"PASS" if f.passed else "FAIL"}</span>{html.escape(f.detail)}</li>'
            for f in check.findings
        )
        link = f"{agent.wallet[:10]}…"
        cards.append(
            f'<div class="card {"win" if hired else "out"}">'
            f'<div class="head"><span class="name">{html.escape(check.label)}</span>'
            f'<span class="quote">asks {agent.quote:.0f} · agent #{agent.agent_id} · {link}</span></div>'
            f'<div class="bars">{bar("claimed", check.raw_praise, most_claimed, "claimed")}'
            f'{bar("verified", check.verified_praise, most_claimed, "verified")}</div>'
            f'<div class="quote">{check.distinct_funders} independent operators have paid it for finished work, '
            f'{check.verified_volume:.0f} in verified volume</div>'
            f'<ul class="rules">{rules}</ul></div>'
        )

    if outcome.is_hire:
        events = do_the_job(ROOT / "data" / "newsletter.txt", ROOT / "site" / "school-events.ics")
        items = "".join(
            f"<li>{e.start:%a %d %b %H:%M} — {html.escape(e.title)}"
            + (f" <span class=\"quote\">{html.escape(e.location)}</span>" if e.location else "")
            + "</li>"
            for e in events
        )
        verdict = (
            f'<div class="verdict"><h2>Hired {html.escape(outcome.hired.label)} for {outcome.quote:.0f}</h2>'
            f"<p>{html.escape(outcome.reason)}</p>"
            f"<p>It did the job. Three dates from the newsletter, ready for the family calendar:</p>"
            f'<ul class="events">{items}</ul>'
            f'<p><a href="school-events.ics" download>Download school-events.ics</a> and open it in your calendar.</p></div>'
        )
    else:
        verdict = (
            '<div class="verdict"><h2>Nobody hired</h2>'
            f"<p>{html.escape(outcome.reason)}</p></div>"
        )

    source = data.source
    provenance = (
        f'<p><b>Where this evidence comes from.</b> {html.escape(source.get("description", ""))}</p>'
        if source.get("seeded_by_us")
        else ""
    )

    # The evidence itself, one row per transaction, so a visitor can open any of it.
    evidence = ""
    if explorer:
        hired_id = outcome.hired.agent_id if outcome.hired else None
        rows = []
        for settlement in data.settlements:
            payer = data.by_id.get(settlement.payer_agent)
            payee = data.by_id.get(settlement.payee_agent)
            if not payer or not payee:
                continue
            note = ""
            if payee.agent_id == hired_id:
                note = "payment to the agent that was hired"
            elif any(
                s.payer_agent == settlement.payee_agent and s.payee_agent == settlement.payer_agent
                for s in data.settlements
            ):
                note = "one leg of a payment that came back"
            rows.append(
                f"<tr><td>{html.escape(payer.label)} paid {html.escape(payee.label)}</td>"
                f"<td>{settlement.amount:.0f}</td><td>{html.escape(note)}</td>"
                f'<td><a href="{explorer}{settlement.tx}">{settlement.tx[:18]}…</a></td></tr>'
            )
        evidence = (
            "<h2 class=\"evidence-h\">Every payment, on chain</h2>"
            '<table class="evidence"><tr><th>who paid whom</th><th>amount</th><th></th><th>transaction</th></tr>'
            + "".join(rows)
            + "</table>"
        )

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent3 Vouch</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>Agent3 Vouch</h1>
<p class="sub">Before your agent spends your money on another agent, check the other agent out.</p>
<div class="job"><b>The job:</b> {html.escape(source.get("job", ""))}<br>
<b>Budget:</b> {budget:.0f} · praise has to point at work that was paid for, from at least
{policy.min_distinct_funders} separate payers, none of them worth more than
{policy.max_share_per_funder:.0%} of the total.</div>
{"".join(cards)}
{verdict}
{evidence}
<div class="note">{provenance}
<p>The checking is arithmetic: counting payments, payers, and whether money came back. It runs with
no model and no account, and a model is never asked what the verdict should be. Run it yourself with
<code>python run.py</code>.</p></div>
</div></body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "sepolia-seeded.json"))
    parser.add_argument("--budget", type=float, default=120.0)
    parser.add_argument("--out", default=str(ROOT / "site" / "index.html"))
    args = parser.parse_args()
    written = build(Path(args.data), args.budget, Path(args.out))
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
