# Running with your PC off ($0)

Everything here is free. No new accounts are needed except where marked optional.

| What | Where it runs with the PC off | Cost |
|---|---|---|
| **Paper bot + dashboard** | GitHub Actions job `cloud-monitor`, every 15 min during the killzones and half-hourly 08:00–16:25 ET on weekdays. It runs the same engine and defaults as the PC paper bot. | $0 (about 1,200–1,500 of the 2,000 free Actions minutes a month for private repos) |
| **Dashboard page** | The `dashboard` branch of your private repo: `README.md` with a chart, status, setups, pools, paper trades, eval tracker and feed health | $0 |
| **Phone alerts** (optional) | The same job sends sweeps, entries, exits and the end-of-day summary to Telegram or Discord | $0 |
| **Live trading** (when ready) | TradingView's servers: strategy "Liquidity Engine - Sweep IFVG DOL" on layout "Liquidity Engine Bot", then a bridge | TradingView is already paid. The bridge is a separate decision and is not set up. |
| **Chat with Claude** | Claude Code on the web / mobile app (claude.ai/code) | included in your Claude plan |

## Open the dashboard (phone)
GitHub app → repo **nq-liquidity-engine** → branch **dashboard** → `README.md`.
Or in a browser: `https://github.com/demetrades2000-coder/nq-liquidity-engine/blob/dashboard/README.md`

It updates itself on market days. Run it on demand: GitHub app → Actions → **cloud-monitor** → Run workflow.

## Turn on phone alerts (optional, 3 minutes)
1. In Telegram, message **@BotFather** → `/newbot` → copy the token. Message your new bot once.
2. Get your chat id: open `https://api.telegram.org/bot<token>/getUpdates` and read `"chat":{"id":...}`.
3. GitHub → repo → Settings → Secrets and variables → Actions → New repository secret: add `TG_TOKEN` (the token) and `TG_CHAT` (the chat id).
   Discord instead: add a `DISCORD_WEBHOOK` secret.

## Keep chatting with Claude when the PC is off
1. On your phone or any browser: **claude.ai/code** → connect GitHub → allow the **nq-liquidity-engine** repo → create the default environment.
2. Start a session on that repo, or ask this PC session to "continue in cloud".
   Cloud sessions work on the GitHub repo directly, and pushes to `main` reach the cloud monitor on its next run.
3. While the PC is on, Remote Control is also on for the main session, so you can type into it from the Claude app.

## When the PC is on (optional)
- The full interactive dashboard runs at `http://127.0.0.1:8766` under `scripts\run_bot.ps1`.
- `scripts\install_autostart.ps1` starts it at login and resumes the paper bot after a reboot.

## Notes
- **What it can and can't do:** the cloud monitor is a 15-minute check, not a second-by-second server. Paper trades are reconstructed from the bars each run, so no trade is lost between runs, but alerts can lag up to about 15 minutes. GitHub may delay scheduled runs at busy times.
- **Docker:** `Dockerfile` + `engine/cloud_guard.py` (password gate, paper only) remain for any future always-on host. Hosts with enough memory (more than 512 MB) currently cost money, so nothing is deployed there.
- **Never in the repo:** passwords, tokens, webhook URLs (secrets live in GitHub Secrets) and CFD data.
