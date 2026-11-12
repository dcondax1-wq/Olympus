# Bots back without GitHub (2026-11-12)

## Your 3 steps
1. **New code on the PC.** Double-click `STOP_BOT.bat`. Put the new code zip (`OLYMPUS_BACKUP_...zip`) and its `.sha256.txt` in Downloads, open the zip, copy `UPDATE_FROM_ZIP.bat` into the bot folder and double-click it (type Y if it asks).
2. **Double-click `BOTS_BACK.bat`** in the bot folder. It brings the bots back on Sim / paper and ends with six lines. Note the phone alert topic it shows (like `nq-amber-falcon-river-7291`).
3. **iPhone:** install the free **ntfy** app, tap **+**, type that topic, tap **Subscribe**. A test push arrives.

| What | Result |
|---|---|
| Trading | unchanged, Sim / paper; a real account is never armed by BOTS_BACK |
| GitHub pushes | off (no more errors) |
| Phone pushes | back: trade opened / closed with $, FEED STALE, bot down, NinjaTrader closed |
| Site status | every 15 min from the PC (free ntfy.sh), once the site has the wiring below |

## Why
The GitHub account was suspended on 2026-11-08. The bots (LIT / ATLAS / BLITZ, paper / Sim through NinjaTrader 8 on the main PC)
never needed GitHub to trade. Everything around them did. This page lists every GitHub dependency in the PC path (read from the
code, not guessed) and the fix.

## What breaks without GitHub, and the fix
| Piece (file) | What it did with GitHub | Without GitHub | Fix |
|---|---|---|---|
| Heartbeat + bar push (`engine/heartbeat.py`, started by `scripts/run_bot.ps1` with `LE_HEARTBEAT=1`) | `git push` of `heartbeat.json` + `bars_1m/5m.csv.gz` to branch `heartbeat` every 5 min | push fails every 5 min, retries, logs "[heartbeat] push failed"; HEALTH_CHECK shows the heartbeat red; the site says "Last report from your PC: N days ago" | GitHub-free mode (file `%USERPROFILE%\.olympus\no_github`, `engine/nogithub.py`): same payload and bars written to `logs\pc_hb\` instead. BOTS_BACK.bat makes the file. Takes effect at the bot server's next start. |
| Phone live feed (`engine/live_publish.py`) | force-push `live.json` to branch `live` of the Pages repo every 60 s | push fails, backs off | off in GitHub-free mode. Replaced by `tools/pc_report.py`: the same live.json shape, cut to a small status, posted to a free ntfy.sh status topic every 15 min |
| Phone remote control (`engine/remote_ctl.py`, `LE_REMOTE=1`) | reads `control/command.json` on branch `control` | fetch fails | off in GitHub-free mode (no replacement: control the bot at the PC) |
| Auto-update (`engine/autoupdate.py`, run by `run_bot.ps1 --on-start` and daily) | fast-forward of `main` | fails | off in GitHub-free mode. Update with the code zip: `UPDATE_FROM_ZIP.bat` |
| UPDATE.bat (`engine.autoupdate --pull`) | `git pull` of main | "[FIX] The update did not go through" | use `UPDATE_FROM_ZIP.bat` (zip + .sha256.txt in Downloads) |
| START_BOT.bat (`engine/go.py`) | step 0 pulls main (`autoupdate.pull`), then asks for the live phrase | the pull fails softly ("Update skipped ... starting the version on this PC"); the rest works. It is the ARMING path (I ACCEPT LIVE RISK) | BOTS_BACK.bat does not use it: it starts the server the way UPDATE.bat does (`scripts\run_bot.ps1`) and resumes only a paper / Sim start you saved before. START_BOT.bat stays the owner's own path to arm the eval |
| Phone Web Push from the PC (`engine/push.py` `pc_sync`) | `git fetch` of branch `dashboard` for the phone subscriptions + the sealed key | fetch fails; it keeps the last good copy (`data/push_pc_sync.json`), so pushes may still go out to the old app, but no new phone can be added | ntfy.sh alerts from `tools/pc_report.py` (trade opened / closed, FEED STALE, bot down, NinjaTrader closed) to the free ntfy app |
| Cloud monitor (`tools/cloud_monitor.py`, `.github/workflows/cloud-monitor.yml`) | GitHub Actions every 15 min: paper ledger, phone pushes, site publish | does not run at all | `tools/pc_publish.py` (PUBLISH_NQ.bat) runs the same code on the PC; `tools/pc_report.py` sends the phone alerts |
| Site publish (Actions -> `nq-dashboard` GitHub Pages) | force-push of the built site | the github.io site is gone or frozen | `PUBLISH_NQ.bat` -> Netlify (about 20 deploys a month on the new free plan: daily) or a synced folder / own server; the 15-minute status comes from ntfy (no deploy needed) |
| Cloud-side alerts (`engine/alerts_plus.py` `cloud_ref`) | `git ls-remote origin` to see the cloud's rules | returns "GitHub unreachable", no change | nothing needed (soft); BOTS_BACK sets `credential.interactive=never` in this folder's git config so no GitHub sign-in window pops up |
| LIT learning pull (`engine/lit_learn.py pull`), live board CLI (`engine/live_board.py`) | `git fetch origin dashboard`, `git show origin/heartbeat` | only these manual commands fail | nothing needed (not on the trading path) |
| STATUS.bat (`scripts/pc_status.ps1`) | read `home.json` from github.io when the bot writes no local heartbeat | "could not read it" | reads `logs\pc_hb\heartbeat.json` in GitHub-free mode (already built in) |
| HEALTH_CHECK.bat (`engine/ops_checks.py`) | heartbeat line checks the GitHub push; internet probe includes github.com | heartbeat red | green again in GitHub-free mode (the local write counts as the push) |
| PUBLISH_NQ.bat / UPDATE_FROM_ZIP.bat / UNDO_UPDATE.bat | none | work | nothing |
| Telegram / Discord from the PC (`engine/alerts.py`, `data/alerts.json`) | none (direct to Telegram) | works if you filled it in Settings | nothing; BOTS_BACK says on or off |
| Trading itself (`engine/live.py`, `engine/ninjatrader.py`, `live_model*.json`) | none | works | nothing, never touched |

## What BOTS_BACK.bat does (one double-click, safe to repeat)
| Step | It does | It never does |
|---|---|---|
| 1 GitHub off | makes `%USERPROFILE%\.olympus\no_github`; sets `credential.interactive=never` in this folder's git config | delete anything, change `live_model*.json`, `engine\` or your settings |
| 2 NinjaTrader | checks it runs and LE_BarFeed's MNQ bars are fresh; opens NinjaTrader if it is closed; waits up to 5 minutes for the bars | log in for you, place an order |
| 3 Bot | starts the bot server hidden (`scripts\run_bot.ps1`, as UPDATE.bat) when it is not answering; resumes your last saved start only if it was paper / Sim | arm live, type the live phrase, restart a running bot |
| 4 Reporting | installs the 15-minute task `OlympusPCReport` (`tools\pc_report.py`): phone alerts + the site's status | use a paid service, put a key in the repo |
| 5 Card | prints six lines: bots, feed, last trade, drawdown left, reporting, next window | |

Undo: `UNDO_BOTS_BACK.bat` removes the report task, the `no_github` file and the git setting. Nothing else.

## Reporting without GitHub
| Channel | What | Cost / limit |
|---|---|---|
| ntfy.sh alert topic (yours, made on the PC, shown on the card, stored in `%USERPROFILE%\.olympus\ntfy.json`, never in the repo) | phone pushes: trade opened, trade closed with $ and R, FEED STALE, bot down, NinjaTrader closed, back to normal | free, no account; the ntfy iPhone app (free) |
| ntfy.sh status topic (`tools/web_public/status_feed.json`, public like the site) | every 15 min a small status in the live.json shape the site already reads (`kind: "le-live"`, `pc`, `pc_verdict`, `board.lit/atlas/blitz`, `accounts`) | free; ntfy keeps it 12 hours; under 4 KB a message |
| Netlify (`PUBLISH_NQ.bat`, existing) | the whole site | free plan about 20 deploys a month: daily |
</content>
</invoke>

## The site side (status in the shape the site already reads)
`tools/pc_report.py` builds the PC's live.json with the bot's own code (`engine/live_publish.build`, the file the phone used to read
from the GitHub `live` branch) and cuts it under 4 KB: `kind: "le-live"`, `lite: true`, `t` (the bot's heartbeat time, never "now"),
`pc`, `pc_verdict` (DOWN / FEED when the PC sees worse right now), `board.lit / atlas / blitz` (room, mll, balance, floor, today, window,
position), the last 3 trades, `accounts` (no trade lists), `reporter` (what the PC saw at `reporter.t`: server up, NinjaTrader, problems).
`tools/web_public/pc_feed.js` reads the newest one from ntfy and lays it over the site: `PC_FEED.toLive(lite, siteBoard)` for
`window.LIVE.j` (live.js / board.js), `PC_FEED.overlayHome(home, lite)` before `OLYMPUS_TRUTH.canonHome` (truth.js) for the apps.

### Wiring needed (the lead)
1. `tools/web_public/live.js` `fetchLive()`: first `const lj = window.PC_FEED && await PC_FEED.fetchLatest(); if (lj) return { j: PC_FEED.toLive(lj, (window.HOMEJ || {}).board), src: 'ntfy' };`, then the old GitHub API / raw (dead) as before; the chip text for src `ntfy`.
2. `tools/web_public/index.html`: `<script src="pc_feed.js"></script>` before `live.js`.
3. `sw.js`: `pc_feed.js` in the shell list, `status_feed.json` network-first; bump the cache.
4. Apps that read home.json: load `../pc_feed.js`, then `home = PC_FEED.overlayHome(home, await PC_FEED.fetchLatest())` before `canonHome` in `nq/nq.js:41`, `aegis/aegis.js:151`, `helios/helios.js:139`, `ergasterion/ergasterion.js:660`, `olympus/people-data.js:30`.
5. After the merge: `python tools/make_backup.py` (the zip for step 1 must hold BOTS_BACK.bat, scripts\bots_back.ps1, scripts\pc_report_task.ps1, tools\bots_back.py, tools\pc_report.py) and redeploy the site once so `status_feed.json` + `pc_feed.js` are live.
6. `docs/CLAUDE_REFERENCE.md` Infrastructure / One chat: BOTS_BACK.bat, `tools/pc_report.py` (task OlympusPCReport), the two ntfy topics, test `tests.test_bots_back` (added to `tests/run_area.py` area `pc`). `docs/NQ_BOT_BACK.md` could point here (its NQ-app sheet is generated by `tools/nq_howto_build.py`, so rebuild that with it).

## Honest limits
- **PC off = nothing.** No cloud fallback any more; ntfy keeps the last status 12 hours, then the site shows its last build's age.
- **The site shows the 15-minute status only after the wiring above and one site deploy.** Until then the phone pushes (ntfy app) work, the site still says "N days ago".
- **A bot server that was already running** before GitHub-free mode keeps trying GitHub (soft errors) until it restarts: STOP_BOT.bat, then BOTS_BACK.bat, when flat and the market is closed. BOTS_BACK never restarts a running bot.
- **A real account is never armed by BOTS_BACK.** If your last start was the eval, the bot stays stopped and the card says START_BOT.bat (you type the phrase). Your own earlier auto-resume opt-in still works as before when the server starts (same as UPDATE.bat).
- **ntfy.sh is public by topic name.** The status topic is in the site (the same numbers the site shows); anyone who knows it could also post a fake status. Your alert topic is only on the PC and your phone (about 36 bits, unguessable in practice); anyone who learns it can read or post to it. Paid ntfy plans can lock topics; not used (free only).
- **ntfy.sh free limits:** a daily message cap per IP (a few hundred); this uses about 100 a day (96 status + alerts). A 429 is logged and retried next run.
- **Not back:** phone remote control and the minute-by-minute Live View (both lived on GitHub). Updates come by zip (UPDATE_FROM_ZIP.bat), not git.
- **Still needs you at the PC:** NinjaTrader log-in, the LE_BarFeed chart if the bars are stale, arming a real account, and step 1 for every code update.

## Tests
`python -X utf8 -m tests.test_bots_back` (77 checks: static, the reporter with fake http, the paper-only resume, pwsh runs with a fake python, pc_feed.js + truth.js in node). Never run `tests.test_win_scripts` in the sandbox (it fills the disk).
