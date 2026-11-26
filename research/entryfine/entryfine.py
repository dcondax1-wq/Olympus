"""LIT entry refinement on 1m bars (research/entryfine/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/entryfine/entryfine.py   -> research/entryfine/results.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "moretrades"))
os.chdir(ROOT)
import moretrades as MT  # noqa: E402  (scoring: span_stats / walk_forward / SPANS)
from engine import lit  # noqa: E402

TICK = 0.25
ORIG = lit.simulate_x
MODE = {"tap": None, "post": 0.0}


def wrapped(M, B, cand, entry_px, tgt, stop, P, live=False):
    m = MODE["tap"]
    if m == "through":
        entry_px = entry_px - TICK
    elif m == "half":
        entry_px = (entry_px + stop) / 2.0
    t = ORIG(M, B, cand, entry_px, tgt, stop, P, live)
    if t and MODE["post"] and t.get("qty"):
        adj = MODE["post"] * lit.PV * t["qty"]       # take back the price edge the deeper limit gave (fill AT the level)
        t["pnl"] = round(t["pnl"] - adj, 2)
        t["low"] = float(t["low"]) - adj
    return t


lit.simulate_x = wrapped
VARS = [("E0 live", None, {}, 0.0),
        ("E1 tap 1 tick through", "through", {}, 0.0),
        ("E2 tap at 50% of the zone", "half", {}, 0.0),
        ("E3 limit expiry 20 min", None, {"wait": 4}, 0.0),
        ("E4 plain limit at 50%, no 1m CISD", "half", {"cisd1m": None}, 0.0),
        ("E5 plain limit at the level, fill only 1 tick through", "through", {"cisd1m": None}, TICK)]


def main():
    from tools import lit_final as F
    from tools import lit_adopt_combo as AC
    from tools import lit_big_ideas as BI
    t0 = time.time()
    M, _ = F.market(MT.LIVE["ref"], MT.LIVE.get("extra_boxes") or [])
    sessions = sorted(set(F.SESS) | {d for d, _, _ in M.days if d > F.SESS[-1] and dt.date.fromisoformat(d).weekday() < 5})
    res = {"made": "2026-11-26", "design": "research/entryfine/DESIGN.md", "sessions": [sessions[0], sessions[-1]], "variants": {}}
    base = None
    for nm, tap, x, post in VARS:
        MODE.update(tap=tap, post=post)
        P = {**lit.DEFAULTS, **MT.LIVE, **x}
        Mx, Cx = F.market(P["ref"], P["extra_boxes"])
        T = [t for t in lit.run_x(Mx, Cx, P, sessions, B1=F.bars(Mx, "1m"), B5=F.bars(Mx, "5m")) if t.get("qty")]
        base = base or T
        o = {"cfg": {"tap": tap, **x, "post_pts": post}, "spans": {k: MT.span_stats(T, sessions, a, z) for k, (a, z) in MT.SPANS.items()}}
        E = BI.short(BI.score(AC.units([t for t in T if t["day"] <= "2026-10-16"])))
        o["eval_path"] = {s: {k: E[s][k] for k in ("n", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_med", "mc_p10")} for s in E}
        o["walk_forward"] = MT.walk_forward(T, base, sessions) if T is not base else "-"
        res["variants"][nm] = o
        s, ep = o["spans"], o["eval_path"]
        print(f"[{time.time() - t0:4.0f}s] {nm:52s} " + " | ".join(
            f"{k}: {s[k]['tpw']}/wk PF {s[k]['pf']} ${s[k]['per_month']:,}/mo" for k in ("H1 2026", "H2 2026", "2021-25"))
            + f" | fresh ${s['fresh Oct19-Nov20']['net']:,} | 2wk {ep['H1']['p10']}/{ep['H2']['p10']} med {ep['H1']['pass_med']}/{ep['H2']['pass_med']}"
            + f" | 50K40 2021-25 {s['2021-25']['evals']['50K']['pass']}/{s['2021-25']['evals']['50K']['fail']} | WF {o['walk_forward']}", flush=True)
    MODE.update(tap=None, post=0.0)
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
