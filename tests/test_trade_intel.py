"""Trade Intelligence (tools/trade_intel.py -> research/lab/trade_intel.json): rows per source, no look-ahead in the entry
columns, the bucket math, the journal's live features, the cloud merge and the JSON size budget.

  python -X utf8 -m tests.test_trade_intel            # ~1-2 min (4 look-ahead cuts)
  python -X utf8 -m tests.test_trade_intel --cuts 2   # quicker
Read-only: builds nothing in research/ (the stored file is read, the look-ahead check runs in memory).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import trade_intel as TI  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


def rows_of(d):
    keys = [c["key"] for c in d["cols"]]
    return [dict(zip(keys, r)) for r in d["rows"]]


# ------------------------------------------------------------------------------------------------ stored file
def stored():
    d = TI._load(TI.OUT)
    check("trade_intel.json exists and is current for run lit_live", d and (d.get("meta") or {}).get("run_stamp") == TI._run_stamp()[1],
          "run python -X utf8 tools/trade_intel.py")
    if not d:
        return None
    from tools import runlib as rl
    run = rl.load(TI.RUN_ID)
    R = rows_of(d)
    bt = [r for r in R if r["source"] == "backtest"]
    c = run["trade_cols"]
    check("rows = sources: one backtest row per run lit_live trade", len(bt) == len(run["trades"])
          and sorted((r["day"], r["entry_t"]) for r in bt) == sorted((x[c.index("day")], x[c.index("entry_t")]) for x in run["trades"]),
          (len(bt), len(run["trades"])))
    check("every row has every column", all(len(x) == len(d["cols"]) for x in d["rows"]) and len(d["cols"]) >= 60, len(d["cols"]))
    check("~40+ entry columns, outcomes marked 'after'", sum(1 for x in d["cols"] if x["when"] == "entry") >= 40
          and {x["key"] for x in d["cols"] if x["when"] == "after"} >= {"exit", "r", "pnl", "mfe", "mae", "mins", "t1r", "heat"})
    by = {r["span"]: 0 for r in bt}
    for r in bt:
        by[r["span"]] += 1
    check("spans: 2026 H1 80 / H2 40 / 2021-25 510 (run lit_live)", by.get("H1") == 80 and by.get("H2") == 40 and by.get("2021-25") == 510, by)
    T = d["totals"]
    check("totals match the run: 2026 H1 PF 4.98 +$33,891, H2 PF 2.69 +$9,493", abs(T["H1"]["net"] - 33891.48) < 1 and T["H1"]["pf"] == 4.98
          and abs(T["H2"]["net"] - 9493.46) < 1 and T["H2"]["pf"] == 2.69, T)
    check("outcomes agree with R / exit", all(r["outcome"] == TI.outcome_of(r["r"]) for r in bt)
          and all(not r["clean_win"] or r["exit"] == "TARGET" for r in bt) and all(not r["gave_back"] or (r["mfe"] >= 1 and r["r"] < 0.5) for r in bt))
    check("time to +1R only when MFE reached 1R", all(r["t1r"] is None or r["mfe"] >= 1.0 for r in bt)
          and sum(1 for r in bt if r["mfe"] >= 1.0 and r["t1r"] is None) <= 5,
          [(r["day"], r["mfe"], r["t1r"]) for r in bt if (r["t1r"] is None) != (r["mfe"] < 1.0)][:5])
    check("heat before +1R never above the trade's MAE", all(r["heat"] <= r["mae"] + 1e-6 for r in bt))
    check("2026 rows carry a chart id (replays)", sum(1 for r in bt if r["span"] in ("H1", "H2") and r["chart"]) >= 110)
    sz = os.path.getsize(TI.OUT)
    cp = json.dumps(TI.compact(d), separators=(",", ":"))
    check("size budget: trade_intel.json < 1.5 MB, the data.json cut < 60 KB", sz < 1_500_000 and len(cp) < 60_000, (sz, len(cp)))
    return d


# ------------------------------------------------------------------------------------------------ journal features
def journal(d):
    """The learning loop's journal (data/lit_journal.jsonl, source backtest: engine/lit_learn.live_features on the same
    trades) holds the same lit_select features: the intel rows must agree with it."""
    J = [r for r in TI._journal(os.path.join(ROOT, "data", "lit_journal.jsonl")) if r.get("source") == "backtest" and r.get("f")]
    if not J:
        check("journal features (skipped: no backtest records in data/lit_journal.jsonl)", True)
        return
    R = {(r["day"], r["entry_t"]): r for r in rows_of(d) if r["source"] == "backtest"}
    pairs = [(R[(j["day"], int(j["entry_t"]))], j["f"]) for j in J if (j["day"], int(j["entry_t"])) in R]
    m = {"depth_atr": "depth", "disp": "disp", "idm_n": "idm_n", "idm_dist": "idm_dist", "obst_r": "obst_r", "vix": "vix", "leg_bars": "leg_bars"}
    bad = [(r["day"], k) for r, f in pairs for k, fk in m.items() if f.get(fk) is not None and r[k] is not None and abs(float(r[k]) - float(f[fk])) > 0.011]
    check(f"intel entry features = the journal's (lit_select feats) on {len(pairs)} 2026 trades", len(pairs) >= 100 and not bad, bad[:6])


# ------------------------------------------------------------------------------------------------ look-ahead
def lookahead(cuts=4, seed=5):
    """Cut the 5m data at each picked trade's fill bar (that bar reduced to its open), rebuild the market + candidates on
    the cut window, and recompute every entry column: it must equal the same columns on the full window."""
    from engine import lit
    from engine.data import Bars, load
    from tests.test_lit_lookahead import _cut
    P = {**TI.live_params(), "tf": "5m"}
    full = load("NQ", "5m")
    a = int(np.searchsorted(np.array(full.date_str), "2025-08-01"))
    B = full.slice(a, len(full))
    Mf = lit.Market(bars=B, extra_boxes=P["extra_boxes"])
    Cf = lit.candidates(Mf, ref=P["ref"])
    Tf = lit.run_x(Mf, Cf, P)
    T26 = [t for t in Tf if t["day"] >= "2026-01-01"]
    rng = random.Random(seed)
    picks = sorted(rng.sample(T26, min(cuts, len(T26))), key=lambda t: t["entry_t"])
    Xf = TI.Ctx(Mf, Cf)
    full_rows = {(r["day"], r["entry_t"]): r for r in TI.rows_for(Xf, picks, P, T_hist=Tf)}
    entry_keys = [c[0] for c in TI.COLS if c[3] == "entry" and c[0] not in ("fill", "wk_half", "micros", "risk_usd")]
    bad, n = [], 0
    for t in picks:
        cut = int(np.searchsorted(Mf.t, int(t["entry_t"]), side="right") - 1)       # the 5m bar the fill is in (just opened)
        Mc = lit.Market(bars=_cut(B, cut), extra_boxes=P["extra_boxes"])
        Cc = lit.candidates(Mc, ref=P["ref"])
        tc = dict(t)
        z = next((z for z in Cc if z["day"] == t["day"] and z["dir"] == t["dir"] and int(Mc.t[z["i"]]) == int(Mf.t[t["i"]])), None)
        if z is None:
            bad.append((t["day"], "setup missing on the cut data"))
            continue
        tc["i"] = z["i"]
        Xc = TI.Ctx(Mc, Cc)
        # entry feats use the plan + the trade's own fill facts (stop, target, fill time: known when the order goes in) and
        # the finished trades before the CISD close (from the full run: they all ended before the cut)
        plans = TI.plans_by_day(Xc, P, {t["day"]})
        zz, pl, same = plans[(t["day"], int(z["i"]), int(t["dir"]))]
        H = [h for h in TI.hist_of(Tf) if h["exit_t"] <= int(Mc.t[z["i"]]) + 300]
        rc = {"source": "backtest", "day": t["day"], "entry_t": int(t["entry_t"])}
        rc.update(TI.time_cols(t["day"], t["entry_t"]))
        rc.update(TI.entry_feats(Xc, zz, pl, same, H, tc))
        rf = full_rows[(t["day"], int(t["entry_t"]))]
        for k in entry_keys:
            n += 1
            a_, b_ = rf.get(k), rc.get(k)
            if isinstance(a_, float) or isinstance(b_, float):
                same_v = (a_ is None and b_ is None) or (a_ is not None and b_ is not None and abs(a_ - b_) < 1e-6)
            else:
                same_v = a_ == b_
            if not same_v:
                bad.append((t["day"], k, a_, b_))
    check(f"no look-ahead: {n} entry values on {len(picks)} trades equal on data cut at the fill bar", n > 0 and not bad, bad[:8])


# ------------------------------------------------------------------------------------------------ bucket math
def bucket_math():
    rows = [{"r": 1.0, "pnl": 100.0}, {"r": -1.0, "pnl": -50.0}, {"r": 0.0, "pnl": 0.0}, {"r": 2.0, "pnl": 200.0}]
    s = TI.stats(rows)
    check("stats: n, win % ($ > 0), avg R, PF, net", s == {"n": 4, "win": 50.0, "avg_r": 0.5, "pf": 6.0, "net": 250.0}, s)
    check("terciles (nearest rank) split 1..9 at 4 / 6, buckets low / mid / high", TI.terciles(list(range(1, 10))) == [4, 6]
          and [TI.bucket_of(v, "num", [4, 6]) for v in (4, 5, 6, 7)] == ["low", "mid", "mid", "high"], TI.terciles(list(range(1, 10))))
    check("terciles: too few values -> no split", TI.terciles([1, 2, 3]) is None)
    rng = random.Random(1)

    def mk(span, x, good):
        r = (1.5 if x > 0.5 else -0.5) if good else (rng.choice([1.5, -0.5]))
        return {"source": "backtest", "span": span, "f": x, "flag": x > 0.5, "r": r, "pnl": r * 100}
    R = [mk(s, rng.random(), True) for s in ("H1", "H2", "2021-25") for _ in range(60)]
    old = TI.ENTRY
    try:
        TI.ENTRY = [("f", "F", "num", "entry", "t", ""), ("flag", "Flag", "bool", "entry", "t", "")]
        sg = {s["key"]: s for s in TI.signs(R)}
        check("a feature that pays in both halves is consistent (high better), held in 2021-25",
              sg["f"]["consistent"] and sg["f"]["better"] == "high" and sg["f"]["held_5y"] and sg["flag"]["better"] == "yes", sg["f"]["why"])
        R2 = [{**r, "r": -r["r"], "pnl": -r["pnl"]} if r["span"] == "H2" else r for r in R]
        sg2 = {s["key"]: s for s in TI.signs(R2)}
        check("the same feature flipped in H2 is not consistent", not sg2["f"]["consistent"] and "flips" in sg2["f"]["why"], sg2["f"]["why"])
        R3 = [r for r in R if not (r["span"] == "H2" and r["f"] > 0.5)][:120] + [r for r in R if r["span"] != "H2"]
        sg3 = {s["key"]: s for s in TI.signs([r for r in R3 if r["span"] != "H2"] + [r for r in R if r["span"] == "H2"][:5])}
        check("too few trades in a half -> not consistent", not sg3["f"]["consistent"], sg3["f"]["why"])
    finally:
        TI.ENTRY = old


# ------------------------------------------------------------------------------------------------ paper / live merge
def merge(d):
    st = {"ledger": {"1792393740": {"day": "2026-10-19", "entry": "10-19 03:09", "side": "SHORT", "exit": "BE", "R": -0.02, "taken": True,
                                    "usd": -11.4, "qty": 6, "exit_ts": 1792406400, "entry_px": 29763.25, "stop_px": 29813.75,
                                    "target_px": 29489.75, "exit_px": 29763.5, "risk_pts": 50.5},
                     "1792480000": {"day": "2026-10-20", "side": "LONG", "exit": "OPEN", "taken": True, "R": 0, "usd": 0, "qty": 3},
                     "1792490000": {"day": "2026-10-20", "side": "LONG", "taken": False, "exit": "STOP"}},
          "pc": {"acct": {"trades": [{"day": "2026-10-19", "entry_t": 1792393741, "exit_t": 1792406401, "side": "SHORT", "qty": 6,
                                      "entry": 29763.25, "stop": 29813.75, "target": 29489.75, "exit": "BE", "r": -0.03, "pnl": -12.0, "risk_pts": 50.5}]}}}
    J = [{"source": "cloud", "day": "2026-10-19", "entry_t": 1792393740, "mfe": 1.3, "mae": 0.2, "swept": ["lon23_h"], "wk_mult": 1.0,
          "f": {"disp": 1.4, "idm_n": 1, "depth": 2.0, "vix": 19.9, "major": 0.0}},
         {"source": "cloud", "day": "2026-10-16", "entry_t": 1792130000, "exit_t": 1792133000, "side": "LONG", "entry_px": 1, "stop_px": 0,
          "target_px": 3, "risk_pts": 1, "qty": 1, "exit": "TARGET", "r": 2.0, "pnl": 4.0}]
    m = TI.merge_live(d, st, J)
    R = rows_of(m)
    src = [r["source"] for r in R if r["source"] != "backtest"]
    check("merge: 2 paper (ledger + journal-only) + 1 live, the open and the skipped trade left out", sorted(src) == ["live", "paper", "paper"]
          and m["meta"]["sources"] == {"backtest": 630, "paper": 2, "live": 1}, m["meta"]["sources"])
    p = next(r for r in R if r["source"] == "paper" and r["entry_t"] == 1792393740)
    check("merge: the paper row = ledger facts + journal features", p["disp"] == 1.4 and p["depth_atr"] == 2.0 and p["major"] is False
          and p["rr"] == 5.42 and p["risk_usd"] == 606.0 and p["gave_back"] is True and p["monday"] is True and p["mins"] == 211.0, p)
    check("merge: totals gain the paper / live lines, signs stay the backtest's", m["totals"]["paper"]["n"] == 2 and m["totals"]["live"]["n"] == 1
          and m["signs"] == d["signs"])
    check("merge: stored file untouched", sum(1 for r in d["rows"] if r[0] != "backtest") == 0)
    c = TI.compact(m)
    check("compact: the 3 paper / live rows, summary, <= 10 top signs", len(c["live_rows"]) == 3 and len(c["top"]) <= 10 and c["summary"]["winners"] is not None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", type=int, default=4)
    a = ap.parse_args(argv)
    d = stored()
    if d:
        journal(d)
        merge(d)
    bucket_math()
    lookahead(a.cuts)
    ok = all(RES)
    print(f"trade intel: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
