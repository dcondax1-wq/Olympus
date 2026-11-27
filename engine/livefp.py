"""LIVE FOOTPRINT (day-livefp 2026-11-27, red team #44): TODAY's NQ footprint per 5-minute bar for the live chart's heat strip,
on the PC's PRIVATE link only. Market data only: no account, no order, no position, no secret in it.

Where it comes from: ninjatrader/LE_TickRec.cs (the read-only tick recorder, engine/tickrec.py) appends every NQ trade with the
bid / ask in force to  Documents\\NinjaTrader 8\\le_ticks\\<ROOT>_<YYYY-MM-DD>.csv  (ET date, header t_ms,price,size,bid,ask).
The nightly order-flow summaries (engine/ofsum) read the same trades; this reads TODAY's file as it grows.

Cheap and outside the trading process (red team worry: CPU / IO on the trading PC):
  * the route (server.py GET /api/live/footprint -> serve()) only reads a small JSON file and, when it is older than REFRESH_S and
    nobody is building it, starts ONE child `python -m engine.livefp build` at BELOW_NORMAL priority (no window). The trading
    process never parses ticks and never holds the GIL for this; nothing runs unless someone is looking (the chart polls once a
    minute on the private link only; never over ntfy, no quota).
  * the child reads only the NEW bytes of today's file since its last run (offset + per-bar sums kept in data/livefp/state.json),
    at most MAX_READ bytes a run (a mid-day first run catches up over a few runs), plain Python (no pandas import), then writes
    data/livefp/fp.json atomically and exits.
Private: serve() answers only the PC itself or the owner's Tailscale link (engine/live_site.private_why: tailnet address, a
signed-in Tailscale user, no Funnel, not the home WiFi); anything else gets 403. Read only: it never writes into NinjaTrader's
folders and imports nothing that can trade.

The shape = tools/build_of_room.strip_from_summary (day-ofroom2: nq/ofstrip.js reads it): {v, day, tick, bucket, bars: [{t "HH:MM"
ET, o, h, l, c, v, d (buy - sell lots), big (signed lots of prints >= 20), cells [[2-pt cell low, buy, sell]], abs [{side, who,
px, vz, dz}] (OF1 absorption at the bar's extreme)}]}, RTH 09:30-15:55 ET, + asof (newest trade, epoch s) and live: true.
Side per trade = engine/tickrec.classify (quote rule, then the tick rule; zero ticks carry the last side), quotes NinjaTrader
filled in (> 90 % of quoted trades at the bid or at the ask, >= 50 quoted) dropped as in engine/tickrec.quotes_filled_in.

    python -X utf8 -m engine.livefp build [--nt DIR] [--out DIR]     one incremental run (what the route starts)
    python -X utf8 -m engine.livefp selftest
Tests: tests/test_livefp.py (parity with engine/ofsum.summarize on the same trades, incremental = whole, private, cheap).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "livefp")
ET = ZoneInfo("America/New_York")
TICK = 0.25
BUCKET_TICKS = 8                 # 2-point cells (tools/build_of_room.STRIP_BUCKET_TICKS)
ZONE_TICKS, ABS_SHARE, ABS_MIN_N = 8, 0.20, 20     # OF1 (research/orderflow/PREREG_ticks.md), as build_of_room
BIG = 20                         # a big print: >= 20 lots (ofsum b20)
RTH = (570, 960)                 # 09:30 .. 15:55 ET bar opens (minutes of the day)
REFRESH_S = 20.0                 # the route starts a build when fp.json is older than this
MAX_READ = 6_000_000             # bytes of new ticks a run reads (~150k trades); the rest on the next run
BUILD_TIMEOUT_S = 120.0          # a child older than this is left alone and a new one may start
ROOTS = ("NQ", "MNQ")            # NQ first; MNQ only when no NQ file today
BELOW_NORMAL, NO_WINDOW = 0x00004000, 0x08000000
VERSION = 1


def et_day(t: float) -> str:
    return dt.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d")


def tick_file(day: str, nd: str | None) -> str | None:
    if not nd:
        return None
    for r in ROOTS:
        p = os.path.join(nd, "le_ticks", f"{r}_{day}.csv")
        if os.path.isfile(p):
            return p
    return None


# ------------------------------------------------------------------------------------------------ the incremental build (child)
def new_state(day: str, path: str) -> dict:
    return {"v": VERSION, "day": day, "path": os.path.basename(path), "off": 0, "last_px": None, "last_side": 0,
            "q": [0, 0, 0], "drop_quotes": None, "asof": None, "rows": 0, "bars": {}}


def _bar(st: dict, bt: int) -> dict:
    k = str(bt)
    b = st["bars"].get(k)
    if b is None:
        b = st["bars"][k] = {"o": None, "h": None, "l": None, "c": None, "vol": 0, "buy": 0, "sell": 0, "n": 0, "big": 0, "fp": {}}
    return b


def _parse(line: str):
    p = line.strip().split(",")
    if len(p) < 3:
        return None
    try:
        t_ms, px, sz = int(float(p[0])), float(p[1]), int(float(p[2]))
        bid = float(p[3]) if len(p) > 3 and p[3] != "" else 0.0
        ask = float(p[4]) if len(p) > 4 and p[4] != "" else 0.0
    except ValueError:
        return None                                   # the header, a torn line
    if px <= 0 or sz <= 0:
        return None
    return t_ms, px, sz, bid, ask


def feed(st: dict, rows: list) -> None:
    """Add trades [(t_ms, price, size, bid, ask)] (file order) to the state: side, then the bar sums and the footprint cells."""
    if st["drop_quotes"] is None:                     # tickrec.quotes_filled_in, decided once >= 50 quoted trades were seen
        q = st["q"]
        for _, px, _, b, a in rows:
            if b > 0 and a > 0:
                q[0] += 1; q[1] += px == b; q[2] += px == a
        if q[0] >= 50:
            st["drop_quotes"] = q[1] / q[0] > 0.9 or q[2] / q[0] > 0.9
    drop = bool(st["drop_quotes"])
    lp, ls = st["last_px"], st["last_side"]
    for t_ms, px, sz, b, a in rows:
        side = 0
        if not drop and b > 0 and a > 0 and a >= b:
            side = 1 if px >= a else -1 if px <= b else 0
        if lp is not None and px != lp:
            ls = 1 if px > lp else -1                 # the tick rule's sign (zero ticks carry the last one)
        if side == 0:
            side = ls
        lp = px
        bt = (t_ms // 1000) // 300 * 300
        B = _bar(st, bt)
        pk = int(round(px / TICK))
        if B["o"] is None:
            B["o"], B["h"], B["l"] = px, pk, pk
        B["h"], B["l"], B["c"] = max(B["h"], pk), min(B["l"], pk), px
        B["vol"] += sz; B["n"] += 1
        if side > 0:
            B["buy"] += sz
        elif side < 0:
            B["sell"] += sz
        if sz >= BIG:
            B["big"] += sz * side
        c = B["fp"].setdefault(str(pk), [0, 0, 0])   # [aggressive buy, aggressive sell, unknown] lots at this tick
        c[0 if side > 0 else 1 if side < 0 else 2] += sz
        st["asof"] = t_ms / 1000.0
    st["last_px"], st["last_side"] = lp, ls
    st["rows"] += len(rows)


def _head(path: str) -> str:
    """red team #44: the file's first 256 bytes (header + first trades), so a REPLACED file of the same or a larger size restarts too."""
    try:
        with open(path, "rb") as fh:
            return fh.read(256).decode("utf-8", "replace")
    except OSError:
        return ""


def read_new(st: dict, path: str, max_read: int = MAX_READ) -> int:
    """Read the complete lines after st["off"] (at most max_read bytes) and feed them. Returns the trades added."""
    size = os.path.getsize(path)
    head = _head(path)
    if size < st["off"] or (st.get("head") and head != st["head"]):   # replaced (shorter, or other first trades): start the day again
        st.update(new_state(st["day"], path))
    st["head"] = head
    if size == st["off"]:
        return 0
    with open(path, "rb") as fh:
        fh.seek(st["off"])
        raw = fh.read(min(max_read, size - st["off"]))
    end = raw.rfind(b"\n")
    if end < 0:
        return 0                                      # a line still being written
    raw = raw[:end + 1]
    rows = [r for r in (_parse(x) for x in raw.decode("utf-8", "replace").splitlines()) if r]
    st["off"] += len(raw)
    feed(st, rows)
    return len(rows)


def strip(st: dict) -> dict:
    """The state -> the strip (tools/build_of_room.strip_from_summary's shape), RTH bars only."""
    bars = []
    for k in sorted(st["bars"], key=int):
        bt, B = int(k), st["bars"][k]
        et = dt.datetime.fromtimestamp(bt, ET)
        mod = et.hour * 60 + et.minute
        if not (RTH[0] <= mod < RTH[1]):
            continue
        lo, hi = B["l"], B["h"]
        cells, fp = {}, {int(p): v for p, v in B["fp"].items()}
        for pk, (a, s, _u) in fp.items():
            c = round(((pk * TICK) // (BUCKET_TICKS * TICK)) * BUCKET_TICKS * TICK, 2)
            x = cells.setdefault(c, [c, 0, 0])
            x[1] += a; x[2] += s
        ab = []
        if B["n"] >= ABS_MIN_N:
            for side, lo_k, hi_k, d in (("low", lo, lo + ZONE_TICKS, 1), ("high", hi - ZONE_TICKS, hi, -1)):
                z = [v for pk, v in fp.items() if lo_k <= pk <= hi_k]
                vz = sum(a + s + u for a, s, u in z); dz = sum(a - s for a, s, _u in z)
                if vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz:
                    ab.append({"side": side, "who": "buyers" if side == "low" else "sellers", "px": (lo if side == "low" else hi) * TICK,
                               "vz": int(vz), "dz": int(dz)})
        bars.append({"t": et.strftime("%H:%M"), "o": B["o"], "h": hi * TICK, "l": lo * TICK, "c": B["c"], "v": B["vol"],
                     "d": B["buy"] - B["sell"], "big": B["big"], "cells": sorted(cells.values()), "abs": ab})
    return {"v": VERSION, "day": st["day"], "tick": TICK, "bucket": BUCKET_TICKS * TICK, "bars": bars, "asof": st["asof"], "live": True,
            "paper": True, "rows": st["rows"], "what": "NQ footprint by 5-minute bar, today, from the PC's tick recorder (market data only)"}


def _write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    from engine import fsutil
    fsutil.replace(tmp, path)


def build(nd: str | None = None, out_dir: str = OUT_DIR, now: float | None = None, max_read: int = MAX_READ) -> dict:
    """One incremental run: today's tick file -> data/livefp/state.json + fp.json. Returns a small report."""
    now = time.time() if now is None else now
    day = et_day(now)
    if nd is None:
        from engine import tickrec
        nd = tickrec.nt_dir()
    path = tick_file(day, nd)
    os.makedirs(out_dir, exist_ok=True)
    sp, fpp = os.path.join(out_dir, "state.json"), os.path.join(out_dir, "fp.json")
    if not path:
        _write_json(fpp, {"v": VERSION, "day": day, "bars": [], "live": True, "built": now,
                          "why": "no tick file today: the tick recorder is off or NinjaTrader has not recorded a trade yet"})
        return {"ok": False, "why": "no tick file", "day": day}
    try:
        st = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        st = None
    if not st or st.get("v") != VERSION or st.get("day") != day or st.get("path") != os.path.basename(path):
        st = new_state(day, path)
    n = read_new(st, path, max_read)
    _write_json(sp, st)
    out = strip(st)
    out["built"] = now
    out["behind"] = os.path.getsize(path) > st["off"] + 1        # more to read: the next run catches up
    _write_json(fpp, out)
    return {"ok": True, "day": day, "added": n, "rows": st["rows"], "bars": len(out["bars"]), "behind": out["behind"]}


# ------------------------------------------------------------------------------------------------ the route side (trading process)
_P: dict = {"proc": None, "started": 0.0}


def _spawn(argv=None):
    argv = argv or [sys.executable, "-X", "utf8", "-m", "engine.livefp", "build"]
    kw = {"cwd": ROOT, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = BELOW_NORMAL | NO_WINDOW
    else:
        kw["preexec_fn"] = lambda: os.nice(10)                      # noqa: PLW1509 (POSIX only)
    return subprocess.Popen(argv, **kw)


def kick(now: float | None = None, out_dir: str = OUT_DIR, spawn=None) -> bool:
    """Start one build child when fp.json is older than REFRESH_S and no child is running. Never waits for it."""
    now = time.time() if now is None else now
    p = _P["proc"]
    if p is not None and p.poll() is None:
        if now - _P["started"] < BUILD_TIMEOUT_S:
            return False
        try:                                          # red team #44: a stuck child is stopped, never left beside a new one
            p.kill()
            p.wait(5)
        except Exception:  # noqa: BLE001
            pass
    fpp = os.path.join(out_dir, "fp.json")
    try:
        if now - os.path.getmtime(fpp) < REFRESH_S:
            return False
    except OSError:
        pass
    try:
        _P["proc"], _P["started"] = (spawn or _spawn)(), now
        return True
    except Exception:  # noqa: BLE001
        _P["proc"] = None
        return False


def serve(client, headers, now: float | None = None, out_dir: str = OUT_DIR, spawn=None) -> tuple:
    """(status, body) for GET /api/live/footprint. Private only (engine/live_site.private_why); the file as it is, and a build
    started in the background when it is old. Never parses ticks here."""
    from engine import live_site
    why = live_site.private_why(client, headers)
    if why:
        return 403, {"ok": False, "error": why}
    now = time.time() if now is None else now
    kick(now, out_dir, spawn)
    day = et_day(now)
    try:
        d = json.load(open(os.path.join(out_dir, "fp.json"), encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if not isinstance(d, dict) or d.get("day") != day:
        return 200, {"v": VERSION, "day": day, "bars": [], "live": True, "building": True, "why": "building today's footprint (about 20 s)"}
    return 200, d


def selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        now = dt.datetime(2026, 11, 27, 10, 7, tzinfo=ET).timestamp()
        os.makedirs(os.path.join(td, "le_ticks"))
        t0 = int(dt.datetime(2026, 11, 27, 10, 0, tzinfo=ET).timestamp() * 1000)
        with open(os.path.join(td, "le_ticks", "NQ_2026-11-27.csv"), "w") as fh:
            fh.write("t_ms,price,size,bid,ask\n")
            for i in range(60):
                p = 21000 + (i % 7) * 0.25
                fh.write(f"{t0 + i * 1000},{p},{1 + i % 3},{p - 0.25 if i % 2 else p},{p if i % 2 else p + 0.25}\n")
        r = build(td, os.path.join(td, "out"), now)
        d = json.load(open(os.path.join(td, "out", "fp.json")))
        ok = r["ok"] and r["rows"] == 60 and len(d["bars"]) == 1 and d["bars"][0]["t"] == "10:00" and d["bars"][0]["v"] == sum(1 + i % 3 for i in range(60))
        print("livefp selftest:", "ok" if ok else "FAIL", r)
        return ok


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="engine.livefp")
    ap.add_argument("cmd", choices=["build", "selftest"])
    ap.add_argument("--nt", default=None)
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    r = build(a.nt, a.out)
    print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
