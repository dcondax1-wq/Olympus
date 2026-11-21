# day-nqops 2026-11-21: LEAD_WIRES (only what a helper may not do)

Base: olympus/pc 7adf312d. All bot-side pieces are read-only notices (no order, arm or route code touched; engine/live.py,
lit_live.py, notify.py, server.py, scripts/*.ps1, *.bat untouched).

## A. pc-watch.yml: add the Sunday runs (the workflow lives on `main` AND `pc`: lead only)

tools/pc_silent_check.py now sends ONE "PC is off: market opens in N min" push in two pre-open windows: Sunday 17:00-18:00 ET
and weekdays 01:00-01:30 ET (the PC-silent window takes over at 01:30). Weekday 01:00-01:30 ET is already inside the
current cron (`7,37 5-21 * * 1-5` UTC). Sunday is not. Add one line under `schedule:` in `.github/workflows/pc-watch.yml`
on BOTH `main` and `pc`:

```diff
   schedule:
     - cron: "7,37 5-21 * * 1-5"
+    - cron: "7,37 21-22 * * 0"       # Sunday 21:07-22:37 UTC = 16:07-17:37 ET in winter (EST), 17:07-18:37 ET in summer (EDT):
+                                     # the pre-open push (Sunday 17:00-18:00 ET, tools/pc_silent_check.preopen_step); others exit in seconds
```

Cost: +4 runs a week (~4 billed minutes). No other change needed: run() already sends the pre-open push with the same
destination (LE_NTFY_TOPIC / the status topic) and alert bus.

## B. Jarvis: read the 7-day clock

The NQ page sets `window.NQ_K7 = {t, rows: [{id, name, last_fill, mffu_last_day, days_left, sessions_left, keepalive, level}]}`
(tools/web_public/nq/clock7.js `jarvis()`). Any page with a PC post can build the same rows without the NQ page:

```js
import * as K7 from '../nq/clock7.js?v=1';
const rows = K7.jarvis(K7.rows(lite /* PC_FEED.fetchLatest() */, Date.now() / 1000));
```

The PC post also carries the ext block `k7` (`{a: [{id, nm, lf, base, dl, hard, left, ses, act, on, lvl}]}`); pc_feed.js
already lays it on top (`lite.k7`), so no pc_feed change. If Jarvis has a status line, one entry is enough:
`rows.find(r => r.level !== 'ok')` -> "Zlarior 50K: MFFU last day Mon 11/23 (1 session left)". jarvis/apps.js is yours.

## C. Owner to-do candidates (STATE.md 'Waiting on the owner')

1. **Zlarior 50K must have a FILLED trade by Mon 11-23** (last fill Mon 11-16). Monday is the only session left. If the PC is
   still off: turn it on Sunday before 18:00 ET. The bot trades as usual. If it has no fill by ~15:30 ET Monday, place 1 MNQ
   by hand while every account is flat, or switch on the keep-alive (KEEPALIVE_ON.bat). The 25K #2 is next (Tue 11-24, no
   fill yet).
2. **Likely cause of the silent weekends:** scripts/schedule_pc.ps1's `LiquidityEngineSleep` hibernates the PC Mon-Fri at 16:35
   ET, Friday included. Its wake task runs Mon-Fri 01:30 ET only, so nothing wakes the PC for Sunday's 18:00 open. One time,
   in an Administrator window: `python -X utf8 tools\pc_always_on.py --check`, then `--apply`
   (docs/PC_ALWAYS_ON.md). That sets never-sleep on AC and says to remove the hibernate task
   (`powershell -File scripts\schedule_pc.ps1 -Uninstall`), or to keep it with `--keep-hibernation` (which adds Sunday 17:30 /
   daily 01:15 ET wake tasks).
3. Optional: auto-login (netplwiz) and the BIOS "restore on AC power loss" setting. Both are guidance only, in
   docs/PC_ALWAYS_ON.md.

## D. What is in the branch

| File | What |
|---|---|
| engine/clock7.py (new) | MFFU 7-day clock per account: last fill (mf lt + keep-alive block), MFFU last day = base + 7, sessions left, ok / warn / bad |
| engine/preflight.py (new) | ONE "Ready for Sunday's open" or the exact first fix: server / bot / heartbeat, NinjaTrader, feed, each account's arm state, the clock, Tier-1 news. `python -X utf8 -m engine.preflight [--send]` |
| engine/ops_checks.py | due()["preflight"] = Sunday 17:30-18:15 ET -> preflight.notice (key ops:sun:<day>, once). The weekday pre-session notice (01:40 ET) gets the clock's amber / red line. The existing windows are unchanged (dst / holiday tests green) |
| tools/pc_report.py | ext block `k7` after `mf` (no "t", so ext_hash does not move every run). Cut: act / dl first |
| tools/pc_silent_check.py | preopen_step + feed_clock (the clock from the newest ext post on the status topic), wired into run() |
| tools/web_public/nq/clock7.js (new), nq.js r31, index.html, nqdesk.css v11 (+ trading/index.html's link) | the "7-day clock" card under Accounts + window.NQ_K7 |
| tools/pc_always_on.py, docs/PC_ALWAYS_ON.md, tests/test_pc_always_on.py (new) | the owner's one-time power hardening (dry run default, --check, --apply; auto-login / BIOS guidance only) |
| tests/test_nqops.py (new), tests/run_area.py (pc area: nqops, pc_always_on) | 32 checks |

Not covered: `--check` and `--apply` of tools/pc_always_on.py have never run on a real Windows PC. The Linux tests cover the
plan, the time conversion and a fake PC.
