"""v5 'sessions' family core (rules: research/orderflow/v5/sessions/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

Lane A's absorbed level fade split by session window (London 02:00-05:00, NY open, NY midday, NY PM) and first-touch-only vs
any-touch. Imports nothing that can trade (engine.ofsum is a pure reader; of_battery is research).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from engine import ofsum  # noqa: E402

TICK, PV, COMM = 0.25, 2.0, 1.90
ABS_SHARE = 0.20
RR, MKT_TICKS, STOP_SLIP, FLAT_SLIP = 2.0, 18, 2, 2
MIN_ROWS = 50_000
N_PERM = 5000

# window id -> (first signal-bar open mod, last signal-bar open mod, flat bar open mod, level set)
NYSET = ("pdh", "pdl", "onh", "onl", "orh", "orl")
WINDOWS = {
    "LON": (120, 295, 565, ("pdh", "pdl", "ash", "asl")),
    "NYO": (570, 625, 955, NYSET),
    "MID": (630, 805, 955, NYSET),
    "PM": (810, 925, 955, NYSET),
}
ORDER = ("pdh", "pdl", "onh", "onl", "orh", "orl", "ash", "asl")
SIDE = {"pdh": 1, "onh": 1, "orh": 1, "ash": 1, "pdl": -1, "onl": -1, "orl": -1, "asl": -1}   # +1 = high-type (fade short)
KNOWN = {"onh": 570, "onl": 570, "orh": 600, "orl": 600, "ash": 120, "asl": 120, "pdh": 0, "pdl": 0}
ALLW = ("LON", "NYO", "MID", "PM")
VARIANTS = {"S1": (("LON",), "WIN"), "S2": (("NYO",), "WIN"), "S3": (("MID",), "WIN"), "S4": (("PM",), "WIN"),
            "S5": (ALLW, "FT"), "S6": (ALLW, "ANY")}
NAMES = {"S1": "London 02-05, per-window 1st rejection", "S2": "NY open 09:30-10:30, per-window", "S3": "NY midday 10:30-13:30, per-window",
         "S4": "NY PM 13:30-15:30, per-window", "S5": "all windows, FIRST TOUCH only", "S6": "all windows, ANY touch",
         "V0": "control: lane A exactly", "SW": "descriptive: S1-S4 pooled (WIN all windows)"}


def _load_battery():
    sp = importlib.util.spec_from_file_location("v5ss_battery", os.path.join(ROOT, "research", "orderflow", "of_battery.py"))
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
    """{day: of_battery.Day} for every file (thin ones = level history only) + the sorted usable list."""
    D, usable = {}, []
    for d, p in day_dirs().items():
        R = ofsum.read(p)
        if not R or not len(R["bars"]):
            continue
        D[d] = B.Day(d, R)
        if int(R["meta"].get("rows", 0)) >= MIN_ROWS:
            usable.append(d)
    return D, sorted(usable)


def _prev_usable(usable, day):
    prior = [u for u in usable if u < day]
    if prior and (dt.date.fromisoformat(day) - dt.date.fromisoformat(prior[-1])).days <= 4:
        return prior[-1]
    return None


def _prev_cal(day):
    return (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()


def day_levels(D, usable, day):
    """name -> price (DESIGN 'Levels')."""
    Dy = D[day]
    b = Dy.bars
    m = b["mod"].to_numpy()
    out = {}
    pu = _prev_usable(usable, day)
    if pu:
        pb = D[pu].bars
        pr = pb[(pb["mod"] >= 570) & (pb["mod"] < 960)]
        if len(pr):
            out["pdh"], out["pdl"] = float(pr.high.max()), float(pr.low.min())
    pc = _prev_cal(day)
    eve = D[pc].bars[D[pc].bars["mod"] >= 1080] if pc in D else b.iloc[0:0]
    for hi, lo, cut in (("onh", "onl", 570), ("ash", "asl", 120)):
        seg = list(eve.high) + list(b.high[m < cut]), list(eve.low) + list(b.low[m < cut])
        if seg[0]:
            out[hi], out[lo] = float(max(seg[0])), float(min(seg[1]))
    orb = b[(m >= 570) & (m < 600)]
    if len(orb) == 6:
        out["orh"], out["orl"] = float(orb.high.max()), float(orb.low.min())
    return out


def _touched_before(D, usable, day, L, side):
    """pdh/pdl: touched from the previous usable day's 16:00 bar up to today's 00:00 (files in between included)?"""
    pu = _prev_usable(usable, day)
    if not pu:
        return True
    x = dt.date.fromisoformat(pu)
    end = dt.date.fromisoformat(day)
    while x < end:
        s = x.isoformat()
        if s in D:
            bb = D[s].bars
            if s == pu:
                bb = bb[bb["mod"] >= 960]
            if len(bb) and ((bb.high >= L).any() if side == 1 else (bb.low <= L).any()):
                return True
        x += dt.timedelta(days=1)
    return False


def window_of(mod, windows):
    for w in windows:
        a, z, _, _ = WINDOWS[w]
        if a <= mod <= z:
            return w
    return None


def absorbed_read(Dy, t, d):
    z = Dy.zone(t, d)
    ab = bool(z is not None and z[0] > 0 and z[1] * d < 0 and abs(z[1]) >= ABS_SHARE * z[0])
    return ab, z


def _cand(Dy, i, nm, L, d, w, flat):
    b = Dy.bars
    ab, z = absorbed_read(Dy, int(b.t.iat[i]), d)
    hh, ll = float(b.high.iat[i]), float(b.low.iat[i])
    return {"day": Dy.day, "i": i, "t_sig": int(b.t.iat[i]), "level": nm, "L": float(L), "d": int(d), "win": w, "flat": flat,
            "absorbed": ab, "vz": None if z is None else int(z[0]), "dz": None if z is None else int(z[1]),
            "stop": float(ll - TICK if d == 1 else hh + TICK)}


def day_candidates(D, usable, day, windows, mode):
    Dy = D[day]
    b = Dy.bars
    mods = b["mod"].to_numpy()
    h, l, c = (b[k].to_numpy() for k in ("high", "low", "close"))
    lv = day_levels(D, usable, day)
    first = {}
    if mode == "FT":
        for nm, L in lv.items():
            sd = SIDE[nm]
            if nm in ("pdh", "pdl") and _touched_before(D, usable, day, L, sd):
                first[nm] = None; continue
            idx = [i for i in range(len(b)) if mods[i] >= KNOWN[nm] and (h[i] >= L if sd == 1 else l[i] <= L)]
            first[nm] = idx[0] if idx else None
    used, out = set(), []
    for i in range(len(b)):
        w = window_of(mods[i], windows)
        if w is None:
            continue
        fired = []
        for nm in ORDER:
            if nm not in WINDOWS[w][3] or nm not in lv or mods[i] < KNOWN[nm]:
                continue
            L, sd = lv[nm], SIDE[nm]
            if sd == 1 and h[i] >= L + TICK and c[i] < L:
                d = -1
            elif sd == -1 and l[i] <= L - TICK and c[i] > L:
                d = 1
            else:
                continue
            if mode == "WIN" and (w, nm) in used:
                continue
            if mode == "FT" and first.get(nm) != i:
                continue
            fired.append((nm, L, d))
        if not fired:
            continue
        for f in fired:
            used.add((w, f[0]))
        nm, L, d = fired[0]
        out.append(_cand(Dy, i, nm, L, d, w, WINDOWS[w][2]))
    return out


def v0_candidates(D, usable, day):
    """control: lane A exactly (of_battery.levels with the previous usable day + ORB from 10:00, 09:45-15:00, one per level)."""
    Dy = D[day]
    b = Dy.bars
    mods = b["mod"].to_numpy()
    k = usable.index(day)
    days = [day]
    if k and (dt.date.fromisoformat(day) - dt.date.fromisoformat(usable[k - 1])).days <= 4:
        days = [usable[k - 1], day]
    L0 = B.levels(D, days, len(days) - 1)
    rth = [i for i in range(len(b)) if 570 <= mods[i] < 960]
    orb = [i for i in rth if mods[i] < 600]
    used, out = set(), []
    for i in rth:
        if not (585 <= mods[i] <= 900):
            continue
        LL = list(L0)
        if mods[i] >= 600 and len(orb) == 6:
            LL += [("orh", float(b.high.iloc[orb].max()), 1), ("orl", float(b.low.iloc[orb].min()), -1)]
        for nm, lvp, side in LL:
            if nm in used:
                continue
            hh, ll, cc = float(b.high.iat[i]), float(b.low.iat[i]), float(b.close.iat[i])
            if side == 1 and hh >= lvp + TICK and cc < lvp:
                d = -1
            elif side == -1 and ll <= lvp - TICK and cc > lvp:
                d = 1
            else:
                continue
            used.add(nm)
            out.append(_cand(Dy, i, nm, lvp, d, "V0", 955))
    return out


# ------------------------------------------------------------------------------------------------ simulator (E5, coarse)
def simulate(Dy, cand):
    b = Dy.bars
    mods = b["mod"].to_numpy()
    o, h, l, c, t = (b[k].to_numpy() for k in ("open", "high", "low", "close", "t"))
    d, L, stop, i, LAST = cand["d"], cand["L"], cand["stop"], cand["i"], cand["flat"]
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
        if mods[m] > LAST:
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
    out, last_exit = [], None
    for x in sorted(cands, key=lambda r: (r["t_sig"], r["level"])):
        x.pop("busy", None)
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
        if vid == "V0":
            cs = v0_candidates(D, usable, day)
        else:
            ws, mode = VARIANTS[vid]
            cs = day_candidates(D, usable, day, ws, mode)
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


def _brief(bk):
    U = np.array([x["usd"] for x in bk], float); R = np.array([x["R"] for x in bk], float)
    return {"n": len(bk), "mean_R": round(float(R.mean()), 3) if len(R) else None, "usd": round(float(U.sum()), 0),
            "win_pct": round(100 * float((U > 0).mean()), 1) if len(U) else None}


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
           "mean_risk_pts": round(float(np.mean([x["risk_pts"] for x in bk])), 1) if bk else None,
           "how": {hh: sum(1 for x in bk if x["how"] == hh) for hh in ("level", "marketable", "market+18")},
           "why": {w: sum(1 for x in bk if x["why"] == w) for w in ("target", "stop", "flat")}}
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
    out["by_window"] = {w: _brief([x for x in bk if x["win"] == w]) for w in sorted({x["win"] for x in bk})}
    out["by_level"] = {lv: _brief([x for x in bk if x["level"] == lv]) for lv in sorted({x["level"] for x in bk})}
    return out


def verdict(s, p_holm):
    if s["trades"] < 20:
        return "TOO FEW"
    hv = s["halves"].values()
    both = all((h["mean_R"] if h["mean_R"] is not None else -1) > 0 and (h["gap_R"] if h["gap_R"] is not None else -1) > 0
               for h in hv)
    if (s["net_usd"] > 0 and (s["pf"] or 0) >= 1.20 and both and (s["placebo_p"] or 1) < 0.10
            and p_holm is not None and p_holm < 0.10):
        return "YES-candidate"
    if s["net_usd"] > 0 and (s["gap_R"] if s["gap_R"] is not None else -1) > 0 and (s["placebo_p"] or 1) < 0.20:
        return "weak"
    return "NO"


def table(rows):
    hdr = ("var", "what", "cand", "abs", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "maxDD", "halves R (old/new)",
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
