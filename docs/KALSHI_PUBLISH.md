# Kalshi in Jarvis: how the Kalshi numbers reach the phone

The owner's Kalshi bot ("Kalshi Edge v2") trades **real money** 24/7 on an **Oracle Cloud VM** (Ubuntu,
`/home/ubuntu/kalshi`). It does not run on the Windows PC. Its own Claude chat, **"kalshi-server"**, also runs on that VM.
The phone side is built and live:
- the Jarvis Kalshi card;
- the Kalshi page `https://demetrades2000-coder.github.io/nq-dashboard/kalshi/`;
- answers to "how's kalshi".

All of them read one file: `kalshi.json` on the branch `kalshi` of the **public** repo `demetrades2000-coder/nq-dashboard`
(`https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/kalshi/kalshi.json`). Until that file exists, the
page shows the owner's one connect step.

Everything below is one file of Python, `tools/kalshi_kit/public/kalshi_status_vm.py`: stdlib only, read-only, imports
nothing from this repo or the bot. The site build copies `tools/kalshi_kit/public/` to `<site>/kalshi/`.
`engine/kalshi_publish.py` loads that same file, so the VM and the PC give the same JSON for the same input.

## 1. The way: the VM publishes by itself
**The owner's one step** (shown on the Kalshi page): open the kalshi-server chat in the Claude app and paste
"Set up Jarvis for my Kalshi bot by following https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md".

The chat then follows `tools/kalshi_kit/public/SETUP.md`:
1. Fetch the script to `~/kalshi_jarvis/`.
2. Run it once (`--from-bot /home/ubuntu/kalshi --check`) and show the JSON.
3. Make a deploy key and show the owner only its public line; he adds it to nq-dashboard with write access.
4. Push once.
5. Add one cron line: every minute, `flock`ed and nice'd, `--cron`. It pushes only when the numbers changed, plus once
   every 10 minutes so the phone knows it's alive.
6. Check the raw URL.

It works with the PC off. Nothing in `/home/ubuntu/kalshi` changes.

**What it reads** (all read-only; never `.env`, `.env2`, `keys/`, `sniper.db` or the bot's modules; no Kalshi API call):

| kalshi.json | from |
|---|---|
| `name` | "Kalshi Edge v2" |
| `mode` | `autotrader_status.json` `mode` (`live`) |
| `running` | the trader's status is under 180 s old, there's no `paused.txt`, and `systemctl is-active kalshi-bot kalshi-trader kalshi-combo` are all active |
| `status` | in order: "Paused (until …)" (`paused.txt`); the `problem` / `blocked` text; a service down; "No word from the trader for N min"; else "Trading · 3 live strategies · N open bets" |
| `balance` | `account_truth.json` `total` (cash + positions); else `cash`; else the trader's `balance` (cash only) |
| `today_pnl` / `week_pnl` / `total_pnl` | `SUM(orders.pnl)` over live filled graded rows of `trades.db`: since 00:00 ET, since Monday 00:00 ET (`--week rolling7` for 7 days), all time. That's the same basis as Discord `/money`. ET days come from a built-in DST rule, never "-5 hours" |
| `days` | the same sum per ET date of the order's `ts`, the last 120 days |
| `positions` | open bets: live, filled, `result IS NULL`, book not `exit`; `UP`/`DOWN` → `yes`/`no`, contracts, `avg_price`, value at cost, `closes` (no live price in the bot's files) |
| `trades` | the last 40 live filled orders, newest first; `exit`/`partial` → `sell`; `pnl` stays null while open |
| `strategies` | one row per `book`: 15-min favourites, Late favourite (BTC hourly), Gold 5 PM first, then the rest; mode from `bot_settings.json` / `combo_settings.json` / `sniper_settings.json`; wins `pnl > 0.005`, losses `pnl < -0.005` |
| `equity` | `autotune_state.json` `eq_main` (24 h at 15-min steps, cash + open cost), then the balance now |
| titles | from the ticker, offline, e.g. "ETH up or down · 15 min to 12:15 PM ET Nov 1", "Bitcoin above $80,500 at 1 PM ET Oct 27" |

## 2. Fallback: the PC pulls over SSH
Use this until the VM pushes, or if the owner never adds the deploy key. Run it from this repo's folder on the PC:
```
python -m engine.kalshi_publish --ssh --check
python -m engine.kalshi_publish --ssh --once
```
- `--ssh` runs the same reader on the VM through the PC's own helper `srv.py`. The helper is found under
  `%APPDATA%\Claude\scratch-workspaces\…\srv.py`, next to `cloud_linux\deploy_to_oracle.py`; `--vm-helper <path>`
  overrides it.
- The script travels inside one shell line (zlib + base64). Nothing is installed on the VM. It runs nice'd at most once a
  minute and prints its JSON between markers.
- The VM's address stays in `srv.py`, which reads it at run time. It's never copied, printed or logged; errors are
  IP-redacted.
- If `paramiko` lives in another Python, add `--vm-python <that python.exe>`.
- The PC pushes with the NQ bot's own route and git login (`engine/live_publish.push`, scratch dir
  `data/kalshi_pub.git`).
- To keep it running, run `powershell -ExecutionPolicy Bypass -File tools\kalshi_kit\install_windows.ps1`. It makes the
  Windows task "Kalshi to Jarvis": at logon, no window, restart on failure, `--ssh --loop`.
- It updates only while the PC is on. Remove the task once the VM pushes by itself:
  `schtasks /Delete /TN "Kalshi to Jarvis" /F`.

## 3. Other sources (same contract)
- `--src <file>`: a status file in the contract below, e.g. from another bot. `python -m engine.kalshi_publish --sample`
  prints an example.
- `--from-api`: **not recommended, off unless asked.** It reads the account with Kalshi's read-only endpoints (GET balance,
  positions, fills, settlements, `markets/{ticker}`), signed RSA-PSS or Ed25519.
  - Why not: the account already gets HTTP 429 on `/portfolio/balance` about 100 times a day from the bot's own
    pollers; the only key is the bot's trading key, which lives on the VM; and the API knows nothing of the bot's
    strategies.
  - Safety in code: GET only; allow-listed paths; Kalshi hosts only; no redirects; one round every 5 min; a 429 stops
    the round at once; the key id, key path and PEM are redacted everywhere.
  - Keys: `--key-id` / `--key-file`, or `KALSHI_API_KEY_ID` / `KALSHI_PRIVATE_KEY_PATH` (the bot's own names).

## The contract: kalshi.json
Every key is optional except `t`. `clean()` keeps only these keys and caps the lists. It drops credential-looking keys,
redacts local paths, and keeps the file under 200 KB. It writes `"v": 1`, or `"v": 2` when `strategies` or `equity` is
present.

| top level | meaning |
|---|---|
| `t` | unix seconds when the numbers were read (the phone shows "updated N min ago") |
| `running` | true / false / null |
| `mode` | `"live"`, `"paper"` or `"demo"` |
| `name`, `status`, `note` | short plain text |
| `balance` | account value in dollars |
| `today_pnl`, `week_pnl`, `total_pnl` | dollars; today = since 00:00 ET |

| list (cap) | row keys |
|---|---|
| `positions` (60) | `ticker`, `title`, `side` (`yes`/`no`), `contracts`, `avg_price`, `price` (0-1 $/contract), `value`, `pnl`, `closes` (ISO) |
| `trades` (40, newest first) | `t`, `ticker`, `title`, `side`, `action` (`buy`/`sell`/`settled`), `contracts`, `price`, `pnl` |
| `days` (120) | `["YYYY-MM-DD", dollars]` |
| `strategies` (10, v2) | `name`, `mode` (`live`/`paper`/`off`), `running`, `today_pnl`, `total_pnl`, `trades`, `wins`, `losses` |
| `equity` (500, v2) | `[unix, dollars]`, oldest first; longer lists are evenly downsampled, first and last kept |

## Rules
- **Read-only.** Never touch trading: no change to the bot, its settings, its services, cron jobs or keys. Paper or real
  money doesn't matter here: this only reads.
- **No secrets anywhere.** `nq-dashboard` is public: only the numbers above go there. No VM address, tunnel URL, token or
  key in this repo, the public kit or any output.
- Don't touch the NQ bot: its processes, settings and scheduled tasks stay as they are.

## Checks
- `python -X utf8 -m tests.test_kalshi_publish` runs 79 checks with temp folders and a mock Kalshi API on 127.0.0.1.
- Live: open the raw URL above. The Jarvis Kalshi card shows the balance and today's P&L; the Kalshi page shows the
  strategies, open bets and last trades.
