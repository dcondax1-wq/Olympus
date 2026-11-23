"""Import REAL CME futures history (NQ / ES) from a data vendor or your platform, then build 1m/5m/15m/1h files.

Sources supported
  databento   python import_futures.py databento NQ 2024-01-01 2026-08-01
              needs env var DATABENTO_API_KEY (your key; never hard-code it). Pulls GLBX.MDP3 ohlcv-1m for the
              continuous front month (NQ.v.0 = highest-volume contract) as CSV.
  ninjatrader python import_futures.py ninjatrader NQ path/to/export.txt [tz]
              NinjaTrader 8 "Historical Data > Export" minute file: "yyyyMMdd HHmmss;open;high;low;close;volume".
              NT stamps bars at their CLOSE in the PC's time zone (default tz America/New_York).
  csv         python import_futures.py csv NQ path/to/file.csv [tz]
              any CSV with columns time|datetime|timestamp, open, high, low, close, volume (bar OPEN time).
              TradingView "Export chart data" files work here too (export with B-ADJ OFF, see research/DATA_AUDIT.md).

Rules (see research/DATA_AUDIT.md)
  * The source bar interval is detected from the median timestamp spacing. A source only writes its own interval and
    coarser ones: a 5m export writes 5m/15m/1h, never 1m (that is how NQ_1m.csv got 5-minute rows on 2026-10-16).
  * If <SYM>_rolls.json exists next to the target files, the files are back-adjusted (additive, anchored to the current
    front month). Incoming raw front-month bars are shifted by the same roll gaps before merging, so they land in the
    same price space.
  * If the incoming bars disagree with the bars already on file by more than a few points over a whole session (e.g. a
    back-adjusted export merged onto unadjusted history), the import is refused instead of silently mixing price spaces.

Imported bars are merged with existing files (imported data wins on overlap).
"""
import base64
import io
import json
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TFS = (("1m", 60), ("5m", 300), ("15m", 900), ("1h", 3600))
MAX_SESSION_MEDIAN_DIFF = 5.0   # points; median |new - old| close over one session above this = different price space


def detect_interval(times) -> int:
    """Source bar interval in seconds from the median spacing of consecutive timestamps (gaps barely move a median)."""
    t = pd.Series(sorted(set(int(x) for x in times)))
    if len(t) < 3:
        raise ValueError("need at least 3 bars to detect the bar interval")
    med = float(t.diff().dropna().median())
    secs = min((s for _, s in TFS), key=lambda s: abs(s - med))
    if abs(secs - med) > 0.2 * secs:
        raise ValueError(f"median bar spacing {med:.0f}s is not a supported interval (1m/5m/15m/1h)")
    return secs


def load_rolls(sym: str, out_dir: str = HERE) -> list:
    path = os.path.join(out_dir, f"{sym}_rolls.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("rolls", [])


def apply_rolls(df: pd.DataFrame, rolls: list) -> pd.DataFrame:
    """Additive back-adjustment: every bar strictly before a roll's switch time gets that roll's gap added."""
    df = df.copy()
    for r in rolls:
        pre = df["time"] < int(r["switch_t"])
        for c in ("open", "high", "low", "close"):
            df.loc[pre, c] = df.loc[pre, c] + float(r["gap"])
    return df


def _check_price_space(sym, tf, old: pd.DataFrame, new: pd.DataFrame):
    m = old.merge(new, on="time", suffixes=("_o", "_n"))
    if len(m) < 50:
        return
    et = pd.to_datetime(m["time"], unit="s", utc=True).dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)
    d = (m["close_n"] - m["close_o"]).groupby(et.dt.strftime("%Y-%m-%d"))
    med = d.median()[d.size() >= 20]
    bad = med[med.abs() > MAX_SESSION_MEDIAN_DIFF]
    if len(bad):
        raise ValueError(f"{sym}_{tf}: incoming bars differ from the bars on file by a median of "
                         f"{bad.iloc[0]:+.2f} pts on {bad.index[0]} ({len(bad)} sessions). Different price space "
                         f"(back-adjusted export? wrong contract? unrecorded roll?). In TradingView turn B-ADJ off and "
                         f"export again, or record the roll in {sym}_rolls.json. Nothing was written.")


def _finish(sym: str, df: pd.DataFrame, out_dir: str = HERE, check: bool = True) -> int:
    """Clean, (back-adjust per <SYM>_rolls.json), and merge into <SYM>_<tf>.csv for the source interval and coarser.
    Returns the detected source interval in seconds."""
    df = df.dropna().copy()
    df["time"] = df["time"].astype("int64")
    df = df.sort_values("time").drop_duplicates("time", keep="last")
    df = df[(df["high"] >= df["low"]) & (df["volume"] >= 0)]
    src = detect_interval(df["time"])
    off = df["time"] % src != 0
    if off.any():
        print(f"  dropping {int(off.sum())} off-grid rows (time not a multiple of {src}s)")
        df = df[~off]
    df = apply_rolls(df, load_rolls(sym, out_dir))
    print(f"{sym}: {len(df)} source bars @ {src}s  {pd.to_datetime(df.time.min(), unit='s')} -> "
          f"{pd.to_datetime(df.time.max(), unit='s')} UTC")
    outs = {}
    for tf, secs in TFS:
        if secs < src or secs % src:
            continue   # never write a finer timeframe than the source (no fake 1m rows from 5m data)
        g = df.assign(b=df["time"] // secs * secs).groupby("b")
        out = pd.DataFrame({"time": g["b"].first(), "open": g["open"].first(), "high": g["high"].max(),
                            "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
        path = os.path.join(out_dir, f"{sym}_{tf}.csv")
        if os.path.exists(path):
            old = pd.read_csv(path)
            if secs > src and df["time"].min() % secs and int(out["time"].iloc[0]) in set(old["time"]):
                out = out.iloc[1:]   # first coarse bucket is only partly covered by the import: keep the full old bar
            if check:
                _check_price_space(sym, tf, old, out)
            out = pd.concat([old[~old["time"].isin(out["time"])], out]).sort_values("time")
        outs[tf] = (path, out)
    for tf, (path, out) in outs.items():   # write only after every price-space check passed
        out.to_csv(path, index=False)
        print(f"  wrote {sym}_{tf}.csv ({len(out)} bars)")
    return src


def build_daily(sym: str, out_dir: str = HERE) -> int:
    """<SYM>_1d.csv from <SYM>_1h.csv for the CME days newer than its last bar (night-cleanup 2026-11-22: the PC's bars only
    ever rebuilt 1m / 5m / 15m / 1h, so NQ_1d / ES_1d stopped at the Oct 16 TradingView export). A day = 18:00 ET the evening
    before -> 17:00 ET, stamped that day 00:00 UTC (TradingView's own daily stamp; checked equal to the export on its last 60
    days, OHLC and volume). Only finished days: one with its 16:00 ET hour or a later day on file. Append-only. -> days added."""
    h_path, d_path = os.path.join(out_dir, f"{sym}_1h.csv"), os.path.join(out_dir, f"{sym}_1d.csv")
    if not (os.path.exists(h_path) and os.path.exists(d_path)):
        return 0
    d = pd.read_csv(d_path)
    last = int(d["time"].max()) if len(d) else 0
    h = pd.read_csv(h_path)
    et = pd.to_datetime(h["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    h = h.assign(day=(et + pd.Timedelta(hours=6)).dt.normalize().dt.tz_localize(None), hr=et.dt.hour)
    h = h[h["day"] > pd.Timestamp(last, unit="s")]
    if not len(h):
        return 0
    days = sorted(h["day"].unique())
    done = [x for i, x in enumerate(days) if i < len(days) - 1 or (h.loc[h["day"] == x, "hr"] == 16).any()]
    h = h[h["day"].isin(done)]
    if not len(h):
        return 0
    g = h.sort_values("time").groupby("day")
    out = pd.DataFrame({"time": ((g["day"].first() - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).astype("int64"),
                        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    if (out["volume"].round() == out["volume"]).all():
        out["volume"] = out["volume"].round().astype("int64")
    pd.concat([d, out], ignore_index=True).to_csv(d_path, index=False)
    return len(out)


def _epoch(series):
    return (series - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)


def databento(sym, start, end):
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        sys.exit("Set DATABENTO_API_KEY in your environment first.")
    q = urllib.parse.urlencode({"dataset": "GLBX.MDP3", "symbols": f"{sym}.v.0", "stype_in": "continuous",
                                "schema": "ohlcv-1m", "start": start, "end": end, "encoding": "csv",
                                "pretty_px": "true", "pretty_ts": "true", "map_symbols": "true"})
    req = urllib.request.Request("https://hist.databento.com/v0/timeseries.get_range?" + q,
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()})
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = r.read().decode()
    df = pd.read_csv(io.StringIO(raw))
    ts = pd.to_datetime(df["ts_event"], utc=True)
    out = pd.DataFrame({"time": _epoch(ts).astype("int64"), "open": df["open"], "high": df["high"], "low": df["low"],
                        "close": df["close"], "volume": df["volume"]})
    _finish(sym, out)


def ninjatrader(sym, path, tz="America/New_York"):
    df = pd.read_csv(path, sep=";", header=None, names=["dt", "open", "high", "low", "close", "volume"])
    ts = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S").dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    out = pd.DataFrame({"time": _epoch(ts.dt.tz_convert("UTC")), "open": df["open"], "high": df["high"],
                        "low": df["low"], "close": df["close"], "volume": df["volume"]}).dropna()
    out["time"] = out["time"] - detect_interval(out["time"])   # close-stamp -> open-stamp (by the file's own interval)
    _finish(sym, out)


def _frame_from_table(df: pd.DataFrame, tz="UTC") -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    col = next((c for c in ("time", "datetime", "timestamp", "date") if c in df.columns), None)
    if col is None or not {"open", "high", "low", "close"} <= set(df.columns):
        raise ValueError("need columns time, open, high, low, close (TradingView: Export chart data)")
    if pd.api.types.is_numeric_dtype(df[col]):
        t = df[col].astype("int64")
        t = t // 1000 if t.max() > 10**11 else t
    else:
        ts = pd.to_datetime(df[col], utc=False)
        if getattr(ts.dt, "tz", None) is None:
            ts = ts.dt.tz_localize(tz)
        t = _epoch(ts.dt.tz_convert("UTC"))
    vol = df["volume"] if "volume" in df.columns else 0
    return pd.DataFrame({"time": t.astype("int64"), "open": df["open"], "high": df["high"], "low": df["low"],
                         "close": df["close"], "volume": vol}).dropna()


def generic(sym, path, tz="UTC"):
    _finish(sym, _frame_from_table(pd.read_csv(path), tz))


def tradingview_text(sym, text, out_dir: str = HERE):
    """TradingView 'Export chart data' CSV as text: time (ISO with offset, or unix seconds), open, high, low, close, Volume.
    Bars are stamped at their OPEN. Returns a summary dict; also records which sessions came from TradingView."""
    out = _frame_from_table(pd.read_csv(io.StringIO(text)))
    if out.empty:
        raise ValueError("no rows")
    src = _finish(sym, out, out_dir)
    # remember which ET sessions are real TradingView futures data (shown in the dashboard)
    et = pd.to_datetime(out["time"], unit="s", utc=True).dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)
    days = sorted(set(et.dt.strftime("%Y-%m-%d")))
    path = os.path.join(out_dir, f"{sym}_imported_days.json")
    old = json.load(open(path)) if os.path.exists(path) else []
    json.dump(sorted(set(old) | set(days)), open(path, "w"))
    five = pd.read_csv(os.path.join(out_dir, f"{sym}_5m.csv"))
    return {"rows": int(len(out)), "from": days[0], "to": days[-1], "days": len(days), "bars_5m": int(len(five)),
            "source_interval_s": int(src)}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    kind, sym = sys.argv[1], sys.argv[2].upper()
    if kind == "databento":
        databento(sym, sys.argv[3], sys.argv[4])
    elif kind == "ninjatrader":
        ninjatrader(sym, sys.argv[3], *(sys.argv[4:5]))
    else:
        generic(sym, sys.argv[3], *(sys.argv[4:5]))
