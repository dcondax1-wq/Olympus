# LEAD_WIRES (day-obsidian2)

Nothing lead-only touched. The refresh is already wired (learn_night rebuilds vault/, obsidian_sync rebuilds hourly on the PC).

1. Land: merge day-obsidian2, then `python tools/obsidian_brain.py` (rebuild vault/ on the merged tree) and
   `python -X utf8 -m tests.test_obsidian_brain` (area pc, 39 checks).
2. The vault now also reads `research/anatomy/trades_*.json`, `data/NQ_1m.csv`, `data/news/events.csv` + `ff_archive.csv` and the
   "Hard rules" section of CLAUDE.md. If any of those (or STATE.md / decisions.json, as before) changes, test g asks for a rebuild:
   `python tools/obsidian_brain.py`. Optional: add that one line to `tools/ship.py` before its tests (not done: ship.py is yours).
3. Optional (Jarvis, not mine): Jarvis indexes the whole Obsidian repo through GitHub; the brain adds about 750 notes there. If the
   phone's first sync feels slow, skip `OLYMPUS/ZEUS Brain/Trades/` in `tools/web_public/jarvis/obsidian.js`'s tree walk.
4. Optional: link docs/OBSIDIAN.md from STATE.md's owner steps (I did not edit STATE.md to avoid a merge clash).
