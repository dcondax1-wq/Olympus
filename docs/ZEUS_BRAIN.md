# ZEUS Brain (the Obsidian vault that learns)

One generated vault of everything ZEUS knows: accounts, every bot's rules and numbers, ~200 research write-ups, a note per day,
the lessons, the decisions, the apps map and Kalshi. Every note links to the others, so Obsidian's graph view shows the web.
No plugins needed (callouts + one CSS snippet).

| Where | What |
|---|---|
| `vault/` in the repo | the full vault (open it as a vault in Obsidian); rebuilt every night by `tools/learn_night.py` |
| `<your vault>/OLYMPUS/ZEUS Brain/` | the same notes, written by the PC once an hour (needs the Obsidian sync set up: `docs/OBSIDIAN_SYNC.md`) |
| `Inbox/` | yours: write anything there; it is never overwritten and your notes are linked from ZEUS Home |

Look: Settings -> Appearance -> CSS snippets -> turn on **zeus** (the PC copies it into `.obsidian/snippets/`). Graph colors
(strategies orange, accounts green, rejected red, research blue) come with the repo vault.

| Note | From |
|---|---|
| ZEUS Home | the map |
| Accounts/Account <name> | `tools/web_public/board/board.json` + `business/accounts.json` + board events + trades |
| Strategies/ (Zlarior (LIT), ATLAS + members, BLITZ, Rapid lanes, 50K combo, Kalshi K8 + legs) | STRATEGY.md, second_model.json, BLITZ_STRATEGY.md, docs/RAPID_EOD_SETUP.md, engine/combo50k.py, research/anatomy/explain.json, docs/TESTED_AND_REJECTED.md |
| Research/<stem>, Families/ | `research/writeups/*.md` |
| Days/Day <date>, Months/ | trades.json, board events, ZEUS daily reviews (`logs/zeus/review_*.json` on the PC), write-up dates |
| ZEUS Lessons | loss clusters (anatomy) + every rejected idea family + rejected / promising write-ups |
| ZEUS Decisions / Apps / Kalshi / State | decisions.json / docs/OLYMPUS_MAP.md / docs/KALSHI*.md + edge tables / STATE.md |

Commands: `python tools/obsidian_brain.py` (rebuild `vault/`), `--check` (exit 1 if stale), `--vault "C:\path\to\vault"` (one
build into a real vault now). Deterministic: the same repo gives the same bytes. Privacy: every note is scrubbed (emails, keys,
account ids, tailnet names, personal folders) and the site privacy scanner runs on it in the test.
Test: `python -X utf8 -m tests.test_obsidian_brain` (area `pc`).
