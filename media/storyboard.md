# Storyboard, vouch-demo.mp4

Silent, 1280x720, 30fps, h264, 3062 frames, 102.066667 seconds. Rendered frame by frame from
`site/demo.html`; no screen was recorded. Every number on screen comes from a real run against the
on-chain snapshot.

| from | to | on screen | what the picture already says |
|---|---|---|---|
| 0:00 | 0:09 | Heading **"A school newsletter"**, subtitle "Three dates buried in it. Somebody has to put them in the family calendar." Below it the letter from Oakfield Primary School, with three dated lines: Wednesday 23 September 6.30pm parents evening, Friday 2 October non-uniform day, Thursday 15 October class assembly. | The errand, and that the dates are buried in prose. |
| 0:09 | 0:18 | Heading **"Four agents say they can do it"**, subtitle "Ranked the way you would see them: price, and how much praise they carry." Four rows: DateHound 40, 12 pieces of praise · PaperTrail 65, 4 pieces · Margin 35, 3 pieces · Quill 55, 2 pieces. | Who is offering, what they charge, how much praise each carries. That DateHound looks best and cheapest. |
| 0:18 | 0:38 | Heading **"The check runs"**, subtitle "python run.py, with no model and no account". A terminal block scrolling through the real output: candidate blocks with claimed and verified bars, PASS and FAIL lines, ending at HIRED. | That this is a real program producing real output, not a mockup. |
| 0:38 | 0:54 | Heading **"The cheapest, most praised candidate"**, subtitle "What the praise turns out to rest on". DateHound card: claimed bar 12, verified bar 0. Lines: PASS praise-is-backed-by-paid-work "3 of 12 pieces of praise point at a job that was completed and paid"; FAIL the-money-did-not-come-back "3 pieces of praise rest on payments that returned to the payer, across 3 operators"; FAIL paid-by-enough-different-people "0 independent operators"; FAIL not-carried-by-a-single-customer; FAIL has-handled-this-much-money-before "verified volume 0 against 120 required". | Twelve claimed, zero verified, and the specific reasons. |
| 0:54 | 1:08 | Heading **"The one that holds up"**, subtitle "Fewer pieces of praise, every one attached to a job somebody paid for". PaperTrail card: claimed 4, verified 4, all six lines PASS, including "4 independent operators have paid this agent for completed work, 3 required" and "the largest single payer accounts for 25% of verified volume". | Four beats twelve, and why. |
| 1:08 | 1:16 | Full screen: **"Hired PaperTrail"** in large type, under it "for 65, not the cheapest, and not the best reviewed". | The decision, and that it went against both surface signals. |
| 1:16 | 1:28 | Heading **"It did the job"**, subtitle "school-events.ics, ready to open in the calendar". Three events listed: Year 4 parents evening, Non-uniform day for the harvest appeal, Class 4B assembly families welcome. | The errand finished, with a file that exists. |
| 1:28 | 1:42 | Heading **"All of it is on a public chain"**, subtitle "Open any transaction and recompute the check yourself". A table of four Ethereum Sepolia transactions, each shown as a 0x-prefixed hash: two payments to PaperTrail, one payment to DateHound, and one row labelled "the same money going back". Footer line: we seeded this evidence ourselves, registered the agents, sent the payments and wrote the praise, none of it is wild data. | That the evidence is public and checkable, and that we put it there. |

Notes for narration: the picture already carries the numbers and the rule names, so the voice has
room for the part the screen does not say, which is why any of it matters: that an agent is about to
spend your money on a stranger, that praise anybody can write costs nothing to write, and that the
only thing that survives checking is money moving between parties that are not each other.

Two things the narration must not say, because they are not what the check found: that the accounts
belong to one person, and that anybody lied. What the check found is that no completed, paid job
could be pointed at, and that some payments went back to whoever sent them.
