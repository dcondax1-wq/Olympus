"""ATLAS funded 25K at ~$150 a trade on the live sizing path (research/atlasfund/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/atlasfund/run.py  -> research/atlasfund/results.json
"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from tools import atlas_funded as AF  # noqa: E402
from engine import account_b as EAB  # noqa: E402

AF.M.SPANS["2021-25"] = ("2021-11-01", "2025-12-31")
SP = ("2021-25", "2025", "H1", "H2")
spec15 = EAB.normalize({"account": "research", "plan": AF.PLAN, "eval_start": "2026-01-02", "stage": "funded",
                        "funded_start": "2000-01-03", "funded_room_pct": 0.15}, lit_account=None)
def q_room15(t, st):
    return int(EAB.qty(spec15, {"risk_pts": float(t["risk"]), "tgt_pts": float(t["tgt"])}, dict(st), base=AF.LSZ)["qty"])
VARS = {"today": AF.q_live, "cap150": AF.q_rule({**AF.CFG["funded"], "pct_max_usd": 150}), "room15": q_room15}

def main():
    AF.M.units()
    U = AF.A.account_units(AF.A.BASE)
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    with AF.Sizer(AF.q_live):
        chk = AF.check_live_equals_code(by)
    out = {"made": "2026-11-24", "design": "research/atlasfund/DESIGN.md", "check_live_equals_code": chk,
           "room15_spec_funded_cfg": EAB.funded_cfg(spec15, AF.LSZ)["funded"], "today_cfg": AF.CFG["funded"], "rows": {}}
    for v, q in VARS.items():
        row = {}
        with AF.Sizer(q):
            for s in SP:
                x, y = AF.mc(by, s, 1000), AF.real(by, s)
                row[s] = {k: x[k] for k in ("paid_6m", "per_month", "per_month_p10", "payouts_6m", "lost_6m", "stuck_6m", "dead_6m",
                                            "first_med", "any_pay_6m", "trades_per_week", "max_risk")}
                row[s]["real"] = {k: y[k] for k in ("accounts", "lost", "stuck", "payouts", "paid", "per_month", "net_trading", "pf")}
                print(f"{v:7s} {s:8s} paid6m ${x['paid_6m']} (${x['per_month']}/mo) pays {x['payouts_6m']} lost {x['lost_6m']}% dead "
                      f"{x['dead_6m']}% first {x['first_med']} risk<=${x['max_risk']} | real: {y['accounts']} acct, lost {y['lost']}, "
                      f"pays {y['payouts']} ${y['paid']:,}", flush=True)
        out["rows"][v] = row
    for v in ("cap150", "room15"):
        why = []
        for s in SP:
            a, b = out["rows"][v][s], out["rows"]["today"][s]
            if a["paid_6m"] <= b["paid_6m"]:
                why.append(f"{s} paid ${a['paid_6m']} vs ${b['paid_6m']}")
            if a["dead_6m"] > b["dead_6m"]:
                why.append(f"{s} dead {a['dead_6m']}% vs {b['dead_6m']}%")
        out["rows"][v]["verdict"] = "needs-owner-yes" if not why else "FAIL"
        out["rows"][v]["why"] = why
        print(v, out["rows"][v]["verdict"], why)
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)

if __name__ == "__main__":
    main()
