# night-nq-accounts: what the lead wires (files I do not own)

1. **Cache bumps** (my files changed under the same names):
   - `tools/web_public/board/index.html` and `tools/web_public/trading/index.html`: `../nq/payready.css?v=2` -> `?v=3` (night palette: mint / gold / red / violet; no olive / terra / sun).
   - `tools/web_public/nq/index.html`: `nqgoals.css?v=9` -> `?v=10` (3D ring wells, gold = payout, violet = pass, mint = done / fleet).
   - `sw.js`: bump the cache so phones fetch `nq/accounts.html|js|css`, `nq/acctcore.js` (imported `?v=2`), `nq/nqgoals.css`, `nq/payready.css` and the NEW `nq/plan12.json`.
2. **`nq/plan12.json`** is a static copy of `research/planner/results.json` (today's plan K0, no tripwire, 4 markets). When the planner is re-run, regenerate it with `python -X utf8 research/handoff/2026-11-27/night-nq-accounts/make_plan12.py` (and update its "made" date; `tests/test_nq_accounts_night` part b fails if it drifts from results.json).
3. **Buy light**: shows only when the PC report carries `bg` (engine/buy_gate.tiny = only when `data/buy_gate.json` {"show": true}); nothing to wire, it appears by itself once the switch is on.
4. **nqtheme.css** (not mine) paints every goal ring one gradient via `html[data-theme] .gl-arc`; nqgoals.css now wins by one more class. If you prefer, drop lines 58-60 of nqtheme.css.
5. Tests: `tests/test_nq_accounts_night.py` (new, area nq); `tests/test_accounts_screen.py` part a now ignores exactly the SVG namespace string (`http://www.w3.org/2000/svg`) in accounts.js.
