"""Every real fill in the day folder (day-zeroerr 2026-11-26, lead: "every real fill, entry AND exit, every lane"), BLITZ paper
rows, and the extra accounts in the day summary. Temp folders only.

    python -X utf8 -m tests.test_fill_log
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:800]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


DAY = "2026-11-20"
LIT_T = ts(2026, 11, 20, 6, 16)
ATL_T = ts(2026, 11, 20, 3, 45)
REAL_A, REAL_B, REAL_X = "MFFUEVBLD50K00006018", "MFFUSFRPD25K0000025", "MFFUEVBLD25K0000778"


def _line(t_ms, acct, cmd, tag=""):
    e = dt.datetime.fromtimestamp(t_ms / 1000, ET)
    return f"{e:%Y-%m-%d %H:%M:%S} ET  {acct}  oif_le_{tag}{t_ms}_1.txt  {cmd}\n"


def setup(root):
    logs, es, data = os.path.join(root, "logs"), os.path.join(root, "logs", "exec_audit"), os.path.join(root, "data")
    for d in (logs, es, data):
        os.makedirs(d, exist_ok=True)
    L, A, X = f"LE{LIT_T}ab12", f"LE{ATL_T}cd34", f"LE{LIT_T}ef56"
    with open(os.path.join(logs, "ninjatrader_oif.log"), "w") as fh:            # the main 50K (LIT)
        fh.write(_line(LIT_T * 1000 + 3200, REAL_A, f"PLACE;{REAL_A};MNQ 12-26;BUY;1;MARKET;0;0;DAY;;{L}E;;"))
        fh.write(_line(LIT_T * 1000 + 3900, REAL_A, f"PLACE;{REAL_A};MNQ 12-26;SELL;1;STOPMARKET;0;27735.25;DAY;{L}O;{L}S;;"))
        fh.write(_line(LIT_T * 1000 + 3900, REAL_A, f"PLACE;{REAL_A};MNQ 12-26;SELL;1;LIMIT;28174;0;DAY;{L}O;{L}T;;"))
        fh.write(_line(LIT_T * 1000 + 900000, REAL_A, f"CHANGE;;;;1;;0;27786.25;;;{L}S;;"))      # breakeven move
    with open(os.path.join(logs, "ninjatrader_oif_acctb.log"), "w") as fh:      # ATLAS funded (account B)
        fh.write(_line(ATL_T * 1000 + 4100, REAL_B, f"PLACE;{REAL_B};MNQ 12-26;SELL;1;MARKET;0;0;DAY;;{A}E;;", "acctb_"))
        fh.write(_line(ATL_T * 1000 + 4800, REAL_B, f"PLACE;{REAL_B};MNQ 12-26;BUY;1;STOPMARKET;0;26420;DAY;{A}O;{A}S;;", "acctb_"))
        fh.write(_line(ATL_T * 1000 + 4800, REAL_B, f"PLACE;{REAL_B};MNQ 12-26;BUY;1;LIMIT;26124;0;DAY;{A}O;{A}T;;", "acctb_"))
    with open(os.path.join(logs, "ninjatrader_oif_b25k_2.log"), "w") as fh:     # an extra account (25K #2): a closed-at-time exit
        fh.write(_line(LIT_T * 1000 + 3300, REAL_X, f"PLACE;{REAL_X};MNQ 12-26;BUY;1;MARKET;0;0;DAY;;{X}E;;", "b25k_2_"))
        fh.write(_line(ts(2026, 11, 20, 15, 55) * 1000, REAL_X, f"CLOSEPOSITION;{REAL_X};MNQ 12-26;;;;;;;;;;", "b25k_2_"))
    st = [{"id": f"{L}E", "state": "FILLED", "filled": 1, "avg": 27784.75, "mtime": LIT_T + 3.4},
          {"id": f"{L}S", "state": "ACCEPTED", "filled": 0, "avg": None, "mtime": LIT_T + 4.1},
          {"id": f"{L}T", "state": "FILLED", "filled": 1, "avg": 28174.0, "mtime": LIT_T + 7200},
          {"id": f"{L}S", "state": "CANCELLED", "filled": 0, "avg": None, "mtime": LIT_T + 7200.2},
          {"id": f"{A}E", "state": "FILLED", "filled": 1, "avg": 26380.75, "mtime": ATL_T + 4.6},
          {"id": f"{A}T", "state": "FILLED", "filled": 1, "avg": 26124.0, "mtime": ATL_T + 3000},
          {"id": f"{X}E", "state": "FILLED", "filled": 1, "avg": 27785.5, "mtime": LIT_T + 3.6}]
    with open(os.path.join(es, "orders.jsonl"), "w") as fh:
        for r in st:
            fh.write(json.dumps(r) + "\n")
    json.dump({f"{L}E": {"entry_t": LIT_T, "fill_px": 27784.75, "sent_at": LIT_T + 3.1, "ref": 27784.0, "dir": 1,
                         "send_at": LIT_T + 3.15, "ack_at": LIT_T + 3.3, "fill_seen_at": LIT_T + 3.6},
               f"{A}E": {"entry_t": ATL_T, "fill_px": 26380.75, "sent_at": ATL_T + 4.0, "ref": 26382.0, "dir": -1, "lane": "acctb"}},
              open(os.path.join(es, "legs.json"), "w"))
    json.dump({"ledger": [{"id": "b1", "day": DAY, "entry_t": ts(2026, 11, 20, 10, 5), "dir": 1, "qty": 2, "entry": 27800,
                           "exit_t": ts(2026, 11, 20, 10, 20), "exit": 27810, "exit_kind": "TARGET", "usd": 36.2}],
               "ledger50": [{"id": "c1", "day": DAY, "entry_t": ts(2026, 11, 20, 11, 0), "dir": -1, "qty": 1, "entry": 27820}]},
              open(os.path.join(data, "blitz_state.json"), "w"))
    return L, A, X


def t_fills(root):
    print("1. every lane, entries AND exits, slippage, times", flush=True)
    from engine import datapipe as DP
    L, A, X = setup(root)
    rows = DP.day_fills(DAY, root=root, names=(REAL_A, REAL_B, REAL_X))
    by = {r["order_id"]: r for r in rows}
    check("the main 50K, ATLAS funded (its own log) and the 25K #2 are all there", {f"{L}E", f"{A}E", f"{X}E"} <= set(by), sorted(by))
    e = by.get(f"{L}E", {})
    check("LIT entry: lane, side, qty, MARKET, intended 27,784 (the adapter's ref), filled 27,784.75, +3 ticks worse",
          e.get("lane") == "zlarior" and e.get("side") == "BUY" and e.get("qty") == 1 and e.get("order_type") == "MARKET"
          and e.get("intended_px") == 27784.0 and e.get("fill_px") == 27784.75 and e.get("slip_ticks") == 3.0, e)
    check("...one schema with big-execution: the leg's own send_at / ack_at / fill_seen_at win (send 3.15, ack 3.30, seen 3.60), "
          "fill_t = NinjaTrader's fill report, model_px = intended_px (alias), ack_s_after_send",
          e.get("signal_t") == LIT_T and abs(e.get("send_t") - (LIT_T + 3.15)) < 0.001 and abs(e.get("ack_t") - (LIT_T + 3.3)) < 0.001
          and abs(e.get("fill_seen_t") - (LIT_T + 3.6)) < 0.001 and abs(e.get("fill_t") - (LIT_T + 3.4)) < 0.01
          and e.get("model_px") == e.get("intended_px") == 27784.0 and e.get("ack_s_after_send") == 0.15, e)
    check("...the old fields kept from the OIF stamp (sent_s_after_open 3.2, fill_s_after_sent 0.2)",
          e.get("sent_s_after_open") == 3.2 and e.get("fill_s_after_sent") == 0.2, e)
    a0 = by.get(f"{A}E", {})
    check("...no leg timestamps (ATLAS here): send_t = the OIF file stamp, ack_t from the archive (None: it filled first)",
          abs(a0.get("send_t", 0) - (ATL_T + 4.1)) < 0.01 and a0.get("ack_t") is None and "fill_seen_t" not in a0, a0)
    t = by.get(f"{L}T", {})
    check("LIT exit (target LIMIT 28,174): leg target, filled at its price, 0 ticks", t.get("leg") == "target" and t.get("fill_px") == 28174.0
          and t.get("slip_ticks") == 0.0 and t.get("side") == "SELL", t)
    s = by.get(f"{L}S", {})
    check("LIT stop: its intended price is the breakeven CHANGE (27,786.25), ack_t = when it was working, CANCELLED (OCO)",
          s.get("intended_px") == 27786.25 and s.get("state") == "CANCELLED" and s.get("ack_t") == LIT_T + 4.1 and s.get("fill_px") is None, s)
    a = by.get(f"{A}E", {})
    check("ATLAS Nov 20 entry (was missing): lane atlas, SELL filled 26,380.75 vs 26,382 = +5 ticks worse",
          a.get("lane") == "atlas" and a.get("fill_px") == 26380.75 and a.get("slip_ticks") == 5.0, a)
    check("ATLAS exit fill (target)", by.get(f"{A}T", {}).get("fill_px") == 26124.0 and by[f"{A}T"].get("lane") == "atlas")
    check("big-exitreal's per-entry columns come from the same stop / target rows (one source): LIT entry stop_px = the moved stop "
          "27,786.25, target_px 28,174, exit_order target filled 28,174, 0 ticks; ATLAS's target exit too",
          e.get("stop_px") == 27786.25 and e.get("target_px") == 28174.0 and e.get("exit_order") == "target"
          and e.get("exit_fill_px") == t.get("fill_px") == 28174.0 and e.get("exit_slip_ticks") == t.get("slip_ticks")
          and e.get("exit_fill_t") == t.get("fill_t") and a.get("exit_order") == "target" and a.get("exit_fill_px") == 26124.0
          and "exit_order" not in t, (e, a))
    cl = [r for r in rows if r.get("leg") == "close"]
    check("the 25K #2's CLOSEPOSITION at 15:55 is a row (lane b25k_2, no price: NinjaTrader has none)",
          len(cl) == 1 and cl[0]["lane"] == "b25k_2" and cl[0].get("fill_px") is None and cl[0]["order_type"] == "CLOSEPOSITION", cl)
    blob = json.dumps(rows)
    check("account names masked (no full NinjaTrader name)", not any(n in blob for n in (REAL_A, REAL_B, REAL_X)) and "6018" in blob)
    check("every row has the one schema's keys", all(set(DP.FILL_FIELDS) >= set(k for k in r if k in DP.FILL_FIELDS) for r in rows)
          and all(k in e for k in ("lane", "leg", "intended_px", "slip_ticks", "signal_t", "send_t", "ack_t", "fill_t")))


def t_readers(root):
    print("2. the older readers and the LIT audit keep their meaning", flush=True)
    from engine import fill_audit as FA
    es = os.path.join(root, "logs", "exec_audit")
    lb = FA._legs_by_entry(es)
    check("the LIT fill audit never takes another lane's leg (ATLAS's 'lane' leg is out)", ATL_T not in lb and LIT_T in lb, sorted(lb))
    from engine import datapipe as DP
    d = os.path.join(root, "day")
    os.makedirs(d, exist_ok=True)
    rows = DP.day_fills(DAY, root=root)
    import gzip
    with gzip.open(os.path.join(d, "fills.jsonl.gz"), "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    from tools import reconcile_live as RL
    fl = {int(r["entry_t"]): r for r in RL._jl(os.path.join(d, "fills.jsonl.gz")) if r.get("entry_t") is not None
          and r.get("leg", "entry") == "entry" and r.get("lane", "zlarior") in ("zlarior", None)}
    check("reconcile_live's filter: the main account's ENTRY per entry_t (not its target row, not the 25K #2's)",
          fl.get(LIT_T, {}).get("order_id", "").endswith("E") and fl[LIT_T].get("lane") == "zlarior", fl.get(LIT_T))
    src = open(os.path.join(ROOT, "tools", "fill_speed.py")).read()
    check("fill_speed reads entries only", 'r.get("leg", "entry") == "entry"' in src)


def t_blitz(root):
    print("3. BLITZ paper rows in the day folder", flush=True)
    from engine import datapipe as DP
    rows = DP.ledger_rows(root=root, exec_store=os.path.join(root, "logs", "exec_audit"))
    b = [r for r in rows if r.get("bot") == "blitz"]
    check("both BLITZ paper ledgers, acct acctc, mode paper", sorted(r["src"] for r in b) == ["blitz50_paper", "blitz_paper"]
          and all(r["acct"] == "acctc" and r["mode"] == "paper" for r in b), b)
    tr = DP.day_trades(DAY, rows)
    check("they land in that day's trades.jsonl rows", sum(1 for r in tr if r.get("bot") == "blitz") == 2, len(tr))


def t_eod():
    print("4. the day summary lists the extra accounts too", flush=True)
    from tools import pc_guard as G
    now = ts(2026, 11, 24, 16, 21)
    snap = {"t": now, "hb_age": 60, "mode": "LIVE",
            "live": {"board": {"lit": {"plan": "MFFU Builder 50K", "today_pnl": 120.0, "week_pnl": 40.0, "trades_today": 1, "to_target": 3200,
                                       "room": 1500, "mll": 2000}}},
            "hb": {"acct": {"eval": {"days": {}},
                            "accounts": [{"id": "b25k_2", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K", "kind": "eval",
                                          "account": {"adapter": "ninjatrader", "kind": "live"}, "day_pnl": -40.0,
                                          "eval": {"days": {"2026-11-18": 24.0, "2026-11-23": 10.0, "2026-11-24": -40.0}},
                                          "plan_rules": {"start": 25000, "target": 1500}, "trades": [{"day": "2026-11-24"}]},
                                         {"id": "rapid", "name": "Rapid EOD 25K", "plan": "Rapid 25K", "kind": "eval",
                                          "account": {"adapter": "paper", "kind": "paper"}, "day_pnl": 0}]}}}
    m = G.day_summary(snap, now, {})
    b = m[0]["body"] if m else ""
    check("the 25K #2 line: today, week, month, trades, to pass", "Zlarior 25K #2: -$40 today, -$30 week, -$6 month, 1 trade, $1,506 to pass" in b, b)
    snap["live"]["board"]["blitz"] = {"name": "BLITZ", "plan": "25K", "today_pnl": 999.0, "week_pnl": 999.0, "configured": True}
    mb = G.day_summary(snap, now, {})
    wb = G.weekly_report(snap, ts(2026, 11, 27, 17, 5), {}, reviews_path=os.devnull)
    check("BLITZ (hidden, paper) is never in the day summary or the week report",
          mb and "BLITZ" not in mb[0]["body"] and "999" not in mb[0]["title"] and all("BLITZ" not in w["body"] for w in wb), (mb, wb))
    snap["live"]["board"].pop("blitz")
    check("a paper lane is left out; the total adds the extra account", "Rapid" not in b and m and m[0]["title"].endswith("+$80"), (b, m and m[0]["title"]))


def main():
    tmp = tempfile.mkdtemp(prefix="filllog_")
    try:
        for f in (lambda: t_fills(tmp), lambda: t_readers(tmp), lambda: t_blitz(tmp), t_eod):
            try:
                f()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check("suite ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nfill log: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
