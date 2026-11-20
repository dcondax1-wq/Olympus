"""K8 'better edge' tests (night-kalshi8 2026-11-20). The same bar as engine/kalshi_adapt's scan: every variant tried is counted,
one-sided Bonferroni on the cluster t (one cluster = one day, verify.py), found on the OLDER weeks (Aug 3 - Oct 21) and checked
once on the HELD-OUT newest weeks (Oct 22 - Nov 19). The variant list was written down before any result was read.

Variants (82):
  timing   +10 s and +40 s vs today's +20 s, the 6 metals legs pooled (paired: the same bets, only the price differs;
           a bet with no fill at that time counts as $0)                                                              2
  caps     per leg, skip asks above 50 / 53 / 55 / 57 / 60c (do the skipped bets lose?)                         6 x 5 = 30
  filters  per leg, the metal's own path from Kalshi's settles (no outside data): the previous quarter hour up/down;
           the 4-hour move before up/down; the session before (00:00 ET -> open for the morning legs, 09:30 ET ->
           open for the evening legs) up/down; the 8-hour realised volatility above/below the leg's own median of the
           20 bet days before (no look-ahead). Skip one side of each split (do the skipped bets lose?)        6 x 4 x 2 = 48
  rolls    natural gas UP and WTI DOWN 17:00-17:15 ET on the 5th-9th business day, at the +20 s price            2
Holiday / early-close skips are a safety rule (no CME close to lean on), not testable: Labor Day is the only US holiday in
the sample. They stay in the executor's calendar.

PASS = find period: t >= bar (a filter / cap: the SKIPPED bets lose with t <= -bar) AND held out: the same sign and at least
5% per $1, on at least 6 bets. All-win samples (t is infinite) use the exact binomial bound instead: the one-sided
(1 - 0.05/82) upper bound of the loss rate must be under the break-even loss rate.

    python research/kalshi_k8_monday/edge.py    -> research/kalshi_k8_monday/edge.json
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics
import sys

import k8m_data as D

sys.path.insert(0, D.ROOT)
from engine import kalshi_clock as KC  # noqa: E402

sys.path.insert(0, os.path.join(D.ROOT, "research", "kalshi_edge_K8"))
import k8lib  # noqa: E402

OUT = os.path.join(D.HERE, "edge.json")
M = 2 + 30 + 48 + 2
BAR = float(D.V.bar_t(M))
STAKE = 2.5
CAPS = (0.50, 0.53, 0.55, 0.57, 0.60)
FEATS = ("prev_qh", "move_4h", "session", "vol_8h")
MIN_HOLD_N = 6
MIN_HOLD = 0.05


def items(rows):
    return [{"cluster": str(r["day"]), "pnl": r["pnl"], "cost": r["cost"]} for r in rows if r.get("n")]


def s_of(rows):
    r = [x for x in rows if x.get("n")]
    if not r:
        return {"n": 0, "net_per_1": None, "t": 0.0}
    c = sum(x["cost"] for x in r)
    return {"n": len(r), "won": sum(1 for x in r if x["won"]), "net_usd": round(sum(x["pnl"] for x in r), 2),
            "net_per_1": round(sum(x["pnl"] for x in r) / c, 4), "avg_price": round(statistics.mean(x["price"] for x in r), 4),
            "t": round(float(D.V.cluster_t(items(r))), 2)}


def path(series):
    """{close epoch: (target, settle)} from every settled 15-minute market."""
    return {m["close"]: (m["fs"], m["ev"]) for m in D.markets(series).values() if m["close"] and m["fs"] and m["ev"]}


def price_at(P, t):
    """The index at epoch t: the settle of the window closing at t (or the target of the window opening at t)."""
    if t in P:
        return P[t][1]
    if t + 900 in P:
        return P[t + 900][0]
    return None


def features(rows):
    P = {s: path(s) for s in ("KXGOLD15M", "KXSILVER15M")}
    hist = {}
    for r in sorted(rows, key=lambda r: r["o"]):
        L = D.LEGS[r["leg"]]
        p, o = P[L["series"]], r["o"]
        f = {}
        pq = p.get(o)
        f["prev_qh"] = None if not pq else ("up" if pq[1] >= pq[0] else "down")
        a, b = price_at(p, o - 4 * 3600), price_at(p, o)
        f["move_4h"] = None if not (a and b) else ("up" if b >= a else "down")
        e = KC.KL.et_dt(o)
        anchor = KC.et_epoch(e.date(), 0, 0) if e.hour < 12 else KC.et_epoch(e.date(), 9, 30)
        a = price_at(p, anchor)
        f["session"] = None if not (a and b) else ("up" if b >= a else "down")
        rets = [math.log(p[t][1] / p[t][0]) for t in range(int(o) - 8 * 3600 + 900, int(o) + 1, 900) if t in p and p[t][0] > 0 and p[t][1] > 0]
        vol = statistics.pstdev(rets) if len(rets) >= 16 else None
        h = hist.setdefault(r["leg"], [])
        if vol is not None and len(h) >= 10:
            f["vol_8h"] = "high" if vol > statistics.median(h[-20:]) else "low"
        else:
            f["vol_8h"] = None
        if vol is not None:
            h.append(vol)
        r["f"] = f
    return rows


def verdict(find, hold, sign=+1):
    """sign +1: the rows must make money; -1: the rows (to be skipped) must lose."""
    ok_find = (find["n"] >= 10) and (sign * find["t"] >= BAR)
    ok_hold = hold["n"] >= MIN_HOLD_N and hold["net_per_1"] is not None and sign * hold["net_per_1"] >= MIN_HOLD
    return "PASS" if ok_find and ok_hold else "fail"


def split(rows):
    return [r for r in rows if not r["hold"]], [r for r in rows if r["hold"]]


def main():
    out = {"variants": M, "bar_t": round(BAR, 3), "find": "2026-08-03..2026-10-21", "held_out": "2026-10-22..2026-11-19",
           "stake": STAKE, "results": []}
    base = {d: D.bets(stake=STAKE, delay=d) for d in (10.0, 20.0, 40.0)}
    rows20 = features([dict(r) for r in base[20.0]])
    f_, h_ = split(rows20)
    out["baseline"] = {"all": s_of(rows20), "find": s_of(f_), "hold": s_of(h_),
                       "by_leg": {lid: {"find": s_of([r for r in f_ if r["leg"] == lid]), "hold": s_of([r for r in h_ if r["leg"] == lid])} for lid in D.LEGS}}
    # timing (paired)
    key = lambda r: (r["leg"], r["day"])
    b20 = {key(r): r for r in base[20.0]}
    for d in (10.0, 40.0):
        diffs = []
        for r in base[d]:
            r0 = b20.get(key(r))
            if not r0:
                continue
            p1 = r["pnl"] if r.get("n") else 0.0
            p0 = r0["pnl"] if r0.get("n") else 0.0
            c0 = r0["cost"] if r0.get("n") else (r["cost"] if r.get("n") else 0.0)
            if not c0:
                continue
            diffs.append({"cluster": str(r["day"]), "pnl": p1 - p0, "cost": c0, "hold": r["hold"],
                          "dp": (r0["price"] - r["price"]) if (r.get("n") and r0.get("n")) else None, "fill": bool(r.get("n"))})
        res = {}
        for nm, sel in (("find", [x for x in diffs if not x["hold"]]), ("hold", [x for x in diffs if x["hold"]])):
            c = sum(x["cost"] for x in sel)
            dps = [x["dp"] for x in sel if x["dp"] is not None]
            res[nm] = {"n": len(sel), "net_per_1": round(sum(x["pnl"] for x in sel) / c, 4) if c else None,
                       "t": round(float(D.V.cluster_t(sel)), 2), "cheaper_c": round(100 * statistics.mean(dps), 2) if dps else None,
                       "fill_rate": round(sum(1 for x in sel if x["fill"]) / len(sel), 3) if sel else None}
        out["results"].append({"kind": "timing", "what": f"+{d:.0f} s instead of +20 s (6 legs pooled)", **res,
                               "verdict": verdict(res["find"], res["hold"], +1)})
    # caps
    for lid in D.LEGS:
        for cap in CAPS:
            sk = [r for r in rows20 if r["leg"] == lid and r.get("n") and r["price"] > cap + 1e-9]
            f, h = split(sk)
            out["results"].append({"kind": "cap", "leg": lid, "what": f"{lid}: skip asks above {cap * 100:.0f}c", "skipped_find": s_of(f),
                                   "skipped_hold": s_of(h), "verdict": verdict(s_of(f), s_of(h), -1)})
    # filters
    for lid in D.LEGS:
        for ft in FEATS:
            vals = ("high", "low") if ft == "vol_8h" else ("up", "down")
            for v in vals:
                sk = [r for r in rows20 if r["leg"] == lid and r.get("n") and r["f"].get(ft) == v]
                kept = [r for r in rows20 if r["leg"] == lid and r.get("n") and r["f"].get(ft) not in (None, v)]
                f, h = split(sk)
                kf, kh = split(kept)
                out["results"].append({"kind": "filter", "leg": lid, "what": f"{lid}: skip when {ft} = {v}", "skipped_find": s_of(f),
                                       "skipped_hold": s_of(h), "kept_find": s_of(kf), "kept_hold": s_of(kh),
                                       "verdict": verdict(s_of(f), s_of(h), -1)})
    # rolls
    T = D.tape()
    roll = set()
    for y, m in ((2026, 8), (2026, 9), (2026, 10), (2026, 11)):
        roll |= set(k8lib.gsci_roll_days(y, m))
    for series, side, nm in (("KXNATGAS15M", "yes", "natgas UP"), ("KXWTI15M", "no", "WTI DOWN")):
        rr = []
        for d in sorted(roll):
            o = KC.et_epoch(d, 17, 0)
            tk = KC.ticker(series, o)
            rec = T.get(tk)
            if not rec:
                continue
            n, px, _ = D.walk_from(rec["tr"], side, 20.0, STAKE)
            row = {"day": d, "won": rec["res"] == side, "n": n, "price": px, "hold": d >= dt.date(2026, 11, 1)}
            if n:
                fe = D.fee(px, n)
                row.update(fee=fe, cost=n * px + fe, pnl=(n if row["won"] else 0) - n * px - fe)
            rr.append(row)
        f, h = split(rr)
        sf, sh = s_of(f), s_of(h)
        allr = [x for x in rr if x.get("n")]
        lost = sum(1 for x in allr if not x["won"])
        ub = None
        if allr:
            # exact one-sided upper bound of the loss rate (Clopper-Pearson) at 1 - 0.05/M
            a = 0.05 / M
            n = len(allr)
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                cdf = sum(math.comb(n, k) * mid ** k * (1 - mid) ** (n - k) for k in range(lost + 1))
                lo, hi = (mid, hi) if cdf > a else (lo, mid)
            ub = round(hi, 4)
        avgp = statistics.mean(x["price"] for x in allr) if allr else None
        be_loss = round(1 - (avgp + statistics.mean(x["fee"] / x["n"] for x in allr)), 4) if allr else None
        v = verdict(sf, sh, +1) if not (sf.get("t") in (math.inf,) or lost == 0) else ("PASS" if ub is not None and ub < be_loss and sh["n"] >= MIN_HOLD_N else "fail")
        out["results"].append({"kind": "roll", "what": f"roll days: {nm} 17:00-17:15 ET at +20 s", "find": sf, "hold": sh, "all_n": len(allr),
                               "lost": lost, "loss_rate_upper": ub, "breakeven_loss_rate": be_loss, "avg_price": round(avgp, 4) if avgp else None,
                               "usd_month_at_stake": round(sum(x["pnl"] for x in allr) / 3.5, 2) if allr else None, "verdict": v})
    out["passed"] = [r["what"] for r in out["results"] if r["verdict"] == "PASS"]
    # near misses: best find t among filters/caps (for the write-up)
    fc = [r for r in out["results"] if r["kind"] in ("cap", "filter")]
    out["closest"] = sorted(({"what": r["what"], "skipped_find_t": r["skipped_find"]["t"], "skipped_find": r["skipped_find"].get("net_per_1"),
                              "skipped_hold": r["skipped_hold"].get("net_per_1"), "n_find": r["skipped_find"]["n"], "n_hold": r["skipped_hold"]["n"]}
                             for r in fc if r["skipped_find"]["n"] >= 10), key=lambda x: x["skipped_find_t"])[:8]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("bar", round(BAR, 2), "passed", out["passed"])
    print(json.dumps(out["baseline"]["find"]), json.dumps(out["baseline"]["hold"]))
    for r in out["results"]:
        if r["kind"] in ("timing", "roll"):
            print(json.dumps(r, default=str))
    for c in out["closest"]:
        print(c)


if __name__ == "__main__":
    main()
