# REPORT: data health (TOP25 idea #5), day-brief 2026-11-20

| What | Result |
|---|---|
| 1. ES research bars (stopped Oct 16) | Cause: the PC never asks NinjaTrader for an ES contract (feed_instruments = MNQ only, + NQ with signal_root NQ; the live signal_root is **MNQ**, so "add ES only when signal_root is NQ" would still send nothing). Fix = `ninjatrader_es_feed.patch` (NOT applied: engine/* is off limits for helpers): MES with MNQ, ES with NQ, same roll day, cfg `feed_es: false` = off, + 1 selftest line. Patched copy: selftest 80/80 PASS (79 today + the new line), test_roll_now 43/43, test_dec_roll 37/37 |
| Trading effect of item 1 | None on routing: ES bars reach only the learning loop's ES features (LiveBot._learn_es) and the data pipe. NinjaTrader subscribes one more contract (MES / ES market data: included in the owner's NinjaTrader data, no paid service) |
| 2. Board DATA line | `tools/data_health.py` + `tools/board.py read` prints e.g. `DATA  6 of 13 files fresh (newest 11-19) / STALE: CBOE_vol_1d end 09-17 (45 sessions); ES_15m, ES_1d, ES_1h, ES_5m, GEX_1d, NQ_1d end 10-16 (24 sessions)`. Stale = more than 3 CME sessions (weekends + CME closures skipped). Newly stale files get ONE Board note (claude_note, deduped per file + newest day; `--no-data-notes` = print only) |
| 3. December roll in data_pull | `tools/data_pull.py roll_from_pc`: when pulled PC days are on the contract after the anchor (NQZ26 -> NQH27) and share bars with data/NQ_5m.csv, the offset is measured with `engine/pcbars.basis_shift` (constant, or steady over the last 120 shared bars; noise never counts); 1m must agree within 1 pt. Steady -> NQ_rolls.json gets the roll (method pc_merge_basis), the anchor moves, every older NQ_{1m,5m,15m,1h} bar gets +gap (backup in data/_import_backup/), then the new days import normally. Not steady / nothing shared -> nothing written, one line why. `--dry-run` writes nothing |
| Tests | `tests/test_dec_roll.py` part E (+7 checks, 37/37): steady roll recorded and file = truth + D bar for bar (5m and 1m), backup, no double shift on a 2nd pull, no shared day -> refused, noisy offset -> refused, dry run. `tests/test_data_health.py` 19/19 (sessions math, DATA line, notes dedupe, board.py line, the patch applies + patched selftest green). `tests/test_roll_now.py` 43/43 now and after the patch. Smoke 9/10 (red = no Python Playwright here) |

## Found on the way (real stale files today)
- ES_5m / 15m / 1h / 1d: Oct 16 (24 sessions): item 1 fixes it once the patch is on the PC.
- NQ_1d: Oct 16. data_pull builds 5m/15m/1h from the PC's bars, never 1d (import_futures TFS). Any 1d reader (dash
  caches, research) sees Oct 16. Not fixed here (a data-file rebuild = research data change; ask before).
- GEX_1d: Oct 16, CBOE_vol_1d: Sep 17: the PC's engine/gamma.py / engine/news.py refreshes do not reach the cloud.

## Honest limits of item 3
- It needs ONE day the cloud already has, re-sent by the PC on the new contract. `--latest` asks from the day of the oldest
  newest bar, so the first pull after the switch normally re-sends that day; if that day was packed before the chart switch
  it is still on December and the line says "no bars shared ... re-send". Fallback: the TradingView path in
  docs/ROLL_DEC_2026.md (tools/import_tv.py --roll).
- The switch time recorded is "just after the newest bar on file" (everything on file is December), not TradingView's
  Dec 14 switch. A later TradingView re-export with `import_tv --roll` will see the roll as already recorded; check its
  message then (import_tv compares known rolls by contract code).
