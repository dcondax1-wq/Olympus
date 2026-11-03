"""The bar store of the data city: CME NQ1! 5m (data/NQ_5m.csv, TradingView export, back-adjusted to the newest contract)
plus the PC's NinjaTrader MNQ 5m bars appended after it (the `heartbeat` branch bars_5m.csv.gz, the cloud's
pc_bars_5m.csv on the `dashboard` branch), kept in research/datacity/bars_extra.csv.gz. Never Yahoo.

The extra store holds only bars newer than the TradingView file; at a contract roll engine.pcbars.merge_basis shifts the
older bars onto the new basis (every outcome here is a price difference, so a constant shift changes nothing).
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine import pcbars  # noqa: E402

NQ_5M = os.path.join(ROOT, "data", "NQ_5m.csv")
ES_5M = os.path.join(ROOT, "data", "ES_5m.csv")
OUT = os.path.join(ROOT, "research", "datacity")
EXTRA = os.path.join(OUT, "bars_extra.csv.gz")


def read_csv(path) -> pd.DataFrame:
    if not os.path.exists(path):
        return pcbars._empty()
    return pcbars.tidy(pd.read_csv(path))


def read_extra(path=EXTRA) -> pd.DataFrame:
    if not os.path.exists(path):
        return pcbars._empty()
    with open(path, "rb") as fh:
        return pcbars.decode(fh.read())


def _git_show(ref_path):
    try:
        p = subprocess.run(["git", "-C", ROOT, "show", ref_path], capture_output=True, timeout=120)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def fetch_pc_bars(fetch=True) -> pd.DataFrame:
    """The PC's NinjaTrader 5m bars: heartbeat bars_5m.csv.gz (last ~40 days) + the cloud store pc_bars_5m.csv (75 days)."""
    frames = []
    for branch, name in (("heartbeat", pcbars.BARS_5M), ("dashboard", pcbars.STORE_5M)):
        if fetch:
            subprocess.run(["git", "-C", ROOT, "fetch", "-q", "--depth", "1", "origin", branch], capture_output=True, timeout=180)
        blob = _git_show(f"FETCH_HEAD:{name}") if fetch else _git_show(f"origin/{branch}:{name}")
        if blob:
            frames.append(pcbars.decode(blob))
    out = pcbars._empty()
    for f in frames:
        out, _ = pcbars.merge_basis(out, f)
    return out


def append_extra(new: pd.DataFrame, base_last: int, path=EXTRA) -> dict:
    """Append bars newer than the TradingView file's last bar to the extra store. Returns {added, shift, last}."""
    old = read_extra(path)
    new = pcbars.tidy(new)
    new = new[new["time"] > base_last]
    if not len(new):
        return {"added": 0, "shift": 0.0, "last": int(old["time"].max()) if len(old) else base_last}
    merged, sh = pcbars.merge_basis(old, new)
    merged = merged[merged["time"] > base_last]
    added = len(merged) - len(old)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(pcbars.encode(merged))
    return {"added": int(added), "shift": float(sh), "last": int(merged["time"].max())}


def load_nq(extra=True, path=NQ_5M, extra_path=EXTRA) -> pd.DataFrame:
    """The full NQ 5m history: the TradingView file + the extra store (bars after the file only)."""
    df = read_csv(path)
    if extra:
        ex = read_extra(extra_path)
        if len(ex) and len(df):
            ex = ex[ex["time"] > int(df["time"].max())]
            if len(ex):
                df, _ = pcbars.merge_basis(df, ex)
    return df


def load_es() -> pd.DataFrame:
    return read_csv(ES_5M)


def load_daily(name) -> pd.DataFrame:
    """VIX_1d / VXN_1d (CBOE's own file): date, close."""
    p = os.path.join(ROOT, "data", f"{name}_1d.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["date", "close"])
    d = pd.read_csv(p)[["date", "close"]].dropna()
    return d.sort_values("date").reset_index(drop=True)


def load_cboe(col) -> pd.DataFrame:
    """One column of CBOE's own index file (data/CBOE_vol_1d.csv: vix9d, vix3m, vix1d, vvix, skew) as date, close."""
    p = os.path.join(ROOT, "data", "CBOE_vol_1d.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["date", "close"])
    d = pd.read_csv(p)
    if col not in d.columns:
        return pd.DataFrame(columns=["date", "close"])
    d = d[["date", col]].rename(columns={col: "close"}).dropna()
    return d.sort_values("date").reset_index(drop=True)


def load_news() -> pd.DataFrame:
    """High-impact scheduled US releases (data/news/events.csv: FOMC, CPI, PPI, NFP ...). Scheduled in advance: no look-ahead."""
    p = os.path.join(ROOT, "data", "news", "events.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["date", "time_et", "event"])
    d = pd.read_csv(p)
    if "impact" in d.columns:
        d = d[d["impact"].astype(str).str.lower() == "high"]
    return d[["date", "time_et", "event"]].reset_index(drop=True)


def fingerprint(df: pd.DataFrame, upto: int | None = None) -> str:
    """Shift-invariant hash of the bars (time, range, body, close-to-close): a roll re-basing keeps it."""
    import hashlib
    d = df if upto is None else df[df["time"] <= upto]
    a = np.round(np.c_[d["time"].to_numpy(dtype=float), (d["high"] - d["low"]).to_numpy(), (d["close"] - d["open"]).to_numpy(),
                       np.r_[0.0, np.diff(d["close"].to_numpy())]] * 4).astype(np.int64)
    return hashlib.sha1(a.tobytes()).hexdigest()[:16]
