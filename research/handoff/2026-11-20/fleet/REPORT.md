# Fleet plan to June 2027 (day-fleet, 2026-11-20): REPORT

## Owner summary (read this)

**Cash to you each month, after MFFU's cut, every fee and a 35% tax set-aside** (35% is a placeholder; day-taxes will
publish the real Maryland-inclusive %). All 5 MFFU slots + Kalshi K8 on 1,000 paths, from today's balances.

| Month | Normal (median) | Bad (1 in 10) | If the edge halves (median) | 2021-25-like (median) |
|---|---|---|---|---|
| Dec 2026 | $74 | -$29 | -$36 | -$159 |
| Jan 2027 | $572 | -$28 | -$43 | -$162 |
| Feb | $1,523 | $0 | -$24 | -$189 |
| Mar | $2,731 | $63 | $0 | -$223 |
| Apr | $3,434 | $291 | $19 | -$218 |
| May | $3,548 | $65 | $37 | -$218 |
| Jun | $3,874 | $266 | $52 | -$218 |
| **Nov 20 - Jun 30 total** | **$19,510** | **$6,886** | $1,987 | -$1,347 |

"Normal" = a Jul-Oct 2026-like market. Real fills (ATLAS 10 ticks a side). If LIT also slipped 10 ticks: total $16,346.
Bad months can be ~$0 even in a good market: payouts are lumpy, so one month may have none.
If the edge halves, the typical month is about $0 (the average is still about +$450 a month, carried by the good runs).
In a 2021-25-like market you lose about $1,350 over the 7 months, all of it on eval re-buys.

**What to buy, and when (paid only from payout money already in the bank):**
1. Today: the Rapid EOD 25K ($97.20). Already in the plan.
2. **The 5th funded slot: a Rapid EOD 50K, $165 with CLUB.** Typical date **Jan 5** (8 in 10 runs Dec 14 - Feb 12).
   ATLAS's first $800 payout pays for it. It is the biggest earner in the plan (median $7,840 by June).
   Never fill that slot with a 2nd Rapid 25K.
3. When an eval dies: buy the same plan again that night ($91.80 / $63 / $97.20 / $165). Expect about 3 re-buys by June
   (about $440 in fees). After that, all 5 funded slots are full and there is nothing more to buy.

**The 3 Decide answers that matter most** ($ a month to you after tax: normal / half edge / 2021-25-like):

| Card | YES is worth | Accounts lost by June |
|---|---|---|
| atlas-on-rapid (keep ATLAS on the Rapid) | **+$390** / +$33 / -$32 | +0.3 more |
| zlarior-funded25 (LIT also on ATLAS's funded 25K) | **+$159** / +$89 / +$27 | about the same (fewer when the edge is weak) |
| zlarior-atlas-50k (ATLAS on the 50K once funded) | **+$209** / -$22 / -$13 | about the same |

Everything else is under $55 a month either way. cloud-alerts and drop-lucid-account4 change $0.

## The numbers behind it

Per account, Nov 20 - Jun 30, normal market, after tax (median total; first payout = typical request date, bank +3 days):

| Account | Median by June | Bad 1 in 10 | First payout | Paid at all |
|---|---|---|---|---|
| Rapid EOD 50K (5th slot, bought ~Jan 5) | $7,840 | $462 | Mar 18 | 93% |
| Rapid EOD 25K (today) | $4,301 | $462 | Feb 16 | 92% |
| Zlarior 50K eval | $3,889 | $948 | Feb 11 | 95% |
| ATLAS funded 25K | $2,366 | $977 | **Jan 7** | 98% |
| Zlarior 25K #2 eval | $1,560 | -$63 | Feb 2 | 89% |
| Kalshi K8 ($2.50 a bet) | about $300 (average) | | | |

All 8 Decide cards (YES minus NO, $ a month to you after the 35% set-aside, Nov 20 - Jun 30 average; real fills):

| Card | Normal | Half edge | 2021-25 | YES better in | Accounts lost (change) |
|---|---|---|---|---|---|
| atlas-on-rapid | +$390 | +$33 | -$32 | 89% of runs | +0.33 |
| zlarior-atlas-50k (funded only) | +$209 | -$22 | -$13 | 84% | +0.04 |
| zlarior-funded25 | +$159 | +$89 | +$27 | 74% | +0.02 / -0.90 / -0.74 |
| rapid25-lit-bank | +$53 | +$17 | +$1 | 55% | +0.04 |
| ask-mffu-parallel (2nd 50K eval) | +$38 | +$10 | -$5 | 40% | -0.01 |
| keep-1000-rapid | +$15 | $0 | $0 | 32% | -0.17 |
| payout-ping-1000 | -$25 | -$9 | $0 | 40% | -0.03 |
| atlas-funded-room-40 | -$54 | -$14 | +$6 | 31% | -0.12 |
| cloud-alerts, drop-lucid-account4 | $0 | $0 | $0 | | |

Notes for the lead:
- **zlarior-funded25** is now positive in all 3 markets. The older single-account study said NO because ATLAS's 25K gets
  lost more often. In the whole-fleet view that is outweighed: LIT's profit keeps the account alive, so fewer ATLAS
  re-buys are needed. The owner still decides. It is not a strategy change, but MFFU's one-account rules apply.
- **zlarior-atlas-50k** is modelled here as "after the pass" (funded LIT + ATLAS $500, builder_levers F50_LA). The
  combo-final study's rule (ATLAS at half size in the eval too) valued it at +$696 before tax.
- The card $ here are AFTER a 35% set-aside and include the fleet knock-on effect (an earlier 50K Rapid buy). That is why
  they differ from the card's own usd_month, which is before the 30% pot.
- **A money gap seen, not tested (no new research here):** in a 2021-25-like market, ATLAS's lost 25K is re-bought about
  12 times (~$730 in fees), because MFFU's rules make a weak ATLAS eval die fast. A rule like "no re-buy while the edge
  check is RED" would cap that. It needs a pre-registered test before it goes on a card.

## How it was run

`python -X utf8 tools/money/fleet_months.py` (n = 1,000 a market, ~5 min on 4 cores) -> research/lab/fleet_months.json +
tools/web_public/business/fleet_plan.json.

- **Accounts:** payday_plan's seats from today's board (the live sizing code, MFFU eval / funded / payout rules and caps
  as coded in money_plan). A failed eval or lost funded account is re-bought at once (money_book.dead_eval).
- **5th slot:** a Rapid EOD 50K, bought when money_book.next_buy says so on the kept cash. Kept cash = payouts in the
  bank x 65%, minus every fee paid so far.
- **Kalshi K8:** the stored held-out bets at $2.50 (kalshi_clock.json), with the -$19.25 kill. Tax is set aside on it too.
- **Markets:** Jul-Oct 2026 week blocks; "half that edge" = each week drawn from Jul-Oct or 2021-25 with even odds;
  2021-25 week blocks.
- **Cash timing:** a month's cash = payouts landing in the bank (3 sessions after the request) - fees that month.
  Thanksgiving, Christmas, New Year and the other CME full closures are skipped.

Tests: `python -X utf8 -m tests.test_fleet_months` 14/14 (in `run_area money`, 16/16 suites, 553 checks). Smoke 7/8: the
one red is test_zenith_mode, which needs the Python `playwright` module; it is not installed in this container and that
has nothing to do with this change. Write-up: research/writeups/fleet-plan-2026-11-20.md. Estimates, not promises:
backtests overstate.
