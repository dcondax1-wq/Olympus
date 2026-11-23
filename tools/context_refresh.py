"""CONTEXT REFRESH (night-cleanup 2026-11-22): the daily context files Claude's research reads, refreshed in the cloud.

Why they went stale: data/CBOE_vol_1d.csv (VIX9D / VIX3M / VIX1D / VVIX / SKEW) was a one-time research import (2026-09-17)
with no refresher at all, and data/GEX_1d.csv is refreshed only on the PC (engine/gamma.py), whose data/ never reaches the
cloud since the first GitHub account went (the PC pushes nothing; engine/generated_files keeps it out of the update check).
Both sources are free, public and answer from this cloud session: CBOE's own index history files (they moved from
cdn.cboe.com to cdn-api.cboe.com with a 307 in Nov 2026) and SqueezeMetrics' DIX.csv. No Yahoo, no CFD, no key, no paid service.

    python tools/context_refresh.py            # CBOE vol + VIX / VXN + GEX, append-only (data_pull.py runs it after an import)
    python tools/context_refresh.py --dry-run  # what it would add, nothing written

Append-only like news._cboe_daily: the source's rows win only for the last 10 stored dates (a partial row gets its final close)
and every newer date is added; older stored rows are never rewritten; a failed or odd download keeps the file as it is.
Test: python -X utf8 -m tests.test_context_refresh (fakes, no network).
"""
from __future__ import annotations

import csv
import io
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CBOE_URLS = ("https://cdn-api.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv",
             "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv")
GEX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
VOL_COLS = (("vix9d", "VIX9D"), ("vix3m", "VIX3M"), ("vix1d", "VIX1D"), ("vvix", "VVIX"), ("skew", "SKEW"))
KEEP_REWRITE = 10


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def cboe_closes(raw: bytes) -> dict:
    """CBOE history file -> {YYYY-MM-DD: close}. Both shapes: DATE,OPEN,HIGH,LOW,CLOSE and DATE,<NAME> (VVIX, SKEW)."""
    out = {}
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8", "replace"))))
    if not rows or rows[0][0].strip().upper() != "DATE":
        raise ValueError("not a CBOE history file")
    head = [h.strip().upper() for h in rows[0]]
    ci = head.index("CLOSE") if "CLOSE" in head else len(head) - 1
    for r in rows[1:]:
        if len(r) <= ci:
            continue
        try:
            m, d, y = r[0].strip().split("/")
            v = float(r[ci])
        except ValueError:
            continue
        if v > 0:
            out[f"{int(y):04d}-{int(m):02d}-{int(d):02d}"] = v
    return out


def cboe_fetch(name: str, fetch=None) -> dict:
    fetch = fetch or _get
    err = None
    for u in CBOE_URLS:
        try:
            got = cboe_closes(fetch(u.format(name=name)))
            if got:
                return got
        except Exception as e:  # noqa: BLE001
            err = e
    raise ValueError(f"CBOE {name}: no file ({err})")


def _read(path: str):
    if not os.path.exists(path):
        return None, []
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    return (rows[0], rows[1:]) if rows else (None, [])


def _eol(path: str) -> str:
    """The file's own line end (CBOE_vol_1d.csv is CRLF, GEX_1d.csv LF): a refresh never rewrites every old line."""
    try:
        with open(path, "rb") as fh:
            return "\r\n" if b"\r\n" in fh.read(4096) else "\n"
    except OSError:
        return "\n"


def _write(path: str, head, rows):
    tmp = path + ".tmp"
    eol = _eol(path)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator=eol)
        w.writerow(head)
        w.writerows(rows)
    os.replace(tmp, path)


def _fmt(v):
    if v is None:
        return ""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s


def refresh_cboe_vol(data_dir: str = DATA, fetch=None, dry: bool = False) -> str:
    """data/CBOE_vol_1d.csv: date,vix9d,vix3m,vix1d,vvix,skew. A series that fails keeps its stored values (blank on new days)."""
    path = os.path.join(data_dir, "CBOE_vol_1d.csv")
    head, rows = _read(path)
    head = head or ["date"] + [c for c, _n in VOL_COLS]
    got, bad = {}, []
    for col, name in VOL_COLS:
        try:
            got[col] = cboe_fetch(name, fetch)
        except Exception:  # noqa: BLE001
            bad.append(name)
    if not got:
        return "CBOE vol: no CBOE file answered; nothing changed"
    stored = {r[0]: r for r in rows if r}
    dates = sorted(stored)
    cut = dates[-KEEP_REWRITE] if len(dates) >= KEEP_REWRITE else ""
    last = dates[-1] if dates else ""
    new_days = sorted({d for s in got.values() for d in s if d > last})
    touched = 0
    for d in sorted(set(d for d in dates if d >= cut) | set(new_days)):
        old = stored.get(d) or [d] + [""] * (len(head) - 1)
        row = list(old) + [""] * (len(head) - len(old))
        for i, h in enumerate(head[1:], 1):
            v = (got.get(h) or {}).get(d)
            if v is not None:
                row[i] = _fmt(v)
        if any(x for x in row[1:]) and row != stored.get(d):
            stored[d] = row
            touched += 1
    if not touched:
        return f"CBOE vol: up to date ({last})" + (f"; no answer for {', '.join(bad)}" if bad else "")
    out = [stored[d] for d in sorted(stored)]
    if not dry:
        _write(path, head, out)
    return (f"CBOE vol: {'would add' if dry else '+'}{len(new_days)} day(s) to {out[-1][0]}" + (f" ({touched - len(new_days)} recent row(s) completed)" if touched > len(new_days) else "")
            + (f"; no answer for {', '.join(bad)}" if bad else ""))


def refresh_gex(data_dir: str = DATA, fetch=None, dry: bool = False) -> str:
    """data/GEX_1d.csv (date,price,dix,gex) from SqueezeMetrics' DIX.csv: append the newer dates, the last 10 refreshed."""
    path = os.path.join(data_dir, "GEX_1d.csv")
    try:
        raw = (fetch or _get)(GEX_URL).decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(raw)))
        if not rows or [h.strip().lower() for h in rows[0][:4]] != ["date", "price", "dix", "gex"]:
            raise ValueError("not the DIX.csv file")
        src = {r[0]: r[:4] for r in rows[1:] if len(r) >= 4 and len(r[0]) == 10 and r[0][4] == "-"}
    except Exception as e:  # noqa: BLE001
        return f"GEX: SqueezeMetrics did not answer ({e.__class__.__name__}); nothing changed"
    head, have = _read(path)
    head = head or ["date", "price", "dix", "gex"]
    stored = {r[0]: r for r in have if r}
    dates = sorted(stored)
    cut = dates[-KEEP_REWRITE] if len(dates) >= KEEP_REWRITE else ""
    last = dates[-1] if dates else ""
    new_days = [d for d in sorted(src) if d > last]
    touched = 0
    for d in [d for d in sorted(src) if d >= cut]:
        if src[d] != stored.get(d):
            stored[d] = src[d]
            touched += 1
    if not touched:
        return f"GEX: up to date ({last})"
    if not dry:
        _write(path, head, [stored[d] for d in sorted(stored)])
    return f"GEX: {'would add' if dry else '+'}{len(new_days)} day(s) to {max(stored)}"


def refresh_vix(data_dir: str = DATA, fetch=None, dry: bool = False) -> list:
    """VIX_1d / VXN_1d through engine/news._cboe_daily (the PC's own refresher), pointed at the files in data_dir."""
    out = []
    if dry:
        return ["VIX / VXN: skipped (dry run)"]
    try:
        from engine import news
    except Exception as e:  # noqa: BLE001
        return [f"VIX / VXN: engine.news not importable ({e.__class__.__name__})"]
    for name in ("VIX", "VXN"):
        p = os.path.join(data_dir, f"{name}_1d.csv")
        before = _read(p)[1][-1:] if os.path.exists(p) else []
        df = news._cboe_daily(name, p, fetch=fetch)
        last = str(df.index[-1]) if len(df) else "none"
        out.append(f"{name}: {'up to date' if before and before[0][0] == last else 'now to'} {last}")
    return out


def run(data_dir: str = DATA, fetch=None, dry: bool = False) -> list:
    lines = [refresh_cboe_vol(data_dir, fetch, dry), refresh_gex(data_dir, fetch, dry)]
    lines += refresh_vix(data_dir, fetch, dry)
    return lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for ln in run(dry="--dry-run" in argv):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
