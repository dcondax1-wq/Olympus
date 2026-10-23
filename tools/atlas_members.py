"""ATLAS member variants (2026-10-22): each member's trades re-run by its OWN research code with other exits / entries.

  EMA  tools/second_ema.py  trades_of(E, X) on the clean bars (entry / exit dicts as second_model.json "ema_lon_vix")
  MD   tools/second_md.py   md_cands + sim_x + greedy (gen / sim / flt as second_model.json "macd_sweep")
  SR   tools/second_sr.py   run_key + set_targets (key as second_model.json "sr_nyreclaim")

Entry modes (ent):
  "mkt"            today: market at the 5m open after the signal (+1 tick)
  ("lc", n)        limit at the SIGNAL CLOSE price for n 5m bars (a latency-proof entry: a late bot still gets the planned
                   price or nothing); filled when a bar trades 1 tick through it, at the limit or a better open; the fill
                   bar gets no target / breakeven credit (each simulator's own limit-fill rule)
  delay k          (late test) the order goes out k 5m bars late: mkt -> the open k bars later; lc -> the same limit
                   price, working from k bars later (tools/second_robust.py's late test for mkt)
Every set is checked: the default key must give exactly research/second/*_best.json (tools/second_robust.same).

    python -X utf8 tools/atlas_members.py check     # defaults == stored research trades
Paper research only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CACHE = os.path.join(ROOT, "research", "runs", "_cache", "atlas_sets")
TICK = 0.25


def _cfg():
    return json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]


# ================================================================================================ EMA
_E = {}


def _ema_base():
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    if "df" not in _E:
        import pandas as pd
        df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        RS.load_frame(df, live_cut=False)
        SE.D.clear() if hasattr(SE.D, "clear") and SE.D is not RS.D else None
        d = SE.load()
        _E["df"] = SE.candidates().copy()
        _E["d"] = d
    return SE, _E["d"], _E["df"]


def ema_trades(E=None, X=None, ent="mkt", delay=0):
    SE, d, df0 = _ema_base()
    c = _cfg()["ema_lon_vix"]
    E = {**c["entry"], **(E or {})}
    X = {**c["exit"], **(X or {})}
    df = df0
    if ent != "mkt" or delay:
        rows = []
        n = d["n"]
        for j, row in enumerate(df0.itertuples(index=False)):
            dr = int(row.dir)
            sig = int(row.sig)
            s = d["sid"][sig]
            if ent == "mkt":
                ei = sig + 1 + delay
                if ei >= n or d["sid"][ei] != s or d["mod"][ei] >= 935:
                    continue
                e = d["o"][ei] * dr + TICK
                risk = e - float(row.stop)
                if SE.MIN_STOP <= risk <= SE.MAX_STOP:
                    rows.append((j, ei, e, risk, 0))
                continue
            nb = int(ent[1])
            lvl = d["c"][sig] * dr
            L = d["l"] if dr > 0 else -d["h"]
            O = d["o"] * dr
            for k in range(sig + 1 + delay, min(sig + 1 + delay + nb, n)):
                if d["sid"][k] != s or d["mod"][k] >= 930:
                    break
                if L[k] <= float(row.stop):          # the stop is gone before a fill: no trade (a fill + stop counts below)
                    if L[k] <= lvl - TICK:
                        e = min(O[k], lvl)
                        risk = e - float(row.stop)
                        if SE.MIN_STOP <= risk <= SE.MAX_STOP:
                            rows.append((j, k, e, risk, 1))
                    break
                if L[k] <= lvl - TICK:
                    e = min(O[k], lvl)
                    risk = e - float(row.stop)
                    if SE.MIN_STOP <= risk <= SE.MAX_STOP:
                        rows.append((j, k, e, risk, 1))
                    break
        df = df0.iloc[[r[0] for r in rows]].copy().reset_index(drop=True)
        df["ei"] = [r[1] for r in rows]; df["e"] = [r[2] for r in rows]; df["risk"] = [r[3] for r in rows]
        df["lim"] = [r[4] for r in rows]
        df = df.sort_values(["ei", "dir"]).reset_index(drop=True)
    d["cand"] = df
    try:
        U = SE.trades_of(E, X)
    finally:
        d["cand"] = df0
    out = []
    for u in U:
        if SE.qty("usd500", u["risk_pts"]) <= 0:
            continue
        out.append({k: u[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} |
                   {"exit_kind": str(u["exit_kind"])})
    return out


# ================================================================================================ MD
_MD = {}


def md_trades(gen=None, sim=None, flt=None, ent="mkt", delay=0):
    from engine import lit
    from tools import second_md as SM
    c = _cfg()["macd_sweep"]
    gen = {**c["gen"], **(gen or {})}
    sim = {**c["sim"], **(sim or {})}
    flt = {**c["flt"], **(flt or {})}
    if "X" not in _MD:
        M = lit.Market()
        _MD["X"] = SM.Ctx(M, lit.bars_1m(M))
    X = _MD["X"]
    ck = json.dumps(gen, sort_keys=True)
    if ck not in _MD:
        _MD[ck] = SM.md_cands(X, **gen)
    C = _MD[ck]
    outs = []
    C2 = []
    for z in C:
        j0 = z["j"]
        if delay:
            j = j0 + delay
            if j + 1 >= X.n or X.day[j] != X.day[j0]:
                continue
            z = {**z, "j": j}
        if ent == "mkt":
            r = SM.sim_x(X, z, sim)
        else:
            nb = int(ent[1])
            z = {**z, "cisd": float(X.c[j0])}
            r = SM.sim_x(X, z, {**sim, "ent": "lim"})
            if r is not None and int(X.Xt[r["x0"]]) >= int(X.t[z["j"] + 1]) + nb * 300:
                r = None
        C2.append(z)
        outs.append(r)
    T = SM.greedy(X, C2, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
    out = []
    for z, r in T:
        q = SM.q_usd(500, r["risk"])
        if q <= 0:
            continue
        t = SM.tr_rec(X, z, r, q, "MACD-div")
        out.append({k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind")})
    return out


# ================================================================================================ SR
def sr_trades(key=None, ent="mkt", delay=0):
    from tools import retail_standalone as RS
    from tools import second_sr as SR
    import pandas as pd
    key = {**_cfg()["sr_nyreclaim"]["key"], **(key or {})}
    if "sr_df" not in _E:
        _E["sr_df"] = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    RS.load_frame(_E["sr_df"], live_cut=False)
    SR.D.clear()
    SR._OC.clear()
    d = SR.data()
    old_gen = SR.gen
    if ent != "mkt" or delay:
        def gen(dd, setup, g, _k=delay, _ent=ent):
            out = []
            for cnd in old_gen(dd, setup, g):
                sig, fill, dr, kind = cnd[0], cnd[1], cnd[2], cnd[3]
                if kind != 0 or fill >= 0:
                    out.append(cnd); continue
                if _ent == "mkt":
                    k0 = sig + 1 + _k
                    if k0 >= dd["n"] or dd["sid"][k0] != cnd[6]:
                        continue
                    out.append((sig, k0) + tuple(cnd[2:]))
                    continue
                nb = int(_ent[1])
                lvl = dd["c"][sig] * dr
                ld = dd["l"] if dr > 0 else -dd["h"]
                od = dd["o"] * dr
                stop_d = cnd[5] * dr
                f = None
                for k in range(sig + 1 + _k, min(sig + 1 + _k + nb, dd["n"])):
                    if dd["sid"][k] != cnd[6] or dd["rel"][k] >= 1315:
                        break
                    if ld[k] <= lvl - TICK:
                        f = k; break
                    if ld[k] <= stop_d:
                        break
                if f is None:
                    continue
                epx = min(od[f], lvl)
                out.append((sig, f, dr, 1, dr * epx, cnd[5], cnd[6], cnd[7], cnd[8]))
            return out
        SR.gen = gen
    try:
        T = SR.run_key(key)
        TT = SR.set_targets(SR.trades_of(T, "usd500", "nyreclaim"), key)
    finally:
        SR.gen = old_gen
    out = [{k: (float(u[k]) if k in ("entry", "stop", "exit") or (k == "target" and u[k] is not None) else u[k])
            for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} | {"exit_kind": str(u["exit_kind"])}
           for u in TT if u["day"] >= "2021-11-01"]
    SR.D.clear(); SR._OC.clear(); RS.D.clear()
    _E.pop("df", None)                       # retail_standalone's frame was reloaded: the EMA cache must rebuild
    return out


# ================================================================================================ sets -> units
def parse(name, key):
    """key = JSON string {"E":..,"X":..} (EMA) | {"gen","sim","flt"} (MD) | {"key"} (SR), + "ent", "delay"."""
    return json.loads(key)


def trades(name, key):
    p = parse(name, key)
    ent = p.get("ent", "mkt")
    if isinstance(ent, list):
        ent = tuple(ent)
    dl = int(p.get("delay", 0))
    if name == "EMA":
        return ema_trades(p.get("E"), p.get("X"), ent, dl)
    if name == "MD":
        return md_trades(p.get("gen"), p.get("sim"), p.get("flt"), ent, dl)
    if name == "SR":
        return sr_trades(p.get("key"), ent, dl)
    raise ValueError(name)


def _path(name, key):
    h = hashlib.md5((name + key).encode()).hexdigest()[:12]
    return os.path.join(CACHE, f"{name}_{h}.pkl")


_U = {}


def units(name, key):
    k = (name, key)
    if k in _U:
        return _U[k]
    p = _path(name, key)
    if os.path.exists(p):
        _U[k] = pickle.load(open(p, "rb"))["units"]
        return _U[k]
    from tools import second_robust as R
    T = trades(name, key)
    U = R.units_of(T, name)
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump({"name": name, "key": key, "units": U, "n": len(T)}, open(p, "wb"))
    _U[k] = U
    return U


def cached(name, key):
    return os.path.exists(_path(name, key))


def check():
    from tools import second_robust as R
    ok = True
    for nm, fn in (("EMA", lambda: ema_trades()), ("SR", lambda: sr_trades()), ("MD", lambda: md_trades()), ("EMA", lambda: ema_trades())):
        T = fn()
        s = R.same(T, R.stored(nm))
        ok &= s
        print(nm, len(T), "== stored" if s else "DIFF", flush=True)
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(0 if check() else 1)
