"""v5 'levels' family core (rules: research/orderflow/v5/levels/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

Lane A's absorption read (of_battery.Day.zone, OF1 constants) at more level types: prior-week H/L, Globex VAH/VAL/POC,
naked prior-day POCs, RTH VWAP +/- 1 sd, round 50s. Imports nothing that can trade.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from engine import ofsum  # noqa: E402

ET = ZoneInfo("America/New_York")
TICK, PV, COMM = 0.25, 2.0, 1.90
ZONE, ABS_SHARE = 8, 0.20
RR, MKT_TICKS, STOP_SLIP, FLAT_SLIP = 2.0, 18, 2, 2
MIN_ROWS, GX_MIN_VOL, NP_N = 50_000, 20_000, 5
W0, W1, LAST = 585, 900, 955
N_PERM = 5000
VARIANTS = {
    "L1": ["PW"], "L2": ["GX"], "L3": ["NP"], "L4": ["VW"], "L5": ["RN"], "L6": ["PW", "GX", "NP", "VW", "RN"],
}
NAMES = {"L1": "prior-week H/L", "L2": "Globex VAH/VAL/POC", "L3": "naked prior-day POC", "L4": "VWAP +/-1 sd",
         "L5": "round 00/50", "L6": "all new levels", "V0": "control: lane A levels"}


def _load_battery():
    sp = importlib.util.spec_from_file_location("v5lv_battery", os.path.join(ROOT, "research", "orderflow", "of_battery.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


B = _load_battery()


# ------------------------------------------------------------------------------------------------ data
def day_dirs():
    out = {}
    for base in (os.path.join(ROOT, "data", "pc_days"), os.path.join(ROOT, "logs", "datapipe", "days")):
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                if len(d) == 10 and os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")):
                    out.setdefault(d, os.path.join(base, d))
    return out


def load_days():
    """{day: of_battery.Day} for every file (thin ones too: level history only) + the sorted usable list."""
    D, usable = {}, []
    for d, p in day_dirs().items():
        R = ofsum.read(p)
        if not R or not len(R["bars"]):
            continue
        D[d] = B.Day(d, R)
        if int(R["meta"].get("rows", 0)) >= MIN_ROWS:
            usable.append(d)
    return D, sorted(usable)


_NQ5 = {}


def nq5m():
    if "df" not in _NQ5:
        p = os.path.join(ROOT, "data", "NQ_5m.csv")
        _NQ5["df"] = pd.read_csv(p).sort_values("time").drop_duplicates("time").reset_index(drop=True) if os.path.exists(p) else None
    return _NQ5["df"]


def _et_ts(day: dt.date, hh: int, mm: int = 0) -> int:
    return int(dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=ET).timestamp())


def _cell_px(Dy):
    """footprint cells -> (bar row, price, volume)."""
    f = Dy.fp
    px = Dy.bars.low.to_numpy()[f.bar.to_numpy()] + f.k.to_numpy() * TICK
    return f.bar.to_numpy(), px, (f.a + f.b + f.u).to_numpy(float)


def profile(cells):
    """cells: (price array, volume array) -> (poc_px, vah_px, val_px) on 1-point bins (DESIGN GX)."""
    px, v = cells
    if not len(px) or v.sum() <= 0:
        return None
    bins = np.floor(px).astype(np.int64)
    lo = int(bins.min())
    vol = np.bincount(bins - lo, weights=v)
    poc = int(np.argmax(vol))                                        # argmax = lowest on a tie
    tot, acc, a, b = vol.sum(), vol[poc], poc, poc
    while acc < 0.70 * tot:
        up = vol[b + 1] if b + 1 < len(vol) else -1.0
        dn = vol[a - 1] if a - 1 >= 0 else -1.0
        if up < 0 and dn < 0:
            break
        if up >= dn:
            b += 1; acc += up
        else:
            a -= 1; acc += dn
    return lo + poc + 0.50, lo + b + 0.75, lo + a + 0.00, float(tot)


def gx_levels(D, day):
    """Globex 18:00 previous calendar day file .. 09:30 today."""
    Dy = D[day]
    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    P, V = [], []
    for dd, sel in ((prev, lambda m: m >= 1080), (day, lambda m: m < 570)):
        if dd not in D:
            continue
        X = D[dd]
        r, px, v = _cell_px(X)
        keep = sel(X.bars["mod"].to_numpy()[r])
        P.append(px[keep]); V.append(v[keep])
    if not P:
        return []
    pr = profile((np.concatenate(P), np.concatenate(V)))
    if pr is None or pr[3] < GX_MIN_VOL:
        return []
    poc, vah, val, _ = pr
    return [("gx_vah", vah), ("gx_val", val), ("gx_poc", poc)]


def rth_poc(Dy):
    r, px, v = _cell_px(Dy)
    m = Dy.bars["mod"].to_numpy()[r]
    keep = (m >= 570) & (m < 960)
    pr = profile((px[keep], v[keep]))
    return None if pr is None else pr[0]


def np_levels(D, usable, day):
    """naked RTH POCs of the last NP_N usable days before `day` (newest first)."""
    k = usable.index(day) if day in usable else len([u for u in usable if u < day])
    prior = [u for u in usable[:k]][-NP_N:][::-1]
    out = []
    d1 = dt.date.fromisoformat(day)
    for u in prior:
        poc = rth_poc(D[u])
        if poc is None:
            continue
        ok, touched = True, False
        x = dt.date.fromisoformat(u)
        while x <= d1:
            s = x.isoformat()
            if s not in D:
                if x.weekday() != 5:
                    ok = False; break
                x += dt.timedelta(days=1); continue
            b = D[s].bars
            if s == u:
                b = b[b["mod"] >= 960]
            elif s == day:
                b = b[b["mod"] < 570]
            if len(b) and ((b.low <= poc) & (b.high >= poc)).any():
                touched = True; break
            x += dt.timedelta(days=1)
        if ok and not touched:
            out.append((f"np_{u}", poc))
    return out


def pw_levels(D, day):
    d1 = dt.date.fromisoformat(day)
    mon = d1 - dt.timedelta(days=d1.weekday())
    pmon = mon - dt.timedelta(days=7)
    t_a, t_b = _et_ts(pmon - dt.timedelta(days=1), 18), _et_ts(pmon + dt.timedelta(days=4), 17)
    N = nq5m()
    Dy = D[day]
    if N is not None:
        m = pd.merge(Dy.bars[["t", "open"]], N[["time", "open"]], left_on="t", right_on="time", suffixes=("", "_n"))
        if len(m) >= 20:
            off = float(np.median(m.open - m.open_n))
            w = N[(N.time >= t_a) & (N.time < t_b)]
            if len(w):
                return [("pwh", float(w.high.max()) + off), ("pwl", float(w.low.min()) + off)]
    hs, ls, n = [], [], 0
    for i in range(5):
        s = (pmon + dt.timedelta(days=i)).isoformat()
        if s in D:
            n += 1
    if n < 4:
        return []
    for i in range(-1, 5):
        s = (pmon + dt.timedelta(days=i)).isoformat()
        if s in D:
            b = D[s].bars
            b = b[(b.t >= t_a) & (b.t < t_b)]
            if len(b):
                hs.append(b.high.max()); ls.append(b.low.min())
    return [("pwh", float(max(hs))), ("pwl", float(min(ls)))] if hs else []


def vwap_bands(Dy):
    """{bar row: (vw+1, vw-1)} using RTH bars before that row (anchored 09:30)."""
    r, px, v = _cell_px(Dy)
    mods = Dy.bars["mod"].to_numpy()
    n = len(Dy.bars)
    keep = (mods[r] >= 570) & (mods[r] < 960)
    c = float(Dy.bars.open.iat[0])
    x = px[keep] - c
    V = np.bincount(r[keep], weights=v[keep], minlength=n)
    S1 = np.bincount(r[keep], weights=v[keep] * x, minlength=n)
    S2 = np.bincount(r[keep], weights=v[keep] * x * x, minlength=n)
    cv, c1, c2 = np.cumsum(V), np.cumsum(S1), np.cumsum(S2)
    out = {}
    for i in range(1, n):
        if mods[i] < 575 or cv[i - 1] <= 0:
            continue
        mu = c1[i - 1] / cv[i - 1]
        sd = math.sqrt(max(0.0, c2[i - 1] / cv[i - 1] - mu * mu))
        out[i] = (c + mu + sd, c + mu - sd)
    return out


def v0_levels(D, usable, day, i_bar):
    """lane A's own levels (of_battery.levels with the previous usable day within 4 days) + ORB from 10:00."""
    k = usable.index(day)
    days = [day]
    if k and (dt.date.fromisoformat(day) - dt.date.fromisoformat(usable[k - 1])).days <= 4:
        days = [usable[k - 1], day]
    return B.levels(D, days, len(days) - 1)


# ------------------------------------------------------------------------------------------------ signals
def fires(o, h, l, c, L):
    if o > L and l <= L - TICK and c > L:
        return 1
    if o < L and h >= L + TICK and c < L:
        return -1
    return 0


def absorbed_read(Dy, t, d):
    z = Dy.zone(t, d)
    ab = bool(z is not None and z[0] > 0 and z[1] * d < 0 and abs(z[1]) >= ABS_SHARE * z[0])
    return ab, z


def day_candidates(D, usable, day, types):
    """Every candidate of `day` for a variant (list of level types), DESIGN rules, in bar order."""
    Dy = D[day]
    b = Dy.bars
    mods = b["mod"].to_numpy()
    o, h, l, c, t = (b[k].to_numpy() for k in ("open", "high", "low", "close", "t"))
    static = []
    if "PW" in types:
        static += [("PW", nm, L) for nm, L in pw_levels(D, day)]
    if "GX" in types:
        static += [("GX", nm, L) for nm, L in gx_levels(D, day)]
    if "NP" in types:
        static += [("NP", nm, L) for nm, L in np_levels(D, usable, day)]
    vb = vwap_bands(Dy) if "VW" in types else {}
    used, out = set(), []
    for i in range(len(b)):
        if not (W0 <= mods[i] <= W1):
            continue
        fired = []                                      # (priority, nearness, name, L, d)
        for ty in types:
            pr = types.index(ty)
            if ty == "RN":
                lo50 = math.ceil((l[i] + TICK) / 50.0) * 50.0
                hi50 = math.floor((h[i] - TICK) / 50.0) * 50.0
                L = lo50
                while L <= hi50 + 1e-9:
                    nm = f"rn_{L:.0f}"
                    d = fires(o[i], h[i], l[i], c[i], L)
                    if d and nm not in used:
                        near = (L - l[i]) if d == 1 else (h[i] - L)
                        fired.append((pr, near, 0, nm, L, d))
                    L += 50.0
            elif ty == "VW":
                if i in vb:
                    for j, (nm, L) in enumerate((("vw_p1", vb[i][0]), ("vw_m1", vb[i][1]))):
                        L = round(L / TICK) * TICK
                        d = fires(o[i], h[i], l[i], c[i], L)
                        if d and nm not in used:
                            fired.append((pr, 0.0, j, nm, L, d))
            else:
                for j, (ty2, nm, L) in enumerate([s for s in static if s[0] == ty]):
                    L = round(L / TICK) * TICK
                    d = fires(o[i], h[i], l[i], c[i], L)
                    if d and nm not in used:
                        near = (L - l[i]) if d == 1 else (h[i] - L)
                        fired.append((pr, near if ty in ("RN",) else 0.0, j, nm, L, d))
        if not fired:
            continue
        for f in fired:
            used.add(f[3])
        fired.sort(key=lambda f: (f[0], f[1], f[2]))
        _, _, _, nm, L, d = fired[0]
        ab, z = absorbed_read(Dy, int(t[i]), d)
        out.append({"day": day, "i": i, "t_sig": int(t[i]), "level": nm, "L": float(L), "d": int(d), "absorbed": ab,
                    "vz": None if z is None else int(z[0]), "dz": None if z is None else int(z[1]),
                    "stop": float(l[i] - TICK if d == 1 else h[i] + TICK)})
    return out


def v0_candidates(D, usable, day):
    """control: lane A's level set and its one-sided rule (of_paper.step), same simulator."""
    Dy = D[day]
    b = Dy.bars
    mods = b["mod"].to_numpy()
    L0 = v0_levels(D, usable, day, None)
    rth = [i for i in range(len(b)) if 570 <= mods[i] < 960]
    orb = [i for i in rth if mods[i] < 600]
    used, out = set(), []
    for i in rth:
        if not (W0 <= mods[i] <= W1):
            continue
        LL = list(L0)
        if mods[i] >= 600 and len(orb) == 6:
            LL += [("orh", float(b.high.iloc[orb].max()), 1), ("orl", float(b.low.iloc[orb].min()), -1)]
        for nm, lv, side in LL:
            if nm in used:
                continue
            hh, ll, cc = float(b.high.iat[i]), float(b.low.iat[i]), float(b.close.iat[i])
            if side == 1 and hh >= lv + TICK and cc < lv:
                d = -1
            elif side == -1 and ll <= lv - TICK and cc > lv:
                d = 1
            else:
                continue
            used.add(nm)
            ab, z = absorbed_read(Dy, int(b.t.iat[i]), d)
            out.append({"day": day, "i": i, "t_sig": int(b.t.iat[i]), "level": nm, "L": float(lv), "d": d, "absorbed": ab,
                        "vz": None if z is None else int(z[0]), "dz": None if z is None else int(z[1]),
                        "stop": float(ll - TICK if d == 1 else hh + TICK)})
    return out


# ------------------------------------------------------------------------------------------------ simulator (E5, coarse)
def simulate(Dy, cand):
    """Adds fill / exit / R / usd to the candidate (as if taken). DESIGN 'Trade'."""
    b = Dy.bars
    mods = b["mod"].to_numpy()
    o, h, l, c, t = (b[k].to_numpy() for k in ("open", "high", "low", "close", "t"))
    d, L, stop, i = cand["d"], cand["L"], cand["stop"], cand["i"]
    j = i + 1
    res = {"fill": None, "how": None, "R": None, "usd": None, "exit_t": None, "why": None}
    if j >= len(b) or int(t[j]) != cand["t_sig"] + 300 or mods[j] > LAST:
        res["how"] = "no bar"; cand.update(res); return cand
    if (o[j] - L) * d <= 0:
        fill, k, stop_only, how = float(o[j]), j, False, "marketable"
    elif (d == -1 and h[j] >= L + TICK) or (d == 1 and l[j] <= L - TICK):
        fill, k, stop_only, how = float(L), j, True, "level"
    elif (d == -1 and h[j] >= stop) or (d == 1 and l[j] <= stop):
        res["how"] = "none"; cand.update(res); return cand
    else:
        if j + 1 >= len(b) or int(t[j + 1]) != int(t[j]) + 300 or mods[j + 1] > LAST:
            res["how"] = "no bar"; cand.update(res); return cand
        fill, k, stop_only, how = float(o[j + 1]) + d * MKT_TICKS * TICK, j + 1, False, "market+18"
    risk = (fill - stop) * d
    if risk <= 0:
        res["how"] = "no risk"; cand.update(res); return cand
    tgt = fill + d * RR * risk
    ex, why, ext, last = None, None, None, None
    for m in range(k, len(b)):
        if mods[m] > LAST or mods[m] < 570:
            break
        last = m
        if (d == 1 and l[m] <= stop) or (d == -1 and h[m] >= stop):
            base = o[m] if (m > k and (o[m] - stop) * d < 0) else stop
            ex, why, ext = base - d * STOP_SLIP * TICK, "stop", int(t[m]); break
        if m == k and stop_only:
            continue
        if (d == 1 and h[m] >= tgt + TICK) or (d == -1 and l[m] <= tgt - TICK):
            ex, why, ext = tgt, "target", int(t[m]); break
    if ex is None:
        if last is None:
            res["how"] = "no bar"; cand.update(res); return cand
        ex, why, ext = float(c[last]) - d * FLAT_SLIP * TICK, "flat", int(t[last])
    pts = (ex - fill) * d
    usd = pts * PV - COMM
    q = int(min(40, 500.0 // (risk * PV)))
    res.update(fill=round(fill, 2), how=how, exit=round(float(ex), 2), why=why, exit_t=ext, risk_pts=round(risk, 2),
               R=round(usd / (risk * PV), 4), usd=round(usd, 2), usd500=round(usd * q, 2) if q >= 1 else 0.0)
    cand.update(res)
    return cand


def book(cands):
    """absorbed + resolved, one position at a time (busy rule)."""
    out, last_exit = [], None
    for x in sorted(cands, key=lambda r: (r["t_sig"], r["level"])):
        if not x["absorbed"] or x.get("R") is None:
            continue
        if last_exit is not None and x["t_sig"] + 300 <= last_exit:
            x["busy"] = True
            continue
        out.append(x); last_exit = x["exit_t"]
    return out


def run_variant(D, usable, days, vid):
    cands = []
    for day in days:
        cs = v0_candidates(D, usable, day) if vid == "V0" else day_candidates(D, usable, day, VARIANTS[vid])
        cands += [simulate(D[day], x) for x in cs]
    return cands


# ------------------------------------------------------------------------------------------------ scoring
def perm_p(x, lab, seed=7, n=N_PERM):
    x = np.asarray(x, float); lab = np.asarray(lab, bool)
    if lab.sum() == 0 or (~lab).sum() == 0:
        return None
    obs = x[lab].mean() - x[~lab].mean()
    rng = np.random.default_rng(seed)
    k, N = int(lab.sum()), len(x)
    hits = 0
    for _ in range(n // 500):
        idx = np.argsort(rng.random((500, N)), axis=1)[:, :k]
        s = x[idx].sum(1)
        diff = s / k - (x.sum() - s) / (N - k)
        hits += int((diff >= obs - 1e-12).sum())
    return round((hits + 1) / (n + 1), 4)


def holm(ps):
    """dict id -> p (None kept None) -> Holm-adjusted."""
    items = sorted([(p, k) for k, p in ps.items() if p is not None])
    m = len(items)
    adj, run = {}, 0.0
    for r, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - r) * p))
        adj[k] = round(run, 4)
    return {k: adj.get(k) for k in ps}


def max_dd(usd_by_time):
    cum, peak, dd = 0.0, 0.0, 0.0
    for u in usd_by_time:
        cum += u; peak = max(peak, cum); dd = max(dd, peak - cum)
    return dd


def score(cands, days):
    days = sorted(days)
    k = (len(days) + 1) // 2
    H = {"older": set(days[:k]), "newer": set(days[k:])}
    res = [x for x in cands if x.get("R") is not None]
    bk = book(cands)
    R = np.array([x["R"] for x in bk], float)
    U = np.array([x["usd"] for x in bk], float)
    wins, loss = U[U > 0].sum(), -U[U <= 0].sum()
    out = {"candidates": len(cands), "resolved": len(res), "absorbed": int(sum(x["absorbed"] for x in res)),
           "no_fill": int(sum(1 for x in cands if x.get("how") in ("none", "no risk", "no bar"))),
           "trades": len(bk), "per_week": round(len(bk) / (len(days) / 5.0), 2),
           "win_pct": round(100 * float((U > 0).mean()), 1) if len(U) else None,
           "mean_R": round(float(R.mean()), 3) if len(R) else None,
           "pf": round(float(wins / loss), 2) if loss > 0 else None,
           "net_usd": round(float(U.sum()), 0), "usd500": round(float(sum(x["usd500"] for x in bk)), 0),
           "max_dd_usd": round(max_dd([x["usd"] for x in sorted(bk, key=lambda r: r["exit_t"])]), 0),
           "how": {h: sum(1 for x in bk if x["how"] == h) for h in ("level", "marketable", "market+18")}}
    ra = np.array([x["R"] for x in res], float); la = np.array([x["absorbed"] for x in res], bool)
    out["gap_R"] = round(float(ra[la].mean() - ra[~la].mean()), 3) if la.any() and (~la).any() else None
    out["notabs_mean_R"] = round(float(ra[~la].mean()), 3) if (~la).any() else None
    out["placebo_p"] = perm_p(ra, la)
    hv = {}
    for nm, s in H.items():
        bR = [x["R"] for x in bk if x["day"] in s]
        rr = [(x["R"], x["absorbed"]) for x in res if x["day"] in s]
        a = [r for r, ab in rr if ab]; na = [r for r, ab in rr if not ab]
        hv[nm] = {"trades": len(bR), "mean_R": round(float(np.mean(bR)), 3) if bR else None,
                  "usd": round(float(sum(x["usd"] for x in bk if x["day"] in s)), 0),
                  "gap_R": round(float(np.mean(a) - np.mean(na)), 3) if a and na else None}
    out["halves"] = hv
    return out


def verdict(s, p_holm):
    if s["trades"] < 20:
        return "TOO FEW"
    hv = s["halves"].values()
    both = all((h["mean_R"] or -1) > 0 and (h["gap_R"] or -1) > 0 for h in hv)
    if (s["net_usd"] > 0 and (s["pf"] or 0) >= 1.20 and both and (s["placebo_p"] or 1) < 0.10
            and p_holm is not None and p_holm < 0.10):
        return "YES-candidate"
    if s["net_usd"] > 0 and (s["gap_R"] or -1) > 0 and (s["placebo_p"] or 1) < 0.20:
        return "weak"
    return "NO"


def table(rows):
    hdr = ("var", "levels", "cand", "abs", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "maxDD", "halves R (old/new)",
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
