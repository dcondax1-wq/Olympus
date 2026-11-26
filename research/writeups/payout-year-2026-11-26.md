---
title: Payout engine + 12-month request policy - ask for the full max each time; when you ask moves < $25 a year, the market moves thousands
family: money
date: 2026-11-26
status: research + a READ-ONLY planner. No live change: the bot already asks at the max. Nothing requests a payout.
runs: tools/money/payout_year.py -> research/payout/results.json (design research/payout/DESIGN.md 700b7705e + erratum 073e031ed, before the run); engine/payout_engine.py (planner, /today, Money tile)
---

## For the owner

| Funded account, 12 months, 600 paths (25% mix = 1 block in 4 from 2026, else 2021-25) | Cash to you 2026-like / **25% mix** / 2021-25 | Account lost in 12 m | Pick |
|---|---|---|---|
| **25K ATLAS** (live now), ask the full $1,000 (today) | $3,047 / **$751** / $284 | 4.8 / 81.8 / 95.7% | **keep: full max** |
| 25K ATLAS, ask as soon as MFFU allows ($250) | $2,936 / $725 / $298 | 5.0 / 83.5 / 95.7% | - |
| 25K LIT + ATLAS $250, full max (today) | $2,947 / **$799** / $221 | 8.0 / 77.8 / 94.3% | **keep** (cushion +$17 a year: under the $25 bar) |
| **50K LIT** (when the eval passes), full $2,000 (today) | $6,059 / **$1,944** / $477 | 4.2 / 63.3 / 90.7% | **keep: full max** |
| 50K LIT, as soon as allowed ($500) | $5,945 / $1,920 / $495 | 4.5 / 64.0 / 90.8% | - |

**Plain answer:** the request habit the bot already uses (ask for the full max once it sits above the buffer, payouts 1-4,
never #5) is the best or tied in every account. Asking earlier gets the first payout ~3-6 trading days sooner but less cash in
total. What decides the money is whether the market stays 2026-like (about $3,000 a year from the 25K, $6,000 from the 50K) or
goes back to 2021-25 (a few hundred, and the account is usually lost within the year).

## The planner (engine/payout_engine.py, read-only)
Per funded account, from the PC's own trackers: **"REQUEST TODAY: $1,000 ($800 to you); after it keep $26,100"**, or
**"next payout: $1,000 possible about 2026-12-11 ($800 to you), keep $26,100; $1,500 more profit to reach the ask line"**.
Blockers in words: $ to the ask line, the 50% best-day rule, the 2 traded days, MFFU's 48 h, the payout #5 guard, a lost account;
Rapid EOD: daily, $ still needed since the last payout. Dates are trading days at the account's own recent pace (an estimate).
- Telegram: **/today** (read-only answer; nothing runs on the PC).
- Money page: `data/payout_tile.json` (written each 15-minute report; the lead wires the page).

## Rules (re-read on MFFU's pages 2026-11-26; every value in research/lit/mffu_rules.json matches)
| Plan (sim funded) | Buffer | Request | Split | Consistency | Days / cycle | Cadence | Sim payouts |
|---|---|---|---|---|---|---|---|
| Builder 25K | $1,100 | $250 - $1,000; later $250 since the last | 80% | best day <= 50% of the cycle | 2 | after 48 h, by cycle | 5 (5th = live) |
| Builder 50K | $2,100 ($1,600 add-on) | $500 - $2,000 | 80% | 50% | 2 | after 48 h, by cycle | 5 |
| Rapid EOD 25K | $1,100 | $500 min, no cap; $250 net since the last | 90% | none in sim | - | daily | no limit stated |
| Rapid EOD 50K | $2,100 | $500 min, no cap; $500 net since the last | 90% | none | - | daily | no limit stated |
Not on MFFU's pages (marked unverified in the planner's words): a sim payout cadence other than "by cycle" for the Builders.
