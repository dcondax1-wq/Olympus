"""HQ bias (owner 2026-10-23: "a strategy that trades 2+ times a week, high-quality setups, with high probability and high
profit"): TOP-DOWN DRAW ON LIQUIDITY. Research only - no engine file, no live_model*.json, no second_model.json, no UI.

Idea (what is new vs research/writeups/lit-htf-confluences.md, lit-bias-discretion.md, lit-untested-targets.md): those
studies kept LIT's 120 trades and its VIX-band target and used the HTF bias as a FILTER / size / target tilt on them. Here
the bias builds a different trade list: the higher-time-frame draw decides the DIRECTION and the TARGET, then LIT's own
5m chain (sweep -> inducement -> displacement -> CISD, engine/lit.py candidates) or a pullback into the displacement FVG
or a market entry is only taken when it points at that draw, and the trade aims AT the draw (the nearest unswept HTF pool
in the bias direction), capped at a fixed R. LIT's own filters can be loosened because the bias does the selecting.

  HTF pools (all known before the trigger bar closes; untested = not touched since they exist):
    pd  PDH / PDL                 pw  PWH / PWL            pm  PMH / PML
    gap NWOG / NDOG edges         fvg unfilled 4H (20 days) and daily (60 days) fair value gaps, near edge
  Bias methods (direction at the close of the trigger bar):
    near      the nearest untested pool of the set is above -> long, below -> short
    near_pd   the same with PDH / PDL only
    pdw       premium / discount of the prior week's range (below the middle -> long)
    pdw_wtd   ... of the prior week + this week so far
    dco / wco the previous day's / week's candle colour (close vs open)
    opp       an HTF pool (pd / pw / pm) on one side was taken this period, the other side not -> draw to the other side
    fvg       the nearest untested 4H / daily FVG
    a+b       two methods agree
  Target: draw = the nearest untested pool of the set in the trade's direction (no trade when it is under min_rr R);
          drawN = the first pool of the set >= min_rr R; both capped (banked) at cap R.
  Entries: lit  = the live LIT entry (limit at the 5m CISD level for 30 min, then a 1m CISD -> next 1m open)
           fvg  = a plain limit (30 min, no 1m CISD) at the near edge of the last displacement FVG
           mkt  = market at the next 5m open after the 5m CISD close
  Stop 1 tick beyond the sweep extreme (8-80 pts), BE at be R (entry + 1.25 pts), 15-minute check (live), flat 15:55.
  Size for the headline $: LIT's size rule ($800 up to a 20-pt stop, 800 x 20 / stop, max 40 micros), $1.90 a micro,
  1 tick slippage on market entries and stop / BE / time exits. 2026 on true 1m bars, 2021-25 on 5m bars (no 1m data).

Method: grid picked on 2026 H1 (constraints first: >= 2 trades a week, win >= 40% (true winners >= +1R), average winner
>= 1.5R), checked untouched on 2026 H2, 2025 and 2021-24; a pre-2025 re-pick (pick on 2021-11..2024-12, test on 2025 +
2026); plateau map; placebos (random bias with the same pipeline; same entry times with shuffled direction; same direction
at random times); month by month; drop the best 5 trades; the MFFU eval path (two_week sizing, tools/second_mix.py /
tools/second_account_b.py executors) alone on a 50K, next to LIT on the 50K (LIT first, one position), and on a 25K
account B (no-hedge vs LIT).

    python -X utf8 tools/hq_bias.py feats      # pools + bias + targets for every LIT candidate (cache)
    python -X utf8 tools/hq_bias.py lookahead  # features recomputed on data cut at the trigger bar == full-data features
    python -X utf8 tools/hq_bias.py grid       # every variant, every span -> research/hq/bias_grid.csv.gz
    python -X utf8 tools/hq_bias.py pick       # H1 pick + pre-2025 re-pick + eval stage -> research/hq/bias_picks.json
    python -X utf8 tools/hq_bias.py study      # plateau, placebos, months, drop-best-5 for the top 3 -> research/hq/bias_study.json
    python -X utf8 tools/hq_bias.py save       # trades JSON (common format) + rl.save runs hq_bias_*
Paper only.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import io
import itertools
import json
import os
import pickle
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402

OUTD = os.path.join(ROOT, "research", "hq")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
VER = "v2"
COMM_REAL = 1.90                    # $ a micro round trip (the engine books lit.COMM = 1.40; the difference is taken here)
FVG_AGE = {"4h": 20 * 276, "d": 60 * 276}     # FVG memory in 5m bars
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31")}
SETS = {"htf": ("pd", "pw", "pm", "gap"), "all": ("pd", "pw", "pm", "gap", "fvg")}
BIASES = ("near", "near_pd", "pdw", "pdw_wtd", "dco", "wco", "opp", "fvg", "near+pdw", "near+dco", "pdw+dco", "near+opp")
# LIT live management (t_check + be_off), no weekly stop / Monday rule (they are LIT's own filters / sizing)
BASE = {**lit.DEFAULTS, **AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF, "wk_stop": None, "monday": False, "scale_in": None}
LIT_LIVE = {**lit.DEFAULTS, **AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF}
WINDOWS = {"kz": [[120, 300], [510, 690]], "kzpm": [[120, 300], [510, 690], [810, 930]], "all": [[120, 930]]}
FILTERS = {"live": {"disp": 0.8, "depth": 0.5, "idm_a": [1.0, 36, 1]}, "loose": {"disp": 0.5, "depth": 0.3, "idm_a": None}}
os.makedirs(OUTD, exist_ok=True)


# ================================================================================================ HTF pools
def _htf_bars(M, key):
    key = np.asarray(key)
    st = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    en = np.r_[st[1:], M.n]
    return {"h": np.maximum.reduceat(M.h, st).astype(float), "l": np.minimum.reduceat(M.l, st).astype(float),
            "last": en - 1}


def _first_touch(M, side, p, a, b):
    """First 5m index in [a, b) that touches p (side +1 = a pool above: high >= p; -1 = below: low <= p); 10**12 if none."""
    if a >= b:
        return 10 ** 12
    seg = (M.h[a:b] >= p) if side > 0 else (M.l[a:b] <= p)
    j = int(np.argmax(seg))
    return a + j if seg[j] else 10 ** 12


def _firsts(key):
    key = np.asarray(key)
    st = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    out = np.zeros(len(key), dtype=np.int64)
    out[st] = st
    np.maximum.accumulate(out, out=out)
    return out


def fvg_list(M):
    """Unfilled-at-birth 4H / daily FVGs: (side, price, known_i, touch_i). Bullish (L[j+1] > H[j-1]): a pool BELOW price at
    L[j+1] (side -1, touched when a 5m low <= it); bearish (H[j+1] < L[j-1]): ABOVE at H[j+1]. Known at the close of the
    third HTF bar; expires FVG_AGE bars later."""
    out = []
    keys = {"4h": M.day_of.astype(np.int64) * 10 + ((M.mod - 1080) % 1440) // 240, "d": M.day_of}
    for nm, key in keys.items():
        B = _htf_bars(M, key)
        H, L, last = B["h"], B["l"], B["last"]
        for j in range(1, len(H) - 1):
            kn = int(last[j + 1])
            end = min(M.n, kn + 1 + FVG_AGE[nm])
            if L[j + 1] - H[j - 1] >= 1.0:
                p = float(L[j + 1])
                out.append((-1, p, kn, _first_touch(M, -1, p, kn + 1, end), end, "fvg"))
            if L[j - 1] - H[j + 1] >= 1.0:
                p = float(H[j + 1])
                out.append((1, p, kn, _first_touch(M, 1, p, kn + 1, end), end, "fvg"))
    return out


def day_pools(M, fvgs):
    """Per trading day k: array rows (side, price, known_i, touch_i, cls_id) of every HTF pool live that day. touch_i is the
    first touch since the pool exists (from the start of its period: day / week / month), searched up to the day's end."""
    CLS = {"pd": 0, "pw": 1, "pm": 2, "gap": 3, "fvg": 4}
    wk0, mo0 = _firsts(M.week_id), _firsts(M.month_id)
    fv = sorted(fvgs, key=lambda z: z[2])
    fk = np.array([z[2] for z in fv]) if fv else np.zeros(0)
    out = []
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        rows = []
        for p_, cls, a in (("pd", "pd", s), ("pw", "pw", int(wk0[s])), ("pm", "pm", int(mo0[s]))):
            if p_ + "h" in x:
                for side, px in ((1, x[p_ + "h"]), (-1, x[p_ + "l"])):
                    rows.append((side, float(px), s - 1, _first_touch(M, side, float(px), a, e), CLS[cls]))
        for g, a in (("nwog", int(wk0[s])), ("ndog", s)):
            gv = x.get(g)
            if gv:
                op = float(M.o[a])
                for px in gv:
                    side = 1 if px > op else -1
                    rows.append((side, float(px), s - 1, _first_touch(M, side, float(px), a, e), CLS["gap"]))
        # FVGs known before the day's end, alive at the day's start, untouched before the day's start
        hi = int(np.searchsorted(fk, e))
        for side, px, kn, tch, end, _ in fv[:hi]:
            if end <= s or tch < s:
                continue
            rows.append((side, px, kn, tch, CLS["fvg"]))
        out.append(np.array(rows, dtype=float) if rows else np.zeros((0, 5)))
    return out


# ================================================================================================ features per candidate
def _near(P, i, px, cls_ids):
    """(dist up, dist down) to the nearest untested pool of the classes at bar i (close px)."""
    if not len(P):
        return np.inf, np.inf
    m = (P[:, 2] <= i) & (P[:, 3] > i) & np.isin(P[:, 4], cls_ids)
    up = P[m & (P[:, 0] > 0) & (P[:, 1] > px), 1]
    dn = P[m & (P[:, 0] < 0) & (P[:, 1] < px), 1]
    return (float(up.min() - px) if len(up) else np.inf), (float(px - dn.max()) if len(dn) else np.inf)


def _sgn_near(u, d):
    if not np.isfinite(u) and not np.isfinite(d):
        return 0
    return 1 if u < d else -1 if d < u else 0


def feats_of(M, C, pools, aux):
    """Bias per method and target distances per set for every candidate (bars <= the trigger bar i only)."""
    CL = {"htf": [0, 1, 2, 3], "all": [0, 1, 2, 3, 4], "pd": [0], "fvg": [4], "hp": [0, 1, 2]}
    out = []
    for z in C:
        k, i, d = z["k"], z["i"], z["dir"]
        x = M.ctx[k]
        P = pools[k]
        px = float(M.c[i])
        f = {}
        for sn in ("htf", "all"):
            u, dn = _near(P, i, px, CL[sn])
            f["near|" + sn] = _sgn_near(u, dn)
        u, dn = _near(P, i, px, CL["pd"]); f["near_pd"] = _sgn_near(u, dn)
        u, dn = _near(P, i, px, CL["fvg"]); f["fvg"] = _sgn_near(u, dn)
        if "pwh" in x and x["pwh"] > x["pwl"]:
            pos = (px - x["pwl"]) / (x["pwh"] - x["pwl"])
            f["pdw"] = 1 if pos < 0.5 else -1
            lo, hi = min(x["pwl"], float(aux["wlo"][i])), max(x["pwh"], float(aux["whi"][i]))
            f["pdw_wtd"] = 1 if (px - lo) / max(hi - lo, 1e-9) < 0.5 else -1
        else:
            f["pdw"] = f["pdw_wtd"] = 0
        f["dco"] = aux["dco"][k]
        f["wco"] = aux["wco"][k]
        # opp: an HTF pool (pd / pw / pm) taken this period (touch_i <= i, inside today's or its period) on one side only
        if len(P):
            m = np.isin(P[:, 4], CL["hp"]) & (P[:, 3] <= i)
            hi_t, lo_t = bool((m & (P[:, 0] > 0)).any()), bool((m & (P[:, 0] < 0)).any())
            f["opp"] = 0 if hi_t == lo_t else (-1 if hi_t else 1)
        else:
            f["opp"] = 0
        # target distances in direction space from the market entry (entry_d), per set, sorted
        tg = {}
        ed = z["entry_d"]
        for sn in ("htf", "all"):
            if len(P):
                m = (P[:, 2] <= i) & (P[:, 3] > i) & np.isin(P[:, 4], CL[sn]) & (P[:, 0] == d)
                dist = np.sort(P[m, 1] * d - ed)
                tg[sn] = [round(float(v), 2) for v in dist if v > 0]
            else:
                tg[sn] = []
        f["tg"] = tg
        f["fvg_mid"] = _disp_fvg(M, z)
        out.append(f)
    return out


def _disp_fvg(M, z):
    """Near edge (first touch on a pullback) of the LAST 5m FVG of the displacement (bars between the sweep extreme and the
    trigger), direction space; None if none. Known at the trigger bar's close."""
    d, ee, i = z["dir"], z["ext_i"], z["i"]
    hi_d, lo_d = (M.h, M.l) if d == 1 else (-M.l, -M.h)
    best = None
    for j in range(ee + 1, i):
        if lo_d[j + 1] > hi_d[j - 1]:
            best = round(float(lo_d[j + 1]), 2)
    return best


def aux_of(M):
    g = lambda a, key, fn: getattr(__import__("pandas").Series(a).groupby(np.asarray(key)), fn)().values
    aux = {"whi": g(M.h.astype(float), M.week_id, "cummax"), "wlo": g(M.l.astype(float), M.week_id, "cummin")}
    dco = [0]
    for k in range(1, len(M.days)):
        _, s, e = M.days[k - 1]
        dco.append(int(np.sign(M.c[e - 1] - M.o[s])))
    aux["dco"] = dco
    # previous ISO week's candle (first bar of the week -> last bar of the week)
    wk = {}
    for k, (_, s, e) in enumerate(M.days):
        w = int(M.week_id[s])
        r = wk.setdefault(w, [float(M.o[s]), None])
        r[1] = float(M.c[e - 1])
    ws = sorted(wk)
    wco = []
    for k, (_, s, e) in enumerate(M.days):
        j = ws.index(int(M.week_id[s]))
        wco.append(int(np.sign(wk[ws[j - 1]][1] - wk[ws[j - 1]][0])) if j > 0 else 0)
    aux["wco"] = wco
    return aux


def build_feats(M, C):
    t0 = time.time()
    fv = fvg_list(M)
    pools = day_pools(M, fv)
    aux = aux_of(M)
    Fz = feats_of(M, C, pools, aux)
    print(f"features: {len(C)} candidates, {len(fv)} FVGs, {time.time() - t0:.0f}s", flush=True)
    return Fz


_D = {}


def data():
    if "M" not in _D:
        M, C = F.market("cisd", [])
        p = os.path.join(CACHE, f"hqbias_{VER}_{len(C)}_{F.rl._data_key().replace(':', '_')}.pkl")
        if os.path.exists(p):
            Fz = pickle.load(open(p, "rb"))
        else:
            Fz = build_feats(M, C)
            pickle.dump(Fz, open(p, "wb"))
        _D.update(M=M, C=C, Fz=Fz, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _D


def bias_dir(f, b, sn):
    def one(nm):
        if nm == "near":
            return f["near|" + sn]
        return f[nm]
    if "+" in b:
        a, c = b.split("+")
        x, y = one(a), one(c)
        return x if x == y else 0
    return one(b)


# ================================================================================================ one variant
def variant_cands(v, seed=None):
    """The candidate list of variant v (bias, set, tgt, entry): only setups pointing at the draw, target = the draw.
    seed: random-bias placebo (a coin per trading day replaces the bias)."""
    D = data()
    C, Fz, M = D["C"], D["Fz"], D["M"]
    rng = np.random.default_rng(seed) if seed is not None else None
    coin = {}
    out = []
    for z, f in zip(C, Fz):
        if rng is not None:
            if z["day"] not in coin:
                coin[z["day"]] = 1 if rng.random() < 0.5 else -1
            b = coin[z["day"]]
        else:
            b = bias_dir(f, v["bias"], v["set"])
        if b != z["dir"]:
            continue
        tl = f["tg"][v["set"]]
        if not tl:
            continue
        zz = dict(z)
        zz["targets"] = {"draw": tl[:1] if v["tgt"] == "draw" else tl}
        if v["entry"] == "fvg":
            if f["fvg_mid"] is None:
                continue
            zz["ref_d"] = f["fvg_mid"]
        elif v["entry"] == "mkt":
            zz["mkt"] = {"t": int(M.t[z["entry_i"]]), "entry_d": z["entry_d"], "stop_d": z["ext_d"] - BASE["stop_buf"], "tf": 5}
        out.append(zz)
    return out


def params_of(v):
    P = {**BASE, **FILTERS[v["filt"]], "window": WINDOWS[v["win"]], "classes": ["draw"], "min_rr": v["min_rr"],
         "max_rr": v["cap"], "be_r": v["be"], "max_per_day": v["mpd"], "fallback_rr": None}
    if v["entry"] == "fvg":
        P["cisd1m"] = None                   # a plain limit at the FVG edge (fills on the touch, no 1m confirmation)
    return P


def run_variant(v, sessions=None, seed=None, cands=None):
    D = data()
    C = cands if cands is not None else variant_cands(v, seed)
    T = lit.run_x(D["M"], C, params_of(v), sessions or F.SESS, B1=D["B1"], B5=D["B5"])
    for t in T:                              # $1.90 a micro instead of the engine's $1.40
        t["pnl"] = round(t["pnl"] - (COMM_REAL - lit.COMM) * t["qty"], 2)
        t["low"] = round(min(t["low"], t["pnl"]) - (COMM_REAL - lit.COMM) * t["qty"], 2)
        t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
    return T


def lit_reference():
    D = data()
    T = lit.run_x(D["M"], D["C"], LIT_LIVE, F.SESS, B1=D["B1"], B5=D["B5"])
    for t in T:
        t["pnl"] = round(t["pnl"] - (COMM_REAL - lit.COMM) * t["qty"], 2)
        t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
    return T


# ================================================================================================ scoring
def span_sess(sp):
    a, z = SPANS[sp]
    return [d for d in F.SESS if a <= d <= z]


def _wk(d):
    return dt.date.fromisoformat(d).isocalendar()[:2]


def stats(T, sp):
    S = span_sess(sp)
    a, z = SPANS[sp]
    TT = [t for t in T if a <= t["day"] <= z]
    weeks = sorted({_wk(d) for d in S})
    nw = max(len(weeks), 1)
    o = {"n": len(TT), "tpw": round(len(TT) / (len(S) / 5), 2)}
    if not TT:
        return o
    cw = collections.Counter(_wk(t["day"]) for t in TT)
    r = np.array([t["r"] for t in TT]); p = np.array([t["pnl"] for t in TT])
    win = r >= 1.0
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    o.update(wk2=round(100.0 * sum(1 for w in weeks if cw[w] >= 2) / nw, 1), win=round(100.0 * win.mean(), 1),
             be=round(100.0 * np.mean([t["exit"] == "BE" for t in TT]), 1), pos=round(100.0 * (p > 0).mean(), 1),
             avgw=round(float(r[win].mean()), 2) if win.any() else None, exp_r=round(float(r.mean()), 3),
             exp_usd=round(float(p.mean())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None, net=round(float(p.sum())),
             per_month=round(float(p.sum()) / (len(S) / 21)),
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())))
    return o


KEYS = ("n", "tpw", "wk2", "win", "be", "pos", "avgw", "exp_r", "exp_usd", "pf", "net", "per_month", "dd")


# ================================================================================================ grid
DIMS = {"bias": BIASES, "set": ("htf", "all"), "tgt": ("draw", "drawN"), "min_rr": (1.5, 2.0), "cap": (2.0, 3.0, 5.0, None),
        "be": (1.0, 1.5, None), "entry": ("lit", "fvg", "mkt"), "filt": ("live", "loose"), "win": ("kz", "kzpm", "all"),
        "mpd": (1, 2)}


def vkey(v):
    return "|".join(f"{k}={v[k]}" for k in DIMS)


def parse(key):
    v = {}
    for kv in key.split("|"):
        k, x = kv.split("=")
        v[k] = None if x == "None" else (float(x) if k in ("min_rr", "cap", "be") else int(x) if k == "mpd" else x)
    return v


def all_variants():
    out = []
    for vals in itertools.product(*DIMS.values()):
        v = dict(zip(DIMS, vals))
        if v["bias"] in ("fvg",) and v["set"] == "htf":
            pass                             # fvg bias with HTF-level targets: kept (a draw to the FVG side, aimed at levels)
        out.append(v)
    return out


_CC = {}


def _job(group):
    """One (bias, set, tgt, entry) candidate list, every management / filter variant on it."""
    head, rest = group
    key = tuple(head.items())
    if key not in _CC:
        _CC.clear()
        _CC[key] = variant_cands(head)
    C = _CC[key]
    res = []
    for r in rest:
        v = {**head, **r}
        T = run_variant(v, cands=C)
        res.append((vkey(v), {sp: stats(T, sp) for sp in SPANS}))
    return res


def grid(procs=4):
    from multiprocessing import Pool
    data()
    V = all_variants()
    heads = collections.OrderedDict()
    for v in V:
        h = {k: v[k] for k in ("bias", "set", "tgt", "entry")}
        heads.setdefault(tuple(h.items()), []).append({k: v[k] for k in v if k not in h})
    jobs = [(dict(h), rest) for h, rest in heads.items()]
    print(len(V), "variants in", len(jobs), "groups", flush=True)
    t0 = time.time()
    rows = []
    with Pool(procs) as pool:
        for j, res in enumerate(pool.imap_unordered(_job, jobs, chunksize=1)):
            rows += res
            if j % 20 == 0:
                print(f"  {j + 1}/{len(jobs)} groups, {time.time() - t0:.0f}s", flush=True)
    write_grid(rows)
    return rows


GRID = os.path.join(OUTD, "bias_grid.csv.gz")


def write_grid(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["key"] + [f"{sp}.{k}" for sp in SPANS for k in KEYS])
    for key, o in sorted(rows):
        w.writerow([key] + [o[sp].get(k, "") for sp in SPANS for k in KEYS])
    with gzip.open(GRID, "wt", encoding="utf-8") as fh:
        fh.write(buf.getvalue())
    print("grid ->", GRID, os.path.getsize(GRID) // 1024, "KB", flush=True)


def read_grid():
    out = {}
    with gzip.open(GRID, "rt", encoding="utf-8") as fh:
        r = csv.reader(fh)
        hdr = next(r)
        for row in r:
            o = {sp: {} for sp in SPANS}
            for h, x in zip(hdr[1:], row[1:]):
                sp, k = h.split(".", 1)
                o[sp][k] = float(x) if x not in ("", "None") else None
            out[row[0]] = o
    return out


# ================================================================================================ eval path (MFFU)
def units_of(T, src="HQ"):
    """Trades -> eval units (tools/second_mix.py format): risk, tgt, pts per micro (slippage in, before commission), w1
    (worst open pts), and the pre-emption path (pt / po / pw) for LIT priority / the no-hedge guard."""
    D = data()
    B1, B5 = D["B1"], D["B5"]
    out = []
    for t in T:
        d = int(t["dir"])
        B = B1 if t.get("tf") == 1 else B5
        e = float(t["entry_px"]) * d
        q = int(t["qty"])
        pts = (t["pnl"] + COMM_REAL * q) / (lit.PV * q)
        risk = float(t["risk_pts"])
        k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        if t["exit"] == "CUT_T15":
            kx -= 1
        lo = B.l if d == 1 else -B.h
        w1 = min(0.0, float(lo[k0:kx + 1].min()) - e) if kx >= k0 else 0.0
        w1 = max(-(risk + 0.25), min(w1, pts))
        k1 = k0 + 1
        op = (B.o[k1:kx + 1] * d - e) if kx >= k1 else np.zeros(0)
        lw = np.minimum.accumulate(np.r_[min(0.0, float(lo[k0]) - e), lo[k1:kx] - e]) if kx >= k1 else np.zeros(0)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "exit": t["exit"],
                    "risk": risk, "tgt": round(d * (float(t["target_px"]) - float(t["entry_px"])), 4), "pts": round(pts, 4),
                    "w1": round(w1, 4), "legs": [(1.0, round(pts, 4))], "on1": t.get("tf") == 1, "src": src,
                    "pt": B.t[k1:kx + 1].astype(np.int64), "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))})
    return out


EVAL_SPANS = ("H1", "H2", "2025", "2021-24")
EK = ("p10", "f10", "p20", "f20", "pass_med", "n", "tpw", "net", "per_month", "dd", "pf", "b2b")


def _ek(o, extra=()):
    return {k: v for k, v in o.items() if k in EK + tuple(extra)}


def eval_alone50(U, spans=EVAL_SPANS):
    """Alone on a Builder 50K with LIT's two_week sizing (the units run as LIT-like units: the live lit_sizing)."""
    from tools import second_mix as SM
    UL = [{**u, "src": "LIT"} for u in U]
    return {sp: _ek(SM.score_span(UL, "usd500", sp)[0]) for sp in spans}


def eval_withlit50(U, spans=EVAL_SPANS):
    """Next to LIT on ONE Builder 50K: LIT first (a LIT signal flattens an open HQ trade = LIT priority), one position, max
    2 trades a day with a slot kept for LIT, HQ at LIT's own two_week need size."""
    from tools import second_mix as SM
    UU = list(SM.units()["LIT"]) + list(U)
    return {sp: _ek(SM.score_span(UU, "need1.0", sp, pre=True)[0], ("lit_lost", "by_src")) for sp in spans}


def eval_acctb(U, plan="builder25k", spans=EVAL_SPANS):
    """Own account B (25K / 50K) next to LIT's 50K: the plan's two_week need size (engine/account_b.qty), no-hedge guard."""
    from tools import second_mix as SM
    from tools import second_account_b as SAB
    UN = SM.no_hedge(list(U))
    with SAB.Plan(plan) as pl:
        return {sp: _ek(SAB.score(UN, "acctb_need", sp, pl.safe_rule)[0], ("s10", "dead10", "p60", "f60")) for sp in spans}


def lit_eval_refs():
    from tools import second_mix as SM
    UL = list(SM.units()["LIT"])
    return {sp: _ek(SM.score_span(UL, "usd500", sp)[0]) for sp in EVAL_SPANS}


# ================================================================================================ pick
CONS = {"tpw": 2.0, "win": 40.0, "avgw": 1.5, "n": 40}


def ok_cons(o, cons=CONS):
    return (o.get("n") or 0) >= cons["n"] and (o.get("tpw") or 0) >= cons["tpw"] and (o.get("win") or 0) >= cons["win"] \
        and (o.get("avgw") or 0) >= cons["avgw"] and (o.get("net") or 0) > 0


def eval_score(e, sp):
    x = e[sp]
    return x["p10"] - 2.0 * x["f10"] - x["f20"] + x["net"] / 5000.0


def pick(G, span="H1", top=40, cons=CONS):
    """Stage 1 (pick span only): the constraints, ranked by net $ (= expectancy $ x trades). Stage 2: the eval path alone
    on the 50K on the pick span for the top `top`; final = 2-week pass - 2 x 2-week fail - 1-month fail + net / 5000, with
    2-week fails <= LIT's on that span."""
    q = [(k, o) for k, o in G.items() if ok_cons(o[span], cons)]
    q.sort(key=lambda kv: -kv[1][span]["net"])
    print(f"{span}: {len(q)} of {len(G)} variants meet the constraints {cons}", flush=True)
    ref = lit_eval_refs()[span]
    rows = []
    for k, o in q[:top]:
        T = run_variant(parse(k))
        e = eval_alone50(units_of(T), (span,))
        rows.append({"key": k, "stats": o, "eval50": e, "score": round(eval_score(e, span), 2), "f10_ok": e[span]["f10"] <= ref["f10"]})
    rows.sort(key=lambda r: (not r["f10_ok"], -r["score"]))
    return {"span": span, "n_ok": len(q), "n_grid": len(G), "lit_ref_eval": ref, "rows": rows}


def top3(P):
    """The best row, then the best rows with a different bias method (distinct families); filled up with the next rows
    when fewer families qualify. Rows whose 2-week fails exceed LIT's come last (flagged f10_ok False)."""
    out, seen = [], set()
    for r in P["rows"]:
        b = parse(r["key"])["bias"]
        if b in seen:
            continue
        out.append(r); seen.add(b)
        if len(out) == 3:
            return out
    for r in P["rows"]:
        if r not in out and len(out) < 3:
            out.append(r)
    return out


def full_numbers(key):
    """Every span: stats (LIT size rule) + eval paths (alone 50K, with LIT on the 50K, account B 25K)."""
    T = run_variant(parse(key))
    U = units_of(T)
    return {"key": key, "stats": {sp: stats(T, sp) for sp in SPANS}, "eval_alone50": eval_alone50(U),
            "eval_withlit50": eval_withlit50(U), "eval_acctb25": eval_acctb(U, "builder25k")}


def cmd_pick():
    from tools import second_mix as SM
    from tools import second_account_b as SAB
    G = read_grid()
    out = {"constraints": CONS, "h1": pick(G, "H1")}
    # pre-2025 re-pick: the same constraints on 2021-24; relaxed step by step when nothing qualifies (recorded)
    for cons in (CONS, {**CONS, "win": 30.0}, {**CONS, "win": 30.0, "tpw": 1.5}, {**CONS, "win": 25.0, "tpw": 1.5}):
        out["pre2025"] = pick(G, "2021-24", cons=cons)
        out["pre2025"]["constraints"] = cons
        if out["pre2025"]["rows"]:
            break
    out["top3"] = [r["key"] for r in top3(out["h1"])]
    t3 = top3(out["pre2025"])
    out["repick"] = t3[0]["key"] if t3 else None
    out["full"] = {k: full_numbers(k) for k in out["top3"] + ([out["repick"]] if out["repick"] else [])}
    UL = list(SM.units()["LIT"])
    out["lit"] = {"stats": {sp: stats(lit_reference(), sp) for sp in SPANS}, "eval_alone50": lit_eval_refs()}
    with SAB.Plan("builder25k") as pl:
        out["lit"]["eval_alone25"] = {sp: _ek(SAB.score(UL, "acctb_need", sp, pl.safe_rule)[0], ("s10", "dead10")) for sp in EVAL_SPANS}
    json.dump(out, open(os.path.join(OUTD, "bias_picks.json"), "w"), indent=1, default=float)
    return out


# ================================================================================================ study (top 3)
def neighbours(key, G):
    v = parse(key)
    out = {}
    for dim, vals in DIMS.items():
        for x in vals:
            if x == v[dim]:
                continue
            k2 = vkey({**v, dim: x})
            if k2 in G:
                out[f"{dim}={x}"] = {sp: {m: G[k2][sp].get(m) for m in ("n", "tpw", "win", "avgw", "exp_r", "net", "pf")} for sp in SPANS}
    return out


def _sim_simple(B, k0, d, risk, tgt_r, be_r, flat=955):
    """A market trade at bar k0's open + 1 tick: stop risk pts away, target tgt_r R, BE at be_r (entry + 1.25), flat at
    flat (ET minute), stop before target inside a bar. Returns R after $1.90 a micro."""
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    e = float(o_d[k0]) + lit.SLIP
    tg, cur, be = e + tgt_r * risk, e - risk, False
    day = B.day[k0]
    k, x = k0, None
    while k < B.n and B.day[k] == day:
        if B.mod[k] >= flat or B.mod[k] >= 1080:
            x = float(c_d[max(k0, k - 1)]) - lit.SLIP; break
        if lo_d[k] <= cur:
            x = cur - lit.SLIP; break
        if hi_d[k] >= tg:
            x = tg; break
        if be_r is not None and not be and hi_d[k] >= e + be_r * risk:
            cur, be = e + AC.BE_OFF, True
        k += 1
    if x is None:
        x = float(c_d[min(k, B.n) - 1]) - lit.SLIP
    return ((x - e) * lit.PV - COMM_REAL) / (risk * lit.PV)


def placebos(key, n_rep=1000, n_seed=200, k_times=40, seed=7):
    """(1) random bias: the same pipeline with a coin per day for the bias (n_seed seeds); (2) same entry times, direction
    shuffled; (3) same direction, random entry times in the same window on the same day. (2) and (3) use a simple market
    executor (_sim_simple) for the trade AND its placebos, so they compare like with like."""
    D = data()
    v = parse(key)
    T = run_variant(v)
    res = {"random_bias": {}, "shuffle_dir": {}, "random_time": {}}
    real = {sp: stats(T, sp) for sp in SPANS}
    R = collections.defaultdict(list)
    for s_ in range(n_seed):
        Ts = run_variant(v, seed=1000 + s_)
        for sp in SPANS:
            o = stats(Ts, sp)
            R[sp].append((o.get("exp_r") or 0.0, o.get("win") or 0.0, o.get("net") or 0.0, o.get("n")))
    for sp in SPANS:
        a = np.array(R[sp], dtype=float)
        rs = real[sp]
        res["random_bias"][sp] = {"real_exp_r": rs.get("exp_r"), "real_win": rs.get("win"), "real_net": rs.get("net"),
                                  "med_exp_r": round(float(np.median(a[:, 0])), 3), "med_win": round(float(np.median(a[:, 1])), 1),
                                  "med_net": round(float(np.median(a[:, 2]))), "med_n": float(np.median(a[:, 3])),
                                  "p_exp_r": round(float((a[:, 0] >= (rs.get("exp_r") or 0)).mean()), 3),
                                  "p_win": round(float((a[:, 1] >= (rs.get("win") or 0)).mean()), 3),
                                  "p_net": round(float((a[:, 2] >= (rs.get("net") or 0)).mean()), 3)}
    rng = np.random.default_rng(seed)
    wins = WINDOWS[v["win"]]
    rows = []
    for t in T:
        B = D["B1"] if t.get("tf") == 1 else D["B5"]
        k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
        risk = float(t["risk_pts"])
        tgt_r = abs(float(t["target_px"]) - float(t["entry_px"])) / risk
        rr = _sim_simple(B, k0, t["dir"], risk, tgt_r, v["be"])
        ro = _sim_simple(B, k0, -t["dir"], risk, tgt_r, v["be"])
        idx = np.flatnonzero(B.day == B.day[k0])
        idx = np.array([j for j in idx if any(a <= int(B.mod[j]) < b for a, b in wins)], dtype=np.int64)
        if len(idx):
            rt = [_sim_simple(B, int(j), t["dir"], risk, tgt_r, v["be"]) for j in rng.choice(idx, size=min(k_times, len(idx)), replace=False)]
        else:
            rt = [rr]
        rows.append((t["day"], rr, ro, rt))
    for sp, (a, z) in SPANS.items():
        X = [r for r in rows if a <= r[0] <= z]
        if not X:
            continue
        rr_ = np.array([r[1] for r in X]); ro_ = np.array([r[2] for r in X])
        sh = np.array([np.where(rng.random(len(X)) < 0.5, rr_, ro_).mean() for _ in range(n_rep)])
        tm = np.array([np.mean([r[3][rng.integers(len(r[3]))] for r in X]) for _ in range(n_rep)])
        res["shuffle_dir"][sp] = {"simple_exp_r": round(float(rr_.mean()), 3), "simple_win": round(float((rr_ >= 1.0).mean() * 100), 1),
                                  "opposite_exp_r": round(float(ro_.mean()), 3), "placebo_med": round(float(np.median(sh)), 3),
                                  "p": round(float((sh >= rr_.mean()).mean()), 3)}
        res["random_time"][sp] = {"simple_exp_r": round(float(rr_.mean()), 3), "placebo_med": round(float(np.median(tm)), 3),
                                  "placebo_win_med": round(float(np.median([np.mean([r[3][0] >= 1.0 for r in X]) * 100])), 1),
                                  "p": round(float((tm >= rr_.mean()).mean()), 3)}
    return res


def months_and_drop(T):
    m = collections.defaultdict(lambda: [0, 0.0, 0])
    for t in T:
        x = m[t["day"][:7]]
        x[0] += 1; x[1] += t["pnl"]; x[2] += t["r"] >= 1.0
    months = {k: {"n": v[0], "net": round(v[1]), "win": round(100.0 * v[2] / v[0], 1)} for k, v in sorted(m.items())}
    drop = {}
    for sp, (a, z) in list(SPANS.items()) + [("2026", ("2026-01-01", "2026-12-31"))]:
        TT = sorted([t for t in T if a <= t["day"] <= z], key=lambda t: -t["pnl"])
        p = np.array([t["pnl"] for t in TT[5:]]) if len(TT) > 5 else np.zeros(1)
        gl = -p[p < 0].sum()
        drop[sp] = {"net_all": round(sum(t["pnl"] for t in TT)), "best5": round(sum(t["pnl"] for t in TT[:5])),
                    "net_without_best5": round(float(p.sum())), "pf_without_best5": round(float(p[p > 0].sum() / gl), 2) if gl else None}
    return months, drop


def multiple_testing(G):
    """How many H1-qualifiers hold in H2 / 2025 / 2021-24 vs the share among all variants (base rate), and the H1-vs-H2
    rank correlation of expectancy over the whole grid."""
    from scipy.stats import spearmanr
    keys = list(G)
    ok = [k for k in keys if ok_cons(G[k]["H1"])]
    hold = lambda k, sp: (G[k][sp].get("exp_r") or -1) > 0 and (G[k][sp].get("win") or 0) >= CONS["win"]
    pos = lambda k, sp: (G[k][sp].get("net") or 0) > 0
    out = {"n_grid": len(keys), "n_h1_ok": len(ok), "n_2124_ok": sum(1 for k in keys if ok_cons(G[k]["2021-24"]))}
    for sp in ("H2", "2025", "2021-24"):
        out[sp] = {"qualifiers_net_pos": round(100.0 * np.mean([pos(k, sp) for k in ok]), 1) if ok else None,
                   "all_net_pos": round(100.0 * np.mean([pos(k, sp) for k in keys]), 1),
                   "qualifiers_hold": round(100.0 * np.mean([hold(k, sp) for k in ok]), 1) if ok else None,
                   "all_hold": round(100.0 * np.mean([hold(k, sp) for k in keys]), 1)}
    xs = [(G[k]["H1"].get("exp_r"), G[k]["H2"].get("exp_r"), G[k]["2021-24"].get("exp_r"), G[k]["2025"].get("exp_r")) for k in keys
          if (G[k]["H1"].get("n") or 0) >= 20 and (G[k]["H2"].get("n") or 0) >= 10]
    a = np.array([x for x in xs if None not in x], dtype=float)
    out["spearman_exp_r"] = {"h1_h2": round(float(spearmanr(a[:, 0], a[:, 1])[0]), 3),
                             "h1_2021_24": round(float(spearmanr(a[:, 0], a[:, 2])[0]), 3),
                             "2021_24_2025": round(float(spearmanr(a[:, 2], a[:, 3])[0]), 3), "n": len(a)}
    out["by_bias"] = {}
    for b in BIASES:
        kb = [k for k in keys if parse(k)["bias"] == b]
        out["by_bias"][b] = {"n": len(kb), "h1_ok": sum(1 for k in kb if ok_cons(G[k]["H1"])),
                             "median_exp_r": {sp: round(float(np.median([G[k][sp].get("exp_r") or 0 for k in kb])), 3) for sp in SPANS},
                             "median_win": {sp: round(float(np.median([G[k][sp].get("win") or 0 for k in kb])), 1) for sp in SPANS}}
    return out


def lookahead(cuts=10, seed=3):
    """Features (every bias method, target lists, FVG edge) recomputed on a Market built from bars cut right after each
    sampled candidate's entry bar == the full-data features (every candidate of that day up to the cut)."""
    D = data()
    M, C, Fz = D["M"], D["C"], D["Fz"]
    rng = np.random.default_rng(seed)
    pick_ = rng.choice([j for j, z in enumerate(C) if z["day"] >= "2022-01-01"], size=cuts, replace=False)
    bad, n = 0, 0
    for j in sorted(pick_):
        z = C[j]
        cut = int(z["entry_i"]) + 1
        Mc = lit.Market(bars=M.b.slice(0, cut))
        pools = day_pools(Mc, fvg_list(Mc))
        aux = aux_of(Mc)
        same = [q for q, y in enumerate(C) if y["entry_i"] <= z["entry_i"] and y["day"] == z["day"]]
        fc = feats_of(Mc, [C[q] for q in same], pools, aux)
        for q, f in zip(same, fc):
            n += 1
            a = Fz[q]
            dif = {k: (a[k], f[k]) for k in a if a[k] != f[k]}
            if dif:
                bad += 1
                print("  DIFF", C[q]["day"], C[q]["i"], dif, flush=True)
    print(f"lookahead: {n} candidate features on {cuts} cuts, {bad} differ", flush=True)
    return {"cuts": cuts, "checked": n, "differ": bad}


def cmd_study():
    PK = json.load(open(os.path.join(OUTD, "bias_picks.json")))
    G = read_grid()
    out = {"multiple_testing": multiple_testing(G), "lookahead": lookahead(), "picks": {}}
    for k in PK["top3"] + ([PK["repick"]] if PK.get("repick") else []):
        T = run_variant(parse(k))
        mo, dr = months_and_drop(T)
        print("study", k, flush=True)
        out["picks"][k] = {"neighbours": neighbours(k, G), "placebos": placebos(k), "months": mo, "drop_best5": dr}
    json.dump(out, open(os.path.join(OUTD, "bias_study.json"), "w"), indent=1, default=float)
    return out


# ================================================================================================ save
NAMES = ("hq_bias_pick1", "hq_bias_pick2", "hq_bias_pick3")


def common(T, key):
    return [{"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
             "entry": t["entry_px"], "stop": t["stop_px"], "target": t["target_px"],
             "exit": round(float(t["entry_px"]) + t["dir"] * ((t["pnl"] + COMM_REAL * t["qty"]) / (lit.PV * t["qty"])), 2),
             "exit_kind": t["exit"], "r": t["r"], "qty": int(t["qty"]), "pnl_usd": t["pnl"], "setup": key} for t in T]


def cmd_save(statuses=None):
    from tools import runlib as rl
    PK = json.load(open(os.path.join(OUTD, "bias_picks.json")))
    sess = [d for d in F.SESS if d >= "2021-01-01"]
    Q = ("Owner 2026-10-23: a strategy with 2+ trades a week, high-quality setups, high win rate and high payoff - top-down "
         "draw on liquidity (the HTF draw picks the direction and the target, LIT's chain or an FVG pullback enters)")
    todo = [(nm, k) for nm, k in zip(NAMES, PK["top3"])] + ([("hq_bias_repick_pre2025", PK["repick"])] if PK.get("repick") else [])
    for nm, k in todo:
        T = run_variant(parse(k))
        json.dump({"key": k, "params": parse(k), "cost_per_micro": COMM_REAL, "trades": common(T, k)},
                  open(os.path.join(OUTD, nm.replace("hq_bias_", "bias_") + "_trades.json"), "w"), separators=(",", ":"))
        x = PK["full"][k]
        s, e = x["stats"], x["eval_alone50"]
        f = lambda sp: (f"{s[sp]['tpw']}/wk, win {s[sp].get('win')}% (>= +1R), BE {s[sp].get('be')}%, avg winner {s[sp].get('avgw')}R, "
                        f"exp {s[sp].get('exp_r')}R / ${s[sp].get('exp_usd')}, PF {s[sp].get('pf')}, net {s[sp].get('net', 0):+,} "
                        f"(${s[sp].get('per_month', 0):,}/mo), DD {s[sp].get('dd', 0):,}; eval alone 2-wk {e[sp]['p10']}/{e[sp]['f10']}, "
                        f"1-mo {e[sp]['p20']}/{e[sp]['f20']}")
        st = (statuses or {}).get(nm, "info")
        rl.save(nm, f"HQ bias: top-down draw on liquidity ({k})", "bias", Q, params=parse(k),
                sizing={"headline": "LIT size rule ($800 up to 20 pts, max 40)", "eval": "two_week (live lit_sizing)"},
                trades=T, scored=rl.score(T, sess), status=st,
                verdict=f"H1 (pick) {f('H1')}. H2 (check) {f('H2')}. 2025 {f('2025')}. 2021-24 {f('2021-24')}.",
                notes="tools/hq_bias.py; $1.90 a micro + 1 tick; 2026 true 1m, before 5m; research/writeups/hq-bias.md",
                writeup="hq-bias", tags=["hq", "bias", "draw"])
        print("saved", nm, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "feats"
    if cmd == "feats":
        data()
    elif cmd == "grid":
        grid()
    elif cmd == "lookahead":
        lookahead()
    elif cmd == "pick":
        o = cmd_pick()
        for k in o["full"]:
            print(k, json.dumps(o["full"][k], default=float)[:2500], flush=True)
    elif cmd == "study":
        cmd_study()
    elif cmd == "save":
        cmd_save(json.loads(sys.argv[2]) if len(sys.argv) > 2 else None)
