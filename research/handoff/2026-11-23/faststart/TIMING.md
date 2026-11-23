# START BOT timing (night-faststart 2026-11-23)

Owner: "running the bot takes too long". START_BOT.bat = `python -X utf8 -m engine.go`. Measured here (Linux cloud, paper/dry world;
`startwait.py` in this folder runs both trees on one fake clock: only START's own waits are counted, nothing real runs).

## Where the time goes (cold start -> "WHAT HAPPENED" summary)
| Step | Before (night-integrate) | After (night-faststart) | What changed |
|---|---:|---:|---|
| Python start + imports + names + every check (`--dry-run`) | 0.5 s | 0.5 s | nothing: imports are 0.28 s (pandas via engine.second), not worth touching |
| 1 update (git fetch of the backup) | network | network | unchanged (needed: new code) |
| NinjaTrader log-in (connected 7 s after the prompt) | 10.0 s | 8.0 s | looks every 2 s (was 5 s); limit still 15 min |
| chart fix, Sim test only (bars back 20 s after the hint) | 30.0 s | 21.0 s | every 3 s (was 15 s); limit still 15 min |
| server stop before a restart (down at 1.3 s) | 2.0 s | 1.5 s | every 0.5 s (was 1 s); limit still 30 s |
| server start (answers at 3.2 s) | 4.0 s | 3.5 s | every 0.5 s (was 2 s, first look only at 2 s); limit still 120 s |
| ATLAS arm: engine.ninjatrader --selftest | 0.8 s here | 0.8 s | unchanged: a safety gate, runs only when ATLAS is not armed yet |
| launch checklist, green 12 s after the bot starts | 20.0 s | 12.0 s | looks at once, then every 3 s (was: sleep 10 s FIRST, then every 10 s); limit still ~90 s |
| launch checklist, already green | 10.0 s | 0.0 s | the same: no fixed 10 s on every START |
| **The five waits of one START** | **66.0 s** | **46.0 s** | **-20 s (-30%); -10 s on every START where the checklist is already green** |

Not cut (they protect money or need the PC): the Sim101 roundtrips (only until both passed once), the 5 s pause before the
direct-write retry, the selftest gate, NinjaTrader's own connect time, the bot's startup reconcile, the git fetch.
No trading code changed: engine/go.py waits only (start_server, stop_server, ensure_ninjatrader, ensure_feed, checklist_launch).
Proof on this branch: tests.test_lit_live OK (intraday 9,923 polls on 120 trade days, 0 differences; day-end replay 120/120 trades identical); engine.ninjatrader --selftest PASS (80/80); tests.test_faststart 11/11; test_go 76/76, test_start_api 117/117, test_arm_rt 47/47, test_rapid_arm 19/19, test_zerotouch 50/50, test_trading_home 50/50; smoke 10/11 (zenith_mode: no python playwright); win_paths fine.
