# day-warroom: lead-only wiring

1. **Wire the new app** (helpers never edit jarvis/apps.js, olympus.js APPS, build_web_dashboard.py, sw.js). `tools/new_apps.json` has the `warroom` row:
   `python tools/wire_new_apps.py --apply` (adds it to apps.js BUILT_INS, olympus.js APPS + AMBIENT, the build tuple, sw.js OTHER_APPS, intro FLAVOUR,
   transitions REGISTRY, then rebuilds olympus/apps-list.js). This fixes `test_apps_list` (a) and puts /warroom/ on the published site.
2. **Gate catalog row** (fixes `test_gate_page` "every app folder is in the catalog"), in `olympus/gate-catalog.js` after the 'pillars' row:
   ```js
   ['warroom', 'warroom/', 'War Room', 'Every bot, every step, live', 'LIT, ATLAS, BLITZ, ORDER FLOW: the steps, what each waits for, how close a trade is', 'bots', 'bots', 'war room live steps ladder brain thinking entry setup now trade countdown narration', 'nq'],
   ```
   then `python tools/bump_versions.py --apply --base origin/pc` (always with `--base`).
3. **Root sw.js CACHE** le-public-v213 -> v214 (the only item `bump_versions --check --base origin/pc` flags: gate / nq / pillars / mind index.html changed).
4. **PC glance: exact numbers** (engine/brain_glance.py, + ~45 bytes a post, MAX_BYTES unchanged). Without it the War Room computes ATR(14) from the
   chart post's 5m bars and reads prices from the PC's own words; with it, the sweep size and the chart lines use the bot's own values.
   In `lit()` add to `out`:
   ```python
   "atr": _f(br.get("atr")), "ax": _lit_ax(br),
   ```
   and next to `_lit_armed`:
   ```python
   def _lit_ax(br):
       for s in reversed(_l(br.get("setups"))):
           pl = _d(_d(s).get("plan"))
           if _d(s).get("status") in ARMED_ST and pl:
               return [_f(pl.get(k)) for k in ("limit", "stop", "target")]
       return None
   ```
   (`build()` already drops None / [] values; tests: tests.test_brain_glance.)
5. **Milestone pushes with the page closed** (the page's switch only alerts while it is open). On the PC, in the 15-minute reporter or the
   heartbeat: when LIT's stage reaches 7/10 (1m CISD wait) or 8/10, when an ATLAS lobe turns armed, and on each entry, send ONE ntfy push to the
   owner's private alert topic ("LIT 8/10: entry likely within minutes"), at most one per milestone per day, behind a setting
   `warroom_push` in data/ (default off). The phone switch's words already say "Alerts with the page closed come from your PC (being wired)".

## What it is
- tools/web_public/warroom/: index.html, warroom.css, warroom.js (page), warcore.js (pure model, node-tested), manifest + icon. Read only.
- Linked FIRST on Home (gold "War Room" pill in the title row: no height added, the 6 dashboards stay on the first screen), NQ (first header
  button; the long head comment was shortened so NQ stays under 300 KB), the Pillars page and the Strategy Brain (first in their top bars).
- Data: the PC's status post (glance: stage n/10, wait, why, lv, arm, pos, log; glog), its chart post (5m bars + open trades by account LABEL),
  nq/brief.json (windows), pillars-data.json (BLITZ / ORDER FLOW steps). The glance's `mode` (holds part of an account id) is never shown.
- BLITZ stays hidden: its 6 steps only, all off, "HIDDEN · PAPER", never live data.
- Tests: tests/test_warroom.py (static + node + Chromium 390x844, 4 scenarios). Shots in shots/.
