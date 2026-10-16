"""Futures data audit + clean-set builder for NQ / ES (see research/DATA_AUDIT.md).

  python tools/data_audit.py fetch-refs            # Yahoo single-contract 1h refs (NQZ26/ESZ26) + fresh NQ=F 1m -> data/clean/_src
  python tools/data_audit.py build-es              # data/clean/ES_{1m,5m,15m,1h}.csv (Yahoo ES=F, Sep-2026 roll fixed)
  python tools/data_audit.py build-1m              # data/clean/NQ_1m.csv (true 1-minute rows only)
  python tools/data_audit.py audit [dir] [out.csv] # per-day quality table for NQ/ES 5m/15m/1h/1m in a data dir
  python tools/data_audit.py compare               # Yahoo NQ=F vs TradingView bar-by-bar comparison (overlap window)
  python tools/data_audit.py backtest <dirA> <dirB> [days_from] [days_to]   # engine.backtest.run on two dirs, trade diff

NQ 5m/15m/1h are built by tools/stitch_tv_chunks.py (TradingView NQ1! chunks), which calls into this module.
Nothing here writes to data/NQ_*.csv or data/ES_*.csv: output goes to data/clean/ only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from functools import lru_cache

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CLEAN = os.path.join(DATA, "clean")
SRC = os.path.join(CLEAN, "_src")
TZ = "America/New_York"
TF_SECS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}
COLS = ["time", "open", "high", "low", "close", "volume"]


# ----------------------------------------------------------------------------------------------- basic io / tagging
def read_bars(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = np.nan
    df = df[COLS].dropna(subset=["time", "open", "high", "low", "close"]).copy()
    df["time"] = df["time"].astype("int64")
    return df.sort_values("time").reset_index(drop=True)


def et_of(t) -> pd.DatetimeIndex:
    return pd.to_datetime(np.asarray(t, dtype="int64"), unit="s", utc=True).tz_convert(TZ)


def tday_of(t) -> np.ndarray:
    """CME trading day (18:00 ET -> next calendar day), same convention as engine.data._tag."""
    return np.array((et_of(t) + pd.Timedelta(hours=6)).strftime("%Y-%m-%d"))


def resample(df: pd.DataFrame, secs: int, extra: list | None = None) -> pd.DataFrame:
    g = df.assign(b=df["time"] // secs * secs).groupby("b", sort=True)
    out = pd.DataFrame({"time": g["b"].first(), "open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
    for c in extra or []:
        out[c] = g[c].first()
    return out.reset_index(drop=True)


def write_csv(df: pd.DataFrame, path: str, cols=COLS):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = df[cols].copy()
    out["time"] = out["time"].astype("int64")
    tmp = path + ".tmp"
    out.to_csv(tmp, index=False)
    os.replace(tmp, path)


def sanitize(df: pd.DataFrame, secs: int, label: str = "") -> pd.DataFrame:
    """Drop rows that cannot be real Globex bars: duplicates, off-grid stamps, bars inside the 17:00-18:00 ET break or
    the weekend, impossible OHLC, and flat no-volume placeholder bars (Yahoo session-open / settlement rows)."""
    n0 = len(df)
    df = df.drop_duplicates("time", keep="last")
    t = df["time"].values
    et = et_of(t)
    mod = et.hour * 60 + et.minute
    wd = et.weekday
    in_break = (mod >= 17 * 60) & (mod < 18 * 60)
    weekend = (wd == 5) | ((wd == 6) & (mod < 18 * 60)) | ((wd == 4) & (mod >= 17 * 60))
    bad = (df["high"].values < np.maximum(df["open"].values, df["close"].values) - 1e-9) | \
          (df["low"].values > np.minimum(df["open"].values, df["close"].values) + 1e-9)
    flat = (df["high"].values == df["low"].values) & (np.nan_to_num(df["volume"].values, nan=0) <= 0)
    # expiry-day 16:00 single-price "settlement" rows Yahoo appends to 1h bars (zero range, huge volume)
    settle = (df["high"].values == df["low"].values) & (mod == 16 * 60) & (secs >= 3600)
    drop = ((t % secs) != 0) | in_break | weekend | bad | flat | settle
    out = df[~drop].copy()
    if label:
        print(f"  sanitize {label}: dropped {n0 - len(out)} of {n0} rows "
              f"(dup {n0 - len(df)}, off-grid {int(((t % secs) != 0).sum())}, break {int(in_break.sum())}, "
              f"weekend {int(weekend.sum())}, bad-ohlc {int(bad.sum())}, flat-no-vol {int(flat.sum())}, settle {int(settle.sum())})")
    return out


# ----------------------------------------------------------------------------------------------- CME calendar
def third_friday(y: int, m: int) -> dt.date:
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def _easter(y: int) -> dt.date:
    from dateutil.easter import easter
    return easter(y)


@lru_cache(maxsize=None)
def us_holidays(y: int) -> dict:
    """NYSE/CME-relevant US holidays -> name (observed dates). CME equity futures usually run a shortened session."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    cal = USFederalHolidayCalendar()
    out = {}
    keys = [("martin luther", "MLK"), ("washington", "Presidents"), ("presidents", "Presidents"), ("memorial", "Memorial"),
            ("juneteenth", "Juneteenth"), ("independence", "July4"), ("labor", "Labor"), ("thanksgiving", "Thanksgiving"),
            ("christmas", "Christmas"), ("new year", "NewYear")]
    for d, n in cal.holidays(dt.date(y, 1, 1), dt.date(y, 12, 31), return_name=True).items():
        for k, v in keys:
            if k in n.lower():
                out[d.date()] = v
                break
    j3 = dt.date(y, 7, 3)
    if j3.weekday() < 5 and out.get(j3) is None:
        out[j3] = "July3(early)"
    if y == 2025:
        out[dt.date(2025, 1, 9)] = "Carter-mourning(NYSE closed)"
    out[_easter(y) - dt.timedelta(days=2)] = "GoodFriday"
    tg = [d for d, n in out.items() if n == "Thanksgiving"]
    if tg:
        out[tg[0] + dt.timedelta(days=1)] = "BlackFriday(early)"
    out[dt.date(y, 12, 24)] = "XmasEve(early)"
    return out


def holiday_name(day: str) -> str | None:
    d = dt.date.fromisoformat(day)
    return us_holidays(d.year).get(d)


def last_trading_day(y: int, m: int) -> dt.date:
    """Equity index futures LTD: 3rd Friday, or the business day before when the exchange is closed (Juneteenth 2026)."""
    d = third_friday(y, m)
    while us_holidays(d.year).get(d) in ("Juneteenth", "GoodFriday", "July4", "Christmas", "NewYear") or d.weekday() > 4:
        d -= dt.timedelta(days=1)
    return d


def contract_code(sym: str, y: int, m: int) -> str:
    return f"{sym}{MONTH_CODE[m]}{y % 100:02d}"


def quarterly_expiries(start: dt.date, end: dt.date):
    out = []
    for y in range(start.year, end.year + 2):
        for m in (3, 6, 9, 12):
            e = last_trading_day(y, m)
            if start - dt.timedelta(days=100) <= e <= end + dt.timedelta(days=100):
                out.append((y, m, e))
    return out


# ----------------------------------------------------------------------------------------------- per-day quality audit
def session_bounds(day: str):
    """Expected Globex session for trading day `day`: [prev calendar day 18:00 ET, day 17:00 ET). Sunday open for Mon."""
    d = dt.date.fromisoformat(day)
    prev = d - dt.timedelta(days=1)
    start = pd.Timestamp(prev.year, prev.month, prev.day, 18).tz_localize(TZ)   # wall-clock 18:00 (DST-safe)
    end = pd.Timestamp(d.year, d.month, d.day, 17).tz_localize(TZ)
    return start, end


def audit_frame(df: pd.DataFrame, secs: int, label: str, extra_cols=("source", "contract")) -> pd.DataFrame:
    """One row per trading day with gap / duplicate / grid / session / volume / spike checks."""
    if df.empty:
        return pd.DataFrame()
    t = df["time"].values
    et = et_of(t)
    td = tday_of(t)
    dup_mask = pd.Series(t).duplicated().values
    offgrid = (t % secs) != 0
    mod = et.hour * 60 + et.minute
    wd = et.weekday
    in_break = (mod >= 17 * 60) & (mod < 18 * 60) if secs < 3600 else (mod == 17 * 60)
    weekend = (wd == 5) | ((wd == 6) & (mod < 18 * 60)) | ((wd == 4) & (mod >= 17 * 60))
    rng = (df["high"] - df["low"]).values
    bad_ohlc = (df["high"].values < np.maximum(df["open"].values, df["close"].values) - 1e-9) | \
               (df["low"].values > np.minimum(df["open"].values, df["close"].values) + 1e-9)
    vol = df["volume"].values
    zero_vol = np.nan_to_num(vol, nan=-1) == 0
    junk = (rng == 0) & (np.nan_to_num(vol, nan=0) <= 0)
    rows = []
    frame = pd.DataFrame({"t": t, "td": td, "dup": dup_mask, "off": offgrid, "brk": in_break, "wkd": weekend,
                          "rng": rng, "bad": bad_ohlc, "zv": zero_vol, "junk": junk, "c": df["close"].values,
                          "o": df["open"].values})
    for c in extra_cols:
        if c in df.columns:
            frame[c] = df[c].values
    for day, g in frame.groupby("td", sort=True):
        start, end = session_bounds(day)
        s0, s1 = int(start.timestamp()), int(end.timestamp())
        hol = holiday_name(day)
        tt = np.unique(g["t"].values[~g["off"].values])
        grid = np.arange(s0, s1, secs)
        present = np.isin(grid, tt)
        first_i = int(np.argmax(present)) if present.any() else 0
        last_i = len(grid) - 1 - int(np.argmax(present[::-1])) if present.any() else -1
        inside_missing = int((~present[first_i:last_i + 1]).sum()) if present.any() else 0
        late_open = first_i  # bars missing at the session start
        early_close = len(grid) - 1 - last_i if present.any() else len(grid)
        # outlier bars: range > 8x the day's median range and > 0.5% of price (mixed-contract / bad prints)
        med = np.median(g["rng"].values) if len(g) else 0
        spikes = int(((g["rng"].values > 8 * max(med, 1e-9)) & (g["rng"].values > 0.005 * g["c"].values)).sum())
        # intra-session jumps (open vs prior close within the session) > 0.5%
        cc = g["c"].values
        jumps = int((np.abs(g["o"].values[1:] - cc[:-1]) > 0.005 * cc[:-1]).sum()) if len(g) > 1 else 0
        row = {"day": day, "file": label, "bars": int(len(g)), "expected": int(len(grid)),
               "first_et": et_of([g["t"].min()])[0].strftime("%a %H:%M"), "last_et": et_of([g["t"].max()])[0].strftime("%a %H:%M"),
               "missing_inside": inside_missing, "missing_at_open": late_open, "missing_at_close": early_close,
               "dups": int(g["dup"].sum()), "off_grid": int(g["off"].sum()), "in_break": int(g["brk"].sum()),
               "weekend": int(g["wkd"].sum()), "zero_vol": int(g["zv"].sum()), "junk_flat": int(g["junk"].sum()),
               "bad_ohlc": int(g["bad"].sum()), "spikes": spikes, "jumps": jumps, "holiday": hol or ""}
        for c in extra_cols:
            if c in g.columns:
                row[c] = "/".join(sorted(set(map(str, g[c].values))))
        problems = []
        if row["dups"] or row["off_grid"] or row["bad_ohlc"]:
            problems.append("BAD")
        if row["in_break"] or row["weekend"]:
            problems.append("off-session")
        if inside_missing > max(2, 0.02 * len(grid)):
            problems.append("gaps")
        if late_open and not hol:
            problems.append("late-open")
        if early_close > 1 and not hol and not dt.date.fromisoformat(day) >= dt.date.today():
            problems.append("early-close")
        if jumps:   # a >0.5% open-vs-prior-close gap inside a running session = contract switch / bad print
            problems.append("jump")
        # `spikes` (bar range > 8x the day's median and > 0.5%) is informational: news bars (CPI, FOMC) trip it too
        row["status"] = "OK" if not problems else ",".join(problems)
        rows.append(row)
    return pd.DataFrame(rows)


def audit_dir(d: str, out_csv: str | None = None, files=None) -> pd.DataFrame:
    files = files or [f"{s}_{tf}.csv" for s in ("NQ", "ES") for tf in ("1m", "5m", "15m", "1h")]
    parts = []
    for f in files:
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        tf = f.split("_")[1][:-4]
        df = pd.read_csv(p)
        df.columns = [c.strip().lower() for c in df.columns]
        parts.append(audit_frame(df, TF_SECS[tf], f[:-4]))
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if out_csv:
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        out.to_csv(out_csv, index=False)
    return out


# ----------------------------------------------------------------------------------------------- reference contracts
def fetch_refs():
    import time
    import yfinance as yf
    os.makedirs(SRC, exist_ok=True)

    def clean(df):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
        idx = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
        df = df.reset_index(drop=True)
        df.insert(0, "time", ((idx - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).astype("int64"))
        return df

    today = dt.date.today()
    for tkr in ("NQZ26.CME", "ESZ26.CME"):
        df = yf.download(tkr, start="2025-10-01", end=str(today + dt.timedelta(days=1)), interval="1h",
                         progress=False, auto_adjust=False)
        if df is not None and len(df):
            p = os.path.join(SRC, f"yahoo_{tkr.split('.')[0]}_1h.csv")
            clean(df).to_csv(p, index=False)
            print("wrote", p, len(df))
    frames = []
    end = dt.datetime.now(dt.timezone.utc)
    lim = end - dt.timedelta(days=29)
    while end > lim:
        start = max(lim, end - dt.timedelta(days=7))
        df = yf.download("NQ=F", start=start, end=end, interval="1m", progress=False, auto_adjust=False, prepost=True)
        if df is not None and len(df):
            frames.append(clean(df))
        end = start
        time.sleep(0.5)
    if frames:
        o = pd.concat(frames).drop_duplicates("time", keep="last").sort_values("time")
        p = os.path.join(SRC, f"yahoo_NQ_1m_{today:%Y%m%d}.csv")
        o.to_csv(p, index=False)
        print("wrote", p, len(o))


def ref_path(sym: str, code: str):
    p = os.path.join(SRC, f"yahoo_{code}_1h.csv")
    return p if os.path.exists(p) else None


def ref_gap(cont: pd.DataFrame, ref: pd.DataFrame, switch_t: int, sessions: int = 4, min_vol: float = 5):
    """Roll gap from a third/next contract quoted at the same hours: median(ref-cont) before minus after the switch.
    Returns (gap, uncertainty, n_before, n_after) or None. Thin hourly prints are filtered by volume."""
    h = resample(cont, 3600)
    r = ref[ref["volume"].fillna(0) >= min_vol]
    m = h.merge(r[["time", "close"]], on="time", suffixes=("", "_ref"))
    span = sessions * 86400 * 1.5
    pre = m[(m.time < switch_t) & (m.time >= switch_t - span)]
    post = m[(m.time >= switch_t) & (m.time < switch_t + span)]
    if len(pre) < 6 or len(post) < 6:
        return None
    dp, dq = pre.close_ref - pre.close, post.close_ref - post.close
    gap = float(dp.median() - dq.median())
    mad = float(np.hypot((dp - dp.median()).abs().median() / np.sqrt(len(dp)),
                         (dq - dq.median()).abs().median() / np.sqrt(len(dq))) * 1.4826)
    return gap, mad, int(len(pre)), int(len(post))


# ----------------------------------------------------------------------------------------------- ES clean build
def build_es():
    """ES has no TradingView export yet: Yahoo ES=F 5m (Aug 6 ->), with Yahoo's mid-session Sep-2026 contract switch
    detected and back-adjusted (additive, anchored to ESZ26) using the ESZ26 single-contract quotes."""
    es5 = sanitize(read_bars(os.path.join(DATA, "ES_5m.csv")), 300, "ES_5m").reset_index(drop=True)
    rp = ref_path("ES", "ESZ26")
    if not rp:
        sys.exit("run `python tools/data_audit.py fetch-refs` first (needs data/clean/_src/yahoo_ESZ26_1h.csv)")
    ref = read_bars(rp)
    # Yahoo switch bar: the 5m bar in the Sep-2026 roll week after which ES=F tracks ESZ26 (|ref-cont| small)
    e = last_trading_day(2026, 9)
    w0 = int(pd.Timestamp(e - dt.timedelta(days=10)).tz_localize(TZ).timestamp())
    w1 = int(pd.Timestamp(e + dt.timedelta(days=1)).tz_localize(TZ).timestamp())
    win = es5[(es5.time >= w0) & (es5.time < w1)].copy()
    win["hb"] = win.time // 3600 * 3600
    r = ref[ref.volume.fillna(0) >= 5][["time", "close"]].rename(columns={"time": "hb", "close": "ref"})
    win = win.merge(r, on="hb", how="left")
    win["d"] = (win["ref"] - win["close"]).abs()
    # switch = first bar from which the median |ref-cont| over the next 24 bars stays below 20 pts
    roll_d = win["d"].rolling(24, min_periods=6).median().shift(-23)
    cand = win[(roll_d < 20)]
    if cand.empty:
        raise RuntimeError("could not locate the ES=F Sep-2026 contract switch")
    switch_t = int(cand.time.iloc[0])
    # walk back to the single bar with the biggest close-open move (the mixed bar) within +-6 bars
    near = es5[(es5.time >= switch_t - 3 * 3600) & (es5.time <= switch_t + 3 * 3600)]
    switch_t = int(near.loc[(near.close - near.open).abs().idxmax(), "time"])
    rg = ref_gap(es5, ref, switch_t + 300)
    gap = round(rg[0] * 4) / 4 if rg else None
    print(f"ES=F switch bar {et_of([switch_t])[0]}  gap(ESZ26-ESU26)={gap}  ref={rg}")
    adj = es5.copy()
    pre = adj.time < switch_t
    for c in ("open", "high", "low", "close"):
        adj.loc[pre, c] += gap
    # the mixed bar: opened on ESU26, closed on ESZ26 -> shift its old-contract open/low into the new price space
    i = adj.index[adj.time == switch_t][0]
    adj.loc[i, "open"] += gap
    adj.loc[i, "low"] = min(adj.loc[i, "low"] + gap, adj.loc[i, "open"], adj.loc[i, "close"])
    adj["source"] = "yahoo-ES=F"
    adj["contract"] = np.where(adj.time < switch_t, "ESU26", "ESZ26")
    rolls = {"sym": "ES", "anchor": "ESZ26", "method": "additive back-adjustment; bars before switch_t get +gap",
             "rolls": [{"from": "ESU26", "to": "ESZ26", "switch_t": switch_t, "switch_et": str(et_of([switch_t])[0]),
                        "gap": gap, "method": "ESZ26 single-contract 1h quotes vs ES=F (median before - after)",
                        "uncertainty": round(rg[1], 2) if rg else None,
                        "note": "Yahoo switched mid-session; the switch bar itself is a mixed bar (open/low re-based)"}]}
    os.makedirs(CLEAN, exist_ok=True)
    json.dump(rolls, open(os.path.join(CLEAN, "ES_rolls.json"), "w"), indent=1)
    write_csv(adj, os.path.join(CLEAN, "ES_5m.csv"))
    write_csv(resample(adj, 900), os.path.join(CLEAN, "ES_15m.csv"))
    h_old = sanitize(read_bars(os.path.join(DATA, "ES_1h.csv")), 3600, "ES_1h (Yahoo history)")
    cut = -(-int(adj.time.min()) // 3600) * 3600
    h_old = h_old[h_old.time < cut].copy()
    for c in ("open", "high", "low", "close"):
        h_old[c] += gap
    h_new = resample(adj[adj.time >= cut], 3600)
    write_csv(pd.concat([h_old, h_new]).sort_values("time"), os.path.join(CLEAN, "ES_1h.csv"))
    m1 = sanitize(read_bars(os.path.join(DATA, "ES_1m.csv")), 60, "ES_1m")
    m1 = from_first_full_session(m1)
    if (m1.time < switch_t).any():
        raise RuntimeError("ES_1m reaches before the roll; adjust it too")
    write_csv(m1, os.path.join(CLEAN, "ES_1m.csv"))
    seg = adj.assign(td=tday_of(adj.time)).groupby("td").agg(source=("source", "first"), contract=("contract", "last"))
    return rolls, seg


def from_first_full_session(df: pd.DataFrame) -> pd.DataFrame:
    """Drop a leading partial session (a pull that starts mid-session)."""
    td = tday_of(df.time)
    for day in sorted(set(td)):
        s0, _ = session_bounds(day)
        if df.time.min() <= int(s0.timestamp()):
            return df[td >= day]
    return df


# ----------------------------------------------------------------------------------------------- NQ 1m repair
def build_1m(tv5_paths=None):
    """NQ_1m.csv was contaminated on 2026-10-16 by 5m rows. Keep only genuine 1-minute bars: a fresh Yahoo NQ=F 1m pull
    (data/clean/_src/yahoo_NQ_1m_*.csv) from its first complete session. It is all after the Sep-2026 roll (NQZ26) so it
    is already in the anchor price space."""
    import glob
    srcs = sorted(glob.glob(os.path.join(SRC, "yahoo_NQ_1m_*.csv")))
    if not srcs:
        sys.exit("run `python tools/data_audit.py fetch-refs` first")
    fresh = from_first_full_session(sanitize(read_bars(srcs[-1]), 60, "NQ_1m (fresh Yahoo)"))
    first_full = tday_of([fresh.time.min()])[0]
    # contamination report on the current file
    cur = read_bars(os.path.join(DATA, "NQ_1m.csv"))
    spacing = cur.time.diff()
    tv = read_bars(os.path.join(DATA, "tv_mnq_5m_2026-10-16.csv"))
    k = cur.merge(tv[["time", "close", "volume"]], on="time", how="left", suffixes=("", "_tv"))
    contaminated = (k.close == k.close_tv) & (k.volume == k.volume_tv)
    # agreement between surviving genuine Yahoo 1m rows and the fresh pull (Yahoo revises bars)
    m = cur[~contaminated.values].merge(fresh, on="time", suffixes=("_o", "_n"))
    rev = {"overlap": int(len(m)), "close_equal_pct": round(float((m.close_o == m.close_n).mean() * 100), 2) if len(m) else None,
           "volume_equal_pct": round(float((m.volume_o == m.volume_n).mean() * 100), 2) if len(m) else None}
    write_csv(fresh, os.path.join(CLEAN, "NQ_1m.csv"))
    return {"rows": int(len(fresh)), "first_day": first_full, "last_t": str(et_of([fresh.time.max()])[0]),
            "source": os.path.basename(srcs[-1]),
            "current_file_rows": int(len(cur)), "current_rows_at_300s_spacing": int((spacing == 300).sum()),
            "current_rows_that_are_tv_5m_bars": int(contaminated.sum()),
            "current_contaminated_inside_yahoo_1m_span": int((contaminated & (k.time >= 1789590000)).sum()),
            "yahoo_revision_check": rev}


# ----------------------------------------------------------------------------------------------- Yahoo vs TV compare
def compare_sources(yahoo_path=None, tv_path=None) -> dict:
    y = read_bars(yahoo_path or os.path.join(DATA, "NQ_5m.yahoo_backup.csv"))
    tv = read_bars(tv_path or os.path.join(DATA, "tv_mnq_5m_2026-10-16.csv"))
    out = {}
    # timestamp alignment: which shift of the TV clock best matches Yahoo closes
    best = []
    for sh in (-3600, -600, -300, 0, 300, 600, 3600):
        m = y.merge(tv.assign(time=tv.time + sh), on="time", suffixes=("_y", "_t"))
        best.append((sh, float((m.close_t - m.close_y).abs().median()), len(m)))
    out["clock_shift_test"] = best
    m = y.merge(tv, on="time", suffixes=("_y", "_t"), how="outer", indicator=True)
    m["td"] = tday_of(m.time)
    both = m[m._merge == "both"].copy()
    both["dc"] = both.close_t - both.close_y
    both["dh"] = both.high_t - both.high_y
    both["dl"] = both.low_t - both.low_y
    out["bars_both"] = int(len(both))
    out["only_tv"] = int((m._merge == "right_only").sum())
    out["only_yahoo"] = int((m._merge == "left_only").sum())
    out["abs_dclose_p50_p90_p99"] = [float(both.dc.abs().quantile(q)) for q in (.5, .9, .99)]
    out["close_exact_pct"] = round(float((both.dc.abs() < 1e-9).mean() * 100), 1)
    out["tv_high_minus_yahoo_median"] = float(both.dh.median())
    out["tv_low_minus_yahoo_median"] = float(both.dl.median())
    out["vol_ratio_tv_over_yahoo_median"] = round(float((both.volume_t / both.volume_y.replace(0, np.nan)).median()), 2)
    out["yahoo_zero_volume_bars"] = int((both.volume_y == 0).sum())
    big = both[both.dc.abs() > 100]
    out["contract_mismatch_bars"] = {"n": int(len(big)), "from": str(et_of([big.time.min()])[0]) if len(big) else None,
                                     "to": str(et_of([big.time.max()])[0]) if len(big) else None,
                                     "median_yahoo_minus_tv": float(-big.dc.median()) if len(big) else None}
    per_day = both.groupby("td").agg(bars=("dc", "size"), med_dclose=("dc", "median"),
                                     max_abs_dclose=("dc", lambda x: x.abs().max()),
                                     vol_ratio=("volume_t", "sum"))
    per_day["vol_ratio"] = (per_day["vol_ratio"] / both.groupby("td").volume_y.sum()).round(2)
    per_day["only_tv"] = m[m._merge == "right_only"].groupby("td").size()
    per_day["only_yahoo"] = m[m._merge == "left_only"].groupby("td").size()
    out["per_day"] = per_day.fillna(0)
    return out


# ----------------------------------------------------------------------------------------------- backtest verification
def run_backtest(data_dir: str, days_from=None, days_to=None, params=None):
    """engine.backtest.run against another data dir (module attribute swap; engine files are not modified)."""
    sys.path.insert(0, ROOT)
    import engine.data as ed
    import engine.backtest as eb
    old = (ed.DATA_DIR, eb.DATA_DIR)
    ed.DATA_DIR = eb.DATA_DIR = data_dir
    ed._cache.clear()
    try:
        p = dict(params or {})
        if days_from:
            p["days_from"] = days_from
        if days_to:
            p["days_to"] = days_to
        return eb.run("NQ", "5m", p, light=True)
    finally:
        ed.DATA_DIR, eb.DATA_DIR = old
        ed._cache.clear()


def diff_trades(a: list, b: list, la="A", lb="B") -> tuple[list, float]:
    def key(t):
        return (int(t["entry_t"]) // 300, t["dir"])

    def f(t):
        if t is None:
            return ""
        e = dt.datetime.fromtimestamp(t["entry_t"], dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo(TZ))
        return (f"{e:%m-%d %H:%M} {'L' if t['dir'] == 1 else 'S'} {t['trigger']} e{t['entry']:.2f} sl{t['stop']:.2f} "
                f"tp{t['target']:.2f} {t['exit_reason']} q{t['qty']} {t['pnl_r']:+.2f}R ${t['pnl']:+.0f}")
    A, B = {key(t): t for t in a}, {key(t): t for t in b}
    rows, tot = [], 0.0
    for k in sorted(set(A) | set(B)):
        x, y = A.get(k), B.get(k)
        d = (y["pnl"] if y else 0) - (x["pnl"] if x else 0)
        tot += d
        same = bool(x and y and abs(d) < 0.5 and abs(x["entry"] - y["entry"]) < 0.3 and x["qty"] == y["qty"])
        kind = "same" if same else ("changed" if x and y else (f"only {la}" if x else f"only {lb}"))
        rows.append({"kind": kind, la: f(x), lb: f(y), "delta": round(d, 1)})
    return rows, round(tot, 1)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "audit"
    if cmd == "fetch-refs":
        fetch_refs()
    elif cmd == "build-es":
        build_es()
    elif cmd == "build-1m":
        print(json.dumps(build_1m(), indent=1))
    elif cmd == "audit":
        d = argv[2] if len(argv) > 2 else CLEAN
        out = argv[3] if len(argv) > 3 else None
        q = audit_dir(d, out)
        pd.set_option("display.width", 250)
        print(q.groupby(["file", "status"]).size().to_string())
    elif cmd == "compare":
        r = compare_sources()
        pd.set_option("display.width", 250)
        print(r.pop("per_day").to_string())
        print(json.dumps(r, indent=1, default=str))
    elif cmd == "backtest":
        a, b = argv[2], argv[3]
        fr = argv[4] if len(argv) > 4 else None
        to = argv[5] if len(argv) > 5 else None
        ra, rb = run_backtest(a, fr, to), run_backtest(b, fr, to)
        for lab, r in (("A", ra), ("B", rb)):
            s = r["stats"]
            print(lab, {k: s.get(k) for k in ("trades", "win_rate", "profit_factor", "net", "max_dd", "trades_per_week")})
        rows, tot = diff_trades(ra["trades"], rb["trades"])
        for r in rows:
            if r["kind"] != "same":
                print(f"  {r['kind']:8s} A: {r['A']}\n           B: {r['B']}  delta {r['delta']:+}")
        print("same:", sum(r["kind"] == "same" for r in rows), "total delta", tot)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
