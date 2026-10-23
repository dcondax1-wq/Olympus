"""December 2026 roll readiness (MNQ 12-26 -> 03-27): the roll simulated end to end on the PC bot, the cloud monitor and the
NinjaTrader order route. See docs/ROLL_DEC_2026.md for the owner's steps.

    python -X utf8 -m tests.test_roll

Real-shaped data: the Sep 2026 roll (U26 -> Z26, TradingView switch Mon 2026-09-14 18:00 ET, gap +294.75 pts) replayed on
data/NQ_5m.csv + data/NQ_1m.csv, which sit on the NEW contract's prices ("truth"); the OLD contract prints truth - 294.75.
The same thing happens in December (Z26 -> H27; TradingView switches Mon 12-14 18:00 ET, NinjaTrader orders Thu 12-10):
  * the TradingView export on disk is anchored on the old contract (made before the roll);
  * the PC bot's NinjaTrader archive (data/nt_bars) holds old-contract bars;
  * the owner switches the NinjaTrader chart (LE_BarFeed) to the new contract, and LE_BarFeed rewrites its files.
Scenarios (each runs the real engine/live.py LiveBot._merged / _lit_1m on a frozen clock, LE_BarFeed files on disk):
  A  chart switched Wed 17:00 ET before NinjaTrader's rollover date, merge policy "Merge back adjusted" (normally
     the default): the whole LIT window equals the truth, LIT's trades and every level (PDH/PDL, PWH/PWL, PMH/PML, NDOG/NWOG)
     are the truth's; also with NinjaTrader's own offset 0.5 pt away from TradingView's gap.
  B  overlap missing (the chart loaded 5 days, no archive): nothing to measure the gap on -> history not shifted, the
     levels are 296 pts off, the bot logs the hole; loading 30 days fixes it.
  C  two real contracts on the overlap (chart switched after NinjaTrader's rollover date, or "Do not merge"): the spread
     moves with the price. The rule before 2026-10-20 missed it (no shift = 296-pt jump); the fixed engine/pcbars.py
     basis_shift catches it.
  D  merge policy "Merge non back adjusted": the jump is inside NinjaTrader's own file; the bot cannot repair it,
     tools/roll_check.py says ACTION.
  E  cloud monitor (tools/cloud_monitor.run_model on CloudFeed): its 5m store + 1m store on the old contract, the PC's
     heartbeat bars on the new one -> back-adjusted, LIT's trades equal the truth's.
  F  orders: engine/ninjatrader.py names MNQ 12-26 through Wed 12-09 and MNQ 03-27 from Thu 12-10 (by the ET date, while
     the bot runs), an open leg keeps its own contract, --instrument / nt_instrument override it; a chart left on 12-26
     after 12-10 sends 12-26-priced stops and targets to 03-27 (tools/roll_check.py says ACTION).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

ET = ZoneInfo("America/New_York")
COLS = ["time", "open", "high", "low", "close", "volume"]
RESULTS = []
PX = ("open", "high", "low", "close")


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def at(y, m, d, hh=0, mm=0, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def plus(df, pts, before=None):
    df = df.copy()
    m = np.ones(len(df), bool) if before is None else (df["time"].values < before)
    for c in PX:
        df.loc[m, c] = df.loc[m, c] + pts
    return df


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, "data", f"NQ_{tf}.csv"))
    df = df[df["time"] >= at(2026, 6, 1)]
    return df[~((df["high"] == df["low"]) & (df["volume"] <= 0))].reset_index(drop=True)   # the bot's own hygiene


def diff(df, ref, t0, t1):
    """max |price diff| between df and ref on [t0, t1), and whether both have the same bars there."""
    a = df[(df["time"] >= t0) & (df["time"] < t1)]
    b = ref[(ref["time"] >= t0) & (ref["time"] < t1)]
    m = a.merge(b, on="time", suffixes=("", "_r"))
    if not len(m):
        return float("inf"), False, 0
    d = max(float(np.abs(m[c] - m[c + "_r"]).max()) for c in PX)
    return d, len(m) == len(a) == len(b), len(m)


def write_feed(folder, b1, b5, t5, t1, upto):
    """LE_BarFeed's files (header + closed bars, time = bar open): 5m from t5, 1m from t1, closed before upto."""
    d = os.path.join(folder, "le_feed")
    os.makedirs(d, exist_ok=True)
    for name, df, secs, t0 in (("MNQ_1m.csv", b1, 60, t1), ("MNQ_5m.csv", b5, 300, t5)):
        x = df[(df["time"] >= t0) & (df["time"] + secs <= upto)]
        x[COLS].to_csv(os.path.join(d, name), index=False)


def levels(df5, days):
    """LIT's day context (engine/lit.py Market) for the given trading days: PDH/PDL, PWH/PWL, PMH/PML, NDOG, NWOG."""
    from engine import lit
    from engine.data import from_frame
    M = lit.Market(bars=from_frame("NQ", "5m", df5[COLS].reset_index(drop=True)))
    out = {}
    for x in M.ctx:
        if x["date"] in days:
            out[x["date"]] = {k: (tuple(x[k]) if isinstance(x.get(k), list) else x.get(k))
                              for k in ("pdh", "pdl", "pwh", "pwl", "pmh", "pml", "ndog", "nwog")}
    return out


def lvl_diff(a, b):
    worst = 0.0
    for d in b:
        for k, v in b[d].items():
            w = a.get(d, {}).get(k)
            if v is None and w is None:
                continue
            if (v is None) != (w is None):
                return float("inf")
            vv, ww = (np.array(v, float), np.array(w, float))
            worst = max(worst, float(np.abs(vv - ww).max()))
    return worst


def trades_key(res):
    return [(t["entry_t"], t["dir"], round(t["entry"], 2), round(t["stop"], 2), round(t.get("target") or 0, 2),
             t.get("exit_t"), t.get("exit_reason"), round(float(t.get("pnl_r") or 0), 3)) for t in res["trades"]]


class PC:
    """The PC bot (engine/live.py LiveBot, LIT, paper adapter) on its own data dir, NinjaTrader folder and archive."""

    def __init__(self, tmp, name, tv5, tv1):
        from engine import live
        self.live = live
        self.dir = os.path.join(tmp, name)
        self.data = os.path.join(self.dir, "data")
        self.folder = os.path.join(self.dir, "NinjaTrader 8")
        self.arc = os.path.join(self.dir, "nt_bars")
        os.makedirs(self.data, exist_ok=True)
        tv5[COLS].to_csv(os.path.join(self.data, "NQ_5m.csv"), index=False)
        tv1[COLS].to_csv(os.path.join(self.data, "NQ_1m.csv"), index=False)
        self.clock = [0]
        b = live.LiveBot()
        b.clock = lambda: self.clock[0]
        b.state_path = os.path.join(self.dir, "live_state.json")
        b._remember = lambda *a, **kw: None
        self.bot = b
        self.started = False

    def poll(self, now):
        """What poll_once feeds LIT: the merged 5m frame and the 1m frame (LiveBot._merged, LiveBot._lit_1m)."""
        live = self.live
        saved = live.DATA_DIR
        live.DATA_DIR = self.data
        try:
            self.clock[0] = now
            if not self.started:
                r = self.bot.start({"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "nt_folder": self.folder,
                                    "nt_archive": self.arc}, spawn=False)
                assert r.get("ok"), r
                self.started = True
            self.bot._nt_feed = None
            df5, _ = self.bot._merged("NQ", "5m", now, 300)
            df1 = self.bot._lit_1m("NQ", now, int(df5["time"].min()))
            return df5, df1
        finally:
            live.DATA_DIR = saved

    def log(self):
        return [x["text"] for x in self.bot.log]


def lit_run(df5, df1, now):
    from engine import lit, lit_live
    from engine.lab_adapter import live_model
    P = {**lit.DEFAULTS, **(live_model().get("lit") or {})}
    w5 = df5[df5["time"] + 300 <= now]
    w1 = df1[df1["time"] + 60 <= now] if df1 is not None else None
    return lit_live.run(w5, P, one_min=w1, now=now, sym="NQ")


def old_rule(old, new, min_overlap=20):
    """engine/pcbars.basis_shift as it was before 2026-10-20 (constant to 1 pt on 70% of the last 600 shared bars)."""
    a = old[["time", "close"]].drop_duplicates("time", keep="last")
    b = new[["time", "close"]].drop_duplicates("time", keep="last")
    m = a.merge(b, on="time", suffixes=("_o", "_n"))
    if len(m) < min_overlap:
        return 0.0
    d = (m["close_n"] - m["close_o"]).to_numpy(dtype=float)[-600:]
    med = float(np.median(d))
    if abs(med) < 2.0 or float(np.mean(np.abs(d - med) <= 1.0)) < 0.7:
        return 0.0
    return round(med * 4) / 4.0


def main():
    from engine import alerts, news, pcbars
    from engine.lit_live import window_start
    alerts.send = lambda *a, **kw: None
    news.volatility = lambda *a, **kw: None                       # CBOE VIX: offline (data/VIX_1d.csv is used as is)
    news.ff_calendar = lambda: []
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))
    sep = [r for r in rolls["rolls"] if r["from"] == "NQU26"][0]
    G, TV_SW = float(sep["gap"]), int(sep["switch_t"])
    NT_ROLL = at(2026, 9, 9, 18)                # NinjaTrader's rollover: the Thu 09-10 session (8 days before expiry)
    T5, T1 = load("5m"), load("1m")             # the new contract's prices (truth)
    O5, O1 = plus(T5, -G), plus(T1, -G)         # the old contract's prices
    TV_END = at(2026, 9, 4)
    tv5_old, tv1_old = O5[O5.time < TV_END], O1[O1.time < TV_END]     # the TradingView export on disk (old anchor)
    tmp = tempfile.mkdtemp(prefix="le_roll_")
    undo = pcbars.install_yahoo_guard()
    try:
        print(f"real-shaped Sep 2026 roll: gap {G:+.2f}, TradingView switch {dt.datetime.fromtimestamp(TV_SW, ET):%a %m-%d %H:%M} ET",
              flush=True)
        # ---------------------------------------------------------------- A
        print("A. chart switched Wed 17:00 ET, merge back adjusted (the recommended way)", flush=True)
        pc = PC(tmp, "A", tv5_old, tv1_old)
        n1 = at(2026, 9, 9, 12, 0, 30)
        write_feed(pc.folder, O1, O5, n1 - 29 * 86400, n1 - 14 * 86400, n1 - n1 % 60)
        d5, d1 = pc.poll(n1)
        ws = window_start(n1)
        e5, s5, k5 = diff(d5, O5, ws, n1 - 300)
        check("before the switch: one contract everywhere (old), no shift, no hole; the archive is written",
              e5 < 1e-6 and s5 and not any("back-adjusted" in x for x in pc.log())
              and os.path.exists(pcbars.archive_path("NQ", "5m", pc.arc)), (e5, s5, k5, pc.log()[:4]))
        n2 = at(2026, 9, 10, 3, 0, 30)
        write_feed(pc.folder, T1, T5, n2 - 29 * 86400, n2 - 14 * 86400, n2 - n2 % 60)   # LE_BarFeed rewrites on the new contract
        d5, d1 = pc.poll(n2)
        ws = window_start(n2)
        e5, s5, k5 = diff(d5, T5, ws, n2 - 300)
        e1, s1, k1 = diff(d1, T1, ws, n2 - 60)
        arc = pcbars.archive_read("NQ", "5m", pc.arc)
        ea, _, _ = diff(arc, T5, 0, n2)
        check(f"first poll after the switch: the whole LIT window (from {dt.datetime.fromtimestamp(ws, ET):%m-%d}) is on the new "
              f"contract, 5m and 1m equal the truth ({k5} / {k1} bars)",
              e5 < 1e-6 and s5 and e1 < 1e-6 and s1, (e5, s5, e1, s1))
        check("the archive is rewritten on the new contract (+294.75) and the log says so ('back-adjusted')",
              ea < 1e-6 and any("back-adjusted" in x for x in pc.log()), (ea, pc.log()[:6]))
        d5b, d1b = pc.poll(n2 + 60)
        e5, s5, _ = diff(d5b, T5, ws, n2 - 300)
        check("next poll: the TradingView history (old anchor) is shifted through the archive overlap; still the truth",
              e5 < 1e-6 and s5, e5)
        n3 = at(2026, 9, 15, 10, 0, 30)                                # after TradingView's own switch (Mon 18:00)
        write_feed(pc.folder, T1, T5, n3 - 29 * 86400, n3 - 14 * 86400, n3 - n3 % 60)
        d5, d1 = pc.poll(n3)
        ws3 = window_start(n3)
        e5, s5, _ = diff(d5, T5, ws3, n3 - 300)
        e1, s1, _ = diff(d1, T1, ws3, n3 - 60)
        check("Tue after TradingView's switch: still the truth (5m and 1m)", e5 < 1e-6 and s5 and e1 < 1e-6 and s1, (e5, e1))
        days = ["2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14", "2026-09-15"]
        lv_bot, lv_true = levels(d5[d5.time >= ws3], days), levels(T5[(T5.time >= ws3) & (T5.time < n3 - 300)], days)
        check("levels after the roll (PDH/PDL, PWH/PWL, PMH/PML, NDOG/NWOG, Sep 8-15) equal the truth's",
              lvl_diff(lv_bot, lv_true) < 1e-6, (lv_bot.get("2026-09-15"), lv_true.get("2026-09-15")))
        t1m = T1[T1.time.isin(set(d1.time))]
        r_bot, r_true = lit_run(d5, d1, n3), lit_run(T5[T5.time < n3], t1m, n3)
        check(f"LIT on the bot's frames = LIT on the truth ({len(r_true['trades'])} trades in the window, same entries, "
              "stops, targets, exits)", trades_key(r_bot) == trades_key(r_true) and len(r_true["trades"]) > 3,
              (trades_key(r_bot)[-3:], trades_key(r_true)[-3:]))
        naive5 = pd.concat([O5[O5.time < n3 - 29 * 86400], T5[(T5.time >= n3 - 29 * 86400) & (T5.time < n3)]])
        naive1 = pd.concat([O1[O1.time < n3 - 14 * 86400], T1[(T1.time >= n3 - 14 * 86400) & (T1.time < n3)]])
        lv_naive = levels(naive5[naive5.time >= ws3], days)
        r_naive = lit_run(naive5, naive1[naive1.time.isin(set(d1.time))], n3)
        bad_lv = lvl_diff(lv_naive, lv_true)
        n_diff = len(set(trades_key(r_naive)) ^ set(trades_key(r_true)))
        check(f"without the back-adjustment (old bars left on the old contract) the levels are {bad_lv:.2f} pts off "
              f"and {n_diff} trade records differ: the shift matters", bad_lv > 200, (bad_lv, n_diff))
        # A': NinjaTrader's own offset 0.5 pt away from TradingView's gap
        pa = PC(tmp, "A2", tv5_old, tv1_old)
        write_feed(pa.folder, O1, O5, n1 - 29 * 86400, n1 - 14 * 86400, n1 - n1 % 60)
        pa.poll(n1)
        nt5 = pd.concat([plus(O5, G + 0.5)[O5.time < NT_ROLL], T5[T5.time >= NT_ROLL]])
        nt1 = pd.concat([plus(O1, G + 0.5)[O1.time < NT_ROLL], T1[T1.time >= NT_ROLL]])
        write_feed(pa.folder, nt1, nt5, n2 - 29 * 86400, n2 - 14 * 86400, n2 - n2 % 60)
        d5, _ = pa.poll(n2)
        e_pre, _, _ = diff(d5, T5, window_start(n2), NT_ROLL)
        e_post, _, _ = diff(d5, T5, NT_ROLL, n2 - 300)
        check("NinjaTrader's offset 0.5 pt off TradingView's: history before the rollover sits 0.5 pt off the truth, after it "
              "exact (harmless)", abs(e_pre - 0.5) < 1e-6 and e_post < 1e-6, (e_pre, e_post))

        # ---------------------------------------------------------------- B
        print("B. overlap missing (chart loaded 5 days, no archive)", flush=True)
        tvB5, tvB1 = O5[O5.time < at(2026, 8, 21)], O1[O1.time < at(2026, 8, 21)]
        pb = PC(tmp, "B", tvB5, tvB1)
        write_feed(pb.folder, T1, T5, n2 - 5 * 86400, n2 - 5 * 86400, n2 - n2 % 60)
        d5, _ = pb.poll(n2)
        lvB = levels(d5[d5.time >= window_start(n2)], ["2026-09-10"])
        lvT = levels(T5[(T5.time >= window_start(n2)) & (T5.time < n2 - 300)], ["2026-09-10"])
        gap_noted = bool((pb.bot.health.get("hist_gap") or {}).get("5m")) and any("bars missing" in x for x in pb.log())
        check(f"no shared bars: no shift; PMH/PML (August) {lvl_diff(lvB, lvT):.2f} pts off the truth; the bot logs the hole "
              "('... bars missing ... load more days on the NinjaTrader chart')",
              lvl_diff(lvB, lvT) > 200 and gap_noted, (lvl_diff(lvB, lvT), pb.bot.health.get("hist_gap"), pb.log()[:4]))
        pb2 = PC(tmp, "B2", tvB5, tvB1)
        write_feed(pb2.folder, T1, T5, n2 - 29 * 86400, n2 - 14 * 86400, n2 - n2 % 60)
        d5, _ = pb2.poll(n2)
        e5, s5, _ = diff(d5, T5, window_start(n2), n2 - 300)
        check("the fix: 30 days on the chart (it then overlaps the TradingView file): the truth again", e5 < 1e-6 and s5, e5)

        # ---------------------------------------------------------------- C
        print("C. two real contracts on the overlap (late switch / 'Do not merge')", flush=True)
        rng = np.random.default_rng(11)
        ref = float(O5.loc[O5.time < NT_ROLL, "close"].iloc[-1])

        def real_new(df, noise):
            sp = G * df["close"].values / ref + (rng.normal(0, noise, len(df)) if noise else 0.0)
            out = df.copy()
            for c in PX:
                out[c] = np.round((out[c].values + sp) * 4) / 4
            return out
        R5, R1 = real_new(O5, 0.5), real_new(O1, 0.75)                    # the new contract's own prices (spread drifts)
        nC = at(2026, 9, 15, 3, 0, 30)
        for label, f5, f1 in (("switched Mon 09-14 (after NinjaTrader's rollover), merge back adjusted",
                               pd.concat([plus(O5, G)[O5.time < NT_ROLL], R5[R5.time >= NT_ROLL]]),
                               pd.concat([plus(O1, G)[O1.time < NT_ROLL], R1[R1.time >= NT_ROLL]])),
                              ("merge policy 'Do not merge'", R5, R1)):
            pcC = PC(tmp, "C" + label[:6].strip(), tv5_old, tv1_old)
            nb = at(2026, 9, 14, 12, 0, 30)
            write_feed(pcC.folder, O1, O5, nb - 29 * 86400, nb - 14 * 86400, nb - nb % 60)
            pcC.poll(nb)
            arc_old = pcbars.archive_read("NQ", "5m", pcC.arc)
            new_closed = f5[(f5.time >= nC - 29 * 86400) & (f5.time + 300 <= nC)]
            before = old_rule(arc_old, new_closed)
            write_feed(pcC.folder, f1, f5, nC - 29 * 86400, nC - 14 * 86400, nC - nC % 60)
            d5, _ = pcC.poll(nC)
            first = int(new_closed["time"].min())
            seam = d5[(d5.time >= first - 3600) & (d5.time < first + 3600)]
            jump = float(np.abs(seam["open"].values[1:] - seam["close"].values[:-1]).max())
            e_feed, _, _ = diff(d5, f5, first, nC - 300)
            check(f"{label}: the old rule found no constant offset ({before}); the fixed rule shifts the history "
                  f"(seam jump {jump:.2f} pts, not ~296) and keeps the chart's own bars",
                  before == 0.0 and jump < 40 and e_feed < 1e-6, (before, jump, e_feed))

        # ---------------------------------------------------------------- D
        print("D. merge policy 'Merge non back adjusted' (the jump is inside NinjaTrader's file)", flush=True)
        import roll_check
        pd_ = PC(tmp, "D", tv5_old, tv1_old)
        write_feed(pd_.folder, O1, O5, n1 - 29 * 86400, n1 - 14 * 86400, n1 - n1 % 60)
        pd_.poll(n1)
        nb5 = pd.concat([O5[O5.time < NT_ROLL], T5[T5.time >= NT_ROLL]])
        nb1 = pd.concat([O1[O1.time < NT_ROLL], T1[T1.time >= NT_ROLL]])
        write_feed(pd_.folder, nb1, nb5, n2 - 29 * 86400, n2 - 14 * 86400, n2 - n2 % 60)
        d5, _ = pd_.poll(n2)
        seam = d5[(d5.time >= NT_ROLL - 7200) & (d5.time < NT_ROLL + 3600)]          # 16:55 close -> 18:00 open
        jump = float(np.abs(seam["open"].values[1:] - seam["close"].values[:-1]).max())
        feed5 = nb5[(nb5.time >= n2 - 29 * 86400) & (nb5.time + 300 <= n2)]
        r = roll_check.diagnose(tv5_old, pcbars.archive_read("NQ", "5m", pd_.arc), feed5, dt.date(2026, 9, 10), "NQU26",
                                order_name="MNQ 12-26")
        check(f"the bot cannot repair it (a {jump:.2f}-pt jump stays at the rollover in its frame); tools/roll_check.py "
              "flags 'Merge back adjusted'",
              jump > 200 and any("Merge back adjusted" in x for x in r["actions"]), (jump, r))

        # ---------------------------------------------------------------- E
        print("E. cloud monitor on the PC's heartbeat bars", flush=True)
        import cloud_monitor as cm
        from engine import live
        from engine.lab_adapter import live_model
        out = os.path.join(tmp, "dash")
        os.makedirs(out, exist_ok=True)
        lm = live_model()
        pcE = PC(tmp, "E", tv5_old, tv1_old)

        def cloud_poll(now):
            hb_files = pcbars.PCBars(sym="NQ", root=pcE.arc).files(pcE.bot, now=now)
            hb = {"present": True, "age_s": 30, "t": now, "files": hb_files, "bars": pcbars.PCBars.meta(hb_files, pcE.bot)}
            feed = pcbars.CloudFeed(out, hb, now, sym="NQ")
            b = live.LiveBot()
            b.no_yahoo = True
            b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "data_source": "pc-ninjatrader", "no_yahoo": True,
                     "params": {}, "window_days": 20}
            b.fetch_recent = feed.recent
            b.read_hist = lambda sym, tf: (tv5_old if tf == "5m" else tv1_old if tf == "1m" else pd.DataFrame(columns=COLS)) \
                if sym == "NQ" else pd.DataFrame(columns=COLS)
            b.clock = lambda: now
            df_all, _ = b._merged("NQ", "5m", now, 300)
            res = cm.run_model(lm, b, df_all, now, store_1m=os.path.join(out, "bars_1m.csv"), week_hist=None)
            return feed, df_all, res

        for k, now in enumerate((n1, n1 + 3 * 3600)):
            write_feed(pcE.folder, O1, O5, now - 29 * 86400, now - 14 * 86400, now - now % 60)
            pcE.poll(now)
            cloud_poll(now)
        store1_old = pd.read_csv(os.path.join(out, "bars_1m.csv"))
        for now in (n2, n2 + 3600, n3):
            write_feed(pcE.folder, T1, T5, now - 29 * 86400, now - 14 * 86400, now - now % 60)
            pcE.poll(now)
            feed, df_all, res = cloud_poll(now)
            if now == n2:
                sh2 = feed.shift
        e5, s5, _ = diff(feed.five, T5, int(feed.five.time.min()), n3 - 300)
        ew, sw, _ = diff(df_all, T5, window_start(n3), n3 - 300)
        check(f"cloud 5m store (pc_bars_5m.csv) on the old contract + the PC's new bars: back-adjusted ({sh2:+.2f}), store "
              "and the LIT window equal the truth", sh2 == G and e5 < 1e-6 and s5 and ew < 1e-6 and sw, (sh2, e5, ew, sw))
        st1 = pd.read_csv(os.path.join(out, "bars_1m.csv"))
        mo = st1.merge(O1, on="time", suffixes=("", "_o"))
        mt = st1.merge(T1, on="time", suffixes=("", "_t"))
        n_old = int((np.abs(mo["close"] - mo["close_o"]) < 1e-6).sum())
        n_new = int((np.abs(mt["close"] - mt["close_t"]) < 1e-6).sum())
        t1m = T1[T1.time.isin(set(st1.time))]
        r_true = lit_run(T5[T5.time < n3], t1m, n3)
        check(f"cloud 1m store (bars_1m.csv) holds both contracts ({n_old} old-contract minutes, {n_new} new): LIT shifts "
              f"each 5m window onto the 5m basis, so the cloud's LIT trades equal the truth's ({len(r_true['trades'])} trades)",
              n_old > 0 and n_new > 0 and trades_key(res) == trades_key(r_true), (n_old, n_new, trades_key(res)[-3:],
                                                                                 trades_key(r_true)[-3:]))

        # ---------------------------------------------------------------- F
        print("F. NinjaTrader orders (OIF instrument names)", flush=True)
        from engine import ninjatrader as nt
        check("nt_instrument: Wed 2026-12-09 MNQ 12-26 / NQ 12-26; Thu 2026-12-10 MNQ 03-27 / NQ 03-27; Thu 2027-03-11 MNQ 06-27",
              nt.nt_instrument("MNQ", dt.date(2026, 12, 9)) == "MNQ 12-26" and nt.nt_instrument("NQ", dt.date(2026, 12, 9)) == "NQ 12-26"
              and nt.nt_instrument("MNQ", dt.date(2026, 12, 10)) == "MNQ 03-27" and nt.nt_instrument("NQ", dt.date(2026, 12, 10)) == "NQ 03-27"
              and nt.nt_instrument("MNQ", dt.date(2027, 3, 11)) == "MNQ 06-27")
        fold = os.path.join(tmp, "F", "NinjaTrader 8")
        fake = nt._FakeNT(fold, price=25280.0)
        clk = [at(2026, 12, 9, 10, 5)]

        def make(extra=None):
            cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": fold, "params": {"max_micros": 40, "flat_mod": 955},
                   "nt_state_path": os.path.join(tmp, "F", "nt_state.json"), "nt_audit_log": os.path.join(tmp, "F", "oif.log"),
                   **(extra or {})}
            ad = nt.NinjaTraderAdapter(cfg, clock=lambda: clk[0])
            ad._sleep = lambda s: (fake.process(), clk.__setitem__(0, clk[0] + s))
            ad._alert_fn = lambda *a, **kw: None
            return ad

        def lines_since(k):
            return [ln for _, ls in fake.files[k:] for ln in ls]

        ad = make()
        k0 = len(fake.files)
        r9 = ad.place_bracket({"side": "buy", "qty": 2, "entry": 25275.0, "stop": 25240.0, "target": 25350.0, "entry_t": clk[0]})
        l9 = lines_since(k0)
        clk[0] = at(2026, 12, 10, 0, 30)                         # the bot keeps running past midnight ET
        inst_now = ad._instruments()["micro"]
        k1 = len(fake.files)
        ad.flatten({})
        lf = lines_since(k1)
        check("Wed 12-09: orders on MNQ 12-26; past midnight (Thu 12-10) the bot names MNQ 03-27 for new orders, but the "
              "open 12-26 leg is closed on MNQ 12-26",
              r9.get("ok") and all(";MNQ 12-26;" in x for x in l9 if x.startswith("PLACE")) and inst_now == "MNQ 03-27"
              and any(x.startswith("CLOSEPOSITION") and ";MNQ 12-26;" in x for x in lf), (r9, l9[:2], inst_now, lf[:2]))
        clk[0] = at(2026, 12, 10, 10, 5)
        fake.pos.clear()
        ad2 = make()
        ad2.legs = []
        k2 = len(fake.files)
        # the chart was left on MNQ 12-26: the signal is on December prices, ~280 pts under March (the fake fills at 25280)
        r10 = ad2.place_bracket({"side": "buy", "qty": 2, "entry": 25000.0, "stop": 24950.0, "target": 25100.0, "entry_t": clk[0]})
        l10 = lines_since(k2)
        legs = r10.get("legs") or [{}]
        fill = legs[0].get("fill_px")
        # (2026-10-20 roll guard) an LE_BarFeed that writes le_feed/MNQ_instrument.txt refuses this entry before it is sent
        # (tests/test_nt_roll_guard.py); without that file the fill-gap backstop catches it: no December-priced bracket
        check("Thu 12-10, chart NOT switched: the order goes to MNQ 03-27 and fills ~280 pts above the December-priced plan; "
              "the fill-gap guard places NO stop (24950) / target (25100) and flattens at once",
              any(";MNQ 03-27;" in x for x in l10 if x.startswith("PLACE")) and fill and fill - 24950.0 > 300
              and not r10.get("ok") and not any("STOPMARKET" in x for x in l10)
              and any(x.startswith("CLOSEPOSITION") for x in l10), (r10, l10[:4]))
        ad2.flatten({})
        ad3 = make({"nt_instrument": "MNQ 12-26"})
        check("nt_instrument 'MNQ 12-26' (start cfg / --instrument) pins the order contract on Thu 12-10",
              ad3._instruments()["micro"] == "MNQ 12-26")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            nt.main(["--status", "--folder", fold, "--instrument", "MNQ 03-27"])
        sent = {}
        saved_http = nt._http
        nt._http = lambda port, path, body=None: (sent.update({path: body}) or {"ok": True, "log": []})
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                nt.main(["--start", "--folder", fold, "--instrument", "MNQ 03-27"])
        finally:
            nt._http = saved_http
        check("--instrument 'MNQ 03-27': --status shows it, --start passes nt_instrument to the bot",
              "Instrument(s)      : MNQ 03-27" in buf.getvalue()
              and (sent.get("/api/live/start") or {}).get("nt_instrument") == "MNQ 03-27", (buf.getvalue()[:400], sent))
        # roll_check on the chart-contract question (frames from scenario A; anchor = the old contract)
        arcA = pcbars.archive_read("NQ", "5m", pc.arc)
        old_feed = O5[(O5.time >= n2 - 29 * 86400) & (O5.time + 300 <= n2)]
        new_feed = T5[(T5.time >= n2 - 29 * 86400) & (T5.time + 300 <= n2)]
        arc_old = O5[(O5.time >= n1 - 29 * 86400) & (O5.time < n1)]
        r_left = roll_check.diagnose(tv5_old, arc_old, old_feed, dt.date(2026, 12, 10), "NQZ26")
        r_sw = roll_check.diagnose(tv5_old, arc_old, new_feed, dt.date(2026, 12, 10), "NQZ26")
        r_bot = roll_check.diagnose(tv5_old, arcA, new_feed, dt.date(2026, 12, 10), "NQZ26")
        r_early = roll_check.diagnose(tv5_old, arc_old, old_feed, dt.date(2026, 12, 9), "NQZ26")
        r_wed = roll_check.diagnose(tv5_old, arc_old, new_feed, dt.date(2026, 12, 9), "NQZ26")
        check("roll_check: chart left on 12-26 on Thu 12-10 -> ACTION 'switch the NinjaTrader chart to MNQ 03-27'; switched "
              "(before or after the bot's first poll) -> chart MNQ 03-27, no action; Wed 12-09 on 12-26 -> fine; Wed 12-09 "
              "evening already on 03-27 -> fine ('orders switch ... at midnight')",
              any("switch the NinjaTrader chart to MNQ 03-27" in x for x in r_left["actions"])
              and r_sw["chart"] == "MNQ 03-27" and not r_sw["actions"] and r_bot["chart"] == "MNQ 03-27" and not r_bot["actions"]
              and r_early["chart"] == "MNQ 12-26" and not r_early["actions"]
              and not r_wed["actions"] and any("midnight" in x for x in r_wed["lines"]), (r_left, r_sw, r_bot, r_early, r_wed))
        check("no Yahoo call anywhere in the roll scenarios", not undo.calls, undo.calls)
    finally:
        undo()
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nroll test: {'PASS' if n_ok == len(RESULTS) else 'FAIL'} ({n_ok}/{len(RESULTS)})")
    return n_ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
