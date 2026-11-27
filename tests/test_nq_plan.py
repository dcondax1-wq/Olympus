"""TODAY'S BATTLE PLAN + ALERT HISTORY (tools/web_public/nq/plancore.js + plan.js, night-nq-main 2026-11-27). Node only, ~0.3 s.
  a. static: plan.js is its own deferred module, plan.css loads non-blocking, plancore is pure (no DOM / fetch / lookbehind), text only
  b. plan: the real brief (Thu Nov 26, half day) read on Fri: "Plan from Thu ... not built yet", its 13:00 halt + windows, the levels ladder
     with distances from the brief's price, the VIX read, one line per bot without a stale "window open"; read on its own day: live, now marker,
     the state; a Tier-1 release -> the Rapid lanes' pause window; the PC's live glance levels win over the brief's; no brief = an honest line
  c. alerts: the PC's brd events + the published board log + trade entries / exits merged, newest first, max 20, deduped, BLITZ never,
     icons by kind (a loss exit red, a pc_silent warning)
    python -X utf8 -m tests.test_nq_plan
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, html = (read(os.path.join(NQ, n)) for n in ("plancore.js", "plan.js", "plan.css", "index.html"))
    check("a. plan.js = its own module tag after nq.js; plan.css media=print onload (never render-blocking); #battle + #alertsDrawer on the page",
          html.index('src="nq.js') < html.index('src="plan.js') and re.search(r'plan\.css\?v=\d+" media="print" onload=', html) and 'id="battle"' in html and 'id="alertsDrawer"' in html)
    check("a. plancore.js is pure and Safari-16 safe (no document / window / fetch / storage / lookbehind / .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. plan.js draws text only (no innerHTML / eval / dynamic import), reads only published files",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js) and set(re.findall(r"get\('([^']+)'\)", js)) == {"./brief.json", "./news_week.json", "../board/board.json"})


JS = r"""
import(process.argv[1]).then((P) => {
  const fs = require('fs'), B = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), o = {};
  const fri = Date.parse('2026-11-27T05:30:00Z') / 1000, thu = Date.parse('2026-11-26T15:00:00Z') / 1000;   // Fri 00:30 ET / Thu 10:00 ET
  const s = P.plan(B, null, {}, fri);
  o.stale = [s.stale, s.staleText, s.early, s.map.halt && s.map.halt.at, s.map.now, s.map.wins.length, s.levels.rows.map((r) => [r.name, Math.round(r.dist)]), s.levels.price, s.read.vix, s.bots.map((b) => [b.name, b.state])];
  const l = P.plan(B, null, {}, thu);
  o.live = [l.stale, l.map.now !== null, l.bots.map((b) => b.state)];
  const B2 = JSON.parse(JSON.stringify(B)); B2.news.today = [{ time: '08:30', event: 'CPI', tier: 1 }, { time: '10:00', event: 'Low', tier: 2 }];
  o.news = P.plan(B2, null, {}, thu).news.map((n) => [n.time, n.tier1, n.pause, n.past]);
  const home = { live: { pc: { glance: { bots: [{ id: 'lit', lv: [['Asia high', 26468.5, 184.75], ['Asia low', 26254.25, -29.5]] }] } } } };
  const g = P.plan(B, null, home, thu); o.glance = [g.levels.price, g.levels.priceSrc, g.levels.rows.map((r) => r.name)];
  o.none = P.plan(null, null, {}, fri);
  const now = Date.parse('2026-11-27T05:30:00Z') / 1000;
  const lite = { brd: { ev: [[now - 600, 'pc_silent', '', 'PC silent 30 min'], [now - 7200, 'bot_started', '', 'Bot running'], [now - 50, 'claude_note', 'blitz', 'BLITZ thing']] } };
  const board = { events: [{ t: now - 7200, kind: 'bot_started', text: 'Bot running' }, { t: now - 90000, kind: 'eval_passed', acct: 'atlas', text: 'ATLAS passed' }] };
  const hm = { board: { trades: [{ acct: 'lit', src: 'live', side: 'long', usd: -129.4, exit: 'STOP', open: false, entry_t: now - 4000, exit_t: now - 3000 },
    { acct: 'blitz', src: 'live', entry_t: now - 10 }, { acct: 'atlas', src: 'paper', entry_t: now - 20 }] } };
  const A = P.alerts(hm, lite, board, now);
  o.alerts = A.map((a) => [a.icon, a.tone, a.kind, a.text.slice(0, 60)]);
  o.many = P.alerts({ board: { trades: Array.from({ length: 30 }, (_, i) => ({ acct: 'lit', src: 'live', side: 'long', entry_t: now - i * 600 })) } }, null, null, now).length;
  o.junk = [null, 1, 'x', [], {}].map((j) => { try { P.plan(j, j, j, now); P.alerts(j, j, j, now); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "plancore.js"), os.path.join(ROOT, "tests", "fixtures", "brief", "nq_brief_2026-11-26.json")],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    st = o["stale"]
    check("b. Thu's brief read on Fri: stale, 'Plan from Thu, Nov 26 - today's (Fri, Nov 27) is not built yet', the 13:00 halt, no now marker, 6 bot windows",
          st[0] is True and st[1].startswith("Plan from Thu, Nov 26 - today's (Fri, Nov 27) is not built yet") and st[2] == "13:00" and st[3] == "13:00" and st[4] is None and st[5] == 6, st[:6])
    check("b. ... the 5 levels nearest the brief's price (PDC -127.5 pts, PDL -312 ...), the VIX read, and no stale 'window open' on a bot",
          st[6][0] == ["PWH", 2991] and ["PDC", -127] in st[6] and st[7] == 25288.25 and st[8].startswith("VIX 28.3 (elevated)") and all(b[1] == "" for b in st[9]), st[6:])
    check("b. on its own day (Thu 10:00 ET): live, the now marker, the bots' states (window open / window over)",
          o["live"][0] is False and o["live"][1] is True and "window open" in o["live"][2] and "window over" in o["live"][2], o["live"])
    check("b. a Tier-1 release at 08:30 -> 'Rapid lanes flat 08:27 to 08:32:30 ET', marked past at 10:00; a Tier-2 one has no pause",
          o["news"][0][:3] == ["08:30", True, "Rapid lanes flat 08:27 to 08:32:30 ET (MFFU Rapid bans 2 min either side; the bot keeps 3 min before / 2.5 after)"] and o["news"][0][3] is True
          and o["news"][1][2] == "", o["news"])
    check("b. the PC's live glance levels win (price from their distance: 26,283.75, 'the PC's last report')",
          o["glance"][0] == 26283.75 and o["glance"][1] == "the PC's last report" and o["glance"][2] == ["Asia high", "Asia low"], o["glance"])
    check("b. no brief: has false and an honest line", o["none"]["has"] is False and "not on the site" in o["none"]["staleText"], o["none"])
    al = o["alerts"]
    check("c. alerts merged newest first: pc_silent warning, the losing exit (red ✗ -$129), its entry, the bot start once (PC + board deduped), the old pass; BLITZ / paper never",
          [a[2] for a in al] == ["pc_silent", "exit", "entry", "bot_started", "eval_passed"] and al[1][:2] == ["✗", "down"] and "-$129" in al[1][3]
          and not any("BLITZ" in a[3] for a in al), al)
    check("c. at most 20; junk never throws", o["many"] == 20 and all(j == "ok" for j in o["junk"]), (o["many"], o["junk"]))


if __name__ == "__main__":
    static()
    core()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
