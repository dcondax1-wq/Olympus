"""research/speed/speedups.tail_load == engine.ninjatrader.NinjaTraderBars.load, frame for frame (day-speed 2026-11-20).

The tail reader parses only the lines LE_BarFeed appended since the last read; this proves it returns exactly today's frame
through appends, a torn last line, LE_BarFeed's trim (file rewritten shorter), a rewrite with the same first bytes, a junk
line, a duplicate bar time, a header line, a file replaced by a copy, and an empty file.
    python -X utf8 -m tests.test_speed_tail_load
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "speed"))

import pandas as pd  # noqa: E402
from pandas.testing import assert_frame_equal  # noqa: E402

from engine.ninjatrader import NinjaTraderBars  # noqa: E402
import speedups as SU  # noqa: E402

FAIL = []


def legacy_load(self, path):
    """engine/ninjatrader.NinjaTraderBars.load as of 2026-11-20 (before the tail reader), verbatim."""
    import pandas as pd
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = self._cache.get(path)
    if hit and hit[0] == key:
        return hit[1]
    cols = ["time", "open", "high", "low", "close", "volume"]
    try:
        df = pd.read_csv(path, header=None, names=cols, usecols=range(6), on_bad_lines="skip", dtype=str,
                         engine="python")
    except Exception:
        return None
    # (2026-11-03) every line LE_Feed / LE_BarFeed writes ends with "\n": a last line without it is still being
    # appended, and a cut number ("21000.5" read as "2100") would parse as a valid but wrong close. Dropped; the
    # next read (the file's size changes, so the cache misses) has it whole.
    try:
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            torn = fh.read(1) not in (b"\n", b"\r")
    except OSError:
        torn = False
    if torn and len(df):
        df = df.iloc[:-1]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time", "open", "high", "low", "close"])          # header row, half-written last line
    df["volume"] = df["volume"].fillna(0.0)
    df["time"] = df["time"].astype("int64")
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    self._cache[path] = (key, df)
    return df


def check(name, ok, info=""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAIL.append(name)


def line(t, px, v=10):
    return f"{t},{px:g},{px + 2:g},{px - 1.5:g},{px + 0.75:g},{v}\n"


class Pair:
    """Today's reader (legacy_load, frozen copy) vs the research tail reader AND engine.ninjatrader's load as it is now
    (after the lead applies patch_1_tail_load.diff it is the tail reader too: both must equal the frozen copy)."""
    def __init__(self, folder):
        self.a = NinjaTraderBars(folder=folder)
        self.b = NinjaTraderBars(folder=folder)
        self.c = NinjaTraderBars(folder=folder)

    def same(self, path):
        x = legacy_load(self.a, path)
        for y in (SU.tail_load(self.b, path), self.c.load(path)):
            if x is None or y is None:
                if not (x is None and y is None):
                    return False, "one is None"
                continue
            try:
                assert_frame_equal(x, y, check_dtype=True)
            except AssertionError as e:
                return False, str(e)[:300]
        return True, ""


def bump(path):
    """Windows-like: make sure the mtime changes between writes (the cache key)."""
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


def main():
    d = tempfile.mkdtemp(prefix="tail_load_")
    os.makedirs(os.path.join(d, "le_feed"))
    p = os.path.join(d, "le_feed", "NQ_1m.csv")
    t0 = 1_793_000_000 - 1_793_000_000 % 60
    rnd = random.Random(7)
    lines = [line(t0 + 60 * i, 27000 + rnd.uniform(-50, 50)) for i in range(3000)]
    with open(p, "w") as fh:
        fh.writelines(lines)
    P = Pair(d)
    ok, info = P.same(p)
    check("a. first read (full file)", ok, info)
    n = len(lines)
    all_ok = True
    for k in range(200):                                  # b. one bar appended a minute, read each time
        with open(p, "a") as fh:
            fh.write(line(t0 + 60 * (n + k), 27000 + rnd.uniform(-50, 50)))
        bump(p)
        ok, info = P.same(p)
        all_ok &= ok
    n += 200
    check("b. 200 appends, one bar each", all_ok, info)
    with open(p, "a") as fh:                              # c. torn last line (being written)
        fh.write(f"{t0 + 60 * n},27010.5,270")
    bump(p)
    ok, info = P.same(p)
    check("c. torn last line dropped like today", ok, info)
    with open(p, "a") as fh:                              # ... then completed
        fh.write("12.25,27009,27011,7\n")
    bump(p)
    ok, info = P.same(p)
    check("c2. the torn line completed", ok, info)
    n += 1
    with open(p, "a") as fh:                              # d. junk, header, duplicate time (last wins), short line
        fh.write("time,open,high,low,close,volume\n")
        fh.write("garbage line\n")
        fh.write(line(t0 + 60 * (n - 1), 27100))          # same time as the previous bar: last wins
        fh.write(f"{t0 + 60 * n},27001,27003,27000,27002\n")   # no volume -> 0
    bump(p)
    ok, info = P.same(p)
    check("d. header / junk / duplicate bar time / no volume", ok, info)
    n += 1
    with open(p) as fh:                                   # e. LE_BarFeed's Trim(): rewritten with the newest lines only
        keep = fh.readlines()[-2000:]
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        fh.writelines(keep)
    os.replace(tmp, p)
    bump(p)
    ok, info = P.same(p)
    check("e. trimmed (rewritten shorter, new file)", ok, info)
    for k in range(30):
        with open(p, "a") as fh:
            fh.write(line(t0 + 60 * (n + k), 27000 + rnd.uniform(-50, 50)))
        bump(p)
    n += 30
    ok, info = P.same(p)
    check("e2. appends after the trim", ok, info)
    with open(p) as fh:                                   # f. same first bytes, an earlier bar corrected, file longer
        L = fh.readlines()
    old = L[-10]
    L[-10] = old.replace(old.split(",")[1], str(round(float(old.split(",")[1]) - 7.0, 10))[:len(old.split(",")[1])].ljust(len(old.split(",")[1]), "0"))
    assert len(L[-10]) == len(old), (L[-10], old)
    L.append(line(t0 + 60 * n, 27000))
    n += 1
    with open(p, "w") as fh:                              # in place (File.Copy fallback): same inode
        fh.writelines(L)
    bump(p)
    SU.FULL_EVERY_S, keep_full = 0.0, SU.FULL_EVERY_S      # the 15-min backstop due: the same-length correction is read
    keep_cls = getattr(NinjaTraderBars, "TAIL_FULL_EVERY_S", None)
    if keep_cls is not None:
        NinjaTraderBars.TAIL_FULL_EVERY_S = 0.0
    ok, info = P.same(p)
    SU.FULL_EVERY_S = keep_full
    if keep_cls is not None:
        NinjaTraderBars.TAIL_FULL_EVERY_S = keep_cls
    check("f. rewrite in place, same head + length, a bar 10 lines back corrected: read by the 15-min full read", ok, info)
    with open(p, "w") as fh:                              # g. empty file
        pass
    bump(p)
    ok, info = P.same(p)
    check("g. empty file", ok, info)
    with open(p, "w") as fh:
        fh.writelines(lines[:50])
    bump(p)
    ok, info = P.same(p)
    check("h. refilled after empty", ok, info)
    big = os.path.join(d, "le_feed", "NQ_5m.csv")         # i. speed at the PC's size (21,000 1m lines)
    with open(big, "w") as fh:
        fh.writelines(line(t0 + 60 * i, 27000 + (i % 97)) for i in range(21000))
    P2 = Pair(d)
    P2.same(big)
    ta = tb = 0.0
    for k in range(20):
        with open(big, "a") as fh:
            fh.write(line(t0 + 60 * (21000 + k), 27000))
        bump(big)
        s = time.perf_counter(); legacy_load(P2.a, big); ta += time.perf_counter() - s
        s = time.perf_counter(); SU.tail_load(P2.b, big); tb += time.perf_counter() - s
    ok, info = P2.same(big)
    check(f"i. 21,000-line file: today {ta / 20 * 1000:.0f} ms a read, tail {tb / 20 * 1000:.0f} ms (identical)", ok and tb < ta, info)
    print(f"\n{'ALL OK' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
