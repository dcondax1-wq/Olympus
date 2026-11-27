"""results.json -> markdown tables for research/evalplan/PLAN.md.   python -X utf8 research/evalplan/render.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "results.json"), encoding="utf-8"))
NAMES = {"Z50": "Zlarior 50K eval (LIT)", "Z25": "Zlarior 25K #2 eval (LIT)", "R25": "Rapid EOD 25K eval (LIT+ATLAS)",
         "A25": "ATLAS 25K funded (ATLAS)"}
LAB = {"none": "no order flow (today)", "SMALL|REAL": "small, edge as measured", "SMALL|Q25": "small, 1/4 of the edge",
       "SMALL|ZERO": "small, NO edge", "SMALL|BAD": "small, bad (losing)", "FULL|REAL": "ATLAS-size, as measured",
       "FULL|Q25": "ATLAS-size, 1/4 edge", "FULL|ZERO": "ATLAS-size, NO edge", "FULL|BAD": "ATLAS-size, bad",
       "SMALL|REAL|quiet": "small, as measured, only on quiet days", "SMALL|ZERO|quiet": "small, NO edge, only on quiet days"}
out = []
for aid, nm in NAMES.items():
    out.append(f"\n### {nm}\n")
    ev = aid != "A25"
    if ev:
        out.append("| lane A | pass % (60 days) Jan-Jun / Jul-Oct / 2021-25 | days to pass (Jul-Oct) | fail % Jul-Oct | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | vs today Jul-Oct |")
        out.append("|---|---|---|---|---|---|")
    else:
        out.append("| lane A | 6 months net $ Jan-Jun / Jul-Oct / 2021-25 | worst 10% Jul-Oct | lose the account % Jul-Oct | vs today Jul-Oct |")
        out.append("|---|---|---|---|---|")
    base = d["cells"][f"{aid}|none"]["H2"]["slot"]["net"]
    for lab, txt in LAB.items():
        c = d["cells"].get(f"{aid}|{lab}")
        if not c:
            continue
        nets = " / ".join(f"${c[s]['slot']['net']:,}" for s in ("H1", "H2", "REF"))
        dv = c["H2"]["slot"]["net"] - base
        if ev:
            ps = " / ".join(f"{c[s]['eval']['pass']:.0f}%" for s in ("H1", "H2", "REF"))
            md = c["H2"]["eval"]["med_days"]
            out.append(f"| {txt} | {ps} | {md:.0f} | {c['H2']['eval']['fail']:.0f}% | {nets} | {dv:+,} |")
        else:
            out.append(f"| {txt} | {nets} | ${c['H2']['slot']['p10']:,} | {c['H2']['slot']['lost']:.0f}% | {dv:+,} |")
out.append("\nPre-registered rule (worth a forward plan = as-measured AND 1/4-edge beat today in both 2026 halves, and NO edge costs <= one eval price in Jul-Oct):\n")
out.append("| account | small | ATLAS-size |\n|---|---|---|")
for aid, nm in NAMES.items():
    v = d["verdict"][aid]
    f = lambda x: f"{'YES' if x['worth_forward_plan'] else 'no'} (beats both halves: {'yes' if x['real_q25_beat_both_halves'] else 'no'}; no-edge cost ${x['zero_cost_H2']:,} vs price ${x['price']})"
    out.append(f"| {nm} | {f(v['SMALL'])} | {f(v['FULL'])} |")
print("\n".join(out))
