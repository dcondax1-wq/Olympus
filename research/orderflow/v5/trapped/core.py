"""v5 'trapped' family core (rules: research/orderflow/v5/trapped/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

Key-level / session-extreme breakouts that CLOSE beyond with heavy aggressive delta: FADE when they fail back inside within 2
bars (trapped traders), HOLD = continuation when the next bar also closes beyond. Reuses the v5 'levels' simulator (E5 fill,
exits, costs, placebo, Holm) unchanged. Imports nothing that can trade.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("v5tr_levels_core", os.path.join(os.path.dirname(HERE), "levels", "core.py"))
C = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(C)

TICK = C.TICK
B0, B1 = 570, 900            # breakout bar opens
F0, F1 = 585, 900            # decision bar opens
ORB_FROM = 600
XD_MIN = 100
FADE_N, SX_COOL = 2, 6
KEY_ORDER = ["pdh", "pdl", "onh", "onl", "orh", "orl"]
VARIANTS = {"T1": ("FADE", "KEY", "BD"), "T2": ("FADE", "KEY", "XD"), "T3": ("FADE", "SX", "BD"),
            "C1": ("HOLD", "KEY", "BD"), "C2": ("HOLD", "KEY", "XD"), "C3": ("HOLD", "SX", "BD")}
NAMES = {"T1": "fade failed key break, bar delta", "T2": "fade failed key break, beyond-level delta",
         "T3": "fade failed session-extreme break, bar delta", "C1": "hold key break, bar delta",
         "C2": "hold key break, beyond-level delta", "C3": "hold session-extreme break, bar delta"}
C.NAMES.update(NAMES)
load_days, score, verdict, holm, table, simulate, book = C.load_days, C.score, C.verdict, C.holm, C.table, C.simulate, C.book


def key_levels(D, usable, day):
    """[(name, price)] known all day (pdh/pdl/onh/onl) + orh/orl (from 10:00) as a separate list."""
    lv = [(nm, float(p)) for nm, p, _ in C.v0_levels(D, usable, day, None)]
    b = D[day].bars
    orb = b[(b["mod"] >= 570) & (b["mod"] < 600)]
    orl = [("orh", float(orb.high.max())), ("orl", float(orb.low.min()))] if len(orb) == 6 else []
    return lv, orl


LOOKS = {1: {"bd": 0.08, "xd": 0.15}, 2: {"bd": 0.05, "xd": 0.05}}   # look 2 = DESIGN_look2.md (post-hoc)
TH = dict(LOOKS[1])


def set_look(k):
    TH.update(LOOKS[int(k)])


def bd_label(b, B, dr):
    n, v, de = int(b.n.iat[B]), float(b.volume.iat[B]), float(b.delta.iat[B])
    return bool(n >= 20 and v > 0 and de * dr >= TH["bd"] * v)


def xd_label(Dy, B, F, L, dr):
    b = Dy.bars
    vx = dx = 0.0
    for r in range(B, F + 1):
        g = Dy.fp_by_bar.get(r)
        if g is None:
            continue
        px = float(b.low.iat[r]) + g.k.to_numpy() * TICK
        m = px >= L + TICK - 1e-9 if dr == 1 else px <= L - TICK + 1e-9
        vx += float((g.a + g.b + g.u).to_numpy()[m].sum()); dx += float((g.a - g.b).to_numpy()[m].sum())
    return bool(vx >= XD_MIN and dx * dr >= TH["xd"] * vx), vx, dx


def _contig(t, a, z):
    return all(int(t[r + 1]) - int(t[r]) == 300 for r in range(a, z))


def _pattern(b, B, L, dr, pat):
    """-> (F, d, stop) or None."""
    c, h, l, t, mods = (b[k].to_numpy() for k in ("close", "high", "low", "t", "mod"))
    n = len(b)
    if pat == "FADE":
        for F in range(B + 1, min(B + FADE_N, n - 1) + 1):
            if not _contig(t, B, F):
                return None
            if (dr == 1 and c[F] < L) or (dr == -1 and c[F] > L):
                if not (F0 <= mods[F] <= F1):
                    return None
                stop = float(h[B:F + 1].max() + TICK) if dr == 1 else float(l[B:F + 1].min() - TICK)
                return F, -dr, stop
        return None
    F = B + 1
    if F >= n or not _contig(t, B, F) or not (F0 <= mods[F] <= F1):
        return None
    if (dr == 1 and c[F] > L) or (dr == -1 and c[F] < L):
        stop = float(l[B:F + 1].min() - TICK) if dr == 1 else float(h[B:F + 1].max() + TICK)
        return F, dr, stop
    return None


def day_candidates(D, usable, day, vid):
    pat, lv, lab = VARIANTS[vid]
    Dy = D[day]
    b = Dy.bars
    c, h, l, t, mods = (b[k].to_numpy() for k in ("close", "high", "low", "t", "mod"))
    out = []
    if lv == "KEY":
        base, orl = key_levels(D, usable, day)
        used = set()
        for B in range(1, len(b)):
            if not (B0 <= mods[B] <= B1) or int(t[B]) - int(t[B - 1]) != 300:
                continue
            LL = base + (orl if mods[B] >= ORB_FROM else [])
            br = []
            for nm, L in LL:
                if nm in used:
                    continue
                L = round(L / TICK) * TICK
                if c[B - 1] <= L < c[B]:
                    br.append((abs(c[B] - L), KEY_ORDER.index(nm), nm, L, 1))
                elif c[B - 1] >= L > c[B]:
                    br.append((abs(c[B] - L), KEY_ORDER.index(nm), nm, L, -1))
            if not br:
                continue
            for x in br:
                used.add(x[2])
            br.sort()
            _, _, nm, L, dr = br[0]
            out += _cand(Dy, day, B, nm, L, dr, pat, lab)
    else:
        last = {1: -99, -1: -99}
        for B in range(1, len(b)):
            if not (ORB_FROM <= mods[B] <= B1):
                continue
            prior = np.where((mods >= 570) & (mods < mods[B]) & (np.arange(len(b)) < B))[0]
            if not len(prior):
                continue
            hi, lo = float(h[prior].max()), float(l[prior].min())
            for dr, L in ((1, hi), (-1, lo)):
                if (dr == 1 and c[B] > L) or (dr == -1 and c[B] < L):
                    if B - last[dr] < SX_COOL:
                        continue
                    cs = _cand(Dy, day, B, f"sx{'h' if dr == 1 else 'l'}_{B}", L, dr, pat, lab)
                    if cs:
                        last[dr] = B
                        out += cs
    return out


def _cand(Dy, day, B, nm, L, dr, pat, lab):
    b = Dy.bars
    p = _pattern(b, B, L, dr, pat)
    if p is None:
        return []
    F, d, stop = p
    vx = dx = None
    if lab == "BD":
        lb = bd_label(b, B, dr)
    else:
        lb, vx, dx = xd_label(Dy, B, F, L, dr)
    return [{"day": day, "i": F, "B": B, "t_sig": int(b.t.iat[F]), "t_brk": int(b.t.iat[B]), "level": nm, "L": float(L),
             "dir": dr, "d": d, "absorbed": lb, "bd_share": round(float(b.delta.iat[B]) * dr / max(1.0, float(b.volume.iat[B])), 4),
             "vx": vx, "dx": dx, "stop": stop}]


def run_variant(D, usable, days, vid):
    cands = []
    for day in days:
        cands += [simulate(D[day], x) for x in day_candidates(D, usable, day, vid)]
    return cands


def price_only(cands, days):
    """information: every candidate booked (label ignored), one position at a time."""
    cp = [dict(x, absorbed=True) for x in cands]
    bk = book(cp)
    U = [x["usd"] for x in bk]
    R = [x["R"] for x in bk]
    return {"trades": len(bk), "mean_R": round(float(np.mean(R)), 3) if R else None, "net_usd": round(float(sum(U)), 0)}
