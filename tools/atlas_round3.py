"""ATLAS round 3 (job 30, 2026-11-04): what raises the ATLAS FUNDED 25K's $ a month without raising the eval fail rate.
RESEARCH ONLY: engine/, second_model.json, live_model*.json untouched. Builds on tools/atlas_funded.py (the funded account: engine/account_b.qty on
the funded spec, the EOD trailing $1,000 floor locked at start + $100, the MFFU tracker engine/funded_life.track for payouts: $1,100 buffer, request
$250-$1,000, best day <= 50% of the cycle, 2 traded days a cycle, 5 payouts, 80% to the owner) and tools/atlas.py / atlas_v2.py (the members and the
real eval rules).

Why $582 / $517 a month: the funded 25K MAKES about $1,500 a month of trading profit but a sim-funded account pays at most 5 requests of $1,000 (80% to
you = $4,000), only when the best day is <= 50% of the cycle's profit, and "ask" at $750 above the buffer. So the lever is not more profit per trade;
it is (a) how fast the 5 payouts come (the 50% rule blocks the request ~45 sessions of 126), (b) how big each request is, (c) not getting stuck / lost.

Funded-phase knobs (all on the same ATLAS trades; the eval is unchanged, so eval p10 / f10 = today's):
  ask    the ask line above the buffer (live 750): the request is made once this much sits above the buffer
  win    the winner cap in the funded size rule (live $1,000)         size   pct of the room / $ cap per trade (live 60% / $750)
  dayTP  no new trade once the day is up $X                           maxday trades a day (live 2)
  dyn    consistency-aware winner cap: a trade's target $ may not exceed what the cycle already holds (max(floor, others)) so no day breaks the 50% rule
  part   half off at +X R (from the stored trade path), the rest as stored
Trade-set knobs (eval re-scored with tools/atlas_v2.score = the real account-B eval rules):
  hunts  the two stop-hunt members at half size (an Asia / any-hour window ATLAS does not trade)       exits  member target banking (SR / EMA / MACD)

    python -X utf8 tools/atlas_round3.py base          # checks the replay against research/second/atlas_funded.json
    python -X utf8 tools/atlas_round3.py grid [fam..]  # -> research/second/atlas_round3.json
    python -X utf8 tools/atlas_round3.py report
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import atlas_funded as AF  # noqa: E402
from tools import atlas as A  # noqa: E402
from tools import second_mix as M  # noqa: E402
from engine import funded_life as FL  # noqa: E402

OUT = os.environ.get("AR3_OUT") or os.path.join(ROOT, "research", "second", "atlas_round3.json")
P0 = dict(AF.P)
PV, ECOMM, SLIP = M.PV, M.ECOMM, M.SLIP
SPANS = ("H1", "H2")
N_MC = int(os.environ.get("AR3_N", "500"))
N_LIFE = int(os.environ.get("AR3_NLIFE", "250"))
PRICE = 43.0
SHARD = tuple(int(x) for x in os.environ["AR3_SHARD"].split("/")) if os.environ.get("AR3_SHARD") else None
OVERHEAD = 7                     # sessions between a funded account ending and the next one trading (eval ~5 + 2 paperwork)
BASE_K = {"ask": P0["ask_above"], "max_day": 2, "day_tp": None, "cfg": None, "dyn": None, "part": None}


# ================================================================================================ sizing
def qfn_for(K):
    cfg = {**AF.CFG["funded"], **(K.get("cfg") or {})}
    base = AF.q_rule(cfg)
    dyn = K.get("dyn")
    if not dyn:
        return base

    def q(t, st):
        n = base(t, st)
        if n <= 1:
            return n
        others = max(0.0, float(st.get("cyc_profit", 0.0)))
        cap = max(float(dyn["floor"]), float(dyn["k"]) * others)
        return max(1, min(n, int(cap / max(1.0, float(t["tgt"]) * PV))))
    return q


def part_adjust(t, part):
    """half (f) off at +X R from the stored path (bar opens), the rest as stored; no path (Asia / hunt units) = unchanged."""
    if not part or not len(t.get("pt", ())):
        return t["pts"], t["w1"]
    f, X = part["f"], part["r"]
    lvl = X * float(t["risk"])
    if float(np.max(t["po"])) >= lvl:
        return f * lvl + (1.0 - f) * float(t["pts"]), t["w1"]
    return t["pts"], t["w1"]


def play_day2(L, bal, floor, qfn, K, extra):
    cum, busy, n, recs = 0.0, 0, 0, []
    dll = float(P0["dll"])
    for t in L:
        if cum <= -dll:
            break
        if K["day_tp"] and cum >= K["day_tp"]:
            break
        if t["entry_t"] < busy or n >= K["max_day"]:
            continue
        st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": 99, "n_today": 0, **extra}
        q = qfn(t, st)
        if q <= 0:
            continue
        pts, w1 = part_adjust(t, K["part"])
        pnl = pts * PV * q - ECOMM * q
        low = min(0.0, w1 * PV * q - ECOMM * q, pnl)
        if cum + low <= -dll:
            pnl = low = -dll - cum - SLIP * PV * q
        recs.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "exit": t["exit"], "pnl": round(pnl, 2), "qty": q,
                     "risk": t["risk"], "risk_usd": round(t["risk"] * PV * q, 2), "src": t["src"]})
        busy = t["exit_t"]
        n += 1
        if bal + cum + low <= floor:
            return cum, recs, True
        cum += pnl
    return cum, recs, False


def account2(by, seq, K, keep=None):
    """AF.account with the knobs: -> lost / grad / stuck / payouts [(session, to_owner)] / made / n trades / end session."""
    Pk = {**P0, "ask_above": float(K["ask"])}
    qfn = qfn_for(K)
    bal = peak = 0.0
    floor = -float(P0["mll"])
    lock = float(P0["lock"])
    days, pays = {}, {}
    out = {"lost": None, "grad": None, "stuck": None, "pay_at": [], "first": None, "n": 0, "end": len(seq), "made": 0.0, "cons_block": 0}
    last = ""
    for k, day in enumerate(seq):
        cd = AF.cal(k)
        cyc = [v for d, v in days.items() if d > last]
        extra = {"locked": floor >= lock - 1e-9, "cyc_profit": sum(cyc), "cyc_best": max(cyc) if cyc else 0.0}
        cum, recs, failed = play_day2(by.get(day, ()), bal, floor, qfn, K, extra)
        out["n"] += len(recs)
        if keep is not None:
            keep.extend(recs)
        if failed:
            out["lost"], out["end"] = k + 1, k + 1
            return out
        bal += cum
        out["made"] += cum
        if recs:
            days[cd] = round(cum, 2)
        peak = max(peak, bal)
        floor = min(max(floor, peak - float(P0["mll"])), lock)
        if bal - floor < AF.EAB.MIN_ROOM:
            out["stuck"], out["end"] = k + 1, k + 1
            return out
        tr = FL.track(days, pays, Pk, today=cd)
        if tr["status"] == "consistency" and tr["above_buffer"] >= Pk["ask_above"]:
            out["cons_block"] += 1
        if tr["status"] == "ready":
            amt = float(tr["max_request"])
            pays[cd] = amt
            last = cd
            bal -= amt
            floor = max(floor, lock)
            out["pay_at"].append((k + 1, amt * P0["split"]))
            out["first"] = out["first"] or k + 1
            if len(pays) >= P0["max_payouts"]:
                out["grad"], out["end"] = k + 1, k + 1
                return out
    return out


def sessions(span):
    return AF.span_sessions(span)


def mc2(by, span, K, n=N_MC, length=126, seed=23, keep_n=120):
    S = sessions(span)
    rng = np.random.default_rng(seed)
    R, T = [], []
    for i in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(0, len(S) - 5 + 1))
            s.extend(S[b:b + 5])
        R.append(account2(by, s[:length], K, keep=T if i < keep_n else None))
    paid = [sum(x for k, x in r["pay_at"]) for r in R]
    fr = [r["first"] for r in R if r["first"]]
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    return {"paid_per_month": round(float(np.mean(paid)) / 6.0), "paid_p10_per_month": round(float(np.percentile(paid, 10)) / 6.0),
            "lost_pct": round(100.0 * sum(1 for r in R if r["lost"]) / n, 1),
            "stuck_pct": round(100.0 * sum(1 for r in R if r["stuck"] and not r["lost"]) / n, 1),
            "grad_pct": round(100.0 * sum(1 for r in R if r["grad"]) / n, 1),
            "payouts_6m": round(float(np.mean([len(r["pay_at"]) for r in R])), 2),
            "first_med": float(np.median(fr)) if fr else None, "any_pay_pct": round(100.0 * len(fr) / n, 1),
            "made_per_month": round(float(np.mean([r["made"] for r in R])) / 6.0),
            "trades_per_week": round(float(np.mean([r["n"] / max(1, r["end"]) * 5 for r in R])), 2),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "cons_block_days": round(float(np.mean([r["cons_block"] for r in R])), 1)}


def life2(by, span, K, p_pass, n=N_LIFE, length=330, seed=31):
    """Renewal view: funded accounts back to back (an ended account is replaced after OVERHEAD sessions of eval + paperwork; the eval costs $43 / pass rate):
    $ a month to you net of eval fees = (E[paid] - fee) / (E[sessions of a funded account] + OVERHEAD) x 21."""
    S = sessions(span)
    rng = np.random.default_rng(seed)
    paid, ends, outc = [], [], collections.Counter()
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(0, len(S) - 5 + 1))
            s.extend(S[b:b + 5])
        r = account2(by, s[:length], K)
        paid.append(sum(x for k, x in r["pay_at"]))
        ends.append(r["end"])
        outc["grad" if r["grad"] else "lost" if r["lost"] else "stuck" if r["stuck"] else "open"] += 1
    fee = PRICE / max(0.05, p_pass)
    e_paid, e_end = float(np.mean(paid)), float(np.mean(ends))
    return {"paid_per_account": round(e_paid), "sessions_per_account": round(e_end, 1), "end_mix": dict(outc),
            "net_per_month_cycling": round((e_paid - fee) / (e_end + OVERHEAD) * 21.0)}


# ================================================================================================ variants
def base_by(V):
    U = A.account_units(V)
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    return by


def funded_variants():
    V = collections.OrderedDict()
    V["today"] = {}
    for a in (250, 500, 1000, 1250):
        V[f"ask_{a}"] = {"ask": a}
    for w in (600, 1500, 2000):
        V[f"winner_cap_{w}"] = {"cfg": {"max_win": float(w)}}
    for pct, mx in ((0.8, 750.0), (1.0, 750.0), (0.6, 1000.0), (0.8, 1000.0), (0.6, 500.0)):
        V[f"size_{int(pct * 100)}pct_max{int(mx)}"] = {"cfg": {"pct": pct, "pct_max_usd": mx}}
    for tp in (300, 500, 800):
        V[f"day_take_profit_{tp}"] = {"day_tp": float(tp)}
    for md in (1, 3):
        V[f"max_trades_day_{md}"] = {"max_day": md}
    for fl, k in ((300, 1.0), (400, 1.0), (300, 1.5)):
        V[f"cons_aware_floor{fl}_k{k}"] = {"dyn": {"floor": float(fl), "k": k}}
    for r in (1.0, 1.5, 2.0):
        V[f"half_off_at_{r}R"] = {"part": {"f": 0.5, "r": r}}
    V["ask_1000_cons_aware"] = {"ask": 1000, "dyn": {"floor": 300.0, "k": 1.0}}
    V["ask_1000_day_tp_500"] = {"ask": 1000, "day_tp": 500.0}
    V["winner_600_ask_1000"] = {"ask": 1000, "cfg": {"max_win": 600.0}}
    return V


def units_variants():
    from tools import atlas_v2 as V2
    V2.install()
    MEM = ["EMA", "MD", "SR"]
    UV = collections.OrderedDict()
    UV["hunts_x0.5"] = V2.V_(members=MEM + ["SHA", "SHT"], w={"SHA": 0.5, "SHT": 0.5})
    UV["hunt_asia_x0.5"] = V2.V_(members=MEM + ["SHA"], w={"SHA": 0.5})
    UV["hunt_trend_x0.5"] = V2.V_(members=MEM + ["SHT"], w={"SHT": 0.5})
    UV["sr_vix_bank5"] = V2.V_(sets={"SR": A.K(key={"tg": "vix", "bk": 5.0})})
    UV["sr_vix_bank3"] = V2.V_(sets={"SR": A.K(key={"tg": "vix", "bk": 3.0})})
    UV["ema_vix_bank3"] = V2.V_(sets={"EMA": A.K(X={"bank": 3.0})})
    UV["ema_3R"] = V2.V_(sets={"EMA": A.K(X={"tgt": 3.0})})
    UV["macd_3R"] = V2.V_(sets={"MD": A.K(sim={"tgt": 3.0})})
    return UV


def grid(fams=None):
    t0 = time.time()
    from tools import atlas_v2 as V2
    V2.install()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    fams = fams or ["funded", "units"]
    BASE_V = A.BASE
    by0 = base_by(BASE_V)
    ev0 = V2.score(V2.V_())
    ppass = {s: (ev0[s].get("p60") or 90.0) / 100.0 for s in SPANS}
    res["_eval_today"] = {s: {k: ev0[s].get(k) for k in ("p10", "f10", "dead10", "dec10", "p15", "f15", "pass_med", "slow_pass", "p60", "tpw", "net", "per_month", "pf")} for s in SPANS}
    print("eval today", {s: (res["_eval_today"][s]["p10"], res["_eval_today"][s]["f10"]) for s in SPANS}, flush=True)

    def dump():
        json.dump(res, open(OUT, "w"), indent=1, default=float)

    def run(key, by, K, ev=None, info=None):
        if key in res:
            print(key, "(stored)", flush=True)
            return
        K = {**BASE_K, **K}
        t1 = time.time()
        row = {"K": {k: v for k, v in K.items() if v != BASE_K.get(k)}, "info": info or {}, "eval": ev or {s: {k: res["_eval_today"][s][k] for k in ("p10", "f10", "dead10", "dec10", "pass_med")} for s in SPANS},
               "same_eval": ev is None}
        for s in SPANS:
            row[s] = mc2(by, s, K)
            row[s]["cycling"] = life2(by, s, K, ppass[s])
        res[key] = row
        a, b = row["H1"], row["H2"]
        print(f"{key:34s} H1 ${a['paid_per_month']:>4}/mo (p10 {a['paid_p10_per_month']}) grad {a['grad_pct']}% lost {a['lost_pct']} stuck {a['stuck_pct']} 1st {a['first_med']} tpw {a['trades_per_week']} PF {a['pf']} cyc ${a['cycling']['net_per_month_cycling']} "
              f"| H2 ${b['paid_per_month']:>4}/mo (p10 {b['paid_p10_per_month']}) grad {b['grad_pct']}% lost {b['lost_pct']} stuck {b['stuck_pct']} 1st {b['first_med']} tpw {b['trades_per_week']} PF {b['pf']} cyc ${b['cycling']['net_per_month_cycling']} ({time.time() - t1:.0f}s)", flush=True)
        dump()

    if "funded" in fams:
        for ix, (nm, K) in enumerate(funded_variants().items()):
            if SHARD and ix % SHARD[1] != SHARD[0]:
                continue
            run("funded:" + nm, by0, K)
    if "combo" in fams:
        UV0 = units_variants()
        for nm, Kc in (("hunt_trend_x0.5", {"max_day": 3}), ("hunts_x0.5", {"max_day": 3}), ("hunt_trend_x0.5", {"cfg": {"pct_max_usd": 1000.0}}), ("hunt_trend_x0.5", {"day_tp": 500.0})):
            tag = "+".join(f"{k}={v}" for k, v in Kc.items()).replace(" ", "")
            key = f"combo:{nm}|{tag}"
            if key in res:
                continue
            Vv = UV0[nm]
            ev = V2.score(Vv)
            evr = {s_: {k: ev[s_].get(k) for k in ("p10", "f10", "dead10", "dec10", "pass_med")} for s_ in SPANS}
            byv = base_by(Vv)
            pp = {s_: (ev[s_].get("p60") or 90.0) / 100.0 for s_ in SPANS}
            K = {**BASE_K, **Kc}
            row = {"K": Kc, "info": {"V": nm}, "eval": evr, "same_eval": False}
            for s_ in SPANS:
                row[s_] = mc2(byv, s_, K)
                row[s_]["cycling"] = life2(byv, s_, K, pp[s_])
            res[key] = row
            a, b = row["H1"], row["H2"]
            print(f"{key:50s} eval {evr['H1']['p10']}/{evr['H1']['f10']} {evr['H2']['p10']}/{evr['H2']['f10']} | H1 ${a['paid_per_month']} tpw {a['trades_per_week']} cyc ${a['cycling']['net_per_month_cycling']} | H2 ${b['paid_per_month']} tpw {b['trades_per_week']} cyc ${b['cycling']['net_per_month_cycling']}", flush=True)
            dump()
    if "units" in fams:
        UV = units_variants()
        for ix, (nm, Vv) in enumerate(UV.items()):
            if SHARD and ix % SHARD[1] != SHARD[0]:
                continue
            key = "units:" + nm
            if key in res:
                print(key, "(stored)", flush=True)
                continue
            try:
                ev = V2.score(Vv)
                evr = {s: {k: ev[s].get(k) for k in ("p10", "f10", "dead10", "dec10", "pass_med")} for s in SPANS}
                byv = base_by(Vv)
                pp = {s: (ev[s].get("p60") or 90.0) / 100.0 for s in SPANS}
                K = dict(BASE_K)
                row = {"K": {}, "info": {"V": nm}, "eval": evr, "same_eval": False, "eval_full": {s: {k: ev[s].get(k) for k in ("p10", "f10", "dead10", "dec10", "p15", "f15", "pass_med", "slow_pass", "p60", "tpw", "net", "per_month", "pf")} for s in SPANS}}
                t1 = time.time()
                for s in SPANS:
                    row[s] = mc2(byv, s, K)
                    row[s]["cycling"] = life2(byv, s, K, pp[s])
                res[key] = row
                a, b = row["H1"], row["H2"]
                print(f"{key:34s} eval {evr['H1']['p10']}/{evr['H1']['f10']} {evr['H2']['p10']}/{evr['H2']['f10']} | H1 ${a['paid_per_month']}/mo grad {a['grad_pct']}% lost {a['lost_pct']} tpw {a['trades_per_week']} PF {a['pf']} cyc ${a['cycling']['net_per_month_cycling']} "
                      f"| H2 ${b['paid_per_month']}/mo grad {b['grad_pct']}% lost {b['lost_pct']} tpw {b['trades_per_week']} PF {b['pf']} cyc ${b['cycling']['net_per_month_cycling']} ({time.time() - t1:.0f}s)", flush=True)
            except Exception as ex:  # noqa: BLE001
                res[key] = {"error": f"{type(ex).__name__}: {ex}"[:300]}
                print(key, "ERROR", res[key], flush=True)
            dump()
    dump()
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def base_check():
    from tools import atlas_funded as AFm
    M.units()
    by = base_by(A.BASE)
    for s in SPANS:
        t0 = time.time()
        r = mc2(by, s, dict(BASE_K), n=300)
        print(s, r, f"{time.time() - t0:.0f}s", flush=True)
    ref = json.load(open(os.path.join(ROOT, "research", "second", "atlas_funded.json")))["configs"]["live"]
    print("stored live: H1", ref["H1"]["per_month"], ref["H1"]["lost_6m"], ref["H1"]["grad_6m"], "| H2", ref["H2"]["per_month"], ref["H2"]["lost_6m"], ref["H2"]["grad_6m"])


def real_path(by, span, K):
    """Back-to-back funded accounts through the span's real sessions (an ended account is replaced the next session; eval time not counted)."""
    S = sessions(span)
    i, T, accts, paid = 0, [], 0, 0.0
    while i < len(S):
        r = account2(by, S[i:], K, keep=T)
        accts += 1
        paid += sum(x for _, x in r["pay_at"])
        i += r["end"]
        if not (r["lost"] or r["grad"] or r["stuck"]):
            break
    return T, accts, paid


def save_runs(keys):
    """rl.save one run per key (research/runs/ar3_*.json): the real back-to-back funded path of 2026 H1 + H2 (the run library's eval columns re-score
    these funded trades on the 50K plan: not the funded numbers, those are in the verdict and research/second/atlas_round3.json)."""
    from tools import runlib as rl
    res = load_all()
    VM = funded_variants()
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    by0 = base_by(A.BASE)
    for key in keys:
        r = res[key]
        K = {**BASE_K, **(VM.get(key.split(":", 1)[1], {}) if key.startswith("funded:") else r.get("K") or {})}
        byk = by0 if key.startswith("funded:") else base_by(units_variants()[key.split(":", 1)[1].split("|")[0]])
        T, accts = [], 0
        for sp in SPANS:
            t, a, _ = real_path(byk, sp, K)
            T += t
            accts += a
        rec = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0,
                "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"],
                "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None} for t in sorted(T, key=lambda t: t["entry_t"])]
        a, b = r["H1"], r["H2"]
        verdict = (f"ATLAS funded 25K, {key}. MC {N_MC} paths x 6 months. Jan-Jun: ${a['paid_per_month']}/mo to you (worst 10% ${a['paid_p10_per_month']}), {a['grad_pct']}% reach 5 payouts, "
                   f"lost {a['lost_pct']}%, stuck {a['stuck_pct']}%, {a['trades_per_week']} trades/wk, PF {a['pf']}; Jul-Oct: ${b['paid_per_month']}/mo (p10 ${b['paid_p10_per_month']}), "
                   f"{b['grad_pct']}% reach 5 payouts, lost {b['lost_pct']}%, stuck {b['stuck_pct']}%, {b['trades_per_week']} trades/wk, PF {b['pf']}. Eval 2-week pass/fail "
                   f"{r['eval']['H1']['p10']}/{r['eval']['H1']['f10']} and {r['eval']['H2']['p10']}/{r['eval']['H2']['f10']}.")
        rid = "ar3_" + key.replace(":", "_").replace(".", "").replace("|", "_").replace("=", "")
        rl.save(rid, f"ATLAS round 3: {key}", "other", "Job 30 (2026-11-04): what raises the ATLAS funded 25K's $ a month?", params={"plan": PLAN_ID, "K": r["K"], "info": r.get("info")},
                sizing={"mode": "funded", **AF.CFG["funded"]}, trades=rec, scored=rl.score(rec, sess), status="info" if key == "funded:today" else "promising" if key in PROMISING else "rejected",
                verdict=verdict, notes="tools/atlas_round3.py; real back-to-back funded accounts through 2026 H1 and H2", writeup="2026-11-04_atlas_round3", tags=["atlas", "funded", "ar3"])
        print("saved", rid, flush=True)


PLAN_ID = "builder25k"
PROMISING = ("units:hunts_x0.5", "units:hunt_trend_x0.5", "combo:hunt_trend_x0.5|day_tp=500.0")


def load_all():
    import glob
    res = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "research", "second", "atlas_round3*.json"))):
        res.update(json.load(open(fn)))
    return res


def report():
    res = load_all()
    b = res.get("funded:today")
    for k, r in res.items():
        if k.startswith("_") or "H1" not in r:
            if isinstance(r, dict) and "error" in r:
                print(k, r)
            continue
        a, c = r["H1"], r["H2"]
        e = r["eval"]
        print(f"{k:34s} H1 ${a['paid_per_month']:>4} PF {a['pf']} tpw {a['trades_per_week']} grad {a['grad_pct']} lost {a['lost_pct']} cyc ${a['cycling']['net_per_month_cycling']} | "
              f"H2 ${c['paid_per_month']:>4} PF {c['pf']} tpw {c['trades_per_week']} grad {c['grad_pct']} lost {c['lost_pct']} cyc ${c['cycling']['net_per_month_cycling']} | eval {e['H1']['p10']}/{e['H1']['f10']} {e['H2']['p10']}/{e['H2']['f10']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "base"
    if cmd == "base":
        base_check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "report":
        report()
    elif cmd == "save":
        save_runs(sys.argv[2:])
