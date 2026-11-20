# night-revamp-main: report (2026-11-20)

1. **Lag (Jarvis):** the 3D sky, the orb and the constellation now hold still while you scroll. Battery mode is now a still sky, and a phone draws the sky at 20 fps. Blocked main-thread time on the Jarvis home at 4x CPU: PERF_LINE.
2. **Bottom bar (Zenith):** the tab bar now sits flush on the bottom edge like an iPhone tab bar. Its keys sit above the home bar, and the old empty band with the page showing through below the bar is gone. The Jarvis dock keeps its low position, which the owner asked for on Nov 19.
3. **One design layer:** `olympus/shell.css` holds the tokens (colour, type, spacing, radius, motion, safe areas, a light set), the bottom bar, and the reduced-motion and phone no-blur rules. It loads last on the Gate, Zenith, Jarvis, Doors, the hubs and Settings.
4. **Home (Gate) and Doors:** flat cards with one hairline border, quiet section labels, a colour dot for each door, and the hubs and shortcuts as one grouped list (iPhone Settings style). Same links and ids.
5. **Fewer apps:** 45 weak or duplicate apps are folded under "Archive" at the end of their door on the Doors page and in the launcher (`olympus/doors.js` ARCHIVE). 31 of 76 stay visible. Nothing was deleted, every URL works, and search finds them all. Scores are in AUDIT.md.
6. **Sounds:** the sound kit already meets the brief: subtle by default (volume 0.35, music off, silent until the first tap), with a switch in Settings. No change.
7. **Glitches:** none of the main pages logs a page error. 16 apps had no icon (404s on the hubs) and now have one. "Why" was missing from the Gate's search and is now in it. The Gate was loading an old theme-file version; it now loads the current one.
8. **New test:** `tests.test_olympus_shell` (olympus area). It fails on sideways scroll, page text under a bottom bar, bar keys on the home indicator, page errors or missing site files. Result: 43/43.
9. **Other suites:** apps_list 44/44, gate_page static 34/34, sfx engine OK, fit_edge 62/62 after the dock fix. SUITES_LINE
10. **Lead to do:** bump the two sw.js caches (LEAD_WIRES.md), or phones keep the old Jarvis files.
11. **Screenshots (390x844, home bar emulated):** `shots/before-*.png` and `shots/after-*.png` for gate, zenith, jarvis, doors, hub and settings, dark and light, top and `-bottom`. Light only changes when a light look is picked, so the light shots match the dark ones.
12. **Tool:** `python tools/olympus_shell_audit.py --shots DIR --tag after --light` gives the same numbers and shots again.
