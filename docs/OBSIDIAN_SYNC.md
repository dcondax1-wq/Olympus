# Obsidian living sync (the PC writes your vault)

**One-time setup (on the PC, 1 minute):** open a terminal in the OLYMPUS folder and paste, with your vault's folder:

    python tools/obsidian_sync.py --setup "C:\Users\YOU\Documents\Obsidian\YourVault"

(Obsidian: the vault switcher at the bottom left → "Show in system explorer" shows that folder.) The path is saved in
`data/obsidian_sync.json` (gitignored, never pushed). Done: from now on the PC report (every 15 minutes, the task that already
runs) updates the vault by itself. Stop it with `python tools/obsidian_sync.py --off`; `--status` shows the last sync.

## What lands in the vault (only in `OLYMPUS/Sync/`, never anywhere else, never a delete)

| Note | What |
|---|---|
| `OLYMPUS Index` | the map: today, the last 14 days, research, business, STATE |
| `Days/Bots 2026-11-16` | Zlarior and ATLAS: drawdown left, today's $, balance, trades, data age; your "How I feel" part is kept |
| `Trades/2026-11-16 Zlarior 0942` | one note per trade: side, micros, entry / stop / target / exit, $ and R, its picture |
| `Pictures/…png` | the trade pictures the bot draws (`logs/charts/`) |
| `Research/Learning <day>` | the nightly learning one-pager (`research/learn/latest.md`) |
| `Business checklist` | each money model's next step and first-dollar list as tasks; **your ticks are kept** |
| `STATE` | the repo's STATE.md |

BLITZ stays hidden (dashboard_view.json). No secrets, logins, emails or account ids are written (the sync cuts them out).
Jarvis already reads the same vault through GitHub (docs/JARVIS_OBSIDIAN.md): with the Obsidian Git plugin on, these notes reach
Jarvis on the phone too ("what did the bots do yesterday", "open tasks").

Code: `tools/obsidian_sync.py` (hook in `tools/pc_report.py`). Test: `python -X utf8 -m tests.test_obsidian_sync`.

**ZEUS Brain (2026-11-20):** the same hook also rebuilds `OLYMPUS/ZEUS Brain/` once an hour (every account, strategy, research
write-up, day, lesson and decision, all linked) and adds the `zeus` CSS snippet to `.obsidian/snippets/` (only if you have none
of that name). `docs/ZEUS_BRAIN.md`.
