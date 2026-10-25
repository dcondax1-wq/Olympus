"""ChatGPT's 10 ATLAS breakout templates A01-A10 (dossier 2026-10-24, research/writeups/specs/chatgpt-2026-10-24-ideas.md)
as candidate members of account B (ATLAS, Builder 25K). Research only: nothing here touches second_model.json or account_b.

Data: TradingView CME NQ1! 5m (data/NQ_5m.csv, back-adjusted) + the clean true 1m bars (engine/lit.bars_1m: 2026 only,
on the 5m price basis). Never Yahoo.

Shared rules (as specified; my reading where the dossier is silent is marked "(choice)"):
  * one attempt a day per template = the first VALID signal of the day (a signal with a usable stop); entry at the next bar's
    open + 1 tick; entries until 15:30 ET (entry open < 15:30); flat at the 15:55 bar's open - 1 tick
  * stop 1 tick beyond the structural level (range extreme / mother bar / narrow bar / the latest opposite 5m pivot); stop
    exits 1 tick worse; target = R x the real risk from the fill (P 3R, A1 2R, A2 4R), filled on a touch; a bar that touches
    stop and target counts as the stop (conservative); the fill bar counts for both
  * pivot = strict 2-left / 2-right 5m fractal, known at the close of its 2nd right bar; the most recent opposite one known at
    the signal, within 12 5m bars of the signal bar, same CME day; none -> no trade
  * 1m-close templates (A01, A05, A07, A08, A10) use the true 1m bars on the 208 days that have them (2026); before 2026 they
    run on 5m closes as a PROXY (A01 cannot be built from 5m bars: no trades before 2026). 5m templates (A02, A03, A04, A06,
    A09) are on 5m closes everywhere (choice). Trades are walked on 1m bars where they exist, else 5m.
  * windows (choice): A03 from its freeze time (02:00 / 03:00 / 04:00); every other template in RTH 09:30-15:30
  * level breakouts (A03-A06) need a cross: the previous close (same timeframe) was not already beyond the level (choice)
  * size (spec): q = floor(min($500, today's budget, room to the floor) / (stop x $2 + $1.90 + 1 tick $0.50)), q < 1 -> skip,
    plus the Builder 25K's 20-micro limit. Standalone: today's budget = the 25K's $600 soft daily loss, no floor.
  * never opposite LIT: tools/atlas.no_hedge_real (LIT's live replay trades = run lit_live + its armed setups; HEDGE close)

Account view (25K eval path): the tools/atlas.py / tools/second_account_b.py executor on the Builder 25K with need sizing
(engine/account_b.qty: 50% room, 20 micros, $600 day guard, safe_eval 30% after session 10), max 2 trades a day combined,
one position; the template alone, and ATLAS (EMA + MACD + S/R) + the template vs ATLAS alone.

    python -X utf8 tools/atlas_gpt.py run          # every template x P/A1/A2 -> research/second/atlas_gpt.json + table
    python -X utf8 tools/atlas_gpt.py lookahead    # regenerate every signal on data cut at its signal close
    python -X utf8 tools/atlas_gpt.py save         # rl.save runs atlas_gpt_*
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "atlas_gpt.json")
TICK = 0.25
PV, COMM, RES = 2.0, 1.90, 0.50
MAXQ, DLL, CEIL = 20, 600.0, 500.0
RTH0, ENTRY_END, FLAT = 570, 930, 955
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31")}

# template -> (P, A1, A2) parameter dicts; "R" = target in R
TEMPLATES = {
    "A01": [dict(m=1, buf=1, R=3), dict(m=2, buf=2, R=2), dict(m=3, buf=4, R=4)],
    "A02": [dict(m=5, buf=1, R=3), dict(m=10, buf=2, R=2), dict(m=20, buf=4, R=4)],
    "A03": [dict(fz=120, buf=1, R=3), dict(fz=180, buf=2, R=2), dict(fz=240, buf=4, R=4)],
    "A04": [dict(buf=1, R=3), dict(buf=2, R=2), dict(buf=4, R=4)],
    "A05": [dict(buf=1, R=3), dict(buf=1, R=2), dict(buf=1, R=4)],
    "A06": [dict(buf=1, R=3), dict(buf=1, R=2), dict(buf=1, R=4)],
    "A07": [dict(N=7, M=5, buf=1, R=3), dict(N=4, M=3, buf=2, R=2), dict(N=10, M=8, buf=4, R=4)],
    "A08": [dict(M=15, buf=1, R=3), dict(M=10, buf=1, R=2), dict(M=20, buf=1, R=4)],
    "A09": [dict(N=12, R=3), dict(N=6, R=2), dict(N=24, R=4)],
    "A10": [dict(K=3, k=0.5, M=30, R=3), dict(K=2, k=0.65, M=20, R=2), dict(K=4, k=0.35, M=40, R=4)],
}
NAMES = {"A01": "1-min opening range breakout", "A02": "5-min opening range breakout", "A03": "overnight box breakout",
         "A04": "previous RTH range breakout", "A05": "previous week high/low breakout", "A06": "inside-day breakout",
         "A07": "1m narrow-range bar breakout", "A08": "5m inside-bar breakout", "A09": "5m N-bar range breakout",
         "A10": "symmetrical compression breakout"}
VAR = ("P", "A1", "A2")
ONE_MIN = {"A01", "A05", "A07", "A08", "A10"}


# ================================================================================================ data
class D:
    M = None
    B1 = None
    days = None          # list of per-day dicts
    force5 = False       # resolution check: run 2026 on 5m bars like the earlier years


def load():
    if D.M is not None:
        return
    M = lit.Market()
    B1 = lit.bars_1m(M)
    D.M, D.B1 = M, B1
    full = set(B1.full)
    i1 = collections.defaultdict(list)
    ix = np.flatnonzero(B1.day >= 0)
    starts = np.r_[0, np.flatnonzero(np.diff(B1.day[ix])) + 1]
    for a, z in zip(starts, np.r_[starts[1:], len(ix)]):
        i1[int(B1.day[ix[a]])] = (int(ix[a]), int(ix[z - 1]) + 1)
    out = []
    for di, (lab, s, e) in enumerate(M.days):
        d = {"di": di, "day": str(lab), "s": s, "e": e, "full": di in full and di in i1}
        if d["full"]:
            d["s1"], d["e1"] = i1[di]
        out.append(d)
    # prior RTH range and prior-prior; previous ISO week high / low (complete CME days of that week)
    rth = {}
    for d in out:
        s, e = d["s"], d["e"]
        m = M.mod[s:e]
        k = np.flatnonzero((m >= RTH0) & (m < 960))
        rth[d["di"]] = (float(M.h[s + k].max()), float(M.l[s + k].min())) if len(k) else None
    wk = collections.defaultdict(list)
    for d in out:
        wk[dt.date.fromisoformat(d["day"]).isocalendar()[:2]].append(d)
    wkl = {w: (max(float(M.h[x["s"]:x["e"]].max()) for x in L), min(float(M.l[x["s"]:x["e"]].min()) for x in L)) for w, L in wk.items()}
    wkeys = sorted(wkl)
    for j, d in enumerate(out):
        d["prth"] = rth.get(d["di"] - 1) if j >= 1 else None
        d["pprth"] = rth.get(d["di"] - 2) if j >= 2 else None
        w = dt.date.fromisoformat(d["day"]).isocalendar()[:2]
        k = wkeys.index(w)
        d["pwk"] = wkl[wkeys[k - 1]] if k >= 1 else None
    D.days = out


def frame(d, tf, cut=None):
    """(t, o, h, l, c, mod, secs) of day d on 1m (tf=1, full days only) or 5m; cut = keep only bars CLOSED by that time."""
    if tf == 1:
        B, a, z, sec = D.B1, d["s1"], d["e1"], 60
    else:
        B, a, z, sec = D.M, d["s"], d["e"], 300
    t = B.t[a:z]
    if cut is not None:
        z2 = int(np.searchsorted(t + sec, cut, side="right"))
        sl = slice(a, a + z2)
    else:
        sl = slice(a, z)
    return B.t[sl], B.o[sl], B.h[sl], B.l[sl], B.c[sl], B.mod[sl], sec


def pivots(d, cut=None):
    """Strict 2/2 5m fractals of the day: lists of (bar index in the day, price, known time) for highs and lows."""
    t, o, h, l, c, m, sec = frame(d, 5, cut)
    H, L = [], []
    for j in range(2, len(t) - 2):
        kt = int(t[j + 2]) + sec
        if h[j] > max(h[j - 2], h[j - 1], h[j + 1], h[j + 2]):
            H.append((j, float(h[j]), kt))
        if l[j] < min(l[j - 2], l[j - 1], l[j + 1], l[j + 2]):
            L.append((j, float(l[j]), kt))
    return H, L


def pivot_stop(d, dr, T, cut=None, within=12):
    """Stop for a dir-dr signal closing at T: 1 tick beyond the latest opposite pivot known by T, within `within` 5m bars."""
    t5 = D.M.t[d["s"]:d["e"]]
    jsig = int(np.searchsorted(t5 + 300, T, side="right")) - 1       # the last 5m bar closed by T
    H, L = pivots(d, cut)
    P = L if dr > 0 else H
    best = None
    for j, px, kt in P:
        if kt <= T and j >= jsig - within:
            best = px
    if best is None:
        return None
    return best - TICK if dr > 0 else best + TICK


def tf_sig(name, d):
    if name in ONE_MIN:
        return 1 if (d["full"] and not D.force5) else (None if name == "A01" else 5)
    return 5


# ================================================================================================ the 10 generators
def first_close_beyond(t, c, m, sec, k0, hi, lo, buf, end=ENTRY_END, cross=False, prev_ok=None):
    """First bar k >= k0 whose close is beyond hi + buf / lo - buf with its close time (entry) before `end`."""
    for k in range(k0, len(t)):
        if int(m[k]) >= 1080 or int(m[k]) + sec // 60 >= end:      # out of the window (entry open at the close of k)
            return None
        up, dn = c[k] > hi + buf * TICK, c[k] < lo - buf * TICK
        if cross and k >= 1:
            up = up and not (c[k - 1] > hi + buf * TICK)
            dn = dn and not (c[k - 1] < lo - buf * TICK)
        if up or dn:
            return k, (1 if up else -1)
    return None


def gen(name, p, d, cut=None):
    """The day's one signal: (signal close time T, dir, stop price) or None."""
    tf = tf_sig(name, d)
    if tf is None:
        return None
    t, o, h, l, c, m, sec = frame(d, tf, cut)
    if not len(t):
        return None
    secm = sec // 60
    if name in ("A01", "A02"):
        k_or = np.flatnonzero((m >= RTH0) & (m < RTH0 + p["m"]))
        if not len(k_or) or int(m[k_or[0]]) != RTH0 or int(m[k_or[-1]]) + secm != RTH0 + p["m"]:
            return None
        hi, lo = float(h[k_or].max()), float(l[k_or].min())
        k0 = int(k_or[-1]) + 1
        r = first_close_beyond(t, c, m, sec, k0, hi, lo, p["buf"])
        if r is None:
            return None
        k, dr = r
        return int(t[k]) + sec, dr, (lo - TICK if dr > 0 else hi + TICK)
    if name in ("A03", "A04", "A05", "A06"):
        if name == "A03":
            # the box: every bar from the 18:00 open until the freeze (bars of the CME day before `fz`)
            kb = np.flatnonzero(np.r_[np.cumsum((m < 1080) & (m >= p["fz"])) == 0])
            if not len(kb) or len(kb) >= len(m):
                return None
            hi, lo = float(h[kb].max()), float(l[kb].min())
            k0, w0 = int(kb[-1]) + 1, p["fz"]
        else:
            lv = d["prth"] if name in ("A04", "A06") else d["pwk"]
            if lv is None:
                return None
            if name == "A06":
                if d["pprth"] is None or not (lv[0] < d["pprth"][0] and lv[1] > d["pprth"][1]):
                    return None
            hi, lo = lv
            ks = np.flatnonzero((m >= RTH0) & (m < 1080))
            if not len(ks):
                return None
            k0, w0 = int(ks[0]), RTH0
        for k in range(max(k0, 1), len(t)):
            mk = int(m[k])
            if mk >= 1080 or mk < w0:
                continue
            if mk + secm >= ENTRY_END:
                break
            for dr in (1, -1):
                lvl = hi + p["buf"] * TICK if dr > 0 else -(lo - p["buf"] * TICK)
                if c[k] * dr > lvl and not (c[k - 1] * dr > lvl):
                    T = int(t[k]) + sec
                    st = pivot_stop(d, dr, T, cut)
                    if st is not None:
                        return T, dr, st
        return None
    if name == "A07":
        N, Mw, buf = p["N"], p["M"], p["buf"]
        rg = h - l
        for j in range(N - 1, len(t)):
            if m[j] < RTH0 or m[j] >= 1080:
                continue
            if int(m[j]) + secm >= ENTRY_END:
                break
            if not (rg[j] < rg[j - N + 1:j].min()):
                continue
            for k in range(j + 1, min(j + 1 + Mw, len(t))):
                if int(m[k]) + secm >= ENTRY_END:
                    break
                up, dn = c[k] > h[j] + buf * TICK, c[k] < l[j] - buf * TICK
                if up or dn:
                    dr = 1 if up else -1
                    return int(t[k]) + sec, dr, (float(l[j]) - TICK if dr > 0 else float(h[j]) + TICK)
        return None
    if name == "A08":
        t5, o5, h5, l5, c5, m5, _ = frame(d, 5, cut)
        for j in range(1, len(t5)):
            if m5[j] < RTH0 or m5[j] >= 1080:
                continue
            if int(m5[j]) + 5 >= ENTRY_END:
                break
            if not (h5[j] < h5[j - 1] and l5[j] > l5[j - 1]):
                continue
            mh, ml = float(h5[j - 1]), float(l5[j - 1])
            T0 = int(t5[j]) + 300
            k0 = int(np.searchsorted(t, T0))
            for k in range(k0, len(t)):
                T = int(t[k]) + sec
                if T - T0 > p["M"] * 60 or int(m[k]) + secm >= ENTRY_END:
                    break
                up, dn = c[k] > mh + p["buf"] * TICK, c[k] < ml - p["buf"] * TICK
                if up or dn:
                    dr = 1 if up else -1
                    return T, dr, (ml - TICK if dr > 0 else mh + TICK)
        return None
    if name == "A09":
        N = p["N"]
        for k in range(N, len(t)):
            if m[k] < RTH0 or m[k] >= 1080:
                continue
            if int(m[k]) + secm >= ENTRY_END:
                break
            hh, ll = h[k - N:k].max(), l[k - N:k].min()
            for dr, ok in ((1, c[k] > hh), (-1, c[k] < ll)):
                if ok:
                    T = int(t[k]) + sec
                    st = pivot_stop(d, dr, T, cut)
                    if st is not None:
                        return T, dr, st
        return None
    if name == "A10":
        K, kk, Mw = p["K"], p["k"], p["M"]
        H, L = pivots(d, cut)
        ev = sorted({kt for _, _, kt in H + L})
        t5 = D.M.t[d["s"]:d["e"]]
        m5 = D.M.mod[d["s"]:d["e"]]
        for T0 in ev:
            j0 = int(np.searchsorted(t5 + 300, T0, side="right")) - 1
            if j0 < 0 or m5[j0] < RTH0 - 5 or m5[j0] >= 1080:
                continue
            if et_mod(T0) >= ENTRY_END:
                break
            hs = [x for x in H if x[2] <= T0][-K:]
            ls = [x for x in L if x[2] <= T0][-K:]
            if len(hs) < K or len(ls) < K:
                continue
            if not (all(hs[i][1] > hs[i + 1][1] for i in range(K - 1)) and all(ls[i][1] < ls[i + 1][1] for i in range(K - 1))):
                continue
            w_old, w_new = hs[0][1] - ls[0][1], hs[-1][1] - ls[-1][1]
            if w_old <= 0 or w_new > kk * w_old:
                continue
            ph, pl = hs[-1][1], ls[-1][1]
            k0 = int(np.searchsorted(t + sec, T0, side="right"))
            for k in range(k0, len(t)):
                T = int(t[k]) + sec
                if T - T0 > Mw * 60 or int(m[k]) + secm >= ENTRY_END:
                    break
                up, dn = c[k] > ph + TICK, c[k] < pl - TICK
                if up or dn:
                    dr = 1 if up else -1
                    return T, dr, (pl - TICK if dr > 0 else ph + TICK)
        return None
    raise KeyError(name)


def et_mod(ts):
    from zoneinfo import ZoneInfo
    x = dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))
    return x.hour * 60 + x.minute


# ================================================================================================ trade walk
def walk(d, T, dr, stop, R):
    """Entry at the open of the first bar starting at T (1m on full days, else 5m). Returns a unit or None."""
    tf = 1 if (d["full"] and not D.force5) else 5
    t, o, h, l, c, m, sec = frame(d, tf)
    k0 = int(np.searchsorted(t, T))
    if k0 >= len(t) or int(m[k0]) >= ENTRY_END:
        return None
    hi, lo = (h, l) if dr > 0 else (-l, -h)
    op = o * dr
    e = float(op[k0]) + TICK
    sd = stop * dr
    risk = e - sd
    if risk <= 0:
        return None
    tg = e + R * risk
    ex, kind, kx = None, None, None
    for k in range(k0, len(t)):
        if int(m[k]) >= FLAT and int(m[k]) < 1080:
            ex, kind, kx = float(op[k]) - TICK, "FLAT", k
            break
        if lo[k] <= sd:
            ex, kind, kx = min(sd, float(op[k])) - TICK, "STOP", k
            break
        if hi[k] >= tg:
            ex, kind, kx = tg, "TARGET", k
            break
    if ex is None:
        kx = len(t) - 1
        ex, kind = float(c[kx]) * dr - TICK, "EOD"
    pts = ex - e
    # open path for HEDGE / LIT cuts (tools/second_mix.second_units format): bars after the entry bar up to the exit bar
    a = k0 + 1
    w = float(lo[k0:kx + 1].min()) - e
    w1 = max(-(risk + TICK), min(0.0, w, pts))
    po = (op[a:kx + 1] - e) if kx >= a else np.zeros(0)
    pw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e])[1:] if kx >= a else np.zeros(0)
    xt = int(t[kx]) + (sec if kind in ("STOP", "TARGET", "EOD") else 0)
    return {"day": d["day"], "entry_t": int(t[k0]), "exit_t": xt, "dir": dr, "exit": kind, "risk": round(risk, 4),
            "tgt": round(R * risk, 4), "pts": round(pts, 4), "w1": round(w1, 4), "sig_t": int(T), "stop_px": stop,
            "pt": t[a:kx + 1].astype(np.int64), "po": np.round(po, 2), "pw": np.maximum(np.round(pw, 2), -(risk + TICK)),
            "on1": tf == 1}


def units(name, vi, days=None):
    p = TEMPLATES[name][vi]
    src = f"{name}{VAR[vi]}"
    out = []
    for d in (days or D.days):
        g = gen(name, p, d)
        if g is None:
            continue
        u = walk(d, g[0], g[1], g[2], p["R"])
        if u is not None:
            u["src"] = src
            out.append(u)
    return out


# ================================================================================================ standalone scoring
def spec_q(risk, budget=DLL, room=float("inf")):
    return max(0, min(MAXQ, int(min(CEIL, budget, room) / (risk * PV + COMM + RES))))


def lit_daily():
    run = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    c = run["trade_cols"]
    out = collections.defaultdict(float)
    for r in run["trades"]:
        t = dict(zip(c, r))
        out[t["day"]] += float(t["pnl"])
    return out


def sessions():
    from tools import second_mix as SM
    return SM.units()["sessions"]


def stand(U, span, LD):
    a, z = SPANS[span]
    S = [s for s in sessions() if a <= s <= z]
    T = [u for u in U if a <= u["day"] <= z]
    rows = []
    for u in T:
        q = spec_q(u["risk"])
        if q < 1:
            continue
        rows.append((u["day"], u["pts"] * PV * q - COMM * q, u))
    p = np.array([r[1] for r in rows]) if rows else np.zeros(0)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0.0
    gl = -p[p < 0].sum()
    wk = collections.Counter(dt.date.fromisoformat(r[0]).isocalendar()[:2] for r in rows)
    weeks = sorted({dt.date.fromisoformat(s).isocalendar()[:2] for s in S})
    dp = collections.defaultdict(float)
    for r in rows:
        dp[r[0]] += r[1]
    x = np.array([dp.get(s, 0.0) for s in S])
    y = np.array([LD.get(s, 0.0) for s in S])
    corr = float(np.corrcoef(x, y)[0, 1]) if len(S) > 2 and x.std() > 0 and y.std() > 0 else None
    n = len(rows)
    return {"n": n, "tpw": round(n / (len(S) / 5), 2) if S else 0, "wk2": round(100.0 * sum(1 for w in weeks if wk[w] >= 2) / len(weeks), 1) if weeks else 0,
            "win": round(100.0 * float((p > 0).mean()), 1) if n else None, "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(S) / 21)) if S else 0, "dd": round(dd),
            "avg_r": round(float(np.mean([r[2]["pts"] / r[2]["risk"] for r in rows])), 3) if n else None,
            "med_stop": round(float(np.median([r[2]["risk"] for r in rows])), 2) if n else None,
            "corr_lit": round(corr, 3) if corr is not None else None,
            "exits": dict(collections.Counter(r[2]["exit"] for r in rows))}


def stand_all(U, LD):
    o = {s: stand(U, s, LD) for s in SPANS}
    a = [u for u in U if u["day"] >= "2026-01-01"]
    o["2026"] = stand_span(a, "2026-01-01", "2026-12-31", LD)
    o["all"] = stand_span(U, "2021-01-01", "2026-12-31", LD)
    return o


def stand_span(U, a, z, LD):
    SPANS["_tmp"] = (a, z)
    try:
        return stand(U, "_tmp", LD)
    finally:
        SPANS.pop("_tmp")


# ================================================================================================ account view (25K eval)
def account(U_tpl, src):
    """25K eval path (need sizing): template alone and ATLAS + template (tools/atlas.score)."""
    from tools import atlas as A
    from tools import second_mix as SM
    SM.units()[src] = U_tpl
    alone = A.score(A.V_(members=[src]))
    combo = A.score(A.V_(members=["EMA", "MD", "SR", src]))
    return alone, combo


EV_KEYS = ("p10", "f10", "s10", "dead10", "p20", "f20", "pass_med", "p60", "net", "per_month", "dd", "pf", "tpw", "n", "fund_paid_3m", "ev_eval_3m", "by_src")


def slim(o):
    return {s: {k: o[s].get(k) for k in EV_KEYS} for s in o}


def better(c, b):
    """atlas.md's test in a half: 2-week pass up or equal, dead (fail + stuck) not up, $ up."""
    return c["p10"] >= b["p10"] and c["dead10"] <= b["dead10"] and c["net"] > b["net"]


# ================================================================================================ placebo
def placebo(U, n=300, seed=7):
    """Random entries at the SAME count and times: each trade's entry bar kept, direction random, stop at the same distance,
    the same R target, walked by the same rules. Returns the share of draws whose 2026 / all-years net >= the real one."""
    rng = np.random.default_rng(seed)
    dmap = {d["day"]: d for d in D.days}
    out = {"2026": [], "all": []}
    for _ in range(n):
        tot = {"2026": 0.0, "all": 0.0}
        for u in U:
            dr = int(rng.choice((1, -1)))
            d = dmap[u["day"]]
            tf = 1 if (d["full"] and not D.force5) else 5
            t, o, *_ = frame(d, tf)
            k0 = int(np.searchsorted(t, u["entry_t"]))
            e = float(o[k0]) * dr + TICK
            stop = (e - u["risk"]) * dr
            v = walk(d, u["entry_t"], dr, stop, u["tgt"] / u["risk"])
            if v is None:
                continue
            q = spec_q(v["risk"])
            pnl = v["pts"] * PV * q - COMM * q
            tot["all"] += pnl
            if u["day"] >= "2026-01-01":
                tot["2026"] += pnl
        for k in tot:
            out[k].append(tot[k])
    return {k: np.array(v) for k, v in out.items()}


# ================================================================================================ commands
def nohedge(U):
    from tools import atlas as A
    return A.no_hedge_real(U, True)


def cmd_run(only=None):
    load()
    from tools import atlas as A
    LD = lit_daily()
    base = A.score(A.BASE)
    res = {"base_atlas": slim(base), "templates": {}}
    print("ATLAS alone (25K need):", {s: (base[s]["p10"], base[s]["dead10"], base[s]["net"]) for s in ("H1", "H2")}, flush=True)
    for name in TEMPLATES:
        if only and name not in only:
            continue
        for vi in range(3):
            src = f"{name}{VAR[vi]}"
            U0 = units(name, vi)
            U = nohedge(U0)
            st = stand_all(U, LD)
            al, co = account(U, src)
            rec = {"name": NAMES[name], "params": TEMPLATES[name][vi], "raw_signals": len(U0), "after_lit_rule": len(U),
                   "stand": st, "eval_alone": slim(al), "eval_atlas_plus": slim(co),
                   "beats_atlas": {s: better(co[s], base[s]) for s in ("H1", "H2", "2025", "2021-24")}}
            res["templates"][src] = rec
            f = lambda s: f"{st[s]['n']:3d} {st[s]['net']:+7,} PF {st[s]['pf']}"
            print(f"{src:6s} H1[{f('H1')}] H2[{f('H2')}] 25[{f('2025')}] 21-24[{f('2021-24')}] corr {st['2026']['corr_lit']} | "
                  f"alone 2w H1 {al['H1']['p10']}/{al['H1']['dead10']} H2 {al['H2']['p10']}/{al['H2']['dead10']} | "
                  f"+ATLAS H1 {co['H1']['p10']}/{co['H1']['dead10']} {co['H1']['net']:+,} H2 {co['H2']['p10']}/{co['H2']['dead10']} "
                  f"{co['H2']['net']:+,} beats {rec['beats_atlas']}", flush=True)
            _U[src] = U
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    old = json.load(open(OUT)) if (only and os.path.exists(OUT)) else {}
    if old:
        old["templates"].update(res["templates"])
        res = old
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


_U = {}


def cmd_lookahead(sample=None):
    """Every signal regenerated on the day's data cut at its own signal close (bars closed by then; pivots confirmed by
    then): it must come out identical."""
    load()
    bad, n = [], 0
    for name in TEMPLATES:
        for vi in range(3):
            p = TEMPLATES[name][vi]
            for d in D.days:
                g = gen(name, p, d)
                if g is None:
                    continue
                n += 1
                g2 = gen(name, p, d, cut=g[0])
                if g2 is None or g2[0] != g[0] or g2[1] != g[1] or abs(g2[2] - g[2]) > 1e-9:
                    bad.append((name, vi, d["day"], g, g2))
    print(f"look-ahead check: {n} signals regenerated on cut data, {len(bad)} differ", flush=True)
    for b in bad[:10]:
        print("  DIFF", b)
    return n, bad


def cmd_placebo(keys, n=200):
    """Placebo for the given variant keys (e.g. A02P): real net vs random-direction entries at the same times."""
    load()
    res = json.load(open(OUT))
    out = res.setdefault("placebo", {})
    for key in keys:
        name, vi = key[:3], VAR.index(key[3:])
        U = nohedge(units(name, vi))
        P = placebo(U, n)
        real = {"2026": sum(spec_q(u["risk"]) * (u["pts"] * PV - COMM) for u in U if u["day"] >= "2026-01-01"),
                "all": sum(spec_q(u["risk"]) * (u["pts"] * PV - COMM) for u in U)}
        out[key] = {k: {"real": round(real[k]), "placebo_med": round(float(np.median(P[k]))), "p90": round(float(np.percentile(P[k], 90))),
                        "share_ge_real": round(float((P[k] >= real[k]).mean()), 3)} for k in P}
        print(key, out[key], flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)


def cmd_save():
    from tools import runlib as rl
    load()
    res = json.load(open(OUT))
    sess = [d for d in sessions() if d >= "2021-01-01"]
    keep_index, rl.index = rl.index, (lambda: None)
    Q = "ChatGPT dossier 2026-10-24: do the 10 ATLAS breakout templates (A01-A10) earn a place on account B (Builder 25K)?"
    try:
        for key, rec in res["templates"].items():
            name, vi = key[:3], VAR.index(key[3:])
            U = nohedge(units(name, vi))
            T = []
            for u in U:
                q = spec_q(u["risk"])
                if q < 1:
                    continue
                pnl = round(u["pts"] * PV * q - COMM * q, 2)
                T.append({"day": u["day"], "entry_t": u["entry_t"], "exit_t": u["exit_t"], "dir": u["dir"], "r": round(u["pts"] / u["risk"], 3),
                          "pnl": pnl, "risk_pts": u["risk"], "qty": q, "risk_usd": round(u["risk"] * PV * q, 2), "half": False, "exit": u["exit"],
                          "trigger": key, "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None})
            st, ea, ec = rec["stand"], rec["eval_alone"], rec["eval_atlas_plus"]
            f = lambda s: f"{st[s]['n']} trades, net {st[s]['net']:+,} (${st[s]['per_month']:,}/mo), PF {st[s]['pf']}"
            g = lambda o, s: f"{o[s]['p10']}/{o[s]['dead10']} path {o[s]['net']:+,}"
            verdict = (f"{NAMES[name]} {key} {rec['params']} at the spec size ($500 ceiling incl. costs, 20 micros, never opposite LIT): "
                       f"H1 {f('H1')}; H2 {f('H2')}; 2025 {f('2025')}; 2021-24 {f('2021-24')}. 25K eval (need size) alone 2-week pass/dead "
                       f"H1 {g(ea, 'H1')}, H2 {g(ea, 'H2')}; ATLAS + it H1 {g(ec, 'H1')}, H2 {g(ec, 'H2')} vs ATLAS alone "
                       f"{g(res['base_atlas'], 'H1')} / {g(res['base_atlas'], 'H2')}.")
            rl.save("atlas_gpt_" + key.lower(), f"ATLAS GPT {key}: {NAMES[name]}", "other", Q, params={"template": name, "variant": key[3:], **rec["params"]},
                    sizing={"rule": "spec: floor(min(500, 600 day budget) / (stop x 2 + 1.90 + 0.50)), max 20"}, trades=T,
                    scored=rl.score(T, sess), status="rejected", verdict=verdict,
                    notes="tools/atlas_gpt.py; pre-2026 1m templates run on 5m closes (proxy), A01 has no pre-2026 trades (no 1m data).",
                    writeup="atlas-chatgpt-breakouts", tags=["second", "atlas", "chatgpt", "breakout"])
            print("saved", key, flush=True)
    finally:
        rl.index = keep_index
    rl.index()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        cmd_run(sys.argv[2:] or None)
    elif cmd == "lookahead":
        cmd_lookahead()
    elif cmd == "placebo":
        cmd_placebo(sys.argv[2:])
    elif cmd == "save":
        cmd_save()
