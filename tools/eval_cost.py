"""Cheaper evals (owner order 2026-10-26, item 3): the eval-sizing trade-off between pass speed and fail rate when the
owner buys MANY evals, priced at his real prices, as the cost of one FUNDED account (every failed / stuck / reset eval
bought again at once) and the time it takes. Write-up: research/writeups/eval-cost.md. Numbers: research/lab/eval_cost.json.
Paper research only (nothing live changes; the live eval sizing stays two_week room_f 0.8, no weekly stop, no reset).

Engines: tools/uprisk.py (Eval = engine/sizing.lit_qty on live_model.json lit_sizing, the A4-checked replay; life = eval ->
2 sessions of paperwork -> funded (live funded sizing) -> payouts -> lost / 5 payouts -> buy again). LIT trades: the 120
live 2026 trades of run lit_live (+ 511 5m-only 2021-25 rows as the reference). $1.90 a micro.

Plans and prices (owner's, 2026-10-26; one-time, $0 activation; codes per research/writeups/prop-codes-2026-10.md):
  MFFU Builder 50K $91.80 | MFFU Builder 25K $63 ($43 on the 2026-10-26 ATLAS purchase) | LucidPro 50K $115.40-$134 |
  FundedNext Rapid Daily 50K $159-$169.99. LucidPro / FundedNext evals have the 50K's $3,000 target and $2,000 EOD trailing
  floor (research/lit/funded_firms.json plans); they are run on the MFFU 50K eval with their own soft daily loss
  ($1,200 / $1,000) as a proxy, and their funded phase is valued at the funded $/month of research/second/
  money_goal_rates.json (LucidPro $938 / FundedNext $629 a month H2) per funded session (the MFFU rows use the exact
  funded replay instead).

Sizing grid (LIT on the eval): two_week room_f 0.4 / 0.55 / 0.6 / 0.7 / 0.8 (live) / 0.9 / 1.0; the 2026-10-24 safe set
(0.55 + $1,200 weekly stop); 0.8 staying two_week past session 10; and buy-a-new-eval resets at session 10 / 15 / 20.

Per plan x price x sizing x span (MC 1,000 paths, 5-session blocks, seed 23 = tools/uprisk.py):
  chain   evals bought back to back until one passes (horizon 252 sessions): P(funded within 10 / 20 / 40 sessions),
          median sessions to funded, evals per funded account, fees per funded account
  value   proxy 6-month value of one slot = V x funded sessions in the 126 - fees (V = the plan's funded $/session)
  life    MFFU only: uprisk.life (exact funded phase) at each price, $ a month to the owner net of every eval

    python -X utf8 tools/eval_cost.py grid [--n 1000]   # chain + value + MFFU life per plan x price x sizing
    python -X utf8 tools/eval_cost.py owner [--n 1000]  # the owner's eval-speed scores (p10/f10 ... slow_pass, real-order
                                                        # rolling 20-session windows) for the two_week_until variants
    python -X utf8 tools/eval_cost.py lifetw [--n 1000] # exact MFFU 6-month slot money for the two_week_until variants
    -> research/lab/eval_cost.json (keys rows / life / owner / life_tw)
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "eval_cost.json")
SPANS = ("H1", "H2", "REF")
RATES = json.load(open(os.path.join(ROOT, "research", "second", "money_goal_rates.json"), encoding="utf-8"))["types"]
PLANS = {   # plan key -> (uprisk eval plan, soft daily loss, prices, funded $ a month H2 / H1 / ref, uprisk funded cfg)
    "mffu50": ("builder50k", 1000.0, (91.80,), (RATES["lit_b50"]["usd_month"], RATES["lit_b50"]["usd_month_h1"], RATES["lit_b50"]["usd_month_ref"]), U.UP50),
    "mffu25": ("builder25k", 600.0, (63.0, 43.0), (405, 445, 30), U.UP25),
    "lucid50": ("builder50k", 1200.0, (115.40, 134.0), (RATES["lit_l50"]["usd_month"], RATES["lit_l50"]["usd_month_h1"], RATES["lit_l50"]["usd_month_ref"]), None),
    "fn50": ("builder50k", 1000.0, (159.0, 169.99), (RATES["lit_fn50"]["usd_month"], RATES["lit_fn50"]["usd_month_h1"], RATES["lit_fn50"]["usd_month_ref"]), None),
}
VARS = [
    ("rf40", {"room_f": 0.4}),
    ("rf55", {"room_f": 0.55}),
    ("rf55_wk1200", {"room_f": 0.55, "wk_loss_usd": 1200}),
    ("rf60", {"room_f": 0.6}),
    ("rf70", {"room_f": 0.7}),
    ("live_rf80", {}),
    ("rf90", {"room_f": 0.9}),
    ("rf100", {"room_f": 1.0}),
    ("rf80_tw99", {"two_week_until": 999}),
    ("rf80_reset10", {"reset_at": 10}),
    ("rf80_reset15", {"reset_at": 15}),
    ("rf80_reset20", {"reset_at": 20}),
    ("rf100_reset10", {"room_f": 1.0, "reset_at": 10}),
]


def ecfg(var, plan_key):
    plan, dll = PLANS[plan_key][0], PLANS[plan_key][1]
    c = U.ecfg_of(dict(var), plan=plan)
    return c, dll


def chain(BY, P, cfg, plan, dll, horizon=252):
    """Evals back to back until one passes. -> per path (evals bought, session the funded account starts or None)."""
    R = []
    E0 = dict(U.EPLAN[plan])
    for seq in P:
        bought, e = 1, U.Eval(cfg, plan)
        e.E = {**E0, "dll": dll}
        start = None
        for k, si in enumerate(seq[:horizon]):
            r = e.step(BY[si])
            if r == "pass":
                start = k + 1 + U.GAP
                break
            if r in ("fail", "stuck", "reset"):
                bought += 1
                e = U.Eval(cfg, plan)
                e.E = {**E0, "dll": dll}
        R.append((bought, start))
    return R


def summarise(R, price, usd_month, n6=126):
    n = len(R)
    funded = [s for _, s in R if s is not None]
    v = usd_month / 21.0
    # 6-month slot proxy: funded sessions inside the first 126 x V - the evals bought inside them
    val = []
    for b, s in R:
        if s is not None and s <= n6:
            val.append(v * (n6 - s) - b * price)
        else:
            val.append(-b * price if s is None else -(b * price))
    fees = sum(b for b, s in R) * price
    return {"p_f10": round(100.0 * sum(1 for s in funded if s - U.GAP <= 10) / n, 1),
            "p_f20": round(100.0 * sum(1 for s in funded if s - U.GAP <= 20) / n, 1),
            "p_f40": round(100.0 * sum(1 for s in funded if s - U.GAP <= 40) / n, 1),
            "p_funded_252": round(100.0 * len(funded) / n, 1),
            "sess_to_funded_med": float(np.median(funded)) if funded else None,
            "evals_per_funded": round(sum(b for b, _ in R) / max(1, len(funded)), 2),
            "usd_per_funded": round(fees / max(1, len(funded)), 1),
            "evals_first_try_pass": round(100.0 * sum(1 for b, s in R if b == 1 and s is not None) / n, 1),
            "value6_proxy": round(float(np.mean(val)))}


TW_VARS = [("live_rf80", {}), ("tw15", {"two_week_until": 15}), ("tw20", {"two_week_until": 20}), ("tw99", {"two_week_until": 999}),
           ("rf90_tw99", {"room_f": 0.9, "two_week_until": 999}), ("rf100_tw99", {"room_f": 1.0, "two_week_until": 999}),
           ("rf70_tw99", {"room_f": 0.7, "two_week_until": 999})]


def roll(BY, S, span, cfg, plan, horizon=60):
    """Real-order rolling windows: an eval started on every session of the half, played on that half's sessions; p/f
    within H counts only the starts that can see H sessions."""
    a, z = U.span_ix(S, span)
    res = []
    for st in range(a, z):
        e = U.Eval(cfg, plan)
        out, used = "open", None
        for k, si in enumerate(range(st, min(z, st + horizon))):
            r = e.step(BY[si])
            if r:
                out, used = r, k + 1
                break
        res.append((out, used, min(z, st + horizon) - st))
    o = {}
    for H in (10, 15, 20):
        rr = [x for x in res if x[2] >= H]
        m = len(rr) or 1
        o[f"p{H}"] = round(100.0 * sum(1 for x in rr if x[0] == "pass" and x[1] <= H) / m, 1)
        o[f"f{H}"] = round(100.0 * sum(1 for x in rr if x[0] in ("fail", "stuck") and x[1] <= H) / m, 1)
    return o


def owner_main(n, out):
    S, BY = U.load()
    res = {}
    for plan in ("builder50k", "builder25k"):
        P = {sp: U.mc_paths(S, sp, n, length=60) for sp in SPANS}
        for vid, v in TW_VARS:
            cfg = U.ecfg_of(dict(v), plan=plan)
            row = {}
            for sp in SPANS:
                R = []
                for seq in P[sp]:
                    e = U.Eval(cfg, plan)
                    o_, used = "open", 60
                    for k, si in enumerate(seq):
                        r = e.step(BY[si])
                        if r:
                            o_, used = r, k + 1
                            break
                    R.append((o_, used))
                pas = [u for o, u in R if o == "pass"]
                m = {f"p{H}": round(100.0 * sum(1 for u in pas if u <= H) / n, 1) for H in (10, 15, 20)}
                m.update({f"f{H}": round(100.0 * sum(1 for o, u in R if o in ("fail", "stuck") and u <= H) / n, 1) for H in (10, 15, 20)})
                m.update(p_ever=round(100.0 * len(pas) / n, 1), fail_ever=round(100.0 * sum(1 for o, _ in R if o in ("fail", "stuck")) / n, 1),
                         open60=round(100.0 * sum(1 for o, _ in R if o == "open") / n, 1), pass_med=float(np.median(pas)) if pas else None,
                         slow_pass=round(100.0 * sum(1 for u in pas if u > 15) / max(1, len(pas)), 1))
                if sp in ("H1", "H2"):
                    m["roll"] = roll(BY, S, sp, cfg, plan)
                row[sp] = m
            res[f"{plan}__{vid}"] = row
            print(f"owner {plan} {vid:11s} " + " | ".join(f"{sp} p10/f10 {r['p10']}/{r['f10']} p20/f20 {r['p20']}/{r['f20']} slow {r['slow_pass']}"
                                                     for sp, r in row.items()), flush=True)
    out["owner"] = res


def lifetw_main(n, out):
    S, BY = U.load()
    P = {sp: U.mc_paths(S, sp, n) for sp in SPANS}
    res = {}
    for plan, fc, prices in (("builder50k", U.UP50, (91.80,)), ("builder25k", U.UP25, (63.0, 43.0))):
        for vid, v in TW_VARS + [("rf70", {"room_f": 0.7})]:
            cfg = U.ecfg_of(dict(v), plan=plan)
            for price in prices:
                U.PRICE[plan] = price
                row = {sp: U.life(BY, P[sp], cfg, fc, plan=plan) for sp in P}
                res[f"{plan}@{price:g}__{vid}"] = row
                print(f"lifetw {plan}@{price:g} {vid:10s} " + " | ".join(f"{sp} ${r['net_m']:>5}/mo" for sp, r in row.items()), flush=True)
        U.PRICE.update({"builder50k": 91.80, "builder25k": 63.0})
    out["life_tw"] = res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    what = args[0] if args else "grid"
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else U.N_MC
    prev = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if what in ("owner", "lifetw"):
        (owner_main if what == "owner" else lifetw_main)(n, prev)
        prev["built"] = dt.date.today().isoformat()
        json.dump(prev, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
        print("->", OUT)
        return
    S, BY = U.load()
    P = {sp: U.mc_paths(S, sp, n, length=252) for sp in SPANS}
    P6 = {sp: U.mc_paths(S, sp, n) for sp in SPANS}
    out = {**prev, "built": dt.date.today().isoformat(), "n": n,
           "plans": {k: {"prices": v[2], "usd_month": v[3]} for k, v in PLANS.items()}, "rows": {}, "life": {}}
    for pk, (plan, dll, prices, um, fcfg) in PLANS.items():
        for vid, var in VARS:
            cfg, dll = ecfg(var, pk)
            ch = {sp: chain(BY, P[sp], cfg, plan, dll) for sp in SPANS}
            for price in prices:
                key = f"{pk}@{price:g}__{vid}"
                row = {sp: summarise(ch[sp], price, um[{"H2": 0, "H1": 1, "REF": 2}[sp]]) for sp in SPANS}
                out["rows"][key] = row
                print(f"{key:28s} " + " | ".join(
                    f"{sp} f10 {row[sp]['p_f10']:>5}% f20 {row[sp]['p_f20']:>5}% med {row[sp]['sess_to_funded_med']} "
                    f"evals {row[sp]['evals_per_funded']:>5} ${row[sp]['usd_per_funded']:>6} v6 ${row[sp]['value6_proxy']:>6}"
                    for sp in SPANS), flush=True)
            if fcfg is not None:
                for price in prices:
                    U.PRICE[plan] = price
                    key = f"{pk}@{price:g}__{vid}"
                    out["life"][key] = {sp: U.life(BY, P6[sp], cfg, fcfg, plan=plan) for sp in SPANS}
                    L = out["life"][key]
                    print(f"   life {key:26s} " + " | ".join(f"{sp} ${L[sp]['net_m']:>5}/mo p_neg {L[sp]['p_neg']:>5}% evals {L[sp]['evals']}"
                                                          for sp in SPANS), flush=True)
                U.PRICE.update({"builder50k": 91.80, "builder25k": 63.00})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


if __name__ == "__main__":
    main()
