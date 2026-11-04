---
title: LIT ideas night - 16 new ideas (165 versions) on the live LIT - partials and stair stops, a second cut check, news, VIX / time / weekday / price-place / setup-strength size tilts, streak size, entry windows, per-session thresholds, Monday rule review, scale-in with real costs
family: other
date: 2026-11-04
status: nothing to switch on today; one size tilt (stop tight in ATR) beats its shuffles in both halves and is the only candidate worth a forward paper check; three thin leads; everything else rejected
summary: Job 26. 16 new ideas for Zlarior (live LIT) written down with a reason, then run as 165 versions on the exact live trades (the re-walk equals all 631 live trades - every exit, point and micro), CME NQ futures, true 1m bars in 2026, costs in. Picked on Jan-Jun 2026, checked on Jul-Oct 2026, 2021-25 as a reference only. Money three ways - LIT size rule, the real MFFU 50K eval path (today's two_week sizing) and the funded 50K. No management change (partials, stair stops, stale exits, news exits, a later cut) and no entry-window or per-session change holds in both halves. One size idea survives - a bigger size when the stop is tight against the 5m ATR.
runs: lit_ideas_base, lit_ideas_tilt_stopatr_tight_up125, lit_ideas_tilt_fast_up125, lit_ideas_mgmt_tc2_at60_x00, lit_ideas_engine2_depth_max40, lit_ideas_engine_monday_off, lit_ideas_mgmt_partial_f050_r20, lit_ideas_mgmt_partial_f033_r3_lock15, lit_ideas_mgmt_ladder_3to10, lit_ideas_engine_win_end_1130
---

## For the owner (one minute)

| What | Result |
|---|---|
| What I did | 16 new ideas for Zlarior, run as **165 versions** on today's live trades (real CME NQ, true 1-minute bars in 2026, costs in). Picked on Jan-Jun 2026, checked on Jul-Oct 2026. |
| Today's bar to beat | Jan-Jun **+$33,901 ($5,562/mo, PF 4.98)**, Jul-Oct **+$9,919 ($2,670/mo, PF 2.91)**, 3.1 / 2.6 trades a week. Eval 2-week pass / fail **57.1 / 1.7%** and **52.2 / 5.8%**. |
| Change the live bot? | **No change tonight.** Nothing was switched on or off. |
| Partial exits (1/3 or 1/2 out at 1R, 2R, 3R, 4R), stair stops | **Worse.** Jan-Jun -$4.5k to -$17k and Jul-Oct down too; they only look good in the 2021-25 line, which is not a gate. |
| A second cut check, stale-trade exit, news exit | **Nothing.** A second check 60 minutes after the fill is +$526 / +$311 (14 trades): a thin lead, not a change. News exits touch 2 trades in 5 years. |
| Monday rule, weekly stop, entry windows, per-session thresholds | **Today's settings stay.** Monday rule off loses $2.1k / $0.3k; every window trim loses; no session setting beats today in both halves. |
| Size by VIX, time of day, weekday, VXN, ES, gamma, news, streak, setup strength (63 versions) | **All fail or are chance**, except one. |
| **The one that survives: bigger size when the stop is tight against the 5m ATR** | Size x1.25 (never above the $990 risk cap) on the third of trades with the smallest stop-to-ATR: LIT **+$4,957 / +$1,148** (2021-25 line +$1,709), eval path **+$4,680 / +$464**, 2-week pass unchanged, fails **not higher** (1.7 -> 1.7, 5.8 -> 0.0). Beats its shuffles in both halves (p 0.007 / 0.027). Funded pay unchanged ($931 / $912). Forward paper check first; see section 3. |
| Scale-in (still OFF), real costs | Worth **+$10.6k (Jan-Jun) / +$5.3k (Jul-Oct)** at LIT size but **three trades make most of it** (without them +$2.3k / +$1.7k). The real-cost drag (+4 ticks, $1.90 commission) is only $360 / $110, so costs are not the risk; one lost target (-$3.3k on 2026-01-07) is. Needs your Sim roundtrip first, as before. |

Your steps: none needed. If you want the one candidate tested, say "paper the stop-ATR tilt" (one line; nothing goes live).

## 1. The ideas, written down before testing (hypothesis for each)

| # | Idea | Why it could add money | Versions run |
|---|---|---|---|
| 1 | Partial exit and runner on the 8R target (1/3 or 1/2 out at 1R, 2R, 3R or 4R, the runner keeps today's rules, some with the runner stop locked at +0.5 to +2R) | bank something on trades that reach 2-4R and then die at BE | 12 |
| 2 | Adaptive breakeven: a stair stop (at +2R stop to +0.5R, at +3R to +1R, ...) and a small profit lock at the 1R breakeven (+0.1R / +0.25R instead of +1.25 pts) | a wide-stop trade that got to 3R should not give back to zero | 9 |
| 3 | A second cut check later (30 / 45 / 60 / 90 minutes) and the live check at 10 / 20 / 25 minutes | the 15-minute cut works (13 cuts in 2026); a second look may catch slower failures | 11 |
| 4 | Stale-trade exit (no breakeven after 1-4 hours and best point under 0.5R / 1R: out at the next open) | dead trades tie up the one-trade-a-day slot | 10 |
| 5 | News awareness: flat or breakeven 2-10 minutes before the next scheduled high-impact release; size x0.5 / x0.75 when a release is within 30 / 60 minutes or on a news day | event spikes are random | 8 + 3 size |
| 6 | VIX / VXN regime as SIZE (never skip): calm VIX x1.25, stressed x0.75, VIX fell / rose yesterday, VXN | the target is a VIX move, so the regime may change how often it is reached | 6 |
| 7 | Time-of-day size, written by session name (not mined): London 02-05 x1.25, NY AM x0.75, NY PM x0.75, ICT macro window, entered before 05:00 | London sweeps are the cleanest in the 2026 trades | 5 |
| 8 | Day-of-week size and Monday rule review (Monday / Friday x0.75, Tue-Wed x1.25, the Tue 03:00-Wed 11:30 high / low-of-week window as size, Monday rule off, Monday rule as half / quarter size instead of a skip) | the weekly high / low forms Tue-Wed; the Monday rule skips about 20 trades | 5 + 3 |
| 9 | Price against yesterday's range and the 18:00 open at the fill (discount / premium, outside / inside the range, prior day / week with or against the trade, gap with or against) | the target is the 18:00 open +/- 1 VIX move, so the entry place decides the room | 13 |
| 10 | Setup strength as SIZE (sweep depth, displacement, clear path to the next opposing level, climax-volume candle, fast CISD, quick fill, wick, inducement closeness, stop in ATR) plus a smooth A+ score (0.75x-1.25x and 0.5x-1.5x) | nothing is skipped, so 2+ a week is kept | 16 |
| 11 | Confluence: ES swept its own extreme too, SPX gamma sign and percentile, wide Asia / London range | SMT-style agreement | 8 |
| 12 | Streak size on LIT's own results (after a loss x0.75 / x1.25, after a win, two losses, week under -1R / over +2R) | cold hand / house money | 7 |
| 13 | Entry window refinements (end at 11:30 / 13:00 / 14:00 / 16:00, start 03:00, no lunch hour, London only, add 00:00-02:00, 00:00-02:00 alone) | the late or the early trades may drag | 9 |
| 14 | Per-session thresholds (displacement 0.6 / 1.0 / 1.3 ATR, sweep depth 0.3 / 0.8 ATR, bank 6R / 12R in each of four sessions); a sweep-depth ceiling (a breakout, not a sweep); stop caps 50-70 pts and floors 10-15 pts | one setting for all hours may not fit each | 28 + 9 |
| 15 | Weekly stop variants (3 stop-outs, 0.75 size, off) | the pack was picked in October | 3 |
| 16 | Scale-in re-measured with real costs and with the best trades removed (OFF today) | measure it honestly before you switch it on | numbers below |

Not re-run because it is already in "Tested and rejected": a 2nd trade on the same sweep, re-entry after the cut or BE, weekly catch-up, target-band variants, BE in ATR, 15m/1h structure trails, reversal exits, ATLAS-style hunts. (Overnight / Asia slot: tested as a window below.)

## 2. How it was run (so the numbers can be trusted)

- Same trades as run `lit_live` (631 trades, 120 in 2026). With every new option off the re-walk reproduces all 631 live exits and points, 0 mismatches (`python -X utf8 tools/lit_ideas_night.py check`).
- New management options decide at a bar's close and act from the next bar (no look-ahead). A partial needs the price to trade 1 tick through its level. Size tilts use only facts known at the fill (the trade-intel file, look-ahead tested). Cut points are terciles of the **Jan-Jun** trades only.
- Money three ways, as in the 10-30 edge night: LIT size rule (backtest), the real MFFU 50K eval path (today's two_week sizing, $1.90 a micro, 2-week pass / fail), the funded 50K (Monte Carlo of the Builder Sim Funded rules, today's funded preset).
- **Shuffle test for every size tilt:** the same multipliers are shuffled across the same span's trades (150 draws, then 800 for the finalist). A size-up on a profitable strategy always "makes more" - the test asks whether the tilt picks better trades than a random pick of the same size. p = share of shuffles with at least the tilt's $.
- **Gate (owner 2026-10-18):** more $ at LIT size AND on the eval path in **both** Jan-Jun and Jul-Oct, no rise in 2-week fails, 2+ trades a week, funded pay not worse.
- Note: the eval path in this tool shows Jul-Oct 2-week pass / fail 52.2 / 5.8 for today's settings (the October docs quote 0.0 fails; the room setting changed on 10-25). Compare every row to the 5.8, not to 0.0.

## 3. What to change on the live bot (owner decides)

**Nothing is recommended for switching on today.** Ranked by how much evidence they have:

1. **Candidate, forward paper check only - size x1.25 when the stop is tight against the 5m ATR** (`stop / ATR(14, 5m)` in the bottom third of the Jan-Jun trades, stop at or under 2.11 x ATR; micros x1.25, never above the existing $990 risk cap; nothing skipped).
   - Numbers (LIT size rule, costs in): Jan-Jun **+$38,858 vs +$33,901** (PF 5.37 vs 4.98, $6,375 vs $5,562/mo, max drop -$2,373 vs -$2,196); Jul-Oct **+$11,067 vs +$9,919** (PF 2.96, $2,980 vs $2,670/mo, max drop -$1,552 vs -$1,396); 2021-25 line +$2,974 vs +$1,265. Same 3.1 / 2.6 trades a week, 85% / 81% of weeks with 2+. 44 of the 120 trades in 2026 are sized up, none down.
   - Eval path: Jan-Jun **+$39,502 vs +$34,822**, 2-week pass / fail 57.1 / 1.7 (same); Jul-Oct **+$16,728 vs +$16,264**, 52.2 / **0.0 vs 5.8** (pass unchanged, fails down); median pass 6 / 5 sessions (same); decided-in-2-weeks Jul-Oct 58.0 -> 52.2 only because the 5.8% fails went away. Funded 50K: $931 / $912 a month vs $929 / $915 (unchanged).
   - Evidence: beats the shuffles in both halves (p 0.007 Jan-Jun, 0.027 Jul-Oct, 150 draws); 800-draw shuffle: p 0.016 (Jan-Jun) and 0.035 (Jul-Oct), both together under 0.0013 (none of 800 shuffles). Neighbours (smallest quarter / third / half of stop-to-ATR, size x1.15 / x1.25 / x1.5, `research/lit/ideas_night_robust.json`): LIT $ up in both halves in all 9 (Jan-Jun +$2.0k to +$11.5k, Jul-Oct +$0.5k to +$2.8k); eval-path $ up in both halves in 6 of 9 (the half-cut is slightly down in Jul-Oct, -$50 to -$960); 2-week fails never above today except +0.8 points in Jan-Jun for the half-cut at x1.25 / x1.5; 2021-25 reference up in 6 of 9 (the quarter-cut is down -$0.5k to -$0.8k). Year by year (LIT size, change vs today): 2021 -$168, 2022 +$1,320, 2023 -$98, 2024 -$1,069, 2025 +$1,724, 2026 +$6,106 - so the 2021-25 line is mixed (2 up, 3 down); the gain is a 2026 gain. Together with the fast-CISD tilt: +$7,768 / +$2,678. Making the loosest third smaller (x0.85) as well does not help (Jul-Oct -$449, fails +2.5 in Jan-Jun).
   - Why not switch it on: it is one of 63 size tilts I tried, so with a Bonferroni penalty the bar is p < 0.0008 (0.05 / 63), and 800 shuffles can only say p < 0.0013 (adjusted p < 0.08): borderline, not proven. The Jul-Oct gain is +$1,148 on 13 changed trades; the idea ("a shallow sweep extreme next to a normal-sized ATR is the cleanest setup") was not written down before; the funded accounts gain nothing from it. It also adds risk (more micros) on the eval, where today's cap logic still applies.
   - If you want it: it is a pure size rule in `engine/sizing.py` / `lit_sizing` (new field), paper first for 4 weeks with the Live learning twin; I changed nothing.
2. **Thin lead - a second cut check 60 minutes after the fill** (if the breakeven has not moved the stop, the best point is under +0.5R and the close is below the entry: out at the next open, like the 15-minute check). LIT +$526 / +$311, eval path +$1,966 / +$2,859, 2-week pass / fail unchanged, funded $974 / $949 vs $929 / $915. It cuts 14 trades in 2026 (10 + 4) and changes 0 trades in 2021-25 (no 1m bars). The neighbours (60 min with x 0.3, 90 min) are positive but smaller (+$174 / +$42, +$213 / +$68). One of 50 management versions: chance-level. Re-check after the first 30 live cuts.
3. **Thin lead - fast extreme -> CISD size x1.25** (CISD within the bottom third of bars): LIT +$2,747 / +$1,062 (2021-25 +$2,045), shuffle p_both 0.026 (800 draws), but Jan-Jun 2-week fails 1.7 -> 2.5 and Jul-Oct dec10 -1.5: fails the no-more-fails rule. Not recommended.
4. **Not a lead, mixed - sweep-depth ceiling 4 ATR** (skip sweeps deeper than 4 ATR beyond the level: "a breakout, not a sweep"): LIT +$1,633 / +$1,741, Jul-Oct 2-week pass 66.7% vs 52.2% and fails 0 vs 5.8, but eval-path $ -$5,773 / -$1,735, 2021-25 -$3,337, trades 2.8 / 2.3 a week and funded -$55 in Jan-Jun. Mixed, not adopted.

## 4. Rejected tonight and why

| Idea | Result (vs today, Jan-Jun / Jul-Oct) | Why rejected |
|---|---|---|
| Partial 1/3 or 1/2 at 1R / 2R / 3R / 4R, runner to 8R | LIT -$4.7k to -$12.5k / -$0.6k to -$4.5k (best: 1/3 at 4R: -$4,725 / -$597) | The 8R winners are the profit; banking early costs more than it saves. Only the 2021-25 reference line improves (+$1.5k to +$13k), which is not a gate. |
| Partial + runner locked at +0.5 to +2R | -$4.5k to -$17.0k / -$0.5k to -$3.3k | Same, plus the lock stops out runners that later reach 8R. |
| Stair stops (2R -> +0.5R ... 6R -> +4R), BE with a small profit (+0.1R / +0.25R) | -$6.6k to +$1.2k / -$1.2k to +$0.8k; best Jan-Jun (2R -> +0.5R) +$1,228 but Jul-Oct -$221 | No version is up in both halves with the eval path; the ones up in Jul-Oct (3R -> +1R: +$817) lose Jan-Jun. |
| Live cut check at 10 / 20 / 25 minutes | at 10: +$2,037 / -$421; at 20: -$961 / -$214; at 25: -$736 / -$1,696 | 15 stays the best. |
| Second check at 30 / 45 / 90 minutes | 30: +$3,016 / -$1,987; 45: +$2,534 / -$2,352 | Up in Jan-Jun only; fails more in Jul-Oct. |
| Stale-trade exit (1-4 hours) | 60 min: -$4,236 / -$3,512 (best +$898 / -$1,955) | Slow trades often get there later; 2021-25 down too. |
| News: flat / BE before the next release; size down near or on news days | 0 trades changed in 2026 (2 in 2021-25); size tilts -$1.8k / -$0.3k | Almost all LIT trades are over before 08:30; news-day size-down loses. |
| VIX / VXN size (calm up, stress down, VIX change, VXN) | stress down -$3,087 / $0; calm up +$3,392 / +$654 but p 0.15 / 0.65 | Down-tilts lose in Jan-Jun; calm-up is no better than shuffled size. |
| Time-of-day size (London up, NY AM / PM down, macro window) | London up +$4,068 / +$531, p 0.33 / 0.35 | A size-up on London trades (the bulk of trades) is just more size. |
| Day-of-week size, high/low-of-week window, Monday / Friday down | Monday down -$1,294 / -$210; Friday down -$2,896 / -$202; how-window up +$2,340 / +$777 (p 0.45 / 0.15) | No pre-written weekday beats shuffled size. |
| Monday rule off, or as half / quarter size instead of a skip | off: -$2,113 / -$305; half: -$1,848 / -$305 | The rule earns its keep: keep it as a skip. |
| Weekly stop: off, 3 stop-outs, 0.75 size | off: +$1,453 / -$233; 3: +$1,620 / -$234; 0.75: +$622 / $0 | Better in Jan-Jun only, worse in Jul-Oct; the funded side is slightly worse too. Keep. |
| Price place: discount / premium vs the 18:00 open; inside / outside yesterday's range; prior day / week; gap | discount-up +$2,177 / +$229 (p 0.49 / 0.55); premium-down -$3,478 / -$2,351; prior-day-with-trade-up +$3,823 / +$446 (p 0.06 / 0.45, Jul-Oct fails +4.3) | None beats shuffled size in both halves with no more fails. |
| Setup strength as size: depth, displacement, clear path, climax volume, wick, quick fill, inducement distance, stop in ATR (wide down) | down-tilts all lose; up-tilts +$0.8k to +$2.6k / small, eval path loses in Jul-Oct for most | Setup strength is not information beyond what the filters already use. |
| Smooth A+ score size (0.75x-1.25x, 0.5x-1.5x) | -$2,871 / -$930 and -$3,455 / -$537 | Worse than today, even with nothing skipped (confirms the 10-30 result). |
| ES swept too, gamma sign / percentile, Asia / London range | ES up +$5,302 / +$865 (p 0.51 / 0.21, Jul-Oct fails +4.3); the rest negative or chance | Chance. |
| Streak size on LIT (after a loss / win, two losses, week red / green) | between -$2.8k and +$4.0k; best after-loss-up +$1,462 / +$995 (p 0.72 / 0.09) | No hot or cold hand to size on (and the weekly stop already exists). |
| Entry window: end 11:30 / 13:00 / 14:00 / 16:00, start 03:00, no lunch, London only, 00:00-02:00 | end 11:30 -$1,858 / -$501; start 03:00 -$11,570 / -$5,484; London only -$6,383 / +$10; 00:00-02:00 added -$5,412 / +$904; alone -$35,518 / -$9,747 | The whole window earns; the 00:00-02:00 slot loses (reference line too). |
| Per-session thresholds (28) incl. bank 6R / 12R per session | none up in both halves (the best are $0 in Jul-Oct); 02:00-05:00 settings lose most (disp 1.3: -$18,278 / -$7,582) | Today's single setting is on a plateau; the 02:00-05:00 session carries the edge. |
| Stop floors / caps (min 10 / 12 / 15, max 50 / 60 / 70), sweep-depth ceiling 2 / 3 ATR | min 15: -$5,321 / $0; max 50: $0 / -$879; ceiling 2: -$9,819 / -$1,207 | The 8-80 pt range stays. |

## 5. Multiple testing (how much luck to expect)

- 165 versions were scored: 50 management, 63 size tilts (56 facts + 7 streak), 10 entry-window and 42 per-session / cap / Monday / weekly-stop runs. Of the 63 tilts, 27 were better in both halves and got a shuffle test (the other 36 lose in one half already). A random size-up passes "more $ in both halves" in 30-96% of shuffles (`chance_both` in the results file), so "up in both halves" means nothing for a size-up; only the shuffle p-values do.
- Bonferroni on the 63 tilts: p must be under 0.05 / 63 = 0.0008. Of the 63, only stop-ATR-tight (p_both < 0.0013 in 800 shuffles) comes near; fast-CISD (0.026), prior-day-with (0.013, 150 draws, but fails the eval path) and obstacle-room (0.027, fails the eval path) do not. A White-style reality check was not run; with this many versions the honest reading is "one lead, probably real size of about half what Jan-Jun shows".
- Management versions have no shuffle control; the second cut check is one of 50.
- Costs and the rule that LIT is judged on 2026: 2021-25 is shown only as a reference; stop-ATR (+$1,709, but only 2 of 5 years up) and fast-CISD (+$2,045) also improve it; the second cut check cannot be tested there (no 1m bars).

## 6. Scale-in, measured honestly (still OFF)

From `tools/lit_edge.py si_slip` (10-30) and a new per-trade look tonight (`python tools/lit_ideas_night.py scale` -> `research/lit/ideas_night_scale.json`; the engine's scale-in as built, 53 trades with adds in 2026):

| Item | Jan-Jun | Jul-Oct |
|---|---|---|
| Extra $ from the adds at LIT size, costs in | **+$10,620** (35 trades) | **+$5,345** (18 trades) |
| Best 3 trades | +$2,929, +$2,913, +$2,504 | +$1,769, +$1,010, +$912 |
| Without the best 3 | **+$2,274** | **+$1,654** |
| Worst trade | -$3,301 (2026-01-07: add moved the stop and a target winner became a BE) | -$404 |
| Micros added | 145 | 45 |
| Extra cost if every add fills 4 ticks worse and pays the real $1.90 | -$362 | -$112 |
| Eval path with all adds (10-30 tool) / adds only from session 5 | +$48.6k / +$38.7k; 2-week pass 58.8 / 60.5 | +$30.9k / +$24.9k; 2-week pass 59.4 / 58.0 |
| Eval path with every add 4 ticks worse | +$47.3k / +$37.7k | +$30.5k / +$24.6k |

Reading: costs are not what could hurt scale-in (4 ticks costs $360 and $110). Concentration is: three trades are 78% of Jan-Jun and 69% of Jul-Oct. It is still positive without them, and it still needs your Sim roundtrip first. Unchanged advice from 10-30: if you switch it on, only on the eval from session 5, never on funded.

## 7. Files and rerun

- `tools/lit_ideas_night.py` (`check`, `grid mgmt tilt streak engine engine2`, `robust`, `report`, `save`): results `research/lit/ideas_night_grid*.json` (every version, full numbers), `research/lit/ideas_night_results.json` (headline), `research/lit/ideas_night_robust.json` (neighbours, long shuffle, per-year).
- Runs (full trades, scored): see the front matter. Nothing in `engine/`, `live_model*.json` or sizing was touched.

## Appendix - every version (change vs today)

### Trade management (after the fill)

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades/wk | shuffle test (p Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| partial_f0.33_r1.0 | -8,344 / -3,016 | +1,557 | -15,496 / -4,886 | -31.9 / -17.4 | +0.0 / -5.8 | -57 / -144 | 3.12 / 2.56 | n/a |
| partial_f0.33_r2.0 | -7,206 / -1,911 | +1,960 | -14,406 / -5,190 | -24.3 / -11.6 | +0.0 / -5.8 | -63 / -48 | 3.12 / 2.56 | n/a |
| partial_f0.33_r3.0 | -5,521 / -716 | +7,873 | -15,388 / -2,723 | -21.0 / -7.3 | +0.0 / -5.8 | -47 / 0 | 3.12 / 2.56 | n/a |
| partial_f0.33_r4.0 | -4,725 / -597 | +4,453 | -15,596 / +3,524 | -16.8 / +0.0 | +2.5 / +0.0 | -37 / 0 | 3.12 / 2.56 | n/a |
| partial_f0.50_r1.0 | -12,516 / -4,524 | +2,336 | -22,535 / -10,365 | -46.2 / -37.7 | +0.0 / -5.8 | -95 / -270 | 3.12 / 2.56 | n/a |
| partial_f0.50_r2.0 | -10,810 / -2,866 | +2,940 | -21,898 / -5,049 | -40.3 / -13.1 | +2.5 / -5.8 | -93 / -97 | 3.12 / 2.56 | n/a |
| partial_f0.50_r3.0 | -8,282 / -1,074 | +11,810 | -14,857 / -4,017 | -25.2 / -11.6 | +0.0 / -5.8 | -71 / -12 | 3.12 / 2.56 | n/a |
| partial_f0.50_r4.0 | -7,088 / -895 | +6,679 | -16,794 / +922 | -22.6 / +1.4 | +0.0 / +0.0 | -70 / 0 | 3.12 / 2.56 | n/a |
| partial_f0.50_r2_lock1 | -16,996 / -3,300 | +4,893 | -19,761 / -7,994 | -38.6 / -29.0 | +0.0 / -5.8 | -209 / -216 | 3.12 / 2.56 | n/a |
| partial_f0.50_r4_lock2 | -8,562 / -792 | +9,051 | -16,923 / +3,214 | -22.6 / +0.0 | +0.0 / +0.0 | -110 / 20 | 3.12 / 2.56 | n/a |
| partial_f0.33_r3_lock1.5 | -7,665 / -455 | +13,032 | -17,577 / -2,514 | -22.6 / -5.8 | +2.5 / -5.8 | -111 / 10 | 3.12 / 2.56 | n/a |
| partial_f0.25_r2_lock0.5 | -4,484 / -1,599 | +2,295 | -14,883 / -3,904 | -20.1 / -8.7 | +0.0 / -5.8 | 0 / -85 | 3.12 / 2.56 | n/a |
| ladder_2to0.5 | +1,228 / -221 | +1,099 | +1,915 / +142 | +0.0 / +0.0 | +0.0 / -5.8 | 31 / -52 | 3.12 / 2.56 | n/a |
| ladder_3to1.0 | -504 / +817 | +1,685 | -1,510 / +4,281 | +0.0 / +1.4 | +0.8 / -5.8 | -33 / 55 | 3.12 / 2.56 | n/a |
| ladder_4to2.0 | -2,949 / +206 | +4,744 | -3,695 / +4,341 | +0.0 / +1.4 | +1.7 / +0.0 | -61 / 38 | 3.12 / 2.56 | n/a |
| ladder_3to1.0_5to3.0 | -5,068 / +817 | +3,931 | -6,762 / +4,281 | -0.8 / +1.4 | +0.8 / -5.8 | -105 / 55 | 3.12 / 2.56 | n/a |
| ladder_2to0.5_4to2.0_6to4.0 | -5,734 / -64 | +5,092 | -2,017 / +2,047 | -13.4 / +1.4 | +1.7 / -5.8 | -85 / -27 | 3.12 / 2.56 | n/a |
| ladder_2.5to1.0_5to2.5 | -6,596 / +817 | +3,083 | -6,356 / +4,281 | -2.5 / +1.4 | +0.8 / -5.8 | -122 / 55 | 3.12 / 2.56 | n/a |
| tc2_at30_x0.0 | +3,016 / -1,987 | +0 | +3,662 / -2,344 | +1.7 / -13.1 | +1.7 / -5.8 | 43 / -212 | 3.12 / 2.56 | n/a |
| tc2_at30_x0.3 | +304 / -1,508 | +0 | +1,677 / -6,885 | +0.0 / -8.7 | +1.7 / -5.8 | 24 / -183 | 3.12 / 2.56 | n/a |
| tc2_at45_x0.0 | +2,534 / -2,352 | +0 | +1,898 / -616 | +1.7 / -11.6 | +0.0 / +0.0 | 28 / -309 | 3.12 / 2.56 | n/a |
| tc2_at45_x0.3 | +2,229 / -913 | +0 | +130 / -413 | +0.9 / -8.7 | +0.0 / +0.0 | 17 / -122 | 3.12 / 2.56 | n/a |
| tc2_at60_x0.0 | +526 / +311 | +0 | +1,966 / +2,859 | +0.0 / +0.0 | +0.0 / +0.0 | 45 / 34 | 3.12 / 2.56 | n/a |
| tc2_at60_x0.3 | +174 / +42 | +0 | +1,522 / +2,566 | +0.0 / +0.0 | +0.0 / +0.0 | 16 / 8 | 3.12 / 2.56 | n/a |
| tc2_at90_x0.0 | +213 / -252 | +0 | +186 / +3,254 | +0.0 / +0.0 | +0.0 / +0.0 | 16 / -26 | 3.12 / 2.56 | n/a |
| tc2_at90_x0.3 | +213 / +68 | +0 | +186 / +3,531 | +0.0 / +0.0 | +0.0 / +0.0 | 16 / 13 | 3.12 / 2.56 | n/a |
| tc1_at10 | +2,037 / -421 | +0 | -2,743 / -2,129 | +0.0 / -1.5 | +1.7 / +0.0 | -20 / -48 | 3.12 / 2.56 | n/a |
| tc1_at20 | -961 / -214 | +36 | -2,169 / -161 | +0.0 / -1.5 | +0.0 / +0.0 | -70 / -9 | 3.12 / 2.56 | n/a |
| tc1_at25 | -736 / -1,696 | -24 | -1,088 / -3,645 | +0.0 / -8.7 | +0.0 / -5.8 | -35 / -158 | 3.12 / 2.56 | n/a |
| stale_m60_r0.5 | +898 / -1,955 | -4,901 | +2,556 / -3,011 | +0.9 / -11.6 | +0.0 / -5.8 | 43 / -251 | 3.12 / 2.56 | n/a |
| stale_m60_r1.0 | -4,236 / -3,512 | -19,213 | -7,584 / -8,323 | -3.3 / -10.2 | +1.7 / -4.4 | -89 / -439 | 3.12 / 2.56 | n/a |
| stale_m90_r0.5 | +537 / -1,344 | -5,221 | +421 / -862 | +0.9 / -2.9 | +0.0 / -5.8 | 18 / -148 | 3.12 / 2.56 | n/a |
| stale_m90_r1.0 | -2,932 / -2,604 | -683 | -838 / -4,796 | +0.0 / -5.8 | +0.0 / -4.4 | -9 / -287 | 3.12 / 2.56 | n/a |
| stale_m120_r0.5 | +237 / -208 | +1,718 | +416 / +3,434 | +0.9 / +0.0 | +0.0 / -5.8 | -4 / -11 | 3.12 / 2.56 | n/a |
| stale_m120_r1.0 | -2,609 / -1,488 | -524 | -1,097 / -831 | +0.0 / +1.4 | +0.0 / -5.8 | -19 / -139 | 3.12 / 2.56 | n/a |
| stale_m180_r0.5 | +65 / +0 | -265 | +279 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -11 / 0 | 3.12 / 2.56 | n/a |
| stale_m180_r1.0 | +222 / -1,927 | -389 | +577 / -2,180 | +0.0 / -2.9 | +0.0 / +0.0 | -4 / -214 | 3.12 / 2.56 | n/a |
| stale_m240_r0.5 | +0 / +0 | -1,191 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| stale_m240_r1.0 | +0 / -1,072 | -296 | +0 / -741 | +0.0 / -1.5 | +0.0 / +0.0 | 0 / -129 | 3.12 / 2.56 | n/a |
| news_flat_lead2_r1 | +0 / +0 | +202 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_flat_lead5_r1 | +0 / +0 | +99 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_flat_lead10_r1 | +392 / +0 | -173 | +1,652 / +0 | +0.0 / +0.0 | -1.7 / +0.0 | 20 / 0 | 3.12 / 2.56 | n/a |
| news_flat_lead5_r0.5 | +0 / +0 | +0 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_be_lead5_r0.5 | +0 / +0 | +147 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_be_lead5_r1.0 | +0 / +0 | +0 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_be_lead5_r1.5 | +0 / +0 | +0 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| news_flat_or_be_lead5 | +0 / +0 | +99 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| ladder_1.0to0.1 | +499 / -46 | -3,322 | +1,334 / -1,772 | +0.9 / +0.0 | +0.0 / -5.8 | 5 / -4 | 3.12 / 2.56 | n/a |
| ladder_1.0to0.25 | -2,146 / -1,126 | +611 | -964 / -2,763 | +0.0 / +1.4 | +0.0 / -5.8 | 13 / -117 | 3.12 / 2.56 | n/a |
| ladder_1.5to0.5 | -4,411 / -1,248 | -1,526 | -3,207 / -2,916 | -1.6 / +1.4 | +0.0 / -5.8 | -91 / -175 | 3.12 / 2.56 | n/a |

### Size tilts (nothing skipped)

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades/wk | shuffle test (p Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| vix_lo_up125 | +3,392 / +654 | +275 | +2,845 / -636 | +0.0 / +0.0 | +0.0 / -1.5 | -1 / 3 | 3.12 / 2.56 | 0.153 / 0.653 |
| vix_hi_dn075 | -3,087 / +0 | -2,165 | -3,170 / +0 | -11.7 / +0.0 | +0.0 / +0.0 | -21 / 0 | 3.12 / 2.56 | worse in a half |
| vix_both | +305 / +654 | -1,890 | -477 / -636 | -11.7 / +0.0 | +0.0 / -1.5 | -18 / 3 | 3.12 / 2.56 | 0.253 / 0.653 |
| vixchg_up_dn075 | -2,508 / -2,768 | +1,226 | -10,888 / -4,068 | -12.6 / -14.5 | -1.7 / -5.8 | -18 / -40 | 3.12 / 2.56 | worse in a half |
| vixchg_dn_up125 | +1,661 / -447 | +1,493 | -896 / -1,639 | +2.6 / +0.0 | +0.0 / +4.3 | 4 / 6 | 3.12 / 2.56 | worse in a half |
| lon_up125 | +4,068 / +531 | +82 | +1,140 / +36 | +0.0 / +0.0 | +0.0 / -1.5 | -3 / 16 | 3.12 / 2.56 | 0.333 / 0.353 |
| lon_up_nypm_dn | +3,839 / +531 | +430 | +501 / -155 | +0.0 / +0.0 | +0.0 / -1.5 | -4 / 11 | 3.12 / 2.56 | 0.393 / 0.38 |
| early_up125 | +4,068 / +531 | +82 | +1,140 / +36 | +0.0 / +0.0 | +0.0 / -1.5 | -3 / 16 | 3.12 / 2.56 | 0.333 / 0.353 |
| fri_dn075 | -2,896 / -202 | +325 | -1,643 / +179 | -15.9 / +1.4 | +0.0 / +0.0 | -13 / -20 | 3.12 / 2.56 | worse in a half |
| how_dn075 | -2,912 / -2,420 | -6,488 | -7,595 / -2,718 | -5.8 / -10.2 | +0.0 / -5.8 | 16 / -78 | 3.12 / 2.56 | worse in a half |
| disc_up125 | +2,177 / +229 | +1,240 | +4,213 / -656 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / -1 | 3.12 / 2.56 | 0.487 / 0.547 |
| disc_both | -1,301 / -2,122 | +1,816 | +456 / -4,849 | -16.8 / -14.5 | +5.0 / -5.8 | -21 / -28 | 3.12 / 2.56 | worse in a half |
| prevday_against_up125 | +1,263 / +246 | -2,244 | +2,427 / -915 | +0.0 / +0.0 | +0.0 / +0.0 | 3 / 9 | 3.12 / 2.56 | 0.813 / 0.433 |
| prevwk_against_up125 | +1,413 / +792 | -1,130 | +757 / -325 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / 4 | 3.12 / 2.56 | 0.733 / 0.073 |
| gap_against_dn075 | -3,894 / -1,197 | +283 | -9,748 / -4,469 | -15.1 / -11.6 | -1.7 / +0.0 | -68 / -34 | 3.12 / 2.56 | worse in a half |
| depth_dn075 | -2,145 / -1,022 | -3,347 | -11,140 / -3,291 | -9.2 / +0.0 | -1.7 / -5.8 | -31 / -35 | 3.12 / 2.56 | worse in a half |
| obst_up125 | +1,617 / +1,138 | +678 | +3,119 / -258 | +0.0 / +0.0 | +0.0 / +4.3 | 6 / 5 | 3.12 / 2.56 | 0.633 / 0.04 |
| vec_up125 | +1,659 / +86 | -3,235 | +1,513 / -1,262 | +2.6 / +0.0 | +0.0 / +0.0 | -3 / -2 | 3.12 / 2.56 | 0.573 / 0.7 |
| fast_up125 | +2,747 / +1,062 | +2,045 | +2,990 / +298 | +0.0 / +0.0 | +0.8 / -1.5 | 0 / 8 | 3.12 / 2.56 | 0.373 / 0.067 |
| wait_short_up125 | +1,101 / +635 | +0 | +3,181 / +711 | +0.0 / +0.0 | +0.0 / +4.3 | 11 / 4 | 3.12 / 2.56 | 0.893 / 0.193 |
| stopatr_tight_up125 | +4,957 / +1,148 | +1,709 | +4,680 / +464 | +0.0 / +0.0 | +0.0 / -5.8 | 2 / -3 | 3.12 / 2.56 | 0.007 / 0.027 |
| wick_up125 | +2,275 / +249 | +1,654 | +2,607 / -681 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / 5 | 3.12 / 2.56 | 0.433 / 0.667 |
| pdpos_prem_dn075 | -4,710 / -2,584 | -1,550 | -5,897 / -1,533 | -21.8 / -7.3 | +0.0 / -5.8 | -23 / -17 | 3.12 / 2.56 | worse in a half |
| pdpos_inside_dn075 | -6,117 / -2,623 | +3,743 | -9,141 / -5,464 | -30.2 / -36.3 | +1.7 / -5.8 | 8 / -68 | 3.12 / 2.56 | worse in a half |
| asia_wide_dn075 | -3,956 / -752 | +2,205 | -2,544 / -1,235 | -11.7 / -4.4 | -1.7 / -5.8 | 0 / -20 | 3.12 / 2.56 | worse in a half |
| es_up125 | +5,302 / +865 | +550 | +5,561 / -254 | +0.0 / +0.0 | +0.0 / +4.3 | 13 / 8 | 3.12 / 2.56 | 0.513 / 0.207 |
| gex_neg_dn075 | -619 / +0 | -859 | -3,105 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -9 / 0 | 3.12 / 2.56 | worse in a half |
| gexpct_lo_dn075 | -3,266 / +0 | -2,001 | -7,028 / +0 | -10.0 / +0.0 | +0.0 / +0.0 | -12 / 0 | 3.12 / 2.56 | worse in a half |
| newsnear_dn075 | +138 / +0 | +173 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 5 / 0 | 3.12 / 2.56 | worse in a half |
| graded_075_125 | -2,871 / -930 | -3,755 | -13,325 / -1,760 | -16.8 / -14.5 | +0.0 / -5.8 | -31 / -58 | 3.12 / 2.56 | worse in a half |
| vxn_hi_dn075 | -2,949 / -424 | -1,488 | -4,390 / -3,525 | -10.0 / -11.6 | +0.0 / +0.0 | -13 / -15 | 3.12 / 2.56 | worse in a half |
| nyam_dn075 | -1 / -44 | +471 | +340 / -682 | +0.9 / +0.0 | +0.0 / +0.0 | 9 / -16 | 3.12 / 2.56 | worse in a half |
| macro_up125 | +1,207 / +645 | -1,928 | -470 / +487 | +0.0 / +0.0 | +0.0 / +0.0 | 1 / 8 | 3.12 / 2.56 | 0.393 / 0.147 |
| mon_dn075 | -1,294 / -210 | +867 | -7,620 / +1,243 | -5.8 / +0.0 | +0.0 / +0.0 | -60 / 18 | 3.12 / 2.56 | worse in a half |
| how_up125 | +2,340 / +777 | +3,687 | +1,022 / -88 | +0.0 / +0.0 | +0.0 / -5.8 | -2 / 13 | 3.12 / 2.56 | 0.453 / 0.147 |
| midweek_up125 | +3,334 / +777 | +2,535 | +1,720 / -107 | +0.0 / +0.0 | +0.0 / -5.8 | -3 / 13 | 3.12 / 2.56 | 0.36 / 0.22 |
| prem_dn075 | -3,478 / -2,351 | +576 | -2,658 / -5,446 | -16.8 / -14.5 | +5.0 / -5.8 | -22 / -26 | 3.12 / 2.56 | worse in a half |
| prevday_with_up125 | +3,823 / +446 | +516 | +536 / -1,129 | +2.6 / +0.0 | +0.0 / +4.3 | 0 / -2 | 3.12 / 2.56 | 0.06 / 0.453 |
| prevwk_with_up125 | +4,233 / -51 | +3,468 | -551 / -115 | +2.6 / +0.0 | +0.0 / -5.8 | 5 / 20 | 3.12 / 2.56 | worse in a half |
| gap_with_up125 | +1,541 / +426 | -1,211 | +2,001 / +149 | +2.6 / +0.0 | +0.0 / +0.0 | -3 / 2 | 3.12 / 2.56 | 0.66 / 0.28 |
| depth_up125 | +2,612 / +483 | -2,273 | +1,645 / -852 | +0.0 / +0.0 | +0.0 / -5.8 | -2 / -3 | 3.12 / 2.56 | 0.36 / 0.2 |
| disp_up125 | +1,505 / -298 | -2,706 | +1,440 / -1,202 | +2.6 / +0.0 | +0.0 / +0.0 | 2 / -10 | 3.12 / 2.56 | worse in a half |
| obst_dn075 | -2,610 / -659 | +808 | -630 / -183 | -7.5 / +0.0 | +0.0 / -5.8 | 6 / -10 | 3.12 / 2.56 | worse in a half |
| vec_dn075 | -5,990 / -3,065 | -4,029 | -13,059 / -4,922 | -26.8 / -2.9 | +1.7 / -5.8 | -52 / -21 | 3.12 / 2.56 | worse in a half |
| fast_dn_slow075 | -5,973 / -307 | +1,881 | -9,080 / -1,880 | -13.4 / +1.4 | +0.0 / -5.8 | -24 / -7 | 3.12 / 2.56 | worse in a half |
| stopatr_wide_dn075 | -183 / -1,597 | +2,677 | -85 / -1,868 | +0.0 / -1.5 | -1.7 / -5.8 | -10 / -40 | 3.12 / 2.56 | worse in a half |
| idm_dist_up125 | +2,455 / -323 | -2,481 | -43 / -1,340 | +0.0 / +0.0 | +0.0 / +4.3 | 3 / 5 | 3.12 / 2.56 | worse in a half |
| pdpos_disc_up125 | +1,262 / +92 | +926 | +3,584 / -819 | +0.0 / +0.0 | +0.0 / +4.3 | 11 / -3 | 3.12 / 2.56 | 0.773 / 0.667 |
| pdpos_outside_up125 | +1,295 / +702 | +3,071 | +3,991 / -1,228 | +0.0 / +0.0 | +0.0 / +4.3 | 9 / -3 | 3.12 / 2.56 | 0.58 / 0.16 |
| asia_wide_up125 | +797 / +1,006 | -620 | +2,250 / -718 | +0.0 / +0.0 | +0.0 / -5.8 | 8 / 2 | 3.12 / 2.56 | 0.913 / 0.04 |
| lon_rng_dn075 | -1,375 / -385 | -1,037 | -6,033 / +4,111 | +0.9 / +4.3 | +0.0 / +0.0 | 2 / 55 | 3.12 / 2.56 | worse in a half |
| es_dn075 | -1,449 / -500 | -337 | -3,164 / +1,800 | -6.7 / -5.8 | -1.7 / -5.8 | 15 / -11 | 3.12 / 2.56 | worse in a half |
| gexpct_hi_up125 | +3,296 / +139 | -1,489 | -257 / -1,490 | +2.6 / +0.0 | +0.0 / -1.5 | -5 / -13 | 3.12 / 2.56 | 0.173 / 0.793 |
| newsnear_dn05 | +276 / +0 | +186 | +1,677 / +0 | +0.0 / +0.0 | -1.7 / +0.0 | 10 / 0 | 3.12 / 2.56 | worse in a half |
| newsday_dn075 | -1,834 / -257 | +96 | -6,621 / +200 | -7.5 / +1.4 | +0.0 / +0.0 | 2 / -14 | 3.12 / 2.56 | worse in a half |
| graded_05_15 | -3,455 / -537 | -6,473 | -14,522 / -1,477 | -19.3 / -13.1 | +0.0 / -5.8 | -65 / -79 | 3.12 / 2.56 | worse in a half |

### Size after LIT's own streak

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades/wk | shuffle test (p Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| after_loss_dn075 | -1,310 / -2,234 | +1,322 | -4,463 / -1,615 | -11.7 / -1.5 | +0.0 / -5.8 | -18 / -12 | 3.12 / 2.56 | worse in a half |
| after_loss_up125 | +1,462 / +995 | -401 | +1,106 / -833 | +0.0 / +0.0 | +0.0 / -5.8 | -1 / 3 | 3.12 / 2.56 | 0.72 / 0.087 |
| after_win_up125 | +1,880 / +212 | -1,328 | -761 / -199 | +0.0 / +0.0 | +0.0 / +4.3 | 0 / 10 | 3.12 / 2.56 | 0.393 / 0.48 |
| after_win_dn075 | -2,804 / -1,290 | +2,833 | -8,184 / -1,113 | -3.3 / -2.9 | +0.0 / +0.0 | -22 / -29 | 3.12 / 2.56 | worse in a half |
| after_2loss_dn05 | +37 / -1,023 | +739 | -1,022 / -750 | +1.7 / +0.0 | -1.7 / +0.0 | 19 / -21 | 3.12 / 2.56 | worse in a half |
| wk_red_dn075 | +309 / -350 | +1,937 | -2,344 / +2,293 | +0.9 / -1.5 | +5.0 / +0.0 | 25 / -13 | 3.12 / 2.56 | worse in a half |
| wk_green_up125 | +3,962 / -67 | -1,058 | +3,346 / -1,248 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 20 | 3.12 / 2.56 | worse in a half |

### Entry window

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades/wk | shuffle test (p Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| monday_off | -2,113 / -305 | +3,749 | -4,826 / -449 | -6.7 / +0.0 | +1.7 / -5.8 | -196 / -55 | 3.32 / 2.69 | n/a |
| win_end_1130 | -1,858 / -501 | -97 | -2,727 / -255 | -1.6 / +0.0 | +0.0 / +0.0 | -71 / -56 | 3.05 / 2.44 | n/a |
| win_end_1300 | -918 / -501 | +708 | -2,194 / -255 | -1.6 / +0.0 | +0.0 / +0.0 | -48 / -56 | 3.09 / 2.44 | n/a |
| win_end_1400 | +0 / +0 | +1,147 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| win_start_0300 | -11,570 / -5,484 | +1,196 | -11,234 / -10,719 | -14.2 / -27.6 | -1.7 / +0.0 | -312 / -558 | 2.66 / 2.18 | n/a |
| win_london_only_0200_0800 | -6,383 / +10 | +5,473 | -4,585 / +2,444 | -1.6 / +0.0 | -1.7 / -5.8 | -241 / 30 | 2.54 / 2.05 | n/a |
| win_no_lunch_1130_1330 | -939 / -501 | -1,318 | -533 / -255 | +0.0 / +0.0 | +0.0 / +0.0 | -21 / -56 | 3.09 / 2.44 | n/a |
| win_pre_london_0000_0200_plus | -5,412 / +904 | -8,342 | -2,786 / -189 | -1.6 / +2.9 | -1.7 / -5.8 | -110 / 129 | 3.24 / 2.82 | n/a |
| win_0000_0200_only | -35,518 / -9,747 | -12,388 | -35,530 / -15,268 | -57.1 / -37.7 | -1.7 / -5.8 | -929 / -872 | 0.51 / 0.45 | n/a |
| win_late_ext_1600 | +0 / +1 | -188 | +0 / +319 | +0.0 / +1.4 | +0.0 / +0.0 | 0 / 1 | 3.12 / 2.69 | n/a |

### Per-session thresholds, caps, Monday / weekly stop

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades/wk | shuffle test (p Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| kz_s0200_0500_disp0.6 | +2,725 / -6,070 | -15,974 | -1,309 / -3,649 | +3.4 / -1.5 | +0.0 / -5.8 | -21 / -386 | 3.4 / 2.76 | n/a |
| kz_s0200_0500_disp1.0 | -10,535 / -4,278 | -10,324 | -17,124 / -2,776 | -18.4 / -2.9 | -1.7 / +0.0 | -343 / -364 | 2.77 / 2.31 | n/a |
| kz_s0200_0500_disp1.3 | -18,278 / -7,582 | -11,479 | -16,733 / -12,787 | -21.8 / -39.2 | -1.7 / -5.8 | -401 / -806 | 2.42 / 1.79 | n/a |
| kz_s0200_0500_depth0.3 | +1 / -617 | -1,149 | +0 / -3,703 | +0.0 / -8.7 | +0.0 / +0.0 | 1 / -97 | 3.16 / 2.56 | n/a |
| kz_s0200_0500_depth0.8 | +343 / -1,465 | -526 | +24 / -5,207 | +0.0 / -11.6 | +0.0 / +0.0 | 24 / -143 | 3.05 / 2.44 | n/a |
| kz_s0200_0500_bank6 | -6,820 / -2,115 | +2,400 | -1,911 / -7,464 | +0.0 / -7.3 | +0.0 / -1.5 | -79 / -139 | 3.12 / 2.56 | n/a |
| kz_s0200_0500_bank12 | -4,008 / -524 | +8,011 | -11,964 / -3,130 | -11.7 / -4.4 | -1.7 / -4.4 | -235 / -253 | 3.12 / 2.56 | n/a |
| kz_s0500_0800_disp0.6 | -2,549 / +2 | +7,218 | -1,082 / +0 | +1.7 / +0.0 | +0.0 / +0.0 | -89 / 0 | 3.24 / 2.63 | n/a |
| kz_s0500_0800_disp1.0 | -648 / -3,798 | -9,047 | -3,943 / -6,729 | +0.0 / -10.2 | +0.0 / -1.5 | -50 / -229 | 3.01 / 2.31 | n/a |
| kz_s0500_0800_disp1.3 | -5,231 / -3,417 | -13,777 | -9,071 / -4,872 | -5.8 / -7.3 | -0.9 / -1.5 | -204 / -152 | 2.77 / 2.12 | n/a |
| kz_s0500_0800_depth0.3 | +0 / +0 | +1,172 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| kz_s0500_0800_depth0.8 | +552 / +0 | -12,613 | +29 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 20 / 0 | 3.09 / 2.56 | n/a |
| kz_s0500_0800_bank6 | -1,490 / -836 | -729 | -439 / -630 | +0.0 / +0.0 | +0.8 / +0.0 | -26 / -22 | 3.12 / 2.56 | n/a |
| kz_s0500_0800_bank12 | +2,872 / -3,163 | -4,253 | +437 / +1,166 | +0.0 / +0.0 | +1.7 / +0.0 | 26 / -104 | 3.12 / 2.56 | n/a |
| kz_s0800_0930_disp0.6 | -312 / -383 | -2,427 | -204 / -3,554 | +0.0 / -1.5 | +1.7 / +0.0 | -17 / -48 | 3.16 / 2.56 | n/a |
| kz_s0800_0930_disp1.0 | -1 / +0 | +3,491 | -1 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / 0 | 3.09 / 2.56 | n/a |
| kz_s0800_0930_disp1.3 | -2,093 / +292 | +3,469 | -47 / +3,690 | -2.5 / +0.0 | -1.7 / -5.8 | -109 / 52 | 2.93 / 2.44 | n/a |
| kz_s0800_0930_depth0.3 | +0 / +0 | -1,076 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| kz_s0800_0930_depth0.8 | +0 / +0 | -1,900 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| kz_s0800_0930_bank6 | -510 / +0 | +2,840 | +161 / -74 | +6.8 / +0.0 | +0.0 / +0.0 | 12 / -39 | 3.12 / 2.56 | n/a |
| kz_s0800_0930_bank12 | -2,114 / +0 | +2,329 | -2,952 / +0 | -0.8 / +0.0 | +0.0 / +0.0 | -90 / 12 | 3.12 / 2.56 | n/a |
| kz_s0930_1530_disp0.6 | -825 / -264 | -7,042 | -672 / -501 | +0.0 / +0.0 | +0.0 / +0.0 | -17 / -32 | 3.28 / 2.82 | n/a |
| kz_s0930_1530_disp1.0 | -2 / +0 | -74 | -1 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / 0 | 3.09 / 2.56 | n/a |
| kz_s0930_1530_disp1.3 | -921 / -845 | +1,857 | -2,195 / -4,287 | -1.6 / -1.5 | +0.0 / +0.0 | -50 / -96 | 3.01 / 2.37 | n/a |
| kz_s0930_1530_depth0.3 | +0 / +0 | -284 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| kz_s0930_1530_depth0.8 | +133 / +0 | +185 | +800 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 20 / 0 | 3.09 / 2.56 | n/a |
| kz_s0930_1530_bank6 | +364 / +0 | +0 | +4,706 / -355 | +0.9 / +0.0 | +0.0 / +0.0 | 41 / 11 | 3.12 / 2.56 | n/a |
| kz_s0930_1530_bank12 | +0 / +0 | +0 | -928 / -682 | -0.8 / +0.0 | +0.0 / +0.0 | -15 / -24 | 3.12 / 2.56 | n/a |
| depth_max2.0 | -9,819 / -1,207 | +8,219 | -7,880 / -8,333 | -1.6 / +20.3 | -1.7 / -5.8 | -218 / -96 | 1.88 / 1.47 | n/a |
| depth_max3.0 | -7,609 / +1,203 | +7,054 | -8,669 / -5,200 | -3.3 / +17.4 | +0.0 / -5.8 | -148 / 56 | 2.58 / 2.12 | n/a |
| depth_max4.0 | +1,633 / +1,741 | -3,337 | -5,773 / -1,735 | -0.8 / +14.5 | +0.0 / -5.8 | -55 / 118 | 2.77 / 2.31 | n/a |
| max_stop50 | +0 / -879 | -2,848 | -6,222 / -170 | -8.4 / +5.8 | +0.8 / -5.8 | -157 / -24 | 2.3 / 1.92 | n/a |
| max_stop60 | -1,212 / -783 | -1,276 | -4,204 / +219 | -8.4 / +4.3 | +0.0 / -5.8 | -115 / -4 | 2.62 / 2.18 | n/a |
| max_stop70 | -903 / -28 | -580 | -2,774 / +3,547 | -3.3 / +0.0 | +0.0 / +0.0 | -75 / 1 | 2.93 / 2.37 | n/a |
| min_stop10 | +0 / +0 | +491 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| min_stop12 | +0 / +0 | -11,011 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3.12 / 2.56 | n/a |
| min_stop15 | -5,321 / +0 | -2,311 | -5,533 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -57 / 0 | 3.05 / 2.56 | n/a |
| monday_half | -1,848 / -305 | +2,700 | -3,685 / -76 | -2.5 / +0.0 | +0.8 / -5.8 | -168 / -37 | 3.32 / 2.69 | n/a |
| monday_quarter | -1,849 / -305 | +2,750 | -3,631 / -313 | +0.0 / +0.0 | +0.0 / -5.8 | -162 / -37 | 3.32 / 2.69 | n/a |
| wk_stop_3 | +1,620 / -234 | -1,111 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -5 / -35 | 3.12 / 2.56 | n/a |
| wk_stop_off | +1,453 / -233 | -621 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -8 / -35 | 3.12 / 2.56 | n/a |
| wk_stop_2_0.75 | +622 / +0 | -373 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -2 / -15 | 3.12 / 2.56 | n/a |

