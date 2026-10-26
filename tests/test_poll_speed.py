"""Poll speed with every background feature ON (owner's Surface 2026-10-26: polls of 5-32 s; here 0.57 s alone, 2.5 s
median / 5 s p90 once the paper work ran in threads next to it, because Python runs one thread at a time per process).

    python -X utf8 -m tests.test_poll_speed             # benchmark + identity + robustness (~3 min)
    python -X utf8 -m tests.test_poll_speed --quick     # fewer polls (~1.5 min)
    python -X utf8 -m tests.test_poll_speed --compare   # + the old way (paper work in threads) for the before / after table

1. Benchmark: engine/live.py LiveBot (LIT, paper, temp state, frozen clock, bars revealed as they close) with every
   background feature on: second strategies + stop-hunt candidates + the ATLAS v2 shadow, trade pictures, account B (paper,
   Builder 25K, routes in the loop), Bot Brain; polled back to back around a LIT entry (2026-10-14), the worst case (the
   paper work of one poll still running during the next). LIT path = poll start -> LIT decided and routed (health.lit_ms).
   FAILS when its median is above 1.6 x the median with every background feature off + 150 ms, its p90 above 2 x + 300 ms,
   or the median above 3 s. Prints the stage table (engine/poll_timing.py) of the polls.
2. Identity: the background worker process (engine/bg_worker.py) gives what the threads gave: two LiveBots on the same
   polls, one with the worker and one with the threads -> the same LIT orders, the same second-strategy run, the same ATLAS
   v2 shadow state, the same trade pictures (byte for byte); bar frames sent as deltas rebuild exactly (growing, a revised
   bar, a back-adjusted history, a shorter frame, no 1m frame, another index); the child loads no order / broker module and
   runs at a lower priority.
3. Robustness: a job that raises -> its error, the child lives; a child that dies / hangs -> the job's callback, busy
   cleared, a new child; MAX_FAILS deaths in a row -> worker off and the LiveBot runs the paper work in its thread again.
4. Off the poll path: news / VIX downloads in a background thread (engine/news.py background_refresh; off = as before), the
   calendar archive not rewritten when unchanged, data._tag identical to the old per-bar strftime, the learning loop's ES
   bars read from the last copy in the poll and refreshed after the routing.
No network; temp folders only; the real data/ and logs/ files are checked unchanged at the end.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import statistics
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import bg_worker, data as D, live, news, poll_timing, trade_chart  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
ENTRY_T = 1791969840                  # LIT's 2026-10-14 entry (run lit_live): a 1m CISD short at 09:44 ET
AB = {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-10-12", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"],
      "sizing": "need", "prior_pnl": 0.0}
WATCH = [os.path.join(ROOT, "data", f) for f in ("VIX_1d.csv", "VXN_1d.csv", "live_state.json", "account_b.json",
                                                 "live_state_atlas_v2.json", "live_state_acctb.json")] + \
    [os.path.join(ROOT, "data", "news", f) for f in ("ff_thisweek.json", "ff_archive.csv")] + \
    [os.path.join(ROOT, "logs", "charts", "index.json")]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not ok else ""), flush=True)


def digest():
    out = {}
    for p in WATCH:
        try:
            out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None


# ------------------------------------------------------------------------------------------------ harness
class Rig:
    """tests/test_live_dryrun.Replay + the 1m feed's forming bar (LE_BarFeed's open file), like tests/test_lit_live."""

    def __init__(self):
        from tests.test_live_dryrun import Replay
        self.rp = rp = Replay()
        df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        rp.frames[("NQ", "1m")] = df1[df1["time"] >= ENTRY_T - 75 * 86400].reset_index(drop=True)
        o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))

        def forming(sym, interval, period="5d"):
            t = rp.now - rp.now % 60
            if sym == "NQ" and interval == "1m" and t in o1:
                return pd.DataFrame([{"time": t, "open": o1[t], "high": o1[t], "low": o1[t], "close": o1[t], "volume": 0.0}])
            return pd.DataFrame()
        rp.recent_hook = forming
        self.keep = (news.ff_calendar, news.volatility, news.guard)
        rp.install_globals()
        self.tmp = tempfile.mkdtemp(prefix="le_pollspeed_")

    def bot(self, tag, bg=True, start_t=None):
        d = os.path.join(self.tmp, tag)
        os.makedirs(d, exist_ok=True)
        cfg = {"nt_archive": None}
        if bg:
            cfg.update(second=True, charts=True, charts_root=os.path.join(d, "charts"), account_b=dict(AB))
        else:
            cfg.update(account_b=None)
        return self.rp.bot(cfg=cfg, state_path=os.path.join(d, "live_state.json"), start_now=start_t or ENTRY_T - 6 * 3600)

    def poll(self, b, w, errors):
        return self.rp.poll(b, w, errors)

    def close(self):
        news.ff_calendar, news.volatility, news.guard = self.keep
        self.rp.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)


def wait_idle(b, timeout=240.0):
    """The worker / threads finished this bot's paper work (second + pictures)."""
    w = bg_worker.shared()
    t_end = time.time() + timeout
    while time.time() < t_end:
        busy = getattr(b, "_second_busy", False) or w.busy("second", id(b)) or w.busy("charts", id(b)) or \
            bool(getattr(getattr(b, "charts", None), "busy", False))
        if not busy:
            return True
        time.sleep(0.2)
    return False


def run_polls(rig, b, times, timed=False):
    errors, lit, tot, tables = [], [], [], []
    for w in times:
        t0 = time.perf_counter()
        rig.poll(b, w, errors)
        tot.append((time.perf_counter() - t0) * 1000)
        lit.append(float(b.health.get("lit_ms") or tot[-1]))
        if timed:
            tables.append(b.health.get("poll_stages"))
    return {"lit": lit, "tot": tot, "errors": errors, "tables": tables}


def stage_avg(tables) -> list:
    acc = {}
    for ps in tables:
        for s in (ps or {}).get("stages") or []:
            if " > " in s["name"] and s["ms"] < 20:
                continue
            a = acc.setdefault(s["name"], [0, 0, 0])
            a[0] += s["ms"]
            a[1] += s["cpu_ms"]
            a[2] += 1
    n = max(1, len(tables))
    return [(k, round(v[0] / n), round(v[1] / n)) for k, v in acc.items()]


def orders(b):
    return [{k: r.get(k) for k in ("side", "qty", "stop", "target", "entry_t", "reason", "pnl")} for r in b.ledger
            if r.get("side") in ("buy", "sell", "exit", "modify")]


# ------------------------------------------------------------------------------------------------ 1. benchmark
def bench(rig, quick=False, compare=False):
    print("1. benchmark: the LIT path of the poll with every background feature on", flush=True)
    n = 24 if quick else 40
    times = [ENTRY_T - 600 + 30 * i + 2 for i in range(n)]          # every 30 s (2 s / 32 s after the minute) through the entry
    poll_timing.install()
    runs = {}
    plan = [("off", False, None), ("worker", True, None)] + ([("threads", True, "threads")] if compare else [])
    w = bg_worker.shared()
    for tag, bg, mode in plan:
        keep_off = w.off_reason
        if mode == "threads":
            w.off_reason = "test: the old threads"
        try:
            b = rig.bot(f"bench_{tag}", bg=bg)
            if bg and mode is None:                         # the child starts and loads its modules before the clock runs
                b.health["lit_ms"] = None
            r = run_polls(rig, b, times, timed=True)
            r["orders"] = orders(b)
            r["bot"] = b
            if bg:
                wait_idle(b)
            runs[tag] = r
        finally:
            w.off_reason = keep_off
    off, on = runs["off"], runs["worker"]
    med_off, med_on = statistics.median(off["lit"]), statistics.median(on["lit"])
    p90_off, p90_on = q(off["lit"], 0.9), q(on["lit"], 0.9)
    print(f"   LIT path, background OFF:        median {med_off:6.0f} ms  p90 {p90_off:6.0f} ms  max {max(off['lit']):6.0f} ms")
    print(f"   LIT path, background ON (worker): median {med_on:6.0f} ms  p90 {p90_on:6.0f} ms  max {max(on['lit']):6.0f} ms"
          f"   (whole poll median {statistics.median(on['tot']):.0f} ms)")
    if "threads" in runs:
        th = runs["threads"]
        print(f"   LIT path, background ON (threads, the old way): median {statistics.median(th['lit']):6.0f} ms  "
              f"p90 {q(th['lit'], 0.9):6.0f} ms  max {max(th['lit']):6.0f} ms")
    print("   stage averages (ms wall / ms CPU): " + "  |  ".join(
        f"{tag}: " + ", ".join(f"{k} {a}/{c}" for k, a, c in stage_avg(r["tables"]) if a >= 5) for tag, r in runs.items()))
    info = bg_worker.shared().info()
    print(f"   worker: {json.dumps(info)}")
    check("benchmark: every poll ran (no errors), background OFF and ON", not off["errors"] and not on["errors"],
          (off["errors"] + on["errors"])[:2])
    check("benchmark: the LIT entry was routed the same way with the background work on (side, micros, stop, target)",
          on["orders"] == off["orders"] and any(o["side"] in ("buy", "sell") for o in on["orders"]), (on["orders"], off["orders"]))
    lim_med, lim_p90 = 1.6 * med_off + 150, 2.0 * p90_off + 300
    check(f"benchmark: LIT path median with the background ON {med_on:.0f} ms <= {lim_med:.0f} ms (1.6 x OFF + 150) and <= 3000 ms",
          med_on <= lim_med and med_on <= 3000, (med_on, med_off))
    check(f"benchmark: LIT path p90 with the background ON {p90_on:.0f} ms <= {lim_p90:.0f} ms (2 x OFF + 300)", p90_on <= lim_p90,
          (p90_on, p90_off))
    b = on["bot"]
    check("benchmark: the background work really ran in the worker (second run, ATLAS v2 shadow, pictures, account B)",
          b.second and b.atlas_v2 and (getattr(b, "_charts_drawn", None) or {}) and b.acct_b is not None
          and info["jobs"] >= 2 and info["pid"], {"second": bool(b.second), "av2": bool(b.atlas_v2), "info": info})
    if "threads" in runs:
        th = runs["threads"]
        check("benchmark: the gate catches the old way (paper work in threads next to the poll) as a regression",
              statistics.median(th["lit"]) > lim_med or q(th["lit"], 0.9) > lim_p90,
              (statistics.median(th["lit"]), q(th["lit"], 0.9)))
    return runs


# ------------------------------------------------------------------------------------------------ 2. identity
def identity(rig):
    print("2. identity: the worker process gives what the threads gave", flush=True)
    times = [ENTRY_T - 120 + 30 * i + 2 for i in range(8)]
    w = bg_worker.shared()
    got = {}
    for tag in ("worker", "threads"):
        keep_off = w.off_reason
        if tag == "threads":
            w.off_reason = "test: threads"
        try:
            b = rig.bot(f"id_{tag}", bg=True)
            errors = []
            for t in times:
                rig.poll(b, t, errors)
                if not wait_idle(b):                     # each poll's paper work done before the next (same inputs both ways)
                    errors.append((t, "paper work did not finish"))
            got[tag] = {"b": b, "errors": errors, "orders": orders(b),
                        "second": json.dumps(b.second, sort_keys=True, default=str),
                        "av2": json.dumps({k: v for k, v in (b.atlas_v2 or {}).items()}, sort_keys=True, default=str)}
        finally:
            w.off_reason = keep_off
    a, t = got["worker"], got["threads"]
    check("identity: no poll errors either way", not a["errors"] and not t["errors"], (a["errors"] + t["errors"])[:2])
    check("identity: the same LIT orders (routing untouched)", a["orders"] == t["orders"])
    check("identity: the same second-strategy run (ATLAS members + stop-hunt candidates, PAPER)", a["second"] == t["second"] and
          a["b"].second is not None, (len(a["second"]), len(t["second"])))
    check("identity: the same ATLAS v2 PAPER shadow state", a["av2"] == t["av2"] and a["b"].atlas_v2 is not None)

    def pics(b):
        root = b.cfg.get("charts_root")
        out = {}
        for dp, _dn, fn in os.walk(root or ""):
            for f in fn:
                if f.endswith(".png"):
                    out[os.path.relpath(os.path.join(dp, f), root)] = hashlib.sha256(open(os.path.join(dp, f), "rb").read()).hexdigest()
        ix = json.load(open(os.path.join(root, "index.json"), encoding="utf-8")) if os.path.exists(os.path.join(root, "index.json")) else {}
        rows = {k: [{x: r.get(x) for x in r if x not in ("made",)} for r in v] for k, v in (ix.get("strategies") or {}).items()}
        return out, rows
    pa, ra = pics(a["b"])
    pt, rt = pics(t["b"])
    check(f"identity: the same trade pictures, byte for byte ({len(pa)} PNG files), and the same index rows",
          pa and pa == pt and ra == rt, (len(pa), len(pt), sorted(set(pa) ^ set(pt))[:4]))

    # bar frames as deltas
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] < ENTRY_T].reset_index(drop=True)
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    df1 = df1[(df1["time"] < ENTRY_T) & (df1["time"] >= ENTRY_T - 20 * 86400)].reset_index(drop=True)
    W = bg_worker.Worker()
    steps = []
    f5, f1 = df5.iloc[:-50].reset_index(drop=True), df1.iloc[:-200].reset_index(drop=True)
    steps.append(("first: full frames", f5, f1))
    f5 = df5.iloc[:-49].reset_index(drop=True)
    steps.append(("one new 5m bar", f5, df1.iloc[:-199].reset_index(drop=True)))
    f5r = f5.copy()
    f5r.loc[len(f5r) - 1, "close"] += 0.25
    steps.append(("a revised last bar", f5r, df1.iloc[:-150].reset_index(drop=True)))
    f5s = f5r.copy()
    for c in ("open", "high", "low", "close"):
        f5s[c] = f5s[c] - 12.5
    steps.append(("the whole history back-adjusted (a roll)", f5s, df1))
    steps.append(("a shorter frame", f5s.iloc[:-500].reset_index(drop=True), df1))
    steps.append(("no 1m frame", f5s, None))
    odd = f5s.iloc[100:].copy()
    steps.append(("a frame with its own index", odd, df1))
    ok_all, bad = True, []
    sizes = []
    for name, x5, x1 in steps:
        ev, box = threading.Event(), {}
        prev = dict(W.sent)
        st = W.submit("echo", {"n": name}, {"df5": x5, "df1": x1}, lambda r, e: (box.update(r=r, e=e), ev.set()))
        ev.wait(120)
        r = box.get("r") or {}
        try:
            pd.testing.assert_frame_equal(r.get("df5"), x5)
            if x1 is None:
                assert r.get("df1") is None
            else:
                pd.testing.assert_frame_equal(r.get("df1"), x1)
        except Exception as e:
            ok_all = False
            bad.append((name, st, box.get("e"), str(e)[:200]))
        pk5, _ = bg_worker.frame_packet(x5, prev.get("df5"))
        sizes.append((name, pk5["keep"], len(pk5["arr"]["time"])))
    check("frames: every step rebuilt exactly in the child (growing, revised bar, back-adjusted, shorter, no 1m, other index)",
          ok_all, bad)
    check("frames: an unchanged history is not sent again (only the last rows), a back-adjusted / re-indexed one is",
          sizes[1][1] > 0 and sizes[1][2] <= bg_worker.TAIL + 5 and sizes[3][1] == 0 and sizes[6][1] == 0, sizes)
    W.stop()
    ev, box = threading.Event(), {}                          # the shared worker's child, after its second / picture jobs
    bg_worker.shared().submit("echo", {"frames": False}, {}, lambda r, e: (box.update(r=r, e=e), ev.set()), owner="modcheck")
    ev.wait(60)
    mods = (box.get("r") or {}).get("modules") or []
    nice = (box.get("r") or {}).get("nice")
    # (engine.account_b / multi_account come in for their sizing functions: the ATLAS v2 shadow sizes with account_b.qty)
    check("the child imports no module that can send an order (engine.live, ninjatrader, tradovate, guards, alerts / push)",
          "engine.second" in mods and not any(m in mods for m in ("engine.live", "engine.ninjatrader", "engine.tradovate",
                                                                  "engine.guards", "engine.alerts", "engine.push")), mods)
    check("the child runs at a lower CPU priority than the bot (nice 10 / BELOW_NORMAL)",
          nice is not None and (nice >= 10 if os.name != "nt" else nice == 0x4000), nice)


# ------------------------------------------------------------------------------------------------ 3. robustness
def robust(rig):
    print("3. robustness: errors, deaths, hangs, off -> threads", flush=True)
    keep = (bg_worker.RESTART_GAP_S, bg_worker.JOB_TIMEOUT_S, bg_worker.MAX_FAILS)
    bg_worker.RESTART_GAP_S = 0.0
    W = bg_worker.Worker(log=lambda t: None)
    try:
        def call(args, kind="echo", wait=60.0):
            ev, box = threading.Event(), {}
            st = W.submit(kind, args, {}, lambda r, e: (box.update(r=r, e=e), ev.set()))
            if st == "queued":
                ev.wait(wait)
            return st, box
        st, box = call({"raise": "boom", "frames": False})
        pid0 = (W.info() or {}).get("pid")
        st2, box2 = call({"frames": False})
        check("a job that raises: its callback gets the error, the child lives on (same pid, next job fine)",
              box.get("e") and "boom" in box["e"] and box2.get("r") and box2["r"]["pid"] == pid0, (box, box2.get("e")))
        st, box = call({"exit": 3, "frames": False})
        check("a child that dies mid-job: the callback gets an error, nothing stays busy", box.get("e") and "stopped" in box["e"]
              and not W.busy("echo"), box)
        st2, box2 = call({"frames": False})
        check("then a new child starts on the next job", st2 == "queued" and box2.get("r") and box2["r"]["pid"] != pid0, (st2, box2))
        bg_worker.JOB_TIMEOUT_S = 1.0
        ev, b3 = threading.Event(), {}
        W.submit("echo", {"sleep": 30, "frames": False}, {}, lambda r, e: (b3.update(r=r, e=e), ev.set()))
        time.sleep(1.5)
        st4 = W.submit("echo", {"frames": False}, {}, lambda r, e: None, owner="other")
        ev.wait(10)
        check("a hung job (longer than JOB_TIMEOUT_S): the child is killed, the job's callback gets an error",
              b3.get("e") and "longer than" in b3["e"], (st4, b3))
        bg_worker.JOB_TIMEOUT_S = keep[1]
        time.sleep(0.5)
        bg_worker.MAX_FAILS = 2
        W.fails = 0
        for _ in range(3):
            call({"exit": 2, "frames": False}, wait=20)
        check("MAX_FAILS deaths in a row: the worker turns itself off (submit says 'off')",
              W.off_reason is not None and W.submit("echo", {}, {}, lambda r, e: None) == "off", W.info())
    finally:
        W.stop()
        bg_worker.RESTART_GAP_S, bg_worker.JOB_TIMEOUT_S, bg_worker.MAX_FAILS = keep
    # the LiveBot falls back to its thread when the worker is off
    w = bg_worker.shared()
    keep_off = w.off_reason
    w.off_reason = "test: off"
    try:
        b = rig.bot("fallback", bg=True)
        errors = []
        rig.poll(b, ENTRY_T + 62, errors)
        wait_idle(b)
        check("worker off: the LiveBot runs the paper work in its thread as before (second run + ATLAS v2 set, pictures drawn)",
              not errors and b.second is not None and b.atlas_v2 is not None and getattr(b, "charts", None) is not None,
              (errors[:1], b.second is not None))
    finally:
        w.off_reason = keep_off


# ------------------------------------------------------------------------------------------------ 4. off the poll path
def offpath():
    print("4. off the poll path: news / VIX downloads, the archive, the bar tags, ES learning bars", flush=True)
    calls = []

    def slow():
        calls.append(time.time())
        time.sleep(1.0)
        return len(calls)
    keep = dict(news._cache), news._BG["on"]
    try:
        news._BG["on"] = False
        news._cache.pop("t_slow", None)
        a = news._cached("t_slow", 0.0, slow)
        t0 = time.time()
        b = news._cached("t_slow", 0.0, slow)
        sync_s = time.time() - t0
        news.background_refresh(True)
        t0 = time.time()
        c = news._cached("t_slow", 0.0, slow)
        bg_s = time.time() - t0
        d = news._cached("t_slow", 0.0, slow)               # a second read while the download runs: no second download
        time.sleep(1.4)
        n3 = len(calls)
        e = news._cached("t_slow", 0.0, slow)
        check("news off (default): an expired entry is downloaded by the caller (as before)", a == 1 and b == 2 and sync_s >= 0.9,
              (a, b, sync_s))
        check("news background_refresh: an expired entry is served at once, downloaded once in a thread, then fresh",
              c == 2 and d == 2 and bg_s < 0.2 and n3 == 3 and e == 3, (c, d, e, bg_s, n3))
        time.sleep(1.2)                                      # the last refresh thread ends before the cache is restored
    finally:
        news._cache.clear()
        news._cache.update(keep[0])
        news._BG["on"] = keep[1]
    # the archive: an unchanged calendar does not rewrite ff_archive.csv
    tmp = tempfile.mkdtemp(prefix="le_news_")
    keep_news = news.NEWS
    try:
        news.NEWS = tmp
        ev = [{"t": 1791969840, "currency": "USD", "impact": "high", "event": "CPI"}]
        news._archive(ev)
        p = os.path.join(tmp, "ff_archive.csv")
        m1 = os.stat(p).st_mtime_ns
        time.sleep(0.05)
        news._archive(ev)
        m2 = os.stat(p).st_mtime_ns
        news._archive(ev + [{"t": 1791969840 + 86400, "currency": "USD", "impact": "high", "event": "PPI"}])
        rows = pd.read_csv(p)
        check("news archive: unchanged -> not rewritten (its time stays, the guard keeps its parse); new event -> written",
              m1 == m2 and len(rows) == 2, (m1, m2, len(rows)))
    finally:
        news.NEWS = keep_news
        shutil.rmtree(tmp, ignore_errors=True)
    # data._tag: identical to the per-bar strftime it replaced
    import numpy as _np
    ok, n = True, 0
    for f in ("NQ_5m.csv", "NQ_1m.csv", "ES_5m.csv", "NQ_1h.csv"):
        df = pd.read_csv(os.path.join(ROOT, "data", f)).sort_values("time").drop_duplicates("time")
        mod, tday, dow, ds = D._tag(df)
        ts = pd.to_datetime(df["time"].values, unit="s", utc=True).tz_convert("America/New_York")
        old = [x.strftime("%Y-%m-%d") for x in (ts + pd.Timedelta(hours=6)).normalize()]
        ok &= ds == old and all(type(x) is str for x in ds[:3]) and len(tday) == len(df) and _np.array_equal(
            tday, (ts + pd.Timedelta(hours=6)).normalize().tz_localize(None).values.astype("datetime64[D]").astype(_np.int64))
        n += len(df)
    check(f"data._tag: the trading-date text identical to the per-bar strftime on {n:,} bars (5 years of 5m, 1m, ES, 1h)", ok)
    # ES learning bars: the poll reads the last copy, the refresh comes after the routing
    b = live.LiveBot()
    b.state_path = live.STATE_PATH                            # _learn_es only works for the real bot; nothing is written here
    seen = []
    b._merged = lambda *a, **k: (seen.append(a[0]) or (pd.DataFrame({"time": [100]}), {}))
    b.no_yahoo = False
    r1 = b._learn_es("NQ", "5m", 1000, 300)                   # first poll: no copy yet -> fetched now
    r2 = b._learn_es("NQ", "5m", 1400, 300)                   # 400 s later, in the poll: the last copy, no fetch
    r3 = b._learn_es("NQ", "5m", 1400, 300, refresh=True)     # after the routing: fetched again
    r4 = b._learn_es("NQ", "5m", 1500, 300, refresh=True)     # < 5 min since: kept
    check("ES learning bars: fetched once at the first poll, then only after the routing (every 5 min), never inside a poll",
          r1 is not None and r2 is r1 and r3 is not None and len(seen) == 2 and r4 is r3, (len(seen),))
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    i, j, k = src.find("es_df=self._learn_es(sym, tf, now, secs)"), src.find("self._route_signals(res, sym, now, secs)"), \
        src.find("self._learn_es(sym, tf, now, secs, refresh=True)")
    check("live.py: the poll's LIT run reads the ES copy, the refresh is after the routing and the state save",
          0 < i < j < k and src.find("self._save_state()", j) < k)


def main():
    before = digest()
    rig = Rig()
    try:
        bench(rig, quick="--quick" in sys.argv, compare="--compare" in sys.argv)
        identity(rig)
        robust(rig)
        offpath()
    finally:
        rig.close()
        try:
            bg_worker.shared().stop()
        except Exception:
            pass
    check("the real data/ and logs/ files did not change", digest() == before)
    print(f"poll speed: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
