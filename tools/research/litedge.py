"""Zlarior (LIT) edge, day helper 2026-11-20 (research/writeups/lit-edge-2026-11-20.md). RESEARCH ONLY, read-only on
the engine. Pre-registered design: research/lit/litedge_design_2026-11-20.md (committed before any run).

Re-uses tools/lit_more_money (executor manage_v, ES helpers, scoring + gate G1-G6) so the numbers line up with the
2026-11-19 batch. Five ideas, one version each: fill_better2, stale_sweep60, news_tgt4, es_room, be_after10.
Plus descriptive studies (fill map, timing map, cold-run anatomy) and a 10-tick cost stress.

    python -X utf8 tools/research/litedge.py check   # options off == live (0 differ)
    python -X utf8 tools/research/litedge.py run     # ideas + stress -> research/lit/litedge.json
    python -X utf8 tools/research/litedge.py study   # fill map, timing map, cold run -> research/lit/litedge_study.json
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_more_money as MM  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "litedge.json")
OUT_S = os.path.join(ROOT, "research", "lit", "litedge_study.json")
ET = MM.ET
TICK, SLIP = lit.TICK, lit.SLIP
LIVE = E.LIVE
SPANS = E.SPANS
IDEAS = ("fill_better2", "stale_sweep60", "news_tgt4", "es_room", "be_after10")
PLAIN = {
    "fill_better2": "Limit order 2 ticks better than today's fill for 1 minute, else market",
    "stale_sweep60": "Skip a setup when the entry comes more than 60 min after the sweep",
    "news_tgt4": "Big-news days: take profit at 4R instead of the far VIX target",
    "es_room": "Trade ES instead of NQ when ES offers 25%+ more reward per risk",
    "be_after10": "No breakeven move in the first 10 minutes of a trade",
}


# ================================================================================================ executor
def manage_b(BX, fill, d, entry, stop, tg, s_day, risk, be_min=None):
    """tools/lit_more_money.manage_v with options off (== live) + be_min: the +1R breakeven may only trigger on a bar
    that ends >= be_min minutes after the fill."""
    LV, BE_OFF = E.LIVE, E.BE_OFF
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LV["flat_mod"]
    tc = LV.get("t_check") if B.secs == 60 else None
    be_r = LV["be_r"]
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        el = (B.t[k] - B.t[fill] + B.secs) / 60.0
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk and (be_min is None or el >= be_min):
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        k += 1
    if exit_px is None:
        return None
    return kind, exit_px - entry, worst, mfe, k


def walk(idea=None, T=None):
    c = E.ctx()
    T = T if T is not None else c["T"]
    nf = MM.news_first() if idea == "news_tgt4" else {}
    out, n_fill, n_chase, n_cap = [], 0, 0, 0
    for t in T:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        s_day = int(B.day[fill])
        if idea == "news_tgt4" and t["day"] in nf:
            z = E.zc(t)
            ep = min(float(z["ref_d"]), z["trig_c"])
            cap = ep + 4.0 * (ep - stop)
            if cap < tg:
                tg = cap
                n_cap += 1
        if idea == "fill_better2" and t["tf"] == 1 and fill + 1 < B.n and B.day[fill + 1] == B.day[fill]:
            hi_d, lo_d, c_d, o_d = B.dirs(d)
            Lp = float(o_d[fill]) - TICK                       # model fill = open + 1 tick; limit 2 ticks better
            if Lp > stop and lo_d[fill] <= Lp - TICK:
                n_fill += 1
                risk = Lp - stop
                if lo_d[fill] <= stop:
                    out.append(MM._unit(t, B, fill, "STOP", stop - SLIP - Lp, lo_d[fill] - Lp, 0.0, Lp, risk, tg, {"fill": "limit"}))
                    continue
                kind, pts, worst, mfe, kx = manage_b(BX, fill + 1, d, Lp, stop, tg, s_day, risk)
                out.append(MM._unit(t, B, kx, kind, pts, min(worst, lo_d[fill] - Lp), mfe, Lp, risk, tg, {"fill": "limit"}))
                continue
            n_chase += 1
            e2 = float(o_d[fill + 1]) + SLIP
            if e2 - stop < 1.0:
                e2 = stop + 1.0
            risk = e2 - stop
            kind, pts, worst, mfe, kx = manage_b(BX, fill + 1, d, e2, stop, tg, s_day, risk)
            out.append(MM._unit(t, B, kx, kind, pts, worst, mfe, e2, risk, tg, {"fill": "chase"}))
            continue
        risk = entry - stop
        r = manage_b(BX, fill, d, entry, stop, tg, s_day, risk, be_min=10 if idea == "be_after10" else None)
        kind, pts, worst, mfe, kx = r
        out.append(MM._unit(t, B, kx, kind, pts, worst, mfe, entry, risk, tg))
    return out, {"limit_filled": n_fill, "chased": n_chase, "news_capped": n_cap}


def stale_trades(mins=60, it=6):
    """Engine re-run skipping setups whose 1m entry comes > mins after the sweep bar (iterated: a freed day can bring a
    later setup that is stale too)."""
    M, C = MM.cands()
    sk, seen = [], set()
    T = F.run({**LIVE})
    for _ in range(it):
        new = []
        for t in T:
            age = (int(t["entry_t"]) - int(M.t[t["sweep_i"]])) / 60.0
            key = (t["day"], int(t["i"]), int(t["dir"]))
            if age > mins and key not in seen:
                new.append(list(key)); seen.add(key)
        if not new:
            break
        sk += new
        T = F.run({**LIVE, "skip_keys": sk})
    return T, len(sk)


def es_room(U0, k=1.25):
    c = E.ctx()
    M = c["M"]
    by_t = {int(t["entry_t"]): t for t in c["T"]}
    out, why = [], collections.Counter()
    for u in U0:
        t = by_t[u["entry_t"]]
        if t["day"] < "2025-04-15":
            out.append(u); continue
        es, w = MM.es_trade_for(t, E.zc(t), M)
        if not es:
            why[w] += 1; out.append(u); continue
        if es["tgt"] / es["risk"] >= k * (u["tgt"] / u["risk"]):
            why["ES"] += 1; out.append(es)
        else:
            why["NQ (ES room not bigger)"] += 1; out.append(u)
    return out, dict(why)


def stress(U, ticks=10):
    """Extra cost of `ticks` ticks a round trip (on top of the model's 1 tick a side + commission)."""
    out = []
    for u in U:
        x = ticks * TICK * (MM.ES_X if u.get("inst") == "ES" else 1.0)
        p = u["pts"] - x
        out.append({**u, "pts": round(p, 4), "legs": [(1.0, p)], "w1": round(min(u["w1"], p), 4)})
    return out


def units_for(name):
    if name in ("fill_better2", "news_tgt4", "be_after10"):
        return walk(name)
    if name == "stale_sweep60":
        T, n = stale_trades()
        U, _ = walk(None, T=T)
        return U, {"skipped_cands": n, "n_trades": {sp: sum(1 for t in T if SPANS[sp][0] <= t["day"] <= SPANS[sp][1]) for sp in SPANS}}
    if name == "es_room":
        return es_room(walk(None)[0])
    raise ValueError(name)


def check():
    U0 = E.trades({})
    W, _ = walk(None)
    bad = sum(1 for a, b in zip(U0, W) if a["exit"] != b["exit"] or abs(a["pts"] - b["pts"]) > 1e-6)
    print(f"check: {len(W)} trades, {bad} differ from tools/lit_edge.trades (options off)")
    return 0 if bad == 0 else 1


def run(names=None):
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res = {"base": bs, "design": "research/lit/litedge_design_2026-11-20.md"}
    print(E.line("base", bs), flush=True)
    for nm in (names or IDEAS):
        U, info = units_for(nm)
        s = MM.score(nm, U, base, L0, info)
        s["plain"] = PLAIN[nm]
        res[nm] = s
    # 10-tick cost stress on the base (and on any pass)
    W, _ = walk(None)
    res["stress10_base"] = MM.score("stress10_base", stress(W), base, L0, {"note": "base with +10 ticks a round trip"})
    for nm in IDEAS:
        if res.get(nm, {}).get("gate", {}).get("PASS"):
            res[f"stress10_{nm}"] = MM.score(f"stress10_{nm}", stress(units_for(nm)[0]), base, L0, {})
    res["passed"] = [k for k in IDEAS if k in res and res[k]["gate"]["PASS"]]
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    print("passed:", res["passed"])
    return res


# ================================================================================================ descriptive studies
def fill_map():
    """2026 1m trades: a limit `off` better than the model fill resting W minutes. Fill share; $ at the LIT size of the
    base trades the limit would MISS (skip if not filled) and the price gain on the ones it fills (approx: same path)."""
    c = E.ctx()
    base = {l["entry_t"]: l for l in E.lit_size(E.trades({}))}
    rows = []
    T = [t for t in c["T"] if t["day"] >= "2026" and t["tf"] == 1]
    for kind, offs in (("ticks", (1, 2, 4, 8)), ("risk", (0.10, 0.25, 0.50))):
        for off in offs:
            for W in (1, 3, 5):
                out = {sp: collections.Counter() for sp in ("H1", "H2")}
                for t in T:
                    B = c[60].B
                    d = t["dir"]
                    f0 = int(np.searchsorted(B.t, t["entry_t"]))
                    hi_d, lo_d, c_d, o_d = B.dirs(d)
                    entry, stop = t["entry_px"] * d, t["stop_px"] * d
                    gap = off * TICK if kind == "ticks" else off * (entry - stop)
                    L = entry - gap
                    seg = [k for k in range(f0, min(f0 + W, B.n)) if B.day[k] == B.day[f0]]
                    filled = any(lo_d[k] <= L - TICK for k in seg)
                    sp = "H1" if t["day"] <= SPANS["H1"][1] else "H2"
                    b = base[int(t["entry_t"])]
                    o = out[sp]
                    o["n"] += 1
                    if filled:
                        o["fill"] += 1
                        o["gain"] += gap * lit.PV * b["qty"]
                        o["fill_pnl"] += b["pnl"]
                    else:
                        o["miss_pnl"] += b["pnl"]
                        o["miss_win"] += 1 if b["pnl"] > 0 else 0
                rows.append({"kind": kind, "off": off, "wait_min": W,
                             **{sp: {"fill_pct": round(100 * o["fill"] / max(1, o["n"]), 1), "n": o["n"],
                                     "missed_trades_usd": round(o["miss_pnl"]), "missed_winners": o["miss_win"],
                                     "price_gain_usd": round(o["gain"]),
                                     "net_if_skip_missed_usd": round(o["gain"] - o["miss_pnl"])} for sp, o in out.items()}})
    return rows


def timing_map():
    c = E.ctx()
    M = c["M"]
    L = [l for l in E.lit_size(E.trades({})) if l["day"] >= "2026"]
    tb = {int(t["entry_t"]): t for t in c["T"]}
    hour = collections.defaultdict(lambda: collections.defaultdict(list))
    age = collections.defaultdict(lambda: collections.defaultdict(list))
    for l in L:
        sp = "H1" if l["day"] <= SPANS["H1"][1] else "H2"
        h = dt.datetime.fromtimestamp(l["entry_t"], ET).hour
        hb = "02-03" if h < 4 else "04-07" if h < 8 else "08-09" if h < 10 else "10-15"
        hour[hb][sp].append(l)
        t = tb[l["entry_t"]]
        a = (l["entry_t"] - int(M.t[t["sweep_i"]])) / 60.0
        ab = "<=20" if a <= 20 else "20-40" if a <= 40 else "40-60" if a <= 60 else ">60"
        age[ab][sp].append(l)

    def agg(D):
        return {k: {sp: {"n": len(v), "usd": round(sum(x["pnl"] for x in v)), "avg_r": round(float(np.mean([x["r"] for x in v])), 2) if v else None}
                    for sp, v in D[k].items()} for k in sorted(D)}
    return {"by_hour_et": agg(hour), "by_minutes_after_sweep": agg(age)}


def cold_run():
    """Twin trades since the eval start (Oct 19) on today's bars + how often the backtest had 7-trade runs this bad."""
    rows = MM.gap()
    tw = [r for r in rows if r["qty_lit"]]
    last7 = tw[-7:]
    s7 = sum(r["pnl_lit"] for r in last7)
    r7 = sum(r["r"] for r in last7)
    w7 = sum(1 for r in last7 if r["pnl_lit"] > 0)
    L = E.lit_size(E.trades({}))
    out = {"twin_since_oct19": tw, "last7_usd": round(s7), "last7_r": round(r7, 2), "last7_winners": w7}
    for nm, sel in (("2026", lambda l: l["day"] >= "2026"), ("2021-26", lambda l: True)):
        X = [l for l in L if sel(l)]
        R = np.array([l["r"] for l in X]); P = np.array([l["pnl"] for l in X])
        n = len(X) - 6
        rw = np.array([R[i:i + 7].sum() for i in range(n)])
        ww = np.array([(P[i:i + 7] > 0).sum() for i in range(n)])
        # longest run without a TARGET
        run = best = 0
        for l in X:
            run = 0 if l["exit"] == "TARGET" else run + 1
            best = max(best, run)
        out[nm] = {"windows": int(n), "share_r_le_last7": round(float((rw <= r7).mean()), 3),
                   "share_wins_le_last7": round(float((ww <= w7).mean()), 3),
                   "share_both": round(float(((rw <= r7) & (ww <= w7)).mean()), 3),
                   "worst7_r": round(float(rw.min()), 2), "longest_no_target": best,
                   "trades": len(X), "target_rate": round(float(np.mean([l["exit"] == "TARGET" for l in X])), 3)}
    # what separated losers from winners in 2026 (base trades)
    c = E.ctx()
    tb = {int(t["entry_t"]): t for t in c["T"]}
    L26 = [l for l in L if l["day"] >= "2026"]
    def grp(v):
        return {"n": len(v), "avg_stop_pts": round(float(np.mean([x["risk"] for x in v])), 1),
                "avg_planned_r": round(float(np.mean([x["tgt"] / x["risk"] for x in v])), 2),
                "avg_mfe_r": round(float(np.mean([x["mfe"] for x in v])), 2),
                "share_before_8et": round(float(np.mean([dt.datetime.fromtimestamp(x["entry_t"], ET).hour < 8 for x in v])), 2),
                "share_long": round(float(np.mean([x["dir"] == 1 for x in v])), 2),
                "avg_depth_atr": round(float(np.mean([float(E.zc(tb[x["entry_t"]])["depth_atr"]) for x in v])), 2)}
    out["anatomy_2026"] = {"winners": grp([l for l in L26 if l["pnl"] > 0]),
                           "losers": grp([l for l in L26 if l["pnl"] <= 0]),
                           "exits": dict(collections.Counter(l["exit"] for l in L26))}
    return out


def study():
    res = {"fill_map": fill_map(), "timing": timing_map(), "cold_run": cold_run()}
    json.dump(res, open(OUT_S, "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in res["cold_run"].items() if k != "twin_since_oct19"}, indent=1, default=float))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        raise SystemExit(check())
    if cmd == "run":
        run(sys.argv[2:] or None)
    elif cmd == "study":
        study()
    else:
        print(__doc__)
