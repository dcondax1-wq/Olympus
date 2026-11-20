"""PAYOUT READINESS (nqdash3 round 2, tools/web_public/nq/payready.js on board/ and trading/): per funded account, eligible yes / no with the exact
MFFU reason (business/payoutcoach.js rules), "$X more / N more days until you can ask for $Y", the projected date at the bot's recent pace, the
MFFU steps. Node only, ~1 s.
    python -X utf8 -m tests.test_payready
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:1200]}"))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


HARNESS = r"""
const coach = require(process.argv[3]);
import(process.argv[2]).then((M) => {
  const today = '2026-11-20';     // Friday
  const biz = { accounts: [{ key: 'atlas', pc: ['atlas', 'acct_b'], name: 'ATLAS', plan: 'MFFU Builder 25K (funded)', stage: 'funded' },
    { key: 'zlarior', pc: ['mffu50k_eval'], plan: 'MFFU Builder 50K', stage: 'eval' }, { key: 'rapid1', pc: ['rapid'], plan: 'MFFU Rapid EOD 25K', stage: 'funded' },
    { key: 'blitz', pc: ['blitz'], stage: 'funded' }] };
  const lite = (bal, f, eq, extra) => ({ board: { atlas: { status: 'funded', balance: bal, room: 887, mll: 1000, plan: 'MFFU Builder 25K funded' } },
    mf: { a: [{ id: 'atlas', nm: 'ATLAS 25K funded', l4: '6018', lt: '2026-11-19', eq, ...(f ? { f } : {}) }, { id: 'mffu50k_eval', nm: 'Zlarior 50K', eq: [1, 2] }] }, ...(extra || {}) });
  const o = {};
  // 1. today: ATLAS funded since Nov 17, balance $24,887 (-$113), no traded day in its cycle yet
  const A = M.model(lite(24887, { cp: -113, bd: 0, cd: 1, ef: '2026-11-21', pn: 0, mr: 0, st: 'building', ft: '2026-11-19' }, [0, -60, -113]), null, biz, coach, today);
  o.now = A.map((a) => [a.id, a.verdict, a.reason, a.need && a.need.text, a.need && a.need.usd, a.need && a.need.days, a.proj && a.proj.text, a.checks.map((c) => [c.k, c.ok, c.text]), a.steps.length]);
  // 2. ready: $27,250, cycle +$2,250, best day $600, 5 days, first trade long ago
  o.ready = M.model(lite(27250, { cp: 2250, bd: 600, cd: 5, ef: '2026-11-21', pn: 0, mr: 1000, ft: '2026-11-03' }, [400, 900, 1500, 2250]), null, biz, coach, today)[0];
  // 3. allowed but smaller: $26,500 (+$400 above the buffer), consistency fine -> MFFU pays $400, the plan waits for $1,000; pace +$200 a day
  o.allowed = M.model(lite(26500, { cp: 1500, bd: 500, cd: 4, pn: 0, mr: 400, ft: '2026-11-03' }, [700, 900, 1100, 1300, 1500]), null, biz, coach, today)[0];
  // 4. consistency broken: best day $1,400 of a $2,300 cycle (61%)
  o.cons = M.model(lite(27300, { cp: 2300, bd: 1400, cd: 3, pn: 0, ft: '2026-11-03' }, [1400, 1800, 2300]), null, biz, coach, today)[0];
  // 5. no tracker block yet: says what is missing, never invents
  o.wait = M.model(lite(25000, null, [0, 0]), null, biz, coach, today)[0];
  o.ids = A.map((a) => a.id);
  // TODAY (2026-11-20 10:20 ET, the PC's post): ATLAS won +$514.18 -> $25,401.38, room $1,401.38; cycle +$401, best day $514, 2 days
  o.today = M.model(lite(25401.38, { cp: 401, bd: 514, cd: 2, ef: '2026-11-20', pn: 0, mr: 0, st: 'consistency' }, [0, -113, 401]), null, biz, coach, today)[0];
  o.pace = [M.pace([0, 100, 300]), M.pace([1, 2]), M.pace(null)];
  o.td = [M.addTradingDays('2026-11-20', 1), M.addTradingDays('2026-11-20', 6)];
  o.junk = [null, undefined, 5, 'x', {}, { mf: { a: [null, 4, { id: 'atlas', f: 'x' }] }, board: 7 }].map((j) => { try { return M.model(j, j, j, coach, today).length; } catch (e) { return 'THROW ' + e.message; } });
  o.nocoach = M.model(lite(27250, { cp: 2250, bd: 600, cd: 5 }, [1, 2, 3]), null, biz, null, today)[0].verdict;
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_static():
    js, css = read(os.path.join(WEB, "nq", "payready.js")), read(os.path.join(WEB, "nq", "payready.css"))
    check("a. text only, no fetch / storage / innerHTML; never asks MFFU for anything (it only shows the steps)",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|fetch\(|localStorage|sessionStorage|XMLHttpRequest|sendBeacon", js))
    cols = re.findall(r"#[0-9a-fA-F]{3,8}\b", re.sub(r"var\(--[a-z0-9-]+,\s*#[0-9a-fA-F]{3,8}\)", "", css))
    check("a. tokens only (hex only as a var() fallback); reduced motion stops it", not cols and "prefers-reduced-motion: reduce" in css, cols)
    b, t = read(os.path.join(WEB, "board", "index.html")), read(os.path.join(WEB, "trading", "index.html"))
    check("a. Board and Trading both have the payout readiness card and load payready.css + the coach",
          'id="payReady"' in b and 'id="payReady"' in t and "payready.css?v=" in b and "payready.css?v=" in t and "payoutcoach.js" in b and "payoutcoach.js" in t)


def test_core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    tmp = tempfile.mkdtemp(prefix="payready-")
    try:
        m = os.path.join(tmp, "payready.mjs")
        shutil.copy(os.path.join(WEB, "nq", "payready.js"), m)
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, m, os.path.join(WEB, "business", "payoutcoach.js")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("the node harness runs", False, r.stderr[-800:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. funded accounts only: ATLAS (PC tracker) and the Rapid (plan says funded); the 50K eval and BLITZ never", o["ids"] == ["atlas", "rapid"], o["ids"])
    a = o["now"][0]
    chk = {c[0]: c for c in a[7]}
    check("b. ATLAS today ($24,887, -$113): Not yet, reason = the first-request date (first trade Thu 19 Nov + 2 days = Sat -> the next weekday, Mon 23 Nov)",
          a[1] == "Not yet" and a[2].startswith("First request from 2026-11-23") and chk["first"][1] is False and "Mon, Nov 23" in chk["first"][2], a)
    check("b. ... '$1,463 more / 1 more traded day until MFFU allows a payout' (= the coach's need_more, the same 'to payout' every page shows); every rule row has its number",
          a[3] == "$1,463 more / 1 more traded day until MFFU allows a payout" and a[4] == 1463 and a[5] == 1
          and chk["days"][2] == "1 (2 needed)" and chk["profit"][2] == "-$113" and chk["buffer"][2].startswith("$0 (minimum request $250)") and chk["max"][2] == "$0", a)
    check("b. ... losing pace: the projection says so instead of a date; the 5 MFFU steps are there", a[6].startswith("not at the recent pace: -$56 a day") and a[8] == 5, a[6])
    r = o["ready"]
    check("b. PAYOUT READY at $27,250: request $1,000 today, $800 to you, $560 after the tax pot; every rule ticked; projected today; the PC's max shown",
          r["verdict"] == "PAYOUT READY" and r["reason"] == "Request $1,000 today: $800 to you (80%), $560 after the 30% tax pot." and all(c["ok"] for c in r["checks"])
          and r["proj"]["text"] == "today" and r["need"]["text"] == "Ready to ask for $1,000" and "(the PC says $1,000)" in r["checks"][5]["text"]
          and "ending 6018" in r["steps"][1], r)
    w = o["allowed"]
    check("b. allowed but smaller at $26,500: MFFU would pay $400, the plan waits for $1,000 ($600 more); at +$200 a day -> 3 trading days -> Wed, Nov 25",
          w["verdict"] == "Allowed (smaller)" and "MFFU would pay $400 today" in w["reason"] and w["need"]["usd"] == 600
          and w["proj"]["date"] == "2026-11-25" and "3 trading days at $200 a day" in w["proj"]["text"], (w["verdict"], w["reason"], w["need"], w["proj"]))
    c = o["cons"]
    cc = {x["k"]: x for x in c["checks"]}
    check("b. consistency broken (best day $1,400 of $2,300 = 60.9%): Not yet, '$500 more on other days', the cons row red",
          c["verdict"] == "Not yet" and cc["cons"]["ok"] is False and "60.9%" in cc["cons"]["text"] and "$500 more on other days" in cc["cons"]["text"]
          and c["need"]["usd"] == 500, (c["verdict"], cc["cons"], c["need"]))
    check("b. no tracker block from the PC: 'Waiting for the PC', names what is missing, no numbers made up",
          o["wait"]["verdict"] == "Waiting for the PC" and "funded tracker (mf.f)" in o["wait"]["reason"] and o["wait"]["has"] is False, o["wait"])
    t = o["today"]
    check("b. TODAY's ATLAS (+$514 -> $25,401.38): 'Not yet', '$949 more until MFFU allows a payout' (balance $26,350 = the same 'To payout $949' the "
          "accounts strip and the ZEUS card show), the 50% rule red (best day $514 > half of the cycle's $401), the plan's $1,000 ask at $27,100 ($1,699 more)",
          t["verdict"] == "Not yet" and t["need"]["text"] == "$949 more until MFFU allows a payout" and t["need"]["okBal"] == 26350
          and next(x for x in t["checks"] if x["k"] == "cons")["ok"] is False and "$1,699 more" in t["need"]["planText"] and "$27,100" in t["need"]["planText"], (t["need"], t["checks"]))
    check("b. the Rapid: says its payout rules are not coded yet (no guess)", o["now"][1][1] == "Not coded yet", o["now"][1])
    check("b. the bot's own ping ($750 above the buffer) and the open card payout-ping-1000 are named", "payout-ping-1000" in r["ping"] and "$750" in r["ping"], r["ping"])
    check("b. pace and trading days", o["pace"] == [{"per": 150, "days": 2}, None, None] and o["td"] == ["2026-11-23", "2026-11-30"], (o["pace"], o["td"]))
    check("c. junk never throws; no coach -> says so", all(isinstance(j, int) for j in o["junk"]) and o["nocoach"] == "No coach", (o["junk"], o["nocoach"]))


if __name__ == "__main__":
    test_static()
    test_core()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
