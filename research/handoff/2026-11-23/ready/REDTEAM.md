# READY check red team (2026-11-23): day-ready 26efd7070 -> day-ready-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | Sim / paper days: preflight.arms marks every non-LIVE account not ok, so "Zlarior on Sim101" or "ATLAS armed on Sim" = NOT READY "is not armed" + a loud alert | HIGH (false NOT READY + spam) | Only LIVE-not-armed / DISABLED is NOT READY; Sim while another account is LIVE = WARN "is on Sim"; no LIVE account = paper_only, no loud alert |
| 2 | 7-day clock used calendar days only: Friday with MFFU's last day Sunday (2 days, 1 session) = WARN, and WARN never alerts -> account can close silently | MED | sessions left counted (clock7's own red: 1 day or 1 session) |
| 3 | "At most hourly" not held: a new / flapping blocker lifts the hour rule; a different blocker every 5 min = 12 alerts/hour | MED | flapping blocker is not "new" (told within the hour); 10-min floor between loud alerts |
| 4 | Clock: raw Date-header drift vs the guard's proven drift (whole seconds + round trip): a right clock near 5 s shows NOT READY while the guard trades | MED | proven_drift() = engine/guards.clock_probe's math |
| 5 | Start hook runs on dev / test servers and the Sunday self-test's sealed children (PCWATCH skips them): real alerts + real data/ files | MED | same env switches (LE_NO_AUTOSTART, LE_SELFTEST_CHILD, LE_PC_WATCH=0) + LE_READY=0 |
| 6 | data/ready_last.json / ready_state.json not gitignored (comment says they are) | LOW | .gitignore |
| 7 | Two writers (ops task + server start) share one .tmp name | LOW | tmp per pid |
| 8 | ops tick reruns run_checks inside readiness (not passed `checks`) | LOW | not changed (cheap file reads, own process) |

Checked OK: server hook = import in try + daemon thread (a 60 s hang returns at once; an exception dies in the thread); ops hook in
try/except in the 5-min pythonw task (own process, 10-min limit, IgnoreNew; no lock with the trade loop); writes only its 2 files,
no subprocess, never arms/starts; bars at halts/weekends/holidays are INFO via ops_checks.market_open + cme_calendar.halted; the
17:30 slot inside the daily halt sees no stale bars; de-dup state on disk survives a restart; rd <= 200 B, no time, no ids
(friendly names only); signed post path unchanged. Merges with day-clockfix and day-clockfix-rt: no conflicts.
Tests: tests/test_ready_rt.py 27/27 (10 fail on 26efd7070). test_ready 36/36, pc_report_sign 21/21, live_publish 86/86, alert_bus
86/86, hidden_bots 64/64, nqops 34/34, trading_home 46/46, ninjatrader --selftest 80/80. Trade code diff 0 lines.
Verdict: SAFE TO LAND with day-ready-rt (not 26efd7070 alone: item 1 alerts the owner on every Sim day).
