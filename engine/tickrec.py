"""Tick recorder (READ-ONLY): NQ / ES trades with size and aggressor side -> data/ticks/YYYY-MM-DD.parquet (day-orderflow 2026-11-23).

Why: every strategy so far ran on OHLC bars. Order flow (delta, absorption, imbalances, big prints) needs every trade with its
size and whether it hit the bid or lifted the ask. We have none of that today (research/writeups/orderflow-2026-11-23.md).

Two sources, both free, both futures:
  1. LIVE: ninjatrader/LE_TickRec.cs (NinjaScript AddOn, read-only) appends every Last trade, with the bid and ask in force at
     that moment, to  Documents\\NinjaTrader 8\\le_ticks\\<ROOT>_<YYYY-MM-DD>.csv  (ET date). It records ONLY while the flag
     file le_ticks\\enabled.txt exists; `python -m engine.tickrec enable` writes it, `disable` removes it.
     `python -m engine.tickrec ingest` (or `run`, a loop) turns those CSVs into data/ticks/YYYY-MM-DD.parquet.
  2. HISTORY: NinjaTrader's free historical tick data (Tools > Historical Data, steps in the writeup). Its Export tab writes a
     text file; `python -m engine.tickrec import <file.txt> --root NQ` turns it into the same daily files.

Rows: t_ns (int64 UTC nanoseconds), root (NQ/ES), price, size, bid, ask, side (+1 buyer lifted the ask, -1 seller hit the bid,
0 unknown). Side = quote rule (price >= ask -> +1, price <= bid -> -1); inside the spread or no quote -> tick rule (up-tick
+1, down-tick -1, same price -> previous side).

SAFETY (non-negotiable): this module never writes to NinjaTrader's incoming\\ folder, never builds an order line and imports
nothing that can trade (no engine.ninjatrader, engine.live, engine.tradovate). It is OFF unless enabled (data/tickrec.json
{"enabled": true} or OLYMPUS_TICKREC=1). Nothing in the bot imports it, so it cannot change a trade. Parquet needs pyarrow
(`pip install pyarrow`, free); without it the daily file is written as .csv.gz instead, same columns.

  python -m engine.tickrec status
  python -m engine.tickrec enable [--roots NQ,ES]      writes data/tickrec.json + le_ticks\\enabled.txt + instruments.txt
  python -m engine.tickrec disable
  python -m engine.tickrec ingest                      le_ticks CSVs -> data/ticks (idempotent, de-duplicated)
  python -m engine.tickrec run [--every 60]            ingest in a loop (only while enabled)
  python -m engine.tickrec import [FILE.txt | FOLDER]   NT8 tick export(s) -> data/ticks (UTC stamps; default folder
                                                       Documents\\NinjaTrader 8\\le_ticks\\export)
  python -m engine.tickrec autopilot                   ingest + run the order-flow study at 60 NQ days (the PC's 15-min
                                                       report task starts it outside 02:00-16:05 ET; nothing to click)
  python -m engine.tickrec selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK_DIR = os.path.join(ROOT, "data", "ticks")
CFG_PATH = os.path.join(ROOT, "data", "tickrec.json")
ENV = "OLYMPUS_TICKREC"
ET = ZoneInfo("America/New_York")
COLS = ["t_ns", "root", "price", "size", "bid", "ask", "side"]
ROOTS_OK = ("NQ", "ES", "MNQ", "MES")
REC_DIR = "le_ticks"


def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------------------ on / off
def _cfg() -> dict:
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_enabled() -> bool:
    if os.environ.get(ENV, "").strip() == "1":
        return True
    return bool(_cfg().get("enabled", False))


def nt_dir() -> str | None:
    """Documents\\NinjaTrader 8 on the PC (None elsewhere). OLYMPUS_NT_DIR overrides (tests)."""
    o = os.environ.get("OLYMPUS_NT_DIR")
    if o:
        return o
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "Documents", "NinjaTrader 8"), os.path.join(home, "OneDrive", "Documents", "NinjaTrader 8")):
        if os.path.isdir(p):
            return p
    return None


def front_names(roots, today: dt.date | None = None) -> list[str]:
    """NinjaTrader names of the front quarterly contract ('NQ 12-26'); rolls 8 days before the 3rd Friday."""
    d = today or dt.datetime.now(ET).date()
    y, m = d.year, d.month
    for _ in range(5):
        if m % 3 == 0:
            first = dt.date(y, m, 1)
            fri3 = first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)
            if d <= fri3 - dt.timedelta(days=8):
                break
        m, y = (1, y + 1) if m == 12 else (m + 1, y)
    return ["%s %02d-%02d" % (r, m, y % 100) for r in roots]


def set_enabled(on: bool, roots=("NQ", "ES")) -> dict:
    roots = [r.upper() for r in roots if r.upper() in ROOTS_OK]
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    cfg = {"enabled": bool(on), "roots": roots, "changed": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    nd = nt_dir()
    if nd:
        rd = os.path.join(nd, REC_DIR)
        os.makedirs(rd, exist_ok=True)
        flag = os.path.join(rd, "enabled.txt")
        if on:
            with open(os.path.join(rd, "instruments.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(front_names(roots)) + "\n")
            with open(flag, "w", encoding="utf-8") as f:
                f.write("on " + cfg["changed"] + "\n")
        elif os.path.exists(flag):
            os.remove(flag)
    cfg["nt_dir"] = nd
    return cfg


# ------------------------------------------------------------------------------------------------------------ side
def classify(price, bid, ask) -> np.ndarray:
    """Aggressor side per trade: quote rule, then tick rule (Lee-Ready without the 5 s lag: NT gives the quote at the trade)."""
    p = np.asarray(price, float)
    b = np.asarray(bid, float)
    a = np.asarray(ask, float)
    side = np.zeros(len(p), np.int8)
    okq = (b > 0) & (a > 0) & (a >= b)
    side[okq & (p >= a)] = 1
    side[okq & (p <= b) & (side == 0)] = -1
    if len(p):
        dp = np.diff(p, prepend=p[0])
        tick = pd.Series(np.sign(dp)).replace(0, np.nan).ffill().fillna(0).values.astype(np.int8)  # tick rule, zero ticks carry
        side = np.where(side == 0, tick, side).astype(np.int8)
    return side


def quotes_filled_in(price, bid, ask) -> bool:
    """NinjaTrader fills in a quote when the feed gives none (Bid = Last, Ask = Bid + 1 tick; NT8 Help 'Developing for Tick
    Replay'). Then every trade sits AT the bid and the quote rule would call all of them sells. Real NQ trades hit the bid
    about half the time, so > 90 % at the bid (with a quote present) = filled in -> drop the quote, use the tick rule."""
    p, b, a = (np.asarray(x, float) for x in (price, bid, ask))
    q = (b > 0) & (a > 0)
    if q.sum() < 50:
        return False
    return float(np.mean(p[q] == b[q])) > 0.9 or float(np.mean(p[q] == a[q])) > 0.9


def frame(t_ns, root, price, size, bid=None, ask=None) -> pd.DataFrame:
    n = len(price)
    bid = np.zeros(n) if bid is None else np.asarray(bid, float)
    ask = np.zeros(n) if ask is None else np.asarray(ask, float)
    if quotes_filled_in(price, bid, ask):
        bid, ask = np.zeros(n), np.zeros(n)
    df = pd.DataFrame({"t_ns": np.asarray(t_ns, np.int64), "root": root, "price": np.asarray(price, float),
                       "size": np.asarray(size, np.int64), "bid": bid, "ask": ask})
    df = df.sort_values("t_ns", kind="stable").reset_index(drop=True)
    df["side"] = classify(df.price.values, df.bid.values, df.ask.values)
    return df[COLS]


# ------------------------------------------------------------------------------------------------------------ storage
def _day_path(day: str, ext: str) -> str:
    return os.path.join(TICK_DIR, day + ext)


def write_days(df: pd.DataFrame, tick_dir: str | None = None, replace_root: bool = False) -> list[str]:
    """Merge df into one file per ET date (de-duplicated on every column, so re-ingesting is harmless).
    replace_root=True: df is a WHOLE day from the history server (LE_TickRec backfill), so that root's old rows of the day
    (a partial live recording with slightly different stamps) are replaced instead of merged."""
    global TICK_DIR
    if tick_dir:
        TICK_DIR = tick_dir
    if df.empty:
        return []
    os.makedirs(TICK_DIR, exist_ok=True)
    et_day = pd.to_datetime(df.t_ns, utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    out = []
    pq = _has_pyarrow()
    for day, part in df.groupby(et_day.values):
        old = read_day(day)
        if old is not None and replace_root:
            old = old[~old.root.isin(part.root.unique())]
        both = _dedup(old, part[COLS])
        both = both.reset_index(drop=True)
        if pq:
            p = _day_path(day, ".parquet")
            both.to_parquet(p + ".tmp", index=False)
        else:
            p = _day_path(day, ".csv.gz")
            both.to_csv(p + ".tmp", index=False, compression="gzip")
        os.replace(p + ".tmp", p)
        out.append(p)
    return out


def _dedup(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Union that keeps legit repeats: NQ prints many identical trades in one time stamp. A row that appears k times in the
    old file and m times in the new data is kept max(k, m) times, so re-importing a file adds nothing and loses nothing."""
    key = ["t_ns", "root", "price", "size", "bid", "ask"]
    fr = [x.assign(_k=x.groupby(key, sort=False).cumcount()) for x in (old, new) if x is not None and len(x)]
    both = pd.concat(fr, ignore_index=True).drop_duplicates(subset=key + ["_k"]).drop(columns="_k")
    return both.sort_values(["root", "t_ns"], kind="stable")


def read_day(day: str) -> pd.DataFrame | None:
    p = _day_path(day, ".parquet")
    if os.path.exists(p) and _has_pyarrow():
        return pd.read_parquet(p)
    p = _day_path(day, ".csv.gz")
    if os.path.exists(p):
        return pd.read_csv(p)
    return None


def load(start: str, end: str, root: str = "NQ") -> pd.DataFrame:
    """All ticks of one root between two ET dates (inclusive)."""
    parts = []
    for d in pd.date_range(start, end, freq="D"):
        x = read_day(d.strftime("%Y-%m-%d"))
        if x is not None:
            parts.append(x[x.root == root])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)


def days_available() -> list[str]:
    fs = glob.glob(os.path.join(TICK_DIR, "*.parquet")) + glob.glob(os.path.join(TICK_DIR, "*.csv.gz"))
    return sorted({os.path.basename(f).split(".")[0] for f in fs})


# ------------------------------------------------------------------------------------------------------------ sources
def read_rec_csv(path: str) -> pd.DataFrame:
    """One LE_TickRec file: header t_ms,price,size,bid,ask (UTC ms). Root from the file name: <ROOT>_<date>.csv (live) or
    bf_<ROOT>_<date>.csv (backfill from the history server)."""
    parts = os.path.basename(path).split("_")
    root = (parts[1] if parts[0].lower() == "bf" else parts[0]).upper()
    x = pd.read_csv(path, on_bad_lines="skip")
    x = x.apply(pd.to_numeric, errors="coerce").dropna()
    x = x[(x["price"] > 0) & (x["size"] > 0)]
    return frame(x["t_ms"].astype(np.int64).values * 1_000_000, root, x["price"].values, x["size"].values,
                 x["bid"].values, x["ask"].values)


def _et_today() -> str:
    return dt.datetime.now(ET).strftime("%Y-%m-%d")


def ingest(nd: str | None = None) -> dict:
    """le_ticks CSVs -> data/ticks. Backfill days (bf_<ROOT>_<day>.csv, written whole by LE_TickRec) REPLACE that root's day,
    then the csv is deleted and bf_<ROOT>_<day>.done left behind, so LE_TickRec never asks for it again and the disk stays small.
    Live files are merged; a past day's live file is skipped once a backfill file for the same root / day exists."""
    nd = nd or nt_dir()
    if not nd:
        return {"ok": False, "why": "no Documents\\NinjaTrader 8 folder here"}
    rd = os.path.join(nd, REC_DIR)
    bf = sorted(glob.glob(os.path.join(rd, "bf_*_????-??-??.csv")))
    live = sorted(f for f in glob.glob(os.path.join(rd, "*_????-??-??.csv")) if not os.path.basename(f).lower().startswith("bf_"))
    done_keys = {os.path.basename(f)[3:-5] for f in glob.glob(os.path.join(rd, "bf_*_????-??-??.done"))}
    man_p = os.path.join(os.path.dirname(CFG_PATH), "tickrec_ingested.json")
    try:
        man = json.load(open(man_p, encoding="utf-8"))
    except Exception:
        man = {}
    rows, written, n_bf, n_live = 0, set(), 0, 0
    for f in bf:
        try:
            df = read_rec_csv(f)
            written.update(write_days(df, replace_root=True))
            rows += len(df)
            n_bf += 1
            key = os.path.basename(f)[3:-4]
            with open(f[:-4] + ".done", "w", encoding="utf-8") as fh:
                fh.write("%d rows ingested %s\n" % (len(df), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
            done_keys.add(key)
            os.remove(f)
        except Exception as e:
            print("tickrec: skip", os.path.basename(f), e)
    today = _et_today()
    for f in live:
        b = os.path.basename(f)
        key = b[:-4]                                         # NQ_2026-11-23
        if key in done_keys and key[-10:] < today:
            continue                                         # the server's whole day is already in
        sig = "%d:%d" % (os.path.getsize(f), int(os.path.getmtime(f)))
        if man.get(b) == sig:
            continue                                         # unchanged since the last ingest
        try:
            df = read_rec_csv(f)
        except Exception as e:
            print("tickrec: skip", b, e)
            continue
        rows += len(df)
        n_live += 1
        written.update(write_days(df))
        man[b] = sig
    try:
        os.makedirs(os.path.dirname(man_p), exist_ok=True)
        with open(man_p, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
    except Exception:
        pass
    return {"ok": True, "files": n_bf + n_live, "backfill_files": n_bf, "live_files": n_live, "rows": rows, "written": sorted(written)}


# ------------------------------------------------------------------------------------------------------------ autopilot
AUTO_PATH = os.path.join(ROOT, "data", "orderflow_auto.json")       # what the autopilot did (runs of the study)
NOTE_PATH = os.path.join(ROOT, "data", "orderflow_note.json")       # the one phone line tools/pc_report.py pushes once
STUDY_DAYS = 60


def in_window(et: dt.datetime) -> bool:
    """Heavy work only outside 02:00-16:05 ET on weekdays (the bot trades then); any time Saturday / Sunday (= LE_TickRec)."""
    if et.weekday() >= 5:
        return True
    m = et.hour * 60 + et.minute
    return m < 120 or m >= 16 * 60 + 5


def nq_days() -> list[str]:
    out = []
    for d in days_available():
        x = read_day(d)
        if x is not None and (x.root == "NQ").any():
            out.append(d)
    return out


def recorder_status(nd: str | None = None) -> dict:
    nd = nd or nt_dir()
    try:
        line = open(os.path.join(nd, REC_DIR, "le_tickrec_status.txt"), encoding="utf-8").read().strip()
    except Exception:
        return {}
    out = {}
    for part in line.split(",")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def phone_line(res: dict, days: int) -> str:
    """One line for the phone from of_study's results.json (PRE-REGISTERED block)."""
    pr = (res or {}).get("PRE-REGISTERED (PREREG_ticks.md)") or {}
    bits = []
    for key, short in (("OF1", "OF1 absorption"), ("OF2", "OF2 blocks"), ("OF3A", "OF3 LVN")):
        k = next((x for x in pr if x.startswith(key + " ") or x.startswith(key)), None)
        v = pr.get(k) if k else None
        if not isinstance(v, dict):
            bits.append(short + " n/a")
            continue
        gains = ["%+d" % v[s]["gain$"] for s in ("2026 H1", "2026 H2") if isinstance(v.get(s), dict) and "gain$" in v[s]]
        nets = ["%+d" % v[s]["net$"] for s in ("2026 H1", "2026 H2") if isinstance(v.get(s), dict) and "net$" in v[s]]
        bits.append("%s %s (%s$)" % (short, v.get("verdict", "?"), "/".join(gains or nets) or "0"))
    anyp = any("PASS" in b for b in bits)
    return ("Order-flow test ran on %d tick days: " % days + "; ".join(bits) + ". "
            + ("A PASS is a candidate only: Claude checks it next chat, nothing live changes without your yes."
               if anyp else "Nothing passed, LIT stays as it is."))


def autopilot(now: dt.datetime | None = None, study=None, nd: str | None = None) -> dict:
    """Zero-click chain, run by the PC's 15-minute report task outside trading hours: ingest new recorder / backfill files,
    then run research/orderflow/of_study.py ONCE when 60+ NQ tick days exist and once more when the backfill reports done
    (2 looks in total, never more), and leave one phone line in data/orderflow_note.json. Read-only towards the bot."""
    et = (now or dt.datetime.now(ET)).astimezone(ET)
    if not is_enabled():
        return {"ran": False, "why": "tick recorder is off"}
    if not in_window(et):
        return {"ran": False, "why": "trading hours (02:00-16:05 ET): later"}
    lock = os.path.join(os.path.dirname(CFG_PATH), "tickrec_autopilot.lock")
    try:
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
            return {"ran": False, "why": "another autopilot is running"}
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, "w") as fh:
            fh.write(str(os.getpid()))
    except Exception:
        return {"ran": False, "why": "no lock"}
    try:
        ing = ingest(nd)
        days = nq_days()
        try:
            auto = json.load(open(AUTO_PATH, encoding="utf-8"))
        except Exception:
            auto = {"runs": []}
        runs = auto.get("runs") or []
        st = recorder_status(nd)
        want = None
        if len(days) >= STUDY_DAYS and not runs:
            want = "first look"
        elif runs and len(runs) < 2 and st.get("backfill") == "done" and len(days) >= runs[-1]["days"] + 20:
            want = "final look (backfill done)"
        out = {"ran": False, "ingest": {k: ing.get(k) for k in ("ok", "files", "rows")}, "nq_days": len(days),
               "backfill": st.get("backfill"), "oldest": st.get("oldest")}
        if not want:
            out["why"] = "waiting: %d of %d NQ tick days" % (len(days), STUDY_DAYS) if len(days) < STUDY_DAYS else "already ran"
            return out
        res = (study or _run_study)()
        line = phone_line(res, len(days))
        runs.append({"t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "days": len(days), "look": want,
                     "first": days[0], "last": days[-1], "line": line})
        auto["runs"] = runs
        with open(AUTO_PATH, "w", encoding="utf-8") as fh:
            json.dump(auto, fh, indent=1)
        with open(NOTE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"key": "research:orderflow:%d" % len(days), "t": int(time.time()), "title": "Order flow: test result",
                       "body": line}, fh)
        out.update(ran=True, look=want, line=line)
        return out
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass


def _run_study() -> dict:
    import subprocess
    sp = os.path.join(ROOT, "research", "orderflow", "of_study.py")
    subprocess.run([sys.executable, sp], cwd=ROOT, timeout=6 * 3600, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return json.load(open(os.path.join(ROOT, "research", "orderflow", "results.json"), encoding="utf-8"))
    except Exception:
        return {}


def _parse_chunk(c: pd.DataFrame, root: str, tz: str) -> pd.DataFrame:
    """One chunk of an NT8 export read with 5 string columns (3-field lines leave columns 3-4 empty)."""
    t0 = c[0].astype(str).str.strip()
    base = pd.to_datetime(t0.str[:15], format="%Y%m%d %H%M%S", errors="coerce")
    frac = pd.to_numeric(t0.str[16:23].str.ljust(7, "0").where(t0.str.len() > 16, "0"), errors="coerce").fillna(0)
    five = c[4].notna()
    num = lambda k: pd.to_numeric(c[k], errors="coerce")  # noqa: E731
    price = num(1)
    bid = num(2).where(five, 0.0)
    ask = num(3).where(five, 0.0)
    vol = num(4).where(five, num(2))
    ok = base.notna() & price.notna() & vol.notna() & (price > 0) & (vol > 0) & bid.notna() & ask.notna()
    if not ok.any():
        return pd.DataFrame(columns=COLS)
    loc = pd.DatetimeIndex(base[ok]).tz_localize(ZoneInfo(tz), ambiguous="NaT", nonexistent="shift_forward")
    keep = ~pd.isna(loc)
    ns = loc[keep].tz_convert("UTC").as_unit("ns").asi8 + (frac[ok].values[keep].astype(np.int64) * 100)
    return frame(ns, root.upper(), price[ok].values[keep], vol[ok].values[keep].astype(np.int64),
                 bid[ok].values[keep], ask[ok].values[keep])


def _chunks(path: str, root: str, tz: str, rows: int = 2_000_000):
    rd = pd.read_csv(path, sep=";", header=None, names=range(5), dtype=str, chunksize=rows, on_bad_lines="skip",
                     engine="c", skip_blank_lines=True, encoding_errors="replace")
    for c in rd:
        yield _parse_chunk(c, root, tz)


def parse_nt_export(path: str, root: str, tz: str = "UTC") -> pd.DataFrame:
    """NinjaTrader 8 Historical Data > Export, Interval Tick, one line per trade:
         yyyyMMdd HHmmss fffffff;last;bid;ask;volume     (NT8 Tick Replay layout, with the quote -> quote rule)
         yyyyMMdd HHmmss[ fffffff];last;volume           (no quote -> tick rule only)
    NT8 always EXPORTS in UTC (help guide 'Exporting'), so the default tz is UTC. Only pass --tz for a file that came from
    somewhere else. Whole file in memory: fine for tests and small files; `import_file` streams big ones."""
    parts = list(_chunks(path, root, tz))
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLS)
    return df.sort_values("t_ns", kind="stable").reset_index(drop=True) if len(df) else df


def root_from_name(path: str) -> str:
    """'NQ 12-25.Last.txt' -> 'NQ' (NT's default export name)."""
    r = os.path.basename(path).replace("_", " ").split(" ")[0].split(".")[0].upper()
    return r if r in ROOTS_OK else "NQ"


def import_file(path: str, root: str | None = None, tz: str = "UTC") -> dict:
    """Stream a (multi-GB) NT8 tick export into data/ticks, 2M lines at a time. Re-importing the same file adds nothing."""
    root = (root or root_from_name(path)).upper()
    rows, quoted, days, mins = 0, 0, set(), np.zeros(1440)
    first = last = None
    for df in _chunks(path, root, tz):
        if df.empty:
            continue
        rows += len(df)
        quoted += int((df.bid > 0).sum())
        et = pd.to_datetime(df.t_ns, utc=True).dt.tz_convert(ET)
        np.add.at(mins, (et.dt.hour * 60 + et.dt.minute).values, df["size"].values)
        first = first if first is not None else et.iloc[0]
        last = et.iloc[-1]
        days.update(os.path.basename(p).split(".")[0] for p in write_days(df))
    top = int(mins.argmax()) if rows else 0
    good = rows and (570 <= top <= 575 or 510 <= top <= 515)
    return {"file": os.path.basename(path), "root": root, "rows": rows, "days": len(days),
            "first_et": str(first)[:19] if first is not None else None, "last_et": str(last)[:19] if last is not None else None,
            "tz_check": ("OK" if good else "CHECK --tz:") + " busiest minute %02d:%02d ET" % (top // 60, top % 60) if rows else "no rows",
            "with_bid_ask%": round(100.0 * quoted / rows, 1) if rows else 0.0,
            "tick_days_total": len(days_available())}


def default_export_dir() -> str | None:
    nd = nt_dir()
    return os.path.join(nd, REC_DIR, "export") if nd else None


def tz_check(df: pd.DataFrame) -> str:
    """The busiest ET minute-of-day should be 09:30-09:35 (the cash open). Anything else = wrong --tz."""
    if df.empty:
        return "no rows"
    et = pd.to_datetime(df.t_ns, utc=True).dt.tz_convert(ET)
    mod = (et.dt.hour * 60 + et.dt.minute)
    top = int(df.groupby(mod.values)["size"].sum().idxmax())
    ok = 9 * 60 + 30 <= top <= 9 * 60 + 35 or 8 * 60 + 30 <= top <= 8 * 60 + 35     # 08:30 = US data days
    return "%s busiest minute %02d:%02d ET" % ("OK" if ok else "CHECK --tz:", top // 60, top % 60)


# ------------------------------------------------------------------------------------------------------------ bars (for research)
def footprint(df: pd.DataFrame, minutes: int = 5) -> pd.DataFrame:
    """Per bar: o h l c, volume, delta (sum size*side), cumulative delta, POC (price with most volume), buy/sell volume."""
    if df.empty:
        return pd.DataFrame()
    t = pd.to_datetime(df.t_ns, utc=True)
    k = t.dt.floor("%dmin" % minutes)
    d = df.assign(bar=k.values, sv=df["size"] * df.side)
    g = d.groupby("bar")
    out = pd.DataFrame({"open": g.price.first(), "high": g.price.max(), "low": g.price.min(), "close": g.price.last(),
                        "volume": g["size"].sum(), "delta": g.sv.sum(),
                        "buy": d[d.side > 0].groupby("bar")["size"].sum(), "sell": d[d.side < 0].groupby("bar")["size"].sum()})
    pv = d.groupby(["bar", "price"])["size"].sum().reset_index()
    out["poc"] = pv.loc[pv.groupby("bar")["size"].idxmax()].set_index("bar")["price"]
    out = out.fillna({"buy": 0, "sell": 0})
    out["cvd"] = out.delta.cumsum()
    return out


# ------------------------------------------------------------------------------------------------------------ CLI
def status() -> dict:
    nd = nt_dir()
    return {"enabled": is_enabled(), "config": _cfg(), "nt_dir": nd, "parquet": _has_pyarrow(), "tick_dir": TICK_DIR,
            "days": len(days_available()), "first": (days_available() or [None])[0], "last": (days_available() or [None])[-1],
            "recorder_flag": bool(nd and os.path.exists(os.path.join(nd, REC_DIR, "enabled.txt"))),
            "recorder": recorder_status(nd) if nd else {}}


def selftest() -> bool:
    import tempfile
    global TICK_DIR
    keep = TICK_DIR
    with tempfile.TemporaryDirectory() as tmp:
        TICK_DIR = os.path.join(tmp, "ticks")
        s = classify([100.25, 100.0, 100.0, 100.5, 100.25], [100.0, 100.0, 0, 100.25, 100.0], [100.25, 100.25, 0, 100.5, 100.5])
        assert list(s) == [1, -1, -1, 1, -1], s
        exp = os.path.join(tmp, "nt.txt")
        with open(exp, "w") as f:
            f.write("20261120 093000 0000000;21000.25;21000;21000.25;3\n20261120 093000 5000000;21000;21000;21000.25;2\nbad\n")
        df = parse_nt_export(exp, "NQ", "America/New_York")
        assert len(df) == 2 and list(df.side) == [1, -1]
        assert pd.Timestamp(int(df.t_ns.iloc[0]), tz="UTC").tz_convert(ET).strftime("%H:%M") == "09:30"
        write_days(df); write_days(df)
        assert len(read_day("2026-11-20")) == 2
        fp = footprint(df, 5)
        assert int(fp.delta.iloc[0]) == 1 and float(fp.poc.iloc[0]) == 21000.25
        TICK_DIR = keep
    print("tickrec selftest OK (parquet=%s)" % _has_pyarrow())
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.tickrec", description="read-only NQ/ES tick recorder")
    ap.add_argument("cmd", choices=["status", "enable", "disable", "ingest", "run", "import", "selftest", "autopilot"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--root", default=None, help="default: from the file name (NQ 12-25.Last.txt -> NQ)")
    ap.add_argument("--roots", default="NQ,ES")
    ap.add_argument("--tz", default="UTC", help="NT8 exports are UTC; change only for other sources")
    ap.add_argument("--every", type=int, default=60)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=1))
    elif a.cmd == "enable":
        print(json.dumps(set_enabled(True, a.roots.split(",")), indent=1))
    elif a.cmd == "disable":
        print(json.dumps(set_enabled(False, a.roots.split(",")), indent=1))
    elif a.cmd == "ingest":
        print(json.dumps(ingest(), indent=1))
    elif a.cmd == "run":
        while True:
            if not is_enabled():
                print("tickrec: OFF (python -m engine.tickrec enable)"); return 0
            print(json.dumps(ingest()))
            time.sleep(max(10, a.every))
    elif a.cmd == "import":
        src = a.file or default_export_dir()
        if not src or not os.path.exists(src):
            ap.error("no file: pass the exported .txt (or a folder of them); default folder %s" % default_export_dir())
        files = sorted(glob.glob(os.path.join(src, "*.txt"))) if os.path.isdir(src) else [src]
        for fp in files:
            print(json.dumps(import_file(fp, a.root, a.tz)))
        print("done: %d tick days on disk (the study needs 60): python research/orderflow/of_study.py" % len(days_available()))
    elif a.cmd == "autopilot":
        print(json.dumps(autopilot(), default=str))
    elif a.cmd == "selftest":
        return 0 if selftest() else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
