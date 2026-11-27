# Order-flow lane (Sim102 only, OFF by default) - night-of-lane 2026-11-27

What: `engine/of_lane.py` routes the order-flow PAPER bot's lane A trades (absorbed level fade, `engine/of_paper.py`,
rules `research/orderflow/DESIGN_paper.md`) to a NinjaTrader **simulation** account through the existing adapter
(`engine/ninjatrader.py`). Same decision code as the paper bot (`of_paper.step`), no second rule.

Status of the idea: a CANDIDATE (51 real days: taken +0.49R vs skipped -0.31R, p 0.0065, but the halves differ). Forward
days decide. The lane is for running it on Sim102 next week (its own Sim account: red team 2026-11-27, so it never fights atlas_exec's Sim101 week or START's Sim test for the account lock; **Sim102 must exist in NinjaTrader: Accounts tab > Add Sim account**, `--sim status` says so when NinjaTrader does not list it); an eval / funded account needs the forward gate + the owner's yes,
and that switch is NOT built (any non-Sim account is refused in 3 places: the switch, the tick, the adapter's own live gate).

## Switch (owner or the lead, one line on the PC)
    python -X utf8 -m engine.of_lane --sim on        # Sim102, $200 risk a trade, max 10 micros
    python -X utf8 -m engine.of_lane --sim off       # no new trades (an open Sim trade keeps its stop/target + 15:55 close)
    python -X utf8 -m engine.of_lane --sim status
File: `data/of_lane.json` {"on", "account", "risk_usd", "max_micros", "plan", "stage", "news_min"} (gitignored; absent = OFF).

## Runner (lead wires it; not wired tonight)
`python -X utf8 -m engine.of_lane loop` = every 15 s until 16:10 ET, its own process (it holds the Sim102 account lock
`le_locks\Sim102.lock`: nothing else may trade Sim102 at the same time). Suggested hook: engine/ops_checks next to
`of_paper_kick`, started detached at 09:20 ET on weekdays only when `data/of_lane.json` says on. It needs LE_TickRec on
(the live tick file `le_ticks\NQ_<day>.csv`).

## Guards (any one = not routed, logged in plain words)
switch OFF | not a Sim account | kill (`live_state.json` kill or `data/of_lane_kill`: no entry + flatten) | CME holiday /
weekend / half-day cut (15 min before an early close) | decision > 2 min after the bar close (never chased) | Tier-1 news
+-2 min | the lane's open trade or ANY Sim102 position (one per account) | another account holds the opposite NQ side (hedge)
| size: `sizing.second_qty` at the fixed $ risk | `firms.check` with the MFFU Builder 50K eval rules on the lane's own book
(soft DLL $1,000, EOD trailing $2,000, contracts, flat time). Exits: OCO bracket (stop 1 tick beyond the sweep bar, 2R),
adapter flat at 15:55 (5 min before an early close), kill flatten. Restart: the adapter's write-ahead state
(`data/ninjatrader_state_oflane.json`) restores the bracket; a send interrupted before the order file is never resent.

## Logs
Order lines `logs/ninjatrader_oif_oflane.log` -> `engine/datapipe.day_fills` lane "oflane" (unified fill log); the lane book
`data/of_lane_state.json` (trades, refusals with why, closes, $ after $1.90/micro).

Entry (E5, night-of-exec 2026-11-27): price already back at / beyond the swept level -> market; else a resting LIMIT at the level
for 300 s (adapter opt-in keys entry_limit / entry_wait_s / target_rr; no key = the old MARKET path for every other bot),
cancelled if the stop trades first (no trade), else one market entry at 300 s (guards re-checked). Target = 2R from the real fill.

Real days (tools/of_lane_realcheck.py, 53 days 09-27..11-26, v1 paper fills): 40 taken -> 30 sent at $200 risk (10 skipped:
stop > $200 on 1 micro, those averaged +0.50R too), +$2,513, 3.5 trades/week, max DD -$950. $300 risk: 37 sent, +$5,171, DD
-$1,362. Owner picks the $ risk; Sim money either way.

Tests: `python tests/run_area.py pc` (suite `of_lane`, ~6 min, fake NinjaTrader, synthetic tick days).

## Ready to switch on from the phone (night-of-lane-ready 2026-11-27)
- **Telegram** (the owner's private chat only, never the control path): `/oflane on` = the switch ON for the Sim account +
  today's paper line + the ladder step; `/oflane off`; `/oflane status` = account, today's lane trades, the ladder step.
  It takes no account name; a real / MFFU account is always refused.
- **Account** (auto): Sim102 when NinjaTrader lists it; when the fresh account list has no Sim102 AND nothing else uses Sim101
  (ATLAS's Sim101 week off, no ATLAS / Rapid / combo lane on Sim101, nobody holds the Sim101 lock) -> Sim101, and the reply
  says so. Unknown list -> Sim102 + "could not check". Re-picked each morning while flat. `--sim on --account SimNNN` pins one.
- **Runner**: `engine/ops_checks.of_lane_kick` (the 5-min ops task) starts `-m engine.of_lane loop` detached at BELOW_NORMAL
  on weekdays 09:20-16:15 ET only when on + a Sim account + no kill; never twice (heartbeat `data/of_lane_run.json` < 2 min,
  or a start < 3 min ago). 16:15 -> stop flag `data/of_lane_stop`; the loop exits only while flat (16:10 / flag / OFF / kill).
- Card draft: `research/handoff/2026-11-27/oflane/card.json` (the lead wires it into decisions.json).

## Monday dry run + the dashboard fields (day-ofready2 2026-11-27)
- `tests/test_of_dryrun.py` replays REAL days (data/pc_days) through the real path: /oflane on (fake Telegram) -> the 09:20
  ops kick -> the runner (run_lock, heartbeat) -> the live tick CSV rebuilt by `tools/of_replay_ticks.py` (bars + footprint
  identical to the PC's summary) -> paper decisions = the paper bot on the real summary -> guards (day cap, real news, half-day
  cut) -> Sim orders in a fake NinjaTrader (E5 limit / market) -> exits -> flat after 16:10 -> /oflane status. Days: Monday
  11-23 (Sunday Globex file before it), Thanksgiving 11-26 (halt 13:00), 11-27 (halt 13:15; 11-25's ticks re-dated). `--full`
  adds 11-24 / 11-25, `--one` only Monday. ~9 min; SKIP without data/pc_days.
- Status ext block `ofl` (tools/pc_report.py, engine/oflive.lane_tiny, <= 400 B, inside the 15-min status): {on, account, cap,
  used, day, trades[{t, dir, qty, status, pnl, why}]} (today's, newest 4; why = short plain words, oflive._short_why).
- Day file `NQ_lane.json.gz` (engine/of_lane.export_day) rides the nightly 'of' answer + the backfill: the public view (R only)
  + `sim_rows` = the forward ladder's step-1 rows (tools/of_ladder.lane_sim_rows: R, usd_1, fill_gap_ticks vs paper).
- Telegram `/oflane on|off|status`: short lines with emojis (engine/of_lane.tg_text); the CLI `--sim status` keeps the detail.
