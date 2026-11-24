"""Every account number from the PC's status post, never the cloud's paper twin (night-feedsB 2026-11-18, owner: "everything with
accounts, all live feed fixed"; ready for trading tonight).

Since GitHub stopped, the site's home.json / data.json are the CLOUD's copy: its board is built from its own paper twin on bars that
stopped weeks ago (Zlarior $49,900, room $1,900, "ATLAS account is not set up", "the PC has not reported yet", NQ 29,391 at a 16:55
bar of Oct 16). The PC posts the real numbers every 15 minutes (ntfy, tools/pc_report.py). Found on the live site at 390 x 844:
false alerts on Home, ATLAS "Blocked / not bought yet / PAPER" while it trades a FUNDED 25K, the Zlarior 25K #2 missing, the cockpit
mixing the 25K #2 with the 50K rules ("$28,000 to pass"), the Zlarior / eval pages on the twin's $49,900, "This week" $0 while both
bots traded, Ares / Argus / Nemesis / Forum ... "LIVE ACCOUNT $49,900, $1,900 left".

  a. node (no browser): pc_feed.js boardOver (a cloud board lends only its calendar: no lines / blocks / stage / sizing / position /
     map / week of the twin; the PC's lines win even empty; the PC's price; this week's real trades per bot; the extra 25K #2 card),
     accountsOver / eval50 / payoutLines (the payout coach's "need $1,463 more" = the ZEUS card) / homeOver (input untouched); the
     cores (statuscore: a 17-min-old post is fresh and says "PC reported"; moneynowcore: the 25K #2 row, "25K funded"; missioncore:
     "To a payout"); litkit realEval = the 50K, never the 25K #2 or the cloud's PAPER placeholder; Aegis / Demeter extra accounts;
     home_feed.js answers an app's fetch of the site's home.json / data.json with the PC's numbers (an app's own data.json and a page
     with no post are left alone)
  b. Chromium 390 x 844 on a copy of tools/web_public with the cloud's stale home.json / data.json and the PC's post on ntfy:
     Home (no false alert, Money now 3 rows, "to a payout $1,463", This week 1 / -$129 and 1 / -$113, NQ = the PC's price, the
     header says "PC reported"), Zlarior tab, ATLAS tab (LIVE, funded, the coach line), eval + cockpit (the real 50K), Money,
     Accounts (order, no twin advice), News (old build said), Ares / Demeter / Aegis (the PC's numbers); then the same site with
     NO post: the old numbers, no error (the fixes only act on a PC post)

    python -X utf8 -m tests.test_feed_accounts            (--node: part a only;  --shots DIR: phone screenshots)
"""
from __future__ import annotations

import copy
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"), flush=True)
    return bool(cond)


# ------------------------------------------------------------------------------------------------ the fixture (fake last-4 digits only)
T = 1795044000                     # Wed 2026-11-18 18:20 ET: the session is over, the CME day is Thu 11-19
HB, RT = T - 600, T - 300          # the bot's heartbeat 18:10 ET, the PC's post 18:15 ET
Z_TR = [1794827760, 1794830400, 1, 1, 27799.5, 27735.25, 28174.0, "STOP", -129.4, -1.01]       # Mon 11-16 03:16 ET, Zlarior 50K
A_TR = [1794995400, 1794996603, -1, 2, 27395.5, 27422.5, 27179.5, "STOP", -112.8, -1.04]       # Wed 11-18 05:10 ET, ATLAS


def lite_core():
    conn = {"present": True, "t": HB, "running": True, "connected": True}
    return {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": HB, "every_s": 300, "price": 27360.5, "day_pnl": 0,
            "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "good", "reason": "routing to the eval through NinjaTrader", "in_session": False, "hb_age_s": 0, "t": HB},
            "pc": {"running": True, "adapter": "ninjatrader", "position": False, "model": "lit", "present": True, "t": HB, "age_s": 0, "silent": False, "every_s": 300},
            "reporter": {"t": RT, "server": True, "nt": True, "market_open": True, "mode": "LIVE", "hb_src": "pc_hb", "problems": []},
            "board": {"v": 1, "kind": "le-board", "t": HB, "data_t": HB, "where": "live", "today": "2026-11-19", "running": True, "level": "good",
                      "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "method": "LIT", "badge": "LIVE", "source": "PC bot", "balance": 49192.78, "floor": 48168.2,
                              "room": 1024.58, "mll": 2000.0, "to_target": 3807.22, "target_balance": 53000.0, "profit": -807.22, "today_pnl": 0.0, "week_pnl": -129.4, "status": "open",
                              "session": 24, "sessions": 10, "dll": 1000.0, "dll_used": 0.0, "trades_today": 0, "max_day": 1, "room_frac": 0.5123,
                              "window": {"open": False, "text": "next entry window Thu 02:00-15:30 ET"}, "waiting": "Before 02:00 ET (no entries yet)"},
                      "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "method": "EMA · MACD · S/R", "badge": "LIVE", "source": "PC bot (account B)",
                                "configured": True, "balance": 24887.2, "floor": 24000.0, "room": 887.2, "mll": 1000.0, "to_target": 1962.8, "target_balance": 26850.0,
                                "profit": -112.8, "today_pnl": 0.0, "status": "funded", "session": 3, "dll": 600.0, "trades_today": 0, "max_day": 2, "room_frac": 0.8872,
                                "window": {"open": False, "text": "next entry window Thu 02:00-05:00 ET"}, "waiting": "All 3 members are outside their hours."},
                      "lines": []},
            "accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "LIVE", "conn": dict(conn),
                          "eval": {"start_balance": 50000.0, "balance": 49192.78, "profit": -807.22, "to_target": 3807.22, "target_balance": 53000.0, "floor": 48168.2,
                                   "room": 1024.58, "mll": 2000.0, "dll": 1000.0, "dll_used": 0.0, "today": 0.0, "session": 24, "status": "open"},
                          "pnl": {"today": 0.0, "week": -129.4, "since_start": -229.4, "traded": -129.4}, "running": True, "trades": [], "days": []},
                         {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc", "badge": "LIVE", "conn": dict(conn),
                          "eval": {"start_balance": 25000.0, "balance": 25000.0, "profit": 0.0, "to_target": 1500.0, "target_balance": 26500.0, "floor": 24000.0, "room": 1000.0,
                                   "mll": 1000.0, "dll": 600.0, "dll_used": 0.0, "today": 0.0, "session": 2, "status": "open"},
                          "pnl": {"today": 0.0, "week": 0, "since_start": 0, "traded": 0}, "running": True, "trades": [], "days": []}],
            "xt": RT}


def lite_ext():
    return {"v": 1, "kind": "le-live-ext", "src": "pc_report", "t": HB, "rt": RT, "part": 0, "of": 1, "x": {
        "mf": {"t": HB, "a": [{"id": "mffu50k_eval", "sd": "2026-10-19", "l4": "0001", "td": 1, "n": 1},
                              {"id": "b25k_2", "sd": "2026-11-18", "l4": "0002"},
                              {"id": "atlas", "sd": "2026-11-17", "l4": "0003", "td": 1, "n": 1, "f": {"cp": -113, "bd": -113, "cd": 1, "ef": "2026-11-20", "pn": 0, "mr": 0}}]},
        "board_trades": [{"acct": "atlas", "src": "live", "key": "macd_sweep", "member": "MACD", "day": "2026-11-18", "entry_t": A_TR[0], "exit_t": A_TR[1], "side": "SHORT",
                          "qty": 2, "exit": "STOP", "r": -1.044, "usd": -112.8, "open": False},
                         {"acct": "atlas", "src": "paper", "key": "ema_lon_vix", "member": "EMA", "day": "2026-11-17", "entry_t": 1794921600, "exit_t": 1794930300, "side": "SHORT",
                          "qty": 3, "exit": "TARGET", "r": 6.865, "usd": 2687.84, "open": False}],
        "at": {"t": HB, "a": [{"id": "mffu50k_eval", "tr": [Z_TR], "l4": "0001"}, {"id": "atlas", "tr": [A_TR], "l4": "0003"}]}}}


def ntfy_lines(core=None, ext=None):
    out = []
    for i, j in enumerate([ext or lite_ext(), core or lite_core()]):
        out.append(json.dumps({"id": f"m{i}", "time": RT, "event": "message", "topic": "t", "message": json.dumps(j)}))
    return "\n".join(out) + "\n"


def cloud_home():
    """the cloud's stale copy: its paper twin, its false alerts, a month-old map and news build"""
    days = [{"day": d, "wd": w, "n": 0, "usd": 0, "future": d > "2026-11-19", "today": d == "2026-11-19"}
            for d, w in (("2026-11-16", "Mon"), ("2026-11-17", "Tue"), ("2026-11-18", "Wed"), ("2026-11-19", "Thu"), ("2026-11-20", "Fri"))]
    win_lit = {"open": False, "open_t": T + 27600, "close_t": T + 76200, "text": "next entry window Thu 02:00-15:30 ET"}
    win_at = {"open": False, "open_t": T + 27600, "close_t": T + 38400, "text": "next entry window Thu 02:00-05:00 ET"}
    board = {"v": 1, "kind": "le-board", "t": T - 1200, "data_t": T - 1200, "where": "cloud", "today": "2026-11-19", "running": True, "level": "bad",
             "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "method": "LIT", "badge": "PAPER", "source": "cloud paper", "balance": 49900.0, "floor": 48000.0,
                     "room": 1900.0, "mll": 2000.0, "to_target": 3100.0, "target_balance": 53000.0, "profit": -100.0, "today_pnl": 0.0, "week_pnl": 0.0, "status": "open",
                     "session": 24, "sessions": 10, "dll": 1000.0, "dll_used": 0.0, "max_day": 1, "trades_today": 0, "room_frac": 0.95,
                     "stage": {"key": "levels", "label": "Levels", "n": 1, "of": 10}, "waiting": "New session: waiting for the first bars of 2026-10-16. Entries from 02:00 ET.",
                     "windows": [dict(win_lit, day="2026-11-19", label="Thu 02:00-15:30 ET")], "window": win_lit,
                     "micros": {"qty": 5, "risk_usd": 470.0, "what": "the cloud twin's size"}, "position": None, "blocks": [], "days": []},
             "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "method": "EMA · MACD · S/R", "badge": None, "configured": False, "source": "none", "balance": None,
                       "room": None, "mll": 1000.0, "status": "not set up", "sessions": 10, "dll": 600.0, "max_day": 2, "max_micros": 20,
                       "members": [{"key": "ema_lon_vix", "short": "EMA", "stage": "armed", "text": "the cloud says armed", "windows": [dict(win_at)]},
                                   {"key": "macd_sweep", "short": "MACD", "stage": None, "text": ""}, {"key": "sr_nyreclaim", "short": "S/R", "stage": None, "text": ""}],
                       "blocks": [{"text": "ATLAS account (account B) is not set up on the PC", "kind": "account", "fix": "Start & Accounts page on the PC", "scope": "atlas"}],
                       "window": win_at},
             "lines": [{"level": "bad", "text": "The PC has not reported yet (no heartbeat). Fix: Check the Surface is on", "kind": "silent"},
                       {"level": "bad", "text": "ATLAS: ATLAS account (account B) is not set up on the PC.", "kind": "account"}],
             "blocks": [{"text": "The PC has not reported yet (no heartbeat)", "kind": "silent", "fix": "Check the Surface is on", "scope": "both"}],
             "map": {"price": 29391.25, "atr": 35.49, "bar_hm": "16:55", "t": T - 1200, "vix": {"vix": 16.46, "up": 30400.99, "dn": 29777.01},
                     "nearest_above": {"label": "equal highs", "price": 30129.75, "dist": 738.5}, "nearest_below": {"label": "PML", "price": 29053.0, "dist": -338.25}},
             "progress": {"lit": {"week": {"n": 0, "lo": 2, "hi": 4, "status": "on_pace", "usd": 0.0, "days": copy.deepcopy(days)}, "sessions": 10, "min_days": 2},
                          "atlas": {"week": {"n": 0, "lo": 3, "hi": 4, "status": "behind", "usd": 0.0, "days": copy.deepcopy(days)}, "sessions": 10, "min_days": 2}},
             "health": {"items": [], "level": "good", "text": "all green"}, "trades": [], "hidden_bots": ["blitz"]}
    paper_eval = {"start_balance": 50000.0, "balance": 49900.0, "profit": -100.0, "to_target": 3100.0, "target_balance": 53000.0, "floor": 48000.0, "room": 1900.0,
                  "mll": 2000.0, "dll": 1000.0, "dll_used": 0.0, "today": 0.0, "session": 24, "sessions": 10, "status": "open", "start": "2026-10-19"}
    accounts = [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "PAPER",
                 "conn": {"present": False, "t": None, "has_detail": False}, "eval": dict(paper_eval), "pnl": {"today": 0, "week": 0, "since_start": -100},
                 "stats": {"n": 7, "win_pct": 71.0, "pf": 9.9}, "position": {"side": "LONG", "qty": 5, "entry": 29380.0, "stop": 29330.0, "target": 29700.0}, "trades": [], "days": []},
                {"id": "cloud_paper", "name": "Paper (cloud)", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval", "source": "cloud", "badge": "PAPER",
                 "conn": {"present": True, "t": T - 1200, "has_detail": True}, "eval": dict(paper_eval), "pnl": {"today": 0, "week": 0, "since_start": -100}, "trades": [], "days": []}]
    second = {"paper": True, "account_b": None, "note": "Paper only", "atlas": {"name": "ATLAS", "members": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]},
              "strategies": [{"key": "ema_lon_vix", "short": "EMA", "label": "EMA London", "trades": []}, {"key": "macd_sweep", "short": "MACD", "label": "MACD sweep", "trades": []},
                             {"key": "sr_nyreclaim", "short": "S/R", "label": "S/R NY reclaim", "trades": []}]}
    return {"built": "2026-11-18T23:00:44+00:00", "board": board, "accounts": accounts, "second": second, "hidden_bots": ["blitz"],
            "live": {"last_run": T - 1200, "runs": 5, "eval": {"balance": 49900.0, "profit": -100.0, "to_target": 3100.0, "trailing_mll": 48000.0, "cushion": 1900.0, "start": "2026-10-19"},
                     "pc": {"present": False, "t": None}, "price": 29391.25, "today": "2026-11-19", "ledger": [], "bars": []},
            "news": {"built": "2026-10-17T21:37:59+00:00", "built_t": 1792273079, "offline": True, "events": [], "days": [], "headlines": [], "sources": [], "notes": []},
            "results": {"periods": {}}, "trades": [], "strategy": {}, "goals": {"calendar": {"news": []}}}


# ------------------------------------------------------------------------------------------------ a. node
NODE = r"""
const path = require('path'), fs = require('fs'), [web, fixPath] = process.argv.slice(2);
const FX = JSON.parse(fs.readFileSync(fixPath, 'utf8'));
globalThis.window = globalThis;
const F = require(path.join(web, 'pc_feed.js')), C = require(path.join(web, 'business', 'payoutcoach.js'));
const out = {};
const lite = F.parseLatest(FX.ndjson), home = FX.home, homeCopy = JSON.stringify(home), T = FX.T;
const b = F.boardOver(home.board, lite, T);
out.board = { lines: b.lines, blocks: b.blocks || null, atlasBlocks: b.atlas.blocks || null, litStage: b.lit.stage || null, litMicros: b.lit.micros || null,
  litPos: b.lit.position || null, map: b.map, weekLit: b.progress.lit.week, weekAtlas: b.progress.atlas.week, litWin: b.lit.window, members: b.atlas.members,
  report_t: b.report_t, feed: b.feed, extra: b.accounts, litWindows: (b.lit.windows || []).length, atlasStatus: b.atlas.status, atlasWeek: b.atlas.week_pnl,
  goalKept: b.progress.lit.goal, oddsGone: b.progress.lit.week.src, quiet: [b.lit.quiet_days, b.lit.last_trade_day, b.atlas.quiet_days, (b.accounts[0] || {}).quiet_days] };
// an old PC copy (not the cloud's) keeps the old merge: its map / progress stay, the PC's empty lines win
const pcCopy = JSON.parse(JSON.stringify(home.board)); pcCopy.where = 'live'; pcCopy.t = pcCopy.data_t = T - 7200;
const m2 = F.mergeBoard(pcCopy, lite.board);
out.oldPath = { map: !!m2.map, progress: !!m2.progress, lines: m2.lines.length, room: m2.lit.room };
const A = F.accountsOver(home.accounts, lite, b);
out.accts = A.map((a) => [a.id, a.name, a.badge, a.live || false, a.eval && a.eval.balance, a.position || null, a.stats || null, (a.trades || []).length, (a.days || []).length]);
out.e50 = F.eval50(A, home.live.eval, lite.t);
const noCoach = JSON.parse(JSON.stringify(b)); out.missing = F.payoutLines(noCoach, A, lite, null); out.noCoachTo = noCoach.atlas.to_target;
out.coached = F.payoutLines(b, A, lite, C, '2026-11-18'); out.atlasPay = [b.atlas.to_target, b.atlas.payout_text, b.atlas.pc_to_target];
out.atlasAcct = A.find((a) => a.id === 'atlas').eval.to_target;
const h = F.homeOver(home, lite, T, C);
out.home = { accts: h.accounts.length, first: h.accounts[0].name, eval: h.live.eval.balance, real: h.live.eval.real, paper: h.live.eval_paper && h.live.eval_paper.balance,
  price: h.live.price, pc: h.live.pc.t, atlasTo: h.board.atlas.to_target, untouched: JSON.stringify(home) === homeCopy, none: F.homeOver(home, null, T) === home };
// the cores in a stub window
globalThis.document = { getElementById: () => null, createElement: () => ({}), head: { appendChild() {} } };
globalThis.OLY_HIDDEN = new Set(['blitz']);
for (const f of ['missioncore.js', 'statuscore.js', 'moneynowcore.js']) eval(fs.readFileSync(path.join(web, f), 'utf8'));
const M = { now: T + 1020 - 300, where: 'phone', board: b };          // 17 min after the post
const items = window.StatusUI.items(M), pcIt = items.find((x) => x.k === 'pc');
out.pcItem = [pcIt.lvl, pcIt.value, pcIt.detail];
const M2 = { now: T + 2400, where: 'phone', board: b };              // 45 min after: quiet
out.pcQuiet = window.StatusUI.items(M2).find((x) => x.k === 'pc').lvl;
const MN = window.MoneyNow.model(M);
out.mn = MN.rows.map((r) => [r.key, r.name, r.size, r.room, r.status.text]);
out.mnBot = MN.bot.text;
out.acctsHTML = window.StatusUI.accounts(M, { where: 'phone' });
out.mission = window.MissionUI.strip ? window.MissionUI.strip(M, {}) : '';
console.log(JSON.stringify(out));
"""

NODE_MODS = r"""
const path = require('path'), fs = require('fs'), [web, fixPath] = process.argv.slice(2);
const FX = JSON.parse(fs.readFileSync(fixPath, 'utf8'));
globalThis.window = globalThis;
const F = require(path.join(web, 'pc_feed.js')), C = require(path.join(web, 'business', 'payoutcoach.js'));
const { pathToFileURL } = require('url');
(async () => {
  const out = {};
  const lite = F.parseLatest(FX.ndjson), H = F.homeOver(FX.home, lite, FX.T, C);
  const LK = await import(pathToFileURL(path.join(web, 'litkit.js')).href);
  const c1 = LK.fromCloud(H, FX.T), c0 = LK.fromCloud(FX.home, FX.T);
  // the 25K #2 listed FIRST must not become the 50K's eval (the "$28,000 to pass" bug)
  const H2 = JSON.parse(JSON.stringify(H)); H2.accounts.unshift(H2.accounts.splice(1, 1)[0]); H2.live.eval = FX.home.live.eval;
  const c2 = LK.fromCloud(H2, FX.T);
  out.lk = { real: c1.eval && [c1.eval.balance, c1.eval.cushion, c1.eval.real], cloud: c0.eval && [c0.eval.balance, !!c0.eval.real], first25: c2.eval && c2.eval.balance };
  const AE = await import(pathToFileURL(path.join(web, 'aegis', 'aegiscore.js')).href);
  const ae = AE.buildAccounts(H, null, null);
  out.aegis = ae.accounts.map((a) => [a.key, a.name, a.room, a.balance]);
  // the NQ page (nq/nqcore.js): the post's three accounts by the ZEUS card's names, the post's time (fresh for 30 min), the funded line
  const NQ = await import(pathToFileURL(path.join(web, 'nq', 'nqcore.js')).href);
  const nv = NQ.build(H, (FX.T + 17 * 60 - 300) * 1000), nc = NQ.build(FX.home, FX.T * 1000);
  out.nq = { names: nv.bots.map((b) => b.name), tags: nv.bots.map((b) => b.tag), dd: nv.bots.map((b) => b.ddLine), flames: nv.bots.map((b) => b.status.flame), head: nv.headline,
    atlas: nv.bots[1].progLine, plan: nv.bots[1].plan, cloudNames: nc.bots.map((b) => b.name), cloudHead: nc.headline,
    cloudHas: nc.bots.map((b) => b.has), cloudDd: nc.bots.map((b) => b.ddLine), cloudCopy: [NQ.cloudCopy(FX.home), NQ.cloudCopy(H)] };
  const DE = await import(pathToFileURL(path.join(web, 'demeter', 'demetercore.js')).href);
  const de = DE.buildAccounts(H, null, null);
  out.demeter = de.accounts.map((a) => [a.key, a.name, a.room, a.balance, a.toTarget]);
  // home_feed.js in a stub page: the app's fetch of home.json gets the PC's numbers; other files and no-post pages are left alone
  async function page(ndjson, have = true) {
    const loaded = {};
    // the page's own copies of pc_feed.js / payoutcoach.js (the shim imports them when missing: http:// cannot be imported in node,
    // which is the "file missing" case of a real page)
    const win = { location: { href: 'http://site/ares/', origin: 'http://site', search: '' }, ...(have ? { PC_FEED: F, PAYOUT_COACH: C } : {}) };
    const doc = { currentScript: { src: 'http://site/home_feed.js?v=4' }, documentElement: {},
      createElement: () => { throw new Error('no script tags: a failed one would trip the OLYMPUS kit'); }, head: { appendChild() { throw new Error('no script tags'); } } };
    const calls = [];
    win.fetch = async (u) => {
      calls.push(String(u));
      if (/status_feed\.json/.test(u)) return new Response(JSON.stringify({ ntfy: 'https://ntfy.sh', topic: 'olympus-nq-status-0123456789abcdef' }));
      if (/ntfy\.sh/.test(u)) return new Response(ndjson);
      if (/\/ares\/data\.json$|^data\.json$/.test(u)) return new Response('{"own":1}');
      if (/home\.json|data\.json/.test(u)) return new Response(JSON.stringify(FX.home));
      return new Response('{"other":1}');
    };
    const src = fs.readFileSync(path.join(web, 'home_feed.js'), 'utf8');
    new Function('window', 'document', 'location', src)(win, doc, win.location);
    const h = await (await win.fetch('../home.json', { cache: 'no-cache' })).json();
    const dj = await (await win.fetch('../data.json')).json();
    const own = await (await win.fetch('data.json')).json();          // an app's OWN data.json (/ares/data.json) is never touched
    const other = await (await win.fetch('../ledger/rules.json')).json();
    return { h, dj, own, other, loaded: Object.keys(loaded), used: win.HOME_FEED.used };
  }
  const p1 = await page(FX.ndjson), p0 = await page('{}'), pm = await page(FX.ndjson, false);
  out.shim = { bal: p1.h.accounts[0].eval.balance, name: p1.h.accounts[0].name, eval: p1.h.live.eval.balance, lines: p1.h.board.lines.length, used: p1.used,
    other: p1.other.other, noPost: p0.h.accounts[0].eval.balance, noPostUsed: p0.used, data: p1.dj.accounts[0].eval.balance, own: p1.own.own,
    missing: pm.h.accounts[0].eval.balance, missingUsed: pm.used };
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ error: String(e && e.stack || e) })); });
"""


def node_bin():
    return shutil.which("node")


def run_node(script, tmp):
    fx = os.path.join(tmp, "fx.json")
    json.dump({"ndjson": ntfy_lines(), "home": cloud_home(), "T": T}, open(fx, "w"))
    js = os.path.join(tmp, "t.cjs")
    open(js, "w").write(script)
    r = subprocess.run([node_bin(), js, WEB, fx], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {"error": (r.stdout[-600:] + r.stderr[-1500:])}


def part_a(tmp):
    if not node_bin():
        check("a. node is not installed: node checks skipped", True)
        return
    o = run_node(NODE, tmp)
    if not check("a. node: pc_feed.js + the cores run on the fixture", "error" not in o, o.get("error")):
        return
    B = o["board"]
    check("a. a cloud board under the PC's: the PC's lines win even empty; no cloud block, ATLAS 'not set up' block, setup stage, sizing or position",
          B["lines"] == [] and B["blocks"] is None and B["atlasBlocks"] is None and B["litStage"] is None and B["litMicros"] is None and B["litPos"] is None
          and B["atlasStatus"] == "funded", B)
    check("a. it lends only its calendar: the windows (times when the cloud names the same window), ATLAS's members without the cloud's stage",
          B["litWindows"] == 1 and B["litWin"].get("open_t") == T + 27600 and B["litWin"].get("close_t") == T + 76200
          and [m.get("key") for m in B["members"]] == ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"] and all("stage" not in m and "text" not in m for m in B["members"]), B["members"])
    check("a. the map is the PC's price at its own time (18:10 ET), not the cloud's 29,391 of a 16:55 bar; report_t = the post's time",
          B["map"] == {"price": 27360.5, "t": HB, "bar_hm": "18:10", "src": "pc"} and B["report_t"] == RT and B["feed"] == "ntfy", B["map"])
    wl, wa = B["weekLit"], B["weekAtlas"]
    check("a. this week from the PC's real trades: Zlarior 1 (Mon -$129.40, the PC's own week $), ATLAS 1 (Wed -$112.80); goals 2-4 / 3-4 kept; today = Thu",
          wl["n"] == 1 and wl["usd"] == -129.4 and wl["days"][0]["n"] == 1 and wl["days"][0]["usd"] == -129.4 and wl["days"][3]["today"] and wl["lo"] == 2 and wl["hi"] == 4
          and wa["n"] == 1 and wa["usd"] == -112.8 and wa["days"][2]["n"] == 1 and wa["lo"] == 3 and wa["hi"] == 4 and wl["src"] == "pc" and B["atlasWeek"] == -112.8, (wl, wa))
    ex = B["extra"] or []
    check("a. the Zlarior 25K #2 is an extra board card (MissionUI shows it): its numbers, LIVE, Zlarior's window (the same LIT signal)",
          len(ex) == 1 and ex[0]["id"] == "b25k_2" and ex[0]["name"] == "Zlarior 25K #2" and ex[0]["balance"] == 25000 and ex[0]["to_target"] == 1500 and ex[0]["room"] == 1000
          and ex[0]["badge"] == "LIVE" and (ex[0].get("window") or {}).get("open_t") == T + 27600, ex)
    check("a. MFFU's 7-day inactivity clock from the post's own trades: Zlarior 50K 2 days (Mon 11-16), ATLAS 0; none for an account with no trade yet",
          B["quiet"] == [2, "2026-11-16", 0, None], B["quiet"])
    check("a. an older PC copy (not the cloud's) keeps the old merge (map, progress), and the PC's empty lines win there too",
          o["oldPath"] == {"map": True, "progress": True, "lines": 0, "room": 1024.58}, o["oldPath"])
    acc = o["accts"]
    check("a. accounts: the PC's first in its order with the ZEUS card's names, ATLAS from its board card, the cloud's twin last",
          [a[0] for a in acc] == ["mffu50k_eval", "b25k_2", "atlas", "cloud_paper"] and [a[1] for a in acc][:3] == ["Zlarior 50K", "Zlarior 25K #2", "ATLAS"]
          and [a[2] for a in acc] == ["LIVE", "LIVE", "LIVE", "PAPER"] and [a[3] for a in acc] == [True, True, True, False], acc)
    check("a. the cloud's PAPER copy of the 50K lends no position / stats (its paper twin's); the real trades come from the post (1 Zlarior, 1 ATLAS)",
          acc[0][5] is None and acc[0][6] is None and acc[0][7] == 1 and acc[0][8] == 1 and acc[2][7] == 1 and acc[1][7] == 0, acc)
    e = o["e50"] or {}
    check("a. eval50 = the real 50K in live.eval's keys ($49,192.78, floor $48,168.20, $1,024.58 left), the paper eval's start kept",
          e.get("balance") == 49192.78 and e.get("trailing_mll") == 48168.2 and e.get("cushion") == 1024.58 and e.get("real") is True and e.get("start") == "2026-10-19", e)
    check("a. payout line = the payout coach's (the ZEUS card's): ATLAS funded 'need $1,463 more' (the PC's own $1,963 line kept aside); no coach = no number",
          o["atlasPay"][0] == 1462.8 and o["atlasPay"][1] == "Not yet: need $1,463 more." and o["atlasPay"][2] == 1962.8 and o["coached"] is False
          and o["missing"] is True and o["noCoachTo"] is None and o["atlasAcct"] == 1462.8, (o["atlasPay"], o["missing"], o["noCoachTo"]))
    h = o["home"]
    check("a. homeOver: one home.json with all of it (4 accounts, Zlarior 50K first, the real eval, the paper one kept aside, the PC's price); the input untouched; no post = the same object",
          h == {"accts": 4, "first": "Zlarior 50K", "eval": 49192.78, "real": True, "paper": 49900.0, "price": 27360.5, "pc": HB, "atlasTo": 1462.8, "untouched": True, "none": True}, h)
    check("a. statuscore: a post 17 min old is fresh and says 'Last report from the PC 17 min ago' (the ZEUS card's minutes); quiet only after 30 min",
          o["pcItem"][0] == "good" and o["pcItem"][1] == "17 min ago" and o["pcItem"][2] == "Last report from the PC 17 min ago." and o["pcQuiet"] in ("warn", "bad"), (o["pcItem"], o["pcQuiet"]))
    check("a. Money now: Zlarior 50K, ATLAS '25K funded', the Zlarior 25K #2 row; no 'Blocked'; 'Bot running · PC reported 17 min ago'",
          [r[0] for r in o["mn"]] == ["lit", "atlas", "b25k_2"] and o["mn"][1][2] == "25K funded" and o["mn"][2][1] == "Zlarior 25K #2" and o["mn"][2][3] == 1000
          and not any(r[4] == "Blocked" for r in o["mn"]) and o["mnBot"] == "Bot running · PC reported 17 min ago", (o["mn"], o["mnBot"]))
    ah = o["acctsHTML"]
    check("a. the account cards: ATLAS '$1,463 to a payout' (never 'to the target'), a card for the Zlarior 25K #2 ($1,500 to the target)",
          "$1,463" in ah and "to a payout" in ah and 'data-bot="b25k_2"' in ah and "Zlarior 25K #2" in ah and "$1,500" in ah and ah.count(' data-bot="') == 3, ah[:600])
    check("a. Mission Control: ATLAS 'to a payout', three chips", "to a payout" in o["mission"] and o["mission"].count('class="mc-chip st-') == 3, o["mission"][:400])
    m = run_node(NODE_MODS, tmp)
    if not check("a. node: litkit / Aegis / Demeter / home_feed.js run", "error" not in m, m.get("error")):
        return
    lk = m["lk"]
    check("a. litkit realEval: the PC's 50K ($49,192.78, $1,024.58 room); the cloud's PAPER placeholder is never 'real'; the 25K #2 listed first is never the 50K",
          lk["real"] == [49192.78, 1024.58, True] and lk["cloud"] == [49900.0, False] and lk["first25"] == 49192.78, lk)
    q = m["nq"]
    check("a. NQ page core: Zlarior (LIT 50K $1,025), ATLAS (25K funded, the coach line), Zlarior 25K #2 (LIT 25K $1,000), all lit by the post 17 min old, 'All 3 accounts reported'",
          q["names"] == ["Zlarior", "ATLAS", "Zlarior 25K #2"] and q["tags"] == ["LIT 50K", "25K funded", "LIT 25K"] and q["dd"] == ["Drawdown left $1,025 of $2,000 max loss", "Drawdown left $887 of $1,000 max loss", "Drawdown left $1,000 of $1,000 max loss"]
          and q["flames"] == [True, True, True] and q["head"].startswith("All 3 accounts reported 17 minutes ago") and q["atlas"] == "Not yet: need $1,463 more." and q["plan"] == "MFFU Builder 25K funded", q)
    check("a. NQ page core without the post: Zlarior and ATLAS with NO numbers (the cloud's paper twin's $1,900 is never shown as the account), 'Waiting for your PC's status report'",
          q["cloudNames"] == ["Zlarior", "ATLAS"] and q["cloudHas"] == [False, False] and q["cloudDd"] == ["Drawdown not reported yet"] * 2
          and q["cloudHead"].startswith("Waiting for your PC's status report") and q["cloudCopy"] == [True, False], q)
    ae, de = m["aegis"], m["demeter"]
    check("a. Aegis: Zlarior 50K $1,024.58, ATLAS $887.20, and the Zlarior 25K #2 ($1,000) as its own account",
          [x[1] for x in ae] == ["Zlarior", "ATLAS", "Zlarior 25K #2"] and ae[0][2] == 1024.58 and ae[1][2] == 887.2 and ae[2][2] == 1000, ae)
    check("a. Demeter: the same three accounts and numbers (its own home.json was the cloud's $1,900)",
          [x[1] for x in de] == ["Zlarior", "ATLAS", "Zlarior 25K #2"] and de[0][2] == 1024.58 and de[0][3] == 49192.78 and de[2][4] == 1500, de)
    s = m["shim"]
    check("a. home_feed.js: an app's fetch of home.json gets the PC's numbers (Zlarior 50K $49,192.78, real eval, no false lines); other files untouched; no post = the cloud's file",
          s["bal"] == 49192.78 and s["name"] == "Zlarior 50K" and s["eval"] == 49192.78 and s["lines"] == 0 and s["used"] is True and s["other"] == 1
          and s["noPost"] == 49900.0 and s["noPostUsed"] is False and s["data"] == 49192.78 and s["own"] == 1, s)
    check("a. home_feed.js never adds a <script> tag (a failed one trips the OLYMPUS kit's 'could not load'): a missing pc_feed.js leaves home.json as it was",
          s["missing"] == 49900.0 and s["missingUsed"] is False, s)


# ------------------------------------------------------------------------------------------------ b. phone
def serve(d):
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=d, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def site(tmp):
    s = os.path.join(tmp, "site")
    shutil.copytree(WEB, s, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options", "charts", "replays", "runs"))
    h = cloud_home()
    for n in ("data.json", "home.json"):
        json.dump(h, open(os.path.join(s, n), "w"))
    return s


def part_b(tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        print("[SKIP] b. playwright not installed")
        return
    from tests import browser_kit as BK
    s = site(tmp)
    srv = serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    nd = ntfy_lines()
    with sync_playwright() as pw:
        br = BK.launch(pw)

        def ctx_for(post=True):
            c = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, timezone_id="America/New_York", reduced_motion="reduce")
            c.clock.install(time=T)
            c.route("https://ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=nd if post else "{}"))
            return c

        errs = []
        c = ctx_for(True)
        pg = c.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))

        def text():
            return pg.evaluate("() => document.body.innerText")

        def go(h, cond, ms=25000):
            pg.goto(base + "index.html" + h)
            try:
                pg.wait_for_function(cond, timeout=ms)
                return True
            except Exception:  # noqa: BLE001
                return False

        sh = (lambda n: pg.screenshot(path=os.path.join(shots, n), full_page=False)) if shots else (lambda n: None)
        ok = go("#/today", "() => { const c = document.querySelector('#mnCard'); return c && c.textContent.includes('25K #2') && document.body.innerText.includes('This week') && document.body.innerText.includes('$1,463') }")
        t = text()
        mn = pg.evaluate("() => (document.querySelector('#mnCard') || {}).innerText || ''")
        check("b. Home: Money now = Zlarior 50K, ATLAS 25K funded, Zlarior 25K #2; no 'Blocked'", ok and "Zlarior 50K" in mn and "ATLAS 25K funded" in mn and "Zlarior 25K #2" in mn
              and "Blocked" not in mn and "$1,025" in mn and "$887" in mn, mn[:400])
        check("b. Home: no false alert from the cloud's copy ('has not reported', 'not set up'), Alerts none",
              "has not reported" not in t and "not set up" not in t and "Alerts · none" in t, [x for x in t.split("\n") if "report" in x or "set up" in x][:6])
        check("b. Home: ATLAS '$1,463 to a payout' (the ZEUS card's coach line), the 25K #2 card", "to a payout" in t and "$1,463" in t and "Zlarior 25K #2" in t)
        wk = pg.evaluate("() => (document.querySelector('.su-week') || {}).innerText || ''")
        check("b. Home: This week · real trades = Zlarior 1 (-$129), ATLAS 1 (-$113)", "1/2-4" in wk.replace("\n", "") and "−$129" in wk and "1/3-4" in wk.replace("\n", "") and "−$113" in wk, wk)
        mk = pg.evaluate("() => (document.querySelector('.su-mkt') || {}).innerText || ''")
        check("b. Home: NQ = the PC's price (27,360.50 at 18:10 ET), not the cloud's 29,391.25", "27,360.50" in mk and "29,391" not in t and "18:10" in mk, mk)
        chip = pg.evaluate("() => { const c = document.getElementById('liveChip'), s = document.getElementById('status'); return [c ? c.textContent : '', c ? c.innerText : '', !!(s && s.hidden)]; }")
        check("b. Home: the header says when the PC reported (the ZEUS card's minutes), the cloud monitor's run chip hidden", "PC reported" in chip[0] and "5 min ago" in chip[1] and chip[2], chip)
        sh("home.png")
        ok = go("#/lit", "() => document.body.innerText.includes('$3,807') && document.body.innerText.includes('REAL')")
        t = text()
        check("b. Zlarior tab: REAL $3,807 to the target, $1,025 left; not the twin's PAPER $3,100 / $1,900; no 'first bars of 2026-10-16'; its last trade is Zlarior's",
              ok and "$1,025" in t and "$1,900" not in t and "$3,100" not in t and "2026-10-16" not in t and "Last trade · Zlarior 50K" in t and "Last trade · ATLAS" not in t,
              [x for x in t.split("\n") if "$" in x][:10])
        ok = go("#/atlas", "() => document.body.innerText.includes('LIVE on MFFU account') && document.body.innerText.includes('need $1,463')")
        t = text()
        check("b. ATLAS tab: LIVE on MFFU account …0003, Funded, 'Not yet: need $1,463 more.', first request from 2026-11-20; never 'not bought yet' / 'not set up'",
              ok and "…0003" in t and "Funded" in t and "first request from 2026-11-20" in t and "not bought yet" not in t and "not set up" not in t and "25K eval · not started" not in t,
              [x for x in t.split("\n") if x.strip()][:30])
        sh("atlas.png")
        ok = go("#/eval", "() => document.body.innerText.includes('Your real Zlarior 50K')")
        t = text()
        check("b. 50K eval: the real account from the PC report ($49,193, floor $48,168), not the twin's $49,900", ok and "$49,193" in t and "$48,168" in t and "$49,900" not in t and "PC report" in t)
        ok = go("#/cockpit", "() => document.body.innerText.includes('to pass') && document.body.innerText.includes('PC report')")
        t = text()
        check("b. Eval cockpit: '$3,807 to pass · $1,025 of room' on the real 50K (never the 25K #2's '$28,000 to pass')", ok and "$3,807 to pass" in t and "$1,025 of room" in t and "$28,000" not in t)
        sh("cockpit.png")
        ok = go("#/money", "() => document.querySelector('#zmNow') && document.querySelector('#zmPay') && document.querySelector('#zmPay').innerText.includes('need $')")
        t = text()
        now_ = pg.evaluate("() => (document.querySelector('#zmNow') || {}).innerText || ''")
        pay = pg.evaluate("() => (document.querySelector('#zmPay') || {}).innerText || ''")
        check("b. Money: per account this week = the PC's (-$129 / -$113), this month not invented ('—'); Payouts = ATLAS funded with the coach line",
              ok and "−$129" in now_ and "−$113" in now_ and "Zlarior 25K #2" in now_ and "—" in now_ and "ATLAS" in pay and "need $1,463" in pay and "not yet" not in pay.lower().split("payouts")[0], (now_[:300], pay[:300]))
        check("b. Money: the accounts table has no cloud twin row; no 'not funded yet' while ATLAS is funded", "Paper (cloud)" not in t and "not funded yet" not in t)
        ok = go("#/accounts", "() => document.querySelector('.acc-pick')")
        t = text()
        pick = pg.evaluate("() => [...document.querySelectorAll('.acc-pick [data-acc]')].map((b) => b.dataset.acc)")
        check("b. Accounts: Zlarior 50K first, then the 25K #2, ATLAS, the cloud twin last; no 'git pull' advice, no 'of undefined'",
              ok and pick == ["mffu50k_eval", "b25k_2", "atlas", "cloud_paper"] and "git pull" not in t and "undefined" not in t and "PC reported" in t, (pick, [x for x in t.split("\n") if "ession" in x][:4]))
        ok = go("#/trades", "() => document.body.innerText.includes('Real trades')")
        t = text()
        rt = pg.evaluate("() => { const h = [...document.querySelectorAll('.card h3')].find((x) => x.textContent === 'Real trades'); return h ? h.closest('.card').innerText : ''; }")
        check("b. Trades: a 'Real trades' card from the PC (Zlarior 50K -$129, ATLAS -$113) next to the backtest replay",
              ok and "Zlarior 50K" in rt and "−$129" in rt and "ATLAS" in rt and "−$113" in rt, rt[:300])
        ok = go("#/news", "() => document.body.innerText.includes('Old news build')")
        check("b. News: a build from Oct 17 says it is old and points to Pythia (never 'Trading normally' on an empty calendar)", ok and "Pythia" in text() and "Trading normally" not in text())
        for app, want, bad in (("ares/", "$1,025", "$1,900"), ("demeter/", "$1,025", "$1,900"), ("aegis/", "25K #2", "MFFU 50K Eval")):
            pg.goto(base + app)
            try:
                pg.wait_for_function(f"() => document.body.innerText.includes({json.dumps(want)})", timeout=25000)
                got = True
            except Exception:  # noqa: BLE001
                got = False
            t = text()
            check(f"b. {app}: the PC's numbers ({want}), not the cloud twin's ({bad})", got and bad not in t, [x for x in t.split("\n") if "$" in x][:8])
            if app == "ares/":
                sh("ares.png")
        pg.goto(base + "nq/?flat=1")
        try:
            pg.wait_for_function("() => document.body.innerText.includes('All 3 accounts reported')", timeout=25000)
            got = True
        except Exception:  # noqa: BLE001
            got = False
        t = text()
        src = pg.evaluate("() => (document.getElementById('src') || {}).textContent || ''")
        names = pg.evaluate("() => [...document.querySelectorAll('#bots .bot h3')].map((e) => e.textContent.trim())")
        check("b. NQ page: 'All 3 accounts reported', Zlarior / ATLAS 25K funded / Zlarior 25K #2 with the PC's drawdown, the source = your PC's report; not the cloud's $1,900",
              got and names == ["Zlarior LIT 50K", "ATLAS 25K funded", "Zlarior 25K #2 LIT 25K"] and "$1,025" in t and "$887" in t and "Source: your PC's status report" in src and "$1,900" not in t,
              (names, src, [x for x in t.split("\n") if "$" in x][:6]))
        check("b. no page error with the PC's post", not errs, errs[:3])
        c.close()
        # the same site with NO post (ntfy answers {}): the pages keep working on the cloud's copy (the fixes only act on a post)
        errs2 = []
        c = ctx_for(False)
        pg = c.new_page()
        pg.on("pageerror", lambda e: errs2.append(str(e)))
        ok = go("#/today", "() => document.querySelector('#mnCard') && !document.querySelector('#page.zs-hold')")   # zenith_settle.js: read the text once Home shows (not under its still copy)
        t = text()
        check("b. no post: Home still draws (Money now from the cloud's copy, which says what it is), no page error", ok and "Money now" in t and not errs2, errs2[:3])
        pg.goto(base + "ares/")
        try:
            pg.wait_for_function("() => document.body.innerText.includes('$1,900')", timeout=25000)
            got = True
        except Exception:  # noqa: BLE001
            got = False
        check("b. no post: Ares reads the cloud's home.json as before (home_feed.js leaves it alone)", got and not errs2, errs2[:3])
        c.close()
    srv.shutdown()


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="feedacc_")
    try:
        part_a(tmp)
        if "--node" not in sys.argv:
            part_b(tmp, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
