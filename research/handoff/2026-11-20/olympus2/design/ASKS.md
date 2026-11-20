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
