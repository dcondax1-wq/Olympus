"""NinjaTrader 8 1-minute exports of other CME micros (MGC gold, MCL crude, M2K Russell) -> data/<SYM>_1m/5m/15m/1h.csv.
Research data only (docs/OTHER_MARKETS.md); nothing here touches the live bot or the NQ files.

Input = NinjaTrader 8 "Tools > Historical Data > Export" text files (Data type Last, Minute 1):
    yyyyMMdd HHmmss;open;high;low;close;volume        one bar per line, stamped at the bar's CLOSE
  * the continuous contract ("MGC ##-##") with NinjaTrader's merge policy "Merge back adjusted" (one file: already rolled
    and back-adjusted by NinjaTrader), or
  * one file per contract ("MGC 12-26.Last.txt", "MGC 02-27.Last.txt", ...): stitched here, each roll on the first session
    after the next contract trades more volume than the current one (never back), additive back-adjustment anchored to the
    newest contract (the gap = new - old close at the last minute both traded before the switch), written to
    data/<SYM>_rolls.json in the data/NQ_rolls.json shape. Both kinds may sit in one folder: per-contract files win.
Time zone: NinjaTrader writes the time zone of its own settings (often the PC's, sometimes the exchange's Chicago time). It is
found from the data: every CME Globex market here halts 17:00-18:00 ET, so the right zone is the one that puts (almost) no bar
close inside that hour (--tz forces one). Bars are re-stamped at their OPEN (UTC seconds), as every data/*.csv file.
The rest is data/import_futures.py (_finish: clean, drop off-grid rows, back-adjust per <SYM>_rolls.json, write 1m and the
coarser files). A run rebuilds the market's files from the export (the export is the whole history), never merges.
Also writes data/<SYM>_rv_1d.csv (20-day realized vol in % a year, per trading day, from the futures closes: the target band
for gold / crude, engine/lit_markets.py) and data/<SYM>_import.json (what was read).

    python -X utf8 tools/nt_import.py MGC                      # finds data/MGC*.txt and data/nt_export/MGC/*.txt
    python -X utf8 tools/nt_import.py MCL path/to/file_or_folder [--tz America/Chicago] [--out data]
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
_spec = importlib.util.spec_from_file_location("import_futures", os.path.join(DATA, "import_futures.py"))
IF = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IF)

ET = "America/New_York"
TZ_CANDIDATES = (ET, "America/Chicago", "America/Denver", "America/Los_Angeles", "UTC", "Europe/London", "Europe/Berlin")
MONTH_CODES = "FGHJKMNQUVXZ"
FILE_RE = re.compile(r"(?P<root>[A-Z0-9]{1,4})\s+(?P<mm>\d\d|##)-(?P<yy>\d\d|##)", re.I)
TFS = ("1m", "5m", "15m", "1h")


# ================================================================================================ reading
def read_nt(path: str) -> pd.DataFrame:
    """One NinjaTrader export: naive local close-stamp `dt` + open, high, low, close, volume."""
    df = pd.read_csv(path, sep=";", header=None, names=["dt", "open", "high", "low", "close", "volume"], dtype={"dt": str})
    df["dt"] = pd.to_datetime(df["dt"].str.strip(), format="%Y%m%d %H%M%S")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna().reset_index(drop=True)


def contract_of(path: str):
    """'MGC 12-26.Last.txt' -> ('MGC', 'MGCZ26', 2026, 12); continuous ('MGC ##-##') or unknown -> None."""
    m = FILE_RE.search(os.path.basename(path))
    if not m or "#" in m.group("mm") + m.group("yy"):
        return None
    mo, yy = int(m.group("mm")), int(m.group("yy"))
    if not 1 <= mo <= 12:
        return None
    root = m.group("root").upper()
    return root, f"{root}{MONTH_CODES[mo - 1]}{yy:02d}", 2000 + yy, mo


def detect_tz(dts: pd.Series, secs: int = 60) -> tuple:
    """(zone, {zone: share of bar closes inside the 17:00-18:00 ET halt}). The zone with the smallest share wins."""
    s = dts.iloc[:: max(1, len(dts) // 200000)]
    share = {}
    for tz in TZ_CANDIDATES:
        loc = s.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT").dropna()
        et = loc.dt.tz_convert(ET)
        m = (et.dt.hour * 60 + et.dt.minute).values
        lo = 1020 + max(1, secs // 60)                 # the first close stamp that cannot exist (17:01 for 1m bars)
        share[tz] = round(float(np.mean((m >= lo) & (m <= 1080))) if len(m) else 1.0, 5)
    best = min(share, key=lambda z: (share[z], TZ_CANDIDATES.index(z)))
    return best, share


def to_frame(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Close-stamped local bars -> open-stamped UTC seconds (the data/*.csv convention)."""
    ts = df["dt"].dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    ok = ts.notna()
    out = pd.DataFrame({"time": IF._epoch(ts[ok].dt.tz_convert("UTC")).astype("int64"), "open": df["open"][ok],
                        "high": df["high"][ok], "low": df["low"][ok], "close": df["close"][ok], "volume": df["volume"][ok]})
    out["time"] = out["time"] - IF.detect_interval(out["time"])
    return out.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)


def tday_of(t) -> np.ndarray:
    """Trading date (18:00 ET -> 17:00 ET belongs to the next day) as yyyy-mm-dd strings."""
    et = pd.to_datetime(np.asarray(t), unit="s", utc=True).tz_convert(ET) + pd.Timedelta(hours=6)
    return et.strftime("%Y-%m-%d").values


# ================================================================================================ rolls
def stitch(contracts: list) -> tuple:
    """contracts = [(code, frame)] (any order). Returns (raw front-month frame with column 'code', roll records).
    Volume roll: from the current contract to the busiest later one on the first session after a later contract traded
    more volume than the current one that day (or the current one stopped trading); never back to an earlier contract."""
    order = {"F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6, "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12}
    contracts = sorted(contracts, key=lambda cf: (int(cf[0][-2:]), order[cf[0][-3]]))
    vol, frames, byday = {}, {}, {}
    for code, f in contracts:
        f = f.copy()
        f["tday"] = tday_of(f["time"])
        vol[code] = f.groupby("tday")["volume"].sum()
        frames[code] = f
        byday[code] = {d: g for d, g in f.groupby("tday")}
    codes = [c for c, _ in contracts]
    days = sorted(set().union(*[set(v.index) for v in vol.values()]))
    cur, assign, switch_next = 0, {}, None
    for d in days:
        if switch_next is not None:
            cur, switch_next = switch_next, None
        while cur < len(codes) - 1 and d not in vol[codes[cur]].index and d > vol[codes[cur]].index.max():
            cur += 1                                     # the current contract has expired: the next one with data
        assign[d] = cur
        vc = float(vol[codes[cur]].get(d, 0.0))
        later = [(float(vol[codes[j]].get(d, 0.0)), j) for j in range(cur + 1, len(codes))]
        if later:
            vb, jb = max(later)
            if vb > vc:
                switch_next = jb
    parts, rolls = [], []
    prev_code = None
    for d in days:
        code = codes[assign[d]]
        part = byday[code].get(d)
        if part is None or part.empty:
            continue
        if prev_code is not None and code != prev_code:
            st = int(part["time"].iloc[0])
            old, new = frames[prev_code], frames[code]
            both = old[old["time"] < st].merge(new[new["time"] < st], on="time", suffixes=("_o", "_n"))
            if len(both):
                last = both.iloc[-1]
                gap, how = float(last["close_n"] - last["close_o"]), "last common minute"
            else:
                o_prev = old[old["time"] < st]
                gap = float(part["open"].iloc[0] - o_prev["close"].iloc[-1]) if len(o_prev) else 0.0
                how = "open jump (no common minute)"
            sw = pd.Timestamp(st, unit="s", tz="UTC").tz_convert(ET)
            rolls.append({"from": prev_code, "to": code, "switch_day": d, "switch_t": st, "switch_et": str(sw),
                          "gap": round(gap, 6), "method": how, "check": "ok" if len(both) else "no overlap"})
        parts.append(part.drop(columns="tday").assign(code=code))
        prev_code = code
    raw = pd.concat(parts).sort_values("time").reset_index(drop=True) if parts else pd.DataFrame()
    return raw, rolls


# ================================================================================================ realized vol (target band)
def rv_frame(adj5: pd.DataFrame, raw_close: pd.Series | None = None, n: int = 20) -> pd.DataFrame:
    """20-day realized vol (% a year) per trading date, known at that date's close (lit._vix reads the last date BEFORE a
    session, so no look-ahead). Point changes of the back-adjusted closes over the raw (unadjusted) close level."""
    td = tday_of(adj5["time"])
    g = adj5.assign(tday=td).groupby("tday")
    cl = g["close"].last()
    lvl = cl if raw_close is None else raw_close.reindex(cl.index).fillna(cl)
    r = cl.diff() / lvl.shift(1)
    rv = r.rolling(n).std() * np.sqrt(252.0) * 100.0
    out = pd.DataFrame({"date": cl.index, "close": rv.round(4).values}).dropna()
    return out.reset_index(drop=True)


# ================================================================================================ the build
def find_exports(sym: str, data_dir: str = DATA) -> list:
    pats = [os.path.join(data_dir, f"{sym}*.txt"), os.path.join(data_dir, f"{sym.lower()}*.txt"),
            os.path.join(data_dir, "nt_export", sym, "*.txt"), os.path.join(data_dir, "nt_export", f"{sym}*.txt")]
    out = []
    for p in pats:
        out += [f for f in glob.glob(p) if f not in out]
    return sorted(out)


def build(sym: str, paths: list, out_dir: str = DATA, tz: str | None = None, log=print) -> dict:
    sym = sym.upper()
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, "*.txt"))) if os.path.isdir(p) else [p]
    if not files:
        raise FileNotFoundError(f"no NinjaTrader export for {sym}: save it as data/{sym} ##-##.Last.txt (docs/OTHER_MARKETS.md)")
    per, cont = [], []
    for f in files:
        c = contract_of(f)
        if c and c[0] != sym:
            log(f"  skipped {os.path.basename(f)} (root {c[0]}, not {sym})")
            continue
        (per if c else cont).append((f, c))
    use = per or cont[:1]
    if per and cont:
        log(f"  per-contract files found: the continuous file(s) {[os.path.basename(f) for f, _ in cont]} are not used")
    raws = [(f, c, read_nt(f)) for f, c in use]
    allt = pd.concat([r[2]["dt"] for r in raws])
    zone, share = (tz, None) if tz else detect_tz(allt)
    if tz:
        auto, share = detect_tz(allt)
        if auto != tz and share[tz] > share[auto] + 0.01:
            log(f"  WARNING: --tz {tz} puts {share[tz]:.1%} of bars inside the 17:00-18:00 ET halt; {auto} puts {share[auto]:.1%}")
    log(f"{sym}: {len(use)} file(s), time zone {zone}" + ("" if tz else " (found from the 17:00-18:00 ET halt)"))
    frames = [(c[1] if c else "cont", to_frame(df, zone)) for f, c, df in raws]
    if per:
        raw, rolls = stitch(frames)
        method = ("volume roll (first session after a later contract trades more), additive back-adjustment anchored to "
                  "the newest contract: bars before switch_t get +gap (cumulative)")
        anchor = raw["code"].iloc[-1]
    else:
        raw, rolls = frames[0][1], []
        method = "NinjaTrader continuous export (merge policy 'Merge back adjusted'): already rolled, no gaps added here"
        anchor = contract_of(use[0][0]) or "continuous"
        anchor = anchor if isinstance(anchor, str) else anchor[1]
        _warn_jumps(raw, log)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{sym}_rolls.json"), "w", encoding="utf-8") as fh:
        json.dump({"sym": sym, "anchor": anchor, "method": method, "rolls": rolls, "source": "ninjatrader"}, fh, indent=1)
    for tf in TFS:                                        # a full rebuild: the export is the whole history
        p = os.path.join(out_dir, f"{sym}_{tf}.csv")
        if os.path.exists(p):
            os.remove(p)
    cols = ["time", "open", "high", "low", "close", "volume"]
    src = IF._finish(sym, raw[cols].copy(), out_dir, check=False)
    five = pd.read_csv(os.path.join(out_dir, f"{sym}_5m.csv"))
    rc = None
    if per:
        rc = raw.assign(tday=tday_of(raw["time"])).groupby("tday")["close"].last()
    rv = rv_frame(five, rc)
    rv.to_csv(os.path.join(out_dir, f"{sym}_rv_1d.csv"), index=False)
    days = sorted(set(tday_of(five["time"])))
    info = {"sym": sym, "files": [os.path.basename(f) for f, _ in use], "kind": "per-contract" if per else "continuous",
            "tz": zone, "tz_halt_share": share, "source_interval_s": int(src), "bars_1m": int(len(raw)),
            "first_day": days[0], "last_day": days[-1], "sessions": len(days), "rolls": len(rolls)}
    with open(os.path.join(out_dir, f"{sym}_import.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    log(f"  {sym}: {info['sessions']} sessions {days[0]} -> {days[-1]}, {len(rolls)} rolls, rv file {len(rv)} days")
    return info


def _warn_jumps(raw: pd.DataFrame, log, k: float = 8.0):
    """A continuous file that was NOT back-adjusted shows big 18:00 open jumps at the rolls: say so (nothing is changed)."""
    if len(raw) < 1000:
        return
    td = tday_of(raw["time"])
    first = np.r_[True, td[1:] != td[:-1]]
    rng = (raw["high"] - raw["low"]).rolling(500, min_periods=50).median().values
    jump = np.abs(raw["open"].values - np.r_[np.nan, raw["close"].values[:-1]])
    big = first & (jump > k * np.maximum(rng, 1e-9) * 10)
    n = int(np.nansum(big))
    if n >= 3:
        log(f"  NOTE: {n} session opens jump more than ~{k * 10:.0f}x a typical minute range. If the export was 'Merge non back "
            f"adjusted', set Tools > Options > Market data > Merge policy = 'Merge back adjusted' and export again.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sym")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--tz")
    ap.add_argument("--out", default=DATA)
    a = ap.parse_args(argv)
    paths = a.paths or find_exports(a.sym.upper(), a.out)
    build(a.sym, paths, a.out, a.tz)
    return 0


if __name__ == "__main__":
    sys.exit(main())
