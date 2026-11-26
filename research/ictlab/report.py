"""results.json -> research/writeups/ict-lab-2026-11-25.md (one-screen table on top, then every view)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
R = json.load(open(os.path.join(HERE, "results.json")))
V = R["variants"]
FY = ["2022", "2023", "2024", "2025", "2026"]
NAMES = {"QT": "Quarterly Theory (AMDX, TDO, TSO, 90 / 22.5 min)", "MAC": "ICT macros", "SB": "Silver Bullet",
         "JUD": "Judas swing", "PO3": "Power of 3", "SMT": "SMT NQ vs ES (2025-04+)", "IPDA": "IPDA 20/40/60-day ranges",
         "DOL": "PDH/PDL draw (daily bias)", "GAP": "NWOG / NDOG", "OTE": "OTE 62-79%", "KZ": "Killzones",
         "CBDR": "CBDR / Asia SD", "COMBO": "Combos of 2-3", "GATE": "Standalone + gate"}


def k(x):
    if x is None:
        return "-"
    return f"{'+' if x > 0 else '-'}${abs(x) / 1000:.1f}k" if abs(x) >= 1000 else f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):.0f}"


def sq(x, yr=None):
    if yr is not None and x > 0 and yr <= 0:
        return "🟨"          # made money but no better than a random filter of the same size
    if abs(x) < 200:
        return "⬜"
    return "🟩" if x > 0 else "🟥"


def yrow(r):
    yr = r.get("years_vs_random")
    return "".join(sq(r["years_delta"][y], yr[y] if yr else None) for y in FY)


def best(kind, concept):
    vs = [r for r in V.values() if r["kind"] == kind and r["concept"] == concept]
    if not vs:
        return None
    return max(vs, key=lambda r: (r["card"], r["years_better"], r["wf"]))


def ev(e):
    return "-" if not e or e["pass"] is None else f"{e['pass']}% / {e['fail']}%" + (f" ({e['days']}d)" if e["days"] else "")


HEAD = """## The answer on one screen (plain words; $ over 2021-11 .. 2026, costs in, real size)

| Concept | Alone (its own trades) | As a LIT / ATLAS confluence | Verdict |
|---|---|---|---|
| Quarterly Theory (True Day Open 00:00, TSO, 90 / 22.5-min AMDX) | never: TDO -$7.8k, TSO -$15.0k, 22.5-min +$1.4k (about 0) | **LIT bigger when long below / short above the 00:00 open: +$27.8k, 4 of 5 years, beats random size-ups (p < 0.002), 00:00 beats every other hourly open** | **alone never; on LIT works most years (not 2023) = card 1** |
| ICT macros (8 windows) | never: -$50k to -$61k, loses 2026 too | chance (no better than random) | never |
| Silver Bullet 03 / 10 / 14 | 03-04 2026 only (+$4.2k 2026, -$47k 2021-25); 10-11 -$4.2k; 14-15 about 0 | **ATLAS's best hours: SB-hour ATLAS trades x1.5 +$21.7k, 5 of 5 years, the same hours shifted 1 h do nothing** | alone never / 2026 only; on ATLAS works every year = card 2 |
| Judas swing | +$2.1k in 5 years (about 0) | - | never (already rejected 2026-11-20) |
| Power of 3 | 0.16 trades a week, about $0 | ATLAS: works, but so does any overnight open (not PO3-specific) | never alone; generic on ATLAS |
| SMT NQ vs ES (2025-04 .. 2026 only) | -$10.6k | worse than no filter | never |
| IPDA 20 / 40 / 60-day | the worst: -$80k to -$101k (buying discount / selling premium at 09:30 loses every year) | chance | never |
| PDH / PDL draw (daily bias) | -$37k | chance | never |
| NWOG / NDOG | -$9k / -$11k (about 1 trade in 5 weeks) | chance | never |
| OTE 62-79% | +$35.6k but only 2023-25 (2022 -$6.1k, 2026 -$3.8k) | chance | works 2023-25 only, not 2026 |
| OTE + PDH/PDL draw (gate) | +$21.1k, green all 5 years incl 2026 (+$3.2k), but 0.9 trades a week, p 0.056 | - | closest standalone; paper watch, no card |
| Killzones | -$31k | ATLAS x1.5 in KZ +$24k every year, but the 1-h-shifted window does the same = it is "morning", not the killzone | never alone; generic on ATLAS |
| CBDR / Asia SD | -$1.3k / -$6.9k | never | never |
| Combos of 2-3 | - | no combo beats its best single part | adds nothing |

**What the owner has seen work in 2026 is real but it is the 2026 market:** LIT made +$43.8k and ATLAS +$23.6k in 2026 vs +$1.3k / +$10.4k in all of 2021-25.
In 2026 the strategies themselves did well, so most confluences on top of them looked good too. As their own strategy, 11 of the 12 ICT
concepts lose money in at least 2 of the 5 years (PO3 is green 4 of 5 but trades 0.16 a week for +$370 in 5 years), and 16 of the 23
standalone rules lose money in 2026 as well.

**The two confluences that survive every view** (year by year, walk-forward, random-filter luck test, shifted-window test):
1. LIT: x1.5 size when the trade is on the True Day Open side (long below the 00:00 open, short above).
2. ATLAS: x1.5 size inside the Silver Bullet hours (03-04, 10-11, 14-15 ET).
**Both cost eval safety:** the 2026 eval fail rate goes from 1% to 20% (LIT) and from 2% to 13% (ATLAS), because x1.5 is more risk. The
half-size version (x0.5 outside instead of x1.5 inside) keeps the 2022-25 gain and lowers max DD (LIT -$19.4k -> -$13.4k, ATLAS -$11.4k -> -$7.1k)
but makes a little less in 2026 (LIT H2 -$805, ATLAS H1 -$1.5k / H2 -$630). So: size-up = more $ on a funded account, more blow-ups on an eval.

**Luck (f):** 133 pre-listed variants. 9 pass the full card test against 1.8 expected by luck. But 8 of the 9 are on ATLAS, and 7 of those 8 overlap: the same ATLAS
"morning trades are better" effect seen through different windows (killzones, 90-min phase, TDO, PO3, combos). Count it as 2 real findings, not 9.
"""

CARDS = """## Needs-owner-yes cards (exact rules) - research only, nothing changed in the live models

### Card 1: LIT x1.5 on the True Day Open side (Quarterly Theory)
- **Rule:** when a LIT entry fills at or after 00:00 ET and it is a LONG below that session's 00:00 open (5m bar open at 00:00), or a SHORT
  above it, size = 1.5 x the normal LIT size (same stop, same target, still capped by the account's micros and room). Entries before 00:00
  (no TDO yet) and against the TDO side: normal size.
- **Numbers (live LIT replay, real 50K size, costs in):** +$27.8k over 2021-11 .. 2026-10 (+$1,198/mo vs +$741); 2026 H1 +$17.1k, H2 +$4.2k
  (the house LIT split: both better); 2022 / 24 / 25 / 26 better than random size-ups, 2023 not (-$432 vs random); walk-forward +$26.9k;
  placebo p < 0.002; 00:00 beats 21:00, 22:00, 23:00, 01:00, 02:00, 03:00 and 06:00 opens.
- **Cost:** max DD -$19.4k -> -$23.1k; eval 40 sessions 2026 pass 77% -> 71%, **fail 1% -> 20%**; all years fail 38% -> 47%.
- **Lead's advice:** not on the eval (the fail rate). A candidate for a FUNDED LIT account only, or the half-size form below the cut.
  Half-size form (x0.5 when NOT on the TDO side): max DD -$13.4k, all-years eval fail 38% -> 31%, 2026 about flat (H1 +$168, H2 -$805).

### Card 2: ATLAS x1.5 inside the Silver Bullet hours
- **Rule:** an ATLAS entry that fills 03:00-03:59, 10:00-10:59 or 14:00-14:59 ET: 1.5 x the ATLAS size; any other time: normal size.
- **Numbers (ATLAS account stream at $250 a trade, costs in):** +$21.7k over 2021-11 .. 2026-10; better than random in all 5 years
  (2022 +$2.4k, 2023 +$3.0k, 2024 +$0.9k, 2025 +$3.7k, 2026 +$4.9k vs random); 2026 H1 +$7.7k, H2 +$2.0k; 2021-25 +$12.0k; walk-forward
  +$19.1k; p < 0.002. The same hours shifted 1 h or 2 h earlier / later make -$1.7k to +$0.8k, so these exact hours matter.
- **Cost:** max DD -$11.4k -> -$12.4k; 2026 25K eval fail 2% -> 13% (pass 93% -> 84%, 10 -> 7 days).
- **Eval-safe cousin:** C2 (x1.5 only when it is ALSO in the 20-day discount for longs / premium for shorts): +$9.0k, 2026 eval 95% pass /
  2% fail (= as is), 4 of 5 years.
- **Lead's advice:** ATLAS is on a FUNDED 25K: yes-candidate there if the owner accepts more swing (it has only about $900 of room). The ONLY form (skip
  ATLAS outside SB hours) is NOT advised: it loses -$4.2k in 2026 even though it cut the old DD from -$11.4k to -$3.7k.

### Not cards (same effect, overlap with card 2): ATLAS x1.5 in killzones / 90-min M-D phase / TDO side / PO3 side / C3 / C10.
They pass the tests, but shifted windows and other overnight opens do just as well: it is "ATLAS's morning trades are better", already covered by card 2.
"""

L = []
w = L.append
lu = R["luck"]
cards = [r for r in V.values() if r["card"]]
w("# ICT lab 2026-11-25: every popular ICT / time-price concept, tested the other ways")
w("")
w("Paper research, futures data only (CME NQ1! 5m 2021-10 .. 2026-11-20; ES1! from 2025-04 only, so SMT is 2025-26 only). "
  "Rules written before the run: `research/ictlab/DESIGN.md` (definitions + sources). Code `research/ictlab/ict_lab.py`, numbers "
  "`research/ictlab/results.json`. LIT = live replay at real 50K size (to 2026-10-16); ATLAS = account stream at $250 a trade "
  "(to 2026-10-13); standalones at LIT size. Costs in everywhere.")
w("")
w(HEAD)
w("**Follow-up (real engine, eval-safe forms, config diffs): `research/writeups/ict-lab-proof-2026-11-25.md`.** Cards there: B2 ATLAS x0.5 outside SB hours (Builder evals), B1 C2 (small). LIT TDO half-size and funded ATLAS x1.5: no card.")
w("")
w("## Detail squares (the best variant of each concept; every variant is in the tables below)")
w("")
w("Years 2022..2026, one square each: 🟩 better, 🟥 worse, ⬜ about flat, 🟨 made $ but no better than a random filter of the same size. "
  "WF = walk-forward $ (pick on the last 6 months, trade the next 3, roll; vs the strategy as is). For each concept the best of its "
  "variants is shown (all variants are in the tables below).")
w("")
w("| Concept | Alone (yrs, WF) | On LIT (yrs, WF) | On ATLAS (yrs, WF) | Plain words |")
w("|---|---|---|---|---|")
for c in ["QT", "MAC", "SB", "JUD", "PO3", "SMT", "IPDA", "DOL", "GAP", "OTE", "KZ", "CBDR", "COMBO", "GATE"]:
    cells = []
    words = []
    for kind in ("STAND", "LIT", "ATLAS"):
        r = best(kind, c)
        if not r:
            cells.append("-")
            continue
        cells.append(f"{yrow(r)} {k(r['wf'])}")
        words.append(f"{'alone' if kind == 'STAND' else kind}: {r['verdict']}")
    w(f"| {NAMES[c]} | " + " | ".join(cells) + " | " + "; ".join(words) + " |")
w("")
w(f"**Luck check (f):** {lu['variants']} variants tested. Passing the card test (better in 4 of 5 years AND walk-forward positive AND "
  f"placebo p < 0.05 AND the house split rule) : **{lu['cards_real']}**. Expected by luck alone: "
  f"{lu['cards_expected_by_luck']} pass the years + WF part (random filters / random-side trades). p < 0.05: {lu['p05_real']} real vs "
  f"{lu['p05_expected']} by chance.")
w("")
if cards:
    w("**Needs-owner-yes candidates:** " + ", ".join(f"`{r['name']}`" for r in cards) + " (cards at the bottom).")
else:
    w("**Needs-owner-yes cards: none.** Nothing is positive in the walk-forward AND most years AND beats luck AND passes the 2026 split rule.")
w("")

# ------------------------------------------------------------------------------------------ (e) 2026 view
w("## (e) 2026 only (what the owner has seen) - labelled: 2026 Jan .. data end")
w("")
w("| Variant | 2026 H1 $ vs as-is | 2026 H2 $ vs as-is | 2026 $/mo (abs) | 2026 eval pass / fail | 2021-25 $ vs as-is | verdict |")
w("|---|---|---|---|---|---|---|")
top26 = sorted([r for r in V.values() if r["concept"] not in ("BASE", "ROBUST")], key=lambda r: -(r["d_h1_2026"] + r["d_h2_2026"]))[:15]
for r in [V["LIT_BASE"], V["ATLAS_BASE"]] + top26:
    w(f"| {r['name']} | {k(r['d_h1_2026'])} | {k(r['d_h2_2026'])} | {k(r['y2026']['usd_mo'])} | {ev(r['eval_2026'])} | "
      f"{k(r['d_2021_25'])} | {r['verdict']} |")
w("")
w("Base rows show absolute $ (H1 / H2 of the strategy itself). Top 15 by 2026 gain. The pattern: what helps in 2026 mostly hurts in 2021-25, "
  "or the reverse.")
w("")

# ------------------------------------------------------------------------------------------ main table per kind
for kind, title in (("STAND", "Standalone (one trade a day max, LIT size, Builder 50K eval)"),
                    ("LIT", "As a filter / size-up on LIT (Builder 50K eval)"),
                    ("ATLAS", "As a filter / size-up on ATLAS (Builder 25K eval)")):
    w(f"## {title}")
    w("")
    w("ONLY = take only trades with the concept; UP = x1.5 size with it, x1 without. $ for filters = change vs the strategy as is.")
    w("")
    w("| Variant | (a) 2021 / 22 / 23 / 24 / 25 / 26 $ | yrs | (b) WF $ | (c) eval 40 sessions all / 2026 | (d) $/mo, max DD | tr/wk | PF | p | verdict |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted([x for x in V.values() if x["kind"] == kind and x["concept"] != "ROBUST"],
                    key=lambda x: (x["concept"] != "BASE", x["name"])):
        yd = " / ".join(k(r["years_delta"][str(y)] if str(y) in r["years_delta"] else r["years_delta"].get(y))
                        for y in ["2021"] + FY)
        w(f"| {r['name']}{' **CARD**' if r['card'] else ''} | {yd} | {yrow(r)} | {k(r['wf'])} | {ev(r['eval_all'])} · {ev(r['eval_2026'])} | "
          f"{k(r['all']['usd_mo'])}/mo, {k(r['all']['maxdd'])} | {r['tpw']} | {r['pf']} | {r['p'] if r['p'] is not None else '-'} | {r['verdict']} |")
    w("")

# ------------------------------------------------------------------------------------------ quarter heat map
w("## (a) Quarter heat map (2021Q4 .. 2026Q4, one square a quarter; filters = change vs as-is)")
w("")
qs = sorted({q for r in V.values() for q in r["quarters_delta"]})
w("`" + " ".join(q[2:] for q in qs) + "`")
w("")
w("| Variant | quarters |")
w("|---|---|")
for r in sorted([x for x in V.values() if x["concept"] != "ROBUST"], key=lambda x: (x["kind"], x["name"])):
    w(f"| {r['name']} | " + "".join(sq(r["quarters_delta"].get(q, 0)) for q in qs) + " |")
w("")

# ------------------------------------------------------------------------------------------ WF per concept
w("## (b) Walk-forward per concept (each quarter: best variant of the concept on the last 6 months, or none if none made $)")
w("")
w("| Strategy : concept | WF $ (vs as-is) | variants | quarters switched on | last pick |")
w("|---|---|---|---|---|")
for key, p in sorted(R["pick"].items()):
    w(f"| {key} | {k(p['wf_pick'])} | {p['n_variants']} | {p['blocks_on']} of {p['blocks']} | {p['last_pick'] or 'none'} |")
w("")

# ------------------------------------------------------------------------------------------ ATLAS member check
w("## ATLAS: is a time filter just picking members? (share of each member's trades the filter keeps)")
w("")
mem = R["atlas_member_keep_pct"]
srcs = sorted({s for m in mem.values() for s in m})
w("| Filter | " + " | ".join(srcs) + " |")
w("|---|" + "---|" * len(srcs))
for f, m in mem.items():
    w(f"| {f} | " + " | ".join(f"{m.get(s, '-')}%" for s in srcs) + " |")
w("")

# ------------------------------------------------------------------------------------------ robustness
w("## Is it really the ICT time / level? (same filter with the clock shifted, or another hourly open instead of 00:00)")
w("")
w("Not counted as tries. If the shifted window or a different open works as well, the edge is 'that part of the day', not the ICT rule.")
w("")
w("| Check | LIT ONLY $ | LIT UP $ | ATLAS ONLY $ | ATLAS UP $ |")
w("|---|---|---|---|---|")
def tot(n):
    r = V.get(n)
    return k(sum(r["years_delta"].values())) + (f" (p {r['p']})" if r and r["p"] is not None else "") if r else "-"
rows_ = [("SB hours as taught", "F_SB")] + [(f"SB shifted {x:+d} min", f"R_SB_shift{x:+d}") for x in (-120, -60, 60, 120)] + \
        [("Killzones as taught", "F_KZ")] + [(f"KZ shifted {x:+d} min", f"R_KZ_shift{x:+d}") for x in (-120, -60, 60, 120)] + \
        [("Macros as taught", "F_MAC")] + [(f"Macros shifted {x:+d} min", f"R_MAC_shift{x:+d}") for x in (-120, -60, 60, 120)] + \
        [("True Day Open 00:00 as taught", "F_TDO")] + [(f"open at {hh:02d}:00 instead", f"R_OPEN_{hh:02d}00") for hh in (21, 22, 23, 1, 2, 3, 6)]
for lab, f in rows_:
    w(f"| {lab} | {tot(f'LIT_{f}_ONLY')} | {tot(f'LIT_{f}_UP')} | {tot(f'ATLAS_{f}_ONLY')} | {tot(f'ATLAS_{f}_UP')} |")
w("")

# ------------------------------------------------------------------------------------------ half-size check
CC = json.load(open(os.path.join(HERE, "cards_check.json")))
w("## Post-hoc: HALF size outside the concept (x1 with it, x0.5 without) - the eval-friendly version")
w("")
w("Not pre-registered; run only on the card candidates to see whether the gain survives without adding risk.")
w("")
w("| Variant | 2022 / 23 / 24 / 25 / 26 $ vs as-is | WF $ | 2026 H1 / H2 $ | max DD (as-is) | eval 40 all (as-is) | eval 2026 (as-is) |")
w("|---|---|---|---|---|---|---|")
for nm, d in CC.items():
    w(f"| {nm} | {' / '.join(k(d['years_delta'][y]) for y in FY)} | {k(d['wf'])} | {k(d['h1_2026_delta'])} / {k(d['h2_2026_delta'])} | "
      f"{k(d['all']['maxdd'])} ({k(d['base_all']['maxdd'])}) | {ev(d['eval_all'])} ({ev(d['base_eval_all'])}) | {ev(d['eval_2026'])} ({ev(d['base_eval_2026'])}) |")
w("")

# ------------------------------------------------------------------------------------------ cards
w(CARDS)
if cards:
    w("## All 9 variants that passed the automatic card test")
    for r in cards:
        w(f"### {r['name']}: {r['desc']}")
        w(f"- Rule: see `research/ictlab/DESIGN.md` ({r['concept']}). Years {yrow(r)}, WF {k(r['wf'])}, p {r['p']}, 2026 H1 {k(r['d_h1_2026'])}, "
          f"H2 {k(r['d_h2_2026'])}, 2021-25 {k(r['d_2021_25'])}, eval {ev(r['eval_all'])} / 2026 {ev(r['eval_2026'])}.")
    w("")
w("## Notes / limits")
w("- 5m bars: the 22.5-min cycle edges and the 02:33 / 04:03 macro starts are rounded to the 5m bar that holds them.")
w("- LIT x1.5 is linear on the replay $ (ignores the 40-micro cap and the eval room sizing): an upper bound.")
w("- `research/ideamill/DESIGN_v3.md` is not in this repo; the luck count here = placebo pass rate x variants (DESIGN.md section 5f).")
w("- Concepts already rejected before (Silver Bullet 10-11, Judas, PO3, SMT, ICT 2022: TESTED_AND_REJECTED 2026-11-20 / -23) were re-run "
  "only for the new views; same answer unless a row above says otherwise.")
open(os.path.join(ROOT, "research", "writeups", "ict-lab-2026-11-25.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:40]))
