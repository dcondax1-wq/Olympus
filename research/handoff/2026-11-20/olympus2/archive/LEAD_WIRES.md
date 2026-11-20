# Archive team: lead wires (day-archive 2026-11-20)

Nothing here is needed for the branch to work: the banners, fixes and tests run as they are. These are the lead-only files the archive
team may not edit, with the exact lines for each optional step.

## 1. Retire 25 apps (proposal; the lead's or owner's call)

What "retire" means: gone from the Doors page, the Archive fold, the launcher, Jarvis's switcher and search. The folder and URL stay
(old links, bookmarks and the data files other apps read keep working), and the page already says "Archived -> <live app>".
Why each one: INVENTORY.md (verdict `RETIRE?`). In short: duplicates of a main app (delphi, stoa, hestia, plutus, argo, mint, harmonia,
kairos, chronos, lyceum, polis, atlascity), 3D gimmicks with no money use (gallery, mintcity, nike, arena, mind, symposium), dev-facing
or stale (herald, ergasterion, observatory, pheme, bridge, arbiter, hermes).

Folders that must stay even if retired, because main apps read their data: plutus (roadmap.json: Hera, Demeter, Ledger),
ergasterion (queue.json: Jarvis, Polis), mint (Jarvis, Cities), bridge (Inbox), arena / hermes / athena (Cities).

`tools/web_public/olympus/doors.js`, after the `var ARCHIVE = [...]` statement (line ~80):
```js
  // RETIRED (day-archive 2026-11-20, research/handoff/2026-11-20/olympus2/archive/INVENTORY.md): not shown anywhere, not even in the
  // Archive fold or search. The page and URL still work and say "Archived -> <live app>". To bring one back: take it out of this list.
  var RETIRED = ['delphi', 'stoa', 'hestia', 'plutus', 'argo', 'mint', 'harmonia', 'kairos', 'chronos', 'lyceum', 'polis', 'atlascity',
    'gallery', 'mintcity', 'nike', 'arena', 'mind', 'symposium', 'herald', 'ergasterion', 'observatory', 'pheme', 'bridge', 'arbiter', 'hermes'];
```
after `function archived(id) {...}`:
```js
  var ret = {}; for (i = 0; i < RETIRED.length; i++) ret[RETIRED[i]] = 1;
  function retired(id) { return !!ret[id]; }                     // not shown anywhere (still in its door's ids so doorOf() works)
```
in `find()`, the apps loop:
```js
    for (var n = 0; n < list.length; n++) if (list[n] && !ret[list[n].id] && all(words(list[n]))) res.apps.push(list[n]);
```
in `api`: add `RETIRED: RETIRED, retired: retired,`.

`tools/web_public/launcher.js` line ~281 (the Archive fold): filter retired ones out of `list` first:
```js
      list = D && D.retired ? list.filter(function (a) { return !D.retired(a.id); }) : list;
```
`tools/web_public/atlas/atlas.js` line 175 (DESIGN team owns atlas; same one-liner): `gone = (id) => !!(D && ((D.archived && D.archived(id)) || (D.retired && D.retired(id))))`.
`tools/web_public/jarvis/index.html` line 2144 (`archivedApp`): same `|| O.retired(id)` (JARVIS team).
The Doors page (`hub/doors.html`, NAV team) draws the Archive fold from `archived()`: skip `retired()` ids there too.
Then `python tools/olympus_map_build.py` and `python tests/run_area.py olympus --only apps_list,olympus_shell,site_sweep`.

## 2. Service worker

No sw.js bump needed: the archive team changed only app pages (network-first) and app JS that GitHub Pages serves with a 10-minute
cache (ares.js, plutus.js, forum.js + forumcore.js / forumplus.js, agency.js). If the lead bumps `le-public-v175` for other teams anyway,
nothing extra.

## 3. For the data owners (not lead-only, but not ours)

- `odeon/trades.json` stops at **2026-10-28** (23 days): `tools/odeon_export.py` reads LIT from `research/lab/replays.json`, which has not
  been rebuilt since. Trading, Journal, Kronos and NQ read this file too. A rebuild of the replays then `python tools/odeon_export.py` refreshes it.
- `pantheon/pantheon.json` was built **2026-11-03** (17 days old). Rebuilt today on this branch (`python -m tools.pantheon --no-research`,
  8/8 free sources). Whatever ran it daily (CRONOS on the PC?) stopped on Nov 3: worth a look, or it goes stale again. Forum now labels
  a read 2+ days old as old either way.
- `pythia/events.json` (the risk calendar Helios, Planner, Jarvis and Hub read) is correct as committed (Nov 10). Regenerating it from
  today's `data/news/events.csv` would have marked FOMC **minutes** days (Nov 18, Dec 30, Feb 17) as "FOMC decision" red days: fixed in
  `tools/money/pythia_dates.py` (selftest ALL PASS + a guard). A regen now adds the real CPI / PPI dates through March, but 5 suites pin
  the file's exact contents (helios, planner, polis_life, pythia, zeus_hub): do it with those owners.
- `plutus/roadmap.json` updated **2026-11-04** (16 days): Hera, Demeter and Ledger read it for the payout plan ("first payout about 2026-12-16").
- `kalshi.json` (site root) is a 404 until the Kalshi bot's feed is connected (Monday per STATE): Inbox, Stoa, Tyche, Polis, Hermes,
  Ergasterion and Symposium each log one console 404 until then. By design; no change made.
