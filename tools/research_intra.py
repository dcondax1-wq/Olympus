"""Intraday anatomy study (run prefix "intra_", 2026-10-17).

Slices the locked strategy's exact live-loop replay (tools/runlib.replay) by entry hour x weekday, AM/PM killzone,
time in trade, MFE/MAE, trigger, swept pool type, stop bucket, target label and confluence score, in 2026 and 2021-25.
Writes research/archive/engine-2026-10-17/intraday_heat.json (the archived engine version) (3D heat view) and prints the tables for research/writeups/intraday-anatomy.md.
The strongest slices that are known at entry are then tested as size rules (x0.5 / x1.25) with rl.size(rule=...).

  python tools/research_intra.py            # tables + heat json + size-rule runs (intra_*)
  python tools/research_intra.py --no-save  # tables only
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

ET = ZoneInfo("America/New_York")
MAJOR = ("H1H", "H1L", "ONH", "ONL", "LOH", "LOL", "ASH", "ASL", "PDH", "PDL", "PWH", "PWL")
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SPANS = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}


# ------------------------------------------------------------------------------------------------ features known at entry
def hour_et(t):
    return dt.datetime.fromtimestamp(int(t["entry_t"]), ET).hour


def minute_et(t):
    d = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
    return d.hour * 60 + d.minute


def dow(t):
    return dt.date.fromisoformat(t["day"]).weekday()


def killzone(t):
    return "AM" if hour_et(t) < 12 else "PM"


def half_hour(t):
    m = minute_et(t)
    return f"{m // 60:02d}:{'00' if m % 60 < 30 else '30'}"


def pool_tags(t):
    tags = set()
    for p in (t.get("pools") or []):
        for tag in p.split("/"):
            tags.add(tag.replace("EQH·", "").replace("EQL·", ""))
            if tag.startswith("EQ"):
                tags.add("EQ")
    return tags


def pool_kind(t):
    """What was swept: minor only (15m swing), a major, or equal highs/lows."""
    tags = pool_tags(t)
    if "EQ" in tags and not any(x in tags for x in MAJOR):
        return "equal highs/lows"
    if any(x in tags for x in MAJOR):
        return "major"
    return "minor (15m swing)"


def pool_detail(t):
    """The most important pool swept (first match in order of weight)."""
    tags = pool_tags(t)
    for k, label in (("PWH", "prior week"), ("PWL", "prior week"), ("PDH", "prior day"), ("PDL", "prior day"),
                     ("ONH", "overnight"), ("ONL", "overnight"), ("LOH", "London"), ("LOL", "London"), ("ASH", "Asia"), ("ASL", "Asia"),
                     ("H1H", "1H swing"), ("H1L", "1H swing"), ("EQ", "equal highs/lows")):
        if k in tags:
            return label
    return "15m swing only"


def stop_bucket(t):
    rp = float(t["risk_pts"])
    return "<20" if rp < 20 else "20-30" if rp < 30 else "30-40" if rp < 40 else "40-50" if rp < 50 else "50-60"


def target_kind(t):
    lab = t.get("target_label") or ""
    if lab.startswith("5.0R cap"):
        return "5R cap (draw farther)"
    for k, label in (("PW", "prior week H/L"), ("PD", "prior day H/L"), ("ON", "overnight H/L"), ("LO", "London H/L"), ("AS", "Asia H/L"),
                     ("EQ", "equal highs/lows"), ("H1", "1H swing")):
        if k in lab:
            return label
    return "other"


def rr_bucket(t):
    rr = float(t["f"].get("rr_plan") or 0)
    return "1.5-2R" if rr < 2 else "2-3R" if rr < 3 else "3-5R" if rr < 5 else "5R (capped)"


def held_bucket(t):
    b = int(t.get("bars_held") or 0)
    return "<=15 min" if b <= 3 else "20-30 min" if b <= 6 else "35-60 min" if b <= 12 else "1-2 h" if b <= 24 else "2 h+"


def score_bucket(t):
    return str(int(t.get("score") or 0))


FEATURES = {
    "hour": hour_et, "dow": dow, "killzone": killzone, "half_hour": half_hour, "trigger": lambda t: t["trigger"],
    "trigger_tf": lambda t: t.get("trigger_tf"), "pool_kind": pool_kind, "pool_detail": pool_detail, "stop_bucket": stop_bucket,
    "target_kind": target_kind, "rr_bucket": rr_bucket, "held": held_bucket, "score": score_bucket, "exit": lambda t: t["exit"],
    "regime": lambda t: t.get("regime"), "late": lambda t: "late" if (t.get("m15_trend") or 0) * t["dir"] > 0 else "not late",
    "dir": lambda t: "long" if t["dir"] > 0 else "short",
}


# ------------------------------------------------------------------------------------------------ tables
def in_span(t, span):
    a, z = SPANS[span]
    return a <= t["day"] <= z


def cell(T):
    if not T:
        return {"n": 0, "avg_r": None, "net": 0, "win": None, "pf": None}
    r = np.array([t["r"] for t in T]); p = np.array([t["pnl"] for t in T])
    gl = -p[p < 0].sum()
    return {"n": len(T), "avg_r": round(float(r.mean()), 3), "net": round(float(p.sum())), "win": round(100 * float((r > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None, "sum_r": round(float(r.sum()), 1),
            "mfe_med": round(float(np.median([t["mfe"] for t in T])), 2), "target_pct": round(100 * sum(t["exit"] == "TARGET" for t in T) / len(T), 1)}


def table(T, feat, order=None):
    fn = FEATURES[feat]
    out = {}
    for span in SPANS:
        by = collections.defaultdict(list)
        for t in T:
            if in_span(t, span):
                by[fn(t)].append(t)
        out[span] = {str(k): cell(v) for k, v in by.items()}
    keys = order or sorted({k for s in out.values() for k in s}, key=lambda k: (len(k), k))
    return keys, out


def md_table(T, feat, title, order=None, cols=("n", "avg_r", "win", "pf", "net")):
    keys, out = table(T, feat, order)
    lines = [f"**{title}**", "", "| | " + " | ".join(f"2026 {c}" for c in cols) + " | " + " | ".join(f"2021-25 {c}" for c in cols) + " |",
             "|---|" + "---|" * (2 * len(cols))]
    for k in keys:
        row = [str(k)]
        for span in SPANS:
            c = out[span].get(str(k), cell([]))
            for col in cols:
                v = c.get(col)
                row.append("-" if v is None else (f"{v:+,}" if col == "net" else f"{v}"))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines), out


def mfe_profile(T):
    """What the best point of each trade says about the 1R breakeven and the 5R bank."""
    out = {}
    for span in SPANS:
        X = [t for t in T if in_span(t, span)]
        n = len(X) or 1
        mfe = np.array([t["mfe"] for t in X]); r = np.array([t["r"] for t in X])
        reach = {lvl: round(100 * float((mfe >= lvl).mean()), 1) for lvl in (0.5, 1, 1.5, 2, 3, 4, 5)}
        losers = [t for t in X if t["r"] <= -0.1]            # real losers (breakeven exits end at about -0.02R from costs)
        los_plus1 = [t for t in losers if t["mfe"] >= 1.0]
        los_plus05 = [t for t in losers if t["mfe"] >= 0.5]
        reached1 = [t for t in X if t["mfe"] >= 1.0]
        r1_then_target = sum(t["exit"] == "TARGET" for t in reached1)
        r1_then_be = sum(t["exit"] == "BE/TRAIL" for t in reached1)
        r1_then_gb = sum(t["exit"] == "SIGNAL giveback" for t in reached1)
        r1_then_loss = sum(t["r"] <= -0.1 for t in reached1)
        r1_then_ts = sum(t["exit"] == "TIME STOP" for t in reached1)
        reached3 = [t for t in X if t["mfe"] >= 3.0]
        # the 5R bank: trades whose plan was capped at 5R
        capped = [t for t in X if (t.get("target_label") or "").startswith("5.0R cap")]
        capped_hit = sum(t["exit"] == "TARGET" for t in capped)
        mae = np.array([t["mae"] for t in X])
        out[span] = {
            "n": len(X), "reach_pct": reach, "mfe_median": round(float(np.median(mfe)), 2),
            "mfe_median_winners": round(float(np.median(mfe[r > 0])), 2) if (r > 0).any() else None,
            "mfe_median_losers": round(float(np.median(mfe[r < 0])), 2) if (r < 0).any() else None,
            "losers": len(losers), "losers_plus1_first": len(los_plus1), "losers_plus1_pct": round(100 * len(los_plus1) / max(1, len(losers)), 1),
            "losers_plus05_first": len(los_plus05), "losers_plus05_pct": round(100 * len(los_plus05) / max(1, len(losers)), 1),
            "losers_plus1_trending": sum(t.get("regime") == "trending" for t in los_plus1),
            "reached_1r": len(reached1), "r1_then_target": r1_then_target, "r1_then_be": r1_then_be, "r1_then_giveback": r1_then_gb,
            "r1_then_loss": r1_then_loss, "r1_then_timestop": r1_then_ts, "r1_avg_r": round(float(np.mean([t["r"] for t in reached1])), 2) if reached1 else None,
            "reached_3r": len(reached3), "r3_avg_r": round(float(np.mean([t["r"] for t in reached3])), 2) if reached3 else None,
            "r3_then_target": sum(t["exit"] == "TARGET" for t in reached3),
            "capped_5r": len(capped), "capped_5r_hit": capped_hit, "capped_5r_hit_pct": round(100 * capped_hit / max(1, len(capped)), 1),
            "capped_5r_mfe_ge4": sum(t["mfe"] >= 4 for t in capped), "capped_5r_avg_r": round(float(np.mean([t["r"] for t in capped])), 2) if capped else None,
            "mae_median": round(float(np.median(mae)), 2), "mae_median_winners": round(float(np.median(mae[r > 0])), 2) if (r > 0).any() else None,
            "winners_mae_ge_05": round(100 * float((mae[r > 0] >= 0.5).mean()), 1) if (r > 0).any() else None,
            "winners_mae_ge_07": round(100 * float((mae[r > 0] >= 0.7).mean()), 1) if (r > 0).any() else None,
            "stops_mae_med": round(float(np.median([t["mfe"] for t in X if t["exit"] == "STOP"])), 2) if any(t["exit"] == "STOP" for t in X) else None,
        }
    return out


def heat(T):
    """dow x hour cells for the 3D heat view: all years, 2026, 2021-25."""
    def cells(X):
        by = collections.defaultdict(list)
        for t in X:
            by[(dow(t), hour_et(t))].append(t)
        rows = []
        for d in range(5):
            for h in range(9, 16):
                c = cell(by.get((d, h), []))
                rows.append({"dow": d, "hour": h, "n": c["n"], "avg_r": c["avg_r"] if c["n"] else 0.0, "net": c["net"],
                             "win": c["win"] if c["n"] else 0.0})
        return rows
    return {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "exact live-loop replay of the locked strategy, live sizing, costs included",
            "dow_labels": DOW, "hours": list(range(9, 16)), "cells": cells(T),
            "periods": {span: cells([t for t in T if in_span(t, span)]) for span in SPANS}}


# ------------------------------------------------------------------------------------------------ size rules
def rule_mult(feat, pick, mult):
    fn = FEATURES[feat]
    def rule(t, ctx):
        return mult if str(fn(t)) in pick else 1.0
    return rule


def combo_rule(parts):
    """parts: [(feat, pick, mult), ...] multiplied together."""
    fns = [(FEATURES[f], set(p), m) for f, p, m in parts]
    def rule(t, ctx):
        m = 1.0
        for fn, pick, mult in fns:
            if str(fn(t)) in pick:
                m *= mult
        return m
    return rule


def judge(S, base_S):
    """The study's adopt rule: more net and at least the same PF in both periods, 2-4 trades a week, and no more 1-month eval
    fails in either period (owner: evals must not fail more often). Mixed periods: promising when the worse period is within
    1% of its baseline net, else rejected."""
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, B = base_S["spans"]["2026"], base_S["spans"]["2021-25"]
    better = a["net"] > A["net"] and (a["pf"] or 0) >= (A["pf"] or 0) and b["net"] > B["net"] and (b["pf"] or 0) >= (B["pf"] or 0)
    no_more_fails = a["f20"] <= A["f20"] and b["f20"] <= B["f20"]
    if better and rl.passes(S) and no_more_fails:
        return "adopt-candidate"
    if better:
        return "promising"           # more money, but more eval fails / drawdown: extra leverage, not an edge
    close = lambda x, X: x["net"] >= X["net"] - 0.01 * abs(X["net"])
    if (a["net"] > A["net"] and close(b, B)) or (b["net"] > B["net"] and close(a, A)):
        return "promising"
    return "rejected"


def run_rule(raw, base_S, rid, title, question, feat, pick, mult, notes="", parts=None, family=None):
    rule = combo_rule(parts) if parts else rule_mult(feat, pick, mult)
    T = rl.size(raw, rule=rule)
    S = rl.score(T, raw)
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, B = base_S["spans"]["2026"], base_S["spans"]["2021-25"]
    status = judge(S, base_S)
    verdict = (f"2026 {a['net']:+,} (PF {a['pf']}, DD {a['dd']:,}, 1-month eval {a['p20']}/{a['f20']}) vs base {A['net']:+,} (PF {A['pf']}, DD {A['dd']:,}, {A['p20']}/{A['f20']}); "
               f"2021-25 {b['net']:+,} (PF {b['pf']}, DD {b['dd']:,}, 1-month eval {b['p20']}/{b['f20']}) vs base {B['net']:+,} (PF {B['pf']}, DD {B['dd']:,}, {B['p20']}/{B['f20']}).")
    desc = " x ".join(f"{f} in {sorted(p)} -> x{m}" for f, p, m in parts) if parts else f"{feat} in {sorted(pick)} -> x{mult}"
    rl.save(rid, title, family or ("timing" if feat in ("hour", "dow", "killzone", "half_hour") else "filters"), question,
            params={}, sizing={"rule": desc, "on_top_of": "live sizing (cold x0.25, late x0.5)"},
            trades=T, scored=S, status=status, verdict=verdict, notes=notes, writeup="intraday-anatomy.md", tags=["intra"])
    return S, status


def random_group(T, feat, pick, shuffles=3000, seed=7):
    """How often a random group of the same size (per period) loses at least as much money as the picked group: the chance
    that the slice is just noise. Scaling a group by m changes the net by about (m-1) x its net, so the group's net is the test."""
    rng = np.random.default_rng(seed)
    fn = FEATURES[feat]
    out = {}
    for span in SPANS:
        X = [t for t in T if in_span(t, span)]
        p = np.array([t["pnl"] for t in X])
        mask = np.array([str(fn(t)) in pick for t in X])
        k = int(mask.sum()); g = float(p[mask].sum())
        if k == 0 or k == len(X):
            out[span] = {"n": k, "net": round(g), "p_random_worse": None}; continue
        sims = np.array([p[rng.permutation(len(p))[:k]].sum() for _ in range(shuffles)])
        out[span] = {"n": k, "net": round(g), "p_random_worse": round(float((sims <= g).mean()), 3), "p_random_better": round(float((sims >= g).mean()), 3)}
    return out


CANDIDATES = [
    ("intra_cisd_125", "CISD triggers at x1.25 size", "trigger", {"CISD"}, 1.25,
     "CISD made more per trade than IFVG in both periods (2026 PF 5.7 vs 2.4, 2021-25 PF 1.53 vs 1.11)."),
    ("intra_ifvg_half", "IFVG triggers at half size", "trigger", {"IFVG"}, 0.5,
     "The mirror of intra_cisd_125: IFVG triggers are the weaker trigger in both periods."),
    ("intra_stop3040_half", "30-40 pt stops at half size", "stop_bucket", {"30-40"}, 0.5,
     "The only stop bucket that lost money in both periods (2026 PF 0.63, 2021-25 PF 0.94)."),
    ("intra_tgt_eq_half", "Equal-highs/lows targets at half size", "target_kind", {"equal highs/lows"}, 0.5,
     "Trades aiming at equal highs/lows lost in both periods (2026 PF 0.42 on 10, 2021-25 PF 0.94 on 120); the target is rarely reached (0% / 13%)."),
    ("intra_open_125", "09:30-09:59 entries at x1.25 size", "half_hour", {"09:30"}, 1.25,
     "The opening half hour was profitable in both periods (2026 PF 3.1, 2021-25 PF 1.45, the best hour in 2021-25)."),
    ("intra_h10_half", "10:00-10:59 entries at half size", "hour", {"10"}, 0.5,
     "The 10 o'clock hour is the weakest hour in both periods (2026 PF 0.13, 2021-25 PF 1.07)."),
    ("intra_rr2_half", "Targets under 2R away at half size", "rr_bucket", {"1.5-2R"}, 0.5,
     "Trades whose target was under 2R away made nothing in either period (2026 PF 0.93, 2021-25 PF 1.01)."),
]


COMBOS = [
    ("intra_combo_defensive", "Half size on 30-40 pt stops and on equal-highs/lows targets", "filters",
     [("stop_bucket", {"30-40"}, 0.5), ("target_kind", {"equal highs/lows"}, 0.5)],
     "The two defensive slices together (both lost money in both periods)."),
    ("intra_combo_all", "Defensive halves + CISD x1.25", "filters",
     [("stop_bucket", {"30-40"}, 0.5), ("target_kind", {"equal highs/lows"}, 0.5), ("trigger", {"CISD"}, 1.25)],
     "The two defensive halves plus more size on the stronger trigger."),
]


def candidates(raw, T, base_S, save=True):
    rows = []
    for rid, title, feat, pick, mult, why in CANDIDATES:
        rg = random_group(T, feat, pick)
        if save:
            S, status = run_rule(raw, base_S, rid, title, f"Is the slice '{feat} in {sorted(pick)}' worth a size change?", feat, pick, mult,
                                 notes=why + f" Random-group check (how often a random group of the same size does as well): {json.dumps(rg)}")
        else:
            S = rl.score(rl.size(raw, rule=rule_mult(feat, pick, mult)), raw); status = judge(S, base_S)
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]
        rows.append({"id": rid, "title": title, "status": status, "2026": a, "2021-25": b, "random": rg})
        print(f"{rid:24s} {status:16s} {rl.line(S, '2026')}\n{'':41s} {rl.line(S, '2021-25')} | random {rg}", flush=True)
    for rid, title, fam, parts, why in COMBOS:
        if save:
            S, status = run_rule(raw, base_S, rid, title, "Do the slices add up?", None, None, None, notes=why, parts=parts, family=fam)
        else:
            S = rl.score(rl.size(raw, rule=combo_rule(parts)), raw); status = judge(S, base_S)
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]
        rows.append({"id": rid, "title": title, "status": status, "2026": a, "2021-25": b})
        print(f"{rid:24s} {status:16s} {rl.line(S, '2026')}\n{'':41s} {rl.line(S, '2021-25')}", flush=True)
    return rows


def main(save=True):
    raw = rl.replay()
    T = rl.size(raw)
    base_S = rl.score(T, raw)
    print("BASE", rl.line(base_S, "2026")); print("BASE", rl.line(base_S, "2021-25"))
    out_tables = {}
    sections = [
        ("killzone", "AM vs PM killzone", ["AM", "PM"]),
        ("hour", "Entry hour (ET)", ["9", "10", "11", "13", "14", "15"]),
        ("half_hour", "Entry half-hour (ET)", None),
        ("dow", "Weekday", ["0", "1", "2", "3", "4"]),
        ("trigger", "Trigger", ["IFVG", "CISD"]),
        ("trigger_tf", "Trigger timeframe", None),
        ("pool_kind", "Pool type swept", ["major", "equal highs/lows", "minor (15m swing)"]),
        ("pool_detail", "Most important pool swept", None),
        ("stop_bucket", "Stop bucket (pts)", ["<20", "20-30", "30-40", "40-50", "50-60"]),
        ("target_kind", "Target (which pool is aimed at)", None),
        ("rr_bucket", "Planned reward (R to target)", ["1.5-2R", "2-3R", "3-5R", "5R (capped)"]),
        ("score", "Confluence score", ["1", "2", "3"]),
        ("held", "Time in trade", ["<=15 min", "20-30 min", "35-60 min", "1-2 h", "2 h+"]),
        ("exit", "Exit reason", None),
        ("dir", "Direction", ["long", "short"]),
        ("regime", "Regime", ["rotational", "trending"]),
        ("late", "Late entry", ["not late", "late"]),
    ]
    md = []
    for feat, title, order in sections:
        cols = ("n", "avg_r", "win", "pf", "net", "target_pct") if feat in ("target_kind", "rr_bucket") else ("n", "avg_r", "win", "pf", "net")
        s, out = md_table(T, feat, title, order, cols)
        md.append(s); out_tables[feat] = out
    # dow x hour (per period) as text
    for span in SPANS:
        X = [t for t in T if in_span(t, span)]
        by = collections.defaultdict(list)
        for t in X:
            by[(dow(t), hour_et(t))].append(t)
        lines = [f"**Weekday x hour, {span} (n / avg R / net $)**", "", "| | " + " | ".join(f"{h}:00" for h in range(9, 16) if h != 12) + " |", "|---|" + "---|" * 6]
        for d in range(5):
            row = [DOW[d]]
            for h in range(9, 16):
                if h == 12:
                    continue
                c = cell(by.get((d, h), []))
                row.append(f"{c['n']} / {c['avg_r'] if c['n'] else '-'} / {c['net']:+,}" if c["n"] else "-")
            lines.append("| " + " | ".join(row) + " |")
        md.append("\n".join(lines))
    prof = mfe_profile(T)
    md.append("MFE/MAE PROFILE\n" + json.dumps(prof, indent=1))
    # dow x killzone
    for span in SPANS:
        X = [t for t in T if in_span(t, span)]
        by = collections.defaultdict(list)
        for t in X:
            by[(dow(t), killzone(t))].append(t)
        lines = [f"**Weekday x killzone, {span} (n / avg R / net $)**", "", "| | AM | PM |", "|---|---|---|"]
        for d in range(5):
            row = [DOW[d]]
            for kz in ("AM", "PM"):
                c = cell(by.get((d, kz), []))
                row.append(f"{c['n']} / {c['avg_r']} / {c['net']:+,}" if c["n"] else "-")
            lines.append("| " + " | ".join(row) + " |")
        md.append("\n".join(lines))
    text = "\n\n".join(md)
    scratch = os.path.join(ROOT.replace("/home/user/nq-liquidity-engine", "/tmp/claude-0/-home-user-nq-liquidity-engine/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad"), "sprint", "intra")
    os.makedirs(scratch, exist_ok=True)
    open(os.path.join(scratch, "tables.md"), "w", encoding="utf-8").write(text)
    json.dump({"tables": out_tables, "mfe": prof}, open(os.path.join(scratch, "tables.json"), "w"), indent=1)
    print(text)
    H = heat(T)
    if save:
        # archived engine version (LIT's research/lab/intraday_heat.json comes from tools/lit_dash_data.py)
        rl._dump(H, os.path.join(ROOT, "research", "archive", "engine-2026-10-17", "intraday_heat.json"), indent=1)
        print("wrote research/archive/engine-2026-10-17/intraday_heat.json")
    rows = candidates(raw, T, base_S, save=save)
    json.dump(rows, open(os.path.join(scratch, "candidates.json"), "w"), indent=1)
    return raw, T, base_S, out_tables, prof, rows


if __name__ == "__main__":
    main(save="--no-save" not in sys.argv)
