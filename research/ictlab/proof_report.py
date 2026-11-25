"""proof.json -> research/writeups/ict-lab-proof-2026-11-25.md (the CLAUDE.md proof format on the eval-safe forms)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
D = json.load(open(os.path.join(HERE, "proof.json")))
SP = ("H1", "H2", "REF", "2025")
SPN = {"H1": "2026 Jan-Jun", "H2": "2026 Jul-Oct 16", "REF": "2021-11..2025", "2025": "2025 alone"}
PN = {"mffu_builder_50k": "Builder 50K", "mffu_builder_25k": "Builder 25K", "mffu_rapid_eod_25k": "Rapid EOD 25K"}


def k(x):
    if x is None:
        return "-"
    s = "+" if x > 0 else "-" if x < 0 else ""
    return f"{s}${abs(x) / 1000:.1f}k" if abs(x) >= 1000 else f"{s}${abs(x):.0f}"


def ev(e):
    return f"{e['pass']:.0f}/{e['fail']:.0f}%" + (f" {e['med_days']:.0f}d" if e["med_days"] else "")


VERD = {
    "A": ("NO CARD (fails the LIT split on $)", "2026 H1 -$152 and Jul-Oct -$822 vs as-is (both halves slightly worse in $), so the house rule "
          "(pick on Jan-Jun, check on Jul-Oct, both better) fails. It is a risk reducer: 2021-25 +$6.3k, max DD -$21.1k -> -$14.0k, "
          "fewer failed evals in every span (50K H1 9.9% -> 6.8%, H2 11.1% -> 8.6%) but slower passes (H2 median 8 -> 12 days) and "
          "a lower 2025 pass rate (25% -> 18%). Paper lead only."),
    "B1": ("CARD (weak): both 2026 halves + 2021-25 + 2025 better", "Fixed $: H1 +$3.2k, H2 +$281, 2021-25 +$565, 2025 +$619; PF up in "
           "every span. 25K eval pass H1 81% -> 83%, H2 60% -> 73%, but fails tick up (H1 4.2% -> 5.0%, H2 4.8% -> 5.3%; 50K H2 10.4% -> "
           "13.2%). Walk-forward 10 of 18 windows won (+$3.5k). Touches only 16% of ATLAS trades; most of the gain is 2026 H1. One of 20 "
           "pre-listed combos: treat as a small, fragile edge."),
    "B2": ("CARD (eval safety): eval better in both 2026 halves, $ about flat", "Fixed $: H1 -$601, H2 -$97 (flat-to-slightly-less), "
           "2021-25 +$20.9k, 2025 +$5.9k; max DD down 30-60% in every span; PF up everywhere. Builder 25K eval: H1 pass 81% -> 92%, fail "
           "4.2% -> 0.1%; H2 pass 60% -> 67%, fail 4.8% -> 0.2% (slower: 11 -> 14 / 20 -> 23 days). Builder 50K: fail 12.0% -> 1.1% / "
           "10.4% -> 1.6%. Walk-forward 13 of 18 windows won (+$18.0k). NOT for the Rapid EOD 25K (pass 51% -> 36%). By the strict "
           "'net $ both halves better' reading it misses by $601 / $97; by eval pass/fail (the money on an eval) it wins both halves."),
}
CFG = {
    "A": ("live_model.json AND live_model_lit.json (same diff in both; not applied)",
          '"lit_sizing": {\n    ...,\n+   "tdo_side": {"on": true, "level": "00:00 ET 5m open (True Day Open)", "wrong_side_mult": 0.5,\n'
          '+                "applies": "entries at/after 00:00 ET: long above / short below the level", "min_micros": 1}\n  }',
          "needs code: engine/sizing.lit_qty + funded_qty read it (the lead wires; then lit_losses.py live, model_versions.py, "
          "tests.test_lit_live)"),
    "B1": ("data/account_b.json on the PC (the account_b block; second_model.json ships null) - not applied",
           '{\n  ...,\n+ "time_size": {"on": true, "hours_et": [3, 10, 14], "need_ipda20_side": true, "in_mult": 1.5, "out_mult": 1.0}\n}',
           "needs code: engine/account_b.qty (eval + funded) applies it before dll_guard; the 20-day range = the last 20 sessions' high/low"),
    "B2": ("data/account_b.json on the PC (the account_b block) - not applied",
           '{\n  ...,\n+ "time_size": {"on": true, "hours_et": [3, 10, 14], "in_mult": 1.0, "out_mult": 0.5}\n}',
           "needs code: engine/account_b.qty (eval stage; keep Rapid accounts OFF), then the ATLAS tests (run_area atlas)"),
}

L = []
w = L.append
w("# ICT lab proof 2026-11-25: the eval-safe forms, real engine")
w("")
w("Lead's follow-up to `ict-lab-2026-11-25.md`. Engine = `research/plans/rank.py` + `research/onebook/book.py` (real fills: ATLAS at "
  "10 ticks a side, LIT eval two_week sizing, funded presets, every MFFU rule), 1,000 Monte Carlo paths per span (60-session evals, "
  "126-session slots incl. the funded stage and payouts), seeds as rank.py. Funded ATLAS = `tools/atlas_funded.py` replay with the live "
  "funded sizing (40% of room, <= $750, winner <= $1,000, soft daily loss, 2-loss streak = 1 micro). Code `research/ictlab/proof.py`, "
  "numbers `research/ictlab/proof.json`. Multipliers floor to whole micros, never below 1. Nothing in the live models changed.")
w("")
w("## One screen")
w("")
w("| Form | 2026 H1 $ | 2026 H2 $ | 2021-25 $ | 2025 $ | max DD 2021-25 | eval 25K H1 / H2 pass-fail | WF windows won | Verdict |")
w("|---|---|---|---|---|---|---|---|---|")
for v, V in D["variants"].items():
    a, b = V["fixed"]["as_is"], V["fixed"]["variant"]
    e = V["plans"]["mffu_builder_25k"]
    w(f"| {v}: {V['desc']} | {k(b['H1']['net'] - a['H1']['net'])} | {k(b['H2']['net'] - a['H2']['net'])} | "
      f"{k(b['REF']['net'] - a['REF']['net'])} | {k(b['2025']['net'] - a['2025']['net'])} | {k(a['REF']['max_dd'])} -> {k(b['REF']['max_dd'])} | "
      f"{ev(e['as_is']['H1']['eval'])} -> {ev(e['variant']['H1']['eval'])} / {ev(e['as_is']['H2']['eval'])} -> {ev(e['variant']['H2']['eval'])} | "
      f"{V['wf']['windows_won']} of {V['wf']['windows']} | {VERD[v][0]} |")
C = D["C"]
a, b = C["as_is"], C["sb_x1.5"]
w(f"| C: FUNDED ATLAS 25K x1.5 in SB hours | paid {k(a['H1']['paid_6m'])} -> {k(b['H1']['paid_6m'])} / 6 mo | {k(a['H2']['paid_6m'])} -> "
  f"{k(b['H2']['paid_6m'])} | 2021-24 {k(a['2021-24']['paid_6m'])} -> {k(b['2021-24']['paid_6m'])} | {k(a['2025']['paid_6m'])} -> "
  f"{k(b['2025']['paid_6m'])} | - | dead H1 {a['H1']['dead_6m']}% -> {b['H1']['dead_6m']}%, H2 {a['H2']['dead_6m']}% -> {b['H2']['dead_6m']}% | - | "
  "NO CARD: same payouts, more dead accounts |")
w("")
w("$ columns = change vs ATLAS / LIT as is, fixed size (LIT at its $800 rule, ATLAS $250 a trade, real fills, costs in).")
w("Note: with real fills (10 ticks a side) ATLAS as is LOSES in 2021-25 (-$28.2k at $250, PF 0.82), unlike the stored-fill stream in the "
  "first write-up (+$10.4k). The 2026 numbers agree.")
w("")
for v, V in D["variants"].items():
    w(f"## {v}: {V['desc']}")
    w("")
    w(f"**{VERD[v][0]}.** {VERD[v][1]}")
    w("")
    w(f"Trades changed: {V['share_changed']}% of the strategy's trades. Walk-forward (3-month windows from 2022-05, 6-month look-back): "
      f"{V['wf']['windows_won']} of {V['wf']['windows']} windows won, switch-on WF {k(V['wf']['wf_usd'])}.")
    w("")
    w("| Span | trades/wk | PF | net $ | $/month | max DD |")
    w("|---|---|---|---|---|---|")
    for s in SP:
        x, y = V["fixed"]["as_is"][s], V["fixed"]["variant"][s]
        w(f"| {SPN[s]} | {y['tpw']} | {x['pf']} -> {y['pf']} | {k(x['net'])} -> {k(y['net'])} | {k(x['per_month'])} -> {k(y['per_month'])} | "
          f"{k(x['max_dd'])} -> {k(y['max_dd'])} |")
    w("")
    w("Eval (60 sessions, pass / fail %, median days to pass) and the 6-month slot net $ (eval fees + funded payouts), as is -> form:")
    w("")
    w("| Account | " + " | ".join(SPN[s] for s in SP) + " |")
    w("|---|" + "---|" * len(SP))
    for p, P in V["plans"].items():
        w(f"| {PN[p]} | " + " | ".join(f"{ev(P['as_is'][s]['eval'])} -> {ev(P['variant'][s]['eval'])}, slot {k(P['as_is'][s]['slot']['net_6m'])} -> "
                                       f"{k(P['variant'][s]['slot']['net_6m'])}" for s in SP) + " |")
    w("")
    f, diff, note = CFG[v]
    w(f"Config diff (exact, NOT applied) - {f}:")
    w("```diff")
    w(diff)
    w("```")
    w(f"({note})")
    w("")
w("## C: FUNDED ATLAS 25K, x1.5 in Silver Bullet hours (live funded sizing)")
w("")
w("Rule: an ATLAS entry 03:00-03:59 / 10:00-10:59 / 14:00-14:59 ET on the funded account sizes with room share 60% (40% x 1.5) and cap "
  "$1,125 ($750 x 1.5); the $1,000 best-day guard, the $600 soft daily loss guard and the 2-loss streak rule stay. 1,000 paths x 6 months.")
w("")
w("| Span | paid 6 mo (owner, 80%) | $/month | payouts in 6 mo | first payout (median session) | lost % | dead % (lost + stuck < $100 room) | real path payouts / $ / lost |")
w("|---|---|---|---|---|---|---|---|")
for s in ("H1", "H2", "2025", "2021-24"):
    x, y = a[s], b[s]
    xr, yr = a[s + "_real"], b[s + "_real"]
    w(f"| {s} | {k(x['paid_6m'])} -> {k(y['paid_6m'])} | {k(x['per_month'])} -> {k(y['per_month'])} | {x['payouts_6m']} -> {y['payouts_6m']} | "
      f"{x['first_med']} -> {y['first_med']} | {x['lost_6m']} -> {y['lost_6m']} | {x['dead_6m']} -> {y['dead_6m']} | "
      f"{xr['payouts']} / {k(xr['paid'])} / {xr['lost']} -> {yr['payouts']} / {k(yr['paid'])} / {yr['lost']} |")
w("")
w("**NO CARD.** The $1,000 best-day guard and the $600 daily loss guard appear to cap most SB-hour trades near the size they already had (max risk per trade is unchanged in every span), so the "
  "payouts do not change (H1 identical, H2 -$34), and the bigger trades that do get through leave more accounts stuck under $100 of room "
  "(H2 2.8% -> 7.2%). Config diff: none proposed.")
w("")
w("## Lead summary")
w("- Owner cards: **B2** (ATLAS x0.5 outside SB hours, Builder evals only: fails 4-12% -> 0-2%, $ about flat in 2026, +$20.9k 2021-25) "
  "and **B1** (C2, small: +$4.1k fixed over 2021-11..2026-10, eval pass up, fails +0.5-3 pts).")
w("- Not cards: **A** (LIT TDO half-size: both 2026 halves slightly worse in $; paper lead as a drawdown cut) and **C** (no effect).")
w("- All need a small engine change before they could go live; config diffs above are proposals only.")
open(os.path.join(ROOT, "research", "writeups", "ict-lab-proof-2026-11-25.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:20]))
