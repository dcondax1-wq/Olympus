"""Every account from the live PC feed, on every page (night-feedsA 2026-11-18, owner: "everything with accounts, all live feed fixed").

The live site (GitHub Pages) is a CLOUD build: its home.json board cards are the cloud's paper twin (where "cloud", badge PAPER, $49,900)
and the real numbers come only from the PC's ntfy status posts (core + ext). Found on the live site at 390 x 844 and fixed:
  1. Jarvis "NQ BOTS TODAY · 2 accounts" (3 real accounts): data.js extraAccounts = the PC's other accounts (Zlarior 25K #2) in every list
  2. Jarvis "KALSHI TODAY: OFFLINE not connected yet" although the PC posts kalshi_k1 / kalshi_rewards (paper): data.js kalshiPaper
  3. truth.js read the cloud paper twin as Zlarior ($1,900 drawdown left) when the feed was late; a cloud board "newer" than the PC
     (its t = build time) won in pc_feed.mergeBoard (+ the Python twin engine/live_site.merge_board)
  4. Board / My Accounts payout coach "NO NUMBERS" while the ZEUS card said "Not yet: need $1,463 more" (payoutcard.js modelState)
  5. My Accounts showed a 4th account "MFFU 50K Eval $49,900" (the cloud paper twin): accounts.js realHome
  6. Trading "Today": no 25K #2, funded ATLAS "To pass $1,963": every account + the ZEUS card's payout line
  7. a 15-day-old Kalshi engine copy gave "today's" advice (kalshi-brain OLD_S) and "Kalshi: $0 today" (copilot kalshiNow)
  8. Jarvis asked the old, suspended GitHub account's live.json first (404s in the console): the PC feed first (test_sync_truth)
  9. pc_feed.fetchLatest: one shared answer per page (3-4 modules asked it at load; a slow phone made some give up after 3 s)
 10. (lead 2026-11-19) a 2nd "Zlarior 50K" row on the Board / ZEUS card when the card and the ledger row differ by cents: mffumodel.match
Node parts are pure (no network). The browser part serves tools/web_public with a cloud-like home.json and answers ntfy with a
fixture feed (core + 2 ext parts, fake last-4), then reads the Jarvis tiles, My Accounts, the Board and Trading at 390 x 844.
Run: python -m tests.test_feeds_accounts  (browser part under: flock -w 2400 /tmp/olympus_browser.lock; FEEDS_NO_BROWSER=1 skips it)
"""
from __future__ import annotations

import copy
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
sys.path.insert(0, ROOT)
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:500]}"))


NOW = int(time.time())


def feed_posts(now: int) -> list:
    """The PC's status as ntfy messages: ext part 0 + 1 then the core (the real shape of 2026-11-18, fake last-4)."""
    t, rt = now - 240, now - 60
    core = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": t, "every_s": 300, "day_pnl": 0,
            "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "good", "reason": "routing through NinjaTrader", "t": t},
            "pc": {"running": True, "adapter": "ninjatrader", "present": True, "t": t, "age_s": 0, "silent": False, "model": "lit"},
            "reporter": {"t": rt, "server": True, "nt": True, "market_open": True, "mode": "LIVE", "problems": []},
            "board": {"v": 1, "kind": "le-board", "t": t, "data_t": t, "where": "live", "today": "2026-11-19", "running": True, "level": "good",
                      "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "source": "PC bot", "balance": 49192.78,
                              "floor": 48168.2, "room": 1024.58, "mll": 2000.0, "to_target": 3807.22, "target_balance": 53000.0, "profit": -807.22,
                              "today_pnl": 0.0, "status": "open", "session": 24, "dll": 1000.0, "dll_used": 0.0, "room_frac": 0.5123},
                      "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "badge": "LIVE", "source": "PC bot (account B)",
                                "balance": 24887.2, "floor": 24000.0, "room": 887.2, "mll": 1000.0, "to_target": 1962.8, "target_balance": 26850.0,
                                "profit": -112.8, "today_pnl": 0.0, "status": "funded", "session": 3, "dll": 600.0, "room_frac": 0.8872},
                      "lines": []},
            "accounts": [
                {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "LIVE",
                 "conn": {"present": True, "t": t, "running": True, "connected": True},
                 "eval": {"start_balance": 50000.0, "balance": 49192.78, "profit": -807.22, "to_target": 3807.22, "target_balance": 53000.0,
                          "floor": 48168.2, "room": 1024.58, "mll": 2000.0, "dll": 1000.0, "dll_used": 0.0, "today": 0.0, "session": 24, "status": "open"},
                 "pnl": {"today": 0.0, "week": -129.4}},
                {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc", "badge": "LIVE",
                 "conn": {"present": True, "t": t, "running": True, "connected": True},
                 "eval": {"start_balance": 25000.0, "balance": 25000.0, "profit": 0.0, "to_target": 1500.0, "target_balance": 26500.0,
                          "floor": 24000.0, "room": 1000.0, "mll": 1000.0, "dll": 600.0, "dll_used": 0.0, "today": 0.0, "session": 2, "status": "open"},
                 "pnl": {"today": 0.0, "week": 0}}]}
    up = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 600))
    ext0 = {"v": 1, "kind": "le-live-ext", "src": "pc_report", "t": t, "part": 0, "of": 2, "x": {
        "mf": {"t": t, "a": [{"id": "mffu50k_eval", "sd": "2026-10-19", "l4": "0001", "td": 1, "bd": ["2026-11-16", -129], "wd": ["2026-11-16", -129], "eq": [-678, -807], "n": 1},
                             {"id": "b25k_2", "sd": "2026-11-18", "l4": "0003"},
                             {"id": "atlas", "sd": "2026-11-17", "l4": "0002", "td": 1, "lt": "2026-11-18", "bd": ["2026-11-18", -113], "wd": ["2026-11-18", -113], "eq": [0, -113], "n": 1,
                              "f": {"cp": -113, "bd": -113, "cd": 1, "ef": "2026-11-20", "pn": 0, "mr": 0}}]},
        "kalshi_k1": {"kind": "kalshi_k1_pub", "paper_only": True, "updated": up, "days": 0.1, "sig": 0, "set": 0, "net": 0.0},
        "kalshi_rewards": {"kind": "kalshi_rewards_pub", "paper_only": True, "updated": up, "days": 0.91, "reward": 12.68, "fill_pnl": -15.0,
                           "net": -2.32, "fills": 2, "markets": 9, "per100_day": -0.13}}}
    ext1 = {"v": 1, "kind": "le-live-ext", "src": "pc_report", "t": t, "part": 1, "of": 2, "x": {"glance": {"v": 1, "t": t, "bots": []}}}
    return [{"event": "message", "time": rt - 2, "message": json.dumps(ext0)}, {"event": "message", "time": rt - 2, "message": json.dumps(ext1)},
            {"event": "message", "time": rt, "message": json.dumps(core)}]


def cloud_home(now: int) -> dict:
    """What the GitHub Pages build publishes: the cloud's paper twin as board.lit, a PAPER 50K row, built at 'now - 50 min'."""
    b = now - 3000
    return {"built": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(b)),
            "live": {"pc": {"present": False, "t": None}, "pc_verdict": {"code": "SILENT", "label": "PC SILENT", "level": "bad", "t": b}},
            "board": {"v": 1, "kind": "le-board", "t": b, "data_t": None, "where": "cloud", "today": "2026-11-19", "running": True,
                      "lit": {"name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "PAPER", "source": "cloud paper", "balance": 49900.0, "floor": 48000.0,
                              "room": 1900.0, "mll": 2000.0, "to_target": 3100.0, "today_pnl": 0.0, "status": "open", "session": 24},
                      "atlas": {"name": "ATLAS", "plan": "MFFU Builder 25K", "badge": None, "source": "none", "balance": None, "status": "not set up"},
                      "trades": []},
            "accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "PAPER",
                          "conn": {"present": False, "t": None},
                          "eval": {"start_balance": 50000.0, "balance": 49900.0, "profit": -100.0, "to_target": 3100.0, "floor": 48000.0, "room": 1900.0, "mll": 2000.0}},
                         {"id": "cloud_paper", "name": "Paper (cloud)", "plan": "MFFU 50K rules", "kind": "paper", "source": "cloud", "badge": "PAPER",
                          "conn": {"present": True, "t": b}, "eval": {"balance": 49900.0, "floor": 48000.0, "room": 1900.0, "mll": 2000.0}}]}


NODE = r"""
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import fs from 'node:fs'; import path from 'node:path'; import vm from 'node:vm';
const [WP, dir] = [process.argv[2], process.argv[3]];
const require = createRequire(import.meta.url);
const I = JSON.parse(fs.readFileSync(path.join(dir, 'in.json'), 'utf8'));
const NOW = I.now, out = {};
const store = new Map();
globalThis.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
const F = require(path.join(WP, 'pc_feed.js'));
const text = I.posts.map((m) => JSON.stringify(m)).join('\n');
const lite = F.parseLatest(text);
const u = (p) => pathToFileURL(path.join(WP, p)).href;
// 1. truth.js: the cloud twin is never an account; the PC feed laid over gives the 3 real accounts; ATLAS (status funded) is funded
const T = await import(u('olympus/truth.js'));
const A0 = T.accountsOf(I.home);
out.cloudOnly = { lit: A0.lit.has, atlas: A0.atlas.has, extra: T.extraOf(I.home).length };
const h1 = { ...F.overlayHome(I.home, lite, NOW), pc_accounts: lite.accounts, pc_accounts_t: lite.t };
const A1 = T.accountsOf(h1);
out.fed = { lit: [A1.lit.balance, A1.lit.room], atlas: [A1.atlas.balance, A1.atlas.kind], extra: T.extraOf(T.canonHome(h1, NOW)).map((x) => [x.name, x.balance, x.toTarget, x.kind]) };
// a cloud board built AFTER the PC's last post never wins over it (its t is the build time)
const late = JSON.parse(JSON.stringify(I.home)); late.board.t = NOW + 60;
const h2 = F.overlayHome(late, lite, NOW);
out.lateCloud = { where: h2.board.where, lit: h2.board.lit.balance, badge: h2.board.lit.badge };
// 2. pc_feed.fetchLatest: one shared answer per page (a browser: window + document) for 3 callers at once
let calls = 0;
const fakeFetch = async (x) => { calls++; x = String(x); if (x.endsWith('status_feed.json')) return { ok: true, json: async () => ({ ntfy: 'https://ntfy.example', topic: 'olympus_test_topic' }) };
  return { ok: true, text: async () => text }; };
globalThis.window = {}; globalThis.document = { baseURI: 'https://site.example/jarvis/' };
const F2 = require(path.join(WP, 'pc_feed.js') + '');
delete require.cache[require.resolve(path.join(WP, 'pc_feed.js'))];
const F3 = require(path.join(WP, 'pc_feed.js'));
const got = await Promise.all([1, 2, 3].map(() => F3.fetchLatest({ feedUrl: '../status_feed.json', fetch: fakeFetch })));
got[0].board.lit.balance = 1;                                  // one caller's change never reaches another
out.shared = { calls, ok: got.every((g) => g && g.kind === 'le-live'), sep: got[1].board.lit.balance };
delete globalThis.window; delete globalThis.document;
// 3. Jarvis data.js: the extra account + Kalshi's paper tests from the merged feed
const D = await import(u('jarvis/data.js'));
out.extra = D.extraAccounts(lite).map((x) => [x.name, x.size, x.stage, x.room, x.to_target]);
out.extraCloud = D.extraAccounts(I.home).length;
const kp = D.kalshiPaper(lite);
out.kpaper = kp ? [kp.k1 && kp.k1.sig, kp.rewards && kp.rewards.net, kp.net] : null;
// 4. kalshi-brain: an engine copy older than 2 days gives no advice ("bet size too big" was today's first thing to do)
const KB = await import(u('jarvis/kalshi-brain.js'));
const edges = { t: NOW - 15 * 86400, book: { ruin_now: 1, balance: 40, running: false }, edges: [{ id: 'x', label: 'XRP', n: 192, pnl: -106.63 }], lists: { stop: ['x'] } };
const sOld = KB.snapshot(null, { edges }, NOW * 1000), sNew = KB.snapshot(null, { edges: { ...edges, t: NOW - 3600 } }, NOW * 1000);
out.kb = { old: KB.items(sOld, NOW * 1000).length, fresh: KB.items(sNew, NOW * 1000).length, line: KB.line(sOld) };
// 5. the copilot's day summary: 3 accounts, funded = no "to the target", Kalshi = the paper tests (the old engine copy is not "today")
const CP = await import(u('jarvis/copilot.js'));
const S = { home: T.canonHome(h1, NOW), kalshiEdges: edges, kpaper: kp, at: { home: NOW * 1000 } };
const card = CP.dayCard(S, NOW * 1000);
out.day = card.rows.map((r) => r.text);
// 6. the briefing's Kalshi line, the home's NQ bots strip, the stale-file nudge level
const BR = await import(u('jarvis/briefing.js'));
const HD = await import(u('jarvis/home-data.js'));
out.bots = HD.botsFrom({ ok: true, bots: { lit: { room: 1024.58, mll: 2000, today_pnl: 0, room_frac: 0.51 }, atlas: { room: 887.2, mll: 1000, today_pnl: 0, room_frac: 0.89 } } },
  { live: { extra: D.extraAccounts(lite) }, system: { rows: [] } }).map((b) => [b.name, b.size, b.text]);
out.brief = Object.keys(BR).join(',');
// 7. the payout card (Board + My Accounts) reads the PC payout tracker through mffumodel.js: the ZEUS card's own words
const sandbox = { window: {}, console, Date, Math, JSON, Number, String, Array, Object, Promise, Map, Set, isFinite, parseFloat, RegExp, localStorage: globalThis.localStorage };
sandbox.window = sandbox; sandbox.globalThis = sandbox;
for (const f of ['business/payoutcoach.js', 'business/mffumodel.js', 'business/payoutcard.js']) vm.runInNewContext(fs.readFileSync(path.join(WP, f), 'utf8'), sandbox, { filename: f });
const plan = JSON.parse(fs.readFileSync(path.join(WP, 'business/accounts.json'), 'utf8'));
const rows = sandbox.PAYOUT_CARD.rowsOf(plan, null, lite);
const r = rows.find((x) => x.key === 'atlas');
const p = r ? sandbox.PAYOUT_CARD.pick(r, null, NOW) : null;
out.pay = p ? { from: p.from, text: sandbox.PAYOUT_COACH.coach(p.state, r.planKey).text, idle: sandbox.PAYOUT_COACH.lines(sandbox.PAYOUT_COACH.coach(p.state, r.planKey, '2026-11-19')).filter((x) => /^Inactivity/.test(x)) } : null;
const mm = sandbox.MFFU_MODEL.cards({ lite, plan, coach: sandbox.PAYOUT_COACH }, NOW).find((c) => c.key === 'atlas');
out.zeusPay = mm && mm.payout && mm.payout.c ? mm.payout.c.text : null;
// 9. ONE row per account (lead 2026-11-19: a 2nd "Zlarior 50K" row on the Board and the ZEUS card when the bot's card and its ledger row
//    read the balance a few cents apart): mffumodel.match by PC id / last 4 first, the balance only as a last resort within $5
const MM = require(path.join(WP, 'business/mffumodel.js')), BMm = require(path.join(WP, 'board/boardmodel.js')), ZC = require(path.join(WP, 'olympus/zeus_core.js'));
const PCm = require(path.join(WP, 'business/payoutcoach.js'));
const cents = JSON.parse(JSON.stringify(lite)); cents.accounts[0].name = 'Zlarior 50K'; cents.accounts[0].eval.balance = 49192.80;
const keys = (rows) => rows.map((r) => r.key + (r.live ? ':' + r.live.id : ''));
out.m = { cents: keys(MM.match(plan, cents, null)), centsNoPlan: keys(MM.match(null, cents, null)) };
const open = JSON.parse(JSON.stringify(lite)); open.accounts[0].eval.balance = 49110.0;       // an open trade: the ledger row moved, the floor did not
out.m.openNoPlan = keys(MM.match(null, open, null));
const twins = JSON.parse(JSON.stringify(lite));                                              // a 2nd fresh 25K eval: its own id, the same numbers
twins.accounts.push({ ...JSON.parse(JSON.stringify(twins.accounts[1])), id: 'b25k_3', name: 'Zlarior Builder 25K #3' });
out.m.twins = keys(MM.match(null, twins, null));
out.m.cloudHome = keys(MM.match(plan, lite, I.home));
const site = BMm.planBoard(plan, NOW); site.accounts.forEach((r) => { delete r.pc; }); site.src = 'cloud';     // a published board.json without "pc" ids
const pick = BMm.pick({ site, lite: cents, plan }, NOW);
out.m.board = pick.board.accounts.map((r) => r.name);
out.m.zeus = ZC.summary({ lite: cents, plan, site: null, BM: BMm, MM, coach: PCm }, NOW).rows.map((r) => r.name);
console.log(JSON.stringify(out));
"""


def node_part():
    tmp = tempfile.mkdtemp(prefix="feeds_acc_")
    try:
        with open(os.path.join(tmp, "in.json"), "w", encoding="utf-8") as fh:
            json.dump({"now": NOW, "posts": feed_posts(NOW), "home": cloud_home(NOW)}, fh)
        with open(os.path.join(tmp, "t.mjs"), "w", encoding="utf-8") as fh:
            fh.write(NODE)
        r = subprocess.run(["node", os.path.join(tmp, "t.mjs"), WP, tmp], capture_output=True, text=True, timeout=180)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("node part ran", False, (r.stdout[-600:], r.stderr[-1500:]))
        return
    check("1. truth.js: the cloud build alone (board 'where cloud', badge PAPER, $49,900) gives NO Zlarior / ATLAS numbers, no extra account",
          o["cloudOnly"] == {"lit": False, "atlas": False, "extra": 0}, o["cloudOnly"])
    check("1. truth.js + the PC feed: Zlarior $49,192.78 / $1,024.58, ATLAS $24,887.20 funded, + Zlarior 25K #2 (extraOf, eval, $1,500 to pass)",
          o["fed"]["lit"] == [49192.78, 1024.58] and o["fed"]["atlas"] == [24887.2, "funded"] and o["fed"]["extra"] == [["Zlarior 25K #2", 25000, 1500, "eval"]], o["fed"])
    check("1. a cloud board built after the PC's last post never beats it (pc_feed.mergeBoard: the PC's card, where 'live')",
          o["lateCloud"] == {"where": "live", "lit": 49192.78, "badge": "LIVE"}, o["lateCloud"])
    check("2. pc_feed.fetchLatest in a browser: 3 callers at once = 1 status_feed.json + 1 ntfy call, each its own copy",
          o["shared"]["calls"] == 2 and o["shared"]["ok"] and o["shared"]["sep"] == 49192.78, o["shared"])
    check("3. Jarvis data.js extraAccounts: the 25K #2 only (the 50K's own row = the lit card; the cloud twin never)",
          o["extra"] == [["Zlarior 25K #2", "25K", "eval", 1000, 1500]] and o["extraCloud"] == 0, (o["extra"], o["extraCloud"]))
    check("3. Jarvis data.js kalshiPaper: K1 0 signals, rewards -$2.32, net -$2.32 (paper only)", o["kpaper"] == [0, -2.32, -2.32], o["kpaper"])
    check("4. kalshi-brain: a 15-day-old engine copy gives no advice and its tile line says how old it is; a fresh one still does",
          o["kb"]["old"] == 0 and o["kb"]["fresh"] >= 1 and "15 days ago" in o["kb"]["line"], o["kb"])
    day = "\n".join(o["day"])
    check("5. copilot day summary: Zlarior 50K, ATLAS (funded, no 'to the target'), Zlarior 25K #2 ($1,500 to the target)",
          "Zlarior 50K:" in day and "ATLAS 25K (funded): $0 today; drawdown left $887 of $1,000." in day and "Zlarior 25K #2:" in day and "$1,500 to the target" in day, o["day"])
    check("5. copilot: Kalshi = 'real money paused' + the paper tests, never the old engine copy's '$0 today'",
          "Kalshi: real money paused. Paper tests: K1 $0.00 (0 signals), rewards -$2.32" in day and "Kalshi: $0 today" not in day, o["day"])
    check("6. the Jarvis home NQ bots strip: Zlarior, ATLAS, then 'Zlarior 25K #2' (eval, $1,500 to pass)",
          o["bots"] == [["Zlarior", "", ""], ["ATLAS", "", ""], ["Zlarior 25K #2", "", "Eval · $1,500 to pass"]] or [b[0] for b in o["bots"]] == ["Zlarior", "ATLAS", "Zlarior 25K #2"], o["bots"])
    m = o["m"]
    check("9. mffumodel.match: the bot's card and its ledger row 2 cents apart = ONE Zlarior row (plan: zlarior / atlas / rapid1 / fresh25; no plan: 3)",
          m["cents"] == ["zlarior:lit", "atlas:atlas", "rapid1", "fresh25:b25k_2"] and m["centsNoPlan"] == ["lit:lit", "atlas:atlas", "b25k_2:b25k_2"], m)
    check("9. an open trade moved the ledger balance $83 (the floor did not): still one Zlarior row", m["openNoPlan"] == ["lit:lit", "atlas:atlas", "b25k_2:b25k_2"], m["openNoPlan"])
    check("9. two different 25K evals with the same fresh numbers stay TWO accounts (own ids are never merged by balance)",
          m["twins"] == ["lit:lit", "atlas:atlas", "b25k_2:b25k_2", "b25k_3:b25k_3"], m["twins"])
    check("9. the cloud's PAPER twin in home.json ($49,900) never becomes an account", m["cloudHome"] == ["zlarior:lit", "atlas:atlas", "rapid1", "fresh25:b25k_2"], m["cloudHome"])
    check("9. Board (a board.json without pc ids) and the ZEUS card: one Zlarior, ATLAS, Zlarior 25K #2 (+ the planned Rapid on the Board)",
          m["board"] == ["Zlarior", "ATLAS", "Rapid EOD 25K (next)", "Zlarior 25K #2"] and m["zeus"] == ["Zlarior", "ATLAS", "Zlarior 25K #2"], (m["board"], m["zeus"]))
    check("7. Board / My Accounts payout coach: from the PC payout tracker (no more 'NO NUMBERS'), the ZEUS card's own words",
          o["pay"] is not None and o["pay"]["text"] == o["zeusPay"] == "Not yet: need $1,463 more." and "payout tracker" in o["pay"]["from"], (o["pay"], o["zeusPay"]))
    check("7. the payout card's 7-day inactivity line from the PC's last traded day (mf 'lt' 2026-11-18): trade by 2026-11-24",
          o["pay"] is not None and len(o["pay"]["idle"]) == 1 and o["pay"]["idle"][0].startswith("Inactivity: trade by 2026-11-24"), o["pay"])


def python_twin():
    from engine import live_site as LS
    site = {"t": NOW + 60, "where": "cloud", "lit": {"balance": 49900.0, "badge": "PAPER"}}
    lite = {"t": NOW - 240, "data_t": NOW - 240, "where": "live", "lit": {"balance": 49192.78, "badge": "LIVE"}}
    m = LS.merge_board(site, lite)
    pc_site = {**site, "where": "live"}
    check("8. engine/live_site.merge_board (the Python twin): a cloud board never wins; the PC's own newer board still does",
          m.get("where") == "live" and m["lit"]["balance"] == 49192.78 and LS.merge_board(pc_site, lite) is pc_site, m)


class Quiet(http.server.SimpleHTTPRequestHandler):
    home = b"{}"

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] == "/home.json":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(self.home)
            except OSError:          # the page moved on (a closed connection is not a failure)
                pass
            return
        try:
            return super().do_GET()
        except OSError:
            return None


def browser_part():
    from playwright.sync_api import sync_playwright
    try:
        from tests import browser_kit as BK
    except Exception:  # noqa: BLE001
        import browser_kit as BK  # type: ignore
    Quiet.home = json.dumps(cloud_home(NOW)).encode()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WP))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    body = "\n".join(json.dumps(m) for m in feed_posts(NOW)) + "\n"
    out = {}
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block")
            ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=body))
            ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith(base) and "ntfy.sh" not in r.request.url else r.fallback())
            errs = []
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.goto(base + "jarvis/", wait_until="domcontentloaded")
            pg.wait_for_function("() => /accounts/.test((document.querySelector('#nsub')||{}).textContent||'') && /PAUSED/.test((document.querySelector('#kpct')||{}).textContent||'')", timeout=30000)
            out["jarvis"] = pg.evaluate("() => ({ n: document.querySelector('#nsub').textContent, k: document.querySelector('#kpct').textContent, ku: document.querySelector('#kusd').textContent })")
            pg.goto(base + "business/accounts.html", wait_until="domcontentloaded")
            pg.wait_for_function("() => /Live numbers from your PC/.test(document.getElementById('status').textContent) && document.querySelector('#coach .st')", timeout=30000)
            out["acc"] = pg.evaluate("""() => ({ names: [...document.querySelectorAll('#list h3')].map((h) => h.textContent), coach: document.querySelector('#coach .st').textContent,
                text: document.getElementById('list').innerText })""")
            pg.goto(base + "board/", wait_until="domcontentloaded")
            pg.wait_for_function("() => document.querySelector('#payouts .st')", timeout=30000)
            out["board"] = pg.evaluate("() => ({ coach: document.querySelector('#payouts .st').textContent, rows: [...document.querySelectorAll('.brow h3')].map((h) => h.textContent) })")
            pg.goto(base + "trading/", wait_until="domcontentloaded")
            pg.wait_for_function("() => document.querySelectorAll('#accts .acct').length >= 3 && /Not yet/.test(document.getElementById('accts').innerText)", timeout=60000)
            out["trading"] = pg.evaluate("() => ({ cards: [...document.querySelectorAll('#accts .acct h3')].map((h) => h.textContent.trim()), text: document.getElementById('accts').innerText })")
            out["errs"] = errs
            ctx.close()
    finally:
        srv.shutdown()
    j = out["jarvis"]
    check("B1. Jarvis tiles: NQ BOTS TODAY '3 accounts', KALSHI TODAY 'PAUSED' + the paper net (never 'OFFLINE not connected yet')",
          j["n"].startswith("3 accounts") and j["k"] == "PAUSED" and "paper" in j["ku"] and "−$2.32" in j["ku"], j)
    a = out["acc"]
    check("B2. My Accounts: Zlarior, ATLAS, Rapid (plan), Zlarior 25K #2: no phantom 'MFFU 50K Eval' ($49,900 cloud twin)",
          "MFFU 50K Eval" not in a["names"] and "49,900" not in a["text"] and "Zlarior 25K #2" in a["names"], a["names"])
    check("B2. My Accounts: the payout coach from the PC (NOT YET), ATLAS's payout line, each account's source + age",
          a["coach"] == "NOT YET" and "Not yet: need $1,463 more." in a["text"] and a["text"].count("Numbers: PC live feed") == 3, (a["coach"], a["text"][:600]))
    b = out["board"]
    check("B3. Board: the payout coach reads the PC's tracker (NOT YET, not NO NUMBERS); 3 account rows", b["coach"] == "NOT YET" and len(b["rows"]) >= 3, b)
    t = out["trading"]
    check("B4. Trading Today: Zlarior, ATLAS, Zlarior 25K #2; funded ATLAS shows the payout line, not 'To pass $1,963'",
          len(t["cards"]) == 3 and t["cards"][2].startswith("Zlarior 25K #2") and "Payout" in t["text"] and "1,963" not in t["text"], t)
    check("B5. no page errors", not out["errs"], out["errs"])


def main() -> int:
    node_part()
    python_twin()
    if os.environ.get("FEEDS_NO_BROWSER") != "1":
        browser_part()
    n, ok = len(RES), sum(RES)
    print(f"feeds accounts: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
