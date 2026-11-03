"""The cached event table of the data city (research/datacity/_cache, gitignored).

Incremental: when the cached table's bars are a prefix of the current bars (a shift-invariant fingerprint, so a contract
roll that re-bases old prices keeps the cache), only the new complete days are built, on a CONTEXT_DAYS tail of bars so
every rolling feature (250-day ATR regime, prior-week levels, EMA warm-up) is exactly what a full build gives.
tests/test_datacity.py checks incremental == full.
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import bars as B
from . import features as F

CACHE = os.path.join(B.OUT, "_cache")
CONTEXT_DAYS = 420
TABLE_VERSION = f"2|{F.COST}|{F.H}|{F.MIN_STOP}|{F.MAX_STOP}|{F.TGT_R}"      # any change = full rebuild
EV_COLS = ("t", "dnum", "trig", "dir", "win", "slot", "risk", "R", "pnl", "h1", "h2", "h3", "f15", "f30", "f60") + \
          tuple("s_" + f for f in F.FAMILIES)
DAY_END = 21 * 3600 + 57 * 60      # UTC seconds after midnight: past 16:55 ET (EST), before 18:00 ET (EDT) of the next day


def sources() -> dict:
    """The side inputs of features.build: ES bars, CBOE VIX / VXN, the news calendar."""
    return {"es": B.load_es(), "vix": B.load_daily("VIX"), "vxn": B.load_daily("VXN"), "news": B.load_news(),
            "vix3m": B.load_cboe("vix3m")}


def _table(feat) -> dict:
    """Event columns of the complete days, with the day as days-since-epoch (stable across builds)."""
    ev = feat["ev"]
    keep = ev["day"] < F.complete_days(feat)
    out = {k: ev[k][keep] for k in EV_COLS if k != "dnum"}
    out["dnum"] = feat["days"][ev["day"][keep]].astype("int64")
    return out


def _events(tab) -> dict:
    """The grid's view of a table: {"ev": columns sorted by (trigger, time) with a day index, "days"}."""
    days, day = np.unique(tab["dnum"], return_inverse=True)
    order = np.lexsort((tab["t"], tab["trig"]))
    ev = {k: v[order] for k, v in tab.items() if k != "dnum"}
    ev["day"] = day[order].astype(np.int32)
    return {"ev": ev, "days": days.astype("datetime64[D]")}


def _read_meta(cache):
    meta_p, tab_p = os.path.join(cache, "meta.json"), os.path.join(cache, "events.npz")
    if not (os.path.exists(meta_p) and os.path.exists(tab_p)):
        return None
    try:
        with open(meta_p, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    if meta.get("version") != TABLE_VERSION or meta.get("schema") != list(EV_COLS):
        return None
    return meta


def event_table(df, full=False, cache=CACHE, src=None, log=print):
    """(events, info) for the bars in df: info["mode"] is "cached", "incremental" or "full"."""
    src = src if src is not None else sources()
    os.makedirs(cache, exist_ok=True)
    tab_p = os.path.join(cache, "events.npz")
    meta = None if full else _read_meta(cache)
    last_bar = int(df["time"].max())
    if meta and int(meta["last_t"]) <= last_bar and B.fingerprint(df, int(meta["last_t"])) == meta["fp"]:
        old = dict(np.load(tab_p))
        if int(meta["last_t"]) == last_bar:
            log(f"event table: cached ({len(old['t'])} events, last day {meta['last_day']})")
            return _events(old), {"mode": "cached", "new_days": 0}
        last_d = np.datetime64(meta["last_day"], "D")
        t_start = int((last_d - np.timedelta64(CONTEXT_DAYS, "D")).astype("datetime64[s]").astype(np.int64))
        new = _table(F.build(df[df["time"] >= t_start].reset_index(drop=True), **src))
        cut = last_d.astype(np.int64)
        tab = {k: np.concatenate([old[k][old["dnum"] <= cut], new[k][new["dnum"] > cut]]) for k in EV_COLS}
        order = np.lexsort((tab["t"], tab["trig"]))                # the same row order as a full build
        tab = {k: v[order] for k, v in tab.items()}
        info = {"mode": "incremental", "new_days": int(len(np.unique(new["dnum"][new["dnum"] > cut])))}
    else:
        tab = _table(F.build(df, **src))
        info = {"mode": "full", "new_days": int(len(np.unique(tab["dnum"])))}
    if not len(tab["t"]):
        raise SystemExit("datacity: no events (no bars?)")
    last_day = np.datetime64(int(tab["dnum"].max()), "D")
    last_t = int(df["time"][df["time"] <= int(last_day.astype("datetime64[s]").astype(np.int64)) + DAY_END].max())
    np.savez_compressed(tab_p, **tab)
    with open(os.path.join(cache, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": TABLE_VERSION, "schema": list(EV_COLS), "last_t": last_t, "last_day": str(last_day),
                   "fp": B.fingerprint(df, last_t), "events": int(len(tab["t"]))}, fh, indent=1)
    log(f"event table: {info['mode']}, {len(tab['t'])} events, {info['new_days']} new days, last day {last_day}")
    return _events(tab), info
