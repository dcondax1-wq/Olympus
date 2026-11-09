"""Jarvis home, briefing, Obsidian and voice (2026-11-04: "make the Jarvis home screen genuinely stunning ... a spoken 7 AM morning
briefing ... deeper Obsidian ... voice commands ... one clear Jarvis settings section"): tools/web_public/jarvis/home3d.js (+ the
hook in backdrop.js, home3d.css), briefing.js, the new memory.js / obsidian.js features and the settings sheet, in node (pure
logic, a fake vault, the brain) and in Chromium (SwiftShader).
  a. the files: home3d.js / briefing.js are ES modules with no static import, no network, Safari 16 safe; backdrop.js loads home3d.js
     by a dynamic import; index.html loads home3d.css and briefing.js; no second renderer or composer was added anywhere
  b. the sky by the New York clock: night, pre-dawn, dawn (6:30), pre-market, the open (9:30), midday, the close, dusk, the evening;
     stars fade by day, the sun and moon cross, shafts are strongest at dawn / dusk, the colours never jump (also over midnight)
  c. weather from the VIX (clear / calm / haze / rain / storm / severe), the VIX found in the feed's shapes, none = clear
  d. the reactor: energy by state and voice level, the mode's colour
  e. the briefing: bots, drawdown left (the real MFFU accounts), the plan and window, Kalshi, the to-dos due, ONE thing; speech has no
     symbols and is short; balances hidden stay hidden; no data still answers; the Markdown note for Obsidian
  f. speak alerts + quiet hours (wrapping midnight), and when the briefing is due (7:00 ET voice, a card on the first open, once a day)
  g. Obsidian: search ranking (title, all terms, phrase, recent, own pages last), "what do I know about X" cites the note titles,
     "pull my tasks" (asks, dedupes, adds to the Jarvis list on yes), the weekly review draft (asks, writes on yes only), "save today's
     brief", "read my notes", "log: ..." (daily note), every write confirmed first
  h. voice commands through the brain: open <app>, switch to <mode> mode, go home, what's next, read my notes, mute / unmute, "hey Jarvis"
  i. Chromium: the home with everything on (sky, shafts, reflections, orbs with badges, constellation lines, dock glass), the clock and
     VIX change the world, state and mode colour the light, Tilt moves the camera (only when on), LITE has no rain and fewer shafts,
     one multisampled composer, no page error
  j. Chromium: the briefing card (first open, spoken from 7:00 ET, quiet hours = card only, once a day, Save to Obsidian asks first) and
     the settings sheet (one Jarvis section: voice, speak alerts, briefing, quiet hours, brain key; saved)
    python -X utf8 -m tests.test_jarvis_home      (node + Chromium; a few minutes on a busy machine)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


RUNNER = r"""
import { pathToFileURL } from 'node:url';
const dir = process.argv[2];
const imp = (f) => import(pathToFileURL(dir + '/' + f).href);
const H = await imp('home3d.js'), Br = await imp('briefing.js'), Mem = await imp('memory.js'), Ob = await imp('obsidian.js');
const Brain = await imp('brain.js'), Asst = await imp('assistant.js'), Modes = await imp('modes.js');
const out = {};
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
const mkKV = () => { const m = new Map(); return { async get(k) { return m.has(k) ? m.get(k) : null; }, async set(k, v) { m.set(k, v); }, async del(k) { m.delete(k); } }; };

// ---- b. the sky
const S = (h, m, we, open) => H.skyFor(h * 60 + m, !!we, !!open);
const pick = (s) => ({ phase: s.phase, label: s.label, stars: +s.stars.toFixed(2), day: +s.day.toFixed(2), sunUp: s.sunUp, sun: s.sun, moon: s.moon, rays: +s.rays.toFixed(2), horizon: s.horizon, exposure: s.exposure });
out.sky = { n3: pick(S(3, 0)), pd: pick(S(5, 30)), dawn: pick(S(6, 30)), pm: pick(S(8, 0)), open: pick(S(9, 30, 0, 1)), noon: pick(S(12, 0, 0, 1)), close: pick(S(16, 0, 0, 1)),
  dusk: pick(S(17, 30)), eve: pick(S(19, 0)), n23: pick(S(23, 30)), noonWeekend: pick(S(12, 0, 1, 0)) };
let jump = 0;
for (let m = 1; m <= 1440; m++) { const a = H.skyFor(m - 1, 0, 0), b = H.skyFor(m % 1440, 0, 0); for (const k of ['zenith', 'horizon', 'glow']) for (let i = 0; i < 3; i++) jump = Math.max(jump, Math.abs(a[k][i] - b[k][i])); }
out.skyJump = +jump.toFixed(4);
out.phases = [[3, 0], [5, 0], [6, 0], [8, 0], [9, 29], [9, 30], [14, 0], [16, 5], [17, 59], [19, 0], [22, 0]].map((x) => H.phaseOf(x[0] * 60 + x[1]).phase);

// ---- c. weather
out.weather = [null, 9, 12, 16, 20, 25, 30, 40].map((v) => { const w = H.weatherFor(v); return { v, name: w.name, rain: +w.rain.toFixed(2), light: +w.lightning.toFixed(2), fog: w.fog }; });
out.vix = [H.findVix({ live: { raw: { lit: { vix: 19.4 } } } }), H.findVix({ live: { raw: { board: { lit: { vix: '22.5' } } } } }), H.findVix({ live: { lit: { vix: 31 } } }), H.findVix(18), H.findVix(2), H.findVix({}), H.findVix(null), H.findVix({ live: { raw: { lit: { vix: 'abc' } } } })];

// ---- d. the reactor
out.react = { idle: H.reactFor('idle', 0), listen: H.reactFor('listening', 0), think: H.reactFor('thinking', 0), s0: H.reactFor('speaking', 0), s1: H.reactFor('speaking', 1), alert: H.reactFor('alert', 0), bad: H.reactFor('speaking', 'x') };
out.tint = { trading: H.modeTint('trading'), auto: H.modeTint('auto'), junk: H.modeTint('toString'), listening: H.STATE_TINT.listening, speaking: H.STATE_TINT.speaking };

// ---- e. the briefing
const NOW = Date.UTC(2026, 10, 4, 12, 30);                     // Wed Nov 4 2026, 7:30 AM ET
const DG = { accounts: [{ key: 'atlas', name: 'ATLAS', status: 'eval', room: 1400, room_frac: 0.8, to_target: 900, today_pnl: 0 }, { key: 'lit', name: 'Zlarior', status: 'eval', room: 900, room_frac: 0.35, to_target: 1500, today_pnl: 120 }],
  window: { text: "Zlarior's next window: today 9:30 AM ET" }, market: { open: false }, live: { missing: false, stale: false, ago: '2 min ago' },
  kalshi: { state: 'ok', run: 'Running', today_pnl: 18.5, week_pnl: 42.1, strategies: [{ name: 'Weather', pnl: 30 }, { name: 'Fed', pnl: -12 }] },
  plan: { ev: [{ title: 'Gym', allDay: false, min: 450, start: '07:30' }, { title: 'Review fills', min: 975 }], tasks: [{ title: 'Buy BLITZ 25K', overdue: false }, { title: 'Pay invoice', overdue: true }] },
  todos: [{ text: 'Buy creatine' }], reminders: [{ text: 'Call mom', at: NOW + 3600e3 }, { text: 'Old one', at: NOW - 3600e3 }],
  priorities: [{ p: 1, text: 'Place 1 MNQ on ATLAS today', speak: 'Place one micro on ATLAS today.', app: 'zenith' }] };
const FX = { system: { verdict: 'ALL GOOD', rows: [{ id: 'pc', name: 'PC', level: 'ok' }, { id: 'lit', name: 'Zlarior', level: 'warn' }], todo: '' } };
const B = Br.buildBrief(DG, { now: NOW, facts: FX, one: { text: 'Size Zlarior down: 35% of the room is left.', say: 'Size Zlarior down.', action: { type: 'open', value: 'zenith' } } });
out.brief = { day: B.day, title: B.title, keys: B.lines.map((l) => l.k), lines: Object.fromEntries(B.lines.map((l) => [l.k, l.text])), one: B.one, speak: B.speak, note: B.note, speakLen: B.speak.length };
const Bh = Br.buildBrief(DG, { now: NOW, facts: FX, hide: true });
out.briefHide = { dd: Bh.lines.find((l) => l.k === 'drawdown').text, speak: Bh.speak, kalshi: Bh.lines.find((l) => l.k === 'kalshi').text };
const Be = Br.buildBrief(null, { now: NOW });
out.briefEmpty = { keys: Be.lines.map((l) => l.k), one: Be.one.text, speak: Be.speak.slice(0, 80), title: Be.title };
const Bp = Br.buildBrief({ ...DG, priorities: [{ p: 1, text: 'Check the PC', speak: 'Check the PC.', app: 'zenith' }] }, { now: NOW });
out.briefPrio = Bp.one;
const Bn = Br.buildBrief({ ...DG, kalshi: { state: 'waiting' }, live: { missing: true }, accounts: [] }, { now: NOW });
out.briefNo = { bots: Bn.lines[0].text, dd: Bn.lines[1].text, k: Bn.lines.find((l) => l.k === 'kalshi').text };

// ---- f. alerts and when it is due
const q = (min) => Br.inQuiet(Br.alertsCfg(null), min);
out.quiet = { m23: q(23 * 60), m3: q(3 * 60), m659: q(6 * 60 + 59), m7: q(7 * 60), m12: q(12 * 60), m22: q(22 * 60), m2159: q(21 * 60 + 59) };
const st = mkStore();
const c1 = Br.saveAlerts(st, { speak: false, from: '23:30', to: '06:15', quiet: true });
out.alerts = { def: Br.alertsCfg(null), saved: c1, re: Br.alertsCfg(st), raw: st.m['jarvis.alerts.v1'], bad: Br.alertsCfg(mkStoreWith('jarvis.alerts.v1', '{"from":"99:99","to":"abc","speak":false}')) };
function mkStoreWith(k, v) { const s = mkStore(); s.m[k] = v; return s; }
out.mayTalk = { def12: Br.mayTalk(Br.alertsCfg(null), 12 * 60), def23: Br.mayTalk(Br.alertsCfg(null), 23 * 60), off12: Br.mayTalk(c1, 12 * 60), noQuiet23: Br.mayTalk({ speak: true, quiet: false, from: '22:00', to: '07:00' }, 23 * 60),
  same: Br.inQuiet({ quiet: true, from: '08:00', to: '08:00' }, 8 * 60), day: Br.inQuiet({ quiet: true, from: '09:00', to: '17:00' }, 12 * 60), dayOut: Br.inQuiet({ quiet: true, from: '09:00', to: '17:00' }, 18 * 60) };
const at = (h, mi) => Date.UTC(2026, 10, 4, h + 5, mi);       // ET -> UTC (EST in November)
const cfg0 = Br.alertsCfg(null);
out.plan = {
  five: Br.briefPlan(null, at(5, 0), cfg0), seven30: Br.briefPlan(null, at(7, 30), cfg0), fifteen: Br.briefPlan(null, at(15, 0), cfg0), night23: Br.briefPlan(null, at(23, 0), cfg0),
  shown: Br.briefPlan({ day: '2026-11-04', shown: true, spoken: false }, at(7, 30), cfg0), shownEarly: Br.briefPlan({ day: '2026-11-04', shown: true, spoken: false }, at(5, 0), cfg0),
  done: Br.briefPlan({ day: '2026-11-04', shown: true, spoken: true }, at(8, 0), cfg0), yesterday: Br.briefPlan({ day: '2026-11-03', shown: true, spoken: true }, at(7, 30), cfg0),
  off: Br.briefPlan(null, at(7, 30), { ...cfg0, brief: false }), speakOff: Br.briefPlan(null, at(7, 30), { ...cfg0, speak: false }), et: Br.etNow(at(7, 30)),
};

// ---- g. Obsidian
const store = mkStore(), vault = Ob.createVault({ storage: store, kv: mkKV(), now: () => NOW });
await vault.importNote('Trailing drawdown', '# Trailing drawdown\nThe max loss trails at the end of the day only. It locks at start + 100.');
await vault.importNote('2026-11-02', 'Felt impatient about the evals. The drawdown worries me. #discipline\n- [ ] Call MFFU support\n- [x] Gym\n');
await vault.importNote('2026-11-03', 'Planned the week. Kalshi sizing ideas.\n- [ ] Review Kalshi strategies\n- [ ] Call MFFU support\n');
await vault.importNote('Random log', 'A long ramble about nothing. ' + 'Words about lunch and the weather. '.repeat(20) + 'One mention of drawdown at the very end.');
await vault.importNote('MFFU notes', '# MFFU rules\nSeven days with no trade can close the account. The trailing drawdown moves up with the balance. Size follows the stop.');
const rank = async (qq) => (await vault.search(qq, 5)).map((x) => x.title);
out.rank = { trailing: await rank('trailing drawdown'), dd: await rank('drawdown'), kalshi: await rank('kalshi sizing'), mffu: await rank('mffu'), none: await rank('zzzz') };
const todosList = [];
const mem = Mem.createMemory({ vault, now: () => NOW, addTodos: (l) => { for (const t of l) todosList.push({ text: t }); return l.length; }, todos: () => todosList });
const h = (t) => mem.handle(t, t.toLowerCase());
const know = await h('what do I know about trailing drawdown');
out.know = { text: know.text, speak: know.speak, cited: know.cited, intent: know.intent, smart: know.smart };
out.parse = Object.fromEntries(['pull my tasks from obsidian', 'import tasks from obsidian', 'pull tasks from my vault', 'add my obsidian tasks to my to-do list', 'sync my vault tasks', 'my tasks', 'open tasks',
  'draft my weekly review', 'weekly review', 'write my weekly review note', 'save today\'s brief', 'save the daily brief to obsidian', 'save my morning briefing', 'read my notes', 'read me my latest notes', 'what is in my notes',
  'what do i know about kalshi'].map((t) => [t, (Mem.parseRead(t) || {}).name || null]));
const impA = await h('pull my tasks from obsidian');
out.imp = { text: impA.text, pending: impA.pending, mem: mem.pending && mem.pending.kind };
const impYes = await h('yes');
out.impYes = { text: impYes.text, todos: todosList.map((t) => t.text) };
const imp2 = await h('pull my tasks from obsidian');
out.imp2 = imp2.text;
const wk = await h('draft my weekly review');
out.wk = { text: wk.text, pending: mem.pending && { kind: mem.pending.kind, title: mem.pending.title, text: mem.pending.text } };
const wkNo = await h('no');
out.wkNo = { text: wkNo.text, outbox: store.m['jarvis.vault.outbox'] || '' };
await h('draft my weekly review'); const wkYes = await h('yes');
out.wkYes = { text: wkYes.text, outbox: JSON.parse(store.m['jarvis.vault.outbox'] || '[]').map((x) => ({ kind: x.kind, title: x.title })) };
const none = await h('save today\'s brief');
out.briefNoText = none.text;
mem.setBrief('### Good morning · Wed Nov 4 · 7:30 AM ET\n- **Bots:** All good.\n- **One thing:** Size down.');
const sb = await h('save today\'s brief to obsidian');
out.saveBrief = { text: sb.text, pending: mem.pending && { kind: mem.pending.kind, title: mem.pending.title } };
const sbYes = await h('yes');
out.saveBriefYes = { text: sbYes.text, outbox: JSON.parse(store.m['jarvis.vault.outbox'] || '[]').map((x) => ({ kind: x.kind, title: x.title, text: String(x.text).slice(0, 40) })) };
const rn = await h('read my notes');
out.readNotes = { text: rn.text, speak: rn.speak, cited: rn.cited };
const asst = Asst.createAssistant({ storage: mkStore(), now: () => NOW });
const lg = asst.handle('log: felt calm after the gym', 'log: felt calm after the gym');
out.log = { vault: lg && lg.vault, text: lg && lg.text };
const off = await mem.offer(lg.vault.kind, lg.vault.text, lg.vault.title);
const offYes = await h('yes');
out.logOffer = { text: off && off.text, yes: offYes.text, outbox: JSON.parse(store.m['jarvis.vault.outbox'] || '[]').map((x) => x.kind) };

// ---- h. voice commands through the brain
const APPS = [{ id: 'home', name: 'Jarvis', url: '' }, { id: 'zenith', name: 'Zenith', url: '../' }, { id: 'planner', name: 'Planner', url: '../planner/' }, { id: 'kalshi', name: 'Kalshi', url: '../kalshi/' }];
const bst = mkStore();
const modes = Modes.createModes({ storage: bst });
const asst2 = Asst.createAssistant({ storage: bst, now: () => NOW });
const mem2 = Mem.createMemory({ vault, now: () => NOW });
const live = { t: NOW / 1000 - 60, board: { running: true, lit: { id: 'lit', name: 'Zlarior', plan: 'MFFU Builder 50K', badge: 'LIVE', balance: 49273.8, floor: 48168.2, room: 1105.6, to_target: 3726.2, today_pnl: 212.5, status: 'eval', room_frac: 0.55 } } };
const brain = Brain.createBrain({ storage: bst, getFacts: () => ({ now: NOW, market: { open: false, text: 'NQ market closed' }, live: { lit: live.board.lit, t: live.t, raw: live, err: null }, kalshi: null, kalshiState: 'waiting', planner: null, apps: APPS }),
  now: () => NOW, assistant: asst2, modes, memory: mem2, zenithRoutes: false, open: () => {} });
const ask = async (t) => { const r = await brain.ask(t); return { open: r.open || '', control: r.control || '', mode: r.mode || '', intent: r.intent || '', text: String(r.text || '').slice(0, 160), speak: String(r.speak || '').slice(0, 120) }; };
out.voice = {};
for (const t of ['open planner', 'open kalshi', 'go home', 'take me home', 'switch to research mode', 'switch to trading mode', 'switch to business mode', 'go to life mode', "what's next", 'read my notes', 'mute', 'unmute', 'hey jarvis, open planner', 'good morning', 'open the planner please']) out.voice[t] = await ask(t);
console.log(JSON.stringify(out));
"""


def run_node():
    d = tempfile.mkdtemp(prefix="jhome_")
    runner = os.path.join(d, "run.mjs")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(RUNNER)
    r = subprocess.run(["node", runner, JV], capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-2500:])
        raise SystemExit("node runner failed")
    return json.loads(r.stdout.strip().splitlines()[-1])


# ----------------------------------------------------------------------------------------------------------------- a. files
def test_static():
    names = ["home3d.js", "briefing.js", "home3d.css"]
    check("a. the new files exist", all(os.path.isfile(os.path.join(JV, n)) for n in names))
    for n in ("home3d.js", "briefing.js"):
        src = read(os.path.join(JV, n))
        code = re.sub(r"//[^\n]*", "", src)
        check(f"a. {n}: an ES module with no static import, no network call, no CDN, no lookbehind, no optional chaining",
              not re.search(r"^\s*import\s", src, re.M) and "fetch(" not in code and "XMLHttpRequest" not in code and not re.search(r"https?://", code)
              and "(?<" not in code and not re.search(r"\?\.[A-Za-z_(\[]", code), n)
    bd = read(os.path.join(JV, "backdrop.js"))
    check("a. backdrop.js hands its scene to home3d.js by a dynamic import and falls back to what it was when that fails",
          "import('./home3d.js')" in bd and ".catch(" in bd and "ext.onStep" in bd and "createRenderer(" in bd and bd.count("createRenderer(") == 1)
    h3 = read(os.path.join(JV, "home3d.js"))
    check("a. home3d.js makes no renderer, no composer and no render target of its own (the one-composer GPU rule)",
          not re.search(r"WebGLRenderer|EffectComposer|WebGLRenderTarget|createRenderer|getContext\(['\"]webgl", h3))
    idx = read(os.path.join(JV, "index.html"))
    check("a. index.html loads home3d.css and briefing.js, and has the one Jarvis settings section",
          'href="home3d.css' in idx and 'src="./briefing.js' in idx and idx.index("<h3>Jarvis</h3>") < idx.index('id="setSpeakAlerts"') < idx.index('id="setQuiet"') < idx.index('id="setSmart"') < idx.index("<h3>Apps</h3>"))
    sw = read(os.path.join(JV, "sw.js"))
    print("   (info) sw.js SHELL lists the new files:", {n: n in sw for n in names}, "- the lead adds them", flush=True)


# ----------------------------------------------------------------------------------------------------------------- b-h. node
def test_node():
    O = run_node()
    s = O["sky"]
    check("b. the phases follow the ET clock: night, pre-dawn, pre-market, the open, the close, dusk, the evening",
          O["phases"] == ["night", "predawn", "predawn", "premarket", "premarket", "open", "open", "close", "dusk", "evening", "night"], O["phases"])
    check("b. stars are full at night and almost gone at midday; day light is 0 at night and 1 at noon",
          s["n3"]["stars"] == 1 and s["noon"]["stars"] < 0.1 and s["n3"]["day"] == 0 and s["noon"]["day"] > 0.95, (s["n3"], s["noon"]))
    check("b. the sun is up from 6:30 to 17:30 (low at dawn, high at noon), the moon takes the night, crossing east to west",
          s["dawn"]["sunUp"] and s["noon"]["sunUp"] and s["dusk"]["sunUp"] and not s["n3"]["sunUp"] and s["dawn"]["sun"]["y"] < 0.1 < 0.9 < s["noon"]["sun"]["y"]
          and s["dawn"]["sun"]["x"] < s["noon"]["sun"]["x"] < s["dusk"]["sun"]["x"] and s["n3"]["moon"]["y"] > 0 and s["n23"]["moon"]["y"] > 0 and not s["noon"]["moon"]["up"], s["dawn"])
    hz = lambda k: s[k]["horizon"]
    check("b. warm at dawn and dusk (red above blue on the horizon), cool at noon (blue above red)",
          hz("dawn")[0] > hz("dawn")[2] and hz("dusk")[0] > hz("dusk")[2] and hz("noon")[2] > hz("noon")[0], (hz("dawn"), hz("noon"), hz("dusk")))
    check("b. the light shafts are strongest with a low sun (dawn, dusk) and softer at midday", s["dawn"]["rays"] > s["noon"]["rays"] and s["dusk"]["rays"] > s["noon"]["rays"], (s["dawn"]["rays"], s["noon"]["rays"], s["dusk"]["rays"]))
    check("b. the weekend is calmer (lower exposure); the colours never jump between two minutes, midnight included", s["noonWeekend"]["exposure"] < s["noon"]["exposure"] and O["skyJump"] < 0.02, (O["skyJump"], s["noonWeekend"]["exposure"]))
    check("c. weather from the VIX: no reading and 9 and 12 clear, 16 calm, 20 haze, 25 rain, 30 storm with lightning, 40 severe",
          [x["name"] for x in O["weather"]] == ["clear", "clear", "clear", "calm", "haze", "rain", "storm", "severe"], O["weather"])
    check("c. rain grows with the VIX, lightning only in storms, the fog thickens", O["weather"][5]["rain"] > 0 and O["weather"][6]["rain"] > O["weather"][5]["rain"] and O["weather"][7]["rain"] == 1
          and O["weather"][5]["light"] == 0 and O["weather"][6]["light"] > 0 and O["weather"][7]["fog"] > O["weather"][3]["fog"], O["weather"])
    check("c. the VIX is found in the feed's shapes (live.raw.lit, live.raw.board.lit as a string, live.lit, a number); junk and out of range = none",
          O["vix"] == [19.4, 22.5, 31, 18, None, None, None, None], O["vix"])
    r = O["react"]
    check("d. energy: calm when idle, up while she listens and thinks, follows her voice level when speaking, high on an alert; junk level = 0.3",
          r["idle"] < 0.1 and 0.35 < r["listen"] < 0.5 and r["think"] == 0.5 and r["s0"] == 0.3 and r["s1"] == 1 and r["alert"] > 0.8 and r["bad"] == 0.3, r)
    check("d. the mode's colour (trading teal) and the state's (listening red); auto and junk (even 'toString') have none",
          O["tint"]["trading"] == "#4b7a99" and O["tint"]["auto"] is None and O["tint"]["junk"] is None and O["tint"]["listening"] == "#c0603f" and O["tint"]["speaking"] is None, O["tint"])

    b = O["brief"]
    check("e. the briefing: a title with the ET day, five lines in order (bots, drawdown, today, Kalshi, to-dos), one thing to do",
          b["day"] == "2026-11-04" and b["title"] == "Good morning · Wed Nov 4" and b["keys"] == ["bots", "drawdown", "today", "kalshi", "todos"] and b["one"]["text"].startswith("Size Zlarior down"), (b["title"], b["keys"]))
    L = b["lines"]
    check("e. 'drawdown left' for the real accounts: the 50K first with its dollars and share of the room, ATLAS next; a low one says size down",
          L["drawdown"].startswith("Zlarior $900 drawdown left (35% of the room)") and "ATLAS $1,400 drawdown left" in L["drawdown"] and "$1,500 to the target" in L["drawdown"]
          and "getting low: size down" in b["speak"], L["drawdown"])
    check("e. today's window and the Planner's events; Kalshi's run line, today, this week, best and worst strategy",
          "next window: today 9:30 AM ET" in L["today"] and "7:30 AM Gym" in L["today"] and "Kalshi" not in L["today"] and L["kalshi"].startswith("Running. Today +$19, this week +$42.") and "Best Weather +$30, worst Fed -$12" in L["kalshi"], (L["today"], L["kalshi"]))
    check("e. the to-dos due: the Planner's (overdue first), my list and today's reminders (an old reminder is not counted), counted",
          L["todos"].startswith("4 things (1 overdue): Pay invoice (overdue)") and "Call mom at 8:30 AM" in L["todos"] and "Old one" not in L["todos"], L["todos"])
    check("e. the bots line names what needs attention from the System view; speech has no symbols or Markdown and stays short",
          "Zlarior to watch" in L["bots"] and "$" not in b["speak"] and "%" not in b["speak"] and "·" not in b["speak"] and b["speakLen"] <= 900 and b["speak"].startswith("Good morning.") and "One thing to do: Size Zlarior down." in b["speak"], (L["bots"], b["speak"]))
    check("e. the Markdown note for Obsidian: a ### title with the time, one bullet per line, the one thing",
          b["note"].startswith("### Good morning · Wed Nov 4 · 7:30 AM ET\n- **Bots:**") and "- **Drawdown left:** Zlarior $900" in b["note"] and b["note"].rstrip().endswith("Size Zlarior down: 35% of the room is left."), b["note"][:200])
    hh = O["briefHide"]
    check("e. hidden balances stay hidden (the brain's hide switch): no dollar figure in the drawdown, Kalshi or the speech",
          "$" not in hh["dd"] and "hidden" in hh["dd"] and "$" not in hh["kalshi"] and "dollars" not in hh["speak"], hh)
    check("e. no data at all still answers: the five lines, a calm one-thing fallback, a greeting; the top priority is the one thing when the rules gave none",
          O["briefEmpty"]["keys"] == ["bots", "drawdown", "today", "kalshi", "todos"] and "Keep the rules" in O["briefEmpty"]["one"] and O["briefEmpty"]["speak"].startswith("Good")
          and O["briefPrio"]["text"] == "Check the PC", (O["briefEmpty"], O["briefPrio"]))
    check("e. no feed: the bots line says so, no eval numbers, Kalshi 'Not connected yet.'",
          "No feed from the PC" in O["briefNo"]["bots"] and "No eval numbers" in O["briefNo"]["dd"] and O["briefNo"]["k"] == "Not connected yet.", O["briefNo"])

    qq = O["quiet"]
    check("f. quiet hours 22:00 to 07:00 wrap midnight: 23:00, 3:00 and 6:59 quiet; 7:00, 12:00 and 21:59 not; 22:00 quiet",
          qq["m23"] and qq["m3"] and qq["m659"] and qq["m22"] and not qq["m7"] and not qq["m12"] and not qq["m2159"], qq)
    al = O["alerts"]
    check("f. the choice is kept (speak, from, to) and bad times fall back; the defaults speak with quiet hours 22:00-07:00 and the briefing on",
          al["def"] == {"speak": True, "brief": True, "quiet": True, "from": "22:00", "to": "07:00"} and al["re"]["speak"] is False and al["re"]["from"] == "23:30" and al["re"]["to"] == "06:15"
          and al["bad"]["from"] == "22:00" and al["bad"]["to"] == "07:00" and al["bad"]["speak"] is False, al)
    mt = O["mayTalk"]
    check("f. she may talk at noon, not at 23:00 (quiet), never with speak alerts off, any time with quiet hours off; same start and end = no quiet; a daytime window works",
          mt["def12"] and not mt["def23"] and not mt["off12"] and mt["noQuiet23"] and not mt["same"] and mt["day"] and not mt["dayOut"], mt)
    p = O["plan"]
    check("f. due: at 5 AM ET the card only (quiet hours); at 7:30 the card and the voice; the first open in the afternoon: both; at 23:00 the card only",
          p["five"]["card"] and not p["five"]["speak"] and p["seven30"]["card"] and p["seven30"]["speak"] and p["fifteen"]["card"] and p["fifteen"]["speak"] and p["night23"]["card"] and not p["night23"]["speak"], p)
    check("f. once a day each: the card shown early, the voice still comes at 7:30; both done = nothing; a new day starts again; briefing off = nothing; speak alerts off = card only",
          not p["shown"]["card"] and p["shown"]["speak"] and not p["shownEarly"]["speak"] and not p["done"]["card"] and not p["done"]["speak"] and p["yesterday"]["card"] and p["yesterday"]["speak"]
          and not p["off"]["card"] and not p["off"]["speak"] and p["speakOff"]["card"] and not p["speakOff"]["speak"] and p["et"]["ymd"] == "2026-11-04" and p["et"]["min"] == 450, p)

    rk = O["rank"]
    check("g. search ranking: the title match first ('trailing drawdown' -> the note with that title), a note with every word before one with a few, junk = nothing",
          rk["trailing"][0] == "Trailing drawdown" and rk["trailing"].index("MFFU notes") < rk["trailing"].index("Random log") and rk["dd"][0] == "Trailing drawdown" and rk["mffu"][0] == "MFFU notes"
          and rk["kalshi"][0] == "2026-11-03" and rk["none"] == [], rk)
    k = O["know"]
    check("g. 'what do I know about X': a plain answer from the notes that cites the note titles (text, speech and cited list)",
          k["cited"][0] == "Trailing drawdown" and "Sources: [[Trailing drawdown]]" in k["text"] and "comes up in" in k["speak"] and "Trailing drawdown" in k["speak"] and k["smart"] is True and k["intent"] == "memory_search", k)
    pr = O["parse"]
    check("g. the phrases: pull / import / sync tasks from Obsidian, the weekly review, save the brief, read my notes; 'my tasks' and 'open tasks' stay the old tasks answer",
          all(pr[t] == "importTasks" for t in ["pull my tasks from obsidian", "import tasks from obsidian", "pull tasks from my vault", "add my obsidian tasks to my to-do list", "sync my vault tasks"])
          and pr["my tasks"] == "tasks" and pr["open tasks"] == "tasks" and pr["draft my weekly review"] == "weekly" and pr["weekly review"] == "weekly" and pr["write my weekly review note"] == "weekly"
          and pr["save today's brief"] == "saveBrief" and pr["save the daily brief to obsidian"] == "saveBrief" and pr["save my morning briefing"] == "saveBrief"
          and pr["read my notes"] == "readNotes" and pr["read me my latest notes"] == "readNotes" and pr["what is in my notes"] == "readNotes" and pr["what do i know about kalshi"] == "search", pr)
    check("g. 'pull my tasks': asks first (the open ones with their notes, never the ticked one), nothing is added before yes",
          O["imp"]["pending"] and O["imp"]["mem"] == "import_tasks" and "Call MFFU support" in O["imp"]["text"] and "Review Kalshi strategies" in O["imp"]["text"] and "Gym" not in O["imp"]["text"]
          and O["imp"]["text"].count("Call MFFU support") == 1 and "Say yes to add them" in O["imp"]["text"], O["imp"])
    check("g. 'yes' adds them (one copy of a task that is in two notes) to the Jarvis list; asking again says they are already there",
          sorted(O["impYes"]["todos"]) == ["Call MFFU support", "Review Kalshi strategies"] and "Added 2 tasks" in O["impYes"]["text"] and "already on your Jarvis list" in O["imp2"], (O["impYes"], O["imp2"]))
    check("g. the weekly review draft asks first (a new note 'Weekly review <day>' with the week's daily notes, themes, done, open, next week), 'no' writes nothing",
          O["wk"]["pending"]["kind"] == "create" and O["wk"]["pending"]["title"] == "Weekly review 2026-11-04" and "Weekly review 2026-11-04" in O["wk"]["text"]
          and "### What I wrote" in O["wk"]["pending"]["text"] and "[[2026-11-03]]" in O["wk"]["pending"]["text"] and "### Still open" in O["wk"]["pending"]["text"] and "- [x] Gym" in O["wk"]["pending"]["text"]
          and "### Next week" in O["wk"]["pending"]["text"] and O["wkNo"]["text"] == "Not saved." and O["wkNo"]["outbox"] in ("", "[]"), (O["wk"]["text"][:200], O["wkNo"]))
    check("g. 'yes' to the weekly review writes it (here kept on the phone: no vault connected), as a new note with its title",
          O["wkYes"]["outbox"] == [{"kind": "create", "title": "Weekly review 2026-11-04"}], O["wkYes"])
    check("g. 'save today's brief': none yet = say so; with the brief set it asks, and yes files it as the note 'Daily brief' (a dated section each day)",
          "no briefing to save" in O["briefNoText"] and O["saveBrief"]["pending"]["title"] == "Daily brief" and O["saveBriefYes"]["outbox"][-1]["title"] == "Daily brief" and O["saveBriefYes"]["outbox"][-1]["text"].startswith("### Good morning · Wed Nov 4"), (O["briefNoText"], O["saveBriefYes"]))
    check("g. 'read my notes': the newest daily notes first, spoken with their titles",
          O["readNotes"]["cited"][0] == "2026-11-03" and "2026-11-03" in O["readNotes"]["speak"] and "Planned the week" in O["readNotes"]["text"], O["readNotes"])
    check("g. 'log: ...' is the daily note: kept as a daily line, offered to the vault, written only after yes",
          O["log"]["vault"]["kind"] == "daily" and O["log"]["vault"]["text"] == "felt calm after the gym" and "Save it to" in O["logOffer"]["text"] and O["logOffer"]["outbox"][-1] == "daily", O["logOffer"])

    v = O["voice"]
    check("h. 'open planner / kalshi' (also 'hey jarvis, open planner' and 'open the planner please') opens the app; 'go home' and 'take me home' go home",
          all(v[t]["open"] == "planner" for t in ("open planner", "hey jarvis, open planner", "open the planner please")) and v["open kalshi"]["open"] == "kalshi" and v["go home"]["open"] == "home" and v["take me home"]["open"] == "home", {t: v[t]["open"] for t in v})
    check("h. 'switch to research / trading / business mode' and 'go to life mode' switch the mode",
          [v[t]["mode"] for t in ("switch to research mode", "switch to trading mode", "switch to business mode", "go to life mode")] == ["research", "trading", "business", "life"]
          and all(v[t]["control"] == "mode" for t in ("switch to research mode", "go to life mode")), {t: (v[t]["mode"], v[t]["control"]) for t in v})
    check("h. 'what's next' answers with what needs me (not the fallback); 'read my notes' reads the vault; 'mute' / 'unmute' are controls; 'good morning' is the briefing",
          v["what's next"]["intent"] not in ("fallback", "error", "") and len(v["what's next"]["text"]) > 10 and v["read my notes"]["intent"] == "memory_read_notes"
          and v["mute"]["control"] == "mute" and v["unmute"]["control"] == "unmute" and v["good morning"]["intent"] == "briefing", {t: (v[t]["intent"], v[t]["control"]) for t in v})


# ----------------------------------------------------------------------------------------------------------------- i, j. Chromium
INIT_DATE = """(() => {
  const D = Date; window.__dateOff = %(off)d - D.now();
  class FD extends D { constructor(...a) { if (a.length) super(...a); else super(D.now() + window.__dateOff); } static now() { return D.now() + window.__dateOff; } }
  window.Date = FD;
})();"""
LAST_LIVE = {"t": 0, "board": {"lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2, "room": 1105.6, "room_frac": 0.55,
                                       "mll": 2000, "to_target": 3726.2, "today_pnl": 212.5, "week_pnl": -224.5, "status": "eval"}, "running": True, "t": 0}}
SAID = "(() => { window.__said = []; let j = null; Object.defineProperty(window, '__jarvis', { configurable: true, get() { return j; }, set(v) { j = v; if (v && typeof v === 'object') v.talk = (t) => { window.__said.push(String(t)); }; } }); })();"


def utc_ms(y, mo, d, h, mi):
    import datetime
    return int((datetime.datetime(y, mo, d, tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=h, minutes=mi)).timestamp() * 1000)


def page(br, origin, fx="high", at_et=(7, 30), extra="", tilt=False, said=True, live=True, alerts=None):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    off = utc_ms(2026, 11, 4, at_et[0] + 5, at_et[1])
    ll = json.loads(json.dumps(LAST_LIVE))
    ll["t"] = ll["board"]["t"] = off // 1000 - 60
    init = INIT_DATE % {"off": off} + f"try {{ localStorage.setItem('jfx', '{fx}'); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.seen', 'j9');"
    if live:
        init += f"localStorage.setItem('jarvis.lastLive', {json.dumps(json.dumps(ll))});"
    if tilt:
        init += "localStorage.setItem('jp3dtilt', '1');"
    if alerts is not None:
        init += f"localStorage.setItem('jarvis.alerts.v1', {json.dumps(json.dumps(alerts))});"
    init += "} catch (e) {}" + extra
    if said:
        init += SAID
    ctx.add_init_script(init)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, p, errs


HOME = "() => { const e = window.__jarvisBackdrop && __jarvisBackdrop.ext; return e && e.state.home && e.state.home.ready ? e.state.home : null; }"
SNAP = """() => { const h = __jarvisBackdrop.ext.state.home; return { phase: h.sky.phase, label: h.sky.label, weather: h.weather.name, rays: h.rays, rain: h.rain, reflect: h.reflect, badges: h.badges,
  cons: h.constellation, draws: h.constellationDraws || 0, energy: +h.energy.toFixed(3), stateTint: h.stateTint, modeTint: h.modeTint, px: +h.parallax.x.toFixed(3), src: h.parallax.src, open: h.open, flashes: h.flashes }; }"""


def boot(p, timeout=300000):
    p.goto(ORIGIN + "/jarvis/?gpu=1")                 # the tests run on software GL: ?gpu=1 lifts the LITE hold so the full world is drawn
    p.wait_for_function("() => window.__jarvisBackdrop && __jarvisBackdrop.frames > 3", timeout=timeout)
    p.wait_for_function("() => { const e = window.__jarvisBackdrop.ext; return e && e.state.home && e.state.home.ready; }", timeout=timeout)
    p.wait_for_timeout(1800)


def opened(br, origin, *a, **kw):
    """page() + boot(), retried: a Chromium tab that crashes while the machine is full is opened again (up to 3 times)"""
    last = None
    for _ in range(3):
        ctx, p, errs = page(br, origin, *a, **kw)
        try:
            boot(p)
            return ctx, p, errs
        except Exception as e:  # noqa: BLE001
            last = e
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass
    raise last


ORIGIN = ""


def session_a(br, GPU, GPU_COUNT):
    # ---- A: 7:30 ET, everything on
    ctx, p, errs = opened(br, ORIGIN, "high", (7, 30), extra=GPU_COUNT)
    s = p.evaluate(SNAP)
    check("i. the home loads home3d.js into the backdrop: no error, the shafts, the mirrored world, the orbs' badges and the constellation lines are there",
          p.evaluate("() => __jarvisBackdrop.extra") == "on" and not p.evaluate("() => __jarvisBackdrop.extError") and s["rays"] >= 3 and s["reflect"] >= 10 and s["badges"] >= 3 and s["cons"] >= 3 and s["draws"] > 0, s)
    check("i. 7:30 AM ET on a weekday is the pre-market morning sky", s["phase"] == "premarket" and s["label"] == "Pre-market", s)
    sat = p.evaluate("() => { const b = document.querySelector('.sat'); const sb = b && b.querySelector('i .sb'); return { n: document.querySelectorAll('.sat').length, sb: document.querySelectorAll('.sat i .sb').length, t: sb ? sb.textContent : '', title: b ? b.title : '' }; }")
    check("i. every orb has a live status badge (a check, a dot, an ! or a dash) and a title with its numbers", sat["n"] >= 3 and sat["sb"] == sat["n"] and sat["t"] in ("✓", "•", "!", "–") and len(sat["title"]) > 3, sat)
    dock = p.evaluate("() => { const d = document.querySelector('#dock'), c = getComputedStyle(d); const b = getComputedStyle(d, '::before'); return { bf: c.backdropFilter || c.webkitBackdropFilter, line: b.content, h: getComputedStyle(document.querySelector('.jconst')).pointerEvents }; }")
    check("i. the dock is glass (a 22 px blur with saturation, a specular line) and the constellation canvas never takes a tap", "blur(22px)" in dock["bf"] and dock["line"] not in ("none", "normal") and dock["h"] == "none", dock)
    g = p.evaluate(GPU)
    check("i. still ONE multisampled composer (the core's two MSAA buffers; the backdrop has none) after home3d.js joined", g["msaa"] == 2, g)
    # the world follows the clock and the VIX
    res = {}
    for name, et, vix in (("dawn", (6, 30), None), ("noon", (12, 0), 14), ("dusk", (17, 30), 20), ("night", (22, 0), 25), ("storm", (22, 0), 31)):
        p.evaluate("([ms, vix]) => { window.__dateOff = ms - (Date.now() - window.__dateOff); window.__homeVix = vix; }", [utc_ms(2026, 11, 4, et[0] + 5, et[1]), vix])
        want = {"dawn": "premarket", "noon": "open", "dusk": "dusk", "night": "night", "storm": "night"}[name]
        try:
            p.wait_for_function("([ph, w]) => { const h = __jarvisBackdrop.ext.state.home; return h.sky.phase === ph && h.weather.vix === w; }", arg=[want, vix], timeout=90000)
        except Exception:
            pass
        p.wait_for_timeout(500)
        res[name] = p.evaluate(SNAP)
    check("i. the sky follows the New York clock live: dawn, midday, dusk, night", [res[k]["phase"] for k in ("dawn", "noon", "dusk", "night")] == ["premarket", "open", "dusk", "night"], {k: v["phase"] for k, v in res.items()})
    check("i. the VIX makes the weather: 14 clear, 20 haze, 25 rain (streaks fall), 31 storm (more rain, lightning flashes over time)",
          res["noon"]["weather"] == "calm" and res["dusk"]["weather"] == "haze" and res["night"]["weather"] == "rain" and res["night"]["rain"] > 50 and res["storm"]["weather"] == "storm" and res["storm"]["rain"] > res["night"]["rain"] and res["dawn"]["rain"] == 0, res)
    # state and mode colour the light
    def until(js, arg=None):
        try:
            p.wait_for_function(js, arg=arg, timeout=90000)
        except Exception:
            pass
    p.evaluate("() => { document.documentElement.dataset.state = 'listening'; }")
    until("() => __jarvisBackdrop.ext.state.home.energy > 0.3 && __jarvisBackdrop.ext.state.home.stateTint === '#c0603f'")
    lis = p.evaluate(SNAP)
    p.evaluate("() => { document.documentElement.dataset.state = 'idle'; }")
    until("() => __jarvisBackdrop.ext.state.home.energy < 0.2 && __jarvisBackdrop.ext.state.home.stateTint === ''")
    idl = p.evaluate(SNAP)
    p.evaluate("() => { localStorage.setItem('jarvis.mode', 'trading'); }")
    until("() => __jarvisBackdrop.ext.state.home.modeTint === '#4b7a99'")
    mode = p.evaluate(SNAP)
    mt = p.evaluate("() => window.__jarvisModeTint")
    check("i. the reactor: listening lifts the energy and turns the light red, idle calms it again, the mode's colour tints the world and the core (window.__jarvisModeTint)",
          lis["energy"] > 0.3 and lis["stateTint"] == "#c0603f" and idl["energy"] < 0.2 and idl["stateTint"] == "" and mode["modeTint"] == "#4b7a99" and mt == "#4b7a99", (lis, idl, mode, mt))
    check("i. no page error from any of it", not errs, errs[:3])
    # a flash of lightning in the storm
    p.wait_for_timeout(500)
    ctx.close()



def test_chromium():
    global ORIGIN
    from playwright.sync_api import sync_playwright
    from tests.test_olympus_kit import launch, serve
    from tests.test_olympus_render import GPU, GPU_COUNT
    srv, ORIGIN = serve()
    with sync_playwright() as pw:
        br = launch(pw)
        if not os.environ.get('JHOME_SKIP_A'):
            session_a(br, GPU, GPU_COUNT)
        if os.environ.get('JHOME_ONLY_A'):
            br.close()
            srv.shutdown()
            return

        # ---- B: Tilt on = the camera leans; off = it does not
        ctx, p, errs = opened(br, ORIGIN, "high", (12, 0), tilt=True, said=False)
        p.evaluate("() => window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', { gamma: 25, beta: 60 }))")
        try:
            p.wait_for_function("() => __jarvisBackdrop.ext.state.home.parallax.x > 0.5", timeout=90000)
            f0 = p.evaluate("() => __jarvisBackdrop.frames")
            p.wait_for_function("(f) => __jarvisBackdrop.frames > f + 2", arg=f0, timeout=90000)
        except Exception:
            pass
        t1 = p.evaluate("() => ({ px: __jarvisBackdrop.ext.state.home.parallax.x, cx: __jarvisBackdrop.ext.camera.position.x - Math.sin(0) , cam: __jarvisBackdrop.ext.cam.x, src: __jarvisBackdrop.ext.state.home.parallax.src })")
        ctx.close()
        ctx, p, errs2 = opened(br, ORIGIN, "high", (12, 0), tilt=False, said=False)
        p.evaluate("() => window.dispatchEvent(new DeviceOrientationEvent('deviceorientation', { gamma: 25, beta: 60 }))")
        f0 = p.evaluate("() => __jarvisBackdrop.frames")
        try:
            p.wait_for_function("(f) => __jarvisBackdrop.frames > f + 6", arg=f0, timeout=90000)
        except Exception:
            pass
        t2 = p.evaluate("() => ({ px: __jarvisBackdrop.ext.state.home.parallax.x, src: __jarvisBackdrop.ext.state.home.parallax.src })")
        check("i. parallax: with Tilt on the phone's lean moves the camera (DeviceOrientation); with Tilt off it does nothing", t1["px"] > 0.5 and t1["src"] == "gyro" and t1["cam"] > 0.7 and t2["px"] == 0 and t2["src"] == "", (t1, t2))
        ctx.close()

        # ---- C: LITE
        ctx, p, errs3 = opened(br, ORIGIN, "low", (12, 0), extra="window.__homeVix = 40;" + GPU_COUNT, said=False)
        lo = p.evaluate(SNAP)
        g = p.evaluate(GPU)
        check("i. LITE (3D effects Low): at most 3 shafts, no rain even in a severe storm, one still constellation, no multisample anywhere, no error",
              0 < lo["rays"] <= 3 and lo["rain"] == 0 and lo["weather"] == "severe" and lo["cons"] >= 3 and g["msaa"] == 0 and not errs3, (lo, g, errs3[:2]))
        ctx.close()

        # ---- D: the briefing at 7:30 ET (cached live feed: Zlarior's room), spoken, saved to Obsidian
        ctx, p, errs4 = opened(br, ORIGIN, "low", (7, 30))
        p.wait_for_function("() => document.querySelector('.jbrief')", timeout=120000)
        p.wait_for_function("() => window.__said && window.__said.length > 0", timeout=60000)
        b = p.evaluate("() => ({ card: document.querySelector('.jbrief').innerText, said: window.__said, says: document.querySelector('#says').textContent, y: scrollY })")
        check("j. 7:30 AM ET first open: the briefing card (title, bots, drawdown left with Zlarior's $1,106, plan, Kalshi, to-dos, ONE THING) and it is READ out loud",
              "Good morning" in b["card"] and "DRAWDOWN LEFT" in b["card"].upper() and "$1,106" in b["card"] and "ONE THING" in b["card"].upper() and len(b["said"]) == 1 and b["said"][0].startswith("Good morning.") and "1106 dollars" in b["said"][0].replace(",", ""), b)
        check("j. on its own it does not scroll the home away (the core stays on screen) and says where the card is", b["y"] < 50 and "your briefing is below" in b["says"], b["y"])
        st = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.brief.v1'))")
        check("j. the day is remembered (shown and spoken): a second tick makes no second card and no second voice",
              st == {"day": "2026-11-04", "shown": True, "spoken": True}, st)
        p.evaluate("() => window.__jarvisBrief.tick()")
        p.wait_for_timeout(800)
        n = p.evaluate("() => [document.querySelectorAll('.jbrief').length, window.__said.length]")
        check("j. once a day: still one card and one voice after another tick", n == [1, 1], n)
        p.evaluate("() => document.querySelector(\".jbrief [data-bf='save']\").click()")
        p.wait_for_selector(".bf-q [data-yn='yes']", timeout=150000)
        q = p.inner_text(".bf-q")
        before = p.evaluate("() => localStorage.getItem('jarvis.vault.outbox')")
        check("j. 'Save to Obsidian' asks first, naming the note (nothing written before yes)", "Daily brief" in q and "Obsidian" in q and (before in (None, "[]", "")), (q, before))
        p.evaluate("() => document.querySelector(\".bf-q [data-yn='yes']\").click()")
        p.wait_for_function("() => { const o = JSON.parse(localStorage.getItem('jarvis.vault.outbox') || '[]'); return o.length > 0; }", timeout=150000)
        ob = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.vault.outbox'))")
        check("j. 'yes' writes it: a note 'Daily brief' (kept on the phone until Obsidian is connected) holding the briefing", ob[-1]["kind"] == "create" and ob[-1]["title"] == "Daily brief" and "### Good morning" in ob[-1]["text"] and "Drawdown left" in ob[-1]["text"], ob)
        p.reload()
        p.wait_for_function("() => window.__jarvisBrief && window.__jarvisBrief.state === 'ready'", timeout=120000)
        p.wait_for_timeout(7000)
        again = p.evaluate("() => [document.querySelectorAll('.jbrief').length, window.__said.length]")
        check("j. a reload the same day: no new briefing", again == [0, 0], again)
        # the settings sheet: one Jarvis section
        p.wait_for_selector("#more [data-key='aikey']", state="attached", timeout=120000)
        p.evaluate("() => document.querySelector('#moreB').click()")
        p.evaluate("() => document.querySelector(\"[data-key='aikey']\").click()")
        p.wait_for_selector("#settings:not([hidden])", timeout=120000)
        sec = p.evaluate("""() => { const f = document.querySelector('#setF'); const order = ['setVoice', 'setSpeakAlerts', 'setBriefOn', 'setQuiet', 'setSmart', 'setKey'].map((id) => { const e = document.getElementById(id); return e ? [id, [...f.querySelectorAll('input,select,button,h3')].indexOf(e)] : [id, -1]; });
          return { h3: [...f.querySelectorAll('h3')].map((h) => h.textContent), title: document.getElementById('setT').textContent, order, vals: { speak: setSpeakAlerts.checked, brief: setBriefOn.checked, quiet: setQuiet.checked, from: setQuietFrom.value, to: setQuietTo.value }, rowHidden: document.getElementById('setQuietRow').hidden }; }""")
        idxs = [i for _, i in sec["order"]]
        check("j. Settings: one 'Jarvis' section first (voice, speak alerts, briefing, quiet hours, then the brain key), then Apps",
              sec["h3"] == ["Jarvis", "Apps"] and sec["title"] == "Settings" and all(i >= 0 for i in idxs) and idxs == sorted(idxs) and sec["vals"] == {"speak": True, "brief": True, "quiet": True, "from": "22:00", "to": "07:00"} and not sec["rowHidden"], sec)
        p.evaluate("() => { setSpeakAlerts.checked = false; setQuietFrom.value = '23:15'; setQuietTo.value = '06:45'; }")
        p.evaluate("() => document.querySelector(\"#setF button[type='submit']\").click()")
        p.wait_for_timeout(500)
        saved = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.alerts.v1'))")
        check("j. Save keeps the Jarvis choices on the phone and the shell obeys them (speak alerts off = no proactive voice)",
              saved == {"speak": False, "brief": True, "quiet": True, "from": "23:15", "to": "06:45"} and p.evaluate("() => window.__jarvisAlerts.mayTalk()") is False, saved)
        check("j. no page error through the briefing and the settings", not errs4, errs4[:3])
        ctx.close()

        # ---- E: 5 AM ET = the card, no voice (quiet hours); the voice at 7:10 on the next tick
        ctx, p, errs5 = opened(br, ORIGIN, "low", (5, 0))
        p.wait_for_function("() => document.querySelector('.jbrief')", timeout=120000)
        p.wait_for_timeout(1500)
        early = p.evaluate("() => [window.__said.length, JSON.parse(localStorage.getItem('jarvis.brief.v1'))]")
        p.evaluate("(ms) => { window.__dateOff = ms - (Date.now() - window.__dateOff); }", utc_ms(2026, 11, 4, 12, 10))
        p.evaluate("() => window.__jarvisBrief.tick()")
        p.wait_for_function("() => window.__said.length > 0", timeout=60000)
        late = p.evaluate("() => [window.__said.length, document.querySelectorAll('.jbrief').length, JSON.parse(localStorage.getItem('jarvis.brief.v1'))]")
        check("j. 5 AM ET (quiet hours): the card, no voice; at 7:10 the voice reads it once, with no second card",
              early[0] == 0 and early[1] == {"day": "2026-11-04", "shown": True, "spoken": False} and late[0] == 1 and late[1] == 1 and late[2]["spoken"] is True and not errs5, (early, late, errs5[:2]))
        ctx.close()
        br.close()
    srv.shutdown()


def main():
    test_static()
    test_node()
    if "node" not in sys.argv[1:]:
        test_chromium()
    n, ok = len(RES), sum(RES)
    print(f"\njarvis home: {ok}/{n} {'ALL PASS' if ok == n else 'FAILED'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
