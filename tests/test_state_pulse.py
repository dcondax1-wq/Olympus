"""night-truth 2026-11-22: the phone's truth.
  (1) STATE PULSE (engine/state_pulse.py + tools/pc_report.py --pulse): a bot state change posts the core status at once,
      debounced >= 30 s, at most DAY_MAX a UTC day, held at ntfy's reserve; a repeat core post with the same state < 5 min
      apart is skipped; the day's worst case holds under ntfy's 250 with the trade-alert reserve.
  (2) FIELD AUDIT: what the phone reads is really sent (armed per account in the core "ar", every extra account in the glance,
      the Rapid room without a broker anchor), checked on tonight's REAL merged post (research/handoff/2026-11-22/truth/).
  (3) $0 VIEW: MFFU sim-funded accounts start at $0 (ATLAS $401, not $25,401) in board.py and Trading Home.
  (4) Trading Home: one line per account (armed / running, room $, today $, next window) for all 4 accounts.

    python -X utf8 -m tests.test_state_pulse        # ~5 s, fakes only: no network, no bot, nothing armed or traded
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import brain_glance as G  # noqa: E402
from engine import mffu_view as MV  # noqa: E402
from engine import state_pulse as SP  # noqa: E402
from tools import pc_report as R  # noqa: E402

REAL = os.path.join(ROOT, "research", "handoff", "2026-11-22", "truth", "real_status_merged.json")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:400]))


# ---------------------------------------------------------------------------------------------- (1) the pulse
class Bot:
    def __init__(self):
        self.running = False
        self.cfg = {"armed": True}
        self.state = {}
        self.health = {}
        self.adapter = SimpleNamespace(disabled=None)
        self.ledger = []
        self.acct_b = None
        self.accts = None


class Runner:
    def __init__(self, rc=0):
        self.calls, self.rc = [], rc

    def __call__(self, argv, timeout):
        self.calls.append(argv)
        return self.rc, ""


def pulse_tests():
    tmp = tempfile.mkdtemp(prefix="pulse_")
    try:
        bot, run, beats = Bot(), Runner(), []
        hb = SimpleNamespace(beat=lambda: beats.append(1))
        p = SP.Pulse(bot, heartbeat=hb, run=run, work=tmp, log=lambda *_: None)
        p.grace_s = 0
        t = 1_795_400_000.0
        r = p.tick(t)
        check("pulse: the first look posts once (no earlier state)", r["fired"] and len(run.calls) == 1, r)
        check("pulse: a fire = a fresh heartbeat first, then pc_report --pulse", beats == [1] and "--pulse" in run.calls[0], run.calls)
        r = p.tick(t + 10)
        check("pulse: nothing changed -> nothing sent", not r["fired"] and not r["changed"] and len(run.calls) == 1, r)
        bot.running = True                                   # the bot comes back 15 s after the last post
        r = p.tick(t + 15)
        check("pulse: a change inside 30 s waits (debounce)", r["changed"] == ["bot running"] and not r["fired"]
              and "debounce" in str(r["held"]), r)
        r = p.tick(t + 31)
        check("pulse: the same change goes once the 30 s are over", r["fired"] and len(run.calls) == 2, r)
        bot.state = {"position": {"side": "LONG"}}
        r1 = p.tick(t + 40)
        bot.state = {}                                       # opened and closed inside the gap: folded, nothing new to say
        r2 = p.tick(t + 50)
        r3 = p.tick(t + 70)
        check("pulse: a flip and back inside the gap is folded (nothing posted)", not r1["fired"] and not r2["changed"] and not r3["fired"]
              and len(run.calls) == 2, (r1, r2, r3))
        bot.cfg["armed"] = False
        r = p.tick(t + 80)
        check("pulse: disarm posts at once after the gap, in plain words", r["fired"] and "lit disarmed" in r["changed"], r)
        bot.health = {"entries_blocked": True, "feed_block": "FEED STALE"}
        r = p.tick(t + 120)
        check("pulse: an entry block appearing posts", r["fired"] and "entry block on" in r["changed"], r)
        # restart: the saved signature survives; same state -> no post
        p2 = SP.Pulse(bot, heartbeat=hb, run=run, work=tmp, log=lambda *_: None)
        p2.grace_s = 0
        r = p2.tick(t + 200)
        check("pulse: after a server restart the saved state counts (no repeat post)", not r["changed"] and not r["fired"], r)
        # grace: right after a start, "stopped" waits for the autostart
        bot.running = False
        p3 = SP.Pulse(bot, heartbeat=hb, run=run, work=tmp, log=lambda *_: None)
        r = p3.tick(t + 300)
        check("pulse: the first 90 s of a server start do not post 'stopped'", not r["fired"] and "starting" in str(r["held"]), r)
        r = p3.tick(t + 300 + SP.START_GRACE_S + 1)
        check("pulse: ... after the grace it does", r["fired"] and "bot stopped" in r["changed"], r)
        # busy report: retried, nothing lost
        busy = Runner(rc=SP.BUSY_RC)
        bot.running = True
        p4 = SP.Pulse(bot, heartbeat=hb, run=busy, work=tmp, log=lambda *_: None)
        p4.grace_s = 0
        p4.tick(t + 1000)
        r = p4.tick(t + 1040)
        check("pulse: a busy report run (exit 3) is tried again after the gap", len(busy.calls) == 2 and "busy" in str(p4.held), busy.calls)
        # day cap
        st = SP.read_state(tmp)
        st["days"] = {SP._utc_day(t + 2000): SP.DAY_MAX}
        SP.write_state(st, tmp)
        bot.cfg["armed"] = True
        p.last_fire = 0
        r = p.tick(t + 2000)
        check(f"pulse: at {SP.DAY_MAX} pulses a day it holds (the 15-minute report goes on)", not r["fired"] and "budget" in str(r["held"]), r)
        b = SP.budget()
        check(f"pulse: ntfy budget proof: {b['core']} core + {b['ext']} ext + {b['bars']} chart + {b['pulse']} pulse = {b['total']}, "
              f"+ {b['reserve']} reserve <= {b['cap']}", b["holds"] and b["total"] + b["reserve"] <= 250, b)
        check("pulse: the budget's numbers are pc_report's own", SP.NTFY_DAY_CAP == R.NTFY_DAY_CAP and SP.TRADE_ALERT_RESERVE == R.TRADE_ALERT_RESERVE
              and SP.BARS_DAY == R.BARS_DAY_MAX and SP.EXT_DAY >= R.EXT_PARTS * -(-86400 // R.EXT_EVERY_S)
              and SP.CORE_DAY == 86400 // 900, (SP.EXT_DAY, R.EXT_PARTS, R.EXT_EVERY_S))
        # signature: extra accounts + ATLAS
        bot.acct_b = SimpleNamespace(disabled_reason=lambda: None, kind=lambda: "LIVE", position=lambda: None, lock=None,
                                     entries_today=lambda d: 0)
        bot.accts = SimpleNamespace(health=lambda now: [{"id": "b25k_2", "armed": True, "enabled": True, "open": False, "locked": None,
                                                         "entries_today": 0}])
        sig = SP.signature(bot, t)
        check("pulse: the signature covers Zlarior, ATLAS and every extra account", set(sig["a"]) == {"lit", "atlas", "b25k_2"}
              and sig["a"]["atlas"][0] is True, sig)
        check("pulse: the signature is small (< 400 bytes)", len(json.dumps(sig)) < 400, len(json.dumps(sig)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class FakeHTTP:
    def __init__(self, remaining=200):
        self.calls, self.remaining = [], remaining

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        self.calls.append((method, url, body))
        if url.startswith("http://127.0.0.1"):
            return 200, '{"ok": true}'
        if url.endswith("/v1/account"):
            return 200, json.dumps({"stats": {"messages": 250 - self.remaining, "messages_remaining": self.remaining}, "limits": {"messages": 250}})
        return 200, "{}"

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


def report_tests():
    tmp = tempfile.mkdtemp(prefix="pulse_rep_")
    try:
        root, work = os.path.join(tmp, "root"), os.path.join(tmp, "work")
        os.makedirs(os.path.join(root, "logs", "pc_hb"))
        now = 1_795_400_000
        hb = {"t": now - 20, "running": True, "adapter": "ninjatrader", "every_s": 300,
              "health": {"account": {"name": "Sim101", "adapter": "ninjatrader", "armed": True, "enabled": True, "label": "SIM"}}}
        with open(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), "w") as fh:
            json.dump(hb, fh)
        env = {"OLYMPUS_HOME": os.path.join(tmp, "home"), "LE_PR_T_NT": "1", "LE_PR_T_MARKET": "1"}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            h = FakeHTTP()
            r = R.pulse_once(work=work, why="bot running", http=h, root=root, now=now, feed_problem=lambda: None, say=lambda *_: None)
            posts = h.posts()
            body = json.loads(posts[0][2]) if posts else {}
            if isinstance(body, dict) and "sg" not in body and posts:
                body = json.loads(posts[0][2])
            check("pc_report --pulse: ONE post, the core only (kind le-live), marked as a pulse", r["posted"] and len(posts) == 1
                  and body.get("kind") == "le-live" and body.get("pulse") == now, (r, body.get("kind"), body.get("pulse")))
            check("pc_report --pulse: the core carries each account armed (ar)", body.get("ar") == {"lit": 1}, body.get("ar"))
            st = SP.read_state(work)
            bars = R.read_json(os.path.join(work, R.BARS_STATE), {})
            check("pc_report --pulse: counted in pulse.json and in the PC's day (bars.json all)", SP.day_count(st, now) == 1
                  and bars["days"][R._utc_day(now)]["all"] == 1 and bars["days"][R._utc_day(now)]["pulse"] == 1, (st, bars))
            last = R.read_json(os.path.join(work, "last.json"), {})
            check("pc_report --pulse: last.json 't' untouched (the 15-minute cadence + keeper go on)", "t" not in last and last.get("pulse_t") == now, last)
            h2 = FakeHTTP(remaining=R.TRADE_ALERT_RESERVE)
            r2 = R.pulse_once(work=work, why="x", http=h2, root=root, now=now + 60, feed_problem=lambda: None, say=lambda *_: None)
            check("pc_report --pulse: held at ntfy's own reserve (trade alerts first)", not r2["posted"] and not h2.posts() and "budget" in str(r2["held"]), r2)
            SP.write_state({"days": {R._utc_day(now): SP.DAY_MAX}}, work)
            h3 = FakeHTTP()
            r3 = R.pulse_once(work=work, why="x", http=h3, root=root, now=now + 90, feed_problem=lambda: None, say=lambda *_: None)
            check("pc_report --pulse: held after DAY_MAX pulses today", not r3["posted"] and not h3.posts(), r3)
            # core dedupe in the regular run: same state < 5 min after a post -> no second core
            os.remove(os.path.join(work, "last.json"))
            h4 = FakeHTTP()
            R.run_once(work=work, http=h4, root=root, now=now + 100, feed_problem=lambda: None, say=lambda *_: None, app_push=R._NO_BUS)
            n1 = sum(1 for c in h4.posts() if '"le-live"' in str(c[2]))
            h5 = FakeHTTP()
            rec = R.run_once(work=work, http=h5, root=root, now=now + 220, feed_problem=lambda: None, say=lambda *_: None, app_push=R._NO_BUS)
            n2 = sum(1 for c in h5.posts() if '"kind":"le-live"' in str(c[2]))
            check("pc_report: a 2nd run 2 min later with the same state skips its core post (tonight's posts came in pairs)",
                  n1 == 1 and n2 == 0 and rec.get("core_skipped"), (n1, n2, rec.get("core_skipped")))
            hb["running"] = False
            with open(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), "w") as fh:
                json.dump(hb, fh)
            h6 = FakeHTTP()
            R.run_once(work=work, http=h6, root=root, now=now + 260, feed_problem=lambda: None, say=lambda *_: None, app_push=R._NO_BUS)
            n3 = sum(1 for c in h6.posts() if '"kind":"le-live"' in str(c[2]))
            check("pc_report: ... but a changed state (bot stopped) posts at once", n3 == 1, n3)
            h7 = FakeHTTP()
            R.run_once(work=work, http=h7, root=root, now=now + 260 + R.CORE_MIN_GAP_S + 1, feed_problem=lambda: None, say=lambda *_: None,
                       app_push=R._NO_BUS)
            check("pc_report: ... and the same state again after 5 min posts (sign of life)",
                  sum(1 for c in h7.posts() if '"kind":"le-live"' in str(c[2])) == 1)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- (2) field audit
def audit_tests():
    real = json.load(open(REAL, encoding="utf-8"))
    ids = {a["id"] for a in real["accounts"]} | {"lit", "atlas"}
    check("audit: tonight's real post has the 4 accounts (Zlarior 50K + ATLAS cards, 3 accounts rows)",
          {"mffu50k_eval", "b25k_2", "rapid"} <= ids and real["board"].get("atlas"), sorted(ids))
    check("audit: tonight's real glance missed Zlarior 25K #2 (the bug this branch fixes)",
          "b25k_2" not in [b["id"] for b in real["pc"]["glance"]["bots"]])
    hb = {"t": 1, "running": True,
          "health": {"account": {"armed": True, "enabled": True, "label": "LIVE"},
                     "accounts": [{"id": "rapid", "armed": True, "enabled": True, "label": "LIVE"},
                                  {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "armed": False, "enabled": True, "label": "LIVE"}]},
          "second": {"route": {"account_b": {"kind": "LIVE", "enabled": True, "label": "ATLAS x"}}},
          "acct": {"accounts": [
              {"id": "rapid", "plan": "Rapid EOD 25K", "enabled": True, "running": True, "eval": {"days": {}},
               "plan_rules": {"start": 25000.0, "mll": 1000.0, "lock": 25100.0}, "account": {"label": "LIVE ACCOUNT"}, "day_pnl": 0},
              {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "enabled": True, "running": True,
               "eval": {"days": {"2026-11-20": 23.62}}, "plan_rules": {"start": 25000.0, "mll": 1000.0, "lock": 25100.0},
               "account": {"label": "LIVE ACCOUNT"}, "day_pnl": 0}]}}
    am = G.armed_map(hb)
    check("audit: armed_map = each account armed + live gate (ATLAS from account_b kind/enabled, no 'armed' key needed)",
          am == {"lit": 1, "atlas": 1, "rapid": 1, "b25k_2": 0}, am)
    g = G.build(hb, {})
    bots = {b["id"]: b for b in g["bots"]}
    check("audit: the glance now has every extra account (Zlarior 25K #2 named the owner's way)",
          "b25k_2" in bots and bots["b25k_2"]["name"] == "Zlarior 25K #2", list(bots))
    check("audit: Rapid's room without a broker anchor = MFFU's floor from the plan ($1,000, was missing)", bots["rapid"].get("room") == 1000,
          bots["rapid"])
    check("audit: the 25K #2 room from its days: EOD trail $25,023.62 - $1,000 -> room $1,000", bots["b25k_2"].get("room") == 1000,
          bots["b25k_2"])
    check("audit: the trailing floor stops at the lock", G._plan_floor({"start": 25000, "mll": 1000, "lock": 25100}, {"d": 3000}) == 25100)
    check("audit: a static plan floor is start - mll", G._plan_floor({"start": 25000, "mll": 1000, "lock": 24000}, {"d": 3000}) == 24000)
    check("audit: 'ar' and 'pulse' ride the CORE post (the glance rides the ext, every 44 min)", "ar" in R.CORE_KEYS and "pulse" in R.CORE_KEYS)
    tr = R.split({"v": 1, "kind": "le-live", "t": 1, "ar": am, "pc": {"running": True}, "reporter": {"t": 1}})[0]
    check("audit: the privacy pass keeps 'ar' as sent", tr.get("ar") == am, tr.get("ar"))
    doc = open(os.path.join(ROOT, "research", "handoff", "2026-11-22", "truth", "FIELD_AUDIT.md"), encoding="utf-8").read()
    check("audit: the field audit table is written (research/handoff/2026-11-22/truth/FIELD_AUDIT.md)", "| " in doc and "sent" in doc.lower())


# ---------------------------------------------------------------------------------------------- (3) $0 view
def zero_tests():
    v = MV.money_view(25401.38, 24401.38, 1000.0, True, "MFFU Builder 25K funded")
    check("$0 view: ATLAS funded $25,401 shows $401 (MFFU starts sim-funded at $0), room $1,000, floor -$599",
          v["balance"] == 401.38 and v["room"] == 1000.0 and v["floor"] == -598.62 and v["mffu"], v)
    v2 = MV.money_view(401.38, None, 1000.0, True, "Builder 25K")
    check("$0 view: a balance already in MFFU terms is kept", v2["balance"] == 401.38 and not v2["mffu"], v2)
    v3 = MV.money_view(49213.9, 48168.2, 1045.7, False, "Builder 50K")
    check("$0 view: an eval keeps its balance", v3["balance"] == 49213.9 and v3["floor"] == 48168.2, v3)
    v4 = MV.money_view(27000.0, 26000.0, 1000.0, True, "Builder 25K")
    check("$0 view: the floor is capped at the +$100 lock", v4["floor"] == 100.0 and v4["balance"] == 2000.0, v4)
    from tools import board as BD
    lines = BD.lines({"pc": {"t": 1795401816, "via": "ntfy"}, "accounts": [
        {"name": "ATLAS", "plan": "MFFU Builder 25K (funded)", "stage": "funded", "chip": "funded", "balance": 25401.38, "floor": 24401.38,
         "room": 1000.0, "src": "PC live"},
        {"name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "balance": 49213.9, "room": 1045.7, "src": "PC live"}]}, now=1795401900)
    at = next(x for x in lines if x.strip().startswith("ATLAS"))
    zl = next(x for x in lines if x.strip().startswith("Zlarior"))
    check("$0 view: board.py read shows ATLAS funded as $401 (floor -$599), not $25,401", "$401 (MFFU from $0, floor -$599)" in at
          and "25,401" not in at, at)
    check("$0 view: board.py keeps the eval's balance", "$49,214" in zl, zl)


# ---------------------------------------------------------------------------------------------- (4) Trading Home rows
NODE = r"""
const T = require(process.argv[1]); const L = require(process.argv[2]);
const out = {};
out.real = T.today(L, { now: L.t + 60 }).lines;
const L2 = JSON.parse(JSON.stringify(L)); L2.ar = { lit: 1, atlas: 1, rapid: 1, b25k_2: 0 };
out.ar = T.today(L2, { now: L2.t + 60 }).lines;
out.old = T.today(L2, { now: L2.t + 3 * 3600 }).lines;
console.log(JSON.stringify(out));
"""


def home_tests():
    if not shutil.which("node"):
        check("trading home: node is here (the rules run in node)", False, "no node")
        return
    js = os.path.join(ROOT, "tools", "web_public", "nq", "trading_home_core.js")
    r = subprocess.run(["node", "-e", NODE, js, REAL], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout)
    except ValueError:
        check("trading home: the node run works", False, r.stderr[-300:])
        return
    acct = [x for x in o["real"] if x.get("acct")]
    names = [x["title"] for x in acct]
    check("trading home: the 4 accounts each get one line (tonight's real post)", len(acct) == 4
          and names == ["Zlarior 50K", "ATLAS 25K funded", "Zlarior 25K #2", "Rapid EOD 25K"], names)
    z = acct[0]["say"]
    check("trading home: a line = armed / running, room $, today $, next window", all(w in z for w in ("running", "room $1,046", "today $0", "next Mon 02:00-15:30 ET")), z)
    check("trading home: ATLAS's line has its own window", "02:00-05:00" in acct[1]["say"], acct[1]["say"])
    check("trading home: an older PC without 'ar' says the armed flag is a guess ('?')", "ARMED ?" in z, z)
    a2 = {x["id"]: x for x in o["ar"]}
    check("trading home: 'ar' decides armed: Zlarior 25K #2 NOT armed, its line red", a2["acct:b25k_2"]["say"].startswith("NOT armed")
          and a2["acct:b25k_2"]["ok"] is False and a2["acct:lit"]["ok"] is True, a2["acct:b25k_2"])
    check("trading home: 'Every account armed' names the one held", a2["armed"]["ok"] is False and "Zlarior 25K #2" in a2["armed"]["say"]
          and "ATLAS" not in a2["armed"]["say"], a2["armed"]["say"])
    old = [x for x in o["old"] if x.get("acct")]
    check("trading home: a 3-hour-old report says so on each line", all(x["say"].startswith("Old report") and x["ok"] is None for x in old), old[:1])
    html = open(os.path.join(ROOT, "tools", "web_public", "nq", "trading_home.html"), encoding="utf-8").read()
    check("trading home: the page renders the core's lines (textContent, no innerHTML)", "res.lines.forEach" in html and "innerHTML" not in html)


if __name__ == "__main__":
    pulse_tests()
    report_tests()
    audit_tests()
    zero_tests()
    home_tests()
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
