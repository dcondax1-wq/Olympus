"""Confluence tags on every LIT (Zlarior) and ATLAS trade (2026-11-23). RESEARCH ONLY: paper, no live file, engine/ untouched.

Definitions: research/confluence/PREREG.md (written and committed before any run). Each tag is one yes/no, never tuned.
Scoring reuses tools/setup_grade.py (the same LIT size rule, live two_week eval path, ATLAS 25K eval path + funded 25K Monte
Carlo, the same gates). Write-up: research/writeups/confluences-2026-11-23.md.

    python -X utf8 research/confluence/confluences.py          # ~10-20 min -> research/confluence/results.json
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import setup_grade as SG  # noqa: E402

OUT = os.path.join(ROOT, "research", "confluence", "results.json")
TAGS = ("smt", "htf_pda", "key_sweep", "killzone", "bias", "vol_spike", "vix_hi", "on_tight", "round", "pd_side")
NAMES = {"smt": "ES/NQ SMT divergence at the sweep", "htf_pda": "1h/4h FVG or order block at the entry",
         "key_sweep": "sweep took PDH/PDL, PWH/PWL or Asia/London high-low", "killzone": "killzone (London 02-05, NY AM 08:30-11)",
         "bias": "daily bias agrees (prior day close vs open + 4h trend)", "vol_spike": "volume spike on the CISD / signal bar (>=1.5x 20-bar avg)",
         "vix_hi": "VIX regime: prior close >= 20", "on_tight": "tight overnight (18:00-02:00 range < its 20-day median)",
         "round": "sweep extreme within 5 pts of a 00/50 level", "pd_side": "premium/discount: long below / short above prior day 50%"}
LOOK_SESS = 3
_C = {}


# ================================================================================================ market prep (closed bars only)
def prep():
    if _C:
        return _C
    M = SG.market()
    n = len(M.days)
    t = np.asarray(M.t, np.int64)
    o, h, l, c, v = (np.asarray(a, float) for a in (M.o, M.h, M.l, M.c, M.v))
    mod = np.asarray(M.mod)
    pos = (mod - 1080) % 1440                         # minutes since 18:00 within the session
    dayk = np.asarray(M.day_of)
    # HTF bars: (session k, bucket) -> first/last 5m idx
    htf = {}
    for nm, w in (("1h", 60), ("4h", 240)):
        b = dayk.astype(np.int64) * 100 + pos // w
        ch = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
        st = ch
        en = np.r_[ch[1:] - 1, len(b) - 1]
        bo, bh, bl, bc = o[st], np.maximum.reduceat(h, st), np.minimum.reduceat(l, st), c[en]
        htf[nm] = dict(st=st, en=en, o=bo, h=bh, l=bl, c=bc, k=dayk[st], bid=b)
    # sessions: open / close, 18:00-02:00 range
    s_open = np.array([o[s] for _, s, e in M.days])
    s_close = np.array([c[e - 1] for _, s, e in M.days])
    on_rng = np.full(n, np.nan)
    on_end = np.full(n, -1)
    for k, (_, s, e) in enumerate(M.days):
        seg = np.flatnonzero(pos[s:e] < 480) + s           # 18:00-02:00
        if len(seg) and pos[seg[-1]] >= 475:
            on_rng[k] = h[seg].max() - l[seg].min()
            on_end[k] = seg[-1]
    on_med = np.full(n, np.nan)
    for k in range(20, n):
        w = on_rng[k - 20:k]
        w = w[w == w]
        if len(w) >= 10:
            on_med[k] = float(np.median(w))
    # ES 5m aligned to the NQ 5m index
    es = {}
    with open(SG.ES5, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            p = line.split(",")
            try:
                es[int(float(p[0]))] = (float(p[2]), float(p[3]))
            except (ValueError, IndexError):
                pass
    esh = np.array([es.get(int(x), (np.nan, np.nan))[0] for x in t])
    esl = np.array([es.get(int(x), (np.nan, np.nan))[1] for x in t])
    v20 = np.full(len(v), np.nan)
    cs = np.r_[0.0, np.cumsum(v)]
    v20[20:] = (cs[20:-1] - cs[:-21]) / 20.0
    _C.update(M=M, t=t, o=o, h=h, l=l, c=c, v=v, mod=mod, pos=pos, dayk=dayk, htf=htf, s_open=s_open, s_close=s_close,
              on_rng=on_rng, on_end=on_end, on_med=on_med, esh=esh, esl=esl, v20=v20, vix=SG.vix_pair())
    return _C


# ================================================================================================ the 10 tags (pure-ish)
def smt_tag(xb: int, d: int) -> bool:
    """NQ's extreme over [xb-5, xb] took the 12 bars before; ES did not (long: ES low held). Unknown (no ES) = False."""
    X = prep()
    a, b = xb - 5, xb + 1
    pa, pb = xb - 17, xb - 5
    if pa < 0:
        return False
    if d > 0:
        nq_took = X["l"][a:b].min() < X["l"][pa:pb].min()
        ew, ep = X["esl"][a:b], X["esl"][pa:pb]
        if np.isnan(ew).any() or np.isnan(ep).any():
            return False
        return bool(nq_took and ew.min() > ep.min())
    nq_took = X["h"][a:b].max() > X["h"][pa:pb].max()
    ew, ep = X["esh"][a:b], X["esh"][pa:pb]
    if np.isnan(ew).any() or np.isnan(ep).any():
        return False
    return bool(nq_took and ew.max() < ep.max())


def htf_closed(nm: str, j: int):
    """Indices of HTF bars fully closed at the close of 5m bar j (bars before the one containing j; that one too if j ends it)."""
    H = prep()["htf"][nm]
    q = int(np.searchsorted(H["st"], j, side="right")) - 1   # bar containing j
    last = q if H["en"][q] == j else q - 1
    return H, last


def htf_pda_tag(j: int, d: int, lo: float, hi: float) -> bool:
    """An unfilled same-direction 1h/4h FVG or a 1h order block (prior LOOK_SESS sessions) overlapping [lo, hi]."""
    X = prep()
    k_now = int(X["dayk"][j])
    for nm in ("1h", "4h"):
        H, last = htf_closed(nm, j)
        q0 = last
        while q0 > 0 and H["k"][q0 - 1] >= k_now - LOOK_SESS:
            q0 -= 1
        for q in range(max(q0, 2), last + 1):
            if d > 0 and H["l"][q] > H["h"][q - 2]:
                z0, z1 = H["h"][q - 2], H["l"][q]
                after = X["l"][H["en"][q] + 1:j + 1]
                if (not len(after) or after.min() > z0) and z0 <= hi and z1 >= lo:
                    return True
            if d < 0 and H["h"][q] < H["l"][q - 2]:
                z0, z1 = H["h"][q], H["l"][q - 2]
                after = X["h"][H["en"][q] + 1:j + 1]
                if (not len(after) or after.max() < z1) and z0 <= hi and z1 >= lo:
                    return True
        if nm == "1h":
            for q in range(max(q0, 0), last):
                y = q + 1
                if d > 0 and H["c"][q] < H["o"][q] and H["c"][y] > H["h"][q]:
                    after = X["c"][H["en"][y] + 1:j + 1]
                    if (not len(after) or after.min() >= H["l"][q]) and H["l"][q] <= hi and H["h"][q] >= lo:
                        return True
                if d < 0 and H["c"][q] > H["o"][q] and H["c"][y] < H["l"][q]:
                    after = X["c"][H["en"][y] + 1:j + 1]
                    if (not len(after) or after.max() <= H["h"][q]) and H["l"][q] <= hi and H["h"][q] >= lo:
                        return True
    return False


def bias_tag(j: int, d: int) -> bool:
    X = prep()
    k = int(X["dayk"][j])
    if k < 1:
        return False
    day_ok = (X["s_close"][k - 1] - X["s_open"][k - 1]) * d > 0
    H, last = htf_closed("4h", j)
    if last < 6:
        return False
    return bool(day_ok and (H["c"][last] - H["c"][last - 6]) * d > 0)


def common_tags(j: int, d: int, entry: float, ext: float, ext_bar: int, entry_mod: int) -> dict:
    """Tags every bot shares. entry / ext in real prices."""
    X = prep()
    M = X["M"]
    k = int(X["dayk"][j])
    x = M.ctx[k]
    day = str(M.days[k][0])
    lo, hi = min(entry, ext), max(entry, ext)
    vx = X["vix"].get(day, (None, None))[0]
    pdh, pdl = x.get("pdh"), x.get("pdl")
    mid = 0.5 * (pdh + pdl) if pdh is not None and pdl is not None else None
    onr, onm = X["on_rng"][k], X["on_med"][k]
    return {
        "smt": smt_tag(ext_bar, d),
        "htf_pda": htf_pda_tag(j, d, lo, hi),
        "killzone": bool(120 <= entry_mod < 300 or 510 <= entry_mod < 660),
        "bias": bias_tag(j, d),
        "vol_spike": bool(X["v20"][j] == X["v20"][j] and X["v20"][j] > 0 and X["v"][j] >= 1.5 * X["v20"][j]),
        "vix_hi": bool(vx is not None and vx >= 20.0),
        "on_tight": bool(onr == onr and onm == onm and X["on_end"][k] < j and onr < onm),
        "round": bool(abs(ext - round(ext / 50.0) * 50.0) <= 5.0),
        "pd_side": bool(mid is not None and (entry - mid) * d < 0),
    }


KEY_LIT = {"pdh", "pdl", "pwh", "pwl"}


def lit_tags() -> dict:
    """Every LIT candidate (all setups, so a skip can free the day): key (day, i, dir) -> tags."""
    if "lit" in _C:
        return _C["lit"]
    from tools import lit_final as F
    from tools import lit_edge as E
    M, C = F.market(E.LIVE["ref"], E.LIVE["extra_boxes"])
    prep()
    out = {}
    for z in C:
        d = int(z["dir"])
        ep = min(float(z["ref_d"]), float(z["trig_c"])) * d
        ext = float(z["ext_d"]) * d
        g = common_tags(int(z["i"]), d, ep, ext, int(z["ext_i"]), int(z["mod"]))
        g["key_sweep"] = any(s in KEY_LIT or s.startswith("asia18_") or s.startswith("lon25_") for s in z["swept"])
        out[(str(z["day"]), int(z["i"]), d)] = g
    _C["lit"] = out
    return out


def atlas_tags(U) -> dict:
    X = prep()
    M = X["M"]
    out = {}
    for u in U:
        j = int(np.searchsorted(X["t"], int(u["entry_t"]))) - 1
        if j < 0 or int(X["t"][j]) + 300 != int(u["entry_t"]):
            j = int(np.searchsorted(X["t"], int(u["entry_t"]) - 300, side="right")) - 1
        d = int(u["dir"])
        nx = min(j + 1, M.n - 1)
        entry = float(X["o"][nx])
        a = max(0, j - 5)
        if d > 0:
            xb = a + int(np.argmin(X["l"][a:j + 1]))
            ext = float(X["l"][xb])
        else:
            xb = a + int(np.argmax(X["h"][a:j + 1]))
            ext = float(X["h"][xb])
        g = common_tags(j, d, entry, ext, xb, int(X["mod"][nx]))
        k = int(X["dayk"][j])
        x = M.ctx[k]
        lv = [x.get("pdl"), x.get("pwl")] if d > 0 else [x.get("pdh"), x.get("pwh")]
        for nm in ("asia18", "lon25"):
            bx = x.get(nm)
            if bx and bx[2] < xb - 5:
                lv.append(bx[1] if d > 0 else bx[0])
        g["key_sweep"] = any(L is not None and (ext - L) * d < 0 and (entry - L) * d > 0 for L in lv)
        out[SG.atlas_key(u)] = g
    return out


# ================================================================================================ stats
def stats(R, P):
    R, P = np.asarray(R, float), np.asarray(P, float)
    if not len(R):
        return {"n": 0}
    g, ls = P[P > 0].sum(), -P[P < 0].sum()
    return {"n": int(len(R)), "win": round(100.0 * float((R > 0).mean()), 1), "avg_r": round(float(R.mean()), 3),
            "pf": round(float(g / ls), 2) if ls > 0 else None, "usd": round(float(P.sum()))}


def welch_p(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or len(b) < 3:
        return None
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = math.sqrt(va + vb)
    if se == 0:
        return None
    z = (a.mean() - b.mean()) / se
    return float(math.erfc(abs(z) / math.sqrt(2)))      # two-sided, normal approx (n is large enough in the pooled spans)


def holm(ps):
    idx = sorted((p, i) for i, p in enumerate(ps) if p is not None)
    m = len(idx)
    out = [None] * len(ps)
    run = 0.0
    for r, (p, i) in enumerate(idx):
        run = max(run, min(1.0, (m - r) * p))
        out[i] = round(run, 4)
    return out


def bh(ps):
    idx = sorted((p, i) for i, p in enumerate(ps) if p is not None)
    m = len(idx)
    out = [None] * len(ps)
    prev = 1.0
    for r in range(m - 1, -1, -1):
        p, i = idx[r]
        prev = min(prev, p * m / (r + 1))
        out[i] = round(prev, 4)
    return out


# ================================================================================================ the run
def span3(day):
    if "2026-01-01" <= day <= "2026-06-30":
        return "H1"
    if day >= "2026-07-01":
        return "H2"
    if "2021-01-01" <= day <= "2025-12-31":
        return "2021-25"
    return ""


def lit_part(res, log=print, n_pl=100):
    from tools import lit_edge as E
    t0 = time.time()
    LT = lit_tags()
    log(f"LIT tags for {len(LT)} candidates in {time.time() - t0:.0f}s")
    o0, U0, L0, T0 = SG.lit_score(fund=False)
    s0 = SG.lit_short(o0)
    kt = {int(t["entry_t"]): (str(t["day"]), int(t["i"]), int(t["dir"])) for t in T0}
    Lb = {int(l["entry_t"]): l for l in L0}
    rows = [(span3(t["day"]), LT[kt[int(t["entry_t"])]], float(Lb[int(t["entry_t"])]["r"]), float(Lb[int(t["entry_t"])]["pnl"]))
            for t in T0]
    rows = [r for r in rows if r[0]]
    out = {"base": s0, "split": {}, "uses": {}, "rates": {}}
    for g in TAGS:
        sp = {}
        for s in ("H1", "H2", "2021-25"):
            X = [r for r in rows if r[0] == s]
            a = [r for r in X if r[1][g]]
            b = [r for r in X if not r[1][g]]
            sp[s] = {"tagged": stats([r[2] for r in a], [r[3] for r in a]), "untagged": stats([r[2] for r in b], [r[3] for r in b])}
        a26 = [r[2] for r in rows if r[0] in ("H1", "H2") and r[1][g]]
        b26 = [r[2] for r in rows if r[0] in ("H1", "H2") and not r[1][g]]
        aR = [r[2] for r in rows if r[0] == "2021-25" and r[1][g]]
        bR = [r[2] for r in rows if r[0] == "2021-25" and not r[1][g]]
        sp["p_2026"] = welch_p(a26, b26)
        sp["p_2021_25"] = welch_p(aR, bR)
        sp["consistent"] = all(sp[s]["tagged"].get("avg_r") is not None and sp[s]["untagged"].get("avg_r") is not None
                               and sp[s]["tagged"]["avg_r"] > sp[s]["untagged"]["avg_r"] for s in ("H1", "H2", "2021-25"))
        out["split"][g] = sp
        log(f"LIT {g:10s} " + " | ".join(f"{s} {sp[s]['tagged'].get('n')}:{sp[s]['tagged'].get('avg_r')} vs {sp[s]['untagged'].get('n')}:{sp[s]['untagged'].get('avg_r')}"
                                         for s in ("H1", "H2", "2021-25")) + f" p26 {sp['p_2026']} pR {sp['p_2021_25']}")
    # uses
    def score(nm, skip=None, mult=None):
        try:
            o, U, L, T = SG.lit_score(skip=skip, mult=mult, fund=False)
        except ValueError as ex:                  # a span with no trade at all (e.g. VIX >= 20 never in Jul-Oct)
            out["uses"][nm] = {"s": None, "ok": False, "why": f"a span has no trades ({ex})"}
            log(f"{nm}: a span has no trades -> fail")
            return None, None
        s = SG.lit_short(o, o0)
        ok, why = SG.lit_gate(s, s0)
        out["uses"][nm] = {"s": s, "ok": ok, "why": why}
        log(E.line(nm, s) + f" | ref {s['eval_ref']['net']:+,} | {'PASS' if ok else 'no'}: {why[:140]}")
        return o, s
    for g in TAGS:
        score(f"skip_untagged:{g}", skip={k for k, v in LT.items() if not v[g]})
    cnt = {k: sum(v[g] for g in TAGS) for k, v in LT.items()}
    mult = {k: 1.5 for k, n in cnt.items() if n >= 2}
    out["rates"]["count2_share_traded"] = {s: round(100.0 * np.mean([cnt[kt[int(t['entry_t'])]] >= 2 for t in T0 if span3(t['day']) == s]), 1)
                                           for s in ("H1", "H2", "2021-25")}
    out["rates"]["count_dist_traded"] = dict(collections.Counter(cnt[kt[int(t["entry_t"])]] for t in T0))
    out["rates"]["tag_share_traded"] = {g: {s: round(100.0 * np.mean([LT[kt[int(t['entry_t'])]][g] for t in T0 if span3(t['day']) == s]), 1)
                                            for s in ("H1", "H2", "2021-25")} for g in TAGS}
    o_b, s_b = score("size_x1.5_on_2plus", mult=mult)
    # leverage / luck control: x1.5 on as many random traded setups per span
    rng = np.random.default_rng(23)
    keys = collections.defaultdict(list)
    for t in T0:
        if span3(t["day"]):
            keys[span3(t["day"])].append(kt[int(t["entry_t"])])
    nup = {s: sum(cnt[k] >= 2 for k in ks) for s, ks in keys.items()}
    beat = collections.Counter()
    t1 = time.time()
    for _ in range(n_pl):
        m = {}
        for s, ks in keys.items():
            ix = rng.permutation(len(ks))[:nup[s]]
            m.update({ks[i]: 1.5 for i in ix})
        o, U, L, T = SG.lit_score(mult=m, fund=False, ref_eval=False)
        for s in ("H1", "H2", "2021-25"):
            if o["lit"][s]["net"] >= o_b["lit"][s]["net"]:
                beat["lit:" + s] += 1
        for s in ("H1", "H2"):
            if o["eval"][s]["net"] >= o_b["eval"][s]["net"]:
                beat["eval:" + s] += 1
    out["uses"]["size_x1.5_on_2plus"]["luck_p"] = {k: round((beat[k] + 1) / (n_pl + 1), 3)
                                                   for k in ("lit:H1", "lit:H2", "lit:2021-25", "eval:H1", "eval:H2")}
    log(f"LIT size luck p {out['uses']['size_x1.5_on_2plus']['luck_p']} ({time.time() - t1:.0f}s)")
    # flat x1.5 on everything (pure leverage reference)
    score("control_x1.5_all", mult={k: 1.5 for k in LT})
    res["lit"] = out


def atlas_part(res, log=print, n_pl=30):
    from tools import atlas_deep as D
    X = SG.atlas_ctx()
    t0 = time.time()
    AT = atlas_tags(X["U"])
    log(f"ATLAS tags for {len(AT)} candidates in {time.time() - t0:.0f}s")
    r0, T0 = SG.atlas_score({})
    b0 = SG.atlas_short(r0)
    rows = [(span3(t["day"]), AT[SG.atlas_key(t)], float(D.r_net(t)), SG.atlas_fixed_pnl(t)) for t in T0]
    rows = [r for r in rows if r[0]]
    out = {"base": b0, "split": {}, "uses": {}, "rates": {}}
    for g in TAGS:
        sp = {}
        for s in ("H1", "H2", "2021-25"):
            Y = [r for r in rows if r[0] == s]
            a = [r for r in Y if r[1][g]]
            b = [r for r in Y if not r[1][g]]
            sp[s] = {"tagged": stats([r[2] for r in a], [r[3] for r in a]), "untagged": stats([r[2] for r in b], [r[3] for r in b])}
        sp["p_2026"] = welch_p([r[2] for r in rows if r[0] in ("H1", "H2") and r[1][g]], [r[2] for r in rows if r[0] in ("H1", "H2") and not r[1][g]])
        sp["p_2021_25"] = welch_p([r[2] for r in rows if r[0] == "2021-25" and r[1][g]], [r[2] for r in rows if r[0] == "2021-25" and not r[1][g]])
        sp["consistent"] = all(sp[s]["tagged"].get("avg_r") is not None and sp[s]["untagged"].get("avg_r") is not None
                               and sp[s]["tagged"]["avg_r"] > sp[s]["untagged"]["avg_r"] for s in ("H1", "H2", "2021-25"))
        out["split"][g] = sp
        log(f"ATL {g:10s} " + " | ".join(f"{s} {sp[s]['tagged'].get('n')}:{sp[s]['tagged'].get('avg_r')} vs {sp[s]['untagged'].get('n')}:{sp[s]['untagged'].get('avg_r')}"
                                         for s in ("H1", "H2", "2021-25")) + f" p26 {sp['p_2026']} pR {sp['p_2021_25']}")

    def score(nm, mult):
        try:
            r, T = SG.atlas_score(mult, name="cf_" + nm.replace(":", "_"))
        except (ValueError, ZeroDivisionError, KeyError) as ex:
            out["uses"][nm] = {"s": None, "ok": False, "why": f"a span has no trades ({ex})"}
            log(f"ATLAS {nm}: a span has no trades -> fail")
            return None, None
        b = SG.atlas_short(r)
        ok, why = SG.atlas_gate(r, r0)
        fx = {s: stats([float(D.r_net(t)) * float(t.get("w", 1.0)) for t in T if span3(t["day"]) == s],
                       [SG.atlas_fixed_pnl(t) for t in T if span3(t["day"]) == s]) for s in ("H1", "H2", "2021-25")}
        out["uses"][nm] = {"s": b, "ok": ok, "why": why, "fixed3": fx}
        log(f"ATLAS {nm:24s} " + SG.aline(b)[:300] + f" | {'PASS' if ok else 'no'}: {why[:140]}")
        return r, b
    for g in TAGS:
        score(f"skip_untagged:{g}", {k: 0.0 for k, v in AT.items() if not v[g]})
    cnt = {k: sum(v[g] for g in TAGS) for k, v in AT.items()}
    out["rates"]["count2_share_traded"] = {s: round(100.0 * np.mean([cnt[SG.atlas_key(t)] >= 2 for t in T0 if span3(t['day']) == s]), 1)
                                           for s in ("H1", "H2", "2021-25")}
    out["rates"]["tag_share_traded"] = {g: {s: round(100.0 * np.mean([AT[SG.atlas_key(t)][g] for t in T0 if span3(t['day']) == s]), 1)
                                            for s in ("H1", "H2", "2021-25")} for g in TAGS}
    rb, bb = score("size_x1.5_on_2plus", {k: 1.5 for k, n in cnt.items() if n >= 2})
    rng = np.random.default_rng(23)
    pools = collections.defaultdict(list)
    for u in X["U"]:
        if span3(u["day"]):
            pools[span3(u["day"])].append(SG.atlas_key(u))
    nup = {s: sum(cnt[k] >= 2 for k in ks) for s, ks in pools.items()}
    from tools import atlas_v2 as V2
    MO = V2.MONEY
    beat = collections.Counter()
    for jx in range(n_pl):
        m = {}
        for s, ks in pools.items():
            ix = rng.permutation(len(ks))[:nup[s]]
            m.update({ks[i]: 1.5 for i in ix})
        r, T = SG.atlas_score(m, name=f"cf_pl{jx}")
        for s in ("H1", "H2"):
            if r["eval"][s][MO] >= rb["eval"][s][MO]:
                beat["eval:" + s] += 1
        if r["eval"]["2025"][MO] + r["eval"]["2021-24"][MO] >= rb["eval"]["2025"][MO] + rb["eval"]["2021-24"][MO]:
            beat["eval:2021-25"] += 1
        fx = {s: sum(SG.atlas_fixed_pnl(t) for t in T if span3(t["day"]) == s) for s in ("H1", "H2", "2021-25")}
        for s in fx:
            if fx[s] >= out["uses"]["size_x1.5_on_2plus"]["fixed3"][s]["usd"]:
                beat["fixed:" + s] += 1
    out["uses"]["size_x1.5_on_2plus"]["luck_p"] = {k: round((beat[k] + 1) / (n_pl + 1), 3) for k in
                                                   ("eval:H1", "eval:H2", "eval:2021-25", "fixed:H1", "fixed:H2", "fixed:2021-25")}
    log(f"ATLAS size luck p {out['uses']['size_x1.5_on_2plus']['luck_p']}")
    score("control_x1.5_all", {k: 1.5 for k in AT})
    res["atlas"] = out


def corrections(res):
    keys, ps26, psR = [], [], []
    for bot in ("lit", "atlas"):
        for g in TAGS:
            sp = res[bot]["split"][g]
            keys.append((bot, g))
            ps26.append(sp["p_2026"])
            psR.append(sp["p_2021_25"])
    h26, b26, hR, bR = holm(ps26), bh(ps26), holm(psR), bh(psR)
    for i, (bot, g) in enumerate(keys):
        res[bot]["split"][g].update(holm_2026=h26[i], bh_2026=b26[i], holm_2021_25=hR[i], bh_2021_25=bR[i])
    res["n_tests"] = len(keys)


def main():
    t0 = time.time()
    SG.setup()
    res = {"date": "2026-11-23", "tags": NAMES, "prereg": "research/confluence/PREREG.md"}
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if os.path.exists(OUT) and only:
        res = json.load(open(OUT, encoding="utf-8"))
    if only in (None, "lit"):
        lit_part(res)
    if only in (None, "atlas"):
        atlas_part(res)
    if "lit" in res and "atlas" in res:
        corrections(res)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=SG._j)
    print(f"wrote {os.path.relpath(OUT, ROOT)} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
