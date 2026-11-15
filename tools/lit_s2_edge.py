"""Team S2 edge (2026-11-15, owner: "make our bot strong; find what other bots have that we don't"). RESEARCH ONLY:
engine/ and live_model*.json untouched. Builds on tools/lit_edge.py + tools/lit_ideas_night.py (same live trades = run
lit_live re-walked exactly, same LIT size rule, same eval path, same funded 50K model, same shuffle placebo).

Eval sizing = the owner's live set of 2026-11-14 (CLAUDE.md): two_week with room_f 0.4, kept past session 10
(two_week_until 999). This worktree's live_model.json still says 0.8 / 10, so the CFG is overridden here (S2_ROOM / S2_UNTIL env).

Six ideas that systematic / prop NQ bots use and that "Tested and rejected" + the LIT idea rounds 1-3 have not covered
(hypotheses written BEFORE the run; cut points = Jan-Jun 2026 terciles; each pair counted as a test):
  thin     thin-liquidity calendar days (NYSE holiday sessions on Globex, the session before / after one, early closes
           Jul 3 / Black Friday / Dec 24, the Dec 24 - Jan 2 stretch): size x0.5 or skip the day
  roll     the quarterly contract roll window (5 sessions before the roll switch day through the last trading day,
           data/NQ_rolls.json): size x0.75 or skip
  opex     monthly options-expiry week / OpEx Friday / quarterly (quad witching) week x0.75; turn of the month
           (last session + first 3) x1.25
  rs       NQ vs ES relative strength from the 18:00 open to the fill, signed by the trade's direction
           (data/ES_5m.csv, 2025-04 on): NQ leading x1.25 / lagging x0.75
  dayext   level quality: the sweep's extreme is the new low / high of the trading day (or of the week) so far
           x1.25; an interior sweep x0.75
  reach    target reachability: target points / (5m ATR x sqrt(5m bars left to 15:55)): easy x1.25 / hard x0.75
  recheck  the Nov 4 candidate (stop tight vs 5m ATR x1.25) under today's room_f 0.4 sizing

  python -X utf8 tools/lit_s2_edge.py grid [fam..]   # -> research/lit/s2_edge_grid.json
  python -X utf8 tools/lit_s2_edge.py report
  python -X utf8 tools/lit_s2_edge.py save           # rl.save runs lit_s2_* (base + the best per family)
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_ideas_night as N  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.environ.get("S2_OUT") or os.path.join(ROOT, "research", "lit", "s2_edge_grid.json")
SPANS = E.SPANS
ROOM = float(os.environ.get("S2_ROOM", "0.4"))
UNTIL = int(os.environ.get("S2_UNTIL", "999"))
A.CFG = {**A.CFG, "two_week": {**A.CFG["two_week"], "room_f": ROOM}, "two_week_until": UNTIL}


# ================================================================================================ calendars
def nth_weekday(y, m, wd, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta((wd - d.weekday()) % 7)
    return d + dt.timedelta(7 * (n - 1))


def last_weekday(y, m, wd):
    d = dt.date(y, m + 1, 1) - dt.timedelta(1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta((d.weekday() - wd) % 7)


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mo = (h + l_ - 7 * m + 114) // 31
    da = ((h + l_ - 7 * m + 114) % 31) + 1
    return dt.date(y, mo, da)


def observed(d):
    return d - dt.timedelta(1) if d.weekday() == 5 else d + dt.timedelta(1) if d.weekday() == 6 else d


def nyse_holidays(y):
    H = {observed(dt.date(y, 1, 1)), nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), easter(y) - dt.timedelta(2),
         last_weekday(y, 5, 0), observed(dt.date(y, 7, 4)), nth_weekday(y, 9, 0, 1), nth_weekday(y, 11, 3, 4),
         observed(dt.date(y, 12, 25))}
    if y >= 2022:
        H.add(observed(dt.date(y, 6, 19)))
    return H


def thin_days():
    """Session date -> reason, for the thin-liquidity calendar (known in advance: no look-ahead)."""
    S = list(F.SESS)
    hol = set()
    for y in range(2021, 2028):
        hol |= {str(d) for d in nyse_holidays(y)}
    out = {}
    for k, d in enumerate(S):
        if d in hol:
            out[d] = "holiday session (cash closed)"
        y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        D = dt.date(y, m, dd)
        if (m == 12 and dd >= 24) or (m == 1 and dd <= 2):
            out.setdefault(d, "Dec 24 - Jan 2")
        if (m == 7 and dd == 3 and D.weekday() < 5) or D == nth_weekday(y, 11, 3, 4) + dt.timedelta(1):
            out.setdefault(d, "early close")
        nxt = S[k + 1] if k + 1 < len(S) else None
        prv = S[k - 1] if k > 0 else None
        if nxt in hol or (D + dt.timedelta(1)).isoformat() in hol or (D.weekday() == 4 and (D + dt.timedelta(3)).isoformat() in hol):
            out.setdefault(d, "day before a holiday")
        if prv in hol or (D - dt.timedelta(1)).isoformat() in hol or (D.weekday() == 0 and (D - dt.timedelta(3)).isoformat() in hol):
            out.setdefault(d, "day after a holiday")
    return out


def roll_days(pre=5):
    R = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))["rolls"]
    S = list(F.SESS)
    six = {d: i for i, d in enumerate(S)}
    out = set()
    for r in R:
        sw = r.get("switch_day")
        ltd = r.get("ltd")
        if not sw:
            continue
        k = six.get(sw)
        if k is None:
            k = int(np.searchsorted(np.array(S), sw))
        a = max(0, k - pre)
        for d in S[a:]:
            if d > max(ltd or sw, sw):
                break
            out.add(d)
    return out


def opex_sets():
    S = list(F.SESS)
    opx, wk, quad = set(), set(), set()
    for y in range(2021, 2028):
        for m in range(1, 13):
            f = nth_weekday(y, m, 4, 3)
            opx.add(str(f))
            for j in range(5):
                d = str(f - dt.timedelta(4 - j))
                wk.add(d)
                if m in (3, 6, 9, 12):
                    quad.add(d)
    # an OpEx Friday that is a holiday (Good Friday) -> the Thursday before
    sset = set(S)
    opx = {d if d in sset else str(dt.date.fromisoformat(d) - dt.timedelta(1)) for d in opx}
    tom = set()
    by_m = collections.defaultdict(list)
    for d in S:
        by_m[d[:7]].append(d)
    for m, ds in by_m.items():
        tom |= set(ds[:3])
        tom.add(ds[-1])
    return opx, wk, quad, tom


# ================================================================================================ features at the fill
def es_bars():
    import csv
    t, c, o = [], [], []
    with open(os.path.join(ROOT, "data", "ES_5m.csv"), encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd)
        for r in rd:
            t.append(int(r[0])); o.append(float(r[1])); c.append(float(r[4]))
    return np.array(t), np.array(o), np.array(c)


def features():
    """entry_t -> facts known at the fill (closed bars only)."""
    c = E.ctx()
    M = c["M"]
    T = sorted(c["T"], key=lambda t: t["entry_t"])
    et, eo, ec = es_bars()
    out = {}
    for t in T:
        z = E.zc(t)
        k, i, x_i = int(z["k"]), int(z["i"]), int(z["ext_i"])
        x = M.ctx[k]
        s = x["s"]
        d = int(t["dir"])
        f = {}
        # NQ vs ES from the 18:00 open to the last closed 5m bar before the fill
        j = int(np.searchsorted(M.t, int(t["entry_t"]) - 300, side="right")) - 1   # last 5m bar CLOSED at the fill
        j = max(j, s)
        t0, t1 = int(M.t[s]), int(M.t[j])
        a0 = int(np.searchsorted(et, t0))
        a1 = int(np.searchsorted(et, t1, side="right")) - 1
        if a0 < len(et) and et[a0] == t0 and a1 > a0 and abs(et[a1] - t1) <= 600:
            rn = math.log(float(M.c[j]) / float(M.o[s]))
            re = math.log(float(ec[a1]) / float(eo[a0]))
            f["rs"] = d * (rn - re) * 1e4                                   # bp, + = NQ leads in the trade's direction
        # level quality: the sweep extreme vs the day's / week's range so far (before the extreme bar)
        if d == 1:
            prior = float(M.l[s:x_i].min()) if x_i > s else np.inf
            f["dayext"] = bool(float(M.l[x_i]) <= prior)
        else:
            prior = float(M.h[s:x_i].max()) if x_i > s else -np.inf
            f["dayext"] = bool(float(M.h[x_i]) >= prior)
        f["wkext"] = bool(z.get("wk_ext"))
        # target reachability
        row = c["intel"].get(int(t["entry_t"]), {})
        atr = E.atr5_at(int(t["entry_t"]))
        et_dt = dt.datetime.fromtimestamp(int(t["entry_t"]), dt.timezone.utc) - dt.timedelta(hours=5)
        emin = E._num(row.get("entry_min"), np.nan)
        if emin != emin:
            emin = et_dt.hour * 60 + et_dt.minute
        left = 955 - emin if emin <= 955 else np.nan
        tg = abs(float(t["target_px"]) - float(t["entry_px"]))
        if atr and left == left and left > 0:
            f["reach"] = tg / (atr * math.sqrt(left / 5.0))
        f["stop_atr"] = E._num(row.get("stop_atr"), np.nan)
        out[int(t["entry_t"])] = f
    return out


def tercile(Fe, key):
    v = np.array([Fe[int(t["entry_t"])][key] for t in E.ctx()["T"] if "2026-01-01" <= t["day"] <= "2026-06-30"
                  and key in Fe[int(t["entry_t"])] and Fe[int(t["entry_t"])][key] == Fe[int(t["entry_t"])][key]], float)
    return float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3)), len(v)


def tilts():
    Fe = features()
    V = collections.OrderedDict()
    TD = thin_days()
    RD = roll_days()
    OPX, OWK, QWK, TOM = opex_sets()
    g = lambda t: Fe.get(int(t["entry_t"]), {})
    V["thin:thin_x0.5"] = (lambda t, r: 0.5 if t["day"] in TD else 1.0, "thin-liquidity calendar day x0.5", "holiday-thin books = random sweeps")
    V["thin:thin_x0.75"] = (lambda t, r: 0.75 if t["day"] in TD else 1.0, "thin-liquidity calendar day x0.75", "same, milder")
    V["roll:roll_x0.75"] = (lambda t, r: 0.75 if t["day"] in RD else 1.0, "roll window x0.75", "split liquidity across two contracts")
    V["roll:roll_x0.5"] = (lambda t, r: 0.5 if t["day"] in RD else 1.0, "roll window x0.5", "same, stronger")
    V["opex:opexwk_x0.75"] = (lambda t, r: 0.75 if t["day"] in OWK else 1.0, "monthly OpEx week x0.75", "dealer pinning damps follow-through")
    V["opex:opexday_x0.5"] = (lambda t, r: 0.5 if t["day"] in OPX else 1.0, "OpEx Friday x0.5", "pinning on expiry day")
    V["opex:quadwk_x0.75"] = (lambda t, r: 0.75 if t["day"] in QWK else 1.0, "quad-witching week x0.75", "the big expiries")
    V["opex:tom_x1.25"] = (lambda t, r: 1.25 if t["day"] in TOM else 1.0, "turn of the month x1.25", "month-start flows trend")
    lo, hi, n = tercile(Fe, "rs")
    V["rs:lead_x1.25"] = (lambda t, r: 1.25 if g(t).get("rs", np.nan) >= hi else 1.0, f"NQ leads ES in the trade's way (>= {hi:.0f} bp) x1.25", "relative strength confirms")
    V["rs:lag_x0.75"] = (lambda t, r: 0.75 if g(t).get("rs", np.nan) <= lo else 1.0, f"NQ lags ES (<= {lo:.0f} bp) x0.75", "fighting the leader")
    V["rs:both"] = (lambda t, r: 1.25 if g(t).get("rs", np.nan) >= hi else 0.75 if g(t).get("rs", np.nan) <= lo else 1.0, "lead x1.25 / lag x0.75", "both")
    V["dayext:dayext_x1.25"] = (lambda t, r: 1.25 if g(t).get("dayext") else 1.0, "sweep extreme = new day low / high so far x1.25", "all the day's stops taken")
    V["dayext:interior_x0.75"] = (lambda t, r: 0.75 if not g(t).get("dayext") else 1.0, "interior sweep x0.75", "partial liquidity")
    V["dayext:wkext_x1.25"] = (lambda t, r: 1.25 if g(t).get("wkext") else 1.0, "sweep extreme = new week low / high x1.25", "weekly stops taken")
    lo2, hi2, _ = tercile(Fe, "reach")
    V["reach:easy_x1.25"] = (lambda t, r: 1.25 if g(t).get("reach", np.nan) <= lo2 else 1.0, f"target easy (<= {lo2:.2f}) x1.25", "time to get there")
    V["reach:hard_x0.75"] = (lambda t, r: 0.75 if g(t).get("reach", np.nan) >= hi2 else 1.0, f"target hard (>= {hi2:.2f}) x0.75", "too far for the time left")
    V["reach:both"] = (lambda t, r: 1.25 if g(t).get("reach", np.nan) <= lo2 else 0.75 if g(t).get("reach", np.nan) >= hi2 else 1.0, "easy x1.25 / hard x0.75", "both")
    lo3, hi3, _ = tercile(Fe, "stop_atr")
    V["recheck:stopatr_tight_x1.25"] = (lambda t, r: 1.25 if g(t).get("stop_atr", np.nan) <= lo3 else 1.0, "stop tight in 5m ATR (Nov 4 candidate) x1.25", "re-check at room 0.4")
    info = {"thin_days": len(TD), "thin_2026": sorted(d for d in TD if d >= "2026"), "roll_days": len(RD),
            "rs_terciles": [lo, hi, n], "reach_terciles": [lo2, hi2], "stop_atr_terciles": [lo3, hi3],
            "n_rs_2026": sum(1 for t in E.ctx()["T"] if t["day"] >= "2026" and "rs" in g(t)),
            "n_rs_total": sum(1 for t in E.ctx()["T"] if "rs" in g(t)),
            "dayext_share_2026": round(float(np.mean([bool(g(t).get("dayext")) for t in E.ctx()["T"] if t["day"] >= "2026"])), 3),
            "wkext_share_2026": round(float(np.mean([bool(g(t).get("wkext")) for t in E.ctx()["T"] if t["day"] >= "2026"])), 3)}
    sk = collections.OrderedDict()
    sk["thin:thin_skip"] = (lambda t: t["day"] in TD, "skip thin-liquidity days")
    sk["roll:roll_skip"] = (lambda t: t["day"] in RD, "skip the roll window")
    sk["opex:opexday_skip"] = (lambda t: t["day"] in OPX, "skip OpEx Friday")
    return V, sk, info


def counts(fn):
    T = E.ctx()["T"]
    o = {}
    for sp, (a, z) in SPANS.items():
        o[sp] = sum(1 for t in T if a <= t["day"] <= z and abs(fn(t, {}) - 1.0) > 1e-9)
    return o


def grid(fams=None):
    t0 = time.time()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs
    res["_cfg"] = {"room_f": ROOM, "two_week_until": UNTIL}
    print(E.line("base", bs), flush=True)
    V, SK, info = tilts()
    res["_info"] = info
    print(info, flush=True)

    def dump():
        json.dump(res, open(OUT, "w"), indent=1, default=float)

    for key, (fn, desc, hyp) in V.items():
        fam, nm = key.split(":")
        if fams and fam not in fams:
            continue
        s = N.run_variant(res, fam, nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp, "touched": counts(fn)})
        dump()
    T = E.ctx()["T"]
    for key, (drop, desc) in SK.items():
        fam, nm = key.split(":")
        if fams and fam not in fams:
            continue
        TT = [t for t in T if not drop(t)]
        N.run_variant(res, fam, nm, bs, L0, T=TT, info={"desc": desc, "dropped": {sp: sum(1 for t in T if a <= t["day"] <= z and drop(t))
                                                                                    for sp, (a, z) in SPANS.items()}})
        dump()
    dump()
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def verdict(s):
    if "d_lit" not in s:
        return ""
    pl = s.get("placebo") or {}
    g = E.gate(s)
    ok_pl = isinstance(pl, dict) and pl.get("p_h1", 1) < 0.1 and pl.get("p_h2", 1) < 0.1
    return "CANDIDATE" if g and (ok_pl or "p_h1" not in pl and "skipped" not in pl) else "gate-only (chance)" if g else "rejected"


def report():
    res = json.load(open(OUT))
    b = res["base"]
    print("cfg", res.get("_cfg"), "info", {k: v for k, v in res.get("_info", {}).items() if k != "thin_2026"})
    print(E.line("base", b))
    for k, s in res.items():
        if k.startswith("_") or k == "base" or "d_lit" not in s:
            continue
        pl = s.get("placebo") or {}
        ev = s["eval"]
        print(f"{k:30s} dLIT {s['d_lit']['H1']:+7,} {s['d_lit']['H2']:+7,} ref {s['d_lit']['2021-25']:+7,} | dEV {s['d_eval']['H1']:+7,} "
              f"{s['d_eval']['H2']:+7,} | 2w {ev['H1']['p10']}/{ev['H1']['f10']} {ev['H2']['p10']}/{ev['H2']['f10']} | fund "
              f"{tuple(s['d_fund'].values())} | tpw {s['lit']['H1']['tpw']}/{s['lit']['H2']['tpw']} | chg {tuple(s['chg'].values())} | "
              f"pl {pl} | {verdict(s)}")


def save():
    """Store the base and one run per family (best H1 $ at the LIT size + eval path) + the reach lead in the run library."""
    from tools import runlib as rl
    res = json.load(open(OUT))
    V, SK, _ = tilts()
    T = E.ctx()["T"]
    best = {}
    for k, s in res.items():
        if k.startswith("_") or k == "base" or "d_lit" not in s or k.startswith("robust:"):
            continue
        fam = k.split(":")[0]
        sc = s["d_eval"]["H1"] + s["d_lit"]["H1"]
        if fam not in best or sc > best[fam][1]:
            best[fam] = (k, sc)
    keys = ["base"] + [k for k, _ in best.values()]
    if "reach:easy_x1.25" not in keys:
        keys.append("reach:easy_x1.25")
    for k in keys:
        s = res[k]
        if k == "base":
            U = N.trades2({})
        elif k in V:
            U = N.trades2({}, mfn=V[k][0])
        else:
            drop = SK[k][0]
            U = N.trades2({}, T=[t for t in T if not drop(t)])
        L = [{kk: (v.item() if isinstance(v, np.generic) else v) for kk, v in l.items()} for l in E.lit_size(U)]
        S = rl.score(L, F.SESS)
        h = lambda sp: f"PF {s['lit'][sp]['pf']} net {s['lit'][sp]['net']:+,} (${s['lit'][sp]['per_month']:,}/mo) {s['lit'][sp]['tpw']}/wk"
        e = lambda sp: (f"PF {s['eval'][sp]['pf']} net {s['eval'][sp]['net']:+,} 2w {s['eval'][sp]['p10']}/{s['eval'][sp]['f10']} "
                        f"dec10 {s['eval'][sp]['dec10']} med {s['eval'][sp]['pass_med']}")
        ver = (f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}. Eval path (two_week room_f {ROOM}, kept past "
               f"session 10): H1 {e('H1')}; H2 {e('H2')}. Funded 50K $/mo H1 {s['fund']['H1']['per_month']} / H2 "
               f"{s['fund']['H2']['per_month']}. Placebo {s.get('placebo')}.")
        v = verdict(s)
        st = "info" if k == "base" else "promising" if v == "CANDIDATE" else "rejected"
        rid = "lit_s2_" + k.replace(":", "_").replace(".", "p")
        rl.save(rid, f"S2 edge (2026-11-15): {k}", "other", "Team S2: what other NQ / prop bots use that LIT has not tested",
                params={"x_s2": k, "desc": (s.get("info") or {}).get("desc")}, trades=L, scored=S, status=st, verdict=ver,
                notes="tools/lit_s2_edge.py: live LIT trades (== lit_live), LIT size rule x tilt; eval = two_week room_f 0.4; funded 50K",
                writeup="2026-11-15-s2-edge", tags=["lit", "s2_edge"])
        print("saved", rid, st, flush=True)


def robust():
    """Neighbours and decomposition of the reach tilt (cut share, multiplier, the formula's parts), + overlap with stop_atr."""
    res = json.load(open(OUT))
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    Fe = features()
    T = E.ctx()["T"]
    h1 = [t for t in T if "2026-01-01" <= t["day"] <= "2026-06-30"]
    for t in T:
        f = Fe[int(t["entry_t"])]
        row = E.ctx()["intel"].get(int(t["entry_t"]), {})
        atr = E.atr5_at(int(t["entry_t"]))
        f["tgt_atr"] = abs(float(t["target_px"]) - float(t["entry_px"])) / atr if atr else np.nan
        em = E._num(row.get("entry_min"), np.nan)
        f["left"] = (955 - em) if em == em else np.nan
        f["tgt_r"] = abs(float(t["target_px"]) - float(t["entry_px"])) / abs(float(t["entry_px"]) - float(t["stop_px"]))

    def q(key, p):
        v = np.array([Fe[int(t["entry_t"])].get(key, np.nan) for t in h1], float)
        return float(np.nanquantile(v, p))

    def mk(key, cut, m, low=True):
        def f(t, r):
            v = Fe.get(int(t["entry_t"]), {}).get(key, np.nan)
            if v != v:
                return 1.0
            return m if ((v <= cut) if low else (v >= cut)) else 1.0
        return f
    V = collections.OrderedDict()
    for p in (0.25, 0.4, 0.5):
        V[f"reach_easy_q{int(p * 100)}_x1.25"] = mk("reach", q("reach", p), 1.25)
    for m in (1.15, 1.5):
        V[f"reach_easy_q33_x{m}"] = mk("reach", q("reach", 1 / 3), m)
    V["tgt_atr_low_q33_x1.25"] = mk("tgt_atr", q("tgt_atr", 1 / 3), 1.25)
    V["time_left_high_q67_x1.25"] = mk("left", q("left", 2 / 3), 1.25, low=False)
    V["tgt_r_low_q33_x1.25"] = mk("tgt_r", q("tgt_r", 1 / 3), 1.25)
    lo3 = q("stop_atr", 1 / 3)
    lo2 = q("reach", 1 / 3)
    ez = lambda t: Fe[int(t["entry_t"])].get("reach", 9) <= lo2
    ti = lambda t: Fe[int(t["entry_t"])].get("stop_atr", 9) <= lo3
    V["reach_easy_not_tightstop_x1.25"] = lambda t, r: 1.25 if (ez(t) and not ti(t)) else 1.0
    V["reach_easy_or_tightstop_x1.25"] = lambda t, r: 1.25 if (ez(t) or ti(t)) else 1.0
    ov = collections.Counter((ez(t), ti(t)) for t in T if t["day"] >= "2026")
    res["_robust_overlap_2026"] = {f"easy={a},tight={b}": n for (a, b), n in ov.items()}
    print(res["_robust_overlap_2026"])
    for nm, fn in V.items():
        N.run_variant(res, "robust", nm, bs, L0, mfn=fn, plc=True, info={"touched": counts(fn)})
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    for sp, (a, z) in SPANS.items():
        easy = [l for l in L0 if a <= l["day"] <= z and Fe[l["entry_t"]].get("reach", 9) <= lo2]
        rest = [l for l in L0 if a <= l["day"] <= z and not Fe[l["entry_t"]].get("reach", 9) <= lo2]
        mr = lambda X: round(float(np.mean([x["r"] for x in X])), 3) if X else None
        wr = lambda X: round(100 * float(np.mean([x["pnl"] > 0 for x in X])), 1) if X else None
        res[f"_robust_easy_{sp}"] = {"n_easy": len(easy), "meanR_easy": mr(easy), "win_easy": wr(easy), "n_rest": len(rest),
                                     "meanR_rest": mr(rest), "win_rest": wr(rest)}
        print(sp, res[f"_robust_easy_{sp}"])
    json.dump(res, open(OUT, "w"), indent=1, default=float)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "report":
        report()
    elif cmd == "save":
        save()
    elif cmd == "info":
        print(tilts()[2])
    elif cmd == "robust":
        robust()
