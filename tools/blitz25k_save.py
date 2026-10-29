"""BLITZ on its own MFFU Builder 25K (account C): store the runs (tools/runlib -> research/runs/) and the pick file
research/scalp/blitz_25k_pick.json (research/writeups/blitz-25k.md). Research only.

    python -X utf8 tools/blitz25k_save.py      # after tools/blitz25k_grid.py baseline / stops / mgmt / ideas / checks and
                                               # tools/blitz25k_size.py grid / today
"""
from __future__ import annotations

import json
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import scalp_na_lib as N  # noqa: E402
from tools import scalp_mo_lib as L  # noqa: E402
from tools import blitz25k_lib as K  # noqa: E402
from tools import blitz25k_grid as BG  # noqa: E402
from tools import blitz25k_size as BS  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp")
J = lambda n: json.load(open(os.path.join(OUT, n)))


def _sessions():
    S5 = N.sessions(N.bars(5), "R")
    S1 = N.sessions(N.bars(1), "H1") + N.sessions(N.bars(1), "H2")
    return sorted(set(S5) | set(S1))


def _store(TT, usd=150.0, trig="blitz"):
    T = [t for t in TT[5] if t["day"] < "2026-01-01"] + [t for t in TT[1] if t["day"] >= "2026-01-01"]
    tr = L.runlib_trades(T, usd, 20)
    for t in tr:
        t["trigger"] = trig
    return tr


def _line(r, sp):
    x = r[sp]
    return (f"{x['tpw']}/wk, {x['wk2']}% weeks 2+, PF {x['pf']}, net ${x['net']:,} (${x['per_month']}/mo), DD ${x['dd']:,}, avg R {x['avg_r']:+.3f}, "
            f"25K 2-week pass/fail {x['f40']['p10']}/{x['f40']['f10']} at 40% of the room")


def main():
    from tools import runlib as rl
    sess = _sessions()
    BG.prep()
    sz = J("b25_today_sizing.json")
    pk = sz["picks"]["money"]
    base = J("b25_baseline.json")
    mg = J("b25_mgmt.json")
    ck = J("b25_checks.json")
    # 1. today's BLITZ as account C (the reference every variant was judged against)
    TT = K.trades({}, "lit+atlas")
    r = base["lit+atlas"]
    slot = lambda sp: pk["today"][sp]["slot"]["life_pm"]
    ev = lambda sp: f"{pk['today'][sp]['eval']['p10']}/{pk['today'][sp]['eval']['f10']}"
    v1 = (f"Today's BLITZ rule on its own MFFU Builder 25K, never opposite LIT / ATLAS (closed first at their opposite entry). At $150 a trade: "
          f"2026 H1 {_line(r, 'H1')}; H2 {_line(r, 'H2')}; 2021-25 (5m) {_line(r, 'R')}. Alone (no anti-hedge rule): $ / month "
          f"{base['alone']['H1']['per_month']} / {base['alone']['H2']['per_month']} / {base['alone']['R']['per_month']}. Random directions: avg R "
          f"{ck['placebo']['H1']['mean']} / {ck['placebo']['H2']['mean']} / {ck['placebo']['R']['mean']} (p {ck['placebo']['H1']['p']} / "
          f"{ck['placebo']['H2']['p']} / {ck['placebo']['R']['p']}). Best 25K slot sizing (picked on H1: {pk['name']}): 2-week pass/fail "
          f"{ev('H1')} / {ev('H2')} / {ev('R')}, whole slot ${slot('H1')} / ${slot('H2')} / ${slot('R')} a month.")
    rl.save("blitz25k_today_acct_c", "BLITZ (today's rule) on its own Builder 25K as account C, $150 a trade", "other",
            "Owner 2026-10-29: BLITZ gets its own MFFU 25K next week - what does the anti-hedge rule cost, and what is its best honest 25K setup?",
            params={**K.TODAY, "account_c": "never opposite LIT / ATLAS; closed at their opposite entry"},
            sizing={"fixed_usd": 150.0, "eval_25k": pk["ez"], "funded_25k": pk["fz"]}, trades=_store(TT), scored=rl.score(_store(TT), sess),
            status="info", verdict=v1, notes="tools/blitz25k_grid.py baseline / checks; tools/blitz25k_size.py today",
            writeup="blitz-25k", tags=["scalp", "blitz", "account_c", "25k"])
    print("saved blitz25k_today_acct_c", flush=True)
    # 2. the H1 pick of the rule search (rejected) and the best "like a person" structure variant (rejected)
    G = json.load(open(os.path.join(OUT, "b25_grid_mgmt.json")))["rows"]
    ok = [x for x in G if BG.ok_h1(x)]
    h1 = max(ok, key=lambda x: x["H1"]["t_r"])

    def fam(x):
        v = x["v"]
        return "structure" if (v.get("sw_trail", 0) or v.get("choch", 0)) else ("target" if v.get("tgt") else "clock")
    st = max((x for x in ok if fam(x) == "structure"), key=lambda x: x["H1"]["t_r"])
    for rid, title, x, q in (("blitz25k_h1pick", "BLITZ rule search: the H1 pick (60-minute low stop, partial at liquidity, 45 minutes) - rejected", h1,
                              "Does a structure stop / target / management beat today's BLITZ on its own 25K?"),
                             ("blitz25k_structure", "BLITZ 'like a person': stop follows each new 1m swing, out on a change of character, target at equal highs / lows - rejected", st,
                              "Owner: trade like a person, learn market structure - does structure management beat the 30-minute clock?")):
        TTx = K.trades(x["v"], "lit+atlas")
        vx = (f"{BG.vname(x['v'])}. At $150 a trade: H1 {_line(x, 'H1')}; H2 {_line(x, 'H2')}; 2021-25 {_line(x, 'R')}. Today's rule (account C): "
              f"$ / month {r['H1']['per_month']} / {r['H2']['per_month']} / {r['R']['per_month']}, avg R {r['H1']['avg_r']:+.3f} / {r['H2']['avg_r']:+.3f} / "
              f"{r['R']['avg_r']:+.3f}. Rejected: not better in H2 and 2021-25.")
        rl.save(rid, title, "other", q, params={**K.TODAY, **x["v"]}, sizing={"fixed_usd": 150.0}, trades=_store(TTx), scored=rl.score(_store(TTx), sess),
                status="rejected", verdict=vx, notes="tools/blitz25k_grid.py mgmt (1,920 variants, account C)", writeup="blitz-25k",
                tags=["scalp", "blitz", "structure", "account_c"])
        print("saved", rid, flush=True)
    pick_file(pk, sz, base, mg, ck)


def pick_file(pk, sz, base, mg, ck):
    """research/scalp/blitz_25k_pick.json: the exact rule + 25K sizing an engine can load, its numbers and the verdict."""
    ideas = J("b25_ideas.json")
    sizeg = J("b25_size.json")
    rule = {"name": "BLITZ", "version": "today (engine/blitz.py VERSION 2, research/writeups/scalp-na-mffu.md)", "tf": "1m", "instrument": "MNQ",
            "band": {"anchor": "09:30 ET open", "lookback_sessions": 14, "vm": 1.0},
            "day_filter": {"prior_rth_range_vs_14_mean_min": 0.8},
            "checks": {"closes_et": ["11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30"], "every_min": 30,
                       "window_open_minutes": [630, 930]},
            "entry": {"type": "market", "when": "next bar open after the check close", "slip_ticks": 1},
            "stop": {"type": "atr", "atr": "Wilder 14 of 5m bars (last completed)", "k": 1.5, "from": "signal close"},
            "target": None, "trail": {"after_r": 1.0, "distance_r": 1.5}, "time_exit_bars_after_entry": 30, "flat_et": "15:55",
            "max_trades_day": 6, "day_stop_r": -3.0, "entries_until_et": "15:30",
            "account_c": {"never_opposite": ["LIT (account A) open position", "ATLAS (account B) open position"],
                          "on_opposite_entry": "close BLITZ at the open of the first bar at / after their entry (they go first)",
                          "lit_armed": "optional stricter mode (also never opposite a LIT setup that is armed): ~equal in research"}}
    ez, fz = pk["ez"], pk["fz"]
    sizing = {"plan": {"name": "MFFU Builder 25K", "price": 63.0, "target": 1500.0, "mll_eod_trailing": 1000.0, "lock": "start + $100",
                       "soft_daily_loss": 600.0, "max_micros": 20},
              "eval": {"mode": "room_fraction", "f": ez["f"], "cap_usd": ez["cap"],
                       "push": {"from_session": ez["push"][0], "f": ez["push"][1]} if ez.get("push") else None,
                       "dll_guard": "risk <= 0.9 x the soft daily loss left", "min_1_micro_if": "1 micro's stop-out <= half the room and the daily loss left",
                       "micros": "floor(risk_usd / ((stop pts + 1 tick) x $2 + $1.90))", "stuck": "room < 2 x the median 1-micro stop-out -> treat as dead"},
              "funded": {"mode": "room_fraction", "f": fz["f"], "cap_usd": fz["cap"], "day_profit_stop_usd": fz.get("day_tp")}}
    nums = {}
    for sp, lab in (("H1", "2026 H1 (pick)"), ("H2", "2026 H2 (check)"), ("R", "2021-25 (5m)")):
        b = base["lit+atlas"][sp]
        e = pk["today"][sp]["eval"]
        s = pk["today"][sp]["slot"]
        f = pk["today"][sp]["funded"]
        nums[lab] = {"trades_week": b["tpw"], "weeks_2plus_pct": b["wk2"], "pf": b["pf"], "net_usd_150": b["net"], "usd_month_150": b["per_month"], "max_dd_150": b["dd"],
                     "avg_r": b["avg_r"], "p10": e["p10"], "f10": e["f10"], "dec10": e["dec10"], "p15": e["p15"], "f15": e["f15"], "p20": e["p20"], "f20": e["f20"],
                     "slow_pass": e["slow_pass"], "pass_med": e["pass_med"], "slot_usd_month": s["life_pm"], "slot_lose_pct": s["life_lose"],
                     "funded_usd_month": f.get("fund_pm"), "funded_stuck_pct": f.get("fund_stuck")}
    paper = sz["picks"].get("paper (engine/blitz.py: 40% / $600)")
    out = {"name": "BLITZ on its own MFFU Builder 25K (account C)", "date": "2026-10-29", "writeup": "research/writeups/blitz-25k.md",
           "verdict": "no-change",
           "why": ("No stop / target / management / window / entry variant beat today's rule in 2026 H1, H2 AND 2021-25 (0 of 1,920 management "
                   "variants, 0 of 45 stops, 0 of 26 window / entry ideas on avg R, $ / month and the 25K 2-week pass - fail together); "
                   "the H1 picks lose in H2 or 2021-25. Today's rule stays. Only the 25K eval SIZING changes for its own account (below)."),
           "rule": rule, "sizing": sizing, "numbers": nums,
           "paper_size_for_comparison": {"name": paper["name"], **{sp: {"p10": paper["today"][sp]["eval"]["p10"], "f10": paper["today"][sp]["eval"]["f10"],
                                                                         "dec10": paper["today"][sp]["eval"]["dec10"], "slow_pass": paper["today"][sp]["eval"]["slow_pass"],
                                                                         "slot_usd_month": paper["today"][sp]["slot"]["life_pm"]}
                                                                    for sp in ("H1", "H2", "R")}} if paper else None,
           "speed_pick": ({"name": sz["picks"]["speed"]["name"], **{sp: {"p10": sz["picks"]["speed"]["today"][sp]["eval"]["p10"],
                                                                          "f10": sz["picks"]["speed"]["today"][sp]["eval"]["f10"],
                                                                          "dec10": sz["picks"]["speed"]["today"][sp]["eval"]["dec10"],
                                                                          "slot_usd_month": sz["picks"]["speed"]["today"][sp]["slot"]["life_pm"]}
                                                                     for sp in ("H1", "H2", "R")}} if sz["picks"].get("speed") else None),
           "account_c_cost": {sp: {"alone_usd_month_150": base["alone"][sp]["per_month"], "account_c_usd_month_150": base["lit+atlas"][sp]["per_month"],
                                   "alone_slot": pk["today_alone"][sp]["slot"]["life_pm"], "account_c_slot": pk["today"][sp]["slot"]["life_pm"]}
                              for sp in ("H1", "H2", "R")},
           "random_directions": ck["placebo"], "stress": ck["stress"],
           "rejected_best": {"h1_pick": BG.vname(mg["pick"]["v"]) if mg.get("pick") else None,
                             "rule_slots": {k: {"name": BG.vname(v["v"]), **{sp: v["slot"][sp]["life_pm"] for sp in ("H1", "H2", "R")}}
                                            for k, v in sizeg["picks"].items()}},
           "ideas_beat_all": ideas.get("beat_all"),
           "caveats": ["2021-25 is the same rule on 5m bars (fills coarser)", "LIT / ATLAS clashes use the research trades (2026 lit_live, 2021-25 REF rows)",
                       "the 25K slot still loses money in 2021-25 with every setting tested: BLITZ on its own 25K is a 2026-regime bet"]}
    json.dump(out, open(os.path.join(OUT, "blitz_25k_pick.json"), "w"), indent=1, default=float)
    print("wrote research/scalp/blitz_25k_pick.json")


if __name__ == "__main__":
    main()
