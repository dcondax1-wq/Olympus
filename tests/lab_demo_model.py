"""Plumbing fixture for engine/lab_adapter.py (NOT a strategy): at the 09:45 ET bar close, go with the first 15 minutes'
direction, stop beyond the 09:30-09:45 range, 2R target, flat 15:55. An unfinished trade is returned as exit_kind 'open'."""
from tools.strategy_lab import make_trade

NAME = "lab_demo"
PARAMS = {"rr": 2.0}


def run(bars5, params=None, es5=None):
    p = {**PARAMS, **(params or {})}
    out = []
    for day, g in bars5.groupby("day", sort=True):
        g = g.reset_index(drop=True)
        orb = g[(g["mod"] >= 570) & (g["mod"] < 585)]
        sig = g[g["mod"] == 580]
        if len(orb) < 3 or not len(sig):
            continue
        i0 = int(sig.index[0])
        d = 1 if g.loc[i0, "close"] > orb["open"].iloc[0] else -1
        entry = float(g.loc[i0, "close"])
        stop = float(orb["low"].min() - 1) if d == 1 else float(orb["high"].max() + 1)
        tgt = entry + d * p["rr"] * abs(entry - stop)
        exit_px, kind, exit_t = None, "open", None
        for j in range(i0 + 1, len(g)):
            b = g.loc[j]
            if (d == 1 and b["low"] <= stop) or (d == -1 and b["high"] >= stop):
                exit_px, kind, exit_t = stop, "stop", b["time"]
                break
            if (d == 1 and b["high"] >= tgt) or (d == -1 and b["low"] <= tgt):
                exit_px, kind, exit_t = tgt, "target", b["time"]
                break
            if b["mod"] >= 955:
                exit_px, kind, exit_t = float(b["close"]), "time", b["time"]
                break
        if kind == "open":
            exit_px, exit_t = float(g["close"].iloc[-1]), int(g["time"].iloc[-1])
        out.append(make_trade(g.loc[i0, "time"], exit_t, d, entry, stop, exit_px, kind, setup="demo-ORB", target=round(tgt, 2)))
    return out


def state(bars5, params=None, es5=None):
    return {"status": "DEMO", "levels": [], "events": []}
