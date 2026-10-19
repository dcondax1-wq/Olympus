"""PC dashboard live pages: /api/next/pc/status, /api/next/pc/account, /api/next/pc/trade/<entry_t>, /api/next/extras
(engine/pcdash_api.py). A fake PC bot (no loop, no broker), a temp journal and a temp state file; every route is a GET and
must leave the bot untouched.

  python -X utf8 -m tests.test_pcdash_api
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine import lit_learn, pcdash_api
from engine.live import LiveBot

ET = ZoneInfo("America/New_York")


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def fake_bot(tmp, account="MFFUEVAL123", env="live", kill=False, stale=False, running=True):
    now = ts(2026, 10, 20, 9, 40)
    b = LiveBot()
    b.state_path = os.path.join(tmp, "live_state.json")
    b.clock = lambda: now
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "eval_start": "2026-10-19", "eval_prior_pnl": -100,
             "webhook_url": "https://hooks.example/SECRET-TOKEN", "model": "lit", "data_source": "ninjatrader"}
    b._lit_sizing = {"eval_start": "2026-10-19", "eval_prior_pnl": -100}
    b._eval_prev = {"2026-10-19": 1450.0}
    b.running, b.kill, b.started_at, b.last_poll = running, kill, now - 7200, now - 20
    e1, e2 = ts(2026, 10, 20, 3, 5), ts(2026, 10, 20, 8, 35)
    oif = r"C:\Users\Owner\Documents\NinjaTrader 8\incoming\oif_LE_1.txt"
    b.ledger = [
        {"t": e1 + 3, "sym": "NQ", "side": "buy", "qty": 12, "stop": 24990.0, "target": 25150.0, "entry": 25020.0, "entry_t": e1,
         "result": {"ok": True, "adapter": "ninjatrader", "legs": [{"filled": 12, "fill_px": 25020.5, "ok": True}]}},
        {"t": e1 + 1800, "sym": "NQ", "side": "modify", "qty": 12, "stop": 25020.5, "reason": "BE", "entry_t": e1,
         "result": {"ok": False, "error": f"stop change REJECTED: see {oif}"}},
        {"t": e1 + 3600, "sym": "NQ", "side": "exit", "qty": 12, "reason": "BE", "pnl": -22.8, "entry_t": e1, "exit_t": e1 + 3600,
         "result": {"ok": True}},
        {"t": e2 + 3, "sym": "NQ", "side": "sell", "qty": 8, "stop": 25110.0, "target": 24900.0, "entry": 25070.0, "entry_t": e2,
         "result": {"ok": True, "legs": [{"filled": 8, "fill_px": 25069.75, "ok": True}]}},
    ]
    b.log.appendleft({"t": e1 - 600, "type": "risk", "text": "Entry at 02:55 ET NOT routed: feed stale"})
    b._open_routed, b._open_qty = e2, 8
    b.state = {"model": "lit", "price": 25050.0, "t": now - 360, "day_trades": 1, "setups": {},
               "model_state": "LIT: IN TRADE SHORT @ 25,070.00 | stop 25,110.00 | target 24,900.00",
               "position": {"entry_t": e2, "dir": -1, "qty": 9, "stop": 25110.0, "stop0": 25110.0, "target": 24900.0,
                            "entry": 25070.0, "risk_pts": 40.0, "be": False, "target_label": "VIX band low"},
               "lit": {"signals_today": [{"t": e2 - 600, "dir": -1, "swept": ["pdh", "asia20_h"], "limit_px": 25070.0, "stop_px": 25110.0,
                                          "target_px": 24900.0, "risk_pts": 40.0, "rr": 4.25}]},
               "eval_2wk": {"session": 2, "limit": 10, "status": "open", "text": "session 2 of 10, 9 left"}}
    b.health.update({"data_source": "ninjatrader", "stale": stale, "market_open": True, "last_bar_t": now - (2400 if stale else 600),
                     "last_1m_bar_t": now - (2400 if stale else 120), "last_ok_poll": now - 20, "poll_ms": 500})
    b.adapter = SimpleNamespace(name="ninjatrader", account=account, env=env, disabled=None, last_error=None, killed=False,
                                legs=[{"entry_t": e2, "dir": -1, "fill_px": 25069.75, "stop": 25110.0, "target": 24900.0,
                                       "status": "protected", "filled": 8, "instrument": "MNQ 12-26", "stop0": 25110.0}],
                                connections=lambda: {"Tradovate": "CONNECTED"}, folder_status=lambda: {"incoming": True, "outgoing": True})
    bars = pd.DataFrame({"time": [now - 3 * 3600 + 60 * i for i in range(180)]})
    bars["open"] = 25060.0
    bars["high"], bars["low"], bars["close"] = 25064.0, 25052.25, 25058.5
    b.bars_tail = [{"time": int(t), "open": 25060.0, "high": 25065.0, "low": 25050.0, "close": 25055.0, "volume": 1}
                   for t in range(now - 6 * 3600, now - 300, 300)]
    b._lit_1m_store = bars
    return b, now


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_pcdash_")
    results = []

    def check(name, cond, info=""):
        results.append(bool(cond))
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""))

    old_bot, old_jp = pcdash_api._bot, lit_learn.JOURNAL_PATH
    try:
        jp = os.path.join(tmp, "journal.jsonl")
        rp = os.path.join(pcdash_api.LAB, "replays.json")
        chart_rec = None
        if os.path.exists(rp):                                      # a real replay chart: the routed trade links to it
            ch = json.load(open(rp, encoding="utf-8")).get("charts") or {}
            k = sorted(ch)[-1]
            chart_rec = (k, ch[k]["day"], int(ch[k]["entry"]["t"]))
        with open(jp, "w", encoding="utf-8") as fh:
            rows = [{"source": "pc", "key": "a", "day": "2026-10-19", "entry_t": ts(2026, 10, 19, 4, 10), "exit_t": ts(2026, 10, 19, 6, 0),
                     "side": "LONG", "qty": 10, "entry_px": 24800, "stop_px": 24770, "target_px": 25040, "exit_px": 25040, "exit": "TARGET",
                     "r": 8.0, "pnl": 1450.0, "risk_pts": 30}]
            rows.append({"source": "pc", "key": "f", "day": "2026-10-12", "entry_t": ts(2026, 10, 12, 5, 0), "exit_t": ts(2026, 10, 12, 6, 0),
                         "side": "LONG", "qty": 2, "entry_px": 25000, "stop_px": 24960, "target_px": 25200, "exit": "STOP", "r": -1, "pnl": -165, "risk_pts": 40})
            if chart_rec:
                rows.append({"source": "pc", "key": "c", "day": chart_rec[1], "entry_t": chart_rec[2], "exit_t": chart_rec[2] + 3600,
                             "side": "SHORT", "qty": 3, "entry_px": 1, "stop_px": 2, "target_px": 0, "exit": "STOP", "r": -1, "pnl": -100, "risk_pts": 1})
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        lit_learn.JOURNAL_PATH = jp
        bot, now = fake_bot(tmp)
        pcdash_api._bot = lambda: bot
        app = FastAPI()
        app.include_router(pcdash_api.router)
        cl = TestClient(app)
        before = copy.deepcopy(bot.ledger)

        # ---- /api/next/pc/status
        r = cl.get("/api/next/pc/status")
        s = r.json()
        check("status 200", r.status_code == 200, r.text[:200])
        check("status: TRADING YOUR EVAL on a live NinjaTrader account", s["verdict"]["code"] == "TRADING" and s["verdict"]["label"] == "TRADING YOUR EVAL", s["verdict"])
        check("status: account, feed age, last poll, LIT stage", s["health"]["account"]["name"] == "MFFUEVAL123" and s["health"]["feed"]["age_1m_s"] == 60
              and s["health"]["poll"]["age_s"] == 20 and s["health"]["lit"]["stage"] == "trade", s["health"])
        check("status: setups seen today", len(s["setups_today"]) == 1 and s["setups_today"][0]["side"] == "SHORT" and "PDH" in s["setups_today"][0]["level"], s["setups_today"])
        check("status: no secrets", "SECRET" not in r.text, "")
        for label, kw, code in (("Sim101 -> ON SIM", {"account": "Sim101", "env": "demo"}, "SIM"), ("kill switch -> DISABLED", {"kill": True}, "DISABLED"),
                                ("stale feed in session -> FEED STALE", {"stale": True}, "FEED"), ("bot stopped -> DISABLED", {"running": False}, "DISABLED")):
            b2, _ = fake_bot(tmp, **kw)
            check("status: " + label, pcdash_api.status_view(b2)["verdict"]["code"] == code, pcdash_api.status_view(b2)["verdict"])
        idle = LiveBot()
        idle.state_path = os.path.join(tmp, "none.json")
        check("status: a never-started bot answers (DISABLED: bot stopped)", pcdash_api.status_view(idle)["verdict"]["code"] == "DISABLED")

        # ---- /api/next/pc/account
        r = cl.get("/api/next/pc/account")
        a = r.json()
        ev = a.get("eval") or {}
        check("account 200", r.status_code == 200, r.text[:200])
        check("eval: balance counts the prior -$100 and routed P&L", ev.get("balance") == 50000 - 100 + 1450 - 22.8 and ev.get("prior") == -100, ev)
        check("eval: trailing floor, room, session N of 10, daily loss used",
              ev.get("floor") is not None and ev.get("room") == round(ev["balance"] - ev["floor"], 2) and ev.get("session") == 2
              and ev.get("sessions") == 10 and ev.get("dll_used") == 22.8, ev)
        check("account: LIVE badge from the bot's health block", a["account"]["badge"] == "LIVE", a["account"])
        p = a.get("position") or {}
        check("position: routed micros, broker fill, stop, target", p.get("side") == "SHORT" and p.get("qty") == 8 and p.get("entry") == 25069.75
              and p.get("stop") == 25110.0 and p.get("target") == 24900.0, p)
        check("position: unrealized $, time in trade, BE trigger", p.get("unrealized_usd") == round((25069.75 - 25050.0) * 2 * 8, 2)
              and p.get("time_in_s") == now - ts(2026, 10, 20, 8, 35) and p.get("be_trigger") == round(25069.75 - 40.25, 2), p)
        kinds = [(o["kind"], o["refused"]) for o in a["orders"]]
        check("timeline: risk refusal, entry, refused BE move, exit, entry", kinds == [("risk", True), ("entry", False), ("stop", True), ("exit", False), ("entry", False)], kinds)
        check("trades: journal + ledger, newest first", len(a["trades"]) >= 2 and a["trades"][0]["entry_t"] >= a["trades"][-1]["entry_t"], a["trades"])
        check("equity curve starts at the prior P&L", a["equity"][0] == ["start", -100.0] and a["equity"][-1][1] == round(-100 + 1450 - 22.8, 2), a["equity"])
        check("bars: the bot's 5m tail and packed 1m", len(a["bars5"]) > 10 and a["bars1"] and len(a["bars1"]["dt"]) == 180, (len(a["bars5"]), (a["bars1"] or {}).get("s")))
        check("account: no secrets or file paths", "SECRET" not in r.text and "Users" not in r.text and "oif_" not in r.text, "")
        b1 = a["bars1"]
        check("pack(): prices round-trip through quarter points", (b1["p0"] + b1["h"][0]) / 4 == 25064.0 and (b1["p0"] + b1["l"][0]) / 4 == 25052.25, b1["p0"])

        # ---- /api/next/pc/trade/<entry_t>
        e1 = ts(2026, 10, 20, 3, 5)
        r = cl.get(f"/api/next/pc/trade/{e1}")
        t = r.json()
        check("trade: today's routed trade with bars from the bot's feed", r.status_code == 200 and t["trade"]["entry_t"] == e1 and t["chart"] is None
              and len(t["bars5"]) > 0 and t["bars_source"] == "bot feed", {k: v for k, v in t.items() if k not in ("bars5", "bars1")})
        if chart_rec:
            r = cl.get(f"/api/next/pc/trade/{chart_rec[2]}")
            check("trade: a routed trade the LIT replay has links its chart id", r.status_code == 200 and r.json().get("chart") == chart_rec[0], r.text[:200])
        if os.path.exists(os.path.join(pcdash_api.DATA, "NQ_5m.csv")):
            r = cl.get(f"/api/next/pc/trade/{ts(2026, 10, 12, 5, 0)}")
            t = r.json()
            check("trade: an older routed trade falls back to data/NQ_5m.csv + NQ_1m.csv", r.status_code == 200 and t.get("bars_source") == "data/NQ_5m.csv"
                  and len(t.get("bars5") or []) > 20 and (t.get("bars1") or {}).get("s") == 60, {k: v for k, v in t.items() if k not in ("bars5", "bars1")})
        r = cl.get("/api/next/pc/trade/123")
        check("trade: unknown entry -> 404", r.status_code == 404 and "error" in r.json())

        # ---- /api/next/extras
        r = cl.get("/api/next/extras")
        x = r.json()
        check("extras 200 with the phone's shapes", r.status_code == 200 and x.get("tcols") and isinstance(x.get("trades"), list), r.text[:200])
        if x.get("trades"):
            check("extras: trade rows match tcols", all(len(row) == len(x["tcols"]) for row in x["trades"]))
        check("extras: two_week odds + MFFU rules when their files exist",
              (not os.path.exists(os.path.join(pcdash_api.RUNS, "lit_2wk_rec.json")) or "H2" in (x.get("two_week") or {}).get("eval", {}))
              and (not os.path.exists(os.path.join(pcdash_api.LIT_DOCS, "mffu_rules.json")) or (x.get("mffu") or {}).get("stages")), list(x))

        # ---- read-only
        check("read-only: every route is a GET", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in pcdash_api.router.routes))
        check("read-only: the bot's ledger, kill flag and state file untouched", bot.ledger == before and not bot.kill
              and not os.path.exists(bot.state_path), "")
    finally:
        pcdash_api._bot, lit_learn.JOURNAL_PATH = old_bot, old_jp
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"pcdash api: {sum(results)}/{len(results)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
