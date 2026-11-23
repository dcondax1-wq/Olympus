"""Tables for research/writeups/confluences-2026-11-23.md + research/lab/confluences.json (from results.json)."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = json.load(open(os.path.join(ROOT, "research/confluence/results.json")))
PH = json.load(open(os.path.join(ROOT, "research/confluence/posthoc_smt.json")))
SP = ("H1", "H2", "2021-25")
LAB = {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026", "2021-25": "2021-25"}
m = lambda x: "-" if x is None else ("-" if x < 0 else "+") + f"${abs(x):,.0f}"
def cell(s):
    return "0" if not s.get("n") else f"{s['n']} / {s['win']}% / {s['avg_r']:+.2f}R / PF {s['pf']}"
def verdict(bot, g, sp):
    if bot == "lit" and g == "smt":
        return "anti-confluence (tagged trades lost in all 3 spans; Holm 2026 p 0.002; 27 trades, ES from 2025-04 only)"
    if bot == "atlas" and g == "killzone":
        return "real in Jan-Jun + 2021-25 (Holm 2021-25 p 0.003), broke in Jul-Oct; as a filter it loses Jul-Oct"
    if sp["consistent"]:
        return "points the right way in all 3 spans but not significant (Holm 1.0); as a filter it loses"
    return "noise (flips between spans, Holm 1.0)"
out, lab = [], []
for bot, nm in (("lit", "Zlarior (LIT)"), ("atlas", "ATLAS")):
    rows = []
    for g, sp in R[bot]["split"].items():
        rows.append((sp["holm_2026"] if sp["holm_2026"] is not None else 1, g, sp))
    rows.sort(key=lambda x: (min(x[0], x[2]["holm_2021_25"] or 1), not x[2]["consistent"]))
    out.append(f"\n### {nm}: tagged vs untagged (trades / win % / avg R / PF), ranked by corrected p\n")
    out.append("| # | Tag | " + " | ".join(f"{LAB[s]} tagged" + f" | {LAB[s]} untagged" for s in SP) + " | p 2026 (Holm / BH) | p 2021-25 (Holm) | verdict |")
    out.append("|" + "---|" * (3 + 2 * len(SP) + 2))
    for i, (_, g, sp) in enumerate(rows, 1):
        p26 = "-" if sp["p_2026"] is None else f"{sp['p_2026']:.4f} ({sp['holm_2026']} / {sp['bh_2026']})"
        pR = "-" if sp["p_2021_25"] is None else f"{sp['p_2021_25']:.4f} ({sp['holm_2021_25']})"
        out.append(f"| {i} | {R['tags'][g]} | " + " | ".join(cell(sp[s]["tagged"]) + " | " + cell(sp[s]["untagged"]) for s in SP) +
                   f" | {p26} | {pR} | {verdict(bot, g, sp)} |")
        lab.append({"id": f"conf_{bot}_{g}", "bot": "LIT" if bot == "lit" else "ATLAS", "name": R["tags"][g],
                    "spans": {s: {"tagged": sp[s]["tagged"], "untagged": sp[s]["untagged"]} for s in SP},
                    "p_2026": sp["p_2026"], "holm_2026": sp["holm_2026"], "p_2021_25": sp["p_2021_25"], "holm_2021_25": sp["holm_2021_25"],
                    "skip_untagged_gate": R[bot]["uses"][f"skip_untagged:{g}"]["ok"], "verdict": verdict(bot, g, sp),
                    "status": "rejected"})
# uses LIT
b = R["lit"]["base"]
def lrow(nm, s):
    if s is None:
        return f"| {nm} | no trades in Jul-Oct | | | | | |"
    L, E, X = s["lit"], s["eval"], s["eval_ref"]
    return (f"| {nm} | " + " / ".join(f"{m(L[h]['per_month'])}" for h in SP) + " | " + " / ".join(m(L[h]["dd"]) for h in SP) +
            " | " + " / ".join(str(L[h]["tpw"]) for h in SP) + " | " + " / ".join(m(E[h]["per_month"]) for h in ("H1", "H2")) + f" / {m(X['per_month'])}" +
            " | " + ", ".join(f"{E[h]['p10']}/{E[h]['f10']}" for h in ("H1", "H2")) + f", {X['p10']}/{X['f10']}" +
            " | " + " / ".join(str(E[h]["pass_med"]) for h in ("H1", "H2")) + f" / {X['pass_med']} |")
out.append("\n### Zlarior uses (LIT size, costs in; eval = live two_week path room 0.4 to session 80)\n")
out.append("| Version | $/month H1 / H2 / 21-25 | max DD | trades/wk | eval $/month | eval 2-week pass/fail % | median sessions to pass | gate |")
out.append("|---|---|---|---|---|---|---|---|")
out.append(lrow("today", b) + " - |")
for nm, u in R["lit"]["uses"].items():
    out.append(lrow(nm, u["s"]) + f" {'PASS' if u['ok'] else 'no'} |")
out.append(lrow("POST-HOC: skip setups WITH SMT", PH["s"]) + " PASS (post-hoc) |")
# uses ATLAS
def arow(nm, s, fx=None):
    if s is None:
        return f"| {nm} | - | | | | | |"
    F, E = s["funded"], s["eval"]
    MO = "mp_net_less_fees"
    return (f"| {nm} | " + " / ".join(m(F[h]["funded"]["per_month"]) for h in ("H1", "H2", "REF")) + " | " +
            " / ".join(m(F[h]["fixed"]["max_dd"]) for h in ("H1", "H2", "REF")) + " | " + " / ".join(str(F[h]["fixed"]["tpw"]) for h in ("H1", "H2", "REF")) +
            " | " + " / ".join(m(E[h][MO]) for h in ("H1", "H2", "2025", "2021-24")) + " | " + ", ".join(f"{E[h]['p10']}/{E[h]['f10']}" for h in ("H1", "H2")) +
            " | " + " / ".join(str(E[h]["pass_med"]) for h in ("H1", "H2")) + " |")
out.append("\n### ATLAS uses (funded 25K Monte Carlo at $250 / 30% of the room; max DD and trades/wk at a fixed $250; 25K eval path after the $43 fees)\n")
out.append("| Version | funded $/month H1 / H2 / 21-25 | max DD ($250) | trades/wk | eval $ H1 / H2 / 2025 / 2021-24 | eval 2-week pass/fail % H1, H2 | median sessions to pass | gate |")
out.append("|---|---|---|---|---|---|---|---|")
out.append(arow("today", R["atlas"]["base"]) + " - |")
for nm, u in R["atlas"]["uses"].items():
    out.append(arow(nm, u["s"]) + f" {'PASS' if u['ok'] else 'no'} |")
open(os.path.join(ROOT, "research/confluence/tables.md"), "w").write("\n".join(out) + "\n")
lab.append({"id": "conf_lit_size_2plus", "bot": "LIT", "name": "x1.5 size on 2+ of the 10 confluences", "spans": None,
            "verdict": "leverage, not skill: 95-98% of trades carry 2+ tags; same as flat x1.5; luck p 0.02 / 0.83 / 0.83; fails 2021-25 eval", "status": "rejected"})
lab.append({"id": "conf_atlas_size_2plus", "bot": "ATLAS", "name": "x1.5 size on 2+ of the 10 confluences", "spans": None,
            "verdict": "the funded 25K preset caps size (x1.5 adds $0 funded); eval Jul-Oct 2-week pass 43.5 -> 42.0%", "status": "rejected"})
lab.append({"id": "conf_lit_skip_smt_posthoc", "bot": "LIT", "name": "POST-HOC: skip LIT setups that have ES/NQ SMT", "spans": None,
            "verdict": "clears the money gate (+$770 / +$1,013 / +$8 a month) with luck p 0.01-0.05 in 2026 and 0.48 in 2021-25, but it was chosen after "
                       "seeing the split, reverses the textbook idea and rests on 27 trades (ES data from 2025-04): forward-paper only, re-test at 60+ tagged trades",
            "status": "watch (post-hoc)", "luck_p": PH["luck_p"]})
json.dump({"date": "2026-11-23", "source": "research/writeups/confluences-2026-11-23.md", "prereg": "research/confluence/PREREG.md",
           "n_tests_split": R["n_tests"], "entries": lab}, open(os.path.join(ROOT, "research/lab/confluences.json"), "w"), indent=1)
print("\n".join(out))
