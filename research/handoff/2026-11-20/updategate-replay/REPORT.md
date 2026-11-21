# Update gate + replay (day-speed, 2026-11-20 evening; idea #11 of TOP25_IDEAS)

## For the owner (one minute)

**A new safety check replays the bot's last 10 trading days with the new code and the old code before an update. If a
trade changes and nobody changed the strategy files, it says HOLD. Tested: a hidden one-tick stop bug was caught on all
4 trades. Today's real update candidate (the speed-ups) changes nothing.**

| What | Result |
|---|---|
| Latest pc vs day-speed (both speed-ups), PC's last 10 sessions Nov 6-19 | SAME: 7,680 polls, all 20 LIT + ATLAS trade lines identical |
| A planted bug (stops 1 tick off, code only) | HOLD: names all 4 entries (LIT Nov 16, ATLAS Nov 6 / 17 / 18) and the stop change |
| Why the Nov 18 ATLAS short was missing in the earlier replays | my replay ran ATLAS as an eval; after Nov 6 + Nov 17 it was "passed" (+$1,539 > $1,500), so the pass lock stopped it. In the funded stage (as on the PC) it trades Nov 18 04:50 SELL 2 with the real stop 27,422.50 |
| Time to run | ~67 min (old code) / ~35 min (new code, the speed-ups) in parallel on this cloud box |

Nothing for you to do. Report-only: it never holds or blocks an update yet.

## How it works

`python -X utf8 tools/update_gate.py --base HEAD --candidate <sha> [--sessions 10] [--json out.json]`

1. `git diff --name-only base candidate`; MODEL_FILES (live_model.json, live_model_lit.json, live_model_*.json,
   second_model.json, accounts/*.json, engine/sizing.py) mark a deliberate strategy / sizing change.
2. The last N CME sessions in data/NQ_1m.csv (weekdays with bars 01:30-12:00 ET).
3. Two scratch git worktrees (base, candidate); each runs research/speed/replay_harness.py, copied from the gate's own
   checkout so the harness is identical, with `--atlas-funded` and `SPEED_DATA_DIR` = ONE data dir for both. The harness
   runs the real engine.live.LiveBot (paper, frozen clock, data_source ninjatrader) on LE_BarFeed-format files growing bar by
   bar, with ATLAS (account B, funded 25K, its 3 live members): bar reading, merge, model, sizing, routing all exercised.
4. Compare LIT + ATLAS ledgers per entry (side, qty, stop, target, $, exit reason; the route second is ignored, since speed
   changes move it), plus LIT's state on every poll and the poll errors.
5. Verdict / exit code: SAME 0, EXPLAINED 0 (trades differ and a model / sizing file changed: listed for review),
   HOLD 2 (trades differ with no model / sizing change), ERROR 1 (a replay failed, or the candidate's poll raises more).
   Worktrees are removed at the end.

Results: gate_pc_vs_dayspeed.json, gate_demo_bug.json (this folder). The demo bug was a LOCAL commit (engine/live.tick_px
stop + 1 tick), never pushed, branch deleted.

## For the lead / day-security2 (autoupdate)

Not wired into engine/autoupdate.py (day-security2 owns that file). Suggested call, after 16:10 ET on the PC, before a
fast-forward that touches bot paths:
`python -X utf8 tools/update_gate.py --base HEAD --candidate origin/pc --json logs/update_gate/<sha>.json`.
Exit 2 -> keep the old code, push "UPDATE HELD: <n> trades differ" (the existing bad_sha path); exit 1 -> report only.
On the PC it will take longer than here (2 replays at once next to NinjaTrader): run it with `--sessions 5`, or in the
evening only. It needs the PC's data/NQ_1m.csv to hold the last sessions (the TradingView export + imported bars; the PC's own
archive data/nt_bars is not read yet: a follow-up could point SPEED_DATA_DIR at a merged copy).

Limits: paper sizing (the harness's paper account, not the eval room), so a sizing-only change on a real account's room is
covered by the eval tests, not here; one LIT account + ATLAS funded (no Rapid lane, no extra accounts); polls each minute
01:30-12:00 ET and every 5 min otherwise (an exit decided between 12:00 and 16:00 is seen at the next 5-min poll).

## Tests

tests/test_update_gate.py 13/13 (verdict rules, model-file list, session picker, a real HEAD-vs-HEAD two-worktree run
with worktree cleanup checked; `--quick` skips the real run).
