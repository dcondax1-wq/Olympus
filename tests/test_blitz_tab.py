"""BLITZ tab, the Mind and Trader's deck on both dashboards (2026-10-29 night, owner: "How's the scalp bot coming along?
Make a separate tab at the bottom ... improve dashboard features"; read-only UI).

  a. static   the shared renderers are byte-identical on both apps (blitzcore.js, mindcore.js, deckcore.js), the phone loads
              them after holo.js, caches bumped (phone le-public-v45+, PC le-shell-next-v27+), clean.js?v=3 kept, the PC sidebar
              puts BLITZ right after ATLAS, GET /api/next/blitz exists, web_next/FEATURES.md lists the new features
  b. node     BlitzUI renders every part for BLITZ off / Sim test / armed real from a real paper-shadow state
              (tests.test_blitz.fake_state on data/NQ_1m.csv), MindUI from the Mind fixture, DeckUI's eight features; garbage
              in = no exception; nothing at all without the Mind block
  c. phone    Playwright 390x844 on a copy of tools/web_public (data.json + live.json + liveview.json from the fixtures, the
              browser clock at the fixture's time): six readable tabs with 44 px targets, the BLITZ tab's six sections (OFF,
              SIM TEST, ARMED · REAL), the Mind cards (Home, Zlarior Brain, ATLAS > Brain, BLITZ > Brain, #/mind), Trader's
              deck (#/deck, a mute per bot), Mission Control's Holodeck links (#/holo/<day>), no page errors, no sideways scroll
  d. PC       Playwright 1440x900 on server.py (board / liveview patched, /api/next/blitz and /api/next/mind answered from the
              fixtures): BLITZ in the sidebar after ATLAS, its six sections, the Mind page, Trader's deck, Home's deck cards

  python -X utf8 -m tests.test_blitz_tab [--shots <dir>]     # ~60-90 s; --shots saves the phone / PC screenshots
"""
from __future__ import annotations

import copy
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def shift(o, dt, keys=("t", "entry_t", "exit_t", "close_t", "time_exit_t", "first_run_t")):
    """Every time key of a nested block moved by dt seconds (the Mind fixture to the page's clock)."""
    if isinstance(o, dict):
        return {k: (v + dt if k in keys and isinstance(v, (int, float)) and v > 1e9 else shift(v, dt, keys)) for k, v in o.items()}
    if isinstance(o, list):
        return [shift(x, dt, keys) for x in o]
    return o


# ------------------------------------------------------------------------------------------------ fixtures
def mind_fixture(T):
    """The Mind block (the Mind agent's samples): the full one (GET /api/next/mind) and the compact phone / heartbeat cut,
    both moved to the page's clock. LE_MIND_FIXTURE=<path> renders another sample instead of the full one."""
    def load(p):
        m = json.load(open(p, encoding="utf-8"))
        m = m.get("mind", m) if isinstance(m, dict) else m
        return shift(m, T - int(m.get("t") or T))
    fx = os.path.join(ROOT, "tests", "fixtures")
    p = os.environ.get("LE_MIND_FIXTURE") or os.path.join(fx, "mind_sample.json")
    pc = os.path.join(fx, "mind_sample_compact.json")
    full = load(p)
    return full, (load(pc) if os.path.exists(pc) and not os.environ.get("LE_MIND_FIXTURE") else full), os.path.basename(p)


def acct_c(kind, T, armed=False, pos=None):
    """account C's heartbeat block (engine/account_c.AccountC.hb_block shape) on Sim101 or a real 25K."""
    real = {"SIM": "SIM", "LIVE": "REAL"}.get(kind, "PAPER")
    closed = [{"day": "2026-09-14", "entry_t": T - 86400 - 3000, "exit_t": T - 86400 - 1200, "dir": 1, "side": "LONG", "qty": 3, "entry": 24310.25,
               "stop": 24250.0, "exit": 24352.5, "exit_kind": "TIME", "pnl": 247.8, "usd": 247.8, "r": 0.69, "strategy": "BLITZ", "src": "blitz"},
              {"day": "2026-09-11", "entry_t": T - 4 * 86400, "exit_t": T - 4 * 86400 + 1500, "dir": -1, "side": "SHORT", "qty": 3, "entry": 24120.0,
               "stop": 24181.0, "exit": 24181.25, "exit_kind": "STOP", "pnl": -373.2, "usd": -373.2, "r": -1.0, "strategy": "BLITZ", "src": "blitz"}]
    return {"label": "BLITZ " + ("Sim101" if kind == "SIM" else "MFFUEVBLITZ25K"), "account": "Sim101" if kind == "SIM" else "MFFUEVBLITZ25K",
            "plan": "builder25k", "plan_label": "MFFU Builder 25K", "kind": kind, "real": real, "strategy": "BLITZ", "enabled": True, "disabled": None,
            "armed": armed, "eval": {"start_balance": 25000.0, "balance": 25124.6, "profit": 124.6, "today": 0.0, "floor": 24100.0, "room": 1024.6,
                                     "target": 26500.0, "to_target": 1375.4, "session": 3, "status": "open", "start": "2026-09-10"},
            "open": pos, "routed": [], "trades_today": [], "day_pnl": 0.0, "entries_today": 1 if pos else 0, "locked": None, "size": None, "paused": None,
            "scorecard": {"n": 7, "wins": 4, "win_pct": 57.1, "avg_r": 0.112, "pf_r": 1.41, "pf_usd": 1.38, "usd": 312.4, "lose_days": 1,
                          "lose_days_cap": 6, "min_trades": 20, "floor": None, "status": "warming", "why": [],
                          "resume_cmd": "python -X utf8 -m engine.account_c --resume"},
            "state": {"stage": "trade" if pos else "watching", "text": f"{real} {pos['side']} 3 MNQ from {pos['entry']:,.2f}, stop {pos['stop']:,.2f}." if pos else "Next check 11:30 ET."},
            "params": None, "filtered": True, "signals": [], "note": "own account", "days": {"2026-09-11": -373.2, "2026-09-14": 247.8},
            "closed": closed, "rules": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20}, "t": T}


def build(shots=""):
    """The paper shadow (a real day of data), its Live View layer, the board, the Mind, three account C cases."""
    from engine import blitz as BZ, liveview_api as LV, narrator as N
    from tests import test_blitz as TBZ
    S, S_open = TBZ.fake_state()
    S_ = S_open or S
    T = int(S_["t"])
    bot = SimpleNamespace(running=True, kill=False, cfg={"adapter": "paper"}, state={"price": None}, brain=None, second=None, acct_b=None,
                          ledger=[], log=[], health={}, bars_tail=[], _lit_1m_store=None, _open_routed=None, _open_qty=None, _open_src=None,
                          adapter=None, clock=lambda: T, blitz=S_)
    bot._push_account = lambda: "Paper"
    LV.CSV_FALLBACK = False
    lv = LV.phone_view(bot, T, narr=N.Narrator())
    lv = json.loads(json.dumps(lv, default=str))
    card = json.loads(json.dumps(BZ.card(S_), default=str))
    mind, mind_c, mind_src = mind_fixture(T)
    lv["mind"] = mind_c                      # the phone gets the compact cut (liveview.json / live.json), the PC the full block
    from tests import test_space_ui as SU
    b2, b3 = SU.boards(T)
    b3 = json.loads(json.dumps(b3, default=str))
    b2 = json.loads(json.dumps(b2, default=str))
    op = card.get("open") or {}
    pos = {"entry_t": op.get("entry_t") or T - 600, "dir": op.get("dir") or 1, "side": op.get("side") or "LONG", "qty": 3, "entry": op.get("entry") or 24402.25,
           "stop": op.get("stop_now") or op.get("stop") or 24341.0, "target": None, "strategy": "BLITZ", "key": "blitz",
           "time_exit_t": op.get("time_exit_t") or T + 1200}
    cases = {"off": None, "sim": acct_c("SIM", T), "armed": acct_c("LIVE", T, armed=True, pos=pos)}
    return {"T": T, "S": S_, "lv": lv, "card": card, "mind": mind, "mind_c": mind_c, "mind_src": mind_src, "board": b3, "board2": b2, "cases": cases}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    for n in ("blitzcore.js", "mindcore.js", "deckcore.js"):
        check(f"a. {n} byte-identical on both apps", rd("tools", "web_public", n) == rd("web_next", "js", "next", n))
    pidx, psw, sw, cl = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js"), rd("tools", "web_public", "clean.js")
    order = [pidx.find(f'src="{n}?v=') for n in ("holo.js", "blitzcore.js", "mindcore.js", "deckcore.js", "blitz.js")]
    check("a. phone index loads blitzcore / mindcore / deckcore / blitz.js after holo.js, in that order", all(i > 0 for i in order) and order == sorted(order), order)
    check("a. caches: phone le-public-v45+, PC le-shell-next-v27+; clean.js?v=3 kept", int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 45
          and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 27 and 'clean.js?v=3"' in pidx)
    check("a. clean.js: six tabs, BLITZ sections Today · Brain · Trades · Results · Rules · Go live", "['today', 'lit', 'atlas', 'blitz', 'money', 'system']" in cl
          and "['Go live', ['blitz/golive'], []]" in cl and "blitz: ['BLITZ', 'blitz']" in cl)
    rt, app, srv = rd("web_next", "js", "next", "routes.js"), rd("web_next", "js", "app.js"), rd("server.py")
    check("a. PC: BLITZ after ATLAS in Main, its six sections, Mind + Trader's deck pages, app.js registers them", "g.ids.indexOf('atlas'); g.ids.splice(i >= 0 ? i + 1" in rt
          and "['Go live', ['blitz:golive']]" in rt and "PAGES.blitz = blitzPage" in app and "PAGES.mind = mindPage" in app and "initBlitzSync()" in app
          and all(f'id="page-{p}"' in rd("web_next", "index.html") for p in ("blitz", "mind", "deck")))
    check("a. server.py: GET /api/next/blitz (blitz.card + account C's block, never 500)", '@app.get("/api/next/blitz")' in srv and "BZ.card(getattr(BOT, \"blitz\", None))" in srv)
    for n in ("blitzcore.js", "mindcore.js", "deckcore.js", "blitz.js"):
        src = rd("tools", "web_public", n)
        check(f"a. {n} is read-only (no POST, no arm / route / order call)", "POST" not in src and "method:" not in src and "/api/live/" not in src and "arm_c" not in src)
    fm = rd("web_next", "FEATURES.md")
    check("a. FEATURES.md lists BLITZ tab, Mind and the deck features (71-80)", "BLITZ tab" in fm and "| 72 | Mind" in fm and "Risk meter" in fm and "| 80 |" in fm)


# ------------------------------------------------------------------------------------------------ b. node render
NODE_JS = r"""
global.window = {}; global.document = undefined;
const dir = process.argv[2], fs = require('fs');
for (const n of ['blitzcore.js', 'mindcore.js', 'deckcore.js']) require(dir + '/' + n);
global.document = { getElementById: () => ({}), querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}) };
require(dir + '/boardcore.js');
const F = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const B = window.BlitzUI, M = window.MindUI, K = window.DeckUI, out = { parts: {}, bad: 0 };
const go = (id, arg) => `data-go="${id}"${arg ? ` data-arg="${arg}"` : ''}`;
for (const c of ['off', 'sim', 'armed']) {
  const m = B.model({ now: F.T, where: 'phone', lv: F.lv, card: F.card, ac: F.cases[c], board: F.board.blitz });
  out.parts[c] = {}; for (const [p] of B.PARTS) out.parts[c][p] = B.page(m, p, { go, mind: p === 'brain' ? M.bot(F.mind, 'blitz', { go }) : '' });
  out[c + '_acct'] = B.acctC(m); out[c + '_line'] = B.line(m);
  if (c === 'off') { out.model = { stage: m.stage, band: m.band && m.band.rows.length, sig: m.signals.length, pos25: !!m.pos25, pos50: !!m.pos50, today: m.today25.length, hist: m.hist25.length, f50: m.today50.length, text: m.text }; }
}
out.mindc = { has: M.has(F.mind_c), page: M.page(F.mind_c, { go }), home: M.home(F.mind_c, { go }), lit: M.bot(F.mind_c, 'lit', { go }) };
out.mind = { has: M.has(F.mind), lit: M.bot(F.mind, 'lit', { go }), atlas: M.bot(F.mind, 'atlas', { go }), blitz: M.bot(F.mind, 'blitz', { go }), home: M.home(F.mind, { go }), page: M.page(F.mind, { go }),
  none: [M.bot(null, 'lit'), M.home(undefined), M.bot({}, 'atlas'), M.bot({ error: 'x' }, 'blitz')], review: (() => { const r = (F.mind.reviews || [])[0]; if (!r) return true; const tr = r.trade && typeof r.trade === 'object' ? r.trade : {};
    const day = tr.day || String(r.trade || '').slice(0, 10); return !!M.reviewFor(F.mind, { day, acct: r.bot, entry_t: r.entry_t || tr.entry_t }); })() };
const DM = { now: F.T, board: F.board, lv: F.lv, mind: F.mind, news: [{ t: F.T + 3600, title: 'CPI', impact: 'high' }], cal: { early_close: [] }, acc: F.cases.armed };
out.deck = { page: K.page(DM, { go }), home: K.home(DM, { go }), replays: K.replays(DM, { go }), ev: K.events24(DM).map((e) => e.label), risk: K.accounts(DM).map((a) => [a.k, Math.round(a.risk)]),
  inbox: K.inboxItems(DM).length, dst: K.dstNext(Date.parse('2026-10-29T12:00:00Z') / 1000) };
for (const g of [null, {}, { lv: 5, card: 'x', ac: [], board: 7 }, { lv: { strategies: { scalp: { band: 'no', signals: {}, position: 3 } } }, card: { band: { checks: 4 }, signals: 'x', today: {}, eval: 9 }, ac: { account: 'x', eval: 'y', closed: 3, scorecard: [] } }]) {
  try { const m = B.model(g || {}); for (const [p] of B.PARTS) B.page(m, p, {}); M.page(g); M.home(g); M.bot(g, 'lit'); K.page(g || {}, {}); K.home(g || {}, {}); } catch (e) { out.bad++; out.err = String(e.stack).slice(0, 400); }
}
{ const U = window.BoardUI, p3 = U.page(F.board, {}), p2 = U.page(F.board2, {}), h3 = U.home(F.board, {});
  out.board = { acct3: (p3.match(/bd-card bd-acct/g) || []).length, acct2: (p2.match(/bd-card bd-acct/g) || []).length, mini3: (h3.match(/class="bd-mini /g) || []).length,
    three: /all three accounts/.test(p3), seg3: /BLITZ<\/button>/.test(p3), seg2: /BLITZ<\/button>/.test(p2) }; }
process.stdout.write(JSON.stringify(out) + '\n', () => process.exit(0));    // boardcore keeps a timer: exit once the line is out
"""


def part_b(F, tmp):
    node = shutil.which("node")
    if not node:
        print("[SKIP] b. node render: node not installed")
        return None
    fp = os.path.join(tmp, "f.json")
    json.dump(F, open(fp, "w"), default=str)
    jp = os.path.join(tmp, "r.js")
    open(jp, "w").write(NODE_JS)
    r = subprocess.run([node, jp, os.path.join(ROOT, "tools", "web_public"), fp], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. node render ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-600:])
        return None
    md = o["model"]
    check("b. the model reads the real paper shadow: band of every check, signals, today's paper trades of both ledgers, the state text",
          md["band"] == 10 and md["sig"] >= 1 and md["today"] >= 1 and md["f50"] >= 1 and md["text"], md)
    P = o["parts"]
    t = P["off"]["today"]
    check("b. Today: next check, the noise band (SVG), the day filter verdict, signals, the open PAPER position with $ at the stop, account C OFF",
          "Next check" in t and "How it is going:" in t and "bl-band" in t and ("TRADING TODAY" in t or "SKIPPED TODAY" in t) and "Signals today" in t
          and "PAPER" in t and "at the stop" in t and "OFF · paper shadow" in t, re.sub("<[^>]+>", " ", t)[:600])
    check("b. Today with account C on Sim101: SIM TEST chip, its eval tiles and scorecard", "SIM TEST" in P["sim"]["today"] and "Sim101" in P["sim"]["today"]
          and "Losing days" in P["sim"]["today"], o["sim_acct"])
    check("b. Today armed on the real 25K: ARMED · REAL, a REAL position card with $ at the stop", "ARMED · REAL" in P["armed"]["today"]
          and re.search(r"REAL (LONG|SHORT)", P["armed"]["today"]) and o["armed_acct"]["mode"] == "armed", o["armed_acct"])
    b = P["off"]["brain"]
    check("b. Brain: what it is thinking, the playbook rule now, B1-B8 ladder, the Mind's BLITZ cards", "What BLITZ is thinking" in b and "playbook rule now" in b
          and all(f">B{i}<" in b for i in range(1, 9)) and 'data-mind="blitz"' in b and "game plan" in b)
    tr = P["armed"]["trades"]
    check("b. Trades: account C (REAL), the paper 25K eval and the 50K + LIT ledgers, Holodeck links", "Account C" in tr and "Paper 25K eval" in tr
          and "Paper 50K + LIT" in tr and 'data-go="holo" data-arg="2026-' in tr and "REAL" in tr)
    rs = P["sim"]["results"]
    check("b. Results: research bands (H1 / H2 / 2021-25), live vs the band, kill switch floors, paper evals", "Research bands" in rs and "2026 H2 (check)" in rs
          and "Live vs the research band" in rs and "Kill switch" in rs and "-0.150R" in rs and "WARMING UP" in rs)
    check("b. Rules: B1-B8 in plain words, size, money first", "B1 · Only on lively days" in P["off"]["rules"] and "Size and the 25K rules" in P["off"]["rules"]
          and "Money first" in P["off"]["rules"])
    g = P["off"]["golive"]
    check("b. Go live: the 3 steps, the console line, preflight from the data", "Buy the MFFU Builder 25K" in g and "Start trading" in g and "engine.account_c" in g
          and "Preflight" in g and "of 6 ready" in g)
    mn = o["mind"]
    check("b. Mind: a card set per bot (plan, similar setups, reviews, ideas, alerts), Home card, the page with regime + IQ",
          mn["has"] and all(("game plan" in mn[k] or not (F["mind"].get("plans") or {}).get(k)) and ("similar past setups" in mn[k] or not (F["mind"].get("similar") or {}).get(k))
                            for k in ("lit", "atlas", "blitz")) and "Mind · today" in mn["home"]
          and "Market regime" in mn["page"] and "Mind IQ" in mn["page"] and "trade reviews" in mn["page"] and "self-research ideas" in mn["page"])
    mc = o["mindc"]
    check("b. Mind: the compact phone cut renders too (game plans, Home card, Zlarior's cards)", mc["has"] and "game plan" in mc["page"]
          and "Mind · today" in mc["home"] and 'data-mind="lit"' in mc["lit"])
    check("b. Mind: nothing at all without the block", mn["none"] == ["", "", "", ""], mn["none"])
    check("b. Mind: the review of a trade is found for the journal", mn["review"])
    d = o["deck"]
    check("b. deck: the eight features on the page", all(x in d["page"] for x in ("Since you last looked", "Risk meter", "Next 24 hours", "Eval odds from today",
          "Real P&L calendar", "Trade journal", "Notification center", "Replay a day in the Holodeck")))
    check("b. deck: next 24 h has each bot's windows / checks + the news; DST = Sun Nov 1 2026 (clocks back)", any("Zlarior entries" in x for x in d["ev"])
          and any("BLITZ checks" in x for x in d["ev"]) and any(x == "CPI" for x in d["ev"]) and d["dst"]["day"] == "2026-11-01" and d["dst"]["way"] == "back", d["ev"][:8])
    check("b. deck: risk meter reads the open trades (Zlarior's $450, BLITZ armed)", ["lit", 450] in d["risk"], d["risk"])
    check("b. garbage in: no exception from any renderer", o["bad"] == 0, o.get("err"))
    bd = o.get("board") or {}
    check("b. live board (boardcore.js): a third card for BLITZ when account C is on (Right now, the Home cut, the trade filter); two without",
          bd.get("acct3") == 3 and bd.get("acct2") == 2 and bd.get("mini3") == 3 and bd.get("three") and bd.get("seg3") and not bd.get("seg2"), bd)
    return o


# ------------------------------------------------------------------------------------------------ c. phone (Playwright)
def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        import glob
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for exe in sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux", "chrome")), reverse=True):
            return p.chromium.launch(executable_path=exe)
        raise


def serve(d):
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=d, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def site(tmp, F):
    s = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), s, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options"))
    T = F["T"]
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T - 600)),
            "live": {"last_run": T - 600, "runs": 1, "pc": {"present": True, "t": T - 60, "age_s": 60, "running": True, "every_s": 60, "host": "SURFACE"}},
            "accounts": [], "results": {"periods": {}}, "trades": [], "strategy": {}, "board": F["board"], "blitz": F["card"],
            "news": {"events": [{"t": T + 5400, "title": "Initial Jobless Claims", "impact": "high"}]},
            "goals": {"calendar": {"news": [], "early_close": [{"day": "2026-11-27", "halt": "13:15"}]}}}
    for n in ("data.json", "home.json"):
        json.dump(data, open(os.path.join(s, n), "w"), default=str)
    return s


def live_json(F, case):
    T = F["T"]
    return {"v": 1, "kind": "le-live", "t": T - 20, "every_s": 60, "host": "SURFACE",
            "pc": {"running": True, "adapter": "ninjatrader", "present": True, "t": T - 20, "age_s": 0, "live": True, **({"account_c": F["cases"][case]} if F["cases"][case] else {})},
            "pc_verdict": {"code": "LIVE", "label": "TRADING YOUR EVAL", "level": "good", "reason": "ok", "checks": [], "t": T}, "accounts": [], "board": F["board"],
            "mind": F["mind_c"]}


def phone_ctx(br, F, lvp, case, errs, seen=None):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    ctx.clock.install(time=F["T"])     # Python Playwright: a number is seconds
    if seen is not None:
        ctx.add_init_script(f"try {{ localStorage.setItem('le.deck.seen', JSON.stringify({{ t: {seen} }})); }} catch (e) {{}}")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{case} pageerror: {str(e)[:240]}"))
    lj = json.dumps(live_json(F, case), default=str)
    pg.route("**/api.github.com/**", lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url
             else r.fulfill(status=200, body=lj, content_type="application/json") if "/live.json" in r.request.url else r.fulfill(status=404, body="{}"))
    pg.route("**/raw.githubusercontent.com/**", lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url
             else r.fulfill(status=200, body=lj, content_type="application/json") if "/live.json" in r.request.url else r.fulfill(status=404, body="{}"))
    return ctx, pg


def no_x(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")


def part_c(F, tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    s = site(tmp, F)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(F["lv"], open(lvp, "w"), default=str)
    srv = serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    sh = (lambda pg, n, full=False: pg.screenshot(path=os.path.join(shots, n), full_page=full)) if shots else (lambda *a, **k: None)
    with sync_playwright() as p:
        br = launch(p)
        errs = []
        ctx, pg = phone_ctx(br, F, lvp, "off", errs, seen=F["T"] - 4 * 3600)
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".cl-hero", timeout=30000)
        pg.wait_for_function("() => window.LIVE && window.LIVE.j", timeout=30000)
        pg.wait_for_timeout(1200)
        pg.evaluate("() => { if (typeof render === 'function') render(true); }")
        pg.wait_for_timeout(500)
        if pg.query_selector("#moInstX"):
            pg.click("#moInstX")
            pg.wait_for_timeout(500)
        tabs = pg.eval_on_selector_all("#tabs a", "els => els.map(e => { const r = e.getBoundingClientRect(), s = e.querySelector('span'); return [s.textContent.trim(), Math.round(r.width), Math.round(r.height), s.scrollWidth <= s.clientWidth + 1]; })")
        check("c. phone bottom bar = Home · Zlarior · ATLAS · BLITZ · Money · More", [t[0] for t in tabs] == ["Home", "Zlarior", "ATLAS", "BLITZ", "Money", "More"], tabs)
        check("c. six tabs fit 390 px: each >= 44 x 44 px, every label readable (not clipped)", all(t[1] >= 44 and t[2] >= 44 and t[3] for t in tabs), tabs)
        check("c. Home: the hero cards stay first (Zlarior, ATLAS, then the plan line)", pg.evaluate(
            "() => { const L = [...document.querySelector('#page').querySelectorAll('.card:not(#moInst):not(.cl-launch)')]; "
            "return L.length > 3 && L[0].classList.contains('cl-hero') && L[1].classList.contains('cl-hero') && L[2].classList.contains('cl-plan'); }"))
        ht = pg.inner_text("#page")
        check("c. Home: since you last looked (4 h ago), risk meter, next 24 h, the Mind card", "SINCE YOU LAST LOOKED" in ht.upper() and "RISK METER" in ht.upper()
              and "NEXT 24 HOURS" in ht.upper() and "MIND · TODAY" in ht.upper(), ht[:400])
        check("c. Home: no sideways scroll", no_x(pg) <= 1, no_x(pg))
        if shots:
            el = pg.query_selector(".bz-home")
            if el:
                el.scroll_into_view_if_needed()
                pg.wait_for_timeout(300)
            sh(pg, "phone_home_deck.png")
        pg.click("#tabs a[data-t='blitz']")
        pg.wait_for_selector(".bl-wrap .bl-hero", timeout=10000)
        pg.wait_for_timeout(600)
        seg = pg.eval_on_selector_all("#sub .zl-seg button", "els => els.map(e => e.textContent.trim())")
        check("c. BLITZ tab sections: Today · Brain · Trades · Results · Rules · Go live", seg == ["Today", "Brain", "Trades", "Results", "Rules", "Go live"], seg)
        t = pg.inner_text("#page")
        tu = t.upper()          # innerText follows the CSS uppercase labels
        check("c. BLITZ > Today: next check, noise band, day filter verdict, signals, open PAPER position, account C OFF",
              "NEXT CHECK" in tu and pg.query_selector(".bl-band") and ("TRADING TODAY" in tu or "SKIPPED TODAY" in tu) and "SIGNALS TODAY" in tu
              and "PAPER" in tu and "OFF · PAPER SHADOW" in tu, t[:500])
        check("c. BLITZ > Today: no sideways scroll", no_x(pg) <= 1, no_x(pg))
        sh(pg, "phone_blitz_today.png")
        sh(pg, "phone_blitz_today_full.png", True)
        for part, want in (("brain", ["What BLITZ is thinking", "playbook rule now", "game plan"]), ("trades", ["Paper 25K eval", "3D"]),
                           ("results", ["Research bands", "Kill switch", "Live vs the research band"]), ("rules", ["B1 · Only on lively days", "Size and the 25K rules"]),
                           ("golive", ["Turn it on", "Preflight"])):
            pg.goto(base + f"?fxoff#/blitz/{part}")
            pg.wait_for_selector(f".bl-wrap[data-bl-part='{part}']", timeout=10000)
            pg.wait_for_timeout(400)
            tt = pg.inner_text("#page")
            on = pg.eval_on_selector("#sub .zl-seg button.on", "e => e.textContent.trim()")
            check(f"c. #/blitz/{part}: {', '.join(want)}; its section is lit; BLITZ tab on; no sideways scroll",
                  all(w in tt for w in want) and on == dict(BU_PARTS)[part] and pg.eval_on_selector("#tabs a.on", "e => e.dataset.t") == "blitz" and no_x(pg) <= 1,
                  (on, tt[:300], no_x(pg)))
            sh(pg, f"phone_blitz_{part}.png", part in ("results", "trades"))
        # the Mind on each bot
        pg.goto(base + "?fxoff#/brain")
        pg.wait_for_timeout(1200)
        check("c. Zlarior Bot Brain: the Mind's Zlarior cards on top", pg.query_selector("#page [data-mind='lit']") is not None)
        sh(pg, "phone_mind_lit_brain.png")
        pg.goto(base + "?fxoff#/atlas/brain")
        pg.wait_for_timeout(1200)
        check("c. ATLAS > Brain: the Mind's ATLAS cards", pg.evaluate("() => { const e = document.querySelector('#page [data-mind=\"atlas\"]'); return !!(e && e.offsetParent); }"))
        pg.goto(base + "?fxoff#/mind")
        pg.wait_for_selector(".mn-page", timeout=10000)
        mt = pg.inner_text("#page").upper()
        check("c. #/mind: regime, a game plan + similar setups per bot, reviews, ideas, alerts, IQ; no sideways scroll", "MARKET REGIME" in mt and mt.count("GAME PLAN") >= 3
              and "TRADE REVIEWS" in mt and "SELF-RESEARCH IDEAS" in mt and "MIND IQ" in mt and no_x(pg) <= 1, mt[:300])
        sh(pg, "phone_mind.png")
        sh(pg, "phone_mind_full.png", True)
        # Trader's deck: a mute per bot
        pg.goto(base + "?fxoff#/deck")
        pg.wait_for_selector(".dk-wrap #dk-inbox", timeout=10000)
        n0 = pg.eval_on_selector_all("#dk-inbox .dk-in li .dk-bot", "els => els.filter(e => /BLITZ/.test(e.textContent)).length")
        pg.click("#dk-inbox [data-dk-mute='blitz']")
        pg.wait_for_timeout(300)
        n1 = pg.eval_on_selector_all("#dk-inbox .dk-in li .dk-bot", "els => els.filter(e => /BLITZ/.test(e.textContent)).length")
        check("c. #/deck: eight features; muting BLITZ hides its lines (this device only)", pg.eval_on_selector_all(".dk-wrap > .dk-card", "e => e.length") == 8
              and n0 >= 1 and n1 == 0 and no_x(pg) <= 1, (n0, n1))
        pg.click("#dk-inbox [data-dk-mute='blitz']")
        sh(pg, "phone_deck.png")
        sh(pg, "phone_deck_full.png", True)
        # Mission Control -> a Holodeck replay link
        pg.goto(base + "?fxoff#/mission")
        pg.wait_for_selector("#dk-replays a", timeout=15000)
        day = pg.eval_on_selector("#dk-replays a", "e => e.dataset.arg")
        pg.click("#dk-replays a")
        pg.wait_for_timeout(800)
        check("c. Mission Control: 'Replay a day in the Holodeck' opens #/holo/<day>", re.match(r"#/holo/\d{4}-\d\d-\d\d$", pg.evaluate("() => location.hash") or "") is not None
              and day in pg.evaluate("() => location.hash"), (day, pg.evaluate("() => location.hash")))
        check("c. phone (account C off): no page errors", not errs, errs[:4])
        ctx.close()
        for case, want in (("sim", "SIM TEST"), ("armed", "ARMED · REAL")):
            e2 = []
            ctx, pg = phone_ctx(br, F, lvp, case, e2)
            pg.goto(base + "?fxoff#/blitz")
            pg.wait_for_selector(".bl-wrap .bl-hero", timeout=30000)
            pg.wait_for_function("() => window.LIVE && window.LIVE.j && window.LIVE.j.pc && window.LIVE.j.pc.account_c", timeout=20000)
            pg.evaluate("() => { if (typeof render === 'function') render(true); }")
            pg.wait_for_timeout(700)
            t = pg.inner_text("#page")
            extra = (re.search(r"REAL (LONG|SHORT)", t) is not None and "at the stop" in t) if case == "armed" else ("Sim101" in t)
            check(f"c. BLITZ > Today with account C {case}: {want}{' + the REAL position with $ at the stop' if case == 'armed' else ' on Sim101'}; no errors",
                  want in t.upper() and extra and not e2 and no_x(pg) <= 1, (t[:400], e2[:3]))
            sh(pg, f"phone_blitz_today_{case}.png")
            ctx.close()
        # sideways (844 x 390) and the light theme: still no sideways scroll, the cards stay readable
        e3 = []
        ctx = br.new_context(viewport={"width": 844, "height": 390}, device_scale_factor=2, is_mobile=True, has_touch=True)
        ctx.clock.install(time=F["T"])
        ctx.add_init_script("try { localStorage.setItem('le.theme', JSON.stringify('light')); } catch (e) {}")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: e3.append(str(e)[:200]))
        lj = json.dumps(live_json(F, "armed"), default=str)
        pg.route("**/api.github.com/**", lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url
                 else r.fulfill(status=200, body=lj, content_type="application/json") if "/live.json" in r.request.url else r.fulfill(status=404, body="{}"))
        pg.route("**/raw.githubusercontent.com/**", lambda r: r.fulfill(status=404, body="{}"))
        ok_all = True
        for h in ("#/blitz", "#/blitz/results", "#/blitz/trades", "#/deck", "#/mind"):
            pg.goto(base + "?fxoff" + h)
            pg.wait_for_selector(".bl-wrap, .dk-wrap, .mn-wrap", timeout=20000)
            pg.wait_for_timeout(500)
            ok_all = ok_all and no_x(pg) <= 1
        light = pg.evaluate("() => document.documentElement.dataset.theme")
        ink = pg.evaluate("() => getComputedStyle(document.querySelector('.mn-card h3, .dk-card h3, .bl-card h3')).color")
        check("c. sideways 844x390 + light theme: BLITZ, Results, Trades, the deck and the Mind with no sideways scroll, dark ink on light glass, no errors",
              ok_all and light == "light" and ink.startswith("rgb(") and sum(int(x) for x in re.findall(r"\d+", ink)[:3]) < 200 and not e3, (ok_all, light, ink, e3[:2]))
        sh(pg, "phone_mind_landscape_light.png")
        pg.goto(base + "?fxoff#/blitz")
        pg.wait_for_selector(".bl-wrap .bl-hero", timeout=20000)
        pg.wait_for_timeout(500)
        sh(pg, "phone_blitz_landscape_light.png")
        ctx.close()
        br.close()
    srv.shutdown()


BU_PARTS = [("today", "Today"), ("brain", "Brain"), ("trades", "Trades"), ("results", "Results"), ("rules", "Rules"), ("golive", "Go live")]


# ------------------------------------------------------------------------------------------------ d. PC (Playwright on server.py)
def pc_go(pg, page, tries=10):
    """LE.go(page) until it sticks (the PC app opens Start by itself once its first health ping says the bot is stopped)."""
    for _ in range(tries):
        pg.evaluate(f"() => window.LE.go('{page}')")
        pg.wait_for_timeout(1200)
        if pg.evaluate(f"() => !!document.querySelector('#page-{page}.active')"):
            return True
    return False


def part_d(F, shots):
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn  # noqa: F401
    except Exception:
        print("[SKIP] d. PC Playwright: playwright / uvicorn not installed")
        return
    from tests.shots_board import free_port, snapshot_files, restore_files
    import atexit
    snap = snapshot_files()
    atexit.register(restore_files, snap)
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    import uvicorn
    import server
    from engine import board_api, liveview_api
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    board_api.board_view = lambda bot, now=None: copy.deepcopy(F["board"])
    lv = copy.deepcopy(F["lv"])
    liveview_api.view = lambda bot, tf="1m", now=None, narr=None, n_feed=100: copy.deepcopy(lv)
    try:                                     # the real route (before the fixture answers it): the card + the Start page slot, no phrase
        rr = server.blitz_view()
        body = json.loads(rr.body)
        check("d. GET /api/next/blitz (server.py): 200, blitz.card + the BLITZ slot, never the live phrase", rr.status_code == 200 and body.get("card", {}).get("paper")
              and "slot" in body and "I ACCEPT" not in rr.body.decode(), str(rr.body)[:300])
    except Exception as e:
        check("d. GET /api/next/blitz (server.py) answers", False, e)
    blz = {"card": F["card"], "account_c": F["cases"]["armed"], "t": F["T"]}
    server.app.router.routes.insert(0, Route("/api/next/blitz", lambda req: JSONResponse(json.loads(json.dumps(blz, default=str)))))
    server.app.router.routes.insert(0, Route("/api/next/mind", lambda req: JSONResponse(F["mind"])))
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(300):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    base = f"http://127.0.0.1:{port}"
    with sync_playwright() as p:
        br = launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        ctx.clock.install(time=F["T"])     # Python Playwright: a number is seconds
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
        pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('le.deck.seen', JSON.stringify({ t: %d }));" % (F["T"] - 7200))
        pg.goto(base + "/?fxoff", wait_until="domcontentloaded")
        pg.wait_for_function("() => window.LE && window.LE.go", timeout=60000)
        pg.wait_for_timeout(2500)
        side = pg.eval_on_selector_all("#nav > a.nx-gl[data-g='Main']", "els => els.map(e => e.dataset.page)")
        check("d. PC sidebar Main: BLITZ right after ATLAS; Mind + Trader's deck after Real results", "blitz" in side and side.index("blitz") == side.index("atlas") + 1
              and side.index("mind") == side.index("real") + 1 and side.index("deck") == side.index("mind") + 1, side)
        home_ok = False
        for _ in range(3):                   # the PC app opens Start by itself while the bot is stopped; cc loads its data first
            pc_go(pg, "cc")
            try:
                pg.wait_for_selector("#page-cc.active #nxDeckHome .dk-card", timeout=30000)
                home_ok = True
                break
            except Exception:
                pass
        ct = pg.inner_text("#page-cc").upper()
        check("d. PC Home: since you last looked, risk meter, next 24 h + the Mind card under the Safety card", home_ok
              and "RISK METER" in ct and "MIND · TODAY" in ct and "SINCE YOU LAST LOOKED" in ct and "NEXT 24 HOURS" in ct, (home_ok, ct[:300]))
        if shots and home_ok:
            pg.query_selector("#nxDeckHome").screenshot(path=os.path.join(shots, "pc_home_deck_1440.png"))
        pc_go(pg, "blitz")
        pg.click("#nav a[data-page='blitz']")
        pg.wait_for_selector("#page-blitz .bl-hero", timeout=30000)
        pg.wait_for_timeout(1200)
        seg = pg.eval_on_selector_all("#nxSub .nx-botseg button", "els => els.map(e => e.textContent.trim())")
        check("d. PC BLITZ: section bar Today · Brain · Trades · Results · Rules · Go live", seg == [x[1] for x in BU_PARTS], seg)
        t = pg.inner_text("#page-blitz")
        check("d. PC BLITZ > Today: the band, the day filter, ARMED · REAL (account C from /api/next/blitz), the REAL position", "ARMED · REAL" in t.upper()
              and re.search(r"REAL (LONG|SHORT)", t) and pg.query_selector("#page-blitz .bl-band") is not None, t[:400])
        if shots:
            pg.screenshot(path=os.path.join(shots, "pc_blitz_today_1440.png"))
        for i, (part, label) in enumerate(BU_PARTS[1:], 1):
            pg.click(f"#nxSub .nx-botseg button:nth-child({i + 1})")
            pg.wait_for_selector(f"#page-blitz .bl-wrap[data-bl-part='{part}']", timeout=15000)
            pg.wait_for_timeout(500)
            on = pg.eval_on_selector("#nxSub .nx-botseg button.on", "e => e.textContent.trim()")
            check(f"d. PC BLITZ > {label}: drawn, its section lit", on == label, on)
            if shots:
                pg.screenshot(path=os.path.join(shots, f"pc_blitz_{part}_1440.png"), full_page=part in ("results",))
        pc_go(pg, "brain")
        try:
            pg.wait_for_selector("#page-brain #nxMindLit [data-mind='lit']", timeout=30000)
            br_ok = True
        except Exception:
            br_ok = False
        check("d. PC Bot Brain: the Mind's Zlarior cards on top (kept through the page's redraws)", br_ok)
        pc_go(pg, "mind")
        pg.wait_for_selector("#page-mind .mn-page", timeout=20000)
        mt = pg.inner_text("#page-mind").upper()
        check("d. PC Mind page: regime, three game plans, reviews, ideas", "MARKET REGIME" in mt and mt.count("GAME PLAN") >= 3 and "TRADE REVIEWS" in mt, mt[:300])
        if shots:
            pg.screenshot(path=os.path.join(shots, "pc_mind_1440.png"))
        pc_go(pg, "deck")
        pg.wait_for_selector("#page-deck .dk-wrap #dk-journal", timeout=20000)
        check("d. PC Trader's deck: the eight features", pg.eval_on_selector_all("#page-deck .dk-wrap > .dk-card", "e => e.length") == 8)
        if shots:
            pg.screenshot(path=os.path.join(shots, "pc_deck_1440.png"))
        pc_go(pg, "mission")
        try:
            pg.wait_for_selector("#page-mission #nxReplays a", timeout=30000)
            mc = True
        except Exception:
            mc = False
        check("d. PC Mission Control: Holodeck replay links", mc)
        if mc:
            pg.click("#page-mission #nxReplays a")
            pg.wait_for_timeout(1500)
            check("d. PC: a replay link opens the Holodeck page", pg.evaluate("() => document.getElementById('page-holo')?.classList.contains('active')"))
        check("d. PC: no page errors", not errs, errs[:4])
        br.close()
    srv.should_exit = True


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    shots = shots or os.environ.get("LE_SHOTS", "")
    part_a()
    F = build(shots)
    check(f"fixtures: a real paper-shadow day ({time.strftime('%Y-%m-%d %H:%M', time.gmtime(F['T'] - 4 * 3600))} ET), the Mind sample ({F['mind_src']})",
          F["card"].get("eval") and F["lv"].get("strategies", {}).get("scalp") and F["mind"].get("plans"))
    tmp = tempfile.mkdtemp(prefix="le_blitz_tab_")
    try:
        part_b(F, tmp)
        part_c(F, tmp, shots)
        part_d(F, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nBLITZ tab / Mind / Trader's deck: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
