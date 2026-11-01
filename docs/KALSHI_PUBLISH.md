# Kalshi in Jarvis: what the PC does (for Claude on the owner's PC)

The owner wants his Kalshi bot inside Jarvis, his iPhone hub (`https://demetrades2000-coder.github.io/nq-dashboard/jarvis/`).
The Kalshi bot runs only on this PC, so the phone can't reach it. The phone side is already built and live:
- the Kalshi page `<site>/kalshi/`;
- the Jarvis Kalshi card;
- answers to "how's kalshi".

They all read one file, `kalshi.json`, from the branch `kalshi` of the public repo `demetrades2000-coder/nq-dashboard`.
Until that file exists they show "Waiting for your PC". Your job is to get the file there and keep it fresh. That's all.

## Rules
- **Read-only.** Don't change how the Kalshi bot trades, its settings or its keys. Never put Kalshi API keys, key file
  paths, the account id, email or anything secret in the status file. The `nq-dashboard` repo is **public**, so only the
  numbers below go there.
- Don't touch the NQ bot: it runs from this folder (`server.py`, `engine/live.py`, `live_model*.json`, `data/`). Leave its
  processes, its settings and its scheduled tasks alone.
- The publisher is `engine/kalshi_publish.py`, in this repo. It:
  - drops credential-looking keys and redacts local paths;
  - keeps only the keys listed below;
  - pushes with this PC's own git login, the same one the NQ bot uses for `live.json`.

## 1. Make the Kalshi bot write a status file
Make the Kalshi bot write one JSON file at a fixed path. Write it whenever something changes, or at least once a minute
while it runs; for example `<the Kalshi bot's folder>\kalshi_status.json`. The bot can be in any language; only the file
matters. If the bot already has a local dashboard or API with these numbers, a small script that reads it and writes the
file is fine too.

To see a full example, run `python -m engine.kalshi_publish --sample`. The keys (every one is optional except `t`):

**Top level**

| key | meaning |
|---|---|
| `t` | unix seconds when the file was written (the phone shows "updated N min ago" from it) |
| `running` | true or false: is the bot running |
| `mode` | `"paper"`, `"demo"` or `"live"` |
| `status` | one short plain sentence, e.g. "Watching 12 markets" |
| `name` | the bot's name |
| `balance` | account balance in dollars |
| `today_pnl`, `week_pnl`, `total_pnl` | realized + open P&L in dollars (today = since midnight ET) |
| `note` | an optional short line |

**`positions`**: a list of the open positions.

| key | meaning |
|---|---|
| `ticker`, `title` | the market's ticker and its plain-language title |
| `side` | `"yes"` or `"no"` |
| `contracts` | number of contracts |
| `avg_price`, `price` | entry and current price in dollars per contract (0-1) |
| `value`, `pnl` | position value and P&L in dollars |
| `closes` | ISO time the market closes |

**`trades`**: the last trades, newest first, with keys `t`, `ticker`, `title`, `side`, `action` (`"buy"` or `"sell"`),
`contracts`, `price` and `pnl`.

**`days`**: daily P&L as a list of `["YYYY-MM-DD", dollars]`, for up to the last 120 days.

## 2. Check it, then push once
Run these in this repo's folder, the NQ bot's folder:

```
python -m engine.kalshi_publish --src "<path to kalshi_status.json>" --check
python -m engine.kalshi_publish --src "<path to kalshi_status.json>" --once
```

`--check` shows exactly what would go public. `--once` pushes it and prints `"ok": true` and the address the phone reads
(`https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/kalshi/kalshi.json`). Open that address to confirm
the numbers. If the push is refused, the NQ bot's own push of `live.json` uses the same login: see
`python -m engine.live_publish --status`.

## 3. Keep it running by itself
Create a Windows Task Scheduler task named "Kalshi to Jarvis":
- **Trigger:** at logon.
- **Action:** `pythonw.exe -m engine.kalshi_publish --src "<path>" --loop`, with *Start in* set to this repo's folder.
- **Settings:** restart every 1 minute on failure; no time limit.

The loop checks every 60 s. It pushes when the file changed, and otherwise once every 10 minutes. It never talks to Kalshi
and places nothing.

## Done when
- Jarvis's Kalshi card on the phone shows the balance and today's P&L.
- The Kalshi page shows the positions.
- Tell the owner in one or two plain sentences.
