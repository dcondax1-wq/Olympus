"""Account rules = MFFU's rules (2026-11-20, owner: "make sure you have all the rules for each account memorized").

research/lit/mffu_rules.json is the one rulebook (MFFU's public pages, each value with its source + checked date;
docs/ACCOUNT_RULES.md is the plain page). This test fails loudly when a number the bot trades or pays by drifts from it:
  a. engine/payout_coach.PLANS and engine/funded_life.PLANS (Builder 25K / 50K payouts: buffer, min, max, split, best day,
     traded days, 48 h, 5 payouts, floor lock, max loss)
  b. engine/multi_account.PRESETS (Builder + Rapid EOD rules: target, max loss, lock, daily loss, max micros, best day,
     min days, news ban) and engine/sizing.TW_25K
  c. engine/rapid.PLANS / constants (Rapid EOD 25K / 50K: target, buffer, split, 30% day, 4 days, payout min)
  d. inactivity days, the flat time (the bot's 15:55 must be at or before MFFU's 16:10), the Tier-1 news window (the bot's
     must cover MFFU's -2 / +2 min)
  e. the rulebook itself: every account rule has a value, a source URL and a checked date no older than 30 days
Stricter-than-MFFU bot values are allowed only where named here (and listed in docs/ACCOUNT_RULES.md).

  python -X utf8 -m tests.test_account_rules
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def V(x):
    return x.get("value") if isinstance(x, dict) and "value" in x else x


RB = json.load(open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))
L = RB["limits"]


def part_a():
    from engine import payout_coach as PC, funded_life as FL
    for key, lim in (("builder25k", L["builder_25k"]), ("builder50k", L["builder_50k"])):
        p, f = PC.PLANS[key], FL.PLANS[key]
        want = {"buffer": lim["buffer"], "pay_min": lim["pay_min"], "pay_max": lim["pay_max"], "split": lim["split"],
                "cons": lim["cons"], "cycle_days": lim["cycle_days"], "max_payouts": lim["max_payouts"], "lock": lim["lock"],
                "mll": lim["mll"]}
        bad = {k: (p.get(k), v) for k, v in want.items() if p.get(k) != v}
        check(f"a. payout_coach.PLANS[{key}] = MFFU (buffer, min, max, 80%, 50% best day, 2 traded days, 5 payouts, lock, max loss)", not bad, bad)
        check(f"a. payout_coach.PLANS[{key}]: first payout wait 2 days = MFFU's 48 h", p.get("first_wait_days") == 2, p.get("first_wait_days"))
        want_f = dict(want, dll=lim["dll"], max_micros=lim["max_micros"])
        bad = {k: (f.get(k), v) for k, v in want_f.items() if f.get(k) != v}
        check(f"a. funded_life.PLANS[{key}] = MFFU (+ daily loss, max micros)", not bad and f.get("first_wait_h") == 48, (bad, f.get("first_wait_h")))
    check("a. owner's real prices in funded_life (Builder 50K $91.80, 25K $63)",
          FL.PLANS["builder50k"]["price"] == 91.80 and FL.PLANS["builder25k"]["price"] == 63.00)
    sf = RB["builder_50k"]["sim_funded"]
    check("a. the 50K rulebook's own sim-funded entries agree with limits (buffer, min, max, split, 5 payouts)",
          (V(sf["buffer"]), V(sf["payout_min"]), V(sf["payout_max"]), V(sf["split"]), V(sf["max_sim_payouts"]))
          == (L["builder_50k"]["buffer"], L["builder_50k"]["pay_min"], L["builder_50k"]["pay_max"], L["builder_50k"]["split"], L["builder_50k"]["max_payouts"]))
    f25 = V(RB["builder_25k"]["funded"])
    check("a. the 25K rulebook's funded entry agrees with limits (buffer, min, max, split, 50%, 5 payouts, $1,000 max loss)",
          (f25["buffer"], f25["payout_min"], f25["payout_max"], f25["split"], f25["consistency"], f25["max_sim_payouts"], f25["max_loss"]["amount"])
          == (L["builder_25k"]["buffer"], L["builder_25k"]["pay_min"], L["builder_25k"]["pay_max"], L["builder_25k"]["split"], L["builder_25k"]["cons"],
              L["builder_25k"]["max_payouts"], L["builder_25k"]["mll"]))


def part_b():
    from engine import multi_account as MA, sizing as SZ
    for key, lim in (("mffu_builder_50k", L["builder_50k"]), ("mffu_builder_25k", L["builder_25k"])):
        r = MA.PRESETS[key]["rules"]
        want = {"target": lim["target"], "mll": lim["mll"], "lock": lim["lock"], "dll": lim["dll"], "max_micros": lim["max_micros"]}
        bad = {k: (r.get(k), v) for k, v in want.items() if r.get(k) != v}
        check(f"b. multi_account.PRESETS[{key}] = MFFU (target, max loss, lock, daily loss, max micros), EOD trail",
              not bad and r.get("trail") == "eod", (bad, r.get("trail")))
        check(f"b. {key}: no news ban (Builder is news-unrestricted at MFFU) and no eval consistency",
              r.get("news_ban") is False and r.get("best_day") is None, (r.get("news_ban"), r.get("best_day")))
    t = SZ.TW_25K
    check("b. sizing.TW_25K = the 25K (target $1,500, max loss $1,000, lock $100, $600 day, 20 micros)",
          (t["target"], t["mll"], t["lock"], t["dll"], t["max_micros"]) == (1500.0, 1000.0, 100.0, 600.0, 20), t)
    g = MA.PRESETS["mffu_builder_25k"]["sizing"]["guard"]
    check("b. the 25K day guard uses MFFU's $1,500 / $600 / 20", (g["target"], g["dll"], g["max_micros"]) == (1500.0, 600.0, 20), g)
    for key, rk in (("mffu_rapid_eod_50k", "rapid_eod_50k"), ("mffu_rapid_eod_25k", "rapid_eod_25k")):
        r = MA.PRESETS[key]["rules"]
        e = V(RB[rk]["eval"])
        want = {"target": e["target"], "mll": e["mll"], "max_micros": e["max_contracts"]["micros"], "min_days": e["min_days"], "best_day": e["consistency"]}
        bad = {k: (r.get(k), v) for k, v in want.items() if r.get(k) != v}
        check(f"b. multi_account.PRESETS[{key}] = MFFU (target, max loss, max micros, 4 days, 30% day), EOD trail, news ban funded",
              not bad and r.get("trail") == "eod" and r.get("news_ban") == "funded", (bad, r.get("trail"), r.get("news_ban")))


def part_c():
    from engine import rapid as RP
    for key, rk in (("mffu_rapid_eod_50k", "rapid_eod_50k"), ("mffu_rapid_eod_25k", "rapid_eod_25k")):
        p = RP.PLANS[key]
        e, f = V(RB[rk]["eval"]), V(RB[rk]["sim_funded"])
        check(f"c. rapid.PLANS[{key}]: target, buffer = MFFU", (p["target"], p["buffer"]) == (e["target"], f["buffer"]), (p, e["target"], f["buffer"]))
        check(f"c. rapid {key}: 90% split, a day <= 30%, 4 days = MFFU",
              (RP.SPLIT, RP.BEST_DAY, RP.MIN_DAYS) == (f["split"], e["consistency"], e["min_days"]), (RP.SPLIT, RP.BEST_DAY, RP.MIN_DAYS))
    f50, f25 = V(RB["rapid_eod_50k"]["sim_funded"]), V(RB["rapid_eod_25k"]["sim_funded"])
    check("c. rapid 50K payout min = MFFU", RP.PAY_MIN == f50["payout_min"], (RP.PAY_MIN, f50["payout_min"]))
    check("c. rapid 25K: 'since the last payout' line = MFFU's 25K payout minimum",
          RP.PLANS["mffu_rapid_eod_25k"]["since"] == f25["payout_min"], (RP.PLANS["mffu_rapid_eod_25k"]["since"], f25["payout_min"]))
    d25 = V(RB["rapid_eod_25k"].get("dll_option"))
    check("c. rapid 25K: the owner's MFFU daily loss option ($500, a pause) is the one in the rulebook",
          d25 and RP.PLANS["mffu_rapid_eod_25k"].get("mffu_dll") == d25.get("amount"), (d25, RP.PLANS["mffu_rapid_eod_25k"].get("mffu_dll")))


def part_d():
    from engine import payout_coach as PC, cme_calendar as CC, multi_account as MA
    idle = L["builder_50k"]["inactivity_days"]
    check("d. inactivity: payout_coach.IDLE_DAYS and cme_calendar.IDLE_LIMIT = MFFU's 7 days",
          PC.IDLE_DAYS == idle == CC.IDLE_LIMIT == L["builder_25k"]["inactivity_days"], (PC.IDLE_DAYS, CC.IDLE_LIMIT, idle))
    day = "2026-11-18"   # a normal Wednesday
    fm = CC.flat_cut(day)
    check("d. flat: the bot is flat by 15:55 ET, at or before MFFU's 16:10 (limits flat_by_mod 970)",
          fm == 955 and fm <= L["builder_50k"]["flat_by_mod"] == L["builder_25k"]["flat_by_mod"] == 970, (fm, L["builder_50k"]["flat_by_mod"]))
    nt = V(RB["builder_50k"]["eval"]["news_trading"])
    pre_min = 2 * 60
    check("d. news: the bot's Rapid funded window (3 min before, 2.5 min after) covers MFFU's -2 / +2 min (stricter is allowed)",
          MA.NEWS_PRE_S >= pre_min and MA.NEWS_POST_S >= pre_min, (MA.NEWS_PRE_S, MA.NEWS_POST_S))
    check("d. the rulebook says Builder news is unrestricted and restricted accounts are flat -2 / +2 min",
          "unrestricted" in json.dumps(nt).lower() + json.dumps(RB["builder_50k"]["eval"]["news_trading"]).lower()
          and "2 min before to 2 min after" in RB["builder_50k"]["eval"]["news_trading"].get("note", ""))
    lim = RB["owner_questions_2026_11_20"]["parallel_evals"]["value"]
    check("d. account limits: 10 evals, Builder 50K x1 + 25K x2 funded, 5 funded in all (rulebook text)",
          "10 active" in lim and "Builder 50K max 1" in lim and "Builder 25K max 2" in lim and "max 5" in lim, lim)


def part_e():
    today = dt.date(2026, 11, 20) if os.environ.get("ACCOUNT_RULES_TODAY") is None else dt.date.fromisoformat(os.environ["ACCOUNT_RULES_TODAY"])
    old, nosrc = [], []
    for acct in ("builder_50k", "builder_25k", "rapid_eod_50k", "rapid_eod_25k"):
        def walk(o, path):
            if isinstance(o, dict) and "value" in o and ("checked" in o or "status" in o):
                c = o.get("checked")
                if not c or (today - dt.date.fromisoformat(str(c)[:10])).days > 30:
                    old.append((path, c))
                if not o.get("source"):
                    nosrc.append(path)
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    if k not in ("owner_screenshot_2026_10_26",):
                        walk(v, path + "." + k)
        walk(RB[acct], acct)
    check("e. every account rule in the rulebook was checked within 30 days", not old, old[:8])
    check("e. every account rule names its source", not nosrc, nosrc[:8])
    doc = os.path.join(ROOT, "docs", "ACCOUNT_RULES.md")
    txt = open(doc, encoding="utf-8").read() if os.path.exists(doc) else ""
    check("e. docs/ACCOUNT_RULES.md has a section per account (50K eval, 25K #2 eval, ATLAS 25K funded, 50K funded, Rapid EOD 25K, live)",
          all(h in txt for h in ("Builder 50K EVAL", "Builder 25K #2 EVAL", "ATLAS: Builder 25K SIM FUNDED", "Builder 50K SIM FUNDED",
                                  "Rapid EOD 25K", "LIVE")), None)


def main():
    for f in (part_a, part_b, part_c, part_d, part_e):
        try:
            f()
        except Exception as e:        # a missing key IS a drift: fail, never crash silently
            check(f"{f.__name__} ran", False, repr(e))
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
