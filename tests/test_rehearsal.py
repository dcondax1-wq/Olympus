"""Dress rehearsal of a live night: the real server.py on a copy of the repo, a fake NinjaTrader 8 folder fed bar by bar
from data/NQ_1m.csv + data/NQ_5m.csv, a fake NinjaTrader that fills the order files, and the owner's clicks over HTTP.

    python -X utf8 -m tests.test_rehearsal                 # every rehearsal day (~10 sessions, see DAYS), ~1 h on one core
    python -X utf8 -m tests.test_rehearsal --days=2026-08-28,2026-09-02 [--jobs=5] [--fast] [--keep]

What it does (Paper / Sim101 only; no real account is ever armed, the live phrase is never written anywhere):
  sandbox    a temp copy of the code (engine, tools, tests, web, server.py, live_model.json exactly as committed) with its own
             data/ (TradingView history cut 2 sessions before each rehearsal day, as the export ends before tonight), its own
             git repo + a local bare "origin" (the heartbeat pushes there instead of GitHub), no network (dead proxy).
  clock      a virtual clock shared through a small mmap file: the server process runs with time.time() = the virtual time
             (tests/test_rehearsal.py --serve wraps server.py), the bot's own aligned poll schedule (2 s / 32 s after each
             minute) waits on that clock, and the test steps it minute by minute through each session (01:50 - 16:05 ET).
  NinjaTrader a fake folder (incoming / outgoing / le_feed): MNQ_5m.csv, MNQ_1m.csv, MNQ_1m_open.csv (the forming bar's open)
             and MNQ_instrument.txt written as LE_BarFeed writes them; a responder thread plays NinjaTrader's ATI (reads and
             deletes every oif*.txt, checks every line against the documented grammar, fills MARKET orders at the forming
             bar's open + 1 tick, works STOPMARKET / LIMIT orders against each 1m bar's range, writes order-state and position
             files, honours OCO, CHANGE, CANCEL, CLOSEPOSITION, FLATTENEVERYTHING).
  the owner  GET /api/next/botctl/status (preflight: every row green), POST /api/next/botctl/start {"account": "Sim101"},
             HOLD TO KILL (POST /api/live/kill), a server restart mid-trade (process stopped, started again: Sim auto-resume).
Checks per day against the backtest (tools/lit_final.run = engine/lit.py run_x on all 2026 sessions, live_model.json "lit"):
  entry time / side / price (fill) / micros (two_week sizing of a fresh eval at -$100: engine/sizing.lit_qty), the bracket
  (stop / target OIF prices), the breakeven CHANGE to entry +/- 1.25, the 15-minute cut, every exit (reason, time), routed
  P&L and the broker's fill P&L; the eval clock (session 1 of 10, $ to go incl. the -$100 prior); the heartbeat payload
  (logs/heartbeat_last.json + the bare repo's heartbeat branch with the bar files); the health block; the execution tracker
  (engine/fill_audit, /api/next/pc/execution); the cloud monitor (tools/cloud_monitor.py on the pushed bars) trading the same
  paper trades. Writes research/lit/rehearsal.json.
"""
from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import mmap
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
TICK = 0.25
LIMIT_S = 10.0
OUT = os.path.join(ROOT, "research", "lit", "rehearsal.json")
CLOCK_SLOTS = 8          # base, real_at, cap, poll_done (virtual t of the last finished poll), poll_n, pos_open, busy, spare
_real_time = time.time
_real_sleep = time.sleep

# the rehearsal days (2026, chronological): what each one exercises
DAYS = [
    ("2026-06-19", "early close (CME halt 13:00): short, flat before the halt"),
    ("2026-08-12", "breakeven exit (be_off: stop to entry - 1.25)"),
    ("2026-08-17", "Monday rule: Monday took Friday's low -> the long setup is blocked, no trade"),
    ("2026-08-25", "target"),
    ("2026-08-26", "15:55 flat (EOD)"),
    ("2026-08-27", "no-trade day"),
    ("2026-08-28", "stop-out"),
    ("2026-09-02", "15-minute cut (t_check)"),
    ("2026-09-09", "KILL SWITCH mid-trade (HOLD TO KILL)"),
    ("2026-09-23", "server RESTART mid-trade (Sim auto-resume)"),
]
KILL_DAY, RESTART_DAY = "2026-09-09", "2026-09-23"
KILL_AFTER_MIN, RESTART_AFTER_MIN = 12, 6

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail if not ok else ""})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""), flush=True)
    return bool(ok)


def et_at(day, hh, mm, ss=0):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm, ss), ET).timestamp())


def hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M:%S") if t is not None else None


# ================================================================================================ the virtual clock
class VClock:
    """time.time() for the server process: base + (real now - real_at), capped at base + cap (a slow test step never lets
    the bot run into the next minute without its bar). Shared through an mmap'd file (8 doubles)."""

    def __init__(self, path, create=False):
        self.path = path
        if create:
            with open(path, "wb") as fh:
                fh.write(b"\0" * 8 * CLOCK_SLOTS)
        self.fh = open(path, "r+b")
        self.mm = mmap.mmap(self.fh.fileno(), 8 * CLOCK_SLOTS)

    def get(self, i):
        return struct.unpack_from("d", self.mm, 8 * i)[0]

    def put(self, i, v):
        struct.pack_into("d", self.mm, 8 * i, float(v))

    def set(self, t, cap=25.0):
        self.put(2, cap)
        self.put(1, _real_time())
        self.put(0, t)

    def now(self):
        base, at, cap = self.get(0), self.get(1), self.get(2)
        return base + min(max(0.0, _real_time() - at), cap)


# ================================================================================================ --serve: server.py on the clock
def serve(sandbox, clock_path, port):
    """Runs inside the sandbox: server.py with time.time() on the virtual clock (installed before any engine import, so
    every default argument bound to time.time sees it), the bot's poll sleeps waiting on that clock, every finished poll
    reported in the clock file. Nothing else of the server changes."""
    vc = VClock(clock_path)
    time.time = vc.now
    os.chdir(sandbox)
    sys.path.insert(0, sandbox)
    from engine import live
    orig_sleep, orig_poll = live.LiveBot._sleep_s, live.LiveBot.poll_once

    def _sleep_s(self):
        vc.put(7, -1)                             # computing the next wake (may wait for a late 1m bar: _await_nt_bar)
        s = orig_sleep(self)                      # the production schedule (2 s / 32 s offsets), on the virtual clock
        tgt = time.time() + s
        vc.put(7, tgt)                            # asleep until this virtual time
        while time.time() < tgt - 1e-6 and not self.stop_flag.is_set():
            _real_sleep(0.003)
        return 0.0

    def poll_once(self):
        t = time.time()
        vc.put(7, 0)
        vc.put(6, 1)
        try:
            return orig_poll(self)
        finally:
            vc.put(5, 1 if (self.state or {}).get("position") else 0)
            vc.put(3, t)
            vc.put(4, vc.get(4) + 1)
            vc.put(6, 0)
    live.LiveBot._sleep_s = _sleep_s
    live.LiveBot.poll_once = poll_once
    import server
    import uvicorn
    server.HEARTBEAT.every_s = 2.0                # a beat every 2 real seconds (each one carries the virtual time)
    uvicorn.run(server.app, host="127.0.0.1", port=int(port), log_level="warning")


def cloud(sandbox, clock_path, out):
    """Runs inside the sandbox: tools/cloud_monitor.py once at the virtual time (time.time patched, as in serve)."""
    vc = VClock(clock_path)
    t0 = vc.now()
    time.time = lambda: t0 + 0.0
    os.chdir(sandbox)
    sys.path.insert(0, sandbox)
    sys.argv = ["cloud_monitor.py", "--out", out]
    import runpy
    runpy.run_path(os.path.join(sandbox, "tools", "cloud_monitor.py"), run_name="__main__")


# ================================================================================================ the sandbox
SKIP_DATA = {"live_state.json", "autostart.json", "alerts.json", "tv.json", "tv_device.json", "ninjatrader_state.json",
             "memory.db", "push.json", "push_sent.json", "push_pc_key.json", "auto_resume.json", "autoupdate.json",
             "accounts.json", "shadow_ledger.json", "NQ_1m.csv", "NQ_5m.csv"}


def build_sandbox(base):
    repo = os.path.join(base, "repo")
    os.makedirs(repo)
    ign = shutil.ignore_patterns("__pycache__", "node_modules", "*.pyc", ".git")
    for d in ("engine", "tools", "tests", "web", "web_next", "ninjatrader", "scripts", "docs"):
        if os.path.isdir(os.path.join(ROOT, d)):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(repo, d), ignore=ign)
    for f in os.listdir(ROOT):
        p = os.path.join(ROOT, f)
        # never .git: in a worktree it is a FILE pointing at the real repository (the sandbox's git commands would run on it)
        if os.path.isfile(p) and not f.startswith((".env", ".git")):
            shutil.copy2(p, os.path.join(repo, f))
    shutil.copy2(os.path.join(ROOT, ".gitignore"), os.path.join(repo, ".gitignore"))
    os.symlink(os.path.join(ROOT, "research"), os.path.join(repo, "research"))      # read-only reference material
    dd = os.path.join(repo, "data")
    os.makedirs(dd)
    for f in os.listdir(os.path.join(ROOT, "data")):
        p = os.path.join(ROOT, "data", f)
        if f in SKIP_DATA:
            continue
        if os.path.isdir(p):
            os.symlink(p, os.path.join(dd, f))
        elif os.path.getsize(p) > 3e6:
            os.symlink(p, os.path.join(dd, f))
        else:
            shutil.copy2(p, os.path.join(dd, f))
    with open(os.path.join(repo, ".gitignore"), "a", encoding="utf-8") as fh:
        fh.write("\n# rehearsal sandbox\ndata/\nresearch\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "rehearsal", "GIT_AUTHOR_EMAIL": "r@local", "GIT_COMMITTER_NAME": "rehearsal",
           "GIT_COMMITTER_EMAIL": "r@local"}
    bare = os.path.join(base, "origin.git")
    assert not os.path.exists(os.path.join(repo, ".git")), "sandbox must not point at the real repository"
    env["GIT_CEILING_DIRECTORIES"] = base
    for cmd in (["git", "init", "-q", "--bare", bare], ["git", "-C", repo, "init", "-q"],
                ["git", "-C", repo, "symbolic-ref", "HEAD", "refs/heads/main"], ["git", "-C", repo, "add", "-A"],
                ["git", "-C", repo, "commit", "-q", "-m", "rehearsal sandbox"], ["git", "-C", repo, "remote", "add", "origin", bare],
                ["git", "-C", repo, "push", "-q", "origin", "main"]):
        subprocess.run(cmd, check=True, capture_output=True, env=env)
    return repo


class History:
    """The TradingView export as it would be on the PC: data/NQ_5m.csv and NQ_1m.csv cut at a given time."""

    def __init__(self, repo):
        self.repo = repo
        self.src = {}
        for tf in ("5m", "1m"):
            with open(os.path.join(ROOT, "data", f"NQ_{tf}.csv"), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            ts = [int(float(ln.split(",", 1)[0])) for ln in lines[1:]]
            self.src[tf] = (lines[0], lines[1:], ts)

    def cut(self, t_end):
        import bisect
        for tf, (head, rows, ts) in self.src.items():
            k = bisect.bisect_left(ts, t_end)
            with open(os.path.join(self.repo, "data", f"NQ_{tf}.csv"), "w", encoding="utf-8") as fh:
                fh.write(head + "\n" + "\n".join(rows[:k]) + "\n")


# ================================================================================================ fake NinjaTrader
def bars_of(tf):
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", f"NQ_{tf}.csv"))
    df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    return df


class Feed:
    """LE_BarFeed: le_feed/MNQ_5m.csv, MNQ_1m.csv (closed bars, time = bar open), MNQ_1m_open.csv (the forming 1m bar),
    MNQ_instrument.txt (the chart's contract). Files get the virtual time as mtime."""

    def __init__(self, folder, b1, b5, keep_days=8):
        self.dir = os.path.join(folder, "le_feed")
        os.makedirs(self.dir, exist_ok=True)
        self.b1, self.b5, self.keep = b1, b5, keep_days
        self.t1, self.t5 = b1["time"].values, b5["time"].values
        self.o1 = dict(zip(b1["time"].astype("int64"), b1["open"].astype(float)))
        self.c1 = b1["close"].values
        self.n1 = self.n5 = None

    @staticmethod
    def _line(r):
        return f"{int(r.time)},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f},{int(r.volume)}"

    def _touch(self, p, vt):
        os.utime(p, (vt, vt))

    def reset(self, now, inst):
        import numpy as np
        a = now - self.keep * 86400
        for name, df, ts, secs in (("MNQ_1m.csv", self.b1, self.t1, 60), ("MNQ_5m.csv", self.b5, self.t5, 300)):
            i0, i1 = int(np.searchsorted(ts, a)), int(np.searchsorted(ts, now - secs, side="right"))
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as fh:
                fh.write("time,open,high,low,close,volume\n")
                fh.write("".join(self._line(r) + "\n" for r in df.iloc[i0:i1].itertuples()))
            if secs == 60:
                self.n1 = i1
            else:
                self.n5 = i1
        with open(os.path.join(self.dir, "MNQ_instrument.txt"), "w", encoding="utf-8") as fh:
            fh.write(inst + "\n")
        self.publish(now)

    def publish(self, now):
        """Closed bars up to `now` appended, the forming bar's open written (LE_BarFeed on the first tick of the minute)."""
        import numpy as np
        for name, df, ts, secs, attr in (("MNQ_1m.csv", self.b1, self.t1, 60, "n1"), ("MNQ_5m.csv", self.b5, self.t5, 300, "n5")):
            n0 = getattr(self, attr)
            n = int(np.searchsorted(ts, now - secs, side="right"))
            p = os.path.join(self.dir, name)
            if n > n0:
                with open(p, "a", encoding="utf-8") as fh:
                    fh.write("".join(self._line(r) + "\n" for r in df.iloc[n0:n].itertuples()))
                setattr(self, attr, n)
            self._touch(p, now)
        m = int(now // 60 * 60)
        p = os.path.join(self.dir, "MNQ_1m_open.csv")
        if m in self.o1:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(f"{m},{self.o1[m]:.2f}\n")
            self._touch(p, now)
        for f in ("MNQ_instrument.txt",):
            self._touch(os.path.join(self.dir, f), now)

    def bar(self, t):
        """(o, h, l, c) of the 1m bar opening at t, or None."""
        import numpy as np
        k = int(np.searchsorted(self.t1, t))
        if k < len(self.t1) and int(self.t1[k]) == t:
            r = self.b1.iloc[k]
            return float(r.open), float(r.high), float(r.low), float(r.close)
        return None

    def price_at(self, t):
        """The market at t: the open of the minute forming (else the last close)."""
        import numpy as np
        m = int(t // 60 * 60)
        if m in self.o1:
            return self.o1[m]
        k = int(np.searchsorted(self.t1, m)) - 1
        return float(self.c1[max(0, k)])


def make_nt(folder, vc):
    """engine.ninjatrader._FakeNT (the self-test's NinjaTrader) with: virtual-time mtimes on every outgoing file, MARKET
    fills 1 tick against us (the backtest's market fill), stops / limits worked against each 1m bar."""
    from engine.ninjatrader import _FakeNT, LIVE_STATES

    class NT(_FakeNT):
        def __init__(self, *a, **kw):
            self.vt = vc.now
            super().__init__(*a, **kw)
            self.log = []                    # (virtual t, file name, [lines]) of every order file NinjaTrader processed
            self.fills = []                  # (virtual t, order id, type, action, qty, px)
            self.lock = threading.RLock()

        def _write(self, name, text):
            p = os.path.join(self.out, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            t = self.vt()
            os.utime(p, (t, t))

        def _fill(self, oid, qty, px):
            o = self.orders[oid]
            if o["type"] == "MARKET":
                px = self.price + (TICK if o["action"] == "BUY" else -TICK)
            self.fills.append((self.vt(), oid, o["type"], o["action"], qty, px))
            return super()._fill(oid, qty, px)

        def process(self, *_):
            with self.lock:
                n0 = len(self.files)
                super().process()
                for name, lines in self.files[n0:]:
                    self.log.append((self.vt(), name, lines))
                    if not lines:                # NinjaTrader read the file before it was written: that order is lost
                        self.errors.append((name, "empty order file read (the writer is not atomic)"))

        def bar(self, o, h, l, c):
            """One 1m bar of market: stops first (gap through the stop: filled at the open), then the limits, 1 tick of
            slippage on a stop (the backtest's stop exit), a limit at its price."""
            with self.lock:
                for want in ("STOPMARKET", "LIMIT"):
                    for oid, x in list(self.orders.items()):
                        if x["state"] not in LIVE_STATES or x["type"] != want:
                            continue
                        buy = x["action"] == "BUY"
                        rest = x["qty"] - x["filled"]
                        if rest <= 0:
                            continue
                        if want == "STOPMARKET" and ((buy and h >= x["stop"]) or (not buy and l <= x["stop"])):
                            px = (max(x["stop"], o) + TICK) if buy else (min(x["stop"], o) - TICK)
                            self._fill(oid, rest, px)
                        elif want == "LIMIT" and ((buy and l <= x["limit"]) or (not buy and h >= x["limit"])):
                            self._fill(oid, rest, x["limit"])
                self.price = c

    return NT(folder, price=25000.0, exchange="Globex")


class Responder(threading.Thread):
    def __init__(self, nt):
        super().__init__(daemon=True)
        self.nt, self.stop = nt, threading.Event()

    def run(self):
        while not self.stop.is_set():
            try:
                self.nt.process()
            except Exception as e:
                self.nt.errors.append(("responder", f"{e.__class__.__name__}: {e}"))
            _real_sleep(0.005)


# ================================================================================================ the server process
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Server:
    def __init__(self, base, repo, clock_path, nt_folder):
        self.base, self.repo, self.clock_path, self.nt_folder = base, repo, clock_path, nt_folder
        self.port = free_port()
        self.proc = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.n = 0

    def env(self):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("LE_", "NINJATRADER", "TRADOVATE", "TRADERSPOST"))}
        dead = "http://127.0.0.1:9"
        e.update(HTTPS_PROXY=dead, HTTP_PROXY=dead, https_proxy=dead, http_proxy=dead, NO_PROXY="127.0.0.1,localhost",
                 no_proxy="127.0.0.1,localhost", LE_HEARTBEAT="1", LE_PREWARM="0", NINJATRADER_FOLDER=self.nt_folder,
                 PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        return e

    def start(self):
        self.n += 1
        logf = open(os.path.join(self.base, f"server_{self.n}.log"), "w", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "-X", "utf8", os.path.join(self.repo, "tests", "test_rehearsal.py"), "--serve",
                                      self.repo, self.clock_path, str(self.port)], cwd=self.repo, env=self.env(),
                                     stdout=logf, stderr=subprocess.STDOUT)
        t_end = _real_time() + 240
        while _real_time() < t_end:
            try:
                self.get("/api/health/ping", timeout=2)
                return True
            except Exception:
                if self.proc.poll() is not None:
                    break
                _real_sleep(0.3)
        raise RuntimeError(f"server did not start (see {logf.name})")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)
        self.proc = None

    def _req(self, path, body=None, timeout=60):
        data = None if body is None else json.dumps(body).encode()
        rq = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                    headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
        try:
            with self.opener.open(rq, timeout=timeout) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode())
            except Exception:
                return {"http_error": e.code}

    def get(self, path, timeout=60):
        return self._req(path, None, timeout)

    def post(self, path, body=None, timeout=60):
        return self._req(path, body or {}, timeout)

    def cloud(self, out):
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(self.repo, "tests", "test_rehearsal.py"), "--cloud", self.repo,
                            self.clock_path, out], cwd=self.repo, env={**self.env(), "LE_HEARTBEAT": "0"}, capture_output=True,
                           text=True, timeout=900)
        return r.returncode, (r.stdout or "")[-3000:] + (r.stderr or "")[-3000:]


# ================================================================================================ the backtest
def backtest():
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    S26 = [d for d in F.SESS if d >= "2026-01-01"]
    T = F.run(P, S26)
    T_off = F.run({**P, "monday": False}, S26)
    return P, S26, T, T_off


def expected_qty(t, lm):
    """The micros the PC routes for backtest trade t on a fresh eval (session 1, -$100 prior, nothing closed today):
    engine/sizing.lit_qty in live_model.json's lit_sizing (two_week), the room from the eval's day P&L."""
    from engine import sizing as _sz
    lsz = lm["lit_sizing"]
    days = {"0000-00-00": float(lsz.get("eval_prior_pnl") or 0.0)}
    room = _sz.mffu_eval(days)["cushion"]
    st = _sz.eval_state(days, 0.0, session=1)
    pos = {"entry": t["entry_px"], "stop": t["stop_px"], "stop0": t["stop_px"], "target": t["target_px"], "risk_pts": t["risk_pts"],
           "dir": t["dir"], "qty": t["qty"], "entry_t": t["entry_t"]}
    return _sz.lit_qty(int(t["qty"]), pos, lsz, room=room, state=st), room, st


# ================================================================================================ the rehearsal
class Rehearsal:
    def __init__(self, days, keep=False, fast=False):
        from engine.ninjatrader import nt_instrument
        self.nt_instrument = nt_instrument
        self.days = days
        self.keep = keep
        self.fast = fast
        self.base = tempfile.mkdtemp(prefix="le_rehearsal_")
        print(f"sandbox {self.base}", flush=True)
        self.repo = build_sandbox(self.base)
        self.nt_folder = os.path.join(self.base, "NinjaTrader 8")
        self.clock_path = os.path.join(self.base, "clock.bin")
        self.vc = VClock(self.clock_path, create=True)
        self.hist = History(self.repo)
        print("loading bars + backtest ...", flush=True)
        self.b1, self.b5 = bars_of("1m"), bars_of("5m")
        self.P, self.S26, self.T, self.T_off = backtest()
        self.lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
        self.nt = make_nt(self.nt_folder, self.vc)
        self.feed = Feed(self.nt_folder, self.b1, self.b5)
        self.resp = Responder(self.nt)
        self.server = Server(self.base, self.repo, self.clock_path, self.nt_folder)
        self.cloud_out = os.path.join(self.base, "cloud")
        self.rows = []
        self.bugs = []

    # ---------------------------------------------------------------- plumbing
    def set_eval_start(self, day):
        p = os.path.join(self.repo, "live_model.json")
        with open(p, encoding="utf-8") as fh:
            lm = json.load(fh)
        lm["lit_sizing"]["eval_start"] = day           # the owner sets it on every new eval purchase
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(lm, fh, indent=2)

    def wait_idle(self, timeout=120):
        """Until the bot's loop is between polls: no poll running and its next wake computed (slot 7 > 0), or waiting
        for a late 1m bar (slot 7 = -1, the next publish wakes it)."""
        t_end = _real_time() + timeout
        while _real_time() < t_end:
            if self.vc.get(6) == 0 and self.vc.get(7) != 0:
                return True
            _real_sleep(0.003)
        return False

    def wait_poll(self, t, timeout=120):
        """Until the bot finished a poll that started at/after virtual t, or sleeps past t (no poll due at t)."""
        t_end = _real_time() + timeout
        while _real_time() < t_end:
            if self.vc.get(6) == 0:
                if self.vc.get(3) >= t - 1e-6 and self.vc.get(7) != 0:
                    return True
                if self.vc.get(7) > t + 1e-6 and self.vc.get(3) < t - 1e-6 and self.vc.get(7) - t < 31:
                    return True              # asleep until after t (its 2 s / 32 s schedule): nothing due at t
            _real_sleep(0.003)
        return False

    def step(self, t, running=True):
        """Bars up to t published, the clock set to t, the bot's poll (if one is due) awaited."""
        if running and not self.wait_idle():
            self.bugs.append(f"bot loop busy before {hm(t)}")
        m = int(t // 60 * 60)
        b = self.feed.bar(m - 60)
        if b is not None and t % 60 < 30:
            self.nt.bar(*b)                    # the minute that just closed: the broker's stops / targets work against it
        self.feed.publish(t)
        with self.nt.lock:
            self.nt.price = self.feed.price_at(t)
        self.vc.set(t)
        if running and not self.wait_poll(t):
            self.bugs.append(f"no poll finished after {hm(t)}")
            return False
        return True

    def oif_lines(self, a=None, z=None):
        return [(t, ln) for t, _, ls in self.nt.log for ln in ls if (a is None or t >= a) and (z is None or t < z)]

    def state(self):
        return self.server.get("/api/live/state") or {}

    # ---------------------------------------------------------------- the owner's start
    def owner_start(self, day):
        st = self.server.get("/api/next/botctl/status?account=Sim101")
        t_end = _real_time() + 60                     # the preflight runs the route self-test by itself (subprocess)
        while (st.get("selftest") or {}).get("ok") is None and _real_time() < t_end:
            _real_sleep(1.0)
            st = self.server.get("/api/next/botctl/status?account=Sim101")
        pf = st.get("preflight") or {}
        rows = pf.get("rows") or []
        not_green = [f"{r['id']}={r['ok']} ({r.get('detail')})" for r in rows if r.get("ok") is not True]
        check(f"{day} preflight on Sim101: every row green ({pf.get('green')} green, {pf.get('amber')} amber, {pf.get('red')} red)",
              pf.get("ok") and not not_green, "; ".join(not_green))
        n_polls = self.vc.get(4)
        res = self.server.post("/api/next/botctl/start", {"account": "Sim101"})
        t_end = _real_time() + 120
        while self.vc.get(4) <= n_polls and _real_time() < t_end:     # its first poll (started by the START itself)
            _real_sleep(0.01)
        check(f"{day} START on Sim101 via Bot Control", res.get("ok") and res.get("sim") and not res.get("warning"), json.dumps(res)[:300])
        return st, res

    # ---------------------------------------------------------------- one session
    def run_day(self, day, what):
        print(f"\n== {day} ({dt.date.fromisoformat(day):%a}): {what}", flush=True)
        i = self.S26.index(day)
        self.hist.cut(et_at(self.S26[i - 2], 17, 0))           # the export ends two sessions before today
        self.set_eval_start(day)
        bt = [t for t in self.T if t["day"] == day]
        bt_off = [t for t in self.T_off if t["day"] == day]
        t0 = et_at(day, 1, 50)
        t_end = et_at(day, 16, 5)
        if self.fast and bt:
            # --fast: START 40 min before the backtest entry (the live loop rebuilds the day from the bars, as after a late
            # START) and stop 20 min after its exit; no-trade days always run the whole session
            t0 = max(t0, (int(bt[0]["entry_t"]) - 40 * 60) // 60 * 60)
            t_end = min(t_end, (int(bt[0]["exit_t"]) + 20 * 60) // 60 * 60)
        self.feed.reset(t0 + 2, self.nt_instrument("MNQ", dt.date.fromisoformat(day)))
        self.vc.set(t0 + 2)
        if not self.server.proc:
            self.server.start()
        n0 = len(self.nt.log)
        # the cloud monitor's first look of the day (its paper ledger counts trades after its first run)
        rc, out = self.server.cloud(self.cloud_out)
        if rc:
            check(f"{day} cloud monitor ran at 01:50", False, out[-600:])
        status, start = self.owner_start(day)
        ev0 = (self.server.get("/api/next/botctl/status?account=Sim101") or {}).get("eval") or {}
        kill_at = restart_at = None
        if day == KILL_DAY and bt:
            kill_at = int(bt[0]["entry_t"]) + 60 * KILL_AFTER_MIN
        if day == RESTART_DAY and bt:
            restart_at = int(bt[0]["entry_t"]) + 60 * RESTART_AFTER_MIN
        running = True
        info = {"day": day, "what": what}
        m = t0 + 60
        ev_mid = None
        while m <= t_end:
            for off in (2, 32):
                t = m + off
                if off == 32 and not self.vc.get(5):
                    continue                     # the 32 s poll matters only with a position open (exits mid-minute)
                self.step(t, running=running)
                if kill_at and t >= kill_at:
                    kill_at = None
                    info["kill"] = self.do_kill(day, t)
                    running = False
                if restart_at and t >= restart_at:
                    restart_at = None
                    info["restart"] = self.do_restart(day, t)
                if t == t0 + 15 * 60 + 2:
                    # the cloud monitor's 02:05 run (it runs every 15 min): the first one that sees the PC's pushed bars
                    # closes its "waiting for NinjaTrader bars" pause, so later entries go in its paper ledger
                    rc, out = self.server.cloud(self.cloud_out)
                    if rc:
                        check(f"{day} cloud monitor ran at 02:05", False, out[-600:])
                if bt and ev_mid is None and t > int(bt[0]["entry_t"]) + 120:
                    ev_mid = (self.server.get("/api/next/botctl/status?account=Sim101") or {}).get("eval") or {}
            m += 60
        snap = self.state()
        ev1 = (self.server.get("/api/next/botctl/status?account=Sim101") or {}).get("eval") or {}
        info.update(self.compare(day, bt, bt_off, snap, n0, killed="kill" in info, restarted="restart" in info))
        info["eval"] = self.check_eval(day, ev0, ev1, snap, bt)
        info["heartbeat"] = self.check_heartbeat(day, snap, killed="kill" in info)
        info["exec"] = self.check_exec(day, bt, killed="kill" in info)
        rc, out = self.server.cloud(self.cloud_out)
        info["cloud"] = self.check_cloud(day, bt, rc, out, snap, killed="kill" in info)
        if running:
            r = self.server.post("/api/next/botctl/stop")      # the owner stops it after the session (Stop clears autostart)
            check(f"{day} STOP after the session", r.get("ok"), json.dumps(r)[:200])
        self.rows.append(info)
        return info

    # ---------------------------------------------------------------- kill / restart
    def do_kill(self, day, t):
        from engine import autoresume  # noqa: F401  (the sandbox's copy is used through a subprocess below)
        # the real-account auto-resume opt-in, as the owner turns it on once (stored as a hash; the sandbox's own data/)
        code = ("import sys; sys.path.insert(0, '.'); from engine import autoresume as a; from engine.tradovate import LIVE_PHRASE as P; "
                "a.enable('MFFUEVAL', P, {'adapter': 'ninjatrader', 'nt_account': 'MFFUEVAL'}); print(a.status().get('on'))")
        r = subprocess.run([sys.executable, "-c", code], cwd=self.repo, env=self.server.env(), capture_output=True, text=True, timeout=60)
        on_before = r.stdout.strip().endswith("True")
        n_lines = len(self.nt.log)
        res = self.server.post("/api/live/kill")
        _real_sleep(0.5)
        snap = self.state()
        lines = [ln for _, _, ls in self.nt.log[n_lines:] for ln in ls]
        with self.nt.lock:
            pos = {k: v[0] for k, v in self.nt.pos.items()}
        ar = subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, '.'); from engine import autoresume as a; "
                             "print(json.dumps(a.status()))"], cwd=self.repo, env=self.server.env(), capture_output=True, text=True, timeout=60)
        try:
            ars = json.loads(ar.stdout.strip().splitlines()[-1])
        except Exception:
            ars = {"error": ar.stdout[-200:] + ar.stderr[-200:]}
        autostart = os.path.exists(os.path.join(self.repo, "data", "autostart.json"))
        check(f"{day} KILL {hm(t)}: the kill endpoint answered ok", res.get("ok"), json.dumps(res)[:200])
        check(f"{day} KILL: FLATTENEVERYTHING written to incoming and processed", any(ln.startswith("FLATTENEVERYTHING") for ln in lines),
              str(lines))
        check(f"{day} KILL: NinjaTrader flat on every account", all(q == 0 for q in pos.values()), str(pos))
        check(f"{day} KILL: bot stopped, kill flag on", not snap.get("running") and snap.get("kill"), f"running={snap.get('running')} kill={snap.get('kill')}")
        check(f"{day} KILL: real-account auto-resume turned OFF (it was ON)", on_before and not ars.get("on"), json.dumps(ars)[:200])
        check(f"{day} KILL: autostart.json cleared (a Sim restart does not resume either)", not autostart)
        return {"t": hm(t), "flatten": any(ln.startswith("FLATTENEVERYTHING") for ln in lines), "auto_resume_after": ars.get("on"),
                "running_after": snap.get("running"), "lines": lines}

    def do_restart(self, day, t):
        before = self.state()
        pos0 = (before.get("state") or {}).get("position")
        n_place = sum(1 for _, ln in self.oif_lines() if ln.startswith("PLACE") and ";MARKET;" in ln)
        self.server.stop()
        polls0 = self.vc.get(4)
        self.server.start()
        t_end = _real_time() + 120
        while self.vc.get(4) <= polls0 and _real_time() < t_end:   # the autostart thread resumes the Sim bot and polls
            _real_sleep(0.05)
        wd = self.server.get("/api/health/watchdog") or {}
        snap = self.state()
        ai = wd.get("autostart") or wd.get("autostart_info") or {}
        check(f"{day} RESTART {hm(t)}: server back, the Sim bot auto-resumed", snap.get("running") and (ai.get("resumed") is not False),
              json.dumps(ai)[:300])
        rs = (snap.get("health") or {})
        restored = None
        for e in snap.get("log") or []:
            if "Restored live state" in str(e.get("text")):
                restored = e["text"]
                break
        check(f"{day} RESTART: today's state restored (open routed position)", restored and "open routed position @" in restored,
              str(restored))
        p1 = (snap.get("state") or {}).get("position")
        check(f"{day} RESTART: the model still shows the same open position", pos0 and p1 and p1.get("entry_t") == pos0.get("entry_t"),
              f"{pos0 and pos0.get('entry_t')} vs {p1 and p1.get('entry_t')}")
        return {"t": hm(t), "restored": restored, "n_place_before": n_place, "health_ok": rs.get("ok")}

    # ---------------------------------------------------------------- comparisons
    def compare(self, day, bt, bt_off, snap, n0, killed=False, restarted=False):
        led = [r for r in snap.get("ledger") or [] if r.get("t") and dt.datetime.fromtimestamp(r["t"], ET).date().isoformat() <= day
               and r["t"] >= et_at(day, 1, 0)]
        ent = [r for r in led if r.get("side") in ("buy", "sell")]
        mods = [r for r in led if r.get("side") == "modify"]
        exits = [r for r in led if r.get("side") == "exit"]
        lines = [(t, ln) for t, _, ls in self.nt.log[n0:] for ln in ls]
        places = [(t, ln) for t, ln in lines if ln.startswith("PLACE")]
        out = {"bt": [{k: (float(v) if hasattr(v, "item") else v) for k, v in t.items() if k in
                       ("entry_t", "exit_t", "dir", "qty", "pnl", "exit", "entry_px", "stop_px", "target_px", "risk_pts")} for t in bt],
               "routed": [{k: r.get(k) for k in ("t", "side", "qty", "stop", "target", "entry", "entry_t", "reason", "pnl", "exit_t")}
                          for r in led], "oif": [f"{hm(t)} {ln}" for t, ln in lines]}
        errs = [r for r in led if not (r.get("result") or {}).get("ok") and not ("kill" in str(r.get("reason")).lower())]
        if not bt:
            check(f"{day} no backtest trade -> no order routed", not ent and not places, f"{len(ent)} entries, {len(places)} PLACE lines")
            if bt_off:
                check(f"{day} Monday rule live: without it the backtest trades ({bt_off[0]['exit']} {'long' if bt_off[0]['dir'] == 1 else 'short'} "
                      f"{hm(bt_off[0]['entry_t'])}), with it nothing is routed", not ent)
            return out
        t = bt[0]
        d = int(t["dir"])
        want_q, room, st = expected_qty(t, self.lm)
        want_q = int(want_q["qty"])
        e = ent[0] if ent else None
        out.update(want_qty=want_q, room=room)
        check(f"{day} exactly one entry routed (backtest: one)", len(ent) == 1, f"{len(ent)} entries")
        if not e:
            return out
        from engine.live import tick_px
        lag = e["t"] - int(t["entry_t"])
        check(f"{day} entry {('BUY' if d == 1 else 'SELL')} at {hm(e['t'])} = the backtest's fill bar {hm(t['entry_t'])} + {lag} s",
              e["side"] == ("buy" if d == 1 else "sell") and int(e["entry_t"]) == int(t["entry_t"]) and 0 <= lag <= LIMIT_S,
              f"routed {e['side']} {e['entry_t']} at {hm(e['t'])}")
        check(f"{day} micros {e['qty']} = two_week sizing of the backtest trade ({want_q}; backtest LIT size {t['qty']})",
              int(e["qty"]) == want_q)
        ws, wt = tick_px(t["stop_px"], d), tick_px(t["target_px"], d, target=True)
        check(f"{day} stop {e['stop']} / target {e['target']} = backtest {ws} / {wt}", abs(e["stop"] - ws) < 1e-9 and abs(e["target"] - wt) < 1e-9)
        # the OIF lines: MARKET entry, then the OCO bracket at those prices
        mk = [(tt, ln) for tt, ln in places if ";MARKET;" in ln and ln.split(";")[3] == ("BUY" if d == 1 else "SELL")]
        br = [ln for _, ln in places if ";STOPMARKET;" in ln or ";LIMIT;" in ln]
        f = [x for x in self.nt.fills if x[2] == "MARKET" and x[0] >= et_at(day, 1, 0) and x[3] == ("BUY" if d == 1 else "SELL")]
        fill_px = f[0][5] if f else None
        check(f"{day} OIF: one MARKET {('BUY' if d == 1 else 'SELL')} {want_q} placed; NinjaTrader fill {fill_px} = backtest entry {t['entry_px']}",
              len(mk) >= 1 and int(mk[0][1].split(";")[4]) == want_q and fill_px is not None and abs(fill_px - t["entry_px"]) < 1e-9,
              str(mk[:2]))
        stop_l = [ln for ln in br if ";STOPMARKET;" in ln]
        tgt_l = [ln for ln in br if ";LIMIT;" in ln]
        check(f"{day} OIF bracket: STOPMARKET @ {ws} + LIMIT @ {wt}, qty {want_q}, one OCO",
              stop_l and tgt_l and float(stop_l[0].split(";")[7]) == ws and float(tgt_l[0].split(";")[6]) == wt
              and int(stop_l[0].split(";")[4]) == want_q and stop_l[0].split(";")[9] == tgt_l[0].split(";")[9], f"{stop_l[:1]} {tgt_l[:1]}")
        if restarted:
            n_mk = len([1 for _, ln in places if ";MARKET;" in ln and ln.split(";")[3] == ("BUY" if d == 1 else "SELL")])
            check(f"{day} RESTART: no duplicate entry ({n_mk} MARKET entry order in the day)", n_mk == 1)
        # breakeven
        be_bt = t["exit"] in ("BE",) or any(True for _ in [])
        chg = [(tt, ln) for tt, ln in lines if ln.startswith("CHANGE")]
        if mods:
            want_be = tick_px(float(t["entry_px"]) + d * float(self.P.get("be_off") or 0.0), d)
            check(f"{day} breakeven: {len(mods)} stop move routed to {mods[0]['stop']} (entry {'+' if d == 1 else '-'} {self.P.get('be_off')} = {want_be}); "
                  f"OIF CHANGE {chg[0][1] if chg else None}",
                  len(mods) == 1 and abs(float(mods[0]["stop"]) - want_be) < 1e-9 and chg and float(chg[0][1].split(";")[7]) == want_be,
                  json.dumps(mods)[:300])
            if restarted:
                check(f"{day} RESTART: the breakeven CHANGE was routed after the restart (stop still managed)",
                      mods[0]["t"] > et_at(day, 0, 0) and chg and chg[0][0] >= int(t["entry_t"]) + 60 * RESTART_AFTER_MIN)
        elif be_bt:
            check(f"{day} breakeven expected (backtest BE exit) but no stop move routed", False)
        if killed:
            k = [r for r in exits if str(r.get("reason")) == "KILL SWITCH"]
            check(f"{day} KILL: the only exit is the kill switch; nothing routed after it", len(k) == 1 and len(exits) == 1
                  and not [1 for r in led if r["t"] > k[0]["t"]], json.dumps(exits)[:300])
            xs = [y for y in self.nt.fills if y[0] >= et_at(day, 1, 0) and y[3] == ("SELL" if d == 1 else "BUY")]
            if k and xs and fill_px is not None:
                from engine import lit as _lit
                q = sum(y[4] for y in xs)
                xp = sum(y[4] * y[5] for y in xs) / q
                bpnl = round(q * ((xp - float(t["entry_px"])) * d * _lit.PV - _lit.COMM), 2)
                kp = k[0].get("pnl")
                out.update(kill_pnl=kp, broker_pnl=bpnl)
                # the flatten fills 1 tick against us at the broker; the bot books the market (forming open) at the kill
                check(f"{day} KILL: the flatten's P&L is booked (${kp}; broker fill {xp:.2f} -> ${bpnl}), so the eval clock counts it",
                      kp is not None and abs(float(kp) - bpnl) <= q * TICK * _lit.PV + 0.01, json.dumps(k[0])[:300])
            return out
        # exit
        x = exits[0] if exits else None
        want_reason = {"EOD": "TIME"}.get(t["exit"], t["exit"])
        check(f"{day} exit {x and x.get('reason')} at {x and hm(x.get('exit_t'))} = backtest {t['exit']} {hm(t['exit_t'])}",
              x is not None and len(exits) == 1 and x.get("reason") in (t["exit"], want_reason) and int(x.get("exit_t") or 0) == int(t["exit_t"]),
              json.dumps(exits)[:300])
        if x is not None:
            want_pnl = round(t["pnl"] * int(e["qty"]) / t["qty"], 2)
            check(f"{day} routed P&L ${x.get('pnl')} = backtest ${t['pnl']} at {e['qty']} micros (${want_pnl})",
                  abs(float(x.get("pnl") or 0) - want_pnl) < 0.01)
        # the broker's own P&L from the fills
        xs = [y for y in self.nt.fills if y[0] >= et_at(day, 1, 0) and y[3] == ("SELL" if d == 1 else "BUY")]
        if fill_px is not None and xs:
            q = sum(y[4] for y in xs)
            xp = sum(y[4] * y[5] for y in xs) / q
            from engine import lit as _lit
            bpnl = round(q * ((xp - fill_px) * d * _lit.PV - _lit.COMM), 2)
            want_pnl = round(t["pnl"] * int(e["qty"]) / t["qty"], 2)
            out.update(broker_pnl=bpnl, broker_exit_px=xp, broker_exit_t=hm(xs[0][0]), broker_exit_type=xs[0][2],
                       broker_vs_bt=round(bpnl - want_pnl, 2))
            if xs[0][2] == "MARKET":
                # a flatten (15-min cut / 15:55 / the early-close flat) fills at the market after the decision: the backtest books
                # the decision bar's close. Checked: the flatten went out on time (cut / EOD: within LIMIT_S of the model's
                # exit; early close: 5 min before the halt, after the last entry); the $ gap is reported, not a failure.
                early = t["exit"] in ("EOD", "TIME") and int(t["exit_t"]) < et_at(day, 15, 0)
                lag = xs[0][0] - int(t["exit_t"])
                # 15:55 flat: the clock flat can go at the 15:55:32 poll, before the model's 15:56 bar-close exit
                ok = (-330 <= lag <= 0) if early else (-60 <= lag <= LIMIT_S + 30)
                check(f"{day} broker fills: flatten MARKET {q} @ {xp:.2f} at {hm(xs[0][0])} ({lag:+.0f} s vs the model's exit"
                      f"{', early-close flat 5 min before the halt' if early else ''}); P&L ${bpnl} vs backtest ${want_pnl} "
                      f"(${bpnl - want_pnl:+.2f} market vs bar close)", ok, f"lag {lag}")
            else:
                ok = abs(bpnl - want_pnl) <= q * TICK * _lit.PV + 0.01      # the backtest target is not tick-rounded
                check(f"{day} broker fills: exit {xs[0][2]} {q} @ {xp:.2f} at {hm(xs[0][0])}, P&L ${bpnl} vs backtest ${want_pnl}", ok,
                      f"diff ${bpnl - want_pnl:+.2f}")
        if t["exit"] == "CUT_T15" and x is not None:
            ct = [(tt, ln) for tt, ln in lines if ln.startswith("CLOSEPOSITION")]
            lag = (ct[0][0] - (int(t["exit_t"]))) if ct else None
            check(f"{day} 15-minute cut: CLOSEPOSITION routed {lag} s after the check bar closed", ct and 0 <= lag <= LIMIT_S, str(ct[:1]))
        check(f"{day} every routed order accepted", not errs, json.dumps([{k: r.get(k) for k in ("side", "reason", "result")} for r in errs])[:400])
        check(f"{day} fake NinjaTrader: every OIF line valid", not self.nt.errors, str(self.nt.errors[-3:]))
        return out

    def check_eval(self, day, ev0, ev1, snap, bt):
        prior = float(self.lm["lit_sizing"].get("eval_prior_pnl") or 0.0)
        need0 = 3000.0 - prior
        ok0 = int(ev0.get("session") or 0) == 1 and int(ev0.get("sessions") or 0) == 10 and abs(float(ev0.get("to_target") or 0) - need0) < 0.01
        check(f"{day} eval clock at the start: session {ev0.get('session')} of {ev0.get('sessions')}, ${ev0.get('to_target')} to go "
              f"(= $3,000 - (${prior:+.0f} prior)), room ${ev0.get('room')}", ok0, json.dumps(ev0)[:300])
        day_pnl = float(snap.get("day_pnl_routed") or 0.0)
        ok1 = abs(float(ev1.get("to_target") or 0) - max(0.0, need0 - day_pnl)) < 0.01 and \
            (ev1.get("status") == "passed") == (day_pnl >= need0)
        check(f"{day} eval clock after the session: ${ev1.get('to_target')} to go = max(0, ${need0:,.0f} - day ${day_pnl:+,.2f})"
              f"{' - PASSED in 1 session' if ev1.get('status') == 'passed' else ''}", ok1, json.dumps(ev1)[:300])
        e2 = (snap.get("state") or {}).get("eval_2wk") or {}
        return {"start": {k: ev0.get(k) for k in ("session", "sessions", "to_target", "room", "balance", "prior")},
                "end": {k: ev1.get(k) for k in ("session", "sessions", "to_target", "room", "balance")}, "eval_2wk": e2.get("text") or e2}

    def check_heartbeat(self, day, snap, killed=False):
        p = os.path.join(self.repo, "logs", "heartbeat_last.json")
        t_end, hb = _real_time() + 90, None
        while _real_time() < t_end:              # a beat every 2 real s; after a kill the test's clock sprints ahead of it
            try:
                hb = json.load(open(p, encoding="utf-8"))
                if abs(float((hb.get("payload") or {}).get("t") or 0) - self.vc.now()) < 180:
                    break
            except Exception:
                pass
            _real_sleep(1)
        if hb is None:
            check(f"{day} heartbeat: logs/heartbeat_last.json written", False, p)
            return None
        pl, push = hb.get("payload") or {}, hb.get("push") or {}
        h = pl.get("health") or {}
        now = self.vc.now()
        check(f"{day} heartbeat pushed to the (local) heartbeat branch, payload t {hm(pl.get('t'))} = virtual now",
              push.get("ok") and abs(float(pl.get("t") or 0) - now) < 180, json.dumps(push)[:200])
        check(f"{day} heartbeat health block: v{h.get('v')}, account {((h.get('account') or {}).get('name'))} "
              f"{(h.get('account') or {}).get('label')}, adapter enabled, feed ninjatrader no Yahoo",
              h.get("v") and (h.get("account") or {}).get("name") == "Sim101" and (h.get("account") or {}).get("label") == "SIM"
              and (h.get("account") or {}).get("enabled") and (h.get("feed") or {}).get("no_yahoo"), json.dumps(h)[:400])
        au = h.get("auto") or {}
        check(f"{day} health: auto-update / auto-resume state reported ({json.dumps(au)[:160]})", isinstance(au, dict) and bool(au))
        bars = pl.get("bars") or {}
        r = subprocess.run(["git", "--git-dir", os.path.join(self.base, "origin.git"), "ls-tree", "--name-only", "heartbeat"],
                           capture_output=True, text=True)
        names = set(r.stdout.split())
        check(f"{day} heartbeat branch carries heartbeat.json + the PC's bars ({', '.join(sorted(names))})",
              {"heartbeat.json", "bars_1m.csv.gz", "bars_5m.csv.gz"} <= names)
        from engine import accounts
        v = accounts.verdict({**pl, "present": True}, now=now)
        want = ("DISABLED",) if killed else ("SIM",)          # after the kill switch the server is up, the bot stopped
        check(f"{day} cloud verdict on the heartbeat: {v.get('code')} ({v.get('label')})", v.get("code") in want, v.get("reason"))
        return {"t": hm(pl.get("t")), "push": push.get("ok"), "health_v": h.get("v"), "auto": au, "bars": bars, "verdict": v.get("code"),
                "exec": pl.get("exec") and (pl["exec"] or {}).get("text")}

    def check_exec(self, day, bt, killed=False):
        # the server's exec-audit thread collects every 60 real s; a stopped (killed) bot lets the test sprint through the
        # rest of the day faster than that: wait for its after-session run (it re-audits once after 16:05)
        t_end = _real_time() + (90 if bt else 5)
        while True:
            v = self.server.get("/api/next/pc/execution") or {}
            rows = [r for r in v.get("rows") or [] if r.get("day") == day]
            if (rows and (not killed or rows[0].get("live_exit_kind"))) or _real_time() > t_end:
                break                                # killed: until the audit has seen the kill-switch exit too
            _real_sleep(3)
        if not bt:
            check(f"{day} execution tracker: no trade, no missed / extra row", not [r for r in rows if r.get("status") in ("missed", "extra")],
                  json.dumps(rows)[:300])
            return {"rows": len(rows)}
        r = rows[0] if rows else {}
        if killed:
            ok = bool(rows) and (r.get("status") == "matched" or (r.get("status") == "extra" and "kill switch" in str(r.get("reason"))))
        else:
            ok = bool(rows) and r.get("status") == "matched" and abs(float(r.get("entry_slip_ticks") or 0)) < 1e-9 \
                and abs(float(r.get("exit_slip_ticks") or 0)) < 1e-9
        check(f"{day} execution tracker: {r.get('status')} (entry slip {r.get('entry_slip_ticks')} t, exit slip {r.get('exit_slip_ticks')} t, "
              f"latency {r.get('latency_s')} s, live ${r.get('live_pnl')}){' - ' + str(r.get('reason')) if r.get('reason') else ''}",
              ok, json.dumps(r)[:500])
        return {k: r.get(k) for k in ("status", "entry_slip_ticks", "exit_slip_ticks", "slip_usd", "latency_s", "live_qty", "bt_qty",
                                      "reason", "live_be_t", "bt_be_t", "live_exit_kind", "live_pnl", "notes")}

    def check_cloud(self, day, bt, rc, out, snap, killed=False):
        if rc:
            check(f"{day} cloud monitor ran at 16:05", False, out[-800:])
            return {"rc": rc}
        try:
            st = json.load(open(os.path.join(self.cloud_out, "state.json"), encoding="utf-8"))
        except Exception as e:
            check(f"{day} cloud monitor state.json", False, str(e))
            return {"error": str(e)}
        led = [{**v, "entry_t": int(k)} for k, v in (st.get("ledger") or {}).items() if v.get("day") == day]   # keyed by entry_t
        h = st.get("health") or {}
        if not bt:
            check(f"{day} cloud monitor on the pushed PC bars: no paper trade either", not led, json.dumps(led)[:300])
            return {"trades": 0, "bars": (h.get("pc_bars") or {}).get("text")}
        c = led[0] if led else {}
        t = bt[0]
        ent = [r for r in snap.get("ledger") or [] if r.get("side") in ("buy", "sell") and r.get("entry_t") == t["entry_t"]]
        q = int(ent[0]["qty"]) if ent else None
        ok = bool(led) and int(c.get("entry_t") or 0) == int(t["entry_t"]) and (killed or c.get("exit") in (t["exit"], "TIME", "EOD"))
        check(f"{day} cloud monitor (PC's pushed bars): same paper trade {hm(c.get('entry_t'))} {c.get('exit')} {c.get('qty')} micros "
              f"(PC {q}), ${c.get('usd')}", ok and (q is None or int(c.get("qty") or 0) == q), json.dumps(c)[:400])
        return {"trades": len(led), "entry": hm(c.get("entry_t")), "exit": c.get("exit"), "qty": c.get("qty"), "usd": c.get("usd"),
                "bars": (h.get("pc_bars") or {}).get("text")}

    # ---------------------------------------------------------------- run all
    def run(self):
        self.resp.start()
        try:
            for day, what in self.days:
                try:
                    self.run_day(day, what)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    check(f"{day} rehearsal day ran", False, f"{e.__class__.__name__}: {e}")
        finally:
            self.resp.stop.set()
            self.server.stop()
        log = os.path.join(self.base, "server_1.log")
        tb = []
        for n in range(1, self.server.n + 1):
            try:
                txt = open(os.path.join(self.base, f"server_{n}.log"), encoding="utf-8", errors="replace").read()
                tb += [ln for ln in txt.splitlines() if "Traceback" in ln or "Error" in ln][:20]
            except OSError:
                pass
        check("server logs: no traceback", not [x for x in tb if "Traceback" in x], "\n".join(tb[:10]))
        return log


def summary(rh, out=None):
    print("\n== rehearsal results")
    print(f"{'day':<11} {'what':<44} {'bt':<20} {'routed':<26} {'P&L bt/routed/broker':<28} cloud")
    for r in rh.rows:
        bt = r.get("bt") or []
        b = bt[0] if bt else None
        ent = [x for x in r.get("routed") or [] if x["side"] in ("buy", "sell")]
        ex = [x for x in r.get("routed") or [] if x["side"] == "exit"]
        btx = f"{b['exit']} {b['qty']}m {hm(b['entry_t'])[:5]}" if b else "no trade"
        rt = f"{ent[0]['qty']}m {hm(ent[0]['t'])} {ex[0]['reason'] if ex else '-'}" if ent else "none"
        pn = f"{round(b['pnl'] * ent[0]['qty'] / b['qty'], 2) if b and ent else '-'}/{ex[0].get('pnl') if ex else '-'}/{r.get('broker_pnl', '-')}"
        c = r.get("cloud") or {}
        print(f"{r['day']:<11} {r['what'][:44]:<44} {btx:<20} {rt:<26} {pn:<28} {c.get('exit') or c.get('trades')}")
    n_ok = sum(1 for x in RESULTS if x["ok"])
    print(f"\n{n_ok}/{len(RESULTS)} checks passed")
    out = out or OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"t": int(_real_time()), "checks": RESULTS, "days": rh.rows, "bugs": rh.bugs}, fh, indent=1, default=str)
    print("->", out)
    return n_ok == len(RESULTS)


def main(argv):
    if argv[:1] == ["--serve"]:
        return serve(*argv[1:4])
    if argv[:1] == ["--cloud"]:
        return cloud(*argv[1:4])
    days = DAYS
    jobs, part = 1, None
    for a in argv:
        if a.startswith("--days="):
            want = a.split("=", 1)[1].split(",")
            days = [d for d in DAYS if d[0] in want] or [(d, "chosen day") for d in want]
        if a.startswith("--jobs="):
            jobs = int(a.split("=", 1)[1])
        if a.startswith("--part="):
            part = a.split("=", 1)[1]
    if jobs > 1:
        return run_parallel(days, jobs, argv)
    rh = Rehearsal(days, keep="--keep" in argv, fast="--fast" in argv)
    try:
        rh.run()
        ok = summary(rh, out=part)
    finally:
        if "--keep" not in argv:
            shutil.rmtree(rh.base, ignore_errors=True)
        else:
            print("sandbox kept:", rh.base)
    return 0 if ok else 1


def run_parallel(days, jobs, argv):
    """Each day in its own sandbox + server (the days are independent: every day is a fresh eval), `jobs` at a time."""
    tmp = tempfile.mkdtemp(prefix="le_rehearsal_parts_")
    procs, done = [], []
    queue = list(days)
    keep = [a for a in argv if a in ("--keep", "--fast")]
    while queue or procs:
        while queue and len(procs) < jobs:
            d = queue.pop(0)
            part = os.path.join(tmp, f"{d[0]}.json")
            logp = os.path.join(tmp, f"{d[0]}.log")
            p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "tests.test_rehearsal", f"--days={d[0]}", f"--part={part}", *keep],
                                 cwd=ROOT, stdout=open(logp, "w", encoding="utf-8"), stderr=subprocess.STDOUT)
            procs.append((p, d, part, logp))
            print(f"started {d[0]} ({d[1]}) -> {logp}", flush=True)
        for x in list(procs):
            if x[0].poll() is not None:
                procs.remove(x)
                done.append(x)
                txt = open(x[3], encoding="utf-8", errors="replace").read()
                print(f"\n---- {x[1][0]} (exit {x[0].returncode})\n" + "\n".join(ln for ln in txt.splitlines() if "[FAIL]" in ln or "[PASS]" in ln),
                      flush=True)
        _real_sleep(2)
    rows, bugs = [], []
    RESULTS.clear()
    for _, d, part, logp in sorted(done, key=lambda x: x[1][0]):
        try:
            j = json.load(open(part, encoding="utf-8"))
        except Exception as e:
            RESULTS.append({"name": f"{d[0]} rehearsal process", "ok": False, "detail": f"no result ({e}); see {logp}"})
            continue
        RESULTS.extend(j["checks"])
        rows += j["days"]
        bugs += j["bugs"]

    class R:
        pass
    r = R()
    r.rows, r.bugs = rows, bugs
    ok = summary(r)
    print("parts:", tmp)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
