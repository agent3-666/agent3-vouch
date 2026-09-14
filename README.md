# Agent3 Vouch

**Before your agent spends your money on another agent, check the other agent out.**

You are starting to let an agent do things for you. The moment it needs a *second* agent to do part of the job, you are trusting a stranger you have never seen, chosen by software, paid with your money. People solve this by asking around for a reference. Agents have nowhere to ask.

Vouch is the reference check. Give it a job and a budget. It finds the agents offering to do it, and for each one does the digging a careful person would do and nobody has time for: who runs it, which of its finished jobs were actually paid for, and what is left of its reputation once the praise that nothing backs is set aside. Then it either hires the one that holds up, or tells you none of them did and stops.

**See it without installing anything: https://agent3-vouch-production.up.railway.app** — the same
report this repository produces, with every payment linked to its transaction on Ethereum Sepolia.

## Run it

It is a Strands agent. The agent calls the checking tools itself, works through the candidates one at
a time, and reports what came back.

```bash
pip install -r requirements.txt
python run.py --agent          # Bedrock by default; a judge with AWS credentials runs this unchanged
```

**It also finishes with no model at all.** The verdict is arithmetic, so the same tools produce the
same answer when nothing is reachable:

```bash
python run.py                  # stock Python 3.9+, nothing installed, no account
```

That second line is the point of the design rather than a fallback: a control that stops working when
a model is unavailable is not much of a control.

## What you see when you run it

The candidate with the most praise and the lowest price does not survive the check.

```
DateHound   (agent #10282, asks 40)
  claimed  ############............ 12
  verified ........................ 0
  [PASS] praise-is-backed-by-paid-work: 3 of 12 pieces of praise point at a job that was completed and paid
  [FAIL] the-money-did-not-come-back: 3 pieces of praise rest on payments that returned to the payer, across 3 operators
  [FAIL] paid-by-enough-different-people: 0 independent operators have paid this agent for completed work, 3 required

PaperTrail   (agent #10283, asks 65)
  claimed  ####.................... 4
  verified ####.................... 4
  [PASS] praise-is-backed-by-paid-work: 4 of 4 pieces of praise point at a job that was completed and paid
  [PASS] the-money-did-not-come-back: 0 pieces of praise rest on payments that returned to the payer
  [PASS] paid-by-enough-different-people: 4 independent operators have paid this agent for completed work, 3 required

HIRED: PaperTrail for 65
```

Then PaperTrail does the actual job, and you get a file you can open:

```
PaperTrail did the job: 3 events written to out/school-events.ics
  Wed 23 Sep 18:30  Year 4 parents evening at school hall
  Fri 02 Oct 09:00  Non-uniform day for the harvest appeal
  Thu 15 Oct 09:15  Class 4B assembly, families welcome at main hall
```

Double-click the `.ics` and the school term is in the family calendar. That is the everyday job: the newsletter came in, the dates came out, and the agent that handled it was one you had a reason to trust.

## What it checks, and why each rule exists

| Rule | What it asks |
|---|---|
| praise-is-backed-by-paid-work | Does this praise point at a job that was finished and paid for, by the person writing it? |
| not-written-by-itself | Was it written by the same operator that runs the agent? |
| the-money-did-not-come-back | Did the payment behind the praise return to whoever made it? |
| paid-by-enough-different-people | How many separate operators have actually paid this agent? |
| not-carried-by-a-single-customer | Is the record one customer, or several? |
| has-handled-this-much-money-before | Has it handled at least as much money as you are about to hand over? |

Every one of those is counted from public records. **The check says only what the records show.** When praise fails, the finding is that no completed, paid job can be pointed at, or that the money behind it went back where it came from. It does not say who anyone is, whether accounts belong to one person, or whether anybody lied. Those would be guesses, and a background check made of guesses is worth nothing.

## Why the verdict is arithmetic

A model never decides anything here. Counting payments, payers, and whether money came back is arithmetic, and arithmetic is the same on a day the model is down.

If you do point it at a model (`--explain`), the model is handed a decision that has already been made and asked to put it in plain words. It is never asked what the answer is.

That is a strong claim, so it has a test with teeth. `tests/test_model_never_votes.py` runs the pipeline with a model that actively lies, one that claims everybody passed and names the wrong winner, then asserts the verdict is identical field for field to the run with no model at all. It also asserts the liar was really called, because otherwise the test would pass in an environment that simply has no model and would have proved nothing.

## The evidence is on a public chain, and we put it there

The candidates, their payments and their praise live on **Ethereum Sepolia**, in the public ERC-8004 registries:

- Identity registry `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- Reputation registry `0x8004B663056A597Dffe9eCcC1965A193B7388713`

**We seeded all of it ourselves.** We registered every agent, sent every payment and wrote every piece of praise, including the circle whose payments come back to them. None of it is wild data and nothing here should be read as a finding about anyone real. What it buys is that you do not have to take our word for any of it: every transaction is in `data/sepolia-seeded.json` with its hash, and you can open each one in a block explorer and recompute the check yourself.

```bash
python scripts/seed_chain.py --plan   # the wallets it would use, no transactions
python scripts/from_chain.py          # rebuild the snapshot from the chain
python run.py --data data/sepolia-seeded.json
```

`run.py` reads the committed snapshot by default, so the project runs with no network at all. Rebuilding from the chain is how you check the snapshot is honest.

## Built with Strands Agents SDK

`vouch/agent.py` builds the agent; `vouch/tools.py` registers the six rules as its tools:
`list_candidates`, `background_check`, `hiring_decision`. The agent loop is the SDK's. The model
provider defaults to Amazon Bedrock, so `python run.py --agent` works unchanged for anyone with AWS
credentials, and `VOUCH_MODEL_HOST` points it at a local Ollama for anyone without.

`tests/test_strands_loop.py` drives that loop with a scripted model provider and asserts the tools
were offered to the model, that one was dispatched, that its result came back into the conversation,
and that the loop terminated. That is a test of our wiring. It is not evidence about how any
particular model behaves, and nothing here claims otherwise.

## Tests

```bash
python -m pytest tests -q          # 15 tests
python scripts/mutation_check.py   # delete each rule, its test must fail
```

Passing tests prove nothing by themselves, so `mutation_check.py` deletes each rule's condition one at a time and requires the test that covers it to fail. It refuses two results that look like success and are not: a test filter that matched nothing, and a mutant that failed to import. The rule with no test of its own is reported as layered rather than counted as proven.

## Layout

```
run.py                     the whole thing, start here
vouch/checks.py            the rules, one function, no model
vouch/evidence.py          what the records look like
vouch/decision.py          who gets hired, or nobody
vouch/worker.py            the job itself: newsletter in, calendar out
vouch/tools.py             the check, as Strands tools
vouch/narrate.py           optional: a model puts the result into words
scripts/seed_chain.py      puts the demo evidence on Ethereum Sepolia
scripts/from_chain.py      reads it back into a snapshot
scripts/build_site.py      renders the page from the same pipeline
scripts/mutation_check.py  removes each rule and requires its test to fail
```
