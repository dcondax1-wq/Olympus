# LEAD WIRES (day-kalshi 2026-11-20)

## 1. tools/web_public/kalshi/sw.js (lead-only)
See `LEAD_WIRES_dashboard.md` in this folder (the helper's exact edit: CACHE = 'kalshi-' + the new kalshi.css / kalshi.js ?v,
both SHELL entries move together; k8.json network-first). Without it, cached phones keep the old K8 card.

## 2. Nothing else is required.
- No edit to build_web_dashboard.py, apps.js, the APPS table, or any live NQ file.
- `tools/web_public/kalshi/k8.json` is a committed, Claude-refreshed file (`python tools/kalshi_k8_feed.py` after
  `python research/kalshi_k8_day/fetch.py`). The PC does NOT rewrite it (a tracked file the PC rewrites breaks its git pull).
  Optional later: have the site build regenerate it into the OUTPUT folder from the PC's weekly tape (data/kalshi_live/), never into the repo.
- `tools/pc_report.py` got one small safe change (not lead-only): if the 2 ext posts are full, the Kalshi block first drops its
  new extras (last 5 bets, then edge health + day stop) instead of being cut whole.

## 3. Round 2: each leg pauses / resumes itself (OPTIONAL, not needed for Monday)
Built: `engine/kalshi_legswitch.py` (pure; rule pre-registered in research/kalshi_k8_day/PREREG_legswitch.md: last 20 windows,
pause at <= 10 won, resume at >= 12). Walk-forward Aug 3 - Nov 20 (research/kalshi_k8_day/legswitch.json): it **never fired** on
the 3 live legs (0 bets skipped, $0 either way), so by the pre-registered rule it stays **display only** (`LIVE_ON = False`); the
phone shows each leg's last 20 and "would pause". It is a free safety brake (no cost in 4 months); to make the live bot obey it,
set `LIVE_ON = True` in engine/kalshi_legswitch.py AND apply this patch to `engine/kalshi_clock.py` `def leg_limits` (the live
order path, so it is the lead's call; changing it does not change what the owner armed):

```diff
     mp = KL._f(ad.get("max_price"))
     if mp is not None and 0.02 <= mp < out["cap"]:
         out["cap"] = mp
+    try:                                             # day-kalshi round 2: the leg's own last 20 windows (engine/kalshi_legswitch)
+        from engine import kalshi_legswitch as LS
+        if LS.LIVE_ON and out["enabled"]:
+            st = LS.replay(LS.leg_results(rows(paths(state_dir)["clock_paper"]), lid))
+            if st["paused"]:
+                out["enabled"], out["why"] = False, ("paused: " + st["why"])[:80]
+    except Exception:  # noqa: BLE001
+        pass
     return out
```
Then `python -X utf8 -m tests.test_kalshi_k8_day` (a3 checks LIVE_ON against legswitch.json: flip legswitch.json's verdict note
in the REPORT if you overrule it) and `python -X utf8 -m tests.test_kalshi_clock`.
