"""1-minute coverage audit: how much of each session data/NQ_1m.csv (and ES_1m.csv) really covers, and what it means for LIT.

    python tools/audit_1m.py                 # 2026, NQ + ES; prints the summary, writes research/lab/coverage_1m.json
    python tools/audit_1m.py --year 2025     # another year (after a 2025 1m import: python tools/import_tv.py <folder>)
    python tools/audit_1m.py --days          # also print every session

Per trading day (18:00 ET -> 17:00 ET) of the 5m file:
  want     = 5 x the 5m bars of the day (the minutes the market traded; quiet minutes inside a 5m bar count as wanted)
  have     = 1m bars inside those 5m windows; missing = want - have
  cover    = have / want
  lit_full = (NQ only) the day passes LIT's own rule (engine/lit.py bars_1m): >= 97% of the day's minutes in 5m windows whose
             five 1m bars rebuild the 5m bar exactly (a constant contract-basis offset is shifted, anything else dropped).
             On a day that fails, LIT's backtest and live loop execute on 5m bars instead (entry, stop, target, BE on the
             5m bars: a coarser, usually worse fill), and the live loop does not re-simulate it on 1m.
The LIT trades of run lit_live (research/runs/lit_live.json) on days that fail are listed, so you can see what is at stake.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import data_audit as da  # noqa: E402

COVER = 0.97


def day_table(sym: str, year: int, data_dir: str) -> pd.DataFrame:
    five = pd.read_csv(os.path.join(data_dir, f"{sym}_5m.csv"))
    p1 = os.path.join(data_dir, f"{sym}_1m.csv")
    one = pd.read_csv(p1) if os.path.exists(p1) else pd.DataFrame(columns=five.columns)
    five = five[~((five["high"] == five["low"]) & (five["volume"] <= 0))]   # engine.data.load hygiene
    five["day"] = da.tday_of(five["time"].values)
    five = five[five["day"].str[:4] == str(year)]
    one = one[(one["time"] % 60 == 0)].drop_duplicates("time")
    one = one[(one["time"] // 300 * 300).isin(set(five["time"]))]
    one["day"] = da.tday_of(one["time"].values) if len(one) else []
    want = five.groupby("day").size() * 5
    have = one.groupby("day").size() if len(one) else pd.Series(dtype=int)
    t = pd.DataFrame({"want": want}).join(pd.DataFrame({"have": have}), how="left").fillna(0).astype(int)
    t["missing"] = t["want"] - t["have"]
    t["cover"] = t["have"] / t["want"]
    t["holiday"] = [da.holiday_name(d) or "" for d in t.index]
    first_1m = da.tday_of([int(one["time"].min())])[0] if len(one) else None
    t["before_1m_file"] = [first_1m is None or d < first_1m for d in t.index]
    return t


def lit_full_days(year: int) -> set:
    """Days that pass engine/lit.py bars_1m on the research data (the backtest's own rule)."""
    from engine import lit
    M = lit.Market()
    B = lit.bars_1m(M)
    days = {M.days[k][0] for k in B.full}
    return {d for d in days if d[:4] == str(year)}


def lit_trades(year: int):
    p = os.path.join(ROOT, "research", "runs", "lit_live.json")
    if not os.path.exists(p):
        return []
    d = json.load(open(p, encoding="utf-8"))
    cols = d["trade_cols"]
    return [dict(zip(cols, r)) for r in d["trades"] if str(r[0])[:4] == str(year)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/audit_1m.py")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--days", action="store_true", help="print every session")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    report = {"year": a.year, "cover_rule": COVER, "symbols": {}}
    for sym in ("NQ", "ES"):
        t = day_table(sym, a.year, a.data)
        if not len(t):
            continue
        cov = t[~t["before_1m_file"]]
        low = cov[cov["cover"] < COVER]
        lowh = low[low["holiday"] == ""]
        rec = {"sessions_5m": int(len(t)), "sessions_with_1m_file": int(len(cov)),
               "first_1m_session": cov.index.min() if len(cov) else None,
               "missing_minutes": int(cov["missing"].sum()), "median_cover": float(cov["cover"].median()) if len(cov) else None,
               "under_97": [{"day": d, "cover": round(float(r.cover), 4), "missing": int(r.missing), "holiday": r.holiday}
                            for d, r in low.iterrows()]}
        print(f"{sym} {a.year}: {len(t)} sessions in {sym}_5m.csv; {sym}_1m.csv covers {len(cov)} of them"
              + (f" (from {rec['first_1m_session']})" if len(cov) < len(t) and len(cov) else ""))
        if len(cov):
            print(f"  missing minutes: {rec['missing_minutes']} of {int(cov['want'].sum())} "
                  f"({rec['missing_minutes'] / max(1, int(cov['want'].sum())):.2%}); median cover {rec['median_cover']:.2%}")
            print(f"  sessions under 97%: {len(low)} ({len(low) - len(lowh)} of them holiday / early-close sessions)")
            for d, r in low.iterrows():
                print(f"    {d}  {r.cover:6.1%}  {int(r.missing):4d} min missing  {r.holiday}")
        if sym == "NQ":
            full = lit_full_days(a.year)
            fail = sorted(d for d in cov.index if d not in full)
            rec["lit_full_days"] = len(full)
            rec["lit_fail_days"] = fail
            tr = lit_trades(a.year)
            on_fail = [x for x in tr if x["day"] in set(fail)]
            by_trig = pd.Series([x["trigger"] for x in tr]).value_counts().to_dict() if tr else {}
            rec["lit_trades"] = {"n": len(tr), "by_trigger": by_trig,
                                 "on_fail_days": [{"day": x["day"], "trigger": x["trigger"], "r": x["r"], "pnl": x["pnl"]}
                                                  for x in on_fail]}
            print(f"  LIT's 1m rule (engine/lit.py bars_1m, >= 97% clean 1m windows): {len(full)} sessions pass, "
                  f"{len(fail)} fail" + (f": {', '.join(fail[:12])}{' ...' if len(fail) > 12 else ''}" if fail else ""))
            if tr:
                print(f"  run lit_live, {a.year}: {len(tr)} trades ({', '.join(f'{k} {v}' for k, v in by_trig.items())}); "
                      f"on failing days: {len(on_fail)}"
                      + (" (" + ", ".join(f"{x['day']} {x['trigger']} {x['r']:+.2f}R ${x['pnl']:+,.0f}" for x in on_fail) + ")" if on_fail else ""))
        if a.days:
            print(t.to_string())
        report["symbols"][sym] = rec
    if not a.no_write:
        out = os.path.join(ROOT, "research", "lab", "coverage_1m.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, default=str)
        print(f"wrote {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
