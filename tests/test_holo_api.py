"""Holodeck data (engine/holo_api.py): the le-holo contract, exact NinjaTrader fill times / prices from the adapter legs, model
price + slippage ticks, stop paths with the breakeven CHANGE, an open trade, a refused order never shown as a fill, account B
(ATLAS) and C (BLITZ) fills labelled by bot, a past day rebuilt from the logs, the model fallback, the phone files' size caps,
the publisher shipping holo.json + holo_hist.json, read-only, never raises, the routes, and the committed sample fixture.
Fake bot + fake NinjaTrader adapters + temp logs: nothing in data/, logs/, .env.local.ps1 or second_model.json is written
(the optional real-data check only reads data/NQ_*.csv).

  python -X utf8 -m tests.test_holo_api            # ~3 s (+ ~3 s for the real-data check when data/NQ_5m.csv exists)
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import time
from collections import deque
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import holo_api as H, live_publish as LP, liveview_api as L, narrator as N  # noqa: E402
from tests import test_liveview_api as F  # noqa: E402  (synthetic bars, T(); sets L.CSV_FALLBACK = False)

RES = []
TMP = tempfile.mkdtemp(prefix="holo_test_")
STORE = os.path.join(TMP, "exec_audit")
H.STORE, H.NARR_DIR, H.BRAIN_DIR = STORE, os.path.join(TMP, "narrator"), os.path.join(TMP, "brain")
H.STATE_PATH = os.path.join(TMP, "live_state.json")
H.CSV_FALLBACK, H.FRAMES = False, None
L.CSV_FALLBACK = False
DAY, PAST, EMPTY = "2026-10-14", "2026-10-13", "2026-10-12"
T = F.T


def T13(h, m):
    return T(h, m, (2026, 10, 13))


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


# ---------------------------------------------------------------------------------------------- the contract
FILL_KEYS = {"id", "t", "px", "qty", "side", "kind", "bot", "acct", "real", "src", "model_px", "slip_ticks", "trade"}
TRADE_KEYS = {"id", "bot", "acct", "real", "side", "qty", "entry", "exit", "stop_path", "target", "risk_usd", "usd", "r", "model", "setup"}
ORDER_KEYS = {"t", "t_end", "bot", "acct", "type", "side", "px", "qty", "state", "why"}
THOUGHT_KEYS = {"t", "bot", "stage", "title", "text", "level", "px"}
LEVEL_KEYS = {"bot", "px", "label", "t0", "t1", "taken_t"}
SETUP_KEYS = {"kind", "t_sweep", "sweep_ext", "swept", "t_idm", "t_disp", "t_cisd", "cisd", "notes"}


def contract_errors(v) -> list:
    bad = []

    def need(ok, what):
        if not ok:
            bad.append(what)
    need(v.get("v") == 1 and v.get("kind") == "le-holo", "v / kind")
    need(isinstance(v.get("t"), int) and isinstance(v.get("day"), str) and len(v["day"]) == 10 and isinstance(v.get("live"), bool), "t / day / live")
    b = v.get("bars") or {}
    need(set(b) >= {"1m", "5m"} and all(isinstance(r, list) and len(r) == 6 for r in (b.get("1m") or []) + (b.get("5m") or [])), "bars [t,o,h,l,c,v]")
    bots = v.get("bots") or {}
    need(set(bots) == {"lit", "atlas", "blitz"} and all({"name", "color", "account", "real", "plan"} <= set(x) for x in bots.values()), "bots")
    need([bots.get(k, {}).get("color") for k in ("lit", "atlas", "blitz")] == ["#4f9bff", "#ff9a3d", "#b388ff"], "bot colours")
    need((bots.get("lit") or {}).get("name") == "Zlarior", "Zlarior")
    tids = {t.get("id") for t in v.get("trades") or []}
    for f in v.get("fills") or []:
        need(FILL_KEYS <= set(f), f"fill keys {sorted(FILL_KEYS - set(f))}")
        need(isinstance(f.get("t"), float) and isinstance(f.get("px"), float) and isinstance(f.get("qty"), int), f"fill types {f.get('id')}")
        need(f.get("side") in ("BUY", "SELL") and f.get("kind") in ("entry", "add", "stop", "target", "exit", "flatten"), f"fill side/kind {f.get('id')}")
        need(f.get("bot") in ("lit", "atlas", "blitz") and f.get("src") in ("ninjatrader", "sim", "paper", "model"), f"fill bot/src {f.get('id')}")
        need(f.get("trade") in tids, f"fill trade link {f.get('id')}")
    for t in v.get("trades") or []:
        need(TRADE_KEYS <= set(t), f"trade keys {sorted(TRADE_KEYS - set(t))}")
        need(t.get("side") in ("LONG", "SHORT") and isinstance(t.get("qty"), int) and {"t", "px"} <= set(t.get("entry") or {}), f"trade side/entry {t.get('id')}")
        need(t.get("exit") is None or {"t", "px", "reason"} <= set(t["exit"]), f"trade exit {t.get('id')}")
        need(all(isinstance(p, list) and len(p) == 2 for p in t.get("stop_path") or []), f"stop_path {t.get('id')}")
        need(t.get("model") is None or {"entry_t", "entry", "exit_t", "exit", "usd"} <= set(t["model"]), f"trade model {t.get('id')}")
        need(t.get("setup") is None or SETUP_KEYS <= set(t["setup"]), f"setup keys {t.get('id')}")
    for o in v.get("orders") or []:
        need(ORDER_KEYS <= set(o) and o.get("type") in ("LIMIT", "STOP", "MARKET") and o.get("state") in ("WORKING", "FILLED", "CANCELLED", "REJECTED"),
             f"order {o}")
    ts = [x.get("t") for x in v.get("thoughts") or []]
    need(ts == sorted(ts), "thoughts time-ordered")
    for x in v.get("thoughts") or []:
        need(THOUGHT_KEYS <= set(x) and x.get("bot") in ("lit", "atlas", "blitz", "sys") and x.get("level") in ("info", "good", "warn", "bad", "dim"),
             f"thought {x}")
    for x in v.get("levels") or []:
        need(LEVEL_KEYS <= set(x), f"level {x}")
    need("structure" in v and "now" in v and isinstance(v.get("errors"), list), "structure / now / errors")
    need(v["now"] is None or set(v["now"]) >= {"lit", "atlas", "blitz"}, "now panels")
    return bad


# ---------------------------------------------------------------------------------------------- fake NinjaTrader + bot
class FakeNT:
    name = "ninjatrader"

    def __init__(self, account, legs=(), history=()):
        self.account = account
        self.legs = list(legs)
        self.history = deque(history, maxlen=20)
        self.folder = None

    def _instruments(self):
        return {"micro": "MNQ 12-26", "mini": "NQ 12-26"}

    def position_for(self, inst):
        return {"side": "FLAT", "qty": 0}

    def _listing(self):
        return []


def leg(entry_t, d, qty, fill, mtime, stop0, stop, target, tag, adds=None, status="closed"):
    base = f"LE{entry_t}{tag}M"
    return {"instrument": "MNQ 12-26", "qty": qty, "side": "BUY" if d == 1 else "SELL", "dir": d, "entry_t": entry_t, "stop": stop, "target": target,
            "entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "status": status, "filled": qty, "fill_px": fill,
            "fill_mtime": mtime, "bracket_qty": qty, "stop0": stop0, "sent_at": entry_t + 1.0, **({"adds": adds} if adds else {})}


def row(t, side, qty, entry_t, ok=True, account=None, **kw):
    res = {"ok": ok, "adapter": "ninjatrader", **({"account": account} if account else {})}
    if "legs" in kw:
        res["legs"] = kw.pop("legs")
    if "error" in kw:
        res["error"] = kw.pop("error")
    return {"t": t, "sym": "NQ", "side": side, "qty": qty, "entry_t": entry_t, **kw, "result": res}


E_LIT = T(5, 24)                  # Zlarior short 7 @ model 30785.75 (fill 30785.50 = 1 tick worse), BE at 06:10, BE stop hit 07:02
E_B = T(9, 40)                    # ATLAS long 4 on account B, still open
E_C = T(10, 0)                    # BLITZ long 2 on account C, target filled 10:12
E_REF = T(10, 30)                 # ATLAS long 3 refused on account B (never a fill)
FILL_T = E_LIT + 3.25


def orders_file(rows):
    os.makedirs(STORE, exist_ok=True)
    with open(os.path.join(STORE, "orders.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def make_bot(now):
    b = F.bot(now)
    lg = leg(E_LIT, -1, 7, 30785.5, FILL_T, 30862.0, 30784.5, 30495.25, "AAAA")
    b.adapter = FakeNT("Sim101", history=[lg])
    b.ledger = [row(E_LIT + 2, "sell", 7, E_LIT, account="Sim101", entry=30785.75, stop=30862.0, target=30495.25,
                    legs=[{"instrument": "MNQ 12-26", "qty": 7, "filled": 7, "fill_px": 30785.5}]),
                row(T(6, 10), "modify", 7, E_LIT, stop=30784.5, reason="BE"),
                row(T(7, 3), "exit", 7, E_LIT, reason="BE", pnl=-15.05, exit_t=T(7, 2))]
    lb = leg(E_B, 1, 4, 30790.25, E_B + 1.5, 30770.0, 30770.0, 30850.0, "BBBB", status="protected")
    B = SimpleNamespace(name="Sim102", label="Account B Sim102", spec={"plan_label": "ATLAS 25K"}, adapter=FakeNT("Sim102", legs=[lb]),
                        ledger=[row(E_B + 1, "buy", 4, E_B, account="Sim102", entry=30790.0, stop=30770.0, target=30850.0, src="ema_lon_vix",
                                    strategy="EMA", legs=[{"filled": 4, "fill_px": 30790.25}]),
                                row(E_REF + 1, "buy", 3, E_REF, ok=False, account="Sim102", entry=30801.0, stop=30780.0, target=30860.0,
                                    src="macd_sweep", strategy="MACD", error="REFUSED: account does not exist",
                                    legs=[{"instrument": "MNQ 12-26", "qty": 3, "ok": False, "state": "REJECTED"}])])
    B.info = lambda now=None: {"label": B.label, "open": None, "routed": []}
    lc = leg(E_C, 1, 2, 30795.0, E_C + 0.8, 30785.0, 30785.0, 30805.0, "CCCC")
    C = SimpleNamespace(name="Sim103", label="Account C Sim103", spec={"plan_label": "BLITZ 25K"}, adapter=FakeNT("Sim103", history=[lc]),
                        ledger=[row(E_C + 1, "buy", 2, E_C, account="Sim103", entry=30794.75, stop=30785.0, target=30805.0,
                                    legs=[{"filled": 2, "fill_px": 30795.0}])])
    C.disabled_reason = lambda: None
    b.acct_b, b.acct_c = B, C
    orders_file([{"id": lg["entry_id"], "state": "FILLED", "filled": 7, "avg": 30785.5, "mtime": FILL_T, "seen": E_LIT + 9},
                 {"id": lg["stop_id"], "state": "FILLED", "filled": 7, "avg": 30784.75, "mtime": T(7, 2) + 17.5, "seen": T(7, 3)},
                 {"id": lg["target_id"], "state": "CANCELLED", "filled": 0, "avg": None, "mtime": T(7, 2) + 18.0, "seen": T(7, 3)},
                 {"id": lc["entry_id"], "state": "FILLED", "filled": 2, "avg": 30795.0, "mtime": E_C + 0.8, "seen": E_C + 5},
                 {"id": lc["target_id"], "state": "FILLED", "filled": 2, "avg": 30805.0, "mtime": T(10, 12) + 4.2, "seen": T(10, 13)},
                 {"id": lc["stop_id"], "state": "CANCELLED", "filled": 0, "avg": None, "mtime": T(10, 12) + 4.6, "seen": T(10, 13)}])
    return b


def past_logs():
    """2026-10-13 as the disk keeps it: the ledger archive, the leg views, NinjaTrader order states, the narrator's feed."""
    e = T13(3, 10)
    lg = leg(e, 1, 5, 30650.25, e + 2.125, 30630.0, 30630.0, 30700.0, "PAST")
    with open(os.path.join(STORE, "ledger.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row(e + 1, "buy", 5, e, account="Sim101", entry=30650.0, stop=30630.0, target=30700.0,
                                legs=[{"filled": 5, "fill_px": 30650.25}])) + "\n")
        fh.write(json.dumps(row(T13(4, 1), "exit", 5, e, reason="TARGET", pnl=487.0, exit_t=T13(4, 0))) + "\n")
    with open(os.path.join(STORE, "legs.json"), "w", encoding="utf-8") as fh:
        json.dump({lg["entry_id"]: lg}, fh)
    with open(os.path.join(STORE, "orders.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": lg["target_id"], "state": "FILLED", "filled": 5, "avg": 30700.0, "mtime": T13(4, 0) + 31.0, "seen": T13(4, 1)}) + "\n")
    # account B's own state file (data/live_state_acctb.json next to the bot's): no leg kept, the order states archived
    eb = T13(9, 45)
    with open(os.path.join(TMP, "live_state_acctb.json"), "w", encoding="utf-8") as fh:
        json.dump({"ledger": [row(eb + 1, "sell", 3, eb, account="Sim102", entry=30720.0, stop=30740.0, target=30660.0, src="sr_nyreclaim",
                                  strategy="S/R", legs=[{"filled": 3, "fill_px": 30719.75}]),
                              row(T13(10, 20), "exit", 3, eb, account="Sim102", reason="TARGET", pnl=354.0, src="sr_nyreclaim")]}, fh)
    with open(os.path.join(STORE, "orders.jsonl"), "a", encoding="utf-8") as fh:
        for oid, st, avg, mt in ((f"LE{eb}QQQQME", "FILLED", 30719.75, eb + 2.5), (f"LE{eb}QQQQMT", "FILLED", 30660.0, T13(10, 19) + 8.0),
                                 (f"LE{eb}QQQQMS", "CANCELLED", None, T13(10, 19) + 8.4)):
            fh.write(json.dumps({"id": oid, "state": st, "filled": 3 if avg else 0, "avg": avg, "mtime": mt, "seen": int(mt) + 3}) + "\n")
    os.makedirs(H.NARR_DIR, exist_ok=True)
    with open(os.path.join(H.NARR_DIR, f"{PAST}.jsonl"), "w", encoding="utf-8") as fh:
        for m in (N.msg("lit:sweep:1", T13(2, 40), "lit", "swept", "Level swept", "Swept Asia low 30,640.25 (0.9 ATR deep)", "info"),
                  N.msg(f"lit:fill:{e}", e + 2, "lit", "entry", "Sim101: FILLED · LONG 5 MNQ", "Filled LONG 5 MNQ at 30,650.25", "good", fill=30650.25),
                  N.msg("scalp:blitz:paper:1", T13(10, 0), "scalp", "blitz", "BLITZ PAPER entry", "PAPER LONG 1 MNQ at 30,660", "dim")):
            fh.write(json.dumps(m) + "\n")
    return e


def model_stub(day, errors=None, now=None):
    """engine/lit_live's backtest of a day, stubbed (the real replay is checked against data/ at the end)."""
    if day == PAST:
        e = T13(3, 10)
        return {"trades": [{"entry_t": e, "exit_t": T13(4, 0), "dir": 1, "entry": 30650.0, "exit_price": 30700.0, "stop": 30630.0, "target": 30700.0,
                            "qty": 5, "pnl": 490.5, "pnl_r": 2.5, "exit_reason": "TARGET", "be_t": None},
                           {"entry_t": T13(11, 5), "exit_t": T13(11, 30), "dir": -1, "entry": 30710.0, "exit_price": 30729.25, "stop": 30729.0,
                            "target": 30650.0, "qty": 3, "pnl": -63.45, "pnl_r": -1.0, "exit_reason": "STOP", "be_t": None}],
                "setups": [{"id": "9:1", "t": e - 300, "dir": 1, "swept": ["Asia low"], "ext": 30629.75, "cisd": 30645.0, "status": "filled",
                            "plan": {"limit": 30645.0, "stop": 30629.5, "target": 30700.0, "armed_t": e - 300, "expires_t": e + 1500},
                            "trade": {"entry_t": e, "qty": 5}, "detail": {"t_sweep": T13(2, 40), "t_idm": T13(2, 0), "t_disp": T13(2, 55), "t_cisd": e - 300,
                                                                 "cisd": 30645.0, "sweep_ext": 30629.75}}],
                "levels": [{"bot": "lit", "px": 30640.25, "label": "Asia low", "t0": T13(0, 0), "t1": None, "taken_t": T13(2, 40), "side": "L"}],
                "log": [{"key": "cisd:9:1", "t": e - 300, "kind": "cisd", "text": "5m CISD up closed at 30,645: swept Asia low"}]}
    if day == EMPTY:
        return {"trades": [{"entry_t": T(4, 5, (2026, 10, 12)), "exit_t": T(5, 0, (2026, 10, 12)), "dir": 1, "entry": 30500.0, "exit_price": 30501.0,
                            "stop": 30480.0, "target": 30600.0, "qty": 4, "pnl": 0.4, "pnl_r": 0.0, "exit_reason": "BE", "be_t": T(4, 30, (2026, 10, 12))}],
                "setups": [], "levels": [], "log": []}
    return None


# ---------------------------------------------------------------------------------------------- the checks
def main():
    t_start = time.time()
    now = T(11, 0)
    b = make_bot(now)
    store_before = sorted(os.listdir(STORE))
    before = copy.deepcopy((b.state, b.brain, b.ledger, b.cfg, b.acct_b.ledger, b.acct_c.ledger, list(b.adapter.history),
                            b.acct_b.adapter.legs))
    t0 = time.perf_counter()
    v = H.build(b, None, now)
    ms = (time.perf_counter() - t0) * 1000
    check("contract shape (every key, types, the three bots and colours)", not contract_errors(v), contract_errors(v)[:8])
    check("live day: today's session, 1m + 5m bars from the bot's feed, now panels", v["live"] and v["day"] == DAY and v["bars"]["1m"]
          and v["bars"]["1m"][1][0] - v["bars"]["1m"][0][0] == 60 and v["bars"]["5m"] and v["now"] and v["now"]["lit"], (v["day"], v.get("bars_source")))
    check("no errors on a healthy bot", v["errors"] == [], v["errors"])
    fills = {f["id"]: f for f in v["fills"]}
    fe = fills.get(f"LE{E_LIT}AAAAME")
    check("exact fill time + price from the NinjaTrader leg (fill_mtime, fill_px)", fe and fe["t"] == FILL_T and fe["px"] == 30785.5 and fe["qty"] == 7
          and fe["side"] == "SELL" and fe["kind"] == "entry" and fe["real"] and fe["src"] == "sim" and fe["acct"] == "Sim101", fe)
    check("model price + slip ticks on the entry (short filled 1 tick lower = +1 worse)", fe and fe["model_px"] == 30785.75 and fe["slip_ticks"] == 1.0, fe)
    fs = fills.get(f"LE{E_LIT}AAAAMS")
    check("the BE stop fill: NinjaTrader's price / time, model = the stop, +1 tick worse", fs and fs["kind"] == "stop" and fs["px"] == 30784.75
          and fs["t"] == T(7, 2) + 17.5 and fs["model_px"] == 30784.5 and fs["slip_ticks"] == 1.0, fs)
    tr = {t["id"]: t for t in v["trades"]}
    tl = tr.get(f"lit:{E_LIT}")
    check("stop_path: the initial stop then the breakeven CHANGE", tl and tl["stop_path"] == [[FILL_T, 30862.0], [T(6, 10), 30784.5]], tl and tl["stop_path"])
    check("LIT trade: real, closed BE, real $ = fills incl. costs", tl and tl["real"] and tl["exit"]["reason"] == "BE" and tl["exit"]["px"] == 30784.75
          and tl["usd"] == round((30785.5 - 30784.75) * 2 * 7 - 1.90 * 7, 2) and tl["risk_usd"] == round((30862.0 - 30785.5) * 2 * 7, 2), tl)
    st = [o for o in v["orders"] if o["bot"] == "lit" and o["type"] == "STOP"]
    check("stop orders: one segment per price, the first replaced at the BE move, the BE stop FILLED",
          len(st) == 2 and st[0]["state"] == "CANCELLED" and st[0]["t_end"] == T(6, 10) and st[1]["state"] == "FILLED" and st[1]["px"] == 30784.5, st)
    ta = next((t for t in v["trades"] if t["bot"] == "atlas" and t["real"]), None)
    check("open trade (account B): exit null, stop + target WORKING", ta and ta["exit"] is None and ta["acct"] == "Sim102" and ta["qty"] == 4 and
          {(o["type"], o["state"]) for o in v["orders"] if o["bot"] == "atlas" and o["t"] >= E_B and o["type"] != "MARKET" and o["t"] < E_REF}
          == {("STOP", "WORKING"), ("LIMIT", "WORKING")}, ta)
    check("account B fills are ATLAS's, account C fills are BLITZ's", fills.get(f"LE{E_B}BBBBME", {}).get("bot") == "atlas"
          and fills.get(f"LE{E_C}CCCCME", {}).get("bot") == "blitz" and fills.get(f"LE{E_C}CCCCMT", {}).get("acct") == "Sim103"
          and fills[f"LE{E_C}CCCCMT"]["kind"] == "target" and fills[f"LE{E_C}CCCCMT"]["t"] == T(10, 12) + 4.2)
    ref = [o for o in v["orders"] if o["state"] == "REJECTED"]
    check("refused order: REJECTED with NinjaTrader's reason, never a fill or a trade (entry_never_placed)",
          len(ref) == 1 and ref[0]["t"] == E_REF + 1 and "account does not exist" in ref[0]["why"] and ref[0]["bot"] == "atlas"
          and not any(str(E_REF) in f["id"] or str(E_REF) in f["trade"] for f in v["fills"]) and not any(str(E_REF) in t["id"] for t in v["trades"]), ref)
    check("the refusal is in the thoughts (bad)", any(x["stage"] == "refused" and x["level"] == "bad" and x["bot"] == "atlas" for x in v["thoughts"]))
    check("thoughts: the Brain's log + the order events, time-ordered, with a price anchor",
          any(x["bot"] == "lit" and x["stage"] == "sweep" and x["px"] == 30804.75 for x in v["thoughts"])
          and any(x["stage"] == "be" for x in v["thoughts"]), [(x["stage"], x["px"]) for x in v["thoughts"]][:12])
    check("levels: LIT levels with taken time", any(x["bot"] == "lit" and x["label"] == "Frankfurt high" and x["taken_t"] == T(3, 0) for x in v["levels"]),
          v["levels"][:3])
    check("structure block of today (from the bot's bars)", isinstance(v["structure"], dict) and "summary" in v["structure"], str(v["structure"])[:200])
    check("unclear refusal (answer not OK, yet a leg filled): kept as a fill", _unclear_case(now))
    ok, info = _close_case(now)
    check("scale-in add fill + a TIME exit closed at market (CLOSEPOSITION: no broker price -> priced from the booked $, src model)", ok, info)
    check(f"build is fast ({ms:.0f} ms < 1500)", ms < 1500, ms)
    # ---- read-only
    v2 = H.build(b, None, now)
    after = (b.state, b.brain, b.ledger, b.cfg, b.acct_b.ledger, b.acct_c.ledger, list(b.adapter.history), b.acct_b.adapter.legs)
    check("read-only: the bot, its accounts and adapters unchanged, no file written", after == before and sorted(os.listdir(STORE)) == store_before
          and not os.path.exists(H.NARR_DIR) and not os.path.exists(H.BRAIN_DIR))
    check("same answer twice (deterministic)", json.dumps({**v, "build_ms": 0}, default=str) == json.dumps({**v2, "build_ms": 0}, default=str))

    # ---- a past day from the logs + the model
    H.model_day = model_stub
    e = past_logs()
    pb = F.bot(now)                                     # a fresh bot: nothing of that day in memory
    pb.ledger, pb.adapter = [], None
    vp = H.build(pb, PAST, now)
    check("past day: contract, live false, no now panels", not contract_errors(vp) and vp["live"] is False and vp["now"] is None, contract_errors(vp)[:5])
    fp = next((f for f in vp["fills"] if f["kind"] == "entry" and f["real"]), None)
    check("past day: the real fill from the archived leg (exact time), model price + slip", fp and fp["t"] == e + 2.125 and fp["px"] == 30650.25
          and fp["model_px"] == 30650.0 and fp["slip_ticks"] == 1.0, fp)
    tp = next((t for t in vp["trades"] if t["real"]), None)
    check("past day: target fill from NinjaTrader's archived order state, the model trade attached",
          tp and tp["exit"]["px"] == 30700.0 and tp["exit"]["t"] == T13(4, 0) + 31.0 and tp["model"]["usd"] == 490.5
          and tp["setup"]["t_sweep"] == T13(2, 40) and tp["setup"]["t_idm"] == T13(2, 0) and tp["setup"]["swept"][0]["px"] == 30640.25, tp)
    miss = [t for t in vp["trades"] if not t["real"] and t["bot"] == "lit"]
    check("past day: the model trade the bot did not take shows as real=false src model", len(miss) == 1 and miss[0]["src"] == "model"
          and all(not f["real"] and f["src"] == "model" for f in vp["fills"] if f["trade"] == miss[0]["id"]), miss)
    ml = [o for o in vp["orders"] if o.get("model")]
    tb = next((t for t in vp["trades"] if t["bot"] == "atlas" and t["real"]), None)
    fb = [f for f in vp["fills"] if tb and f["trade"] == tb["id"]]
    check("past day, account B from its state file + the archived order states: exact fill time, target fill, ATLAS",
          tb and tb["acct"] == "Sim102" and tb["side"] == "SHORT" and [f["kind"] for f in fb] == ["entry", "target"]
          and fb[0]["t"] == T13(9, 45) + 2.5 and fb[0]["px"] == 30719.75 and fb[1]["t"] == T13(10, 19) + 8.0 and fb[1]["px"] == 30660.0
          and tb["exit"]["reason"] == "TARGET", (tb, fb))
    check("past day: the armed LIT limit as the model's order (not routed), FILLED at the entry",
          len(ml) == 1 and ml[0]["type"] == "LIMIT" and ml[0]["state"] == "FILLED" and ml[0]["t"] == e - 300 and ml[0]["t_end"] == e
          and ml[0]["acct"] is None and ml[0]["px"] == 30645.0, ml)
    check("past day: the narrator's feed from logs/narrator/<day>.jsonl (+ BLITZ as blitz)",
          any(x["title"] == "Level swept" and x["px"] == 30640.25 for x in vp["thoughts"]) and any(x["bot"] == "blitz" for x in vp["thoughts"])
          and sum(1 for x in vp["thoughts"] if x["stage"] == "entry" and x["bot"] == "lit") == 1, [(x["bot"], x["stage"], x["title"]) for x in vp["thoughts"]])
    ve = H.build(pb, EMPTY, now)
    check("a day without real fills: the model's trades (real=false) so a replay always has something",
          len(ve["trades"]) == 1 and not ve["trades"][0]["real"] and len(ve["fills"]) == 2 and not any(f["real"] for f in ve["fills"])
          and len(ve["trades"][0]["stop_path"]) == 2, ve["trades"])

    # ---- today: the replay runs only for what the Brain cannot say, throttled
    calls = []

    def live_stub(day, errors=None, now=None):
        calls.append((day, now))
        return {"trades": [], "setups": [{"id": "1:-1", "t": T(4, 55), "dir": -1, "status": "tapped",
                                          "detail": {"t_sweep": T(4, 15), "t_idm": T(3, 50), "t_disp": T(4, 50), "t_cisd": T(4, 55), "cisd": 30797.25}}],
                "levels": [], "log": []}
    H.model_day = live_stub
    H._MODEL.clear()
    H._LIVE_TRY.clear()
    lb = F.bot(now)
    lb.brain = F.brain(status="tapped")
    lb.ledger, lb.adapter = [], None
    v1 = H.build(lb, None, now)
    v2 = H.build(lb, None, now + 60)
    check("today: the Brain's new setup triggers one replay (throttled to one per 5 min while it is missing)",
          len(calls) == 1 and calls[0] == (DAY, now) and v1["errors"] == [] and v2["live"], calls)
    H._MODEL[DAY] = ("sig", live_stub(DAY))
    calls.clear()
    v3 = H.build(lb, None, T(5, 0))
    lim = [o for o in v3["orders"] if o.get("model")]
    check("today: no replay once the cache has the setup; the armed limit is a WORKING model order until it expires",
          not calls and len(lim) == 1 and lim[0]["state"] == "WORKING" and lim[0]["t_end"] is None and lim[0]["px"] == 30797.25, (calls, lim))
    lb.brain = F.brain(status="tapped", trade=None)
    v4 = H.build(lb, None, T(5, 40))
    check("today: the expired limit is CANCELLED at its expiry", [o["state"] for o in v4["orders"] if o.get("model")] == ["CANCELLED"]
          and [o["t_end"] for o in v4["orders"] if o.get("model")] == [T(5, 25)])
    H._MODEL.clear()
    H.model_day = model_stub

    # ---- days list + routes
    dl = H.days(b, 30, now)
    check("days: newest first, with trades / real $", [d["day"] for d in dl][:2] == [DAY, PAST] and dl[0]["real_n"] >= 2
          and dl[1]["real_usd"] == 487.0 + 354.0, dl[:3])
    app = FastAPI()
    app.include_router(H.router)
    H._bot = lambda: b
    c = TestClient(app)
    r1, r2 = c.get(f"/api/next/holo?day={PAST}"), c.get("/api/next/holo/days")
    check("GET /api/next/holo?day= and /api/next/holo/days", r1.status_code == 200 and r1.json()["day"] == PAST and r1.json()["kind"] == "le-holo"
          and r2.status_code == 200 and r2.json()["days"][0]["day"] == DAY, (r1.status_code, r2.text[:200]))
    check("bad day -> today's session + an error line, never a 500", c.get("/api/next/holo?day=nope").json().get("day") == DAY)
    srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("server.py mounts the Holodeck router once (one include line)", srv.count("from engine.holo_api import router as holo_router") == 1
          and srv.count("app.include_router(holo_router)") == 1)

    # ---- phone files: size caps, cache
    ph = H.phone(b, now)
    check("holo.json <= 300 KB, every fill / trade / thought kept", ph["bytes"] <= H.PHONE_MAX and len(ph["fills"]) == len(v["fills"])
          and len(ph["trades"]) == len(v["trades"]) and len(ph["thoughts"]) == len(v["thoughts"]), ph.get("bytes"))
    big = F.bot(now)
    big.__dict__.update({k: getattr(b, k) for k in ("adapter", "ledger", "acct_b", "acct_c")})
    big.brain = {**b.brain, "log": [{"key": f"sweep:{i}", "t": T(3, 0) + i * 30, "kind": "sweep", "text": f"Swept a level {30700 + i}.25 ({i})" * 3}
                                    for i in range(400)]}
    vb = H.build(big, None, now)
    nonbar = len(json.dumps({**vb, "bars": {"1m": [], "5m": vb["bars"]["5m"]}}, separators=(",", ":"), default=str))
    old_max = H.PHONE_MAX
    H.PHONE_MAX = nonbar + 12 * 1024
    pt = H.phone(big, now)
    H.PHONE_MAX = old_max
    check("over the cap: the 1m bars trimmed to the trading windows, under the cap, nothing else lost",
          pt.get("trimmed") and pt["bytes"] <= nonbar + 12 * 1024 and len(pt["bars"]["1m"]) < len(vb["bars"]["1m"])
          and len(pt["thoughts"]) == len(vb["thoughts"]) == len([x for x in vb["thoughts"]]) and len(pt["fills"]) == len(vb["fills"]),
          (pt.get("bytes"), nonbar, len(pt["bars"]["1m"])))
    hs = H.hist(b, now, force=True)
    check("holo_hist.json: the last 10 trading days' trades with fills / thoughts / a bar window, <= 400 KB",
          hs["kind"] == "le-holo-hist" and [d["day"] for d in hs["days"]][:2] == [PAST, EMPTY] and hs["bytes"] <= H.HIST_MAX
          and all(t.get("fills") and "thoughts" in t and t.get("win") for d in hs["days"] for t in d["trades"]), [d["day"] for d in hs["days"]])
    check("holo_hist cached (same answer inside 10 min, no rebuild)", H.hist(b, now + 120) is hs)
    b.ledger = b.ledger + [row(now + 200, "exit", 1, E_LIT, reason="NO TRADE", pnl=0.0)]
    h2 = H.hist(b, now + 230)
    check("holo_hist rebuilt when a trade closes (a ledger row), at most once a minute", h2 is not hs and h2["t"] == now + 230 and H.hist(b, now + 240) is h2)
    b.ledger = b.ledger[:-1]
    old = H.HIST_MAX
    H.HIST_MAX = 3 * 1024
    hsm = H.hist(b, now, force=True)
    H.HIST_MAX = old
    check("holo_hist over its cap: older days' bars trimmed first, flagged", hsm.get("trimmed") is True and hsm["days"], hsm.get("bytes"))
    H.hist(b, now, force=True)

    # ---- the publisher ships both files in the live commit
    sent = {}

    def push_fn(payload, url, **kw):
        sent.update(kw.get("extra") or {})
        return {"ok": True, "commit": "abc", "bytes": 1}
    pub = LP.Publisher(b, push_fn=push_fn, url="https://github.com/x/y.git", clock=lambda: now, log=lambda *a: None)
    t0 = time.perf_counter()
    res = pub.publish(force=True)
    pms = (time.perf_counter() - t0) * 1000
    check("publisher: liveview.json + holo.json + holo_hist.json in the same commit", res.get("ok") and {"liveview.json", "holo.json", "holo_hist.json"} <= set(sent)
          and sent["holo.json"]["kind"] == "le-holo" and sent["holo_hist.json"]["kind"] == "le-holo-hist", sorted(sent))
    check("publisher: holo.json reuses the Live View's thinking (same LIT headline)", (sent["holo.json"]["now"] or {}).get("lit", {}).get("headline")
          == sent["liveview.json"]["strategies"]["lit"]["thinking"]["headline"])
    check(f"publisher: build times measured (extra_ms {pub.extra_ms}; publish {pms:.0f} ms)", {"liveview", "holo", "holo_hist"} <= set(pub.extra_ms)
          and "extra_ms" in pub.status() and pub.extra_ms["holo"] < 1500)
    check("publisher: the scrubbed files carry no local path", "/home/" not in json.dumps(sent["holo.json"]) and "/home/" not in json.dumps(sent["holo_hist.json"]))

    # ---- never raises on a broken bot
    class Broken:
        def __getattr__(self, k):
            raise RuntimeError("broken " + k)
    vb2 = H.build(Broken(), None, now)
    check("never raises: a broken bot gives the contract with [] / null and errors", vb2["kind"] == "le-holo" and isinstance(vb2["errors"], list)
          and vb2["fills"] == [] and vb2["trades"] == [] and set(vb2["bots"]) == {"lit", "atlas", "blitz"}, vb2.get("errors"))
    pbr, hbr = H.phone(Broken(), now), H.hist(Broken(), now, force=True)
    check("phone() / hist() / days() never raise either", pbr.get("kind") == "le-holo" and hbr.get("kind") == "le-holo-hist"
          and isinstance(H.days(Broken(), 5, now), list))
    weird = F.bot(now)
    weird.ledger = [None, {"t": "x"}, {"t": now, "side": "sell", "entry_t": "nope"}, row(now, "buy", "x", T(9, 0), legs="bad")]
    weird.adapter = SimpleNamespace(legs=[None, {"entry_id": "x", "entry_t": "y"}], history=None, name=None)
    vw = H.build(weird, None, now)
    check("garbage ledger rows / legs: still the contract", vw["kind"] == "le-holo" and not contract_errors(vw), contract_errors(vw)[:4])

    # ---- the committed sample fixture (the 3D page's tests use it)
    fx = json.load(open(os.path.join(ROOT, "tests", "fixtures", "holo_sample.json"), encoding="utf-8"))
    check("tests/fixtures/holo_sample.json follows the contract", not contract_errors(fx), contract_errors(fx)[:6])
    check("fixture: a busy day (LIT real + ATLAS real + BLITZ paper, a refused order, the LIT setup timeline)",
          {t["bot"] for t in fx["trades"]} == {"lit", "atlas", "blitz"} and any(o["state"] == "REJECTED" for o in fx["orders"])
          and all(next(t for t in fx["trades"] if t["bot"] == "lit")["setup"].get(k) for k in ("t_sweep", "t_idm", "t_disp", "t_cisd", "cisd"))
          and any(f["real"] and abs(f["slip_ticks"] or 0) == 1.0 for f in fx["fills"]))

    # ---- optional: the real LIT replay of a 2026 day (reads data/NQ_*.csv only)
    if os.path.exists(os.path.join(ROOT, "data", "NQ_5m.csv")) and os.environ.get("LE_HOLO_REAL", "1") != "0":
        import importlib
        Hr = importlib.reload(H)
        Hr.STORE, Hr.NARR_DIR, Hr.BRAIN_DIR, Hr.STATE_PATH = STORE, H.NARR_DIR, os.path.join(TMP, "brain2"), os.path.join(TMP, "x.json")
        Hr.CSV_FALLBACK = True
        t0 = time.perf_counter()
        m = Hr.model_day("2026-10-13")
        mt = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        Hr.model_day("2026-10-13")
        mt2 = (time.perf_counter() - t0) * 1000
        check(f"real data: the LIT backtest of 2026-10-13 (SHORT 06:03, TARGET; {mt:.0f} ms, cached {mt2:.0f} ms)",
              m and len(m["trades"]) == 1 and m["trades"][0]["exit_reason"] == "TARGET" and m["trades"][0]["dir"] == -1
              and any(s.get("detail") and s["detail"].get("t_idm") for s in m["setups"]) and mt2 < 1200, m and m["trades"])
        # the PC appends a NinjaTrader bar to data/nt_bars every minute (engine/live.py _archive_add), which invalidates
        # engine/fill_audit.load_bars: a FINISHED day (holo_hist on the publisher thread every 10 min / after each trade, a
        # past day's page) must not re-read the ~30 MB of CSV for it; today's replay still gets the fresh bars
        from engine import fill_audit as FA, pcbars
        arc0, bars0, ar0, reads = pcbars.ARCHIVE_DIR, dict(FA._BARS), pcbars.archive_read, []
        try:
            pcbars.ARCHIVE_DIR = os.path.join(TMP, "nt_bars")
            os.makedirs(pcbars.ARCHIVE_DIR, exist_ok=True)
            a1 = pcbars.archive_path("NQ", "1m")
            with open(a1, "w", encoding="utf-8") as fh:
                fh.write("time,open,high,low,close,volume\n1792400000,25000,25001,24999,25000.5,1\n")

            def bump(j):                                   # the poll's archive append (a new mtime)
                with open(a1, "a", encoding="utf-8") as fh:
                    fh.write(f"{1792400000 + 60 * j},25000,25001,24999,25000.5,1\n")
                os.utime(a1, (time.time() + 5 * j, time.time() + 5 * j))
            pcbars.archive_read = lambda *a, **k: (reads.append(a), ar0(*a, **k))[1]
            FA._BARS.update(key=None, d5=None, d1=None)
            Hr._frames(past=True)
            n0 = len(reads)
            bump(1)
            m3 = Hr.model_day("2026-10-13")
            Hr._frames(past=True)
            Hr.day_bars(SimpleNamespace(bars_tail=[], _lit_1m_store=None), "2026-10-13", False)
            n1 = len(reads)
            bump(2)
            d5n, d1n = Hr._frames()
            n2 = len(reads)
        finally:
            pcbars.archive_read, pcbars.ARCHIVE_DIR = ar0, arc0
            FA._BARS.update(bars0)
        check("finished days: a new NinjaTrader archive bar (every minute on the PC) re-reads no CSV for them (holo_hist / a "
              "past day), the same model; today's frames are re-read and carry the new bar",
              n0 == 2 and n1 == n0 and m3 == m and n2 == n0 + 2 and int(d1n["time"].max()) == 1792400000 + 120, (n0, n1, n2, m3 == m))
        Hr.CSV_FALLBACK = False
    shutil.rmtree(TMP, ignore_errors=True)
    n, k = len(RES), sum(RES)
    print(f"\n{k}/{n} passed ({time.time() - t_start:.1f} s)")
    return 0 if k == n else 1


def _close_case(now):
    e = T(8, 40)
    add = {"id": f"LE{e}ADDSMA1", "qty": 2, "filled": 2, "fill_px": 30812.0, "status": "filled", "sent_at": e + 600.5, "n": 1}
    lg = leg(e, 1, 3, 30800.25, e + 1.75, 30780.0, 30780.0, 30900.0, "ADDS", adds=[add])
    b = F.bot(now)
    b.adapter = FakeNT("Sim101", history=[lg])
    pnl = round((30815.0 - 30800.25) * 2 * 3 + (30815.0 - 30812.0) * 2 * 2 - 1.90 * 5, 2)
    b.ledger = [row(e + 1, "buy", 3, e, account="Sim101", entry=30800.0, stop=30780.0, target=30900.0, legs=[{"filled": 3, "fill_px": 30800.25}]),
                row(e + 600, "add", 2, e, account="Sim101"),
                row(T(9, 55) + 4, "exit", 5, e, account="Sim101", reason="TIME", pnl=pnl, exit_t=T(9, 55))]
    R = H.real_trades(b, DAY, now, [])
    f = {x["kind"]: x for x in R["fills"]}
    tr = R["trades"][0] if R["trades"] else {}
    ok = (set(f) == {"entry", "add", "exit"} and f["add"]["px"] == 30812.0 and f["add"]["qty"] == 2 and f["add"]["t"] == e + 600.5
          and tr.get("qty") == 5 and f["exit"]["t"] == float(T(9, 55) + 4) and f["exit"]["src"] == "model" and f["exit"]["real"] is False
          and abs(f["exit"]["px"] - 30815.0) < 0.01 and tr["exit"]["reason"] == "TIME" and tr["usd"] == pnl)
    return ok, (R["fills"], tr)


def _unclear_case(now) -> bool:
    """An entry whose answer was not OK while NinjaTrader did fill it (a leg filled): it is a position, shown as a fill."""
    e = T(8, 15)
    lg = leg(e, 1, 2, 30800.25, e + 4.0, 30780.0, 30780.0, 30840.0, "UNCL", status="protected")
    b = F.bot(now)
    b.adapter = FakeNT("Sim101", legs=[lg])
    b.ledger = [row(e + 1, "buy", 2, e, ok=False, account="Sim101", entry=30800.0, stop=30780.0, target=30840.0,
                    error="fill not reported yet", legs=[{"qty": 2, "ok": False, "state": "WORKING"}])]
    R = H.real_trades(b, DAY, now, [])
    return any(f["kind"] == "entry" and f["px"] == 30800.25 and f["t"] == e + 4.0 for f in R["fills"]) and len(R["trades"]) == 1


if __name__ == "__main__":
    raise SystemExit(main())
