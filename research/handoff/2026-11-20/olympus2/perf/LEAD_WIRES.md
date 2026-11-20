# LEAD_WIRES: PERF + OFFLINE (day-quality, Olympus v2, 2026-11-20)

## 1. Offline for every app (tools/web_public/sw.js, lead-only): `git apply research/handoff/2026-11-20/olympus2/perf/sw-offline.patch`

**Why:** the root worker controls every app page (scope = the site root) but `OTHER_APPS` makes it ignore every app folder, so after
one visit only Zenith, Jarvis and Kalshi open offline; the other 29 visible apps show the browser's "no internet" page (measured:
BASELINE.md, offline column).
**What the patch does (20 lines, the only change):** for a request inside an `OTHER_APPS` folder that has no worker of its own
(`OWN_WORKER` = jarvis/, kalshi/, planner/, hub/manual), answer **network first** (online: exactly as today, always fresh, no wait
added) and keep the good answer in a separate cache `le-apps-v1` (max 400 entries, oldest dropped); when the network fails, answer
the last copy (exact URL, else the same path with any `?v=`), else the existing `offlinePage()` for a page. `le-apps-v1` is not a
`le-public-*` name, so a CACHE bump keeps the apps' last copies; nothing else in the worker changes.
**Proof:** a copy of the site with the patch, 11 apps through tools/perf_sweep.py's offline pass (Zenith once, the app once, network
cut, reload): zenith, fates, ledger, inbox, demeter, aegis, nq, kalshi, jarvis, gate, hub = all `ok` (today: 3 of 11).
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

## 3. Lead-only build path: none needed for perf today

tools/build_web_dashboard.py: no change asked. The publish already gzips; the two unreferenced brand sources
(olympus/brand/olympus-logo-source.png 901 KB, olympus-logo-1024.png 445 KB, loaded by no page) only cost publish time, not phones.
