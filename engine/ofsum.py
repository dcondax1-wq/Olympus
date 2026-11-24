"""Order-flow day summaries (day-ofready 2026-11-24, READ-ONLY): data/ticks/<day> -> a few small files the cloud can test with.

Why: the tick files (engine/tickrec.py, data/ticks/YYYY-MM-DD.parquet, ET calendar days) are far too big for the PC -> cloud path
(engine/datafeed.py: one ntfy attachment of <= 1.85 MB, 8 answers a day), and raw CME ticks should not leave the PC anyway.
Every pre-registered order-flow test (research/orderflow/DESIGN.md, PREREG_ticks.md) only needs per-5m-bar numbers, the
footprint (volume at each price, split by aggressor side) and the big single prints per bar. So the PC writes, per ET day:

  of/NQ_bars5m.csv.gz   t (bar open, unix s), o, h, l, c, vol, buy, sell, unk, n
  of/NQ_fp5m.csv.gz     bar (row number in NQ_bars5m), k (ticks above that bar's low), b (sell vol), a (buy vol), u (no side)
  of/NQ_meta.json       day, rows, t0/t1, size histogram 1..199 + 200+, side source shares, filled_in, block_th
Bars also carry signed block volume (sum of size x side of single trades >= a size): b10 / b20 / b50 (fixed sizes) and bth
(>= block_th = the 99.5th pct of trade size over the 5 previous tick days, PREREG_ticks OF2, computed here from their meta
files; empty when fewer than 3 previous days exist). So no trade-level tape leaves the PC: only 5-minute aggregates.

About 30-80 KB a day gzip'd (selftest prints the size of a synthetic 300k-trade day). Market data only: no account, no
balance, no path, nothing from the bot.

SAFETY: reads data/ticks only, writes only under the folder it is given (default logs/datapipe/days/<day>/of/). Imports nothing
that can trade (no engine.ninjatrader / live / tradovate / lit_live). Nothing in the bot imports this module.

    python -X utf8 -m engine.ofsum build [--days 60] [--out logs/datapipe/days]   # every tick day missing its summary
    python -X utf8 -m engine.ofsum selftest
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25
HIST_MAX = 200
VERSION = 1
NAMES = ("NQ_bars5m.csv.gz", "NQ_fp5m.csv.gz", "NQ_meta.json")
BLOCK_PCT, BLOCK_DAYS = 99.5, 5          # frozen: research/orderflow/PREREG_ticks.md OF2
OUT_DEFAULT = os.path.join(ROOT, "logs", "datapipe", "days")


def _gz_csv(df: pd.DataFrame) -> bytes:
    raw = df.to_csv(index=False, lineterminator="\n").encode("ascii")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as g:
        g.write(raw)
    return buf.getvalue()


def pick_root(x: pd.DataFrame) -> pd.DataFrame:
    for r in ("NQ", "MNQ"):
        y = x[x.root == r]
        if len(y):
            return y
    return x.iloc[0:0]


def side_quality(x: pd.DataFrame) -> dict:
    """Share of volume whose side came from the quote rule (a real bid/ask at the trade) vs the tick rule."""
    from . import tickrec
    p, b, a, v = (x[c].to_numpy(float) for c in ("price", "bid", "ask", "size"))
    filled = bool(tickrec.quotes_filled_in(p, b, a))
    okq = (b > 0) & (a > 0) & (a >= b) & ((p >= a) | (p <= b))
    if filled:
        okq[:] = False
    tot = float(v.sum()) or 1.0
    unk = float(v[x.side.to_numpy() == 0].sum())
    return {"quote_rule": round(float(v[okq].sum()) / tot, 4), "unknown": round(unk / tot, 4),
            "tick_rule": round(max(0.0, 1.0 - float(v[okq].sum()) / tot - unk / tot), 4), "filled_in": filled}


def summarize(x: pd.DataFrame, day: str, block_th: float | None = None) -> dict:
    """One ET day of ticks (engine.tickrec columns) -> {file name: bytes}. Empty dict when the day has no NQ / MNQ trades."""
    x = pick_root(x)
    if x.empty:
        return {}
    x = x.sort_values("t_ns", kind="stable").reset_index(drop=True)
    t_ns = x.t_ns.to_numpy(np.int64)
    px = x.price.to_numpy(float)
    sz = x["size"].to_numpy(np.int64)
    sd = x.side.to_numpy(np.int64)
    pk = np.rint(px / TICK).astype(np.int64)                     # price in ticks
    bar_t = (t_ns // 10**9) // 300 * 300
    ub, bi = np.unique(bar_t, return_inverse=True)
    nb = len(ub)
    idx = np.arange(len(px))
    first = pd.Series(idx).groupby(bi).first().to_numpy()
    last = pd.Series(idx).groupby(bi).last().to_numpy()
    hi = pd.Series(pk).groupby(bi).max().to_numpy(); lo = pd.Series(pk).groupby(bi).min().to_numpy()
    vol = np.bincount(bi, weights=sz, minlength=nb)
    buy = np.bincount(bi, weights=sz * (sd > 0), minlength=nb)
    sell = np.bincount(bi, weights=sz * (sd < 0), minlength=nb)
    n = np.bincount(bi, minlength=nb)
    bars = pd.DataFrame({"t": ub, "o": px[first], "h": hi * TICK, "l": lo * TICK, "c": px[last], "vol": vol.astype(np.int64),
                         "buy": buy.astype(np.int64), "sell": sell.astype(np.int64),
                         "unk": (vol - buy - sell).astype(np.int64), "n": n.astype(np.int64)})
    for lab, th in (("b10", 10), ("b20", 20), ("b50", 50), ("bth", block_th)):
        if th is None:
            bars[lab] = ""
        else:
            m = sz >= th
            bars[lab] = np.bincount(bi[m], weights=(sz * sd)[m], minlength=nb).astype(np.int64)
    k = pk - lo[bi]
    f = pd.DataFrame({"bar": bi, "k": k, "b": sz * (sd < 0), "a": sz * (sd > 0), "u": sz * (sd == 0)})
    fp = f.groupby(["bar", "k"], sort=True)[["b", "a", "u"]].sum().reset_index()
    hist = np.bincount(np.minimum(sz, HIST_MAX), minlength=HIST_MAX + 1)[1:]
    meta = {"v": VERSION, "day": day, "root": str(x.root.iloc[0]), "rows": int(len(x)), "t0_ns": int(t_ns[0]),
            "t1_ns": int(t_ns[-1]), "tick": TICK, "block_th": block_th, "block_rule": "99.5th pct of size, 5 prior tick days (>= 3)",
            "size_hist": [int(v) for v in hist], "size_hist_note": "counts of trades of size 1..199, last = 200+",
            "sides": side_quality(x), "bars": int(nb), "fp_rows": int(len(fp))}
    return {"NQ_bars5m.csv.gz": _gz_csv(bars), "NQ_fp5m.csv.gz": _gz_csv(fp),
            "NQ_meta.json": json.dumps(meta, separators=(",", ":")).encode("utf-8")}


def hist_percentile(hists, q):
    """np.percentile(all trade sizes of these days, q) (linear) from size histograms 1..199, 200+ -> (value, in the 200+ bucket)."""
    h = np.sum(np.array(hists, dtype=np.int64), axis=0)
    n = int(h.sum())
    if n == 0:
        return None, True
    cum = np.cumsum(h)
    pos = (n - 1) * q / 100.0
    lo, hi = int(np.floor(pos)), int(np.ceil(pos))
    v_lo = int(np.searchsorted(cum, lo + 1)) + 1
    v_hi = int(np.searchsorted(cum, hi + 1)) + 1
    return float(v_lo + (v_hi - v_lo) * (pos - lo)), v_hi >= len(h)


def block_threshold(day: str, out_root: str = OUT_DEFAULT, metas: dict | None = None):
    """OF2's frozen threshold for `day` from the meta files of the 5 previous tick days (>= 3 needed), else None."""
    if metas is None:
        metas = {}
        for p in sorted(os.listdir(out_root)) if os.path.isdir(out_root) else []:
            mp = os.path.join(out_root, p, "of", "NQ_meta.json")
            if p < day and os.path.exists(mp):
                try:
                    metas[p] = json.load(open(mp, encoding="utf-8"))
                except (OSError, ValueError):
                    pass
    prev = sorted(d for d in metas if d < day)[-BLOCK_DAYS:]
    if len(prev) < 3:
        return None
    v, _ = hist_percentile([metas[d]["size_hist"] for d in prev], BLOCK_PCT)
    return v


def write_day(day: str, out_root: str = OUT_DEFAULT, x: pd.DataFrame | None = None, force: bool = False) -> dict:
    """Write days/<day>/of/* (atomic per file). Returns {"day", "ok", "bytes"} and never raises."""
    try:
        d = os.path.join(out_root, day, "of")
        if not force and all(os.path.exists(os.path.join(d, nm)) for nm in NAMES):
            return {"day": day, "ok": True, "skipped": True}
        if x is None:
            from . import tickrec
            x = tickrec.read_day(day)
        if x is None:
            return {"day": day, "ok": False, "why": "no tick file"}
        files = summarize(x, day, block_threshold(day, out_root))
        if not files:
            return {"day": day, "ok": False, "why": "no NQ trades"}
        os.makedirs(d, exist_ok=True)
        for nm, b in files.items():
            p = os.path.join(d, nm)
            with open(p + ".tmp", "wb") as fh:
                fh.write(b)
            os.replace(p + ".tmp", p)
        return {"day": day, "ok": True, "bytes": sum(len(b) for b in files.values())}
    except Exception as e:                                                 # never raise into a caller (nightly task)
        return {"day": day, "ok": False, "why": f"{e.__class__.__name__}: {str(e)[:120]}"}


def build(days_back: int = 400, out_root: str = OUT_DEFAULT) -> list:
    from . import tickrec
    return [write_day(d, out_root) for d in tickrec.days_available()[-days_back:]]     # oldest first: thresholds see earlier metas


# ------------------------------------------------------------------------------------------------ cloud-side reader
def read(day_dir: str) -> dict | None:
    """days/<day>/of folder -> {"bars": DataFrame, "fp": DataFrame, "meta": dict} or None."""
    try:
        d = os.path.join(day_dir, "of") if os.path.basename(day_dir.rstrip("/\\")) != "of" else day_dir
        meta = json.load(open(os.path.join(d, "NQ_meta.json"), encoding="utf-8"))
        bars = pd.read_csv(os.path.join(d, "NQ_bars5m.csv.gz"))
        fp = pd.read_csv(os.path.join(d, "NQ_fp5m.csv.gz"))
        return {"bars": bars, "fp": fp, "meta": meta}
    except (OSError, ValueError, KeyError):
        return None


# ------------------------------------------------------------------------------------------------ selftest
def synth_day(day: str = "2026-11-02", n: int = 300_000, seed: int = 1, quotes: bool = True) -> pd.DataFrame:
    """A synthetic NQ ET day (random walk, NQ-like size mix) for tests; never written to data/."""
    rng = np.random.default_rng(seed)
    t0 = int(pd.Timestamp(day + " 00:00", tz="America/New_York").tz_convert("UTC").value)
    t = np.sort(rng.integers(0, 24 * 3600 * 10**9, n)) + t0
    steps = rng.choice([-1, 0, 0, 0, 1], n)
    pk = 100_000 + np.cumsum(steps)
    price = pk * TICK
    size = np.where(rng.random(n) < 0.97, rng.integers(1, 4, n), rng.integers(4, 120, n))
    side = np.where(rng.random(n) < 0.5, 1, -1)
    bid = np.where(side > 0, price - TICK, price) if quotes else np.zeros(n)
    ask = np.where(side > 0, price, price + TICK) if quotes else np.zeros(n)
    return pd.DataFrame({"t_ns": t, "root": "NQ", "price": price, "size": size, "bid": bid, "ask": ask, "side": side.astype(np.int8)})


def selftest() -> bool:
    import tempfile
    x = synth_day()
    files = summarize(x, "2026-11-02")
    ok = set(files) == set(NAMES)
    with tempfile.TemporaryDirectory() as td:
        r = write_day("2026-11-02", td, x=x)
        R = read(os.path.join(td, "2026-11-02"))
        ok = ok and r["ok"] and R is not None
        b, fp, m = R["bars"], R["fp"], R["meta"]
        ok = ok and int(b.vol.sum()) == int(x["size"].sum()) == int(fp[["b", "a", "u"]].sum().sum())
        d = (x["size"] * x.side).sum()
        ok = ok and int((b.buy - b.sell).sum()) == int(d) and int((fp.a - fp.b).sum()) == int(d)
        ok = ok and sum(m["size_hist"]) == len(x) and int(b.b20.sum()) == int((x["size"] * x.side)[x["size"] >= 20].sum())
        ok = ok and m["sides"]["quote_rule"] > 0.99
        # footprint reproduces each bar's extreme
        mx = fp.groupby("bar").k.max().to_numpy() * TICK + b.l.to_numpy()
        ok = ok and np.allclose(mx, b.h.to_numpy())
    sizes = {k: len(v) for k, v in files.items()}
    print("ofsum selftest:", "OK" if ok else "FAIL", "| synthetic 300k-trade day ->", sizes, "total", sum(sizes.values()), "bytes")
    return bool(ok)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="engine.ofsum")
    ap.add_argument("cmd", choices=("build", "selftest"))
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    res = build(a.days, a.out)
    print(json.dumps({"days": len(res), "ok": sum(1 for r in res if r.get("ok")), "bytes": sum(r.get("bytes", 0) for r in res),
                      "failed": [r for r in res if not r.get("ok")][:5]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
