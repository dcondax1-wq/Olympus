# Live dashboard on the iPhone (2026-11-12)

## Your 3 steps
1. **On the PC** double-click `LIVE_LINK.bat` in the bot folder. If it opens a Tailscale page, do what the page says (install, sign in, or click **Enable HTTPS**), then double-click `LIVE_LINK.bat` again. It ends with your link, like `https://your-pc.tail1234.ts.net/`.
2. **On the iPhone** install the free **Tailscale** app from the App Store, sign in with the **same** account, allow the VPN.
3. **In Safari** on the iPhone open that link, tap **Share**, then **Add to Home Screen**.

| What | Result |
|---|---|
| One link, one home-screen icon | the Gate, the full dashboard, every OLYMPUS app, all served by the bot server on your PC |
| Bot numbers (bots on / off, drawdown left, today's $, open trade) | live from the running bot, at most 15 seconds old; the Gate refreshes every minute |
| Every app that reads home.json (NQ, Aegis, Helios, ...) | the same live numbers (the PC lays them over home.json) |
| The rest of the site (research, charts, data.json) | rebuilt on the PC every 15 minutes |
| Kalshi | shown when the VM's feed reaches the PC (see below) |
| Money pages | the money machines' newest output on the PC (RUN_MONEY.bat), else the sample |
| Trading | unchanged. Read only over the link: nothing on the phone can start, stop or arm a bot |
| Cost | free (Tailscale personal plan, your own PC) |

## What LIVE_LINK.bat does (safe to run again)
| Step | It does | It never does |
|---|---|---|
| 1 App | checks Tailscale for Windows is installed; if not, opens its download page | install anything by itself |
| 2 Sign in | checks Tailscale is signed in and connected; if not, starts it and opens the sign-in page, waits up to 5 minutes | log out, change your Tailscale settings |
| 3 Link | `tailscale serve --bg --yes http://127.0.0.1:8766`: the https address of this PC inside your tailnet; HTTPS off in the tailnet: opens the admin page (one click) | turn on Funnel (the public internet); a Funnel found on that address is switched off |
| 4 Server | checks the bot server answers and serves the phone site | start, stop or restart the bot |
| 5 Site | keeps the site fresh every 15 minutes: PUBLISH_NQ's task when you have it, else its own build-only task `OlympusLiveSite` (builds on this PC, sends nothing anywhere) | publish to Netlify or anywhere else |
| Card | prints the link, puts it on the PC's clipboard, saves it in `%USERPROFILE%\.olympus\live_link.json` | |

Undo: `UNDO_LIVE_LINK.bat` turns the link off (only if it points at the bot server) and removes `OlympusLiveSite`. Tailscale stays installed and signed in.

## Security
- **Tailnet only.** `tailscale serve` (not Funnel) makes the link reachable only from devices signed in to **your** Tailscale account. Nobody on the internet can open it. LIVE_LINK.bat never turns Funnel on, switches it off on that address, and the bot server refuses any request that comes through Funnel.
- **Read only over the link.** Every request through the link carries Tailscale's proxy headers. The bot server (`engine/live_site.py`) lets those requests only read (GET / HEAD). Every POST is refused before it reaches the bot: start, stop, kill, arm, go live, settings, account changes. The page that shows the TradingView webhook key is hidden too. Arming and real-account starts were already PC-only (`engine/cloud_guard.local_only`); that did not change.
- **The PC itself is unchanged.** `http://localhost:8766` on the PC is the same Command Center with every button.
- **No secrets.** No key or token is stored in the repo or sent anywhere. Tailscale's sign-in is between you and Tailscale. The link address names your PC and your tailnet; it is not a password and opens nothing without your Tailscale sign-in.
- **Encrypted.** The phone talks to the PC over Tailscale's WireGuard tunnel and https with a real certificate.

## Kalshi
The Kalshi bot runs on the VM. Its status reaches the phone link when the PC has it:
- the VM's kit puts `kalshi.json` in `%USERPROFILE%\.olympus\kalshi_feed\` (a synced folder), or `publish.json` has `kalshi_file`, or
- the VM publishes the feed at an https address: run `LIVE_LINK.bat -KalshiUrl https://<the feed address>/kalshi.json` once.

The PC reads it fresh (the address at most once a minute) and serves it as `kalshi.json` to the Kalshi apps.

## How it is built (for Claude)
| Piece | File | Notes |
|---|---|---|
| The phone site and the live numbers | `engine/live_site.py`, installed by `server.py` before its static mount | `/site/...` = the newest of `data/pc_publish/site` (PUBLISH_NQ) and `data/live_site/site` (OlympusLiveSite), a missing file falls back to `tools/web_public`; `/site/home.json` = built home.json + the bot's live.json (`overlay_home`, the Python twin of `pc_feed.js overlayHome`, parity-tested in node); `/site/kalshi.json`; `/site/money/*.json` from `money_out/`; `GET /api/site/live.json` (`LIVEPUB.payload()`, cached 15 s); `GET /api/site/status`; a proxied `/` goes to `/site/gate/` |
| Read-only guard | `engine/live_site.guard` | proxied = any of X-Forwarded-For / -Host / -Proto, Tailscale-User-Login, Tailscale-Funnel-Request ...; proxied and not GET / HEAD / OPTIONS = 403; Funnel = 403; `/api/tv/status` hidden |
| The Gate's live card | `tools/web_public/gate/gate.js` (v=g2), `gate/index.html` loads `../pc_feed.js` | only when the page path starts with `/site/` |
| The one double-click | `LIVE_LINK.bat`, `UNDO_LIVE_LINK.bat`, `scripts/live_link.ps1` | CLI syntax checked against the Tailscale v1.104.7 source (`tailscale serve --bg --yes <target>`, `serve status --json`, `serve --https=443 off`, bare `tailscale up`) |
| Tests | `tests/test_live_link.py` | guard, site, live + node parity, feeds, the real server.py in a child process, static, pwsh with a fake tailscale, the Gate in node, Chromium through a fake link (under `/tmp/olympus_browser.lock`) |

## Honest limits
- **PC off or asleep = no link.** The phone shows "can't connect". The ntfy pushes and the 15-minute ntfy status from BOTS_BACK.bat cover alerts, not the dashboard.
- **The bot server must run this code.** A server started before this update has no `/site/`: LIVE_LINK says "older code"; restart it once when flat and the market is closed (STOP_BOT.bat, then BOTS_BACK.bat).
- **The first full site takes a few minutes** after LIVE_LINK.bat (the build runs in the background). Until then the Gate and the apps open from the unbuilt files and the bot numbers are already live.
- **Tailscale must be on** on the iPhone (the VPN switch in its app) for the link to open.
- **The phone link is read only on purpose.** Start, stop and the kill switch stay at the PC (`http://localhost:8766`).
- **The PC's plain address `http://<PC's Tailscale IP>:8766`** (the old "Open on your phone" path, any device on your Wi-Fi or tailnet) is unchanged and keeps the PC dashboard's own rules; the https link above is the read-only one to use.
- **Kalshi** shows only after the VM's feed reaches the PC; nothing is invented when it does not.
- **The phone's Add to Home Screen icon** belongs to the link: if you rename the PC in Tailscale, run LIVE_LINK.bat again and add the new link.
