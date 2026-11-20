"""Replay harness for the PC bot's live loop timing (day-speed 2026-11-20). Research only: never routes to a broker.

Runs the REAL engine.live.LiveBot (paper adapter, frozen clock) with data_source "ninjatrader" on LE_BarFeed-format files
that grow bar by bar like on the PC (engine.ninjatrader.NinjaTraderBars reads them: the real parse, merge, clean path),
with engine.poll_timing installed. Pre-registered in research/speed/PREREG.md.

    python -X utf8 research/speed/replay_harness.py --days 2026-11-16,2026-11-17,2026-11-18 [--patch NAME ...] [--out f.json]

--patch names a read-only speed-up from research/speed/speedups.py, monkeypatched in this process only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

DATA = os.path.join(ROOT, "data")
ET = dt.timezone(dt.timedelta(hours=-5))          # November: EST
MAX1, MAX5, TRIM = 20000, 8000, 1000


def et_at(day: str, hh: int, mm: int) -> int:
    d = dt.datetime.strptime(day, "%Y-%m-%d").replace(hour=hh, minute=mm, tzinfo=ET)
    return int(d.timestamp())


def poll_times(days, offset=2.0):
    """Every minute 01:30-12:00 ET of each day, every 5 minutes from the previous 18:00 ET otherwise (+offset s)."""
    out = set()
    for d in days:
        t0 = et_at(d, 18, 0) - 86400
        for t in range(t0 + 300, et_at(d, 16, 0) + 1, 300):
            out.add(t)
        for t in range(et_at(d, 1, 30), et_at(d, 12, 0) + 1, 60):
            out.add(t)
    return [t + offset for t in sorted(out)]


class Feed:
    """LE_BarFeed-format files that grow as the replay clock moves (append-only, trimmed like LE_BarFeed)."""

    def __init__(self, folder, df1, df5, root="NQ"):
        self.folder, self.root = folder, root
        self.df1 = df1.reset_index(drop=True)
        self.df5 = df5.reset_index(drop=True)
        self.p1 = os.path.join(folder, f"{root}_1m.csv")
        self.p5 = os.path.join(folder, f"{root}_5m.csv")
        self.po = os.path.join(folder, f"{root}_1m_open.csv")
        self.i1 = self.i5 = 0
        self.n1 = self.n5 = 0
        self.o1 = dict(zip(self.df1["time"].astype("int64"), self.df1["open"].astype(float)))

    @staticmethod
    def _lines(df):
        return "".join(f"{int(r.time)},{r.open:g},{r.high:g},{r.low:g},{r.close:g},{int(r.volume)}\n" for r in df.itertuples())

    def _grow(self, path, df, i, n, secs, now, cap):
        j = int(df["time"].searchsorted(now - secs, side="right"))       # bars with time + secs <= now
        if j <= i:
            return i, n
        if i == 0:
            i = max(0, j - cap)
            n = 0
        chunk = df.iloc[i:j]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(self._lines(chunk))
        n += len(chunk)
        if n > cap + TRIM:                                                # LE_BarFeed's Trim(): keep the newest cap lines
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()[-cap:]
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
            n = cap
        return j, n

    def advance(self, now: int):
        self.i1, self.n1 = self._grow(self.p1, self.df1, self.i1, self.n1, 60, now, MAX1)
        self.i5, self.n5 = self._grow(self.p5, self.df5, self.i5, self.n5, 300, now, MAX5)
        m = now - now % 60
        if m in self.o1:
            with open(self.po, "w", encoding="utf-8") as fh:
                fh.write(f"{m},{self.o1[m]:g}\n")


def build(days, tmp):
    from engine import live
    hist_dir = os.path.join(tmp, "hist")
    nt_dir = os.path.join(tmp, "nt8")                           # the NinjaTrader 8 folder; LE_BarFeed writes nt8/le_feed/
    arc_dir = os.path.join(tmp, "nt_bars")
    for p in (hist_dir, os.path.join(nt_dir, "le_feed"), arc_dir):
        os.makedirs(p, exist_ok=True)
    start = et_at(days[0], 18, 0) - 86400
    cut = start - 10 * 86400                                     # the TradingView export lags the feed by ~10 days
    for name in ("NQ_5m", "NQ_1m", "NQ_15m", "NQ_1h", "NQ_1d", "ES_5m", "ES_15m", "ES_1h", "ES_1d"):
        src = os.path.join(DATA, f"{name}.csv")
        if os.path.exists(src):
            df = pd.read_csv(src)
            df[df["time"] < cut].to_csv(os.path.join(hist_dir, f"{name}.csv"), index=False)
    for extra in ("VIX_1d.csv", "VXN_1d.csv", "CBOE_vol_1d.csv", "GEX_1d.csv", "NQ_rolls.json", "ES_rolls.json"):
        if os.path.exists(os.path.join(DATA, extra)):
            shutil.copy(os.path.join(DATA, extra), hist_dir)
    df1 = pd.read_csv(os.path.join(DATA, "NQ_1m.csv"))
    df5 = pd.read_csv(os.path.join(DATA, "NQ_5m.csv"))
    df1 = df1[df1["time"] >= start - 30 * 86400]
    df5 = df5[df5["time"] >= start - 40 * 86400]
    feed = Feed(os.path.join(nt_dir, "le_feed"), df1, df5)
    live.DATA_DIR = hist_dir
    return feed, nt_dir, arc_dir, start


def run(days, patches=(), quiet=False, offset=2.0, cfg_extra=None):
    from engine import live, poll_timing
    from tests.test_live_dryrun import Replay
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import speedups as SU
    tmp = tempfile.mkdtemp(prefix="speed_replay_")
    old_dir = live.DATA_DIR
    rp = Replay()
    rp.install_globals()
    undo = []
    try:
        feed, nt_dir, arc_dir, start = build(days, tmp)
        for p in patches:
            undo.append(SU.apply(p))
        poll_timing.install()
        clock = {"now": start}
        bot = live.LiveBot()
        bot.clock = lambda: clock["now"]
        poll_timing.install(bot)
        bot.state_path = os.path.join(tmp, "live_state.json")
        feed.advance(start)
        cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "poll_sec": 60, "data_source": "ninjatrader", "no_yahoo": True,
               "nt_folder": nt_dir, "nt_archive": arc_dir, "nt_feed_roots": {"NQ": ["NQ"], "ES": ["ES"]}, **(cfg_extra or {})}
        r = bot.start(cfg, spawn=False)
        assert r.get("ok"), r
        rows, errors = [], []
        for t in poll_times(days, offset):
            clock["now"] = int(t)
            feed.advance(int(t))
            w0 = time.perf_counter()
            try:
                bot.poll_once()
            except Exception as e:                       # noqa: BLE001
                errors.append(f"{int(t)} {e.__class__.__name__}: {e}")
            wall = (time.perf_counter() - w0) * 1000
            ps = bot.health.get("poll_stages") or {}
            rows.append({"t": int(t), "wall_ms": round(wall, 1), "state": str((bot.state or {}).get("model_state"))[:80], "total_ms": ps.get("total_ms"), "lit_ms": ps.get("lit_ms"),
                         "stages": {s["name"]: s["ms"] for s in ps.get("stages") or []}})
        led = [{k: r.get(k) for k in ("side", "qty", "stop", "target", "entry_t", "pnl", "t", "reason", "px")}
               for r in bot.ledger]
        led_b = [{k: r.get(k) for k in ("side", "qty", "stop", "target", "entry_t", "pnl", "t", "reason", "key")}
                 for r in (getattr(bot.acct_b, "ledger", None) or [])] if getattr(bot, "acct_b", None) is not None else None
        sig = [l["text"] for l in reversed(list(bot.log)) if l.get("type") in ("order", "signal", "trade", "risk")]
        return {"days": list(days), "patches": list(patches), "polls": len(rows), "errors": errors[:10], "n_errors": len(errors),
                "ledger": led, "ledger_atlas": led_b, "signals": sig, "rows": rows}
    finally:
        for u in undo:
            u()
        live.DATA_DIR = old_dir
        rp.cleanup()
        shutil.rmtree(tmp, ignore_errors=True)


def summary(res):
    rows = [r for r in res["rows"] if r["total_ms"] is not None]
    per = {}
    for r in rows:
        for k, v in r["stages"].items():
            per.setdefault(k, []).append(v)
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(p * len(xs)))]     # noqa: E731
    tot = [r["wall_ms"] for r in rows]
    lit = [r["lit_ms"] for r in rows if r["lit_ms"] is not None]
    out = {"polls": len(rows), "wall_median_ms": round(statistics.median(tot), 1), "wall_p90_ms": q(tot, 0.9),
           "lit_median_ms": statistics.median(lit) if lit else None, "lit_p90_ms": q(lit, 0.9) if lit else None,
           "stages": sorted(({"name": k, "median_ms": statistics.median(v), "p90_ms": q(v, 0.9), "n": len(v)}
                             for k, v in per.items()), key=lambda s: -s["median_ms"])}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default="2026-11-16,2026-11-17,2026-11-18")
    ap.add_argument("--patch", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--atlas", action="store_true", help="also ATLAS (account B, paper, its 3 live members, builder25k)")
    ap.add_argument("--offset", type=float, default=2.0, help="seconds after each minute the poll runs (2.0 = today; 0.2 = fast entry)")
    a = ap.parse_args(argv)
    extra = {"account_b": {"account": "SimATLAS", "plan": "builder25k", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"],
                           "sizing": "need"}} if a.atlas else None
    res = run(a.days.split(","), a.patch, offset=a.offset, cfg_extra=extra)
    s = summary(res)
    print(json.dumps({"polls": s["polls"], "errors": res["n_errors"], "wall_median_ms": s["wall_median_ms"],
                      "wall_p90_ms": s["wall_p90_ms"], "lit_median_ms": s["lit_median_ms"], "ledger": len(res["ledger"]),
                      "ledger_atlas": None if res.get("ledger_atlas") is None else len(res["ledger_atlas"])}))
    for st in s["stages"][:14]:
        print(f"  {st['median_ms']:>7} ms med  {st['p90_ms']:>7} p90  x{st['n']:<5} {st['name']}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({**res, "summary": s}, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
