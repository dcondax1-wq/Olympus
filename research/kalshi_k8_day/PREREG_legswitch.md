# Pre-registration: each K8 leg turns itself OFF / ON from its own rolling record (written 2026-11-20 ~11:25 UTC, before testing)

Committed before the walk-forward below is run on the refreshed public tape (research/kalshi_k8_day/data/tape.jsonl).

## The rule (one main rule; fixed now)
For each leg, look at its last **20 settled windows** (every weekday window of that leg, whether we bet or not: the bot's paper
ledger records all of them, Kalshi's public results give the same), won = Kalshi's result equals our side.
- **Pause** the leg (no live bet; paper keeps recording) when it won **10 or fewer of the last 20** (<= 50%: under the ~54%
  break-even at ~52c + fee).
- **Resume** it when it won **12 or more of the last 20** (>= 60%). Between 11 and 11: keep the current state (no flip-flop).
- Under 20 settled windows: never paused. It only ever pauses or resumes a leg the owner armed; it never adds a leg or raises a size.
The phone shows a paused leg in plain words, e.g. "silver UP paused: won 9 of the last 20 (resumes at 12)".

Robustness only (reported, not used for the decision): N=10 pause <= 4 / resume >= 6; N=30 pause <= 15 / resume >= 18.

## The test (walk-forward on the public tape, $2.50 bets at the +20 s price, fees exact)
Days Aug 3 - Nov 20; the rule decides each day's bet from windows BEFORE that day only. Halves: find Aug 3 - Oct 21, check
Oct 22 - Nov 20. Reported: bets skipped, their won / lost and **net $** in each half, and the 3 live legs' total $ with vs without.

## Decision (fixed now)
- **ON in the live bot** only if the bets the rule skips LOSE money in BOTH halves (the kalshi_adapt bar: a filter must skip losers).
- Otherwise: **built but OFF for live** (display only: the phone shows the leg's last-20 record and what the rule WOULD do), because
  skipping winning bets costs money; the existing stops (day / week / peak / 58% after 60 / 58c creep, the weekly re-test) stay.
