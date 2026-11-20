"""K8 for a $55 account, ready by Monday (night-kalshi8 2026-11-20): the research outputs agree with the executor's rules. Offline:
it reads only the committed results (research/kalshi_k8_monday/*.json) and pure functions; no network, no key, no order.

  a. sizing    size55.json = engine/kalshi_clock.bankroll_rule(55); the week stop holds in every simulated world (never a week
               worse than -25%); $15 a bet cannot even place one bet under the $55 week stop; the edge-holds world is positive
  b. edge      84 variants, the Bonferroni bar for 84, nothing passed (so nothing new is live or paper); +10 s and +40 s were dearer
  c. dry run   the executor on the real Nov 16-19 windows: right side, size within $2.50, Kalshi's result, the exact fee and $
  d. maths     the tape walk + verify.py's fee (4 contracts at 52c = 7c, 1 contract = 2c)
  e. records   TESTED_AND_REJECTED has the K8 Monday entry; the write-up exists with the owner's Monday steps and :8444

  python -X utf8 -m tests.test_kalshi_k8_monday
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "kalshi_k8_monday"))

from engine import kalshi_clock as KC  # noqa: E402

HERE = os.path.join(ROOT, "research", "kalshi_k8_monday")
RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    import k8m_data as D
    sz, ed, dr = rd("size55.json"), rd("edge.json"), rd("dryrun.json")
    rule = sz["rules"]["$2.50 a bet (the rule)"]
    want = KC.bankroll_rule(55)
    check("a1. the simulated rule is the executor's bankroll rule for $55 ($2.50, 3 a day, -$8, -$13.75 a week, OFF at -$19.25)",
          all(rule["rule"][k] == want[k] for k in ("stake_usd", "max_bets_per_day", "daily_loss_stop_usd", "week_loss_stop_usd", "kill_drawdown_usd")),
          (rule["rule"], want))
    W = rule["worlds"]
    check("a2. in every world (as tested / half the edge / edge gone) no simulated week is worse than -25% of $55 ($13.75)",
          all(w["p_week_worse_than_25pct"] == 0 and w["worst_week_usd"] >= -13.75 - 1e-6 for w in W.values()), W)
    check("a3. as tested: positive a week and under 5% chance of being down after 4 weeks; half the edge: still positive on average",
          W["tested"]["usd_week_mean"] > 5 and W["tested"]["p_down_4w"] < 0.05 and W["half"]["usd_week_mean"] > 0, W["tested"])
    big = sz["rules"]["$15 a bet (old)"]["worlds"]["tested"]
    check("a4. $15 a bet with $55: one bet alone could pass the week stop, so not one bet goes in", big["bets_4w_mean"] == 0, big)
    check("a5. Kelly: full Kelly at the planning win rate (in-sample - 10 points) about 20%; a quarter is about 5%; the rule bets 4.5%",
          0.15 < sz["kelly"]["full_kelly_plan"] < 0.25 and abs(sz["kelly"]["quarter_kelly_plan"] - 0.05) < 0.01 and KC.BANKROLL["bet_share"] == 0.045,
          sz["kelly"])
    check("b1. the edge tests: 84 variants, the one-sided Bonferroni bar for 84 (about 3.24), nothing passed",
          ed["variants"] == 84 and abs(ed["bar_t"] - float(D.V.bar_t(84))) < 1e-3 and ed["passed"] == [] and len(ed["results"]) == 84,
          (ed["variants"], ed["bar_t"], ed["passed"]))
    tm = {r["what"][:6]: r for r in ed["results"] if r["kind"] == "timing"}
    check("b2. timing: +10 s and +40 s both paid more than +20 s in the find weeks (today's +20 s stays)",
          tm["+10 s "]["find"]["cheaper_c"] < 0 and tm["+40 s "]["find"]["cheaper_c"] < 0 and tm["+40 s "]["find"]["fill_rate"] < 0.9, tm)
    for mode, n in (("paper", 20), ("live", 12)):
        c = dr["checks"][mode]
        check(f"c. dry run ({mode}, Nov 16-19 real windows): {n} bets, right side, within $2.50, Kalshi's result, exact fee and $",
              c["rows"] == n and c["settled"] == n and c["right_side"] and c["settled_right"] and c["pnl_right"] and c["fee_right"] and c["size_ok"]
              and c["armed"] == (mode == "live"), c)
    o = dr["checks"]["live"]["orders"]
    check("c3. the live orders: DOWN = sell YES (side ask), UP = buy YES (side bid), whole contracts, expiring 40 s after the open",
          o and all(x["side"] in ("ask", "bid") and int(x["count"]) >= 1 for x in o)
          and all((x["side"] == "ask") == ("0530" in x["ticker"]) for x in o), o[:3])
    tr = [[19.0, "no", 0.40, 50], [20.4, "no", 0.48, 2], [21.0, "no", 0.47, 3], [22.0, "yes", 0.50, 9], [23.0, "no", 0.49, 10]]
    n, px, first = D.walk_from(tr, "no", 20.0, 2.5)
    check("d1. the +20 s walk: NO bought at 1 - YES price, from 20 s on, whole contracts within $2.50 (2 at 52c + 2 at 53c)",
          (n, px, first) == (4, 0.525, 0.52), (n, px, first))
    check("d2. verify.py's exact fee: 4 at 52c = $0.07, 1 at 52c = $0.02, 5 at 50c = $0.09", (D.fee(0.52, 4), D.fee(0.52, 1), D.fee(0.50, 5)) == (0.07, 0.02, 0.09))
    tr_ = open(os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md"), encoding="utf-8").read()
    check("e1. docs/TESTED_AND_REJECTED.md has the K8 Monday entry (timing, caps, filters, streaks, rolls)",
          "K8 better edge" in tr_ and "kalshi-k8-monday-2026-11-20.md" in tr_)
    wu = open(os.path.join(ROOT, "research", "writeups", "kalshi-k8-monday-2026-11-20.md"), encoding="utf-8").read()
    check("e2. the write-up: the $55 rule, the owner's Monday steps on :8444, the Thanksgiving calendar, never the key in chat",
          ":8444/kalshi-live/" in wu and "I ACCEPT KALSHI LIVE RISK" in wu and "Thanksgiving" in wu and "$2.50" in wu and "$13.75" in wu)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
