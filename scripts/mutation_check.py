"""Delete one rule at a time and require the test that covers it to fail.

A suite that stays green when a rule is removed is decoration. Two traps are handled explicitly,
because both look exactly like success:

  * pytest exits 5 when a filter matches no tests. That is not a pass, it is nothing having run.
  * a mutant that fails to import would make every test "fail" for the wrong reason.

Run: python scripts/mutation_check.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vouch"

# rule marker -> the test that must fail once the rule is gone
SPEC = {
    "praise-is-backed-by-paid-work": "test_praise_with_nothing_behind_it_is_caught",
    "the-money-did-not-come-back": "test_praise_whose_payments_returned_is_caught",
    "not-carried-by-a-single-customer": "test_a_single_customer_is_not_a_track_record",
    "paid-by-enough-different-people": "test_too_few_independent_payers_is_caught",
    "has-handled-this-much-money-before": "test_agent_that_has_not_handled_this_much_money_is_caught",
    # not-written-by-itself is layered: the backing rule already drops that praise, so removing this
    # one alone changes nothing. Listed so the coverage check below cannot silently miss it.
    "not-written-by-itself": None,
}


def pytest(args: list[str]) -> int:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).returncode


def markers_in_source() -> set[str]:
    found = set()
    for path in SRC.rglob("*.py"):
        found.update(re.findall(r"#\s*GUARD:([a-z0-9-]+)", path.read_text()))
    return found


def main() -> int:
    print("== baseline: the suite must pass before any rule is removed")
    if pytest([]) != 0:
        print("FAIL baseline: suite is not green")
        return 1
    print("ok   baseline")

    print("== coverage: every GUARD marker must be named in this script")
    missing = markers_in_source() - set(SPEC)
    if missing:
        print(f"FAIL coverage: {', '.join(sorted(missing))} not in SPEC")
        return 1
    print("ok   coverage")

    backup = Path(tempfile.mkdtemp()) / "vouch"
    shutil.copytree(SRC, backup)
    failures = 0
    try:
        for marker, test_name in SPEC.items():
            shutil.rmtree(SRC)
            shutil.copytree(backup, SRC)

            hits = []
            for path in SRC.rglob("*.py"):
                lines = path.read_text().splitlines(keepends=True)
                kept = [ln for ln in lines if not re.search(rf"#\s*GUARD:{re.escape(marker)}\s*$", ln.rstrip())]
                if len(kept) != len(lines):
                    hits.append((path, len(lines) - len(kept)))
                    path.write_text("".join(kept))

            total = sum(n for _, n in hits)
            if total != 1:
                print(f"FAIL {marker}: matched {total} lines, expected exactly 1")
                failures += 1
                continue

            if test_name is None:
                print(f"note {marker}: layered, another rule already covers this case")
                continue

            # A filter that selects nothing exits 5 and would otherwise read as a result.
            if pytest(["--collect-only", "-k", test_name]) != 0:
                print(f"FAIL {marker}: no test named {test_name} was collected")
                failures += 1
                continue

            code = pytest(["-k", test_name])
            if code == 1:
                print(f"ok   {marker}: {test_name} turned red")
            elif code == 0:
                print(f"FAIL {marker}: {test_name} stayed green without the rule")
                failures += 1
            else:
                print(f"FAIL {marker}: pytest exited {code}, which proves nothing")
                failures += 1
    finally:
        shutil.rmtree(SRC, ignore_errors=True)
        shutil.copytree(backup, SRC)
        shutil.rmtree(backup.parent, ignore_errors=True)

    if failures:
        print(f"== {failures} rule(s) unproven")
        return 1
    print("== every rule is proven by a failing test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
