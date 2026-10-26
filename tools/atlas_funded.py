"""ATLAS's funded account (2026-10-26, research/writeups/atlas-funded.md): what the MFFU Builder 25K pays once ATLAS's eval
passes and the bot keeps trading it under the funded rules (engine/account_b.py stage "funded").

Trades = ATLAS as it trades account B (tools/atlas.account_units(BASE): EMA + MACD + S/R pooled, entries at the 5m open,
LIT's opposite open trade / entry / ARMED setup blocks an ATLAS entry, LIT entering the other way closes ATLAS = HEDGE),
2021-11 .. 2026-10-16, real CME NQ1! / MNQ, $1.90 a micro round trip, slippage in the stored exits.
One funded account = tools/second_mix.play_day (one position, max 2 trades a day, the plan's $600 soft daily loss over the
day, the floor checked against each trade's worst open loss) with every trade sized by engine/account_b.qty on the FUNDED
spec (= what the bot routes: engine/sizing.funded_qty on the 25K preset + the soft daily loss guard; checked equal here),
the EOD trailing $1,000 floor locked at start + $100 (and at start + $100 after the first payout), and at each session's
end the MFFU tracker engine/funded_life.track: a payout is requested when it says "ready" (every MFFU rule: $1,100 buffer
kept, request $250-$1,000, best day <= 50% of the cycle, 2 traded days a cycle, the first request 48 h after the first
trade; and the owner's habit: $750 above the buffer), for the max it allows, 80% to the owner; 5 payouts end the sim
account (graduated: MFFU moves it to live).

Sizing rules compared:
  live  the 25K funded preset (owner 2026-10-25, research/writeups/uprisk.md): 60% of the room, <= $750 a trade (x20/stop
        past 20 pts), a winner <= $1,000, skip when 1 micro could reach the floor   <- what engine/account_b.py routes
  old   the research rule before uprisk (lit-funded-sizing.md / funded-path.md): 40% of the room, <= $400, a winner <= $750
Spans as every ATLAS report: 2026 H1 (Jan-Jun), 2026 H2 (Jul-Oct 16, the check), 2025, 2021-24 (references).
Per span: Monte Carlo 1,000 funded accounts x 126 sessions (6 months) drawn in 5-session blocks from the span (seed 23),
and the real path: back-to-back funded accounts through the span (a lost or graduated account is replaced the next
session; eval time not counted). The eval leg (how often ATLAS's 25K eval passes) is tools/atlas.score(BASE).

    python -X utf8 tools/atlas_funded.py            # -> research/second/atlas_funded.json + runs atlas_funded_* (~5 min)
    python -X utf8 tools/atlas_funded.py --quick    # 200 paths, no save
Paper research only. Needs research/runs/_cache/second_mix_units.pkl and atlas_lit_armed.pkl (tools/second_mix.py units,
tools/atlas_lit_armed.py).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import account_b as EAB  # noqa: E402
from engine import funded_life as FL  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import atlas as A  # noqa: E402
from tools import second_mix as M  # noqa: E402

PLAN = "builder25k"
OUT = os.path.join(ROOT, "research", "second", "atlas_funded.json")
SPANS = ("H1", "H2", "2025", "2021-24")
N_MC, BLOCK, LEN = 1000, 5, 126
PRICE_NOW, PRICE_USUAL = 43.0, 63.0          # this 25K cost $43 (2026-10-26); the owner usually pays $63
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
P = FL.plan_of(PLAN)
OLD = {"pct": 0.4, "pct_min_usd": 50, "pct_max_usd": 400, "ref": 20, "wk": True, "room_f": None, "max_win": 750,
       "slip_ticks": 2, "skip_breach": True}


def spec():
    return EAB.normalize({"account": "research", "plan": PLAN, "eval_start": "2026-01-02", "stage": "funded",
                          "funded_start": "2000-01-03"}, lit_account=None)


SPEC = spec()
CFG = EAB.funded_cfg(SPEC, LSZ)
ACCT = {**CFG["acct"], "max_micros": int(SPEC["rules"]["max_micros"])}


def q_live(t, st):
    """engine/account_b.qty on the funded spec: exactly what the bot routes."""
    return int(EAB.qty(SPEC, {"risk_pts": float(t["risk"]), "tgt_pts": float(t["tgt"])}, dict(st), base=LSZ)["qty"])


def q_rule(cfg):
    def q(t, st):
        r = float(t["risk"])
        n = SZ.funded_qty({"risk_pts": r, "tgt_pts": float(t["tgt"]), "size_mult": 1.0}, dict(st), cfg, acct=ACCT)
        return int(EAB.dll_guard({"qty": min(int(ACCT["max_micros"]), int(n)), "reasons": []}, r, SPEC["rules"], st)["qty"])
    return q


RULES = {"live": q_live, "old": q_rule(OLD)}
TITLES = {"live": "ATLAS funded 25K, the live funded preset (60% of the room, <= $750 a trade, a winner <= $1,000)",
          "old": "ATLAS funded 25K, the older research rule (40% of the room, <= $400, a winner <= $750)"}

_CAL = []


def cal(k: int) -> str:
    """Synthetic weekday calendar for a path (block resampling repeats days): weekday k from 2027-01-04."""
    while len(_CAL) <= k:
        d = dt.date(2027, 1, 4) if not _CAL else dt.date.fromisoformat(_CAL[-1]) + dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        _CAL.append(d.isoformat())
    return _CAL[k]


class Sizer:
    """tools/second_mix.play_day with ATLAS's funded size (rule "funded")."""

    def __init__(self, qfn):
        self.qfn = qfn

    def __enter__(self):
        self._old = M.second_q
        qfn, inner = self.qfn, M.second_q

        def second_q(t, st, rule):
            return qfn(t, st) if rule == "funded" else inner(t, st, rule)
        M.second_q = second_q
        return self

    def __exit__(self, *a):
        M.second_q = self._old


def account(by, seq, keep=None, real_days=False, k0=0):
    """One funded account over the session list seq (real days). -> {"lost", "grad", "pay_at", "first", "cons_block",
    "max_risk", "n", "end"}; keep collects the sized trades (real day labels)."""
    bal = peak = 0.0
    floor = -float(P["mll"])
    lock = float(P["lock"])
    days, pays = {}, {}
    out = {"lost": None, "grad": None, "pay_at": [], "first": None, "cons_block": 0, "max_risk": 0.0, "n": 0, "end": len(seq),
           "paid_gross": 0.0, "stuck": None, "left": 0.0, "made": 0.0}
    for k, day in enumerate(seq):
        cd = cal(k0 + k) if not real_days else day
        cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, 99, "funded", False, 2, None, dll=float(P["dll"]),
                                       reserve=False, extra={"locked": floor >= lock - 1e-9})
        for r in recs:
            out["n"] += 1
            out["max_risk"] = max(out["max_risk"], (r["risk"] + 0.25) * 2.0 * r["qty"] + 1.90 * r["qty"])
            if keep is not None:
                keep.append(r)
        if failed:
            out["lost"], out["end"] = k + 1, k + 1
            out["left"] = floor
            return out
        bal += cum
        out["made"] += cum
        out["left"] = bal
        if recs:
            days[cd] = round(cum, 2)
        peak = max(peak, bal)
        floor = min(max(floor, peak - float(P["mll"])), lock)
        if bal - floor < EAB.MIN_ROOM:
            # stuck (engine/account_b.py funded stage, as a funded extra account): under $100 of room the bot stops trading it
            out["stuck"], out["end"] = k + 1, k + 1
            return out
        tr = FL.track(days, pays, P, today=cd)
        if tr["status"] == "consistency" and tr["above_buffer"] >= P["ask_above"]:
            out["cons_block"] += 1                 # the money is there, only the 50% rule holds it back today
        if tr["status"] == "ready":
            amt = float(tr["max_request"])
            pays[cd] = amt
            bal -= amt
            floor = max(floor, lock)
            out["paid_gross"] += amt
            out["pay_at"].append((k + 1, amt * P["split"]))
            out["first"] = out["first"] or k + 1
            out["left"] = bal
            if len(pays) >= P["max_payouts"]:
                out["grad"], out["end"] = k + 1, k + 1
                return out
    return out


def span_sessions(span):
    a, z = M.SPANS[span]
    return [d for d in M.units()["sessions"] if a <= d <= min(z, "2026-10-16")]


def mc(by, span, n=N_MC):
    S = span_sessions(span)
    rng = np.random.default_rng(23)
    R = []
    for _ in range(n):
        s = []
        while len(s) < LEN:
            b = int(rng.integers(0, len(S) - BLOCK + 1))
            s.extend(S[b:b + BLOCK])
        R.append(account(by, s[:LEN]))
    o = {"paths": n}
    for lab, h in (("3m", 63), ("6m", 126)):
        paid = [sum(x for k, x in r["pay_at"] if k <= h) for r in R]
        o[f"lost_{lab}"] = round(100.0 * sum(1 for r in R if r["lost"] and r["lost"] <= h) / n, 1)
        o[f"paid_{lab}"] = round(float(np.mean(paid)))
        o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)))
        o[f"any_pay_{lab}"] = round(100.0 * sum(1 for r in R if r["first"] and r["first"] <= h) / n, 1)
    o["per_month"] = round(o["paid_6m"] / 6.0)
    o["per_month_p10"] = round(o["paid_p10_6m"] / 6.0)
    fr = [r["first"] for r in R if r["first"]]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["first_p75"] = float(np.percentile(fr, 75)) if fr else None
    o["payouts_6m"] = round(float(np.mean([len(r["pay_at"]) for r in R])), 2)
    o["payouts_per_month"] = round(o["payouts_6m"] / 6.0, 2)
    o["grad_6m"] = round(100.0 * sum(1 for r in R if r["grad"]) / n, 1)
    o["stuck_6m"] = round(100.0 * sum(1 for r in R if r["stuck"] and not r["lost"]) / n, 1)
    o["dead_6m"] = round(o["lost_6m"] + o["stuck_6m"], 1)
    o["made_per_month"] = round(float(np.mean([r["made"] for r in R])) / 6.0)
    o["left_6m"] = round(float(np.mean([r["left"] for r in R])))
    o["cons_block_days"] = round(float(np.mean([r["cons_block"] for r in R])), 1)
    o["trades_per_week"] = round(float(np.mean([r["n"] / max(1, r["end"]) * 5 for r in R])), 2)
    o["max_risk"] = round(max(r["max_risk"] for r in R))
    return o


def real(by, span, keep=None):
    """Back-to-back funded accounts through the span's real sessions (a lost / graduated account is replaced the next
    session; eval time not counted)."""
    S = span_sessions(span)
    i, accts, paid, n_pay, lost, grad, stuck, firsts, T = 0, 0, 0.0, 0, 0, 0, 0, [], []
    while i < len(S):
        r = account(by, S[i:], keep=T, real_days=True)
        accts += 1
        paid += sum(x for _, x in r["pay_at"])
        n_pay += len(r["pay_at"])
        lost += 1 if r["lost"] else 0
        grad += 1 if r["grad"] else 0
        stuck += 1 if r["stuck"] and not r["lost"] else 0
        if r["first"]:
            firsts.append(r["first"])
        i += r["end"]
        if not (r["lost"] or r["grad"] or r["stuck"]):
            break
    if keep is not None:
        keep.extend(T)
    months = len(S) / 21.0
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    return {"sessions": len(S), "months": round(months, 1), "accounts": accts, "lost": lost, "graduated": grad, "stuck": stuck,
            "payouts": n_pay,
            "paid": round(paid), "per_month": round(paid / months) if months else 0, "payouts_per_month": round(n_pay / months, 2) if months else 0,
            "first_payout_sessions": firsts, "trades": len(T), "net_trading": round(float(p.sum())),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "max_risk": round(max(((t["risk"] + 0.25) * 2 * t["qty"] + 1.9 * t["qty"]) for t in T), 0) if T else 0}


def check_live_equals_code(by):
    """The replay's size == engine/account_b.qty == an AccountB on a fake bot (the bot's own funded path) on every 2026 trade
    at a grid of rooms."""
    bad, n = [], 0
    U = [t for d in sorted(by) if d >= "2026-01-01" for t in by[d]]
    for t in U:
        for room, cum in ((1000.0, 0.0), (400.0, -250.0), (2600.0, 300.0), (90.0, 0.0)):
            st = {"profit": 0.0, "cum": cum, "room": room, "session": 99, "n_today": 0, "locked": room > 1500}
            a = q_live(t, st)
            b = int(SZ.funded_qty({"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, dict(st), CFG["funded"], acct=ACCT))
            b = int(EAB.dll_guard({"qty": min(20, b), "reasons": []}, t["risk"], SPEC["rules"], st)["qty"])
            n += 1
            if a != b:
                bad.append((t["day"], t["risk"], room, a, b))
    return {"checked": n, "diff": len(bad), "examples": bad[:3]}


def eval_leg():
    """ATLAS's 25K eval odds per span (tools/atlas.score on BASE = the live ATLAS, the real account-B rules)."""
    o = A.score(A.BASE)
    keys = ("p10", "f10", "dead10", "dec10", "p15", "f15", "p20", "f20", "slow_pass", "pass_med", "p60", "f60", "tpw", "net", "per_month", "pf")
    return {s: {k: o[s].get(k) for k in keys} for s in SPANS}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quick = "--quick" in argv
    n = 200 if quick else N_MC
    M.units()
    U = A.account_units(A.BASE)
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    out = {"built": dt.date.today().isoformat(), "plan": PLAN, "trades": {s: sum(len(by[d]) for d in span_sessions(s)) for s in SPANS},
           "sessions": {s: len(span_sessions(s)) for s in SPANS}, "price_now": PRICE_NOW, "price_usual": PRICE_USUAL,
           "rules": {"live": CFG["funded"], "old": OLD}, "acct": ACCT, "plan_rules": {k: P[k] for k in ("mll", "lock", "dll", "buffer",
           "pay_min", "pay_max", "split", "cons", "cycle_days", "first_wait_h", "max_payouts", "ask_above")}, "configs": {}}
    with Sizer(q_live):
        out["check"] = check_live_equals_code(by)
    print("replay size == engine/account_b.qty:", out["check"], flush=True)
    paths = {}
    for rid, qfn in RULES.items():
        row = {"title": TITLES[rid]}
        T = []
        with Sizer(qfn):
            for s in SPANS:
                row[s] = mc(by, s, n)
                row[s + "_real"] = real(by, s, keep=T)
                x, y = row[s], row[s + "_real"]
                print(f"{rid:5s} {s:8s} MC ${x['per_month']:>5}/mo (p10 ${x['per_month_p10']}) lost {x['lost_6m']:>5}% stuck "
                      f"{x['stuck_6m']}% payouts {x['payouts_6m']} first {x['first_med']} grad {x['grad_6m']}% made ${x['made_per_month']}/mo "
                      f"left ${x['left_6m']} cons {x['cons_block_days']}d risk<=${x['max_risk']} "
                      f"| real {y['accounts']} acct lost {y['lost']} stuck {y['stuck']} pays {y['payouts']} ${y['paid']:,} "
                      f"(${y['per_month']}/mo) trading {y['net_trading']:+,} PF {y['pf']}", flush=True)
        out["configs"][rid] = row
        paths[rid] = T
    if not quick:
        print("eval leg (tools/atlas.score BASE) ...", flush=True)
        out["eval"] = eval_leg()
        for s in SPANS:
            e, f = out["eval"][s], out["configs"]["live"][s]
            out["configs"]["live"][s]["per_eval"] = {
                str(int(pr)): round((e["p60"] or 0) / 100.0 * f["paid_6m"] - pr) for pr in (PRICE_NOW, PRICE_USUAL)}
            for rid in out["configs"]:
                # the back-to-back path needs a passed eval per funded account: evals bought = accounts / eventual pass rate
                y = out["configs"][rid][s + "_real"]
                pp = max(0.05, (e["p60"] or 0) / 100.0)
                y["evals_needed"] = round(y["accounts"] / pp, 1)
                y["fees_63"] = round(y["accounts"] / pp * PRICE_USUAL)
                y["net_63"] = y["paid"] - y["fees_63"]
                y["net_per_month_63"] = round(y["net_63"] / y["months"]) if y["months"] else 0
            print(f"eval {s:8s} 2-wk {e['p10']}/{e['f10']} dec10 {e['dec10']} p15/f15 {e['p15']}/{e['f15']} med {e['pass_med']} "
                  f"slow {e['slow_pass']} p60 {e['p60']} -> per eval bought (6 mo funded) ${out['configs']['live'][s]['per_eval']}",
                  flush=True)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
        print("->", OUT, flush=True)
        save(out, paths)
    return out


def save(out, paths):
    """rl.save one run per sizing rule (research/runs/atlas_funded_<id>.json): the stored trades are the real back-to-back
    funded paths of every span; the funded numbers (MC payouts, loss, first payout) are in the verdict and
    research/second/atlas_funded.json."""
    from tools import runlib as rl
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    E = out.get("eval") or {}
    for rid, T in paths.items():
        r = out["configs"][rid]
        rec = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
                "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
                "bars_held": None, "regime": "", "mult": None} for t in sorted(T, key=lambda t: t["entry_t"])]
        f = lambda s: (f"${r[s]['per_month']:,}/mo to you (worst 10% ${r[s]['per_month_p10']:,}), {r[s]['payouts_per_month']} payouts a "
                       f"month, lost {r[s]['lost_6m']}% / stuck under $100 of room {r[s]['stuck_6m']}% in 6 months, first payout "
                       f"median session {r[s]['first_med']}, trading profit ${r[s]['made_per_month']:,}/mo; real path "
                       f"{r[s + '_real']['accounts']} account(s), {r[s + '_real']['lost']} lost, {r[s + '_real']['payouts']} payouts "
                       f"${r[s + '_real']['paid']:,} (${r[s + '_real']['per_month']:,}/mo)")
        ev = lambda s: (f"eval 2-week pass/fail {E[s]['p10']}/{E[s]['f10']} (dec10 {E[s]['dec10']}, p15/f15 {E[s]['p15']}/{E[s]['f15']}, "
                        f"slow_pass {E[s]['slow_pass']}%, pass_med {E[s]['pass_med']})") if s in E else ""
        verdict = (f"{TITLES[rid]}. MC 1,000 x 6 months per span. 2026 H1 (pick): {f('H1')}; {ev('H1')}. H2 (check): {f('H2')}; "
                   f"{ev('H2')}. Reference 2025: {f('2025')}; 2021-24: {f('2021-24')}.")
        rl.save("atlas_funded_" + rid, TITLES[rid], "risk", "Owner 2026-10-26: once ATLAS's 25K eval passes, what does the funded "
                "account pay a month, how often is it lost, how many payouts?", params={"plan": PLAN, "strategy": "atlas"},
                sizing={"mode": "funded", **(out["rules"][rid])}, trades=rec, scored=rl.score(rec, sess),
                status="adopt-candidate" if rid == "live" else "info", verdict=verdict,
                notes=("tools/atlas_funded.py; trades tools/atlas.account_units(BASE); size engine/account_b.qty (funded spec); "
                       "payouts engine/funded_life.track at each session's end (ready = every MFFU rule + $750 above the buffer); "
                       "$1.90 a micro. The run library's eval columns re-score these funded paths on the 50K plan: not the "
                       "funded numbers (those are in the verdict)."),
                writeup="atlas-funded", tags=["funded", "atlas", "account_b", PLAN])
        print("saved atlas_funded_" + rid, flush=True)


if __name__ == "__main__":
    main()
