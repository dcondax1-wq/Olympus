"""Readiness dry-run for importing 2025 (or any older) NQ 1-minute bars: runs the real importer (data/import_futures.py
_finish, the same code the dashboard's TradingView import uses) on a COPY of data/ in a temp folder and reports what the
import would do. data/ is never written.

    python -X utf8 tools/import_1m_dryrun.py                       # self-test: cut Feb 2026 out of a copy, import it back
    python -X utf8 tools/import_1m_dryrun.py data/tv_exports/NQ1_1m_2025_*.csv     # the owner's real 2025 exports
    python -X utf8 tools/import_1m_dryrun.py --json out.json ...

Checks (each OK / WARN / FIX):
  source      each file parses as a TradingView "Export chart data" CSV, 1-minute spacing, ET range
  price space the importer's own guard: the 1m bars (back-adjusted by data/NQ_rolls.json) land within 5 pts of the 5m bars
              on file, session by session; a back-adjusted (B-ADJ on) export or a wrong contract is refused here
  5m rewrite  a 1m import also rewrites NQ_5m/15m/1h on the same days (imported data wins): how many 5m bars change, and
              by how much (the 2021-25 reference line moves if they do)
  coverage    days whose 5m windows are >= 97% covered by clean 1m windows (engine/lit.bars_1m's rule): only those days
              execute on 1m in the backtest; the rest stay on 5m
  cache       research/runs/_cache keys on the NQ_5m.csv size only (tools/runlib._data_key): when the import leaves the 5m
              file the same size, cached LIT replays would not see the new 1m bars -> clear the cache after the import
Doc: research/IMPORT_1M_2025.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import shutil
import sys
import tempfile
import contextlib
import io

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data"))
DATA = os.path.join(ROOT, "data")
OK, WARN, BAD = "ok", "warn", "fix"
COVER = 0.97
SIM_FROM, SIM_TO = "2026-02-01", "2026-03-01"


def _et(t):
    return pd.to_datetime(t, unit="s", utc=True).dt.tz_convert("America/New_York")


def _sday(t):
    return (_et(pd.Series(t)) + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d").to_numpy()


def _copy_data(tmp):
    for f in ("NQ_1m.csv", "NQ_5m.csv", "NQ_15m.csv", "NQ_1h.csv", "NQ_rolls.json", "NQ_imported_days.json"):
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            shutil.copy(p, tmp)


def coverage(one, five):
    """{day: share of 5m windows with a clean complete 1m window} (engine/data._clean_1m, engine/lit.bars_1m cover rule)."""
    from engine.data import _clean_1m
    c = _clean_1m(one[["time", "open", "high", "low", "close", "volume"]].copy())
    have = set(c["bucket"].unique()) if len(c) else set()
    f = five[["time"]].copy()
    f["day"] = _sday(f["time"])
    f["ok"] = f["time"].isin(have)
    g = f.groupby("day")["ok"].mean()
    return g


def run(files=None):
    import import_futures as IF
    rep = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "mode": "files" if files else "self-test", "items": []}
    add = lambda lvl, what, text: rep["items"].append({"level": lvl, "what": what, "text": text})  # noqa: E731
    tmp = tempfile.mkdtemp(prefix="le_1m_dry_")
    try:
        _copy_data(tmp)
        one0 = pd.read_csv(os.path.join(tmp, "NQ_1m.csv"))
        five0 = pd.read_csv(os.path.join(tmp, "NQ_5m.csv"))
        if files:
            parts = []
            for p in files:
                try:
                    fr = IF._frame_from_table(pd.read_csv(p))
                    src = IF.detect_interval(fr["time"])
                    e = _et(fr["time"])
                    add(OK if src == 60 else BAD, "source " + os.path.basename(p),
                        f"{len(fr):,} bars @ {src}s, {e.min():%Y-%m-%d %H:%M} -> {e.max():%Y-%m-%d %H:%M} ET"
                        + ("" if src == 60 else " (not a 1-minute export: set the chart to 1m before exporting)"))
                    if src == 60:
                        parts.append(fr)
                except Exception as ex:                      # noqa: BLE001
                    add(BAD, "source " + os.path.basename(p), f"cannot read: {ex}")
            if not parts:
                add(BAD, "import", "no usable 1-minute file")
                return rep
            inc = pd.concat(parts).sort_values("time").drop_duplicates("time", keep="last")
            raw_inc = inc                                   # TradingView raw front month (B-ADJ off): the importer back-adjusts
        else:
            # self-test: cut a month of real 1m bars out of the copy, then import them back as if they were a new export.
            # NQ_1m.csv is already back-adjusted; the importer adds the roll gaps again, so undo them first (= a raw export)
            a, z = (int(pd.Timestamp(x, tz="America/New_York").timestamp()) for x in (SIM_FROM, SIM_TO))
            cut = one0[(one0["time"] >= a) & (one0["time"] < z)].copy()
            rest = one0[(one0["time"] < a) | (one0["time"] >= z)]
            rest.to_csv(os.path.join(tmp, "NQ_1m.csv"), index=False)
            raw_inc = cut.copy()
            for r in IF.load_rolls("NQ", tmp):
                pre = raw_inc["time"] < int(r["switch_t"])
                for col in ("open", "high", "low", "close"):
                    raw_inc.loc[pre, col] = raw_inc.loc[pre, col] - float(r["gap"])
            add(OK, "source (self-test)", f"{len(cut):,} real 1m bars {SIM_FROM} -> {SIM_TO} cut from the copy and re-imported")
        # the import itself, on the copy
        log = io.StringIO()
        try:
            with contextlib.redirect_stdout(log):
                src = IF._finish("NQ", raw_inc.copy(), out_dir=tmp)
            add(OK, "price space", "the importer accepted the bars (within 5 pts of the 5m file per session); "
                + " | ".join(x.strip() for x in log.getvalue().splitlines() if x.strip())[:300])
        except ValueError as ex:
            add(BAD, "price space", str(ex))
            return rep
        one1 = pd.read_csv(os.path.join(tmp, "NQ_1m.csv"))
        five1 = pd.read_csv(os.path.join(tmp, "NQ_5m.csv"))
        if not files:
            m = cut.merge(one1, on="time", suffixes=("", "_n"))
            same = bool(len(m) == len(cut) and np.allclose(m[["open", "high", "low", "close"]].to_numpy(),
                                                          m[["open_n", "high_n", "low_n", "close_n"]].to_numpy()))
            add(OK if same else BAD, "round trip", f"{len(m):,} of {len(cut):,} bars back, prices {'identical' if same else 'DIFFERENT'}")
        new_t = set(raw_inc["time"])
        if files:
            add(OK, "new bars", f"{len(set(one1['time']) - set(one0['time'])):,} of {len(new_t):,} incoming 1m bars are new to NQ_1m.csv")
        days = sorted(set(_sday(np.array(sorted(new_t))))) if new_t else []
        # 5m rewrite
        mm = five0.merge(five1, on="time", suffixes=("_o", "_n"))
        d = (mm["close_n"] - mm["close_o"]).abs()
        ch = mm[(d > 1e-9) | ((mm["high_n"] - mm["high_o"]).abs() > 1e-9) | ((mm["low_n"] - mm["low_o"]).abs() > 1e-9)]
        add(OK if len(ch) <= 0.01 * max(1, len(days)) * 276 else WARN, "5m rewrite",
            f"{len(ch):,} 5m bars change on {len(set(_sday(ch['time'].to_numpy()))) if len(ch) else 0} days "
            f"(max close change {d.max() if len(d) else 0:.2f} pts); {len(five1) - len(five0):+,} 5m bars added")
        # coverage
        if days:
            cov = coverage(one1, five1)
            cv = cov[cov.index.isin(days)]
            good = int((cv >= COVER).sum())
            add(OK if good >= 0.9 * len(cv) else WARN, "coverage",
                f"{good} of {len(cv)} imported days have >= {COVER:.0%} of their 5m windows in clean 1m bars (they will run on 1m)"
                + (f"; lowest {cv.idxmin()} {cv.min():.0%}" if len(cv) else ""))
            yrs = sorted({x[:4] for x in days})
            rep["days"] = {"n": len(days), "from": days[0], "to": days[-1], "years": yrs, "on_1m": good}
        # cache
        same_size = os.path.getsize(os.path.join(tmp, "NQ_5m.csv")) == os.path.getsize(os.path.join(DATA, "NQ_5m.csv"))
        add(WARN if same_size else OK, "cache",
            "NQ_5m.csv keeps its size: cached LIT replays (research/runs/_cache, key = 5m file size) would NOT see the new 1m "
            "bars - delete research/runs/_cache/litfinal_*.pkl and lit_2wk_unit_*.json after the real import"
            if same_size else "NQ_5m.csv changes size: the replay caches rebuild by themselves (still: rerun the runs you quote)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rep


def render(rep):
    tag = {OK: " OK ", WARN: "WARN", BAD: "FIX "}
    L = [f"1m import dry-run ({rep['mode']}) {rep['built']} - data/ untouched"]
    L += [f"  [{tag[i['level']]}] {i['what']}: {i['text']}" for i in rep["items"]]
    nb = sum(1 for i in rep["items"] if i["level"] == BAD)
    L.append("READY: the real import can run (see research/IMPORT_1M_2025.md)" if not nb else f"NOT READY: {nb} item(s) to fix")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    files = [f for p in a.files for f in sorted(glob.glob(p))] if a.files else None
    rep = run(files)
    print(render(rep))
    if a.json:
        json.dump(rep, open(a.json, "w", encoding="utf-8"), indent=1)
    return 1 if any(i["level"] == BAD for i in rep["items"]) else 0


if __name__ == "__main__":
    sys.exit(main())
