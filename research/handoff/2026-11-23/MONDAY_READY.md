# Monday 2026-11-23 trade readiness (day-monday, paper dry-run)

How: tools/rehearse_day.py = the REAL LiveBot with every account's NinjaTrader adapter on one simulated NinjaTrader, the PC's
exact config built the way ADD_ACCOUNT / START BOT write it (Zlarior 50K eval, Zlarior 25K #2 eval, ATLAS funded 25K, Rapid EOD 25K
LIT + ATLAS lanes), replayed minute by minute. Days: the newest bars in the repo **Nov 17, 18, 19** (Nov 20-21 bars are on the PC only,
not in the repo) + **Oct 7 and Oct 13** (days Zlarior traded, so its sizing path ran too). **87 / 87 checks passed** (51 + 36),
no poll raised, never long on one account and short on another, flat 15:55-16:10 everywhere.

| Account | What it will do Monday | Risk $ a trade (full stop, costs in) | Blocker? |
|---|---|---|---|
| **Zlarior 50K eval** ($49,193, $1,025 room) | LIT, 1 trade a day typical; two_week size = 40% of the room | **~$330-$410** (e.g. 7 micros on a 20-pt stop = $388, 2 on 60 pts = $327); soft day stop $1,000 | none |
| **Zlarior 25K #2 eval** (fresh, $1,000 room) | the same LIT signal, its own size | **~$330-$400** (6 micros $332, 2 micros $327) | none |
| **ATLAS funded 25K** | EMA / MACD / S/R members, max 2 a day, never opposite Zlarior; **room 40% + 2-losses-then-1-micro are ON** (owner YES, code check: `funded: 40% of $1,000 room -> $400`) | **<= 40% of the room** (~$355 at an $887 room); fills seen $102-$145; soft day $600 | none. A 1-micro winner over the funded winner cap ($1,000) is skipped by design |
| **Rapid EOD 25K eval** - ATLAS lane | min($250, 30% of the room, the day left), sized on stop + 10 ticks (owner YES) | **<= $250** (fills seen $51-$149) | none. Skips a trade whose 1-micro winner pays > $427 (MFFU's 30% best day) and anything opposite another account (correct) |
| **Rapid EOD 25K eval** - LIT lane | LIT's signal at 40% of the room, then the 30% best-day cap | 0-1 micro (~$55 seen) | **Not a bug, by design:** a LIT target over ~215 pts pays > $427 on 1 micro, so it trades 0 micros there: **58-64% of LIT signals in 2026** (Jul-Nov 23 of 40), another ~40% capped to 1 micro. Known; card rapid25-lit-bank (recommend no) |

What was checked and is fine: every account armed + routed (phrase, NINJATRADER_LIVE, allowlist), each lane on its own NinjaTrader Name
(the 25K #2 eval never confused with the funded 25K), distinct order tags / state files, one position at a time on the Rapid (LIT
closes ATLAS first: HEDGE seen on Oct 13), the Rapid's day stays under 30% x $1,500, payout coach = ATLAS's own book, status payload
< 3,900 bytes, board events clean.

## Fixed on this branch
- **tools/rehearse_day.py checked ATLAS's funded sizes against 60% of the room after the owner's room-40% YES** (PLAN_CAPS 0.6): a
  60% size would have passed the rehearsal unnoticed. Now it reads the live switch (engine/account_b.FUNDED_ON, else 0.6).
  Test: tests/test_rehearse_caps.py (2/2), added to run_area "nq". The bot itself was right (it sizes at 40%).

## Not covered / owner-side
- Nov 20-21 bars (PC only) and a live NinjaTrader: the PC's own START BOT checklist covers them.
- From STATE "Waiting on the owner": STOP BOT -> START_BOT.bat -> type I ACCEPT LIVE RISK (Rapid EOD 25K armed); Sunday before 6 PM:
  KEEPALIVE_ON.bat (the 7-day rule).
- ES daily / 1h files end Oct 16 (stale on the board): no live rule reads them.
