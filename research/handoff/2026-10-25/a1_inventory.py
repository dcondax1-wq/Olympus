"""A1 pre-launch audit (2026-10-25): dataset inventory for LIT / ATLAS. Read-only; writes CSVs next to this file.

    python -X utf8 research/handoff/2026-10-25/a1_inventory.py

Outputs (this folder):
  a1_inventory.csv         one row per data file: symbol, tf, rows, first/last bar (ET), sha1, duplicates, out-of-order,
                           off-grid stamps, bars stamped in the 17:00-18:00 ET halt, flat no-volume bars (load() drops them)
  a1_gaps_by_session.csv   per bar file (NQ/ES/MNQ 5m, NQ 1m) and trading day: bars present, internal missing slots per
                           session part (asia 18-02, london 02-08, pre 08-09:30, rth 09:30-16, post 16-17), last bar time
  a1_gap_summary.csv       the same summed per file and year
"""
from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DATA = os.path.join(ROOT, "data")

FILES = [  # (path rel to data/, symbol / source, tf seconds or None for daily)
    ("NQ_5m.csv", "TV CME NQ1! (back-adjusted to NQZ26, repo roll method)", 300),
    ("NQ_1m.csv", "TV CME NQ1! 1m (2026)", 60),
    ("NQ_15m.csv", "NQ1! 15m (built from 5m)", 900),
    ("NQ_1h.csv", "NQ1! 1h (built from 5m)", 3600),
    ("NQ_1d.csv", "NQ1! 1d", None),
    ("ES_5m.csv", "TV CME ES1! 5m", 300),
    ("tv_mnq_5m_2026-10-16.csv", "TV CME MNQ1! 5m ETH back-adjusted (TV)", 300),
    ("ltf/NQJ_1m.csv", "TV CME_MINI NQ1! 1m (verified extra, data/ltf)", 60),
    ("ltf/NQJ_5m.csv", "TV CME_MINI NQ1! 5m (data/ltf)", 300),
    ("clean/raw/NQ_5m_unadjusted.csv", "NQ 5m unadjusted, per contract", 300),
    ("VIX_1d.csv", "CBOE VIX daily", "d"),
    ("VXN_1d.csv", "CBOE VXN daily", "d"),
    ("CBOE_vol_1d.csv", "CBOE VIX9D/VIX3M/VIX1D/VVIX/SKEW daily", "d"),
]
PARTS = (("asia", 1080, 120), ("london", 120, 480), ("pre", 480, 570), ("rth", 570, 960), ("post", 960, 1020))


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def part_of(m):
    for nm, a, z in PARTS:
        if (m - a) % 1440 < (z - a) % 1440:
            return nm
    return "halt"


def main():
    inv, gaps = [], []
    for rel, sym, tf in FILES:
        p = os.path.join(DATA, rel)
        if not os.path.exists(p):
            inv.append({"file": rel, "symbol": sym, "exists": False})
            continue
        df = pd.read_csv(p)
        df.columns = [c.strip().lower() for c in df.columns]
        row = {"file": rel, "symbol": sym, "exists": True, "bytes": os.path.getsize(p), "sha1": sha1(p), "rows": len(df)}
        if tf == "d":
            ds = df["date"].astype(str)
            row.update(first=ds.iloc[0], last=ds.iloc[-1], duplicates=int(ds.duplicated().sum()),
                       out_of_order=int((ds.values[1:] < ds.values[:-1]).sum()),
                       nan_close=int(df.iloc[:, 1:].isna().all(axis=1).sum()) if rel == "CBOE_vol_1d.csv" else int(df["close"].isna().sum()))
            if "close" in df:
                d = pd.to_datetime(ds)
                bd = pd.bdate_range(d.iloc[0], d.iloc[-1])
                row["missing_weekdays"] = int(len(set(bd) - set(d)))
                row["missing_weekdays_2026"] = int(len({x for x in set(bd) - set(d) if x.year == 2026}))
            inv.append(row)
            continue
        t = df["time"].astype("int64").values
        et = pd.to_datetime(t, unit="s", utc=True).tz_convert("America/New_York")
        mod = (et.hour * 60 + et.minute).values
        row.update(first=str(et[0]), last=str(et[-1]), duplicates=int(pd.Series(t).duplicated().sum()),
                   out_of_order=int((np.diff(t) < 0).sum()))
        if tf is not None:
            row["off_grid"] = int((t % tf != 0).sum())
            wd = et.dayofweek.values
            row["halt_17_18"] = int(((mod >= 1020) & (mod < 1080) & (wd < 5)).sum())
            vcol = "volume" if "volume" in df else None
            if vcol:
                row["flat_no_volume"] = int(((df["high"] == df["low"]) & (df[vcol] <= 0)).sum())
            row["ohlc_bad"] = int(((df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))).sum())
        inv.append(row)
        if tf in (60, 300) and rel in ("NQ_5m.csv", "NQ_1m.csv", "ES_5m.csv", "tv_mnq_5m_2026-10-16.csv", "ltf/NQJ_1m.csv"):
            tdate = (et + pd.Timedelta(hours=6)).strftime("%Y-%m-%d").values
            s = pd.DataFrame({"t": t, "day": tdate, "mod": mod}).drop_duplicates("t").sort_values("t")
            for day, g in s.groupby("day", sort=True):
                tt = g["t"].values
                full = np.arange(tt[0], tt[-1] + 1, tf)
                miss = np.setdiff1d(full, tt)
                mm = pd.to_datetime(miss, unit="s", utc=True).tz_convert("America/New_York")
                mmod = (mm.hour * 60 + mm.minute).values
                r = {"file": rel, "day": day, "bars": len(tt), "first_et": str(pd.Timestamp(tt[0], unit="s", tz="UTC").tz_convert("America/New_York").strftime("%H:%M")),
                     "last_et": str(pd.Timestamp(tt[-1], unit="s", tz="UTC").tz_convert("America/New_York").strftime("%m-%d %H:%M")),
                     "missing_total": 0}
                for nm, a, z in PARTS:
                    r["miss_" + nm] = 0
                for m in mmod:
                    pn = part_of(int(m))
                    if pn == "halt":
                        continue
                    r["miss_" + pn] += 1
                    r["missing_total"] += 1
                gaps.append(r)
    inv = pd.DataFrame(inv)
    inv.to_csv(os.path.join(HERE, "a1_inventory.csv"), index=False)
    G = pd.DataFrame(gaps)
    G.to_csv(os.path.join(HERE, "a1_gaps_by_session.csv"), index=False)
    G["year"] = G["day"].str[:4]
    cols = ["bars", "missing_total"] + ["miss_" + p[0] for p in PARTS]
    S = G.groupby(["file", "year"])[cols].sum()
    S["days"] = G.groupby(["file", "year"]).size()
    S["days_with_gap"] = G[G["missing_total"] > 0].groupby(["file", "year"]).size()
    S = S.fillna(0).astype(int).reset_index()
    S.to_csv(os.path.join(HERE, "a1_gap_summary.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(inv.drop(columns=["sha1"]).to_string())
    print(S.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
