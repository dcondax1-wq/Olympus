# day-nqops 2026-11-21: LEAD_WIRES (only what a helper may not do)

Base: olympus/pc 7adf312d. All bot-side pieces are read-only notices (no order, arm or route code touched; engine/live.py,
lit_live.py, notify.py, server.py, scripts/*.ps1, *.bat untouched).

## A. pc-watch.yml: add the Sunday runs (the workflow lives on `main` AND `pc`: lead only)

tools/pc_silent_check.py sends ONE Sunday 17:00-18:00 ET message when the PC is silent. The weekend hibernation (schedule_pc.ps1 Fri
16:35 -> Mon 01:30 ET) is by design: no live lane enters before 02:00 ET, and tests/test_nqops `lanes` guards that. So the message is a
quiet note ("PC is off: asleep until the Mon 01:30 ET wake (as scheduled)", priority low) unless a 7-day clock is red. Then it is ONE
loud push saying exactly what to do. The weekday 01:00-01:30 ET window was dropped: the PC is asleep then by design, and the PC-silent
check covers a missed wake from 01:30 + 20 min. Sunday needs one cron line in `.github/workflows/pc-watch.yml` on BOTH `main` and `pc`:

```diff
   schedule:
     - cron: "7,37 5-21 * * 1-5"
+    - cron: "7,37 21-22 * * 0"       # Sunday 21:07-22:37 UTC = 16:07-17:37 ET in winter (EST), 17:07-18:37 ET in summer (EDT):
+                                     # the Sunday note / red-clock push (17:00-18:00 ET, tools/pc_silent_check.preopen_step); others exit in seconds
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
2. **Weekend silence is by design** (schedule_pc.ps1 hibernates Fri 16:35 ET and wakes Mon 01:30 ET; nothing trades before 02:00 ET).
   The real risk is a missed Monday wake. One time, in an Administrator window: `python -X utf8 tools\pc_always_on.py --check`, then
   `--apply`. That sets wake timers on and, when the hibernate task exists, adds a weekday 01:15 ET second-chance wake. It never
   removes the hibernation. Monday ~02:00 ET: the phone shows "Ready for the week" (01:35 ET) or the fix.
3. Optional: auto-login (netplwiz) and the BIOS "restore on AC power loss" setting. Both are guidance only, in
   docs/PC_ALWAYS_ON.md.

## D. What is in the branch

| File | What |
|---|---|
| engine/clock7.py (new) | MFFU 7-day clock per account: last fill (mf lt + keep-alive block), MFFU last day = base + 7, sessions left, ok / warn / bad |
| engine/preflight.py (new) | ONE "Ready for Sunday's open" or the exact first fix: server / bot / heartbeat, NinjaTrader, feed, each account's arm state, the clock, Tier-1 news. `python -X utf8 -m engine.preflight [--send]` |
| engine/ops_checks.py | due()["preflight"] = Monday 01:35-01:50 ET (just after the 01:30 wake) -> preflight.notice with the pre-session's key ops:pre:<day>, so Monday gets ONE push. The Tue-Fri pre-session notice (01:40 ET) gets the clock's amber / red line. The existing windows are unchanged (dst / holiday tests green) |
| tools/pc_report.py | ext block `k7` after `mf` (no "t", so ext_hash does not move every run). Cut: act / dl first |
| tools/pc_silent_check.py | preopen_step (Sunday only: quiet note, or a loud push for a red clock) + feed_clock (the clock from the newest ext post on the status topic), wired into run(); SUNDAY_EVENING_LANES = () |
| tools/web_public/nq/clock7.js (new), nq.js r31, index.html, nqdesk.css v11 (+ trading/index.html's link) | the "7-day clock" card under Accounts + window.NQ_K7 |
| tools/pc_always_on.py, docs/PC_ALWAYS_ON.md, tests/test_pc_always_on.py (new) | the owner's one-time power hardening (dry run default, --check, --apply; auto-login / BIOS guidance only). Hibernation by design: --check wants the 01:30 ET wake task + wake timers, never says to remove the hibernation; --keep-hibernation adds only the weekday 01:15 ET second-chance wake |
| tests/test_nqops.py (new), tests/run_area.py (pc area: nqops, pc_always_on) | 32 checks |

Not covered: `--check` and `--apply` of tools/pc_always_on.py have never run on a real Windows PC. The Linux tests cover the
plan, the time conversion and a fake PC.
