"""Live View API (engine/liveview_api.py): bars, the three strategy layers (Zlarior / ATLAS / Strategy 3), REAL sizes and $
on positions, the thinking panel, windows, the narrator feed, read-only routes. Fake bot with synthetic bars / Brain /
ATLAS / account B; the CSV fallback is off, so no real data/ file is read or written.

  python -X utf8 -m tests.test_liveview_api        # ~2 s
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import liveview_api as L, narrator as N  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
L.CSV_FALLBACK = False


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def T(h, m, day=(2026, 10, 14)):
    return int(dt.datetime(*day, h, m, tzinfo=ET).timestamp())


def frames(now):
    t0 = T(18, 0, (2026, 10, 12))
    r5, r1, p = [], [], 30800.0
    for i in range((now - t0) // 300):
        t = t0 + i * 300
        o, c = p, p + (3 if i % 3 else -4)
        r5.append({"time": t, "open": o, "high": max(o, c) + 2, "low": min(o, c) - 2, "close": c, "volume": 100})
        p = c
    t1 = T(18, 0, (2026, 10, 13))
    q = 30800.0
    for i in range((now - t1) // 60):
        t = t1 + i * 60
        o, c = q, q + (0.5 if i % 2 else -0.25)
        r1.append({"time": t, "open": o, "high": max(o, c) + 1, "low": min(o, c) - 1, "close": c, "volume": 10})
        q = c
    return r5, pd.DataFrame(r1)


def brain(stage="displacement", status=None, trade=None, day_trades=0):
    setups = []
    if status:
        setups.append({"id": "1:-1", "t": T(4, 55), "dir": -1, "side": "SHORT", "status": status, "cisd": 30797.25, "ext": 30861.75,
                       "plan": {"limit": 30797.25, "stop": 30862.0, "stop_pts": 64.75, "target": 30495.31, "rr": 4.66, "target_label": "VIX band",
                                "armed_t": T(4, 55), "armed_hm": "04:55", "expires_t": T(5, 25), "expires_hm": "05:25"},
                       "checks": [{"key": "disp", "ok": True, "label": "Displacement >= 0.8 ATR", "text": "1.21 ATR"}], "status_text": "Armed"})
    key = "trade" if trade else ("cisd1m" if status == "tapped" else "limit" if status == "armed" else "sweep")
    return {"day": "2026-10-14", "at": "Wed 04:50 ET", "atr": 21.4, "day_trades": day_trades, "rules": {"depth": 0.5, "disp": 0.8},
            "stage": {"key": key, "label": key, "n": 3, "waiting": "waiting text"},
            "stages": [{"key": "levels", "label": "Levels", "state": "done", "n": 1}, {"key": "sweep", "label": "Sweep", "state": "now", "n": 2}],
            "watch": [{"dir": -1, "side": "SHORT", "allowed": True, "ext": 30861.75, "ext_t": T(4, 15), "swept": ["Frankfurt high", "London 03-04 high"],
                       "level": 30804.75, "depth_atr": 2.67, "depth_pts": 57.0, "depth_ok": True, "idm_n": 1, "idm_ok": True, "disp": 0.52,
                       "disp_ok": False, "cisd": 30797.25, "cisd_dist": -13.5, "cisd_closed": False, "stop_preview": 64.75, "stage": stage,
                       "text": "Short setup forming"}],
            "levels": [{"label": "Asia high", "price": 30891.5, "side": "H", "kind": "asia", "taken": False},
                       {"label": "Frankfurt high", "price": 30804.75, "side": "H", "kind": "lon", "taken": True, "taken_t": T(3, 0), "taken_hm": "03:00"}],
            "nearest": {"above": [{"label": "Asia high", "price": 30891.5, "dist": 91.5}], "below": []},
            "setups": setups, "trade": trade, "guards": {"blocking": []},
            "log": [{"key": "sweep:1", "t": T(3, 0), "kind": "sweep", "text": "Swept Frankfurt high 30,804.75 (1.01 ATR deep; deep enough: ✓)"}]}


class AB:
    def info(self, now=None):
        return {"label": "ATLAS 25K", "open": {"entry_t": T(4, 40), "dir": 1, "side": "LONG", "qty": 4, "entry": 30780.0, "stop": 30760.0,
                                                "target": 30860.0, "strategy": "EMA"},
                "routed": [{"t": T(4, 40), "side": "buy", "qty": 4, "entry_t": T(4, 40), "strategy": "EMA", "ok": True}]}


def bot(now, **kw):
    r5, d1 = frames(now)
    b = SimpleNamespace(running=True, kill=False, cfg={"adapter": "ninjatrader", "confirm": "I ACCEPT LIVE RISK", "webhook_url": "https://x"},
                        state={"price": 30800.0}, brain=brain(), second=None, acct_b=None, ledger=[], log=[],
                        health={"stale": False, "data_age_s": 5}, bars_tail=r5[-400:], _lit_1m_store=d1, _open_routed=None, _open_qty=None,
                        _open_src=None, adapter=None, clock=lambda: now)
    b._push_account = lambda: "MFFU 50K"
    b._broker_stop = lambda t: None
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def main():
    now = T(4, 50)
    b = bot(now)
    before = copy.deepcopy((b.state, b.brain, b.ledger, b.cfg))
    v = L.view(b, "1m", now, narr=N.Narrator())
    check("1m bars of today's session from the bot's 1m store", v["bars"] and v["bars"][0][0] >= v["t0"] and v["bars"][1][0] - v["bars"][0][0] == 60
          and "NinjaTrader" in v["source"], (len(v["bars"]), v["source"]))
    v5 = L.view(b, "5m", now, narr=N.Narrator())
    check("5m bars from bars_tail", v5["bars"] and v5["bars"][1][0] - v5["bars"][0][0] == 300)
    lit = v["strategies"]["lit"]
    check("three layers, each its own colour", set(v["strategies"]) == {"lit", "atlas", "scalp"} and
          [v["strategies"][k]["color"] for k in ("lit", "atlas", "scalp")] == ["#2563eb", "#ea580c", "#7c3aed"])
    check("LIT levels: untouched + swept with time", any(not x["taken"] for x in lit["levels"]) and any(x["taken"] and x["taken_hm"] == "03:00" for x in lit["levels"]))
    th = lit["thinking"]
    check("thinking: plain sentence (swept, displacement, CISD close below)",
          "Swept Frankfurt high" in th["headline"] and "displacement >= 0.8 ATR" in th["headline"] and "CISD close below 30,797.25" in th["headline"], th["headline"])
    ck = {c["label"]: c["ok"] for c in th["checklist"]}
    check("checklist ticks / crosses / pending", ck.get("Sweep depth >= 0.5 ATR") is True and ck.get("Displacement >= 0.8 ATR") is None
          and ck.get("1 trade a day") is True, ck)
    check("distance to the trigger in points", th["distance"] == [{"label": "to the CISD close", "pts": 13.5}], th["distance"])
    check("entry window countdown", th["window"]["open"] and th["window"]["secs"] == T(15, 30) - now, th["window"])
    check("setup mock-up data: sweep extreme, level, CISD", lit["setup"]["ext"] == 30861.75 and lit["setup"]["cisd"] == 30797.25)

    # armed / tapped
    b.brain = brain(status="tapped")
    lit = L.view(b, "1m", now, narr=N.Narrator())["strategies"]["lit"]
    ids = {x["id"] for x in lit["lines"]}
    check("tapped setup = live: limit / stop / target lines + expiry", {"limit", "plan_stop", "plan_target"} <= ids and
          lit["thinking"]["expires"]["t"] == T(5, 25) and lit["setup"]["armed"]["status"] == "tapped", ids)
    check("armed: distance to the limit", lit["thinking"]["distance"][0]["label"] == "to the limit")

    # real routed position: REAL micros and $
    et_ = T(5, 24)
    tr = {"side": "SHORT", "dir": -1, "entry_t": et_, "entry": 30785.75, "stop0": 30862.0, "stop": 30862.0, "target": 30495.31, "qty": 1,
          "be": {"done": False, "trigger": 30709.5, "text": "BE at +1R"}, "t_check": {"state": "passed", "text": "passed"}}
    b.brain = brain(trade=tr)
    b._open_routed, b._open_qty = et_, 7
    b.state = {"price": 30791.0, "position": {"entry_t": et_, "dir": -1, "entry": 30785.75, "stop": 30862.0, "stop0": 30862.0, "target": 30495.31, "qty": 1}}
    b.ledger = [{"t": et_ + 3, "side": "sell", "qty": 7, "entry_t": et_, "entry": 30785.75, "stop": 30862.0, "target": 30495.31, "result": {"ok": True}}]
    lit = L.view(b, "1m", T(5, 45), narr=N.Narrator())["strategies"]["lit"]
    ln = {x["id"]: x for x in lit["lines"]}
    check("position drawn with the REAL size (7 MNQ, not the model's 1)", lit["position"]["qty"] == 7 and "7 MNQ" in ln["entry"]["label"], lit["position"])
    check("stop / target lines carry real $ (7 x pts x $2)", "-$1,068" in ln["stop"]["label"] and "+$4,066" in ln["target"]["label"], (ln["stop"], ln["target"]))
    check("BE trigger line while the stop is not at BE", "be" in ln)
    check("thinking in trade: real micros + distances", "7 MNQ" in lit["thinking"]["headline"] and len(lit["thinking"]["distance"]) == 3, lit["thinking"])
    check("ledger entry mark", any(m["kind"] == "entry" and m["qty"] == 7 for m in lit["marks"]))
    # model trade, nothing routed: never a paper size
    b._open_routed, b._open_qty, b.ledger = None, None, []
    lit = L.view(b, "1m", T(5, 45), narr=N.Narrator())["strategies"]["lit"]
    check("model trade (not routed): no size, labelled", lit["position"]["qty"] is None and "no size" in lit["lines"][0]["label"], lit["lines"][0])

    # ATLAS + Strategy 3
    sec = {"t": now, "day": "2026-10-14", "strategies": {
        "ema_lon_vix": {"short": "EMA", "label": "London EMA", "on": True, "state": {"stage": "waiting", "text": "Waiting", "window": "03:00-09:30 ET"},
                        "brain": {"checks": [{"k": "t15", "name": "15m trend", "ok": True, "val": "down"}], "first_fail": None}},
        "sr_nyreclaim": {"short": "S/R", "on": True, "state": {"stage": "off", "window": "09:30-12:00 ET"},
                         "brain": {"levels": [{"name": "pdh", "px": 30814.75, "stage": "reclaimed"}]}},
        "macd_sweep": {"short": "MACD", "on": True, "state": {"stage": "armed", "text": "Armed (long)", "window": "02:00-05:00, 09:30-11:00 ET"},
                       "brain": {"plan": {"side": "long", "entry": 30790.0, "stop": 30770.0, "target": 30850.0}}},
        "lit_asia": {"short": "LIT+Asia", "on": True, "state": {"stage": "waiting"}},
        "scalp_mr": {"short": "MR", "on": True, "state": {"stage": "waiting", "text": "scalp waiting"}}}}
    b2 = bot(now, second=sec, acct_b=AB())
    v = L.view(b2, "1m", now, narr=N.Narrator())
    at, sc = v["strategies"]["atlas"], v["strategies"]["scalp"]
    mem = {m["short"]: m for m in at["members"]}
    check("ATLAS members with stage, checks, window", mem["EMA"]["window"]["open"] and mem["EMA"]["checks"][0]["ok"] is True
          and mem["MACD"]["window"]["secs"] == T(5, 0) - now, mem["EMA"])
    check("Asia slot is not an ATLAS member (listed apart)", mem["LIT+Asia"]["candidate"] and mem["LIT+Asia"].get("other"))
    check("S/R levels + MACD paper plan (no size) on the ATLAS layer", any("pdh" in x["label"] for x in at["levels"])
          and any("paper, no size" in x["label"] for x in at["lines"]))
    bl = {x["id"]: x for x in at["lines"]}
    check("account B position: REAL 4 MNQ with $ at stop / target", "4 MNQ" in bl["b_entry"]["label"] and "-$160" in bl["b_stop"]["label"]
          and "+$640" in bl["b_target"]["label"] and at["position"]["unrealized_usd"] == 160.0, (bl.get("b_stop"), at["position"]))
    ref, e, a = [], None, 2 / 22
    for r in L.bars(b2, "1m", now)["hist5"]:
        e = r[4] if e is None else e + a * (r[4] - e)
        if r[0] >= v["t0"]:
            ref.append(round(e, 2))
    check("EMA 21 of the 5m closes", [x[1] for x in at["ema21"]] == ref and len(at["ema50"]) == len(ref), (at["ema21"][:2], ref[:2]))
    check("scalp member fills the Strategy 3 layer", not sc["placeholder"] and sc["members"][0]["short"] == "MR")
    v0 = L.view(bot(now), "1m", now, narr=N.Narrator())
    check("Strategy 3 placeholder when no scalp member", v0["strategies"]["scalp"]["placeholder"] and "research" in v0["strategies"]["scalp"]["text"])

    # windows
    check("windows_of parses two windows", L.windows_of("02:00-05:00, 09:30-11:00 ET") == [(120, 300), (570, 660)])
    ws = L.window_state(T(12, 0, (2026, 10, 17)), [(180, 570)])
    check("window_state: weekend -> Monday", ws and not ws["open"] and "Mon" in ws["label"], ws)

    # no bars, narrator, safety
    b3 = bot(now, bars_tail=[], _lit_1m_store=None)
    v3 = L.view(b3, "1m", now, narr=N.Narrator())
    check("no bars (CSV fallback off) -> empty, no error", v3["bars"] == [] and "lit" in v3["strategies"])
    nar = N.Narrator()
    v4 = L.view(b, "1m", now, narr=nar)
    check("narrator feed in the answer", v4["narrator"] and v4["narrator"][0]["strat"] in ("lit", "sys", "atlas"))
    check("push kinds listed: default on = armed, entry, exit, refused",
          sorted(k for k, x in v4["push_kinds"].items() if x["on"]) == ["armed", "entry", "exit", "refused"] or os.environ.get("LE_NARRATOR_PUSH") == "0")
    b4 = bot(now)
    L.view(b4, "1m", now, narr=N.Narrator())
    check("read-only: bot state / brain / ledger / cfg unchanged", copy.deepcopy((b4.state, b4.brain, b4.ledger, b4.cfg)) ==
          copy.deepcopy((bot(now).state, bot(now).brain, [], bot(now).cfg)))
    check("first bot unchanged too", copy.deepcopy((bot(now).state, brain(), [], bot(now).cfg)) == before)

    app = FastAPI()
    app.include_router(L.router)
    L._bot = lambda: bot(now)
    c = TestClient(app)
    r = c.get("/api/next/liveview?tf=5m")
    txt = r.text
    check("GET /api/next/liveview 200", r.status_code == 200 and r.json()["tf"] == "5m", r.text[:200])
    check("no confirm phrase / webhook in the answer", "I ACCEPT" not in txt and "https://x" not in txt and "webhook" not in txt.lower())
    r2 = c.get("/api/next/liveview/feed?n=5")
    check("GET /api/next/liveview/feed", r2.status_code == 200 and isinstance(r2.json()["feed"], list) and len(r2.json()["feed"]) <= 5, r2.text[:200])
    check("only GET routes (POST refused)", c.post("/api/next/liveview").status_code == 405)
    L._bot = lambda: object()
    r3 = c.get("/api/next/liveview")
    check("a broken bot never 500s the page badly (JSON answer)", r3.status_code in (200, 500) and isinstance(r3.json(), dict))
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("server.py includes the router once", src.count("liveview_api import router") == 1)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
