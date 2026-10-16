# Night log · 2026-10-15 → 16 (launch target 5:15 AM ET)

## 21:50 ET
- Agents finished: research (NIGHT_REPORT.md: no default changes; giveback holds walk-forward; first-week odds 4%/21%), UI overhaul (Space Grotesk / Oxanium / Unbounded, new hex-aperture logo, glass theme), Tradovate live layer (engine/tradovate.py, engine/golive.py, Live page checklist + arm + kill; offline self-test PASS), features (Ctrl+K palette, what-if sliders, edge-decay monitor, MFFU gauges, voice briefing, Weekly Review page, /api/extras/*).
- Still running: live-loop QA agent (engine/live.py, tests/test_live_dryrun.py, pluggable data_source + stale guard).
- Fixed: server.py `_tv` name clash (module alias vs webhook dict) that 500'd /api/tv/status. Server restarted; all pages load, no JS errors; go-live checklist runs (creds rows red as expected, feed/clock/risk/news/gate green).
- Added myself: exit-signal markers on chart + Daily Report "Warning signs" column; LIVE presets (Day 1 $250 / Steady $350); Playbook kill rule; Chart.js font to Space Grotesk.
- Data: Dukascopy 2024 download at 168/~250 days (mid-Aug 2024). Rebuild + re-run studies when complete.
- Yahoo NQ feed measured ~10 min delayed → live must use the Tradovate bar feed (data_source "tradovate").
- Open for the user: confirm MFFU account is Tradovate; create Tradovate API key (CID/secret) and set env vars per README "Going live".

## 22:05 ET
- QA agent finished: 44/44 dry-run assertions pass (tests/test_live_dryrun.py, 3 sessions replayed; entries/exits match the backtest exactly; failure injection, restart persistence, kill switch, limits, news block all hold; poll_once ~330 ms). live.py now has health block in snapshot, data_source yahoo|tradovate with fallback + stale entry block, state persistence (data/live_state.json), clock-based safety flatten, DESYNC detection. Ranked risks in tests/README_LIVE_QA.md.
- Server restarted with all agent work integrated.

## 21:55 ET (the 22:05 stamp above was an estimate; actual 21:50)
- Live path exercised end to end on real data: /api/live/poll 1.2 s, data age 466 s (= Yahoo delay), health clean. Paper bot started for an overnight stability soak (paper adapter, Yahoo, 60 s polls); no orders possible in paper mode.

## 22:34 ET check-in
- 2024 download: 216 days, at 2024-10-25; process alive. Not complete yet.
- Paper soak: running, 0 errors, feed age ~520 s (Yahoo), bot logged Yahoo bar revisions (expected; a reason live must use the Tradovate feed).

## 23:35 ET check-in
- 2024 Dukascopy download COMPLETE: 264 trading days of 2024 (58k 5m bars) in NQX_5m.csv. Running study_be.py and engine.discovery on the full year (background); results -> research/study_be_full2024.txt, research/discovery_full2024.txt.
- Paper soak: running, 0 errors, feed age ~9.5 min (Yahoo delay).
- Discovery on full 2024 (334 candidates, avg +0.16R, a positive unseen year): STABLE = VWAP value side helps (+0.31R, already in the grade) and London H/L raids hurt (-0.27R, sizing penalty was tested earlier and did not help taken trades); discount/premium is no longer flagged negative. study_be still running.
- study_be on FULL 2024 (175 trades, 3.7/wk): current defaults +$5,259, PF 1.52, +0.14R, max DD -$1,880. Four-period record now: NQ 2026 +12.6k | Q4 2023 -2.4k | 2024 +5.3k | Q4 2025 -1.1k = +$14.4k total. 'BE off' would total +16.4k but loses more in both losing periods and gives back $318 on NQ 2026 -> not adopted before launch; noted as a candidate for later. Re-running giveback variants (study_exitsig2) on the full year.
- Giveback confirmed on full 2024: with it +$5,259 / PF 1.52 / DD -1,880 vs effectively without (threshold 1.0R) +$3,922 / PF 1.34 / DD -2,247. Helps in every CFD period incl. the full year; 0.5R remains the best threshold. Defaults unchanged. Regime page write-up updated for the full-year result.

## 00:35 ET check-in
- No new agent output. Paper soak: running, 0 errors, feed age ~9.5 min, Yahoo bar revisions logged (expected).
- Regenerating the phone snapshot CSVs with the full-2024 period for the morning artifact refresh.
- Phone snapshot artifact refreshed with the full-2024 period row and updated intro text.

## 01:34 ET check-in
- All pages load; paper soak running 3.5 h with 0 errors; feed age ~9 min; live_state.json persisting each poll. No new agent output. No code changes this hour (freezing the build ahead of launch; only the 5 AM report remains).

## 02:34 ET check-in
- Paper soak 4.5 h, 0 errors, feed age ~9 min. Build frozen; nothing to integrate.

## 03:34 ET check-in
- Paper soak 5.5 h, 0 errors, feed age ~9 min. Build frozen; nothing to integrate.

## 04:34 ET check-in
- Paper soak 6.5 h, 0 errors, feed age ~9 min. Build frozen. Morning report due at 05:00.

## 05:23 ET
- Morning report delivered (MORNING_REPORT.md). Overnight check-ins end here; hourly job removed. Waiting on the user's Tradovate confirmation and API key.

## 07:15 ET
- TradingView export (user signed in, Plus plan): MNQ1! 5m history available only from 2026-08-24 (10,876 bars). Imported over Yahoo for that window (backup: data/NQ_5m.yahoo_backup.csv). Same 29 trades: +$10,718 PF 6.94 on exchange bars vs +$12,642 PF 9.87 on Yahoo bars. Note: importer also wrote 5m-spaced rows into NQ_1m.csv for Aug 24+ (1m file is now mixed; only matters for 1m experiments).
- Agents launched: persistent trade memory (SQLite, learner seeding, Memory page) and the 1-minute-trigger study.
- Jan-Jul 2026 CFD download running (data/duka_2026.log).

## 15:05 ET Fri
- Server had died with the old session at 07:16; restarted 14:52, paper bot restarted (armed long after PDL/ONL/ASL sweep). Lesson -> always-on supervisor agent.
- FINDING: Tradovate gives no API keys to prop/eval accounts -> live path = TradingView Pine strategy + webhook bridge (TradersPost/PickMyTrade), runs with PC off.
- Owner rule: futures only, no CFD. NQX files moved to data/_cfd_archive; discovery slices now NQ month blocks + ES.
- 10 agents: memory, 1m trigger, always-on, Pine+bridge, regime, confluence x2, data audit, launch page, news calendar.
