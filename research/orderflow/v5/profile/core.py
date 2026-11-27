"""v5 'profile' family core (rules: research/orderflow/v5/profile/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

80% rule (classic / fast), prior-RTH value-area edge fades (2R / to POC), composite LVN rejection with delta, POC magnet.
Reuses the v5 'levels' loaders, profile(), score(), holm(), verdict() unchanged. Imports nothing that can trade.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("v5pf_levels_core", os.path.join(os.path.dirname(HERE), "levels", "core.py"))
LV = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(LV)

TICK, PV, COMM = LV.TICK, LV.PV, LV.COMM
MKT_TICKS, STOP_SLIP, FLAT_SLIP, LAST = LV.MKT_TICKS, LV.STOP_SLIP, LV.FLAT_SLIP, LV.LAST
load_days, score, holm, verdict, perm_p = LV.load_days, LV.score, LV.holm, LV.verdict, LV.perm_p

VARIANTS = ["P1", "P2", "P3", "P4", "P5", "P6"]
NAMES = {"P1": "80% rule classic (2x30m)", "P2": "80% rule fast (2x5m)", "P3": "prior VA edge fade 2R +abs",
         "P4": "composite LVN reject +delta", "P5": "POC magnet (inside open)", "P6": "prior VA edge fade -> POC +abs"}


def rnd(x):
    return round(x / TICK) * TICK


# ------------------------------------------------------------------------------------------------ profiles
def prior_rth_day(D, day):
    d1 = dt.date.fromisoformat(day)
    for k in range(1, 5):
        s = (d1 - dt.timedelta(days=k)).isoformat()
        if s in D:
            m = D[s].bars["mod"].to_numpy()
            if ((m >= 570) & (m < 960)).sum() >= 40:
                return s
    return None


def _cells(Dy, sel):
    r, px, v = LV._cell_px(Dy)
    keep = sel(Dy.bars["mod"].to_numpy()[r])
    return px[keep], v[keep]


def prior_profile(D, day):
    p = prior_rth_day(D, day)
    if p is None:
        return None
    pr = LV.profile(_cells(D[p], lambda m: (m >= 570) & (m < 960)))
    if pr is None:
        return None
    poc, vah, val, _ = pr
    return {"day": p, "poc": rnd(poc), "vah": rnd(vah), "val": rnd(val)}


def composite_lvns(D, day):
    p = prior_rth_day(D, day)
    if p is None:
        return []
    P, V = [list(x) for x in zip(_cells(D[p], lambda m: (m >= 570) & (m < 960)))]
    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    if prev in D:
        a, b = _cells(D[prev], lambda m: m >= 1080); P.append(a); V.append(b)
    a, b = _cells(D[day], lambda m: m < 570); P.append(a); V.append(b)
    px, v = np.concatenate(P), np.concatenate(V)
    if not len(px) or v.sum() <= 0:
        return []
    bins = np.floor(px).astype(np.int64)
    lo = int(bins.min())
    vol = np.bincount(bins - lo, weights=v)
    n = len(vol)
    s = np.array([vol[max(0, j - 2):min(n, j + 3)].mean() for j in range(n)])
    smax = s.max()
    cand = []
    for j in range(n):
        if s[j] != s[max(0, j - 5):min(n, j + 6)].min() or s[j] > 0.35 * smax:
            continue
        up, dn = s[j + 3:min(n, j + 31)], s[max(0, j - 30):max(0, j - 2)]
        if len(up) and len(dn) and up.max() >= 2 * s[j] and dn.max() >= 2 * s[j]:
            cand.append(j)
    keep = []
    for j in sorted(cand, key=lambda j: (s[j], j)):
        if all(abs(j - k) >= 6 for k in keep):
            keep.append(j)
    return [(f"lvn_{lo + j}", rnd(lo + j + 0.50)) for j in sorted(keep)]


# ------------------------------------------------------------------------------------------------ candidates
def _arr(b):
    return [b[k].to_numpy() for k in ("open", "high", "low", "close", "t", "mod", "delta", "volume")]


def _cand(day, i, t, d, L, stop, tgt, gate, lvl, extra=None):
    x = {"day": day, "i": int(i), "t_sig": int(t), "level": lvl, "L": None if L is None else float(L), "d": int(d),
         "absorbed": bool(gate), "stop": float(stop), "tgt": None if tgt is None else float(tgt)}
    if extra:
        x.update(extra)
    return x


def cands_80(D, day, fast):
    Dy = D[day]
    pp = prior_profile(D, day)
    if pp is None:
        return []
    o, h, l, c, t, m, dl, vol = _arr(Dy.bars)
    rth = [i for i in range(len(m)) if 570 <= m[i] < 960]
    if not rth or m[rth[0]] != 570:
        return []
    vah, val = pp["vah"], pp["val"]
    op = o[rth[0]]
    if op > vah:
        d, edge, far = -1, vah, val
    elif op < val:
        d, edge, far = 1, val, vah
    else:
        return []
    inside = lambda x: val < x < vah  # noqa: E731
    if fast:
        for a, b in zip(rth, rth[1:]):
            if not (575 <= m[b] <= 720):
                continue
            if inside(c[a]) and inside(c[b]):
                win = [a, b]; sig = b; break
        else:
            return []
    else:
        per = {}
        for i in rth:
            per.setdefault((m[i] - 570) // 30, []).append(i)
        sig = None
        for k in sorted(per):
            if k == 0 or (k - 1) not in per or 570 + 30 * k > 750:
                continue
            p0, p1 = per[k - 1], per[k]
            if len(p0) == 6 and len(p1) == 6 and inside(c[p0[-1]]) and inside(c[p1[-1]]):
                win = p0 + p1; sig = p1[-1]; break
        if sig is None:
            return []
    upto = [i for i in rth if i <= sig]
    if (d == -1 and min(l[i] for i in upto) <= far) or (d == 1 and max(h[i] for i in upto) >= far):
        return []
    stop = (max(h[i] for i in win) + TICK) if d == -1 else (min(l[i] for i in win) - TICK)
    gate = sum(dl[i] for i in win) * d > 0
    return [_cand(day, sig, t[sig], d, edge, stop, far, gate, "vah" if d == -1 else "val",
                  {"win_delta": int(sum(dl[i] for i in win))})]


def cands_edge(D, day, to_poc):
    Dy = D[day]
    pp = prior_profile(D, day)
    if pp is None:
        return []
    o, h, l, c, t, m, dl, vol = _arr(Dy.bars)
    used, out = set(), []
    for i in range(len(m)):
        if not (585 <= m[i] <= 900):
            continue
        for nm, L, d in (("vah", pp["vah"], -1), ("val", pp["val"], 1)):
            if nm in used:
                continue
            if (d == -1 and h[i] >= L + TICK and c[i] < L) or (d == 1 and l[i] <= L - TICK and c[i] > L):
                used.add(nm)
                ab, z = LV.absorbed_read(Dy, int(t[i]), d)
                stop = (l[i] - TICK) if d == 1 else (h[i] + TICK)
                out.append(_cand(day, i, t[i], d, L, stop, pp["poc"] if to_poc else None, ab, nm,
                                 {"vz": None if z is None else int(z[0]), "dz": None if z is None else int(z[1])}))
    return out


def cands_lvn(D, day):
    Dy = D[day]
    lv = composite_lvns(D, day)
    if not lv:
        return []
    o, h, l, c, t, m, dl, vol = _arr(Dy.bars)
    used, out = set(), []
    for i in range(len(m)):
        if not (585 <= m[i] <= 900):
            continue
        fired = []
        for nm, L in lv:
            if nm in used:
                continue
            d = LV.fires(o[i], h[i], l[i], c[i], L)
            if d:
                fired.append(((L - l[i]) if d == 1 else (h[i] - L), nm, L, d))
        if not fired:
            continue
        for f in fired:
            used.add(f[1])
        fired.sort()
        _, nm, L, d = fired[0]
        gate = dl[i] * d > 0 and abs(dl[i]) >= 0.10 * vol[i]
        stop = (l[i] - TICK) if d == 1 else (h[i] + TICK)
        out.append(_cand(day, i, t[i], d, L, stop, None, gate, nm, {"bar_delta": int(dl[i]), "bar_vol": int(vol[i])}))
    return out


def cands_magnet(D, day):
    Dy = D[day]
    pp = prior_profile(D, day)
    if pp is None:
        return []
    o, h, l, c, t, m, dl, vol = _arr(Dy.bars)
    idx = {int(m[i]): i for i in range(len(m))}
    if not all(k in idx for k in (570, 575, 580)):
        return []
    a, b, s = idx[570], idx[575], idx[580]
    vah, val, poc = pp["vah"], pp["val"], pp["poc"]
    op, cc = o[a], c[s]
    if not (val < op < vah):
        return []
    if (op - poc) * (cc - poc) <= 0 or abs(cc - poc) < max(8.0, 0.25 * (vah - val)):
        return []
    d = 1 if poc > cc else -1
    win = [a, b, s]
    stop = (min(l[i] for i in win) - TICK) if d == 1 else (max(h[i] for i in win) + TICK)
    gate = sum(dl[i] for i in win) * d > 0
    return [_cand(day, s, t[s], d, None, stop, poc, gate, "poc", {"win_delta": int(sum(dl[i] for i in win))})]


def day_candidates(D, day, vid):
    if vid == "P1":
        return cands_80(D, day, fast=False)
    if vid == "P2":
        return cands_80(D, day, fast=True)
    if vid == "P3":
        return cands_edge(D, day, to_poc=False)
    if vid == "P6":
        return cands_edge(D, day, to_poc=True)
    if vid == "P4":
        return cands_lvn(D, day)
    if vid == "P5":
        return cands_magnet(D, day)
    raise KeyError(vid)


# ------------------------------------------------------------------------------------------------ simulator
def simulate(Dy, cand):
    """E5 (or market when L is None), one target: cand['tgt'] price or 2R. DESIGN 'Trade'."""
    b = Dy.bars
    o, h, l, c, t, m, _, _ = _arr(b)
    d, L, stop, i = cand["d"], cand["L"], cand["stop"], cand["i"]
    j = i + 1
    res = {"fill": None, "how": None, "R": None, "usd": None, "exit_t": None, "why": None}

    def done(how):
        res["how"] = how; cand.update(res); return cand
    if j >= len(b) or int(t[j]) != cand["t_sig"] + 300 or m[j] > LAST:
        return done("no bar")
    if L is None:
        fill, k, stop_only, how = float(o[j]) + d * MKT_TICKS * TICK, j, False, "market+18"
    elif (o[j] - L) * d <= 0:
        fill, k, stop_only, how = float(o[j]), j, False, "marketable"
    elif (d == -1 and h[j] >= L + TICK) or (d == 1 and l[j] <= L - TICK):
        fill, k, stop_only, how = float(L), j, True, "level"
    elif (d == -1 and h[j] >= stop) or (d == 1 and l[j] <= stop):
        return done("none")
    else:
        if j + 1 >= len(b) or int(t[j + 1]) != int(t[j]) + 300 or m[j + 1] > LAST:
            return done("no bar")
        fill, k, stop_only, how = float(o[j + 1]) + d * MKT_TICKS * TICK, j + 1, False, "market+18"
    risk = (fill - stop) * d
    if risk <= 0:
        return done("no risk")
    tgt = cand["tgt"] if cand.get("tgt") is not None else fill + d * 2.0 * risk
    if (tgt - fill) * d <= 0:
        return done("no room")
    ex = why = ext = last = None
    for q in range(k, len(b)):
        if m[q] > LAST or m[q] < 570:
            break
        last = q
        if (d == 1 and l[q] <= stop) or (d == -1 and h[q] >= stop):
            base = o[q] if (q > k and (o[q] - stop) * d < 0) else stop
            ex, why, ext = base - d * STOP_SLIP * TICK, "stop", int(t[q]); break
        if q == k and stop_only:
            continue
        if (d == 1 and h[q] >= tgt + TICK) or (d == -1 and l[q] <= tgt - TICK):
            ex, why, ext = tgt, "target", int(t[q]); break
    if ex is None:
        if last is None:
            return done("no bar")
        ex, why, ext = float(c[last]) - d * FLAT_SLIP * TICK, "flat", int(t[last])
    usd = (ex - fill) * d * PV - COMM
    qn = int(min(40, 500.0 // (risk * PV)))
    res.update(fill=round(fill, 2), how=how, exit=round(float(ex), 2), why=why, exit_t=ext, risk_pts=round(risk, 2),
               R=round(usd / (risk * PV), 4), usd=round(usd, 2), usd500=round(usd * qn, 2) if qn >= 1 else 0.0,
               rr=round((tgt - fill) * d / risk, 2))
    cand.update(res)
    return cand


def run_variant(D, days, vid):
    out = []
    for day in days:
        out += [simulate(D[day], x) for x in day_candidates(D, day, vid)]
    return out


def ungated(cands):
    r = [x for x in cands if x.get("R") is not None]
    if not r:
        return {"n": 0}
    R = np.array([x["R"] for x in r]); U = np.array([x["usd"] for x in r])
    loss = -U[U <= 0].sum()
    return {"n": len(r), "mean_R": round(float(R.mean()), 3), "net_usd": round(float(U.sum()), 0),
            "win_pct": round(100 * float((U > 0).mean()), 1), "pf": round(float(U[U > 0].sum() / loss), 2) if loss > 0 else None}


def table(rows):
    hdr = ("var", "setup", "cand", "gated", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "maxDD", "halves R (old/new)",
           "halves gap", "gap", "p", "Holm", "verdict")
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for vid, s in rows:
        hv = s["halves"]
        lines.append("| " + " | ".join(str(x) for x in (
            vid, NAMES.get(vid, vid), s["candidates"], s["absorbed"], s["trades"], s["per_week"], s["win_pct"], s["mean_R"],
            s["pf"], f"${s['net_usd']:+,.0f}", f"${s['max_dd_usd']:,.0f}",
            f"{hv['older']['mean_R']} / {hv['newer']['mean_R']}", f"{hv['older']['gap_R']} / {hv['newer']['gap_R']}",
            s["gap_R"], s["placebo_p"], s.get("holm_p"), s.get("verdict"))) + " |")
    return "\n".join(lines)
