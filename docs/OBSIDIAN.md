# ZEUS Brain on your iPhone (3 steps, free)

ZEUS Brain is the Obsidian vault the bots write for you: 1,200+ linked notes (every trade, why each loss lost, each week,
each news type, each Decide card, each hard rule, every write-up). The PC rebuilds it **once an hour** into your vault
(`OLYMPUS/ZEUS Brain/`), the cloud night rebuilds the repo copy (`vault/`). Nothing to pay: no Obsidian Sync needed.

1. **PC, once (skip if done):** in the OLYMPUS folder paste
   `python tools/obsidian_sync.py --setup "C:\Users\YOU\Documents\Obsidian\YourVault"` (your vault folder).
   From then on the brain lands in `OLYMPUS/ZEUS Brain/` by itself (docs/OBSIDIAN_SYNC.md).
2. **PC Obsidian, once:** the free **Git** community plugin pushes the vault to your private `obsidian-vault` repo
   (the same setup Jarvis uses: docs/JARVIS_OBSIDIAN.md). In the plugin's settings set "Auto commit-and-sync interval" to 30.
3. **iPhone:** App Store → **Obsidian** (free) → Create a vault → Settings → Community plugins → **Git** → "Clone an existing
   remote repo" with the same repo and token → open **OLYMPUS/ZEUS Brain/ZEUS Home**. Tap the graph icon for the Graph view.

## What to open first

| Note | What it tells you |
|---|---|
| ZEUS Home | accounts, this week in $, the real (live + paper) trades, what the losses teach, every hub |
| ZEUS Weeks → Week ... | the weekly review: each bot's trades and $, best / worst, why the losers lost, the news |
| Days → Day ... | the daily note: what each bot did, every trade, the day's lessons, the news, the research |
| ZEUS Lessons → Lesson ... | the learning layer: each reason code (never worked, worked then turned, shaken out, news hit, the 4 checklist flags), recounted on every build, with examples and "would skipping pay?" |
| ZEUS Decisions → Decide ... | each Decide card with its $ a month and Claude's recommendation |
| ZEUS Dataview | live tables, only if you add the free Dataview plugin (everything else reads fine without it) |

Write your own notes in `Inbox/` (or anywhere outside `ZEUS Brain/`): the brain never overwrites them.

For Claude: the builder is `tools/obsidian_brain.py` + `tools/obsidian_more.py` (deterministic, no clock; `--check` for stale);
test `python -X utf8 -m tests.test_obsidian_brain` (area pc).
