#!/usr/bin/env python3
"""Red team: the 'best live markets' stress. The owner-size version of the rewards rule would put $50-100 on the 1-5 markets
whose LIVE book pays the most reward per $ (thin side, mid price). Those are the strikes where a resting order is most likely
to be swept just before a move. For the top 5 markets of today's books (results_paper.json, 50 a side): the last 7 days of
public tape + 1-minute candles (GET only, <= 1 request a second), replayed with the backtest's fill rule (quote both sides at
the best bid, the measured queue ahead, a trade through my price fills what is left), marked at the latest mid. The reward is
today's share for every hour (optimistic: these markets were picked on today's book). Writes results_thin.json.
    python research/kalshi_red_team/thin_stress.py [--fetch]"""
from __future__ import annotations

import bisect
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402
from harvest_bt import candles, trades  # noqa: E402

RAW = os.path.join(fetch.CACHE, "thin_raw.json")
OUT = os.path.join(HERE, "results_thin.json")
Q = 50
DAYS = 7


def main():
    fp = json.load(open(os.path.join(HERE, "results_paper.json")))
    rows = [r for r in fp["formula"]["rows"] if r["q"] == Q]
    rows.sort(key=lambda r: -(r["usd_day_paid_after_1usd_min"] / r["capital"]))
    top = rows[:5]
    if "--fetch" in sys.argv or not os.path.exists(RAW):
        now = float(int(time.time() // 60 * 60))
        raw = {"fetched": now, "markets": {}}
        for r in top:
            t0 = now - DAYS * 86400
            raw["markets"][r["m"]] = {"s": r["s"], "candles": candles(r["s"], r["m"], t0 - 3600, now, cache=False),
                                      "trades": trades(r["m"], t0, now, cache=False)}
            print(r["m"], len(raw["markets"][r["m"]]["trades"]), "trades", fetch.COUNT[0], "requests", flush=True)
        json.dump(raw, open(RAW, "w"))
    raw = json.load(open(RAW))
    now = raw["fetched"]
    out = {"q": Q, "days": DAYS, "markets": {}}
    for r in top:
        mk = raw["markets"].get(r["m"])
        if not mk:
            continue
        cs = [c for c in mk["candles"] if c[1] is not None and c[2] is not None]
        cts = [c[0] for c in cs]
        last_mid = (float(cs[-1][1]) + float(cs[-1][2])) / 2 if cs else None
        sides = {"yes": {"p": None, "q": 0.0, "queue": 0.0}, "no": {"p": None, "q": 0.0, "queue": 0.0}}
        fills, pnl, cost, held = [], 0.0, 0.0, 0.0
        t0 = now - DAYS * 86400
        evs = sorted(set([c[0] for c in cs if c[0] >= t0] + [x[0] for x in mk["trades"] if x[0] >= t0]))
        ti = 0
        tr = sorted(x for x in mk["trades"] if x[0] >= t0)
        capsec = 0.0
        prev = t0
        for t in evs:
            # capital resting over [prev, t)
            capsec += sum((o["p"] or 0) * o["q"] for o in sides.values()) * (t - prev) + held * (t - prev)
            prev = t
            # trades at t (before the quote update at t: the quote was set from candles that closed before t)
            while ti < len(tr) and tr[ti][0] <= t:
                tt, side, py, n = tr[ti]
                ti += 1
                for sd in ("yes", "no"):
                    o = sides[sd]
                    if o["p"] is None or o["q"] <= 1e-9:
                        continue
                    px = py if (sd == "yes" and side == "no") else round(1 - py, 4) if (sd == "no" and side == "yes") else None
                    if px is None or px > o["p"] + 1e-9:
                        continue
                    if px < o["p"] - 1e-9:
                        o["queue"] = 0.0
                        got = min(n, o["q"])
                    else:
                        e = min(n, o["queue"])
                        o["queue"] -= e
                        got = min(n - e, o["q"])
                    if got > 1e-9:
                        o["q"] -= got
                        held += got * o["p"]
                        val = last_mid if sd == "yes" else 1 - last_mid
                        pnl += got * (val - o["p"])
                        cost += got * o["p"]
                        fills.append((round(tt), sd, o["p"], round(got, 1), round(val - o["p"], 3)))
            # quote update from the last candle that closed strictly before t
            ci = bisect.bisect_left(cts, t) - 1
            if ci < 0:
                continue
            bid, ask = float(cs[ci][1]), float(cs[ci][2])
            for sd, px, ahead in (("yes", bid, r["ahead_yes"]), ("no", round(1 - ask, 2), r["ahead_no"])):
                o = sides[sd]
                if not (0 < px < 1):
                    o.update(p=None, q=0.0, queue=0.0)
                    continue
                if o["p"] is None or abs(o["p"] - px) > 1e-9 or o["q"] <= 1e-9:
                    o.update(p=px, q=float(Q), queue=float(ahead))
        cap_days = capsec / 86400
        rew = r["usd_day_paid_after_1usd_min"] * DAYS
        out["markets"][r["m"]] = {"reward_if_todays_share_all_week": round(rew, 2), "fill_pnl_marked": round(pnl, 2), "fills": len(fills),
                                  "filled_usd": round(cost, 2), "avg_capital": round(cap_days / DAYS, 1),
                                  "net_per100_day": round(100 * (rew + pnl) / cap_days, 2) if cap_days else None,
                                  "fill_per100_day": round(100 * pnl / cap_days, 2) if cap_days else None,
                                  "worst_fills": sorted(fills, key=lambda f: f[3] * f[4])[:5], "mid_now": last_mid}
        print(r["m"], out["markets"][r["m"]])
    tot_r = sum(x["reward_if_todays_share_all_week"] for x in out["markets"].values())
    tot_f = sum(x["fill_pnl_marked"] for x in out["markets"].values())
    tot_c = sum(x["avg_capital"] * DAYS for x in out["markets"].values())
    out["pooled"] = {"reward": round(tot_r, 2), "fill_pnl": round(tot_f, 2), "net_per100_day": round(100 * (tot_r + tot_f) / tot_c, 2) if tot_c else None,
                     "fill_per100_day": round(100 * tot_f / tot_c, 2) if tot_c else None, "reward_per100_day": round(100 * tot_r / tot_c, 2) if tot_c else None}
    print("POOLED top-5 at %d a side, last %d days:" % (Q, DAYS), out["pooled"])
    json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
