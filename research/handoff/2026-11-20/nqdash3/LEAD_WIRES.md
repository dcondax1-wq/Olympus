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
