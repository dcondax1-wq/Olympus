#!/usr/bin/env python3
"""Red team step 1: rebuild the rewards PAPER test (tools/kalshi_rewards_paper.py, ledger
research/kalshi_edge_K5/paper/rewards_paper_snapshot.json) from the raw public data in paper_raw.json (paper_fetch.py), and
check its reward maths against Kalshi's published Liquidity Incentive Program (CFTC self-certification of 2026-10-14,
effective 2026-10-28; help.kalshi.com article 13823851):
  * a side's QUALIFYING bids: walk down from the best bid adding WHOLE price levels until the size reaches Target; the
    reference price is the level where it first reaches Target / 5; levels after the Target is reached do not count;
  * score = size x 0.5 ^ ticks below the reference; NORMALISED PER SIDE (my share of the yes side + my share of the no side,
    a snapshot is worth 2.0 in all); a snapshot with either side under Target is excluded (pays nobody, scales the pool);
  * payout per market per Time Period (here one day): share x pool x valid fraction, paid only if >= $1.00, rounded down.
The paper test instead pools both sides (my yes + my no) / (all yes + all no) and scores every level on the book.
Offline. Writes results_paper.json next to this file.
    python research/kalshi_red_team/audit_paper.py"""
from __future__ import annotations

import bisect
import datetime as dt
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import fetch  # noqa: E402

LEDGER = os.path.join(ROOT, "research", "kalshi_edge_K5", "paper", "rewards_paper_snapshot.json")
RAW = os.path.join(fetch.CACHE, "paper_raw.json")
OUT = os.path.join(HERE, "results_paper.json")


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def levels(ob, side):
    return sorted([(float(a), float(b)) for a, b in (ob.get(side + "_dollars") or [])], reverse=True)


# ---------------------------------------------------------------- the two reward formulas
def official_side(lv, target, df, mine=None):
    """(my score, everyone's score, reference, reaches_target) per the filed procedure. lv = others' (price, size) desc;
    mine = (price, size) joins the level at its price."""
    book = {}
    for p, s in lv:
        book[round(p, 4)] = book.get(round(p, 4), 0.0) + s
    if mine:
        book[round(mine[0], 4)] = book.get(round(mine[0], 4), 0.0) + mine[1]
    cum, ref, qual = 0.0, None, []
    for p in sorted(book, reverse=True):
        cum += book[p]
        qual.append(p)
        if ref is None and cum >= target / 5 - 1e-9:
            ref = p
        if cum >= target - 1e-9:
            break
    else:
        return 0.0, 0.0, ref, False
    w = lambda p: df ** max(round((ref - p) * 100), 0)   # noqa: E731
    tot = sum(book[p] * w(p) for p in qual)
    my = (mine[1] * w(round(mine[0], 4))) if mine and round(mine[0], 4) in qual else 0.0
    return my, tot, ref, True


def paper_side(lv, target, df, mine=None):
    """tools/kalshi_rewards_paper.py: every level on the book, discounted from the reference (incl. my order)."""
    allv = sorted(lv + ([mine] if mine else []), reverse=True)
    cum, ref = 0.0, None
    for p, s in allv:
        cum += s
        if cum >= target / 5 - 1e-9:
            ref = p
            break
    if ref is None:
        return 0.0, 0.0, None, False
    sc = lambda p: 1.0 if p >= ref - 1e-9 else df ** round((ref - p) * 100)   # noqa: E731
    tot = sum(s * sc(p) for p, s in allv)
    my = mine[1] * sc(mine[0]) if mine else 0.0
    return my, tot, ref, sum(s for _, s in allv) >= target - 1e-9


def ref_price(lv, target):
    cum = 0.0
    for p, s in lv:
        cum += s
        if cum >= target / 5 - 1e-9:
            return p
    return None


def shares(ob, target, df, q):
    """my fraction of the day's pool for one snapshot with q contracts a side at the reference: (official, paper, valid)."""
    yes, no = levels(ob, "yes"), levels(ob, "no")
    ry, rn = ref_price(yes, target), ref_price(no, target)
    if ry is None or rn is None:
        return 0.0, 0.0, False, None
    oy = official_side(yes, target, df, (ry, q))
    on = official_side(no, target, df, (rn, q))
    py = paper_side(yes, target, df, (ry, q))
    pn = paper_side(no, target, df, (rn, q))
    valid = oy[3] and on[3]
    off = (oy[0] / oy[1] + on[0] / on[1]) / 2 if valid and oy[1] > 0 and on[1] > 0 else 0.0
    pap = (py[0] + pn[0]) / (py[1] + pn[1]) if (py[3] and pn[3]) and (py[1] + pn[1]) > 0 else 0.0
    ahead = (sum(s for p, s in yes if p >= ry - 1e-9), sum(s for p, s in no if p >= rn - 1e-9))
    cap = ry * q + rn * q
    return off, pap, valid, {"ref_yes": ry, "ref_no": rn, "ahead_yes": ahead[0], "ahead_no": ahead[1], "capital": cap,
                             "best_yes": yes[0][0] if yes else None, "best_no": no[0][0] if no else None}


def paid(day_usd):
    """the $1.00 minimum per market per Time Period, rounded down to the cent."""
    return math.floor(day_usd * 100 + 1e-9) / 100 if day_usd >= 1.0 else 0.0


# ---------------------------------------------------------------- fills from the raw tape
def replay_fills(mk, side, price, queue, t0, t1, through_fills_all=True):
    """taker volume at / through a resting `side` bid at `price` in [t0, t1): (filled contracts, list of fills).
    yes bid: hit by taker SELLING yes (taker_side 'no') at yes_price <= price; no bid: taker BUYING yes at no price <= price."""
    got, fills, q = 0.0, [], queue
    for tt, ts_side, py, n in mk["trades"]:
        if not (t0 <= tt < t1):
            continue
        if side == "yes" and ts_side == "no":
            px = py
        elif side == "no" and ts_side == "yes":
            px = round(1 - py, 4)
        else:
            continue
        if px > price + 1e-9:
            continue
        if px < price - 1e-9 and through_fills_all:
            q = 0.0
            g = n
        else:
            e = min(n, q)
            q -= e
            g = n - e
        if g > 1e-9:
            got += g
            fills.append((tt, px, g))
    return got, fills


def mid_at(mk, t):
    c = mk["candles"]
    i = bisect.bisect_right([x[0] for x in c], t) - 1
    while i >= 0:
        b, a = c[i][1], c[i][2]
        if b is not None and a is not None:
            return (float(b) + float(a)) / 2
        i -= 1
    return None


def main():
    led = json.load(open(LEDGER))
    raw = json.load(open(RAW))
    ps, pe = T(led["started"]), T(led["updated"])
    days = (pe - ps) / 86400
    res = {"paper": {"started": led["started"], "updated": led["updated"], "hours": round(days * 24, 2), "totals": led["totals"]},
           "programs": {}, "fills": {}, "formula": {}, "notes": []}
    # 1) the programs that paid during the paper window
    for t, m in led["markets"].items():
        pr = [x for x in raw["programs"][m["s"]] if x["market_ticker"] == t and T(x["start_date"]) < pe and T(x["end_date"]) > ps]
        res["programs"][t] = [{"start": x["start_date"], "end": x["end_date"], "usd": x["period_reward"] / 1e4, "target": float(x["target_size_fp"]),
                               "df": x["discount_factor_bps"] / 1e4, "paid_out": x.get("paid_out")} for x in pr]
    # 2) the paper's own reward, per market-day, and what the $1 minimum would pay
    rows = []
    for t, m in led["markets"].items():
        day_rate = m["reward"] / (m["secs"] / 86400) if m["secs"] else 0.0
        cap = (m["yes"]["p"] or 0) * 200 + (m["no"]["p"] or 0) * 200
        rows.append({"m": t, "reward": round(m["reward"], 3), "per_day": round(day_rate, 2), "paid_per_day_if_1usd_min": paid(day_rate),
                     "capital": round(cap, 0), "per100_day": round(100 * day_rate / cap, 2) if cap else None,
                     "queue_yes": m["yes"]["queue"], "queue_no": m["no"]["queue"]})
    res["paper_markets"] = rows
    tot_day = sum(r["per_day"] for r in rows)
    res["paper_reward_per_day"] = round(tot_day, 2)
    res["paper_reward_per_day_after_1usd_min"] = round(sum(r["paid_per_day_if_1usd_min"] for r in rows), 2)
    # 3) fills: the paper's one fill and a tape replay at the paper's final quotes, window and after
    fl = {}
    for t, m in led["markets"].items():
        mk = raw["markets"][t]
        win = [x for x in mk["trades"] if ps <= x[0] < pe]
        after = [x for x in mk["trades"] if x[0] >= pe]
        d = {"trades_in_window": len(win), "contracts_in_window": round(sum(x[3] for x in win), 2), "trades_after": len(after),
             "status_now": mk["info"].get("status"), "result_now": mk["info"].get("result"),
             "mid_end_of_paper": m.get("mid"), "mid_now": mid_at(mk, raw["fetched"])}
        for sd in ("yes", "no"):
            o = m[sd]
            if o["p"] is None:
                continue
            g0, f0 = replay_fills(mk, sd, o["p"], o["queue"], ps, pe, through_fills_all=False)
            g1, f1 = replay_fills(mk, sd, o["p"], o["queue"], ps, pe, through_fills_all=True)
            g2, f2 = replay_fills(mk, sd, o["p"], 0.0, ps, pe, through_fills_all=True)
            ga, fa = replay_fills(mk, sd, o["p"], o["queue"], pe, raw["fetched"], through_fills_all=True)
            d[sd] = {"final_price": o["p"], "paper_pos": o["pos"], "paper_cost": o["cost"], "replay_paper_rule": round(g0, 2),
                     "replay_through_fills_all": round(g1, 2), "replay_front_of_queue": round(g2, 2), "after_paper_through_rule": round(ga, 2),
                     "after_fills": [(dt.datetime.fromtimestamp(a, dt.timezone.utc).isoformat(timespec="minutes"), p, n) for a, p, n in fa][:10]}
        fl[t] = d
    res["fills"] = fl
    # the recorded fill: KXPANAMAWEEKLY-26NOV22-T205 NO, 28 @ 0.91 (cost 25.48)
    t205 = "KXPANAMAWEEKLY-26NOV22-T205"
    if t205 in raw["markets"]:
        mk = raw["markets"][t205]
        hits = [x for x in mk["trades"] if ps <= x[0] < pe and x[1] == "yes" and x[2] <= 0.09 + 1e-9]
        res["t205_fill"] = {"tape_trades_hitting_no_bids_at_or_above_91c": [(dt.datetime.fromtimestamp(a, dt.timezone.utc).isoformat(timespec="seconds"), s, p, n) for a, s, p, n in hits][:20],
                            "mid_after_1h": [mid_at(mk, a + 3600) for a, *_ in hits][:5], "mid_now": mid_at(mk, raw["fetched"]),
                            "mark_now": round(28 * (1 - (mid_at(mk, raw["fetched"]) or 0)) - 25.48, 2) if mid_at(mk, raw["fetched"]) is not None else None}
    # 4) the reward formula on today's live books: official / paper, at the paper's 200 a side and at small sizes
    by = {}
    for b in raw["books"]:
        for q in (200, 100, 50, 25):
            off, pap, valid, info = shares(b["ob"], b["target"], b["df"], q)
            if info is None:
                continue
            by.setdefault((b["s"], b["m"], q), []).append((off, pap, valid, info, b["usd_day"]))
    form = []
    for (s, m, q), xs in sorted(by.items()):
        off = statistics.fmean(x[0] for x in xs)
        pap = statistics.fmean(x[1] for x in xs)
        usd = xs[0][4]
        cap = statistics.fmean(x[3]["capital"] for x in xs)
        form.append({"s": s, "m": m, "q": q, "official_share": round(off, 4), "paper_share": round(pap, 4),
                     "ratio": round(off / pap, 2) if pap > 0 else None, "valid": sum(x[2] for x in xs) / len(xs),
                     "usd_day_official": round(usd * off, 2), "usd_day_paid_after_1usd_min": paid(usd * off),
                     "capital": round(cap, 2), "per100_day_official": round(100 * usd * off / cap, 2) if cap else None,
                     "per100_day_paid": round(100 * paid(usd * off) / cap, 2) if cap else None,
                     "ahead_yes": xs[0][3]["ahead_yes"], "ahead_no": xs[0][3]["ahead_no"], "ref_yes": xs[0][3]["ref_yes"], "ref_no": xs[0][3]["ref_no"]})
    res["formula"]["rows"] = form
    for q in (200, 100, 50, 25):
        f = [r for r in form if r["q"] == q and r["paper_share"] > 0]
        if not f:
            continue
        res["formula"]["q%d" % q] = {
            "markets": len(f), "median_ratio_official_over_paper": round(statistics.median(r["ratio"] for r in f), 2),
            "sum_usd_day_official": round(sum(r["usd_day_official"] for r in f), 2),
            "sum_usd_day_paper": round(sum(r["paper_share"] * 100 for r in f), 2),
            "sum_usd_day_paid": round(sum(r["usd_day_paid_after_1usd_min"] for r in f), 2),
            "sum_capital": round(sum(r["capital"] for r in f), 0),
            "per100_day_official": round(100 * sum(r["usd_day_official"] for r in f) / sum(r["capital"] for r in f), 2),
            "per100_day_paid": round(100 * sum(r["usd_day_paid_after_1usd_min"] for r in f) / sum(r["capital"] for r in f), 2),
            "markets_paying_nothing_after_1usd_min": sum(1 for r in f if r["usd_day_paid_after_1usd_min"] == 0)}
    # the same books, only the paper's 9 markets (they are still listed today)
    nine = [r for r in form if r["m"] in led["markets"] and r["q"] == 200]
    res["formula"]["paper_nine_q200"] = {"markets": len(nine), "sum_usd_day_official": round(sum(r["usd_day_official"] for r in nine), 2),
                                         "sum_usd_day_paper": round(sum(r["paper_share"] * 100 for r in nine), 2)}
    json.dump(res, open(OUT, "w"), indent=1)
    # ---- print
    print("PAPER: %.2f h, reward $%.2f, fills $%.2f, net $%.2f; $%.2f a day of rewards on 9 markets -> $%.2f a day after the $1 minimum" % (
        days * 24, led["totals"]["reward"], led["totals"]["fills_pnl"], led["totals"]["net"], tot_day, res["paper_reward_per_day_after_1usd_min"]))
    for r in rows:
        print("  %-36s reward/day $%6.2f  paid/day $%6.2f  per $100/day %5.2f  queue %8.0f / %8.0f" % (
            r["m"], r["per_day"], r["paid_per_day_if_1usd_min"], r["per100_day"] or 0, r["queue_yes"], r["queue_no"]))
    print("PROGRAMS in the window:")
    for t, p in res["programs"].items():
        print("  %-36s %s" % (t, [(x["start"][5:16], x["end"][5:16], x["usd"], x["target"], x["df"], x["paid_out"]) for x in p]))
    print("FILLS (paper rule / through-fills-all / front of queue; after the paper stopped, through rule):")
    for t, d in fl.items():
        print("  %-36s trades %3d (%7.0f ct) after %3d  now %s %s mid %s->%s" % (t, d["trades_in_window"], d["contracts_in_window"], d["trades_after"],
              d["status_now"], d["result_now"] or "-", d["mid_end_of_paper"], d["mid_now"]))
        for sd in ("yes", "no"):
            if sd in d:
                x = d[sd]
                print("      %-3s @%.2f paper pos %5.1f | replay %6.1f / %6.1f / %6.1f | after %6.1f %s" % (
                    sd, x["final_price"], x["paper_pos"], x["replay_paper_rule"], x["replay_through_fills_all"], x["replay_front_of_queue"],
                    x["after_paper_through_rule"], x["after_fills"][:3]))
    if "t205_fill" in res:
        print("T205 fill:", json.dumps(res["t205_fill"])[:900])
    print("FORMULA on live books (official / paper share):")
    for q in (200, 100, 50, 25):
        if "q%d" % q in res["formula"]:
            print("  q=%3d" % q, res["formula"]["q%d" % q])
    print("  paper's 9 markets, q=200:", res["formula"]["paper_nine_q200"])
    for r in form:
        if r["q"] == 200:
            print("   %-38s off %.4f pap %.4f ratio %s valid %.0f%% $/day %.2f paid %.2f cap %.0f ahead %.0f/%.0f ref %s/%s" % (
                r["m"], r["official_share"], r["paper_share"], r["ratio"], 100 * r["valid"], r["usd_day_official"], r["usd_day_paid_after_1usd_min"],
                r["capital"], r["ahead_yes"], r["ahead_no"], r["ref_yes"], r["ref_no"]))


if __name__ == "__main__":
    main()
