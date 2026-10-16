"""Night study 2 - entry quality filters that must NOT cut frequency below 2.5 trades/week in any period.

Filters tested (real engine where a parameter exists, post-filter of the default trade list where it does not):
  (a) shallow raid: sweep extreme within 0.5 ATR of the swept pool.  ENGINE: w_shallow=100 + min_score=101 turns the
      existing 'shallow raid' confluence into a hard gate (a trade must have it AND still score >= 1 on the normal weights).
      Other depths (<= 1.0 / 1.5 ATR, in ticks) are POST-FILTERS on the recorded depth_atr feature.
  (b) trigger candle body >= x ATR.  ENGINE for x = 1.0 (w_disp=100 + min_score=101); POST-FILTER for 0.5 / 0.75.
  (c) skip only the first 10 / 15 / 30 minutes after the 09:30 open: ENGINE via entry_windows.
  (d) first valid setup only: ENGINE max_trades_day=1 (first per day); POST-FILTER first per (day, AM/PM, direction).
  (e) target room >= 2R: ENGINE min_rr=2.0 (with and without the 2R fallback target); POST-FILTER rr_plan >= 2.
Post-filters simply drop trades from the default trade list; they ignore the knock-on effect on the day's second trade
(max 2 trades/day, stop after a win), so treat them as upper bounds on what an engine implementation would do.
Run: python study_night_2_filters.py
"""
from multiprocessing import Pool

from study_night_common import SEGS, run_both, seg_trades, metrics, fmt, md_table, verdict

HARD = 100   # weight that turns a w_* confluence into a hard gate together with min_score = HARD + 1
ENGINE_V = [
    ("baseline (defaults)", {}),
    ("(a) shallow raid only (<=0.5 ATR past pool)", {"w_shallow": HARD, "min_score": HARD + 1}),
    ("(b) trigger body >= 1.0 ATR", {"w_disp": HARD, "min_score": HARD + 1}),
    ("(c) skip first 10 min (entry from 09:40)", {"entry_windows": [[580, 690], [810, 930]]}),
    ("(c) skip first 15 min (entry from 09:45)", {"entry_windows": [[585, 690], [810, 930]]}),
    ("(c) skip first 30 min (entry from 10:00)", {"entry_windows": [[600, 690], [810, 930]]}),
    ("(c) ref: skip first 45 min (entry from 10:15)", {"entry_windows": [[615, 690], [810, 930]]}),
    ("(d) first valid setup per day (max_trades_day=1)", {"max_trades_day": 1}),
    ("(e) min_rr 2.0 (fallback 2R target kept)", {"min_rr": 2.0}),
    ("(e) min_rr 2.0, no fallback (skip if no 2R pool)", {"min_rr": 2.0, "use_fallback": False}),
    ("(e) ref: min_rr 1.5, no fallback", {"use_fallback": False}),
    ("(e) min_rr 1.75", {"min_rr": 1.75}),
    ("combo: skip 15 min + first setup per day", {"entry_windows": [[585, 690], [810, 930]], "max_trades_day": 1}),
]


def _job(job):
    name, p = job
    res = run_both(p)
    segs = seg_trades(res)
    return name, {lab: metrics(tr, dy) for lab, (tr, dy) in segs.items()}, {lab: (tr, dy) for lab, (tr, dy) in segs.items()}


def _mod(t):
    """Entry time as minutes after midnight ET."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    x = dt.datetime.fromtimestamp(t["entry_t"], ZoneInfo("America/New_York"))
    return x.hour * 60 + x.minute


def _first_per_session_side(tr):
    seen, keep = set(), []
    for t in sorted(tr, key=lambda t: t["entry_t"]):
        key = (t["day"], int(t["features"].get("pm", 0)), t["dir"])
        if key in seen:
            continue
        seen.add(key); keep.append(t)
    return keep


POST = [
    ("(a) post: depth <= 0.5 ATR", lambda tr: [t for t in tr if t["features"]["depth_atr"] <= 0.5]),
    ("(a) post: depth <= 1.0 ATR", lambda tr: [t for t in tr if t["features"]["depth_atr"] <= 1.0]),
    ("(a) post: depth <= 1.5 ATR", lambda tr: [t for t in tr if t["features"]["depth_atr"] <= 1.5]),
    ("(a) post: depth > 0.5 ATR (the complement)", lambda tr: [t for t in tr if t["features"]["depth_atr"] > 0.5]),
    ("(b) post: body >= 0.5 ATR", lambda tr: [t for t in tr if t["features"]["disp_atr"] >= 0.5]),
    ("(b) post: body >= 0.75 ATR", lambda tr: [t for t in tr if t["features"]["disp_atr"] >= 0.75]),
    ("(b) post: body >= 1.0 ATR", lambda tr: [t for t in tr if t["features"]["disp_atr"] >= 1.0]),
    ("(d) post: first setup per session & side", _first_per_session_side),
    ("(d) post: drop 2nd trade of the day", lambda tr: [t for t in tr if not t["features"].get("x_second_trade")]),
    ("(e) post: planned R:R >= 2", lambda tr: [t for t in tr if t["features"]["rr_plan"] >= 2.0]),
    ("(e) post: room to major liquidity >= 3R", lambda tr: [t for t in tr if t["features"].get("dol_room3")]),
]


if __name__ == "__main__":
    with Pool(6) as pool:
        out = pool.map(_job, ENGINE_V)
    base_ms = out[0][1]
    base_total = sum(m["net"] for m in base_ms.values())
    base_segs = out[0][2]

    print("# Study 2 - entry quality filters\n")
    print("Cells: trades / trades-per-week / avg R / net $ / profit factor / max drawdown. 'LOW' = below 2.5 trades/week.\n")
    print("## Real-engine variants\n")
    rows = []
    for name, ms, _ in out:
        tot = sum(m["net"] for m in ms.values())
        rows.append([name] + [fmt(ms[lab]) for lab, *_ in SEGS] + [f"${tot:+,.0f}", verdict(ms, tot, base_ms, base_total)])
    print(md_table(rows, ["variant"] + [lab for lab, *_ in SEGS] + ["4-period total", "owner's test"]))
    print()

    print("## Post-filters on the default trade list (approximate - see docstring)\n")
    rows = []
    for name, fn in POST:
        ms = {lab: metrics(fn(tr), dy) for lab, (tr, dy) in base_segs.items()}
        tot = sum(m["net"] for m in ms.values())
        rows.append([name] + [fmt(ms[lab]) for lab, *_ in SEGS] + [f"${tot:+,.0f}", verdict(ms, tot, base_ms, base_total)])
    print(md_table(rows, ["filter"] + [lab for lab, *_ in SEGS] + ["4-period total", "owner's test"]))
    print()

    # ---- where do the default trades sit on these features? (so the reader can see the frequency cost)
    print("## Feature distribution of the default trades (for context)\n")
    rows = []
    for lab, (tr, dy) in base_segs.items():
        n = len(tr) or 1
        rows.append([lab, len(tr),
                     f"{sum(t['features']['depth_atr'] <= 0.5 for t in tr) / n:.0%}",
                     f"{sum(t['features']['disp_atr'] >= 1.0 for t in tr) / n:.0%}",
                     f"{sum(570 <= _mod(t) < 585 for t in tr) / n:.0%}",
                     f"{sum(bool(t['features'].get('x_second_trade')) for t in tr) / n:.0%}",
                     f"{sum(t['features']['rr_plan'] >= 2.0 for t in tr) / n:.0%}"])
    print(md_table(rows, ["period", "trades", "shallow (<=0.5 ATR)", "body >= 1 ATR", "entered 09:30-09:45", "2nd trade of day", "planned RR >= 2"]))
