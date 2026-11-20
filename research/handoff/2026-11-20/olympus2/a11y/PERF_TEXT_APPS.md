# PERF asks 3, 4, 6 done on the text apps (day-a11y, 2026-11-20)

Measured with `python -X utf8 tools/perf_sweep.py --pages ledger,helios,aegis,chrysos,mercury,oikos,compass,kronos,tyche,fates --no-offline`
(390 x 844, CPU x4, Fast 3G, cold), before -> after:

| App | KB first open | 3D on open | first paint ms | largest paint ms | long tasks (longest ms) | blocking ms | CLS |
|---|---|---|---|---|---|---|---|
| ledger | 506 -> 277 | yes -> no | 2740 -> 2708 | 8832 -> 5380 | 25 (983) -> 1 (60) | 2996 -> 10 | 0.004 -> 0.002 |
| oikos | 401 -> 235 | yes -> no | 2220 -> 2212 | 6092 -> 4116 | 5 (374) -> 1 (64) | 427 -> 14 | 0.002 -> 0.002 |
| mercury | 387 -> 223 | yes -> no | 2160 -> 2144 | 4112 -> 3972 | 4 (262) -> 1 (62) | 322 -> 12 | 0.002 -> 0.002 |
| compass | 602 -> 362 | yes -> no | 2168 -> 2152 | 7768 -> 5196 | 3 (225) -> 0 (0) | 186 -> 0 | 0.0 -> 0.0 |
| kronos | 660 -> 385 | yes -> no | 2200 -> 2140 | 7752 -> 5256 | 63 (1173) -> 1 (68) | 3164 -> 18 | 0.0 -> 0.0 |
| helios | 279 -> 279 | no -> no | 2200 -> 2192 | 4916 -> 4904 | 1 (63) -> 0 (0) | 13 -> 0 | 0.002 -> 0.002 |
| aegis | 259 -> 259 | no -> no | 2124 -> 2160 | 4728 -> 4308 | 1 (58) -> 1 (70) | 8 -> 20 | 0.002 -> 0.002 |
| chrysos | 235 -> 235 | no -> no | 2160 -> 2136 | 4188 -> 4072 | 2 (107) -> 1 (70) | 62 -> 20 | 0.002 -> 0.002 |
| fates | 588 -> 442 | yes -> yes | 2936 -> 2856 | 9416 -> 8392 | 18 (1665) -> 23 (1570) | 4034 -> 4439 | 0.019 -> 0.019 |
| tyche | 462 -> 462 | yes -> yes | 2220 -> 2240 | 10980 -> 11136 | 9 (3168) -> 9 (3214) | 7766 -> 7556 | 0.036 -> 0.036 |

**What changed**
- **3D after the numbers (ask 3).** On open these apps now have no three.js; the numbers paint first.
  - mercury, compass and kronos: their 3D module tag is now `olympus/lazy3d.js` (after the first paint, never on LITE, skipped on save-data, 2G/3G or small-memory phones).
  - kronos: the page waits for a `kronos-dial` event (12 s) instead of a 2.5 s poll.
  - compass: waits 12 s, and goes flat at once when the 3D is skipped.
  - ledger and oikos imported their scene at boot. They now import it after `load` plus an idle moment, with the same skip rule. The flat vase / CSS vault shows first on the same fixed stage, so nothing jumps. Ledger no longer holds the page (veil) until the vault is built.
  - helios, aegis and chrysos already used lazy3d (unchanged).
  - **"3D on open: no" in the table means the profile is Fast 3G, so the decorative 3D is skipped by design.** On an iPhone (no connection info) it loads after the page is idle.
- **sfx.js (ask 4):** the direct `<script src="../olympus/sfx.js">` tags are gone from ledger, helios, aegis, chrysos, mercury, oikos, compass and kronos. olympus.js loads it on the first sound. `tests/agora_kit.py` now accepts the page without the tag.
- **fates.json (ask 6):** 772 KB -> **84 KB** on open. `tools/fates/build.py split()` keeps the open scenario (Zlarior 2026) inline and writes the other big scenarios' threads to `fates/threads/<key>.json`, which the page fetches when that scenario is picked. `--one-file` turns it off; `--split-only` splits an existing file. The fates page itself is still 3D-heavy (its scene is the page), so its long tasks remain.
- **tyche: not changed.** The 3D wheel is the app itself (main.js imports three.js for its content), so deferring it would mean a rebuild, not a tag change. It still has 9 long tasks (3.2 s).

**Tests:** ledger 88/88, oikos 65/65, mercury 40/40, compass 57/57, kronos 54/54, helios 55/55, aegis 53/53, chrysos 61/61, fates 80/80.
The fates test's temp site gained age.css + jarvis/ask.js: they were 2 pre-existing 404 failures on pc too.
