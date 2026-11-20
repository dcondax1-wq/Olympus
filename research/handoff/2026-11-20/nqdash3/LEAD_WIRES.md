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
