"""LIT scale-in option (engine/lit.py "scale_in", engine/sizing.scale_in_qty; research/writeups/lit-big-ideas.md). Default off.

    python -X utf8 -m tests.test_lit_scale_in

1. Off by default: lit.DEFAULTS["scale_in"] is None and live_model.json "lit" does not set it.
2. Sizing: scale_in_qty caps (the first entry's $ risk, 60% of the room, the soft daily loss left, 40 micros, earlier adds).
3. Engine == research: run_x on the live LIT params with scale_in on gives the same 2026 trades (entry, first-entry exit
   unchanged where no add happened) and, for every trade with an add, the same add price, add points and exit as the
   research simulator (tools/lit_big_ideas.py padd) that produced the published numbers.
4. scale_trade on a scaled-in trade (the weekly stop) scales the first entry and the adds together.
Run tests.test_lit_live --days for the default 120/120. One process.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit  # noqa: E402
from engine.sizing import scale_in_qty  # noqa: E402

CAND = {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info else ''}")
    return bool(ok)


def main():
    r = []
    live = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    r.append(check("default off", lit.DEFAULTS.get("scale_in") is None and "scale_in" not in live))
    # ---- sizing: 10 micros, 20-pt stop -> budget $400; add risk 22 pts -> (22.25 x 2 + 1.90) = $46.40 / micro -> 8
    r.append(check("budget = first entry's $ risk", scale_in_qty(10, 10, 20.0, [{"rk": 22.0, "prev_rk": []}]) == [8],
                   scale_in_qty(10, 10, 20.0, [{"rk": 22.0, "prev_rk": []}])))
    r.append(check("f 0.5 -> 5", scale_in_qty(10, 10, 20.0, [{"rk": 22.0, "prev_rk": []}], f=0.5) == [5]))
    r.append(check("room cap 60% of $300", scale_in_qty(10, 10, 20.0, [{"rk": 22.0, "prev_rk": []}],
                                                         state={"room": 300.0, "cum": 0.0}) == [3]))
    r.append(check("soft daily loss left $100", scale_in_qty(10, 10, 20.0, [{"rk": 22.0, "prev_rk": []}],
                                                              state={"room": 2000.0, "cum": -900.0}) == [2]))
    r.append(check("40 micros max", scale_in_qty(38, 38, 20.0, [{"rk": 5.0, "prev_rk": []}]) == [2]))
    r.append(check("second add pays for the first's open risk",
                   scale_in_qty(10, 10, 20.0, [{"rk": 10.0, "prev_rk": []}, {"rk": 10.0, "prev_rk": [10.0]}], f="max") == [17, 2]))
    # ---- engine vs research
    from tools import lit_final as F
    from tools import lit_big_ideas as BI
    S26 = [d for d in F.SESS if d >= "2026-01-01"]
    base = F.run(live, S26)
    on = F.run({**live, "scale_in": CAND}, S26)
    r.append(check("same trades (day, entry, side, stop, target)",
                   [(t["day"], t["entry_t"], t["dir"], t["stop_px"], t["target_px"]) for t in base]
                   == [(t["day"], t["entry_t"], t["dir"], t["stop_px"], t["target_px"]) for t in on], f"{len(base)} / {len(on)}"))
    U = {t["entry_t"]: t for t in BI.live()}
    bad, nadd = [], 0
    for b, t in zip(base, on):
        u = U.get(t["entry_t"])
        if u is None or not u["on1"]:
            if t.get("adds") or t["exit"] != b["exit"]:
                bad.append((t["day"], "5m day changed"))
            continue
        s = BI.padd(u, {"trig": "cisd", "pb": CAND["pb"], "rat": True, "rat_k": CAND["rat_k"], "n": 1, "min_rk": CAND["min_rk"]})
        ea = [(a["px"], a["pts"]) for a in (t.get("adds") or [])]
        sa = [(round(a["px"] * t["dir"], 2), round(a["pts"], 4)) for a in s["adds"]]
        if ea != sa or t["exit"] != s["exit"]:
            bad.append((t["day"], t["exit"], s["exit"], ea, sa))
        if not t.get("adds") and (t["exit"] != b["exit"] or abs(t["pnl"] - b["pnl"]) > 1e-6):
            bad.append((t["day"], "no add but changed"))
        nadd += bool(t.get("adds"))
    r.append(check(f"engine adds == research simulator ({nadd} trades with an add)", not bad, bad[:3]))
    # ---- scale_trade on a scaled-in trade
    t = next(t for t in on if t.get("adds") and t["adds"][0]["qty"] >= 2)
    h = lit.scale_trade(t, 0.5)
    want = t["pts"] * lit.PV * h["qty"] - lit.COMM * h["qty"] + sum(a["qty"] * (a["pts"] * lit.PV - lit.COMM) for a in h["adds"])
    r.append(check("scale_trade x0.5 scales the adds", h["qty"] == max(1, t["qty"] // 2)
                   and h["adds"][0]["qty"] == t["adds"][0]["qty"] // 2 and abs(h["pnl"] - round(want, 2)) < 0.01))
    print(f"{sum(r)}/{len(r)} checks passed")
    return all(r)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
