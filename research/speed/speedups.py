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


# ------------------------------------------------------------------ 2. history: keep the last 150 days in the poll
HIST_KEEP_DAYS = 150        # LIT and ATLAS read from engine/lit_live.window_start: the previous month's first day - 8 days (<= ~70 days)


def _read_hist_capped(self, sym, tf):
    """engine.live.LiveBot._read_hist with the cap of patch_2_hist_cap.diff (before the archive merge)."""
    import pandas as pd
    from engine import live, pcbars
    path = os.path.join(live.DATA_DIR, f"{sym}_{tf}.csv")
    if not os.path.exists(path):
        df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    else:
        st_ = os.stat(path)
        hit = getattr(self, "_hist_cache", {}).get(path)
        if hit and hit[0] == (st_.st_mtime_ns, st_.st_size):
            df = hit[1]
        else:
            df = pd.read_csv(path)
            df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
            if self.no_yahoo:
                df = pcbars.tidy(df)
                self._hist_cache = {**getattr(self, "_hist_cache", {}), path: ((st_.st_mtime_ns, st_.st_size), df)}
    keep = self.cfg.get("hist_keep_days", HIST_KEEP_DAYS)
    if keep and tf in ("1m", "5m") and sym == self.cfg.get("sym", "NQ") and len(df):
        cut = int(self.clock()) - int(float(keep) * 86400)
        if int(df["time"].min()) < cut:
            df = df[df["time"] >= cut]
    if self.no_yahoo and tf in ("1m", "5m"):
        arc = self._archive(sym, tf)
        if len(arc):
            df, sh = pcbars.merge_basis(df, arc)
            if sh:
                self._nt_note(f"basis:{sym}:{tf}", "warn", f"{sym} {tf}: the TradingView history sits {-sh:+.2f} pts from "
                              "NinjaTrader's bars (a contract roll): history back-adjusted onto NinjaTrader's contract", every_s=86400)
    return df


@reg
def hist_cap():
    """The bot's own NQ 1m / 5m history (TradingView export: 5 years of 5m, all of 2026 in 1m) capped to the last
    HIST_KEEP_DAYS days of the bot's clock BEFORE the per-poll archive merge, de-duplicate, sort and clean."""
    from engine import live
    old = live.LiveBot._read_hist
    live.LiveBot._read_hist = _read_hist_capped

    def undo():
        live.LiveBot._read_hist = old
    return undo
