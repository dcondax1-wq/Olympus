# LEAD_WIRES: PERF + OFFLINE (day-quality, Olympus v2, 2026-11-20)

## 1. Offline for every app (tools/web_public/sw.js, lead-only): `git apply research/handoff/2026-11-20/olympus2/perf/sw-offline.patch`

**Why:** the root worker controls every app page (scope = the site root) but `OTHER_APPS` makes it ignore every app folder, so after
one visit only Zenith, Jarvis and Kalshi open offline; the other 29 visible apps show the browser's "no internet" page (measured:
BASELINE.md, offline column).
**What the patch does (20 lines, the only change):** for a request inside an `OTHER_APPS` folder that has no worker of its own
(`OWN_WORKER` = jarvis/, kalshi/, hub/manual; planner is covered too: a worker a folder registers itself takes over its own scope anyway), answer **network first** (online: exactly as today, always fresh, no wait
added) and keep the good answer in a separate cache `le-apps-v1` (max 400 entries, oldest dropped); when the network fails, answer
the last copy (exact URL, else the same path with any `?v=`), else the existing `offlinePage()` for a page. `le-apps-v1` is not a
`le-public-*` name, so a CACHE bump keeps the apps' last copies; nothing else in the worker changes.
**Proof:** a copy of the site with the patch, all 32 visible apps through tools/perf_sweep.py's offline pass (Zenith once, the app
once, network cut, reload): **32 of 32 `ok`** (today: 3 of 32). 13 of them also show their data age offline (board, compass, dionysus,
helios, hera, inbox, jarvis, kalshi, mercury, nq, settings, trading, widget); the others open with their last data but no visible age
(ASKS: each app prints "as of <time>"). Permanent test: `tests.test_offline_apps` (area olympus) requires all 32 once `appNetFirst`
is in sw.js.
**Then:** `const CACHE = 'le-public-v<N>'` +1 (the worker file changed) or `python tools/bump_versions.py --apply --base <base>`;
`python -X utf8 tools/perf_sweep.py --pages nq,ledger,inbox` must say `ok` in the offline column.

## 2. Apps opened directly (not from the Home Screen app) never register the worker

Only Zenith's main.js (`location.protocol === 'https:'`), jarvis/, kalshi/ and hub/manual register a worker. An app opened from a
direct link or its own Home Screen shortcut has no worker until Zenith was opened once on that phone. Smallest fix (olympus.js
is DESIGN's kit; the lead may prefer to wire it): in `tools/web_public/olympus/olympus.js`, once after load:
```js
if ('serviceWorker' in navigator && location.protocol === 'https:' && !navigator.serviceWorker.controller)
  navigator.serviceWorker.getRegistration('../').then((r) => r || navigator.serviceWorker.register(me.src.replace(/olympus\/olympus\.js.*$/, 'sw.js'))).catch(() => null);
```
(registers the ROOT worker with its own root scope; a no-op when Zenith already did). Needs patch 1 to be useful.

## 3. Build / publish speed (measured 2026-11-20 in this container: `gh_publish --dry-run` 82 s, of which the site build 68-77 s)

Done in tools/ (no lead file): **the privacy scrub was 45 of the build's 77 s** (tools/site_privacy.scrub re-scanned all ~3,900 built
files on every build, every 15 min on the PC too). It now remembers files it found CLEAN by sha256(path + bytes), under a key of its
own code + the canary values (logs/site_privacy_cache.json, gitignored; LE_SCRUB_CACHE=0 = off). Measured: build 67 s cold ->
**29 s warm**, the output identical (3 builds compared file by file; only build timestamps differ); privacy area 7/7 incl.
public_build_privacy 59/59; tests.test_scrub_cache 7/7. gh_publish's mirror now copies only changed files (was: delete the whole
Pages copy + copy all, so git re-hashed ~280 MB each publish).

Lead-only, optional (tools/build_web_dashboard.py, ~4-6 s more):
- lines 945, 1123, 1183, 1212: `json.dump(obj, fh, separators=(",", ":"), default=str)` -> `fh.write(json.dumps(obj, separators=(",", ":"), default=str))`
  (json.dump streams thousands of small chunks; dumps is one C pass: the 6 dumps took 6.7 s, ~2x faster as one string; data.json is 8.6 MB).
- `_runs()` (6.7 s) rewrites all 2,345 runs/<id>.json every build: skip the write when `os.path.exists(dst)` holds the same bytes
  (it already computes `blob`), and do not `rmtree(dest)` first (remove only ids that are gone).
- 9 helper subprocesses (8.9 s, premarket brief, weekly review ...): fine as they are.
The two unreferenced brand sources (olympus/brand/olympus-logo-source.png 901 KB, -1024.png 445 KB) are loaded by no page: they only
cost publish bytes (skip them in the build when convenient).
