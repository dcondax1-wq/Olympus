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
- ROOT fix done too (lead 06:03 ET): `ext_hash` leaves an open trade's live $ / R out (`_news_of`: `at` open rows keep [entry_t .. kind], `board_trades`
  open rows drop usd / r / live keys). The ext is back to every 2nd run with a trade open; an entry, a moved stop / target or a close still
  posts it at once. The posted blocks still carry the live $. The grace guard stays as a backstop. Tests: test_live_publish (2 new checks, 86/86).
- The page now says the candle age plainly: the Quality card's "Chart candles: last bar 1 h 35 min ago (8:55 AM ET)" (amber after 80 min
  in the bots' hours), on top of the chart's own "These are the PC's last bars (..., ... ago)".

## H. Small wording nit (bot side, optional)
A stop moved to break-even that fills more than 1 point past the entry is called "(stop)" in the close push. Example: the live ATLAS short,
stop 26,379.50 vs entry 26,380.75, gives "closed SHORT +$2 (stop)". `_push_exit` decides "BE" only within 1.0 pt. To say "(break-even)",
use `abs(ex - fill) <= 1.0 or float(lg.get("stop") or 0) != float(lg.get("stop0") or 0)` for the BE test. That is a judgement call, so there is no proof suite for it.

## I. brief.json (helper day-brief) and N accounts
- `nq/nq.js` reads `./brief.json` when present (`nqdesk.briefFor`). A missing file, yesterday's brief or junk changes nothing.
  Its contract (docs/BRIEF.md on day-brief) was not pushed when I wrote this, so the reader takes the likely shapes:
  - `day`
  - `bias` {side|call, why|text, conf}
  - `levels` [{label|name, price|px, dist}] or [[label, px, dist]]
  - `news` [{date, time, title}]
  - `bots` as a list [{id, waiting, bias, levels}] or a map
  - `recap` (a string or {lit, atlas})
  Shown as: a "Morning brief: LONG/SHORT why" line under the bot's own lean; levels / news / waiting only where the PC's own glance has none
  (the bot's live words win); the recap in "After". When BRIEF.md lands, check the field names against `briefFor` (tests/test_nq_desk "brief" checks).
- Accounts: the strip takes N accounts from the feed. The Rapid EOD 25K arrives with PC id `rapid` and fills the planned Rapid tile. Any other PC
  account the plan file does not name gets its own tile after it. Tested in test_nq_desk (27/27).

## J. Round 2: payout readiness (board/ + trading/), and the payout-ready alert proposal (card payout-ping-1000)
**Built:** `nq/payready.js` + `nq/payready.css` (pure core + drawing), mounted on Board (`board/payready_mount.js`, after the Payouts card; board.js
dispatches `board-data`, bumped b9) and Trading (`#payReadyCard` after the accounts strip, trading.js v9, loads `business/payoutcoach.js?v=1`).
Per funded account it shows:
- eligible yes / no with the exact first reason (payoutcoach.js rules = engine/payout_coach.py)
- 6 rule rows: first-request date, traded days, cycle profit, consistency 50%, above the buffer vs the minimum, max request (with the PC's `mr`)
- "$X more / N more traded days until you can ask for $Y" (Y = the playbook's full max: $1,000 at $27,100 on the 25K)
- the projected date at the last `eq` days' pace (or "not at the recent pace")
- the inactivity line
- the 5 MFFU steps (docs/FUNDED_25K_PLAYBOOK.md section 5)
The Rapid says "rules not coded yet" (payoutcoach.js has Builder plans only). Board has no light theme (dark page), so its light screenshot looks dark.

**Fields:** none missing. mf `f` (cp, bd, cd, ef, pn, mr, ft), mf `lt` + `eq`, and the board card's balance / room are all in today's post.
One gap for later accounts: `eq` has only 8 points (EQ_N), so the pace covers at most the last 7 traded days. That is fine for a projection.

**Payout-ready alert:** it already exists. engine/lifecycle `payout_ready` and engine/funded_life push "PAYOUT READY: request" once $750 (25K) /
$1,500 (50K) sits above the buffer, through notify kind "life:" (always on, "important only"). The open card **payout-ping-1000** asks only
whether to wait for the full $1,000. Recommendation in the card: **NO** (keep $750: same money or a bit more, 2-5 trading days sooner).
If the owner taps **YES**, the whole patch is:
```diff
--- engine/funded_life.py   PLANS["builder25k"]
-                   "max_payouts": 5, "max_micros": 20, "ask_above": 750.0, "typical_day": 150.0, "price": 63.00,
+                   "max_payouts": 5, "max_micros": 20, "ask_above": 1000.0, "typical_day": 150.0, "price": 63.00,
```
- then in `tests/test_funded_life.py` line 83: `ask_at_balance == 26850` -> `27100`, and the title "payout line $26,850" -> "$27,100"
- `nq/payready.js` `PING_ABOVE.builder25k` 750 -> 1000 (the card's ping line)
- run `python -X utf8 -m tests.test_funded_life`, `tests.test_account_b_funded`, `tests.test_payready`
- set the card's status in business/decisions.json.
If NO: nothing to change (the tracker already shows the $750 ping next to the $1,000 plan).
