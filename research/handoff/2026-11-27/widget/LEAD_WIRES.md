# day-widget: lead wires (2026-11-27)

NQ NOW: a new Scriptable widget for the owner's iPhone (Home Screen small / medium / large + lock screen rectangular / inline /
circular). New: `tools/web_public/widget/nq-now.js`, `tests/test_nq_now.py`, `tests/nq_now_harness.cjs`, `tests/fixtures/nq_now/`.
Changed: `tools/web_public/widget/setup.html` (NQ NOW one-tap copy first; the old Olympus widget section kept below it).
The old `olympus-widget.js` is untouched (tests.test_widget 56/56).

## Wires

1. Test area: add `"nq_now"` next to `"widget"` in tests/run_area.py (`AREAS["money"]`), and to `AREAS["nq"]` if you like.
2. `nq/ports.json` comes from origin/day-nqports (tools/nq_ports.py). Land that first or together: without it the widget simply
   shows no countdown and no ▲/▼ vs the close (it falls back to ▲/▼ vs its own last reading; tested).
3. sw.js: `widget/` is in OTHER_APPS (never cached) - nothing to do. Scriptable fetches the raw files from the site.
4. Publish. Owner's one step (his phone): open https://dcondax1-wq.github.io/widget/setup.html, tap "Copy NQ NOW + open Scriptable",
   paste, name it NQ NOW, add the widget. Put it in STATE "Waiting on the owner" only if you want it pushed to him.

## What it reads (public only)

- The PC's status post on the public ntfy topic (status_feed.json; since=70m, then latest, then 12h): price, pc.glance bots (stage n/10,
  armed), board.<bot>.position (🟢 in trade +$: unrealized_usd, else (price - entry) x dir x qty x $2 MNQ), accounts[].eval.today
  (today $), k7 (7-day last day), pc_verdict label. BLITZ never shown. Not signature-checked (Scriptable has no WebCrypto ECDSA):
  display only, same as the old widget.
- nq/ports.json: cal.events (next news / half day / roll / closed), vol.nq_close + nq_day (the arrow reference).
- Age honesty: <= 20 min "live · HH:MM ET"; 20-60 min "as of HH:MM ET" gold; > 60 min "PC silent" red + every chip 🔴;
  no network = the last real post saved in Scriptable's Documents as "Saved copy · as of HH:MM ET".
- Refresh: asks iOS for 5 min (refreshAfterDate); iOS decides the real pace.
