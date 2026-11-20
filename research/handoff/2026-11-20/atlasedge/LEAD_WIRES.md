# LEAD_WIRES - day-atlasedge

none. No lead-only file needs an edit: no sw.js, build_web_dashboard.py, jarvis/apps.js or APPS table change, no ?v= tag,
no cache name.

For the lead's merge:
- tools/web_public/business/decisions.json gets one new open item (atlas-funded-streak-1micro); tests.test_decide 14/14.
  If the Decide card caps the open list, it goes in the normal order.
- STATE.md (lead's): add under "Waiting on the owner": "Decide: ATLAS 2 losses in a row -> 1 micro (atlas-edge-2026-11-20)".
- pip: `numba` was missing in the cloud container (tools/blitz25k_lib imports it); installed locally only, no repo change.
- Edge check (nqdash3 LEAD_WIRES part F, done another way, no lead-only file): tools/edge_health.py ATLAS_RUN = "atlas_fresh_fixed"
  (research/runs/atlas_fresh_fixed.json, committed; rebuild with `python -X utf8 tools/atlas_edge_fresh.py save` after the next
  fresh replay). research/lab/edge_health.json and tools/web_public/edge.json rebuilt (`python tools/edge_health.py --fetch`): ATLAS
  "a" = ["G", 2.4, 2.8, "2026-11-19"]. The PC's daily `edge_health.py --pc` reads the same run after its auto-update. The card key
  `usd_pf40_eval_sized` now holds the fixed-$250 $ PF (2.27): the run has no eval sizing any more; the key name was kept so the chip
  and tests need no change. If the NQ page's Quality card still has the red "ATLAS to Oct 16" row from day-nqdash3, it will clear
  once edge.json carries Nov 19 (no edit needed if it reads `a[3]`).
- The *_best.json member files and runs/baseline.json were NOT rebuilt (VIX after Oct 16 is not in the repo, so a raw re-run would
  mis-set the VIX targets; the replay with CBOE VIX already exists and was used). They still end Oct 16; nothing reads them for the light now.
