---
title: ATLAS revive (2026-11-17) - the fade is a low-VIX summer plus eval sizing, not a broken member; no weight / drop / add passes the proof rule, one post-hoc lead (skip VIX < 15) is a knife edge
family: risk
date: 2026-11-17
status: nothing to switch. Lead only (paper tally): skip ATLAS on days whose prior VIX close is under 15. second_model.json, data/account_b.json, live_model*.json untouched.
summary: Edge health showed ATLAS's stored run at PF 1.41 / ~$411 a month over its last 40 sessions (to Oct 16) vs a 2026 median PF 2.8. At a fixed risk the same 24 trades are +8.0R, PF 1.89 (+0.33R a trade vs +0.92R in Jan-Jun); the $ PF 1.41 is the eval's need size (losers on tight stops got 4-6 micros, winners 1-2). The R that is missing comes from the VIX regime - Sep 1 - Oct 16 had 0 sessions with VIX >= 18 (Jan-Jun 69 of 128), so the VIX-band targets shrank (target winners +2.5R vs +4.3R) and ATLAS's best bucket (VIX 18-22) never traded. No member is broken - S/R is the flattest lately (+0.04R on 7 trades) but dropping or halving it costs Jan-Jun money. On the freshest data (the PC's own member paper trades Oct 19 - Nov 6) the three members made +8.6R on 11 trades, PF 2.2, and VIX is back at 17-28. 19 variants scored on the funded 25K (ATLAS alone, MFFU builder25k funded rules, 600 paths x 126 sessions - reproduces funded25.py exactly) - drops, member weights down, adds from the candidate pool, and low-VIX rules. Only the post-hoc low-VIX rules pass the money gate - skip VIX < 15 lifts the funded 25K to $599 / $582 a month (vs $592 / $497), first payout 18 / 23 sessions (vs 18 / 26), no payout 4.3 / 1.0% (vs 5.0 / 5.5%), and 0 of 40 random skips match it - but Jan-Jun cannot pick it (4 trades, +$7), it was found by looking at Jul-Oct, and its neighbours swing (VIX < 15.5 - Jul-Oct $490, < 16 - $330). Not adopted.
runs: none (research/second/atlas_revive_diag.json, atlas_revive.json, atlas_revive_placebo.json; tools/atlas_revive.py)
---

## For the owner

| What | Result |
|---|---|
| Is ATLAS broken? | **No.** Its last 40 sessions to Oct 16 made +8.0R at a fixed size (PF 1.89, 3 trades a week). The "PF 1.41, $411 a month" was the old eval's sizing: the losers happened to carry 4-6 micros, the winners 1-2 |
| Why weaker than spring | **Calm market.** From Sep 1 to Oct 16 the VIX never closed at 18 or more (Jan-Jun: 69 of 128 days). ATLAS's targets are sized by the VIX, so winners got smaller (+2.5R vs +4.3R) and its best days (VIX 18-22) never came |
| Newest weeks (Oct 19 - Nov 6, the PC's own paper trades) | **+8.6R on 11 trades** (EMA +1.7R, MACD +5.9R, S/R +1.0R). VIX is back at 17-28 |
| Drop / shrink / add a member (11 tries) | **None passes.** Every drop or smaller weight loses money in Jan-Jun or Jul-Oct on the funded 25K; adding the hunts gives more $ but 5-6 trades a week (rule 2-4) and was already tested |
| Skip days with VIX under 15 | **Lead, not a switch.** Funded 25K $592 -> $599 (Jan-Jun), $497 -> $582 (Jul-Oct) a month, first payout 26 -> 23 sessions, no payout 5.5% -> 1.0%. But Jan-Jun had only 4 such trades, I found it by looking at Jul-Oct, and a cut at 15.5 instead of 15 loses money. VIX is above 15 now, so it would change nothing today |
| Your funded 25K, as is | **$592 / $497 a month** to you (Jan-Jun / Jul-Oct markets), first payout after a median 18 / 26 funded sessions, 5.0 / 5.5% chance of no payout in 6 months, 0% lost |

Your steps: none. Keep ATLAS as it is.

## 1. Diagnosis (tools/atlas_revive.py diag -> research/second/atlas_revive_diag.json)

Trades = live ATLAS units (tools/atlas.account_units: never opposite LIT incl. its armed setups, HEDGE close), then
ATLAS's own one position + max 2 a day. R per trade at a fixed risk, costs in ($1.90 a micro + 1 tick in the unit's pts).

| R a trade (n) | Jan-Jun | Jul-Aug | Sep 1 - Oct 16 | last 40 (Aug 24 - Oct 16) | 2025 | 2021-24 |
|---|---|---|---|---|---|---|
| **All** | +0.92 (104) PF 2.95 | +0.77 (27) PF 2.78 | +0.51 (19) PF 2.64 | **+0.33 (24) PF 1.89** | +0.11 (222) | +0.04 (777) |
| EMA | +0.67 (51) | +1.26 (12) | +0.56 (8) | +0.34 (10) | -0.01 | +0.03 |
| MACD | +1.47 (27) | +0.86 (6) | +0.48 (6) | +0.61 (7) | +0.33 | +0.09 |
| S/R | +0.83 (26) | +0.05 (9) | +0.47 (5) | +0.04 (7) | +0.08 | +0.01 |
| VIX < 15 | -0.30 (4) | -0.30 (5) | -1.05 (2) | -0.44 (4) | -0.34 (27) | -0.10 (245) |
| VIX 15-18 | +0.93 (47) | +0.71 (16) | +0.69 (17) | +0.49 (20) | +0.22 | +0.08 |
| VIX 18-22 | +1.14 (37) | +1.80 (6) | none | none | +0.14 | +0.30 |
| Target exits (avg R) | +4.29 (31) | +3.87 (8) | +2.50 (4) | +2.50 (4) | +3.95 | +3.86 |

- **VIX regime** is the one clear cause: sessions with VIX >= 18 were 69 / 128 in Jan-Jun, 7 / 44 in Jul-Aug, **0 / 34** in
  Sep-Oct 16. The VIX-band target shrinks with the VIX, so the same hit rate pays less. VIX < 15 loses in every span.
- **Members:** none loses in any 2026 span. S/R is the flattest lately (S/R long -0.65R on 3 trades in the last 40), MACD
  short -0.36R on 3: samples of 3-9 trades, nothing to act on (see the fixes).
- **Side, hour, trend/chop:** long and short both positive in every 2026 span. 03:00 (the money hour, +1.95R in Jan-Jun)
  made +0.07R on 5 trades in the last 40. RTH day type (efficiency >= 0.35 trend, < 0.15 chop) and the prior day's type:
  no bucket negative across the 2026 spans; with / against the daily 20-day trend both positive. No trade bucket to cut.
- **$ vs R:** the stored run atlas_deep_zombie is an eval path at need size. Its last-40 $ PF 1.41 (+$783) vs R PF 1.89
  (+8.0R) - e.g. Aug 27 S/R stop 4 micros -$410, Aug 31 S/R stop 6 micros -$287, Oct 9 MACD stop 5 micros -$310, while
  Oct 2 EMA +3.5R had 2 micros. The funded 25K sizes by $ (60% of the room, <= $750), so the R view is the one that matters now.
- **Freshest data:** the cloud cannot re-run the members on the PC's bars, so this reads the PC's own member paper trades
  (heartbeat branch, last push 2026-11-07): Oct 19 - Nov 6 EMA 6 trades +1.68R, MACD 3 +5.92R, S/R 2 +0.95R = **+8.55R,
  PF 2.19** (members' own ledgers, before the account rules). Candidates: trend hunt 3 trades -2.08R, Asia hunt 1 BE.
  VIX (CBOE) Oct 19 - Nov 16: 16.6-28.2, mostly 17-21.

## 2. Fixes on the funded 25K (tools/atlas_revive.py fixes -> research/second/atlas_revive.json)

Money = `tools/money/builder_levers.funded_run` on the paths of `tools/money/funded25.py` (MFFU Builder 25K funded:
$1,000 EOD trailing, payouts above the $1,100 buffer, $250-1,000, 80%, 50% consistency, 5 payouts; 600 paths x 126
sessions, 5-session blocks; Jan-Jun pick, Jul-Oct to Oct 16 check, REF = 2021-11..2025). The "ATLAS today" row reproduces
funded25.py exactly. Weights as engine/account_b.funded_qty: micros x w, min 1, never above the funded preset.
Gate (declared in the tool): funded $ a month better in both 2026 halves, no-payout and first payout not worse in
either, REF $ not lower, 2-4 trades a week (top = max(4, today's + 0.1): today already trades 4.06 a week in Jan-Jun).

| Idea (kind) | $/mo Jan-Jun | $/mo Jul-Oct | REF | 1st payout (sessions) | No payout 6 m | Trades/wk, PF at $250 | Gate |
|---|---|---|---|---|---|---|---|
| **ATLAS today** | **$592** | **$497** | $48 | 18 / 26 | 5.0 / 5.5% | 4.06 / 2.95, PF 2.92 / 2.55 | bar |
| drop S/R | $417 | $464 | $39 | 26 / 33 | 10.5 / 0.2% | 3.05 / 2.05 | no |
| drop EMA | $558 | $155 | $41 | 23 / 53 | 3.7 / 32.3% | 2.23 / 1.86 | no |
| drop MACD | $566 | $453 | $49 | 24 / 28 | 3.5 / 9.8% | 3.24 / 2.31 | no |
| S/R x0.5 / x0.75 | $559 / $575 | $509 / $520 | $47 / $49 | 21-20 / 30-28 | | | no (Jan-Jun down) |
| EMA x0.5 / x0.75 | $601 / $602 | $390 / $430 | $47 / $49 | | | | no (Jul-Oct down) |
| MACD x0.5 / x0.75 | $581 / $586 | $506 / $506 | $50 / $48 | | | | no (Jan-Jun down) |
| + both hunts x0.5 (re-measure, round 3) | $632 | $596 | $70 | 17 / 18 | 2.3 / 5.8% | **5.51 / 5.83** | no (trades/wk, no-pay Jul-Oct) |
| + trend hunt x0.5 (re-measure) | $609 | $613 | $58 | 17 / 21 | 3.7 / 1.8% | **4.77 / 4.04** | no (trades/wk) |
| skip VIX < 14 (post-hoc) | $592 | $497 | $50 | 18 / 26 | 5.0 / 5.5% | | no (no 2026 trade) |
| skip VIX < 14.5 (post-hoc, neighbour) | $592 | $547 | $51 | 18 / 25 | 5.0 / 2.7% | 4.06 / 2.76 | no (Jan-Jun equal) |
| **skip VIX < 15 (post-hoc)** | **$599** | **$582** | $51 | **18 / 23** | **4.3 / 1.0%** | 3.91 / 2.50, PF 3.12 / 3.56 | passes the money gate |
| skip VIX < 15.5 (post-hoc, neighbour) | $596 | $490 | $40 | 18 / 31 | 4.0 / 0.3% | 3.79 / 1.73 | no |
| skip VIX < 16 (post-hoc) | $587 | $330 | $36 | 20 / 43 | 3.5 / 1.5% | 3.44 / 1.03 | no |
| half size VIX < 15 (post-hoc) | $596 | $561 | $50 | 18 / 25 | 4.8 / 1.3% | 4.06 / 2.95 | passes the money gate |

Same rules with LIT + ATLAS $250 on the funded 25K (built OFF, engine/lit25.py; this tool drops an ATLAS trade LIT would
cut, slightly conservative): today $602 / $522, 1st payout 15 / 18, no payout 7.0 / 13.2%; skip VIX < 15 $605 / $577,
15 / 17, 6.8 / 8.3%.

**Random-skip control** (tools/atlas_revive.py placebo, 300 paths): skipping the same number of trades per span on
random days (4 Jan-Jun, 7 Jul-Oct, 272 REF) matched the VIX < 15 gain in both halves in **0 of 40** draws (Jul-Oct gain
median -$78, p90 +$44 vs +$86). So the skipped trades really are bad ones - in 2021-24 too (245 trades, -0.10R, PF 0.83).

**Why it is still not a switch:**
- The proof rule picks on Jan-Jun. Jan-Jun had 5 sessions under VIX 15 and 4 ATLAS trades on them (+$7 a month):
  Jan-Jun cannot tell this rule from today. It was suggested by the diagnosis, which had already looked at Jul-Oct.
- It is a knife edge, not a plateau: 14.5 -> +$50, 15 -> +$85, 15.5 -> -$7, 16 -> -$167 a month in Jul-Oct. Jul-Oct had
  30 of 78 sessions with VIX 15-16, so a half point moves a third of the half's trades.
- The earlier tests of the same family were rejected: per-member VIX >= 14 / >= 16 gates on the eval (atlas.md, 15
  tries), funded per-member VIX terciles (atlas-funded-one-a-day-2026-10-31.md), VIX regime gates (atlas-v2.md).
- It would not have acted on one session since Oct 16 (VIX 16.6-28.2).
- Account B has no VIX gate today (it would need a new `account_b` key and code).

**Lead to watch (paper):** ATLAS trades on days with the prior VIX close under 15. If the next 20 such trades also lose,
re-test with that out-of-sample tally. No code needed now: atlas_revive_diag.json already splits by VIX.

## 3. Honest limits
- 2026 is 166 sessions; the last-40 window is 24 trades. A 3-trade member/side bucket says nothing.
- Fresh data = the PC's own paper ledgers (before the account rules) to Nov 6; Nov 9-16 are missing (PC silent).
- The funded money is a Monte Carlo of 5-session blocks; +-$10 a month is seed noise.

Files: `tools/atlas_revive.py` (diag, fixes, placebo), `research/second/atlas_revive_diag.json`,
`research/second/atlas_revive.json`, `research/second/atlas_revive_placebo.json`. Rerun:
`python -X utf8 tools/atlas_revive.py all` (~12 min).
