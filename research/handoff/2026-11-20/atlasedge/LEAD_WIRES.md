# LEAD_WIRES - day-atlasedge

none. No lead-only file needs an edit: no sw.js, build_web_dashboard.py, jarvis/apps.js or APPS table change, no ?v= tag,
no cache name.

For the lead's merge:
- tools/web_public/business/decisions.json gets one new open item (atlas-funded-streak-1micro); tests.test_decide 14/14.
  If the Decide card caps the open list, it goes in the normal order.
- STATE.md (lead's): add under "Waiting on the owner": "Decide: ATLAS 2 losses in a row -> 1 micro (atlas-edge-2026-11-20)".
- pip: `numba` was missing in the cloud container (tools/blitz25k_lib imports it); installed locally only, no repo change.
