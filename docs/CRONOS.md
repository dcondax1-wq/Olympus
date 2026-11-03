# CRONOS: the nightly refresh that keeps OLYMPUS alive

Before CRONOS, the research apps (Data City, FATES, ODEON, DAPHNE, PROMETHEUS; PANTHEON since 2026-11-03) only changed when someone reran them by
hand, so their Jarvis cards went grey. CRONOS reruns them on a schedule, for free, and makes every card say honestly how
fresh it is. Research and paper only: it never touches trading logic, `live_model*.json` or an order.

## What refreshes when

| App | What runs | When (ET) | Skips when | Timeout | Card goes amber after |
|---|---|---|---|---|---|
| Data City | PC's new 5m bars appended, ~67k combinations re-scored (`datacity.yml`) | Mon-Fri nights, 22:37 (winter) / 23:37 (summer) | never | 20 min | 36 weekday hours |
| FATES | 1,000 futures of today's evals from the latest `live.json` state | Mon-Fri nights, 23:07 / 00:07 | Actions saver mode | 15 min | 36 weekday hours |
| ODEON | the replay reels, with the PC's NinjaTrader bars (heartbeat branch) + the paper ledger | Mon-Fri nights, with FATES | no new PC bars since the last run | 5 min | 36 weekday hours |
| PANTHEON | the eight free data gods re-read (FRED, CBOE, CFTC, SqueezeMetrics, US Treasury, the calendar: key-less public files), the council verdict, `states.json` for Data City (`docs/PANTHEON.md`) | Mon-Fri nights, with FATES | never (light: also in saver mode) | 8 min | 36 weekday hours |
| HERMES | OLYMPUS Wrapped | inside every site publish | never | - | (always fresh: rebuilt each publish) |
| DAPHNE (tree) | the strategy-tree search | Sundays 14:17 / 15:17 | its data or code did not change; saver mode | 30 min | a week + 36 h (156 weekday hours) |
| PROMETHEUS | the LIT evolution forge | Sundays, with DAPHNE | its data, LIT or code did not change; saver mode | 30 min | 156 weekday hours |

Weekday hours: weekends do not count, because the nightly jobs do not run on weekends by design (Friday night's data is still
fresh on Monday morning).

## How the data reaches the site

1. `.github/workflows/cronos.yml` runs `python -X utf8 -m tools.cronos --group nightly|weekly --out pub`. Each task runs in
   its own process with its own timeout. Its files only replace the last good ones when they are complete, valid JSON and
   the card passes the Jarvis contract; a failure keeps yesterday's data and is written to `cronos/status.json`.
2. The workflow force-pushes `pub` as one commit to the `cronos` branch (Data City does the same on `datacity`). Main
   never gets bot commits; no secrets are added (the workflow's own `GITHUB_TOKEN`).
3. At every site publish (the cloud monitor, `tools/build_web_dashboard.py`), `tools/cronos/site.py` fetches both
   branches and copies each app's files in when they are newer than the page's own copy (all of an app's files or none).
   A missing branch is skipped; any error is printed and the publish carries on.
4. Then every research app's `jarvis.json` is stamped with the publish time and its freshness:
   - **fresh**: the engine's own status, plus "Updated nightly · last run Tue Nov 3, 23:07 ET";
   - **stale** (older than its limit) or **failed** (the last run failed): amber, "Not updated since Tue Nov 3", the reason,
     and the last numbers labelled as the last status. Never fake-fresh.

The nightly results reach the phone at the next monitor publish (01:30 ET on weekdays); the Sunday results at the
Sunday 17:47 ET publish. Between publishes Jarvis still greys every card after 30 minutes (its own rule in
`tools/web_public/jarvis/apps.js`), so overnight and on Saturdays all cards look grey until the next publish.

## Minutes budget (private repo: 2,000 free minutes a month)

Estimated on a 2-core GitHub runner, each job rounded up to the minute; ~22 weeknights and ~4.35 Sundays a month.

| Job | Per run | Runs a month | Minutes a month |
|---|---|---|---|
| CRONOS nightly (setup 1.5 + FATES 5.5 + ODEON 0.5 + PANTHEON 1) | ~8.5 | 22 | ~187 |
| CRONOS weekly, nothing changed (setup + two quick checks) | ~2 | 4.35 | ~9 |
| CRONOS weekly, data changed (setup + DAPHNE 11 + PROMETHEUS 9) | ~21.5 | at most 4.35 | at most ~94 |
| **CRONOS total** | | | **~196, at most ~281** |
| Data City (`datacity.yml`) | ~3 | 22 | ~66 |
| Cloud monitor + watcher (measured Oct 27-31: 219 min in 5 weekdays) | | | ~960 (cap ~1,850) |
| **All workflows** | | | **~1,200-1,300 of 2,000** |

Guard: when the monitor's `budget.json` (dashboard branch) says "saver" this month, CRONOS skips FATES, DAPHNE and PROMETHEUS
(their cards go amber after their limit, honestly) and keeps the cheap ODEON and PANTHEON.

## Commands

- `python -X utf8 -m tools.cronos --list`: the registry (cadence, timeout, max age, minutes).
- `python -X utf8 -m tools.cronos --task fates --out <dir>`: one task (`--force` to rebuild even when nothing new came in).
- `python -X utf8 -m tests.test_cronos` (`--quick` skips the two site builds and the real ODEON export).
- Manual run on GitHub: Actions -> cronos -> Run workflow (group, tasks, force).
