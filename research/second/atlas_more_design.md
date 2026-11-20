# ATLAS more money (2026-11-19, night-atlasmore): pre-registered design

Written and committed BEFORE any idea was run. Research only: no live code, no live_model*.json, no second_model.json,
no data/account_b.json change. Tool: `tools/atlas_more.py`. Results: `research/second/atlas_more.json`. Write-up:
`research/writeups/atlas-more-money-2026-11-19.md`.

## The account (today)
MFFU Builder 25K FUNDED, ATLAS alone (EMA London pullback, MACD sweep divergence, S/R NY reclaim), balance $24,887
(-$113 on its first day), floor $24,000, room $887, first $1,000 payout at about $27,100. Live sizing = engine/account_b
funded preset (60% of the room, $50-$750, ref stop 20 pts, a winner <= $1,000, $600 soft daily loss, 20 micros, the
full stop-out must fit the room), max 2 a day, one position, never opposite LIT (incl. its armed setups), stuck = no new
trade once the room is under $100.

## Base and scoring (re-used from tools/atlas_health.py, unchanged)
- Trades: the live ATLAS units (tools/atlas.account_units + one position + max 2 a day), 2021-11 .. 2026-10-16, costs in.
- Funded money: MFFU Builder 25K funded rules (tools/uprisk.Funded = engine/funded_life builder25k), 600 Monte Carlo paths
  x 126 sessions of 5-session (week) blocks = a week-block bootstrap; spans H1 = 2026 Jan-Jun, H2 = 2026 Jul 1 - Oct 16,
  REF = 2021-11 .. 2025. From a fresh funded start AND from today's account ($887 room), plus the real day order.
- Fixed view (the proof rule's table): every trade at $250, real days in order, costs in: trades a week, PF, net $,
  $ a month, max drawdown for H1 / H2 / 2025 / 2021-24.
- Fresh check (not a gate, 5 weeks): the members re-run by engine/second.run on the new bars Oct 19 - Nov 19
  (data/NQ_*.csv refreshed to Nov 19, VIX from CBOE's free daily file), one position, max 2 a day (LIT block not applied).

## The 10 ideas (14 variants with neighbours)
(a) funded payout speed and safety from today's account
- A1 `stuck_off`: no stuck stop. Keep trading whenever the live funded sizing still gives 1 micro (its full stop-out fits
  the room and the day's soft loss). An account under $100 of room that goes 5 sessions with no trade is counted DEAD
  (MFFU closes an account after 7 days without a trade).
- A2 `stuck_50`: the stuck stop at $50 instead of $100 (same inactivity rule under $100).
- A3 `thin_macd`: while the room (incl. today's closed P&L) is under $500, only MACD trades (the member with the best
  fixed-size R per trade in Jan-Jun 2026, picked on Jan-Jun only); EMA / S/R signals are skipped. Neighbours $300 / $700
  (counted, plateau check only).
- A4 `thin_no_ema`: while the room is under $500, EMA (the Jan-Jun worst R per trade) sits out. Neighbours $300 / $700.
- A5 `stuck_off_room40`: A1 + 40% of the room a trade (the open card atlas-funded-room-40, combined).
(b) members
- B1 `v2_hunts` (= the answer to "switch ATLAS v2 on?" for the FUNDED account): + sh_asia + sh_trend at weight 0.5
  (never above the funded preset), stuck $100. Re-measure (atlas-revive scored it on a fresh start without the stuck stop).
- B2 `v2_full`: B1 + min_room $200 (the built v2 key as engine/account_b.min_room applies it to the funded stage).
- B3 `asia_hunt`: + sh_asia x0.5 only (market entry; the hunt account B could route first).
(c) LIT-proven filters on ATLAS's members (VIX band: EMA and MACD already use it, S/R's VIX band was rejected in
second-sr.md; news blackouts at entry were rejected for S/R and in setup-grade; so only the exit side is new)
- C1 `news_flat`: an ATLAS trade still open at an MFFU tier-1 release (the calendar of the Rapid funded news rule,
  tools/lit_mffu_rapid_stack.tier1: CPI 08:30, jobs report 08:30 (first Friday before Oct 2023), FOMC 14:00 + 14:30,
  FOMC minutes 14:00; data/news/events.csv) is closed at the open of the bar that starts >= 3 min before it (2026 1m
  path: 08:27 / 13:57; 5m path before 2026: 08:25 / 13:55), 1 tick slippage; no new entry from 5 min before to 2.5 min
  after. (CPI is in the file only from late 2023: 2021-23 checks FOMC + jobs only.)
- C2 `news_flat_notbe`: C1, but a trade that already reached +1R keeps running.

## Gate (an idea is a winner only if ALL hold)
- G1 money: funded $ a month >= base - $10 in H1 and H2, REF >= base - $5; from a fresh start AND from today's account.
- G2 a real gain: from today's account +$10 a month in BOTH H1 and H2, OR dead-in-6-months at least 1 point lower in
  H1 or H2 with no span worse.
- G3 safety: dead and no-payout in 6 months <= base + 0.5 point in every span (fresh start and today's account).
- G4 speed: median first payout <= base + 1 session in H1 and H2 (fresh start and today's account).
- G5 trades a week 2.0-4.1 on the account in H1 and H2 (fixed view).
- G6 real day order: dead not higher in any span, $ a month not lower by more than $10 in H1 / H2.
- G7 for ideas that change trades (B, C): fixed-view net $ not lower in H1, H2 and 2021-25 (2025 + 2021-24).
- G8 it must act in Jul-Oct (change a trade or the funded numbers there).
- G9 controls for timing / state rules: A3 / A4 vs 40 random sit-outs of the same number of trades per span; C1 / C2 vs
  40 shifted calendars (each release moved to a random other weekday of its span, same clock time). The idea must beat
  >= 90% of draws on H1 + H2 money and dead accounts.
- G10 week-block bootstrap of the paired difference (the 600 paths are the week-block resamples; 2,000 resamples of the
  paths): the 90% interval of (idea - base) $ a month from today's account must sit above -$10 in H1 and H2.

## Counting
10 ideas, 14 variants (A3 and A4 with 2 neighbours each). Diagnostics that are not ideas: each member per span
(H1 / H2 / 2025 / 2021-24 / fresh Oct 19 - Nov 19), the cost of the armed-setup block (report only: the no-hedge
rule is a safety rule and is not proposed for change).
Decide card only for a winner. Rejected ideas go to docs/TESTED_AND_REJECTED.md.
