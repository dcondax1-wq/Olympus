"""K8 Monday (night-kalshi8 2026-11-20): shared loaders for the $55 sizing, the edge tests and the dry run.

Reads only local caches (no network): the K8 public tape /home/user/kalshi_cache/kmetal (ot_ = the first 45 s of trades of each
leg window, mk_ = every settled 15-minute market with its target and settle) and the fresh tape of Nov 16-19 fetched tonight with
engine.kalshi_adapt.fetch_tape (public GET, <= 1 a second) at research/kalshi_k8_monday/data/tape_fresh.jsonl.
Fees are verify.py's exact ones (ceil to the cent of 0.07 x C x P x (1-P) per order).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine import kalshi_clock as KC  # noqa: E402

CACHE = os.environ.get("K8_CACHE_DIR", "/home/user/kalshi_cache/kmetal")
FRESH = os.path.join(HERE, "data", "tape_fresh.jsonl")
_spec = importlib.util.spec_from_file_location("k8m_verify", os.path.join(ROOT, "research", "kalshi_red_team", "verify.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

FIRST, LAST = dt.date(2026, 8, 3), dt.date(2026, 11, 19)
HOLD_FROM = dt.date(2026, 10, 22)            # held out: the newest 4 weeks (Oct 22 - Nov 18) + Nov 19
# the six metals legs (5 are executor legs; gold 16:15 DOWN was the friend's too, never ours)
LEGS = {lid: dict(KC.LEG[lid]) for lid in KC.LEG}
LEGS["gold_1615_down"] = {"id": "gold_1615_down", "series": "KXGOLD15M", "tz": "ET", "open": (16, 0), "side": "no", "skip": "cme",
                          "name": "gold DOWN 16:00-16:15 ET"}
LIVE3 = ("gold_0530_down", "gold_1700_up", "silver_1700_up")


def fee(price, n) -> float:
    return float(V.fee(Decimal(str(round(price, 4))), Decimal(int(n))))


def _jl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out


_MK = {}


def markets(series) -> dict:
    """{ticker: {"res", "fs" (target), "ev" (settle), "close" epoch}} of every settled 15-minute market in the cache."""
    if series not in _MK:
        out = {}
        for r in _jl(os.path.join(CACHE, f"mk_{series}.jsonl")):
            if r.get("result") not in ("yes", "no"):
                continue
            try:
                close = dt.datetime.fromisoformat(r["close_time"].replace("Z", "+00:00")).timestamp()
                fs, ev = float(r["floor_strike"]), float(r["expiration_value"])
            except (TypeError, ValueError, KeyError):
                fs = ev = None
                close = None
            out[r["ticker"]] = {"res": r["result"], "fs": fs, "ev": ev, "close": close}
        _MK[series] = out
    return _MK[series]


_TAPE = {}


def tape() -> dict:
    """{ticker: {"o", "res", "tr"}}: the cached first-45-s tape (results from mk_) + tonight's fresh tape (wins on overlap)."""
    if not _TAPE:
        for s in ("KXGOLD15M", "KXSILVER15M", "KXNATGAS15M", "KXWTI15M", "KXBRENT15M"):
            mk = markets(s)
            for r in _jl(os.path.join(CACHE, f"ot_{s}.jsonl")):
                m = mk.get(r["t"])
                if m:
                    _TAPE[r["t"]] = {"o": float(r["o"]), "res": m["res"], "tr": r.get("tr") or []}
        for r in _jl(FRESH):
            if r.get("res") in ("yes", "no"):
                _TAPE[r["t"]] = {"o": float(r["o"]), "res": r["res"], "tr": r.get("tr") or []}
    return _TAPE


def our_trades(tr, side):
    """[(seconds, price of OUR side, contracts)] of takers buying our side, in time order."""
    out = []
    for x in tr or []:
        try:
            s, ts, yp, c = float(x[0]), str(x[1]), float(x[2]), float(x[3])
        except (TypeError, ValueError, IndexError):
            continue
        if ts == side and c > 0 and 0 < yp < 1:
            out.append((s, round(yp if side == "yes" else 1 - yp, 4), c))
    return sorted(out)


def walk_from(tr, side, t0, stake, cap=0.99, until=45.0):
    """What a stake-$ taker order sent at t0 s gets, walking the takers of our side from t0 (the red team's '+20 s walk'):
    -> (contracts, average price, first price) or (0, None, None). Whole contracts, at most `stake` $, prices <= cap."""
    got, cost, first = 0, 0.0, None
    for s, p, c in our_trades(tr, side):
        if s < t0 or s > until:
            continue
        if p > cap + 1e-9:
            continue
        first = p if first is None else first
        k = int(min(c + 1e-9, math.floor((stake - cost) / p + 1e-9)))
        if k <= 0:
            if got == 0 and c < 1 and (stake - cost) >= p:      # fractional prints: count them toward one contract
                continue
            break
        got, cost = got + k, cost + k * p
        if stake - cost < p:
            break
    return (got, round(cost / got, 4), first) if got else (0, None, first)


def bets(stake=2.5, delay=20.0, legs=None, first=FIRST, last=LAST, cap=0.99, min_share=0.5):
    """One row per leg-day the executor would bet (its own calendar: London clock, UK / CME holiday skips), priced by walking
    the public tape from +delay s with `stake` $. Unfilled (under half the wanted contracts by 45 s) rows are kept with n=0."""
    T = tape()
    out = []
    d = first
    while d <= last:
        if d.weekday() < 5:
            for lid in (legs or LEGS):
                L = LEGS[lid]
                if KC.skipped(L, d):
                    continue
                o = KC.leg_open(L, d)
                tk = KC.ticker(L["series"], o)
                rec = T.get(tk)
                if not rec:
                    continue
                n, px, p1 = walk_from(rec["tr"], L["side"], delay, stake, cap)
                want = None
                if p1:
                    want = max(1, int(math.floor(stake / p1 + 1e-9)))
                row = {"day": d, "leg": lid, "ticker": tk, "side": L["side"], "o": o, "res": rec["res"], "won": rec["res"] == L["side"],
                       "n": 0, "price": None, "first": p1, "hold": d >= HOLD_FROM}
                if n and (want is None or n >= max(1, math.ceil(want * min_share - 1e-9))):
                    f = fee(px, n)
                    cost = n * px + f
                    row.update(n=n, price=px, fee=f, cost=round(cost, 4), pnl=round((n if row["won"] else 0) - cost, 4))
                out.append(row)
        d += dt.timedelta(days=1)
    return out


def summary(rows) -> dict:
    r = [x for x in rows if x.get("n")]
    if not r:
        return {"n": 0}
    cost = sum(x["cost"] for x in r)
    net = sum(x["pnl"] for x in r)
    days = sorted({x["day"] for x in rows})
    weeks = max(1.0, ((days[-1] - days[0]).days + 1) / 7.0)
    items = [{"cluster": str(x["day"]), "pnl": x["pnl"], "cost": x["cost"]} for x in r]
    return {"n": len(r), "won": sum(1 for x in r if x["won"]), "win_rate": round(sum(1 for x in r if x["won"]) / len(r), 4),
            "avg_price": round(sum(x["price"] for x in r) / len(r), 4), "net_usd": round(net, 2), "cost_usd": round(cost, 2),
            "net_per_1": round(net / cost, 4), "t": round(V.cluster_t(items), 2), "fees_usd": round(sum(x["fee"] for x in r), 2),
            "usd_week": round(net / weeks, 2), "bets_week": round(len(r) / weeks, 2), "unfilled": len(rows) - len(r)}
