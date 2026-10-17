"""TRADER LAYER batch: every model raw vs the shared trader layer (configs fixed in research/lab/TRADER_LAYER_RULES.md).

    python tools/lab_trader_run.py run [--sources ENG1,SB] [--configs FULL,noJ] [--years 2026,2025]
    python tools/lab_trader_run.py tables            # research/lab/TRADER_LAYER_tables.md from TRADER_LAYER_results.json
The default `run` (no --configs) re-runs every row in about 3 minutes (FULL_v2 only once engine/narrative.py has a v2).

Single process. Outputs (no "__" in names, so strategy_lab.board() ignores them):
  research/lab/TRADER_LAYER_results.json             one scorecard row per (source, config, period)
  research/lab/TRADER_LAYER_trades_<SRC>_<CFG>.json  the layer's trades (2026 + 2025) with thoughts / plan / mgmt
  research/lab/TRADER_LAYER_decisions_<SRC>_<CFG>.json  every setup's take / skip decision and reason
"""
from __future__ import annotations

import argparse
import collections
import gc
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")

from tools import strategy_lab as sl  # noqa: E402
from tools import trader_layer as tl  # noqa: E402

LAB = os.path.join(ROOT, "research", "lab")
RES = os.path.join(LAB, "TRADER_LAYER_results.json")

SOURCES = {   # name: (file, kind, years, uses 1m paths in every config)
    "ENG1": ("conf_testbed_orig1day.json", "engine", ("2026", "2025"), False),
    "ENG2": ("conf_testbed_engine.json", "engine", ("2026", "2025"), False),
    "SB": ("SB_trades_NQ_base.json", "limit", ("2026", "2025"), False),
    "MECH": ("MECH_trades_NQ_base.json", "signal_open", ("2026", "2025"), False),
    "M22": ("M22_trades/M22_NQ_canon.json", "limit", ("2026", "2025"), False),
    "CONT": ("CONT_trades/CONT_NQ_IFVG_AMPM.json", "cont", ("2026", "2025"), False),
    "ATM": ("ATM_trades_base_flat.json", "atm", ("2026", "2025"), False),
    "ATMX": ("ATM_trades_diag_noskip_flat.json", "atm", ("2026", "2025"), False),
    "ATM1M": ("ATM_trades_1m_base.json", "atm", ("2026",), True),
    "ATM1MB": ("ATM_trades_1m_best.json", "atm", ("2026",), True),
}
PORT = ("ENG1", "SB", "MECH", "M22", "CONT")
CONFIGS = {"FULL": {}, "noJ": {"judgment": False}, "noP": {"plan": False}, "noM": {"manage": False},
           "noS": {"sizing": False}, "BIAS": {"bias_align": "require"}}
SENS = {"FULL_1m": ({}, True)}          # sensitivity: FULL with 1m intrabar paths (2026 only)
POSTHOC = {"JF": {"plan": False, "manage": False, "sizing": False, "replay_raw": True},   # RULES section 7
           "BIASoff": {"bias_align": "off"},
           "BIAS_db": {"bias_align": "require", "bias_source": "daily_bias:ttrades", "bias_replace": True},
           # RULES section 8.3 (coordinator, 20:10): daily_bias method D open_amd as a grade +/-1 or a counter-bias skip
           "DB_grade": {"bias_align": "grade_pm1", "bias_source": "daily_bias:open_amd"},
           "DB_skip": {"bias_align": "skip_counter", "bias_source": "daily_bias:open_amd"},
           "Monly": {"judgment": False, "plan": False, "sizing": False},                  # RULES section 7 (20:15)
           "FULL_rec": {"risk_policy": "recommended"},                                     # RULES section 7 (20:05)
           "FULL_v2": {"version": "v2"}}             # RULES section 5 sensitivity: runs only once the brain has a v2
# RULES section 8 (coordinator variants): retest entry windows (minutes) per source family, ATM recent-swing stop
RETEST = {"RTa": (30, 15), "RTb": (60, 30)}           # (5m sources, 1m ATM sources)
SWING = {"SW_FULL": {"stop_mode": "recent_swing"}, "SW_noP": {"stop_mode": "recent_swing", "plan": False},
         "SW1_FULL": {"stop_mode": "recent_swing", "swing_tf": 1},
         "SW1_noP": {"stop_mode": "recent_swing", "swing_tf": 1, "plan": False}}
NO_RETEST = {"SB", "M22"}                             # already limit entries
YEARS = {"2026": ("2026-01-02", "2026-10-16", ("dev", "confirm", "ytd", "aug_oct")),
         "2025": ("2025-04-14", "2025-12-31", ("y2025",))}
KEEP = ("trades", "tpw", "weeks_in_2_5", "weeks_zero", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day",
        "losing_months", "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail", "avg_days_to_pass", "months")


def raw_trades(src):
    f, kind, _, _ = SOURCES[src]
    d = json.load(open(os.path.join(LAB, f), encoding="utf-8"))
    days = {}
    if isinstance(d, dict) and "ytd" in d:
        tr = list(d["ytd"]["trades"]) + list(d["y2025"]["trades"])
        days = {"2026": d["ytd"].get("days"), "2025": d["y2025"].get("days")}
    elif isinstance(d, dict) and "trades" in d:
        tr = list(d["trades"])
    else:
        tr = list(d)
    return tr, kind, days


def in_year(t, y):
    a, z, _ = YEARS[y]
    return a <= t["day"] <= z


def row(trades, per, given_days=None):
    a, z = sl.PERIODS[per]
    gd = None
    if given_days:
        gd = [{"date": x["date"], "pnl": x["pnl"], "low": x["low"], "trades": x.get("trades", 0)} for x in given_days]
    s = sl.stats(trades, a, z, gd)
    return {k: s.get(k) for k in KEEP}


def load_frame(y, need_1m):
    a, z, _ = YEARS[y]
    b5 = sl.bars("NQ", "5m", a, z, warmup_days=45)
    try:
        e5 = sl.bars("ES", "5m", a, z, warmup_days=45)
    except Exception:
        e5 = None
    m1 = None
    if need_1m and y == "2026":
        import pandas as pd
        m1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"), usecols=["time", "high", "low"])
        m1 = m1[(m1["time"] >= int(b5["time"].iloc[0])) & (m1["time"] <= int(b5["time"].iloc[-1]) + 300)].reset_index(drop=True)
    return b5, e5, m1


def run(sources, configs, years, sens=True):
    out = json.load(open(RES, encoding="utf-8")) if os.path.exists(RES) else {"rows": [], "meta": {}}
    rows = {(r["source"], r["config"], r["period"]): r for r in out["rows"]}
    tl._load()
    meta = out.setdefault("meta", {})
    meta.update({"run_at": time.strftime("%Y-%m-%d %H:%M"), "narrative_versions": list(getattr(tl.NAR, "VERSIONS", {}) or {}),
                 "imports": dict(tl._IMPORT_ERR),
                 "mtimes": {m: time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(os.path.join(ROOT, "engine", m + ".py"))))
                            for m in ("narrative", "liquidity_map", "risk_policy", "draw_learner")}})
    srcs = [s for s in sources if s in SOURCES or s == "PORT"]
    for y in years:
        need_1m = True
        b5, e5, m1 = load_frame(y, need_1m)
        print(f"[{y}] frame {len(b5)} bars, ES {0 if e5 is None else len(e5)}, 1m {0 if m1 is None else len(m1)}", flush=True)
        a, z, pers = YEARS[y]
        for src in srcs:
            members = PORT if src == "PORT" else (src,)
            if any(y not in SOURCES[m][2] for m in members):
                continue
            raw_all, setups, gdays = [], [], None
            for m in members:
                tr, kind, days = raw_trades(m)
                tr = [t for t in tr if in_year(t, y)]
                raw_all += tr
                if src != "PORT":
                    gdays = days.get(y) if days else None
                setups += tl.setups_from_trades(tr, kind, b5, model=m)
            one_m = src != "PORT" and SOURCES[src][3]
            # RAW
            for per in pers:
                r = row(raw_all, per, gdays)
                rows[(src, "RAW", per)] = {"source": src, "config": "RAW", "period": per, **r}
            todo = [(c, CONFIGS[c], one_m) for c in configs if c in CONFIGS]
            if sens and y == "2026" and not one_m and src != "PORT":
                todo += [(c, cf, True) for c, (cf, _) in SENS.items() if "FULL" in configs or c in configs]
            todo += [(c, POSTHOC[c], one_m) for c in configs if c in POSTHOC
                     and (c != "FULL_v2" or "v2" in (getattr(tl.NAR, "VERSIONS", {}) or {}))]
            for c in configs:
                if c in RETEST and src not in NO_RETEST:
                    todo.append((c, {"entry": "retest", "retest_min": RETEST[c][1] if one_m else RETEST[c][0]}, True))
                if c in SWING and src in ("ATM1M", "ATM1MB"):
                    todo.append((c, SWING[c], True))
            for cname, cfg, use1m in todo:
                t0 = time.time()
                log = []
                trs = tl.apply(setups, b5, e5, cfg, log=log, bars1=(m1 if use1m else None))
                L = getattr(tl.apply, "last_layer", None)
                for per in pers:
                    r = row(trs, per)
                    r["setups"] = sum(1 for s in setups if sl.PERIODS[per][0] <= tl._et(s["entry_t"]).strftime("%Y-%m-%d") <= sl.PERIODS[per][1])
                    r["evals_sim"] = dict(L.evals) if L is not None else None
                    rows[(src, cname, per)] = {"source": src, "config": cname, "period": per, **r}
                skip = collections.Counter(x["reason"].split(":")[0] if x.get("decision") == "skip" else "take" for x in log)
                rows[(src, cname, "_decisions_" + y)] = {"source": src, "config": cname, "period": "_decisions_" + y,
                                                          "counts": dict(skip)}
                fn = os.path.join(LAB, f"TRADER_LAYER_trades_{src}_{cname}.json")
                prev = json.load(open(fn, encoding="utf-8")) if os.path.exists(fn) else {}
                prev[y] = trs
                with open(fn, "w", encoding="utf-8") as fh:
                    json.dump(prev, fh, default=float)
                fd = os.path.join(LAB, f"TRADER_LAYER_decisions_{src}_{cname}.json")
                prevd = json.load(open(fd, encoding="utf-8")) if os.path.exists(fd) else {}
                prevd[y] = log
                with open(fd, "w", encoding="utf-8") as fh:
                    json.dump(prevd, fh, default=float)
                main = "ytd" if y == "2026" else "y2025"
                rr = rows[(src, cname, main)]
                print(f"  {src:6s} {cname:8s} {y} setups={len(setups):4d} trades={rr['trades']:4d} tpw={rr['tpw']} net={rr['net']:+,.0f} "
                      f"pf={rr['pf']} dd={rr['max_dd']:,.0f} pass={rr['rolling_pass']} ({rr['zero_edge_pass']}) "
                      f"raw={rows[(src, 'RAW', main)]['net']:+,.0f} [{time.time() - t0:.0f}s] {dict(skip.most_common(4))}", flush=True)
            out["rows"] = list(rows.values())
            with open(RES, "w", encoding="utf-8") as fh:
                json.dump(out, fh, indent=0, default=float)
        del b5, e5, m1
        gc.collect()
    return out


# ------------------------------------------------------------------------------------------------ tables
def _f(x, nd=0, sign=True):
    if x is None:
        return "-"
    if isinstance(x, (int, float)):
        return f"{x:+,.{nd}f}" if sign else f"{x:,.{nd}f}"
    return str(x)


def tables(sources=None):
    out = json.load(open(RES, encoding="utf-8"))
    R = {(r["source"], r["config"], r["period"]): r for r in out["rows"]}
    srcs = sources or [s for s in list(SOURCES) + ["PORT"] if any(k[0] == s for k in R)]
    L = [f"# TRADER LAYER tables (generated {time.strftime('%Y-%m-%d %H:%M')} by `python -X utf8 tools/lab_trader_run.py tables`)",
         "", "Cells: net $ / PF / trades a week / max DD $ / rolling MFFU 50K pass % (zero-edge baseline). `-` = not run.",
         "Pre-registered: RAW, FULL, noJ, noP, noM, noS, BIAS. Everything else is a sensitivity, coordinator or post-hoc row",
         "(see TRADER_LAYER_RULES.md sections 5, 7, 8).", ""]
    groups = [("pre-registered", ["RAW"] + list(CONFIGS)),
              ("sensitivity / bias rows", ["FULL", "FULL_1m", "FULL_rec", "BIASoff", "BIAS_db", "DB_grade", "DB_skip"]),
              ("post-hoc and coordinator rows", ["RAW", "JF", "Monly", "RTa", "RTb", "SW_FULL", "SW_noP", "SW1_FULL", "SW1_noP"])]
    for per in ("dev", "confirm", "ytd", "aug_oct", "y2025"):
        for gname, cfgs in groups:
            if not any(R.get((s, c, per)) for s in srcs for c in cfgs if c not in ("RAW", "FULL")):
                continue
            L.append(f"\n### {per}: {gname}\n")
            L.append("| model | " + " | ".join(cfgs) + " |")
            L.append("|---|" + "---|" * len(cfgs))
            for s in srcs:
                cells = []
                for c in cfgs:
                    r = R.get((s, c, per))
                    cells.append("-" if not r else f"{_f(r['net'])} / {r['pf']} / {r['tpw']} / {_f(r['max_dd'], sign=False)} / {r['rolling_pass']} ({r['zero_edge_pass']})")
                L.append(f"| {s} | " + " | ".join(cells) + " |")
    L.append("")
    with open(os.path.join(LAB, "TRADER_LAYER_tables.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    cfgs = ["RAW"] + list(CONFIGS) + list(SENS) + list(POSTHOC)
    L = []
    L.append("### Headline: 2026 ytd, raw vs trader layer (FULL)\n")
    L.append("| model | config | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | losing months | 50K pass % (zero-edge) | b2b P/F |")
    L.append("|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|")
    for s in srcs:
        for c in ("RAW", "FULL", "BIAS"):
            r = R.get((s, c, "ytd"))
            if r:
                L.append(f"| {s} | {c} | {r['trades']} | {r['tpw']} | {r['win_rate']} | {r['avg_r']:+.3f} {r['ci95_r']} | {r['pf']} | "
                         f"{_f(r['net'])} | {_f(r['max_dd'], sign=False)} | {r['losing_months']} | {r['rolling_pass']} ({r['zero_edge_pass']}) | {r['b2b_pass']}/{r['b2b_fail']} |")
    for per in ("dev", "confirm", "ytd", "aug_oct", "y2025"):
        L.append(f"\n### {per}: every config (net $ / PF / trades a week / max DD $ / 50K pass % vs zero-edge)\n")
        L.append("| model | " + " | ".join(cfgs) + " |")
        L.append("|---|" + "---|" * len(cfgs))
        for s in srcs:
            cells = []
            for c in cfgs:
                r = R.get((s, c, per))
                cells.append("-" if not r else f"{_f(r['net'])} / {r['pf']} / {r['tpw']} / {_f(r['max_dd'], sign=False)} / {r['rolling_pass']} ({r['zero_edge_pass']})")
            L.append(f"| {s} | " + " | ".join(cells) + " |")
    L.append("\n### Monthly net $ (2026), RAW vs FULL vs BIAS\n")
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    L.append("| model | config | " + " | ".join(m[5:] for m in months) + " | losing |")
    L.append("|---|---|" + "---:|" * len(months) + "---:|")
    for s in srcs:
        for c in ("RAW", "FULL", "BIAS"):
            r = R.get((s, c, "ytd"))
            if not r:
                continue
            mm = r.get("months") or {}
            L.append(f"| {s} | {c} | " + " | ".join(_f((mm.get(m) or {}).get("net"), 0) if m in mm else "0" for m in months) +
                     f" | {r['losing_months']} |")
    L.append("\n### Decision counts (FULL)\n")
    for s in srcs:
        for y in ("2026", "2025"):
            r = R.get((s, "FULL", "_decisions_" + y))
            if r:
                L.append(f"- {s} {y}: " + ", ".join(f"{k} {v}" for k, v in sorted(r["counts"].items(), key=lambda kv: -kv[1])))
    txt = "\n".join(L)
    print(txt)
    return txt


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "tables"])
    ap.add_argument("--sources", default=",".join(list(SOURCES) + ["PORT"]))
    ap.add_argument("--configs", default=",".join(list(CONFIGS) + list(POSTHOC) + list(RETEST) + list(SWING)))
    ap.add_argument("--years", default="2026,2025")
    ap.add_argument("--nosens", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.sources.split(","), a.configs.split(","), a.years.split(","), sens=not a.nosens)
    else:
        tables()
