# Open questions

Questions that wait on a decision. Each has a lasting id (Q1, Q2, …), shared with the
questions asked while MoneyKata is built: a question that is answered is removed, its answer
goes into the section it belongs to, and its id is never used again. A new question takes the
next number. Q1–Q18 are answered. Each carries a rank: **High** decides what the next change
is, **Med** decides something before the first release, **Low** can wait. The
[README](README.md#open-questions) lists them.

## Q19: The requirements written from the code — Med

**The question:** do these items say what MoneyKata should do? Each was written from the code
as built, where no requirement described what it does, and each is confirmed as it stands or
rewritten, the code following:

- **Accounts, options and prices:** S1.3.2 (an OFX file holds one account's statement),
  S1.3.3.8.1 (half a percent or $1), S1.6.1.2 (ten rounds of derivation in one check),
  S1.6.1.4 (at most 15 keys), S1.6.2.6 (a deleted transaction isn't recorded again), S1.7
  (4 days, and no link on a tie), S1.9.1–2 (the term's and rate's bounds, rounding half up),
  S3.3 (option lots oldest first), S3.6 (a close up to four days old; at the strike is out of
  the money), S4.4 (five years of backfill; the benchmarks).
- **Users and sessions:** S10.1.1, S10.1.3, S10.1.5, S10.1.7, S13.7.1, S13.7.3, S13.7.5.5.
- **The server:** S12.11.1.1–2 (three alerts), S13.3 (forwarded headers, the listening
  address), S13.4 (the hourly prune), S13.5 (timeouts and ceilings), S13.6 (`starting`, and
  what the unlock route tells anyone), S13.7.6, and the settings' bounds and defaults in
  S16.3, S16.5, S16.8, S16.9, S16.10, S16.12 and S16.16.
- **Keys and email:** S15.1.7 and S16.2 (the outbox, in the clear), S15.3.5 (the data key's
  id), S15.7.2 (`keyring.next`, and its removal at an unlock), S16.14 (404, and no ranges while
  locked).
- **The connector:** S18.2.1, S18.2.2, S18.3.1, S18.3.2, S18.8, S18.9.1–3, and
  `connector-protocol.md` §4 and §7.
- **Links:** `link-protocol.md` §1.4, §4, §4.2, §4.4.3, §4.4.4 and §7.

**Where it matters most:** the outbox in the clear, the ranges not applied while locked, a
`not-linked` answer ending a link, the removal of a `keyring.next` at an unlock, and an expiry
decided on a close up to four days old, each of which is a behaviour to confirm rather than a
detail to record.
