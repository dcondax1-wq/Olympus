# MFFU 2% price-limit rule guard (branch day-multirapid, 2026-11-20)

## For the owner

| What | Result |
|---|---|
| The rule (MFFU help 9698984, "2% Price Limit Rule") | No trading when NQ is within 2% of CME's limit, on **funded** accounts (sim funded + live). For NQ overnight: CME limit 7% -> MFFU stops at a 5% move from the prior settlement |
| Before | The bot had no guard (the one MFFU rule it did not obey: rules audit 2026-11-17) |
| Now | A funded account takes no new trade and closes an open one once NQ is 4.75% from the prior close; blocked for the rest of that session. Evals are untouched (MFFU names funded only) |
| How often | 9 sessions in 5 years on our 5m data (2022-11-10, 2024-08-05, 2025-04-03/04/07/09/10, 2026-06-05, 2026-11-05); a normal day never |
| Live? | No. Branch only; lands after the weekend + a red-team pass |

## The rule (cited)

help.myfundedfutures.com/en/articles/9698984-2-price-limit-rule (dated 2026-08-24, read 2026-11-20):
- "we enforce strict guidelines to prevent trading when a product is within 2% of a CME price limit."
- "This prohibited conduct is enforced in the following accounts: Sim Funded Account and Live Funded Account."
- "Price limits are calculated based on the end-of-day settlement price ... overnight price limits differ from the price limits
  used during business hours."
- "Equity Products ES, MES, NQ, MNQ ... overnight price limits have increased to 5%, which is 2% below the CME limit of 7%.
  Consequently, trading is suspended at MyFunded Futures."
- Their example: reference 18,556 -> "Stop trading when market priced above: 18556 x (1 + 0.07 - 0.02) = 19483", "below:
  18556 x (1 - 0.07 + 0.02) = 17628".
- research/lit/mffu_rules.json price_limit_rule already had it (confirmed 2026-11-17, sim funded + live, not the eval).
- CME's own page (cmegroup.com/trading/price-limits.html) returned 503 twice: CME's regular-hours levels (downside 7 / 13 / 20%)
  are not re-verified here; the guard does not depend on them (see "Choices").

## What the bot does (engine/price_limit.py, new)

- Reference = the prior session's settlement, proxied by the close of the last regular-hours bar ending at or before 16:00 ET
  (Friday's for a Monday / Sunday-evening session; a half day's last bar).
- Trigger = |price / reference - 1| >= 4.75% (MFFU's 5% minus 0.25% margin: our close is a proxy for CME's settlement and the
  tape can move inside a poll). Price = the newest 1m close each poll.
- Sticky: once hit, blocked to the end of that trading day (18:00 ET), as "trading is suspended".
- Unknown / stale (> 3 min) reading = not blocked (the stale-feed guard already blocks entries).
- Who: FUNDED stages only:
  - extra LIT lanes in funded mode (engine/multi_account: Zlarior 25K #2 once funded, LIT on ATLAS's funded 25K, a funded
    Rapid's LIT lane): entry_block refuses; an open position is closed (reason "PRICE LIMIT", booked at the mark like NEWS FLAT);
  - account B code in its funded stage (ATLAS's funded 25K, a funded Rapid's ATLAS lane, lit25's shared ATLAS): guard refuses;
    tick closes an open position first;
  - Zlarior's own account once funded (lit_sizing mode funded / auto past target): entry refused. NOT auto-closed (see Gaps).
- Wiring: LiveBot.poll_once reads it once per poll after LIT's model, before any account routes (health["price_limit"]).
  Phone alert words: notify.EXIT_WORDS "PRICE LIMIT" -> "MFFU price-limit rule".

## Choices (say no and Claude changes them)

1. Same +/-5% band in regular hours. CME's day-session equity limits are downside only, so the upside stop in regular hours is
   stricter than MFFU asks (costs only a few squeeze days like 2025-04-09 +11%).
2. 0.25% margin (stops at 4.75%, not 5%).
3. Rapid EVAL not guarded: MFFU's article names sim funded + live only (the lead's brief said "funded + Rapid stages"; a Rapid
   becomes guarded the day it is funded).

## Tests

| Check | Result |
|---|---|
| tests.test_price_limit (new): MFFU's example, references, real crash days 2026-11-05 / 2025-04-04 / 2024-08-05 blocked + sticky, normal days 2026-10-13 / 2026-11-18 / 2025-06-02 never, every session 2021-26 scanned, funded vs eval accounts, stale reading, Zlarior funded only | 27/27 |
| tools/rehearse_day.py --scenarios pricelimit (real bot, simulated NinjaTrader, 2026-10-06, rule forced at 04:20 with ATLAS's funded 25K long) | 34/34: funded 25K closed "PRICE LIMIT", its later MACD / S/R signals refused, evals kept trading, no hedge across accounts |
| tools/rehearse_day.py --days 2026-11-05 (the real -7% day) | 15/15 (no strategy traded that day, nothing to close) |
| `python -X utf8 -m tests.test_lit_live --quick` | OK |
| `python -m engine.ninjatrader --selftest` | PASS 79/79 |
| test_rapid25 / test_account_b_funded / test_multi_rapid / test_rapid / test_rapid_launch | 95/95 / 71/71 / 41/41 / 60/60 / 12/12 |
| others | OTHERS_RESULT |

## Gaps (for the lead)

- Zlarior's own account (main LIT): entries are blocked once funded, but an OPEN main position is not auto-closed (the only
  main-only close path today is the phone FLATTEN, which also closes every other account). It is an eval today; wire a
  main-only close before the 50K is funded.
- Fleet followers (engine/fleet.py) in a funded stage are not guarded (none funded today).
- CME regular-hours levels unverified (503).

## Rollback

Revert the commit; no data file is written (the reading lives in memory). engine/price_limit.py can also be neutralised by
setting TRIGGER = 1.0.

Files: engine/price_limit.py (new), engine/live.py (update per poll + Zlarior funded entry block), engine/multi_account.py
(price_limit_block, entry_block, flatten, booking), engine/account_b.py (_price_limit, guard, tick flatten), engine/notify.py
(exit words), tools/rehearse_day.py (scenario pricelimit + funded checks on any day the rule is hit), tests/test_price_limit.py.
