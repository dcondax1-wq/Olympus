# THE BRAIN (day-brain-app 2026-11-24): lead wires

The app lives in `tools/web_public/brain/` (index.html, brain.js, braincore.js, brain-scene.js, chart3d.js, brain.css, learn.json,
fixture.json, manifest, icon). Deep links: `brain/#lit #atlas #blitz #of #learn #risk`. Test: `python -X utf8 -m tests.test_brain_app`
(area `nq`, 67 checks: static + node + Chromium). Links added (helper-allowed pages): Home hero (gate/index.html, "Brain" beside Open),
NQ (header "3D Brain" button + the pillars hero), Pillars (a link bar under the temple + footer), War Room (a "3D Brain ›" button in "Right now").

## 1. Wire the app (the files helpers never edit)
`tools/new_apps.json` already has the `brain` row and `docs/NEW_APPS_WIRING.md` its section (`tests.test_wire_new_apps` 39/39). Run:
```
python tools/wire_new_apps.py --dry-run     # 6 rows: apps.js BUILT_INS, olympus.js APPS + AMBIENT, build tuple, sw.js OTHER_APPS, intro FLAVOUR, transitions REGISTRY
python tools/wire_new_apps.py --apply       # then python tools/apps_list_build.py --check
```
- `tools/web_public/sw.js`: `OTHER_APPS` gets `'brain/'` (from --apply). Note the root `brain.js` (Bot Brain module) is a different path; no clash.
- `tools/build_web_dashboard.py`: the app tuple gets `brain` (from --apply), and please run `python tools/build_brain_learn.py` before
  the copy (it rewrites `brain/learn.json` from `research/learn/`), or let CRONOS do it nightly. `--check` exits 1 when stale.
- Bump `sw.js` CACHE (as usual) because nq/index.html, gate/index.html, pillars/index.html + .css, warroom/* changed.
- `olympus/gate-catalog.js` (Home "Go to" search) row, if wanted: `['brain', 'brain/', 'The Brain', 'Every bot, thinking, in 3D', ...]`.

## 2. The learning feed (session day-brain-research)
`tools/build_brain_learn.py` reads, best first: `research/learn/journal.json` `[{date, pillar, text, n, usd, status}]` and
`research/learn/brain_state.json` `{pillar: {confidence, lessons, last_learned, testing_next, market_read}}` (pillar ids: lit, atlas,
blitz, of (or orderflow), learn (or shared / market), risk; confidence 0..1 or 0..100). Until those land it uses the real weekly
`research/learn/insights.json` (lessons + tested fixes + the market read); the confidence meter then says "not scored yet" (never invented).
No `BRAIN_FEED.md` existed on any branch when this was built (no `day-brain-research` branch yet), so the shape above is the one the
lead brief named; if that helper ships a different one, only `journal_rows` / `state_rows` in the builder need a tweak.

## 3. The PC report fields (session day-brain-feed)
The page renders these per bot when present, at `pc.glance.bots[i]` (or `lite.brain[<id>]`), and derives them when absent:
- `think`: last 8 reasoning lines, newest first: `["text"]` or `[["HH:MM", "text"]]` or `[{hm|t, text}]`. Absent -> `glog` / the glance `log` + the day's story (the room says the fuller lines are not in the report yet).
- `next`: `{setup, steps: [{label, state: done|now|wait}] | ["label"], waiting_for, dist_pts, window, limit, stop, target}`. Absent -> the War Room model (warcore: step n/10, what the next step needs, the PC's prices from its words / glance `ax`, the open trade).
- `levels`: `[{k, p, p2?, label?}]` with k in sweep, level, limit/entry, stop, target, fvg (p..p2 zone), leg (p = start, p2 = end: the page draws the 0.5 / 0.618 / 0.705 / 0.79 fib lines), cisd; `[label, price]` also accepted. Absent -> the glance `lv` + the War Room's levels.
- The bars post (le-bars) is unchanged.
Size: think 8 x ~100 chars + next ~300 + levels ~400 bytes a bot; pc_report's EXT_LAST budget may need `think` trimmed like `glog`.

## 4. Fixed on the way
- `warroom/warcore.js`: the stale headline read "ATLAS is was imminent" -> "ATLAS was imminent" (warcore ?v=w2, warroom.js ?v=w2).
- `docs/NEW_APPS_WIRING.md`: the missing `warroom` section (tests.test_wire_new_apps a. failed on it before).

## 5. Screenshots
`research/handoff/2026-11-24/brain-app/shots/`: before_* / after_* (Home, NQ, Pillars, War Room at 390 x 844 @2x), brain_* (the overview
SAMPLE in 3D, LIT SAMPLE + live + in a trade, ATLAS live, MARKET LEARN, the 2D fallback).
