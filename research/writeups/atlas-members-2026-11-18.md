---
title: ATLAS new members (2026-11-18) - VWAP pullback, opening-drive 1m continuation, value-area re-entry, 15m Keltner squeeze and a prior-day POC touch; none adds winning days on the funded 25K, nothing changed
family: second
date: 2026-11-18
status: rejected (no change). All 5 families registered in the ZEUS Lab as kind atlas_member, status Rejected. second_model.json, data/account_b.json, live_model*.json untouched.
summary: Owner - "I want our strategies to keep getting stronger." ATLAS now trades his FUNDED Builder 25K, where payouts need many small winning days (50% consistency). 29 pre-declared versions in 5 families (VWAP pullback with trend 8, opening-drive continuation on a 1m trigger 8, prior-day value-area re-entry = Dalton 80% re-measure 1, 15m Keltner squeeze 8, own idea prior-day POC first touch 4), 5m NQ1! RTH, stop 1 tick beyond structure, one target (2R or ATLAS's VIX band), costs in, $250 a trade. 0 versions hold in H1 / H2 / 2025 / 2021-24 (coin-flip sides: 0 too). Two families have a Jan-Jun pick (opening drive k 0.75 by 09:45 + VIX band: H1 +$1,244 PF 1.59 on 18 trades; POC touch until 15:00 + VIX band: H1 +$1,601 PF 1.78 on 14) - both lose Jul-Oct alone. As a 4th ATLAS member on the funded 25K ($250 / 30% of the room, 600 paths x 126 sessions): opening drive $541 -> $578 Jan-Jun but $353 -> $253 Jul-Oct, no-payout 15.0 -> 34.3%, 4.49 trades a week; POC $521 / $279. Swapping S/R out keeps the trade count but loses ~$90 a month in both halves. Sign-flip p 0.12 / 1.0 vs the 0.0059 bar. Nothing passes.
runs: none (research/second/atlas_plus.json; tools/atlas_plus.py)
---

## For the owner

| What | Result |
|---|---|
| Tried | 5 new ATLAS member ideas, 29 versions, each written down before the run, costs in, $250 a trade |
| VWAP pullback with trend | **No.** All 8 versions lose in Jul-Oct; best Jan-Jun only +$204 (PF 1.04) |
| Opening-drive continuation (1m trigger) | **No.** Jan-Jun +$1,244 but Jul-Oct -$518, 2021-25 -$3,584. As a 4th member: Jul-Oct $353 -> $253 a month to you, no-payout chance 15% -> 34% |
| Yesterday's value-area re-entry (80% rule) | **No (already rejected 11-17).** Its stops are too wide for $250: only 3 Jan-Jun trades |
| 15m Keltner squeeze | **No.** Too rare (0.1-0.4 a week) and loses in 2025 / Jul-Oct |
| Yesterday's POC first touch (my idea) | **No.** Jan-Jun +$1,601, Jul-Oct -$127, 2025 -$8,238. As a member: $521 / $279 a month vs $541 / $353 |
| ATLAS on your funded 25K, as is | **$541 / $353 a month** at $250 / 30% of the room (Jan-Jun / Jul-Oct markets); first payout after 21 / 32 sessions |
| ZEUS Lab | All 5 show as **Rejected** on Business -> ZEUS Lab, with the reason |

Your steps: none. Keep ATLAS as it is.

## 1. What was already tested (not redone)
docs/TESTED_AND_REJECTED.md: VWAP reversion on low-VIX days + gap fade / failed opening drive (E2), the first pullback in a
London / NY leg (hq-continuation) and BLITZ's opening drive, the failed auction at the prior value edge + Dalton's 80% rule
(new-strategy hunt 11-17), VWAP side / distance as a size filter (ab_edge, strategy tree), NR7 / NR4 (public strategies),
every ATLAS member weight / drop (atlas-revive 11-17). New here: the VWAP PULLBACK with the trend as an entry, an opening
drive triggered on 1m, a 15m Keltner squeeze release, a prior-day POC touch, and each as an ATLAS member on the funded 25K.
The 80% rule was re-measured once as a member (its hunt cell d80_c1_u12_r2), not re-searched.

## 2. Method (tools/atlas_plus.py, hypotheses in its docstring, written before the run)
- Bars: CME NQ1! 5m RTH 2021-11 -> 2026-10-16 (tools/div_search.D); the opening-drive trigger uses data/NQ_1m.csv in 2026
  (1m exists only from 2026-01-02); 2021-25 runs the same rule on 5m bars (labelled).
- Execution = tools/div_search.walk (entry next open + 1 tick, stop first when a bar touches both, a target needs a
  trade-through, stop / 15:55 exits 1 tick worse), $1.90 a micro. Stops < 8 pts widened to 8, > 80 pts skipped (S/R's
  max_stop; the 80% re-measure keeps the hunt's own rules). Check: the re-measure at $500 reproduces the hunt exactly
  (H1 18 trades PF 1.56 +$1,127, H2 16 PF 0.77 -$704).
- One target: 2R or ATLAS's VIX band (open18 +- VIX/100/sqrt(252) x open18, at least 1.5R, at most 8R).
- Stage 1 (alone, $250): H1 pick = best Jan-Jun $ among versions with 12+ Jan-Jun trades and PF >= 1.2.
- Stage 2: the same versions with coin-flip sides, 10 seeds ("holds" = net > 0 and PF >= 1.1 in H1, H2, 2025, 2021-24).
- Stage 3: days next to ATLAS + LIT (green days the member adds where they were not green; its red days on their red days).
- Stage 4 (picks only): the live account-B rules (never opposite LIT incl. armed setups, HEDGE close, one position, max 2
  a day), funded 25K Monte Carlo of tools/atlas_revive (MFFU builder25k funded rules, 600 paths x 126 sessions) at
  $250 / 30% of the room (the preset "fq" sizing shown too: today $592 / $497 / $48 = atlas_revive exactly). Gate =
  atlas_revive.passes (funded $ up in both halves, no-payout / first payout not worse, 2021-25 not lower, 2-4 trades a week
  with today's 4.06 as the top) + green days up in both halves + red days shared with LIT not up > 0.2 a month. Shapes
  "+ member" and "+ member, S/R out".
- Stage 5 (ZEUS Lab guard): sign-flip p of the per-day $ change <= 0.2 / 34 cells = 0.0059 in both halves.

## 3. Alone at $250 a trade (best Jan-Jun version of each family)

| Family (cells) | Version | Jan-Jun n, /wk, PF, $ | Jul-Oct | 2025 | 2021-24 | Hold all 4 (coin-flip) |
|---|---|---|---|---|---|---|
| VWAP pullback (8) | until 12:00, s1 trend, 2R | 38, 1.54, 1.04, +$204 | 28, PF 0.85, -$608 | -$624 | -$7,794 | 0 (0) |
| Opening drive 1m (8) | k 0.75 by 09:45, VIX band | 18, 0.73, 1.59, +$1,244 | 12, PF 0.71, -$518 | -$43 | -$3,541 | 0 (0) |
| 80% rule re-measure (1) | 1 close inside, until 12:00, 2R | 3, 0.12, 2.04, +$249 | 5, +$259 | +$2,130 | +$6,654 | 0 (0) |
| Keltner squeeze (8) | N 4, box mid, VIX band | 2, 0.08, -, +$415 | 3, -$281 | -$851 | -$423 | 0 (0) |
| POC first touch (4) | until 15:00, VIX band | 14, 0.57, 1.78, +$1,601 | 10, PF 0.93, -$127 | -$8,238 | -$1,270 | 0 (0) |

- VWAP pullback: all 8 versions lose in Jul-Oct, 7 of 8 in Jan-Jun, 6 of 8 in 2021-25 (the two slope-only VIX-band ones
  make +$3-4k in 2021-25 but lose $2.9-4.8k in each 2026 half); 2-3.4 a week. Its red days land on ATLAS / LIT red days as often as chance (H2 2.76 vs 2.14 a month expected).
- Opening drive: 0.4-1.1 a week; the VIX-band versions are the Jan-Jun winners, the 10:00 drives win only in 2021-24 (5m
  proxy) - the two eras disagree.
- 80% rule at $250: its stops (median 105-163 pts) buy 0 micros on most days, so only 3 / 5 trades a year in 2026 are left.
  The trades that fit $250 are positive in every span (PF 1.8-2.3), but that is a post-hoc cut at 0.1-0.3 a week (adds
  ~0.3 green days a month): a note, not a lead.
- Keltner squeeze: 2-9 Jan-Jun trades in every version (BB inside KC on 15m RTH bars is rare); loses in 2025.

## 4. As a 4th ATLAS member on the funded 25K ($250 / 30% of the room)

| Shape | Jan-Jun $/mo, 1st payout, no-pay | Jul-Oct | 2021-25 $/mo | Trades/wk H1 / H2 | Green days/mo H1 / H2 | Gate |
|---|---|---|---|---|---|---|
| **ATLAS today** | **$541**, 21, 5.8% | **$353**, 32, 15.0% | $34 | 4.06 / 2.95 | 8.20 / 6.36 | bar |
| + opening drive | $578, 18, 4.7% | $253, 27, 34.3% | $32 | **4.49** / 3.59 | 8.54 / 6.08 | no |
| + opening drive, S/R out | $447, 22, 11.7% | $272, 32, 25.3% | $25 | 3.59 / 2.76 | 6.66 / 5.53 | no |
| + POC touch | $521, 21, 8.5% | $279, 30, 27.0% | $23 | **4.38** / 3.53 | 8.02 / 6.08 | no |
| + POC touch, S/R out | $423, 23, 14.0% | $263, 37, 22.0% | $17 | 3.48 / 2.69 | 6.49 / 5.25 | no |

Preset ("fq") sizing tells the same story: today $592 / $497 / $48; + opening drive $618 / $417 / $44; + POC $566 / $484 / $35.
Sign-flip p (per-day $ change): opening drive 0.12 / 1.0, POC 0.47 / 0.49 (bar 0.0059). The member's Jul-Oct trades are
losers that also take ATLAS's second slot of the day, so the funded account pays less and the no-payout risk doubles.

## 5. Honest limits
- 2026 is 166 sessions; the picks rest on 14-18 Jan-Jun trades.
- The 1m trigger is tested only in 2026; 2021-25 is the 5m version of the same rule.
- RTH only (ATLAS's EMA / MACD members also trade London); a London version of these ideas was not run.
- The funded $ is a Monte Carlo of 5-session blocks: +-$10 a month is seed noise.

## ZEUS Lab
Registered through `tools/zeus_lab.register` as kind `atlas_member` (new: the runner reads this tool's stored verdict;
"cells" = versions searched, so all 29 count in the many-tests bar): atlas_member_vwp / _odc / _pva / _ksq / _poc, all
Rejected with the reason (`python -X utf8 tools/zeus_lab.py status`). A future pass would go to the Lab's 4-week shadow.

Files: `tools/atlas_plus.py`, `research/second/atlas_plus.json`. Rerun: `python -X utf8 tools/atlas_plus.py all` (~1 min).
