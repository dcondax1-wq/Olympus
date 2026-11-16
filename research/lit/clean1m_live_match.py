"""Night W1 (2026-11-16) RESEARCH: the LIT backtest with a 1m cleaner that matches what the live feed sees.

engine/data._clean_1m drops a 5-minute window when its first 1m row "covers the whole window with more volume than the other
four minutes together" (the volume heuristic, meant to catch a 5m bar written into the 1m file). The live PC bot never
applies it (engine/lit_live.feed_1m + lit.bars_1m(tol=1.0)), so on those windows live and backtest see different 1m bars
(tests/test_lit_oif 117/120: 2026-03-23, 2026-05-05; 2026-04-03 is a data gap).

Variants (all costs in, live_model.json "lit" sizing, tools/lit_final.score):
  today   engine/data._clean_1m as is (the research rule)
  A       _clean_1m without the volume heuristic; the exact base check (first row == the 5m bar's H/L/C = a real import
          artifact, which a real live feed never has) stays
  B       A + the live loop's own rule on top: lit.bars_1m(tol=LIVE_TOL_1M) (a window rebuilding its 5m bar within 1 pt)

    python -X utf8 research/lit/clean1m_live_match.py      -> research/lit/clean1m_live_match.json
Read-only on engine files (monkeypatches in this process only).

RESULT (2026-11-16, live_model.json lit, costs in):
  H1 2026  today 80 tr 3.12/wk PF 4.98 net $33,901 ($5,562/mo) DD -$2,196 pass 83.7% f10 1.6%
           A     80 tr 3.12/wk PF 4.85 net $33,171 ($5,442/mo) DD -$2,196 pass 83.7% f10 3.9%   (-$730)
  H2 2026  identical (40 tr, PF 2.91, $9,919, DD -$1,396, pass 100%);  2021-25 identical (no 1m data: 5m execution)
  B = A exactly. Trades that change: 03-23 (+$1,236 -> +$596), 04-03 (-$360 -> -$285), 05-05 (-$279 -> -$443).
  tests.test_lit_oif with A as the backtest cleaner: 120/120 (today 117/120) = live == backtest on every 2026 trade.
  The other way (the live feed fed today's cleaned bars): 1/3 of those days match; 03-23 is still no entry (the trigger
  window is missing, the bot sees a 5-bar gap), 04-03 still differs. The backtest's 03-23 winner is unreachable live either way.
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from engine import data as ED  # noqa: E402
from engine import lit  # noqa: E402
from engine.lit_live import LIVE_TOL_1M  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "clean1m_live_match.json")


def clean_no_volume_rule(df, base=None):
    """engine/data._clean_1m minus the volume heuristic (the base check stays)."""
    df = df.sort_values("time").drop_duplicates("time", keep="last")
    df = df[df["time"] % 60 == 0].copy()
    df["bucket"] = df["time"] // 300 * 300
    df = df[df.groupby("bucket")["time"].transform("size") == 5]
    if df.empty or base is None:
        return df
    first = df.groupby("bucket").head(1).set_index("bucket")
    bb = pd.DataFrame({"h5": base.h, "l5": base.l, "c5": base.c}, index=base.t)
    jb = first.join(bb, how="left")
    bad = (jb["high"] == jb["h5"]) & (jb["low"] == jb["l5"]) & (jb["close"] == jb["c5"])
    return df[~df["bucket"].isin(jb.index[bad.values])]


def trades(P, variant):
    PP = {**lit.DEFAULTS, **P}
    M, C = F.market(PP["ref"], PP["extra_boxes"])
    orig = ED._clean_1m
    if variant in ("A", "B"):
        ED._clean_1m = clean_no_volume_rule
    try:
        B1 = lit.bars_1m(M, tol=LIVE_TOL_1M if variant == "B" else None)
    finally:
        ED._clean_1m = orig
    return lit.run_x(M, C, PP, F.SESS, B1=B1, B5=F.bars(M, "5m"))


def key(t):
    return t and (int(t["entry_t"]), int(t["dir"]), int(t["qty"]), t["exit"], round(float(t["pnl"]), 2))


def main():
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    out = {"label": "RESEARCH (night W1 2026-11-16): LIT with a live-matching 1m cleaner", "variants": {}, "changed": {}}
    TT = {}
    for v in ("today", "A", "B"):
        t0 = time.time()
        TT[v] = trades(P, v)
        out["variants"][v] = F.score(TT[v])
        print(v, f"{time.time() - t0:.0f}s", json.dumps(out["variants"][v]), flush=True)
    kb = {t["day"]: t for t in TT["today"]}
    for v in ("A", "B"):
        kv = {t["day"]: t for t in TT[v]}
        out["changed"][v] = [{"day": d, "today": key(kb.get(d)), v: key(kv.get(d))}
                             for d in sorted(set(kb) | set(kv)) if key(kb.get(d)) != key(kv.get(d))]
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    for v, ch in out["changed"].items():
        print(v, "changed:", *ch, sep="\n  ")


if __name__ == "__main__":
    main()
