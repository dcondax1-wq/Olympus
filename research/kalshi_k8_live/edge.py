"""K8 live re-check (2026-11-21): the edge of the 3 LIVE legs at the owner's size ($2.50, $55) on the freshest public tape.
Pre-registered in research/kalshi_k8_live/PREREG.md. Reads only the local tape (research/kalshi_k8_live/data/tape.jsonl, filled
by fetch.py), reuses research/kalshi_k8_monday/k8m_data.py (the +20 s walk, exact fees, the executor's calendar).

    python research/kalshi_k8_live/edge.py      -> research/kalshi_k8_live/edge.json
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "kalshi_k8_monday"))
sys.path.insert(0, ROOT)
import k8m_data as D  # noqa: E402
from engine import kalshi_adapt as KA, kalshi_clock as KC  # noqa: E402

TAPE = os.path.join(HERE, "data", "tape.jsonl")
OUT = os.path.join(HERE, "edge.json")
FIRST, LAST = dt.date(2026, 8, 3), dt.date(2026, 11, 20)
L4_FROM, OOS_FROM = dt.date(2026, 10, 26), dt.date(2026, 11, 19)
LIVE3 = ("gold_0530_down", "gold_1700_up", "silver_1700_up")
GOLD2 = ("gold_0530_down", "gold_1700_up")
ORDER = {k: i for i, k in enumerate(LIVE3)}
CFG = dict(start=55.0, day=8.0, week=13.75, dd=19.25, kill_n=60, kill_wr=0.58, px_n=30, px_max=0.58)
PATHS, BOOT, SEED = 20000, 5000, 20261121
SIM_START = dt.date(2026, 11, 23)


def load():
    D._TAPE.clear()
    for t, r in KA.read_tape(TAPE).items():
        D._TAPE[t] = {"o": float(r["o"]), "res": r["res"], "tr": r.get("tr") or []}


def first_trade_price(tr, side, t0=20.0, until=45.0):
    for s, p, c in D.our_trades(tr, side):
        if t0 <= s <= until and p <= 0.70 + 1e-9:
            return p
    return None


def rows(stake, legs=LIVE3):
    out = []
    for r in D.bets(stake=stake, legs=legs, first=FIRST, last=LAST, cap=0.70):
        r["first_px"] = first_trade_price(D._TAPE[r["ticker"]]["tr"], r["side"])
        out.append(r)
    return out


def planned_bets_week(legs, start=SIM_START, weeks=12):
    n, d, end = 0, start, start + dt.timedelta(weeks=weeks)
    while d < end:
        if d.weekday() < 5:
            n += sum(1 for lid in legs if not KC.skipped(KC.LEG[lid], d))
        d += dt.timedelta(days=1)
    return round(n / weeks, 2)


def stats(rs, legs, rng):
    f = [x for x in rs if x.get("n")]
    if not f:
        return {"bets": 0, "unfilled": len(rs)}
    days = sorted({x["day"] for x in rs})
    weeks = max(1.0, ((days[-1] - days[0]).days + 1) / 7.0)
    per = sum(x["pnl"] for x in f) / len(f)
    bw_plan = planned_bets_week(legs)
    fill = len(f) / len(rs)
    by = {}
    for x in f:
        by.setdefault(x["day"], []).append(x["pnl"])
    dl = list(by.values())
    boots = []
    for _ in range(BOOT):
        s = [rng.choice(dl) for _ in dl]
        n = sum(len(v) for v in s)
        boots.append(sum(sum(v) for v in s) / n)
    boots.sort()
    lo, hi = boots[int(0.025 * BOOT)], boots[int(0.975 * BOOT) - 1]
    k = bw_plan * fill
    fp = [x["first_px"] for x in f if x["first_px"]]
    return {"bets": len(f), "won": sum(x["won"] for x in f), "win_rate": round(sum(x["won"] for x in f) / len(f), 4),
            "avg_price": round(sum(x["price"] for x in f) / len(f), 4),
            "avg_first_trade_price": round(sum(fp) / len(fp), 4) if fp else None,
            "usd_per_bet": round(per, 3), "usd_per_bet_95": [round(lo, 3), round(hi, 3)],
            "net_usd": round(sum(x["pnl"] for x in f), 2), "fees_usd": round(sum(x["fee"] for x in f), 2),
            "bets_week_actual": round(len(f) / weeks, 2), "bets_week_planned": bw_plan, "fill_share": round(fill, 3),
            "usd_week": round(per * k, 2), "usd_week_95": [round(lo * k, 2), round(hi * k, 2)], "unfilled": len(rs) - len(f)}


def haircut(rs, drop=0.10):
    f = [x for x in rs if x.get("n")]
    wr = sum(x["won"] for x in f) / len(f)
    p = drop / wr
    n = sum(1 for x in f if x["won"])
    pnl_win = sum(x["pnl"] for x in f if x["won"]) / n
    pnl_lose_if_win = sum(-x["cost"] for x in f if x["won"]) / n
    per = sum(x["pnl"] for x in f) / len(f) + wr * p * (pnl_lose_if_win - pnl_win)
    return {"win_rate": round(wr - drop, 4), "usd_per_bet": round(per, 3), "flip_prob": round(p, 4)}


# ---------------------------------------------------------------- Monte Carlo of the executor's gates
def day_table(rs):
    by = {}
    for x in rs:
        by.setdefault(x["day"], [])
        if x.get("n"):
            by[x["day"]].append((x["leg"], x["price"], x["won"], x["cost"], x["pnl"]))
    return [sorted(v, key=lambda b: ORDER[b[0]]) for _, v in sorted(by.items())]


def calendar(weeks, legs):
    out, d = [], SIM_START
    end = d + dt.timedelta(weeks=weeks)
    while d < end:
        if d.weekday() < 5:
            out.append((d.isocalendar()[1], {lid for lid in legs if not KC.skipped(KC.LEG[lid], d)}))
        d += dt.timedelta(days=1)
    return out


def sim(table, legs, weeks, flip=0.0, rng=None, paths=PATHS):
    cal = calendar(weeks, legs)
    res = []
    for _ in range(paths):
        bal, peak, wk, wk_pnl = CFG["start"], CFG["start"], None, 0.0
        off, off_why, wk_hit, wk_hits, low30, minbal, dd_block = False, None, False, 0, False, bal, False
        n_bets = n_won = 0
        prices = []
        bal4 = None
        for i, (w, ok) in enumerate(cal):
            if wk != w:
                wk, wk_pnl, wk_blocked = w, 0.0, False
            if i == 20:
                bal4 = bal
            if off:
                continue
            day = rng.choice(table)
            day_pnl = 0.0
            # the morning leg settles before the evening; the two 17:00 bets are open together
            groups = [[b for b in day if b[0] == "gold_0530_down"], [b for b in day if b[0] != "gold_0530_down"]]
            for g in groups:
                open_cost, placed = 0.0, []
                for b in g:
                    if b[0] not in ok or off:
                        continue
                    lid, px, won, cost, pnl = b
                    if flip and won and rng.random() < flip:
                        won, pnl = False, -cost
                    if day_pnl - open_cost - cost < -CFG["day"] - 1e-9:
                        continue
                    if (peak - bal) + cost > CFG["dd"] + 1e-9:      # not even one bet fits: OFF until the owner looks
                        off, off_why = True, "dd"
                        continue
                    if (peak - bal) + open_cost + cost > CFG["dd"] + 1e-9:   # this bet (with the open one) could breach: refused
                        dd_block = True
                        continue
                    if wk_pnl - open_cost - cost < -CFG["week"] - 1e-9:
                        if not wk_blocked:
                            wk_hits += 1
                            wk_blocked = True
                        wk_hit = True
                        continue
                    if bal - open_cost < cost:
                        continue
                    open_cost += cost
                    placed.append((px, won, pnl))
                for px, won, pnl in placed:
                    bal += pnl
                    wk_pnl += pnl
                    day_pnl += pnl
                    n_bets += 1
                    n_won += won
                    prices.append(px)
                peak = max(peak, bal)
                minbal = min(minbal, bal)
                if not off and n_bets >= CFG["kill_n"] and n_won / n_bets < CFG["kill_wr"]:
                    off, off_why = True, "winrate"
                if not off and len(prices) >= CFG["px_n"] and sum(prices[-CFG["px_n"]:]) / CFG["px_n"] > CFG["px_max"]:
                    off, off_why = True, "price"
        res.append({"end": bal, "bal4": bal4 if bal4 is not None else bal, "wk_hit": wk_hit, "wk_hits": wk_hits, "off": off_why,
                    "low30": minbal < 30.0, "bets": n_bets, "dd_block": dd_block})
    ends = sorted(r["end"] for r in res)
    n = len(res)
    return {"weeks": weeks, "p_week_stop": round(sum(r["wk_hit"] for r in res) / n, 3),
            "avg_week_stops": round(sum(r["wk_hits"] for r in res) / n, 2),
            "p_dd_refused_a_bet": round(sum(r["dd_block"] or r["off"] == "dd" for r in res) / n, 3),
            "p_off_drawdown": round(sum(r["off"] == "dd" for r in res) / n, 3),
            "p_off_winrate": round(sum(r["off"] == "winrate" for r in res) / n, 3),
            "p_off_price": round(sum(r["off"] == "price" for r in res) / n, 3),
            "p_off_any": round(sum(r["off"] is not None for r in res) / n, 3),
            "p_below_30": round(sum(r["low30"] for r in res) / n, 3),
            "p_down": round(sum(r["end"] < CFG["start"] for r in res) / n, 3),
            "median_end": round(st.median(ends), 2), "p5_end": round(ends[int(0.05 * n)], 2),
            "mean_end": round(sum(ends) / n, 2), "expected_gain": round(sum(ends) / n - CFG["start"], 2),
            "expected_gain_4w": round(sum(r["bal4"] for r in res) / n - CFG["start"], 2),
            "avg_bets": round(sum(r["bets"] for r in res) / n, 1)}


def fills(rs):
    """Other takers' buying of our side in 20-30 s / 20-45 s vs our wanted contracts (a lower bound on what could fill)."""
    out = {}
    for lid in LIVE3:
        got30 = got45 = n = 0
        vol = []
        for x in rs:
            if x["leg"] != lid:
                continue
            tr = D.our_trades(D._TAPE[x["ticker"]]["tr"], x["side"])
            p1 = x["first"] or x["first_px"]
            want = max(1, int(math.floor(2.5 / p1))) if p1 else 4
            v30 = sum(c for s, p, c in tr if 20 <= s <= 30)
            v45 = sum(c for s, p, c in tr if 20 <= s <= 45)
            n += 1
            vol.append(v30)
            got30 += v30 >= want
            got45 += v45 >= want
        out[lid] = {"days": n, "filled_by_30s": round(got30 / n, 3), "filled_by_45s": round(got45 / n, 3),
                    "median_contracts_20_30s": round(st.median(vol), 1), "walk_filled": round(sum(1 for x in rs if x["leg"] == lid and x.get("n")) / n, 3)}
    return out


def by_week(rs):
    out = {}
    for x in rs:
        if not x.get("n"):
            continue
        k = f"{x['day'].isocalendar()[0]}-W{x['day'].isocalendar()[1]:02d}"
        out.setdefault(k, []).append(x)
    return {k: {"from": str(min(x["day"] for x in v)), "bets": len(v), "won": sum(x["won"] for x in v),
                "avg_price": round(sum(x["price"] for x in v) / len(v), 4), "net_usd": round(sum(x["pnl"] for x in v), 2)}
            for k, v in sorted(out.items())}


def main():
    load()
    rng = random.Random(SEED)
    R = {"prereg": "research/kalshi_k8_live/PREREG.md", "tape_rows": len(D._TAPE), "first": str(FIRST), "last": str(LAST),
         "in_sample_note": "everything through 2026-11-18 is in-sample (the friend picked the windows from it); Nov 19 was seen by the Nov 20 write-up; only Nov 20 is unseen",
         "settings": {}}
    settings = {"2.50_3legs": (2.5, LIVE3), "2.50_gold_only": (2.5, GOLD2), "1.00_3legs": (1.0, LIVE3)}
    for name, (stake, legs) in settings.items():
        rs = rows(stake, legs)
        win = {"full": rs, "last4w": [x for x in rs if x["day"] >= L4_FROM], "oos": [x for x in rs if x["day"] >= OOS_FROM]}
        S = {w: stats(v, legs, rng) for w, v in win.items()}
        hc = haircut(rs)
        hc["usd_week"] = round(hc["usd_per_bet"] * S["full"]["bets_week_planned"] * S["full"]["fill_share"], 2)
        S["haircut"] = hc
        S["per_leg_full"] = {lid: stats([x for x in rs if x["leg"] == lid], (lid,), rng) for lid in legs}
        mc = {}
        for wname, src, flip in (("full", rs, 0.0), ("last4w", win["last4w"], 0.0), ("haircut", rs, hc["flip_prob"])):
            t = day_table(src)
            mc[wname] = {f"{wk}w": sim(t, legs, wk, flip, random.Random(SEED + wk)) for wk in (4, 12)}
        S["monte_carlo"] = mc
        if name == "2.50_3legs":
            S["fills"] = fills(rs)
            S["by_week"] = by_week(rs)
            S["oos_bets"] = [{"day": str(x["day"]), "leg": x["leg"], "won": x["won"], "n": x["n"], "price": x["price"],
                              "pnl": x.get("pnl")} for x in win["oos"]]
        R["settings"][name] = S
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, default=str)
    s = R["settings"]
    for k, v in s.items():
        print(k, {w: (v[w].get("bets"), v[w].get("win_rate"), v[w].get("avg_price"), v[w].get("usd_per_bet"), v[w].get("usd_week"), v[w].get("usd_week_95")) for w in ("full", "last4w", "oos")},
              "haircut", v["haircut"])
        for w, m in v["monte_carlo"].items():
            print("   ", w, m)
    print(json.dumps(s["2.50_3legs"]["fills"]))
    print(json.dumps(s["2.50_3legs"]["by_week"]))
    print(json.dumps(s["2.50_3legs"]["oos_bets"]))


if __name__ == "__main__":
    main()
