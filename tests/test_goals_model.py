"""ONE goals model (tools/web_public/nq/goals_model.js, night-nq-main 2026-11-27): to pass / to payout by the owner rule (docs/ACCOUNT_RULES.md).
Node only, ~0.2 s.
  a. evals: the plan target above the start (50K +$3,000, 25K +$1,500, Rapid +$1,500); below the start says so
  b. funded: MFFU's from-$0 view whether the balance is $401 or $25,401; Builder 25K goal $1,000 at $2,100 ($800 to you, 80%), earliest $250 at
     $1,350; Builder 50K $2,000 at $4,100; Rapid: no max, keeps $500: $500 at $2,100, 90% = $450; ready when there
  c. no numbers = kind 'none', never a made-up goal; junk never throws; the model names no date
  d. the rule numbers match research/lit/mffu_rules.json where it states them
    python -X utf8 -m tests.test_goals_model
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "tools", "web_public", "nq", "goals_model.js")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:600]}"))


JS = r"""
import(process.argv[2]).then((G) => {
  const o = {};
  const g = (a) => { const x = G.goal(a); return [x.plan, x.kind, x.left, x.big, x.unit, x.frac === null ? null : Math.round(x.frac * 1000) / 1000, x.ask, x.toYou, x.goalAt, x.earliestAt, x.line]; };
  o.z50 = g({ key: 'zlarior', stage: 'Eval', balance: 51500 });
  o.z50neg = g({ key: 'zlarior', name: 'Zlarior 50K', stage: 'Eval', balance: 49177.52 });
  o.z25 = g({ key: 'fresh25', name: 'Zlarior 25K #2', stage: 'Eval', balance: 26600 });
  o.at = g({ key: 'atlas', name: 'ATLAS 25K', stage: 'Funded', balance: 401.38 });
  o.atNt = g({ key: 'atlas', name: 'ATLAS 25K', plan: 'MFFU Builder 25K (funded)', stage: 'Funded', balance: 25401.38 });
  o.atReady = g({ key: 'atlas', stage: 'Funded', balance: 2150 });
  o.b50f = g({ name: 'Zlarior 50K', stage: 'Funded', balance: 1000 });
  o.rapid = g({ key: 'rapid1', name: 'Rapid EOD 25K', stage: 'Eval', balance: 24995.24 });
  o.rapidF = g({ key: 'rapid1', name: 'Rapid EOD 25K', status: 'funded', balance: 1700 });
  o.none = g({ key: 'atlas', stage: 'Funded' });
  o.junk = [null, undefined, 1, 'x', [], {}, { balance: 'NaN' }].map((j) => { try { G.goal(j); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  o.plans = G.PLANS;
  console.log(JSON.stringify(o));
});
"""


def main():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "--input-type=module", "-e", JS.replace("import(process.argv[2])", "import(process.argv[1])"), "file://" + MOD],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    check("a. Builder 50K eval at $51,500: $1,500 to pass, 50%", o["z50"][:6] == ["builder50k", "pass", 1500, "$1,500", "to pass", 0.5], o["z50"])
    check("a. ... below the start ($49,177.52): $3,822 to pass, 0%, the line says how far below the start",
          o["z50neg"][2] == 3822.48 and o["z50neg"][5] == 0 and "$822 below the start" in o["z50neg"][10], o["z50neg"])
    check("a. Builder 25K past its +$1,500: 'Target reached'", o["z25"][:4] == ["builder25k", "pass", 0, "Target reached"], o["z25"])
    check("b. ATLAS funded at MFFU $401 and NinjaTrader $25,401 read the same: $1,699 to the $2,100 goal, ask $1,000, $800 to you, earliest $1,350",
          o["at"][:10] == ["builder25k", "payout", 1698.62, "$1,699", "to $2,100", 0.191, 1000, 800, 2100, 1350] and o["atNt"][:10] == o["at"][:10], (o["at"], o["atNt"]))
    check("b. ... at $2,150: Ready", o["atReady"][3] == "Ready" and o["atReady"][2] == 0, o["atReady"])
    check("b. Builder 50K funded: ask $2,000 at $4,100 ($1,600 to you), earliest $2,600", o["b50f"][6:10] == [2000, 1600, 4100, 2600], o["b50f"])
    check("b. Rapid EOD 25K: eval +$1,500 ($1,505 to go from $24,995); funded no max: keep $500, ask $500 at $2,100, 90% = $450",
          o["rapid"][:3] == ["rapid25", "pass", 1504.76] and o["rapidF"][:9] == ["rapid25", "payout", 400, "$400", "to $2,100", 0.81, 500, 450, 2100], (o["rapid"], o["rapidF"]))
    check("c. no balance = kind 'none' with no goal number; junk never throws; no date in any line",
          o["none"][1] == "none" and o["none"][2] is None and all(j == "ok" for j in o["junk"])
          and not any(m in " ".join(str(x[10]) for x in o.values() if isinstance(x, list) and len(x) > 10) for m in ("Dec", "Jan", "Nov")), (o["none"], o["junk"]))
    P = o["plans"]
    check("d. the plan numbers = docs/ACCOUNT_RULES.md (50K +$3,000 / $2,000 MLL / $2,100 buffer / $500-$2,000 / 80%; 25K +$1,500 / $1,000 / $1,100 / $250-$1,000 / 80%; Rapid $500 min, no max, 90%)",
          (P["builder50k"]["target"], P["builder50k"]["mll"], P["builder50k"]["buffer"], P["builder50k"]["payMin"], P["builder50k"]["payMax"], P["builder50k"]["split"]) == (3000, 2000, 2100, 500, 2000, 0.8)
          and (P["builder25k"]["target"], P["builder25k"]["mll"], P["builder25k"]["buffer"], P["builder25k"]["payMin"], P["builder25k"]["payMax"], P["builder25k"]["split"]) == (1500, 1000, 1100, 250, 1000, 0.8)
          and (P["rapid25"]["payMin"], P["rapid25"]["payMax"], P["rapid25"]["split"], P["rapid25"]["buffer"]) == (500, None, 0.9, 1100), P)


if __name__ == "__main__":
    main()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
