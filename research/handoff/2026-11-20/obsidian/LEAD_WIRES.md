# LEAD_WIRES (night-obsidian)

Nothing lead-only was touched (no sw.js, build_web_dashboard.py, jarvis/apps.js, olympus.js, pc_report.py, engine/, live_model*).

Optional wiring for the lead:
1. Land: merge night-obsidian; `python -X utf8 -m tests.test_obsidian_brain` (area pc) + test_obsidian_sync + test_learn_night.
2. After every nightly `tools/learn_night.py`, ship `vault/` with the rest (it rebuilds it; test g fails if vault/ is stale:
   fix = `python tools/obsidian_brain.py`).
3. If you want Jarvis to point at it: add a "ZEUS Brain" line to docs/JARVIS_OBSIDIAN.md / the Jarvis Obsidian paths
   (`OLYMPUS/ZEUS Brain/ZEUS Home.md`) - lead-only files, not done here.
Pre-existing, not mine: tests.test_repo_secrets c fails on tests/test_rapid25.py (an 18-char MF... id); left for the lead.
