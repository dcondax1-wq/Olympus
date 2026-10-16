"""Silver Bullet lab runner.

  python tools/lab_sb_run.py smoke NQ            # mechanics check on recent bars (prints trades, no scoring)
  python tools/lab_sb_run.py score               # score every pre-declared variant on NQ and ES, all periods
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.strategy_lab import PERIODS, PV, bars, score  # noqa: E402
from tools.lab_models import silver_bullet as sb  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lab")

# Pre-declared variants (documented choices only; every one that is run is reported).
VARIANTS = {
    "base": {},                                          # AM+PM, edge entry, swing stop, DOL target
    "am": {"windows": [[600, 660]]},                     # AM window only
    "ce": {"entry": "ce"},                               # entry at consequent encroachment (50%)
    "rr2": {"target": "rr", "rr": 2.0},                  # fixed 2R target instead of the draw on liquidity
}


def smoke(sym):
    b = bars(sym, "5m", "2026-09-01", "2026-10-16", warmup_days=5)
    t0 = time.time()
    dbg = []
    tr = sb.run(b, {"sym": sym}, None, _debug=dbg)
    print("secs", round(time.time() - t0, 2), "trades", len(tr), "armed", len(dbg))
    for x in tr[-15:]:
        et = dt.datetime.fromtimestamp(x["entry_t"], ET).strftime("%H:%M")
        xt = dt.datetime.fromtimestamp(x["exit_t"], ET).strftime("%H:%M")
        print(x["day"], et, xt, x["dir"], x["entry"], x["stop"], x["target"], x["exit"], x["exit_kind"], x["qty"],
              x["pnl"], x["r"], x["setup"], x["fvg"])
    print(collections.Counter(t["exit_kind"] for t in tr))
    st = sb.state(b, {"sym": sym})
    st.pop("params", None)
    print(json.dumps(st, default=str)[:1500])


def score_all(syms=("NQ", "ES"), names=None):
    rows = []
    for sym in syms:
        a = "2025-04-14"
        b = bars(sym, "5m", a, PERIODS["all18m"][1], warmup_days=7)
        for vname, vp in VARIANTS.items():
            if names and vname not in names:
                continue
            p = {"sym": sym, **vp}
            t0 = time.time()
            tr = sb.run(b, p, None)
            name = f"SB_{sym}_{vname}"
            with open(os.path.join(OUT, f"SB_trades_{sym}_{vname}.json"), "w", encoding="utf-8") as fh:
                json.dump(tr, fh)
            for per in ("ytd", "aug_oct", "y2025", "all18m"):
                s = score(tr, name, per, params=p, notes="ICT Silver Bullet")
                rows.append({"name": name, "period": per, **{k: s[k] for k in (
                    "trades", "tpw", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day", "rolling_pass",
                    "zero_edge_pass", "b2b_pass", "b2b_fail", "months", "losing_months", "weeks_zero", "weeks_in_2_5")}})
            print(f"  ({time.time() - t0:.1f}s)")
    with open(os.path.join(OUT, "SB_results.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, default=float)


def xcheck_1m(vname="base"):
    """Same rules on 1m bars vs 5m bars over the only 1m history we have (last ~4 weeks). Mechanics check, not a score."""
    out = {}
    for sym in ("NQ", "ES"):
        for tf, scale in (("5m", 1), ("1m", 5)):
            b = bars(sym, tf, "2026-09-21", "2026-10-16", warmup_days=3)
            p = {"sym": sym, **VARIANTS[vname], "sweep_lookback": 12 * scale}
            tr = [t for t in sb.run(b, p, None) if t["day"] >= "2026-09-22"]
            n = len(tr)
            out[(sym, tf)] = tr
            wr = 100 * sum(t["pnl"] > 0 for t in tr) / max(n, 1)
            print(f"{sym} {tf}: trades={n} win%={wr:.0f} avgR={sum(t['r'] for t in tr) / max(n, 1):+.2f} "
                  f"net={sum(t['pnl'] for t in tr):+,.0f}")
    return out


def _agg(g):
    n = len(g)
    if not n:
        return "n=0"
    return (f"n={n} wr={100 * sum(t['pnl'] > 0 for t in g) / n:.0f}% avgR={sum(t['r'] for t in g) / n:+.2f} "
            f"net={sum(t['pnl'] for t in g):+,.0f}")


def ana():
    """Descriptive breakdowns of the scored trade files (diagnostics only; nothing here feeds back into the rules)."""
    for sym in ("NQ", "ES"):
        for v in VARIANTS:
            with open(os.path.join(OUT, f"SB_trades_{sym}_{v}.json"), encoding="utf-8") as fh:
                tr = [t for t in json.load(fh) if "2025-04-14" <= t["day"] <= "2026-10-16"]
            print(sym, v, "ALL", _agg(tr), dict(collections.Counter(t["exit_kind"] for t in tr)))
            if v != "base":
                continue
            print("   AM window ", _agg([t for t in tr if t["window"] == "600"]))
            print("   PM window ", _agg([t for t in tr if t["window"] == "840"]))
            print("   long      ", _agg([t for t in tr if t["dir"] == 1]))
            print("   short     ", _agg([t for t in tr if t["dir"] == -1]))
            q = collections.defaultdict(list)
            for t in tr:
                q[f"{t['day'][:4]}Q{(int(t['day'][5:7]) - 1) // 3 + 1}"].append(t)
            for k in sorted(q):
                print("  ", k, _agg(q[k]))
            rp = sorted(t["risk_pts"] for t in tr)
            qty = sorted(t["qty"] for t in tr)
            cost = [1.40 * t["qty"] + (0.25 * PV[sym] * t["qty"] if t["exit_kind"] != "target" else 0) for t in tr]
            tg = sorted(abs(t["target"] - t["entry"]) / t["risk_pts"] for t in tr)
            print(f"   median stop {rp[len(rp) // 2]} pts, median qty {qty[len(qty) // 2]}, avg cost/trade ${sum(cost) / len(cost):.0f}"
                  f" ({sum(cost) / len(cost) / 350:.2f}R), median planned R to the draw {tg[len(tg) // 2]:.2f}")


def audit(v="base"):
    """Re-check every trade of a variant against raw bars, independently of the model's loop."""
    import numpy as np
    for sym in ("NQ", "ES"):
        b = bars(sym, "5m", "2025-04-01", PERIODS["all18m"][1])
        tix = {int(x): k for k, x in enumerate(b["time"].to_numpy())}
        H, L, M = b["high"].to_numpy(), b["low"].to_numpy(), b["mod"].to_numpy()
        with open(os.path.join(OUT, f"SB_trades_{sym}_{v}.json"), encoding="utf-8") as fh:
            tr = json.load(fh)
        bad = collections.Counter()
        for t in tr:
            i, j = tix[t["entry_t"]], tix[t["exit_t"] - 300]
            d, e, s, g = t["dir"], t["entry"], t["stop"], t["target"]
            ws = int(t["window"])
            if not (ws <= M[i] < ws + 60):
                bad["fill outside window"] += 1
            if (d == 1 and not L[i] <= e - 0.25) or (d == -1 and not H[i] >= e + 0.25):
                bad["fill without trade-through"] += 1
            seg = range(i + 1, j)                       # bars strictly between fill and exit: nothing may have triggered
            for k in seg:
                if (d == 1 and L[k] <= s) or (d == -1 and H[k] >= s):
                    bad["missed stop"] += 1
                    break
                if (d == 1 and H[k] >= g + 0.25) or (d == -1 and L[k] <= g - 0.25):
                    bad["missed target"] += 1
                    break
            if t["exit_kind"] == "stop" and not ((d == 1 and L[j] <= s) or (d == -1 and H[j] >= s)):
                bad["stop not touched"] += 1
            if t["exit_kind"] == "target":
                if not ((d == 1 and H[j] >= g + 0.25) or (d == -1 and L[j] <= g - 0.25)):
                    bad["target not traded through"] += 1
                if (d == 1 and L[j] <= s) or (d == -1 and H[j] >= s):
                    bad["target credited on a stop bar"] += 1
                if j == i:
                    bad["target on fill bar"] += 1
            if t["qty"] < 1:
                bad["qty 0"] += 1
        per_day = collections.Counter(t["day"] for t in tr)
        print(sym, v, "trades", len(tr), "issues", dict(bad) or "none", "max trades/day", max(per_day.values()),
              "open", sum(t["exit_kind"] == "open" for t in tr))


def tables():
    with open(os.path.join(OUT, "SB_results.json"), encoding="utf-8") as fh:
        rows = json.load(fh)
    L = ["| variant | period | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | worst day $ | 50K pass % | zero-edge % | b2b P/F |",
         "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['period']} | {r['trades']} | {r['tpw']} | {r['win_rate']} | {r['avg_r']:+.3f} {r['ci95_r']} | "
                 f"{r['pf']} | {r['net']:+,.0f} | {r['max_dd']:,.0f} | {r['worst_day']:,.0f} | {r['rolling_pass']} | "
                 f"{r['zero_edge_pass']} | {r['b2b_pass']}/{r['b2b_fail']} |")
    print("\n".join(L))
    print()
    ytd = [r for r in rows if r["period"] == "ytd"]
    months = sorted({m for r in ytd for m in r["months"]})
    print("| month | " + " | ".join(r["name"] for r in ytd) + " |")
    print("|---|" + "---:|" * len(ytd))
    for m in months:
        cells = []
        for r in ytd:
            x = r["months"].get(m)
            cells.append(f"{x['net']:+,.0f} ({x['trades']})" if x else "0 (0)")
        print(f"| {m} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    if sys.argv[1] == "smoke":
        smoke(sys.argv[2] if len(sys.argv) > 2 else "NQ")
    elif sys.argv[1] == "tables":
        tables()
    elif sys.argv[1] == "ana":
        ana()
    elif sys.argv[1] == "audit":
        for v in sys.argv[2:] or VARIANTS:
            audit(v)
    elif sys.argv[1] == "xcheck":
        xcheck_1m(sys.argv[2] if len(sys.argv) > 2 else "base")
    else:
        score_all(names=sys.argv[2:] or None)
