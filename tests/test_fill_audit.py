"""Execution-quality tracker (engine/fill_audit.py): synthetic fills against the real LIT backtest of seven October 2026 days
(data/NQ_5m.csv + NQ_1m.csv), in a temp store. No broker, no network: pushes go to a list.

  good fill      2026-10-01  NinjaTrader fill at the backtest's price, target filled at the target: 0 ticks, $0
  slipped fill   2026-10-02  entry 6 ticks worse, target limit at the tick-rounded price: slippage $ and a push
  missed (feed)  2026-10-13  the bot held the entry back (feed stale) while running: missed $ = the backtest's, a push
  refused        2026-10-06  the broker refused the entry: missed, reason "refused"
  PC off         2026-10-08  no record of the bot that day: missed, pc_on unknown, no push
  qty mismatch   2026-10-07  paper, 3 micros vs the backtest's 1: size effect, not an execution cost
  extra trade    2026-10-15  the bot traded, the backtest did not
Plus collect() from a fake bot, the session alert for a held-back entry, the heartbeat block, the PC endpoint.

  python -X utf8 -m tests.test_fill_audit
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

from engine import fill_audit as fa

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def _w(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def main() -> bool:
    tmp = tempfile.mkdtemp(prefix="fa_")
    try:
        d5, d1 = fa.load_bars()
        P = fa._params()
        days = ["2026-10-01", "2026-10-02", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-13", "2026-10-15"]
        bt = {}
        for day in days:
            r = fa.replay_day(day, d5, d1, P)
            bt[day] = r["trades"][0] if r["trades"] else None
        need = {d: bt[d] is not None for d in days if d != "2026-10-15"}
        check("the backtest trades on the six trade days and not on 2026-10-15", all(need.values()) and bt["2026-10-15"] is None,
              {d: (t or {}).get("entry_t") for d, t in bt.items()})
        if not all(need.values()):
            return False
        ledger, orders, journal = [], [], []

        def entry_row(t, qty, fill=None, adapter="ninjatrader", ok=True, err=None, lag=3):
            side = "buy" if t["dir"] == 1 else "sell"
            res = {"ok": ok, "adapter": adapter}
            if not ok:
                res["error"] = err
            elif fill is not None:
                res["legs"] = [{"filled": qty, "fill_px": fill, "ok": True}]
            return {"t": t["entry_t"] + lag, "side": side, "qty": qty, "stop": t["stop"], "target": t["target"], "entry": t["entry"],
                    "entry_t": t["entry_t"], "result": res, "adapter": adapter}

        def exit_row(t, qty):
            return {"t": t["exit_t"] + 5, "side": "exit", "qty": qty, "reason": t["exit_reason"], "pnl": t["pnl"], "entry_t": t["entry_t"],
                    "exit_t": t["exit_t"], "result": {"ok": True}}

        # good fill: fill = the backtest's entry, the target order filled at the target
        g = bt["2026-10-01"]
        ledger += [entry_row(g, g["qty"], fill=g["entry"]), exit_row(g, g["qty"])]
        orders.append({"id": f"LE{g['entry_t']}AB12MT", "state": "FILLED", "filled": g["qty"], "avg": g["target"], "mtime": g["exit_t"] + 2})
        if g.get("be_t"):
            ledger.append({"t": g["be_t"] + 20, "side": "modify", "qty": g["qty"], "stop": g["entry"], "reason": "BE", "entry_t": g["entry_t"],
                           "result": {"ok": True}})
        # slipped: entry 6 ticks worse; the target limit sits at the tick price rounded toward the entry
        s = bt["2026-10-02"]
        s_fill = s["entry"] + 6 * fa.TICK * s["dir"]
        s_tgt = (int(s["target"] / fa.TICK) * fa.TICK) if s["dir"] == 1 else (-int(-s["target"] / fa.TICK) * fa.TICK)
        ledger += [entry_row(s, 2, fill=s_fill), exit_row(s, 2)]
        orders.append({"id": f"LE{s['entry_t']}CD34MT", "state": "FILLED", "filled": 2, "avg": s_tgt, "mtime": s["exit_t"] + 2})
        # refused by the broker
        rf = bt["2026-10-06"]
        ledger.append(entry_row(rf, rf["qty"], ok=False, err="REFUSED: NinjaTrader reports every connection DISCONNECTED"))
        # qty mismatch: paper, 3 micros vs the backtest's
        q = bt["2026-10-07"]
        ledger += [entry_row(q, q["qty"] + 2, adapter="paper"), exit_row(q, q["qty"] + 2)]
        journal.append({"source": "pc", "day": "2026-10-07", "entry_t": q["entry_t"], "exit_t": q["exit_t"], "side": "LONG" if q["dir"] == 1 else "SHORT",
                        "entry_px": q["entry"], "stop_px": q["stop"], "target_px": q["target"], "exit_px": q["exit_price"], "exit": q["exit_reason"],
                        "qty": q["qty"] + 2, "pnl": 0.0})
        # extra: a paper trade on a day the backtest has none
        x_et = fa._ts("2026-10-15", 10, 0)
        xt = {"entry_t": x_et, "dir": 1, "stop": 25000.0, "target": 25100.0, "entry": 25050.0, "exit_t": x_et + 1800, "exit_reason": "STOP", "pnl": -203.8}
        ledger += [entry_row(xt, 2, adapter="paper"), exit_row(xt, 2)]
        # missed while the PC was on: the bot's own note (feed stale) + uptime samples around the entry
        m = bt["2026-10-13"]
        notes = {"blocked": {str(m["entry_t"]): {"reason": "feed stale", "t": m["entry_t"] + 60, "running": True}},
                 "uptime": [{"t": m["entry_t"] - 120, "running": True, "blocked": True, "feed_block": "NinjaTrader 1m 5 min old", "kill": False},
                            {"t": m["entry_t"] + 120, "running": True, "blocked": True, "feed_block": "NinjaTrader 1m 5 min old", "kill": False}]}
        os.makedirs(tmp, exist_ok=True)
        _w(os.path.join(tmp, "ledger.jsonl"), ledger)
        _w(os.path.join(tmp, "orders.jsonl"), orders)
        fa._write_json(os.path.join(tmp, "notes.json"), notes)
        jp = os.path.join(tmp, "journal.jsonl")
        _w(jp, journal)

        now = fa._ts("2026-10-16", 12, 0)
        rep = fa.audit(store=tmp, days=days, bars=(d5, d1), params=P, journal_path=jp, now=now)
        R = {r["day"]: r for r in rep["rows"]}
        rg = R.get("2026-10-01") or {}
        check("good fill: matched, entry 0 ticks, exit 0 ticks, slippage $0, execution $0",
              rg.get("status") == "matched" and rg.get("entry_slip_ticks") == 0 and rg.get("exit_slip_ticks") == 0 and rg.get("slip_usd") == 0
              and abs(rg.get("exec_usd", 9)) < 0.01, rg)
        check("good fill: latency 3 s from the 1m CISD close, qty equal, no notes about qty",
              rg.get("latency_s") == 3 and rg.get("live_qty") == rg.get("bt_qty") and not rg.get("qty_diff"), rg)
        if g.get("be_t"):
            check("good fill: breakeven move 20 s after the backtest's", rg.get("be_delay_s") == 20, rg)
        rs = R.get("2026-10-02") or {}
        ex_ticks = round((s["target"] - s_tgt) * s["dir"] / fa.TICK, 2)
        check("slipped fill: entry +6 ticks = -$6 on 2 micros", rs.get("entry_slip_ticks") == 6.0 and rs.get("entry_slip_usd") == -6.0, rs)
        check("slipped fill: target rounded to the tick costs its fraction of a tick", rs.get("exit_slip_ticks") == ex_ticks
              and abs((rs.get("exit_slip_usd") or 0) + ex_ticks * 0.5 * 2) < 0.01, rs)
        check("slipped fill: execution $ = real P&L - the backtest at 2 micros", abs((rs.get("exec_usd") or 0) - (rs["live_pnl"] - rs["bt_pnl_live_qty"])) < 0.01
              and rs["exec_usd"] < 0, rs)
        check("slipped fill: qty 2 vs the backtest's -> size effect noted, not counted as slippage",
              rs.get("qty_diff") == 2 - s["qty"] if s["qty"] != 2 else not rs.get("qty_diff"), rs)
        rm = R.get("2026-10-13") or {}
        check("missed (feed stale, PC on): reason and the backtest $", rm.get("status") == "missed" and rm.get("pc_on") is True
              and rm.get("reason") == "feed stale" and rm.get("missed_usd") == round(m["pnl"], 2), rm)
        rr = R.get("2026-10-06") or {}
        check("refused entry: missed with the broker's reason", rr.get("status") == "missed" and str(rr.get("reason")).startswith("refused: REFUSED"), rr)
        ro = R.get("2026-10-08") or {}
        check("PC off: missed, pc_on unknown, reason says no record", ro.get("status") == "missed" and ro.get("pc_on") is None
              and "PC bot off" in str(ro.get("reason")), ro)
        rq = R.get("2026-10-07") or {}
        check("qty mismatch: +2 micros, size effect $ = backtest per micro x 2, execution $0 (paper fills at the model price)",
              rq.get("qty_diff") == 2 and abs((rq.get("size_effect_usd") or 0) - round((q["pnl"] + fa.COMM * q["qty"]) / q["qty"] * 2 - fa.COMM * 2, 2)) < 0.02
              and abs(rq.get("exec_usd", 9)) < 0.01 and any("qty" in n for n in rq.get("notes") or []), rq)
        re_ = R.get("2026-10-15") or {}
        check("extra trade: the bot traded, the backtest did not", re_.get("status") == "extra" and re_.get("live_qty") == 2, re_)
        S = rep["summary"]
        check("summary: 3 matched, 3 missed (2 with the PC on: feed stale, refused), 1 extra", S["trades"] == 3 and S["missed"] == 3 and S["missed_pc_on"] == 2
              and S["extra"] == 1, {k: S[k] for k in ("trades", "missed", "missed_pc_on", "extra")})
        check("summary: slippage $ total and per trade add up", abs(S["slip_usd"] - sum(R[d]["slip_usd"] for d in ("2026-10-01", "2026-10-02", "2026-10-07"))) < 0.01
              and abs(S["slip_usd_per_trade"] - S["slip_usd"] / 3) < 0.01, S)
        check("summary: missed $ = the three backtest trades", abs(S["missed_usd"] - round(m["pnl"] + rf["pnl"] + bt["2026-10-08"]["pnl"], 2)) < 0.02, S)
        check("summary: one month row for October, a headline", [x["month"] for x in S["months"]] == ["2026-10"] and "audited" in S["text"], S["months"])
        check("summary: 1 trade slipped more than 4 ticks", S["slipped"] == 1 and S["worst"]["day"] == "2026-10-02", S["worst"])
        check("report + summary files written", os.path.exists(os.path.join(tmp, "report.json")) and os.path.exists(os.path.join(tmp, "summary.json")))

        # ---- pushes
        sent = []
        p1 = fa.alert_payloads(rep["rows"], now=s["exit_t"] + 600)
        check("push: the slipped fill (> 4 ticks) only, shortly after it", [p["key"] for p in p1] == [f"exec:slip:{s['entry_t']}"]
              and "+6 ticks" in p1[0]["body"] and p1[0]["kind"] == "pc", p1)
        p2 = fa.alert_payloads(rep["rows"], now=fa._ts("2026-10-13", 16, 30))
        check("push: the missed trade with the PC on; not the PC-off day", [p["key"] for p in p2] == [f"exec:miss:{m['entry_t']}"]
              and "feed stale" in p2[0]["body"], p2)
        k1 = fa.send_alerts(p1 + p2, store=tmp, notify=sent.append)
        k2 = fa.send_alerts(p1 + p2, store=tmp, notify=sent.append)
        check("push: each notice sent once", len(k1) == 2 and k2 == [] and len(sent) == 2, (k1, k2))

        # ---- collect() from a fake bot + the session alert for a held-back entry
        st2 = tempfile.mkdtemp(prefix="fa2_", dir=tmp)
        bt_now = fa._ts("2026-10-20", 3, 10)
        held = fa._ts("2026-10-20", 3, 4)
        lg = {"instrument": "MNQ 12-26", "qty": 3, "dir": 1, "entry_t": held - 3600, "stop": 25000.0, "stop0": 25000.0, "target": 25100.0,
              "entry_id": f"LE{held - 3600}ZZ99ME", "stop_id": "s", "target_id": "t", "status": "protected", "filled": 3,
              "fill_px": 25050.5, "fill_mtime": held - 3598, "sent_at": held - 3599}
        bot = SimpleNamespace(cfg={"adapter": "ninjatrader"}, running=True, kill=False, health={"entries_blocked": True, "feed_block": "NinjaTrader 1m stale"},
                              ledger=[{"t": held - 3597, "side": "buy", "qty": 3, "stop": 25000.0, "target": 25100.0, "entry": 25050.25,
                                       "entry_t": held - 3600, "result": {"ok": True, "adapter": "ninjatrader"}}],
                              adapter=SimpleNamespace(legs=[lg], history=[], folder=os.path.join(tmp, "no_nt")),
                              _blocked_entries={held}, log=[{"t": held + 20, "type": "risk", "text": f"Entry at {fa._hm(held)} ET NOT routed: feed stale"}])
        c = fa.collect(bot, store=st2, now=bt_now, state_path=os.path.join(tmp, "none.json"))
        c2 = fa.collect(bot, store=st2, now=bt_now + 30, state_path=os.path.join(tmp, "none.json"))
        check("collect: 1 ledger row, 1 leg, 1 held-back note; nothing twice", c["ledger"] == 1 and c["legs"] == 1 and c["notes"] == 1
              and c2["ledger"] == 0 and c2["legs"] == 0 and c2["notes"] == 0, (c, c2))
        N = fa._read_json(os.path.join(st2, "notes.json"), {})
        check("collect: the bot's reason and an uptime sample (feed blocked)", N["blocked"][str(held)]["reason"] == "feed stale"
              and N["uptime"][-1]["blocked"] and len(N["uptime"]) == 1, N)
        L = fa.live_trades(st2, journal_path=jp)
        check("live trades: the NinjaTrader leg's fill price and time", L[held - 3600]["fill_entry"] == 25050.5 and L[held - 3600]["t_fill"] == held - 3598
              and L[held - 3600]["fill_src"] == "broker", L.get(held - 3600))
        ss = []
        k = fa.session_alerts(bot, store=st2, now=bt_now, notify=ss.append)
        k_again = fa.session_alerts(bot, store=st2, now=bt_now + 60, notify=ss.append)
        check("session alert: a held-back entry while the bot runs is pushed once", k == [f"exec:miss:{held}"] and k_again == []
              and "feed stale" in ss[0]["body"], (k, ss))
        bot.running = False
        check("session alert: nothing when the bot is not running", fa.session_alerts(bot, store=st2, now=bt_now, notify=ss.append) == [])

        # ---- heartbeat block + view
        hb = fa.heartbeat_block(store=tmp)
        check("heartbeat block: small, the totals and the last rows", hb and hb["trades"] == 3 and len(json.dumps(hb)) < 4000 and len(hb["recent"]) <= 5,
              len(json.dumps(hb or {})))
        v = fa.view(store=tmp, now=now + 60)
        check("view: newest row first, summary, alert threshold", v["rows"][0]["day"] == "2026-10-15" and v["summary"]["trades"] == 3 and v["alert_ticks"] == 4, v.get("summary"))
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from engine import pcdash_api
            old = fa.STORE
            fa.STORE = tmp
            try:
                fa._write_json(os.path.join(tmp, "report.json"), {**rep, "t": 4102444800})     # fresh: no re-run inside the request
                app = FastAPI(); app.include_router(pcdash_api.router)
                r = TestClient(app).get("/api/next/pc/execution")
                check("GET /api/next/pc/execution 200 with rows and the summary", r.status_code == 200 and r.json()["summary"]["missed"] == 3
                      and len(r.json()["rows"]) == len(rep["rows"]), r.text[:300])
            finally:
                fa.STORE = old
        except ImportError as e:
            check("fastapi available for the endpoint check", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RES)
    print(f"fill audit: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
