"""ATM track runner: the owner's ATM model (tools/lab_models/atm.py) on NQ 5m, ES for SMT. Single process.

  python -X utf8 tools/lab_atm_run.py smoke     -> dev only, unscored (mechanics check; nothing is logged)
  python -X utf8 tools/lab_atm_run.py all       -> the one scored batch: every documented variant x {flat, tier} x
                                                  {dev, confirm, ytd, aug_oct, y2025}; writes research/lab/ATM_results.json
                                                  and research/lab/ATM_trades_<variant>_<scheme>.json

The variant list is fixed here BEFORE the scored batch (see research/lab/ATM_RULES.md); nothing else is searched.
"""
import collections
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.strategy_lab import OUT, PERIODS, bars, score, stats  # noqa: E402
from tools.lab_models import atm as M  # noqa: E402

# base = the owner's literal rules; each variant changes exactly one thing (what the owner/lead asked to test)
VARIANTS = {
    "base": {},
    "n4": {"v_bars": 4},                          # V must complete within 4 bars
    "n8": {"v_bars": 8},                          # ... within 8 bars
    "x618": {"v_retrace": 0.618},                 # V must retrace 61.8% of the sweep leg
    "tgt_first": {"target": "first_clear"},       # (b) first clear pool with a clean path, else the opposite side
    "tgt_half": {"target": "partial"},            # (c) half at the first clear pool, runner to the opposite side, BE
    "rr1": {"min_rr": 1.0},                       # skip only if the opposite side is < 1R
    "rr2": {"min_rr": 2.0},                       # skip if the opposite side is < 2R
    "two_a_day": {"max_trades_day": 2},           # up to 2 trades a day
    "win1100": {"entry_end": 660},                # entries 09:30-11:00
}
SCHEMES = ("flat", "tier")
PERIOD_LIST = ["dev", "confirm", "ytd", "aug_oct", "y2025"]
KEEP = ("trades", "tpw", "weeks_in_2_5", "weeks_zero", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day",
        "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail", "losing_months", "months", "avg_days_to_pass", "completed")


def load(start="2025-04-14", end="2026-10-16", tf="5m"):
    return bars("NQ", tf, start, end, warmup_days=10), bars("ES", tf, start, end, warmup_days=10)


def tier_table(trades, a, z):
    """Avg R / win % / net by tier and by score inside [a, z]."""
    out = {}
    for key in ("tier", "score"):
        by = collections.defaultdict(list)
        for t in trades:
            if a <= t["day"] <= z:
                by[t[key]].append(t)
        out[key] = {str(k): {"n": len(v), "avg_r": round(float(np.mean([x["r"] for x in v])), 3),
                             "win": round(100 * float(np.mean([x["pnl"] > 0 for x in v])), 1),
                             "net": round(float(sum(x["pnl"] for x in v)), 2)} for k, v in sorted(by.items())}
    return out


def conf_table(trades, a, z):
    """Each confluence: avg R with vs without (descriptive)."""
    out = {}
    tr = [t for t in trades if a <= t["day"] <= z]
    for k in M.CONF_KEYS:
        w = [t["r"] for t in tr if t["conf"].get(k)]
        wo = [t["r"] for t in tr if not t["conf"].get(k)]
        out[k] = {"n_with": len(w), "r_with": round(float(np.mean(w)), 3) if w else None,
                  "n_without": len(wo), "r_without": round(float(np.mean(wo)), 3) if wo else None}
    return out


def smoke():
    a, z = PERIODS["dev"]
    t0 = time.time()
    nq, es = bars("NQ", "5m", a, z, warmup_days=10), bars("ES", "5m", a, z, warmup_days=10)
    fun = collections.Counter()
    raws = [r for r in M.run_raw(nq, {}, es, _funnel=fun) if a <= r["day"] <= z]
    print("run", round(time.time() - t0, 1), "s", dict(fun))
    print("raws", len(raws), "tiers", dict(collections.Counter(r["tier"] for r in raws)),
          "scores", dict(sorted(collections.Counter(r["score"] for r in raws).items())))
    print("dirs", dict(collections.Counter(r["d"] for r in raws)), "exits", dict(collections.Counter(r["full"]["kind"] for r in raws)))
    for k in M.CONF_KEYS:
        print(" ", k, dict(collections.Counter(r["conf"][k] for r in raws)))
    for r in raws[:8]:
        print(r["day"], r["d"], r["entry"], round(r["stop"], 2), round(r["risk_pts"], 2), r["tgt_lvl"], round(r["rr_opp"], 2),
              r["full"]["kind"], r["full"]["exit_px"], r["tier"], r["info"])
    print("median risk", float(np.median([r["risk_pts"] for r in raws])), "median rr_opp",
          float(np.median([r["rr_opp"] for r in raws])))
    for sch in SCHEMES:
        s = stats(M.build_all(raws, sch, {}), a, z)
        print(sch, {k: s[k] for k in ("trades", "tpw", "win_rate", "avg_r", "pf", "net", "max_dd", "rolling_pass", "zero_edge_pass")})


def main():
    t0 = time.time()
    nq, es = load()
    print("loaded", len(nq), len(es), round(time.time() - t0, 1), "s")
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "variants": VARIANTS, "periods": {p: PERIODS[p] for p in PERIOD_LIST},
           "runs": {}}
    for vname, vp in VARIANTS.items():
        fun = collections.Counter()
        raws = [r for r in M.run_raw(nq, vp, es, _funnel=fun) if r["day"] >= PERIODS["y2025"][0]]
        entry = {"funnel": dict(fun), "params": vp}
        for sch in SCHEMES:
            trades = M.build_all(raws, sch, vp)
            name = f"ATM_{vname}_{sch}"
            with open(os.path.join(OUT, f"ATM_trades_{vname}_{sch}.json"), "w", encoding="utf-8") as fh:
                json.dump(trades, fh, default=float)
            per = {}
            for pn in PERIOD_LIST:
                s = score(trades, name, pn, notes="ATM owner model", params={**vp, "sizing": sch})
                per[pn] = {k: s.get(k) for k in KEEP}
                per[pn]["gate"] = s["gate"]["ok"]
                per[pn]["exits"] = dict(collections.Counter(t["exit_kind"] for t in trades if PERIODS[pn][0] <= t["day"] <= PERIODS[pn][1]))
                per[pn]["avg_risk_usd"] = round(float(np.mean([t["risk_pts"] * 2.0 * t["qty"] for t in trades
                                                               if PERIODS[pn][0] <= t["day"] <= PERIODS[pn][1]] or [0])), 1)
                per[pn]["tiers"] = tier_table(trades, *PERIODS[pn])
                if sch == "flat":
                    per[pn]["conf"] = conf_table(trades, *PERIODS[pn])
                    per[pn]["long_short"] = {str(d): {"n": len(v), "avg_r": round(float(np.mean(v)), 3)} for d, v in
                                             ((d, [t["r"] for t in trades if t["dir"] == d and PERIODS[pn][0] <= t["day"] <= PERIODS[pn][1]])
                                              for d in (1, -1)) if v}
            entry[sch] = per
        entry["median_stop_pts"] = float(np.median([r["risk_pts"] for r in raws])) if raws else None
        entry["median_rr_opp"] = float(np.median([r["rr_opp"] for r in raws])) if raws else None
        entry["first_found"] = sum(1 for r in raws if r["first"]) if vp.get("target") in ("first_clear", "partial") else None
        res["runs"][vname] = entry
        print(vname, "done", round(time.time() - t0, 1), "s")
    with open(os.path.join(OUT, "ATM_results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("all done", round(time.time() - t0, 1), "s")


def _spearman(x, y, n_perm=2000, seed=11):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 8:
        return None, None
    rx = np.argsort(np.argsort(x + np.random.default_rng(1).random(len(x)) * 1e-6))   # ties broken at random
    ry = np.argsort(np.argsort(y))
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.array([np.corrcoef(rx, rng.permutation(ry))[0, 1] for _ in range(n_perm)])
    return round(rho, 3), round(float((null >= rho).mean()), 3)          # one-sided: does a higher score mean higher R?


def diag():
    """DIAGNOSTIC (not a candidate): every V+IFVG signal of the base rules, with the 1.5R skip removed (min_rr 0), so the
    entry signal and the confluence score can be judged on a usable sample. Scored and logged like everything else."""
    t0 = time.time()
    nq, es = load()
    vp = {"min_rr": 0.0}
    fun = collections.Counter()
    raws = [r for r in M.run_raw(nq, vp, es, _funnel=fun) if r["day"] >= PERIODS["y2025"][0]]
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "funnel": dict(fun), "params": vp, "note":
           "diagnostic only: violates the owner's skip rule; never selected"}
    for sch in SCHEMES:
        trades = M.build_all(raws, sch, vp)
        with open(os.path.join(OUT, f"ATM_trades_diag_noskip_{sch}.json"), "w", encoding="utf-8") as fh:
            json.dump(trades, fh, default=float)
        per = {}
        for pn in PERIOD_LIST:
            a, z = PERIODS[pn]
            s = score(trades, f"ATM_diag_noskip_{sch}", pn, notes="DIAGNOSTIC: all V+IFVG signals, no R:R skip (not a candidate)",
                      params={**vp, "sizing": sch})
            per[pn] = {k: s.get(k) for k in KEEP}
            per[pn]["tiers"] = tier_table(trades, a, z)
            tp = [t for t in trades if a <= t["day"] <= z]
            per[pn]["rho_score_r"] = _spearman([t["score"] for t in tp], [t["r"] for t in tp])
            per[pn]["exits"] = dict(collections.Counter(t["exit_kind"] for t in tp))
            if sch == "flat":
                per[pn]["conf"] = conf_table(trades, a, z)
                bk = collections.defaultdict(list)
                for t in tp:
                    rr = t["rr_opp"]
                    bk["<1.0" if rr < 1.0 else ("1.0-1.5" if rr < 1.5 else ("1.5-2.0" if rr < 2.0 else ">=2.0"))].append(t)
                per[pn]["rr_buckets"] = {k: {"n": len(v), "avg_r": round(float(np.mean([x["r"] for x in v])), 3),
                                             "win": round(100 * float(np.mean([x["pnl"] > 0 for x in v])), 1),
                                             "net": round(float(sum(x["pnl"] for x in v)), 2)} for k, v in sorted(bk.items())}
        out[sch] = per
    with open(os.path.join(OUT, "ATM_diag.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("diag done", round(time.time() - t0, 1), "s", dict(fun))


def _fmt_row(v, sch, pn, s):
    pf = "-" if s["pf"] is None else s["pf"]
    pas = "n/a" if s["rolling_pass"] is None else f"{s['rolling_pass']} ({s['zero_edge_pass']})"
    ci = s["ci95_r"] if s["ci95_r"] and s["ci95_r"][0] is not None else "-"
    return (f"| {v} | {sch} | {pn} | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} {ci} | {pf} | "
            f"{s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['worst_day']:,.0f} | {pas} |")


def report():
    """Print the markdown tables used in research/lab/ATM_REPORT.md (from ATM_results.json / ATM_diag.json)."""
    with open(os.path.join(OUT, "ATM_results.json"), encoding="utf-8") as fh:
        R = json.load(fh)
    with open(os.path.join(OUT, "ATM_diag.json"), encoding="utf-8") as fh:
        D = json.load(fh)
    H = ("| variant | sizing | period | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | worst day $ | "
         "50K pass % (zero-edge) |\n|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|")
    for sch in SCHEMES:
        print(f"\n### all variants, {sch} sizing\n\n" + H)
        for v, e in R["runs"].items():
            for pn in PERIOD_LIST:
                print(_fmt_row(v, sch, pn, e[sch][pn]))
    print("\n### diagnostic (all signals, no R:R skip)\n\n" + H)
    for sch in SCHEMES:
        for pn in PERIOD_LIST:
            print(_fmt_row("diag_noskip", sch, pn, D[sch][pn]))
    print("\n### funnel (2025-04-14 .. 2026-10-16)\n\n| variant | days | days swept | armed | V expired: no close back inside | "
          "no IFVG | no displacement | no retrace | fell back | signals | skipped < min R | skipped size | trades |\n"
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    rows = list(R["runs"].items()) + [("diag_noskip", D)]
    for v, e in rows:
        f = collections.Counter(e["funnel"])
        print(f"| {v} | {f['days_ok']} | {f['days_swept']} | {f['armed']} | {f['fail_no_reclaim']} | {f['fail_no_ifvg']} | "
              f"{f['fail_no_disp']} | {f['fail_no_retrace']} | {f['fail_fell_back']} | {f['signals']} | {f['skip_rr']} | "
              f"{f['skip_size']} | {f['trades']} |")
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    print("\n### 2026 by month (trades / net $)\n\n| line | " + " | ".join(m[5:] for m in months) + " |\n|---|" + "---:|" * 10)
    for v, sch, src in (("base", "flat", R["runs"]["base"]), ("base", "tier", R["runs"]["base"]), ("rr1", "flat", R["runs"]["rr1"]),
                        ("rr1", "tier", R["runs"]["rr1"]), ("diag_noskip", "flat", D), ("diag_noskip", "tier", D)):
        mm = src[sch]["ytd"]["months"]
        print(f"| {v} {sch} | " + " | ".join(f"{mm[m]['trades']} / {mm[m]['net']:+,.0f}" if m in mm else "0" for m in months) + " |")
    print("\n### by tier (avg R on flat sizing; net $ flat -> tier)\n\n| line | period | A n / avg R / win % | B | C | "
          "net flat | net tier | Spearman rho(score, R), one-sided p |\n|---|---|---|---|---|---:|---:|---|")
    for v, src in (("base", R["runs"]["base"]), ("rr1", R["runs"]["rr1"]), ("diag_noskip", D)):
        for pn in PERIOD_LIST:
            tt = src["flat"][pn]["tiers"]["tier"]
            cells = [f"{tt[x]['n']} / {tt[x]['avg_r']:+.2f} / {tt[x]['win']:.0f}" if x in tt else "0" for x in "ABC"]
            rho = src["flat"][pn].get("rho_score_r", "-")
            print(f"| {v} | {pn} | " + " | ".join(cells) + f" | {src['flat'][pn]['net']:+,.0f} | {src['tier'][pn]['net']:+,.0f} | {rho} |")
    print("\n### confluences on the diagnostic set (avg R with / without, n with)\n\n| confluence | dev | confirm | y2025 |\n|---|---|---|---|")
    for k in M.CONF_KEYS:
        cells = []
        for pn in ("dev", "confirm", "y2025"):
            c = D["flat"][pn]["conf"][k]
            w = "-" if c["r_with"] is None else f"{c['r_with']:+.2f}"
            wo = "-" if c["r_without"] is None else f"{c['r_without']:+.2f}"
            cells.append(f"{w} / {wo} (n {c['n_with']})")
        print(f"| `{k}` | " + " | ".join(cells) + " |")
    print("\n### diagnostic: avg R by R:R to the opposite side at the signal (flat)\n\n| period | <1.0 | 1.0-1.5 | 1.5-2.0 | >=2.0 |\n|---|---|---|---|---|")
    for pn in PERIOD_LIST:
        b = D["flat"][pn]["rr_buckets"]
        print(f"| {pn} | " + " | ".join(f"{b[x]['n']} / {b[x]['avg_r']:+.2f}" if x in b else "0" for x in ("<1.0", "1.0-1.5", "1.5-2.0", ">=2.0")) + " |")
    print("\n### base trades (all 18 months, flat sizing)\n\n| day | side | entry | stop | stop pts | target (ATM side) | R:R | exit | "
          "exit kind | R | score / tier | MNQ flat / tier | confluences present |\n|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|")
    with open(os.path.join(OUT, "ATM_trades_base_flat.json"), encoding="utf-8") as fh:
        tf_ = json.load(fh)
    with open(os.path.join(OUT, "ATM_trades_base_tier.json"), encoding="utf-8") as fh:
        tt_ = {t["entry_t"]: t for t in json.load(fh)}
    for t in tf_:
        on = ", ".join(k for k in M.CONF_KEYS if t["conf"].get(k))
        print(f"| {t['day']} | {'long' if t['dir'] == 1 else 'short'} | {t['entry']:.2f} | {t['stop']:.2f} | {t['risk_pts']:.1f} | "
              f"{t['target']:.2f} | {t['rr_opp']:.2f} | {t['exit']:.2f} | {t['exit_kind']} | {t['r']:+.2f} | {t['score']} / {t['tier']} | "
              f"{t['qty']} / {tt_.get(t['entry_t'], {}).get('qty', '-')} | {on} |")
    for v in ("base", "rr1"):
        e = R["runs"][v]
        print(f"\n{v}: median stop {e['median_stop_pts']:.1f} pts, median R:R at entry {e['median_rr_opp']:.2f}; exits ytd "
              f"{e['flat']['ytd']['exits']} y2025 {e['flat']['y2025']['exits']}; avg risk $ flat ytd {e['flat']['ytd']['avg_risk_usd']} "
              f"tier ytd {e['tier']['ytd']['avg_risk_usd']}; long/short ytd {e['flat']['ytd']['long_short']}")
    print("\ndiag exits", {pn: D["flat"][pn]["exits"] for pn in PERIOD_LIST})


# ================================================================================================ 1m / 3m version (section G)
import glob  # noqa: E402

import pandas as pd  # noqa: E402

from tools.strategy_lab import ET, ROOT  # noqa: E402

VARIANTS_1M = {                                   # pre-registered in ATM_RULES.md section G8 (complete list)
    "m1_base": {"tf": 1},
    "m1_rr1": {"tf": 1, "min_rr": 1.0},
    "m1_nbars6": {"tf": 1, "v_bars_fixed": 6},
    "m1_tf5321": {"tf": 1, "ladder": [5, 3, 2, 1]},
    "m1_tgt_half": {"tf": 1, "target": "partial"},
    "m1_two_a_day": {"tf": 1, "max_trades_day": 2},
}
STITCHED = os.path.join(ROOT, "data", "clean", "NQ_1m_tv.csv")
NOTES_1M = os.path.join(ROOT, "research", "lab", "DATA_1M.md")


def _frame_from(df):
    df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))].sort_values("time").drop_duplicates("time", keep="last")
    df = df.reset_index(drop=True)
    et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    df["et"] = et
    df["day"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    df["mod"] = et.dt.hour * 60 + et.dt.minute
    return df


def load_1m_chunks():
    """DEV ONLY: raw TradingView NQ1! 1m chunks (front month, unadjusted) restricted to bars after the last roll, where
    raw = back-adjusted. Never the Yahoo NQ_1m.csv."""
    with open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8") as fh:
        sw = max(int(r["switch_t"]) for r in json.load(fh)["rolls"] if r.get("switch_t"))
    parts = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "tv_exports", "NQ1_1m_chunk_*.csv"))):
        x = pd.read_csv(f)
        x.columns = [c.lower() for c in x.columns]
        parts.append(x[["time", "open", "high", "low", "close", "volume"]])
    df = pd.concat(parts)
    df = df[df["time"] >= sw]
    return _frame_from(df), sw


def load_1m_stitched():
    """The stitched, back-adjusted TradingView file (data/clean/NQ_1m_tv.csv), only once its notes exist."""
    if not (os.path.exists(STITCHED) and os.path.exists(NOTES_1M)):
        return None
    df = pd.read_csv(STITCHED)
    df.columns = [c.lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 1
    return _frame_from(df[["time", "open", "high", "low", "close", "volume"]])


def check_1m(nq1):
    """Resample 1m -> 5m and compare with the TradingView 5m file on common bars (same price space expected)."""
    o, h, l, c, t = (nq1[x].to_numpy(float) for x in ("open", "high", "low", "close")), None, None, None, None
    o, h, l, c = (nq1[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    t = nq1["time"].to_numpy(np.int64)
    t0, o5, h5, l5, c5, d5, _ = M._resample(t, o, h, l, c, nq1["day"].to_numpy(), 5)
    ref = bars("NQ", "5m", str(d5[0]), str(d5[-1]))
    r = ref.set_index("time")
    common = np.intersect1d(t0, r.index.to_numpy())
    ix = np.searchsorted(t0, common)
    rr = r.loc[common]
    same = {nm: float(np.mean(np.abs(a[ix] - rr[nm].to_numpy()) < 1e-6)) for nm, a in
            (("open", o5), ("high", h5), ("low", l5), ("close", c5))}
    full = float(np.mean((np.abs(o5[ix] - rr["open"].to_numpy()) < 1e-6) & (np.abs(h5[ix] - rr["high"].to_numpy()) < 1e-6) &
                         (np.abs(l5[ix] - rr["low"].to_numpy()) < 1e-6) & (np.abs(c5[ix] - rr["close"].to_numpy()) < 1e-6)))
    sess = sorted(set(nq1["day"]))
    return {"sessions": len(sess), "first": sess[0], "last": sess[-1], "bars_1m": len(nq1), "common_5m": int(len(common)),
            "match_by_field": {k: round(v, 4) for k, v in same.items()}, "match_all_ohlc": round(full, 4),
            "max_abs_close_diff": float(np.max(np.abs(c5[ix] - rr["close"].to_numpy()))) if len(common) else None}


def smoke1m():
    """Unscored: data check, engine consistency (ladder [5] vs the 5m engine) and the m1_base funnel on what exists."""
    t0 = time.time()
    nq1 = load_1m_stitched()
    src = "stitched"
    if nq1 is None:
        nq1, sw = load_1m_chunks()
        src = f"chunks after roll t={sw}"
    print("1m source:", src, check_1m(nq1))
    a, z = nq1["day"].iloc[0], nq1["day"].iloc[-1]
    es5 = bars("ES", "5m", a, z, warmup_days=10)
    nq5 = bars("NQ", "5m", a, z)
    r5 = [r for r in M.run_raw(nq5, {}, es5) if r["day"] > a]
    rl = [r for r in M.run_raw_mtf(nq1, {"tf": 1, "ladder": [5]}, es5) if r["day"] > a]
    k5 = {(r["day"], r["d"], r["entry"], round(r["stop"], 2)) for r in r5}
    kl = {(r["day"], r["d"], r["entry"], round(r["stop"], 2)) for r in rl}
    print("consistency 5m engine vs ladder[5] on 1m:", len(k5), len(kl), "common", len(k5 & kl), "only5m", sorted(k5 - kl),
          "onlyladder", sorted(kl - k5))
    for vname, vp in VARIANTS_1M.items():
        fun = collections.Counter()
        raws = M.run_raw_mtf(nq1, vp, es5, _funnel=fun)
        tr = M.build_all(raws, "flat", vp)
        s = stats(tr, a, z) if tr else None
        print(vname, round(time.time() - t0, 1), "s", dict(fun))
        if s:
            print("   ", {k: s[k] for k in ("trades", "tpw", "win_rate", "avg_r", "pf", "net", "max_dd")},
                  dict(collections.Counter(r["info"]["trigger_tf"] for r in raws)))
        if vname == "m1_base":
            for r in raws:
                f = r["full"]
                print("   ", r["day"], r["d"], f"{r['info']['trigger_tf']}m", r["entry"], round(r["stop"], 2), round(r["risk_pts"], 1),
                      round(r["rr_opp"], 2), f["kind"], r["tier"], r["info"]["minutes_to_entry"], r["info"]["leg_pts"])


PERIODS_1M = ["dev", "confirm", "ytd", "aug_oct"]


def _tradable_days(nq1):
    """Sessions the 1m engine can trade: in the file, with the previous session also in the file (<= 4 days earlier)."""
    ds = sorted(set(nq1["day"]))
    return [d for k, d in enumerate(ds) if k > 0 and (pd.Timestamp(d) - pd.Timestamp(ds[k - 1])).days <= 4]


def all1m(dry=False):
    """The one scored batch of the 1m version (section G): every G8 variant x {flat, tier} x the covered periods.
    dry=True: code check on the post-roll chunks; nothing is written or logged."""
    from tools.strategy_lab import sessions
    t0 = time.time()
    nq1 = load_1m_chunks()[0] if dry else load_1m_stitched()
    if nq1 is None:
        raise SystemExit("stitched TradingView 1m file or research/lab/DATA_1M.md missing - not scoring on chunks")

    def _w(fname, obj, indent=None):                       # every file write goes through here (none when dry)
        if not dry:
            with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=indent, default=float)

    def _score(trades, name, pn, **kw):                    # logged scorecard (plain stats when dry)
        if dry:
            return stats(trades, *PERIODS[pn])
        return score(trades, name, pn, **kw)
    flat_mem = {}
    chk = check_1m(nq1)
    print("1m data:", chk)
    trad = set(_tradable_days(nq1))
    es5 = bars("ES", "5m", min(trad), max(trad), warmup_days=10)
    cov = {}
    for pn in PERIODS_1M:
        a, z = PERIODS[pn]
        allp = sessions(a, z)
        c = [d for d in allp if d in trad]
        cov[pn] = {"sessions": len(allp), "covered": len(c), "first": c[0] if c else None, "last": c[-1] if c else None,
                   "full": len(c) == len(allp)}
    print("coverage:", cov)
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "data": chk, "coverage": cov, "variants": VARIANTS_1M, "runs": {}}
    for vname, vp in VARIANTS_1M.items():
        fun = collections.Counter()
        raws = [r for r in M.run_raw_mtf(nq1, vp, es5, _funnel=fun) if r["day"] >= PERIODS["ytd"][0]]
        entry = {"funnel": dict(fun), "params": vp}
        for sch in SCHEMES:
            trades = M.build_all(raws, sch, vp)
            for tr in trades:
                tr["trigger_tf"] = tr["info"]["trigger_tf"]
            _w(f"ATM_trades_{vname}_{sch}.json", trades)
            if sch == "flat":
                flat_mem[vname] = trades
            per = {}
            for pn in PERIODS_1M:
                cv = cov[pn]
                if not cv["covered"]:
                    continue
                name = f"ATM_{vname}_{sch}"
                if cv["full"]:
                    s = _score(trades, name, pn, notes="ATM 1m ladder (owner model)", params={**vp, "sizing": sch})
                    a, z = PERIODS[pn]
                else:                                      # partial coverage: only the covered window, saved as _cov
                    a, z = cv["first"], cv["last"]
                    s = stats(trades, a, z)
                    s.update({"name": name, "period_name": pn + "_cov", "window": [a, z], "params": {**vp, "sizing": sch}})
                    _w(f"{name}__{pn}_cov.json", s, indent=1)
                tp = [t for t in trades if a <= t["day"] <= z]
                row = {kk: s.get(kk) for kk in KEEP}
                row.update({"window": [a, z], "full_coverage": cv["full"], "covered_sessions": cv["covered"],
                            "exits": dict(collections.Counter(t["exit_kind"] for t in tp)),
                            "trigger_tf": {str(k_): {"n": len(v_), "avg_r": round(float(np.mean([x["r"] for x in v_])), 3),
                                                     "net": round(float(sum(x["pnl"] for x in v_)), 2)}
                                           for k_, v_ in sorted(collections.defaultdict(list, {
                                               tf_: [x for x in tp if x["trigger_tf"] == tf_] for tf_ in {x["trigger_tf"] for x in tp}}).items())},
                            "tiers": tier_table(trades, a, z),
                            "rho_score_r": _spearman([t["score"] for t in tp], [t["r"] for t in tp]),
                            "avg_risk_usd": round(float(np.mean([t["risk_pts"] * 2.0 * t["qty"] for t in tp] or [0])), 1),
                            "median_stop_pts": float(np.median([t["risk_pts"] for t in tp])) if tp else None})
                if sch == "flat":
                    row["conf"] = conf_table(trades, a, z)
                per[pn] = row
            entry[sch] = per
        res["runs"][vname] = entry
        print(vname, "done", round(time.time() - t0, 1), "s", dict(fun))
    # pre-registered selection (G8): dev net (flat) if >= 40 dev sessions covered, else covered 2026 before Aug-03
    if cov["dev"]["covered"] >= 40:
        crit = "dev net (flat)"
        best = max(VARIANTS_1M, key=lambda v: res["runs"][v]["flat"].get("dev", {}).get("net") or -1e9)
    else:
        crit = "net (flat) on covered 2026 sessions before 2026-08-03"
        best = max(VARIANTS_1M, key=lambda v: sum(t["pnl"] for t in flat_mem[v] if t["day"] < "2026-08-03"))
    res["best"] = {"variant": best, "criterion": crit}
    for tag, v in (("base", "m1_base"), ("best", best)):
        tr = [t for t in flat_mem[v] if PERIODS["ytd"][0] <= t["day"] <= PERIODS["ytd"][1]]
        _w(f"ATM_trades_1m_{tag}.json", {"variant": v, "sizing": "flat $350", "note": "TradingView NQ1! 1m, ATM model 1m "
           "ladder; prices are back-adjusted to the current front month; times are unix seconds (entry_t/exit_t = bar close; "
           "info.*_t = bar open)", "trades": tr}, indent=1)
    _w("ATM_results_1m.json", res, indent=1)
    print("best:", best, crit, "| all done", round(time.time() - t0, 1), "s")
    return res


def report1m():
    with open(os.path.join(OUT, "ATM_results_1m.json"), encoding="utf-8") as fh:
        R = json.load(fh)
    print("data", R["data"])
    print("coverage", R["coverage"])
    print("best", R["best"])
    H = ("| variant | sizing | period (window) | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | worst day $ | "
         "50K pass % (zero-edge) |\n|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|")
    for sch in SCHEMES:
        print(f"\n### 1m variants, {sch} sizing\n\n" + H)
        for v, e in R["runs"].items():
            for pn, s in e[sch].items():
                pf = "-" if s["pf"] is None else s["pf"]
                pas = "n/a" if s["rolling_pass"] is None else f"{s['rolling_pass']} ({s['zero_edge_pass']})"
                ci = s["ci95_r"] if s["ci95_r"] and s["ci95_r"][0] is not None else "-"
                wtxt = pn if s["full_coverage"] else f"{pn} ({s['window'][0]}..{s['window'][1]})"
                print(f"| {v} | {sch} | {wtxt} | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} {ci} | {pf} | "
                      f"{s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['worst_day']:,.0f} | {pas} |")
    print("\n### funnel\n\n| variant | days ok | swept | armed | signals 5m / 3m / 2m / 1m | skipped < min R | skipped size | "
          "trades 5m / 3m / 2m / 1m |\n|---|---:|---:|---:|---|---:|---:|---|")
    for v, e in R["runs"].items():
        f = collections.Counter(e["funnel"])
        print(f"| {v} | {f['days_ok']} | {f['days_swept']} | {f['armed']} | {f['signals_5m']} / {f['signals_3m']} / {f['signals_2m']} / "
              f"{f['signals_1m']} | {f['skip_rr']} | {f['skip_size']} | {f['trades_5m']} / {f['trades_3m']} / {f['trades_2m']} / {f['trades_1m']} |")
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    print("\n### 2026 by month, flat (trades / net $)\n\n| variant | " + " | ".join(m[5:] for m in months) + " |\n|---|" + "---:|" * 10)
    for v, e in R["runs"].items():
        mm = e["flat"].get("ytd", {}).get("months", {})
        print(f"| {v} | " + " | ".join(f"{mm[m]['trades']} / {mm[m]['net']:+,.0f}" if m in mm else "0" for m in months) + " |")
    print("\n### trigger frame (flat): n / avg R / net\n")
    for v, e in R["runs"].items():
        print(v, {pn: s["trigger_tf"] for pn, s in e["flat"].items()})
    print("\n### tiers (flat avg R) and rank test\n\n| variant | period | A | B | C | net flat | net tier | rho, p |\n|---|---|---|---|---|---:|---:|---|")
    for v, e in R["runs"].items():
        for pn, s in e["flat"].items():
            tt = s["tiers"]["tier"]
            cells = [f"{tt[x]['n']} / {tt[x]['avg_r']:+.2f} / {tt[x]['win']:.0f}" if x in tt else "0" for x in "ABC"]
            print(f"| {v} | {pn} | " + " | ".join(cells) + f" | {s['net']:+,.0f} | {e['tier'][pn]['net']:+,.0f} | {s['rho_score_r']} |")
    print("\n### max DD / worst day by scheme")
    for v, e in R["runs"].items():
        print(v, {pn: (e["flat"][pn]["max_dd"], e["tier"][pn]["max_dd"], e["flat"][pn]["worst_day"], e["tier"][pn]["worst_day"])
                  for pn in e["flat"]})
    print("\n### confluences m1_base (flat, with / without)")
    for pn, s in R["runs"]["m1_base"]["flat"].items():
        print(pn, {k: (v["r_with"], v["r_without"], v["n_with"]) for k, v in s["conf"].items()})
    for v, e in R["runs"].items():
        print(v, "median stop", {pn: s["median_stop_pts"] for pn, s in e["flat"].items()}, "exits",
              {pn: s["exits"] for pn, s in e["flat"].items()})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    {"smoke": smoke, "all": main, "diag": diag, "report": report, "smoke1m": smoke1m, "all1m": all1m,
     "dry1m": lambda: all1m(dry=True), "report1m": report1m}[cmd]()
