---
title: ATLAS real fills - why its NinjaTrader entries fill ~11 ticks worse than the backtest, what it costs at 3 / 6 / 10 ticks a side, 6 fixes tested
family: second
date: 2026-11-20
status: finding - no change. ATLAS stays (still earns in 2026-like markets at 10 ticks a side, and carries the Rapid 25K), but at real fills it has no long-run edge (2021-25 PF 0.80) and the funded 25K's 6-month loss risk roughly doubles. 0 of 6 pre-registered fixes pass. Fill cost now on the ZEUS card data.
summary: ATLAS enters with a MARKET order at the 5m open right after its signal bar closes; the order leaves 3-5 s after the open. Its 3 real fills were 10 / 12 / 16 ticks past that open (the backtest counts 1). Not a timestamp mismatch (the backtest re-run on the PC's own bars has the bot's exact entries), not book depth (2 micros; the NY pre-market fill was as bad as the London ones), not a stop order. It is price moving in the first seconds after a 5m close, in the trade's direction, then coming back. At 10 ticks a side the funded 25K still makes $512 / $404 a month (Jan-Jun / Jul-Oct like; $588 / $494 at 1 tick) but the chance of losing it in 6 months from today's account goes 7.7 -> 17.7% / 9.5 -> 23.0%; 2021-25 PF 1.06 -> 0.80. Rapid 25K: LIT + ATLAS $1,878 / $753 a month at 10 ticks vs Zlarior alone $224 / $194. Limit entries, a 1-minute delay, fast-bar skips, member hours, a London pause: all fail.
runs: tools/atlas_fills.py why / costs / fixes / posthoc -> research/second/atlas_fills_why.json, research/second/atlas_fills.json; design research/second/atlas_fills_design.md (committed d9ed3b2a before any run); tests/test_fill_cost.py
---

# ATLAS real fills (2026-11-20)

## For the owner (one minute)

**ATLAS's real entries cost about $5.50 a micro more than its backtest. Keep it running: it still makes money in markets like
2026, and the Rapid 25K needs it. Nothing to change tonight.**

| What | Backtest (1 tick) | Real fills (10 ticks a side) |
|---|---:|---:|
| Funded 25K, $ a month to you (Jan-Jun / Jul-Oct-like) | $588 / $494 | $512 / $404 |
| Chance to lose the funded 25K in 6 months, from today's $887 room | 7.7% / 9.5% | 17.7% / 23.0% |
| Rapid 25K, LIT + ATLAS, $ a month (Zlarior alone: $224 / $194) | $2,312 / $972 | $1,878 / $753 |
| ATLAS's long-run edge (2021-25 profit factor) | 1.06 | 0.80 (loses) |

Why: ATLAS buys / sells at market the moment its 5-minute signal closes. In those first 3-5 seconds the price keeps running
the way ATLAS wants to trade, so it fills 2.5-4 points late. A limit order or waiting a minute was tested: both lose more
(they miss the big winners). Your phone's ZEUS card data now says "Real fills so far: 11 ticks worse (median of 3)".

**Next for you:** nothing. Claude re-checks once ATLAS has 10+ real fills (about a month).

## Why (job 1)

### How ATLAS enters live (code)

- engine/account_b.AccountB.tick -> entry (after Zlarior's routing in each poll, engine/live.poll_once): on the first poll after
  a 5m close (polls at +2 s and +32 s each minute, engine/live.next_wake) it appends a probe bar at the forming 1m open,
  runs the members (engine/second.run), takes the first member with a signal at that open (EMA > MACD > S/R) and routes a
  **MARKET** order (engine/ninjatrader place_line "MARKET", own "acctb_" order file). Only after the fill does it place the
  stop + target bracket (up to 6 s fill wait, nt_fill_wait_s). No limit or stop entry exists for ATLAS.
- The backtest (research/second/ema_best / md_best / sr_best.json, all 1,395 member trades checked): entry = the 5m open + 1
  tick worse, stop exits = the stop + 1 tick, targets exact. tools/atlas_* / second_mix SLIP 0.25.
- Timing (ledger row minus the open; the row is written after the fill and the bracket, so the order left earlier): 5 / 4 /
  3 s for ATLAS, 4 s for Zlarior. 2 s of that is the poll offset by design.

### The fills against the bars (NinjaTrader 1m bars of the same days, data/pc_days)

| Entry | Model | 1m open | Real fill | vs model / vs open | $ (2 micros) | Entry minute's reach our way | Fill at | Minute before |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| EMA Nov 6 04:00 SELL | 27,037.75 | 27,038.00 | 27,035.50 | 9 / 10 ticks | $9 | 8.5 pts (2026 median 4.75) | 29% of it | range 17 pts (p74), vol 867 -> 2,598 |
| EMA Nov 17 08:20 SELL | 27,367.50 | 27,367.75 | 27,364.75 | 11 / 12 ticks | $11 | 6.0 pts | 50% | 23 pts (p86) |
| MACD Nov 18 04:50 SELL | 27,395.50 | 27,395.75 | 27,391.75 | 15 / 16 ticks | $15 | 10.5 pts | 38% | 21.5 pts (p83) |
| Zlarior Nov 16 06:16 BUY 1 | 27,798.75 | 27,798.50 | 27,799.50 | 3 / 4 ticks | $1.50 | 12 pts | 8% | 30.5 pts (p93) |

What each possible cause says:

- **Wrong timestamps / data in the comparison: no.** The PC's bars are start-stamped and contiguous (03:59 closes 27,038.25,
  04:00 opens 27,038.00; data/NQ_1m.csv has the same rows), and the backtest re-run on the PC's own bars
  (research/second/atlas_more_fresh.json) has exactly the bot's entries (27,037.75 / 27,367.50 / 27,395.50), stops and
  targets. The signal is right; only the fill differs. The fill is NinjaTrader's position average on MNQ 12-26 (no chart
  contract gap was flagged).
- **A stop order through a thin book: no.** Entries are market orders. 2 micros do not walk the MNQ book.
- **London liquidity: not the separator.** The 08:20 NY pre-market fill (12 ticks) was as bad as the London ones (10, 16),
  while Zlarior's London fill (06:16) was 4. The 1-2 tick bid / ask spread is a small part of it.
- **The move during the delay: yes, this is it.** All three were shorts entered while the first seconds after the 5m close kept
  falling: the fills sit 29-50% of the way from the open to that minute's low, after a fast minute (17-23 pts, p74-p86 of
  2026's ATLAS entries; the 5m signal bars themselves were normal for the day, 0.7-1.5x their 20-bar median). Then price came
  back: 2 of the 3 entry minutes closed above the open, and a limit at the open would have filled all 3 within 1-2 minutes.
  ATLAS trades a 5m close that everyone sees (a sweep + 5m CISD), on the 5m boundary (Nov 6 = the top of the hour, volume
  3x the minute before). Zlarior's one fill came off a 1m signal, not at a 5m boundary, and paid 4 ticks.
  Across 2026's ATLAS entries the entry minute closes against the trade 53% of the time (with it 46%) and reaches 2.5+ points
  our way 70% of the time: a 10-tick late fill is ordinary for that minute; WHEN in the minute it happens decides the cost.

Exits: no real exit price exists in the rows (stop / target fills are not priced there), so exit slippage is unknown. The bot
books its ledger at the model's prices; NinjaTrader's balance anchor keeps the room right.

## How much it matters (job 2)

N ticks PER SIDE in total (the backtest's 1 included): entry N ticks past the 5m open, every non-target exit N ticks past its
level, a target (resting limit) 0. Sizes unchanged. "Measured" = entry 13 ticks (the 3 fills' mean vs the open), exits 1.
Funded 25K = tools/atlas_more's Monte Carlo (600 week-block paths, MFFU Builder 25K funded rules, the live funded size,
today's approved min_room 0); "lost" = floor touched or MFFU's 7-day inactivity close. Rapid = tools/money/rapid25.py
"25K, keep $500" (LIT + ATLAS $250 at 30% of the room), only ATLAS's trades re-priced, 1,000 paths.

Fixed $250 a trade, real days (trades a week / PF / $ a month / max DD):

| Ticks a side | 2026 Jan-Jun | Jul-Oct 16 | 2025 | 2021-24 |
|---:|---|---|---|---|
| 1 (backtest) | 4.06 / 2.92 / $3,012 / -$1,062 | 2.95 / 2.55 / $1,415 / -$876 | 4.30 / 1.17 / $364 / -$4,871 | 4.71 / 1.06 / $152 / -$11,403 |
| 3 | 2.79 / $2,924 / -$1,082 | 2.43 / $1,361 / -$943 | 1.10 / $223 / -$5,739 | 0.99 / -$24 / -$15,849 |
| 6 | 2.61 / $2,791 / -$1,206 | 2.26 / $1,280 / -$1,043 | 1.00 / $12 / -$7,043 | 0.90 / -$287 / -$23,600 |
| 10 | 2.39 / $2,614 / -$1,476 | 2.07 / $1,172 / -$1,177 | 0.90 / -$269 / -$8,781 | 0.80 / -$638 / -$34,062 |
| measured | 2.53 / $2,705 / -$1,294 | 2.18 / $1,224 / -$1,086 | 0.97 / -$89 / -$7,612 | 0.86 / -$410 / -$27,107 |

Funded 25K and the Rapid 25K lane:

| Ticks a side | Funded 25K $ a month (H1 / H2 / 2021-25) | 1st payout (session) | Lost in 6 m, fresh / from today's $887 room (H1, H2, 2021-25) | Rapid LIT + ATLAS $ a month (H1 / H2 / 2021-25) | Rapid no payout in 6 m |
|---:|---|---|---|---|---|
| 1 | $588 / $494 / $48 | 18 / 25 | 7.3, 8.3, 93.0 / 7.7, 9.5, 94.0% | $2,312 / $972 / -$6 | 6.6 / 18.4% |
| 3 | $571 / $473 / $41 | 18 / 25 | 8.8, 10.8, 95.0 / 10.0, 11.7, 96.0% | $2,228 / $914 / -$18 | 7.6 / 20.2% |
| 6 | $550 / $438 / $31 | 18 / 26 | 11.8, 16.5, 97.2 / 13.5, 18.7, 97.7% | $2,067 / $853 / -$30 | 8.9 / 21.7% |
| 10 | $512 / $404 / $21 | 19 / 27 | 16.8, 21.8, 99.0 / 17.7, 23.0, 99.2% | $1,878 / $753 / -$43 | 10.4 / 24.5% |
| measured | $535 / $421 / $25 | 18 / 27 | 13.5, 19.0, 98.0 / 14.7, 20.5, 98.0% | $1,963 / $813 / -$39 | 9.6 / 22.7% |
| Rapid, Zlarior alone | | | | $224 / $194 / -$21 | 54.5 / 49.8% |

**Is ATLAS still worth running at 10 ticks? Yes, in markets like 2026, and on the Rapid it is essential.** The pre-declared
rule (funded > $50 a month in both 2026 halves and PF >= 1.2) holds at every cost. It loses ~$75-90 a month on the funded
25K and ~$220-430 a month on the Rapid versus the backtest, and its biggest cost is safety: the funded 25K's chance of being
lost in 6 months about doubles (from today's account 7.7 -> 17.7% Jan-Jun-like, 9.5 -> 23.0% Jul-Oct-like; lost = mostly
MFFU's inactivity close once the room is too small for a micro). **But at real fills ATLAS has no long-run edge:** 2021-24
PF 0.99 already at 3 ticks, 0.80 at 10, and 2025 0.90. It is a 2026-market strategy; in a calm 2021-25-like market it
loses money at real fills (it was barely positive even at 1 tick). The 2026 VIX-band targets carry it.

## The fixes (job 3, pre-registered in research/second/atlas_fills_design.md, commit d9ed3b2a)

Judged against today at the SAME cost, must hold at both 6 and 10 ticks a side (funded $ +$10 in both halves, 2021-25 and the
lost rate not worse, PF and fixed $ not worse, 2-4.1 trades a week, testable on all spans). 0 of 6 pass.

| Fix | Funded 25K $ a month at 6 ticks (H1 / H2 / 2021-25), today $550 / $438 / $31 | at 10 ticks, today $512 / $404 / $21 | Why it fails |
|---|---|---|---|
| F1 limit at the 5m open, 5-min timeout | $314 / $382 / $3 | $296 / $355 / $3 | fills only when price comes back: misses 17-18% of 2026's trades, the runners (PF H1 2.61 -> 2.07); 2021-25 (5m-bar check) worse |
| F2 limit 4 ticks worse, 5 min | $278 / $337 / $2 | $258 / $324 / $1 | the same at 6-10 ticks (rests); = market at 3 ticks |
| F3 enter on the 1m close (+60 s) | $475 / $495 / n.a. | $428 / $442 / n.a. | Jul-Oct better (+$57 / +$38), Jan-Jun worse (-$75 / -$84, lost 11.8 -> 16.8%); 2021-25 has no 1m bars |
| F4 skip a signal bar > 2x its 20-bar median range | $483 / $343 / $27 | $460 / $313 / $19 | skips 30% of signals, and those are good trades |
| F5 member hours picked on Jan-Jun (EMA 03-05, MACD 02-10, S/R 09-11 ET) | $615 / $274 / $46 | $602 / $245 / $31 | the in-sample half improves, Jul-Oct loses $164 a month: an overfit |
| F6 London pause (no entry before 08:00 ET) | $354 / $74 / $20 | $334 / $66 / $14 | London is most of ATLAS's money (1.3 trades a week left); also with London at N and NY at N/2 |

Post-hoc (added after the fixes ran; shown, never eligible):
- P1 a limit at the open for 60 s, else market at the 2nd minute: $445 / $381 (6 ticks), $420 / $344 (10): worse than F3 (when
  price comes back in minute 1, waiting gets a better price than the open; the runners are chased late either way).
- P2 the hope behind F3: IF an entry one minute after the 5m boundary filled like Zlarior's (3 ticks) while today's keeps
  paying 10, F3 would be $510 / $523 vs today $512 / $404 (lost 12.5 / 11.2% vs 16.8 / 21.8%). The real slippage of such an
  entry is unmeasured, and F3 at the same cost loses in Jan-Jun, so this is a question for real fills, not a change.
- On the 3 real trades a limit at the open would have filled all 3 and saved $38, and entering a minute later would have been
  better on all 3. Three trades are not the evidence; 2026's 150 trades say both lose.

Not testable on bars: polling on NinjaTrader's first tick (engine/fast_entry, built OFF by night-nqlive) moves the order up to
~1.8 s earlier inside the first seconds where the cost is made. It is the one change aimed straight at the cause, but only
tick-time fills can price it.

What would settle it: 10+ ATLAS fills (about a month at ~2 a week), next to Zlarior's fills (1m entries, mostly off the 5m
boundary). If ATLAS stays near 10+ ticks while Zlarior stays near 2-4, the 5m-boundary delay is confirmed and F3 / fast_entry
are worth a pre-registered re-test with the measured costs. engine/zeus_learn already proposes "re-run its gates with the real
fill cost" once 8+ fills have a median over 1.5 ticks.

## Fill cost visible (job 4)

The PC already measures every real entry against the model price (engine/zeus_learn.fills, last 20 fills) and ships it in
the day folder's learn.json (ATLAS today: n 3, median 11, worst 15). New:
- `tools/fill_cost.py`: words / block -> "Real fills so far: 11 ticks worse than the backtest price (median of 3 fills; worst
  15, about $5.50 a micro a trade; the backtest already counts 1)"; from_rows rebuilds it from the ledger rows of the pulled
  days when a learn.json lacks it (live only, hidden bots never, no account text).
- `tools/learn_night.card_doc`: each strategy row of tools/web_public/hub/learned.json (the ZEUS page's cloud card) now carries
  `fills` {n, med, worst, assumed, line} (K8 never). Lead: show `bots[].fills.line` on the ZEUS card (hub/zeus.js learned
  rows) and, if wanted, on the ATLAS account card; the data is there after the next `python tools/learn_night.py`.
- tests/test_fill_cost.py 13/13 (nq area); tests.test_learn_night unchanged.

## Files

tools/atlas_fills.py (research), tools/fill_cost.py (new, read only), tools/learn_night.py (card row + fills),
tests/test_fill_cost.py, research/second/atlas_fills_design.md, research/second/atlas_fills.json, research/second/atlas_fills_why.json.
Nothing live changed: no engine file, no live_model*.json, no second_model.json, no data/account_b.json.
