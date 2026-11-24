"""day-brain-feed 2026-11-24: the Brain app feed (engine/brain_feed.py) on the PC's 15-minute report (tools/pc_report ext block "bf").
Read-only: it never trades, sizes, arms or writes. docs/BRAIN_FEED_PC.md.

  a. LIT       a replayed Brain (2026-10-14): armed limit 03:30 / in trade 05:26 / done 10:05 -> think (<= 8, ET times), next
               (setup, steps, waiting_for, dist_pts, window, limit / stop / target = the plan), levels (<= 12, known kinds)
  b. ATLAS / BLITZ / order flow from small fixtures (second.compact, blitz.compact, the order-flow files)
  c. market    the phase rules on made-up bars (expanding / retracing / ranging), today = since 18:00 ET, no bars = regime only
  d. safety    junk in = no exception; one bot failing = {"err"} for that bot only; the heartbeat is not changed; no trading import
  e. size      <= 2,000 bytes with very long texts; fit() cuts lesser bots first and never drops LIT
  f. report    "bf" rides the ext post (EXT_LAST), every post <= MAX_STATUS_BYTES, merged() has it, ext_hash ignores it,
               a brain_feed crash leaves the report as before
  g. glance    lead wire 4: brain_glance lit() carries "atr" and "ax" [limit, stop, target]
  h. preflight ATLAS's route reads kind before label (the label is "ATLAS <account>": readiness warned "on Sim" while LIVE)

    python -X utf8 -m tests.test_brain_feed
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from engine import brain_feed as F  # noqa: E402

check = AK.check
ET = ZoneInfo("America/New_York")
KINDS = {"sweep", "stop", "target", "fvg", "expansion", "retrace", "liq"}


def ts(y, mo, d, h, mi=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def bars_5m(t0, closes, spread=4.0):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        out.append((t0 + 300 * i, o, max(o, c) + spread / 2, min(o, c) - spread / 2, c))
        prev = c
    return out


def lit_part():
    from engine import brain
    day = "2026-10-14"
    B = {hm: brain.compact(brain.replay(day, ts(2026, 10, 14, *hm))) for hm in ((3, 30), (5, 26), (10, 5))}
    a = F.lit_bot(B[(3, 30)])
    nx = a["next"]
    plan = next(s["plan"] for s in reversed(B[(3, 30)]["setups"]) if s.get("status") in F.ARMED)
    check("a1. armed: next.limit / stop / target = the armed plan's, window = until its expiry, dist = |price - limit|",
          (nx.get("limit"), nx.get("stop"), nx.get("target")) == (plan["limit"], plan["stop"], plan["target"])
          and nx.get("window") == f"until {plan['expires_hm']} ET"
          and abs(nx.get("dist_pts") - abs(B[(3, 30)]["price"] - plan["limit"])) < 0.01, nx)
    check("a2. armed: steps = the Brain's 10 stages [{name, done}], cisd5 done, entry not yet",
          len(nx["steps"]) == 10 and {"name": "cisd5", "done": True} in nx["steps"] and {"name": "entry", "done": False} in nx["steps"], nx["steps"])
    th = a["think"]
    check("a3. think: <= 8 lines, each 'HH:MM words', <= 64 chars, the first = the armed limit, a VIX line",
          0 < len(th) <= 8 and all(len(x) <= F.LINE_N and x[:2].isdigit() and x[2] == ":" for x in th)
          and "limit" in th[0] and any(x[6:].startswith("VIX ") for x in th), th)
    lv = a["levels"]
    check("a4. levels: <= 12, known kinds, the stop + the target at the plan's prices, the VIX band as expansion",
          len(lv) <= 12 and all(r["kind"] in KINDS for r in lv)
          and any(r["kind"] == "stop" and r["price"] == plan["stop"] for r in lv)
          and any(r["kind"] == "target" and r["price"] == plan["target"] for r in lv)
          and any(r["kind"] == "expansion" for r in lv), lv)
    t = F.lit_bot(B[(5, 26)])["next"]
    check("a5. in trade: stop / target of the trade, steps up to entry done, no dist", t.get("stop") is not None and t.get("target") is not None
          and {"name": "entry", "done": True} in t["steps"] and t.get("dist_pts") is None, t)
    d = F.lit_bot(B[(10, 5)])["next"]
    check("a6. done for today: setup 'done for today', no limit / stop / target / dist", d.get("setup") == "done for today"
          and all(d.get(k) is None for k in ("limit", "stop", "target", "dist_pts")) and "Done for today" in (d.get("waiting_for") or ""), d)
    return B


def other_bots():
    now = ts(2026, 11, 24, 10, 0)
    sec = {"route": {"account_b": {"enabled": True, "keys": ["ema_london"]}},
           "strategies": {"ema_london": {"short": "EMA", "route": True, "state": {"stage": "armed", "text": "Pullback to the 20 EMA armed"},
                                         "brain": {"first_fail": "price not back at the EMA yet",
                                                   "plan": {"side": "long", "entry": 21418.25, "stop": 21402.0, "target": 21470.0, "when": "09:30-11:00 ET"},
                                                   "checks": [{"name": "trend", "ok": True}, {"name": "pullback", "ok": False}],
                                                   "log": [{"t": now - 600, "text": "Trend up on 15m (ok)"}],
                                                   "levels": [{"name": "London high", "px": 21430.0, "stage": "waiting"}]}},
                          "macd_sweep": {"short": "MACD", "candidate": True, "state": {"stage": "waiting", "text": "x"}}}}
    a = F.atlas_bot(sec, 21425.0)
    check("b1. ATLAS: next = the routed lobe's plan (limit = entry), steps from its checks, waiting = its first fail, dist from price",
          a["next"].get("limit") == 21418.25 and a["next"].get("stop") == 21402.0 and a["next"]["steps"][1] == {"name": "pullback", "done": False}
          and a["next"].get("waiting_for") == "price not back at the EMA yet" and a["next"].get("dist_pts") == 6.75
          and any("EMA:" in x for x in a["think"]) and not any("MACD" in x for x in a["think"]), a)
    check("b2. ATLAS levels: stop, target + its S/R levels (liq)", {r["kind"] for r in a["levels"]} >= {"stop", "target", "liq"}, a["levels"])
    bz = {"state": {"stage": "watching", "text": "Next check 11:00 ET: a 1m close above 21,460.00 = PAPER LONG, below 21,380.00 = PAPER SHORT"},
          "band": {"o0": 21420.0, "checks": [{"hm": "11:00", "up": 21460.0, "lo": 21380.0}]},
          "signals": [{"t": now - 3600, "dir": 1, "close": 21455.0, "taken": False, "why": "day filter"}]}
    b = F.blitz_bot(bz, 21425.0)
    check("b3. BLITZ (paper): the next band check as 2 expansion levels, dist to the nearer one, think has the signal",
          b.get("paper") is True and sorted(r["price"] for r in b["levels"] if r["kind"] == "expansion") == [21380.0, 21460.0]
          and b["next"].get("dist_pts") == 35.0 and b["next"].get("window") == "11:00 ET check" and any("signal long" in x for x in b["think"]), b)
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "data", "ticks"))
    check("b4. order flow: nothing on disk = no row", F.of_bot(d) == {})
    json.dump({"enabled": True}, open(os.path.join(d, "data", "tickrec.json"), "w"))
    for i in range(3):
        open(os.path.join(d, "data", "ticks", f"2026-11-{10 + i}.parquet"), "w").close()
    o = F.of_bot(d)
    check("b5. order flow: recorder on, 3 tick days -> waiting for 57 more, steps recorder done / 60 days not",
          o["next"]["waiting_for"] == "57 more NQ tick days" and o["next"]["steps"][0]["done"] is True and o["next"]["steps"][1]["done"] is False
          and "3 tick days" in o["think"][0], o)
    return sec, bz, d


def market_part():
    t0 = ts(2026, 11, 23, 18, 0)
    br = {"guards": {"vix": {"vix": 17.2, "move": 300.0}}, "price": None}
    up = [21000 + i * 1.0 for i in range(60)] + [21060 + i * 12 for i in range(6)]     # quiet, then a push to new highs
    m = F.market(bars_5m(t0, up), now=t0 + 66 * 300, br=br)
    check("c1. a push to a new day high with a big 30-min move = expanding; where ~100%, range measured", m.get("phase") == "expanding"
          and m.get("where_in_range_pct", 0) >= 90 and m.get("regime") == "normal (VIX 17.2)" and m.get("today_range_pts") > 60, m)
    pb = [21000 + i * 3.0 for i in range(40)] + [21120 - i * 8 for i in range(8)] + [21056.0] * 6
    m = F.market(bars_5m(t0, pb), now=t0 + 54 * 300, br=br)
    check("c2. a high, then price back >= 30% of the range = retracing", m.get("phase") == "retracing", m)
    fl = [21000 + (i % 4) for i in range(60)]
    m = F.market(bars_5m(t0, fl), now=t0 + 60 * 300, br=br)
    check("c3. flat bars = ranging", m.get("phase") == "ranging", m)
    old = bars_5m(t0 - 86400, [25000.0] * 30)
    m = F.market(old + bars_5m(t0, fl), now=t0 + 60 * 300, br=br)
    check("c4. 'today' starts 18:00 ET: yesterday's bars (at 25,000) are not in the range", m.get("today_range_pts", 999) < 20, m)
    check("c5. no bars = the regime only (VIX classes: calm < 15 <= normal < 20 <= high vol < 28 <= extreme)",
          F.market(None, br=br) == {"regime": "normal (VIX 17.2)"} and F.market([], br={}) == {}
          and F.market(None, br={"guards": {"vix": {"vix": 30}}})["regime"].startswith("extreme"))


def safety_part(B, sec, bz, root):
    hb = {"t": 1, "brain": B[(3, 30)], "second": sec, "blitz": bz}
    before = copy.deepcopy(hb)
    g = F.build(hb, root=root)
    check("d1. read-only: the heartbeat is not changed; all 4 bots present", hb == before and set(g["bots"]) == {"lit", "atlas", "blitz", "of"}, list(g.get("bots") or {}))
    junk = [None, {}, {"brain": "x"}, {"brain": [], "second": [1], "blitz": 5}, {"brain": {"setups": "x", "stages": [[1]], "log": [None, 3]},
            "second": {"strategies": {"a": None, "b": {"brain": {"plan": "x", "log": "y"}}}}, "blitz": {"state": 3, "signals": [None]}}]
    ok = True
    for j in junk:
        try:
            r = F.build(j, bars=[("x",), None, (1, 2)], root=root)
            ok = ok and (r is None or isinstance(r, dict))
        except Exception as e:  # noqa: BLE001
            ok = False
            print("   raised:", e)
    check("d2. junk heartbeats / bars never raise", ok)
    real = F.blitz_bot
    F.blitz_bot = lambda *a, **k: 1 / 0
    try:
        g2 = F.build(hb, root=root)
    finally:
        F.blitz_bot = real
    check("d3. one bot failing = {'err'} for that bot only, the others stay", "err" in g2["bots"]["blitz"] and g2["bots"]["lit"].get("next"), g2["bots"].get("blitz"))
    src = AK.read(F.__file__)
    check("d4. no trading import (ninjatrader / live / tradovate / account_b), no file write",
          not any(x in src for x in ("import ninjatrader", "engine.ninjatrader", "engine.live ", "from . import live", "tradovate", "account_b import",
                                     "open(p, \"w\"", "json.dump(")), "")
    return hb


def size_part(hb, root):
    g = F.build(hb, root=root)
    check("e1. the real-ish block is under 2,000 bytes", F.size(g) <= F.MAX_BYTES, F.size(g))
    big = copy.deepcopy(hb)
    for r in big["brain"]["log"]:
        r["text"] = "very long thought " * 40
    big["brain"]["levels"] = [{"label": "L" * 80, "price": 21000 + i, "taken": bool(i % 2), "kind": "gap"} for i in range(80)]
    big["second"]["strategies"]["ema_london"]["brain"]["log"] = [{"t": i, "text": "y " * 200} for i in range(40)]
    g = F.build(big, root=root)
    check("e2. very long texts + 80 levels still fit 2,000 bytes, LIT kept", F.size(g) <= F.MAX_BYTES and "lit" in g["bots"], F.size(g))
    g = F.build(big, root=root, max_bytes=700)
    check("e3. a 700-byte budget: lesser bots go first, LIT stays (with its next)", "lit" in g["bots"] and g["bots"]["lit"].get("next")
          and g.get("trimmed") is True, (F.size(g), list(g["bots"])))


def report_part(B, sec, bz):
    from engine import live_publish as lp
    from tests.test_live_publish import hb_payload
    from tools import pc_report as R
    t = ts(2026, 10, 14, 3, 30)
    hb = hb_payload(t)
    hb.update(brain=B[(3, 30)], second=sec, blitz=bz)
    p = lp.build(hb, now=t)
    snap = {"t": t, "hb": hb, "hb_t": t - 60, "server": True, "nt": True, "market_open": True, "entry_hours": True, "mode": "LIVE", "live": p,
            "bf_bars": bars_5m(ts(2026, 10, 13, 18, 0), [30700 + (i % 7) * 5 for i in range(100)])}
    core, exts = R.posts(snap)
    lt = R.merged(snap)
    check("f1. 'bf' is in EXT_LAST (after every other block), rides an ext post, merged() has it with the LIT next + market",
          "bf" in R.EXT_LAST and any("bf" in (e.get("x") or {}) for e in exts) and (lt.get("bf") or {}).get("bots", {}).get("lit", {}).get("next")
          and (lt.get("bf") or {}).get("market", {}).get("phase"), [list(e.get("x") or {}) for e in exts])
    check("f2. every post stays under MAX_STATUS_BYTES", all(R._size(x) <= R.MAX_STATUS_BYTES for x in [core, *exts]), [R._size(x) for x in [core, *exts]])
    e2 = copy.deepcopy(exts)
    for e in e2:
        if "bf" in e.get("x", {}):
            e["x"]["bf"]["bots"]["lit"]["think"] = ["changed"]
    check("f3. ext_hash ignores bf (a new thought is not 'news': no extra ntfy post)", R.ext_hash(exts) == R.ext_hash(e2))
    from engine import brain_feed
    real = brain_feed.build
    brain_feed.build = lambda *a, **k: 1 / 0
    try:
        core2, exts2 = R.posts(snap)
    finally:
        brain_feed.build = real
    check("f4. a brain_feed crash: the report still goes out, the same core, just no bf", core2 == core
          and not any("bf" in (e.get("x") or {}) for e in exts2) and exts2, "")
    cut = R._cuts("bf")
    v = copy.deepcopy(lt["bf"])
    for f in cut:
        f(v)
    check("f5. the bf cut steps make it <= 900 bytes", len(cut) == 2 and F.size(v) <= 900, F.size(v))


def glance_part(B):
    from engine import brain_glance as G
    arm = G.lit({"brain": B[(3, 30)], "running": True}, None)
    plan = next(s["plan"] for s in reversed(B[(3, 30)]["setups"]) if s.get("status") in F.ARMED)
    check("g1. glance lit(): atr = the Brain's ATR, ax = [limit, stop, target] of the armed plan",
          arm.get("atr") == round(B[(3, 30)]["atr"], 2) and arm.get("ax") == [plan["limit"], plan["stop"], plan["target"]], (arm.get("atr"), arm.get("ax")))
    done = G.lit({"brain": B[(10, 5)], "running": True}, None)
    check("g2. done for today: no ax (nothing armed, no open trade)", "ax" not in done and done.get("atr") is not None, done.get("ax"))
    g = G.build({"brain": B[(3, 30)], "running": True, "t": 1})
    check("g3. the glance still fits its budget", G.size(g) <= G.MAX_BYTES, G.size(g))


def preflight_part():
    from engine import preflight as PF
    def atlas(ab):
        r = [x for x in PF.arms({"second": {"route": {"account_b": ab}}}) if x[0] == "ATLAS 25K"]
        return r[0] if r else None
    live = atlas({"label": "ATLAS MFFU25K123", "kind": "LIVE", "enabled": True, "armed": True})
    sim = atlas({"label": "ATLAS Sim101", "kind": "SIM", "enabled": True, "armed": True})
    old = atlas({"label": "LIVE", "enabled": True, "armed": True})
    check("h1. preflight: ATLAS on the real account (label 'ATLAS <account>', kind LIVE) = LIVE, armed (no false 'on Sim'); SIM stays not ok; "
          "a label-only heartbeat still works", live == ("ATLAS 25K", True, "LIVE, armed") and sim[1] is False and sim[2].startswith("SIM")
          and old == ("ATLAS 25K", True, "LIVE, armed"), (live, sim, old))


def main():
    B = lit_part()
    sec, bz, root = other_bots()
    market_part()
    hb = safety_part(B, sec, bz, root)
    size_part(hb, root)
    report_part(B, sec, bz)
    glance_part(B)
    preflight_part()
    AK.finish()


if __name__ == "__main__":
    main()
