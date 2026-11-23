"""TRADING HOME (owner 2026-11-22): the one-menu PC launcher (engine/trade_home.py, TRADE_HOME.bat, scripts/trade_home.ps1),
the add-account plan list with real prices, and the phone page nq/trading_home.html at 390x844.

    python -X utf8 -m tests.test_trading_home          # ~15 s (the browser part is skipped, said loudly, with no Chromium)

Fakes only: no real .bat runs, no bot, no NinjaTrader. Nothing here arms or trades.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:500]))


PHRASES = ("I ACCEPT LIVE RISK", "KEEP ALIVE ON")


class Fake:
    """Scripted input + a recording runner: what the menu typed / ran."""
    def __init__(self, answers):
        self.answers, self.out, self.ran, self.prompts = list(answers), [], [], []

    def ask(self, prompt=""):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def say(self, *a):
        self.out.append(" ".join(str(x) for x in a))

    def run(self, argv):
        self.ran.append(list(argv))
        return 0


def logic():
    from engine import trade_home as T, account_cli as AC
    fx_run = {"bot": lambda: {"running": True, "last_poll": 1000, "trades_today": 1}, "keepalive": lambda: {"a": True},
              "alerts": lambda: (True, False, True)}
    fx_down = {"bot": lambda: None, "keepalive": lambda: {}, "alerts": lambda: (False, False, False)}

    # status: one plain screen, one verdict line
    rows = [{"name": "SIM-ZLARIOR-0001", "plan": "Builder 50K", "stage": "eval", "armed": True},
            {"name": "SIM-ATLAS-0002", "plan": "Builder 25K", "stage": "funded", "armed": False}]
    L, P = T.status_screen(now=1060, bot={"running": True, "last_poll": 1000, "trades_today": 1}, accounts=rows,
                           keepalive={"x": True}, alerts=(True, False, True))
    txt = "\n".join(L)
    check("a. status screen: bot yes, ARMED vs HELD per account, keep-alive, alerts, last trade, one verdict line",
          "RUNNING" in txt and "ARMED" in txt and "HELD" in txt and "Keep-alive: ON" in txt and "Telegram (bus on)" in txt
          and "1 trade(s) today" in txt and L[-1].startswith("  [FIX]") and P[0][0] == "2" and "...0001" in txt and "SIM-ZLARIOR-0001" not in txt, txt)
    L2, P2 = T.status_screen(now=1060, bot={"running": True, "last_poll": 1000, "trades_today": 0},
                             accounts=[dict(rows[0])], keepalive={"x": True}, alerts=(True, True, True))
    check("a2. all green -> '[OK] Everything is green.'", L2[-1].strip() == "[OK] Everything is green." and not P2, L2)
    L3, P3 = T.status_screen(now=1, bot=None, accounts=[], keepalive={}, alerts=(False, False, False))
    check("a3. everything down -> each problem names its menu number (7, 4, 3, 5)", [p[0] for p in P3] == ["7", "4", "3", "5"], P3)

    # menu: each number calls the existing .bat, never a phrase; one result line; back to the menu
    f = Fake(["2", "3", "6", "7", "0"])
    rc = T.menu(ask=f.ask, out=f.say, run=f.run, fx=fx_run)
    bats = [os.path.basename(a[-1]) for a in f.ran]
    check("b. menu 2/3/6/7 run START_BOT / KEEPALIVE_ON / STOP_BOT / UPDATE .bat in order, then 0 leaves",
          rc == 0 and bats == ["START_BOT.bat", "KEEPALIVE_ON.bat", "STOP_BOT.bat", "UPDATE.bat"] and all(a[0] == "cmd" for a in f.ran), f.ran)
    res = [l for l in f.out if l.strip().startswith(("[OK]", "[FIX]"))]
    check("b2. exactly ONE [OK]/[FIX] result line per step", len(res) == 4, res)
    f2 = Fake(["2", "0"])
    T.menu(ask=f2.ask, out=f2.say, run=f2.run, fx=fx_down)
    check("b3. Start bot with the bot still down -> a [FIX] telling him to type the phrase himself",
          any("[FIX]" in l and "type it yourself" in l for l in f2.out), f2.out)
    f3 = Fake(["9", "0"])
    T.menu(ask=f3.ask, out=f3.say, run=f3.run, fx=fx_run)
    check("b4. a wrong number -> [FIX] and the menu again", any("[FIX] Type a number" in l for l in f3.out) and not f3.ran, f3.out)

    # the hard rule: no phrase is ever typed, stored, passed or defaulted
    src = open(os.path.join(ROOT, "engine", "trade_home.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    tail = code.split('MENU = (')[0]
    check("c. no live phrase is in the code as a value, no stdin / input= / do_start / arm( call",
          not any(p in tail.replace('"I ACCEPT LIVE RISK"', "X") for p in ("input=", "stdin=", "do_start", ".arm(", "rearm", "LIVE_PHRASE"))
          and 'input="' not in src and "typed_phrase" not in src, "")
    allrun = f.ran + f2.ran
    check("c2. what the menu ran contains no phrase and passes no stdin (list of argv only)",
          not any(p in " ".join(a) for a in allrun for p in PHRASES), allrun)
    check("c3. run_cmd hands the console through (no stdin / stdout capture)", "stdin" not in src.split("def run_cmd")[1].split("def run_bat")[0].replace("Never passes stdin", ""), "")

    # routine: status, start, keep-alive, alert test, IN ORDER, a pause before each
    f4 = Fake(["", "", "", ""])
    T.do_choice("8", ask=f4.ask, out=f4.say, run=f4.run, fx=fx_run)
    names = [os.path.basename(a[-1]) for a in f4.ran]
    check("d. routine = status, START_BOT, KEEPALIVE_ON, TEST_ALERT in that order, 4 pauses", names == ["START_BOT.bat", "KEEPALIVE_ON.bat", "TEST_ALERT.bat"]
          and len(f4.prompts) == 4 and "Status" in f4.prompts[0] and "Start bot" in f4.prompts[1] and "Keep-alive" in f4.prompts[2] and "Alert" in f4.prompts[3], (names, f4.prompts))
    f5 = Fake(["", "s", "q"])
    r5 = T.do_choice("8", ask=f5.ask, out=f5.say, run=f5.run, fx=fx_run)
    check("d2. S skips a step, Q stops the routine and says what was done", f5.ran == [] and "Routine stopped" in r5 and "Status" in r5, (f5.ran, r5))

    # alerts submenu
    f6 = Fake(["2"])
    r6 = T.do_choice("5", ask=f6.ask, out=f6.say, run=f6.run, fx=fx_run)
    f7 = Fake(["1"])
    T.do_choice("5", ask=f7.ask, out=f7.say, run=f7.run, fx=fx_run)
    check("e. alerts: 2 = TEST_ALERT.bat, 1 = ALERTS_SETUP.bat", os.path.basename(f6.ran[0][-1]) == "TEST_ALERT.bat" and r6.startswith("[OK]")
          and os.path.basename(f7.ran[0][-1]) == "ALERTS_SETUP.bat", (f6.ran, f7.ran))

    # add an account: prices, one confirm, HELD
    by = {p["key"]: p for p in T.PLAN_MENU}
    check("f. plan list has the owner's real prices: Builder 50K $91.80, 25K $63 / $43, Rapid 25K $97.20 CLUB",
          by["builder50k"]["price"] == "$91.80" and by["builder25k"]["price"].startswith("$63") and "$43" in by["builder25k"]["price"]
          and by["rapideod25"]["price"].startswith("$97.20") and by["rapideod"]["price"].startswith("$165"), by)
    check("f2. each price matches engine/account_cli's own CLUB price text (no drift)",
          all(AC.PLANS[k]["price"].split(" ")[0].rstrip(",") in by[k]["price"] for k in T.ENGINE_PLANS if k != "builder25k")
          and AC.PLANS["builder25k"]["price"].startswith("$63") and "FundedNext" in by["fundednext"]["label"] and by["fundednext"]["price"] == "OFF"
          and by["lucidpro50k"]["price"] == "OFF" and by["fundednext"].get("off") and by["lucidpro50k"].get("off"), by)
    added = []
    f8 = Fake(["3", "1", "y"])
    ok, line = T.add_flow(ask=f8.ask, out=f8.say, run=f8.run, unseen={"RAPID-TEST-1234": 25000.0}, add_fn=lambda k, n: added.append((k, n)) or {"ok": True, "say": "[OK] Rapid added"})
    check("g. add: pick 3 (Rapid 25K), tap the NinjaTrader Name by number, ONE Y -> added HELD + the exact next sentence",
          ok and added == [("rapideod25", "RAPID-TEST-1234")] and "HELD" in line and "choose 2 (Start bot)" in line and "type the live phrase yourself" in line
          and any("NOT armed" in l for l in f8.out) and any("$97.20" in l for l in f8.out) and sum("Type Y" in p for p in f8.prompts) == 1, (ok, line, added, f8.out))
    f9 = Fake(["3", "", "y"])
    ok9, l9 = T.add_flow(ask=f9.ask, out=f9.say, run=f9.run, unseen={}, add_fn=lambda k, n: added.append((k, n)) or {"ok": True})
    check("g2. an empty Name adds nothing", not ok9 and "Nothing added" in l9 and len(added) == 1, (ok9, l9))
    f10 = Fake(["1", "SOME-NAME-5678", "n"])
    ok10, l10 = T.add_flow(ask=f10.ask, out=f10.say, run=f10.run, unseen={}, add_fn=lambda k, n: added.append((k, n)) or {"ok": True})
    check("g3. anything but Y cancels, nothing added", not ok10 and "Cancelled" in l10 and len(added) == 1, l10)
    for n, w in (("6", "FundedNext"), ("7", "Lucid")):
        fo = Fake([n])
        oko, lo = T.add_flow(ask=fo.ask, out=fo.say, run=fo.run, unseen={}, add_fn=lambda k, nn: added.append((k, nn)) or {"ok": True})
        check(f"g4. {w} is OFF: names the written-yes step, adds nothing", not oko and "OFF" in lo and "written yes" in lo.lower() and len(added) == 1, lo)
    fr = Fake(["2", "B25-NAME-9999", "y"])
    ok11, l11 = T.add_flow(ask=fr.ask, out=fr.say, run=fr.run, unseen={})
    check("g5. no add_fn: runs `engine.accounts add --plan builder25k --name ...` (the same code as ADD_ACCOUNT.bat), nothing else",
          ok11 and fr.ran[0][-6:] == ["engine.accounts", "add", "--plan", "builder25k", "--name", "B25-NAME-9999"] and len(fr.ran) == 1, fr.ran)
    fa = Fake(["5", "ATLAS-FUND-1", "y"])
    T.add_flow(ask=fa.ask, out=fa.say, run=fa.run, unseen={}, today="2026-11-22")
    check("g6. ATLAS funded 25K = engine.lit25 --funded NAME --start DATE (as ADD_ACCOUNT.bat option 4)",
          fa.ran and fa.ran[0][-6:] == ["engine.lit25", "--funded", "ATLAS-FUND-1", "--start", "2026-11-22"][-6:] if False else fa.ran[0][-5:] == ["engine.lit25", "--funded", "ATLAS-FUND-1", "--start", "2026-11-22"], fa.ran)


def files():
    for rel in ("TRADE_HOME.bat", "scripts/trade_home.ps1"):
        raw = open(os.path.join(ROOT, rel), "rb").read()
        check(f"h. {rel}: ASCII only, CRLF everywhere, no bare LF",
              all(b < 128 for b in raw) and raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r") == raw.count(b"\r\n"), rel)
    ps = open(os.path.join(ROOT, "scripts", "trade_home.ps1"), encoding="ascii").read()
    bat = open(os.path.join(ROOT, "TRADE_HOME.bat"), encoding="ascii").read()
    check("h2. PowerShell 5.1 safe: no ?? / ?. / ternary / && / ForEach-Object -Parallel / pwsh-only syntax",
          not re.search(r"\?\?|\?\.|\s\?\s.+\s:\s|&&|\|\||-Parallel|ConvertFrom-Json -AsHashtable", ps), ps)
    check("h3. the .bat calls the ps1 and the ps1 opens engine.trade_home; neither holds a phrase",
          "scripts\\trade_home.ps1" in bat and "engine.trade_home" in ps and not any(p in ps + bat for p in PHRASES), "")
    check("h4. TRADE_HOME.bat and START/KEEPALIVE/STOP/UPDATE/TEST_ALERT/ALERTS_SETUP exist",
          all(os.path.isfile(os.path.join(ROOT, b)) for b in ("TRADE_HOME.bat", "START_BOT.bat", "KEEPALIVE_ON.bat", "STOP_BOT.bat", "UPDATE.bat", "TEST_ALERT.bat", "ALERTS_SETUP.bat", "ADD_ACCOUNT.bat")), "")
    ab = open(os.path.join(ROOT, "ADD_ACCOUNT.bat"), encoding="ascii").read()
    check("h5. ADD_ACCOUNT.bat lists the real prices, names FundedNext / Lucid as OFF, ends 'Added HELD'",
          "$91.80" in ab and "$63" in ab and "$97.20" in ab and "OFF" in ab and "Added HELD" in ab, "")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "win_paths.py")], capture_output=True, text=True, cwd=ROOT)
    check("h6. tools/win_paths.py: all fine", r.returncode == 0, r.stdout[-200:])


NODE_JS = r"""
const T = require(process.argv[1]), F = require(process.argv[2]);
const now = 1000000, fresh = now - 120;
const acc = (id, name, badge, ev, kind, run) => ({ id, name, badge, source: 'pc', kind: kind || 'eval', eval: ev || {}, conn: { running: run !== false } });
const good = { t: fresh, board: { running: true }, accounts: [acc('z', 'MFFU 50K Eval', 'LIVE', { to_target: 3807 }), acc('rp', 'Rapid EOD 25K', 'LIVE', { to_target: 1500 })],
  k7: { a: [{ id: 'z', nm: 'Zlarior', on: true }, { id: 'rp', nm: 'Rapid', on: true }] } };
const out = {};
out.good = T.today(good, { now, alertsOkAt: now - 86400, mffuView: F.mffuView });
const bad = { t: fresh, board: { running: false }, accounts: [acc('z', 'MFFU 50K Eval', 'LIVE', { to_target: 3807 }, 'eval', false), acc('rp', 'Rapid EOD 25K', 'Sim', { to_target: 1500 }, 'eval', false)],
  k7: { a: [{ id: 'z', nm: 'Zlarior', on: true }, { id: 'rp', nm: 'Rapid', on: false }] } };
out.bad = T.today(bad, { now, mffuView: F.mffuView });
out.silent = T.today({ ...good, t: now - 7200 }, { now, alertsOkAt: now, mffuView: F.mffuView });
out.none = T.today(null, { now });
const fund = { t: fresh, board: { running: true }, accounts: [acc('atlas', 'ATLAS 25K', 'LIVE', { balance: 401, room: 700 }, 'funded')], k7: { a: [] } };
out.funded = T.today(fund, { now, alertsOkAt: now, mffuView: F.mffuView });
out.rdok = T.today({ ...good, rd: { s: 'ok', w: '02:00' } }, { now, alertsOkAt: now - 86400, mffuView: F.mffuView });
out.rdno = T.today({ ...good, rd: { s: 'no', w: '02:00', b: 'PC clock 25 s behind', f: 'On the PC: Sync now.' } }, { now, alertsOkAt: now - 86400, mffuView: F.mffuView });
out.rdold = T.today({ ...good, t: now - 7200, rd: { s: 'ok', w: '02:00' } }, { now, alertsOkAt: now, mffuView: F.mffuView });
console.log(JSON.stringify(out));
"""


def core():
    p = subprocess.run(["node", "-e", NODE_JS, os.path.join(ROOT, "tools/web_public/nq/trading_home_core.js"), os.path.join(ROOT, "tools/web_public/pc_feed.js")],
                       capture_output=True, text=True)
    if p.returncode:
        check("i. core runs under node", False, p.stderr[-400:])
        return
    o = json.loads(p.stdout)
    by = lambda r: {l["id"]: l for l in r["lines"]}
    g, b, s, n, f = by(o["good"]), by(o["bad"]), by(o["silent"]), by(o["none"]), by(o["funded"])
    check("i. all good -> 5 lines, 0 to do, the next step is in $ (Rapid 25K +$1,500 is the closest)",
          o["good"]["left"] == 0 and [l["id"] for l in o["good"]["lines"]] == ["bot", "keepalive", "alerts", "armed", "next"] and "$1,500" in g["next"]["say"], o["good"])
    check("i2. unchecked lines say what to do and WHICH menu number: bot 2 (bot off), keep-alive 3, alerts 5, armed 2",
          not b["bot"]["ok"] and b["bot"]["menu"] == 2 and b["keepalive"]["ok"] is False and b["keepalive"]["menu"] == 3 and "Rapid" in b["keepalive"]["say"]
          and b["alerts"]["menu"] == 5 and b["armed"]["ok"] is False and "Rapid EOD 25K" in b["armed"]["say"] and b["armed"]["menu"] == 2 and "TRADE_HOME" in b["bot"]["say"], b)
    check("i3. a silent PC (2 h) -> bot unchecked with the age; armed 'cannot tell'", s["bot"]["ok"] is False and "silent" in s["bot"]["say"] and "2.0 h" in s["bot"]["say"] and s["armed"]["ok"] is None, s)
    check("i4. no report at all -> nothing is shown as done (bot / armed / keep-alive), every unchecked line names a menu number",
          not n["bot"]["ok"] and n["armed"]["ok"] is not True and n["keepalive"]["ok"] is None and all(l["ok"] is True or l["menu"] for l in o["none"]["lines"]), n)
    check("i5. funded ATLAS: the next step is the payout in $ ('$1,000 payout')", "$1,000 payout" in f["next"]["say"] and "ATLAS" in f["next"]["say"], f["next"])
    ro, rn, rs = by(o["rdok"]), by(o["rdno"]), by(o["rdold"])
    check("i7. ready check from the PC: READY = mint, done, first line; no 'rd' (older PC) = no extra line",
          o["rdok"]["lines"][0]["id"] == "ready" and ro["ready"]["ok"] is True and ro["ready"]["tone"] == "mint" and "READY for 02:00" in ro["ready"]["say"]
          and o["rdok"]["left"] == 0 and "ready" not in g, ro.get("ready"))
    check("i8. NOT READY = gold, not done, says the first blocker and its fix, counts as 1 to do; a 2 h old post shows no ready line",
          rn["ready"]["ok"] is False and rn["ready"]["tone"] == "gold" and "NOT READY for 02:00: PC clock 25 s behind" in rn["ready"]["say"]
          and "Sync now" in rn["ready"]["say"] and o["rdno"]["left"] == 1 and "ready" not in rs, rn.get("ready"))
    check("i6. alerts are only ever 'done' by his own tick (the public post cannot show it)", g["alerts"]["ok"] and not b["alerts"]["ok"] and b["alerts"]["tick"], "")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def page():
    chk = os.path.join(ROOT, "tests", "trading_home_page_check.js")
    p = subprocess.run(["node", chk, os.path.join(ROOT, "tools", "web_public")], capture_output=True, text=True,
                       env={**os.environ, "NODE_PATH": "/opt/node22/lib/node_modules"})
    if p.returncode and not p.stdout.strip():
        check("j. phone page check ran (node + playwright)", False, p.stderr[-400:])
        return
    for line in p.stdout.splitlines():
        if line.startswith(("PASS ", "FAIL ")):
            check(line[5:], line.startswith("PASS "), line)


def main() -> int:
    logic()
    files()
    core()
    page()
    ok = sum(RESULTS)
    print(f"\n{ok}/{len(RESULTS)} passed")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
