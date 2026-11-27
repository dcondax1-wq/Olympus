"""v5 'exhaustion' family core (rules: research/orderflow/v5/exhaustion/DESIGN.md, frozen before any result). PAPER ONLY.

Footprint exhaustion prints (THIN), finished / unfinished 1-point top row (FIN / UNF) and delta exhaustion after 3 push bars
(DEX) at new 1-hour extremes. Reuses the v5 levels loader + scoring helpers. Imports nothing that can trade.
"""
from __future__ import annotations

import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("v5ex_levels_core", os.path.join(os.path.dirname(HERE), "levels", "core.py"))
LC = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(LC)

TICK, PV, COMM = 0.25, 2.0, 1.90
RR, MKT_TICKS, STOP_SLIP, FLAT_SLIP = 2.0, 18, 2, 2
W0, W1, LAST = 585, 900, 955
THIN_R, DEX_R, X6_ROOM, X6_MIN = 0.33, 0.33, 40, 8
NAMES = {"X1": "fade, thin top (exhaustion print)", "X2": "fade, finished auction (1-pt row)",
         "X3": "fade, delta exhaustion", "X4": "fade, thin top + delta exh.", "X5": "fade, 2 of 3 marks",
         "X6": "revisit unfinished extreme (with push)"}
VIDS = list(NAMES)


def pool_day(Dy):
    """push-extreme bars of one day with their labels (DESIGN 'pool' + 'labels')."""
    b = Dy.bars
    m = b["mod"].to_numpy()
    o, h, l, c, t, dl, n = (b[k].to_numpy() for k in ("open", "high", "low", "close", "t", "delta", "n"))
    out = []
    for i in range(12, len(b)):
        if not (W0 <= m[i] <= W1) or int(t[i]) - int(t[i - 12]) != 3600 or n[i] < 20:
            continue
        g = Dy.fp_by_bar.get(i)
        if g is None:
            continue
        for s in (1, -1):
            if not all((c[k] - o[k]) * s > 0 for k in (i - 3, i - 2, i - 1)):
                continue
            if s == 1 and not h[i] > h[i - 12:i].max():
                continue
            if s == -1 and not l[i] < l[i - 12:i].min():
                continue
            kmax = int(round((h[i] - l[i]) / TICK))
            kk = (kmax - g.k.to_numpy()) if s == 1 else g.k.to_numpy()
            ag = (g.a if s == 1 else g.b).to_numpy(float)
            op = (g.b if s == 1 else g.a).to_numpy(float)
            a8 = ag[kk <= 7].sum() / 8.0
            a16 = ag[(kk >= 8) & (kk <= 23)].sum() / 16.0
            thin = bool(kmax >= 24 and a16 > 0 and a8 <= THIN_R * a16)
            fin = bool(ag[kk <= 3].sum() == 0 or op[kk <= 3].sum() == 0)
            pdl = [float(dl[k]) * s for k in (i - 3, i - 2, i - 1)]
            dex = bool(min(pdl) > 0 and float(dl[i]) * s <= DEX_R * float(np.mean(pdl)))
            ext = float(h[i] if s == 1 else l[i])
            opp = float(l[i] if s == 1 else h[i])
            room = (ext - float(c[i])) * s / TICK
            out.append({"day": Dy.day, "i": i, "t_sig": int(t[i]), "s": s, "ext": ext, "opp": opp, "room_ticks": room,
                        "thin": thin, "fin": fin, "dex": dex, "a8": round(a8, 2), "a16": round(a16, 2),
                        "level": f"{'up' if s == 1 else 'dn'}_{i}"})
    return out


def label(x, vid):
    if vid == "X1":
        return x["thin"]
    if vid == "X2":
        return x["fin"]
    if vid == "X3":
        return x["dex"]
    if vid == "X4":
        return x["thin"] and x["dex"]
    if vid == "X5":
        return (int(x["thin"]) + int(x["fin"]) + int(x["dex"])) >= 2
    if vid == "X6":
        return not x["fin"]
    raise KeyError(vid)


def in_pool(x, vid):
    return x["room_ticks"] >= X6_ROOM if vid == "X6" else True


def simulate(Dy, x, vid, mkt_ticks=MKT_TICKS):
    """one candidate as if taken (DESIGN 'Trade'); returns a new dict."""
    b = Dy.bars
    mods = b["mod"].to_numpy()
    o, h, l, c, t = (b[k].to_numpy() for k in ("open", "high", "low", "close", "t"))
    r = dict(x)
    s, i = x["s"], x["i"]
    d = s if vid == "X6" else -s
    stop = (x["opp"] - d * TICK) if vid == "X6" else (x["ext"] - d * TICK)
    r.update(d=d, stop=stop, absorbed=label(x, vid), R=None, usd=None, exit_t=None, how=None)
    j = i + 1
    if j >= len(b) or int(t[j]) != x["t_sig"] + 300 or mods[j] > LAST:
        r["how"] = "no bar"; return r
    fill = float(o[j]) + d * mkt_ticks * TICK
    risk = (fill - stop) * d
    if risk <= 0:
        r["how"] = "no risk"; return r
    if vid == "X6":
        tgt = x["ext"]
        if (tgt - fill) * d < X6_MIN * TICK:
            r["how"] = "no room"; return r
    else:
        tgt = fill + d * RR * risk
    ex, why, ext_t, last = None, None, None, None
    for k in range(j, len(b)):
        if mods[k] > LAST or mods[k] < 570:
            break
        last = k
        if (d == 1 and l[k] <= stop) or (d == -1 and h[k] >= stop):
            base = o[k] if (k > j and (o[k] - stop) * d < 0) else stop
            ex, why, ext_t = base - d * STOP_SLIP * TICK, "stop", int(t[k]); break
        if (d == 1 and h[k] >= tgt + TICK) or (d == -1 and l[k] <= tgt - TICK):
            ex, why, ext_t = tgt, "target", int(t[k]); break
    if ex is None:
        if last is None:
            r["how"] = "no bar"; return r
        ex, why, ext_t = float(c[last]) - d * FLAT_SLIP * TICK, "flat", int(t[last])
    usd = (ex - fill) * d * PV - COMM
    q = int(min(40, 500.0 // (risk * PV)))
    r.update(fill=round(fill, 2), how="market", exit=round(float(ex), 2), why=why, exit_t=ext_t, risk_pts=round(risk, 2),
             R=round(usd / (risk * PV), 4), usd=round(usd, 2), usd500=round(usd * q, 2) if q >= 1 else 0.0)
    return r


def run_variant(D, days, vid, mkt_ticks=MKT_TICKS, pools=None):
    out = []
    for day in days:
        P = pools[day] if pools is not None else pool_day(D[day])
        out += [simulate(D[day], x, vid, mkt_ticks) for x in P if in_pool(x, vid)]
    return out


def score(cands, days):
    s = LC.score(cands, days)
    bk = LC.book(cands)
    res = [x for x in cands if x.get("R") is not None]
    s["pool_all_R"] = round(float(np.mean([x["R"] for x in res])), 3) if res else None
    s["pool_all_usd"] = round(float(sum(x["usd"] for x in res)), 0)
    s["targets"] = sum(1 for x in bk if x["why"] == "target")
    s["no_room"] = sum(1 for x in cands if x.get("how") == "no room")
    return s


holm, verdict = LC.holm, LC.verdict


def table(rows):
    hdr = ("var", "rule", "pool", "label", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "maxDD", "halves R (old/new)",
           "halves gap", "gap", "p", "Holm", "verdict")
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for vid, s in rows:
        hv = s["halves"]
        lines.append("| " + " | ".join(str(x) for x in (
            vid, NAMES.get(vid, vid), s["resolved"], s["absorbed"], s["trades"], s["per_week"], s["win_pct"], s["mean_R"],
            s["pf"], f"${s['net_usd']:+,.0f}", f"${s['max_dd_usd']:,.0f}",
            f"{hv['older']['mean_R']} / {hv['newer']['mean_R']}", f"{hv['older']['gap_R']} / {hv['newer']['gap_R']}",
            s["gap_R"], s["placebo_p"], s.get("holm_p"), s.get("verdict"))) + " |")
    return "\n".join(lines)
