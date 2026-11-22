## Tested and rejected (don't redo without a new idea)
- **2026-11-22 Regime guard round 3** (research/regime/guard3.py, regime-guard3-2026-11-22.md): shadow-setup hit rate R1, intraday variance ratio R2, trend-day share R3, thin volume R4, NQ-VIX co-movement R5, 2-of-5 vote R6; half / out; LIT and ATLAS. **0 of 22 pass, all fail the stage-0 kill-gate.** R1 sweeps pay worse in 2026 than in 2021-25 (flags 2026 87.5/80.8% vs OLD 70.4%). R5 flags LIT's best days. Best placebo 47.5% / 68.5% (95 needed). Closes the regime lever for market-weather and market-wide sweep signals, not every possible signal. ATLAS funded baseline moved 8.5/9.2/94.5 -> 8.2/8.3/94.2 because of a code change after 153552591; verdict unaffected.
- **Zlarior edge, 5 pre-registered ideas (2026-11-20, `lit-edge-2026-11-20.md`, `tools/research/litedge.py`,
  `research/lit/litedge.json`, design `research/lit/litedge_design_2026-11-20.md`):** LIT $/month H1 / H2 / 2021-25 vs
  today $5,562 / $2,670 / $25: limit 2 ticks better than the model fill for 1 min, else market $5,184 / $2,585 / $26;
  skip a setup when the 1m entry is > 60 min after the sweep bar $849 / $824 / $119 (1.2 / 0.8 trades a week); Tier-1
  day target capped at 4R $4,997 / $2,616 / $89; MES instead of MNQ when ES's planned target R >= 1.25 x NQ's $5,069 /
  $9,656 / $198 (fails Jan-Jun, eval -$10.6k / +$7.0k; paper lead, forward only); no +1R breakeven in the first 10 min
  $5,068 / $2,670 / $25. 0 pass. Fill map: limits 10-50% of the risk better fill 0-60% and miss $17-34k of Jan-Jun
  winners. +10 ticks a trade: $5,176 / $2,447 / -$353. Cold run (7 twin trades -4.2R) = 8.8% of 2026 7-trade windows.
- **ATLAS edge at real fills (2026-11-20, `atlas-edge-2026-11-20.md`, `tools/atlas_edge.py`, `research/second/atlas_edge.json`,
  design `research/second/atlas_edge_design.md`)**: 14 of 15 fail at 6 and 10 ticks on 60% and 40% sizing. Limit at the 5m open /
  1-2 ticks better with a 1-2 min timeout (only ~52% fill, the runners are missed: funded $151-285 a month Jan-Jun-like vs $503),
  limit 2 min then market, the next 5m open, per leg +0 / +5 min (picked +0), drop EMA (-$301 a month Jul-Oct-like), EMA half
  size, the day stop after a loss (re-check at real fills), 3 losses -> 3 sessions off, a weekly cap at 35% of the room. Info
  only (1m bars, 2021-25 untestable): EMA +60 s, per-leg minute (MACD +1: Jul-Oct $436 vs $402). ES versions of the 3 legs
  (`tools/atlas_es.py`): PF 0.60-0.84 in 2026 at 3 ES ticks, all lose at 10. Passed: 2 losses in a row -> 1 micro (Decide card).
- **ATLAS real-fill fixes (2026-11-20, `atlas-fills-2026-11-20.md`, `tools/atlas_fills.py`, `research/second/atlas_fills.json`,
  design `research/second/atlas_fills_design.md`):** ATLAS's 3 real entries filled 10 / 12 / 16 ticks past the 5m open (market
  order 3-5 s after a 5m close, price still running our way). Judged at 6 AND 10 ticks a side vs today at the same cost (funded
  25K, fixed view, 2026 halves + 2021-25): 0 of 6 pass. Limit at the open 5 min (misses 17-18% of 2026's trades = the runners,
  funded $550 -> $314 a month Jan-Jun at 6 ticks), limit 4 ticks worse (-$272), enter on the 1m close +60 s (Jul-Oct +$57,
  Jan-Jun -$75, 2021-25 untestable: no 1m bars), skip a signal bar > 2x its 20-bar median (skips 30%, good trades), member
  hours picked on Jan-Jun (Jul-Oct -$164: overfit), London pause before 08:00 ET (Jul-Oct $438 -> $74). Post-hoc, never
  eligible: limit 60 s then market (-$105 Jan-Jun); "F3 if a 1-minute-later entry slips only 3 ticks" = a question for real
  fills. Costs (no fix): at 10 ticks a side ATLAS still makes $512 / $404 a month funded (vs $588 / $494) but lost in 6 months
  from today's room 7.7 -> 17.7% / 9.5 -> 23.0%, 2021-24 PF 1.06 -> 0.80. Re-test only with 10+ real fills (and poll-on-tick
  engine/fast_entry priced on tick-time fills).
- **Payday levers + cross-bot loss cuts (2026-11-20, `payday-plan-2026-11-20.md`, `tools/money/payday_plan.py`,
  `tools/payday_losses.py`, `research/lab/payday_plan.json` / `payday_losses.json`, Lab rows `research/lab/payday_levers.json`,
  design `research/lab/payday_design_2026-11-20.md`):** judged on the FIRST PAYOUT date AND the chance of losing the account
  (today's balances, 1,000 same paths a market; Jul-Oct / Jan-Jun). 8 levers, 0 pass: ATLAS funded 40% of the room (first
  payout +5 / +5 days, paid by Jan 15 66 -> 58 / 84 -> 81%, lost 10.2 -> 5.8%: safer, later), ask at $1,000 (+2 / +4 days),
  ATLAS "need" funded size (-$91 / -$70 a month), 25K #2 40% + $300 cap (+5 / +2 days), Rapid ATLAS $150 (+6 / +3 days,
  -$198 / -$522) or $350 (lost in 6 m 28.9 -> 36.8%), Rapid LIT bank lane (eval lost first 8.4 -> 11.6% Jan-Jun), ATLAS on
  Zlarior's 50K NOW vs after the pass (nearest miss: sooner, eval deaths 26 -> 8% Jan-Jun, but 6-month lost 8.3 -> 9.7% and
  2021-25-like 48 -> 63%). Loss cuts: ATLAS stands down after a closed Zlarior loss that day (cut trades +0.82 / +1.07R,
  -$580 / -$226 a month, funded 25K first payout Jan 4 -> Jan 13) and Zlarior stands down after a closed ATLAS loss
  (-$1,733 / -$297 / -$212 a month): both rejected. Anatomy: no bucket loses in both 2026 halves except ATLAS VIX < 15
  (already rejected 2026-11-18).
- **Zlarior more money, 2 pre-registered batches (2026-11-19, `lit-more-money-2026-11-19.md`, `tools/lit_more_money.py`,
  `research/lit/more_money.json`, designs `research/lit/more_money_design_batch1/2.md`, Lab rows `research/lab/lit_more_money.json`):**
  9 single versions, LIT $/month H1 / H2 / 2021-25 vs today $5,562 / $2,670 / $25: ES (MES) LIT filler on days NQ has not
  traded yet, NQ preempts (4.5 trades/wk) $4,478 / $3,026 / -$66, eval 2-week pass 44.5 -> 43.7, funded $929 -> $642 a month;
  breakeven at clip(0.25 x target R, 0.5-2R) $5,194 / $2,429 / $209; LIMIT entry at the 1m CISD close (1 tick through, else
  market) $5,554 / $2,583 / $26 (fills 112/119 at the same price on average; the 7 misses are runners, chase ~5 pts); NY setups only on London's
  discount side $5,482 / $2,770 / $51; Tier-1 news day: only setups after the release $4,277 / $2,736 / $54; out on a 5m close
  back through the CISD level before +0.5R $4,738 / $532 / -$75; ES closes beyond its own sweep-window extreme before +0.5R ->
  out $5,562 / $2,771 / $30 (0 cuts in Jan-Jun, 4 in Jul-Oct: nearest miss, paper only); keep only SMT setups (ES held) 0.8 /
  1.0 trades a week $150 / $937 / $61; trade MES instead of MNQ when ES held (SMT pick) $4,945 / $5,383 / $76 (30 ES trades in
  2026, loses Jan-Jun). 0 pass. Target touch-fills checked: requiring 1 tick through changes 0 trades. Live gap Oct 26 - Nov 16:
  see the write-up (one real miss, one refused order already fixed, one traded trade the audit could not see; fix proposal
  `tools/live_gap_proposal.py`).
- **ATLAS more money (2026-11-19, `atlas-more-money-2026-11-19.md`, `tools/atlas_more.py`, `research/second/atlas_more.json`, Lab
  kind `atlas_more`, design `research/second/atlas_more_design.md`):** 10 pre-registered ideas (14 variants) on the FUNDED 25K
  from today's $887 room (600 week-block paths, live stuck stop, costs in). Rejected: thin-room sit-outs (only MACD / EMA
  out while the room is under $300 / $500 / $700: Jul-Oct -$6 to -$63 a month, more lost or no-payout), no stuck stop + 40%
  of the room (first payout +3 / +7 sessions), ATLAS v2 hunts x0.5 on the funded account (+$51 / +$93 / +$18 a month but
  4.5-4.7 trades a week, Jul-Oct lost 10.5 -> 12.2%, real-order Jan-Jun lost 0 -> 3.8%, Jan-Jun fixed $ down; fresh Oct
  19 - Nov 19 hunts -1.1R / 0R), v2 as built (+ min_room $200: Jul-Oct lost 16.8%), Asia hunt only (Jul-Oct lost 18%),
  flat 3 min before CPI / jobs / FOMC (-$82 a month Jul-Oct, 25 trades cut) and the same unless +1R (-$47). Passed: no
  funded stuck stop (A1, +$10 / +$3 / +$4, lost 9.8 -> 7.7%, never worse on a path) -> Decide card atlas-funded-keep-trading.
  The armed-setup block costs nothing (without it funded $ is lower). Members: none to drop (fresh 5 weeks ATLAS PF 1.99).
- **BLITZ review (2026-11-18, `blitz-review-2026-11-18.md`, `tools/blitz_review.py`, `research/scalp/blitz_review.json`, Lab kind
  `blitz_idea`):** 8 pre-declared EXIT ideas on today's BLITZ (account C, $150, costs in): out at minute 10 / 15 if in a loss and
  never +0.5R, out at minute 10 if never +0.25R (H1 pick: +$22 Jan-Jun, -$292/mo Jul-Oct, 2-week fails 21.7 -> 40.6%), out on a
  1m close back inside the noise band (from entry / from minute 10), breakeven at +0.5R, the minute-15 cut / band exit with a
  45-minute hold (+$144-162 Jul-Oct, -$240 Jan-Jun). 0 pass; every one LOWERS the win rate (35-53% vs 57%): non-starters (not
  +0.5R by minute 10) still end near 0R in 2026. Today's BLITZ: +$963 / +$667 / +$73 a month, own 25K slot +$286 / +$52 / -$39.
- **Third strategy hunt (2026-11-19, `third-strategy-2026-11-18.md`, `tools/third_strategy.py`, `research/second/third_strategy.json`,
  Lab kind `new_strategy`):** 172 pre-declared cells, NQ 5m whole CME day, $500 a trade, structure stops, costs in, flat 15:55:
  post-close move (16:00-17:00) traded at the 18:00 reopen, follow / fade (80), Camarilla H3/L3 fade + H4/L4 break + floor
  R1/S1 fade (44), TD Sequential 9-count fade on 15m / 1h, any hour (48). 0 hold H1/H2/2025/2021-24 vs 0.4 with coin-flip sides.
  H1 picks lose Jul-Oct: H4 break +$1,683 -> -$881/mo, 1h 9-count +$3,265 -> -$381/mo (both lose 2025). Fades of pivots and
  of the post-close move lose. Paper lead: FOLLOW a big post-close move at the reopen (14/32 cells positive H1/H2/2021-24,
  p 0.005 over 2021-25) but no cell reaches PF 1.1 in 2025, 0.2-1.4 trades a week, and it adds LIT-eval fails. Nothing adopted.
- **Setup grade, "trade like a calm person" (2026-11-18, `setup-grade-2026-11-18.md`, `tools/setup_grade.py`, Lab kind
  `setup_grade`):** 7 human warnings at the signal (daily trend vs SMA20 against, prior-day / overnight high-low / 18:00 VWAP /
  100-pt number within 0.5R toward the target, range so far >= ADR14, inside day so far, high-impact news in 30 min, ES 30-min
  move against, VIX >= 25 or +20%), A / B / C = fewer / typical (Jan-Jun median) / more warnings; all 7 or the Jan-Jun-kept
  checks; skip C (day / slot left free) or A x1 / B x0.5 / C skip. Zlarior: grades do not rank (Jul-Oct A -$1,615, B +$12,333);
  size use -$188 / -$1,518 a month; H1-kept trend+level+chop -$592 / -$1,711 (1.54 trades/wk); all-7 skip C +$712 / +$303 /
  +$11 a month, eval 2-week 39.1 -> 47.8% Jul-Oct, but random skips p 0.16 / 0.37 and it loses with level at 1R or C = 4+.
  ATLAS: all 4 lose on the funded 25K (skip C $353 -> $211 a month Jul-Oct). Each check alone: none helps in Jul-Oct; the key
  level in the way is the only one pointing right in every period. VIX-not-normal and against-trend trades were among the best.
- **Win / loss anatomy rules (2026-11-18, `win-loss-anatomy-2026-11-18.md`):** `tools/win_loss_anatomy.py`, ZEUS Lab kind
  `anatomy` + one atlas_tilt. 4 pre-declared single versions from the strongest findings of the per-trade anatomy, on the real
  backtests (costs in): Zlarior x1.25 on a pullback in the daily trend (prior close vs its 20-day SMA with the trade, 1h EMA 20/50 against;
  15 + 6 trades) Jan-Jun +$349 / Jul-Oct -$6 a month at the LIT size (the Jul-Oct winners were 2-3 micro trades x1.25 cannot
  change), eval +$163 / +$130, flip p 0.08 / 1.0; Zlarior skip the careful-human checklist (against the daily AND 1h trend / the
  day already moved 1 daily ATR / big US release within 30 min / prior-day high-low under 1R ahead) -$412 / -$1,514 a month,
  1.8 / 1.5 trades a week, 2-week pass 44.5 -> 37.0 / 39.1 -> 24.6 (2021-25 +$90); ATLAS x1.25 in the 03:00 ET hour (25K path)
  +$125 / +$34 a month but 2025 money after fees -$494, Jul-Oct p 0.075 (nearest miss, re-tested nightly); ATLAS checklist skip
  -$1,811 / -$484 a month, 2-week pass 61.3 -> 39.5 / 43.5 -> 30.4 (2021-24 PF 0.96 -> 1.22: care pays only in bad years). 0 pass.
  Diagnosis: losers mostly never worked (Zlarior 62%, ATLAS 58%, BLITZ 72% of 2026's lost $), a 50% wider stop wins 0-9% of
  Zlarior / ATLAS stop-outs, entry-fact buckets consistent in all 3 periods = chance (18 of 86 vs 15.4 shuffled; ATLAS 12 / 90 vs
  15.7; BLITZ 7 / 66 vs 14.2).
- **Zlarior's two live evals together (2026-11-18b, `lit-ideas-2026-11-18b.md`, `tools/money/lit_two_evals.py`, Lab
  `lit_eval_zombie` / `lit_two_eval_stagger`):** the 50K hole + the 25K #2 on ONE Monte Carlo (same paths, live sizing).
  ATLAS's zombie-eval rule on Zlarior (1-micro last bullet at 80% of the room + give up under $200): pair +$57 / +$51 a
  month only by killing evals (2-week fails 50K 4.9 -> 10.4 / 3.1 -> 6.9%, 25K 0 -> 8.1 / 0 -> 8.3%, both dead in 20
  sessions 0.4 -> 16.3%); stagger (alternate full / half size per signal): -$80 / -$49 a month, 25K 2-week pass 48 -> 31%.
  Today both evals die together 0.3-0.4% within 20 sessions: the joint risk is waiting, not failing. Rejected.
- **ATLAS funded 25K protective rules (2026-11-18, `atlas-health-2026-11-18.md`, `tools/atlas_health.py`,
  `research/second/atlas_health.json`, Lab kind `atlas_funded`):** 17 pre-declared + 5 post-hoc on the funded 25K Monte
  Carlo WITH the live $100 stuck stop (600 paths, fresh start + today's -$113, real day order, fixed $250, random-timing
  controls): member pause on its own last 10 / 20 trades (PF < 1 -> paper / x0.5), size by the edge light (AMBER / RED x0.75
  / x0.5 / paper, last-40 R-PF < 1.5 x0.5), day caps (stop after a loss, $275, $367, a third of the room), 30-40% of the room
  in a hole or always, skip the day after a losing day. 0 pass: caps / skips / light sizes cost $18-191 a month in Jul-Oct
  or slow the first payout; the member pause never acts in Jul-Oct (Jan-Jun +$9, 2021-25 stranded 94.5 -> 90.5%, random
  halving 93%); 40% of the room halves 2026 stranding (8.5 / 9.2 -> 5.8 / 4.5%) at the same $ but first payout 18 / 25 -> 20
  / 31 sessions. VIX < 15 skip re-measured: still post-hoc + a $ knife edge (Jul-Oct $543 / $581 / $490 / $330 at 14.5 / 15
  / 15.5 / 16). Found: at 60% of the room the stuck stop strands ~9% (2026-like) / ~95% (2021-25-like) funded 25Ks in 6
  months; older funded tools showed 0% lost. The AMBER light = a calm-market dip (VIX < 18 every session Aug 24 - Oct 16,
  still +8.0R at a fixed size). Nothing changed.
- **ZEUS Lab LIT ideas (2026-11-18, `zeus-lab-lit-ideas-2026-11-18.md`, `tools/lit_lab_ideas.py`, Lab kind `lit_idea`):** 10
  pre-declared single versions on the live LIT trades (LIT size + two_week eval path room 0.4, costs in), $/month vs today H1 /
  H2: time stop 60 min without +1R -$695 / -$945; out at 09:29 if not at BE -$317 / +$33 (5 + 2 trades); BE at 09:29 if +0.5R
  $0 / $0; out 2 min before CPI / jobs / PPI / FOMC if not at BE +$64 / $0 (1 trade); BE before news if +0.5R $0; after BE out
  when 60 min without a new best -$1,516 / -$457; BE only on a 1m close at +1R -$326 / $0; NR7 day after x1.25 -$24 / -$11
  (eval +$66 / +$149); London build-up sweeps x1.25 +$295 / +$14 but eval H1 -$4, 2-week pass 44.5 -> 41.2, flip p 0.15 /
  0.51 (nearest miss, re-tested nightly); 18:00 gap against x0.75 -$408 / -$188. 0 pass. Clock exits all lose (targets need
  hours); NY-open / news rules touch 0-7 trades in 2026.
- **ATLAS new members (2026-11-18, `atlas-members-2026-11-18.md`, `tools/atlas_plus.py`, `research/second/atlas_plus.json`):** 29
  pre-declared versions, 5m NQ RTH, stop 1 tick beyond structure, 2R or VIX-band target, $250 a trade, costs in: VWAP pullback
  with trend (8; all lose Jul-Oct), opening-drive continuation on a 1m trigger (8; 2021-25 = 5m proxy), prior-day value-area
  re-entry = 80% rule re-measure (1; stops too wide for $250), 15m Keltner squeeze (8; 0.1-0.4 a week), prior-day POC first
  touch (4). 0 hold H1/H2/2025/2021-24 (coin-flip 0). Picks as a 4th member on the funded 25K ($250 / 30% room): opening
  drive $541/$353 -> $578/$253 a month, no-pay 15 -> 34% Jul-Oct, 4.49/wk; POC $521/$279; with S/R out both ~-$90/mo.
  ZEUS Lab: atlas_member_* Rejected. Nothing changed.
- **New-strategy hunt (2026-11-17, `new-strategy-hunt-2026-11-17.md`, `tools/new_hunt.py`, `research/second/new_hunt.json`):** 354 cells,
  5m RTH, $500 a trade, structure stops: lunch-box squeeze -> PM break (any / WITH / AGAINST the AM trend = the 14:00-15:30
  continuation), failed auction at the prior value-area edge (5m-built profile), Dalton 80% rule, London 02:00->09:30 extension
  fade at the NY open. 0 hold H1/H2/2025/2021-24 vs 3.7 with coin-flip sides; no 2-4/wk cell with H1 PF >= 1.2. WITH-trend PM
  break: 71/72 cells positive 2021-24, 0/72 in 2026 H1. D80 / London fade PF 1.3-1.5 in 2021-25 but lose Jul-Oct, ~1/wk. Corr LIT ~0.
- **Market-regime warning features (2026-11-17, `edge-health-2026-11-17.md`, `tools/edge_health.py`):** VIX, RTH range %, overnight share, trend efficiency, sweep reclaim (40-session means) as a 2026-vs-2021-25 light: only overnight share separates (BA 0.94) and it is a yearly drift that calls 2022 (LIT's good year) bad and precedes a worse LIT in 2021-25. Kept: the light from LIT's own last 40 sessions (warning only).
- **Regime guard (2026-11-20, `regime-guard-2026-11-20.md`, `research/regime_guard/`):** VRP (RV20 > VIX), 1-year ATR20 / ER20
  bottom-third, 2-of-3 vote, half / out for LIT + ATLAS: 0 of 8. None is more common in 2021-25 than 2026 (G1/G4 fire most in Jul-Oct);
  LIT's 2021-25 $ is made on the flagged days (+$2,065 -> -$1.8k..-$5.9k). Post-hoc lead: ATLAS worse on chop days in all 3 periods; out
  = ATLAS Jan-Jun -$4,746, funded 2021-25 lost 94.5 -> 85.7%. NQ/ES correlation not testable (ES daily from 2025-04).
- **Famous published strategies (2026-11-17, `public-strategies-2026-11-17.md`, `tools/pub_strats.py`):** 22 cells as
  published + MFFU-legal day versions: Gao intraday momentum (wrong sign 2021-25, t -2.2), pre-FOMC drift (2021-25 only),
  turn of the month (2026 only; day-trade version = random days, placebo p 0.12-0.24), overnight drift, Connors RSI(2),
  12-month and 20/60-day time-series momentum, Crabel NR7 / NR4 / NR7-ID. None holds in 2021-25 + both 2026 halves; the
  ones that look best hold overnight (MFFU: flat by 16:10) and lost in H2. LIT corr ~0 but no money. Nothing adopted.
- **Drift switch (2026-11-17, `drift-switch-2026-11-17.md`, `tools/money/drift_switch.py`):** cut LIT to paper/half after a rolling
  loss (51 versions): 0 pass; never fires in 2026; 2021-25 fewer failed evals but same less payout; no better than random cuts.
- **Walk-forward re-tuning (2026-11-17, `lit-walkforward-2026-11-17.md`, `tools/lit_wf_retune.py`, `research/lit/wf_retune.json`):**
  re-fit disp 0.7/0.8/0.9 x BE 1R/1.5R/off x bank 5/8/12R (27) every month / quarter on the trailing 6 / 12 months (8 versions),
  OOS 2022-05..2026-10. Main (monthly, 12 mo, net-DD): 2022-25 +$23.1k vs static +$0.7k (1.3 s.e., +$26k is 2025 alone, 2023/24
  worse; beats random re-picks 93.5%, others 44-83%); 2026 H1 -$11.0k, H2 -$3.0k; all 8 lose both 2026 halves. 2023 loses at all
  27 settings: the bad years are regime, not knobs. (2026-only anchored version: `tools/lit_walkforward.py`, also lost.)
- **Rule-native layer (2026-11-17, `rule-native-2026-11-17.md`):** 2nd target / 1R / scalp / profit lock: no sooner payout.
  Lead only: BLITZ max 3/day on the Rapid (chance-level by count; 2021-25 2-week eval fails 2.9% -> 6.0%). Watch on paper.
- Published models as taught: ICT 2022, Silver Bullet, Mech/IFVG, continuation, ATM 5m/1m with a sharp V (0.2–1.5 trades/wk,
  PF ~1).
- **ICT ATM range + ES/NQ SMT as the trigger, MES, Judas swing (2026-11-20, `newstrat-ict-smt-2026-11-20.md`):** 5 pre-registered
  sets, $250, costs in: every SMT set loses all 3 periods (PF 0.57-0.99, gross 0.59-1.05), MES not cleaner (10-tick stress
  -$3.7k..-$10.1k), Judas control +$1,672 Jan-Jun then -$2,244 Jul-Oct / -$11,472 2021-25. Rapid 25K eval pass 0-5%. 0 pass.
- 92 confluences; 6 daily-bias methods; grade/confidence sizing; partials and trails.
- Fixed 10–15 pt stops: wicked out, lose money. Structural stops are rarely ≤15 pts.
- Target variants: no cap / draw mode / "last real pool" all worse (2026 PF 1.6–2.2 vs 3.48).
- Re-sweep, inducement, FBOS, RBOS: recorded as engine features `x_resweep`, `x_inducement`, `x_fbos`, `x_rbos`; no edge that
  held in both periods. "No inducement" looked better, but the sample is thin.
- The skip-mode cold-streak filter: best PF, but it paused for 14 weeks, which the owner rejected.
- All variants with numbers: `research/lab/variant_results.json`.
- **B-holds (2026-10-27, `b-holds-vs-lit-priority.md`, `tools/bholds.py`, runs `bholds_*`):** while ATLAS (account B) holds a trade, skip
  LIT's opposite entry instead of closing B (HEDGE). Both accounts 2026 +$52.3k -> +$53.6k, 2021-25 -$3.2k -> -$5.0k; ATLAS 25K
  2-week pass H1 65.5 -> 60.5 (stuck 0.8 -> 3.4); 9 clashes in 2026, 35 in 2021-25. Rejected: LIT priority stays.
- The owner's LIT Complete Report (2026-10-18, `research/writeups/lit-report-tests.md`, `tools/lit_report.py`, runs `lit_rep_*`):
  reclaim, confirmation deadline, acceptance, displacement quality (top-quarter close, 1.5-3x median body, FVG), 2+
  inducements, inducement room, 2+ levels swept, leg premium/discount, double-sided sweep, first obstacle (0.5R = lone spike),
  continuation / flip 2nd trade, costs inside the $800, Berlin-time London boxes (no 2026 change, 2021-25 +$5.8k): none adopted.
  The report's ch.21 model makes 0 trades in 2026. Beginner guide: `research/writeups/lit-playbook.md`.

- **LIT studies of 2026-10-18/19 (none adopted unless noted; write-ups in research/writeups/):** HTF confluences (75,
  chance level, `lit-htf-confluences.md`); order blocks incl. HTF OB entries and the owner's mitigation notes (84,
  `lit-order-blocks.md`); entry precision (43, today's entry is best, `lit-entry-precision.md`); all-hours / Asia /
  per-session / re-arm / F-BoS build-up (30, `lit-all-hours.md`); report-2 continuation, sessions, Smart Money Trap,
  inducement speed/hierarchy (176, `lit-adv-continuation.md`); BE/partials/targets (`lit-adv-management.md`: BE at
  entry + 1.25 pts is a small candidate); backtest honesty audit (-$500 of $41.7k, `lit-adv-audit-smt.md`); NQ/ES
  divergence; more setups: ES/MES, 15m/30m/1h, missed fills, looser filters (95, `lit-more-setups.md`); trend-day mode,
  volatility sizing, news setups (`lit-big-ideas.md`). **Of the three adopt-candidates, two are ON since 2026-10-20**
  (owner approved; numbers in "Results" above): the 15-minute check (`t_check {"at":15,"x":0.3,"mfe":0.5}`,
  `lit-loss-learning.md`; route fixed: all 13 2026 cuts routed 2 s after the check-bar close, priced from the forming bar's
  open, `tests/test_lit_exit_route.py`) and BE + costs (`be_off 1.25`). **Scale-in after BE is OFF** (`"scale_in": null`,
  `lit-big-ideas.md`; NinjaTrader MARKET add + resize of the one OCO bracket, `add_to_position`, 52/52 2026 adds match the
  backtest; two safety reviews: safe only after the owner's `--sim-roundtrip-add` on Sim101 (since 2026-10-26 it proves the size itself: step 5 moves the target under the market, it must fill 2 micros and end flat, then prints SCALE-IN READY; `tests/test_sim_add_proof.py`) shows stop + target qty 2 at the
  right prices). All three on the eval path (run `lit_adopt_all3_eval`): H1 +$53.1k / H2 +$17.3k vs live now +$34.2k /
  +$9.1k, 2-week pass/fail 58.0/2.5 and 52.2/0.0 (live now 57.1/5.9, 52.2/0.0); scale-in alone makes more in H2 (+$26.0k)
  but fails more. Thin samples (13 cuts, 52 adds); the cut route is still untested on a real NinjaTrader install (watch the
  first week on Sim). `idm_size` (inducement-count size) helps the LIT size rule but not the
  eval path: keep it off for evals (`lit-new-entries.md`). Funded plan: MFFU Builder + LucidPro 50K + FundedNext
  Rapid Daily 50K (`lit-funded-firms.md`, ~$1,750-2,300/mo for three); one bot can now route to several accounts
  (`engine/multi_account.py`, off by default, `data/accounts.json`).
- **Reversal exits after the first live trade (2026-10-28, `lit-reversal-exit.md`, `tools/lit_rev_exit.py`, runs `lit_rev_*`):**
  exit / BE on a violent reversal once +0.5-0.9R (ATR candles, 2-3 candles, profit giveback), 1m/5m swing trails after
  +0.5-1R, BE at 0.75/0.9R, stop at the first 1m/5m highs: 103 variants, none better in both 2026 halves (the 2-ATR candle exit
  after 0.9R: today +$168 vs -$437 but H1 -$9.1k / H2 -$2.3k; first 1m highs H1 +$29k / H2 -$13k PF 0.75). 2026 had 0
  trades that went 0.9-1R then stopped before 2026-10-28. Nothing changes.
- **Diversifier search (2026-10-26, `diversifier-search.md`, `tools/div_search.py` / `div_stack.py`, runs `div_*`):** the
  VXN-normalised initial-balance breakout is dead (0/24 settings positive in all four spans). The noise-area intraday momentum
  (Zarattini 2024) is REAL as futures trading (paper rule and joint pick `na_vm125_1000_n99_fixed` positive in H1 / H2 / 2025 /
  2021-24, placebo p 0.007 in 2026, daily corr with LIT ~0) but NOT a prop strategy alone (MFFU eval p10 <= 22%, funded
  $13-117/mo: 27% winners, 18-23R drawdowns vs the 50% best-day rule and the $2,000 floor). Only as a small add-on on LIT's
  funded accounts (3-4% of the room, <= $150, never while LIT holds): +$54-83/mo per 50K in 2026, +$7-12 in 2021-25; paper only.
- **Payout / eval mechanics (2026-10-26, `payout-policy.md`, `eval-cost.md`):** ask line $1,000 / $2,000 vs $1,500,
  cons_aware, stack payout reserves (cap a month) and pre-buying the next eval at the 4th payout: see the write-ups before
  redoing. Eval: keeping two_week after session 10 (`two_week_until` 999) is the one change that held in H1, H2 and 2021-25
  (+$14-21/mo per slot; owner decides, not switched).
- **BLITZ on its own 25K, "like a person" (2026-10-29, `blitz-25k.md`, `tools/blitz25k_*.py`, runs `blitz25k_*`, pick
  `research/scalp/blitz_25k_pick.json` = no-change):** as account C (never opposite LIT / ATLAS, closed first; costs $0 in
  2026, $16/mo at $150 in 2021-25): structure stops (last 1m / 5m swing, the move's low, caps; 45), liquidity targets /
  partials / swing trails / change-of-character exits / no clock (1,920), opening drive, London band, retest limits, 15m / 1h
  BOS filters (32), funded-only structure rule: none beats today's rule in H1, H2 and 2021-25. 25K size: 40% of the room,
  100% from eval session 5 (decided in 2 weeks 71-74% vs 29-41%, same money: slot $270 / $37 / -$40 a month; random
  directions make the same H2 slot $). The post-hoc 1.0 x ATR / 45 min / no trail variant is worse on LIT's 50K too (H2).
- **Structure management (2026-10-29, `structure-management.md`, `tools/structure_manage.py` LIT 101 variants, runs
  `lit_struct_*`; `tools/structure_atlas.py` ATLAS 24, runs `atlas_struct_*`):** with `engine/structure.py` (closed-bar BOS /
  CHoCH / protected swing / pools): target at the next opposing pool (cap / instead of the band), half off at the first pool,
  stop to the protected swing after a BOS (1m / 5m / 15m), exit / BE on a CHoCH against after +0.5-2R, 1h / 15m trend skip /
  size. None beats live LIT in both halves on both sizings (the owner's BE on a 5m CHoCH after +0.75R: H1 -$1,442 / H2 -$775;
  1h skip: H1 -$15.0k / H2 -$7.5k, ~1 trade a week; runner past the target, lock 75% + 15m trail: H1 +$13.6k / H2 +$956 at
  the LIT size but two trend days are the gain and the eval path loses, 2-week pass 57 -> 36% H1, rejected). Lead, not
  switched: 15m structure trail after +1R (H1 +$467 / H2 +$13,
  eval +$1,019 / +$3,762, one more 2-week fail in H1, 7 trades changed): the advisor's `trail_15m` tally watches it. ATLAS:
  the 15m protected-swing stop passes the 25K account gates but its trades lose R in every span at a fixed risk (sizing
  path): rejected; every ATLAS exit / trail loses in 2026. The executors' base = live exactly (LIT 0 mismatches; ATLAS 96%
  within 0.5 pt, difference method).
- **ATLAS funded 25K day limit (2026-10-31, `atlas-funded-one-a-day-2026-10-31.md`, `tools/atx_funded_day.py`, runs `atxd_*`):**
  eval unchanged, funded max 1 a day: slot $ H1 / H2 / 2021-25 $454 / $275 / -$3 a month vs today's $568 / $382 / -$2,
  below a random-1-a-day control ($541 / $361); the H1 pick max 3 (= max 4) is +$44 H1, $0 H2 on 4 seeds. Keep 2 a day.
  Funded-only VIX band per member: no member loses in any H1 VIX tercile, so nothing to skip (`atx_funded_vix.json`).
  Funded half off at 0.75 / 1 / 1.5R + BE runner: H1 slot $336 / $366 / $414 vs $568 (runs `atxd_partial_*`): rejected.
  Funded re-entry after a stop-out (same setup once more, same direction): slot H1 $404 / H2 $257 / 2021-25 -$15 vs
  $568 / $382 / -$2, inside a coin-flip-direction control (run `atxd_reentry_1r`): rejected.
- **ATLAS + BLITZ edge night (2026-10-30, `atlas-blitz-edge-2026-10-30.md`, `tools/ab_edge.py`, runs `ab_*`):**
  - BLITZ trend-day SIZE (range so far, first-hour range / volume, overnight range / open's place in it, gap, VIX change,
    2-sigma excursion, VWAP side / distance, held at the previous check, time; 430 tilts): 39 survivors vs 36 on shuffled
    facts = chance.
  - BLITZ + a 10:30 check: H1 25K slot $270 -> $54.
  - BLITZ in-day streak size (2026-10-31, `blitz-streak-size-2026-10-31.md`, `tools/bzx_streak.py`, run `bzx_streak`): eval
    size x m after a same-day BLITZ loss / win (7 cells, 10 shuffled controls). H1 pick x0.5 after a loss: slot $286 / $53 /
    -$40 a month vs today $286 / $52 / -$39; 2021-25 no better than shuffled (after-loss trades are the BETTER ones there).
  - BLITZ cold-streak size on its own last K trades (2026-10-31, same write-up, `tools/bzx_cold.py`, run `bzx_cold`; K 5 / 10
    / 20, x0.5 / x1.5): H1 pick K 5 x0.5 when cold: slot $288 / $52 / -$40 vs $286 / $52 / -$39; shuffled -$37 in 2021-25.
  - The later-break size on LIT's funded 50K: neutral.
  - ATLAS (110, none passes the v2 test): member weights from the member's last 5-20 trades; member agreement; the 2nd
    trade sized by the 1st's result; LIT copied in as a member (x0.25: both 2026 halves better, 2021-24 -$3.0k vs -$1.4k,
    and the two accounts become one LIT bet); the NA day-hold as a 4th member (dead evals up); S/R level count / EMA sweep
    depth / EMA distance as size; London-clock windows in the DST gap weeks (the volume surge does move to 04:00 ET, but
    EMA / MACD lose there).
  - The one adopt-candidate is BLITZ's 25K later-break eval size (`research/scalp/blitz_25k_pick_v2.json`): adopted, owner 2026-10-31.
  - ATLAS paper lead (run `ab_atlas_na_hunts_lead`): the hunts x0.5 + the NA day-hold member x0.5.
    - More passes a month and more eval-path $ in all four spans: $2,046 / $1,584 / +$47 / +$194 a month vs $1,394 /
      $547 / -$148 / -$36; 13 of 15 neighbours do the same.
    - Fails the H1 2-week test: 62.2 / 5.9 vs 65.5 / 0.8.
- **Zlarior edge night (2026-10-30, `lit-edge-2026-10-30.md`, `tools/lit_edge.py` 190 variants, runs `lit_edge_*`,
  headline numbers `research/lit/edge_results.json`; LIT size + live two_week eval path + funded 50K $/mo):** target band
  from NQ's 5/10/20-day range or a VIX/range blend, re-anchored at the entry / midnight open / time left; BE at max or
  min(1R, k ATR or X pts); 15-minute check threshold in ATR; slow-trade nearer target; pre-registered A+ quality score and 13
  single-fact / mined size tilts (200-draw placebo; also on the funded path: size-ups -$16..+$16/mo, cuts cost up to
  -$109/mo); weekly catch-up (looser setup Thu/Fri when < 2 trades: +0.13 tr/wk); re-entry after the 15-minute cut or a BE
  (30 trades, -3.35R); a 2nd trade a day re-run (H1 -$1.0k..-5.0k); funded $2,000 cap as a take-profit (-$37 / -$70/mo);
  eval room-cap size + take-profit at the need (H2 2-week pass 33%); eval-only 3-6R bank; need buffer 0.8 / 1.2, clock
  press, room share by session: all rejected. Thin leads, not switched: afternoon target cap (from 14:00 at most 3R: LIT
  +$460 / +$311, eval +$606 / +$3,913, 2+1 trades) and lifting the 8R bank after +2R within 15 min (3 trades, funded
  -$143 / -$52/mo). Room share 0.7: same money, H2 2-week fails 5.8 -> 0.0% but slower passes (owner chose 0.8). Scale-in
  re-measured: eval +$13.8k / +$14.6k, 2-week pass 58.8 / 59.4%, but H1 fails 1.7 -> 3.4% and on a funded 50K -$149 / +$49
  a month (adds capped at the $2,000 winner -$22 / +$73). **Adopt-candidate (with the scale-in switch, after the Sim
  roundtrip): adds on the eval only from eval session 5, none on funded accounts** (run `lit_edge_eval_scale_in_s5`: eval
  +$38.7k / +$24.9k vs +$34.8k / +$16.3k, 2-week pass/fail 60.5/1.7 and 58.0/5.8 vs 57.1/1.7 and 52.2/5.8, sessions 2-6 and
  +4 ticks an add all hold; owner $/slot $827 / $815 vs $827 / $804 a month). Needs new code first: `lit_sizing`
  `scale_in_from_session` / `scale_in_funded` in `engine/live.py _add_qty` + `cloud_monitor.lit_add_usd` (not built).

- **Rapid EOD levers (2026-11-16, `rapid-levers-2026-11-16.md`, `tools/money/rapid_levers.py`):** on LIT + ATLAS $500 Rapid EOD 50K:
  eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse),
  eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size
  (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies
  pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
- **ATLAS deep edge (2026-11-15, `2026-11-15-atlas-deep.md`, `tools/atlas_deep.py`, 29 variants, slot $ at $43):** loser
  autopsy (member, side, hour, stop pts / ATR / vs the member's median, target R, daily trend, VIX, LIT's day, the members'
  paper day) finds no trade bucket that loses in all spans except the known 06:00 / 11:00 hours. Rejected (16 variants):
  skip / halve after LIT won the other side (slot +$19 / +$29, but 4 H2 trades worth -0.05R; random same-size skips pass
  the 2026 test 6.7% of draws = chance), same-side retry skip (retries are the best bucket) or x1.25 / x1.5, skip while LIT
  holds / after LIT won the same side, stop > 1.6x / 2x the member's median, first trades at x0.5 / x0.75 until green, eval
  weekly brake $400 / $600, daily-trend skip / halve, one signal per side a day. The one keeper is the zombie-eval rule
  (Second strategies above).

- **DAPHNE strategy-tree search (2026-11-03, `2026-11-03-strategy-tree.md`, `tools/strategytree/`, runs `strategytree_top1` /
  `_top5`, page `tools/web_public/tree/`):** 80 plain level roots (PDH/PDL, overnight, Asia, London, opening-range high/low;
  fade = sweep + reclaim, break = 5m close through; 1R / 2R; 60 / 120 min) x up to 5 conditions (vol quintile, gap, open vs
  yesterday's range, distance from the open, hour, weekday, VWAP side, EMA trend, VIX, OR width; ES agreement skipped: no ES
  before 2025-04), best-first branch-and-bound, train <= 2024, test 2025-26. 1,127,006 nodes, 54.6% cut by the bound; 31 of 80
  best rules hold out of sample vs 25 / 28 with shuffled conditions = chance. Every rule trades 0.1-0.5 a week. Nothing
  adopted; the page is a research lens, paper only.
- **E2 new NQ strategies (2026-11-13, `nq-new-strategies-2026-11-13.md`, `tools/e2_new_strats.py`, runs `e2_*`):** 7 families,
  140 variants, 5m RTH, $500 a trade, stops beyond structure: ORB 2nd side after a failed break, PDH/PDL sweep + climax
  volume (the volume gate makes it worse), NQ/ES relative strength at 10:00 (ES only 2025-04+), gap fade + failed opening
  drive + volume, VWAP reversion on low-VIX days, late-day break / last-half-hour reversal (the "since 2025" reversal loses
  in 2021-24), CPI/NFP/FOMC playbook (0.1-0.2 a week). 2 of 140 hold in H1/H2/2025/2021-24 vs 0.75 with coin-flip sides.
  Paper lead only: G1 gap fade (gap >= 0.1 x 14-day range, 09:30-10:00 range closes in its half away from the gap, stop 1
  tick beyond the range, 2R): $180 / $496 a month 2026 / 2021-25, PF 1.14 / 1.34, 1.7 a week, corr LIT 0.03; placebo p 0.003
  over 2021-25 but 0.22 in 2026; the plain gap fade loses; 2026 stops ~145 pts = 1 micro, so its own 25K / 50K passes 0-7%
  in 2 weeks and the slot is ~$0 a month; on LIT's funded 50K +$23 H1 / -$16 H2. BLITZ gap-aware band (Zarattini) H1 / H2
  $936 / $771 vs $912 / $577 but 2021-25 -$15 vs +$89; implied-vol band worse: BLITZ unchanged. No new eval account.
- **E3 same edge, more markets (2026-11-13, `es-and-sessions-2026-11-13.md`, `tools/e3_es_sessions.py`, runs `e3_*`):** live LIT and
  the 3 ATLAS members unchanged on ES1! as MES (points x 0.28, BE 0.75 ES pts; ES = 5m only, 2025-04+, no 1m, no 2021-24), each on
  its own MFFU eval. ES LIT H1 -$3.8k / H2 +$12.7k / 2025 -$15.9k (NQ 5m-exec +$6.6k / +$1.5k / -$0.5k), 50K 2-week 27.7/10.9 and
  44.9/15.9, corr LIT 0.14. ES ATLAS -$6.3k / +$2.2k / -$2.8k (NQ ATLAS +$47.3k / +$12.1k / +$13.0k): positive before costs, but
  costs are 7-13% of R on ES vs 2.5-5% on NQ (same tick, ~0.19x the points). NQ LIT NY-only slot as its own account +$12.8k /
  -$1.2k / -$2.6k at 1/wk; ES London / NY slots lose a span. Asia not redone. Nothing adopted; the 2nd stream stays NQ ATLAS.

- **S2 edge (2026-11-15, `2026-11-15-s2-edge.md`, `tools/lit_s2_edge.py` 28 versions, runs `lit_s2_*`, grid
  `research/lit/s2_edge_grid.json`; eval path at two_week room_f 0.4 kept past session 10):** "what other bots have":
  holiday-thin days (holiday Globex sessions, the day before / after, early closes, Dec 24 - Jan 2; x0.5 / x0.75 / skip),
  the contract roll window (5 sessions before the switch to the last trading day; x0.75 / x0.5 / skip), OpEx week / OpEx
  Friday / quad-witching week / turn of the month, NQ-vs-ES strength from the 18:00 open (lead x1.25 / lag x0.75),
  sweep of the day's or week's own extreme (x1.25, interior x0.75): none passes (calendar ones lose a half; ES strength
  and day-extreme are chance in Jul-Oct). Lead, not switched: target reachability (target pts / (5m ATR x sqrt(bars to
  15:55))) easiest third x1.25: LIT +$4,079 / +$1,021, eval +$2,724 / +$660, 2-week pass/fail unchanged, funded +$12 /
  +$19/mo, shuffle p 0.067 / 0.093; but easy trades without a tight stop add nothing (= the Nov 4 stop-ATR lead, which at
  room 0.4 loses $538 of H2 eval money).
- **E-LIT deep edge (2026-11-15, `2026-11-15-lit-deep.md`, `tools/lit_deep.py`, runs `lit_deep_*`, grid
  `research/lit/deep_grid.json`; eval two_week room_f 0.4 to session 80):** structural SKIP rules (engine `skip_keys`, the day
  left free for a later setup), Jan-Jun tercile and q80 cuts, 16 versions: target > 333 / 431 pts, target > 1.05 / 1.22 VIX
  day-moves, day range so far > 0.80 / 0.92 VIX moves, stop > 0.152 / 0.175 VIX moves, stop > 2.51 / 2.81 x 5m ATR, an
  opposing level within 0.97R / 0.61R, planned target < 7.46R / 6.13R, deep sweep + big displacement ("breakout"): none
  passes (best: target > 1.22 VIX moves LIT +$1,602 / +$81 but eval H1 -$2,872); the skipped trades still make +0.3-0.9R
  and a later setup rarely replaces them; trades fall to 1.2-2.4 a week in H2. Missed-setup census (cap 3 a day, limit / 1m
  CISD window doubled, 00:00-15:55, min target 1.0R, stop 4-120, Monday rule off): none adds money in H1. Loser structure:
  no single-fact bin loses in both halves; 425 two-fact H1 loser cells -> 88 lose again in H2 vs 95 by chance. H2 vs H1 =
  18% fewer trades/mo, 12% less R a trade (lower VIX, wider stops), 18% less $ per R; low-VIX trades +0.77R in both halves.

- **Smart entries (2026-11-17, `lit-smart-entries-2026-11-17.md`, `tools/lit_smart_entries.py`, 31 cells, grid
  `research/lit/smart_entries.json`; eval two_week room_f 0.4 to session 80):** same setups, other ways in. Pullback limit
  (candle 50% / 1m CISD level, 3 / 5 min, then market) only when the 1m CISD candle ran > 0.14 / 0.25R or is > 0.22 / 0.27R
  tall (16): H2 $2,670 -> $225-1,236/mo (closer BE + 15-min check scratch the H2 winners). 1m CISD OR a 1m BOS: +$1,778 /
  -$787, eval -$877 / +$2,069. CISD AND BOS / close above the zone / inside the swept level / 2+ down candles / strong close /
  close above the last high (7): Jan-Jun -$1.6k to -$24k. Wait 5-15 min for proof (4): -$8k to -$26k a half. Half now +
  half at minute 5 / 15 inside the same $ risk (3): -$8.7-10.1k / -$2.9-4.8k, eval 2-week pass 44.5 -> 15%. None passes.
  Wide-stop half size and an entry-quality score were not re-run (already rejected above).
- **Regime sizing (2026-11-17, `lit-regime-sizing-2026-11-17.md`, `tools/lit_regime_size.py`, 124 bucket cells, 8 size rules,
  grid `research/lit/regime_size.json`):** LIT x1.25 / x0.75 by the prior close's regime: GEX sign / level ($bn), VIX level /
  1-day change, VXN - VIX spread, VIX/VIX3M, prior NQ range percentile, 2-3 buckets each + every 2x2 pair, VIX / spread as a
  1-year percentile. Jan-Jun splits flip in Jul-Oct (VIX falling +1.09R vs +0.61R H1, +0.14R vs +1.24R H2); H2 sits in one
  bucket (VIX low, spread high, gamma positive on 38-40 of 40). Only gate-passer VIX/VIX3M high x range: +$37 / +$119/mo,
  placebo 0.53, 5+2 H2 trades, VIX3M ends 2026-09-17, 2021-25 -$1,089, 2-week pass 44.5 -> 42.0%. None adopted; Rapid not run.
- **Learn loop first night (2026-11-15, `docs/LEARN_LOOP.md`, queue `research/learn_queue.json`):** Zlarior size x1.25 on low dealer
  gamma / after a tight Asia range / on a many-times-touched or an old swept level / on a fast fill after the CISD, x0.75 the day after
  a VIX jump; ATLAS x1.25 after Zlarior was stopped on the other side, x0.5 on a two-way day: all 8 rejected (best: old level +$138 /
  +$125 a month at the LIT size but eval path Jul-Oct -$34). The loop re-checks them on new bars.

- **Kalshi K8 better edge (2026-11-20 night-kalshi8, `research/writeups/kalshi-k8-monday-2026-11-20.md`, `research/kalshi_k8_monday/edge.py`,
  84 variants, one-sided Bonferroni t >= 3.24 found on Aug 3-Oct 21, checked on the held-out Oct 22-Nov 19, $2.50 bets, the +20 s tape
  price, verify.py fees): NOTHING passed. Entry +10 s pays 0.15-0.5c MORE than +20 s (-2% to -3% per $1), +40 s pays 0.8c more and
  misses 19% of fills: +20 s stays. Price caps 50-60c per leg (30): the skipped dearer bets still made +19% to +53% per $1 in the find
  weeks (only gold 16:15 above 60c lost, 8 bets). Leg filters from the metals' own path on Kalshi's settles (48: previous quarter hour,
  4-hour move, the session before, 8-hour volatility vs its 20-day median, skip either side): every skipped group made money (+6% to
  +76% per $1), so every filter costs money. Pause a leg after 2 / 3 losses in a row: the next bet won 19 of 22 (+70%) / 3 of 3 in
  the find weeks, 10 of 15 held out. Roll days: natural gas UP 17:00-17:15 won 15 of 15 but now costs 93c (+7% held out, loss-rate
  bound 39% vs 15% break-even, about $2 a month at $2.50); WTI DOWN 17 of 20, +43% / +50% but t 2.41 on 20 bets (about $6 a month).
  CME holiday / early-close skips are a safety rule, not testable (Labor Day was the only US holiday: the evening legs won that day).
- **edge2 (2026-11-21, `edge2-2026-11-21.md`, `research/edge2/`):** 10 pre-registered. ATLAS deep limits 8 / 16 ticks better for 15 min: fill 38-45%,
  miss $22-39k of winners, funded $ halves. ATLAS stop entry +12 ticks / 5 min (A3): H1 funded $511 -> $631, lost 16 -> 3%, 2021-24 PF
  0.80 -> 0.99, but H2 $401 -> $398 / 20.7 -> 23.5% and 2025 6t -$74/mo: fails (PAPER LEAD - skipped signals lose every year, -0.22..-0.66R);
  +20 ticks / 10 min worse in H2. New NQ setups at $250: IB failed-break fade, IB break-retest limit, prior-day level break-retest limit,
  opening gap fade to the prior close, first-hour trend at 10:30 (+$45 / +$197 / +$121 a month, PF 1.08 H1, 0.5/wk H2), overnight-inside
  breakout: none PF >= 1.2 in all 3 periods; all add -$500 days on a shared 25K. 0 pass.
- **Holidays / roll / FOMC windows (2026-11-21, `holidays-2026-11-21.md`, `research/holidays/`):** Thanksgiving week, CME roll-date week,
  Dec 15 - Jan 5, FOMC days x sit out / half, LIT and ATLAS (LIT roll = already rejected): 0 of 14. 2021-25 windows all weak (LIT PF
  0.14-0.89, ATLAS 0.51-0.75 vs ~1.1) but 2026 windows profitable (FOMC LIT +$634/trade, ATLAS roll PF 8.9): sit-outs lose Jan-Jun $
  (LIT FOMC -$2,535, ATLAS roll -$2,985). Thanksgiving / late Dec have no 2026 sample (untestable). Nearest: ATLAS FOMC out (funded lost
  down in all 3, but Jan-Jun fixed -$1,223).
