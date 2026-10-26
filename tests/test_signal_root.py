"""signal_root: LIT decides on an NQ chart's bars while every order stays MNQ (engine/ninjatrader.py, default OFF).

    python -X utf8 -m tests.test_signal_root          (~1 min; temp folders only, fake NinjaTrader, no network)

research/writeups/mnq-vs-nq-feed.md: LIT is backtested on NQ1!; on MNQ bars a third of its setups differ. The option
reads an NQ chart's LE_BarFeed files (le_feed\\NQ_5m.csv, NQ_1m.csv, NQ_1m_open.csv, NQ_instrument.txt) for every
decision and keeps the order route on MNQ. Checks:
  1. the switch: live_model.json "signal_root" ships "MNQ"; cfg / LE_SIGNAL_ROOT / LE_LIVE_MODEL override it; anything
     else -> MNQ; nt_feed_roots (start cfg) wins over all of it.
  2. NinjaTraderBars with both charts' files: default -> every MNQ file (5m, 1m, 1m open, contract); NQ -> every NQ file;
     NQ chart missing -> MNQ as before; NQ 5m without NQ 1m -> no 1m (never MNQ 1m under NQ 5m); a stale NQ chart blocks
     (FEED STALE naming NQ_5m.csv), never a silent switch to MNQ.
  3. LiveBot (engine/live.py, paper, frozen clock): with NQ on, the merged 5m / 1m window = the NQ chart's bars and LIT's
     trades on it = LIT on the NQ bars (the backtest's own data); off -> the MNQ chart's bars.
  4. Orders: the NinjaTrader adapter with NQ on still names MNQ 12-26, the stop / target / qty it is given; the roll guard
     reads the NQ chart's contract (NQ 12-26 with MNQ 03-27 orders after Dec 10 -> refused; NQ 03-27 -> placed on MNQ 03-27).
  5. The heartbeat's bars (pcbars.PCBars, bot stopped) and HEALTH CHECK's feed lines follow the chart the bot reads.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import ninjatrader as N  # noqa: E402
from engine import pcbars  # noqa: E402
from engine.ninjatrader import ET, FEED_DIR, NinjaTraderBars  # noqa: E402

RES = []
COLS = ["time", "open", "high", "low", "close", "volume"]


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:600]) if not ok and info is not None else ''}", flush=True)
    RES.append(bool(ok))


def at(y, m, d, hh=0, mm=0, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


class Env:
    """Set / clear environment variables for a block."""

    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def write(folder, root, b1=None, b5=None, inst=None, open_=None):
    d = os.path.join(folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    if b5 is not None:
        b5[COLS].to_csv(os.path.join(d, f"{root}_5m.csv"), index=False)
    if b1 is not None:
        b1[COLS].to_csv(os.path.join(d, f"{root}_1m.csv"), index=False)
    if inst is not None:
        open(os.path.join(d, f"{root}_instrument.txt"), "w").write(inst)
    if open_ is not None:
        open(os.path.join(d, f"{root}_1m_open.csv"), "w").write(f"{open_[0]},{open_[1]}\n")


def synth(t0, n, secs, px=25000.0, seed=0):
    rng = np.random.default_rng(seed)
    t = t0 + np.arange(n) * secs
    c = px + np.cumsum(rng.normal(0, 2, n)).round(2)
    c = np.round(c * 4) / 4
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) + 1.0, "low": np.minimum(o, c) - 1.0, "close": c,
                       "volume": 100.0})
    e = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    return df[~((e.dt.hour == 17) & (e.dt.weekday < 5))].reset_index(drop=True)      # CME's daily break: no bars


# ------------------------------------------------------------------------------------------------ 1. the switch
def switch_checks():
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    lml = json.load(open(os.path.join(ROOT, "live_model_lit.json"), encoding="utf-8"))
    check("1. live_model.json and live_model_lit.json ship signal_root MNQ (default OFF)",
          lm.get("signal_root") == "MNQ" and lml.get("signal_root") == "MNQ", (lm.get("signal_root"), lml.get("signal_root")))
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None):
        check("1. default: MNQ, roots MNQ then NQ", N.signal_root() == "MNQ" and N.feed_roots()["NQ"] == ["MNQ", "NQ"],
              N.feed_roots())
        check("1. cfg signal_root nq -> NQ first", N.signal_root({"signal_root": "nq"}) == "NQ"
              and N.feed_roots({"signal_root": "NQ"})["NQ"] == ["NQ", "MNQ"])
        check("1. nonsense -> MNQ", N.signal_root({"signal_root": "ES"}) == "MNQ")
        check("1. start cfg nt_feed_roots wins", N.feed_roots({"nt_feed_roots": {"NQ": ["MNQ"]}, "signal_root": "NQ"}) == {"NQ": ["MNQ"]})
    with Env(LE_SIGNAL_ROOT="NQ"):
        check("1. LE_SIGNAL_ROOT=NQ -> NQ", N.signal_root() == "NQ" and NinjaTraderBars("x").roots["NQ"][0] == "NQ")
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=json.dumps({**lm, "signal_root": "NQ"})):
        check("1. live_model.json signal_root NQ (LE_LIVE_MODEL) -> NQ", N.signal_root() == "NQ")


# ------------------------------------------------------------------------------------------------ 2. the reader
def reader_checks(tmp):
    folder = os.path.join(tmp, "nt2")
    now = at(2026, 10, 21, 10, 0, 30)
    m5, m1 = synth(now - 3 * 86400 - 300, 864, 300), synth(now - 86400 - 60, 1440, 60, seed=1)
    q5 = m5.assign(**{c: m5[c] + 0.25 for c in ("open", "high", "low", "close")})
    q1 = m1.assign(**{c: m1[c] + 0.25 for c in ("open", "high", "low", "close")})
    t_open = now - now % 60
    write(folder, "MNQ", m1, m5, "MNQ 12-26", (t_open, 25001.0))
    write(folder, "NQ", q1, q5, "NQ 12-26", (t_open, 25001.25))
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None):
        f = NinjaTraderBars(folder)
        d5, _, _ = f.recent_bars("NQ", "5m", "2d", now=now)
        d1, _, _ = f.recent_bars("NQ", "1m", "1d", now=now)
        check("2. default: MNQ files (5m, 1m, 1m open, contract)", f.root_for("NQ") == "MNQ" and d5 is not None
              and float(d5["close"].iloc[-1]) == float(m5["close"].iloc[-1])
              and float(d1["close"].iloc[-1]) == float(m1["close"].iloc[-1])
              and f.forming_open("NQ", now=now) == (t_open, 25001.0) and f.chart_instrument("NQ") == "MNQ 12-26",
              (f.root_for("NQ"), f.forming_open("NQ", now=now), f.chart_instrument("NQ")))
    with Env(LE_SIGNAL_ROOT="NQ"):
        f = NinjaTraderBars(folder)
        d5, _, _ = f.recent_bars("NQ", "5m", "2d", now=now)
        d1, _, _ = f.recent_bars("NQ", "1m", "1d", now=now)
        check("2. NQ on: every NQ file (5m, 1m, 1m open, contract)", f.root_for("NQ") == "NQ"
              and float(d5["close"].iloc[-1]) == float(q5["close"].iloc[-1]) and float(d1["close"].iloc[-1]) == float(q1["close"].iloc[-1])
              and f.forming_open("NQ", now=now) == (t_open, 25001.25) and f.chart_instrument("NQ") == "NQ 12-26"
              and os.path.basename(f.file_for("NQ", 1)) == "NQ_1m.csv",
              (f.root_for("NQ"), f.forming_open("NQ", now=now), f.chart_instrument("NQ")))
        os.remove(os.path.join(folder, FEED_DIR, "NQ_1m.csv"))
        d1, why, _ = f.recent_bars("NQ", "1m", "1d", now=now)
        check("2. NQ 5m but no NQ 1m -> no 1m bars (never MNQ 1m under NQ 5m), the reason names NQ_1m.csv",
              d1 is None and "NQ_1m.csv" in why and f.file_for("NQ", 1) is None, why)
        write(folder, "NQ", q1)
        stale = now + 3600
        d5, why, _ = f.recent_bars("NQ", "5m", "2d", now=stale)
        write(folder, "MNQ", synth(now - 3 * 86400 - 300, 864 + 12, 300))
        d5b, whyb, _ = f.recent_bars("NQ", "5m", "2d", now=stale)
        check("2. stale NQ chart (fresh MNQ) -> FEED STALE on NQ_5m.csv, no silent switch to MNQ",
              d5 is None and d5b is None and "NQ_5m.csv is stale" in whyb, whyb)
        for n in ("NQ_5m.csv", "NQ_1m.csv", "NQ_1m_open.csv", "NQ_instrument.txt"):
            os.remove(os.path.join(folder, FEED_DIR, n))
        f = NinjaTraderBars(folder)
        d5, _, _ = f.recent_bars("NQ", "5m", "2d", now=now)
        check("2. NQ on but no NQ chart -> the MNQ chart, as before", f.root_for("NQ") == "MNQ" and d5 is not None
              and f.chart_instrument("NQ") == "MNQ 12-26" and f.forming_open("NQ", now=now) == (t_open, 25001.0))
    return folder


# ------------------------------------------------------------------------------------------------ 3. LiveBot + LIT
def livebot_checks(tmp):
    from tests import test_roll as R
    from engine import alerts, news
    alerts.send = lambda *a, **kw: None
    news.volatility = lambda *a, **kw: None
    news.ff_calendar = lambda: []
    nq5, nq1 = R.load("5m"), R.load("1m")                   # NQ1! (truth: the backtest's bars), from 2026-06-01
    # the MNQ chart: TradingView MNQ1! where it exists (real MNQ wicks), else NQ + a tick (a different feed either way)
    from tools.mnq_vs_nq import tv_mnq5
    tv, _ = tv_mnq5()
    mq5 = pcbars.tidy(pd.concat([R.plus(nq5, 0.25)[nq5.time < int(tv.time.min())], tv]))
    mq1 = R.plus(nq1, 0.25)
    tv_end = at(2026, 9, 25)
    hist5, hist1 = nq5[nq5.time < tv_end], nq1[nq1.time < tv_end]
    now = at(2026, 10, 15, 17, 0, 5)
    out = {}
    for lab, env in (("off", None), ("on", "NQ")):
        with Env(LE_SIGNAL_ROOT=env, LE_LIVE_MODEL=None):
            pc = R.PC(tmp, f"bot_{lab}", hist5, hist1)
            write(pc.folder, "MNQ", mq1[(mq1.time >= now - 14 * 86400) & (mq1.time + 60 <= now)],
                  mq5[(mq5.time >= now - 29 * 86400) & (mq5.time + 300 <= now)], "MNQ 12-26")
            write(pc.folder, "NQ", nq1[(nq1.time >= now - 14 * 86400) & (nq1.time + 60 <= now)],
                  nq5[(nq5.time >= now - 29 * 86400) & (nq5.time + 300 <= now)], "NQ 12-26")
            out[lab] = pc.poll(now)
    from engine.lit_live import window_start
    ws = window_start(now)
    (d5_on, d1_on), (d5_off, d1_off) = out["on"], out["off"]
    e_on, s_on, k_on = R.diff(d5_on, nq5, ws, now - 300)
    e1_on, s1_on, _ = R.diff(d1_on, nq1, now - 14 * 86400, now - 60)
    check(f"3. NQ on: the bot's LIT window = the NQ chart's bars (5m {k_on} bars, 1m) exactly", e_on < 1e-9 and s_on
          and e1_on < 1e-9 and s1_on, (e_on, s_on, e1_on, s1_on))
    feed_from = now - 29 * 86400
    e_off, s_off, _ = R.diff(d5_off, mq5, feed_from, now - 300)
    check("3. NQ off (default): the bot reads the MNQ chart's bars (as before)", e_off < 1e-9 and s_off, (e_off, s_off))
    t1 = nq1[nq1.time.isin(set(d1_on.time))]
    r_on, r_true = R.lit_run(d5_on, d1_on, now), R.lit_run(nq5[nq5.time < now], t1, now)
    k_on, k_true = R.trades_key(r_on), R.trades_key(r_true)
    check(f"3. LIT on the NQ-on bot's frames = LIT on the NQ bars ({len(k_true)} trades in the window: entries, stops, "
          "targets, exits)", k_on == k_true and len(k_true) >= 5, (k_on[-3:], k_true[-3:]))


# ------------------------------------------------------------------------------------------------ 4. orders
def order_checks():
    from tests.test_lit_add_safety import World
    with Env(LE_SIGNAL_ROOT="NQ"):
        w = World()
        fake = w.fake
        d = os.path.join(w.folder, FEED_DIR)
        os.makedirs(d, exist_ok=True)
        synth(int(w.now[0]) - 86400, 288, 300).to_csv(os.path.join(d, "NQ_5m.csv"), index=False)
        open(os.path.join(d, "NQ_instrument.txt"), "w").write("NQ 12-26")
        open(os.path.join(d, "MNQ_instrument.txt"), "w").write("MNQ 09-26")     # a leftover MNQ chart: not read
        ad = w.make("o.json")
        fake.move(25020.0)
        t = int(w.now[0]) - 3
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 3, "stop": 24990.25, "target": 25100.5, "entry": 25020.0, "entry_t": t})
        lines = [ln for _, ls in fake.files[k:] for ln in ls]
        check("4. NQ on, Oct 22: orders still MNQ 12-26 with the given qty / stop / target (NQ chart on 12-26 passes)",
              r["ok"] and any(ln.startswith("PLACE;Sim101;MNQ 12-26;BUY;3;MARKET") for ln in lines)
              and any("STOPMARKET;0;24990.25" in ln for ln in lines) and any("LIMIT;25100.50" in ln for ln in lines)
              and not any(";NQ 12-26;" in ln for ln in lines), lines)
        ad.send({"side": "exit", "reason": "x", "entry_t": t})
        w.now[0] = dt.datetime(2026, 12, 10, 3, 0, 3, tzinfo=ET).timestamp()
        ad2 = w.make("o2.json")
        fake.move(25330.0)
        t = int(w.now[0]) - 3
        k = len(fake.files)
        r = ad2.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t})
        check("4. Dec 10, NQ chart still on NQ 12-26, orders MNQ 03-27 -> refused, no order file",
              not r["ok"] and "Chart is on the old contract (NQ 12-26): switch it to NQ 03-27" in r["error"]
              and len(fake.files) == k, r)
        open(os.path.join(d, "NQ_instrument.txt"), "w").write("NQ 03-27")
        r = ad2.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t})
        lines = [ln for _, ls in fake.files[k:] for ln in ls]
        check("4. NQ chart on NQ 03-27 -> placed on MNQ 03-27", r["ok"] and any(";MNQ 03-27;BUY;2;" in ln for ln in lines), [r, lines])
        ad2.send({"side": "exit", "reason": "x", "entry_t": t})
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None):
        synth(int(w.now[0]) - 86400, 288, 300).to_csv(os.path.join(d, "MNQ_5m.csv"), index=False)   # the MNQ chart's bars
        ad3 = w.make("o3.json")
        check("4. NQ off: the roll guard reads the MNQ chart (MNQ 09-26 vs MNQ 03-27 orders -> refused)",
              ad3._contract_mismatch(["MNQ 03-27"]) is not None and "MNQ 09-26" in ad3._contract_mismatch(["MNQ 03-27"]))


# ------------------------------------------------------------------------------------------------ 5. heartbeat + health check
def hb_checks(folder_unused, tmp):
    from engine import ops_checks as oc
    folder = os.path.join(tmp, "nt5")
    now = int(dt.datetime.now(ET).timestamp())
    m5 = synth(now - 2 * 86400 - now % 300, 576, 300)
    q5 = m5.assign(close=m5["close"] + 0.5, high=m5["high"] + 0.5)
    write(folder, "MNQ", None, m5, "MNQ 12-26")
    write(folder, "NQ", None, q5, "NQ 12-26")
    bot = SimpleNamespace(running=False, cfg={"nt_folder": folder}, _nt_last={})
    arc = os.path.join(tmp, "arc5")
    with Env(LE_SIGNAL_ROOT="NQ"):
        files = pcbars.PCBars("NQ", root=arc).files(bot=bot, now=now)
        b5 = pcbars.decode(files.get(pcbars.BARS_5M))
        check("5. heartbeat bars (bot stopped) come from the chart the bot reads (NQ on -> NQ_5m.csv)",
              len(b5) > 0 and float(b5["close"].iloc[-1]) == float(q5["close"].iloc[-1]), b5.tail(2))
        ctx = {"now": now, "folder": folder, "ping": None, "hb": {}, "net": {"up": True, "n": 3, "drift_s": 0.0}, "state": {},
               "light": True}
        try:
            rows = oc.run_checks(ctx)
            feed = [c for c in rows if str(c.get("key", "")).startswith("feed_5m")]
            ok = bool(feed) and "MNQ_5m.csv missing" not in feed[0]["text"]
        except Exception as e:
            ok, feed = False, repr(e)
        os.remove(os.path.join(folder, FEED_DIR, "NQ_5m.csv"))
        open(os.path.join(folder, FEED_DIR, "NQ_1m.csv"), "w").write("")
        try:
            rows = oc.run_checks(ctx)
            f5 = [c for c in rows if str(c.get("key", "")).startswith("feed_5m")]
            ok2 = bool(f5) and "NQ_5m.csv missing" in f5[0]["text"]
        except Exception as e:
            ok2, f5 = False, repr(e)
        check("5. HEALTH CHECK's feed lines follow the NQ chart (its 5m file gone -> 'le_feed\\NQ_5m.csv missing')", ok and ok2,
              (feed, f5))


def main():
    tmp = tempfile.mkdtemp(prefix="le_sigroot_")
    undo = pcbars.install_yahoo_guard()
    try:
        switch_checks()
        folder = reader_checks(tmp)
        order_checks()
        hb_checks(folder, tmp)
        livebot_checks(tmp)
        check("no Yahoo call anywhere", not undo.calls, undo.calls)
    finally:
        undo()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nsignal_root: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
