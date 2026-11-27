"""night-of-daycap 2026-11-27: the order-flow lane's per-day entry cap (engine/of_lane.py max_per_day, default 1 = the tested book:
the first absorbed signal of each day). Synthetic tick days (research/orderflow/of_sim.py) on the fake NinjaTrader, temp folders only.
  a. day_cap reading: missing / bad / below 1 = 1, a whole number >= 1 kept; tools/of_ladder.lane_day_cap reads it the same way
  b. day_entries: filled / live / pending / unclear count, refused and never-filled limits do not, other days do not, a trade's own
     market fallback is not a second entry, the adapter's saved history counts even when the lane's trade log lost it
  c. whole day with 3 taken signals: cap 1 -> 1 entry, the later ones "skipped: day cap"; cap 2 -> 2; missing key -> 1
  d. restart mid-day (a fresh adapter + module state after the first entry): still 1 entry; the open trade's exit is never capped
  e. /oflane status shows the cap; the ladder's step-1 hold lifts with the default cap and holds with cap 2
    python -X utf8 -m tests.test_of_daycap
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def entries(S, day):
    return [t for t in S["trades"] if t.get("day") == day and (t.get("filled") or t["status"] in ("sending", "open", "fallback", "unknown"))]


def main():
    from engine import of_lane as L
    import of_ladder as LD
    from tests.test_of_lane import Rig
    L.STEP_EVERY = 25
    # ---- a. reading the cap
    vals = [None, 1, 2, 3, 0, -1, "2", "x", 1.5, True, False, [], {}]
    got = [(L.day_cap({} if v is None else {"max_per_day": v}), LD.lane_day_cap({} if v is None else {"max_per_day": v})) for v in vals]
    check("a day_cap: missing/0/-1/'x'/1.5/bool/list = 1, 2 and '2' = 2, 3 = 3", [g[0] for g in got] == [1, 1, 2, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1], got)
    check("a ladder reads the cap exactly like the engine", all(a == b for a, b in got), got)
    check("a default config carries max_per_day 1", L.DEFAULT_CFG.get("max_per_day") == 1 and L.load_cfg("/nonexistent")["max_per_day"] == 1)
    # ---- b. counting
    day = "2026-09-18"
    T = lambda st, et, **kw: {"day": day, "status": st, "entry_t": et, **kw}
    S = {"trades": [T("refused", 1000 * 300), T("closed", 1001 * 300, filled=0, why="no fill: stopped before entry"),
                    T("closed", 1002 * 300, filled=1), {"day": "2026-09-17", "status": "closed", "entry_t": 900 * 300, "filled": 1}]}
    check("b refused / never-filled / other day do not count, a filled close does", L.day_entries(S, day) == 1, L.day_entries(S, day))
    for st in ("open", "sending", "fallback", "unknown"):
        S2 = {"trades": [T(st, 1003 * 300)]}
        check(f"b status {st} counts (fail closed)", L.day_entries(S2, day) == 1)
    S3 = {"trades": [T("fallback", 1004 * 300)]}
    check("b a trade's own market fallback (entry_t + 1) is not a second entry",
          L.day_entries(S3, day, exclude=1004 * 300 + 1) == 0 and L.day_entries(S3, day) == 1)

    class Ad:
        legs = []
        history = []
    import datetime as dt
    from zoneinfo import ZoneInfo
    t10 = int(dt.datetime(2026, 9, 18, 10, 5, tzinfo=ZoneInfo("America/New_York")).timestamp())
    a = Ad(); a.history = [{"entry_t": t10, "filled": 1, "closed": "stop filled"}]
    check("b the adapter's saved history counts when the lane's trade log lost the trade", L.day_entries({"trades": []}, day, a) == 1)
    a.history = [{"entry_t": t10, "filled": 0, "closed": "entry cancelled"}]
    check("b an unfilled, closed adapter leg does not count", L.day_entries({"trades": []}, day, a) == 0)
    a.history = []; a.legs = [{"entry_t": t10}]
    check("b a live adapter leg (resting limit) counts", L.day_entries({"trades": []}, day, a) == 1)
    a.legs = []; a.history = [{"entry_t": t10, "filled": 1}]
    check("b both sources for one entry = 1, not 2", L.day_entries({"trades": [T("closed", t10, filled=1)]}, day, a) == 1)
    # ---- c / d. whole days
    sp = importlib.util.spec_from_file_location("t_sim_cap", os.path.join(ROOT, "research", "orderflow", "of_sim.py"))
    Sim = importlib.util.module_from_spec(sp); sp.loader.exec_module(Sim)
    W = Sim.world(7, "planted", seed=31, lvl=True, keep_ticks=True)
    d0, d1 = "2026-09-17", "2026-09-18"

    def day_run(cfg, drop_key=False, restart=False):
        with tempfile.TemporaryDirectory() as td:
            g = Rig(td, W, d0, d1, cfg=cfg)
            if drop_key:
                p = os.path.join(g.root, "data", L.CFG_NAME)
                c = json.load(open(p)); c.pop("max_per_day", None); json.dump(c, open(p, "w"))
            if not restart:
                g.run(g.hm(9, 25), g.hm(16, 6))
                return g.S(), None
            t, t_end, first = g.hm(9, 25), g.hm(16, 6), None
            while t < t_end:
                g.run(t, t + 60)
                t += 60
                if first is None and entries(g.S(), d1):
                    first = t
                    importlib.reload(L)            # a new process: no module memory, a new adapter (its own saved state)
                    L.STEP_EVERY = 25
                    g.L = L
                    g.new_adapter()
            return g.S(), first

    S1, _ = day_run({"max_per_day": 1})
    taken = [r for r in S1["paper"]["rows"] if r.get("taken")]
    e1 = entries(S1, d1)
    capped = [t for t in S1["trades"] if t["status"] == "refused" and "skipped: day cap" in t.get("why", "")]
    check("c the test day has 3 taken signals", len(taken) == 3, len(taken))
    check("c cap 1: one entry, the later signals refused 'skipped: day cap'", len(e1) == 1 and len(capped) >= 1,
          [(t["status"], t.get("why", "")[:70]) for t in S1["trades"]])
    check("c cap 1: the first entry is the day's first taken signal", e1 and e1[0]["row_id"] == min(taken, key=lambda r: r["t_sig"])["id"],
          (e1[:1], [r["id"] for r in taken]))
    check("c cap 1: the entry still exits (closed with an exit, not capped)", e1 and e1[0]["status"] == "closed" and e1[0].get("why"),
          e1[:1])
    S2, _ = day_run({"max_per_day": 2})
    e2 = entries(S2, d1)
    check("c cap 2: two entries", len(e2) == 2, [(t["status"], t.get("why", "")[:70]) for t in S2["trades"]])
    S0, _ = day_run({}, drop_key=True)
    check("c missing key: one entry (default 1)", len(entries(S0, d1)) == 1, [(t["status"], t.get("why", "")[:70]) for t in S0["trades"]])
    SR, first = day_run({"max_per_day": 1}, restart=True)
    er = entries(SR, d1)
    check("d restart after the first entry: still one entry, later signals day-capped",
          first is not None and len(er) == 1 and any("skipped: day cap" in t.get("why", "") for t in SR["trades"]),
          (first, [(t["status"], t.get("why", "")[:70]) for t in SR["trades"]]))
    check("d restart: the open trade is managed to its exit", er and er[0]["status"] == "closed", er[:1])
    # ---- e. words + ladder
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "data"))
        json.dump({**L.DEFAULT_CFG, "on": True}, open(os.path.join(td, "data", L.CFG_NAME), "w"))
        st = L.status_text(td)
    check("e /oflane status names the day cap", "day cap 1 entry a day" in st, st)
    base = [{"day": f"2026-12-{i + 1:02d}", "R": 0.6, "t": i, "first": True} for i in range(30)]
    try:
        held_ok = True
        d_cap = LD.evaluate(base, lane_capped=LD.lane_day_cap({}) == 1)
        d_two = LD.evaluate(base, lane_capped=LD.lane_day_cap({"max_per_day": 2}) == 1)
    except Exception as ex:  # noqa: BLE001
        held_ok, d_cap, d_two = False, ex, None
    check("e ladder: the default cap counts as capped, cap 2 does not", held_ok and LD.lane_day_cap({}) == 1
          and LD.lane_day_cap({"max_per_day": 2}) == 2, (d_cap, d_two))
    # ---- rt (red team #37): the book is the paper bot's FIRST taken signal; a refused / cancelled first signal gives no later trade
    tk = sorted(taken, key=lambda r: r["t_sig"])
    SP = {"paper": S1["paper"], "trades": []}
    check("rt signal_rank: the day's taken signals rank 0, 1, 2", [L.signal_rank(SP, r, d1) for r in tk] == [0, 1, 2],
          [L.signal_rank(SP, r, d1) for r in tk])
    for first in ({"day": d1, "status": "refused", "entry_t": tk[0]["t_sig"] + 300, "why": "news"},
                  {"day": d1, "status": "closed", "entry_t": tk[0]["t_sig"] + 300, "filled": 0, "stop_first": True,
                   "why": "no fill: stopped before entry"}):
        S4 = {"paper": S1["paper"], "trades": [first], "closes": [], "day": d1}
        res = {}
        for cap in (1, 2):
            try:
                why, _q, _fc = L.entry_guards(S4, dict(L.DEFAULT_CFG, on=True, account="Sim102", max_per_day=cap), None, tk[1],
                                              tk[1]["t_sig"] + 301, float(tk[1]["level_px"]), False)
            except Exception as ex:  # noqa: BLE001
                why = [f"error {ex!r}"]
            res[cap] = why
        check(f"rt first signal {first['status']} ({first['why']}): no entry used, yet the 2nd signal is day-capped at cap 1",
              L.day_entries(S4, d1) == 0 and res[1] and str(res[1][0]).startswith("skipped: day cap (paper signal 2"), res[1])
        check(f"rt ... and not day-capped at max_per_day 2", not any("day cap" in str(w) for w in res[2]), res[2])
    n = sum(RES)
    print(f"\nof_daycap: {n}/{len(RES)} " + ("ALL OK" if n == len(RES) else "FAILURES"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
