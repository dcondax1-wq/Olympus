# 3 PM report, 2026-10-25 (work 02:30-10:40 ET, all merged into main)

## What's new today
1. **Phone app: 142 features (66 new)**: Goals card at the top of Home (progress to target, room to floor, sessions
   left, trades this week vs target, ATLAS 20-trade scorecard, month vs expected, payouts, scale step), Today's plan
   (what the bot waits for, countdowns, news chips, early-close / clock-change banners), Launch checklist card, More hub
   with search and 6 sections, week heatmap, last 10 trades with pictures, 12 health lights, eval timeline, ATLAS stats
   per setup, ATLAS v2 shadow card, All-features page. (PR #37, #39, #40)
2. **PC dashboard: 61 new features**: Command center home (50K and 25K side by side, 9 health lights, launch checklist),
   Goals, eval timeline, session calendar, trade log + CSV, ATLAS per setup, emergency runbook, audit evidence, All
   features; 6-group sidebar, Ctrl+K, dark/light.
3. **Launch checklist** (phone + PC): 10 lines turn green from the PC's own data; each red line shows its fix command.
4. **ATLAS v2** (research, PR #38): the only change that held up = add LIT's two stop hunts at half size. 25K 2-week pass
   H1 67.2% / H2 55.1% (today 65.5 / 43.5); with "new eval below $200 room" positive in all four periods (H1 +$10.9k,
   H2 +$3.9k, 2025 +$0.2k, 2021-24 +$4.6k). Picked with 2025 / 2021-24 in view, and one hunt was called weak / luck in an
   earlier audit, so: **running as a paper shadow next to the live ATLAS** (PR #40). Decide after 20+ hunt trades
   (shown on the ATLAS page). Live ATLAS is unchanged.
5. **App icon: 19 options** (A-M, then detailed Compass J1-J3 and Orbit K1-K3). Pick one code; applying is one command.
6. **Pre-launch audit (earlier today, PR #36):** 9 bugs fixed incl. the kill that would have flattened the 50K too and
   the hedge-close gap; full report research/handoff/2026-10-25/README.md.

## Numbers to expect (costs in, judged on 2026)
- LIT 50K: ~2.9 trades/week, Jul-Oct ~$2,670/month (LIT size rule), fresh-eval 2-week pass 57% / 51%, no breach.
  On your real 50K ($3,289 to go): ~1 in 3 two-week stretches pass, the rest still open (not failed).
- ATLAS 25K: 2-week pass 66% / 44%, 0 fails; thinner edge than LIT (2025 negative).
- Live will scatter around the backtest (the bot trades MNQ bars, the backtest NQ).

## Tonight, PC, after 18:00 ET
1. `python -m engine.launch_prep --atlas "YOUR_25K_NAME"`
2. Stop the bot; on Sim101 run `python -m engine.ninjatrader --sim-roundtrip` then `--sim-roundtrip-add`; send me the output.
3. If both pass (the launch checklist goes green), arm both accounts yourself.
