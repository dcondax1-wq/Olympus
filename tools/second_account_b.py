"""Account B (owner 2026-10-22): EMA + MACD + S/R together on their OWN MFFU account - Builder 25K or Builder 50K?

Same executor as tools/second_mix.py part 2 ("separate"; units, one position, max 2 trades a day, the account's soft daily
loss over every trade of the day, the no-hedge guard against LIT's account), with the plan's own numbers:

  plan         price    target  EOD trailing max loss (lock)  soft daily loss  micros   funded: buffer  payouts       split
  builder50k   $91.80   $3,000  $2,000 (start + $100)         $1,000           40       $2,100          $500-$2,000   80%
  builder25k   $63.00   $1,500  $1,000 (start + $100)         $600             20       $1,100          $250-$1,000   80%
  (research/lit/mffu_rules.json "limits"; engine/sizing.TW_50K / TW_25K; engine/multi_account.PRESETS)

Sizes (what engine/account_b.py routes):
  need   LIT's two_week "one winner passes": micros so the trade's target covers what is left to the plan's target, capped
         at room_f of the room to the trailing floor (50K 0.6 = live lit_sizing; 25K 0.5 = the 25K preset,
         research/writeups/lit-builder-25k.md) and the soft daily loss, max micros, for 10 sessions; then safe_eval (50K
         60%, 25K 30% of the room), no reset. 25K: + the preset's day guard (a worst-case stop-out inside the room and the
         $600 soft loss, else no trade).
  safe   eval-safe: $300 (50K) / $150 (25K) risk, capped at 60% of the room (min 1 micro) and the soft daily loss.
Funded view: the same strategies at the safe size on the plan's sim-funded account (63 / 126 sessions).

    python -X utf8 tools/second_account_b.py          # -> research/second/account_b.json + a table (~1 min)
    python -X utf8 tools/second_account_b.py save     # + rl.save the runs acctb_*
Paper only. Needs research/runs/_cache/second_mix_units.pkl (python -X utf8 tools/second_mix.py units, ~20 s).
"""
from __future__ import annotations

import collections
import copy
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import account_b as AB  # noqa: E402
from tools import second_mix as M  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "account_b.json")
NAMES = ("EMA", "MD", "SR")
MIN_ROOM = 100.0
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
SPANS = ("H1", "H2", "2025", "2021-24")

PLANS = {
    "builder50k": {"label": "Builder 50K", "price": 91.80, "preset": "mffu_builder_50k", "safe_usd": 300.0,
                   "eval": dict(SZ.TW_50K), "funded": dict(SZ.FD_50K)},
    "builder25k": {"label": "Builder 25K", "price": 63.00, "preset": "mffu_builder_25k", "safe_usd": 150.0,
                   "eval": dict(SZ.TW_25K),
                   "funded": {**SZ.FD_50K, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "buffer": 1100.0, "pay_min": 250.0,
                              "pay_max": 1000.0, "max_micros": 20, "scale": 0.5}},
}


def sizing_cfg(plan: str) -> dict:
    """live_model.json lit_sizing + the plan preset's sizing (engine/multi_account.sizing_cfg) in two_week mode: exactly
    what engine/account_b.py hands engine/sizing.lit_qty for a "need" trade."""
    base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
    spec = MA.normalize({"id": "b", "preset": PLANS[plan]["preset"], "mode": "two_week", "adapter": "paper"})
    c = MA.sizing_cfg(base, spec)
    c.pop("eval_start", None)
    return c


class Plan:
    """Patches tools/second_mix's module constants (target, max loss, daily loss, price, funded rules, sizes) for a plan."""

    def __init__(self, plan):
        self.plan = plan
        P = PLANS[plan]
        self.P = P
        self.cfg = sizing_cfg(plan)
        self.maxq = int(P["eval"]["max_micros"])
        self.safe_rule = f"usd{int(P['safe_usd'])}_safe_dll"

    def __enter__(self):
        self._old = {k: getattr(M, k) for k in ("TGT", "MLL", "DLL", "LOCK", "PRICE", "FD", "lit_q", "second_q", "play_day")}
        E = self.P["eval"]
        M.TGT, M.MLL, M.DLL, M.LOCK, M.PRICE = float(E["target"]), float(E["mll"]), float(E["dll"]), float(E["lock"]), self.P["price"]
        M.FD = dict(self.P["funded"])
        cfg, maxq, old_play = self.cfg, self.maxq, self._old["play_day"]

        def lit_q(t, st, c=None):
            m0 = lit.qty_for(t["risk"])
            return SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, c or cfg, room=st["room"],
                              state=st, max_micros=maxq, learning=None)["qty"] if m0 else 0

        spec = AB.normalize({"account": "research", "plan": self.plan, "eval_start": "2026-01-02"}, lit_account=None)

        def second_q(t, st, rule):
            r = t["risk"]
            if rule.startswith("acctb_"):
                # exactly what engine/account_b.py routes (engine/account_b.qty on the plan)
                return AB.qty({**spec, "sizing": rule[6:]}, {"risk_pts": r, "tgt_pts": t["tgt"]}, dict(st))["qty"]
            if rule.startswith("need"):
                q = lit_q(t, st)
                return 0 if q <= 0 else max(1, int(q * float(rule[4:]) + 1e-9))
            base, *flags = rule.split("_")
            q = min(maxq, int(float(base[3:]) / (r * M.PV)))
            if "safe" in flags and q > 0:
                q = max(1, min(q, int(0.6 * max(0.0, st["room"]) / (r * M.PV))))
            if "dll" in flags:
                q = min(q, M.dll_cap(t, st))
            return max(0, q)

        def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=None, reserve=True, extra=None):
            return old_play(L, day, bal, floor, session, rule, pre, max_day, lost, litcfg, M.DLL if dll is None else dll, reserve, extra)

        M.lit_q, M.second_q, M.play_day = lit_q, second_q, play_day
        return self

    def __exit__(self, *a):
        for k, v in self._old.items():
            setattr(M, k, v)


def run_eval(days, by, rule, horizon=20, keep=None):
    """tools/second_mix.run_eval + the end state: (result, sessions, room at the end). Account B has no LIT (reserve off)."""
    bal = peak = 0.0
    floor = -M.MLL
    for kk, day in enumerate(days[:horizon]):
        cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, kk + 1, rule, False, 2, None, reserve=False)
        if keep is not None:
            keep.extend(recs)
        if failed:
            return "FAIL", kk + 1, 0.0
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1, 0.0
        peak = max(peak, bal)
        floor = min(max(floor, peak - M.MLL), M.LOCK)
        if bal >= M.TGT:
            return "PASS", kk + 1, bal - floor
        if bal - floor < MIN_ROOM:
            # stuck (engine/multi_account Account.entry_block / engine/account_b.py): 1 micro no longer fits a stop, the bot
            # stops trading this account; the owner buys a new one
            return "STUCK", kk + 1, bal - floor
    return "OPEN", min(len(days), horizon), bal - floor


def run_funded(days, by, rule):
    """tools/second_mix.run_funded with the plan's funded rules (M.FD) and the safe size for the second strategies."""
    FD = M.FD
    bal = peak = 0.0
    floor = -FD["mll"]
    paid, n_pay, last_bal, cyc = 0.0, 0, 0.0, []
    for k, day in enumerate(days):
        cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, 99, rule, False, dll=FD["dll"], reserve=False)
        if failed or bal + cum <= floor:
            return {"paid": paid, "n": n_pay, "blown": k + 1}
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - FD["mll"]), FD["lock"])
        if recs:
            cyc.append(cum)
        if k + 1 < FD["first_wait"] or len(cyc) < FD["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or max(cyc) > FD["cons"] * prof:
            continue
        amt = min(bal - FD["buffer"], FD["pay_max"])
        if amt < FD["pay_min"]:
            continue
        paid += amt * FD["split"]; n_pay += 1; bal -= amt; last_bal, cyc = bal, []
        if n_pay >= FD["max_payouts"]:
            break
    return {"paid": paid, "n": n_pay, "blown": None}


def score(U, rule, span, frule):
    by = M.by_day(U)
    allS = M.units()["sessions"]
    a, z = M.SPANS[span]
    ix = [i for i, d in enumerate(allS) if a <= d <= z]
    S = [allS[i] for i in ix]
    res = [(run_eval(S[i:i + 20], by, rule), len(S) - i) for i in range(len(S))]
    o = {"starts": len(S)}
    for lab, h in (("10", 10), ("15", 15), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
        o["s" + lab] = round(100.0 * sum(1 for r in R if r[0] == "STUCK" and r[1] <= h) / N, 1)
        o["dead" + lab] = round(o["f" + lab] + o["s" + lab], 1)
    o["dec10"] = round(o["p10"] + o["dead10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    E = [run_eval(allS[i:i + 60], by, rule, 60) for i in ix if i + 60 <= len(allS)]
    o["p60"] = round(100.0 * sum(1 for r in E if r[0] == "PASS") / len(E), 1) if E else None
    o["f60"] = round(100.0 * sum(1 for r in E if r[0] in ("FAIL", "STUCK")) / len(E), 1) if E else None
    for lab, h in (("3m", 63), ("6m", 126)):
        Fd = [run_funded(allS[i:i + h], by, frule) for i in ix if i + h <= len(allS)]
        o["fund_n_" + lab] = len(Fd)
        o["fund_paid_" + lab] = round(float(np.mean([f["paid"] for f in Fd]))) if Fd else None
        o["fund_lost_" + lab] = round(100.0 * sum(1 for f in Fd if f["blown"]) / len(Fd), 1) if Fd else None
    price = M.PRICE
    o["cost_2wk_pass"] = round(price / (o["p10"] / 100.0)) if o["p10"] > 0 else None
    o["cost_pass"] = round(price / (o["p60"] / 100.0)) if o.get("p60") else None
    for lab in ("3m", "6m"):
        if o["p60"] is not None and o["fund_paid_" + lab] is not None:
            o["ev_eval_" + lab] = round(o["p60"] / 100.0 * o["fund_paid_" + lab] - price)
    # back-to-back eval path ($, no reset: a new eval after each pass / fail)
    k, T, n = 0, [], collections.Counter()
    while k < len(S):
        r, used, _ = run_eval(S[k:], by, rule, len(S) - k, keep=T)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    o.update(n=len(T), tpw=round(len(T) / (len(S) / 5), 2), net=round(float(p.sum())), per_month=round(float(p.sum()) / (len(S) / 21)),
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
             b2b=f"{n['PASS']}/{n['FAIL']}/{n['STUCK']}/{n['OPEN']}", evals_bought=n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0),
             max_risk=round(max((t["risk_usd"] for t in T), default=0.0)),
             med_risk=round(float(np.median([t["risk_usd"] for t in T]))) if T else 0,
             med_qty=float(np.median([t["qty"] for t in T])) if T else 0,
             by_src={s: [sum(1 for t in T if t["src"] == s), round(sum(t["pnl"] for t in T if t["src"] == s))] for s in sorted({t["src"] for t in T})})
    o["path_net_less_fees"] = round(o["net"] - o["evals_bought"] * price)
    return o, T


def check_50k():
    """Builder 50K + need + no-hedge here == second-mix.md account B (H1 72.3/4.2, H2 53.6/0.0; second_mix has no stuck rule)."""
    global MIN_ROOM
    U = M.acct_units(NAMES, nohedge=True)
    keep, MIN_ROOM = MIN_ROOM, 0.0
    try:
        with Plan("builder50k") as pl:
            o = {s: score(U, "need1.0", s, pl.safe_rule)[0] for s in ("H1", "H2")}
            o2 = {s: score(U, "acctb_need", s, pl.safe_rule)[0] for s in ("H1", "H2")}
    finally:
        MIN_ROOM = keep
    ok = (o["H1"]["p10"], o["H1"]["f10"], o["H2"]["p10"], o["H2"]["f10"]) == (72.3, 4.2, 53.6, 0.0) and \
        all(o[s][k] == o2[s][k] for s in ("H1", "H2") for k in ("p10", "f10", "p20", "f20", "net"))
    print("  engine/account_b.qty need on the 50K:", {s: (o2[s]["p10"], o2[s]["f10"], o2[s]["net"]) for s in o2}, flush=True)
    print(f"CHECK 50K need vs second-mix.md: H1 {o['H1']['p10']}/{o['H1']['f10']} H2 {o['H2']['p10']}/{o['H2']['f10']} ->",
          "OK" if ok else "DIFF", flush=True)
    return ok


def main(save=False):
    M.units()
    ok = check_50k()
    U = M.acct_units(NAMES, nohedge=True)
    out = {"check_50k_vs_second_mix": ok, "plans": {}, "paths": {}}
    for plan in PLANS:
        with Plan(plan) as pl:
            for sz, rule in (("need", "acctb_need"), ("safe", "acctb_safe")):
                key = f"{plan}|{sz}"
                o, P = {}, []
                for s in SPANS:
                    o[s], T = score(U, rule, s, pl.safe_rule)
                    P += T
                out["plans"][key] = o
                out["paths"][key] = P
                f = lambda s: (f"2w {o[s]['p10']}/{o[s]['f10']} st {o[s]['s10']} 1m {o[s]['p20']}/{o[s]['f20']} med {o[s]['pass_med']} "
                               f"p60 {o[s]['p60']} path {o[s]['net']:+,} ({o[s]['per_month']:+,}/mo) DD {o[s]['dd']:,} risk {o[s]['med_risk']}/{o[s]['max_risk']} "
                               f"fund3m ${o[s]['fund_paid_3m']} lost {o[s]['fund_lost_3m']}% ev ${o[s].get('ev_eval_3m')}")
                print(key)
                for s in SPANS:
                    print(f"   {s:8s} {f(s)}", flush=True)
    paths = out.pop("paths")
    out["sizing_cfg"] = {p: sizing_cfg(p) for p in PLANS}
    out["plans_rules"] = {p: {k: v for k, v in PLANS[p].items()} for p in PLANS}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    if save:
        store(out, paths)
    return out


RUNS = {"builder50k|need": ("acctb_50k_need", "Account B on a Builder 50K: EMA + MACD + S/R, two_week need size, no-hedge", "promising"),
        "builder25k|need": ("acctb_25k_need", "Account B on a Builder 25K: EMA + MACD + S/R, 25K two_week need size (50% room), no-hedge", "adopt-candidate"),
        "builder50k|safe": ("acctb_50k_safe", "Account B on a Builder 50K: EMA + MACD + S/R at $300 + 60% room cap, no-hedge", "info"),
        "builder25k|safe": ("acctb_25k_safe", "Account B on a Builder 25K: EMA + MACD + S/R at $150 + 60% room cap, no-hedge", "info")}


def store(out, paths):
    from tools import runlib as rl
    Q = "Owner 2026-10-22: run the second strategies on their own prop account (account B) - Builder 25K or 50K?"
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    for key, (rid, title, status) in RUNS.items():
        T = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
              "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
              "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in paths[key]]
        x = out["plans"][key]
        f = lambda s: (f"{x[s]['tpw']}/wk path {x[s]['net']:+,} (${x[s]['per_month']:,}/mo) DD {x[s]['dd']:,}; 2-week pass/fail "
                       f"{x[s]['p10']}/{x[s]['f10']}, 1 month {x[s]['p20']}/{x[s]['f20']}, median {x[s]['pass_med']} sessions, "
                       f"funded 3 mo ${x[s]['fund_paid_3m']}, $ per eval bought {x[s].get('ev_eval_3m')}")
        plan, sz = key.split("|")
        rl.save(rid, title, "other", Q, params={"accounts": list(NAMES), "plan": plan, "size": sz, "no_hedge": True},
                sizing={"plan": plan, "size": sz}, trades=T, scored=rl.score(T, sess), status=status,
                verdict=f"Account B alone (fresh eval every session, 20 sessions; $ = back-to-back eval path). 2026 H1 (pick) {f('H1')}. "
                        f"H2 (check) {f('H2')}. Reference 2025 {f('2025')}; 2021-24 {f('2021-24')}.",
                notes="tools/second_account_b.py; stored trades = the back-to-back eval path of each span; the run library's own "
                      "eval columns re-score that path on the 50K plan and are not the published odds (those are in the verdict).",
                writeup="second-account-b", tags=["second", "account_b"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
