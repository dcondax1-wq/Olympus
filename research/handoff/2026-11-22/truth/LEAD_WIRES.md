# LEAD_WIRES (night-truth field audit)

mffumodel.js changed (coach reads the PC's mf `lt` / `f.ft`). Cache bump for the two pages that load it with ?v=:
- tools/web_public/business/mffu.html:111   `<script src="mffumodel.js?v=4"></script>`  ->  `<script src="mffumodel.js?v=5"></script>`
- tools/web_public/board/index.html:83      `<script src="../business/mffumodel.js?v=4"></script>`  ->  `<script src="../business/mffumodel.js?v=5"></script>`
(sw.js has no mffumodel entry: no sw.js change.)

Optional Python side (tools/pc_report.py `_life`): keep `"why"` (cut ~80 chars) per account so mffucenter.js's `life_why` line can show.

## night-truth round 2 (Packages D + E)
- sw.js: bump the cache for the changed site files: nq/trading_home.html + trading_home_core.js, nq/braincore.js (brain.js ?v=6 imports
  braincore.js?v=6; brain.html loads brain.js?v=6), business/accounts.js (?v=6 in accounts.html), business/mffumodel.js (?v=5 everywhere).
- CLAUDE.md (lead only, audit E4): "git push origin HEAD:pc" -> push by URL (`git push https://github.com/dcondax1-wq/Olympus HEAD:pc`)
  or `python tools/ship.py`; docs/AUTO_UPDATE.md already says so.
- Package C (brain_glance, NOT touched here, reverted to land-fixes): two glance gaps seen in tonight's real post for that builder:
  (a) Zlarior 25K #2 (b25k_2, an extra account of acct.accounts) has no glance row: build() only adds rapid / rapid2;
  (b) rapid(): room is None until a broker anchor exists (eval.anchor.floor): MFFU's own floor from plan_rules + eval.days would do.
  The core "ar" follows the glance's armed rule (pc_report.armed_core), so Package C's fix flows into "ar" by itself.
- engine/state_pulse.py is wired in server.py (PULSE, started with REPORT_KEEPER; LE_STATE_PULSE=0 = off).
