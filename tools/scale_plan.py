"""The scaling plan (owner 2026-10-22: "LIT is on the 50K, ATLAS (EMA+MACD+S/R, account B) on the 25K, then eventually we
just scale. And keep scaling."). Research only, paper only: nothing here trades, arms or routes anything.

The ladder (2 -> 4 -> 6 -> 8 -> 10 accounts), each step = two accounts bought a week apart (the stagger rule):
  step 0  today        LIT on the MFFU Builder 50K eval + ATLAS (EMA + MACD + S/R, account B) on an MFFU Builder 25K
  step 1  +2 -> 4      LIT copies on a LucidPro 50K and a FundedNext Rapid Daily 50K       when: the first payout landed
  step 2  +2 -> 6      LIT copy on a 2nd LucidPro + ATLAS on a LucidPro 50K                 when: 3 funded + $2,000 paid out
  step 3  +2 -> 8      LIT copy on a 2nd FundedNext + ATLAS on a FundedNext Rapid Daily     when: 4 funded + $5,000 paid out
  step 4  +2 -> 10     LIT copy on a 3rd LucidPro + ATLAS on a 2nd FundedNext               when: 6 funded + $10,000 paid out
  every step also needs: cash (budget $300 + payouts - every fee so far) >= the step's two eval prices, and no funded account
  lost in the last 10 sessions.
Why these firms (research/props/firms.json, lit-funded-firms.md, second-account-b.md): MFFU allows 1 funded Builder 50K and 2
funded Builder 25Ks per person (copy trading between own accounts unclear: so MFFU only holds LIT once and ATLAS once);
Lucid allows bots and trade copiers in writing (5 funded per household, sources say 5 or 10: the plan keeps 4 there);
FundedNext allows bots and "copying your own accounts only" (no futures cap found; up to 5 live). Tradeify (same bot at
another firm banned), Bulenox (no copying, approval), Topstep (no NinjaTrader), Apex / TPT / Alpha / Elite are out.

Models (the stored studies' own code, same Monte Carlo paths for every account so the accounts win and lose together):
  LIT accounts    tools/lit_funded_combo.py on the live LIT trades (t_check + be_off, scale-in OFF = variant t15_be_off):
                  each plan's eval and funded sizing as picked there (research/lit/funded_combo.json), FF.run_eval /
                  run_funded, re-buy after a fail / lost / finished account. Reproduces the stored 6-month numbers exactly.
  ATLAS accounts  tools/second_account_b.py: EMA + MACD + S/R on its own account, no-hedge against LIT, the "need" eval size
                  (engine/account_b.qty) and the safe funded size ($150 25K / $300 50K, 60% room cap), re-buy after a fail /
                  stuck / lost. On Lucid / FundedNext the eval is the Builder 50K's (same $3,000 / $2,000 / $1,000 numbers;
                  Lucid's $1,200 daily loss is not used = a bit conservative) and the payouts follow that firm's rules.
  Paths           1,000 (static stacks) / 600 (the ladder) bootstrap paths in 5-session blocks of each span, 21 sessions a
                  month: 2026 H1 (Jan-Jun) and H2 (Jul-Oct, the half to quote), 2025 and 2021-24 = the bad-year cases.
  Stacks          all accounts of a step held from the start (a week apart): months 7-12 = the steady $ a month at that step
                  (payouts to you minus re-buy fees), worst months, P(month <= $0).
  Ladder          start at step 0 (50K on session 0, 25K on session 5), each step bought the session after its trigger:
                  months and eval $ to reach each step, % of paths that get there within 24 months.
  Risk            every trade's $ at risk recorded per account type and phase (eval / funded): max simultaneous risk =
                  the sum over the step's accounts (all copies of a signal fire together) at the median and at the max.

  python -X utf8 tools/scale_plan.py           # -> research/second/scale.json + the ladder table (~5-10 min on 4 cores)
  python -X utf8 tools/scale_plan.py check     # the LIT / ATLAS executors reproduce the stored numbers
  python -X utf8 tools/scale_plan.py table     # rebuild the table from research/second/scale.json (no Monte Carlo)
Needs research/runs/_cache/lit_fc_units_t15_be_off.json + lit_2wk_unit_live.json (tools/lit_funded_combo.py units) and
second_mix_units.pkl (python -X utf8 tools/second_mix.py units). Write-up: research/writeups/scale-plan.md.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "research", "second", "scale.json")
COMBO = os.path.join(ROOT, "research", "lit", "funded_combo.json")
ACCTB = os.path.join(ROOT, "research", "second", "account_b.json")
VARIANT = "t15_be_off"                          # live LIT now (scale-in OFF)
SPANS = ("H1", "H2", "2025", "2021-24")
SPAN_DATES = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
              "2021-24": ("2021-01-01", "2024-12-31")}
MONTH = 21
H_STACK, H_LADDER = 252, 504                    # 12 months (steady = months 7-12), 24 months
N_STACK, N_LADDER = 1000, 600
STAGGER = 5
BUDGET = 300.0                                  # research/props/business.json planner budget_usd
LOST_QUIET = 10                                 # no new step within 10 sessions of a lost funded account
DAY_CAP_USD = 3000.0                            # the cross-account cap on $ at risk at the same time (see risk_cap)

# account types: strategy, plan, firm, price (owner's / study price with a code; list for the "no code" case)
TYPES = {
    "lit_b50": {"strategy": "LIT", "plan": "mffu_builder_50k", "firm": "MFFU", "label": "MFFU Builder 50K", "price": 91.80, "list": 153.0,
                "price_basis": "owner's price (paid 2026-10-18)"},
    "atlas_b25": {"strategy": "ATLAS", "plan": "mffu_builder_25k", "firm": "MFFU", "label": "MFFU Builder 25K", "price": 63.0, "list": 105.0,
                  "price_basis": "owner's price"},
    "lit_l50": {"strategy": "LIT", "plan": "lucid_pro_50k", "firm": "Lucid", "label": "LucidPro 50K", "price": 115.40, "list": 192.0,
                "price_basis": "with code DGT (affiliate page 2026-10-19, unconfirmed; list $129.50-$192)"},
    "lit_fn50": {"strategy": "LIT", "plan": "fn_rapid_daily_50k", "firm": "FundedNext", "label": "FundedNext Rapid Daily 50K", "price": 169.99,
                 "list": 299.98, "price_basis": "study price with a code (unconfirmed; FundedNext's own page: up to 50% off a first buy)"},
    "atlas_l50": {"strategy": "ATLAS", "plan": "lucid_pro_50k", "firm": "Lucid", "label": "LucidPro 50K", "price": 115.40, "list": 192.0,
                  "price_basis": "as LIT's LucidPro"},
    "atlas_fn50": {"strategy": "ATLAS", "plan": "fn_rapid_daily_50k", "firm": "FundedNext", "label": "FundedNext Rapid Daily 50K",
                   "price": 169.99, "list": 299.98, "price_basis": "as LIT's FundedNext"},
}
# the ladder: who is added at each step and the trigger (all conditions; plus cash >= the step's prices, no recent loss)
STEPS = [
    {"n": 0, "add": ["lit_b50", "atlas_b25"], "trigger": {},
     "action": "LIT on the MFFU Builder 50K eval + ATLAS on an MFFU Builder 25K", "why": "today's plan (owner 2026-10-22)"},
    {"n": 1, "add": ["lit_l50", "lit_fn50"], "trigger": {"payouts_n": 1},
     "action": "buy a LucidPro 50K, a week later a FundedNext Rapid Daily 50K; both copy LIT",
     "why": "the first payout proves the whole chain (eval -> funded -> money) and pays most of the two evals"},
    {"n": 2, "add": ["lit_l50", "atlas_l50"], "trigger": {"funded": 3, "payouts_usd": 2000},
     "action": "buy a 2nd LucidPro 50K (LIT copy) and a LucidPro 50K for ATLAS (an ATLAS copy)",
     "why": "3 accounts funded at once and $2,000 paid out: the copies work; ATLAS on a 2nd firm spreads the luck"},
    {"n": 3, "add": ["lit_fn50", "atlas_fn50"], "trigger": {"funded": 4, "payouts_usd": 5000},
     "action": "buy a 2nd FundedNext Rapid Daily 50K (LIT) and one for ATLAS",
     "why": "4 funded at once and $5,000 paid out"},
    {"n": 4, "add": ["lit_l50", "atlas_fn50"], "trigger": {"funded": 6, "payouts_usd": 10000},
     "action": "buy a 3rd LucidPro 50K (LIT) and a 2nd FundedNext for ATLAS",
     "why": "6 funded at once and $10,000 paid out; after this: per-firm caps (Lucid 5 per household, MFFU 1x50K + 2x25K)"},
]


def step_types(n: int) -> list:
    out = []
    for s in STEPS[: n + 1]:
        out += s["add"]
    return out


def step_cost(n: int, list_prices=False) -> float:
    return round(sum(TYPES[t]["list" if list_prices else "price"] for t in STEPS[n]["add"]), 2)


# ================================================================================================ the executors
_E = {}


def setup():
    """Load the stored studies' executors once (LIT: lit_funded_combo on t15_be_off; ATLAS: second_account_b)."""
    if _E:
        return _E
    import lit_funded_combo as C
    from tools import second_mix as M
    import second_account_b as AB2
    FF = C.FF
    C.use(VARIANT)
    for k, v in SPAN_DATES.items():
        FF.SPAN.setdefault(k, v)
    d = json.load(open(COMBO, encoding="utf-8"))[VARIANT]
    R = {p["id"]: p["results"] for p in d["plans"]}
    base = {p["id"]: p for p in FF.plans()}
    LP = {}
    for pid in ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"):
        P = dict(base[pid])
        if pid != "mffu_builder_50k":
            P.pop("fixed_eval", None)
        LP[pid] = (P, R[pid]["eval_cfg"], R[pid]["funded_cfg"])
    M.units()
    U = M.acct_units(AB2.NAMES, nohedge=True)
    by_atlas = M.by_day(U)
    # risk recorder: every LIT trade's micros x stop pts x $2 (combo.trade_pnl is looked up at call time)
    orig_tp = C.trade_pnl

    def tp(t, q, *a, **k):
        rec = _E.get("rec")
        if rec is not None and q and q > 0:
            rec.append(float(q) * float(t["risk"]) * FF.PV)
        return orig_tp(t, q, *a, **k)

    C.trade_pnl = tp
    fd50 = {**AB2.PLANS["builder50k"]["funded"]}
    ATL = {
        "mffu_builder_25k": {"plan": "builder25k", "funded": dict(AB2.PLANS["builder25k"]["funded"])},
        "lucid_pro_50k": {"plan": "builder50k", "funded": {**fd50, "dll": 1200.0, "buffer": 2100.0, "pay_min": 500.0, "pay_max": 2000.0,
                                                           "split": 0.9, "cons": 0.4, "cycle_days": 3, "first_wait": 1, "max_payouts": 5}},
        "fn_rapid_daily_50k": {"plan": "builder50k", "funded": {**fd50, "dll": 1000.0, "buffer": 2100.0, "pay_min": 250.0, "pay_max": 1200.0,
                                                                "split": 0.9, "cons": 1e9, "cycle_days": 1, "first_wait": 1, "max_payouts": 5}},
    }
    _E.update(C=C, FF=FF, M=M, AB2=AB2, LP=LP, R=R, by_atlas=by_atlas, ATL=ATL, sess=FF.data()["sess"], rec=None)
    return _E


def lit_life(pid, seq, offset, horizon):
    """tools/lit_funded_firms.life from session `offset` (absolute k), with the fee times and the funded spans kept."""
    E = setup()
    FF = E["FF"]
    P, ce, cf = E["LP"][pid]
    by = FF.data()["by"]
    k = offset
    fees, pays, fund = [], [], []
    while k < horizon:
        fees.append((k, P["price"]))
        E["phase"] = "eval"
        r, n = FF.run_eval(P, ce, seq[k:horizon], by, horizon=horizon - k)
        if r != "PASS":
            if r == "OPEN":
                break
            k += n
            continue
        k += n
        E["phase"] = "funded"
        f = FF.run_funded(P, cf, seq[:horizon], by, start=k)
        pays.extend((int(a), float(v)) for a, v in f["pay_at"])
        if f["blown"] is not None:
            fund.append((k, int(f["blown"]), "lost"))
            k = int(f["blown"]) + 1
            continue
        if f["grad"] is not None:
            fund.append((k, int(f["grad"]), "done"))
            k = int(f["grad"]) + 1
            continue
        fund.append((k, horizon, "alive"))
        break
    return {"fees": fees, "pays": pays, "fund": fund}


def _atlas_funded(days, start, horizon, rule, FD, M, rec):
    """tools/second_account_b.run_funded from session `start` with the payout times kept."""
    bal = peak = 0.0
    floor = -FD["mll"]
    pays, n_pay, last_bal, cyc = [], 0, 0.0, []
    for k in range(start, horizon):
        day = days[k]
        cum, recs, failed = M.play_day(M_BY(day), day, bal, floor, 99, rule, False, dll=FD["dll"], reserve=False)
        if rec is not None:
            rec.extend(float(t["risk_usd"]) for t in recs if t.get("risk_usd"))
        if failed or bal + cum <= floor:
            return pays, k, "lost"
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - FD["mll"]), FD["lock"])
        if recs:
            cyc.append(cum)
        if k - start + 1 < FD["first_wait"] or len(cyc) < FD["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or max(cyc) > FD["cons"] * prof:
            continue
        amt = min(bal - FD["buffer"], FD["pay_max"])
        if amt < FD["pay_min"]:
            continue
        pays.append((k, amt * FD["split"]))
        n_pay += 1
        bal -= amt
        last_bal, cyc = bal, []
        if n_pay >= FD["max_payouts"]:
            return pays, k, "done"
    return pays, horizon, "alive"


def M_BY(day):
    return _E["by_atlas"].get(day, ())


def atlas_life(pid, seq, offset, horizon):
    """ATLAS (EMA + MACD + S/R, account B) on its own account: the need-size eval (engine/account_b.qty), the safe funded size,
    a re-buy after a fail / stuck / lost / finished account."""
    E = setup()
    M, AB2 = E["M"], E["AB2"]
    A = E["ATL"][pid]
    sess = E["sess"]
    days = [sess[i] for i in seq]
    price = TYPES["atlas_b25" if pid == "mffu_builder_25k" else "atlas_l50" if pid == "lucid_pro_50k" else "atlas_fn50"]["price"]
    fees, pays, fund = [], [], []
    with AB2.Plan(A["plan"]) as pl:
        M.FD = dict(A["funded"])
        k = offset
        while k < horizon:
            fees.append((k, price))
            keep = [] if E.get("rec") is not None else None
            r, n, _ = AB2.run_eval(days[k:horizon], E["by_atlas"], "acctb_need", horizon=horizon - k, keep=keep)
            if keep is not None:
                E["rec"].extend(("eval", float(t["risk_usd"])) for t in keep if t.get("risk_usd"))
            if r == "OPEN":
                break
            k += n
            if r != "PASS":
                continue
            frec = [] if E.get("rec") is not None else None
            p, end, how = _atlas_funded(days, k, horizon, pl.safe_rule, M.FD, M, frec)
            if frec is not None:
                E["rec"].extend(("funded", x) for x in frec)
            pays.extend(p)
            fund.append((k, end, how))
            if how == "alive":
                break
            k = end + 1
    return {"fees": fees, "pays": pays, "fund": fund}


def life(t, seq, offset, horizon):
    T = TYPES[t]
    return (lit_life if T["strategy"] == "LIT" else atlas_life)(T["plan"], seq, offset, horizon)


def seqs(span, n, length, seed=31):
    E = setup()
    return E["FF"].mc_seqs(span, n, length, seed)


# ================================================================================================ checks
def check():
    """LIT: this executor == the stored 6-month life (funded_combo.json t15_be_off). ATLAS: the 25K's eval odds on every
    H1 session == research/second/account_b.json (68.9 / 0.0 within 10 sessions)."""
    E = setup()
    FF = E["FF"]
    ok = {}
    for pid in E["LP"]:
        stored = E["R"][pid]["life"]["H2"]["net_per_month"]
        L = [lit_life(pid, s, 0, FF.H6) for s in seqs("H2", 1500, FF.H6)]
        net = np.mean([sum(v for _, v in x["pays"]) - sum(v for _, v in x["fees"]) for x in L]) / 6
        ok[f"lit {pid} H2 $/mo"] = [round(float(net)), stored]
    M, AB2 = E["M"], E["AB2"]
    a, z = M.SPANS["H1"]
    allS = M.units()["sessions"]
    S = [d for d in allS if a <= d <= z]
    with AB2.Plan("builder25k"):
        res = [(AB2.run_eval(S[i:i + 20], E["by_atlas"], "acctb_need"), len(S) - i) for i in range(len(S))]
    R10 = [r for r, av in res if av >= 10]
    p10 = round(100.0 * sum(1 for r in R10 if r[0] == "PASS" and r[1] <= 10) / len(R10), 1)
    stored = json.load(open(ACCTB, encoding="utf-8"))["plans"]["builder25k|need"]["H1"]["p10"]
    ok["atlas 25K H1 p10"] = [p10, stored]
    for k, v in ok.items():
        print(f"  {k}: here {v[0]} stored {v[1]} {'OK' if abs(v[0] - v[1]) <= max(1, 0.02 * abs(v[1])) else 'DIFF'}", flush=True)
    return ok


# ================================================================================================ static stacks (steady state)
def flows(L, horizon):
    """Per path: payouts / fees per session index -> monthly arrays."""
    nm = horizon // MONTH
    pay, fee = np.zeros(nm), np.zeros(nm)
    for x in L:
        for k, v in x["pays"]:
            if k < horizon:
                pay[k // MONTH] += v
        for k, v in x["fees"]:
            if k < horizon:
                fee[k // MONTH] += v
    return pay, fee


def stack_job(arg):
    n, span, npaths = arg
    setup()
    types = step_types(n)
    rows = []
    for s in seqs(span, npaths, H_STACK, 41):
        L = [life(t, s, STAGGER * i, H_STACK) for i, t in enumerate(types)]
        pay, fee = flows(L, H_STACK)
        fund_now = [sum(1 for x in L for (a, b, _) in x["fund"] if a <= m * MONTH < b) for m in range(H_STACK // MONTH)]
        lost = sum(1 for x in L for f in x["fund"] if f[2] == "lost")
        rows.append((pay, fee, fund_now, lost))
    pay = np.array([r[0] for r in rows])
    fee = np.array([r[1] for r in rows])
    net = pay - fee
    st = net[:, 6:12]                                      # months 7-12
    m_tot = st.reshape(-1)
    return {"step": n, "span": span, "accounts": len(types), "paths": npaths,
            "steady_net_month": round(float(st.mean())), "steady_pay_month": round(float(pay[:, 6:12].mean())),
            "steady_fee_month": round(float(fee[:, 6:12].mean())), "first6_net_month": round(float(net[:, :6].mean())),
            "month_p10": round(float(np.percentile(m_tot, 10))), "month_p5": round(float(np.percentile(m_tot, 5))),
            "month_med": round(float(np.median(m_tot))), "month_le0": round(100.0 * float((m_tot <= 0).mean()), 1),
            "six_months_le0": round(100.0 * float((st.sum(axis=1) <= 0).mean()), 1),
            "year_net": round(float(net.sum(axis=1).mean())), "year_net_p10": round(float(np.percentile(net.sum(axis=1), 10))),
            "funded_avg_m7_12": round(float(np.mean([np.mean(r[2][6:12]) for r in rows])), 2),
            "lost_per_year": round(float(np.mean([r[3] for r in rows])), 2),
            "by_month_net": [round(float(x)) for x in net.mean(axis=0)]}


# ================================================================================================ the ladder (dynamic)
def trigger_k(L, tr, start, horizon, cost, budget):
    """The first session k >= start where every condition of the trigger holds (state after session k's close)."""
    pay = np.zeros(horizon)
    fee = np.zeros(horizon)
    npay = np.zeros(horizon)
    funded = np.zeros(horizon)
    lostk = np.full(horizon, -10 ** 6)
    for x in L:
        for k, v in x["pays"]:
            if k < horizon:
                pay[k] += v
                npay[k] += 1
        for k, v in x["fees"]:
            if k < horizon:
                fee[k] += v
        for a, b, how in x["fund"]:
            funded[a:min(b, horizon)] += 1
            if how == "lost" and b < horizon:
                lostk[b] = b
    cp, cf, cn = np.cumsum(pay), np.cumsum(fee), np.cumsum(npay)
    last_lost = np.maximum.accumulate(lostk)
    cash = budget + cp - cf
    ok = (cash >= cost) & ((np.arange(horizon) - last_lost) > LOST_QUIET)
    if tr.get("payouts_n"):
        ok &= cn >= tr["payouts_n"]
    if tr.get("payouts_usd"):
        ok &= cp >= tr["payouts_usd"]
    if tr.get("funded"):
        ok &= funded >= tr["funded"]
    ok[:start] = False
    idx = np.flatnonzero(ok)
    return (int(idx[0]), float(cf[idx[0]]), float(cp[idx[0]])) if idx.size else (None, float(cf[-1]), float(cp[-1]))


def ladder_path(seq, horizon=H_LADDER, budget=BUDGET):
    L = [life("lit_b50", seq, 0, horizon), life("atlas_b25", seq, STAGGER, horizon)]
    types = ["lit_b50", "atlas_b25"]
    hit = [{"k": 0, "fees": 91.80 + 63.0, "paid": 0.0}]
    k0 = 0
    for st in STEPS[1:]:
        k, fees, paid = trigger_k(L, st["trigger"], k0 + 1, horizon, step_cost(st["n"]), budget)
        if k is None:
            hit.append(None)
            break
        for i, t in enumerate(st["add"]):
            off = k + 1 + STAGGER * i
            if off < horizon:
                L.append(life(t, seq, off, horizon))
                types.append(t)
        hit.append({"k": k, "fees": round(fees + step_cost(st["n"]), 2), "paid": round(paid, 2)})
        k0 = k
    while len(hit) < len(STEPS):
        hit.append(None)
    pay, fee = flows(L, horizon)
    return {"hit": hit, "pay": pay, "fee": fee, "evals": sum(len(x["fees"]) for x in L)}


def ladder_job(arg):
    span, npaths = arg
    setup()
    P = [ladder_path(s) for s in seqs(span, npaths, H_LADDER, 53)]
    out = {"span": span, "paths": npaths, "steps": []}
    for st in STEPS:
        H = [p["hit"][st["n"]] for p in P]
        got = [h for h in H if h is not None]
        months = [h["k"] / MONTH for h in got]
        out["steps"].append({"step": st["n"], "reach_24m": round(100.0 * len(got) / npaths, 1),
                             "reach_12m": round(100.0 * sum(1 for h in got if h["k"] < 252) / npaths, 1),
                             "months_med": round(float(np.median(months)), 1) if got else None,
                             "months_p25": round(float(np.percentile(months, 25)), 1) if got else None,
                             "months_p75": round(float(np.percentile(months, 75)), 1) if got else None,
                             "fees_to_reach_med": round(float(np.median([h["fees"] for h in got]))) if got else None,
                             "fees_to_reach_mean": round(float(np.mean([h["fees"] for h in got]))) if got else None,
                             "paid_at_reach_med": round(float(np.median([h["paid"] for h in got]))) if got else None})
    pay = np.array([p["pay"] for p in P])
    fee = np.array([p["fee"] for p in P])
    net = pay - fee
    out["by_month_net_mean"] = [round(float(x)) for x in net.mean(axis=0)]
    out["by_month_net_p10"] = [round(float(x)) for x in np.percentile(net, 10, axis=0)]
    out["cum_net_med"] = [round(float(x)) for x in np.median(np.cumsum(net, axis=1), axis=0)]
    out["cum_net_p10"] = [round(float(x)) for x in np.percentile(np.cumsum(net, axis=1), 10, axis=0)]
    out["fees_24m_mean"] = round(float(fee.sum(axis=1).mean()))
    out["paid_24m_mean"] = round(float(pay.sum(axis=1).mean()))
    out["net_24m_le0"] = round(100.0 * float((net.sum(axis=1) <= 0).mean()), 1)
    return out


# ================================================================================================ risk per account type
def risk_job(arg):
    t, span, npaths = arg
    E = setup()
    ev, fu = [], []
    for s in seqs(span, npaths, H_STACK, 61):
        E["rec"] = []
        E["phase"] = "eval"
        if TYPES[t]["strategy"] == "LIT":
            # tag LIT records by the phase set in lit_life around run_eval / run_funded
            R = []
            E["rec"] = R
            orig = E["FF"].run_funded

            def rf(*a, **k):
                n0 = len(R)
                o = orig(*a, **k)
                fu.extend(R[n0:])
                del R[n0:]
                return o
            E["FF"].run_funded = rf
            try:
                life(t, s, 0, H_STACK)
            finally:
                E["FF"].run_funded = orig
            ev.extend(R)
        else:
            life(t, s, 0, H_STACK)
            for ph, x in E["rec"]:
                (ev if ph == "eval" else fu).append(x)
        E["rec"] = None
    q = lambda a, p: round(float(np.percentile(a, p))) if a else None
    return {"type": t, "span": span, "eval": {"n": len(ev), "med": q(ev, 50), "p95": q(ev, 95), "max": round(max(ev)) if ev else None},
            "funded": {"n": len(fu), "med": q(fu, 50), "p95": q(fu, 95), "max": round(max(fu)) if fu else None}}


def risk_step(n, risk):
    """$ at risk at the same moment if every account of step n takes a trade together (LIT copies fire on the same signal;
    ATLAS can be open at the same time on its own accounts): typical = funded medians, worst = every account still in its
    eval at its max trade."""
    types = step_types(n)
    typ = sum((risk[t]["funded"]["med"] or risk[t]["eval"]["med"] or 0) for t in types)
    worst = sum((risk[t]["eval"]["max"] or 0) for t in types)
    p95 = sum(max(risk[t]["eval"]["p95"] or 0, risk[t]["funded"]["p95"] or 0) for t in types)
    lit_worst = sum((risk[t]["eval"]["max"] or 0) for t in types if TYPES[t]["strategy"] == "LIT")
    # the ladder's own worst: the accounts of the earlier steps funded (their p95 trade), the two new ones in eval at their max
    old = step_types(n - 1) if n > 0 else []
    ladder = sum((risk[t]["funded"]["p95"] or 0) for t in old) + sum((risk[t]["eval"]["max"] or 0) for t in STEPS[n]["add"])
    return {"typical": round(typ), "p95": round(p95), "worst": round(worst), "lit_worst": round(lit_worst), "ladder": round(ladder)}


# ================================================================================================ main
def make_table(stacks, ladder, risk):
    table = []
    for st in STEPS:
        n = st["n"]
        g = lambda sp, k: stacks[f"{n}|{sp}"][k]
        lh2, lh1 = ladder["H2"]["steps"][n], ladder["H1"]["steps"][n]
        rs = risk_step(n, risk)
        table.append({
            "step": n, "accounts": len(step_types(n)), "add": [TYPES[t]["strategy"] + " " + TYPES[t]["label"] for t in st["add"]],
            "action": st["action"], "trigger": st["trigger"], "trigger_text": trigger_text(st),
            "lit": sum(1 for t in step_types(n) if TYPES[t]["strategy"] == "LIT"),
            "atlas": sum(1 for t in step_types(n) if TYPES[t]["strategy"] == "ATLAS"),
            "usd_month_h2": g("H2", "steady_net_month"), "usd_month_h1": g("H1", "steady_net_month"),
            "usd_month_2025": g("2025", "steady_net_month"), "usd_month_2021_24": g("2021-24", "steady_net_month"),
            "fees_month_h2": g("H2", "steady_fee_month"), "fees_month_2025": g("2025", "steady_fee_month"),
            "month_p10_h2": g("H2", "month_p10"), "month_le0_h2": g("H2", "month_le0"), "month_le0_2025": g("2025", "month_le0"),
            "month_p10_2025": g("2025", "month_p10"), "funded_avg_h2": g("H2", "funded_avg_m7_12"),
            "risk": rs, "cap_binds_typical": rs["typical"] > DAY_CAP_USD, "cap_binds_worst": rs["worst"] > DAY_CAP_USD, "cap_binds_ladder": rs["ladder"] > DAY_CAP_USD,
            "step_cost": step_cost(n), "step_cost_list": step_cost(n, True),
            "fees_to_reach_h2": lh2["fees_to_reach_med"], "fees_to_reach_h1": lh1["fees_to_reach_med"],
            "months_h2": lh2["months_med"], "months_h1": lh1["months_med"],
            "months_h2_iqr": [lh2["months_p25"], lh2["months_p75"]],
            "reach_24m_h2": lh2["reach_24m"], "reach_24m_h1": lh1["reach_24m"],
            "reach_24m_2025": ladder["2025"]["steps"][n]["reach_24m"], "reach_24m_2021_24": ladder["2021-24"]["steps"][n]["reach_24m"],
            "months_2025": ladder["2025"]["steps"][n]["months_med"]})
    return table


def main(procs=4):
    import multiprocessing as mp
    t0 = dt.datetime.now()
    setup()
    chk = check()
    jobs_r = [(t, "H2", 200) for t in TYPES]
    jobs_s = [(st["n"], sp, N_STACK) for st in STEPS for sp in SPANS]
    jobs_l = [(sp, N_LADDER) for sp in SPANS]
    with mp.get_context("fork").Pool(procs) as pool:
        RK = pool.map(risk_job, jobs_r, chunksize=1)
        ST = pool.map(stack_job, jobs_s, chunksize=1)
        LD = pool.map(ladder_job, jobs_l, chunksize=1)
    risk = {r["type"]: r for r in RK}
    stacks = {f"{s['step']}|{s['span']}": s for s in ST}
    ladder = {l["span"]: l for l in LD}
    table = make_table(stacks, ladder, risk)
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "scale_plan", "writeup": "research/writeups/scale-plan.md",
           "owner": "2026-10-22: LIT is on the 50K, ATLAS (EMA+MACD+S/R, account B) on the 25K, then eventually we just scale. And keep scaling.",
           "variant": VARIANT, "budget": BUDGET, "stagger": STAGGER, "lost_quiet": LOST_QUIET, "day_cap_usd": DAY_CAP_USD,
           "types": TYPES, "steps": STEPS, "table": table, "risk": risk, "stacks": stacks, "ladder": ladder, "check": chk,
           "method": __doc__.split("Models")[1].split("python -X utf8")[0].strip(),
           "honest": ["2026 is one good year for LIT (2021-25 PF 1.01) and for ATLAS (2025 / 2021-24: a third of evals dead in 2 weeks); "
                      "the 2026 numbers are a bet that 2026 continues, the 2025 / 2021-24 rows are what a bad year looks like.",
                      "Thin samples: H2 2026 = 75 sessions, ~40 LIT trades and ~48 ATLAS trades; the Monte Carlo re-uses the same weeks.",
                      "All LIT accounts take the same signals (results 81-91% correlated): more accounts = more money and the same bad months.",
                      "ATLAS on Lucid / FundedNext uses the Builder 50K eval numbers and those firms' payout rules: an approximation, not a study of those rules.",
                      "Prices: MFFU = the owner's real prices; Lucid / FundedNext = study prices with affiliate codes (unconfirmed); list prices shown too.",
                      "Live accounts (after 5 sim payouts at MFFU / Lucid) are not modelled: the path buys a new eval instead (conservative)."]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print_table(out)
    print("wrote", OUT, (dt.datetime.now() - t0).seconds, "s", flush=True)
    return out


def trigger_text(st) -> str:
    tr = st["trigger"]
    if not tr:
        return "today"
    parts = []
    if tr.get("payouts_n"):
        parts.append("the first payout" if tr["payouts_n"] == 1 else f"{tr['payouts_n']} payouts")
    if tr.get("funded"):
        parts.append(f"{tr['funded']} accounts funded at the same time")
    if tr.get("payouts_usd"):
        parts.append(f"${tr['payouts_usd']:,.0f} paid out in total")
    parts.append(f"cash (budget ${BUDGET:,.0f} + payouts - fees) covers the two evals")
    parts.append(f"no funded account lost in the last {LOST_QUIET} sessions")
    return "; ".join(parts)


def print_table(out):
    print("step accts  $/mo H2  H1   2025  21-24 | fees/mo | p10 mo H2 | risk typ/worst | evals $ to reach | months H2 (H1) | reach 24m H2/2025")
    for r in out["table"]:
        print(f"{r['step']:>4} {r['accounts']:>5} {r['usd_month_h2']:>8,} {r['usd_month_h1']:>6,} {r['usd_month_2025']:>6,} {r['usd_month_2021_24']:>6,} | "
              f"{r['fees_month_h2']:>7,} | {r['month_p10_h2']:>9,} | {r['risk']['typical']:>5,}/{r['risk']['worst']:>6,} | "
              f"{r['fees_to_reach_h2'] or 0:>8,} | {r['months_h2']} ({r['months_h1']}) | {r['reach_24m_h2']}/{r['reach_24m_2025']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        setup()
        check()
    elif len(sys.argv) > 1 and sys.argv[1] == "table":          # rebuild the table from the stored Monte Carlo blocks
        o = json.load(open(OUT, encoding="utf-8"))
        o["table"] = make_table(o["stacks"], o["ladder"], o["risk"])
        json.dump(o, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
        print_table(o)
    else:
        main()
