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
