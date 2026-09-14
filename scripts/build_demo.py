"""Build the page the video records, and the storyboard that goes with it.

The terminal block on that page is the real output of `python run.py`, captured here rather than
typed by hand, so the video cannot show something the code does not do.

    python scripts/build_demo.py --data data/sepolia-seeded.json
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vouch.checks import Policy  # noqa: E402
from vouch.evidence import load  # noqa: E402
from vouch.pipeline import run  # noqa: E402

# seconds each beat holds on screen
BEATS = [
    ("the-job", 9, "The school newsletter arrives. Three dates buried in it."),
    ("candidates", 9, "Four agents say they can turn it into calendar entries. Prices and praise counts."),
    ("terminal", 20, "The real output of python run.py, scrolling."),
    ("datehound", 16, "The cheapest, most praised candidate: 12 claimed, 0 verified, and why."),
    ("papertrail", 14, "The one that holds up: 4 claimed, 4 verified, paid by 4 separate operators."),
    ("hired", 8, "Hired PaperTrail for 65."),
    ("ics", 12, "It did the job. Three events, ready for the family calendar."),
    ("chain", 14, "Every payment and every piece of praise, on Ethereum Sepolia, seeded by us."),
]


def capture_run(data_path: Path) -> str:
    result = subprocess.run(
        [sys.executable, "run.py", "--data", str(data_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout


def build(data_path: Path, budget: float) -> tuple[Path, Path]:
    data = load(data_path)
    policy = Policy(budget=budget)
    result = run(data, policy)
    checks = {c.label: c for c in result.checks}
    explorer = data.source.get("explorer", "https://sepolia.etherscan.io/tx/")
    terminal = capture_run(data_path)

    newsletter = (ROOT / "data" / "newsletter.txt").read_text()

    def card(label: str) -> str:
        check = checks[label]
        agent = data.by_id[check.agent_id]
        rules = "".join(
            f'<li class="{"pass" if f.passed else "fail"}"><b>{"PASS" if f.passed else "FAIL"}</b> {html.escape(f.detail)}</li>'
            for f in check.findings
        )
        most = max(c.raw_praise for c in result.checks) or 1
        return f"""
        <div class="card">
          <div class="cardhead"><span class="name">{html.escape(label)}</span><span class="ask">asks {agent.quote:.0f}</span></div>
          <div class="bar"><span>claimed</span><i style="width:{round(100*check.raw_praise/most)}%" class="claimed"></i><b>{check.raw_praise}</b></div>
          <div class="bar"><span>verified</span><i style="width:{round(100*check.verified_praise/most)}%" class="verified"></i><b>{check.verified_praise}</b></div>
          <ul>{rules}</ul>
        </div>"""

    quotes = "".join(
        f'<div class="quotecard"><span class="name">{html.escape(c.label)}</span>'
        f'<span class="ask">{data.by_id[c.agent_id].quote:.0f}</span>'
        f'<span class="praise">{c.raw_praise} pieces of praise</span></div>'
        for c in result.checks
    )

    tx_rows = "".join(
        f'<tr><td>{html.escape(s["kind"])}</td><td><a href="{explorer}{s["tx"]}">{s["tx"][:22]}…</a></td></tr>'
        for s in (
            [{"kind": "payment to PaperTrail", "tx": t.tx} for t in data.settlements if t.payee_agent == checks["PaperTrail"].agent_id][:2]
            + [{"kind": "payment to DateHound", "tx": t.tx} for t in data.settlements if t.payee_agent == checks["DateHound"].agent_id][:1]
            + [{"kind": "the same money going back", "tx": t.tx} for t in data.settlements if t.payer_agent == checks["DateHound"].agent_id][:1]
        )
    )

    events_html = ""
    ics_path = ROOT / "site" / "school-events.ics"
    if ics_path.exists():
        lines = [ln for ln in ics_path.read_text().splitlines() if ln.startswith("SUMMARY:")]
        events_html = "".join(f"<li>{html.escape(ln.removeprefix('SUMMARY:'))}</li>" for ln in lines)

    beats_js = json.dumps([[name, seconds] for name, seconds, _ in BEATS])

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Agent3 Vouch</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0a0a0a; color:#f2f2f2; width:1280px; height:720px; overflow:hidden;
  font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif; }}
.stage {{ position:relative; width:1280px; height:720px; }}
section {{ position:absolute; inset:0; padding:46px 60px; opacity:0; transition:opacity .45s ease; }}
section.on {{ opacity:1; }}
h1 {{ font-size:34px; margin:0 0 4px; letter-spacing:-.5px; }}
h1 small {{ display:block; font-size:16px; color:#9a9a9a; font-weight:400; letter-spacing:0; margin-top:6px; }}
.letter {{ background:#111; border:1px solid #262626; border-radius:12px; padding:24px 28px; margin-top:22px;
  white-space:pre-wrap; font:14px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace; color:#d8d8d8; }}
.letter em {{ color:#d4e85a; font-style:normal; }}
.quotecard {{ display:flex; gap:20px; align-items:baseline; border:1px solid #262626; border-radius:10px;
  padding:14px 18px; margin-top:12px; background:#0e0e0e; }}
.quotecard .name {{ font-size:19px; font-weight:600; width:180px; }}
.quotecard .ask {{ color:#d4e85a; width:70px; }}
.quotecard .praise {{ color:#9a9a9a; }}
pre.term {{ background:#000; border:1px solid #262626; border-radius:10px; padding:18px 20px; margin-top:18px;
  height:560px; overflow:hidden; font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; color:#cfcfcf; }}
pre.term .scroll {{ display:block; animation:scroll 19s linear forwards; }}
@keyframes scroll {{ from {{ transform:translateY(0); }} to {{ transform:translateY(-58%); }} }}
.card {{ border:1px solid #2a2a2a; border-radius:12px; padding:20px 24px; margin-top:20px; background:#0e0e0e; }}
.card .cardhead {{ display:flex; justify-content:space-between; align-items:baseline; }}
.card .name {{ font-size:24px; font-weight:600; }}
.card .ask {{ color:#9a9a9a; }}
.bar {{ display:flex; align-items:center; gap:12px; margin:10px 0; }}
.bar span {{ width:80px; color:#9a9a9a; font-size:13px; }}
.bar i {{ height:16px; border-radius:8px; display:block; }}
.bar i.claimed {{ background:#4a4a4a; }}
.bar i.verified {{ background:#d4e85a; }}
.bar b {{ font-size:14px; color:#e8e8e8; }}
.card ul {{ list-style:none; padding:0; margin:14px 0 0; }}
.card li {{ padding:6px 0; border-top:1px solid #1c1c1c; font-size:13.5px; color:#cfcfcf; }}
.card li b {{ font-size:11px; letter-spacing:.06em; margin-right:10px; }}
.pass b {{ color:#d4e85a; }} .fail b {{ color:#ff8b6b; }}
.hired {{ margin-top:120px; text-align:center; }}
.hired .big {{ font-size:64px; font-weight:700; color:#d4e85a; letter-spacing:-1px; }}
.hired p {{ color:#9a9a9a; font-size:18px; }}
ul.events {{ margin-top:24px; font-size:20px; line-height:2; }}
table {{ margin-top:20px; border-collapse:collapse; width:100%; font-size:14px; }}
td {{ padding:9px 8px; border-bottom:1px solid #1c1c1c; color:#cfcfcf; }}
a {{ color:#d4e85a; }}
.seeded {{ margin-top:20px; color:#9a9a9a; font-size:14px; }}
</style></head>
<body><div class="stage">

<section id="the-job"><h1>A school newsletter<small>Three dates buried in it. Somebody has to put them in the family calendar.</small></h1>
<div class="letter">{html.escape(newsletter)}</div></section>

<section id="candidates"><h1>Four agents say they can do it<small>Ranked the way you would see them: price, and how much praise they carry.</small></h1>
{quotes}</section>

<section id="terminal"><h1>The check runs<small>python run.py, with no model and no account</small></h1>
<pre class="term"><span class="scroll">{html.escape(terminal)}</span></pre></section>

<section id="datehound"><h1>The cheapest, most praised candidate<small>What the praise turns out to rest on</small></h1>
{card("DateHound")}</section>

<section id="papertrail"><h1>The one that holds up<small>Fewer pieces of praise, every one attached to a job somebody paid for</small></h1>
{card("PaperTrail")}</section>

<section id="hired"><div class="hired"><div class="big">Hired PaperTrail</div>
<p>for 65, not the cheapest, and not the best reviewed</p></div></section>

<section id="ics"><h1>It did the job<small>school-events.ics, ready to open in the calendar</small></h1>
<ul class="events">{events_html}</ul></section>

<section id="chain"><h1>All of it is on a public chain<small>Open any transaction and recompute the check yourself</small></h1>
<table>{tx_rows}</table>
<p class="seeded">We seeded this evidence ourselves on Ethereum Sepolia: we registered the agents, sent the payments and wrote the praise, including the payments that come back. None of it is wild data.</p></section>

</div>
<script>
const beats = {beats_js};
const params = new URLSearchParams(location.search);
const still = params.get('beat');

if (still) {{
  // One frame, no timers: this is how the video frames are rendered.
  document.querySelectorAll('section').forEach(s => s.classList.remove('on'));
  const target = document.getElementById(still);
  if (target) target.classList.add('on');
  const scroll = parseInt(params.get('scroll') || '0', 10);
  const term = document.querySelector('#terminal .scroll');
  if (term) {{
    term.style.animation = 'none';
    term.style.transform = 'translateY(-' + scroll + 'px)';
  }}
}} else {{
  let i = 0;
  (function show() {{
    document.querySelectorAll('section').forEach(s => s.classList.remove('on'));
    const [id, secs] = beats[i];
    document.getElementById(id).classList.add('on');
    i = (i + 1) % beats.length;
    if (i !== 0) setTimeout(show, secs * 1000);
  }})();
}}
</script>
</body></html>
"""

    demo = ROOT / "site" / "demo.html"
    demo.parent.mkdir(parents=True, exist_ok=True)
    demo.write_text(page)

    at = 0
    rows = []
    for name, seconds, description in BEATS:
        rows.append(f"| {at//60}:{at%60:02d} | {seconds}s | {description} |")
        at += seconds
    storyboard = ROOT / "media" / "storyboard.md"
    storyboard.parent.mkdir(parents=True, exist_ok=True)
    storyboard.write_text(
        "# Storyboard\n\n"
        f"Silent recording, 1280x720, 30fps, {at} seconds.\n\n"
        "| starts at | holds | what is on screen |\n|---|---|---|\n" + "\n".join(rows) + "\n"
    )
    return demo, storyboard


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "sepolia-seeded.json"))
    parser.add_argument("--budget", type=float, default=120.0)
    args = parser.parse_args()
    demo, storyboard = build(Path(args.data), args.budget)
    print(f"wrote {demo}\nwrote {storyboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
