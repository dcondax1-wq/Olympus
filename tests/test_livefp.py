"""engine/livefp (day-livefp 2026-11-27, red team #44): today's NQ footprint for the live chart's strip, private link only.

  a. parity       the same trades -> the same bars as engine/ofsum.summarize (o h l c, volume, delta, big prints, the footprint cells
                  per 2-point bucket) and the OF1 absorption read of tools/build_of_room.strip_from_summary (re-derived here)
  b. incremental  many small runs (torn lines included) = one whole run; appended trades only add; a replaced file restarts the day
  c. private      serve(): the home WiFi / a Funnel / a forwarded non-tailnet address -> 403; the PC itself and the Tailscale link -> 200;
                  the body is market data only (no account / order / position keys)
  d. cheap        the route never parses ticks: it reads one file and starts at most one BELOW_NORMAL child, only when the file is older
                  than 20 s; no pandas / numpy imported by the route path; reads at most MAX_READ bytes a run
  e. server.py    GET /api/live/footprint wired (the real route through FastAPI's TestClient when fastapi is installed)
    python -X utf8 -m tests.test_livefp
"""
from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import os
import random
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import livefp as F  # noqa: E402

ET = ZoneInfo("America/New_York")
DAY = "2026-11-27"
NOW = dt.datetime(2026, 11, 27, 11, 2, tzinfo=ET).timestamp()
FAILS: list = []
PASSES = [0]


def check(name, ok, detail=None):
    if ok:
        PASSES[0] += 1
        print(f"  ok  {name}")
    else:
        FAILS.append(name)
        print(f"[FAIL] {name}  -> {str(detail)[:300]}")


def ticks(seed=7, n=6000, start=(10, 0)):
    """trades from 10:00 ET for ~an hour: a random walk on the tick grid, quotes around it (some inside / missing), sizes 1..60"""
    rnd, p, out = random.Random(seed), 21000.0, []
    t = int(dt.datetime(2026, 11, 27, *start, tzinfo=ET).timestamp() * 1000)
    for i in range(n):
        t += rnd.randint(50, 900)
        p = round((p + rnd.choice((-0.25, 0, 0, 0.25))) * 4) / 4
        sz = rnd.choice((1, 1, 1, 2, 3, 5, 8, 20, 25, 60)) if rnd.random() < 0.97 else rnd.randint(1, 4)
        r = rnd.random()
        bid, ask = (p - 0.25, p) if r < 0.45 else (p, p + 0.25) if r < 0.9 else (0, 0) if r < 0.95 else (p - 0.25, p + 0.25)
        out.append((t, p, sz, bid, ask))
    return out


def write(td, rows, mode="w", day=DAY):
    d = os.path.join(td, "le_ticks")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"NQ_{day}.csv")
    with open(path, mode) as fh:
        if mode == "w":
            fh.write("t_ms,price,size,bid,ask\n")
        for t, p, s, b, a in rows:
            fh.write(f"{t},{p},{s},{b},{a}\n")
    return path


def ofsum_strip(path):
    """the nightly route for the same trades: tickrec.read_rec_csv -> ofsum.summarize -> build_of_room.strip_from_summary (re-derived)"""
    import pandas as pd
    from engine import ofsum, tickrec
    files = ofsum.summarize(tickrec.read_rec_csv(path), DAY)
    bars = pd.read_csv(io.BytesIO(gzip.decompress(files["NQ_bars5m.csv.gz"])))
    fp = pd.read_csv(io.BytesIO(gzip.decompress(files["NQ_fp5m.csv.gz"])))
    out = []
    byb = {int(k): g for k, g in fp.groupby("bar")}
    for i, r in bars.iterrows():
        et = dt.datetime.fromtimestamp(int(r.t), ET)
        if not (570 <= et.hour * 60 + et.minute < 960):
            continue
        g, lo, hi = byb[i], float(r.l), float(r.h)
        cells, ab = {}, []
        kmax = int(round((hi - lo) / 0.25))
        for k, a, b in zip(g.k, g.a, g.b):
            px = lo + int(k) * 0.25
            c = round((px // 2.0) * 2.0, 2)
            x = cells.setdefault(c, [c, 0, 0]); x[1] += int(a); x[2] += int(b)
        if int(r.n) >= 20:
            for side, z, d in (("low", g[g.k <= 8], 1), ("high", g[g.k >= kmax - 8], -1)):
                vz = float((z.a + z.b + z.u).sum()); dz = float((z.a - z.b).sum())
                if vz > 0 and dz * d < 0 and abs(dz) >= 0.2 * vz:
                    ab.append({"side": side, "who": "buyers" if side == "low" else "sellers", "px": lo if side == "low" else hi, "vz": int(vz), "dz": int(dz)})
        out.append({"t": et.strftime("%H:%M"), "o": float(r.o), "h": hi, "l": lo, "c": float(r.c), "v": int(r.vol), "d": int(r.buy - r.sell),
                    "big": int(r.b20), "cells": sorted(cells.values()), "abs": ab})
    return out


def test_parity():
    with tempfile.TemporaryDirectory() as td:
        path = write(td, ticks())
        r = F.build(td, os.path.join(td, "out"), NOW)
        live = json.load(open(os.path.join(td, "out", "fp.json")))
        ref = ofsum_strip(path)
        check("a. one run reads the whole file (6,000 trades), RTH bars 10:00 .. ", r["ok"] and r["rows"] == 6000 and len(live["bars"]) == len(ref) >= 10, (r, len(ref)))
        diff = [(a["t"], k) for a, b in zip(live["bars"], ref) for k in ("t", "o", "h", "l", "c", "v", "d", "big", "cells") if a[k] != b[k]]
        check("a. every bar = engine/ofsum.summarize on the same trades: o h l c, volume, delta, big prints (>= 20), the 2-point cells", not diff, diff[:5])
        absd = [(a["t"], a["abs"], b["abs"]) for a, b in zip(live["bars"], ref) if a["abs"] != b["abs"]]
        check("a. the OF1 absorption read = build_of_room.strip_from_summary's (zone 8 ticks, >= 20 % of it, >= 20 trades)", not absd, absd[:3])
        check("a. the strip's shape for nq/ofstrip.js: day, tick 0.25, bucket 2.0, live, asof = the newest trade",
              live["day"] == DAY and live["tick"] == 0.25 and live["bucket"] == 2.0 and live["live"] is True and abs(live["asof"] - ticks()[-1][0] / 1000) < 1e-6)
        n_abs = sum(len(b["abs"]) for b in ref)
        check("a. the fixture has absorption to compare (not a vacuous check)", n_abs >= 1, n_abs)


def test_incremental():
    rows = ticks(seed=11, n=4000)
    with tempfile.TemporaryDirectory() as td:
        write(td, rows)
        F.build(td, os.path.join(td, "whole"), NOW)
        whole = json.load(open(os.path.join(td, "whole", "fp.json")))
        runs, out = 0, os.path.join(td, "steps")
        while True:
            r = F.build(td, out, NOW, max_read=7_001)            # 7 KB a run: torn lines on almost every run
            runs += 1
            if not r["behind"] or runs > 500:
                break
        step = json.load(open(os.path.join(out, "fp.json")))
        check("b. ~25 small runs (torn lines) = one whole run", runs > 10 and step["bars"] == whole["bars"] and step["rows"] == 4000, (runs, step["rows"]))
    with tempfile.TemporaryDirectory() as td:
        write(td, rows[:2500])
        out = os.path.join(td, "out")
        F.build(td, out, NOW)
        write(td, rows[2500:], mode="a")
        r = F.build(td, out, NOW)
        st = json.load(open(os.path.join(out, "state.json")))
        check("b. appended trades: the second run reads only them (1,500 added) and the day matches one whole run",
              r["added"] == 1500 and st["rows"] == 4000 and json.load(open(os.path.join(out, "fp.json")))["bars"] == whole["bars"], r)
        write(td, rows[:100])                                     # the file replaced (shorter): the day starts again
        r = F.build(td, out, NOW)
        check("b. a replaced (shorter) file restarts the day instead of reading garbage", r["rows"] == 100, r)
    with tempfile.TemporaryDirectory() as td:
        write(td, ticks(n=50), day="2026-11-26")                  # only yesterday's file
        r = F.build(td, os.path.join(td, "out"), NOW)
        d = json.load(open(os.path.join(td, "out", "fp.json")))
        check("b. no tick file today: no bars and a plain reason (never yesterday's file as today)", not r["ok"] and d["bars"] == [] and "tick recorder" in d["why"], d)


class Proc:
    def __init__(self):
        self.done = False

    def poll(self):
        return 0 if self.done else None


def test_private_and_cheap():
    with tempfile.TemporaryDirectory() as td:
        write(td, ticks(n=300))
        out = os.path.join(td, "out")
        F.build(td, out, NOW)
        os.utime(os.path.join(out, "fp.json"), (NOW, NOW))
        spawned = []
        sp = lambda: spawned.append(1) or Proc()  # noqa: E731
        F._P.update(proc=None, started=0.0)
        wifi = {"host": "192.168.1.20:8766"}
        ts = {"host": "pc.tail1234.ts.net", "x-forwarded-for": "100.101.102.103", "tailscale-user-login": "owner@example.com"}
        cases = [("the home WiFi", "192.168.1.50", wifi, 403), ("a Funnel (internet) request", "127.0.0.1", {**ts, "tailscale-funnel-request": "?1"}, 403),
                 ("a forwarded address outside Tailscale", "127.0.0.1", {**ts, "x-forwarded-for": "8.8.8.8"}, 403),
                 ("the Tailscale link without a signed-in user", "127.0.0.1", {k: v for k, v in ts.items() if k != "tailscale-user-login"}, 403),
                 ("the PC itself (localhost)", "127.0.0.1", {"host": "localhost:8766"}, 200), ("the owner's Tailscale link", "127.0.0.1", ts, 200)]
        got = [(n, F.serve(c, h, NOW + 5, out, sp)[0], want) for n, c, h, want in cases]
        check("c. private only: WiFi / Funnel / non-tailnet / no Tailscale user -> 403; the PC itself and the Tailscale link -> 200",
              all(g == w for _, g, w in got), [x for x in got if x[1] != x[2]])
        st, body = F.serve("127.0.0.1", ts, NOW + 5, out, sp)
        bad = {k for k in json.dumps(body).lower().split('"') if k in ("account", "acct", "pos", "position", "order", "pnl", "balance", "login", "user", "token", "key")}
        check("c. the body is market data only: no account / order / position / user keys", st == 200 and body["bars"] and not bad, bad)
        check("d. a fresh file (< 20 s): no build started", not spawned, spawned)
        os.utime(os.path.join(out, "fp.json"), (NOW - 60, NOW - 60))
        F.serve("127.0.0.1", ts, NOW, out, sp); F.serve("127.0.0.1", ts, NOW + 1, out, sp); F.serve("127.0.0.1", ts, NOW + 2, out, sp)
        check("d. an old file: ONE build child started while it runs (three requests, one child)", len(spawned) == 1, spawned)
        F._P["proc"].done = True
        F.serve("127.0.0.1", ts, NOW + 3, out, sp)
        check("d. ... and another only after that child ended", len(spawned) == 2, spawned)
        F.serve("192.168.1.50", wifi, NOW + 4, out, sp)
        check("d. a refused (WiFi) request never starts a build", len(spawned) == 2, spawned)
        F._P.update(proc=None, started=0.0)
        st, body = F.serve("127.0.0.1", ts, NOW + 86400, out, lambda: Proc())
        check("c. yesterday's file is never served as today (the next day: empty + building)", st == 200 and body["bars"] == [] and body.get("building"), body)
    src = open(os.path.join(ROOT, "engine", "livefp.py"), encoding="utf-8").read()
    head = src.split("# ------------------------------------------------------------------------------------------------ the incremental build")[0]
    check("d. no pandas / numpy anywhere in engine/livefp.py (the route path stays light; the child is plain Python)", "import pandas" not in src and "import numpy" not in src)
    check("d. the child runs BELOW_NORMAL with no window on Windows (nice 10 elsewhere), stdin / out / err closed",
          "BELOW_NORMAL | NO_WINDOW" in src and "os.nice(10)" in src and "subprocess.DEVNULL" in src and "0x00004000" in head)
    body = src.split("def selftest()")[0]                       # the selftest writes its own temp tick file only
    import re as _re
    writes = _re.findall(r'open\(([^,]+),\s*"(?:w|a|wb|ab)"', body)
    check("d. read only: nothing that can trade is imported; the only file it writes is its own JSON (data/livefp, via a .tmp + replace)",
          not any(m in src for m in ("engine.ninjatrader", "engine import live\n", "engine.live ", "tradovate", "oif", "incoming")) and writes == ["tmp"], writes)
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys; sys.path.insert(0, %r); import engine.livefp; print('pandas' in sys.modules, 'numpy' in sys.modules)" % ROOT],
                       capture_output=True, text=True, timeout=60)
    check("d. importing engine.livefp loads neither pandas nor numpy", r.stdout.strip() == "False False", (r.stdout, r.stderr[-200:]))


def test_server():
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("e. server.py: GET /api/live/footprint next to /api/live/state, through engine/livefp.serve, never a 500",
          '@app.get("/api/live/footprint")' in src and "_fp.serve(" in src and src.index('"/api/live/state"') < src.index('"/api/live/footprint"'))
    try:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
    except Exception:  # noqa: BLE001
        check("e. route test skipped: no fastapi here", True)
        return
    import re
    block = re.search(r'@app\.get\("/api/live/footprint"\)\n(def live_footprint.*?)(?=\n\n\n)', src, re.S).group(1)
    app = FastAPI()
    ns = {"app": app, "Request": Request, "J": lambda b, s=200: __import__("fastapi").responses.JSONResponse(b, status_code=s)}
    exec("@app.get('/api/live/footprint')\n" + block, ns)  # noqa: S102 (the route's own text, under test)
    with tempfile.TemporaryDirectory() as td:
        write(td, ticks(n=300))
        F.build(td, F.OUT_DIR if False else os.path.join(td, "out"), NOW)
        real = F.OUT_DIR
        F.OUT_DIR = os.path.join(td, "out")
        try:
            os.utime(os.path.join(td, "out", "fp.json"))
            c = TestClient(app, base_url="http://testserver")
            r1 = c.get("/api/live/footprint", headers={"host": "192.168.1.20:8766"})
            check("e. the real route: a device that is not the PC / Tailscale -> 403", r1.status_code == 403, (r1.status_code, r1.text[:120]))
        finally:
            F.OUT_DIR = real


if __name__ == "__main__":
    test_parity()
    test_incremental()
    test_private_and_cheap()
    test_server()
    print(f"\n{PASSES[0]}/{PASSES[0] + len(FAILS)} passed")
    sys.exit(1 if FAILS else 0)
