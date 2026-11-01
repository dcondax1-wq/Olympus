# Kalshi to Jarvis

This kit puts the owner's Kalshi bot numbers on his phone (Jarvis), read-only. The bot ("Kalshi Edge v2") trades real
money on its own cloud server, and its Claude chat "kalshi-server" runs there too. The numbers go to their own public repo,
`demetrades2000-coder/kalshi-feed`. The phone reads `https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json`.
The full picture is in `docs/KALSHI_PUBLISH.md`.

## 3 steps
1. **Owner:** in the Claude app, open the kalshi-server chat and paste the line from `python tools/kalshi_kit/print_sha.py`:
   `Set up Jarvis for my Kalshi bot by following https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md (sha256 <hex>)`
2. **The chat** follows `public/SETUP.md`. It fetches `kalshi_status_vm.py`, checks the hash, shows the JSON that will be
   public, and shows the owner one public deploy-key line.
   **Owner:** on GitHub, make the empty public repo `kalshi-feed` and add that key to it (Settings → Deploy keys, tick
   **Allow write access**), then reply OK.
3. **The chat** pushes once, adds one cron line (every minute, a push only when the numbers change), and checks the raw
   address. Jarvis shows the Kalshi card and page within a few minutes.

## Files
| file | what |
|---|---|
| `public/kalshi_status_vm.py` | The one script: Python 3.9+, standard library only. `--from-bot DIR` reads the bot's files (`trades.db` read-only, the status / settings JSON); `--cron`, `--once`, `--loop` and `--check` run it. The site build copies `public/` to `<site>/kalshi/`. |
| `public/SETUP.md` | The steps the kalshi-server chat follows on the server. |
| `print_sha.py` | The script's SHA-256 and the owner's paste line; `--live` compares it with the file the site serves. Run it on the merged main, after the site publishes. |
| `install_windows.ps1` | The PC fallback until the server pushes: the task "Kalshi to Jarvis" (`engine.kalshi_publish --ssh --loop`), with the PC's own `srv.py` picked once, at install time. |
| `../../engine/kalshi_publish.py` | The PC side. It loads `public/kalshi_status_vm.py`, so both give the same JSON, and pushes to `kalshi-feed` too. |

## Safety
- It never trades and never changes the bot. It only reads the bot's files: never `.env`, `keys/` or `sniper.db`, and it
  makes no Kalshi API call. It runs nice'd, at most once a minute.
- **Its own repo.** The deploy key can write only `kalshi-feed`, never the phone app's site (`nq-dashboard`). A
  compromised server could change the numbers, not the app.
- **A pinned script.** The owner's paste line carries the script's SHA-256, and SETUP.md stops on a mismatch. Cron runs
  the local copy, which never updates itself.
- The public file carries only the contract's numbers and names. Every text string is redacted: links, IP and e-mail
  addresses, paths, keys, ids and tokens.
- `--from-api` exists but is **not recommended**. The account already meets Kalshi's rate limits, and the only key is the
  bot's trading key. It is GET-only and allow-listed in code.

## Checks
`python -X utf8 -m tests.test_kalshi_publish` runs 98 checks. They use a mock Kalshi API that verifies RSA-PSS and
Ed25519 signatures, a fake bot folder built from the real schema, a stand-in `srv.py` and local bare git repos. They
make no network calls and use no real keys.
