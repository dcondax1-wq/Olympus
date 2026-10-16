"""ICT 2022 Mentorship model lab runner (tools/lab_models/ict2022.py).

  python tools/lab_m22_run.py smoke NQ        # mechanics check on recent bars (prints trades, no scoring)
  python tools/lab_m22_run.py score           # score every pre-declared variant on NQ and ES, all periods
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
from tools.strategy_lab import PERIODS, bars, score, stats  # noqa: E402
from tools.lab_models import ict2022 as m22  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lab")
TR_DIR = os.path.join(OUT, "M22_trades")

# Pre-declared variants (documented choices only, fixed before the first scoring run; every one that is run is reported).
VARIANTS = {
    "canon": {},                                    # bias on, AM+PM killzones, opposite-liquidity target (-2 SD fallback)
    "nobias": {"bias": False},                      # same, without the daily-bias filter (both directions)
    "rr2": {"target": "rr", "rr": 2.0},             # same as canon, fixed 2R target instead of opposite liquidity
}
SCORE_PERIODS = ("ytd", "aug_oct", "y2025", "all18m")


def _hm(ts):
    return dt.datetime.fromtimestamp(ts, ET).strftime("%H:%M")


def smoke(sym, start="2026-09-01", end="2026-10-16", extra=None):
    b = bars(sym, "5m", start, end, warmup_days=5)
    t0 = time.time()
    p = {"sym": sym, **(extra or {})}
    tr = m22.run(b, p, None)
    print(sym, "bars", len(b), "last", b["et"].iloc[-1], "secs", round(time.time() - t0, 2), "trades", len(tr))
    for x in tr[-25:]:
        print(x["day"], _hm(x["entry_t"]), _hm(x["exit_t"]), x["dir"], x["entry"], x["stop"], x["target"], x["exit"],
              x["exit_kind"], x["qty"], x["pnl"], x["r"], x["setup"], x["tgt_kind"], x["plan_r"], x["sess"])
    print(collections.Counter(t["exit_kind"] for t in tr), collections.Counter(t["tgt_kind"] for t in tr))
    st = m22.state(b, p)
    st.pop("params", None)
    print(json.dumps(st, default=str)[:1500])


def _breakdown(tr, a, z):
    tr = [t for t in tr if a <= t["day"] <= z]
    out = {}
    for key in ("sess", "dir", "tgt_kind", "exit_kind", "pool"):
        g = collections.defaultdict(list)
        for t in tr:
            g[str(t[key])].append(t)
        out[key] = {k: {"n": len(v), "win": round(100 * sum(x["pnl"] > 0 for x in v) / len(v), 1),
                        "avg_r": round(sum(x["r"] for x in v) / len(v), 3), "net": round(sum(x["pnl"] for x in v), 0)}
                    for k, v in sorted(g.items())}
    if tr:
        out["median_risk_pts"] = sorted(t["risk_pts"] for t in tr)[len(tr) // 2]
        out["median_plan_r"] = sorted(t["plan_r"] for t in tr)[len(tr) // 2]
        out["median_qty"] = sorted(t["qty"] for t in tr)[len(tr) // 2]
    return out


def score_all(syms=("NQ", "ES"), names=None):
    os.makedirs(TR_DIR, exist_ok=True)
    summary = {"run_at": dt.datetime.now(ET).isoformat(timespec="seconds"), "rows": []}
    for sym in syms:
        b = bars(sym, "5m", PERIODS["all18m"][0], PERIODS["all18m"][1], warmup_days=7)
        summary.setdefault("data", {})[sym] = [str(b["et"].iloc[0]), str(b["et"].iloc[-1]), len(b)]
        print(sym, "bars", len(b), b["et"].iloc[0], "->", b["et"].iloc[-1])
        for vname, vp in VARIANTS.items():
            if names and vname not in names:
                continue
            p = {"sym": sym, **vp}
            t0 = time.time()
            tr = m22.run(b, p, None)
            name = f"M22_{sym}_{vname}"
            with open(os.path.join(TR_DIR, f"{name}.json"), "w", encoding="utf-8") as fh:
                json.dump(tr, fh, default=float)
            print(name, "trades", len(tr), "secs", round(time.time() - t0, 1))
            for per in SCORE_PERIODS:
                s = score(tr, name, per, params=p, notes="ICT 2022 Mentorship model, research/lab/M22_RULES.md")
                a, z = PERIODS[per]
                row = {k: s[k] for k in ("trades", "tpw", "weeks_in_2_5", "weeks_zero", "win_rate", "avg_r", "ci95_r",
                                         "pf", "net", "max_dd", "worst_day", "rolling_pass", "zero_edge_pass",
                                         "b2b_pass", "b2b_fail", "avg_days_to_pass", "losing_months", "months")}
                row.update({"name": name, "sym": sym, "variant": vname, "period": per, "gate": s["gate"]["ok"],
                            "breakdown": _breakdown(tr, a, z)})
                if vname == "canon":   # AM-killzone-only subset == an AM-only run (PM trades never affect AM decisions)
                    am = [t for t in tr if t["sess"] == "AM"]
                    sa = stats(am, a, z)
                    row["am_only"] = {k: sa[k] for k in ("trades", "tpw", "win_rate", "avg_r", "pf", "net", "max_dd",
                                                         "rolling_pass", "zero_edge_pass")}
                summary["rows"].append(row)
    with open(os.path.join(OUT, "M22_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=float)
    tables(summary)


def tables(summary=None):
    if summary is None:
        with open(os.path.join(OUT, "M22_summary.json"), encoding="utf-8") as fh:
            summary = json.load(fh)
    L = [f"Generated {summary['run_at']} from research/lab/M22_summary.json", ""]
    L += ["| name | period | trades | /wk | weeks 2-5 % | weeks 0 % | win % | avg R [95% CI] | PF | net $ | max DD $ | "
          "worst day $ | 50K pass % | zero-edge % | edge pts |",
          "|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in summary["rows"]:
        ed = (r["rolling_pass"] or 0) - (r["zero_edge_pass"] or 0)
        L.append(f"| {r['name']} | {r['period']} | {r['trades']} | {r['tpw']} | {r['weeks_in_2_5']:.0f} | "
                 f"{r['weeks_zero']:.0f} | {r['win_rate']} | {r['avg_r']:+.3f} {r['ci95_r']} | {r['pf']} | "
                 f"{r['net']:+,.0f} | {r['max_dd']:,.0f} | {r['worst_day']:,.0f} | {r['rolling_pass']} | "
                 f"{r['zero_edge_pass']} | {ed:+.1f} |")
    L += ["", "## 2026 monthly (ytd period)", ""]
    ytd = [r for r in summary["rows"] if r["period"] == "ytd"]
    months = sorted({m for r in ytd for m in r["months"]})
    L.append("| name | " + " | ".join(months) + " |")
    L.append("|---|" + "---:|" * len(months))
    for r in ytd:
        L.append(f"| {r['name']} | " + " | ".join(
            f"{r['months'][m]['net']:+,.0f} ({r['months'][m]['trades']})" if m in r["months"] else "0 (0)"
            for m in months) + " |")
    L += ["", "## Breakdowns (all18m)", ""]
    for r in summary["rows"]:
        if r["period"] != "all18m":
            continue
        bd = r["breakdown"]
        L.append(f"**{r['name']}** median stop {bd.get('median_risk_pts')} pts, median planned R {bd.get('median_plan_r')}, "
                 f"median qty {bd.get('median_qty')}")
        for key in ("sess", "dir", "tgt_kind", "exit_kind", "pool"):
            L.append(f"- {key}: " + "; ".join(f"{k} n={v['n']} win {v['win']}% avgR {v['avg_r']:+.3f} net {v['net']:+,.0f}"
                                               for k, v in bd[key].items()))
        L.append("")
    L += ["## AM-killzone-only subset of canon (identical to an AM-only run)", "",
          "| name | period | trades | /wk | win % | avg R | PF | net $ | max DD $ | 50K pass % | zero-edge % |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in summary["rows"]:
        if "am_only" in r:
            a = r["am_only"]
            L.append(f"| {r['name']} AM | {r['period']} | {a['trades']} | {a['tpw']} | {a['win_rate']} | {a['avg_r']:+.3f} | "
                     f"{a['pf']} | {a['net']:+,.0f} | {a['max_dd']:,.0f} | {a['rolling_pass']} | {a['zero_edge_pass']} |")
    with open(os.path.join(OUT, "M22_tables.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


def diag(syms=("NQ", "ES")):
    """Extra descriptive diagnostics for the report (same trades as the scored runs; no new variants)."""
    from tools.strategy_lab import PV, sessions
    a, z = PERIODS["all18m"]
    days = sessions(a, z)
    L = ["| name | quarters net $ (trades) | avg $ risked | max losing streak | weeks with 1-4 trades % | weeks 0 % | funnel (all18m) |",
         "|---|---|---:|---:|---:|---:|---|"]
    for sym in syms:
        b = bars(sym, "5m", a, z, warmup_days=7)
        for vname, vp in VARIANTS.items():
            name = f"M22_{sym}_{vname}"
            with open(os.path.join(TR_DIR, f"{name}.json"), encoding="utf-8") as fh:
                tr = [t for t in json.load(fh) if a <= t["day"] <= z]
            q = collections.defaultdict(lambda: [0.0, 0])
            for t in tr:
                y, mth = int(t["day"][:4]), int(t["day"][5:7])
                k = f"{y}Q{(mth - 1) // 3 + 1}"
                q[k][0] += t["pnl"]
                q[k][1] += 1
            risk = [t["qty"] * t["risk_pts"] * PV[sym] for t in tr]
            streak = cur = 0
            for t in sorted(tr, key=lambda t: t["entry_t"]):
                cur = cur + 1 if t["pnl"] <= 0 else 0
                streak = max(streak, cur)
            wk = collections.Counter()
            for d in days:
                y, w, _ = dt.date.fromisoformat(d).isocalendar()
                wk[(y, w)] += 0
            for t in tr:
                y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar()
                wk[(y, w)] += 1
            v = list(wk.values())
            dbg = []
            m22.run(b, {"sym": sym, **vp}, None, _debug=dbg)
            fun = dbg[0]
            fs = (f"raids {fun.get('raid', 0)} -> MSS {fun.get('mss', 0)} -> armed {fun.get('armed', 0)} -> filled "
                  f"{fun.get('fill', 0)} (ran away {fun.get('cancel_target', 0)}, expired {fun.get('cancel_window', 0)}, "
                  f"no FVG {fun.get('no_fvg', 0)}, stop too wide {fun.get('skip_qty0', 0)})")
            L.append(f"| {name} | " + ", ".join(f"{k} {q[k][0]:+,.0f} ({q[k][1]})" for k in sorted(q)) +
                     f" | {sum(risk) / max(len(risk), 1):,.0f} | {streak} | {100 * sum(1 <= x <= 4 for x in v) / len(v):.0f} | "
                     f"{100 * sum(x == 0 for x in v) / len(v):.0f} | {fs} |")
    with open(os.path.join(OUT, "M22_diag.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"
    if cmd == "smoke":
        smoke(sys.argv[2] if len(sys.argv) > 2 else "NQ")
    elif cmd == "tables":
        tables()
    elif cmd == "diag":
        diag()
    else:
        score_all(names=sys.argv[2].split(",") if len(sys.argv) > 2 else None)
