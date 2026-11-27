# NQ Replay Theater: what the lead wires (files I do not own)

New page: `tools/web_public/nq/replay.html` + `replay.js?v=r1` + `replay.css?v=r1`; data `tools/web_public/nq/replay/index.json` + one
`replay/<YYYY-MM-DD>.json` a day (~15 KB each, the last 35 days), built by `tools/build_replay.py` (also run nightly, soft, at the end of
`tools/forward_paper.py`, the learn_night 'forward' step).

1. Nav: add a Replay tab to the Desk's tabs in `tools/web_public/nq/index.html` (and live.html / accounts.html if they carry the same
   `.nqtabs`): `<a href="replay.html">Replay</a>`. The NQ Brain (mine) already has it.
2. `tools/web_public/sw.js`: precache `nq/replay.html`, `nq/replay.js?v=r1`, `nq/replay.css?v=r1`; the day files are data: network-first
   (or stale-while-revalidate) for `nq/replay/*.json`.
3. Optional: a launcher / Jarvis entry ("NQ Replay") in jarvis/apps.js / the olympus.js APPS table, if you want it outside the NQ tabs.
4. Test area: `replay` added to run_area nq (tests/test_replay.py).
