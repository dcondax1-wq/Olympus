"""Import a folder of TradingView exports (CME NQ1! / ES1!, 1m or 5m) into data/: check them, merge them, say what happened.

    python tools/import_tv.py <folder>              # check every export in the folder, then merge it into data/ (backup first)
    python tools/import_tv.py <folder> --check      # only check and print the summary; nothing is written
    python tools/import_tv.py <folder> --roll       # also accept a NEW contract roll found in the export (re-anchors history)
    options: --data DIR (default data/), --sym NQ|ES (when a file name does not say), --gap PTS (the new roll's gap, if
             you know it better than the export's own session-open jump), --tz America/New_York (time stamps without an
             offset; the default TradingView export uses UNIX seconds and needs nothing)

How to export (TradingView, chart CME_MINI:NQ1! or CME_MINI:ES1!, ETH session, Volume indicator on the chart, B-ADJ OFF):
"Export chart data" -> default name (e.g. "CME_MINI_NQ1!, 1.csv") or this repo's names (NQ1_1m_chunk_<date>.csv,
ES1_5m_chunk_<date>.csv). Put every file in one folder and run this command on it.

What it checks (any ERROR = nothing is written, exit code 1):
  * file name -> symbol (NQ / ES; MNQ1! / MES1! micro files are skipped) and bar size (from the name, checked against the
    median spacing of the time stamps: 1m or 5m)
  * time zone: UNIX seconds or ISO stamps with an offset are unambiguous. ERROR when bars sit in the 17:00-17:59 ET CME halt
    (the stamps are shifted); a warning when the busiest bar of the day is not near the 09:30 ET open
  * duplicates: the same time twice in one file, and overlapping files that disagree on a bar (the copy farther from its
    file's end wins: a Bar Replay file can end on a still-forming bar)
  * junk rows: off-grid stamps, weekend / halt bars, high < low, flat no-volume placeholder bars (dropped and counted)
  * gaps: sessions with missing bars inside (holiday sessions are named, not counted as faults)
  * rolls: TradingView's NQ1! / ES1! switches to the next contract at the session that opens 3 full trading days before the
    last trading day (Dec 2026: Mon 2026-12-14 18:00 ET). The export is front-month UNADJUSTED, so each switch shows a
    jump of the contract spread (~1%). A roll already in data/<SYM>_rolls.json must jump at that very bar (TradingView
    switched where the files say). A roll the files do not have yet is a NEW roll: with --roll the importer records it
    (gap = the session-open jump, or --gap) and re-anchors every <SYM> file on the new contract (bars before the switch
    + gap), as tools/stitch_tv_chunks.py does: the history always sits on the newest contract's prices.
  * B-ADJ: a known roll without its jump = TradingView back-adjusted the export itself: ERROR, export again with B-ADJ off
  * overlap with the files on disk: after the roll adjustment the bars both have must agree (per-session median close
    within 5 pts, else ERROR: different price space); how many bars are new, how many replace equal bars
  * 1m only: rebuilt to 5m it must match data/<SYM>_5m.csv (median |close diff| <= 0.125, 90% within 0.25)

What it writes (after a backup of every file it changes into data/_import_backup/<time>/):
  * 5m export -> <SYM>_5m.csv, and the 15m / 1h bars it touches (rebuilt from the merged 5m)
  * 1m export -> <SYM>_1m.csv, plus 5m bars where <SYM>_5m.csv has a hole and the 1m export has all five minutes
  * a new roll (--roll) -> <SYM>_rolls.json + every <SYM>_{1m,5m,15m,1h}.csv shifted onto the new contract
  * <SYM>_imported_days.json: the sessions that now come from TradingView
Imported bars win over the bars on disk on every time both have.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import data_audit as da  # noqa: E402

COLS = ["time", "open", "high", "low", "close", "volume"]
TF_NAME = {60: "1m", 300: "5m", 900: "15m", 3600: "1h"}
SESSION_DIFF_MAX = 5.0        # pts: per-session median |new - old| close above this = another price space
ROLL_GAP_RANGE = (40.0, 800.0)  # a real NQ / ES roll gap (NQ Sep 2026: 294.75; ES: 30-90)
KNOWN_JUMP_TOL = 1.0          # pts: TradingView's jump at a recorded roll vs the recorded open jump
MED_MAX, P90_MAX = 0.125, 0.25  # 1m rebuilt to 5m vs the 5m file (tools/stitch_tv_1m.py)
CONTRACT_MONTH = {3: "H", 6: "M", 9: "U", 12: "Z"}


# ------------------------------------------------------------------------------------------------ calendar
def tv_switch_t(y: int, m: int) -> int:
    """TradingView's NQ1! / ES1! switch from the (y, m) contract to the next one: the first bar (18:00 ET) of the session
    that is 3 full trading days before the last trading day (holiday / early-close sessions do not count). Same rule as
    tools/stitch_tv_chunks.detect_rolls; reproduces every NQ switch in data/NQ_rolls.json."""
    ltd = da.last_trading_day(y, m)
    full, d = [], ltd - dt.timedelta(days=1)
    while len(full) < 3:
        if d.weekday() < 5 and not da.holiday_name(d.isoformat()):
            full.append(d)
        d -= dt.timedelta(days=1)
    start, _ = da.session_bounds(full[-1].isoformat())
    return int(start.timestamp())


def next_contract(y: int, m: int):
    return (y, m + 3) if m < 12 else (y + 1, 3)


def code(sym: str, y: int, m: int) -> str:
    return f"{sym}{CONTRACT_MONTH[m]}{y % 100:02d}"


def parse_code(c: str):
    """'NQZ26' -> (2026, 12)."""
    mm = {v: k for k, v in CONTRACT_MONTH.items()}[c[-3]]
    return 2000 + int(c[-2:]), mm


# ------------------------------------------------------------------------------------------------ reading
NAME_SYM = re.compile(r"(?i)(?<![A-Z])(M?)(NQ|ES)1?!?(?![A-Z])")


def name_info(path: str):
    """(sym, micro, secs from the name or None) from a TradingView / repo file name."""
    base = os.path.basename(path)
    m = NAME_SYM.search(base)
    sym = m.group(2).upper() if m else None
    micro = bool(m and m.group(1))
    secs = None
    mt = re.search(r"(?i)(?:_|^)(1|5)m(?:_|\.|$)", base) or re.search(r",\s*(1|5)(?:\D|$)", base)
    if mt:
        secs = 60 * int(mt.group(1))
    return sym, micro, secs


def detect_secs(t) -> int | None:
    t = np.unique(np.asarray(t, dtype="int64"))
    if len(t) < 3:
        return None
    med = float(np.median(np.diff(t)))
    for s in (60, 300, 900, 3600):
        if abs(med - s) <= 0.2 * s:
            return s
    return None


def read_export(path: str, tz: str | None = None) -> pd.DataFrame:
    """A TradingView 'Export chart data' file -> time (bar OPEN, unix s UTC), open, high, low, close, volume, pos_from_end.
    Raises ValueError with a plain reason."""
    try:
        raw = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f"cannot read it as CSV ({e.__class__.__name__})")
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    col = next((c for c in ("time", "datetime", "timestamp", "date") if c in raw.columns), None)
    if col is None or not {"open", "high", "low", "close"} <= set(raw.columns):
        raise ValueError("needs the columns time, open, high, low, close (TradingView: Export chart data)")
    if "volume" not in raw.columns:
        raise ValueError("no Volume column: add the Volume indicator to the chart and export again")
    s = raw[col]
    if pd.api.types.is_numeric_dtype(s):
        t = s.astype("int64")
        t = t // 1000 if t.max() > 10 ** 11 else t                  # milliseconds -> seconds
    else:
        sv = s.astype(str)
        has_off = sv.str.contains(r"(?:[+-]\d{2}:?\d{2}|Z)$", regex=True).all()
        if not has_off and not tz:
            raise ValueError("time stamps have no time zone (no offset): export with UNIX time, or pass --tz America/New_York")
        ts = pd.to_datetime(sv, utc=has_off)
        if not has_off:
            ts = ts.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        t = ((ts - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1))
    df = pd.DataFrame({"time": pd.to_numeric(t, errors="coerce"), "open": pd.to_numeric(raw["open"], errors="coerce"),
                       "high": pd.to_numeric(raw["high"], errors="coerce"), "low": pd.to_numeric(raw["low"], errors="coerce"),
                       "close": pd.to_numeric(raw["close"], errors="coerce"),
                       "volume": pd.to_numeric(raw["volume"], errors="coerce").fillna(0.0)})
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df["time"] = df["time"].astype("int64")
    df["pos_from_end"] = np.arange(len(df))[::-1]
    if not len(df):
        raise ValueError("no rows")
    return df


def tz_problems(df: pd.DataFrame, secs: int):
    """(errors, warnings): bars in the CME halt = shifted stamps; the busiest bar should be near the 09:30 ET open."""
    err, warn = [], []
    et = da.et_of(df["time"].values)
    mod = et.hour * 60 + et.minute
    wk = et.weekday < 5
    halt = wk & (mod >= 17 * 60) & (mod < 18 * 60)
    if halt.sum() > max(2, 0.002 * len(df)):
        err.append(f"{int(halt.sum())} bars stamped 17:00-17:59 ET, when CME is closed: the time stamps are shifted "
                   "(time zone, or bar-close stamps). Export with UNIX time stamps.")
    if len(df) > 2000:
        rng = pd.Series((df["high"] - df["low"]).values).groupby(mod).median()
        busiest = int(rng.idxmax())
        if not (8 * 60 + 30 <= busiest <= 10 * 60 + 5):
            warn.append(f"the busiest bar of the day is at {busiest // 60:02d}:{busiest % 60:02d} ET (expected near the "
                        "09:30 open): check the time zone")
    return err, warn


def combine(frames):
    """One row per time stamp across overlapping files. Returns (frame, n_overlap_times, n_disagreements)."""
    df = pd.concat(frames, ignore_index=True)
    dup = df[df.duplicated("time", keep=False)]
    n_ov = int(dup["time"].nunique())
    n_bad = 0
    if n_ov:
        rng = dup.groupby("time")[["open", "high", "low", "close"]].agg(lambda x: float(x.max() - x.min()))
        n_bad = int((rng.max(axis=1) > 0.01).sum())
    df = df.sort_values(["time", "pos_from_end"], ascending=[True, False]).drop_duplicates("time", keep="first")
    return df[COLS].reset_index(drop=True), n_ov, n_bad


# ------------------------------------------------------------------------------------------------ checks
def gap_summary(df: pd.DataFrame, secs: int):
    q = da.audit_frame(df.assign(source="tv"), secs, "export", extra_cols=())
    if q.empty:
        return q, []
    holes = q[(q["missing_inside"] > np.maximum(2, 0.02 * q["expected"])) & (q["holiday"] == "")]
    return q, [f"{r.day} ({int(r.missing_inside)} bars missing)" for r in holes.itertuples()]


def roll_doc(sym: str, data_dir: str) -> dict:
    p = os.path.join(data_dir, f"{sym}_rolls.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return {"sym": sym, "anchor": None, "rolls": []}


def jump_at(df: pd.DataFrame, t: int):
    """open of the bar at t minus the previous bar's close (None when the export has no bar at t or before it)."""
    tt = df["time"].values
    j = int(np.searchsorted(tt, t))
    if j >= len(tt) or int(tt[j]) != t or j == 0 or t - int(tt[j - 1]) > 3 * 3600:
        return None
    return float(df["open"].iloc[j] - df["close"].iloc[j - 1])


def find_rolls(df: pd.DataFrame, sym: str, doc: dict, gap_override=None):
    """The contract rolls to apply to the export, checked against the export's own jumps. Returns (rolls [{..., gap,
    tv_switch_t}], new roll or None, errors, notes). Every recorded roll is applied (bars before its switch + gap, so the
    export lands on the files' anchor); a recorded roll inside the export must show its jump at TradingView's switch bar.
    A switch inside the export past the anchor is a NEW roll (gap = the session-open jump there, or gap_override)."""
    err, notes = [], []
    t0, t1 = int(df["time"].min()), int(df["time"].max())
    rec = doc.get("rolls") or []
    anchor = doc.get("anchor")
    apply, new = [], None
    pick = {}
    for r in rec:                     # one roll per contract (an older ES_rolls.json carried ESU26 twice)
        if r["from"] not in pick or int(r.get("switch_t", 0)) == tv_switch_t(*parse_code(r["from"])):
            pick[r["from"]] = r
    rec = list(pick.values())
    for r in rec:
        y, m = parse_code(r["from"])
        st = tv_switch_t(y, m)
        apply.append({**r, "tv_switch_t": st, "in_export": t0 < st <= t1})
        if not t0 < st <= t1:
            continue
        when = f"{da.et_of([st])[0]:%Y-%m-%d %H:%M} ET"
        jmp = jump_at(df, st)
        g = float(r["gap"])
        if jmp is None:
            notes.append(f"roll {r['from']}->{r['to']} ({when}): no bar at the switch in the export; recorded gap {g:+.2f} used")
        elif abs(g) >= ROLL_GAP_RANGE[0] and abs(jmp) < 0.3 * abs(g):
            err.append(f"roll {r['from']}->{r['to']} ({when}): the export shows no roll jump there ({jmp:+.2f} pts; the files "
                       f"have a {g:+.2f} gap). TradingView back-adjusted it: turn B-ADJ off and export again.")
        elif r.get("open_jump") is not None and abs(jmp - float(r["open_jump"])) > KNOWN_JUMP_TOL:
            err.append(f"roll {r['from']}->{r['to']} ({when}): the export jumps {jmp:+.2f} pts at the switch bar, the files "
                       f"recorded {float(r['open_jump']):+.2f}: TradingView did not switch where the files say")
        else:
            notes.append(f"roll {r['from']}->{r['to']} ({when}): same switch bar as the files (jump {jmp:+.2f}, gap {g:+.2f})")
    known = {r["from"] for r in rec}
    # an older switch inside the export that the files do not know
    d0, d1 = dt.date.fromtimestamp(t0), dt.date.fromtimestamp(t1)
    for y in range(d0.year - 1, d1.year + 1):
        for m in (3, 6, 9, 12):
            st = tv_switch_t(y, m)
            if t0 < st <= t1 and code(sym, y, m) not in known and (anchor is None or (y, m) < parse_code(anchor)):
                err.append(f"roll {code(sym, y, m)} at {_fmt_t(st)} is inside the export but not in {sym}_rolls.json")
    if anchor:
        y, m = parse_code(anchor)
        st = tv_switch_t(y, m)
        if t0 < st <= t1:
            frm, to = anchor, code(sym, *next_contract(y, m))
            nst = tv_switch_t(*next_contract(y, m))
            jmp = jump_at(df, st)
            if t0 < nst <= t1:
                err.append(f"the export crosses two new rolls ({frm}->{to} and the next): import it in two parts")
            elif jmp is None and gap_override is None:
                err.append(f"NEW roll {frm}->{to} at {_fmt_t(st)}: the export has no bar at the switch, so the gap cannot be "
                           "measured: pass --gap PTS")
            else:
                gap = round(float(gap_override if gap_override is not None else jmp) * 4) / 4
                if not ROLL_GAP_RANGE[0] <= abs(gap) <= ROLL_GAP_RANGE[1]:
                    err.append(f"NEW roll {frm}->{to} at {_fmt_t(st)}: a {gap:+.2f}-pt jump is not a roll-sized gap "
                               f"({ROLL_GAP_RANGE[0]:.0f}-{ROLL_GAP_RANGE[1]:.0f} pts): pass --gap PTS")
                else:
                    drift = (doc.get("weekday_open_drift_p50_p90") or [4.0, 23.0])[0]
                    new = {"from": frm, "to": to, "ltd": da.last_trading_day(y, m).isoformat(), "switch_day": None,
                           "switch_t": st, "switch_et": str(da.et_of([st])[0]),
                           "weekend_switch": bool(da.et_of([st])[0].weekday() == 6), "open_jump": jmp,
                           "source_at_switch": f"tv-{sym}1!", "check": "ok",
                           "method": "override (--gap)" if gap_override is not None else "open_jump", "gap": gap,
                           "uncertainty": 0.25 if gap_override is not None else float(drift),
                           "price_before": float(df.loc[df["time"] < st, "close"].iloc[-1]) if (df["time"] < st).any() else None,
                           "added_by": "tools/import_tv.py", "added_on": dt.date.today().isoformat()}
                    new["switch_day"] = da.tday_of([st])[0]
                    apply.append({**new, "tv_switch_t": st, "in_export": True})
    return apply, new, err, notes


def back_adjust(df: pd.DataFrame, rolls) -> pd.DataFrame:
    """Additive, anchored to the newest contract: every bar before a switch gets that roll's gap (cumulative)."""
    out = df.copy()
    adj = np.zeros(len(out))
    t = out["time"].values
    for r in rolls:
        adj += np.where(t < int(r.get("tv_switch_t", r["switch_t"])), float(r["gap"]), 0.0)
    for c in ("open", "high", "low", "close"):
        out[c] = out[c].values + adj
    return out


def overlap_check(old: pd.DataFrame, new: pd.DataFrame):
    """(errors, stats) for the bars both have."""
    if old is None or not len(old):
        return [], {"overlap": 0, "same": 0, "new": int(len(new)), "sessions_bad": 0}
    m = old[["time", "close"]].merge(new[["time", "close"]], on="time", suffixes=("_o", "_n"))
    st = {"overlap": int(len(m)), "same": int((np.abs(m["close_n"] - m["close_o"]) <= 0.25).sum()) if len(m) else 0,
          "new": int((~new["time"].isin(old["time"])).sum()), "sessions_bad": 0}
    err = []
    if len(m) >= 20:
        d = (m["close_n"] - m["close_o"]).groupby(da.tday_of(m["time"].values))
        med = d.median()[d.size() >= 10]
        bad = med[med.abs() > SESSION_DIFF_MAX]
        st["sessions_bad"] = int(len(bad))
        if len(bad):
            err.append(f"the export differs from the bars on disk by a median of {bad.iloc[0]:+.2f} pts on {bad.index[0]} "
                       f"({len(bad)} sessions): a different price space (B-ADJ on? a single contract instead of {{SYM}}1!? "
                       "an unrecorded roll?). Nothing was written.")
    return err, st


def verify_1m(one: pd.DataFrame, five: pd.DataFrame):
    """(ok, text): the 1m export rebuilt to 5m vs the 5m file on complete windows."""
    if five is None or not len(five) or not len(one):
        return True, "no 5m bars to compare with"
    g = one.assign(b=one["time"] // 300 * 300).groupby("b")
    r = pd.DataFrame({"time": g["b"].first(), "close": g["close"].last(), "n": g["time"].size()})
    r = r[r["n"] == 5]
    m = r.merge(five[["time", "close"]], on="time", suffixes=("_1", "_5"))
    if len(m) < 50:
        return True, f"only {len(m)} complete 5m windows to compare with the 5m file"
    d = (m["close_1"] - m["close_5"]).abs()
    med, p90 = float(d.median()), float(d.quantile(0.9))
    ok = med <= MED_MAX and p90 <= P90_MAX
    return ok, f"rebuilt to 5m it matches the 5m file on {len(m)} bars (median diff {med:.3f}, 90% within {p90:.2f} pts)"


def cover_1m(one: pd.DataFrame, five: pd.DataFrame):
    """Per session: 1m minutes present vs the minutes the 5m file has (5 per 5m bar). LIT executes on 1m only on days
    with >= 97% (engine/lit.py bars_1m)."""
    if not len(one) or five is None or not len(five):
        return pd.DataFrame(columns=["day", "have", "want", "cover"])
    days = sorted(set(da.tday_of(one["time"].values)))
    f = five[five["time"].between(int(one["time"].min()) // 300 * 300, int(one["time"].max()))]   # the export's own span
    want = pd.Series(da.tday_of(f["time"].values)).value_counts() * 5
    o = one[(one["time"] // 300 * 300).isin(set(f["time"]))]
    have = pd.Series(da.tday_of(o["time"].values)).value_counts()
    out = pd.DataFrame({"day": days})
    out["have"] = out["day"].map(have).fillna(0).astype(int)
    out["want"] = out["day"].map(want).fillna(0).astype(int)
    out["cover"] = np.where(out["want"] > 0, out["have"] / out["want"].clip(lower=1), np.nan)
    return out


# ------------------------------------------------------------------------------------------------ files
def read_file(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    for c in COLS:
        if c not in df.columns:
            df[c] = 0.0
    df = df[COLS].dropna(subset=["time"])
    df["time"] = df["time"].astype("int64")
    return df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)


def resample(df: pd.DataFrame, secs: int) -> pd.DataFrame:
    return da.resample(df[COLS], secs)


def merge_in(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if old is None or not len(old):
        return new[COLS].sort_values("time").reset_index(drop=True)
    return pd.concat([old[~old["time"].isin(new["time"])], new[COLS]]).sort_values("time").reset_index(drop=True)


def shift_before(df: pd.DataFrame, t: int, gap: float) -> pd.DataFrame:
    if not len(df):
        return df
    df = df.copy()
    pre = df["time"] < t
    for c in ("open", "high", "low", "close"):
        df.loc[pre, c] = df.loc[pre, c] + gap
    return df


def _fmt_t(t) -> str:
    return f"{da.et_of([int(t)])[0]:%Y-%m-%d %H:%M} ET"


# ------------------------------------------------------------------------------------------------ the import
def plan(folder: str, data_dir: str, sym_arg=None, tz=None, gap=None, accept_roll=False):
    """Read + check everything; no file is written. Returns a dict: errors, warnings, lines (the summary), writes
    {file name: frame}, rolls {sym: new rolls doc}, days {sym: sessions}."""
    out = {"errors": [], "warnings": [], "lines": [], "writes": {}, "rolls": {}, "days": {}}
    E, W, L = out["errors"], out["warnings"], out["lines"]
    paths = sorted(p for p in glob.glob(os.path.join(folder, "**", "*.csv"), recursive=True) if os.path.isfile(p))
    if not paths:
        E.append(f"no .csv files in {folder}")
        return out
    groups = {}
    for p in paths:
        nm = os.path.basename(p)
        sym, micro, secs_name = name_info(p)
        sym = sym or (sym_arg.upper() if sym_arg else None)
        if micro:
            W.append(f"{nm}: a micro (MNQ1!/MES1!) export, skipped: export CME_MINI:NQ1! / ES1! instead")
            continue
        if sym not in ("NQ", "ES"):
            E.append(f"{nm}: cannot tell NQ or ES from the name (rename it, e.g. NQ1_1m_<date>.csv, or pass --sym)")
            continue
        try:
            df = read_export(p, tz)
        except ValueError as e:
            E.append(f"{nm}: {e}")
            continue
        secs = detect_secs(df["time"])
        if secs not in (60, 300):
            E.append(f"{nm}: bar spacing is not 1 or 5 minutes (median {np.median(np.diff(np.unique(df['time']))):.0f} s)")
            continue
        if secs_name and secs_name != secs:
            E.append(f"{nm}: the name says {TF_NAME[secs_name]} but the bars are {TF_NAME[secs]} apart")
            continue
        e2, w2 = tz_problems(df, secs)
        E.extend(f"{nm}: {x}" for x in e2)
        W.extend(f"{nm}: {x}" for x in w2)
        groups.setdefault((sym, secs), []).append((nm, df))
    if E:
        return out
    # 5m first: a new roll is measured on the 5m export when there is one, and the same gap is used for the 1m export
    order = sorted(groups, key=lambda k: (k[0], -k[1]))
    new_rolls = {}
    files = {}

    def cur(sym, tf):
        key = f"{sym}_{tf}.csv"
        if key not in files:
            files[key] = read_file(os.path.join(data_dir, key))
        return files[key]

    for sym, secs in order:
        tf = TF_NAME[secs]
        items = groups[(sym, secs)]
        raw, n_ov, n_bad = combine([d for _, d in items])
        n0 = len(raw)
        clean = da.sanitize(raw, secs).reset_index(drop=True)
        dropped = n0 - len(clean)
        L.append(f"{sym} {tf}: {len(items)} file(s), {n0} bars {_fmt_t(raw['time'].min())} -> {_fmt_t(raw['time'].max())}")
        if n_ov:
            L.append(f"  overlapping files: {n_ov} bars in more than one file, {n_bad} disagree"
                     + (" (the copy farther from its file's end kept)" if n_bad else ""))
            if n_bad > max(5, 0.01 * n_ov):
                W.append(f"{sym} {tf}: {n_bad} bars differ between overlapping files")
        if dropped:
            L.append(f"  dropped {dropped} junk rows (weekend / halt / off-grid / bad OHLC / flat no-volume)")
        q, holes = gap_summary(clean, secs)
        hol = q[q["holiday"] != ""]["day"].tolist() if len(q) else []
        L.append(f"  sessions: {len(q)}" + (f" ({len(hol)} holiday sessions: {', '.join(hol[:4])}{' ...' if len(hol) > 4 else ''})" if hol else "")
                 + (f"; {len(holes)} with holes: {', '.join(holes[:6])}{' ...' if len(holes) > 6 else ''}" if holes else "; no holes"))
        doc = new_rolls.get(sym) or roll_doc(sym, data_dir)
        rolls, new, e3, notes = find_rolls(clean, sym, doc, gap)
        for n in notes:
            L.append("  " + n)
        if e3:
            E.extend(f"{sym} {tf}: {x}" for x in e3 if x)
            continue
        if new is not None:
            if not accept_roll:
                E.append(f"{sym} {tf}: NEW roll {new['from']} -> {new['to']} at {new['switch_et'][:16]} ET, gap {new['gap']:+.2f} "
                         f"pts ({new['method']}, +-{new['uncertainty']}). Importing it re-anchors the whole {sym} history on "
                         f"{new['to']} (every bar before the switch {new['gap']:+.2f}). Run again with --roll to do it.")
                continue
            doc = json.loads(json.dumps(doc))
            doc["rolls"] = (doc.get("rolls") or []) + [{k: v for k, v in new.items()}]
            doc["anchor"] = new["to"]
            new_rolls[sym] = doc
            out["rolls"][sym] = doc
            L.append(f"  NEW roll {new['from']} -> {new['to']} at {new['switch_et'][:16]} ET, gap {new['gap']:+.2f} pts: "
                     f"the {sym} history is re-anchored on {new['to']}")
            for t2 in ("1m", "5m", "15m", "1h"):
                k = f"{sym}_{t2}.csv"
                files[k] = shift_before(cur(sym, t2), new["switch_t"], new["gap"])
                out["writes"][k] = files[k]
        adj = back_adjust(clean, rolls)
        old = cur(sym, tf)
        e4, st = overlap_check(old, adj)
        ok1, txt1 = verify_1m(adj, cur(sym, "5m")) if secs == 60 else (True, "")
        if secs == 60 and not ok1:
            E.append(f"{sym} 1m: {txt1}: the 1m bars are not in the 5m file's price space")
            continue
        if e4 and secs == 60 and txt1.startswith("rebuilt"):
            # the 5m file is the authority: the export matches it, so the old 1m file was off there (another contract's
            # basis on some days, see engine/lit.py bars_1m): the export replaces those bars
            W.append(f"{sym} 1m: the old {sym}_1m.csv sat on another price basis on {st['sessions_bad']} session(s); the "
                     "export matches the 5m file and replaces those bars")
            e4 = []
        if e4:
            E.extend(f"{sym} {tf}: {x.replace('{SYM}', sym)}" for x in e4)
            continue
        L.append(f"  vs data/{sym}_{tf}.csv: {st['overlap']} bars overlap ({st['same']} equal within a tick), "
                 f"{st['new']} new bars")
        if txt1:
            L.append("  " + txt1)
        merged = merge_in(old, adj)
        files[f"{sym}_{tf}.csv"] = merged
        out["writes"][f"{sym}_{tf}.csv"] = merged

        def coarse(five_all, touched_t):
            for t2, s2 in (("15m", 900), ("1h", 3600)):
                bk = set((np.asarray(list(touched_t), dtype="int64") // s2 * s2).tolist())
                m5 = five_all[(five_all["time"] // s2 * s2).isin(bk)]
                k = f"{sym}_{t2}.csv"
                files[k] = merge_in(cur(sym, t2), resample(m5, s2))
                out["writes"][k] = files[k]

        if secs == 300:
            coarse(merged, adj["time"].values)
        else:
            five = cur(sym, "5m")
            full = adj.groupby(adj["time"] // 300 * 300)["time"].size()
            fill = resample(adj, 300)
            fill = fill[fill["time"].isin(full[full == 5].index) & ~fill["time"].isin(five["time"])]
            if len(fill):
                files[f"{sym}_5m.csv"] = merge_in(five, fill)
                out["writes"][f"{sym}_5m.csv"] = files[f"{sym}_5m.csv"]
                coarse(files[f"{sym}_5m.csv"], fill["time"].values)
                L.append(f"  {len(fill)} 5m bars {sym}_5m.csv did not have were built from complete 1m windows")
            cov = cover_1m(adj, files.get(f"{sym}_5m.csv", five))
            if len(cov):
                low = cov[cov["cover"] < 0.97]
                L.append(f"  1m cover: {len(cov)} sessions, median {cov['cover'].median():.1%}; under 97% (LIT trades those "
                         f"days on 5m bars): {len(low)}" + (f" ({', '.join(low['day'].head(6))}{' ...' if len(low) > 6 else ''})" if len(low) else ""))
        out["days"].setdefault(sym, set()).update(set(da.tday_of(adj["time"].values)))
    for k in list(out["writes"]):                     # a file that ends up exactly as it was is not rewritten
        a, b = out["writes"][k], read_file(os.path.join(data_dir, k))
        if len(a) == len(b) and (a["time"].to_numpy() == b["time"].to_numpy()).all() and \
                np.allclose(a[COLS[1:]].to_numpy(dtype=float), b[COLS[1:]].to_numpy(dtype=float), atol=1e-9):
            del out["writes"][k]
    return out


def write(out: dict, data_dir: str) -> str:
    """Back up every file that changes, then write. Returns the backup folder."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(data_dir, "_import_backup", stamp)
    os.makedirs(bdir, exist_ok=True)
    names = list(out["writes"]) + [f"{s}_rolls.json" for s in out["rolls"]] + [f"{s}_imported_days.json" for s in out["days"]]
    for n in names:
        p = os.path.join(data_dir, n)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bdir, n))
    for n, df in out["writes"].items():
        da.write_csv(df.assign(time=df["time"].astype("int64")), os.path.join(data_dir, n))
    for s, doc in out["rolls"].items():
        with open(os.path.join(data_dir, f"{s}_rolls.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, default=str)
    for s, days in out["days"].items():
        p = os.path.join(data_dir, f"{s}_imported_days.json")
        old = []
        if os.path.exists(p):
            try:
                old = json.load(open(p, encoding="utf-8"))
            except Exception:
                old = []
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(sorted(set(old) | set(days)), fh)
    return bdir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/import_tv.py", description="Import TradingView NQ1!/ES1! exports into data/")
    ap.add_argument("folder")
    ap.add_argument("--check", action="store_true", help="only check, write nothing")
    ap.add_argument("--roll", action="store_true", help="accept a new contract roll found in the export (re-anchors history)")
    ap.add_argument("--gap", type=float, default=None, help="the new roll's gap in points (default: the export's session-open jump)")
    ap.add_argument("--sym", default=None, help="NQ or ES, when a file name does not say")
    ap.add_argument("--tz", default=None, help="time zone of time stamps without an offset, e.g. America/New_York")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"), help="the data folder (default data/)")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.folder):
        print(f"ERROR: {a.folder} is not a folder")
        return 1
    out = plan(a.folder, a.data, sym_arg=a.sym, tz=a.tz, gap=a.gap, accept_roll=a.roll)
    print("\n".join(out["lines"]) or "(nothing read)")
    for w in out["warnings"]:
        print("warning: " + w)
    if out["errors"]:
        for e in out["errors"]:
            print("ERROR: " + e)
        print("\nNothing was written.")
        return 1
    if a.check:
        print(f"\nCheck only: everything is fine; {len(out['writes'])} file(s) would change: {', '.join(sorted(out['writes']))}")
        return 0
    if not out["writes"]:
        print("\nNothing to write.")
        return 0
    bdir = write(out, a.data)
    print(f"\nDone: wrote {', '.join(sorted(out['writes']))}" + (f" and {', '.join(s + '_rolls.json' for s in out['rolls'])}" if out["rolls"] else "")
          + f". Backup of the old files: {os.path.relpath(bdir, ROOT) if bdir.startswith(ROOT) else bdir}")
    if out["rolls"]:
        print("A new roll re-anchored the history: rerun python tools/export_backtest.py and the research baselines "
              "(prices moved by the gap; the VIX-band target is a % of price, so results move a little).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
