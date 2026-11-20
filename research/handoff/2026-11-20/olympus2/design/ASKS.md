# DESIGN team: asks for other slices (day-arenas, 2026-11-20)

The design system is now one documented source: `docs/DESIGN_SYSTEM.md` + the live page `/olympus/kit.html`. Audit any page with
`python tools/design_audit.py --site <built site> [--apps ...]` (add your pages to `APPS` in it: id -> path). Each ask names who owns the file.

| # | For | Ask | Why |
|---|---|---|---|
| 1 | NAV (hub/), HOME (gate/) | Bump `olympus/shell.css?v=s5` -> `?v=s6` in `gate/index.html`, `hub/index.html`, `hub/doors.html` | shell.css changed (bottom-bar labels 12 px, the bar rules no longer hit in-page tab chips). Nothing breaks without it; phones just keep the old copy longer |
| 2 | JARVIS, NAV (hub/zeus.html) | Bump `olympus/zeus_core.js?v=5` -> `?v=6` in `jarvis/index.html` and `hub/zeus.html` | the ZEUS card's account tags are 12 px now (were 11) and use text-safe colours (Eval blue / Funded green read on a light look) |
| 3 | every slice | Pages that use the kit: `<html ... data-oly-shell="app" data-oly-light>` + `olympus/shell.css` loaded LAST; a page without `olympus.js` calls `OLYMPUS_THEMES.apply('page')` after `themes.js` (see business/plan.html, atlas/) | otherwise a light look never reaches the page, and a phone keeps live blur behind scrolling cards |
| 4 | A11Y | The 12 px floor and AA contrast are now measured by `tools/design_audit.py` (taps, text size, contrast in dark AND Ivory). My 20 pages: 0 low-contrast texts, 0 texts < 12 px except Zenith (see below) | reuse it for your per-team fix lists instead of a second tool |
| 5 | PERF | 3D scene start is the only long task left on my pages: Ledger vault ~1.1 s, Kronos sundial ~1.6 s, Fates loom ~1.8 s (headless software WebGL; a real iPhone GPU is much faster). Oikos ~0.3 s. Worth a `lazy3d.js` idle start if you have time | the bar says no long task > 200 ms |
| 6 | PERF / DATA | `kalshi.json` (Business, Ledger) and `money/scoreboard.json` (Ledger) are 404 on a local build; the PC's publisher writes them. A real build should check they exist or quiet-net should list them as optional | 0 failed requests on the public site |
| 7 | HOME (gate/) | `launcher.js` `.oly-lbtn` is 40 px tall (the file is byte-identical with web_next, so I did not touch it); Zenith gets an invisible 44 px tap ring from `polish.css`. If the Gate shows the launcher button, the same ring rule fits there | 44 px taps |

## Round 2 (after PERF / A11Y / DATA lists, 2026-11-20 afternoon)

| # | For | Ask | Why |
|---|---|---|---|
| 8 | every slice using AGORA | Bump `olympus/agora.css?v=a7` -> `?v=a8` on your pages (69 pages still say a7; my 28 say a8) | a8 = A11Y K2 type tokens (13 / 14 / 15, new `--ag-fs-note`), K3 44 px chips / segments, K5 title, K6 grid guard, and the empty back row that stops the +0.06 header shift |
| 9 | every app on the kit | Call `OLYMPUS.ready()` right after your first real render. Your content now stays undrawn under the veil until then (12 s cap) | that is what turns the 0.3-0.95 card shifts into 0. An app that never calls it shows its content only after 12 s |
| 10 | DATA TRUTH | UNDONE 11-20 (lead): the age component stays at the site root `age.js` + `age.css` (DATA owns it; pulse / Settings / kit load the root files ?v=2; no olympus copy) (your API unchanged: `OLY_AGE.text/level/chip/LIMITS`; font = `--ag-fs-cap`). Switch nq / trading / board to it and drop the root copies when you can | one age format site-wide |
| 11 | PERF + lead | Zenith Home on a phone line: layout shift ~1.0, all of it at ~16 s when the 8.5 MB `data.json` lands: Home is drawn first from `home.json` (hub.js), then redrawn from data.json, and polish.js / zenith_hero.js / more.js re-shuffle it (zh-hero, su-sun, zn-hi appear, then fold away; `.pl-home` moves). Fix = update Home in place from data.json (no second full draw) or a slimmer data.json. Not done: too risky today | the biggest shift left on my slice |
| 12 | PERF | lazy3d.js now waits for window load + idle (2 s cap) and skips like LITE on Save-Data / 2G-3G / <= 4 GB memory. Pages that import their 3D directly (ledger, mercury, oikos, compass, kronos) still pay it at load: moving them onto lazy3d is the next step (each app's own test pins its scene start, so one by one) | long tasks |
| 13 | JARVIS | `tests.test_olympus_a11y` fails on `jarvis/classic.css --dim #221b2e` (1.26:1); `tests.test_phone_budget` f expects `const behind3d = () => root.dataset.bg3d === 'on'` in jarvis/index.html | both predate my changes |
