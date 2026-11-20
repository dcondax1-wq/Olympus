# Zenith Home: no jumps, first content sooner (DESIGN, day-arenas 2026-11-20)

The dogfood audit graded Zenith **D**: main content 10.8 s live, layout jump (CLS) 1.08 from late add-on cards.

## Before / after (390 x 844 phone, 4x slower CPU, 1.6 Mbps / 150 ms line, files gzipped like GitHub Pages; 2-3 runs each)

| | Before | After |
|---|---|---|
| **Layout jump (CLS)** | **0.96 - 1.14** | **0.016 - 0.086** (Google "good" < 0.1) |
| First Home content on screen (accounts, verdict, P&L) | 4.2 - 4.4 s | **3.2 s** |
| home.json (Home's own small file) arrives | 4.0 s (waited behind main.js) | **0.7 s** |
| First paint (FCP) | 0.8 s | 1.0 s |
| LCP (the browser's "main content" = the Money-now card's big number) | 4.4 - 5.0 s | 5.7 - 6.0 s (see below) |
| CPU only, no line limit: first Home content / CLS | 0.97 s / 0 | 0.81 s / 0 - 0.07 |

The local server speaks HTTP/1.1 (6 connections share the line); the live site is HTTP/2, where `fetchpriority="high"` really puts main.js / hub.js
first. Expect the live first Home content under 3 s.

## What changed

1. **home.json starts with the page** (`index.html` `<head>`: `window.HOMEP0`; `main.js` uses it). It used to start only after main.js (138 kB
   gzipped) had downloaded behind 50 other scripts.
2. **main.js, extras.js, hub.js fetched first** (`fetchpriority="high"`): the three files Home's first draw needs.
3. **data.json (8.7 MB, 1.5 MB on the wire) waits for Home's first draw** on Home (or 2.5 s). Home draws from home.json; data.json no longer takes
   the line from the scripts. Every other page loads it at once, as before.
4. **The NQ strip has its slot from the first frame**: `#znNq` is in index.html before `#page`; `zenith_nq.js` fills it (it used to insert itself
   above Home at 5.4 s: a 0.06-0.08 jump on its own).
5. **`zenith_settle.js`** (new, right after main.js): while Home starts up (until the full data.json draw has settled, max 25 s), each burst of
   add-on changes (the ZEUS card at the top, the hero, the money / session cards, polish's regrouping, the strip) happens behind a still copy of
   the last drawn frame; when `#page` is quiet for 0.3 s (max 3 s) the finished page shows in one step. Text-only updates (the clock) never hold;
   a tap or focus on the copy shows the real page at once; leaving Home releases it; after start-up nothing is held.

## Honest notes

- **The swap is still one visible change.** The cascade of 6-8 jumps over ~1 s became one step from the first draw to the finished Home. The
  browser's CLS does not count a swap, but the eye sees it once. The real end state is the dogfood's slot plan: every add-on fills a reserved slot
  in `hub.js VIEWS.today` (ZEUS card 240 px at the top, the hero ~155 px, the strip ~119 px, the money / session cards inside `.pl-hi`). That needs
  edits in ~8 add-on files (zeus_core.js, zenith_hero.js, moneynow.js, sessionday.js, more.js, polish.js, statuscore.js) and was not safe in tonight's
  window; the settle layer keeps working once slots exist (fewer, shorter holds).
- **LCP got ~1 s later** (the money card's big number is the largest text and arrives last; under the copy it shows at the swap). What you can
  read (accounts, verdict, P&L) is on screen 1 s **earlier** than before. Getting LCP under 3 s needs the money card in the first draw (load
  moneynowcore / moneynow / polish before the other add-ons, or draw it from home.json in hub.js).
- **Screen readers**: during a hold the real page is hidden and the copy is read instead (same text, a few hundred ms older).
- **CPU is the other half**: 50 deferred scripts = ~6 s of long tasks at 4x CPU (1.8 MB of JS). The next big win is loading the add-ons that
  only matter on other pages lazily.

## Tests

- New `tests/test_zenith_settle.py` 12/12 (in run_area `zenith`): the head fetch, priorities, the data.json wait, the NQ slot, start-up CLS < 0.1
  on a throttled phone, holds released and nothing left behind, other pages untouched.
- `run_area zenith`: 10/11 suites green; `phone_e2e` needs a GitHub login to clone the live site (this cloud session has none).
- `test_feed_accounts` 47/47 (one check now waits for the copy to lift before reading `innerText`), `test_zenith_nq` 20/20, `olympus_shell` 42/42,
  `site_sweep` 4/4, smoke 10/10.
- Not mine, seen while testing: `phone_budget` lazy / ctx (the NQ page's 3D and the render lab time out here) and g; `olympus_themes` t2 "brutal" on
  ledger / kalshi / mint (merged from pc).

## Lead wires

- `sw.js` (lead-only): if it pre-caches Zenith's files, add `zenith_settle.js` and bump for `main.js?v=w14` / `zenith_nq.js?v=5`.
