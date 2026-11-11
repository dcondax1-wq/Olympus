# QA Round 6: quality lock-in (owner 2026-11-11 evening)

Owner: "We have a good starting point, but really lock in on quality. There's a lot of bugs, a lot of stuff you should add. Think."

Evidence from the lead's own pass on the built site (390x844, headless Chromium): `docs/shots/qa_round6/lead_sheet1.jpg`,
`lead_sheet2.jpg`, `lead_console_report.json`; `tools/site_smoke.py` gave 73/74 (Aegis FAILED), 15 pages with warnings.

## Bugs found (each must be fixed or explained)
1. **Aegis fails site_smoke** and shows **DEMO numbers** (Zlarior $1,420 of $2,000) while Helios shows the real $1,145. Any app that has
   real published data must show it; DEMO only when the real file is missing, and labelled.
2. **Numbers disagree between apps** (drawdown left, "data age": root says 59 min, NQ says 5 days). One source of truth per number.
3. **The floating orb (the "O" button) covers content** at the bottom right on every page (Polis harbour text, Helios, Colosseum
   buttons). Pages need bottom padding / safe-area so nothing sits under it.
4. **Sideways scroll**: `olympus-live.html` (409 px at 390) and `olympus/agora-lab.html` (409 px).
5. **Console 404 noise** on optional files: `kalshi.json`, `cronos/status.json`, `kalshi/jarvis.json`, `zenith/jarvis.json`,
   `kalshicity/forward.json`, `kalshicity/scan.json`, `money/sibyl_forward.json`, `polis/sky.json`, `kalshi/icon.svg`. Either publish
   a valid empty file from the build or load quietly (no red console errors). A page must never look broken because an optional file is missing.
6. **Dead live sources**: the owner's GitHub account is suspended. Pages still call `api.github.com/.../nq-dashboard/...live.json`
   and `raw.githubusercontent.com/.../kalshi-feed/...` (404 / 403 rate limit). They must fail quietly, fast and once, and the page must say
   plainly where its numbers come from and how old they are.
7. **Sample data in the worlds**: Symposium "9 showing sample data", Ergasterion "5 showing sample data". Use the real published
   files wherever they exist.
8. **Crude 3D hero scenes** in older apps: Mint "five pillars" (sticks on a disc), NQ "three bots" (three plain columns), Kairos ring,
   Helios, Pinakes cabinet, Herald newsstand, Aegis shield. They must reach the Round 5 bar (env-kit materials, HDRI light, real props,
   Polis kit ornament) or be replaced by a beautiful 2D painting.
9. Polis: harbour card text clipped under the orb; ships small at phone size; "City life" should sit nearer the top.

## Things to add (the "you should add" list)
- The rigged cast (Characters v3) walking in Polis, Hellas and Athens (today the towns use small blocky figures).
- Footsteps, presence jingles (`OLYMPUS_SFX.walker/presence`) wired into the walking scenes.
- Polis life pieces placed in the apps (herald banner on home, oracle on Pythia, grove on Helios/Aegis, amphorae on Nike/Kronos,
  statues on Colosseum, stoic line on home/Journal) per `docs/POLIS_KIT.md` and the Polis life report.
- Athens walking mode (terrain height), Jarvis courtyard framing at phone size.
- A real-phone budget pass: first paint < 2 s on a mid iPhone, no page over its draw-call budget, WebGL context-loss recovery,
  audio unlock on iOS, memory under control when switching apps.

## Rules
Same as `docs/NIGHT_BRIEF.md` (paper only; never touch engine/ or live_model*.json; no secrets; CC0 only with licence rows; agents never
edit `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js` or the olympus.js APPS table; browser work only under
`flock -w 2400 /tmp/olympus_browser.lock`; never run tests.test_win_scripts; temp files only in your own scratchpad subfolder).
Every fix is shown with a before/after screenshot that the agent itself reads back and judges.
