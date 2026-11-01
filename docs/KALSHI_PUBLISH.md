# Kalshi in Jarvis: how the Kalshi numbers reach the phone

The owner's Kalshi bot ("Kalshi Edge v2") trades **real money** 24/7 on an **Oracle Cloud VM** (Ubuntu,
`/home/ubuntu/kalshi`). It does not run on the Windows PC. Its own Claude chat, **"kalshi-server"**, also runs on that VM.
The phone side is built and live:
- the Jarvis Kalshi card;
- the Kalshi page `https://demetrades2000-coder.github.io/nq-dashboard/kalshi/`;
- answers to "how's kalshi".

All of them read one file: `kalshi.json` on the branch `main` of its own **public** repo
`demetrades2000-coder/kalshi-feed`. They read it from
`https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json`, with
`https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main` as the fallback. Until
that file exists, the page shows the owner's one connect step.

**Why its own repo (security review, 2026-11-01):** the server pushes with a deploy key that has write access. On
`nq-dashboard`, whose `main` is the Pages site, that key could rewrite the whole phone app; a compromised Kalshi server
could then replace `jarvis/index.html` and steal the owner's keys on the phone. On `kalshi-feed` it can only rewrite that
one JSON file.

Everything below is one file of Python, `tools/kalshi_kit/public/kalshi_status_vm.py`: stdlib only, read-only, imports
nothing from this repo or the bot. The site build copies `tools/kalshi_kit/public/` to `<site>/kalshi/`.
`engine/kalshi_publish.py` loads that same file, so the VM and the PC give the same JSON for the same input.

## 1. The way: the VM publishes by itself
**The owner's one step** (shown on the Kalshi page): open the kalshi-server chat in the Claude app and paste
"Set up Jarvis for my Kalshi bot by following https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md
(sha256 `<hex>`)".
- The hash pins the script. `python tools/kalshi_kit/print_sha.py` prints it with the whole paste line.
- `--live` also checks that the site serves that exact file.
- Give the owner the line outside the site, so a changed site can't change the hash.

The chat then follows `tools/kalshi_kit/public/SETUP.md`:
1. Fetch the script to `~/kalshi_jarvis/`. If the owner's message has a `sha256`, check it with `sha256sum -c` and
   stop on a mismatch.
2. Run it once (`--from-bot /home/ubuntu/kalshi --check`) and show the JSON.
3. Make a deploy key and show the owner only its public line. He makes the empty public repo `kalshi-feed` (no README,
   no license) and adds the key to THAT repo with write access.
4. Push once. The first push into the empty repo creates `main`. Errors end with the fix: repo missing, key not added, or
   key read-only.
5. Add one cron line: every minute, `flock`ed and nice'd, `--cron`. It pushes only when the numbers changed, plus once
   every 3 minutes so the phone knows it's alive.
6. Check the raw URL.

It works with the PC off. Nothing in `/home/ubuntu/kalshi` changes. Cron runs the local copy, which never updates itself.
An update is step 1 again, with a new hash from the owner.

**What it reads** (all read-only; never `.env`, `.env2`, `keys/`, `sniper.db` or the bot's modules; no Kalshi API call):

| kalshi.json | from |
|---|---|
| `name` | "Kalshi Edge v2" |
| `mode` | `autotrader_status.json` `mode` (`live`) |
| `running` | the trader's status is under 180 s old, there's no `paused.txt`, and `systemctl is-active kalshi-bot kalshi-trader kalshi-combo` are all active |
| `status` | in order: "Paused (until …)" (`paused.txt`); "Problem: …" / "Blocked: …" (the trader's own text, short and redacted); a service down; "No word from the trader for N min"; else "Trading · 3 live strategies · N open bets" |
| `balance` | `account_truth.json` `total` (cash + positions); else `cash`; else the trader's `balance` (cash only) |
| `today_pnl` / `week_pnl` / `total_pnl` | `SUM(orders.pnl)` over live filled graded rows of `trades.db`: since 00:00 ET, since Monday 00:00 ET (`--week rolling7` for 7 days), all time. That's the same basis as Discord `/money`. ET days come from a built-in DST rule, never "-5 hours" |
| `days` | the same sum per ET date of the order's `ts`, the last 120 days |
| `positions` | open bets: live, filled, `result IS NULL`, book not `exit`; `UP`/`DOWN` → `yes`/`no`, contracts, `avg_price`, value at cost, `closes` (no live price in the bot's files), `asset`, `strategy` (the book's name) |
| `trades` | the last 40 live filled orders, newest first; `exit`/`partial` → `sell`; `pnl` stays null while open; `asset`, `strategy` |
| `strategies` | one row per `book`: 15-min favourites, Late favourite (BTC hourly), Gold 5 PM first, then the rest; mode from `bot_settings.json` / `combo_settings.json` / `sniper_settings.json`; wins `pnl > 0.005`, losses `pnl < -0.005` |
| `equity` | `autotune_state.json` `eq_main` (24 h at 15-min steps, cash + open cost), then the balance now |
| titles | from the ticker, offline, e.g. "ETH up or down · 15 min to 12:15 PM ET Nov 1", "Bitcoin above $80,500 at 1 PM ET Oct 27" |

## 2. Fallback: the PC pulls over SSH
Use this until the VM pushes, or if the owner never adds the deploy key. Run it from this repo's folder on the PC:
```
python -m engine.kalshi_publish --ssh --check
python -m engine.kalshi_publish --ssh --once
```
- `--ssh` runs the same reader on the VM through the PC's own helper `srv.py`.
  - Run by hand, it finds the newest `%APPDATA%\Claude\scratch-workspaces\…\srv.py` that has
    `cloud_linux\deploy_to_oracle.py` beside it; `--vm-helper <path>` overrides that.
  - The task always gets the absolute path that `install_windows.ps1` picked once, at install time. It never searches
    again.
- The script travels inside one shell line (zlib + base64). Nothing is installed on the VM. It runs nice'd at most once a
  minute and prints its JSON between markers.
- The VM's address stays in `srv.py`, which reads it at run time. It's never copied, printed or logged; errors are
  IP-redacted.
- If `paramiko` lives in another Python, add `--vm-python <that python.exe>`.
- The PC pushes to `kalshi-feed` too: `feed_url()` takes this repo's owner and protocol, and `LE_KALSHI_REPO`
  overrides it. It uses the PC's own git login, the way `engine/live_publish` pushes `live.json` (orphan commit, the
  repo's credential settings, scratch dir `data/kalshi_pub.git`). The repo must exist first: SETUP.md step 3.
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
Every key is optional except `t`. `clean()` keeps only these keys, caps the lists and keeps the file under 200 KB. It
writes `"v": 1`, or `"v": 2` when `strategies` or `equity` is present. It also cleans what goes public:
- Credential-looking keys are dropped.
- Every free-text string goes through `public_text()`, which redacts links (a tunnel link carries its token), IP and
  e-mail addresses, local paths, PEM keys, UUIDs, long hex or token-like strings, and `NAME=value` / `Bearer` secrets.
  Plain sentences pass untouched.
- Tickers and `closes` must look like tickers and times: an odd ticker is redacted, an odd `closes` is dropped.

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
| `positions` (60) | `ticker`, `title`, `side` (`yes`/`no`), `contracts`, `avg_price`, `price` (0-1 $/contract), `value`, `pnl`, `closes` (ISO), and optionally `asset` (BTC, ETH, GOLD …) and `strategy` |
| `trades` (40, newest first) | `t`, `ticker`, `title`, `side`, `action` (`buy`/`sell`/`settled`), `contracts`, `price`, `pnl`, and optionally `asset` and `strategy` |
| `days` (120) | `["YYYY-MM-DD", dollars]` |
| `strategies` (10, v2) | `name`, `mode` (`live`/`paper`/`off`), `running`, `today_pnl`, `total_pnl`, `trades`, `wins`, `losses` |
| `equity` (500, v2) | `[unix, dollars]`, oldest first; longer lists are evenly downsampled, first and last kept |

## Rules
- **Read-only.** Never touch trading: no change to the bot, its settings, its services, cron jobs or keys. Paper or real
  money doesn't matter here: this only reads.
- **No secrets anywhere.** `kalshi-feed` and the site are public: only the numbers above go there. No VM address,
  tunnel URL, token or key in this repo, the public kit or any output.
- **The deploy key writes `kalshi-feed` only**, never `nq-dashboard` (the phone app's site). The script is pinned by its
  SHA-256 in the owner's paste line.
- Don't touch the NQ bot: its processes, settings and scheduled tasks stay as they are.

## Checks
- `python -X utf8 -m tests.test_kalshi_publish` runs 98 checks with temp folders and a mock Kalshi API on 127.0.0.1.
- `python tools/kalshi_kit/print_sha.py --live` prints the hash for the owner's paste line and checks it against the
  file the site serves.
- Live: open the raw URL above. The Jarvis Kalshi card shows the balance and today's P&L; the Kalshi page shows the
  strategies, open bets and last trades.
