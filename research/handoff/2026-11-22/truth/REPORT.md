# night-truth (2026-11-22) – the phone tells the truth, fast

| What | Result |
|---|---|
| (1) Lag | engine/state_pulse.py (server thread, 10 s tick): a state change (running/stopped, armed/disarmed, entry block, trade open/close, lock) -> fresh heartbeat + live.json + `pc_report.py --pulse` (core post only) at once; debounce 30 s, 90 s start grace for "stopped", <= 24/day, held at ntfy's 12-post reserve (own count + ntfy's /v1/account) |
| Budget | 96 core + 66 ext + 24 chart + 24 pulse = 210, + 12 reserve = 222 <= 250 (state_pulse.budget(), tested). Tonight's posts came in PAIRS ~2 min apart (two report runs per 15 min on the PC); a core with the same state < 5 min after the last is now skipped (pc_report.core_sig) – saves up to ~96 posts/day |
| (2) Audit | FIELD_AUDIT.md: core `ar` {bot: [on, armed]} + ext_hash on armed, account rows keep enabled/locked, post built from the bot's 15 s live.json, braincore prefers ar, accounts.js $0, mffumodel lt/ft; glance gaps (b25k_2, Rapid room) handed to Package C |
| (3) $0 | board.py ATLAS funded "$401 (MFFU from $0, floor -$599)"; phone pages already used pc_feed.mffuView |
| (4) Trading Home | synthetic ATLAS row + held rules; one line per account under the 5-line checklist: "ARMED, running · room $1,046 · today $0 · next Mon 02:00-15:30 ET" (4 accounts, real post) |

Lead: nothing lead-only touched (mffumodel ?v=5 bumped in the 5 pages that load it; sw.js has no entry). On the PC: the two report runs a
15 min – check Task Scheduler for a second task running tools/pc_report.py (the dedupe covers it either way).

Package D extras: launch checklist test tolerant of rapid/rapid2/blitz lines (simulated), test_ops FIX_CLOCK.bat, run_area pc +14 suites (all green here; selfheal needed fsutil.replace in state_pulse), data_health WHY for GEX / CBOE.
