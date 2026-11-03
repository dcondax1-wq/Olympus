"""Jarvis brain v2 (tools/web_public/jarvis/brain.js, owner 2026-11-01): the hub's voice, as an ES module the shell imports.
Drives the real module in node (it needs no DOM: one process runs every scenario, with a fixed clock, a fake localStorage,
a mocked fetch and a recorded open()) and once in Chromium (a real page), and checks:
  a. the module: one ES module, no imports, Safari 16 syntax (no regex lookbehind), the only network addresses are the
     four smart-mode APIs
  b. today's answers keep their key phrases (tests/test_jarvis_hub.py d and e): status, room, target, P&L, how's blitz,
     blitz room, today's plan, the market, open planner / kalshi, Kalshi not connected / published, kalshi balance
  c. the combined briefing ("Good evening. ..."): the bots, the market and the next session, the plan, Kalshi; and with
     missing data (said to be missing, no invented number)
  d. the market clock: CME NQ Sun 18:00 - Fri 17:00 ET, the daily 17:00-18:00 halt, Thanksgiving / Christmas
  e. follow-ups ("and atlas?", "what about kalshi", "and the target?"), eval progress, "what should I do now", positions,
     waiting, the money goal, Kalshi strategies (best / worst today), Kalshi outcomes in the owner's alert style, the
     shell's own facts (data.js: a slim live view + .raw, liveError, extras), Zenith pages from zenith-mode.js's
     zenithRouteFor (and the local map without it)
  f. speech: short, natural ("up 213 dollars", "6 PM Eastern"), no symbols
  g. the old Jarvis's commands (specs: good morning, mission control, hide my balance, stop, verse / quote of the day ...)
  h. smart mode: off by default; on with a mocked fetch for Groq, Gemini and Anthropic (address, headers, body), the
     fallback to the rule answer on any error, keys kept per provider in localStorage only
  i. junk facts (null, {}, wrong types, a throwing getFacts) never raise
  j. Chromium: the module loads in a real page, answers, and keeps only "jarvis.smart" in localStorage
    python -X utf8 -m tests.test_jarvis_brain      (temp folder + node + one Chromium page; nothing else touched)
"""
from __future__ import annotations

import datetime as dt
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN = os.path.join(ROOT, "tools", "web_public", "jarvis", "brain.js")
ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def at(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp() * 1000)


T_SUN13, T_SUN1930, T_MON8, T_MON10 = at(2026, 11, 1, 13, 0), at(2026, 11, 1, 19, 30), at(2026, 11, 2, 8, 0), at(2026, 11, 2, 10, 0)
T_MON1730, T_WED3, T_FRI1730 = at(2026, 11, 2, 17, 30), at(2026, 11, 4, 3, 0), at(2026, 11, 6, 17, 30)
T_THX14, T_XMAS12 = at(2026, 11, 26, 14, 0), at(2026, 12, 25, 12, 0)


def live(now_ms, age_s=120, **over):
    """The hub test's sample live.json (tests/test_jarvis_hub.py LIVE), stamped age_s before now."""
    L = {"v": 1, "kind": "le-live", "t": now_ms // 1000 - age_s,
         "pc_verdict": {"code": "RUNNING", "label": "RUNNING: bot trading", "level": "good", "reason": "heartbeat fresh"},
         "board": {"running": True,
                   "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2,
                           "room": 1105.6, "to_target": 3726.2, "today_pnl": 212.5, "week_pnl": -224.5, "status": "open"},
                   "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "balance": 24750.4, "floor": 24000.0,
                             "room": 750.4, "to_target": 1749.6, "today_pnl": 0.0, "status": "open"},
                   "blitz": {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "SIM", "balance": 25112.3, "floor": 24500.0,
                             "room": 612.3, "to_target": 1387.7, "today_pnl": 95.25, "week_pnl": 140.0, "status": "open", "off": False,
                             "trades_today": 2, "waiting": "Waiting for the 14:30 check."}}}
    for k, v in over.items():
        L["board"][k] = v
    return L


def kalshi(now_ms, **over):
    """kalshi.json as engine/kalshi_publish.clean() makes it from its SAMPLE (the hub test's published case)."""
    t = now_ms // 1000
    K = {"v": 1, "kind": "kalshi", "name": "Kalshi bot", "mode": "paper", "status": "Watching 12 markets", "running": True, "t": t - 60,
         "balance": 512.34, "today_pnl": 18.5, "week_pnl": 42.1, "total_pnl": 112.34, "note": None,
         "positions": [{"ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes", "contracts": 10,
                        "avg_price": 0.42, "price": 0.55, "value": 5.5, "pnl": 1.3, "closes": "2026-11-02T23:59:00Z"}],
         "trades": [{"t": t - 3600, "ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes", "action": "buy",
                     "contracts": 10, "price": 0.42}],
         "days": [["2026-10-30", 12.4], ["2026-10-31", -3.1], ["2026-11-01", 18.5]], "pub_t": t}
    K.update(over)
    return K


PLANNER = {"day": "2026-11-01",
           "ev": [{"id": "e1", "title": "Gym", "allDay": False, "start": "07:30", "end": "08:30"},
                  {"id": "e2", "title": "Review fills", "allDay": False, "start": "16:15"}],
           "tasks": [{"id": "t1", "title": "Buy BLITZ 25K", "date": "2026-11-01", "done": False},
                     {"id": "t2", "title": "Old", "date": "2026-11-01", "done": True}],
           "projects": [{"id": "p1", "name": "Kalshi bot"}]}
APPS = [{"id": "home", "name": "Jarvis", "url": ""}, {"id": "zenith", "name": "Zenith", "url": "../"},
        {"id": "planner", "name": "Planner", "url": "../planner/"}, {"id": "kalshi", "name": "Kalshi", "url": "../kalshi/"}]


def shell_live(j, cached=False):
    """The shell's view of live.json (tools/web_public/jarvis/data.js liveView / slim): the cards at the top, the full
    live.json as .raw; the copy saved on the phone has no .raw and cached: true."""
    b = j.get("board") or {}
    bz = b.get("blitz") if isinstance(b.get("blitz"), dict) else j.get("blitz") if isinstance(j.get("blitz"), dict) else None
    v = {"lit": b.get("lit"), "atlas": b.get("atlas"), "blitz": bz, "verdict": j.get("pc_verdict"), "running": b.get("running"), "t": j.get("t"),
         "trades": [], "health": [], "lines": [{"level": x.get("level"), "text": x.get("text")} for x in (b.get("lines") or [])[:4] if x.get("text")],
         "level": b.get("level"), "price": j.get("price"), "last_signal": None}
    return {**v, "cached": True, "raw": None, "err": "Failed to fetch"} if cached else {**v, "raw": j, "err": None}


def facts(now_ms, **over):
    f = {"now": now_ms, "market": {"open": False, "text": "NQ market closed · opens Sunday 6:00 PM ET"}, "live": live(now_ms),
         "kalshi": None, "kalshiState": "waiting", "planner": PLANNER, "apps": APPS}
    f.update(over)
    return f


RUNNER = r"""
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [brainPath, scenPath] = process.argv.slice(2);
const mod = await import(pathToFileURL(brainPath).href);
const D = await import(pathToFileURL(brainPath.replace(/brain\.js$/, 'data.js')).href);      // the shell's MFFU rules and System view
const scen = JSON.parse(fs.readFileSync(scenPath, 'utf8'));
const out = { exports: Object.keys(mod).sort() };
const NAV = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
for (const sc of scen) {
  if (sc.withShell) { sc.facts = { ...sc.facts, mffu: D.MFFU_RULES }; sc.facts.system = D.systemStatus(sc.facts); }
  if (NAV) Object.defineProperty(globalThis, 'navigator', NAV);
  if (sc.offline) Object.defineProperty(globalThis, 'navigator', { value: { onLine: false }, configurable: true });
  const store = new Map(Object.entries(sc.storage || {}));
  const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
  const calls = [], opened = [];
  let cur = sc.facts;
  const plans = Array.isArray(sc.fetch) ? sc.fetch : [sc.fetch || {}];
  const fetchMock = async (url, init) => {
    calls.push({ url, method: init.method, headers: init.headers, body: JSON.parse(init.body) });
    const p = plans[Math.min(calls.length - 1, plans.length - 1)];
    if (p.throw) throw new TypeError('Failed to fetch');
    if (p.hang) return new Promise((ok, no) => { const sg = init.signal; if (sg) sg.addEventListener('abort', () => { const e = new Error('aborted'); e.name = 'AbortError'; no(e); }); });
    const status = p.status || 200;
    return { ok: status < 400, status, json: async () => p.json, text: async () => JSON.stringify(p.json || {}) };
  };
  const getFacts = sc.factsMode === 'throw' ? () => { throw new Error('boom'); } : sc.factsMode === 'null' ? () => null
    : sc.factsMode === 'promise' ? () => Promise.resolve(cur) : () => cur;
  const brain = mod.createBrain({ getFacts, open: (a, r) => opened.push([a, r === undefined ? null : r]), now: sc.now ? () => sc.now : undefined, storage, fetch: fetchMock, openDelay: 0,
    ...(sc.opts || {}), ...(sc.routeJunk ? { routeFor: () => 'javascript:alert(1)' } : {}) });
  const res = [];
  for (const st of sc.steps) {
    try {
      if (st.facts) { cur = st.facts; res.push({}); }
      else if (st.shellFacts) {          // the shell's next getFacts(): the marks this brain saved, counted by data.js
        const mt = JSON.parse(store.get('jarvis.manualTrades') || '{}');
        cur = { ...cur, manualTrades: mt, live: D.withManualTrades(cur.live, mt, sc.now) }; cur.system = D.systemStatus(cur); res.push({ marks: mt });
      }
      else if (st.ask !== undefined) res.push(await brain.ask(st.ask, st.opt));
      else if (st.briefing) res.push(await brain.briefing());
      else if (st.suggestions) res.push({ list: brain.suggestions() });
      else if (st.setSmart) res.push({ smart: brain.setSmart(st.setSmart) });
      else if (st.smart) res.push({ smart: brain.smart });
      else if (st.idle) res.push({ text: brain.idle() });
      else if (st.headline) res.push({ headline: brain.headline(), priorities: brain.priorities() });
      else if (st.timed !== undefined) { const t0 = Date.now(); const r = await brain.ask(st.timed); res.push({ ...r, ms: Date.now() - t0 }); }
      else if (st.outcomes) res.push({ list: mod.outcomeAlerts(st.outcomes[0], st.outcomes[1]) });
    } catch (e) { res.push({ exception: String((e && e.stack) || e) }); }
  }
  await new Promise((r) => setTimeout(r, 10));
  out[sc.name] = { res, calls, opened, storage: Object.fromEntries(store) };
}
process.stdout.write(JSON.stringify(out));
"""


T_MON1958 = at(2026, 11, 2, 19, 58)
TONIGHT_Q = ("what should I do today", "brief me", "status", "how's my PC", "eval pace", "why no trade", "when does it trade next", "last trade",
             "how much did I make this month", "what is the MFFU inactivity rule", "mffu payout rules", "whats the daly loss limit rule", "deals",
             "how are the bots", "what did the bots learn", "kalshi", "is zlarior trading", "pnl this week")


def tonight(now_ms, q_lit=5, q_atlas=5, ram=95, running=True):
    """live.json as the shell sees it tonight: Zlarior room $1,106 / $3,726 to go, ATLAS $746 / $1,754, both 5 days with no trade."""
    t = now_ms // 1000 - 60
    card = lambda **o: {"status": "open", "today_pnl": 0.0, "week_pnl": 0.0, "trades_today": 0, **o}      # noqa: E731
    ph = {"level": "bad" if ram >= 95 else "ok", "cpu": 31, "ram": ram,
          "lines": [{"key": "ram", "label": "Memory (RAM)", "level": "bad" if ram >= 95 else "ok", "text": f"RAM {ram}% in use (3.4 of 3.6 GB): close other apps (browser tabs)"}]}
    lv = {"t": t, "running": running, "verdict": {"level": "good", "label": "TRADING YOUR EVAL", "reason": "heartbeat fresh"},
          "lit": card(name="Zlarior", plan="MFFU Builder 50K", balance=49273.8, floor=48168.2, room=1105.6, room_frac=0.55, to_target=3726.2, profit=-726.2,
                      session=6, sessions=10, quiet_days=q_lit, waiting="Waiting for the 02:00 ET window (Asia range building).",
                      days=[["2026-10-27", -400.0], ["2026-10-28", -326.2]]),
          "atlas": card(name="ATLAS", plan="MFFU Builder 25K", balance=24746.0, floor=24000.0, room=746.0, room_frac=0.746, to_target=1754.0, profit=-254.0,
                        session=5, sessions=10, quiet_days=q_atlas, waiting="All 3 members are outside their hours. Next: EMA at Tue 09:35 ET."),
          "blitz": {"off": True, "status": "off"}, "health": [{"key": "age_1m_s", "value": "14 s", "ok": True}, {"key": "nt", "ok": True}],
          "pc_health": ph, "lines": [],
          "trades": [{"acct": "lit", "side": "LONG", "qty": 4, "exit": "stop", "usd": -326.2, "r": -1.0, "entry_t": at(2026, 10, 28, 10, 5) // 1000, "day": "2026-10-28"}],
          "money": {"next": {"kind": "buy", "text": "Buy 2 LucidPro 50K evals (about $231): code VIBES"}},
          "mind": {"regime": {"label": "range, low volatility", "why": "VXN 18, inside last week's range"},
                   "reviews": [{"bot": "lit", "grade": "B", "lesson": "Entered on the 1m CISD before the 5m confirmed: wait for the 5m close."}]}}
    return {"now": now_ms, "market": {"open": True, "rth": False, "next": {"mins": 1262}}, "live": lv, "kalshi": None, "kalshiState": "waiting",
            "planner": None, "apps": APPS}


def S(name, steps, now=T_SUN13, f=None, **kw):
    return {"name": name, "now": now, "facts": f if f is not None else facts(now), "steps": steps, **kw}


def ask(*qs):
    return [{"ask": q} for q in qs]


def scenarios():
    K13 = kalshi(T_SUN13)
    STRATS = [{"name": "15-min favourites", "mode": "live", "running": True, "today_pnl": -1.1, "total_pnl": 20.0, "trades": 41, "wins": 27, "losses": 14},
              {"name": "Late favourite (BTC hourly)", "mode": "live", "running": True, "today_pnl": 0.4, "total_pnl": 5.5, "trades": 12, "wins": 9, "losses": 3},
              {"name": "Gold 5 PM", "mode": "live", "running": True, "today_pnl": 3.2, "total_pnl": 8.0, "trades": 9, "wins": 6, "losses": 3}]
    bad_line = {"level": "bad", "kind": "feed", "text": "FEED STALE: NinjaTrader bars are old, new entries blocked. Fix: NinjaTrader: right-click the MNQ 5-minute chart > Reload NinjaScript"}
    lit2 = {**live(T_SUN13)["board"]["lit"], "session": 3, "sessions": 10, "profit": -726.2,
            "waiting": "Waiting for a sweep of a LIT level", "window": {"open": False, "text": "next entry window Mon 02:00-15:30 ET"},
            "position": {"side": "long", "qty": 3, "entry": 20100.25, "stop": 20080, "target": 20160}}
    lit_missing = {k: v for k, v in live(T_SUN13)["board"]["lit"].items() if k not in ("to_target", "today_pnl")}
    off_live = live(T_SUN13)
    off_live["board"].pop("blitz")
    off_live["blitz"] = {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "OFF", "off": True, "status": "off", "room": None}
    money = {"title": "Road to $10K / Stingray 3LT", "next": {"kind": "buy", "text": "Buy 2 MFFU Builder 25K (about $86): the Start page has the steps."},
             "goals": [{"k": "month", "title": "$10K month by Feb 2027", "sentence": "November so far: $0 of $10,000 (0%)."}]}
    junk_f = {"now": "not a date", "market": 7, "live": {"board": {"lit": "x", "atlas": {"room": "abc", "today_pnl": None}, "blitz": 5, "lines": "x"},
              "pc_verdict": "bad", "t": "soon", "money": [1]}, "kalshi": {"positions": "x", "balance": "lots", "strategies": [None, 3, {"name": 7}], "days": [5, [None]]},
              "kalshiState": 9, "planner": {"ev": [None, 5, {"title": 7, "start": "zz"}], "tasks": "x", "projects": [None]}, "apps": "x"}
    groq_ok = {"json": {"choices": [{"message": {"role": "assistant", "content": "Forty-two, sir. The facts do not cover the rest."}, "finish_reason": "stop"}]}}
    anth_ok = {"json": {"content": [{"type": "text", "text": "Claude here: nothing in the facts says so."}], "stop_reason": "end_turn"}}
    gem_ok = {"json": {"candidates": [{"content": {"parts": [{"text": "Gemini here: that is missing from the facts."}]}, "finishReason": "STOP"}]}}
    Q = "what is the meaning of life"
    settled = {**K13, "today_pnl": 19.76, "trades": K13["trades"] + [{"t": T_SUN13 // 1000 - 30, "ticker": "KXBTCD-26NOV0113-T80499.99",
                                                                        "title": "Bitcoin above $80,500 at 1 PM ET Nov 1", "side": "yes", "action": "buy", "contracts": 3, "price": 0.58, "pnl": 1.26}]}
    return [
        S("today_waiting", ask("How are the bots?", "how much room do I have", "how far to target", "what's on today", "is the market open",
                               "today's p&l", "how's blitz", "blitz room", "open planner", "how's kalshi", "open kalshi", "help", "hi", "what time is it")),
        S("today_kalshi", ask("how's kalshi", "kalshi balance", "kalshi positions"), f=facts(T_SUN13, kalshi=K13, kalshiState="ok")),
        S("brief_full", [{"briefing": True}, {"suggestions": True}], now=T_SUN1930,
          f=facts(T_SUN1930, kalshi=kalshi(T_SUN1930, strategies=STRATS), kalshiState="ok", planner={**PLANNER})),
        S("sugg_first", [{"suggestions": True}], f=facts(T_SUN13, kalshi=kalshi(T_SUN13), kalshiState="ok")),
        S("brief_missing", [{"briefing": True}], now=T_SUN1930, f={"now": T_SUN1930, "live": None, "kalshi": None, "kalshiState": "waiting", "planner": None, "apps": []}),
        S("brief_error", [{"briefing": True}], now=T_SUN13, f={"live": None, "liveState": "error", "kalshi": None, "kalshiState": "error", "planner": None}),
        S("brief_closed", [{"briefing": True}]),
        S("mkt_sun13", ask("when does the market open", "any holidays coming up")),
        S("mkt_mon10", ask("is the market open", "when does the market open"), now=T_MON10, f=facts(T_MON10)),
        S("mkt_wed3", ask("is the market open"), now=T_WED3, f=facts(T_WED3)),
        S("mkt_halt", ask("is the market open"), now=T_MON1730, f=facts(T_MON1730)),
        S("mkt_thx", ask("is the market open"), now=T_THX14, f=facts(T_THX14)),
        S("mkt_xmas", ask("when does the market open"), now=T_XMAS12, f=facts(T_XMAS12)),
        S("mkt_fri", ask("is the market open"), now=T_FRI1730, f=facts(T_FRI1730)),
        S("follow", ask("how's blitz", "and atlas?", "blitz room", "and atlas", "today's p&l", "what about kalshi",
                        "how much room on zlarior", "and the target?"), f=facts(T_SUN13, kalshi=K13, kalshiState="ok")),
        S("bare_atlas", ask("atlas", "how are the bots doing today", "how's today looking")),
        S("eval_pos", ask("how's the eval", "are we in a trade", "what is zlarior waiting for", "how's my money goal", "what should I do now"),
          f=facts(T_SUN13, live={**live(T_SUN13, lit=lit2), "money": money})),
        S("more_intents", ask("where is nq", "how much can I lose today", "is the pc on", "is nq open", "how many trades today", "what's my balance"),
          now=T_MON10, f=facts(T_MON10, live={**live(T_MON10, lit={**live(T_MON10)["board"]["lit"], "dll": 1000.0, "dll_used": 212.0, "trades_today": 1, "max_day": 1}),
                                                 "price": 25123.5}, kalshi=kalshi(T_MON10), kalshiState="ok")),
        S("shell_facts", ask("how are the bots", "what should I do now", "how's my money goal", "where is nq", "verse of the day", "quote of the day",
                             "bitcoin price", "crypto", "what can't you do"), now=T_MON10,
          f=facts(T_MON10, live=shell_live({**live(T_MON10, lines=[bad_line], level="bad"), "money": money, "price": 25123.5}), liveError=None,
                  extras={"verse": ["The hand of the diligent shall bear rule: but the slothful shall be under tribute.", "Proverbs 12:24"],
                          "quote": ["Risk comes from not knowing what you're doing.", "Warren Buffett"],
                          "crypto": {"t": T_MON10 // 1000 - 300, "BTC": {"usd": 81234.5, "chg": 1.234}, "ETH": {"usd": 2650.25, "chg": -0.5}, "SOL": None}})),
        S("shell_cached", ask("how are the bots", "bitcoin price"), now=T_MON10, f=facts(T_MON10, live=shell_live(live(T_MON10, age_s=3 * 3600), cached=True), liveError="Failed to fetch")),
        S("shell_error", ask("how are the bots") + [{"briefing": True}], f=facts(T_SUN13, live=None, liveError="HTTP 500")),
        S("missing_fields", ask("how are the bots", "how far is zlarior from the target"), f=facts(T_SUN13, live=live(T_SUN13, lit=lit_missing))),
        S("blitz_off", ask("how are the bots", "how's blitz"), f=facts(T_SUN13, live=off_live)),
        S("now_plain", ask("what should I do now")),
        S("now_bad", ask("what should I do now"), now=T_MON10, f=facts(T_MON10, live=live(T_MON10, lines=[bad_line], level="bad"))),
        S("now_stale", ask("what should I do now", "how are the bots"), now=T_MON10, f=facts(T_MON10, live=live(T_MON10, age_s=3 * 3600))),
        S("now_kalshi_setup", ask("what should I do now", "how's kalshi"), f=facts(T_SUN13, planner={"day": "2026-11-01", "ev": [], "tasks": [], "projects": []})),
        S("kalshi_states", [{"ask": "how's kalshi"}, {"facts": facts(T_SUN13, kalshiState="error")}, {"ask": "how's kalshi"},
                            {"facts": facts(T_SUN13, kalshiState="")}, {"ask": "how's kalshi"}]),
        S("kalshi_strats", ask("how's kalshi", "kalshi strategies", "kalshi yesterday"), f=facts(T_SUN13, kalshi=kalshi(T_SUN13, strategies=STRATS), kalshiState="ok")),
        S("outcomes", [{"outcomes": [K13, settled]}, {"outcomes": [None, settled]}, {"outcomes": [settled, settled]}]),
        S("old_jarvis", ask("good morning", "hide my balance", "how are the bots", "show my balance", "stop", "mission control", "open liquidity",
                            "remind me in 20 minutes to call mom", "add buy milk to my todo", "verse of the day", "quote of the day", "what's new",
                            "what's the weather tomorrow", "open tradingview", "place a trade on nq", "who are you", "what can't you do",
                            "open blitz", "news", "good day") + [{"idle": True}], now=T_MON8, f=facts(T_MON8, kalshi=kalshi(T_MON8), kalshiState="ok")),
        S("phrasings", ask("how close are we to passing", "where's nq", "is the bot trading my eval", "who made you", "flatten everything", "stop the bot",
                           "take me home", "anything overdue", "what's up", "should i buy another eval", "good evening"), now=T_MON8, f=facts(T_MON8)),
        S("smart_decision", [{"setSmart": {"key": "gsk_FAKE", "on": True}}] + ask("should i buy another eval"), fetch=groq_ok),
        S("zroutes", ask("atlas trades", "holodeck", "open zenith", "open settings", "blitz rules", "open the deck", "how many atlas trades")),
        S("zroutes_local", ask("atlas trades", "holodeck", "open blitz", "open the deck", "zlarior brain"), opts={"zenithRoutes": False}),
        S("zroutes_junk", ask("open blitz", "open the chart"), routeJunk=True),
        S("smart_off", ask(Q) + [{"smart": True}]),
        S("smart_groq", [{"setSmart": {"key": "gsk_FAKE_TEST_KEY", "on": True}}] + ask(Q, "How are the bots?") + [{"smart": True}], fetch=groq_ok),
        S("smart_anth", [{"setSmart": {"provider": "anthropic", "key": "sk-ant-FAKE-TEST", "on": True}}] + ask("tell me something interesting"), fetch=anth_ok),
        S("smart_gem", [{"setSmart": {"provider": "gemini", "key": "AIza-FAKE-TEST", "on": True}}] + ask(Q), fetch=gem_ok),
        S("smart_speech", [{"setSmart": {"key": "gsk_FAKE", "on": True}}] + ask(Q),
          fetch={"json": {"choices": [{"message": {"content": "Zlarior is +$213 today, room $1,106, and Kalshi made $18.50."}, "finish_reason": "stop"}]}}),
        S("smart_detect", [{"setSmart": {"key": "sk-ant-FAKE-AUTO", "model": "openai/gpt-oss-120b", "on": True}}] + ask(Q) + [{"setSmart": {"key": "AIza-FAKE-AUTO"}},
                           {"setSmart": {"model": "openai/gpt-oss-20b"}}, {"setSmart": {"key": "", "on": False}}], fetch=anth_ok),
        S("smart_500", [{"setSmart": {"key": "gsk_FAKE", "on": True}}] + ask(Q), fetch={"status": 500, "json": {"error": {"message": "overloaded"}}}),
        S("smart_throw", [{"setSmart": {"key": "gsk_FAKE", "on": True}}] + ask(Q), fetch={"throw": True}),
        S("smart_401", [{"setSmart": {"provider": "anthropic", "key": "sk-ant-BAD", "on": True}}] + ask(Q),
          fetch={"status": 401, "json": {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}}),
        S("smart_refusal", [{"setSmart": {"provider": "anthropic", "key": "sk-ant-FAKE", "on": True}}] + ask(Q),
          fetch={"json": {"content": [], "stop_reason": "refusal"}}),
        S("smart_retry", [{"setSmart": {"provider": "anthropic", "key": "sk-ant-FAKE", "on": True}}] + ask(Q),
          fetch=[{"status": 400, "json": {"error": {"message": "thinking.type.between_tools is not supported"}}}, anth_ok]),
        S("smart_keys", [{"setSmart": {"key": "gsk_FAKE_ONE", "on": True}}, {"setSmart": {"provider": "gemini", "key": "AIza-FAKE-TWO"}},
                         {"setSmart": {"provider": "groq", "depth": "auto"}}] + ask("should I start a second business this year") + [{"smart": True}], fetch=groq_ok),
        S("smart_stored", [{"smart": True}] + ask(Q), storage={"jarvis.smart": json.dumps({"v": 2, "on": True, "provider": "groq", "depth": "quick",
                                                                                        "keys": {"groq": "gsk_STORED_FAKE"}, "models": {}})}, fetch=groq_ok),
        S("junk_null", ask("How are the bots?", "what's on today", "how's kalshi") + [{"briefing": True}, {"suggestions": True}], f=None, factsMode="null"),
        S("junk_throw", ask("How are the bots?", "what should I do now") + [{"briefing": True}], factsMode="throw"),
        S("junk_empty", ask("How are the bots?", "is the market open", "and atlas?") + [{"briefing": True}], f={}),
        S("junk_types", ask("How are the bots?", "how much room", "today's p&l", "how's kalshi", "kalshi strategies", "what's on today",
                            "what should I do now", "how's the eval", "and blitz?", "open zenith", "when does the market open", 12345, None)
          + [{"briefing": True}, {"suggestions": True}], now=None, f=junk_f),
        S("junk_promise", ask("How are the bots?"), factsMode="promise"),
        # the System view (2026-11-02): data.js systemStatus hands the brain one verdict and one line per system
        S("system", ask("status", "is everything ok?", "how's the pc", "all good", "how are the bots") + [{"suggestions": True}],
          f=facts(T_SUN13, live={**live(T_SUN13), "pc_health": PC_HEALTH}, system=SYSTEM_WARN, kalshi=K13, kalshiState="ok")),
        S("system_good", ask("status", "is everything running"), f=facts(T_SUN13, system=SYSTEM_GOOD)),
        S("system_none", ask("status", "how's the pc")),
        S("system_junk", ask("status", "is everything ok", "how's the pc"),
          f=facts(T_SUN13, live={**live(T_SUN13), "pc_health": {"cpu": "x", "lines": [None, 5, {"level": "bad"}]}}, system={"verdict": "NEEDS YOU", "rows": [None, 3, {"name": 7}, {"id": "pc"}]})),
        # tonight (2026-11-02 7:58 PM ET): both evals quiet 5 days, the PC's RAM at 95%, the market open overnight, Kalshi not linked
        S("tonight", [{"headline": True}] + ask(*TONIGHT_Q), now=T_MON1958, f=tonight(T_MON1958), withShell=True),
        S("tonight_q6", [{"headline": True}] + ask("what should I do", "status"), now=T_MON1958, f=tonight(T_MON1958, q_lit=6), withShell=True),
        S("tonight_q7", [{"headline": True}] + ask("what should I do"), now=T_MON1958, f=tonight(T_MON1958, q_lit=7, q_atlas=3), withShell=True),
        S("tonight_calm", [{"headline": True}] + ask("what should I do"), now=T_MON1958, f=tonight(T_MON1958, q_lit=1, q_atlas=2, ram=50), withShell=True),
        S("tonight_stopped", ask("what should I do"), now=T_MON1958, f=tonight(T_MON1958, running=False), withShell=True),
        # the owner placed his keep-alive trades by hand (2026-11-02 ~10 PM ET): said once, the day-5 warning goes
        S("manual", [{"headline": True}] + ask("did I trade today", "I traded on both") + [{"shellFacts": True}, {"headline": True}] + ask("what should I do", "status"),
          now=T_MON1958, f=tonight(T_MON1958), withShell=True),
        S("manual_atlas", ask("I placed my keep-alive trade on ATLAS") + [{"shellFacts": True}, {"headline": True}], now=T_MON1958, f=tonight(T_MON1958), withShell=True),
        S("manual_plain", ask("I traded") + [{"shellFacts": True}, {"headline": True}], now=T_MON1958, f=tonight(T_MON1958, q_lit=6, q_atlas=2), withShell=True),
        S("smart_timeout", [{"setSmart": {"key": "gsk_FAKE", "on": True}}, {"timed": "blorp zzz what is the meaning of it all"}], now=T_MON1958, f=tonight(T_MON1958),
          withShell=True, fetch={"hang": True}),
        S("smart_offline", [{"setSmart": {"key": "gsk_FAKE", "on": True}}, {"timed": "blorp zzz what is the meaning of it all"}], now=T_MON1958, f=tonight(T_MON1958),
          withShell=True, offline=True, fetch=groq_ok),
        S("smart_grounded", [{"setSmart": {"key": "gsk_FAKE", "on": True}}] + ask("blorp zzz what is the meaning of it all"), now=T_MON1958, f=tonight(T_MON1958),
          withShell=True, fetch=groq_ok),
    ]


PC_HEALTH = {"t": 0, "level": "warn", "cpu": 23, "ram": 89, "lines": [
    {"key": "cpu", "label": "CPU", "level": "ok", "text": "CPU 23%"},
    {"key": "ram", "label": "Memory (RAM)", "level": "warn", "text": "RAM 89% in use (3.2 of 3.6 GB): close other apps (browser tabs)"},
    {"key": "nt", "label": "NinjaTrader", "level": "ok", "text": "NinjaTrader running, 900 MB"}]}
SYSTEM_WARN = {"verdict": "HEADS UP", "level": "warn", "todo": "PC: RAM 89% in use (3.2 of 3.6 GB): close other apps (browser tabs)", "todoApp": "zenith", "rows": [
    {"id": "pc", "name": "PC", "sub": "bot server · NinjaTrader", "app": "zenith", "level": "warn", "value": "CPU 23% · RAM 89%",
     "text": "Memory (RAM) to watch · checked in 2 min ago · feed 12 s", "todo": "PC: RAM 89% in use (3.2 of 3.6 GB): close other apps (browser tabs)"},
    {"id": "lit", "name": "Zlarior", "sub": "50K eval", "app": "zenith", "level": "ok", "value": "+$213", "text": "RUNNING: bot trading · room $1,106", "todo": ""},
    {"id": "atlas", "name": "ATLAS", "sub": "25K", "app": "zenith", "level": "ok", "value": "$0", "text": "open · room $750", "todo": ""},
    {"id": "blitz", "name": "BLITZ", "sub": "25K", "app": "zenith", "level": "", "value": "OFF", "text": "paper only until its own account is set up", "todo": ""},
    {"id": "kalshi", "name": "Kalshi", "sub": "its own server", "app": "kalshi", "level": "ok", "value": "+$18.50", "text": "Running · balance $512.34", "todo": ""},
    {"id": "planner", "name": "Planner", "sub": "your day", "app": "planner", "level": "ok", "value": "4:15 PM", "text": "Review fills · 1 task open", "todo": ""}]}
SYSTEM_GOOD = {**SYSTEM_WARN, "verdict": "ALL GOOD", "level": "ok", "todo": "", "todoApp": "",
               "rows": [{**SYSTEM_WARN["rows"][0], "level": "ok", "text": "checked in 2 min ago · feed 12 s", "todo": ""}] + SYSTEM_WARN["rows"][1:]}


def run_node(tmp):
    node = shutil.which("node")
    if not node:
        return None, "node not found"
    sc = scenarios()
    rp, sp = os.path.join(tmp, "runner.mjs"), os.path.join(tmp, "scen.json")
    open(rp, "w", encoding="utf-8").write(RUNNER)
    open(sp, "w", encoding="utf-8").write(json.dumps(sc, ensure_ascii=False))
    r = subprocess.run([node, rp, BRAIN, sp], capture_output=True, text=True, timeout=120)
    if r.returncode:
        return None, r.stderr[-2000:]
    return json.loads(r.stdout), None


BAD = re.compile(r"undefined|NaN|\[object|null\b|—")


def clean(s):
    return isinstance(s, str) and s.strip() != "" and not BAD.search(s)


def part_a():
    src = open(BRAIN, encoding="utf-8").read()
    check("a. brain.js exists and exports createBrain (named and default)", "export function createBrain(" in src and "export default createBrain" in src)
    check("a. no imports, no lookbehind regex (Safari 16), no class static blocks", not re.search(r"^\s*import\s", src, re.M) and "(?<=" not in src
          and "(?<!" not in src and "static {" not in src)
    urls = set(re.findall(r"https?://[^\s'\"`]+", src))
    check("a. the only network addresses are the four smart-mode APIs (Groq, Gemini, OpenRouter, Anthropic)",
          urls <= {"https://api.groq.com/openai/v1/chat/completions", "https://generativelanguage.googleapis.com/v1beta/models/",
                   "https://openrouter.ai/api/v1/chat/completions", "https://api.anthropic.com/v1/messages"}, urls)
    check("a. no control characters in the source", not any(ord(c) < 32 and c not in "\n\t" for c in src))


def part_node(O):
    g = lambda n: O[n]["res"]                                          # noqa: E731
    t = lambda n, i: (O[n]["res"][i] or {}).get("text") or ""        # noqa: E731
    sp = lambda n, i: (O[n]["res"][i] or {}).get("speak") or ""      # noqa: E731
    check("a. module exports createBrain, default, outcomeAlerts", {"createBrain", "default", "outcomeAlerts"} <= set(O["exports"]), O["exports"])
    # b. today's phrasings (tests/test_jarvis_hub.py d / e)
    a1, a2, a3, a4, a5, a8, a9, a10, a6, a7, a7b, hp, hi, tm = (t("today_waiting", i) for i in range(14))
    check("b. status: the verdict, Zlarior and ATLAS numbers", "RUNNING" in a1 and "Zlarior 50K" in a1 and "$1,106" in a1 and "ATLAS 25K" in a1, a1)
    check("b. room", "$1,106" in a2 and "$750" in a2, a2)
    check("b. target", "$3,726" in a3 and "$1,750" in a3, a3)
    check("b. today's plan from the Planner (done tasks left out)", "Gym" in a4 and "Buy BLITZ 25K" in a4 and "Old" not in a4 and "7:30 AM" in a4, a4)
    check("b. the market", "NQ market" in a5, a5)
    check("b. status / room / target carry BLITZ next to Zlarior and ATLAS",
          "BLITZ 25K" in a1 and "$612" in a1 and "BLITZ 25K: drawdown left $612" in a2 and "BLITZ: $1,388 to the target" in a3, (a1, a2, a3))
    check("b. P&L: Zlarior, ATLAS and BLITZ (today and this week)", "Zlarior today +$213" in a8 and "ATLAS today" in a8 and "BLITZ today +$95, this week +$140" in a8, a8)
    r9 = g("today_waiting")[6]
    check("b. 'how's blitz' answers BLITZ alone (not 'Opening Zenith')", "BLITZ 25K: today +$95, room $612, $1,388 to target, 2 trades today" in a9
          and "Zlarior" not in a9 and "Opening" not in a9 and not r9.get("open"), a9)
    check("b. 'blitz room' answers BLITZ's room alone", "BLITZ 25K: drawdown left $612" in a10 and "Zlarior" not in a10, a10)
    r6 = g("today_waiting")[8]
    check("b. 'open planner' switches to the Planner (reply.open and the shell's open())", "Opening Planner" in a6 and r6.get("open") == "planner"
          and ["planner", None] in O["today_waiting"]["opened"], (a6, O["today_waiting"]["opened"]))
    check("b. Kalshi not published ('waiting'): not connected yet, its own server, the kalshi-server setup line, never 'PC'",
          "not connected yet" in a7 and "own server" in a7 and "kalshi-server" in a7 and "setup line" in a7 and "PC" not in a7, a7)
    check("b. 'open kalshi' opens the Kalshi page", "Opening Kalshi" in a7b and g("today_waiting")[10].get("open") == "kalshi", a7b)
    check("b. help names the commands", 'open planner' in hp and "brief me" in hp, hp)
    check("b. hello: a greeting and the market line", re.match(r"^Good (morning|afternoon|evening)", hi) and "NQ market" in hi, hi)
    check("b. the time, in ET", "1:00 PM ET" in tm and "Sunday" in tm, tm)
    k1, k2, k3 = (t("today_kalshi", i) for i in range(3))
    check("b. 'how's kalshi' answers from the published numbers (balance, today, week, positions)",
          "Kalshi (PAPER): running, balance $512.34, today +$18.50, this week +$42.10, 1 open position" in k1
          and "NYC high 58-59°F on Nov 2: YES x10, P&L +$1.30" in k1 and not g("today_kalshi")[0].get("open"), k1)
    check("b. 'kalshi balance' answers instead of switching", "balance $512.34" in k2 and not g("today_kalshi")[1].get("open"), k2)
    check("b. 'kalshi positions' lists the position", "1 open position" in k3 and "NYC high" in k3, k3)
    # c. the briefing
    b = g("brief_full")[0]
    bt = b.get("text", "")
    check("c. briefing opens 'Good evening.' with the date and time in ET", bt.startswith("Good evening. Sunday, November 1, 7:30 PM ET."), bt[:80])
    check("c. briefing: Zlarior, ATLAS and BLITZ with today, room and to target",
          "Zlarior 50K: today +$213, room $1,106, $3,726 to target" in bt and "ATLAS 25K: today $0, room $750, $1,750 to target" in bt
          and "BLITZ 25K: today +$95, room $612, $1,388 to target" in bt and "RUNNING: bot trading" in bt, bt)
    check("c. briefing: the market and the next session", "Market: NQ market open · overnight session; next halt tomorrow 5:00 PM ET." in bt, bt)
    check("c. briefing: today's plan and open tasks", "Plan:" in bt and "Gym" in bt and "1 open task: Buy BLITZ 25K" in bt, bt)
    check("c. briefing: Kalshi balance, today, positions, yesterday, best / worst strategy",
          "Kalshi (PAPER): running, balance $512.34, today +$18.50" in bt and "1 open position" in bt and "Yesterday −$3.10" in bt
          and "Best today: Gold 5 PM +$3.20; worst: 15-min favourites −$1.10" in bt, bt)
    check("c. briefing speech: natural numbers, no symbols", "up 213 dollars" in b.get("speak", "") and "$" not in b.get("speak", "")
          and "Good evening." in b.get("speak", "") and "\n" not in b.get("speak", ""), b.get("speak"))
    check("c. briefing cards: one per bot plus Kalshi", [c.get("title") for c in b.get("cards", [])] == ["Zlarior 50K", "ATLAS 25K", "BLITZ 25K", "Kalshi"], b.get("cards"))
    bm = g("brief_missing")[0].get("text", "")
    check("c. briefing with missing data says what is missing, invents nothing",
          bm.startswith("Good evening.") and "no live feed yet" in bm and "cannot see your Planner" in bm and "not connected yet (open your kalshi-server chat" in bm
          and "$" not in bm and clean(bm), bm)
    be = g("brief_error")[0].get("text", "")
    check("c. briefing with unreachable feeds", "cannot reach the live feed" in be and "Kalshi: I cannot reach its feed" in be, be)
    bc = g("brief_closed")[0].get("text", "")
    check("c. briefing while closed names the next session", "Market: NQ market closed · opens today 6:00 PM ET (in 5 h)." in bc, bc)
    sg = g("brief_full")[1].get("list")
    check("c. suggestions: 4-6 short phrases", isinstance(sg, list) and 4 <= len(sg) <= 6 and all(isinstance(x, str) and x for x in sg) and "How are the bots?" in sg, sg)
    sf = g("sugg_first")[0].get("list")
    check("c. suggestions before any question already follow the facts (the plan, Kalshi, the next open)",
          isinstance(sf, list) and "What's on today?" in sf and "How's Kalshi?" in sf and "When does the market open?" in sf, sf)
    # d. the market clock
    m1, m2 = t("mkt_sun13", 0), t("mkt_sun13", 1)
    check("d. Sunday 13:00: closed for the weekend, opens today 6:00 PM ET in 5 h", "NQ market closed · opens today 6:00 PM ET (in 5 h)" in m1
          and "6 PM Eastern, in 5 hours" in sp("mkt_sun13", 0), (m1, sp("mkt_sun13", 0)))
    check("d. the coming CME holiday hours", "Thu Nov 26: early close 1:00 PM (Thanksgiving)" in m2 and "Fri Nov 27: early close 1:15 PM" in m2
          and "Fri Dec 25: closed (Christmas)" in m2, m2)
    check("d. Monday 10:00: open, regular session", "NQ market open · regular session" in t("mkt_mon10", 0), t("mkt_mon10", 0))
    check("d. 'when does it open' while open: open now, next halt 5 PM, back 6 PM", "It is open now." in t("mkt_mon10", 1)
          and "Next halt today 5:00 PM ET, back today 6:00 PM ET" in t("mkt_mon10", 1), t("mkt_mon10", 1))
    check("d. Wednesday 03:00: open, overnight session", "NQ market open · overnight session" in t("mkt_wed3", 0), t("mkt_wed3", 0))
    check("d. Monday 17:30: the daily halt, opens 6 PM", "NQ market closed · daily halt · opens today 6:00 PM ET" in t("mkt_halt", 0), t("mkt_halt", 0))
    check("d. Thanksgiving 14:00: early close at 1 PM, opens 6 PM", "Thanksgiving early close at 1:00 PM ET · opens today 6:00 PM ET" in t("mkt_thx", 0), t("mkt_thx", 0))
    check("d. Christmas: closed all day, opens Sunday 6 PM", "NQ market closed · Christmas · opens Sunday 6:00 PM ET" in t("mkt_xmas", 0), t("mkt_xmas", 0))
    check("d. Friday 17:30: closed for the weekend, opens Sunday 6 PM", "opens Sunday 6:00 PM ET" in t("mkt_fri", 0), t("mkt_fri", 0))
    # e. follow-ups and the other intents
    f = [t("follow", i) for i in range(8)]
    check("e. follow-up 'and atlas?' after 'how's blitz': ATLAS alone", "ATLAS 25K: today $0, room $750, $1,750 to target" in f[1] and "BLITZ" not in f[1]
          and "Zlarior" not in f[1], f[1])
    check("e. follow-up keeps the topic: 'blitz room' -> 'and atlas' = ATLAS's room", "ATLAS 25K: drawdown left $750" in f[3] and "BLITZ" not in f[3], f[3])
    check("e. 'what about kalshi' after the P&L: Kalshi's P&L", "Kalshi today +$18.50" in f[5] and "Zlarior" not in f[5], f[5])
    check("e. 'and the target?' after Zlarior's room: Zlarior's target alone", "Zlarior: $3,726 to the target" in f[7] and "ATLAS" not in f[7], f[7])
    ba = g("bare_atlas")[0]
    check("e. a bare 'atlas' with nothing to follow opens Zenith on ATLAS", ba.get("open") == "zenith" and ba.get("route") == "#/atlas"
          and ["zenith", "#/atlas"] in O["bare_atlas"]["opened"], ba)
    check("e. 'how are the bots doing today' is the status; 'how's today looking' is the plan", "Zlarior 50K: today +$213" in t("bare_atlas", 1)
          and "Gym" in t("bare_atlas", 2), (t("bare_atlas", 1)[:80], t("bare_atlas", 2)[:80]))
    e1, e2, e3, e4, e5 = (t("eval_pos", i) for i in range(5))
    # owner 2026-11-03: no "session X of 10" counter; the drawdown left (balance - the max-loss floor) instead
    check("e. eval progress: profit, % of the way, to target, drawdown left, no session X of 10", "Zlarior 50K eval: profit −$726" in e1
          and "$3,726 to the target" in e1 and "drawdown left $1,106" in e1 and "session 3 of 10" not in e1, e1)
    check("e. positions: the open trade (paper only, read-only)", "Zlarior: long 3 micros from 20,100.25, stop 20,080, target 20,160" in e2
          and "ATLAS: flat" in e2 and "Paper only" in e2, e2)
    check("e. what a bot waits for: its waiting text and entry window", "Waiting for a sweep of a LIT level" in e3 and "next entry window Mon 02:00-15:30 ET" in e3, e3)
    check("e. the money goal card from live.json", "Road to $10K" in e4 and "Next: Buy 2 MFFU Builder 25K" in e4, e4)
    check("e. 'what should I do now': the open position first; no sales line unless asked (owner 2026-11-02)", e5.startswith("Zlarior: long 3 micros") and "Money" not in e5 and "Buy 2" not in e5, e5)
    n1 = t("now_plain", 0)
    check("e. 'what should I do now' with nothing urgent: the open task and the next session", "Open task: Buy BLITZ 25K" in n1 and "opens today 6:00 PM ET" in n1, n1)
    n2 = t("now_bad", 0)
    check("e. 'what should I do now' with a feed problem in session: that problem and its fix first", n2.startswith("FEED STALE") and "Reload NinjaScript" in n2, n2)
    n3, s3 = t("now_stale", 0), t("now_stale", 1)
    check("e. a live feed 3 h old: turn the PC on; the status says it is old", n3.startswith("The PC has been silent since 3 h ago: turn it on and start the bot") and "3 h ago" in n3
          and "Heads up: the live feed is from 3 h ago" in s3, (n3, s3))
    n4, k4 = t("now_kalshi_setup", 0), t("now_kalshi_setup", 1)
    check("e. nothing else to do: connect Kalshi (the kalshi-server chat), never 'PC'", "kalshi-server" in n4 and "PC" not in k4, (n4, k4))
    ks = [t("kalshi_states", i) for i in (0, 2, 4)]
    check("e. Kalshi waiting / error / still loading", "not connected yet" in ks[0] and "cannot reach the Kalshi feed" in ks[1] and "Still checking Kalshi" in ks[2], ks)
    kk1, kk2, kk3 = (t("kalshi_strats", i) for i in range(3))
    check("e. 'how's kalshi' names the best and worst strategy today", "Best today: Gold 5 PM +$3.20; worst: 15-min favourites −$1.10" in kk1, kk1)
    check("e. 'kalshi strategies' lists each strategy (mode, today, all time, wins / losses)", "15-min favourites (live): today −$1.10, all time +$20.00, 41 trades (27 won, 14 lost)" in kk2
          and "Late favourite (BTC hourly)" in kk2 and not g("kalshi_strats")[1].get("open"), kk2)
    check("e. 'kalshi yesterday' from its daily P&L", "Kalshi yesterday: −$3.10" in kk3, kk3)
    oc = g("outcomes")
    check("e. Kalshi outcomes in the owner's alert style ('🌌 +$1.26' with the day's total), new settlements only",
          oc[0]["list"] == [{"title": "🌌 +$1.26", "body": "Bitcoin above $80,500 at 1 PM ET Nov 1 · today +$19.76", "pnl": 1.26, "t": T_SUN13 // 1000 - 30}]
          and oc[1]["list"] == [] and oc[2]["list"] == [], oc)
    mi = [t("more_intents", i) for i in range(6)]
    check("e. the NQ price from the bot's feed, with its age", mi[0].startswith("NQ 25,123.50 (the bot's last price, 2 min ago)"), mi[0])
    check("e. the daily loss limit and what is used of it", "Zlarior: daily loss limit $1,000, used $212; $1,106 of room to the floor" in mi[1], mi[1])
    check("e. 'is the pc on': the one fix first (none), its last check-in and the verdict", mi[2].startswith("The PC looks healthy: nothing to fix.") and "checked in 2 min ago" in mi[2] and "RUNNING: bot trading" in mi[2], mi[2])
    check("e. 'is nq open' is a market question, not 'open Zenith'", mi[3].startswith("NQ market open · regular session") and not g("more_intents")[3].get("open"), mi[3])
    check("e. trades today per bot (with the daily maximum)", "Zlarior: 1 trade today (max 1 a day)" in mi[4] and "BLITZ: 2 trades today" in mi[4], mi[4])
    check("e. balances: each account and Kalshi", "Zlarior 50K balance $49,274" in mi[5] and "Kalshi balance $512.34" in mi[5], mi[5])
    sps = O["smart_speech"]["res"][1].get("speak", "")
    check("f. a text with $ amounts said naturally: no stray commas, cents, no symbols",
          sps == "Zlarior is up 213 dollars today, room 1,106 dollars, and Kalshi made 18 dollars 50." and "1,000 dollars a day" in sp("more_intents", 1), sps)
    sh = [t("shell_facts", i) for i in range(9)]
    check("e. the shell's facts (slim view + .raw): the bots, the 'needs you' line, the money card, the price",
          "Zlarior 50K: today +$213, room $1,106, $3,726 to target" in sh[0] and "Needs you: FEED STALE" in sh[0] and sh[1].startswith("FEED STALE")
          and "Next: Buy 2 MFFU Builder 25K" in sh[2] and sh[3].startswith("NQ 25,123.50"), sh[:4])
    check("e. the shell's verse and quote of the day (the same as its card)", sh[4] == "The hand of the diligent shall bear rule: but the slothful shall be under tribute. (Proverbs 12:24, KJV)"
          and sh[5] == '"Risk comes from not knowing what you\'re doing." (Warren Buffett)', sh[4:6])
    check("e. crypto prices from the shell's feed (no guess when one is missing)", sh[6] == "Bitcoin $81,235 (+1.2% in 24 h) (5 min ago)."
          and "Ethereum $2,650 (−0.5% in 24 h)" in sh[7] and "Solana" not in sh[7] and "crypto prices" not in sh[8], sh[6:9])
    sc1, sc2 = t("shell_cached", 0), t("shell_cached", 1)
    check("e. the copy saved on the phone is said to be a saved copy, with its age", "This is the saved copy from 3 h ago" in sc1
          and "I have no crypto prices right now" in sc2, (sc1, sc2))
    se1, se2 = t("shell_error", 0), O["shell_error"]["res"][1].get("text", "")
    check("e. the shell's liveError: the live feed cannot be reached", "cannot reach the bots' live feed" in se1 and "Bots: I cannot reach the live feed" in se2, (se1, se2[:160]))
    ph = [t("phrasings", i) for i in range(11)]
    check("e. phrasings: 'how close to passing' is the target, 'where's nq' the price (missing: said so), 'is the bot trading my eval' the status",
          ph[0].startswith("Zlarior: $3,726 to the target") and ph[1].startswith("No NQ price in the live feed right now") and ph[2].startswith("The bot is running (RUNNING"),
          ph[:3])
    check("e. 'who made you', trading actions refused ('flatten everything', 'stop the bot'), 'take me home'",
          "You did, sir" in ph[3] and g("phrasings")[4].get("intent") == "refuse_trade" and g("phrasings")[5].get("intent") == "refuse_trade"
          and g("phrasings")[6].get("open") == "home", ph[3:7])
    check("e. 'anything overdue' lists the overdue tasks; 'what's up' is a short status", "open task" in ph[7] and ph[8].startswith("All quiet: RUNNING: bot trading"), ph[7:9])
    check("e. 'should I ...' without smart mode: the numbers, the call left to the owner", ph[9].startswith("Your call, sir. The numbers I have:") and "Zlarior 50K: session" in ph[9], ph[9])
    check("e. a greeting at the wrong hour gets a polite 'technically'", ph[10].startswith("Good morning, technically."), ph[10])
    sdec = O["smart_decision"]
    check("h. 'should I ...' with smart mode on goes to the model, deep (the expert persona)", len(sdec["calls"]) == 1
          and sdec["calls"][0]["body"].get("reasoning_effort") == "high" and sdec["res"][1].get("smart") is True, sdec["res"][1])
    zr = g("zroutes")
    check("e. Zenith routes from zenith-mode.js's zenithRouteFor: 'atlas trades', 'holodeck', 'blitz rules', 'the deck'",
          (zr[0].get("open"), zr[0].get("route"), zr[0].get("text")) == ("zenith", "#/atlas/trades", "Opening ATLAS trades in Zenith.")
          and zr[1].get("route") == "#/holo" and zr[4].get("route") == "#/blitz/rules" and zr[5].get("route") == "#/deck"
          and ["zenith", "#/atlas/trades"] in O["zroutes"]["opened"], [(r.get("open"), r.get("route")) for r in zr])
    check("e. a plain 'open zenith' keeps Zenith where it was; 'open settings' points to Jarvis's gear", zr[2].get("open") == "zenith" and "route" not in zr[2]
          and not zr[3].get("open") and "gear" in zr[3].get("text", ""), (zr[2], zr[3]))
    check("e. 'how many atlas trades' is a question (the week's count), not a page", not zr[6].get("open") and "ATLAS this week" in zr[6].get("text", ""), zr[6])
    zl = g("zroutes_local")
    check("e. without zenith-mode.js: the local map gives the same bot pages (and no page it does not know)",
          [r.get("route") for r in zl] == ["#/atlas/trades", "#/holo", "#/blitz", None, "#/brain"] and "not one of your dashboards" in zl[3].get("text", ""),
          [(r.get("route"), r.get("text")) for r in zl])
    zj = g("zroutes_junk")
    check("e. a route that is not a Zenith address is never passed on (the local map answers)", zj[0].get("route") == "#/blitz" and zj[1].get("route") == "#/liveview",
          [r.get("route") for r in zj])
    mf1, mf2 = t("missing_fields", 0), t("missing_fields", 1)
    check("e. a missing field is said to be missing (never '—' or a guess)", "Zlarior 50K: today missing, room $1,106, to target missing" in mf1 and clean(mf1), mf1)
    check("e. a missing target asked for one bot", "Zlarior: the distance to the target is missing from the feed" in mf2, mf2)
    bo1, bo2 = t("blitz_off", 0), t("blitz_off", 1)
    check("e. BLITZ off: the account C line (as today)", "BLITZ: account C is off on the PC (paper only until its own 25K is set up)." in bo1
          and "BLITZ: account C is off" in bo2, (bo1, bo2))
    # f. speech
    check("f. status speech: 'up 213 dollars', no symbols, no newlines", "Zlarior is up 213 dollars today" in sp("today_waiting", 0)
          and not re.search(r"[$·\n]", sp("today_waiting", 0)), sp("today_waiting", 0))
    check("f. Kalshi speech: cents said naturally", "Balance 512 dollars 34, up 18 dollars 50 today" in sp("today_kalshi", 0), sp("today_kalshi", 0))
    check("f. every reply has a speak string and clean text", all(clean(r.get("text")) and isinstance(r.get("speak"), str)
                                                                  for n in ("today_waiting", "follow", "eval_pos", "mkt_sun13") for r in g(n)))
    # g. the old Jarvis's commands
    oj = g("old_jarvis")
    ot = [r.get("text", "") for r in oj]
    check("g. 'good morning' is the morning briefing", oj[0].get("intent") == "briefing" and ot[0].startswith("Good morning. Monday, November 2, 8:00 AM ET."), ot[0][:90])
    check("g. 'hide my balance' masks every $ figure (text, speech, cards); 'show my balance' brings them back",
          oj[1].get("control") == "hide_balance" and "$1,106" not in ot[2] and "$•••" in ot[2] and "1,106" not in oj[2].get("speak", "")
          and "hidden amount" in oj[2].get("speak", "") and all("$1" not in str(c) for c in oj[2].get("cards", [])) and oj[3].get("control") == "show_balance", (ot[2], oj[2].get("speak")))
    check("g. 'stop' is a control, said silently", oj[4].get("control") == "stop" and oj[4].get("speak") == "", oj[4])
    check("g. 'mission control' and 'open liquidity' open Zenith's pages", oj[5].get("open") == "zenith" and oj[5].get("route") == "#/mission"
          and oj[6].get("route") == "#/levels" and ["zenith", "#/mission"] in O["old_jarvis"]["opened"], (oj[5], oj[6]))
    check("g. reminders and to-dos: honest, nothing written", "nothing was added" in ot[7] and "nothing was added" in ot[8], (ot[7], ot[8]))
    check("g. verse and quote of the day (bundled, no network)", "KJV" in ot[9] and re.search(r'^".+" \(.+\)$', ot[10]), (ot[9], ot[10]))
    check("g. what's new, the weather (missing, no guess), an unknown app", "New in Jarvis" in ot[11] and "no weather feed" in ot[12]
          and "Tradingview is not one of your dashboards here" in ot[13], (ot[11], ot[12], ot[13]))
    check("g. read-only: a trade request is refused politely", oj[14].get("intent") == "refuse_trade" and "cannot do that, sir" in ot[14], ot[14])
    check("g. who are you / what can't you do", "Jarvis, at your service" in ot[15] and "trade, arm a bot or go live" in ot[16], (ot[15], ot[16]))
    check("g. 'open blitz' opens Zenith on BLITZ (open('zenith', '#/blitz'))", oj[17].get("open") == "zenith" and oj[17].get("route") == "#/blitz"
          and ["zenith", "#/blitz"] in O["old_jarvis"]["opened"], oj[17])
    check("g. 'news': no feed here, points to Zenith's News", "no news feed" in ot[18] or "Opening News" in ot[18], ot[18])
    check("g. the old greeting: 'Good day. Tap the core ...'", ot[19] == "Good day. Tap the core or type below to speak with me." and oj[20].get("text") == ot[19], (ot[19], oj[20]))
    # h. smart mode
    so = O["smart_off"]
    check("h. smart mode off by default: the rule answer, no network", so["calls"] == [] and so["res"][0].get("intent") == "fallback"
          and so["res"][1]["smart"]["on"] is False and so["res"][1]["smart"]["provider"] == "groq" and so["res"][1]["smart"]["hasKey"] is False, so["res"])
    gq = O["smart_groq"]
    c0 = gq["calls"][0] if gq["calls"] else {}
    check("h. Groq (default): its address, Bearer key, the model, facts in the system prompt, the question last",
          c0.get("url") == "https://api.groq.com/openai/v1/chat/completions" and c0.get("method") == "POST"
          and c0.get("headers", {}).get("Authorization") == "Bearer gsk_FAKE_TEST_KEY" and c0.get("body", {}).get("model") == "openai/gpt-oss-120b"
          and c0["body"]["messages"][0]["role"] == "system" and "FACTS:" in c0["body"]["messages"][0]["content"]
          and "say plainly that it is missing" in c0["body"]["messages"][0]["content"] and c0["body"]["messages"][-1] == {"role": "user", "content": "what is the meaning of life"}
          and c0["body"].get("reasoning_effort") in ("low", "medium") and isinstance(c0["body"].get("max_completion_tokens"), int), c0)
    check("h. Groq answer used; a rule question never goes to the model", gq["res"][1].get("text") == "Forty-two, sir. The facts do not cover the rest."
          and gq["res"][1].get("smart") is True and len(gq["calls"]) == 1 and "Zlarior 50K" in gq["res"][2].get("text", ""), gq["res"][1:3])
    an = O["smart_anth"]
    a0 = an["calls"][0] if an["calls"] else {}
    h = a0.get("headers", {})
    check("h. Anthropic: x-api-key, anthropic-version 2023-06-01, the browser-access header, claude-sonnet-5-5, ~300 tokens",
          a0.get("url") == "https://api.anthropic.com/v1/messages" and h.get("x-api-key") == "sk-ant-FAKE-TEST" and h.get("anthropic-version") == "2023-06-01"
          and h.get("anthropic-dangerous-direct-browser-access") == "true" and a0["body"].get("model") == "claude-sonnet-5-5" and a0["body"].get("max_tokens") == 300
          and "Answer ONLY from the FACTS" in a0["body"].get("system", "") and a0["body"]["messages"][-1]["role"] == "user"
          and "temperature" not in a0["body"] and an["res"][1].get("text") == "Claude here: nothing in the facts says so.", a0)
    gm = O["smart_gem"]
    m0 = gm["calls"][0] if gm["calls"] else {}
    check("h. Gemini: generateContent address, x-goog-api-key header (not in the URL), system instruction with the facts",
          m0.get("url") == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent" and "key=" not in m0.get("url", "")
          and m0.get("headers", {}).get("x-goog-api-key") == "AIza-FAKE-TEST" and "FACTS:" in m0["body"]["systemInstruction"]["parts"][0]["text"]
          and m0["body"]["contents"][-1]["role"] == "user" and gm["res"][1].get("text") == "Gemini here: that is missing from the facts.", m0)
    for n, why in (("smart_500", "Groq could not be reached"), ("smart_throw", "Groq could not be reached"), ("smart_401", "the Anthropic key was refused"),
                   ("smart_refusal", "the model declined")):
        r = O[n]["res"][1]
        check(f"h. smart mode error ({n[6:]}) falls back to the rule answer", r.get("intent") == "fallback" and r.get("text", "").startswith("I can switch dashboards")
              and why in r.get("text", "") and r.get("smartError"), r)
    rt = O["smart_retry"]
    check("h. a 400 retries once without the optional fields, then answers", len(rt["calls"]) == 2 and "output_config" in rt["calls"][0]["body"]
          and "output_config" not in rt["calls"][1]["body"] and "thinking" not in rt["calls"][1]["body"]
          and rt["res"][1].get("text") == "Claude here: nothing in the facts says so.", [c["body"].keys() for c in rt["calls"]])
    kk = O["smart_keys"]
    st = json.loads(kk["storage"].get("jarvis.smart", "{}"))
    sm = kk["res"][-1]["smart"]
    check("h. keys kept per provider, only in localStorage 'jarvis.smart'; brain.smart never shows a key",
          st.get("keys", {}).get("groq") == "gsk_FAKE_ONE" and st.get("keys", {}).get("gemini") == "AIza-FAKE-TWO" and list(kk["storage"]) == ["jarvis.smart"]
          and sm["keys"] == {"groq": True, "gemini": True, "openrouter": False, "anthropic": False} and sm["provider"] == "groq" and "FAKE" not in json.dumps(sm), (st, sm))
    k0 = kk["calls"][0] if kk["calls"] else {}
    check("h. a decision question goes deep: high reasoning and the expert persona", k0.get("body", {}).get("reasoning_effort") == "high"
          and "Expert mode" in k0["body"]["messages"][0]["content"] and "never promise returns" in k0["body"]["messages"][0]["content"], k0.get("body", {}).get("reasoning_effort"))
    sd = O["smart_detect"]
    check("h. the key says which provider it is (sk-ant- Anthropic, AIza Gemini; another provider's pre-filled model is not kept), the model too (openai/... Groq); 'forget' clears every key",
          sd["res"][0]["smart"]["provider"] == "anthropic" and sd["res"][0]["smart"]["model"] == "claude-sonnet-5-5"
          and sd["calls"][0]["url"] == "https://api.anthropic.com/v1/messages" and sd["calls"][0]["body"]["model"] == "claude-sonnet-5-5"
          and sd["res"][2]["smart"]["provider"] == "gemini" and sd["res"][3]["smart"]["provider"] == "groq" and sd["res"][3]["smart"]["model"] == "openai/gpt-oss-20b"
          and sd["res"][4]["smart"]["keys"] == {"groq": False, "gemini": False, "openrouter": False, "anthropic": False} and sd["res"][4]["smart"]["on"] is False
          and "FAKE" not in sd["storage"].get("jarvis.smart", ""), [r.get("smart") for r in sd["res"]])
    ss = O["smart_stored"]
    check("h. settings saved on the phone are read back (provider, depth, key)", ss["res"][0]["smart"]["active"] is True and ss["res"][0]["smart"]["depth"] == "quick"
          and ss["calls"] and ss["calls"][0]["headers"]["Authorization"] == "Bearer gsk_STORED_FAKE" and ss["calls"][0]["body"]["reasoning_effort"] == "low", ss["res"][0])
    # i. junk facts
    for n in ("junk_null", "junk_throw", "junk_empty", "junk_types", "junk_promise"):
        rs = g(n)
        ok = all("exception" not in r for r in rs) and all(clean(r.get("text")) for r in rs if "text" in r) and all(
            isinstance(r.get("list"), list) for r in rs if "list" in r)
        check(f"i. junk facts ({n[5:]}): no exception, clean text", ok, [r.get("exception") or r.get("text") for r in rs][:6])
    jt = t("junk_types", 0)
    check("i. junk cards read as missing, not as numbers", "missing" in jt or "not in the feed" in jt or "no eval numbers" in jt, jt)


PAGE = """<!doctype html><meta charset="utf-8"><title>brain test</title><script type="module">
import { createBrain } from './brain.js';
window.run = async (facts, now) => {
  localStorage.clear();
  const calls = [];
  window.fetch = async (u, init) => { calls.push([String(u), init.headers]);
    return new Response(JSON.stringify({ choices: [{ message: { content: 'Browser smart answer.' }, finish_reason: 'stop' }] }), { status: 200, headers: { 'content-type': 'application/json' } }); };
  const opened = [];
  const b = createBrain({ getFacts: () => facts, now: () => now, open: (a, r) => opened.push([a, r || null]) });
  const r1 = await b.ask('How are the bots?');
  const r2 = await b.ask('open blitz');
  b.setSmart({ key: 'gsk_FAKE_BROWSER', on: true });
  const r3 = await b.ask('what is the meaning of life');
  const r4 = await b.briefing();
  await new Promise((r) => setTimeout(r, 600));
  return { r1: r1.text, r2: r2.text, r3: r3.text, r4: r4.text, calls, opened, store: Object.keys(localStorage), smart: b.smart };
};
window.ready = true;
</script>"""


def part_browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                                   # pragma: no cover
        check("j. Chromium: playwright available", False, e)
        return
    tmp = tempfile.mkdtemp(prefix="le_jbrain_web_")
    shutil.copy(BRAIN, os.path.join(tmp, "brain.js"))
    open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write(PAGE)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    hnd = functools.partial(Quiet, directory=tmp)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), hnd)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            p = br.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html")
            p.wait_for_function("window.ready === true", timeout=10000)
            out = p.evaluate("([f, n]) => window.run(f, n)", [facts(T_SUN1930, kalshi=kalshi(T_SUN1930), kalshiState="ok"), T_SUN1930])
            br.close()
        check("j. Chromium: the module loads as an ES module and answers", "Zlarior 50K: today +$213" in out["r1"] and not errs, (out["r1"][:120], errs))
        check("j. Chromium: 'open blitz' calls the shell's open('zenith', '#/blitz')", out["r2"] == "Opening BLITZ in Zenith." and ["zenith", "#/blitz"] in out["opened"], out["opened"])
        check("j. Chromium: smart mode through the page's fetch (Groq), the key only under jarvis.smart",
              out["r3"] == "Browser smart answer." and out["calls"] and out["calls"][0][0] == "https://api.groq.com/openai/v1/chat/completions"
              and out["store"] == ["jarvis.smart"] and out["smart"]["active"] is True, (out["r3"], out["store"]))
        check("j. Chromium: the briefing", out["r4"].startswith("Good evening.") and "Kalshi (PAPER)" in out["r4"], out["r4"][:200])
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def part_system(O):
    """k. the System view (2026-11-02): "status", "is everything ok", "how's the pc" answer every system at once."""
    t = lambda n, i: (O[n]["res"][i] or {}).get("text") or ""        # noqa: E731
    sp = lambda n, i: (O[n]["res"][i] or {}).get("speak") or ""      # noqa: E731
    it = lambda n, i: (O[n]["res"][i] or {}).get("intent")           # noqa: E731
    s1, s2, pc, s4, bots = (t("system", i) for i in range(5))
    check("k. 'status': the verdict and the one thing to do first, then one line per system (PC, Zlarior, ATLAS, BLITZ, Kalshi, Planner)",
          s1.startswith("HEADS UP: RAM 89% in use on the PC: close the browser tabs") and all(x in s1 for x in ("PC (bot server", "CPU 23% · RAM 89%", "Zlarior (50K eval): +$213",
                                                                          "ATLAS (25K)", "BLITZ (25K): OFF", "Kalshi (its own server): +$18.50", "Planner (your day): 4:15 PM"))
          and it("system", 0) == "system", s1)
    check("k. 'is everything ok?' and 'all good' give the same System answer", s2 == s1 and s4 == s1 and it("system", 1) == "system", (s2[:80], s4[:80]))
    check("k. the System answer speaks short and plain (the one thing to watch, the PC's check-in; no symbols)",
          sp("system", 0).startswith("All running, one thing to watch:") and "checked in 2 minutes ago, feed 12 seconds" in sp("system", 0) and "·" not in sp("system", 0)
          and "$" not in sp("system", 0), sp("system", 0))
    check("k. 'how's the pc': the one fix first (the amber RAM line), then its check-in, verdict, CPU and RAM",
          pc.startswith("The fix: RAM 89% in use on the PC: close the browser tabs") and "checked in 2 min ago" in pc and "RUNNING" in pc and "CPU 23%, RAM 89%" in pc
          and it("system", 2) == "pc" and "RAM 89 percent in use on the PC" in sp("system", 2), (pc, sp("system", 2)))
    check("k. 'how are the bots' stays the bots' status (unchanged)", "RUNNING" in bots and "Zlarior 50K" in bots and "PC (bot server" not in bots, bots)
    sg = (O["system"]["res"][5] or {}).get("list") or []
    check("k. suggestions: 'Is everything OK?' first while the System view has something", sg[:1] == ["Is everything OK?"] and 4 <= len(sg) <= 6, sg)
    g1, g2 = t("system_good", 0), t("system_good", 1)
    check("k. all good: 'ALL GOOD: nothing needs you.' and 'All good, sir.'",
          g1.startswith("ALL GOOD: nothing needs you.") and g2 == g1 and sp("system_good", 0).startswith("All good, sir. Nothing needs you."), (g1[:80], sp("system_good", 0)))
    n1, n2 = t("system_none", 0), t("system_none", 1)
    check("k. a shell without the System view: 'status' is the bots' status as before; 'how's the pc' says the CPU / RAM reading is missing",
          "RUNNING" in n1 and "Zlarior 50K" in n1 and "checked in 2 min ago" in n2 and "no CPU / RAM reading yet" in n2, (n1[:120], n2))
    j = [t("system_junk", i) for i in range(3)]
    check("k. junk System facts never raise and never print undefined / NaN / [object",
          all(x and not re.search(r"undefined|NaN|\[object", x) for x in j) and not any("exception" in (r or {}) for r in O["system_junk"]["res"]), j)


def part_tonight(O):
    """l. the priority engine and the new intents (2026-11-02), on tonight's live.json; smart mode's fallback (timeout, offline)."""
    r = O["tonight"]["res"]
    hd = r[0]["headline"]
    A = {q: (r[i + 1] or {}).get("text") or "" for i, q in enumerate(TONIGHT_Q)}
    check("l. the proactive line: both evals on day 5, one MNQ on each before Wednesday Nov 4; red; '+1 more' (the PC)",
          hd["text"] == "Both evals are on day 5 with no trade: place 1 MNQ on each before Wednesday Nov 4 (MFFU can close them at day 7)."
          and hd["level"] == "bad" and hd["more"] == 1 and hd["key"].startswith("quiet5:lit5,atlas5"), hd)
    check("l. the ranking: the evals first (money at risk), then the PC's RAM, then Kalshi (context only); no sales line",
          [x["key"].split(":")[0] for x in r[0]["priorities"]] == ["quiet5", "pc", "kalshi"] and not any("Buy" in x["text"] or "VIBES" in x["text"] for x in r[0]["priorities"]), r[0]["priorities"])
    w = A["what should I do today"]
    check("l. 'what should I do': 1-3 lines, the evals first, then the PC fix, then the market and Zlarior's next window; never a sale",
          w.split("\n")[0].startswith("Both evals are on day 5") and w.split("\n")[1].startswith("Then: RAM 95% in use on the PC: close the browser tabs")
          and "Zlarior's next window: tomorrow (Tue) 2:00 AM ET" in w and len(w.split("\n")) <= 3 and "Buy" not in w and "VIBES" not in w, w)
    check("l. 'what should I do' speaks short: the one action, then the next", (r[1].get("speak") or "").startswith("Both evals are on day 5 with no trade. Place one micro on each before Wednesday."), r[1].get("speak"))
    check("l. 'brief me' puts the urgent thing first ('First: ...') and has no sales line", A["brief me"].split("\n")[1].startswith("First: Both evals") and "VIBES" not in A["brief me"], A["brief me"][:300])
    check("l. 'status' (System view): the verdict with the priority engine's one thing; Kalshi NOT LINKED, the Planner NOT LINKED (grey, intentional)",
          A["status"].startswith("NEEDS YOU: Both evals are on day 5") and "Kalshi (its own server): NOT LINKED · not linked yet · planned" in A["status"]
          and "Planner (your day): NOT LINKED · open the Planner once on this phone" in A["status"], A["status"])
    check("l. 'how's my PC': the one fix first, then the numbers", A["how's my PC"].startswith("The fix: RAM 95% in use on the PC: close the browser tabs") and "CPU 31%, RAM 95%" in A["how's my PC"], A["how's my PC"])
    check("l. eval pace: session X of 10, $ to go, $ a session to pass, days left before the 7-day rule",
          "Zlarior 50K: session 6 of 10, $3,726 to go, about $932 a session to pass in 4 sessions, 5 days since its last trade (2 left before the 7-day rule)" in A["eval pace"]
          and "ATLAS 25K: session 5 of 10, $1,754 to go, about $351 a session" in A["eval pace"], A["eval pace"])
    check("l. 'why no trade': the bot runs, what each account waits for, 5 days without a trade, outside the window, the A-setups line",
          A["why no trade"].startswith("The bot is running (TRADING YOUR EVAL).") and "Zlarior: waiting: Waiting for the 02:00 ET window" in A["why no trade"]
          and "no trade for 5 days" in A["why no trade"] and "outside the entry window" in A["why no trade"] and "2-4 a week" in A["why no trade"], A["why no trade"])
    check("l. 'when does it trade next': Zlarior's window (02:00-15:30 ET) and the setup", A["when does it trade next"].startswith("Zlarior's next window: tomorrow (Tue) 2:00 AM ET (entries 02:00-15:30 ET")
          and "sweep extreme" in A["when does it trade next"], A["when does it trade next"])
    check("l. 'last trade' explained: account, side, size, time, result in $ and R, the Mind's lesson",
          A["last trade"].startswith("Last trade: Zlarior long 4 micros, Wed Oct 28 10:05 AM ET: stop, −$326 (-1.0R).") and "wait for the 5m close" in A["last trade"], A["last trade"])
    check("l. P&L this month from the booked days ($0 in November); this week; ATLAS without days is 'missing', never a guess",
          "Zlarior this month: $0." in A["how much did I make this month"] and "ATLAS this month: missing." in A["how much did I make this month"]
          and "Zlarior this week: $0." in A["pnl this week"], (A["how much did I make this month"], A["pnl this week"]))
    check("l. MFFU rules Q&A: inactivity, payouts, the daily loss limit (a typo tolerated)",
          A["what is the MFFU inactivity rule"].startswith("Inactivity: no trade for 7 calendar days") and "$2,100 buffer" in A["mffu payout rules"]
          and A["whats the daly loss limit rule"].startswith("Daily loss limit: $1,000 on the 50K, $600 on the 25K; soft"), (A["what is the MFFU inactivity rule"][:80], A["whats the daly loss limit rule"][:80]))
    check("l. sales only when asked: 'deals' shows the money idea and the evals' pace", A["deals"].startswith("Money idea: Buy 2 LucidPro 50K evals") and "Zlarior 50K: session 6 of 10" in A["deals"], A["deals"])
    check("l. 'how are the bots' names what needs you (the evals)", "Needs you: Both evals are on day 5" in A["how are the bots"], A["how are the bots"])
    check("l. 'what did the bots learn': the regime and the Mind's lesson", "Regime: range, low volatility" in A["what did the bots learn"] and "wait for the 5m close" in A["what did the bots learn"], A["what did the bots learn"])
    check("l. 'is zlarior trading': the trading answer for Zlarior alone", A["is zlarior trading"].startswith("The bot is running") and "ATLAS" not in A["is zlarior trading"], A["is zlarior trading"])
    check("l. Kalshi not linked: the one step, calm (not an error)", "not connected yet" in A["kalshi"] and "kalshi-server" in A["kalshi"], A["kalshi"])
    q6 = O["tonight_q6"]["res"]
    check("l. day 6 on Zlarior, day 5 on ATLAS: 'today', both named with their days, red",
          q6[0]["headline"]["text"].startswith("Both evals are on Zlarior day 6, ATLAS day 5 with no trade: place 1 MNQ on each today.") and q6[0]["headline"]["level"] == "bad"
          and q6[2]["text"].startswith("NEEDS YOU: Both evals are on Zlarior day 6"), (q6[0]["headline"], q6[2]["text"][:120]))
    q7 = O["tonight_q7"]["res"]
    check("l. day 7 on Zlarior alone: 'MFFU may close it now', check the dashboard", q7[1]["text"].startswith("Zlarior (50K) has gone 7 days with no trade: MFFU may close it now."), q7[1]["text"])
    c = O["tonight_calm"]["res"]
    check("l. nothing urgent: 'Nothing needs you', the market and the next window, Kalshi's planned link; the proactive line says all quiet (level ok)",
          c[1]["text"].startswith("Nothing needs you right now, sir.") and "Kalshi: not linked yet (planned" in c[1]["text"] and c[0]["headline"]["level"] == "ok", (c[0]["headline"], c[1]["text"]))
    check("l. a stopped bot beats the quiet days (it is why nothing trades)", O["tonight_stopped"]["res"][0]["text"].startswith("Start the bot on the PC: it is stopped."), O["tonight_stopped"]["res"][0]["text"])
    to, of = O["smart_timeout"]["res"][1], O["smart_offline"]["res"][1]
    check("l. smart mode times out within 8 s: the local answer, with the reason", to.get("smartError") == "Groq timed out" and to["ms"] < 9500 and "Smart mode is unavailable: Groq timed out" in to["text"], {k: to.get(k) for k in ("smartError", "ms")})
    check("l. smart mode offline: the local answer at once, no network call", of.get("smartError") == "offline" and of["ms"] < 1500 and not O["smart_offline"]["calls"], {k: of.get(k) for k in ("smartError", "ms")})
    body = json.dumps(O["smart_grounded"]["calls"][0]["body"]) if O["smart_grounded"]["calls"] else ""
    check("l. smart mode is grounded: the priorities, the quiet days, the PC's RAM, the next window and the MFFU rules go with the question; no key in the body",
          "Both evals are on day 5" in body and "quiet_days_no_trade" in body and "RAM 95%" in body and "next window" in body and "inactivity" in body and "gsk_FAKE" not in body, body[:300])
    rules = json.load(open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))
    e50 = rules["builder_50k"]["eval"]
    m = re.search(r"b50: \{[^}]*target: (\d+), mll: (\d+), dll: (\d+)", open(os.path.join(ROOT, "tools", "web_public", "jarvis", "data.js"), encoding="utf-8").read())
    check("l. data.js MFFU_RULES matches research/lit/mffu_rules.json (50K target, max loss, daily loss)",
          bool(m) and (int(m[1]), int(m[2]), int(m[3])) == (int(e50["profit_target"]["value"]), int(e50["max_loss"]["value"]["amount"]), int(e50["daily_loss_limit"]["value"]["amount"])), m and m.groups())


def part_manual(O):
    """m. the owner's manual keep-alive trades (2026-11-03): "I traded on both" marks today per account; the warning goes."""
    r, st = O["manual"]["res"], O["manual"]["storage"]
    day = "2026-11-02"
    check("m. before: both evals on day 5 lead the headline; 'did I trade today' is a question (nothing marked)",
          r[0]["headline"]["key"].startswith("quiet5") and r[1].get("intent") != "manual_trade" and r[1].get("control") != "manual_trade", (r[0]["headline"], r[1].get("intent")))
    check("m. 'I traded on both': today's ET date for Zlarior and ATLAS kept on this phone, said back, the shell told (control manual_trade)",
          r[2].get("intent") == "manual_trade" and r[2].get("control") == "manual_trade" and "Zlarior and ATLAS" in r[2]["text"]
          and json.loads(st["jarvis.manualTrades"]) == {"lit": day, "atlas": day} and r[3]["marks"] == {"lit": day, "atlas": day}, (r[2], st))
    check("m. after: the quiet days count from the mark, so no inactivity warning in the headline, 'what should I do' or 'status'",
          not r[4]["headline"]["key"].startswith("quiet") and not any(x["key"].startswith("quiet") for x in r[4]["priorities"])
          and "place 1 MNQ" not in r[5]["text"] + r[6]["text"] and "day 5" not in r[5]["text"], (r[4]["headline"], r[5]["text"][:200], r[6]["text"][:200]))
    a = O["manual_atlas"]
    check("m. 'I placed my keep-alive trade on ATLAS': ATLAS only; Zlarior still on day 5",
          json.loads(a["storage"]["jarvis.manualTrades"]) == {"atlas": day} and a["res"][2]["headline"]["key"].startswith("quiet5:lit5"), (a["storage"], a["res"][2]["headline"]))
    p = O["manual_plain"]
    check("m. 'I traded' with no account named: the open evals that count quiet days (both)", json.loads(p["storage"]["jarvis.manualTrades"]) == {"lit": day, "atlas": day}
          and not p["res"][2]["headline"]["key"].startswith("quiet"), (p["storage"], p["res"][2]["headline"]))


def main():
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_jbrain_")
    try:
        O, err = run_node(tmp)
        check("node: every scenario ran", O is not None, err)
        if O:
            part_node(O)
            part_system(O)
            part_tonight(O)
            part_manual(O)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if "--no-browser" not in sys.argv:
        part_browser()
    n = sum(RES)
    print(f"\njarvis brain: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
