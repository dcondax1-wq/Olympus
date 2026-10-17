"""Draw learner: P(a draw on liquidity is hit before the stop), learned walk-forward from the engine's own trades.

    from engine.draw_learner import predict
    p = predict(features)        # float in [0, 1], or None when no trained model is available (caller falls back)

`features` is one draw. Exact definitions (they follow research/lab/DOL_PLAYBOOK.md) are in research/lab/DRAW_LEARNER.md:
    kind         "ERL" (resting pools: day / week / session H-L, swings, equal highs-lows) | "IRL" (unmitigated FVGs)
    source       PDH PDL PWH PWL RTH ASIA LON ON D1SW H4SW H1SW M15SW M5SW EQ FVG5 FVG15 FVG1H FVG4H FVG1D
                 (unknown -> average source)
    dist_atr     distance entry -> draw / Wilder ATR14 of the closed 5m bars at the signal bar
    dist_r       distance entry -> draw / planned stop distance
    obstacles    price zones (live opposing 15m+ gaps, fresh 5m k=2 / 15m k=1 swings, merged within max(2 ticks, 0.1 ATR5))
                 starting strictly between entry and draw - 2 ticks
    age_h        hours since the pool / gap became usable
    eq           bool: the draw is (or merged with) a D8 equal-highs / equal-lows pool
    htf_dir      1H structure trend x trade direction: +1 / 0 / -1 (engine h1.trend * d)
    session      "AM" (signal bar opens before 12:00 ET) | "PM"
    within_reach bool: dist <= max(0.5 x ADR10, ADR10 - today's CME-day range so far)

The model is an L2-regularised logistic regression stored in data/draw_learner.json (trained by tools/train_draw_learner.py
on every labelled draw up to the training cut-off). Pure Python: no numpy needed at prediction time. The file is re-read
when it changes on disk, so a retrain is picked up by a running process.
"""
from __future__ import annotations

import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "data", "draw_learner.json")

SOURCES = ("PDH", "PDL", "PWH", "PWL", "RTH", "ASIA", "LON", "ON", "D1SW", "H4SW", "H1SW", "M15SW", "M5SW", "EQ",
           "FVG5", "FVG15", "FVG1H", "FVG4H", "FVG1D")
IRL_SOURCES = ("FVG5", "FVG15", "FVG1H", "FVG4H", "FVG1D")
# clip ranges: predictions outside the training support are made at the nearest edge
CLIP = {"dist_r": (0.1, 12.0), "dist_atr": (0.1, 60.0), "obstacles": (0.0, 40.0), "age_h": (0.0, 2000.0)}

# design: one row per draw. Groups are what the training report ranks (drop-one walk-forward log-loss).
NUMERIC = ("log_dist_r", "log_dist_r2", "log_dist_atr", "log1p_obstacles", "log1p_age_h", "eq", "htf_dir", "htf_flat",
           "pm", "irl", "within_reach")
FEATURE_NAMES = NUMERIC + tuple("src_" + s for s in SOURCES)
GROUPS = {"dist_r": ("log_dist_r", "log_dist_r2"), "dist_atr": ("log_dist_atr",), "obstacles": ("log1p_obstacles",),
          "age_h": ("log1p_age_h",), "eq": ("eq",), "htf_dir": ("htf_dir", "htf_flat"), "session": ("pm",),
          "kind": ("irl",), "within_reach": ("within_reach",), "source": tuple("src_" + s for s in SOURCES)}


def _num(x, default=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _clip(v, key):
    lo, hi = CLIP[key]
    return min(max(v, lo), hi)


def _truthy(x):
    if isinstance(x, str):
        return x.strip().lower() in ("1", "true", "yes", "y", "t")
    return bool(x)


def design_row(f: dict):
    """Feature dict -> list of floats in FEATURE_NAMES order, or None when the draw is unusable (no distance)."""
    if not isinstance(f, dict):
        return None
    dr, da = _num(f.get("dist_r")), _num(f.get("dist_atr"))
    if dr is None or da is None or dr <= 0 or da <= 0:
        return None
    ldr = math.log(_clip(dr, "dist_r"))
    lda = math.log(_clip(da, "dist_atr"))
    ob = math.log1p(_clip(_num(f.get("obstacles"), 0.0), "obstacles"))
    age = math.log1p(_clip(_num(f.get("age_h"), 0.0), "age_h"))
    eq = 1.0 if _truthy(f.get("eq")) else 0.0
    h = _num(f.get("htf_dir"), 0.0)
    hd = 1.0 if h > 0 else (-1.0 if h < 0 else 0.0)
    pm = 1.0 if str(f.get("session") or "AM").strip().upper() == "PM" else 0.0
    src = str(f.get("source") or "").strip().upper()
    kind = str(f.get("kind") or "").strip().upper()
    if kind not in ("ERL", "IRL"):
        kind = "IRL" if src.startswith("FVG") else "ERL"
    wr = f.get("within_reach")
    if wr is None:          # not supplied: derive nothing, treat as the common case (inside the day's remaining range)
        wr = 1.0
    row = [ldr, ldr * ldr, lda, ob, age, eq, hd, 1.0 if hd == 0 else 0.0, pm, 1.0 if kind == "IRL" else 0.0,
           1.0 if _truthy(wr) else 0.0]
    row += [1.0 if src == s else 0.0 for s in SOURCES]
    return row


# ------------------------------------------------------------------------------------------------ model file
_CACHE = {"path": None, "mtime": None, "model": None}


def load_model(path: str | None = None, reload: bool = False):
    """The trained model dict, or None (missing / unreadable / wrong schema). Cached; re-read when the file changes."""
    path = path or MODEL_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        _CACHE.update(path=path, mtime=None, model=None)
        return None
    if not reload and _CACHE["path"] == path and _CACHE["mtime"] == mtime:
        return _CACHE["model"]
    model = None
    try:
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
        names = tuple(m.get("features") or ())
        coef, mu, sd = m.get("coef"), m.get("mu"), m.get("sd")
        if names == FEATURE_NAMES and len(coef) == len(mu) == len(sd) == len(names) and _num(m.get("intercept")) is not None:
            model = m
    except Exception:
        model = None
    _CACHE.update(path=path, mtime=mtime, model=model)
    return model


def predict(features: dict, model: dict | None = None):
    """P(draw is touched before the stop is hit, before 15:55 ET) in [0, 1]; None without a trained model or usable input."""
    try:
        m = model if model is not None else load_model()
        if m is None:
            return None
        x = design_row(features)
        if x is None:
            return None
        eta = float(m["intercept"])
        for v, b, mu, sd in zip(x, m["coef"], m["mu"], m["sd"]):
            eta += b * (v - mu) / (sd if sd else 1.0)
        eta = max(-30.0, min(30.0, eta))
        return 1.0 / (1.0 + math.exp(-eta))
    except Exception:
        return None


def ev(p: float, dist_r: float) -> float:
    """Expected R of targeting a draw: win dist_r with probability p, lose the 1R stop otherwise."""
    return p * dist_r - (1.0 - p)


def pick(draws, min_r: float = 1.0, max_r: float | None = None, model: dict | None = None):
    """The max-EV draw among `draws` (dicts carrying the feature keys) with min_r <= dist_r (<= max_r).
    Returns (draw, p, ev) or None (no model / no qualifying draw)."""
    m = model if model is not None else load_model()
    if m is None:
        return None
    best = None
    for dw in draws or ():
        r = _num(dw.get("dist_r"))
        if r is None or r < min_r or (max_r is not None and r > max_r):
            continue
        p = predict(dw, m)
        if p is None:
            continue
        e = ev(p, r)
        if best is None or e > best[2]:
            best = (dw, p, e)
    return best


def info():
    """Small summary of the loaded model for dashboards / logs."""
    m = load_model()
    if m is None:
        return {"loaded": False, "path": MODEL_PATH}
    return {"loaded": True, "path": MODEL_PATH, "trained_through": m.get("trained_through"), "n_trades": m.get("n_trades"),
            "n_draws": m.get("n_draws"), "version": m.get("version")}
