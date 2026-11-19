#!/usr/bin/env python3
"""Red team step 2: re-check the rewards tape backtest (research/kalshi_rewards_bt/backtest.py) on a fresh re-harvest of
its raw tape (harvest_bt.py: the same seeded 40-market sample for Panama + Bab-el-Mandeb, plus the days after its window).
  A. reproduce: the backtest's own sim() and depth profiles on my copy of the tape -> its published halves
  B. luck: per-market cluster bootstrap of each half (the fills come in a few jumps, so markets are the unit), and the
     chance that 2 of 8 series are positive in both halves by luck
  C. the rules as filed: per-side normalisation (Kalshi's formula) instead of pooled sides, the $1.00 minimum per market per
     daily program, at the paper's size (200 a side) and at the owner's size ($50-100: 25-50 a side)
  D. out of sample: the same rule on the days after the backtest's window (2026-11-17 05:00 UTC .. the harvest)
  E. bad week: the worst 7 days in a row, per $100 parked
Offline (reads /home/user/kalshi_cache/kred/bt/); small (about 85 MB, 30 s). Writes results_bt.json next to this file.
    python research/kalshi_red_team/audit_bt.py"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import gzip
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BT = os.path.join(ROOT, "research", "kalshi_rewards_bt")
sys.path.insert(0, HERE)
sys.path.insert(0, BT)
import fetch  # noqa: E402
import backtest as B  # noqa: E402   (the original: sim, profiles, halves, T0, END)

DATA = os.path.join(fetch.CACHE, "bt")
OUT = os.path.join(HERE, "results_bt.json")
SERIES = ["KXPANAMAWEEKLY", "KXBABELMANDEBWEEKLY"]
F, T, bucket = B.F, B.T, B.bucket


def load(s, window):
    fn = os.path.join(DATA, "%s_%s.json.gz" % (s, window))
    return json.load(gzip.open(fn, "rt")) if os.path.exists(fn) else None


def sim2(m, v, prof, fee_type, r, qmult, pull_h, acc, t0, t1, per_side=False, qfrac=1.0, min_pay=0.0, jump_c=0, fills_out=None,
         bk=None):
    """backtest.sim() with the window as arguments and three switches: per_side (Kalshi's per-side normalisation),
    qfrac (my size as a fraction of Target/5), min_pay (a program's credit under this is not paid). Same everything else."""
    info = v["info"]
    res = info.get("result") or ""
    close = T(info["close_time"]) if info.get("close_time") else t1 + 86400 * 365
    yb, ya = F(info.get("yes_bid_dollars")), F(info.get("yes_ask_dollars"))
    mid_now = (yb + ya) / 2 if yb is not None and ya is not None else F(info.get("last_price_dollars")) or 0.5
    val_yes = 1.0 if res == "yes" else 0.0 if res == "no" else mid_now
    progs = sorted(v["programs"], key=lambda p: p["start"])
    stop = min(t1, close - pull_h * 3600)
    windows = [(max(p["start"], t0), min(p["end"], stop), p) for p in progs if min(p["end"], stop) > max(p["start"], t0)]
    if not windows or not prof["rep"]:
        return
    cand = [c for c in v["candles"] if c[0] <= t1]
    cts = [c[0] for c in cand]
    trades = [x for x in v["trades"] if t0 - 3600 <= x[0] <= t1]
    ev = set()
    last = None
    for c in cand:
        q = (c[1], c[2])
        if q != last:
            ev.add(c[0])
            last = q
    for a, b, _ in windows:
        ev.add(a)
        ev.add(b)
    ev = sorted(e for e in ev if windows[0][0] <= e <= windows[-1][1])
    if not ev:
        return
    sides = {sd: {"p": None, "q": 0.0, "queue": 0.0} for sd in ("yes", "no")}
    ti = bisect.bisect_left([x[0] for x in trades], ev[0])
    credit = collections.defaultdict(float)          # (program start, day) -> reward credited
    held = [0.0]                                      # $ in filled contracts (as in backtest.sim: parked, never released)

    def prog_at(t):
        for a, b, p in windows:
            if a <= t < b:
                return p
        return None

    for k, t in enumerate(ev):
        nxt = ev[k + 1] if k + 1 < len(ev) else None
        p = prog_at(t)
        ci = bisect.bisect_right(cts, t) - 1
        bid = F(cand[ci][1]) if ci >= 0 else None
        ask = F(cand[ci][2]) if ci >= 0 else None
        jumped = False
        if jump_c and p is not None and bid is not None and ask is not None:
            cj = bisect.bisect_right(cts, t - 3600) - 1
            b0, a0 = (F(cand[cj][1]), F(cand[cj][2])) if cj >= 0 else (None, None)
            jumped = b0 is not None and a0 is not None and abs((bid + ask) / 2 - (b0 + a0) / 2) >= jump_c / 100 - 1e-9
        if p is None or jumped:
            for sd in sides.values():
                sd.update(p=None, q=0.0, queue=0.0)
        else:
            tgt = p["target"]
            Q = tgt / 5 * qfrac
            for sd, px in (("yes", bid), ("no", (1 - ask) if ask is not None else None)):
                o = sides[sd]
                if px is None or px <= 0 or px >= 1:
                    o.update(p=None, q=0.0, queue=0.0)
                    continue
                rp = prof["rep"].get(bucket(px)) or next(iter(prof["rep"].values()))
                rp = rp[r]
                ref = round(px - rp["ticks"] * 0.01, 2)
                if ref < 0.01:
                    o.update(p=None, q=0.0, queue=0.0)
                    continue
                if o["p"] is None or abs(o["p"] - ref) > 1e-9 or o["q"] <= 1e-9:
                    o.update(p=ref, q=Q, queue=qmult * rp["ahead_t"] * tgt, rp=rp, info_ts=cand[ci][0])
        if nxt is None:
            break
        dur = nxt - t
        day = int((t - t0) // 86400)
        a = acc[day]
        if p is not None and sides["yes"]["p"] is not None and sides["no"]["p"] is not None:
            tgt = p["target"]
            qy, qn = sides["yes"]["q"], sides["no"]["q"]
            sy, sn = sides["yes"]["rp"]["score_t"] * tgt, sides["no"]["rp"]["score_t"] * tgt
            usd_s = p["usd"] / max(p["end"] - p["start"], 1)
            if per_side:
                share = ((qy / (qy + sy) if qy + sy > 0 else 0.0) + (qn / (qn + sn) if qn + sn > 0 else 0.0)) / 2
            else:
                tot = qy + qn + sy + sn
                share = (qy + qn) / tot if tot > 0 else 0.0
            x = usd_s * dur * share * prof["valid"]
            a[0] += x
            credit[(p["start"], day)] += x
            if bk is not None:                       # split by side price bucket (cheap < 15c, mid, rich > 85c)
                sh_y = (qy / (qy + sy) if qy + sy > 0 else 0.0) / 2 if per_side else (qy / (qy + qn + sy + sn) if qy + qn + sy + sn > 0 else 0.0)
                sh_n = (qn / (qn + sn) if qn + sn > 0 else 0.0) / 2 if per_side else (qn / (qy + qn + sy + sn) if qy + qn + sy + sn > 0 else 0.0)
                bk[bucket(sides["yes"]["p"])][0] += usd_s * dur * sh_y * prof["valid"]
                bk[bucket(sides["no"]["p"])][0] += usd_s * dur * sh_n * prof["valid"]
        cap = sum((o["p"] or 0) * o["q"] for o in sides.values()) + held[0]
        a[2] += cap * dur
        if bk is not None:
            for o in sides.values():
                if o["p"] is not None:
                    bk[bucket(o["p"])][2] += o["p"] * o["q"] * dur
        while ti < len(trades) and trades[ti][0] < nxt:
            tt, side, py, n = trades[ti]
            ti += 1
            if tt < t:
                continue
            for sd in ("yes", "no"):
                o = sides[sd]
                if o["p"] is None or o["q"] <= 1e-9:
                    continue
                if sd == "yes" and side == "no":
                    px = py
                elif sd == "no" and side == "yes":
                    px = round(1 - py, 4)
                else:
                    continue
                if px > o["p"] + 1e-9:
                    continue
                if px < o["p"] - 1e-9:
                    o["queue"] = 0.0
                    got = min(n, o["q"])
                else:
                    eat = min(n, o["queue"])
                    o["queue"] -= eat
                    got = min(n - eat, o["q"])
                if got <= 1e-9:
                    continue
                o["q"] -= got
                held[0] += got * o["p"]
                win = val_yes if sd == "yes" else 1 - val_yes
                fee = B.maker_fee(o["p"], got, fee_type)
                dd = acc[int((tt - t0) // 86400)]
                dd[1] += got * (win - o["p"]) - fee
                if bk is not None:
                    b_ = bk[bucket(o["p"])]
                    b_[1] += got * (win - o["p"]) - fee
                    b_[3] += 1
                    b_[4] += got * o["p"]
                if fills_out is not None:
                    x = {"ts": tt, "info_ts": o.get("info_ts"), "price": round(o["p"], 2), "contracts": round(got, 2), "role": "maker",
                         "maker_fee": "maker" in str(fee_type or ""), "ticker": m, "event": m, "side": sd}
                    if res in ("yes", "no"):
                        x["result"] = res
                    else:
                        x["mark_price"] = round(win, 4)
                    fills_out.append(x)
                dd[3] += 1
                dd[4] += got * o["p"]
    if min_pay > 0:                                   # the $1.00 minimum per market per program (one day here)
        tot = collections.defaultdict(float)
        for (ps, day), x in credit.items():
            tot[ps] += x
        for (ps, day), x in credit.items():
            if tot[ps] < min_pay:
                acc[day][0] -= x


def per_market(d, prof, t0, t1, ndays, **kw):
    """{market: acc} where acc[day] = [reward, fill, capital_seconds, fills, filled$], averaged over the 4 representative books."""
    out = {}
    nrep = len(B.QS)
    for m, v in d["markets"].items():
        acc = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
        for r in range(nrep):
            sim2(m, v, prof, d["fee_type"], r, kw.get("qmult", 1.0), kw.get("pull_h", 0), acc, t0, t1, kw.get("per_side", False),
                 kw.get("qfrac", 1.0), kw.get("min_pay", 0.0), kw.get("jump_c", 0))
        for a in acc.values():
            for i in range(5):
                a[i] /= nrep
        out[m] = acc
    return out


def half_stats(pm, lo, hi, boot=2000, seed=11):
    """net per $100 parked per day over days [lo, hi) and a market-cluster bootstrap 95% range."""
    rows = []
    for m, acc in pm.items():
        r = sum(acc[k][0] for k in range(lo, hi) if k in acc)
        f = sum(acc[k][1] for k in range(lo, hi) if k in acc)
        c = sum(acc[k][2] for k in range(lo, hi) if k in acc) / 86400
        n = sum(acc[k][3] for k in range(lo, hi) if k in acc)
        if c > 0 or r or f:
            rows.append((r, f, c, n))
    R, Fl, C = sum(x[0] for x in rows), sum(x[1] for x in rows), sum(x[2] for x in rows)
    if C <= 0:
        return {"markets": len(rows), "net_per100_day": None}
    rnd = random.Random(seed)
    vals = []
    for _ in range(boot):
        s = c = 0.0
        for _ in range(len(rows)):
            x = rows[rnd.randrange(len(rows))]
            s += x[0] + x[1]
            c += x[2]
        vals.append(100 * s / c if c > 0 else 0.0)
    vals.sort()
    return {"markets": len(rows), "reward": round(R, 2), "fill_pnl": round(Fl, 2), "fills": round(sum(x[3] for x in rows), 2),
            "capital_days": round(C, 1), "avg_capital": round(C / max(hi - lo, 1), 1),
            "reward_per100_day": round(100 * R / C, 3), "fill_per100_day": round(100 * Fl / C, 3), "net_per100_day": round(100 * (R + Fl) / C, 3),
            "ci95": [round(vals[int(0.025 * boot)], 3), round(vals[int(0.975 * boot)], 3)],
            "p_net_le_0": round(sum(1 for x in vals if x <= 0) / boot, 3)}


def daily(pm, ndays):
    """pooled per day: (reward, fill, capital_days)."""
    out = []
    for k in range(ndays):
        r = sum(acc[k][0] for acc in pm.values() if k in acc)
        f = sum(acc[k][1] for acc in pm.values() if k in acc)
        c = sum(acc[k][2] for acc in pm.values() if k in acc) / 86400
        out.append((r, f, c))
    return out


def worst_week(days):
    best = None
    for i in range(0, max(1, len(days) - 6)):
        w = days[i:i + 7]
        r, f, c = sum(x[0] for x in w), sum(x[1] for x in w), sum(x[2] for x in w)
        if c <= 0:
            continue
        v = 100 * (r + f) / c * 7          # $ per $100 parked over the 7 days
        if best is None or v < best[0]:
            best = (v, i, r, f, c / 7)
    return best


def biggest_losses(pm, top=5):
    xs = []
    for m, acc in pm.items():
        for k, a in acc.items():
            xs.append((a[1], m, k))
    xs.sort()
    return xs[:top]


def main():
    prof = B.profiles()
    res = {"series": {}, "notes": []}
    pub = json.load(open(os.path.join(BT, "results.json")))
    t0, t1 = B.T0, B.END
    pool_pm = collections.defaultdict(dict)        # variant -> {series:market: acc} for the pooled view
    for s in SERIES:
        d = load(s, "bt")
        if d is None:
            print(s, "no re-harvest yet")
            continue
        R = {"markets": len(d["markets"]), "n_markets": d["n_markets"]}
        # A. reproduce with the ORIGINAL sim (module window) and with sim2 (same switches off)
        acc = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
        for m, v in d["markets"].items():
            for r in range(len(B.QS)):
                B.sim(m, v, prof[s], d["fee_type"], r, 1.0, 0, acc)
        for a in acc.values():
            for i in range(5):
                a[i] /= len(B.QS)
        h = B.halves(acc)
        R["reproduce"] = {"mine": {k: round(h[k]["net_per100_day"], 3) for k in ("first15", "last15", "all30")},
                          "published": {k: round(pub["series"][s]["queue"]["1.0"][k]["net_per100_day"], 3) for k in ("first15", "last15", "all30")},
                          "mine_reward": {k: round(h[k]["reward"], 1) for k in ("first15", "last15")},
                          "published_reward": {k: round(pub["series"][s]["queue"]["1.0"][k]["reward"], 1) for k in ("first15", "last15")},
                          "mine_fill": {k: round(h[k]["fill_pnl"], 1) for k in ("first15", "last15")},
                          "published_fill": {k: round(pub["series"][s]["queue"]["1.0"][k]["fill_pnl"], 1) for k in ("first15", "last15")}}
        base = per_market(d, prof[s], t0, t1, 30)
        pool_pm["base"].update({s + ":" + m: a for m, a in base.items()})
        sr = sum(a[0] for acc_ in base.values() for a in acc_.values())
        sf = sum(a[1] for acc_ in base.values() for a in acc_.values())
        R["sim2_equals_sim"] = abs(sr - h["all30"]["reward"]) < 1e-6 * max(1, abs(sr)) and abs(sf - h["all30"]["fill_pnl"]) < 1e-6 * max(1, abs(sf))
        print("  sim2 (switches off) equals backtest.sim:", R["sim2_equals_sim"], round(sr, 4), round(h["all30"]["reward"], 4), round(sf, 4), round(h["all30"]["fill_pnl"], 4))
        R["base"] = {"first15": half_stats(base, 0, 15), "last15": half_stats(base, 15, 30), "all30": half_stats(base, 0, 30)}
        # C. the filed formula and the owner's size
        var = {}
        for name, kw in (("per_side", dict(per_side=True)),
                         ("per_side_min1", dict(per_side=True, min_pay=1.0)),
                         ("owner_50_a_side", dict(per_side=True, min_pay=1.0, qfrac=0.25)),
                         ("owner_25_a_side", dict(per_side=True, min_pay=1.0, qfrac=0.125)),
                         ("owner_50_no_min", dict(per_side=True, min_pay=0.0, qfrac=0.25)),
                         ("pause5c_per_side", dict(per_side=True, jump_c=5))):
            pm = per_market(d, prof[s], t0, t1, 30, **kw)
            pool_pm[name].update({s + ":" + m: a for m, a in pm.items()})
            var[name] = {"first15": half_stats(pm, 0, 15), "last15": half_stats(pm, 15, 30), "all30": half_stats(pm, 0, 30)}
            if name == "owner_50_a_side":
                var[name]["biggest_market_day_fill_losses"] = [(round(a, 2), m, k) for a, m, k in biggest_losses(pm)]
                ww = worst_week(daily(pm, 30))
                var[name]["worst_week"] = {"usd_per100_over_7_days": round(ww[0], 2), "start_day": ww[1], "reward": round(ww[2], 2),
                                           "fill": round(ww[3], 2), "avg_capital": round(ww[4], 1)} if ww else None
        R["variants"] = var
        ww = worst_week(daily(base, 30))
        R["worst_week_base"] = {"usd_per100_over_7_days": round(ww[0], 2), "start_day": ww[1], "reward": round(ww[2], 2), "fill": round(ww[3], 2),
                                "avg_capital": round(ww[4], 1)} if ww else None
        R["biggest_market_day_fill_losses_base"] = [(round(a, 2), m, k) for a, m, k in biggest_losses(base)]
        # the verifier on the backtest's own fills (one representative book, r = 1): timing, exact fees, per $1, halves
        fo = []
        for m, v in d["markets"].items():
            sim2(m, v, prof[s], d["fee_type"], 1, 1.0, 0, collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0]), t0, t1, fills_out=fo)
        import verify as V  # noqa: E402
        vv = V.verify(fo, {"name": s + " backtest fills (maker, before rewards)"}, rules_tried=272, split=dt.datetime.fromtimestamp(B.HALF, dt.timezone.utc).isoformat(), boot=2000)
        print(V.report(vv))
        R["verify_fills"] = {k: vv[k] for k in ("verdict", "reasons", "problem_counts", "all", "first_half", "second_half")}
        # by side price bucket (per-side formula): where do the rewards and the fill losses come from?
        bks = {}
        for half, lo, hi in (("first15", t0, B.HALF), ("last15", B.HALF, t1)):
            bk = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
            for m, v in d["markets"].items():
                for r in range(len(B.QS)):
                    sim2(m, v, prof[s], d["fee_type"], r, 1.0, 0, collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0]), lo, hi, per_side=True, bk=bk)
            bks[half] = {b: {"reward_per100_day": round(100 * x[0] / (x[2] / 86400), 3) if x[2] else None,
                             "fill_per100_day": round(100 * x[1] / (x[2] / 86400), 3) if x[2] else None,
                             "net_per100_day": round(100 * (x[0] + x[1]) / (x[2] / 86400), 3) if x[2] else None,
                             "fill_per1_filled": round(x[1] / x[4], 4) if x[4] else None, "filled_per100_day": round(100 * x[4] / (x[2] / 86400), 2) if x[2] else None,
                             "capital_days": round(x[2] / 86400 / len(B.QS), 1), "fills": round(x[3] / len(B.QS), 1)} for b, x in bk.items()}
        R["by_bucket_per_side"] = bks
        print("  by bucket", json.dumps(bks))
        # D. out of sample
        o = load(s, "oos")
        if o is not None:
            n_days = max(1, int(math.ceil((o["t1"] - o["t0"]) / 86400)))
            for name, kw in (("base", {}), ("per_side_min1", dict(per_side=True, min_pay=1.0)), ("owner_50_a_side", dict(per_side=True, min_pay=1.0, qfrac=0.25)),
                             ("pause5c_per_side", dict(per_side=True, jump_c=5))):
                pm = per_market(o, prof[s], o["t0"], o["t1"], n_days, **kw)
                pool_pm["oos_" + name].update({s + ":" + m: a for m, a in pm.items()})
                pool_pm["oos_ndays"] = n_days
                R.setdefault("oos", {})[name] = half_stats(pm, 0, n_days)
            R["oos_window"] = [dt.datetime.fromtimestamp(o["t0"], dt.timezone.utc).isoformat(timespec="minutes"),
                               dt.datetime.fromtimestamp(o["t1"], dt.timezone.utc).isoformat(timespec="minutes"), len(o["markets"])]
        res["series"][s] = R
        print(s, json.dumps(R["reproduce"]))
        print("  base", {k: (v["net_per100_day"], v["ci95"], v["p_net_le_0"]) for k, v in R["base"].items()})
        for name, v in var.items():
            print("  %-18s" % name, {k: (x["net_per100_day"], x.get("ci95")) for k, x in v.items() if k in ("first15", "last15", "all30")}, v.get("worst_week", ""))
        print("  worst week base", R["worst_week_base"], "biggest", R["biggest_market_day_fill_losses_base"][:3])
        if "oos" in R:
            print("  OOS", R["oos_window"], {k: (v.get("net_per100_day"), v.get("reward_per100_day"), v.get("fill_per100_day"), v.get("fills")) for k, v in R["oos"].items()})
    # pooled (both series, capital-weighted, markets resampled together)
    nd = pool_pm.pop("oos_ndays", 2)
    P = {}
    for name, pm in pool_pm.items():
        if name.startswith("oos_"):
            P[name] = half_stats(pm, 0, nd)
        else:
            P[name] = {"first15": half_stats(pm, 0, 15), "last15": half_stats(pm, 15, 30), "all30": half_stats(pm, 0, 30)}
            ww = worst_week(daily(pm, 30))
            P[name]["worst_week"] = {"usd_per100_over_7_days": round(ww[0], 2), "start_day": ww[1]} if ww else None
    res["pooled_two_series"] = P
    for name, v in P.items():
        if name.startswith("oos_"):
            print("POOLED %-22s net %s reward %s fill %s fills %s" % (name, v.get("net_per100_day"), v.get("reward_per100_day"), v.get("fill_per100_day"), v.get("fills")))
        else:
            print("POOLED %-22s" % name, {k: (x["net_per100_day"], x["ci95"]) for k, x in v.items() if k in ("first15", "last15", "all30")}, v.get("worst_week"))
    # B. the luck of "2 of 8 series positive in both halves"
    sys.path.insert(0, HERE)
    import verify as V  # noqa: E402
    res["chance_2_of_8_both_halves"] = round(V.chance_both_halves(2, 8), 3)
    res["chance_2_of_11_both_halves"] = round(V.chance_both_halves(2, 11), 3)
    json.dump(res, open(OUT, "w"), indent=1)
    print("chance >= 2 of 8 positive in both halves by luck:", res["chance_2_of_8_both_halves"])


if __name__ == "__main__":
    main()
