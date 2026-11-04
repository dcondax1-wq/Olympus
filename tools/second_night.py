"""Second-strategies night (job 27, 2026-11-04): BLITZ / ATLAS on the 25K accounts, LIT correlation, and the more-accounts plan.
RESEARCH ONLY: engine/, second_model.json, live_model*.json untouched. Builds on tools/ab_edge.py (BLITZ trades as account C via
tools/blitz25k_lib, MFFU Builder 25K eval / slot via tools/blitz25k_size, ATLAS via tools/atlas_v2 + tools/atlas).

Judging (owner 2026-10-18 for the 2026 strategies): picked on Jan-Jun 2026 (H1), checked on Jul-Oct (H2), 2021-25 a reference line;
costs in; 2+ trades a week; eval speed p10/f10 = pass/fail within 10 sessions (2 weeks).

    python -X utf8 tools/second_night.py blitz     # BLITZ new ideas -> research/scalp/sn_blitz.json
    python -X utf8 tools/second_night.py atlas     # ATLAS members / priority / sizing -> research/second/sn_atlas.json
    python -X utf8 tools/second_night.py corr      # daily correlation LIT / ATLAS / BLITZ + stop fit -> research/second/sn_corr.json
    python -X utf8 tools/second_night.py plan      # the more-accounts plan -> research/second/sn_plan.json
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import ab_edge as AB  # noqa: E402

OUT_S = os.path.join(ROOT, "research", "scalp", "sn_blitz.json")
OUT_A = os.path.join(ROOT, "research", "second", "sn_atlas.json")
OUT_C = os.path.join(ROOT, "research", "second", "sn_corr.json")
OUT_P = os.path.join(ROOT, "research", "second", "sn_plan.json")


def dump(o, p):
    AB.dump(o, p)


# ================================================================================================ BLITZ
def blitz_variants():
    V = collections.OrderedDict()
    # 1 stop multiple of the 5m ATR (how the stop fits the $ caps: tighter = more micros under the same $ risk)
    for k in (1.0, 1.25, 2.0, 2.5):
        V[f"stop_atr{k}"] = {"stop": "atr", "k": k}
    # 2 time-of-day windows (last entry minute: 930 = 15:30)
    for lm in (780, 840, 870, 900):
        V[f"last_entry_{lm // 60:02d}{lm % 60:02d}"] = {"last_mod": lm}
    # 3 per-day loss cap (R) and trades a day
    for ds in (1.0, 1.5, 2.0):
        V[f"day_stop_{ds}R"] = {"day_stop": ds}
    for md in (2, 3, 4):
        V[f"max_day_{md}"] = {"maxday": md}
    # 4 hold time
    for h in (15, 20, 45, 60):
        V[f"hold_{h}"] = {"hold": h}
    # 5 breakeven and trail shape
    for be in (1.0, 1.5):
        V[f"be_{be}R"] = {"be": be}
    for ts, tr in ((0.75, 1.5), (1.25, 1.5), (1.0, 1.0), (1.0, 2.0)):
        V[f"trail_start{ts}_dist{tr}"] = {"tstart": ts, "trail": tr}
    # 6 day filter strength
    for f in ("prng>=0.6", "prng>=1.0", "prng>=0.7", "prng>=0.9"):
        V[f"filter_{f}"] = {"filter": f}
    # 6b partials (half out at p R, the runner keeps the trail / 30-minute clock) and fixed targets: where they help on the 25K
    for pr in (0.75, 1.0, 1.5, 2.0):
        V[f"partial_half_at_{pr}R"] = {"part": pr, "part_f": 0.5}
    for pr in (1.0, 1.5):
        V[f"partial_half_at_{pr}R_then_BE"] = {"part": pr, "part_f": 0.5, "part_be": True}
    for tg in (1.5, 2.0, 3.0):
        V[f"fixed_target_{tg}R"] = {"tgt": tg}
    # 7 stop width bounds in 5m-ATR units (a stop floor / ceiling)
    for lo, hi in ((1.0, 99.0), (0.0, 3.0), (0.0, 2.5), (1.2, 3.0)):
        V[f"stop_bounds_{lo}_{hi}"] = {"dmin": lo, "dmax": hi}
    return V


def score_blitz(TT, base=None, slot_n=300):
    SP = AB.spans_of(TT)
    out = {}
    for sp, (T, S) in SP.items():
        r = AB.rview(T, S)
        e = AB.ev25(T, S)
        o = {"n": r["n"], "tpw": r["tpw"], "wk2": r["wk2"], "pf": r["pf"], "avg_r": r["avg_r"], "per_month500": r["per_month"], "dd500": r["dd"],
             **{k: e[k] for k in ("p10", "f10", "dec10", "p15", "f15", "pass_med", "slow_pass")}}
        s = AB.slot25(T, S, n=slot_n)
        o["slot_pm"] = s.get("life_pm")
        o["slot_p10"] = s.get("life_p10")
        o["slot_lose"] = s.get("life_lose")
        o["first_pay_med"] = s.get("first_pay_med")
        out[sp] = o
    return out


def blitz_line(nm, o, b=None):
    t = f"{nm:34s}"
    for sp in ("H1", "H2", "R"):
        x = o[sp]
        t += f" | {sp} n {x['n']} {x['tpw']}/wk $500view {x['per_month500']:+}/mo PF {x['pf']} 2w {x['p10']}/{x['f10']} dec {x['dec10']} med {x['pass_med']} slot {x['slot_pm']:+}"
    return t


def _patch_filter(K):
    """blitz25k_lib.base knows only prng>=0.8 / none: let it take any prng>=x threshold."""
    orig = K.base

    def base(B, filt="prng>=0.8", wins=("rth",)):
        if isinstance(filt, str) and filt.startswith("prng>=") and filt != "prng>=0.8":
            thr = float(filt[6:])
            k = ("sn_base", B["tf"], len(B["t"]), filt, tuple(wins))
            if k in K._S:
                return K._S[k]
            parts = []
            for wk in wins:
                F = K._signals_win(B, wk)
                m = F["prng_ratio"] >= thr
                parts.append({kk: F[kk][m] for kk in ("sig", "dir")})
            I = np.concatenate([p["sig"] for p in parts]).astype(np.int64)
            D = np.concatenate([p["dir"] for p in parts])
            o = np.argsort(I, kind="stable")
            I, D = I[o], D[o]
            keep = np.r_[True, I[1:] != I[:-1]]
            K._S[k] = {"sig": I[keep], "dir": D[keep]}
            return K._S[k]
        return orig(B, filt, wins)
    K.base = base


def cmd_blitz():
    t0 = time.time()
    res = json.load(open(OUT_S)) if os.path.exists(OUT_S) else {}
    N, K, BS = AB.blitz_libs()
    _patch_filter(K)
    base_TT = AB.blitz_trades()
    if "base" not in res:
        res["base"] = score_blitz(base_TT)
    print(blitz_line("base", res["base"]), flush=True)
    # priority rule: BLITZ with no LIT / ATLAS blocking at all (what the anti-hedge rule costs)
    for nm, cm in (("no_block", None), ("lit_only", "lit")):
        key = f"priority_{nm}"
        if key not in res:
            try:
                TT = AB.blitz_trades({}, cm)
                res[key] = score_blitz(TT)
            except Exception as ex:  # noqa: BLE001
                res[key] = {"error": str(ex)[:200]}
        if "error" not in res[key]:
            print(blitz_line(key, res[key]), flush=True)
        else:
            print(key, res[key], flush=True)
        dump(res, OUT_S)
    for nm, v in blitz_variants().items():
        if nm in res:
            print(blitz_line(nm, res[nm]), flush=True)
            continue
        t1 = time.time()
        try:
            TT = AB.blitz_trades(v)
            res[nm] = {**score_blitz(TT), "v": v}
        except Exception as ex:  # noqa: BLE001
            res[nm] = {"error": str(ex)[:300], "v": v}
            print(nm, "ERROR", str(ex)[:200], flush=True)
            dump(res, OUT_S)
            continue
        print(blitz_line(nm, res[nm]), f"({time.time() - t1:.0f}s)", flush=True)
        dump(res, OUT_S)
    dump(res, OUT_S)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


# ================================================================================================ ATLAS
def lit_day_info():
    """day -> LIT trades [(entry_t, exit_t, dir, pts/risk)] from the ATLAS unit cache (the same LIT units the no-hedge rule uses)."""
    V2, A, M, EAB = AB.atlas_libs()
    by = collections.defaultdict(list)
    for u in M.units()["LIT"]:
        by[u["day"]].append((u["entry_t"], u["exit_t"], u["dir"], float(u["pts"]) / float(u["risk"]) if u["risk"] else 0.0))
    return by


def atlas_ideas(base_V):
    """New per-trade size multipliers {(src, entry_t): m} known at the ATLAS entry (nothing skipped)."""
    V2, A, M, EAB = AB.atlas_libs()
    U = A.account_units(base_V)
    lit = lit_day_info()
    out = collections.OrderedDict()

    def mk(fn):
        return {(u["src"], u["entry_t"]): float(fn(u)) for u in U}
    mod = lambda u: A.et_mod(u["entry_t"])
    out["london_up125_ny_dn075"] = (mk(lambda u: 1.25 if 120 <= mod(u) < 330 else 0.75 if mod(u) >= 570 else 1.0), "London entries x1.25, NY x0.75")
    out["ny_up125"] = (mk(lambda u: 1.25 if mod(u) >= 570 else 1.0), "NY entries x1.25")
    out["monday_dn075"] = (mk(lambda u: 0.75 if dt.date.fromisoformat(u["day"]).weekday() == 0 else 1.0), "Monday x0.75")
    out["midweek_up125"] = (mk(lambda u: 1.25 if dt.date.fromisoformat(u["day"]).weekday() in (1, 2) else 1.0), "Tue/Wed x1.25")

    def after_lit(u, up, dn):
        done = [x for x in lit.get(u["day"], []) if x[1] <= u["entry_t"]]
        if not done:
            return 1.0
        r = sum(x[3] for x in done)
        return dn if r < 0 else up
    out["lit_lost_today_dn05"] = (mk(lambda u: after_lit(u, 1.0, 0.5)), "LIT already lost today: ATLAS x0.5 (avoid a double-loss day)")
    out["lit_lost_today_up125"] = (mk(lambda u: after_lit(u, 1.0, 1.25)), "LIT already lost today: ATLAS x1.25")
    out["lit_won_today_up125"] = (mk(lambda u: after_lit(u, 1.25, 1.0)), "LIT already won today: ATLAS x1.25 (house money)")
    out["lit_won_today_dn075"] = (mk(lambda u: after_lit(u, 0.75, 1.0)), "LIT already won today: ATLAS x0.75")

    def agree_lit(u, up, dn):
        ls = [x for x in lit.get(u["day"], []) if x[0] <= u["entry_t"]]
        if not ls:
            return 1.0
        return up if any(x[2] == u["dir"] for x in ls) else dn
    out["with_lit_up125"] = (mk(lambda u: agree_lit(u, 1.25, 1.0)), "same direction as LIT's trade today x1.25")
    out["against_lit_dn075"] = (mk(lambda u: agree_lit(u, 1.0, 0.75)), "opposite to LIT's trade of the day x0.75")
    return out


def cmd_atlas():
    t0 = time.time()
    V2, A, M, EAB = AB.atlas_libs()
    base_V = V2.V_()
    res = json.load(open(OUT_A)) if os.path.exists(OUT_A) else {}
    base = AB.a_score(base_V)
    res["base"] = AB.a_compact(base)
    print("ATLAS today:")
    for s in base:
        print("  ", AB.a_line(base, s), flush=True)

    def run(fam, name, V, um=None):
        key = f"{fam}:{name}"
        if key in res:
            print(key, "(stored)", flush=True)
            return
        if um is not None:
            AB._UM[name] = um
            V = {**V, "um": name}
        o = AB.a_score(V)
        v = V2.verdict(o, base)
        res[key] = {"fam": fam, "name": name, "verdict": v, "o": AB.a_compact(o)}
        print(f"{fam:8s} {name:36s} {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
              " | ".join(AB.a_line(o, s) for s in ("H1", "H2", "2025", "2021-24")), flush=True)
        AB.dump(res, OUT_A)
    MEM = ["EMA", "MD", "SR"]
    for keep in (["EMA"], ["MD"], ["SR"], ["MD", "SR"], ["EMA", "SR"], ["EMA", "MD"]):
        run("members", "+".join(keep), V2.V_(members=keep))
    run("priority", "no armed-LIT block", V2.V_(armed=False))
    for w in (0.75, 1.25):
        for nm in MEM:
            run("weight", f"{nm}x{w}", V2.V_(w={nm: w}))
    for mu in (300.0, 400.0, 500.0, 600.0):
        run("stopfit", f"max_usd{mu:g}", V2.V_(tw={"max_usd": mu}))
    for dl in (300.0, 450.0):
        run("stopfit", f"dll{dl:g}", V2.V_(tw={"dll": dl}, cfg={"guard": {"dll": dl}}))
    for nm, (um, desc) in atlas_ideas(base_V).items():
        run("idea", nm, base_V, um)
        res[f"idea:{nm}"]["desc"] = desc
    # shuffle control for the ideas that pass the 2026 test in both halves
    for k, r in list(res.items()):
        if k.startswith("idea:") and r["verdict"]["both"] and "placebo" not in r:
            r["placebo"] = AB.a_placebo(base_V, AB._UM[r["name"]], n=30)
            print("   placebo", k, r["placebo"], flush=True)
            AB.dump(res, OUT_A)
    AB.dump(res, OUT_A)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


# ================================================================================================ daily series, correlation, stop fit
def daily_series():
    """2026 sessions and the daily $ of each strategy at a nominal live-like size:
    LIT = run lit_live (LIT size rule, $), ATLAS = account-B units at $500 risk, BLITZ = account-C 1m trades at $150 risk (funded size)
    and $450 (eval size); R series too (scale-free)."""
    from tools import runlib as rl
    V2, A, M, EAB = AB.atlas_libs()
    lit = rl.load("lit_live")
    days = [d[0] for d in lit["days"] if d[0] >= "2026-01-02"]
    ix = {d: i for i, d in enumerate(days)}
    n = len(days)
    out = {"days": days}
    L = np.zeros(n); LR = np.zeros(n)
    for d, pnl, low, k in lit["days"]:                    # day_cols: date, pnl, low, trades
        if d in ix:
            L[ix[d]] = pnl
    tc = lit["trade_cols"]
    for t in lit["trades"]:
        if t[0] in ix:
            LR[ix[t[0]]] += float(t[tc.index("r")])
    out["L"] = L
    Ar = np.zeros(n)
    base_V = V2.V_()
    U = A.account_units(base_V)
    for u in U:
        if u["day"] in ix and u["risk"]:
            Ar[ix[u["day"]]] += (float(u["pts"]) - 0.95) / float(u["risk"])
    out["A_R"] = Ar
    TT = AB.blitz_trades()
    Br = np.zeros(n)
    for t in TT[1]:
        if t["day"] in ix:
            Br[ix[t["day"]]] += t["pnl_pm"] / t["risk_pm"]
    out["B_R"] = Br
    out["L_R"] = LR
    out["units"] = U
    out["TT"] = TT
    return out


def cmd_corr():
    D = daily_series()
    days = D["days"]
    n = len(days)
    h1 = np.array([d <= "2026-06-30" for d in days])
    series = {"LIT ($, LIT size)": D["L"], "ATLAS ($500 risk)": 500.0 * D["A_R"], "BLITZ ($150 risk)": 150.0 * D["B_R"]}
    names = list(series)
    res = {"sessions": n, "corr": {}, "coloss": {}}
    for nm_sp, mask in (("2026", np.ones(n, bool)), ("H1", h1), ("H2", ~h1)):
        C = {}
        for i in range(3):
            for j in range(i + 1, 3):
                a, b = series[names[i]][mask], series[names[j]][mask]
                C[f"{names[i]} x {names[j]}"] = round(float(np.corrcoef(a, b)[0, 1]), 3)
        res["corr"][nm_sp] = C
        # scale-free R correlation
        R3 = [D["L_R"][mask], D["A_R"][mask], D["B_R"][mask]]
        res["corr"][nm_sp + "_R"] = {"LIT x ATLAS": round(float(np.corrcoef(R3[0], R3[1])[0, 1]), 3),
                                    "LIT x BLITZ": round(float(np.corrcoef(R3[0], R3[2])[0, 1]), 3),
                                    "ATLAS x BLITZ": round(float(np.corrcoef(R3[1], R3[2])[0, 1]), 3)}
        S3 = [series[k][mask] for k in names]
        loss = [x < -1e-9 for x in S3]
        trade = [np.abs(x) > 1e-9 for x in S3]
        res["coloss"][nm_sp] = {
            "sessions": int(mask.sum()),
            "days_each_traded": [int(t.sum()) for t in trade],
            "days_each_lost": [int(l.sum()) for l in loss],
            "LIT+ATLAS lose together": int((loss[0] & loss[1]).sum()), "LIT+BLITZ lose together": int((loss[0] & loss[2]).sum()),
            "ATLAS+BLITZ lose together": int((loss[1] & loss[2]).sum()), "all three lose": int((loss[0] & loss[1] & loss[2]).sum()),
            "LIT+ATLAS both traded": int((trade[0] & trade[1]).sum()), "LIT+BLITZ both traded": int((trade[0] & trade[2]).sum()),
            "ATLAS+BLITZ both traded": int((trade[1] & trade[2]).sum()),
            "worst day LIT": round(float(S3[0].min())), "worst day ATLAS": round(float(S3[1].min())), "worst day BLITZ": round(float(S3[2].min())),
            "worst day of the sum": round(float((S3[0] + S3[1] + S3[2]).min())),
            "sum of the three worst days alone": round(float(S3[0].min() + S3[1].min() + S3[2].min())),
        }
    # stop fit: micros each strategy can carry under the 25K caps
    fit = {}
    TT = D["TT"][1]
    rp = np.array([t["risk_pm"] for t in TT])
    rpts = np.array([t["risk_pts"] for t in TT])
    fit["BLITZ"] = {"trades": len(TT), "stop_pts_p10_med_p90": [round(float(np.percentile(rpts, q)), 1) for q in (10, 50, 90)],
                    "risk_per_micro_p10_med_p90": [round(float(np.percentile(rp, q))) for q in (10, 50, 90)],
                    "share_1_micro_over_150": round(float((rp > 150).mean()), 3), "share_1_micro_over_600": round(float((rp > 600).mean()), 3),
                    "micros_at_400_eval_p10_med_p90": [int(np.percentile(np.floor(400 / rp), q)) for q in (10, 50, 90)],
                    "share_20_micro_cap_binds_at_600": round(float((np.floor(600 / rp) >= 20).mean()), 3),
                    "share_zero_micros_at_400": round(float((np.floor(400 / rp) < 1).mean()), 3),
                    "micros_at_150_funded": [int(np.percentile(np.floor(150 / rp), q)) for q in (10, 50, 90)],
                    "share_zero_micros_at_150": round(float((np.floor(150 / rp) < 1).mean()), 3)}
    for src in ("EMA", "MD", "SR"):
        U = [u for u in D["units"] if u["src"] == src and u["day"] >= "2026-01-02"]
        r = np.array([float(u["risk"]) for u in U])
        rpm = r * 2.0 + 1.9 + 0.5
        fit[src] = {"trades": len(U), "stop_pts_p10_med_p90": [round(float(np.percentile(r, q)), 1) for q in (10, 50, 90)],
                    "micros_at_500_p10_med_p90": [int(np.percentile(np.minimum(20, np.floor(500 / rpm)), q)) for q in (10, 50, 90)],
                    "share_20_micro_cap_binds_at_500": round(float((np.floor(500 / rpm) >= 20).mean()), 3),
                    "share_stop_over_60pts_(risk>$120 a micro)": round(float((rpm > 120).mean()), 3),
                    "share_over_$600_for_1_micro": round(float((rpm > 600).mean()), 3)}
    res["stopfit"] = fit
    for k, v in res["corr"].items():
        print(k, v)
    for k, v in res["coloss"].items():
        print(k, v)
    print(json.dumps(fit, indent=0))
    dump(res, OUT_C)
    np.savez(os.path.join(ROOT, "research", "second", "sn_daily.npz"), days=np.array(days), L=D["L"], L_R=D["L_R"], A_R=D["A_R"], B_R=D["B_R"])


def cmd_save():
    """Store a few of tonight's runs in the run library (BLITZ at $500 a trade x1, 2021-25 5m + 2026 1m; ATLAS from the account-B paths)."""
    from tools import runlib as rl
    N, K, BS = AB.blitz_libs()
    V2, A, M, EAB = AB.atlas_libs()
    TT0, SP = AB._prep_blitz()
    sess = sorted(set(M.units()["sessions"]) | {d for sp in SP for d in SP[sp][1]})
    res = json.load(open(OUT_S))
    picks = [("sn_blitz_today", "base", {}, "info", "BLITZ as account C today (the bar for tonight's versions)"),
             ("sn_blitz_half_off_1_5R", "partial_half_at_1.5R", {"part": 1.5, "part_f": 0.5}, "rejected", "half off at 1.5R: neutral"),
             ("sn_blitz_hold_45", "hold_45", {"hold": 45}, "promising", "hold 45 min: Jul-Oct and 2021-25 up, Jan-Jun down"),
             ("sn_blitz_stop_1_25atr", "stop_atr1.25", {"stop": "atr", "k": 1.25}, "rejected", "stop 1.25 ATR: more fails")]
    for rid, key, v, st, why in picks:
        TT = AB.blitz_trades(v) if v else TT0
        rows = AB._blitz_store(TT)
        o = res[key]
        ver = (f"{why}. Jan-Jun {o['H1']['n']} trades, 2-week pass/fail {o['H1']['p10']}/{o['H1']['f10']}, slot ${o['H1']['slot_pm']}/mo; "
               f"Jul-Oct {o['H2']['n']} trades, {o['H2']['p10']}/{o['H2']['f10']}, slot ${o['H2']['slot_pm']}/mo; 2021-25 slot ${o['R']['slot_pm']}/mo.")
        rl.save(rid, f"Second strategies night: {key}", "other", "Job 27 (2026-11-04): BLITZ on the MFFU 25K, new ideas", params={**K.TODAY, **v},
                sizing={"usd_per_trade": 500.0}, trades=rows, scored=rl.score(rows, sess), status=st, verdict=ver,
                notes="tools/second_night.py blitz; stored at $500 a trade, costs in", writeup="2026-11-04_second_strategies_night",
                tags=["scalp", "blitz", "second_night"])
        print("saved", rid, flush=True)
    o, rows = AB._atlas_store(V2.V_(armed=False), "atlas_armed_off")
    rl.save("sn_atlas_armed_off", "Second strategies night: ATLAS without the armed-LIT block (hedge risk)", "other",
            "Job 27: what the armed-LIT no-hedge block costs ATLAS", params={"members": ["EMA", "MD", "SR"], "armed": False}, sizing={"account_b": "25K need"},
            trades=rows, scored=rl.score(rows, sess), status="rejected",
            verdict="More money on paper (Jan-Jun +$570, Jul-Oct +$1,086 eval-path) but trades against armed LIT setups: MFFU forbids hedging across accounts.",
            notes="tools/second_night.py atlas", writeup="2026-11-04_second_strategies_night", tags=["atlas", "second_night"])
    print("saved sn_atlas_armed_off", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "blitz"
    if cmd == "blitz":
        cmd_blitz()
    elif cmd == "atlas":
        cmd_atlas()
    elif cmd == "corr":
        cmd_corr()
    elif cmd == "save":
        cmd_save()
