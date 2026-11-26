"""results2.json + tdo_funded.json -> research/writeups/ict-lab2-2026-11-25.md"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
R = json.load(open(os.path.join(HERE, "results2.json")))
V = R["variants"]
TF = json.load(open(os.path.join(HERE, "tdo_funded.json")))
FY = ["2022", "2023", "2024", "2025", "2026"]
NAMES = {"MMXM": "Market Maker Buy/Sell Model", "TURTLE": "Turtle Soup", "BRK": "Breaker / Mitigation block", "OB": "Order block (strict) / Unicorn",
         "FVG": "IFVG / BPR / Liquidity void / FVG", "WEEK": "Weekly profiles / weekly PO3 / weekly bias", "DOR": "Daily open retracement",
         "WYK": "Wyckoff spring / upthrust", "MP": "Market Profile 80% / VAH-VAL / POC", "VWAP": "VWAP SD bands", "ORB": "Opening range + volume",
         "DIV": "RSI / MACD divergence at levels", "ROUND": "Round-number magnet", "PW": "Prior-week high / low", "PAIR": "Pairs (all 120)",
         "GATE": "Standalone + bias gate"}


def k(x):
    if x is None:
        return "-"
    s = "+" if x > 0 else "-" if x < 0 else ""
    return f"{s}${abs(x) / 1000:.1f}k" if abs(x) >= 1000 else f"{s}${abs(x):.0f}"


def sq(x, yr=None):
    if yr is not None and x > 0 and yr <= 0:
        return "🟨"
    if abs(x) < 200:
        return "⬜"
    return "🟩" if x > 0 else "🟥"


def yrow(r):
    yr = r.get("years_vs_random")
    return "".join(sq(r["years_delta"][y], yr[y] if yr else None) for y in FY)


def ev(e):
    return "-" if not e or e["pass"] is None else f"{e['pass']}/{e['fail']}%"


def best(kind, c):
    vs = [r for r in V.values() if r["kind"] == kind and r["concept"] == c]
    return max(vs, key=lambda r: (r["card"], r["years_better"], r["wf"])) if vs else None


def tot(r):
    return sum(r["years_delta"].values())


L = []
w = L.append
lu = R["luck"]
w("# ICT lab round 2 (2026-11-25): 22 more concepts + 120 pairs, every test view")
w("")
w("Rules pre-registered in `research/ictlab/DESIGN2.md` (definitions + sources) before the run; code `research/ictlab/ict_lab2.py`, numbers "
  "`results2.json`; TDO funded re-test `tdo_funded.py` / `tdo_funded.json` (real engine). Same data, sizes, costs and views as round 1 "
  "(`ict-lab-2026-11-25.md`). Confluence modes are eval-safe: HALF = x0.5 without the concept, ONLY = skip without it.")
w("")
w("## The answer on one screen")
w("")
w(f"**{lu['variants']} variants, 0 cards** (expected by luck alone: {lu['cards_expected_by_luck']}). p < 0.05: {lu['p05_real']} real vs "
  f"{lu['p05_expected']} by chance = noise level. Nothing to bring the owner from round 2.")
w("")
w("| Concept | Alone: $ 2021-11 .. 2026-11 | On LIT, best form (years, 2026 H1 / H2 $) | On ATLAS, best form (years, 2026 H1 / H2 $) | Plain words |")
w("|---|---|---|---|---|")
WORDS = {
    "MMXM": "mixed alone (+$6.0k, 0.8 trades/wk, loses 2024-25); with the weekly bias green all 5 years (+$11.6k) but 0.35 trades/wk, p 0.11: too few trades to trust, paper watch",
    "TURTLE": "mixed (+$7.1k, 0.2 trades/wk; rejected 2026-11-23); as a filter it costs money",
    "BRK": "never: breakers and mitigation blocks lose alone and as filters",
    "OB": "never: strict order blocks and Unicorn lose alone and as filters",
    "FVG": "never alone (liquidity void -$147k = the worst rule tested; BPR 2026 only); IFVG on LIT cuts 2021-25 losses but costs -$13k in 2026 H1",
    "WEEK": "weekly PO3 green 4 of 5 years but +$765 at 0.07 trades/wk; Tue / Wed / Thu profiles 0.1-0.3 trades/wk, mixed / never; weekly bias on LIT: 2021-25 +$7.7k (HALF) but 2026 H1 -$3.2k / H2 -$3.8k",
    "DOR": "never alone; ATLAS ONLY near the daily open: 2021-25 +$12.3k, 2026 -$14.2k",
    "WYK": "21 trades in 5 years (too rare to judge); no filter value",
    "MP": "never (80% rule 53 trades, about $0; VA fades -$40k); VA / POC filters cost money",
    "VWAP": "never (already rejected as textbook)",
    "ORB": "never",
    "DIV": "never: RSI -$98k, MACD -$89k alone; filters cost money",
    "ROUND": "38 trades, about $0",
    "PW": "fade -$14k, break -$18k",
}
for c in ["MMXM", "TURTLE", "BRK", "OB", "FVG", "WEEK", "DOR", "WYK", "MP", "VWAP", "ORB", "DIV", "ROUND", "PW"]:
    st = [r for r in V.values() if r["kind"] == "STAND" and r["concept"] == c]
    s_tot = " / ".join(f"{r['name'][2:]} {k(tot(r))}" for r in st) or "-"
    cells = []
    for kind in ("LIT", "ATLAS"):
        r = best(kind, c)
        cells.append(f"{r['name'].split('_', 1)[1]} {yrow(r)} {k(r['d_h1_2026'])} / {k(r['d_h2_2026'])}" if r else "-")
    w(f"| {NAMES[c]} | {s_tot} | {cells[0]} | {cells[1]} | {WORDS[c]} |")
pl = [r for r in V.values() if r["group"] == "pair"]
pb = sorted(pl, key=lambda r: -(r["d_h1_2026"] + r["d_h2_2026"]))[:3]
w(f"| Pairs (120 x LIT / ATLAS, HALF) | - | best 2026: " + ", ".join(f"{r['name']} {k(r['d_h1_2026'])}/{k(r['d_h2_2026'])}" for r in pb if r['kind'] == 'LIT')
  + " | " + ", ".join(f"{r['name']} {k(r['d_h1_2026'])}/{k(r['d_h2_2026'])}" for r in pb if r['kind'] == 'ATLAS') + " | 0 of 240 pass; "
  f"{sum(1 for r in pl if r['d_h1_2026'] > 0 and r['d_h2_2026'] > 0)} are better in both 2026 halves, "
  f"{sum(1 for r in pl if r['house_rule'])} also in 2021-25 |")
w("")
w("**Same pattern as round 1:** what cuts the 2021-25 losses (skip or halve trades without the concept) costs money in 2026, when "
  "LIT and ATLAS won almost everywhere. No concept makes more money in both 2026 halves AND the older years.")
w("")
# TDO funded
w("## True Day Open re-test on FUNDED accounts only (real engine, 1,000 x 6-month funded paths)")
w("")
w("LIT x0.5 when long above / short below the 00:00 open (entries after 00:00), funded stage only (no eval leg).")
w("")
w("| Account | Span | owner $ in 6 months (as is -> TDO half) | payouts | lost % | no payout % | first payout (session) |")
w("|---|---|---|---|---|---|---|")
SPN = {"H1": "2026 Jan-Jun", "H2": "2026 Jul-Oct", "REF": "2021-25", "2025": "2025"}
for plan, P in TF["plans"].items():
    for s in ("H1", "H2", "REF", "2025"):
        x, y = P["as_is"][s], P["tdo_half"][s]
        w(f"| {plan.replace('mffu_', '').replace('_', ' ')} | {SPN[s]} | {k(x['owner_6m'])} -> {k(y['owner_6m'])} | {x['payouts']} -> {y['payouts']} | "
          f"{x['lost']} -> {y['lost']} | {x['no_pay']} -> {y['no_pay']} | {x['first_med']} -> {y['first_med']} |")
w("")
w("**Verdict: NO CARD.** It halves how often a funded account is lost (Builder 50K Jul-Oct 13.1% -> 6.9%, 2021-25 82% -> 70%), "
  "but the owner gets LESS in 2026 Jul-Oct on every plan (50K -$245, 25K -$106, Rapid 25K -$467 per 6 months) and in 2025, and the first "
  "payout comes later. H1 is slightly better (+$68 to +$140). It fails both-halves-better again; it is a safety dial, not more money.")
w("")
# tables
for kind, title in (("STAND", "Standalone (LIT size, Builder 50K eval)"), ("LIT", "On LIT (single concepts)"), ("ATLAS", "On ATLAS (single concepts)")):
    w(f"## {title}")
    w("")
    w("| Variant | 2021 / 22 / 23 / 24 / 25 / 26 $ | yrs | WF $ | eval 40 all / 2026 | $/mo, max DD | tr/wk | PF | p | verdict |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    rows = [x for x in V.values() if x["kind"] == kind and x["group"] in ("base", "single", "stand")]
    for r in sorted(rows, key=lambda x: (x["concept"] != "BASE", x["name"])):
        yd = " / ".join(k(r["years_delta"][y]) for y in ["2021"] + FY)
        w(f"| {r['name']} | {yd} | {yrow(r)} | {k(r['wf'])} | {ev(r['eval_all'])} · {ev(r['eval_2026'])} | {k(r['all']['usd_mo'])}/mo, "
          f"{k(r['all']['maxdd'])} | {r['tpw']} | {r['pf']} | {r['p'] if r['p'] is not None else '-'} | {r['verdict']} |")
    w("")
w("## Pairs and gates: top 15 by walk-forward $ (all 240 pairs / 72 gates are in results2.json)")
w("")
w("| Variant | yrs | WF $ | 2026 H1 / H2 $ | 2021-25 $ | p | verdict |")
w("|---|---|---|---|---|---|---|")
for r in sorted([x for x in V.values() if x["group"] in ("pair", "gate")], key=lambda x: -x["wf"])[:15]:
    w(f"| {r['name']} | {yrow(r)} | {k(r['wf'])} | {k(r['d_h1_2026'])} / {k(r['d_h2_2026'])} | {k(r['d_2021_25'])} | {r['p']} | {r['verdict']} |")
w("")
w("## Quarter heat map (standalones + single confluences; 2021Q4 .. 2026Q4)")
w("")
qs = sorted({q for r in V.values() for q in r["quarters_delta"]})
w("`" + " ".join(q[2:] for q in qs) + "`")
w("")
w("| Variant | quarters |")
w("|---|---|")
for r in sorted([x for x in V.values() if x["group"] in ("single", "stand")], key=lambda x: (x["kind"], x["name"])):
    w(f"| {r['name']} | " + "".join(sq(r["quarters_delta"].get(q, 0)) for q in qs) + " |")
w("")
w("## Luck (f)")
w("")
w("| Group | tries | cards | expected by luck |")
w("|---|---|---|---|")
for g, d in lu["by_group"].items():
    w(f"| {g} | {d['n']} | {d['cards']} | {d['luck']} |")
w("")
w("## Notes")
w("- Weekly profiles, weekly PO3, Wyckoff, the 80% rule, round numbers and the volume ORB trade 0.05-0.35 times a week: too rare for a "
  "card at 2-4 trades/week and too few trades to trust any year's sign.")
w("- Pivots are only used once confirmed (2 bars later); value areas are the PRIOR session's RTH profile; VWAP from 09:30.")
w("- Turtle Soup / Unicorn run the 2026-11-23 code (`tools/popular_ict.py`); VWAP SD, ORB, divergence were already rejected in textbook form.")
open(os.path.join(ROOT, "research", "writeups", "ict-lab2-2026-11-25.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:30]))
