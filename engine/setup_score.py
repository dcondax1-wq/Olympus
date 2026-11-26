"""LIT setup score (big-setupscore 2026-11-26; design research/setupscore/DESIGN.md). DISPLAY ONLY: it never decides, sizes,
routes or blocks a trade. "Similar setups: N, won X%, avg +Y R (+$Z at this size)" from every LIT setup since 2021 with an
outcome (taken R, or what it would have made with every gate open): k nearest neighbours on time of day, sweep depth,
displacement, inducements and the prior VIX close, same side only, standardised, k = 50, only setups dated before today.

Pure and safe: no network, no orders, no numpy; every public function returns None / "" on any problem instead of raising.
Called only off the order thread: engine/setup_progress (watchdog) and engine/notify.entry_message (push daemon thread).
Pool file: research/setupscore/pool.json (tools/setupscore_build.py, nightly); its "verdict" says whether the score separated
winners from losers out of sample ("separates") or not ("info only": the line then says so).
Tests: python -X utf8 -m tests.test_setup_score
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL_PATH = os.path.join(ROOT, "research", "setupscore", "pool.json")
FEATS = ("h", "depth", "disp", "idm", "vix")        # time of day in hours, sweep depth / displacement in ATR, inducements (<= 3), VIX
K = 50
_LOCK = threading.Lock()
_CACHE: dict = {}


def load(path: str | None = None) -> dict | None:
    """The pool (cached by file mtime). None when missing / unreadable."""
    p = path or POOL_PATH
    try:
        mt = os.path.getmtime(p)
        with _LOCK:
            c = _CACHE.get(p)
            if c and c[0] == mt:
                return c[1]
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict) or not isinstance(d.get("rows"), list):
            return None
        with _LOCK:
            _CACHE[p] = (mt, d)
        return d
    except Exception:  # noqa: BLE001
        return None


def _num(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def feats(mod=None, depth=None, disp=None, idm=None, vix=None) -> dict:
    """The score's feature dict from raw facts (ET minute of day, ATR multiples, count, VIX)."""
    m = _num(mod)
    i = _num(idm)
    return {"h": None if m is None else m / 60.0, "depth": _num(depth), "disp": _num(disp),
            "idm": None if i is None else min(3.0, max(0.0, i)), "vix": _num(vix)}


def score(f: dict, d: int, pool: dict | None = None, before: str | None = None, k: int = K) -> dict | None:
    """k nearest same-side setups dated before `before` (YYYY-MM-DD; default: all of the pool). Missing features are left out of
    the distance. -> {n, won, win, avg_r, k} or None."""
    try:
        P = pool if pool is not None else load()
        if not P or d not in (1, -1):
            return None
        cols = P.get("cols") or ["day", "dir"] + list(FEATS) + ["r"]
        ix = {c: j for j, c in enumerate(cols)}
        sd = P.get("sd") or {}
        use = [c for c in FEATS if f.get(c) is not None and (sd.get(c) or 0) > 0]
        if not use:
            return None
        dist = []
        for row in P["rows"]:
            if row[ix["dir"]] != d or (before and row[ix["day"]] >= before):
                continue
            s = 0.0
            for c in use:
                v = row[ix[c]]
                if v is None:
                    s += 4.0                       # a missing fact counts as 2 sd away
                else:
                    s += ((v - f[c]) / sd[c]) ** 2
            dist.append((s, row[ix["r"]]))
        if not dist:
            return None
        dist.sort(key=lambda x: x[0])
        nb = [r for _, r in dist[:k]]
        won = sum(1 for r in nb if r > 0)
        return {"n": len(nb), "won": won, "win": round(won / len(nb), 3), "avg_r": round(sum(nb) / len(nb), 3), "k": k,
                "on": use}
    except Exception:  # noqa: BLE001
        return None


def line(sc: dict | None, risk_usd=None, verdict: str | None = None) -> str:
    """One phone line. '' when there is no score."""
    try:
        if not sc or not sc.get("n"):
            return ""
        r = float(sc["avg_r"])
        s = f"Similar setups: {sc['n']}, won {round(100 * sc['win'])}%, avg {r:+.2f}R"
        ru = _num(risk_usd)
        if ru:
            u = r * ru
            s += f" ({'+' if u >= 0 else '-'}${abs(u):,.0f} at this size)"
        if (verdict if verdict is not None else (load() or {}).get("verdict")) != "separates":
            s += " · history only, not a predictor"
        return s
    except Exception:  # noqa: BLE001
        return ""


def _prior_vix(day: str):
    """The newest CBOE VIX close dated before `day` from data/VIX_1d.csv (None when missing)."""
    try:
        p = os.path.join(ROOT, "data", "VIX_1d.csv")
        mt = os.path.getmtime(p)
        c = _CACHE.get("vix")
        if not c or c[0] != mt:
            rows = []
            with open(p, encoding="utf-8") as fh:
                next(fh)
                for ln in fh:
                    a = ln.strip().split(",")
                    if len(a) >= 5:
                        rows.append((a[0], float(a[4])))
            c = (mt, sorted(rows))
            _CACHE["vix"] = c
        best = None
        for dd, v in c[1]:
            if dd < day:
                best = v
            else:
                break
        return best
    except Exception:  # noqa: BLE001
        return None


def _et_mod(t):
    from zoneinfo import ZoneInfo
    e = dt.datetime.fromtimestamp(float(t), ZoneInfo("America/New_York"))
    return e.hour * 60 + e.minute, (e + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def from_brain_row(row: dict) -> tuple | None:
    """engine/brain setup row ({t, dir, checks: [{key, value}], plan}) -> (feature dict, side, session day) or None."""
    try:
        d = int(row.get("dir"))
        mod, day = _et_mod(float(row.get("t")) - 300)        # the Brain stamps the bar CLOSE; the pool uses the bar's open minute
        cv = {c.get("key"): c.get("value") for c in row.get("checks") or [] if isinstance(c, dict)}
        return feats(mod=mod, depth=cv.get("depth"), disp=cv.get("disp"), idm=cv.get("idm"), vix=_prior_vix(day)), d, day
    except Exception:  # noqa: BLE001
        return None


_LAST: dict = {}                      # side -> (t, score): the newest scored setup, for the entry push that follows it


def brain_score(row: dict) -> dict | None:
    """The score of one Brain setup row (remembered for the entry push). None on any problem."""
    try:
        x = from_brain_row(row)
        if not x:
            return None
        f, d, day = x
        sc = score(f, d, before=day)
        if sc:
            with _LOCK:
                _LAST[d] = (float(row.get("t")), sc)
        return sc
    except Exception:  # noqa: BLE001
        return None


def brain_line(row: dict, risk_usd=None) -> str:
    """The score line for one Brain setup row ('' on any problem)."""
    return line(brain_score(row), risk_usd)


def entry_line(side, t, risk_usd=None, within_s: float = 3 * 3600) -> str:
    """The line for a LIT entry push: the score the setup ping remembered for this side (set up within 3 h before the fill),
    else a lookup on time of day + VIX only. '' on any problem."""
    try:
        d = 1 if str(side).upper().startswith("L") else -1 if str(side).upper().startswith("S") else None
        if d is None or t is None:
            return ""
        with _LOCK:
            m = _LAST.get(d)
        if m and 0 <= float(t) - m[0] <= within_s:
            return line(m[1], risk_usd)
        mod, day = _et_mod(float(t))
        return line(score(feats(mod=mod, vix=_prior_vix(day)), d, before=day), risk_usd)
    except Exception:  # noqa: BLE001
        return ""
