# Running everything with your PC off

Three things need to keep going when the PC is off. Each one runs somewhere else:

| What | Where it runs | Status |
|---|---|---|
| **Live trading on the MFFU eval** | TradingView's servers → bridge (TradersPost or PickMyTrade) → Tradovate/MFFU | Strategy is loaded in the TradingView layout "Liquidity Engine Bot" (MNQ1! 5m). You still need to subscribe to a bridge, connect MFFU, and create the one alert. |
| **Dashboard + paper bot (monitoring, memory, learning)** | A small always-on cloud server (Render, Docker) | Repo is ready (`Dockerfile`, `render.yaml`). You create the Render account and set the password. |
| **Working on the bot with Claude** | Claude Code on the web / phone (claude.ai/code) using the private GitHub repo | Repo is on GitHub (private). Open it from claude.ai/code on any device. |

---

## 1. Live trading (TradingView → bridge → MFFU)

Full detail: `tradingview/BRIDGE_SETUP.md`. Short version:

1. **Bridge:** sign up for TradersPost or PickMyTrade. Connect your Tradovate/MFFU account inside the bridge (their OAuth screen, your login). Start in the bridge's **paper** mode.
2. **TradingView:** open the layout **Liquidity Engine Bot** (MNQ1!, 5m, ETH). The strategy "Liquidity Engine - Sweep IFVG DOL" is on the chart.
3. **The one alert:** Alerts → Create alert → Condition: the strategy → "Order fills only".
   - Message: `{{strategy.order.alert_message}}`
   - Notifications: Webhook URL = the URL the bridge gives you, plus "Notify in app" so your phone buzzes.
   - Expiration: open-ended (Premium) or the longest your plan allows; set a reminder to renew.
4. TradingView alerts run on TradingView's servers: **your PC can be off.**
5. Paper first (bridge paper account) for a few days. Compare its fills with the dashboard's paper bot, then switch the bridge to MFFU.
6. **MFFU rules:** automation is allowed only with you supervising. Keep the TradingView and bridge apps on your phone, and know the kill switch: pause the alert in TradingView, or flatten and disable the strategy in the bridge.

## 2. Always-on dashboard + paper bot (Render)

The server has a **cloud mode** (`LE_CLOUD=1`):
- **Paper only.** Live arming, go-live, non-paper adapters and webhook tests are refused.
- **Password required.** It won't start without `LE_DASH_PASSWORD` (12+ characters). The browser asks for it, and any username works.
- **Paper bot starts itself** about 30 seconds after the server boots.

The server uses about 410–510 MB, so it needs a host with **more than 512 MB**. The free and 512 MB plans would hit out-of-memory restarts, and free plans also sleep.

**Option A: Railway (recommended, usage-based, about $5–10/month)**
1. railway.com → **Login with GitHub** → allow access to `nq-liquidity-engine` only.
2. New Project → Deploy from GitHub repo → `nq-liquidity-engine`. It builds from `Dockerfile`, with health check and restart settings from `railway.json`.
3. Service → **Variables**: add `LE_CLOUD = 1` and `LE_DASH_PASSWORD = <a long password you type yourself, used nowhere else>`.
4. Settings → Networking → **Generate Domain**. Open it on your phone, log in (any username plus that password), and add it to your home screen.
5. Optionally set a monthly usage limit under Account → Usage.

**Option B: Render ($25/month Standard, 2 GB)**
1. render.com → sign up with GitHub → New → **Blueprint** → pick the repo (reads `render.yaml`).
2. Type your `LE_DASH_PASSWORD` when asked, then deploy.

Either way, every `git push` to `main` redeploys automatically.

Notes:
- Cloud data is real CME futures history from the repo plus live Yahoo `NQ=F` polling. CFD data is never used.
- The trade memory database (`data/memory.db`) resets when the container is rebuilt. Your local PC copy stays the master.
- `/api/tv/webhook` keeps its own secret key and works in cloud mode, so TradingView can also send alerts to the cloud dashboard feed: Settings → TradingView hook → set the public base to your Render URL.

## 3. Working on the bot from anywhere (Claude)

- On your phone or another computer, open **claude.ai/code**, connect GitHub, pick `nq-liquidity-engine`, and start a session. Cloud sessions run with your PC off and push changes to the repo; Render redeploys the dashboard automatically.
- On this PC, `git pull` brings those changes down.

## 4. The PC (optional, when it's on)

- `scripts\install_autostart.ps1` starts the local server and paper bot at login and resumes after crashes or reboots (paper or demo only).
- `scripts\status.ps1` shows a health summary.

## Never

- No passwords, API keys or webhook URLs in the repo. `.gitignore` blocks `.env*`, `data/tv.json`, `data/tv_device.json` and the autostart and live state files.
- No CFD data (`data/_cfd_archive`, Dukascopy cache) in the repo or the cloud.
- Live eval orders never go through the cloud server; only TradingView → bridge.
