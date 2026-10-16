"""Bar loading, ET session tagging and resampling."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


@dataclass
class Bars:
    sym: str
    tf: str
    t: np.ndarray       # bar open time, unix seconds UTC
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    mod: np.ndarray = field(default=None)    # ET minute of day (bar open)
    tday: np.ndarray = field(default=None)   # trading-day ordinal (18:00 ET -> 17:00 ET)
    dow: np.ndarray = field(default=None)    # weekday of trading day 0=Mon
    date_str: list = field(default=None)     # trading day yyyy-mm-dd

    def __len__(self):
        return len(self.t)

    @property
    def secs(self):
        return TF_SECONDS[self.tf]

    def slice(self, a: int, b: int) -> "Bars":
        return Bars(self.sym, self.tf, self.t[a:b], self.o[a:b], self.h[a:b], self.l[a:b], self.c[a:b], self.v[a:b],
                    self.mod[a:b], self.tday[a:b], self.dow[a:b], self.date_str[a:b])

    def to_records(self, a: int = 0, b: int | None = None):
        b = len(self) if b is None else b
        return [{"time": int(self.t[i]), "open": float(self.o[i]), "high": float(self.h[i]), "low": float(self.l[i]),
                 "close": float(self.c[i]), "volume": float(self.v[i])} for i in range(a, b)]


def _tag(df: pd.DataFrame) -> tuple:
    ts = pd.to_datetime(df["time"].values, unit="s", utc=True).tz_convert("America/New_York")
    mod = (ts.hour * 60 + ts.minute).values.astype(np.int32)
    shifted = ts + pd.Timedelta(hours=6)  # 18:00 ET -> next calendar day
    tdate = shifted.normalize()
    tday = (tdate.tz_localize(None).values.astype("datetime64[D]").astype(np.int64)).astype(np.int64)
    dow = tdate.dayofweek.values.astype(np.int32)
    date_str = [d.strftime("%Y-%m-%d") for d in tdate]
    return mod, tday, dow, date_str


def from_frame(sym: str, tf: str, df: pd.DataFrame) -> Bars:
    df = df.sort_values("time").drop_duplicates("time")
    mod, tday, dow, date_str = _tag(df)
    return Bars(sym, tf, df["time"].values.astype(np.int64), df["open"].values.astype(float),
                df["high"].values.astype(float), df["low"].values.astype(float), df["close"].values.astype(float),
                df["volume"].values.astype(float), mod, tday, dow, date_str)


_cache: dict = {}


def load(sym: str, tf: str) -> Bars:
    path = os.path.join(DATA_DIR, f"{sym}_{tf}.csv")
    mtime = os.path.getmtime(path)
    key = (sym, tf)
    if key in _cache and _cache[key][0] == mtime:
        return _cache[key][1]
    df = pd.read_csv(path)
    # drop weekend/maintenance junk bars with no range and no volume
    df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
    bars = from_frame(sym, tf, df)
    _cache[key] = (mtime, bars)
    return bars


def resample(b: Bars, tf: str) -> Bars:
    """Resample to a higher timeframe aligned to UTC epoch buckets (4h aligned to 18:00 ET session start)."""
    secs = TF_SECONDS[tf]
    if tf == "1d":
        bucket = b.tday.astype(np.int64)
    else:
        offset = 0
        if tf == "4h":
            offset = 22 * 3600  # 18:00 ET (EDT) = 22:00 UTC
        bucket = (b.t - offset) // secs * secs + offset
    df = pd.DataFrame({"bucket": bucket, "t": b.t, "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v})
    g = df.groupby("bucket", sort=True)
    out = pd.DataFrame({
        "time": g["t"].first() if tf == "1d" else g["bucket"].first(),
        "open": g["o"].first(), "high": g["h"].max(), "low": g["l"].min(), "close": g["c"].last(), "volume": g["v"].sum(),
    }).reset_index(drop=True)
    return from_frame(b.sym, tf, out)


LTF_DIR = os.path.join(DATA_DIR, "ltf")
# verified true-1m exports kept apart from <sym>_*.csv (data/ltf/NQJ_1m.csv = TradingView CME_MINI_NQ1! 1-minute exports)
LTF_EXTRA = {"NQ": ["NQJ"]}


def _clean_1m(df: pd.DataFrame, base: Bars | None = None) -> pd.DataFrame:
    """Keep only complete, genuine 1-minute 5-minute windows: five rows at 60 s spacing whose first row is not a 5m bar that
    a 5m import wrote into the 1m file. Such a row carries the 5m bar's exact high / low / close (checked against `base`
    when given) or covers the whole window with more volume than the other four minutes together."""
    df = df.sort_values("time").drop_duplicates("time", keep="last")
    df = df[df["time"] % 60 == 0].copy()
    df["bucket"] = df["time"] // 300 * 300
    df = df[df.groupby("bucket")["time"].transform("size") == 5]
    if df.empty:
        return df
    g = df.groupby("bucket")
    first = g.head(1).set_index("bucket")
    rest = df[df["time"] % 300 != 0].groupby("bucket").agg(h=("high", "max"), l=("low", "min"), v=("volume", "sum"))
    j = first.join(rest)
    bad = (j["high"] >= j["h"]) & (j["low"] <= j["l"]) & (j["volume"] > j["v"])
    if base is not None:
        bb = pd.DataFrame({"h5": base.h, "l5": base.l, "c5": base.c}, index=base.t)
        jb = j.join(bb, how="left")
        bad |= (jb["high"] == jb["h5"]) & (jb["low"] == jb["l5"]) & (jb["close"] == jb["c5"])
    return df[~df["bucket"].isin(j.index[bad.values])]


def load_ltf(sym: str, base: Bars | None = None):
    """True 1-minute bars for the hybrid trigger (ifvg_tf 'lower'): data/<sym>_1m.csv plus any verified exports in
    data/ltf (LTF_EXTRA; later sources win per 5-minute window), each cleaned by _clean_1m. Returns (Bars | None, info)."""
    srcs = [(f"{sym}_1m.csv", os.path.join(DATA_DIR, f"{sym}_1m.csv"))]
    srcs += [(f"ltf/{x}_1m.csv", os.path.join(LTF_DIR, f"{x}_1m.csv")) for x in LTF_EXTRA.get(sym, [])]
    info, parts = {}, []
    for name, path in srcs:
        if not os.path.exists(path):
            continue
        raw = pd.read_csv(path)
        raw.columns = [c.strip().lower() for c in raw.columns]
        raw = raw[["time", "open", "high", "low", "close", "volume"]]
        clean = _clean_1m(raw, base)
        info[name] = {"rows": int(len(raw)), "true_1m_rows": int(len(clean)), "windows": int(clean["bucket"].nunique()) if len(clean) else 0}
        parts.append(clean)
    if not parts:
        return None, info
    out = parts[0]
    for nxt in parts[1:]:
        out = pd.concat([out[~out["bucket"].isin(set(nxt["bucket"]))], nxt])
    if out.empty:
        return None, info
    return from_frame(sym, "1m", out.drop(columns="bucket")), info


def available():
    out = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith(".csv") and "_" in f:
            s, tf = f[:-4].split("_", 1)
            out.setdefault(s, []).append(tf)
    order = list(TF_SECONDS)
    return {s: sorted(v, key=lambda x: order.index(x) if x in order else 99) for s, v in out.items()}
