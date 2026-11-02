"""Jarvis's System view (2026-11-02, owner: "everything combined and simple"): tools/web_public/jarvis/data.js systemStatus,
driven in node (no DOM, no network: fetch is mocked), end to end from the PC's own publish:
  a. engine/live_publish.build -> live.json (with the heartbeat's pc_health block) -> data.js refreshLive (mocked fetch) ->
     getFacts().system: the PC line carries CPU / RAM, the bots their numbers, the verdict ALL GOOD
  b. one verdict, the one thing to do: a stopped bot, a stale NinjaTrader feed, NinjaTrader disconnected, a red / amber PC
     health line, the PC's own verdict (ON SIM = heads up), a bot near its floor, the Kalshi bot stopped / not updating
  c. the PC silent: NEEDS YOU while the market is open or opens within 2 h; grey (fine) on a quiet weekend; the bots' lines
     then say "last known" and do not count
  d. junk in (null, wrong types, a throwing part): an answer out ('CHECKING' or a verdict), never an exception
    python -X utf8 -m tests.test_jarvis_system      (node + a temp folder; nothing else touched; a few seconds)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from engine import live_publish as lp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "web_public", "jarvis", "data.js")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


RUNNER = r"""
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [dataPath, scenPath] = process.argv.slice(2);
const store = new Map();
globalThis.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
const scen = JSON.parse(fs.readFileSync(scenPath, 'utf8'));
let liveBody = null;
globalThis.fetch = async (url) => {
  if (String(url).includes('live.json') && liveBody) return { ok: true, status: 200, json: async () => liveBody };
  return { ok: false, status: 404, json: async () => ({}) };
};
const D = await import(pathToFileURL(dataPath).href);
const out = {};
// a. the PC's publish, read the way the phone reads it
liveBody = scen.published;
await D.refreshLive();
const f = D.getFacts();
out.published = { system: f.system, slim: f.live && f.live.pc_health };
// b-d: systemStatus on hand-made facts
for (const [name, facts] of Object.entries(scen.cases)) {
  try { out[name] = D.systemStatus(facts === '__throw__' ? { get live() { throw new Error('boom'); } } : facts); }
  catch (e) { out[name] = { exception: String(e) }; }
}
process.stdout.write(JSON.stringify(out));
"""


def hb_payload(now):
    """A running PC bot's heartbeat payload (the shape engine/heartbeat sends) with its pc_health block."""
    return {"t": now, "running": True, "adapter": "ninjatrader", "position": False, "model_state": "watching levels", "host": "SURFACE",
            "model": "lit", "every_s": 300,
            "acct": {"v": 1, "t": now, "account": {"name": "FAKEEVAL1", "label": "LIVE ACCOUNT", "adapter": "ninjatrader"}, "running": True,
                     "kill": False, "model": "lit", "eval": {"start": "2026-10-19", "days": {"2026-10-19": 300.0}}, "position": None,
                     "orders": [], "trades": [], "day_pnl": 0.0},
            "health": {"v": 1, "t": now, "running": True, "kill": False, "model": "lit",
                       "account": {"name": "FAKEEVAL1", "adapter": "ninjatrader", "is_live": True, "label": "LIVE", "enabled": True,
                                   "disabled": None, "armed": True, "live_lock": True},
                       "feed": {"source": "ninjatrader", "used": "ninjatrader", "no_yahoo": True, "age_1m_s": 12, "age_5m_s": 40,
                                "last_1m_t": now - 72, "last_5m_t": now - 340, "stale": False, "market_open": True, "entries_blocked": False},
                       "poll": {"last_t": now - 3, "age_s": 3, "errors": 0}, "nt": {"connected": True},
                       "lit": {"stage": "levels", "text": "watching", "price": 25070.5}},
            "pc_health": {"t": now - 30, "level": "green", "skipped": [], "lines": [
                {"key": "cpu", "level": "green", "text": "CPU 23%"},
                {"key": "ram", "level": "green", "text": "RAM 61% in use (2.2 of 3.6 GB)"},
                {"key": "disk", "level": "green", "text": "41.0 GB free"},
                {"key": "nt", "level": "green", "text": "NinjaTrader running, 900 MB"}]}}


def cases(now_s):
    now_ms = now_s * 1000
    card = lambda **o: {"room": 1105.6, "room_frac": 0.55, "today_pnl": 212.5, "status": "open", **o}      # noqa: E731
    good_v = {"level": "good", "label": "TRADING YOUR EVAL", "reason": "heartbeat fresh"}

    def live(age=60, **o):
        v = {"t": now_s - age, "running": True, "verdict": good_v, "lit": card(), "atlas": card(room=750.4, room_frac=0.75, today_pnl=0.0),
             "blitz": {"off": True, "status": "off"}, "health": [{"key": "age_1m_s", "value": "12 s", "ok": True}, {"key": "nt", "ok": True}],
             "pc_health": {"level": "ok", "cpu": 23, "ram": 61, "lines": [{"key": "cpu", "label": "CPU", "level": "ok", "text": "CPU 23%"}]}}
        v.update(o)
        return v
    kal = {"running": True, "t": now_s - 60, "today_pnl": 18.5, "balance": 512.34}
    opn = {"open": True, "rth": True, "next": {"mins": 300}}
    wkend = {"open": False, "next": {"mins": 1500}}
    soon = {"open": False, "next": {"mins": 45}}
    plan = {"ev": [{"title": "Review fills", "start": "23:59", "allDay": False}], "tasks": [{"title": "Buy BLITZ 25K"}]}
    base = {"now": now_ms, "market": opn, "live": live(), "kalshi": kal, "kalshiState": "ok", "planner": plan}
    c = lambda **o: {**base, **o}      # noqa: E731
    ph_bad = {"level": "bad", "cpu": 97, "ram": 50, "lines": [{"key": "cpu", "label": "CPU", "level": "bad", "text": "CPU 97% (the bot's decisions may run late)"}]}
    ph_warn = {"level": "warn", "cpu": 20, "ram": 90, "lines": [{"key": "ram", "label": "Memory (RAM)", "level": "warn", "text": "RAM 90% in use: close other apps (browser tabs)"}]}
    return {
        "good": c(),
        "stopped": c(live=live(running=False)),
        "feed_stale": c(live=live(health=[{"key": "age_1m_s", "value": "9 min", "ok": False}, {"key": "nt", "ok": True}])),
        "nt_off": c(live=live(health=[{"key": "age_1m_s", "value": "12 s", "ok": True}, {"key": "nt", "ok": False}])),
        "ph_bad": c(live=live(pc_health=ph_bad)),
        "ph_warn": c(live=live(pc_health=ph_warn)),
        "on_sim": c(live=live(verdict={"level": "warn", "label": "ON SIM", "reason": "orders go to Sim101, not your eval"})),
        "near_floor": c(live=live(lit=card(room=300.0, room_frac=0.15))),
        "kalshi_stopped": c(kalshi={**kal, "running": False}),
        "kalshi_stale": c(kalshi={**kal, "t": now_s - 3600}),
        "kalshi_waiting": c(kalshi=None, kalshiState="waiting"),
        "silent_open": c(live=live(age=3600)),
        "silent_soon": c(live=live(age=3600), market=soon),
        "silent_weekend": c(live=live(age=3 * 86400), market=wkend),
        "no_signal": c(live=None, liveError="Failed to fetch"),
        "loading": {"now": now_ms},
        "junk_null": None,
        "junk_types": {"now": "x", "market": 7, "live": {"t": "soon", "lit": "x", "atlas": {"room": "abc"}, "health": "x", "pc_health": {"lines": [None, 5]}},
                       "kalshi": {"t": "x", "running": "maybe"}, "kalshiState": 9, "planner": {"ev": [None, 5], "tasks": "x"}},
        "junk_throw": "__throw__",
    }


def main() -> int:
    node = shutil.which("node")
    if not node:
        check("node is installed", False, "node not found")
        return 1
    now = int(time.time())
    published = lp.build(hb_payload(now), now, lm={"lit_sizing": {"eval_start": "2026-10-19"}}, hb_last={"at": now - 30, "ok": True}, every_s=60)
    tmp = tempfile.mkdtemp(prefix="le_jsys_")
    try:
        rp, sp = os.path.join(tmp, "runner.mjs"), os.path.join(tmp, "scen.json")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        open(sp, "w", encoding="utf-8").write(json.dumps({"published": published, "cases": cases(now)}))
        r = subprocess.run([node, rp, DATA, sp], capture_output=True, text=True, timeout=60)
        check("node ran data.js", r.returncode == 0, r.stderr[-800:])
        if r.returncode:
            return 1
        O = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # a. end to end from the PC's publish
    S, slim = O["published"]["system"] or {}, O["published"]["slim"] or {}
    rows = {x["id"]: x for x in S.get("rows") or []}
    check("a. live.json carries pc_health and the phone keeps it (CPU 23, RAM 61, four lines)",
          (published.get("pc_health") or {}).get("cpu") == 23 and slim.get("cpu") == 23 and slim.get("ram") == 61 and len(slim.get("lines") or []) == 4, slim)
    check("a. getFacts().system from the published live.json: the PC line CPU / RAM, checked in, the feed; one line per system",
          list(rows) == ["pc", "lit", "atlas", "blitz", "kalshi", "planner"] and rows["pc"]["value"] == "CPU 23% · RAM 61%"
          and rows["pc"]["level"] == "ok" and "checked in" in rows["pc"]["text"], rows.get("pc"))
    check("a. the published live.json holds no secret-looking key", not any(k in json.dumps(published) for k in ('"token"', '"password"', '"push_pk"')))

    def v(name):
        return O[name] or {}
    lv = lambda name, rid: next((x for x in v(name).get("rows") or [] if x["id"] == rid), {}).get("level")      # noqa: E731
    g = v("good")
    check("b. all fine: ALL GOOD, no to-do, every line green but BLITZ (off: grey)",
          g["verdict"] == "ALL GOOD" and g["level"] == "ok" and not g["todo"] and [x["level"] for x in g["rows"]] == ["ok", "ok", "ok", "", "ok", "ok"], g)
    check("b. the planner line: the next event and the open tasks", next(x for x in g["rows"] if x["id"] == "planner")["text"] == "Review fills · 1 task open", g["rows"][-1])
    for name, verdict, todo_has, short in (("stopped", "NEEDS YOU", "Start the bot on the PC", "PC: bot stopped"),
                                           ("feed_stale", "NEEDS YOU", "bar feed is stale", "PC: feed stale"),
                                           ("nt_off", "NEEDS YOU", "Reconnect NinjaTrader", "PC: NinjaTrader not connected"),
                                           ("ph_bad", "NEEDS YOU", "CPU 97%", "PC: CPU red"),
                                           ("ph_warn", "HEADS UP", "RAM 90% in use", "PC: Memory (RAM) to watch"),
                                           ("on_sim", "HEADS UP", "Zlarior: ON SIM (orders go to Sim101", "Zlarior: ON SIM"),
                                           ("near_floor", "HEADS UP", "Zlarior is close to its floor: $300", "Zlarior: near its floor"),
                                           ("kalshi_stopped", "NEEDS YOU", "Kalshi bot stopped", "Kalshi bot stopped"),
                                           ("kalshi_stale", "HEADS UP", "Kalshi bot not updating since 1 h ago", "Kalshi not updating")):
        x = v(name)
        check(f"b. {name}: {verdict}, the one thing to do names it, the strip says '{short}'",
              x.get("verdict") == verdict and todo_has in (x.get("todo") or "") and x.get("short") == short, {k: x.get(k) for k in ("verdict", "todo", "short")})
    check("b. Kalshi not connected yet: grey, not counted (ALL GOOD)", v("kalshi_waiting")["verdict"] == "ALL GOOD" and lv("kalshi_waiting", "kalshi") == "", v("kalshi_waiting"))
    so, ss, sw = v("silent_open"), v("silent_soon"), v("silent_weekend")
    check("c. the PC silent with the market open: NEEDS YOU, turn the PC on, the bots' lines 'last known' and not counted",
          so["verdict"] == "NEEDS YOU" and so["todo"].startswith("Turn the PC on and start the bot: it last checked in 1 h ago") and so["short"] == "PC silent"
          and lv("silent_open", "lit") == "" and next(x for x in so["rows"] if x["id"] == "lit")["text"].startswith("last known"), so)
    check("c. the PC silent 45 min before the open: NEEDS YOU too", ss["verdict"] == "NEEDS YOU", ss["verdict"])
    check("c. the PC silent on a quiet weekend: grey, 'fine if it is off', not a to-do",
          lv("silent_weekend", "pc") == "" and "fine if it is off" in sw["rows"][0]["text"] and sw["verdict"] == "ALL GOOD", sw["rows"][0])
    ns = v("no_signal")
    check("c. no signal from this phone: HEADS UP, check the phone's signal first", ns["verdict"] == "HEADS UP" and "signal" in ns["todo"] and ns["short"] == "No signal from the PC", ns)
    check("c. still loading: CHECKING, no to-do", v("loading")["verdict"] == "CHECKING" and not v("loading")["todo"], v("loading"))
    for name in ("junk_null", "junk_types", "junk_throw"):
        x = v(name)
        check(f"d. {name}: an answer, never an exception", "exception" not in x and x.get("verdict") in ("CHECKING", "ALL GOOD", "HEADS UP", "NEEDS YOU")
              and isinstance(x.get("rows"), list) and "undefined" not in json.dumps(x) and "NaN" not in json.dumps(x), x)
    n = sum(RES)
    print(f"\njarvis system: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
