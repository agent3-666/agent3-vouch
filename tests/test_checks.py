"""One test per rule, each aimed at the candidate that rule is supposed to catch.

scripts/mutation_check.py deletes each rule's condition and requires the named test here to fail.
A test that still passes without its rule is not testing the rule.
"""

from __future__ import annotations

from pathlib import Path

from vouch.checks import Policy, check_agent, check_all, circular_payers
from vouch.decision import decide
from vouch.evidence import load

DATA = Path(__file__).parent.parent / "data" / "candidates.json"

DATEHOUND, PAPERTRAIL, QUILL, MARGIN = 101, 102, 103, 104


def _check(agent_id: int, budget: float = 120):
    return check_agent(load(DATA), agent_id, Policy(budget=budget))


def _rule(check, name: str):
    return next(f for f in check.findings if f.rule == name)


def test_praise_with_nothing_behind_it_is_caught():
    check = _check(MARGIN)
    assert _rule(check, "praise-is-backed-by-paid-work").passed is False
    assert check.raw_praise == 6
    assert check.verified_praise == 0


def test_praise_whose_payments_returned_is_caught():
    check = _check(DATEHOUND)
    assert _rule(check, "the-money-did-not-come-back").passed is False
    assert check.verified_praise == 0
    # the headline number: most praised on the page, nothing left after checking
    assert check.raw_praise == 12


def test_a_single_customer_is_not_a_track_record():
    check = _check(QUILL)
    assert _rule(check, "not-carried-by-a-single-customer").passed is False


def test_too_few_independent_payers_is_caught():
    check = _check(QUILL)
    assert _rule(check, "paid-by-enough-different-people").passed is False


def test_agent_that_has_not_handled_this_much_money_is_caught():
    # PaperTrail's verified volume is 360, so a budget of 400 is more than it has ever handled.
    check = _check(PAPERTRAIL, budget=400)
    assert _rule(check, "has-handled-this-much-money-before").passed is False


def test_self_written_praise_is_dropped():
    data = load(DATA)
    check = check_agent(data, DATEHOUND, Policy(budget=120))
    rule = _rule(check, "not-written-by-itself")
    # DateHound's operator wrote about its own agent; that praise carries no weight either way.
    assert rule.passed is True
    assert check.verified_praise == 0


def test_the_candidate_with_real_customers_passes():
    check = _check(PAPERTRAIL)
    assert check.passed is True
    assert check.distinct_funders == 4
    assert check.verified_volume == 360


def test_circular_payers_are_identified_by_money_returning():
    data = load(DATA)
    circular = circular_payers(data, DATEHOUND)
    # three operators paid DateHound and were paid back at least as much
    assert len(circular) == 3


def test_the_cheapest_best_reviewed_candidate_is_not_hired():
    data = load(DATA)
    policy = Policy(budget=120)
    checks = check_all(data, policy)
    outcome = decide(data, checks, policy)

    # Ranked by raw reputation, DateHound is first and cheapest.
    assert checks[0].label == "DateHound"
    assert data.by_id[DATEHOUND].quote < data.by_id[PAPERTRAIL].quote
    # It is still not the one hired.
    assert outcome.hired is not None
    assert outcome.hired.label == "PaperTrail"


def test_nobody_is_hired_when_nobody_qualifies():
    data = load(DATA)
    policy = Policy(budget=5)
    checks = check_all(data, policy)
    outcome = decide(data, checks, policy)
    assert outcome.hired is None
    assert "Nobody was hired" in outcome.reason
