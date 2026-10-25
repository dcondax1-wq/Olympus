"""A1 pre-launch audit (2026-10-25): data timing fixtures for LIT / ATLAS (research/handoff/2026-10-25/A1_data_timing.md).

    python -X utf8 -m tests.test_a1_timing          # ~1 min (one full-history LIT market for the real-data checks)
    python -X utf8 -m tests.test_a1_timing --quick  # synthetic fixtures only (seconds)

 1. Bar stamps: the TradingView files are stamped with the bar OPEN (each trading day starts 18:00, nothing in the 17:00-18:00
    halt); LE_BarFeed writes the open (close - N minutes, OnBarClose); the bot keeps only closed bars (time + secs <= now).
 2. A 5m bar built from 1m bars is "closed" only when the feed has closed its last minute (BUG_FIX regression: the
    NinjaTrader 1m-only fallback returned a 4-minute 10:00 bar as closed at 10:05:01); CloudFeed same rule; lit_live early
    mode adds the forming 5m bar flat at its open and never as a closed bar.
 3. VIX / VXN: the LIT target band uses the last CBOE close dated BEFORE the trading date (a same-date row, final or
    partial, is never read): synthetic fixture with a 4x same-day VIX, plus every 2026 day of the real file.
 4. Session boxes: a box is a level only from its last bar on (known index = last bar; partial boxes on a cut window are
    never usable); real data: every 2026 setup's swept box closed before the sweep extreme.
 5. ATR: causal (prefix ATR == full ATR on the prefix).
 6. Monday rule: decided on the bars up to the trigger bar; the Monday trading day starts Sunday 18:00 ET.
 7. DST week 2026-10-26..30 (UK on GMT, US still on EDT) and the US change on 2026-11-01: LIT uses fixed America/New_York
    minutes, so boxes / windows sit at the same ET clock times (UTC moves by one hour after Nov 1).
 8. Early closes: lit_live.early_close == CME (2026-11-26 13:00, 11-27 13:15, 12-24 13:15 ET), cross-checked on every
    early close in data/NQ_5m.csv (2021-2026); no fill after the halt (_next_bar_same_day), session over at the halt.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit, lit_live  # noqa: E402
from engine.data import from_frame  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:500]}"), flush=True)


def ts(y, m, d, hh, mm):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def synth_5m(start_et: dt.datetime, end_et: dt.datetime, seed=1, base=20000.0, overrides=None):
    """A 5m CME-hours frame (no bars 17:00-18:00 ET, none Friday 17:00 -> Sunday 18:00), random walk, bar OPEN stamps.
    overrides: {unix time: (o, h, l, c)}."""
    rng = np.random.default_rng(seed)
    t = int(start_et.timestamp())
    end = int(end_et.timestamp())
    rows, px = [], base
    while t < end:
        e = dt.datetime.fromtimestamp(t, ET)
        m = e.hour * 60 + e.minute
        closed = (1020 <= m < 1080) or e.weekday() == 5 or (e.weekday() == 4 and m >= 1020) or (e.weekday() == 6 and m < 1080)
        if not closed:
            o = px
            c = o + float(rng.normal(0, 4))
            h = max(o, c) + abs(float(rng.normal(0, 2)))
            lo = min(o, c) - abs(float(rng.normal(0, 2)))
            if overrides and t in overrides:
                o, h, lo, c = overrides[t]
            rows.append({"time": t, "open": round(o * 4) / 4, "high": round(h * 4) / 4, "low": round(lo * 4) / 4,
                         "close": round(c * 4) / 4, "volume": 100.0})
            px = c
        t += 300
    return pd.DataFrame(rows)


class FakeVol:
    """data/VIX_1d.csv + VXN_1d.csv in a temp dir (engine/lit.py reads lit.DATA_DIR)."""

    def __init__(self, rows):
        self.dir = tempfile.mkdtemp(prefix="a1_vix_")
        for nm in ("VIX", "VXN"):
            pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"]).to_csv(os.path.join(self.dir, f"{nm}_1d.csv"), index=False)

    def __enter__(self):
        self.old = lit.DATA_DIR
        lit.DATA_DIR = self.dir
        lit._VIX_CACHE.clear()
        return self

    def __exit__(self, *a):
        lit.DATA_DIR = self.old
        lit._VIX_CACHE.clear()
        shutil.rmtree(self.dir, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 1. bar stamps
def t_stamps(real=True):
    print("1. bar time stamps (bar OPEN) and the closed-bar rule", flush=True)
    from engine.live import clean_bars
    src = open(os.path.join(ROOT, "ninjatrader", "LE_BarFeed.cs"), encoding="utf-8").read()
    check("LE_BarFeed: Calculate.OnBarClose and open = NinjaTrader close stamp - N minutes",
          "Calculate = Calculate.OnBarClose;" in src and "- 60L * minutes" in src and "Times[s][0]" in src)
    df = pd.DataFrame({"time": [ts(2026, 10, 21, 10, 0), ts(2026, 10, 21, 10, 5)], "open": [1.0, 1.0], "high": [2.0, 2.0],
                       "low": [0.5, 0.5], "close": [1.5, 1.5], "volume": [1.0, 1.0]})
    a, _ = clean_bars(df, 300, ts(2026, 10, 21, 10, 9) + 59)
    b, _ = clean_bars(df, 300, ts(2026, 10, 21, 10, 10))
    check("live.clean_bars: the 10:05 bar is dropped at 10:09:59 and kept from 10:10:00 (time + 300 <= now)",
          len(a) == 1 and len(b) == 2, (len(a), len(b)))
    if not real:
        return
    for f, secs, last in (("NQ_5m.csv", 300, 1015), ("NQ_1m.csv", 60, 1019)):
        d = pd.read_csv(os.path.join(ROOT, "data", f), usecols=["time"])
        e = pd.to_datetime(d["time"], unit="s", utc=True).dt.tz_convert(ET)
        m = (e.dt.hour * 60 + e.dt.minute).to_numpy()
        td = (e + pd.Timedelta(hours=6)).dt.date.to_numpy()
        first = pd.Series(m).groupby(td).first()
        lastm = pd.Series(m).groupby(td).last()
        check(f"{f}: every trading day's first bar is stamped 18:00 ET and no bar sits in 17:00-17:59 (open stamps); "
              f"latest stamp of a normal day {last // 60}:{last % 60:02d}",
              (first == 1080).all() and not ((m >= 1020) & (m < 1080)).any() and lastm.max() == last,
              (first[first != 1080].head(), lastm.max()))


# ------------------------------------------------------------------------------------------------ 2. 5m from 1m
def t_agg():
    print("2. a 5m bar built from 1m bars counts only once its last minute closed", flush=True)
    from engine import ninjatrader as nt
    from engine import pcbars
    from engine.live import clean_bars
    t0 = ts(2026, 10, 21, 10, 0)
    d = tempfile.mkdtemp(prefix="a1_nt_")
    try:
        os.makedirs(os.path.join(d, nt.FEED_DIR))
        p = os.path.join(d, nt.FEED_DIR, "MNQ_1m.csv")

        def write(last_min):
            rows = ["time,open,high,low,close,volume"]
            for k in range(-120, last_min + 1):
                rows.append(f"{t0 + 60 * k},100,{101 + (k == 3) * 50},99,100.5,10")
            open(p, "w").write("\n".join(rows) + "\n")
        write(3)                                     # 10:04 not written yet (LE_BarFeed writes it on the first tick after 10:05)
        f = nt.NinjaTraderBars(folder=d)
        df, why, _ = f.recent_bars("NQ", "5m", "5d", now=t0 + 301)
        cb, _ = clean_bars(df if df is not None else pd.DataFrame(), 300, t0 + 301)
        check("BUG_FIX NinjaTrader 1m-only feed at 10:05:01, 1m bars to 10:03: no 10:00 5m bar (it held 4 of 5 minutes)",
              df is not None and int(cb["time"].max()) == t0 - 300, (why, None if df is None else df.tail(2).to_dict("records")))
        write(4)
        f = nt.NinjaTraderBars(folder=d)
        df, why, _ = f.recent_bars("NQ", "5m", "5d", now=t0 + 302)
        cb, _ = clean_bars(df, 300, t0 + 302)
        r = cb[cb["time"] == t0]
        check("... once 10:04 is written: the 10:00 bar is there with all 5 minutes (volume 50, high 151)",
              len(r) == 1 and float(r["volume"].iloc[0]) == 50 and float(r["high"].iloc[0]) == 151, r.to_dict("records"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # CloudFeed (the PC's 1m bars on the heartbeat): same rule
    one = pd.DataFrame([{"time": t0 + 60 * k, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0}
                        for k in range(-30, 4)])
    cf = pcbars.CloudFeed(None, {"present": True, "files": {pcbars.BARS_1M: pcbars.encode(one)}}, now=t0 + 301, save=False)
    cf2 = pcbars.CloudFeed(None, {"present": True, "files": {pcbars.BARS_1M: pcbars.encode(
        pd.concat([one, pd.DataFrame([{"time": t0 + 300, "open": 1e2, "high": 1e2, "low": 1e2, "close": 1e2, "volume": 1.0}])]))}},
        now=t0 + 361, save=False)
    check("CloudFeed: 1m to 10:03 -> last 5m bar 09:55; a 10:05 print (10:04 had no trade) completes 10:00",
          int(cf.five["time"].max()) == t0 - 300 and t0 in set(cf2.five["time"]), (cf.last_5m_t, cf2.last_5m_t))
    # lit_live early mode: the forming 5m bar is added flat at its open and is never a closed bar
    df5 = synth_5m(dt.datetime(2026, 9, 1, 18, 0, tzinfo=ET), dt.datetime(2026, 10, 21, 10, 0, tzinfo=ET))
    one = pd.DataFrame([{"time": int(t) + 60 * j, "open": float(o), "high": float(max(o, c)), "low": float(min(o, c)),
                         "close": float(c), "volume": 1.0}
                        for t, o, c in zip(df5["time"].tail(60), df5["open"].tail(60), df5["close"].tail(60)) for j in range(5)])
    # make every 5m window rebuild exactly: high/low/close of the 1m set = the 5m bar's
    one = one.merge(df5[["time", "high", "low", "close"]].rename(columns={"time": "b", "high": "H", "low": "L", "close": "C"}),
                    left_on=one["time"] // 300 * 300, right_on="b", how="left")
    one["high"] = np.where(one["time"] % 300 == 0, one["H"], one["low"].clip(upper=one["H"]))
    one["low"] = np.where(one["time"] % 300 == 0, one["L"], one["low"].clip(lower=one["L"]))
    one["close"] = np.where(one["time"] % 300 == 240, one["C"], one["open"])
    one = one[["time", "open", "high", "low", "close", "volume"]]
    one["high"] = one[["open", "high", "close"]].max(axis=1)
    one["low"] = one[["open", "low", "close"]].min(axis=1)
    fo = pd.DataFrame([{"time": t0, "open": 20001.0, "high": 20005.0, "low": 20000.0, "close": 20004.0, "volume": 1.0},
                       {"time": t0 + 60, "open": 20004.0, "high": 20010.0, "low": 20003.0, "close": 20009.0, "volume": 1.0}])
    keep = {}
    with FakeVol([[str(d.date()), 20, 20, 20, 20.0] for d in pd.bdate_range("2026-08-01", "2026-10-21")]):
        lit_live.run(df5, {**lit.DEFAULTS, "tf": "1m"}, one_min=pd.concat([one, fo]), now=t0 + 125, early=True, keep=keep)
    M = keep["M"]
    check("lit_live early mode at 10:02:05: 5m market = closed bars to 09:55 + the 10:00 bar FLAT at its open (n_closed excludes it)",
          M.n == M.n_closed + 1 and int(M.t[-1]) == t0 and M.h[-1] == M.l[-1] == M.c[-1] == M.o[-1] == 20001.0
          and int(M.t[M.n_closed - 1]) == t0 - 300, (M.n, M.n_closed, M.o[-1], M.h[-1]))


# ------------------------------------------------------------------------------------------------ 3. VIX
def t_vix(real=True):
    print("3. VIX / VXN: prior-day CBOE close only", flush=True)
    df5 = synth_5m(dt.datetime(2026, 10, 4, 18, 0, tzinfo=ET), dt.datetime(2026, 10, 9, 17, 0, tzinfo=ET))
    rows = [["2026-10-02", 0, 0, 0, 15.0], ["2026-10-05", 0, 0, 0, 16.0], ["2026-10-06", 0, 0, 0, 17.0],
            ["2026-10-07", 0, 0, 0, 18.0], ["2026-10-08", 0, 0, 0, 72.0],       # the 10-08 row: 4x (a same-day leak would show)
            ["2026-10-09", 0, 0, 0, 99.0]]                                       # a partial "today" row for 10-09
    with FakeVol(rows):
        M = lit.Market(bars=from_frame("NQ", "5m", df5))
        got = {x["date"]: x.get("vix") for x in M.ctx}
        want = {"2026-10-05": 15.0, "2026-10-06": 16.0, "2026-10-07": 17.0, "2026-10-08": 18.0, "2026-10-09": 72.0}
        check("synthetic: trading date D uses the close dated D-1 (Monday uses Friday); the 4x row of 10-08 reaches only 10-09",
              got == want, got)
        x = M.ctx[[c["date"] for c in M.ctx].index("2026-10-08")]
        mv = 18.0 / 100 / np.sqrt(252) * x["open18"]
        z = {"k": [c["date"] for c in M.ctx].index("2026-10-08"), "dir": 1, "entry_d": x["open18"], "i": x["s"] + 10, "targets": {}}
        T = lit.targets_x(M, z, {**lit.DEFAULTS, "classes": ["vix"], "vix_k": 1.0})
        check("synthetic: the 10-08 VIX band = 18:00 open + 18.0/100/sqrt(252) x open (not the 72.0 close of 10-08)",
              abs(x["vix_move"] - mv) < 1e-9 and abs(T["vix"][0] - round(mv, 2)) < 0.011, (x["vix_move"], mv, T))
    if not real:
        return
    lit._VIX_CACHE.clear()
    vd = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    xd = pd.read_csv(os.path.join(ROOT, "data", "VXN_1d.csv"))
    M = lit.Market()
    bad = []
    n = 0
    for x in M.ctx:
        if x["date"] < "2026-01-01":
            continue
        n += 1
        for nm, f in (("vix", vd), ("vxn", xd)):
            prior = f[f["date"] < x["date"]]
            if not len(prior) or abs(float(prior["close"].iloc[-1]) - x.get(nm, -1)) > 1e-9:
                bad.append((x["date"], nm, x.get(nm)))
    check(f"real data: all {n} 2026 trading days use the last VIX and VXN close dated before the trading date", not bad and n > 200, bad[:5])
    return M


# ------------------------------------------------------------------------------------------------ 4/5. boxes, ATR
def t_boxes_atr(M=None):
    print("4. session boxes known from their last bar; 5. ATR causal", flush=True)
    df5 = synth_5m(dt.datetime(2026, 10, 4, 18, 0, tzinfo=ET), dt.datetime(2026, 10, 7, 17, 0, tzinfo=ET), seed=3)
    with FakeVol([["2026-10-02", 0, 0, 0, 15.0]]):
        B = from_frame("NQ", "5m", df5)
        Mf = lit.Market(bars=B)
        k = [c["date"] for c in Mf.ctx].index("2026-10-06")
        hi, lo, ki = Mf.ctx[k]["asia20"]
        s, e = Mf.days[k][1], Mf.days[k][2]
        sel = [i for i in range(s, e) if 1200 <= Mf.mod[i] < 1440]
        ok_full = ki == sel[-1] and int(Mf.mod[ki]) == 23 * 60 + 55 and hi == Mf.h[sel].max() and lo == Mf.l[sel].min()
        n = int(np.searchsorted(B.t, ts(2026, 10, 5, 22, 0)))         # cut at 22:00: the 20:00-24:00 box is half built
        Mc = lit.Market(bars=B.slice(0, n))
        hc, lc, kc = Mc.ctx[k]["asia20"]
        Cc = lit.candidates(Mc, ref="cisd")
        use = [z for z in Cc if z["k"] == k and any(nm.startswith("asia20") for nm in z["swept"])]
        check("synthetic: asia20 box known index = its 23:55 bar; cut at 22:00 the partial box's index is the cut's last bar, "
              "so no setup can use it (liquidity needs index < extreme, a target index <= trigger < last bar)",
              ok_full and kc == n - 1 and not use, (ki, kc, n, len(use)))
        full_atr = lit.atr(B.h, B.l, B.c)
        pre = lit.atr(B.h[:500], B.l[:500], B.c[:500])
        check("ATR (Wilder 14) on a prefix == the full-data ATR on that prefix (causal)", np.allclose(pre, full_atr[:500], rtol=0, atol=0))
    if M is None:
        return
    C = lit.candidates(M, ref="cisd")
    bad, n = [], 0
    for z in C:
        if z["day"] < "2026-01-01":
            continue
        x = M.ctx[z["k"]]
        for nm in z["swept"]:
            box = nm[:-2] if nm[:-2] in lit.SESSIONS else None
            if box:
                n += 1
                if not (x[box][2] < z["ext_i"] <= z["i"] < z["entry_i"]):
                    bad.append((z["day"], nm, x[box][2], z["ext_i"]))
    check(f"real data: {n} swept session boxes of the 2026 setups all closed before the sweep extreme", n > 0 and not bad, bad[:5])
    a = int(np.searchsorted(M.t, ts(2026, 3, 2, 18, 0)))
    pre = lit.atr(M.h[:a], M.l[:a], M.c[:a])
    check("real data: Market ATR on bars up to 2026-03-02 == full-history ATR there", np.array_equal(pre, M.atr[:a]))


# ------------------------------------------------------------------------------------------------ 6. Monday
def t_monday():
    print("6. Monday rule state", flush=True)
    fri = dt.datetime(2026, 10, 9, 0, 0, tzinfo=ET)
    df5 = synth_5m(dt.datetime(2026, 10, 7, 18, 0, tzinfo=ET), dt.datetime(2026, 10, 12, 15, 0, tzinfo=ET), seed=5)
    with FakeVol([["2026-10-06", 0, 0, 0, 15.0]]):
        B = from_frame("NQ", "5m", df5)
        M = lit.Market(bars=B)
        k = [c["date"] for c in M.ctx].index("2026-10-12")
        x = M.ctx[k]
        s = x["s"]
        # put Friday's high and low out of reach, then take the high at 03:00 Monday and the low at 10:00
        h, l = M.h.copy(), M.l.copy()
        pdh, pdl = x["pdh"], x["pdl"]
        for i in range(s, M.days[k][2]):
            h[i] = min(h[i], pdh - 1); l[i] = max(l[i], pdl + 1)
        i3 = int(np.searchsorted(M.t, ts(2026, 10, 12, 3, 0)))
        i10 = int(np.searchsorted(M.t, ts(2026, 10, 12, 10, 0)))
        h[i3] = pdh + 5
        l[i10] = pdl - 5
        M.h, M.l = h, l
        st = [lit.monday_state(M, k, int(np.searchsorted(M.t, ts(2026, 10, 12, hh, 0)))) for hh in (2, 3, 9, 10, 11)]
        blk = [lit.monday_block(M, {"k": k, "i": i3 + 12, "dir": 1}), lit.monday_block(M, {"k": k, "i": i3 + 12, "dir": -1}),
               lit.monday_block(M, {"k": k, "i": i10 + 1, "dir": 1})]
        check("Monday trading day starts Sunday 18:00 ET (dow 0) and its Friday levels are Thursday 18:00 -> Friday 17:00",
              int(M.dow[s]) == 0 and int(M.t[s]) == ts(2026, 10, 11, 18, 0) and x["pdh"] == float(M.h[M.days[k - 1][1]:M.days[k - 1][2]].max())
              and M.days[k - 1][0] == "2026-10-09", (int(M.dow[s]), M.days[k - 1][0]))
        check("monday_state at 02:00/03:00/09:00/10:00/11:00 = none/high/high/both/both (bars up to each bar only); "
              "a long after the high-only take is blocked, a short is not, after both sides nothing is blocked",
              st == ["none", "high", "high", "both", "both"] and blk == [True, False, False], (st, blk))
    del fri


# ------------------------------------------------------------------------------------------------ 7. DST
def t_dst():
    print("7. DST: UK changed 2026-10-25, US 2026-11-01; LIT uses fixed America/New_York minutes", flush=True)
    df5 = synth_5m(dt.datetime(2026, 10, 22, 18, 0, tzinfo=ET), dt.datetime(2026, 11, 6, 17, 0, tzinfo=ET), seed=7)
    with FakeVol([["2026-10-21", 0, 0, 0, 15.0]]):
        M = lit.Market(bars=from_frame("NQ", "5m", df5))
    days = [d for d, s, e in M.days]
    want_days = [str(d.date()) for d in pd.bdate_range("2026-10-23", "2026-11-06")]
    first_utc = {d: dt.datetime.fromtimestamp(int(M.t[s]), UTC).strftime("%H:%M") for d, s, e in M.days}
    check("trading days 10-23 .. 11-06 each start 18:00 ET: 22:00 UTC up to 11-02's session (Sun Nov 1 18:00 EST = 23:00 UTC)",
          days == want_days and all(first_utc[d] == ("22:00" if d < "2026-11-02" else "23:00") for d in days), first_utc)
    k27, k03 = days.index("2026-10-27"), days.index("2026-11-03")
    lon27 = M.ctx[k27]["lon25"][2]
    lon03 = M.ctx[k03]["lon25"][2]
    utc27 = dt.datetime.fromtimestamp(int(M.t[lon27]), UTC).strftime("%H:%M")
    utc03 = dt.datetime.fromtimestamp(int(M.t[lon03]), UTC).strftime("%H:%M")
    check("London box lon25 (02:00-05:00 ET) ends with the 04:55 ET bar in both weeks: 08:55 UTC on 10-27 (UK already on GMT: "
          "London opened 04:00 ET that week) and 09:55 UTC on 11-03 (fixed ET clock, not the London clock)",
          int(M.mod[lon27]) == int(M.mod[lon03]) == 295 and utc27 == "08:55" and utc03 == "09:55", (utc27, utc03))
    t9 = ts(2026, 10, 28, 9, 30)
    check("entry window / flat / trading date use ET: 2026-10-28 09:30 ET = 13:30 UTC (EDT), 2026-11-04 09:30 ET = 14:30 UTC",
          dt.datetime.fromtimestamp(t9, UTC).hour == 13 and dt.datetime.fromtimestamp(ts(2026, 11, 4, 9, 30), UTC).hour == 14
          and str(lit_live.trading_date(ts(2026, 11, 1, 18, 0))) == "2026-11-02")


# ------------------------------------------------------------------------------------------------ 8. early closes
def t_early(real=True):
    print("8. early closes", flush=True)
    ec = lit_live.early_close
    cases = {"2026-11-26": 780, "2026-11-27": 795, "2026-12-24": 795, "2026-11-25": None, "2026-12-31": None,
             "2026-12-23": None, "2027-01-18": 780, "2027-03-26": 555,
             "2025-07-03": 795, "2028-07-03": 795, "2026-07-03": 780, "2026-07-02": None, "2027-07-02": None}
    got = {d: ec(d) for d in cases}
    check("lit_live.early_close: Thanksgiving 2026-11-26 13:00, 11-27 13:15, Christmas Eve 12-24 13:15 ET (CME 12:00 / 12:15 CT); "
          "MLK 2027 13:00; Good Friday 2027 09:15; BUG_FIX July 3 13:15 when July 4 is Tue-Fri (2025, 2028), not in 2026 (Jul 3 = the "
          "observed holiday, 13:00); normal days None", got == cases, got)
    # no fill after the halt: a 1m bar at 13:14 on 11-27 is the session's last (the next one would be after the halt)
    t = np.array([ts(2026, 11, 27, 13, 13), ts(2026, 11, 27, 13, 14)])
    B = lit.XBars(t, t * 0.0, t * 0.0, t * 0.0, t * 0.0, np.array([793, 794]), np.array([0, 0]), 60)
    t2 = np.array([ts(2026, 11, 27, 13, 12), ts(2026, 11, 27, 13, 13)])
    B2 = lit.XBars(t2, t2 * 0.0, t2 * 0.0, t2 * 0.0, t2 * 0.0, np.array([792, 793]), np.array([0, 0]), 60)
    check("no live entry into the halt: after the 13:14 bar (11-27) no next-bar fill; after 13:13 there is one",
          not lit._next_bar_same_day(B, 1, "2026-11-27") and lit._next_bar_same_day(B2, 1, "2026-11-27"))
    halt = ts(2026, 11, 26, 13, 0)
    check("session over on 2026-11-26 once the feed stopped at the 13:00 halt and 5 min passed (not before)",
          lit_live._session_over("2026-11-26", halt + 300, halt) and not lit_live._session_over("2026-11-26", halt + 240, halt))
    if not real:
        return
    d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time"])
    e = pd.to_datetime(d["time"], unit="s", utc=True).dt.tz_convert(ET)
    td = (e + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    last = (e.dt.hour * 60 + e.dt.minute).groupby(td).last()
    short = {k: int(v) + 5 for k, v in last.items() if v < 1015}
    one_off = {"2025-01-09": "national day of mourning (President Carter): CME equity halted 09:30 ET; a one-off, not coded"}
    bad = {k: (v, ec(k)) for k, v in short.items() if ec(k) != v and k not in one_off}
    # Good Friday 2026 traded to 09:15 (last 5m bar 09:10): the rule's 09:15 matches; a day the export cut short is a data gap
    check(f"data/NQ_5m.csv: every one of the {len(short)} short sessions (2021-2026) ends at lit_live.early_close "
          f"(last 5m bar + 5 min), except {list(one_off)} ({list(one_off.values())[0]})", not bad, bad)
    nd = [k for k in last.index if ec(k) is not None and k not in short and k >= "2021-11-01"]
    check("and no early-close date in the data runs a full session", not nd, nd)


def main():
    quick = "--quick" in sys.argv
    t_stamps(real=not quick)
    t_agg()
    M = t_vix(real=not quick)
    t_boxes_atr(M)
    t_monday()
    t_dst()
    t_early(real=not quick)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    for n in bad:
        print("  FAIL:", n)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
