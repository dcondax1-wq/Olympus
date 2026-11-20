"""Read-only speed-up candidates for the PC bot's poll (day-speed 2026-11-20), monkeypatched in a research process only.
apply(name) -> undo(). Each must leave every frame the bot sees identical (tests/test_speed_replay.py proves it).
"""
from __future__ import annotations

import os
import time

REG = {}


def reg(fn):
    REG[fn.__name__] = fn
    return fn


def apply(name):
    return REG[name]()


@reg
def none():
    return lambda: None


# ------------------------------------------------------------------ 1. NinjaTrader bar file: parse only the appended tail
FULL_EVERY_S = 900.0        # backstop: a full read at least every 15 min (an in-place rewrite of the same length is caught)
MAX_GROWTH = 16384          # more than ~350 new lines at once (a catch-up / rewrite): full read


def tail_load(self, path):
    """Drop-in for engine.ninjatrader.NinjaTraderBars.load: same frame, but a file that only GREW since the last read
    (LE_BarFeed appends one line a bar) is parsed from the last complete line on; anything else (trimmed / rewritten /
    replaced: the first bytes differ or the file got shorter) is a full read exactly as today."""
    import io
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
    inc = getattr(self, "_tail", None)
    if inc is None:
        inc = self._tail = {}
    prev = inc.get(path)
    try:
        with open(path, "rb") as fh:
            head = fh.read(256)
            same = bool(prev) and st.st_ino == prev["ino"] and prev["off"] <= st.st_size <= prev["off"] + MAX_GROWTH \
                and time.time() - prev["full_t"] < FULL_EVERY_S \
                and len(head) >= len(prev["head"]) and head[:len(prev["head"])] == prev["head"]
            if same and prev["off"] > 0:                 # the bytes just before the old end must be the same too
                fh.seek(max(0, prev["off"] - 64))
                same = fh.read(prev["off"] - max(0, prev["off"] - 64)) == prev["tailfp"]
            if same:
                fh.seek(prev["off"])
                new = fh.read()
                base, off0 = prev["raw"], prev["off"]
            else:
                fh.seek(0)
                new = fh.read()
                base, off0 = None, 0
    except OSError:
        return None
    cut = new.rfind(b"\n") + 1                       # only complete lines (LE_BarFeed ends every line with "\n")
    body = new[:cut]
    try:
        part = pd.read_csv(io.BytesIO(body), header=None, names=cols, usecols=range(6), on_bad_lines="skip", dtype=str,
                           engine="python") if body.strip() else pd.DataFrame(columns=cols, dtype=str)
    except Exception:
        return None
    for c in cols:
        part[c] = pd.to_numeric(part[c], errors="coerce")
    part = part.dropna(subset=["time", "open", "high", "low", "close"])
    part["volume"] = part["volume"].fillna(0.0)
    raw = part if base is None else pd.concat([base, part], ignore_index=True)
    off = off0 + cut
    tailfp = ((prev["tailfp"] if base is not None else b"") + body)[-64:]
    inc[path] = {"off": off, "head": head, "raw": raw, "ino": st.st_ino, "tailfp": tailfp,
                 "full_t": prev["full_t"] if base is not None else time.time()}
    df = raw.copy()
    df["time"] = df["time"].astype("int64")
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    self._cache[path] = (key, df)
    return df


@reg
def nt_tail_load():
    from engine import ninjatrader as nt
    old = nt.NinjaTraderBars.load
    nt.NinjaTraderBars.load = tail_load

    def undo():
        nt.NinjaTraderBars.load = old
    return undo
