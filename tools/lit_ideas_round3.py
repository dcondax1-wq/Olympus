"""LIT ideas round 3 (job 29, 2026-11-04): ideas not in "Tested and rejected" and not in rounds 1 / 2. RESEARCH ONLY: engine/ and live_model*.json
untouched (new level classes live in a subclass of engine.lit.Market in this file).

  levels    weekly open / monthly open / quarterly open / quarterly pivot (P, R1, S1 of the prior quarter) as extra liquidity levels the engine
            can sweep (a new trade list: engine candidates + run_x, like tools/lit_gaps.py extra_levels)
  inside    the prior trading day was an inside day (high under and low over the day before it): size x0.75 / x1.25
  onrange   the overnight range so far at the CISD close (18:00 -> trigger), as a percentile of the same stretch on the last 60 days: size
  cisdbody  the CISD (trigger) candle body in ATR (the displacement body is tested in round 1 as `disp`): size
  lastwin   sessions since LIT's last winner (> 0.5R) when the trade is taken: size after a long drought / right after a win
  season    month-of-year: months picked on 2021-25 (top / bottom 3 by mean R), checked on 2026 H1 / H2; month-label permutation test
  wait      the limit stays valid 3 / 4 / 5 / 7 / 8 / 9 / 12 five-minute bars (live 6 = 30 minutes; 20 / 45 minutes = 4 / 9)
  be        breakeven trigger 0.75 / 0.9 / 1.1 / 1.25 / 1.5 R and the cost cushion (be_off 0.5 / 2.5 / 3.75 pts; live 1.25)
  cut       the 15-minute check at 12 / 18 minutes and its thresholds (x 0.2 / 0.4 R, mfe 0.4 / 0.6 R)

    python -X utf8 tools/lit_ideas_round3.py grid [fam..]   # -> research/lit/ideas_round3_grid.json
    python -X utf8 tools/lit_ideas_round3.py report
Judging: LIT rules (owner 2026-10-18): pick on 2026 Jan-Jun, check on Jul-Oct, 2021-25 a reference; costs in; size tilts shuffle-tested.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pickle
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_ideas_night as N  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402
from engine import lit  # noqa: E402

OUT = os.environ.get("R3_OUT") or os.path.join(ROOT, "research", "lit", "ideas_round3_grid.json")
LIVE = E.LIVE
SPANS = E.SPANS


# ================================================================================================ new level classes
class MarketX(lit.Market):
    """engine.lit.Market + research level classes known at the start of each trading day (no look-ahead):
    wo weekly open, mo monthly open, qo quarterly open (single prices: both a high and a low level), qpiv R1 / S1 and qpp P of the prior quarter."""

    def _extra_levels_ctx(self):
        super()._extra_levels_ctx()
        names = set(self.extra_levels)
        if not names & {"wo", "mo", "qo", "qpiv", "qpp"}:
            return
        h, l, c, o = self.h, self.l, self.c, self.o
        days = self.days
        first_of = {}                                   # (kind, key) -> open of the first trading day with that key
        qhlc = {}
        for k, (d, s, e) in enumerate(days):
            y, m = int(d[:4]), int(d[5:7])
            q = (y, (m - 1) // 3)
            first_of.setdefault(("m", y, m), float(o[s]))
            first_of.setdefault(("q",) + q, float(o[s]))
            r = qhlc.setdefault(q, [-np.inf, np.inf, 0.0])
            r[0], r[1], r[2] = max(r[0], float(h[s:e].max())), min(r[1], float(l[s:e].min())), float(c[e - 1])
        for k, x in enumerate(self.ctx):
            s = x["s"]
            d = x["date"]
            y, m = int(d[:4]), int(d[5:7])
            q = (y, (m - 1) // 3)
            if "wo" in names:
                x["wo"] = (float(self.open_wk[s]), float(self.open_wk[s]))
            if "mo" in names:
                x["mo"] = (first_of[("m", y, m)],) * 2
            if "qo" in names:
                x["qo"] = (first_of[("q",) + q],) * 2
            pq = (y, q[1] - 1) if q[1] > 0 else (y - 1, 3)
            if pq in qhlc and ("qpiv" in names or "qpp" in names):
                H, L, C = qhlc[pq]
                P = (H + L + C) / 3.0
                if "qpp" in names:
                    x["qpp"] = (P, P)
                if "qpiv" in names:
                    x["qpiv"] = (2 * P - L, 2 * P - H)          # R1 (a high level) and S1 (a low level)


_MX = {}


def market_x(levels):
    levels = tuple(sorted(levels))
    if levels in _MX:
        return _MX[levels]
    M = MarketX(extra_boxes=list(LIVE["extra_boxes"]), extra_levels=list(levels))
    p = os.path.join(F.CACHE, f"litr3_{F.CAND_V}_{'-'.join(levels)}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, ref=LIVE["ref"])
        os.makedirs(F.CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    _MX[levels] = (M, C)
    return M, C


def run_levels(levels):
    M, C = market_x(levels)
    P = {**lit.DEFAULTS, **LIVE}
    return lit.run_x(M, C, P, F.SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))


# ================================================================================================ features at the fill
def feature_tilts(U0):
    c = E.ctx()
    M = c["M"]
    T = sorted(c["T"], key=lambda t: t["entry_t"])
    dh = np.array([float(M.h[s:e].max()) for d, s, e in M.days])
    dl = np.array([float(M.l[s:e].min()) for d, s, e in M.days])
    inside, body, onr = {}, {}, {}
    for t in T:
        z = E.zc(t)
        k, i = int(z["k"]), int(z["i"])
        inside[int(t["entry_t"])] = bool(k >= 2 and dh[k - 1] < dh[k - 2] and dl[k - 1] > dl[k - 2])
        body[int(t["entry_t"])] = abs(float(M.c[i] - M.o[i])) / float(M.atr[i]) if M.atr[i] else np.nan
        s = M.days[k][1]
        n = i - s + 1
        cur = float(M.h[s:i + 1].max() - M.l[s:i + 1].min())
        prev = []
        for j in range(max(0, k - 60), k):
            sj, ej, = M.days[j][1], M.days[j][2]
            if sj + n <= ej:
                prev.append(float(M.h[sj:sj + n].max() - M.l[sj:sj + n].min()))
        onr[int(t["entry_t"])] = (np.mean([p < cur for p in prev]) if len(prev) >= 20 else np.nan)
    h1 = [t for t in T if "2026-01-01" <= t["day"] <= "2026-06-30"]

    def terc(d):
        v = np.array([d[int(t["entry_t"])] for t in h1 if d[int(t["entry_t"])] == d[int(t["entry_t"])]], float)
        return float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3))
    blo, bhi = terc(body)
    olo, ohi = terc(onr)
    V = collections.OrderedDict()
    V["inside_dn075"] = (lambda t, r: 0.75 if inside.get(int(t["entry_t"])) else 1.0, "the prior day was an inside day: x0.75", "inside day = chop")
    V["inside_up125"] = (lambda t, r: 1.25 if inside.get(int(t["entry_t"])) else 1.0, "the prior day was an inside day: x1.25", "a coil breaks")
    for nm, d, lo, hi, what in (("cisdbody", body, blo, bhi, "CISD candle body"), ("onrange", onr, olo, ohi, "overnight range percentile")):
        def mk(which, up, dn, d=d, lo=lo, hi=hi):
            def f(t, r):
                v = d.get(int(t["entry_t"]))
                if v is None or v != v:
                    return 1.0
                if which in ("hi", "both") and v >= hi:
                    return up
                if which in ("lo", "both") and v <= lo:
                    return dn
                return 1.0
            return f
        V[f"{nm}_high_up125"] = (mk("hi", 1.25, 1.0), f"{what} in the top third: x1.25", what)
        V[f"{nm}_low_up125"] = (lambda t, r, d=d, lo=lo: 1.25 if (d.get(int(t["entry_t"])) == d.get(int(t["entry_t"])) and d.get(int(t["entry_t"])) <= lo) else 1.0,
                                f"{what} in the bottom third: x1.25", what)
        V[f"{nm}_high_up_low_dn"] = (mk("both", 1.25, 0.75), f"{what}: top third x1.25, bottom third x0.75", what)
    # sessions since LIT's last winner
    order = sorted(U0, key=lambda u: u["entry_t"])
    since = {}
    last_win = None
    sess = [d[0] for d in rl.load("lit_live")["days"]]
    six = {d: i for i, d in enumerate(sess)}
    pend = []
    for u in order:
        done = [x for x in pend if x[0] <= u["entry_t"]]
        for x in done:
            if x[2] > 0.5:
                last_win = x[1]
        pend = [x for x in pend if x[0] > u["entry_t"]]
        since[int(u["entry_t"])] = (six.get(u["day"], 0) - six[last_win]) if last_win in six else None
        pend.append((u["exit_t"], u["day"], u["pts"] / u["risk"] if u["risk"] else 0.0))
    V["drought_up125"] = (lambda t, r: 1.25 if (since.get(int(t["entry_t"])) or 0) >= 6 else 1.0, "no LIT winner for 6+ sessions: x1.25", "a winner is due")
    V["drought_dn075"] = (lambda t, r: 0.75 if (since.get(int(t["entry_t"])) or 0) >= 6 else 1.0, "no LIT winner for 6+ sessions: x0.75", "cold market")
    V["fresh_win_dn075"] = (lambda t, r: 0.75 if (since.get(int(t["entry_t"])) is not None and since[int(t["entry_t"])] <= 1) else 1.0, "LIT won in the last 1 session: x0.75", "give-back")
    V["fresh_win_up125"] = (lambda t, r: 1.25 if (since.get(int(t["entry_t"])) is not None and since[int(t["entry_t"])] <= 1) else 1.0, "LIT won in the last 1 session: x1.25", "hot hand")
    return V


def season_fns(U0):
    """Months picked on 2021-25 (reference years), checked on 2026: top / bottom 3 months by mean R."""
    R = collections.defaultdict(list)
    for u in U0:
        if u["day"] < "2026-01-01" and u["risk"]:
            R[int(u["day"][5:7])].append(u["pts"] / u["risk"])
    prof = {m: float(np.mean(v)) for m, v in R.items() if len(v) >= 10}
    ms = sorted(prof, key=prof.get)
    bot, top = set(ms[:3]), set(ms[-3:])
    V = collections.OrderedDict()
    V["season_pick_up125_dn075"] = (lambda t, r: 1.25 if int(t["day"][5:7]) in top else 0.75 if int(t["day"][5:7]) in bot else 1.0,
                                    f"months picked on 2021-25: top {sorted(top)} x1.25, bottom {sorted(bot)} x0.75", "calendar months repeat")
    V["season_pick_dn_only075"] = (lambda t, r: 0.75 if int(t["day"][5:7]) in bot else 1.0, f"bottom months {sorted(bot)} x0.75 only", "avoid the bad months")
    V["season_pick_up_only125"] = (lambda t, r: 1.25 if int(t["day"][5:7]) in top else 1.0, f"top months {sorted(top)} x1.25 only", "press the good months")
    return V, {"profile_mean_R_2021_25": {str(m): round(v, 3) for m, v in sorted(prof.items())}, "top": sorted(top), "bottom": sorted(bot)}


def season_permutation(U0, fn, n=300, seed=5):
    """Random month groups (3 up, 3 down out of the 12 months) instead of the picked ones: how often does chance gain as much in 2026?"""
    base = E.lit_size(N.trades2({}))
    bsum = {sp: sum(l["pnl"] for l in base if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) for sp in ("H1", "H2")}
    real = E.lit_size(N.trades2({}, mfn=fn))
    rs = {sp: sum(l["pnl"] for l in real if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) - bsum[sp] for sp in ("H1", "H2")}
    rng = np.random.default_rng(seed)
    hit = collections.Counter()
    for _ in range(n):
        pick = rng.permutation(12) + 1
        up, dn = set(pick[:3].tolist()), set(pick[3:6].tolist())
        f = lambda t, r, up=up, dn=dn: 1.25 if int(t["day"][5:7]) in up else 0.75 if int(t["day"][5:7]) in dn else 1.0
        L = E.lit_size(N.trades2({}, mfn=f))
        g = {sp: sum(l["pnl"] for l in L if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) - bsum[sp] for sp in ("H1", "H2")}
        if g["H1"] >= rs["H1"] and g["H2"] >= rs["H2"]:
            hit["both"] += 1
        for sp in ("H1", "H2"):
            if g[sp] >= rs[sp]:
                hit[sp] += 1
    return {"real_gain": {k: round(v) for k, v in rs.items()}, "p_h1": round(hit["H1"] / n, 3), "p_h2": round(hit["H2"] / n, 3), "p_both": round(hit["both"] / n, 3), "draws": n}


# ================================================================================================ the grid
def engine_param_variants():
    V = collections.OrderedDict()
    for w in (3, 4, 5, 7, 8, 9, 12):
        V[f"wait_{w}bars_{w * 5}min"] = {"wait": w}
    return V


def be_variants():
    """Post-fill options (the exits are re-walked by lit_ideas_night.manage2, so these go in as X, not as engine params)."""
    V = collections.OrderedDict()
    for b in (0.75, 0.9, 1.1, 1.25, 1.5):
        V[f"be_trigger_{b}R"] = {"be_r": b}
    for o in (0.5, 2.5, 3.75):
        V[f"be_cushion_{o}pts"] = {"be_off": o}
    for b, o in ((0.75, 2.5), (1.25, 0.5), (0.9, 3.75)):
        V[f"be_trigger_{b}R_cushion_{o}pts"] = {"be_r": b, "be_off": o}
    return V


def cut_variants():
    V = collections.OrderedDict()
    for at in (12, 18):
        V[f"cut_at_{at}"] = {"tc1": {"at": at}}
    for x in (0.2, 0.4):
        V[f"cut_x{x}R"] = {"tc1": {"x": x}}
    for m in (0.4, 0.6):
        V[f"cut_mfe{m}R"] = {"tc1": {"mfe": m}}
    V["cut_at_12_x0.2"] = {"tc1": {"at": 12, "x": 0.2}}
    V["cut_at_18_x0.4"] = {"tc1": {"at": 18, "x": 0.4}}
    return V


def grid(fams=None):
    t0 = time.time()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs
    print(E.line("base", bs), flush=True)
    fams = fams or ["cut", "params", "be", "tilt", "season", "levels"]

    def dump():
        json.dump(res, open(OUT, "w"), indent=1, default=float)

    if "cut" in fams:
        for nm, X in cut_variants().items():
            N.run_variant(res, "cut", nm, bs, L0, X=X)
            dump()
    if "params" in fams:
        for nm, ch in engine_param_variants().items():
            key = f"params:{nm}"
            if key in res:
                continue
            T = F.run({**LIVE, **ch})
            N.run_variant(res, "params", nm, bs, L0, T=T, info={"ch": ch, "n_trades": len(T)})
            dump()
    if "be" in fams:
        for nm, X in be_variants().items():
            N.run_variant(res, "be", nm, bs, L0, X=X)
            dump()
    if "tilt" in fams:
        for nm, (fn, desc, hyp) in feature_tilts(N.trades2({})).items():
            N.run_variant(res, "tilt", nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp})
            dump()
    if "season" in fams:
        V, info = season_fns(N.trades2({}))
        res["_season"] = info
        print(info, flush=True)
        for nm, (fn, desc, hyp) in V.items():
            N.run_variant(res, "season", nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp})
            if nm == "season_pick_up125_dn075":
                res["season:perm"] = season_permutation(N.trades2({}), fn)
                print("month-label permutation", res["season:perm"], flush=True)
            dump()
    if "levels" in fams:
        for nm, lv in (("weekly_open", ["wo"]), ("monthly_open", ["mo"]), ("quarterly_open", ["qo"]), ("quarterly_pivot_R1S1", ["qpiv"]),
                       ("quarterly_pivot_P", ["qpp"]), ("weekly_and_monthly_open", ["wo", "mo"]), ("all_five", ["wo", "mo", "qo", "qpiv", "qpp"])):
            key = f"levels:{nm}"
            if key in res:
                continue
            t1 = time.time()
            try:
                T = run_levels(lv)
            except Exception as ex:  # noqa: BLE001
                res[key] = {"error": f"{type(ex).__name__}: {ex}"[:300]}
                print(key, "ERROR", res[key], flush=True)
                dump()
                continue
            N.run_variant(res, "levels", nm, bs, L0, T=T, info={"levels": lv, "n_trades": len(T), "secs": round(time.time() - t1)})
            dump()
    dump()
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def report():
    res = json.load(open(OUT))
    for k, s in res.items():
        if k in ("base", "_season") or "d_lit" not in s:
            if k.startswith("season:perm") or "error" in (s if isinstance(s, dict) else {}):
                print(k, s)
            continue
        pl = s.get("placebo") or {}
        print(f"{k:42s} dLIT {s['d_lit']['H1']:+7,} {s['d_lit']['H2']:+7,} ref {s['d_lit']['2021-25']:+7,} | dEV {s['d_eval']['H1']:+7,} {s['d_eval']['H2']:+7,} | p10 {tuple(s['d_p10'].values())} f10 {tuple(s['d_f10'].values())} "
              f"| fund {tuple(s['d_fund'].values())} | tpw {s['lit']['H1']['tpw']}/{s['lit']['H2']['tpw']} | chg {tuple(s['chg'].values())} | pl {pl}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "report":
        report()
