# nqdash3: lead-only edits

## A. Bot-side patches: put R in every CLOSE push (owner: "closed with results")
Proof: `python -X utf8 -m tests.test_alert_audit` applies these three patches IN MEMORY and passes 15/15 on every account route,
over both web push and ntfy. `--now` (the bot as it is) fails: no close push shows R on any route today. After applying them,
that suite must pass the same way, and `tests.test_trade_alerts` must stay 21/21.
They only add a keyword argument to the push payload. No order or sizing code changes. Safe to ship after today's session.

### 1. `engine/ninjatrader.py` `NinjaTraderAdapter._push_exit` (every stop / target close on every account: this push is the one that reaches the phone)
```diff
         reason = "TARGET" if name == "TARGET" else ("BE" if abs(ex - fill) <= 1.0 else "STOP")
+        risk = abs(fill - float(lg.get("stop0") or lg.get("stop") or 0))
+        rr = round((ex - fill) * lg["dir"] / risk, 2) if fill and ex and risk > 0 else None
         if lg.get("who"):                    # the combo (engine/combo50k.py): "ATLAS on Zlarior 50K: LONG closed"
             def mk(P):
                 p = P.outcome_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", reason, usd,
-                                      lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled"), who=lg["who"])
+                                      lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled"), who=lg["who"], R=rr)
 ...
         self._push(lambda P: P.outcome_payload(self._push_account(), "LONG" if lg["dir"] == 1 else "SHORT", reason, usd,
-                                               lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled")))
+                                               lg["entry_t"], int(self.clock()), src="pc", exit_px=ex, qty=x.get("filled"), R=rr))
```

### 2. `engine/account_b.py` `AccountB._push_outcome` (ATLAS time / cut / kill closes)
```diff
             p = push.outcome_payload(self.label, "LONG" if pv.get("dir") == 1 else "SHORT", reason, usd, int(et_), exit_t, src="pc",
-                                     qty=q, strategy=pv.get("short"))
+                                     qty=q, strategy=pv.get("short"),
+                                     R=round(float(usd) / (float(pv["risk_pts"]) * q * 2.0), 2) if pv.get("risk_pts") and q else None)
```

### 3. `engine/multi_account.py` `AccountRouter.notify_outcome` (extra accounts' time / day-end closes)
```diff
-                                                      pnl, tr["entry_t"], tr.get("exit_t"), src="pc", qty=qty), acc))
+                                                      pnl, tr["entry_t"], tr.get("exit_t"), src="pc", qty=qty, R=tr.get("pnl_r")), acc))
```
(`engine/live.py _push_outcome` already passes `R=tr.get("pnl_r")`: nothing to do there.)

Also add `"alert_audit"` to `AREAS["pc"]` in `tests/run_area.py`, next to `notify` (that file is shared, so I left it alone).

## B. Bot-side (PC report): post the exact time of the last trade alert (optional, the page works without it)
The Quality card's "Last trade alert" reads `live.reporter.na` (the PC's post, laid in by pc_feed.js overlayHome). Today the PC does not post it,
so the card falls back to the newest entry / exit time in the report and says so. To post the real time, in `tools/pc_report.py` `full()`:
```diff
            "reporter": {"t": snap["t"], "server": bool(snap.get("server")), "nt": snap.get("nt"), "market_open": snap.get("market_open"),
-                        "mode": snap.get("mode"), "hb_src": snap.get("hb_src"), "problems": sorted(conditions(snap))}}
+                        "mode": snap.get("mode"), "hb_src": snap.get("hb_src"), "na": last_alert_t(), "problems": sorted(conditions(snap))}}
```
and next to `instant_today`:
```python
def last_alert_t():
    """When this PC last sent a trade alert (phone app or ntfy): engine/notify's instant_sent.json keys. None when unknown. Never raises."""
    try:
        from engine import notify as _n
        k = _n._instant_state().get("keys") or {}
        return int(max(float(v) for v in k.values())) if k else None
    except Exception:  # noqa: BLE001
        return None
```
Check after: `python -X utf8 -m tests.test_public_build_privacy` (reporter goes through site_privacy.public_status; `na` is a plain time, not private)
and `python tests/run_area.py pc --only pc_report,bots_back`.

## C. Test lists (tests/run_area.py, shared)
- `AREAS["pc"]`: add `"alert_audit"` (tests/test_alert_audit.py).
- `AREAS["trading"]`: add `"nq_desk"` (tests/test_nq_desk.py, node only, 1 s).

## D. Lead-only web files: none
No `sw.js`, `build_web_dashboard.py`, `jarvis/apps.js` or APPS-table change is needed: nq/ and trading/ have no service worker of their own and
the root sw.js skips them (OTHER_APPS). The new files (`nq/nqdesk.js`, `nq/nqdesk.css`) are loaded by the pages themselves.
Version tags I bumped in my own pages: `nq/index.html` nq.js `?v=r13` (was r12), `trading/index.html` trading.js `?v=7` (was 6); new `nqdesk.css?v=1`, `nqdesk.js?v=1`.

## E. trades.json
Committed the lead's fresh export (with the PC data branch: 303 trades, z50k + atlas25f LIVE). This container cannot fetch the `data` branch, so
`tools/trading_export.py --check` here says STALE; the trading test now accepts that case (built with the data branch, everything else equal to a
local build). Re-run `python tools/trading_export.py --fetch` on a machine with the branch whenever you like: the test no longer pins its content.

## F. ATLAS edge chip "data to Oct 16 (old)": root cause + refresh plan (not done here: it moves pinned research numbers)
- `tools/edge_health.py` re-runs LIT on the newest bars, but ATLAS is the **stored run** `atlas_deep_zombie` (`atlas_trades()` -> `runlib.load`),
  built 2026-11-15 on data that ends **2026-10-16**. A fresh re-score does not help: its inputs end there too.
  - the ATLAS member trades are stored files `research/second/{ema,md,sr}_best.json` (`second_mix.second_units`)
  - the session list is the stored run `research/runs/baseline.json` (`lit_final.SESS`)
  - re-scoring the zombie variant takes 6 s, rebuilding the units 4 s (both measured here), and both still end Oct 16.
- To refresh (cloud, research files only, no bot file):
  1. re-run each ATLAS member's research backtest on `data/NQ_5m.csv` (now to 2026-11-19) -> `research/second/*_best.json`
  2. `python tools/runlib.py baseline` (the session list to Nov 19)
  3. delete `research/runs/_cache/second_mix_units.pkl`, then `python -X utf8 tools/atlas_deep.py save`
  4. `python tools/edge_health.py` -> `tools/web_public/edge.json` (ATLAS "data to" = Nov 19).
  Steps 1-2 change the H1 / H2 numbers that several suites pin (trading_page b, atlas_deep, second...): run the money, trading and nq areas after.
- Meanwhile the NQ page's Quality card shows it as a red row ("Edge check data: LIT to Nov 19 · ATLAS to Oct 16: read its PF as old").

## G. Chart candles stopped while a trade was open (04:15 -> nothing at 05:15 / 05:30 / 05:45): FIXED in `tools/pc_report.py` (tools/, not engine/)
- Cause: candles never go on a run that also sent the "ext" post (`busy_run`). An open trade changes the ext's news every run (its live $ in
  the `at` block feeds `ext_hash`), so the ext went on every run, every run was busy, and the candles starved for as long as the trade was open.
- Fix (commit on day-nqdash3): new `BARS_BUSY_GRACE_S = 900`. Once the candles are 74 min old they go on a busy run too: one extra post that run.
  The daily caps (24 chart posts, 18 candle posts, 226 all posts) are unchanged.
  `tests.test_pc_bars` 75/75, with a new "trade open all day" day: the old code sent **0** candle posts that day, the new code one about every 75 min.
- It reaches the PC with the normal auto-update (branch pc). The bot process does not use this file; it is the 15-minute reporter.
- Worth a later look: with the ext on every run, the simulation spends ntfy's daily share by ~12:20 ET (3 posts a run). The status post is
  protected, so the PC never looks silent, but the chart stops for the rest of the day. A better root fix is to leave the open trade's live $
  out of `ext_hash` (the core post already carries it). I did not make that change; it is your call.
- The page now says the candle age plainly: the Quality card's "Chart candles: last bar 1 h 35 min ago (8:55 AM ET)" (amber after 80 min
  in the bots' hours), on top of the chart's own "These are the PC's last bars (..., ... ago)".

## H. Small wording nit (bot side, optional)
A stop moved to break-even that fills more than 1 point past the entry is called "(stop)" in the close push. Example: the live ATLAS short,
stop 26,379.50 vs entry 26,380.75, gives "closed SHORT +$2 (stop)". `_push_exit` decides "BE" only within 1.0 pt. To say "(break-even)",
use `abs(ex - fill) <= 1.0 or float(lg.get("stop") or 0) != float(lg.get("stop0") or 0)` for the BE test. That is a judgement call, so there is no proof suite for it.
