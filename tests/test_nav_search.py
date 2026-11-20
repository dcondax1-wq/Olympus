"""Search the owner's way (olympus/gate-catalog.js findAll, the Home search + every Go to sheet; 2026-11-20 day-manual NAV team).
  a. 64 real phrasings ("how much can I lose", "is atlas in a trade", "stop the bot", ...) -> the FIRST result opens the right place
     (first = what the Gate draws first: a page hub, then an action, then an app, then a hub tab)
  b. the old pins still hold (kalshi -> the Kalshi bot first, theme -> Change the look, payout -> act-payout + Ledger first app,
     micros, all apps, health -> Me, money -> Mint + Ledger in the apps)
  c. every action's page exists and its #anchor is an id on that page
    python -X utf8 -m tests.test_nav_search      (node only, ~1 s)
"""
from __future__ import annotations

import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []

# phrasing -> where the first result must go (a path prefix from the site root)
CASES = {
    # 1 each account's room
    "room": "business/mffu.html", "how much room do I have": "business/mffu.html", "how much can I lose": "business/mffu.html",
    "drawdown": "business/mffu.html", "max loss": "business/mffu.html", "how close am I to failing": "business/mffu.html",
    # 2 today's $
    "today's pnl": "hub/zeus.html", "what did I make today": "hub/zeus.html", "how much did zlarior make": "hub/zeus.html",
    "money made today": "hub/zeus.html",
    # 3 open trade
    "is atlas in a trade": "business/mffu.html", "am I in a trade": "business/mffu.html", "open trade": "business/mffu.html",
    "open position": "business/mffu.html",
    # 4 next payout
    "payout": "business/accounts.html#coach", "when is my next payout": "business/accounts.html#coach",
    "can I get paid": "business/accounts.html#coach", "withdraw": "business/accounts.html#coach",
    # 5 Decide cards
    "decide": "board/index.html#decide", "decisions waiting": "board/index.html#decide", "questions for me": "board/index.html#decide",
    # 6 alerts settings
    "notifications": "jarvis/index.html#pushCard", "turn off alerts": "jarvis/index.html#pushCard", "phone alerts": "jarvis/index.html#pushCard",
    # 7 Kalshi K8 today
    "kalshi today": "kalshi/index.html#k8d", "k8": "kalshi/index.html#k8d", "gold bets": "kalshi/index.html#k8d",
    # 8 taxes pot
    "taxes": "business/taxes.html", "tax pot": "business/taxes.html", "how much tax do I owe": "business/taxes.html",
    # 9 the manual's SOS
    "emergency": "hub/manual.html#sos", "something is wrong": "hub/manual.html#sos", "panic": "hub/manual.html#sos",
    "ninjatrader disconnected": "hub/manual.html#sos",
    "stop the bot": "hub/manual.html#sos-8", "kill switch": "hub/manual.html#sos-8", "flatten everything": "hub/manual.html#sos-8",
    "stop everything": "hub/manual.html#sos-8",
    # 10 the PC status
    "is the pc on": "hub/zeus.html", "pc silent": "hub/zeus.html", "bot down": "hub/zeus.html", "is the bot running": "hub/zeus.html",
    # words and help
    "manual": "hub/manual.html", "glossary": "hub/manual.html", "what does dll mean": "hub/manual.html#g-dll",
    "what is a twin": "hub/manual.html#g-twin", "what is room": "hub/manual.html#g-room", "what does eod mean": "hub/manual.html#g-eod",
    "my steps": "hub/steps.html", "what do I need to do": "hub/steps.html", "help": "hub/help.html",
    "add an account": "hub/manual.html#sos-9", "eval passed": "hub/help.html#eval-passed", "restart the bot": "hub/help.html#restart",
    "update the pc": "hub/help.html#update", "holidays": "hub/help.html#holidays",
    # the rest of the site
    "my accounts": "business/accounts.html", "zeus": "hub/zeus.html", "board": "board/", "kalshi": "kalshi/", "journal": "journal/",
    "news today": "pheme/", "how many micros": "pnyx/index.html", "change theme": "gate/index.html#lookSec", "dark mode": "gate/index.html#lookSec",
    "all apps": "gate/index.html#az", "weekly review": "apollo/",
    # what's new (2026-11-20 lead follow-up)
    "what's new": "hub/whatsnew.html", "what changed": "hub/whatsnew.html", "whats new this week": "hub/whatsnew.html",
}

JS = r"""
const G = require(process.argv[1]);
const first = (q) => { const r = G.findAll(q, 8);
  if (r.hubs[0]) return 'hub/index.html?h=' + r.hubs[0].id; if (r.actions[0]) return r.actions[0].path;
  if (r.apps[0]) return r.apps[0].path || 'index.html'; if (r.tabs[0]) return r.tabs[0].path; return '-'; };
const qs = JSON.parse(process.argv[2]);
const pins = {}; for (const q of ['kalshi', 'theme', 'payout', 'micros', 'all apps', 'health', 'money', 'drawdown', 'journal', 'news']) {
  const r = G.findAll(q, 8); pins[q] = { hubs: r.hubs.map((h) => h.id), actions: r.actions.map((x) => x.id), apps: r.apps.map((a) => a.id), find: G.find(q, 8).map((a) => a.id) }; }
console.log(JSON.stringify({ first: Object.fromEntries(qs.map((q) => [q, first(q)])), pins, actions: G.actions.map((a) => [a.id, a.path]) }));
"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"))


def main():
    out = subprocess.run(["node", "-e", JS, os.path.join(WEB, "olympus", "gate-catalog.js"), json.dumps(list(CASES))],
                         capture_output=True, text=True, timeout=60)
    d = json.loads(out.stdout)
    bad = {q: (d["first"][q], want) for q, want in CASES.items() if not d["first"][q].startswith(want)}
    check(f"a. {len(CASES)} plain phrasings: the first result opens the right place ({len(CASES) - len(bad)}/{len(CASES)})", not bad, bad)
    p = d["pins"]
    check("b. old pins: kalshi -> Kalshi bot first (no action ahead), theme -> act-look, payout -> act-payout + Ledger, micros, all apps, health -> Me",
          p["kalshi"]["actions"] == [] and p["kalshi"]["apps"][0] == "kalshi" and p["theme"]["actions"][:1] == ["act-look"]
          and p["payout"]["actions"][:1] == ["act-payout"] and p["payout"]["apps"][0] == "ledger" and p["micros"]["actions"][:1] == ["act-micros"]
          and p["all apps"]["actions"][:1] == ["act-az"] and p["health"]["hubs"] == ["me"], p)
    check("b. old pins: money -> Mint + Ledger, drawdown -> Aegis, journal first, news -> Pheme / Pythia / Herald (find)",
          {"mint", "ledger"} <= set(p["money"]["find"]) and "aegis" in p["drawdown"]["find"] and p["journal"]["find"][0] == "journal"
          and {"pheme", "pythia", "herald"} <= set(p["news"]["find"]), p)
    miss = []
    helpids = {i["id"] for i in json.load(open(os.path.join(WEB, "hub", "help.json"), encoding="utf-8"))["items"]}
    js_routes = {"gate/index.html#az", "index.html#/brain"}          # opened by the page's own script (the A-Z sheet, the dashboard view)
    for aid, path in d["actions"]:
        if path in js_routes:
            continue
        if path.startswith("hub/help.html#"):                       # help.js opens help.html#<item id>
            if path.split("#", 1)[1] not in helpids:
                miss.append((aid, path))
            continue
        f, _, frag = path.partition("#")
        f = f.split("?")[0]
        fp = os.path.join(WEB, f if f and not f.endswith("/") else f + "index.html")
        if not os.path.exists(fp):
            miss.append((aid, path))
            continue
        if frag and not re.search(r'id="' + re.escape(frag) + '"', open(fp, encoding="utf-8").read()):
            miss.append((aid, path))
    check(f"c. every action ({len(d['actions'])}) opens a page that exists, with its #anchor", not miss, miss)
    n = sum(RES)
    print(f"\nnav_search: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
