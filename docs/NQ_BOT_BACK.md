# NQ bots, reporting without GitHub (2026-11-11)

The bots (LIT / ATLAS / BLITZ) never needed GitHub to trade. Only their reporting did. This puts the reporting on your main PC.

| What | Result |
|---|---|
| Trading | Unchanged. Same rules, same files, same orders. Paper / Sim only here. |
| Reporting | The PC builds the site every 15 minutes and sends it out (Netlify, or a folder). |
| Check-ins to GitHub | Off (bot writes its status to its own folder instead). |

## Do this (5 steps, once)
1. **Update the bot folder from the zip.** Stop the bot (STOP_BOT.bat). Put the code zip and its `.sha256.txt` in Downloads on the PC, open the zip, copy `UPDATE_FROM_ZIP.bat` into the bot folder and double-click it.
   It checks the zip, keeps your settings and every local file, and shows six lines. Best time: 17:00-18:00 ET or the weekend.
2. **Make a free Netlify site and a token.** Site: app.netlify.com/drop, drop any file, note the **Site ID** (Site configuration, "Site ID").
   Token: Netlify > your avatar > User settings > Applications > Personal access tokens > New access token > copy it.
3. **Save both on the PC.** In the bot folder, one line, then paste the token and press Enter (it is typed hidden, never shown or uploaded):
   `python tools\pc_publish.py --setup netlify --site-id YOUR_SITE_ID --token-stdin`
4. **Double-click `PUBLISH_NQ.bat`.** It sets up the 15-minute task, switches the bot to GitHub-free mode and publishes once.
5. **Start the bot again.** Double-click `START_BOT.bat` while the market is closed. `STATUS.bat` any time shows the last publish.

Undo: `UNDO_UPDATE.bat` puts the old files back; `UNDO_PUBLISH_NQ.bat` removes the publish task.

Notes: the token goes to `%USERPROFILE%\.olympus\netlify.json`, outside the repo. No Netlify? In step 3 use `--setup folder --folder "C:\path\to\a synced folder"` instead.
On the phone, the **NQ** app shows each bot's status with the exact age of the last report, and these same five steps.

## Updating the bot later (no GitHub)
`git pull` and UPDATE.bat no longer work (the account is gone). Every update is step 1 again: the new zip in Downloads, double-click `UPDATE_FROM_ZIP.bat`.
| It does | It never does |
|---|---|
| Checks the zip's SHA-256 against the `.sha256.txt` next to it | Run while the bot is running (it says: stop the bot first) |
| Asks before updating while the market is open | Overwrite local-only files: alerts, TradingView, autostart, bot state, memory, `.env`, NinjaTrader bars, logs |
| Saves the old files in `backups\update_from_zip\` first | Replace a `live_model*.json` you changed: yours is kept and it says so |
| Shows six lines: zip, folder, changed, kept, backup, next | Start, stop or arm the bot, or delete a file |

## What runs where
| Piece | Where | Needs |
|---|---|---|
| Bot + NinjaTrader | main PC | nothing from GitHub |
| Bot status | `logs\pc_hb\` on the PC | nothing |
| `tools\pc_publish.py` (task `OlympusPublishNQ`, every 15 min) | main PC | Python, internet |
| The site | Netlify (or your folder) | your token |
| Kalshi bot feed | Oracle VM | see below |

## If the PC is off
Nothing is built or published, and the bots do not trade either (they live on the PC). The phone keeps showing the **last good site** (the old numbers, with their age). There is no cloud fallback any more: the GitHub Actions monitor is gone.

## Honest limits
- **Netlify's new free plan allows about 20 deploys a month** (each costs 15 of 300 credits; at zero the site pauses). So the publisher keeps a budget: at most **1 a day, 18 a month** by default, and says so on its status line. 15-minute freshness on the phone is therefore **not** possible on Netlify's new free plan. Older Netlify accounts have no such cap: raise `max_deploys_per_month` in `publish.json`. For fresher numbers use `--setup scp` to your own Oracle VM (docs/HOSTING_OPTIONS.md), or keep Netlify for a daily page.
- Check your real limit at app.netlify.com > Usage (the price page can change).
- The phone live view (minute-by-minute) and phone remote control used GitHub; they are **off**. Phone alerts from the cloud monitor are gone; PC-side alerts still work.
- Auto-update of the bot from GitHub is off: update with the zip and `UPDATE_FROM_ZIP.bat` (step 1).
- Your on-phone data (Ledger, journal) stays in the browser of the old address; a new address starts empty, so export first.

## Kalshi bot feed (Oracle VM)
The VM's `kalshi_status_vm.py` now publishes without GitHub: `--publish folder --publish-dir DIR`, `--publish netlify` (its own small Netlify site; id and token in `~/.olympus/netlify.json` on the VM, paced to 1 an hour), or `--publish scp --publish-dir user@host:/path`. The same redaction applies (only the contract's keys, free text cleaned). Easiest path: the VM writes a folder the PC can read, then in `%USERPROFILE%\.olympus\publish.json` set `"kalshi_file": "<that path>"` or `"kalshi_feed_url": "https://<feed-site>/kalshi.json"`; the PC puts it in the site as `kalshi.json`.
Every Kalshi page (Jarvis, Hermes, Tyche, Ledger, Stoa, Inbox, Dionysus, Ergasterion, Kalshi City, Cities, the Kalshi page) now reads the site's own `kalshi.json` first and the old GitHub address only as a fallback. A `kalshi.json` that the VM kit left in `%USERPROFILE%\.olympus\kalshi_feed\` goes into the site with no setting.
The Kalshi setup message says `{SITE_URL}`, which the page fills from its own address.

More hosts and what each needs: `docs/HOSTING_OPTIONS.md` (best for 15-minute updates: your own Oracle VM with `--setup scp`, no deploy limit).
