"""A1 audit (2026-10-25) RESEARCH_VARIANT: how much of the 2026 LIT backtest rests on 1m windows that engine/data._clean_1m
drops with its volume heuristic ("the first row covers the whole window with more volume than the other four minutes" =
taken for a 5m bar written into the 1m file) although the five rows are genuine and rebuild the 5m bar exactly.

The live PC bot never applies that heuristic (engine/lit_live.feed_1m keeps every minute), so on such a window the backtest
and the live loop see different 1m bars (tests/test_prefix_invariance.py --raw1m: 2026-03-23, 2026-05-05).

    python -X utf8 research/handoff/2026-10-25/a1_clean1m_variant.py
Read-only: no engine file or run is changed. Writes a1_clean1m_variant.json / a1_clean1m_dropped_windows.csv here.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from engine import data as ED  # noqa: E402
from engine import lit  # noqa: E402


def dropped_windows():
    base = ED.load("NQ", "5m")
    raw = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    clean = ED._clean_1m(raw, base)
    df = raw.sort_values("time").drop_duplicates("time", keep="last")
    df = df[df["time"] % 60 == 0].copy()
    df["bucket"] = df["time"] // 300 * 300
    full = df[df.groupby("bucket")["time"].transform("size") == 5]
    gone = sorted(set(full["bucket"]) - set(clean["bucket"]))
    b5 = pd.DataFrame({"o": base.o, "h": base.h, "l": base.l, "c": base.c}, index=base.t)
    rows = []
    for b in gone:
        g = full[full["bucket"] == b]
        r5 = b5.loc[b] if b in b5.index else None
        rebuild = r5 is not None and g["open"].iloc[0] == r5["o"] and g["high"].max() == r5["h"] and g["low"].min() == r5["l"] \
            and g["close"].iloc[-1] == r5["c"]
        first_is_5m = r5 is not None and g["high"].iloc[0] == r5["h"] and g["low"].iloc[0] == r5["l"] and g["close"].iloc[0] == r5["c"]
        rows.append({"bucket": int(b), "et": str(pd.Timestamp(b, unit="s", tz="UTC").tz_convert("America/New_York")),
                     "rebuilds_5m_exactly": bool(rebuild), "first_row_equals_5m_bar": bool(first_is_5m),
                     "vol_first": float(g["volume"].iloc[0]), "vol_rest": float(g["volume"].iloc[1:].sum())})
    return pd.DataFrame(rows)


def clean_variant(df, base=None):
    """_clean_1m without the volume heuristic: only the base check (first row = the 5m bar's exact high/low/close)."""
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


def stats(T, a, b):
    T = [t for t in T if a <= t["day"] <= b]
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(0)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(p) else 0.0
    return {"n": len(T), "net": round(float(p.sum()), 2), "pf": round(float(gw / gl), 2) if gl else None, "dd": round(dd, 2)}


def main():
    W = dropped_windows()
    W.to_csv(os.path.join(HERE, "a1_clean1m_dropped_windows.csv"), index=False)
    W26 = W[W["et"] >= "2026-01-01"]
    print(f"windows with 5 genuine-looking rows dropped by _clean_1m: {len(W)} (2026: {len(W26)}); rebuild the 5m bar exactly: "
          f"{int(W['rebuilds_5m_exactly'].sum())}; first row = the 5m bar (a real import artifact): {int(W['first_row_equals_5m_bar'].sum())}")
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    PP = {**lit.DEFAULTS, **P}
    M, C = F.market(PP["ref"], PP["extra_boxes"])
    base_T = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    orig = ED._clean_1m
    ED._clean_1m = clean_variant
    try:
        B1v = lit.bars_1m(M)
    finally:
        ED._clean_1m = orig
    var_T = [t for t in lit.run_x(M, C, PP, F.SESS, B1=B1v, B5=F.bars(M, "5m")) if t["day"] >= "2026-01-01"]
    kb = {t["day"]: t for t in base_T}
    kv = {t["day"]: t for t in var_T}
    changed = []
    for d in sorted(set(kb) | set(kv)):
        a, b = kb.get(d), kv.get(d)
        ka = a and (a["entry_t"], a["dir"], a["qty"], a["exit"], round(a["pnl"], 2))
        kvv = b and (b["entry_t"], b["dir"], b["qty"], b["exit"], round(b["pnl"], 2))
        if ka != kvv:
            changed.append({"day": d, "baseline": ka, "variant": kvv})
    out = {"label": "RESEARCH_VARIANT (not adopted): 1m cleaning without the volume heuristic",
           "dropped_windows_total": len(W), "dropped_windows_2026": len(W26),
           "dropped_rebuild_5m_exactly": int(W["rebuilds_5m_exactly"].sum()),
           "dropped_first_row_equals_5m": int(W["first_row_equals_5m_bar"].sum()),
           "baseline": {p: stats(base_T, a, b) for p, a, b in (("2026", "2026-01-01", "2026-10-16"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"))},
           "variant": {p: stats(var_T, a, b) for p, a, b in (("2026", "2026-01-01", "2026-10-16"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"))},
           "trades_changed": changed}
    json.dump(out, open(os.path.join(HERE, "a1_clean1m_variant.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != "trades_changed"}, indent=1))
    for c in changed:
        print(c)


if __name__ == "__main__":
    main()
