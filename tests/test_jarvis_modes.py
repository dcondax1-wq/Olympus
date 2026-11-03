"""Jarvis modes + "think for me" (owner 2026-11-03: "make modes for research, trading, business whatever so it is smart. You
should think about things, it shouldn't just be me"): tools/web_public/jarvis/modes.js with brain.js, assistant.js and tools.js,
driven in node on a mocked clock (America/New_York) with one mocked fetch (Groq), then the real shell in Chromium. Checks:
  a. the files: modes.js is an ES module, no imports, no network, Safari 16 safe; the worker saves it (SHELL); the shell loads
     it; assist-ui.js has mountModes
  b. switching: "switch to research mode", "Research mode.", "go to business mode", "life mode on", "auto mode" (and not
     "voice mode", "trading" alone); the auto pick by the question's words; the tools' order per mode in every provider format
  c. deadlines in to-dos: by friday / tomorrow / yesterday / nov 5 / 11/5 / 2026-11-05 / end of the week
  d. the rules ("Here's what I'd do", no key): eval risk (room < 40%), the 7-day rule early (days 3-4) and urgent (day 6), stale
     research data, overdue + due-soon to-dos, a research idea (the Mind's proposal), tomorrow's plan in the evening, the money
     goal, the Kalshi edge, Ascend; each mode its own list with the urgent item first; every action read-only (ask / open /
     mode / control) and never a trade
  e. the brain: a mode switch by words (control 'mode', kept on the phone, the greeting said), "think for me" with no key (the
     rules) and with a Groq key (the model's 3 suggestions, the MODE line in its prompt, no tools); smart answers carry the
     MODE line and the mode's tools first; the quick asks follow the mode; every reply has `say` (plain words)
  f. the set times: once per slot per day
  g. Chromium: the chip row (5 modes + Think for me), a chip switches the mode (pressed, the greeting in the chat, the list
     shown), Think for me fills the list, an item's button asks Jarvis, no page errors
    python -X utf8 -m tests.test_jarvis_modes      (node + Chromium; ~20 s)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []
GROQ = "gsk_FAKE_modes_groq_0123456789"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


RUNNER = r"""
import { pathToFileURL } from 'node:url';
const dir = process.argv[2], KEY = process.argv[3];
const M = await import(pathToFileURL(dir + '/modes.js').href);
const B = await import(pathToFileURL(dir + '/brain.js').href);
const A = await import(pathToFileURL(dir + '/assistant.js').href);
const T = await import(pathToFileURL(dir + '/tools.js').href);
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
const out = {};
let NOW = new Date(2026, 10, 3, 20, 10).getTime();                       // Tue Nov 3 2026, 8:10 PM ET
const et = { y: 2026, mo: 11, d: 3, h: 20, min: 20 * 60 + 10, wd: 2, dn: Math.round(Date.UTC(2026, 10, 3) / 864e5) };

// b. switching, the auto pick, the tools' order
out.sw = ['switch to research mode', 'Research mode.', 'go to business mode', 'life mode on', 'auto mode', 'Jarvis, trading mode', 'turn on money mode',
  'voice mode', 'trading', 'what mode is this', 'personal mode please'].map((q) => M.parseSwitch(q));
out.pick = ['how much room does zlarior have', 'remind me to go to the gym', 'what is the kalshi edge this week', 'look up a study on mean reversion', 'hello'].map((q) => M.pickMode(q));
const oa = T.toolSchema('openai'), ge = T.toolSchema('gemini'), an = T.toolSchema('anthropic');
out.order = {
  research: M.orderTools(oa, 'research').slice(0, 3).map((d) => d.function.name), life: M.orderTools(an, 'life').slice(0, 3).map((d) => d.name),
  gemini: M.orderTools(ge, 'business')[0].functionDeclarations.slice(0, 2).map((d) => d.name), n: [M.orderTools(oa, 'trading').length, oa.length],
  auto: M.orderTools(oa, 'auto') === oa,
};
// c. deadlines
out.dl = ['file taxes by friday', 'call sam by tomorrow', 'pay rent by yesterday', 'essay due nov 5', 'renew by 11/5', 'ship it (due 2026-11-05)', 'plan done by end of the week', 'just a thing', 'by jan 5 send it']
  .map((t) => { const d = M.parseDeadline(t, et); return d == null ? null : d - et.dn; });

// d. the rules
const base = () => ({ now: NOW, et, priorities: [], quiet: [], accounts: [], window: { open: false, text: "Zlarior's next window: tomorrow (Wed) 2:00 AM ET" }, market: { open: false },
  live: { missing: false, stale: false, ago: '' }, kalshi: { state: 'ok', strategies: [{ name: 'Weather', pnl: 42 }, { name: 'Fed', pnl: -18 }], week_pnl: 24 },
  plan: { ev: [], tasks: [] }, todos: [], reminders: [], mind: null, money: { next: 'Pass Zlarior, then the payout', goals: [] }, apps: [{ id: 'ascend', name: 'Ascend' }], smart: false, vault: false, cards: {} });
const D1 = base();
D1.priorities = [{ p: 1, key: 'quiet6:atlas6', text: 'ATLAS (25K) is on day 6 with no trade: place 1 MNQ today. MFFU can close it Wednesday Nov 4.', speak: 'ATLAS is on day 6 with no trade. Place one micro today.', app: 'zenith' }];
D1.quiet = [{ key: 'lit', name: 'Zlarior', q: 4 }, { key: 'atlas', name: 'ATLAS', q: 6 }];
D1.accounts = [{ key: 'lit', name: 'Zlarior', status: 'eval', room: 900, room_frac: 0.3, to_target: 500 }];
D1.todos = [{ text: 'File taxes by yesterday' }, { text: 'Email the landlord by tomorrow' }, { text: 'Buy creatine' }];
D1.reminders = [{ text: 'Call mom', at: NOW + 40 * 60e3 }];
D1.mind = { regime: 'Trend', proposals: [{ idea: 'Skip Mondays after a gap', status: 'testing' }], plan: 'Watch the London low' };
D1.cards = { datacity: { stale: true, age: 4 * 86400, lines: ['old'] }, prometheus: { stale: false, age: 3600, lines: ['3 of 40 strategies beat LIT on 2026'] } };
const all = M.thinkAll(D1);
out.all = all.map((x) => ({ key: x.key, p: x.p, mode: x.mode, text: x.text, say: x.say, label: x.label, action: x.action }));
out.per = {};
for (const id of M.MODE_IDS) { const r = M.thinkFor(D1, id, 3); out.per[id] = { items: r.items.map((x) => x.key), text: r.text, say: r.say }; }
const D2 = base(); D2.kalshi = { state: 'waiting' }; D2.apps = []; D2.money = null; D2.plan = null; D2.et = { ...et, h: 9, min: 9 * 60 };
out.calm = M.thinkFor(D2, 'trading', 3).items.map((x) => x.key);
out.calmAll = M.thinkAll(D2).map((x) => x.key);

// f. the set times
const st0 = mkStore(), mo = M.createModes({ storage: st0 });
const at = (h, mi) => ({ et: { ...et, h, min: h * 60 + mi } });
out.slots = [mo.dueSlot(at(7, 0)), mo.dueSlot(at(7, 45))];
mo.markSlot(at(7, 45), 'morning');
out.slots.push(mo.dueSlot(at(8, 10)), mo.dueSlot(at(12, 5)), mo.dueSlot(at(16, 20)), mo.dueSlot(at(21, 30)), mo.dueSlot(at(23, 30)));
out.modeDefault = mo.mode; mo.set('research'); out.modeKept = st0.m['jarvis.mode']; out.modeNew = M.createModes({ storage: st0 }).mode; mo.set('nonsense'); out.modeBad = mo.mode;

// e. the brain
const CALLS = [], llm = [];
async function fetchAll(url, init) {
  const body = init && typeof init.body === 'string' ? init.body : '';
  CALLS.push({ url: String(url), body });
  const rep = llm.shift() || { choices: [{ message: { content: 'OK.' }, finish_reason: 'stop' }] };
  return { ok: true, status: 200, json: async () => rep, text: async () => JSON.stringify(rep) };
}
const st = mkStore();
const live = { t: NOW / 1000 - 60, board: { lit: { name: 'Zlarior', plan: '50K', status: 'eval', room: 900, room_frac: 0.3, to_target: 500, quiet_days: 4 },
  atlas: { name: 'ATLAS', plan: '25K', status: 'eval', room: 1500, room_frac: 0.8, quiet_days: 6 } } };
const asst = A.createAssistant({ storage: st, now: () => NOW });
const tools = T.createTools({ storage: st, now: () => NOW, fetch: fetchAll });
const modes = M.createModes({ storage: st, cards: () => ({ prometheus: { stale: false, age: 60, lines: ['3 of 40 strategies beat LIT on 2026'] } }) });
const brain = B.createBrain({ storage: st, fetch: fetchAll, getFacts: () => ({ now: NOW, live, kalshiState: 'waiting', apps: [] }), now: () => NOW, assistant: asst, tools, modes, zenithRoutes: false });
const R = {};
const say = async (k, q) => { const r = await brain.ask(q); R[k] = { text: r.text, say: r.say, speak: r.speak, control: r.control || '', mode: r.mode || '', intent: r.intent, items: (r.items || []).map((x) => ({ key: x.key, label: x.label, action: x.action })), smart: !!r.smart }; return r; };
await say('todo', 'add pay rent by yesterday to my list');
await say('think', 'think for me');
out.sugAuto = brain.suggestions();
await say('research', 'switch to research mode');
out.modeAfter = [brain.mode, st.m['jarvis.mode']];
out.sugResearch = brain.suggestions();
await say('wwyd', 'what would you do');
await say('life', 'Life mode.');
out.sugLife = brain.suggestions();
await say('bots', 'how are the bots?');
await say('risk', 'Am I at risk?');
await say('tplan', "Today's trading plan");
await say('accts', 'Plan for more accounts');
await say('dls', 'My to-dos with deadlines');
await say('rf', 'Research findings');
// smart: a Groq key, then think for me = the model's list; a smart answer carries the MODE line and the mode's tools first
brain.setSmart({ key: KEY, on: true });
brain.setMode('research');
llm.push({ choices: [{ message: { content: 'Sure:\n[{"text": "Place 1 MNQ on ATLAS today: day 6.", "ask": "Why no trade?"}, {"text": "Save the Prometheus finding to Obsidian.", "ask": "make a note called Research log: Prometheus finding"}, {"text": "Check why Data City stopped updating."}]' }, finish_reason: 'stop' }] });
const n0 = CALLS.length;
await say('smartThink', 'think for me');
const tb = CALLS[n0] ? JSON.parse(CALLS[n0].body) : {};
out.smartThinkReq = { url: CALLS[n0] ? CALLS[n0].url : '', sys: tb.messages ? tb.messages[0].content : '', tools: !!tb.tools };
llm.push({ choices: [{ message: { content: 'Mean reversion means prices drift back to an average.' }, finish_reason: 'stop' }] });
const n1 = CALLS.length;
await say('smartAsk', 'explain mean reversion in simple words');
const ab = CALLS[n1] ? JSON.parse(CALLS[n1].body) : {};
out.smartAskReq = { sys: ab.messages ? ab.messages[0].content : '', tools: (ab.tools || []).slice(0, 3).map((d) => d.function.name) };
llm.push({ choices: [{ message: { content: 'not json at all' }, finish_reason: 'stop' }] });
await say('smartBad', 'think for me');
const th = await brain.think('business', { smart: false });
out.apiThink = { mode: th.mode, n: (th.items || []).length, say: th.say };
out.digest = (() => { const d = brain.digest(); return d ? { quiet: d.quiet.length, accounts: d.accounts.length, todos: d.todos.length, window: !!d.window } : null; })();
out.R = R;
out.keyHosts = CALLS.filter((c) => c.body.indexOf(KEY) >= 0 || true).map((c) => new URL(c.url).origin);
console.log(JSON.stringify(out));
"""


def part_files():
    src = open(os.path.join(JV, "modes.js"), encoding="utf-8").read()
    ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
    check("a. modes.js parses as an ES module", ok.returncode == 0, ok.stderr)
    check("a. modes.js: no imports, no network, no DOM, Safari 16 safe (no lookbehind, no ?? / ?.)",
          not re.search(r"^\s*import ", src, re.M) and "fetch(" not in src and "http" not in src and "document." not in src
          and "(?<" not in src and "??" not in src and not re.search(r"[\w)\]]\?\.[\w(\[]", src))
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    shell = re.search(r"const SHELL = \[([^\]]*)\]", sw)
    check("a. the worker saves modes.js (SHELL)", shell and "'./modes.js'" in shell.group(1))
    html = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    ui = open(os.path.join(JV, "assist-ui.js"), encoding="utf-8").read()
    check("a. the shell loads modes.js and mounts the mode row; assist-ui.js exports mountModes",
          "load('modes', './modes.js'" in html and "brainDeps.modes" in html and "assist.mountModes" in html and "export function mountModes" in ui)


def run_node():
    tmp = tempfile.mkdtemp(prefix="le_jarvis_modes_")
    try:
        rp = os.path.join(tmp, "runner.mjs")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        r = subprocess.run(["node", rp, JV, GROQ], capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/New_York"})
        check("node ran modes.js + brain.js + assistant.js + tools.js", r.returncode == 0, r.stderr[-2000:])
        if r.returncode:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


PLAIN_BAD = re.compile(r"[*#`\[\]<>$]|https?://|\*\*")


def checks(O):
    check("b. switching by words: research / Research mode. / business / life on / auto / 'Jarvis, trading mode' / money = business; "
          "not 'voice mode', 'trading' alone or a question; personal = life",
          O["sw"] == ["research", "research", "business", "life", "auto", "trading", "business", None, None, None, "life"], O["sw"])
    check("b. auto picks the mode from the words (room = trading, gym = life, kalshi edge = business, study = research, hello = none)",
          O["pick"] == ["trading", "life", "business", "research", ""], O["pick"])
    od = O["order"]
    check("b. the mode's tools first, in OpenAI, Anthropic and Gemini form; none dropped; auto keeps the list",
          od["research"][:2] == ["wiki_summary", "web_search"] and od["life"][:2] == ["list_tasks", "add_task"] and od["gemini"] == ["calc", "get_money"]
          and od["n"][0] == od["n"][1] and od["auto"], od)
    check("c. deadlines: friday +3, tomorrow +1, yesterday -1, nov 5 +2, 11/5 +2, 2026-11-05 +2, end of the week +3, none, jan 5 next year",
          O["dl"][:8] == [3, 1, -1, 2, 2, 2, 3, None] and O["dl"][8] and O["dl"][8] > 50, O["dl"])
    keys = [x["key"] for x in O["all"]]
    has = lambda pre: any(k.startswith(pre) for k in keys)
    check("d. rules: the urgent 7-day item first, eval room < 40%, the 7-day rule early (day 4), near pass, stale Data City, overdue + "
          "due-soon to-dos, a reminder soon, the Mind's idea, the Prometheus finding, tomorrow's plan, the money goal, the Kalshi edge, Ascend",
          keys[0].startswith("pri:quiet6") and all(has(p) for p in ("room:lit", "quiet-early:lit4", "near-pass:lit", "stale:datacity", "todo-over:", "todo-soon:",
                                                                     "rem:", "idea:", "find:prometheus", "tomorrow", "goal", "kalshi-edge", "ascend")), keys)
    tx = {x["key"]: x for x in O["all"]}
    for x in O["all"]:
        tx.setdefault(x["key"].split(":")[0] + ":" + x["key"].split(":")[1] if x["key"].count(":") > 1 else x["key"], x)
    check("d. the words carry the real numbers: $900 room (30%), $500 from passing, Kalshi Weather +$42 / Fed -$18, Data City 4 days, the overdue to-do",
          "$900" in tx["room:lit"]["text"] and "30%" in tx["room:lit"]["text"] and "$500" in tx["near-pass:lit"]["text"]
          and "+$42" in tx["kalshi-edge"]["text"] and "-$18" in tx["kalshi-edge"]["text"] and "4 days" in tx["stale:datacity"]["text"]
          and "File taxes" in [x for x in O["all"] if x["key"].startswith("todo-over")][0]["text"], [tx.get("room:lit"), tx.get("kalshi-edge")])
    acts = [x["action"] for x in O["all"] if x["action"]]
    check("d. every action is read-only: ask / open / mode / control (the key setup) only; no ask places, buys or arms anything",
          acts and all(a["type"] in ("ask", "open", "mode", "control") for a in acts)
          and not any(re.search(r"\b(place|buy|sell|arm|go live|order)\b", str(a.get("value", "")), re.I) for a in acts if a["type"] == "ask"), acts)
    check("d. a research finding is one tap from Obsidian (a 'make a note called Research log: ...' ask, confirmed by the vault)",
          tx["find:prometheus"]["action"] == {"type": "ask", "value": "make a note called Research log: Prometheus: 3 of 40 strategies beat LIT on 2026"}, tx.get("find:prometheus"))
    per = O["per"]
    mode_of = {x["key"]: x["mode"] for x in O["all"]}
    check("d. each mode its own list: the urgent item first, then only that mode's items (3 each)",
          all(per[m]["items"][0].startswith("pri:quiet6") and len(per[m]["items"]) == 3 for m in per)
          and all(mode_of[k] == m for m in ("trading", "research", "business", "life") for k in per[m]["items"][1:]), per)
    check("d. the list's text and speech: 'Here's what I'd do (Research):', numbered; spoken in plain words (no $ or symbols)",
          per["research"]["text"].startswith("Here's what I'd do (Research):\n1. ") and per["auto"]["text"].startswith("Here's what I'd do:\n1. ")
          and all(not PLAIN_BAD.search(per[m]["say"]) for m in per) and "dollars" in per["auto"]["say"], per["auto"]["say"])
    check("d. a calm day still gets useful items (no urgent one): trading has tomorrow / the window, the others a next step each",
          O["calm"] and all(k for k in O["calm"]) and "kalshi-link" in O["calmAll"] and "plan-missing" in O["calmAll"] and "ascend-add" in O["calmAll"], (O["calm"], O["calmAll"]))
    check("f. the set times: none before 7:30, morning at 7:45 once, then midday, close, evening; none at 11:30 PM; mode default auto, kept, junk = auto",
          O["slots"] == [None, "morning", None, "midday", "close", "evening", None] and O["modeDefault"] == "auto" and O["modeKept"] == "research"
          and O["modeNew"] == "research" and O["modeBad"] == "auto", O["slots"])
    R = O["R"]
    check("e. 'think for me' with no key: the rules, 3 items with actions, the overdue to-do among them, spoken (say)",
          R["think"]["intent"] == "think" and len(R["think"]["items"]) == 3 and R["think"]["text"].startswith("Here's what I'd do:")
          and R["think"]["say"] and not R["think"]["smart"], R["think"])
    check("e. 'switch to research mode': control 'mode', kept on the phone, the Research greeting + its list; said out loud",
          R["research"]["control"] == "mode" and R["research"]["mode"] == "research" and O["modeAfter"] == ["research", "research"]
          and "Research mode" in R["research"]["text"] and "Research mode" in R["research"]["say"] and R["research"]["items"], (R["research"], O["modeAfter"]))
    check("e. the quick asks follow the mode (auto: the classic chips; research: its own; life: Planner, reminders, Ascend), the urgent one first",
          "How are the bots?" in O["sugAuto"] and "Research findings" in O["sugResearch"] and "Open Ascend" in O["sugLife"] and O["sugResearch"][0] in ("What should I do now?", "Why no trade?"),
          (O["sugAuto"], O["sugResearch"], O["sugLife"]))
    check("e. 'what would you do' in Research mode: the Research list; 'Life mode.' switches; the rule answers still work ('how are the bots?')",
          R["wwyd"]["intent"] == "think" and "(Research)" in R["wwyd"]["text"] and R["life"]["mode"] == "life" and "Zlarior" in R["bots"]["text"], (R["wwyd"], R["bots"]["text"][:200]))
    check("e. the modes' quick asks answer without a key: risk (the urgent item + each eval's room %), today's trading plan (the window), "
          "more accounts (Zlarior $500 to pass, Builder 50K $91.80), deadlines (overdue), research findings (Prometheus + the bar)",
          R["risk"]["intent"] == "mode_risk" and R["risk"]["text"].startswith("Yes, one thing: ATLAS") and "(30%)" in R["risk"]["text"]
          and R["tplan"]["intent"] == "mode_plan" and "next window" in R["tplan"]["text"]
          and R["accts"]["intent"] == "mode_accounts" and "$500 to pass" in R["accts"]["text"] and "$91.80" in R["accts"]["text"]
          and R["dls"]["intent"] == "mode_deadlines" and "OVERDUE" in R["dls"]["text"]
          and R["rf"]["intent"] == "mode_research" and "Prometheus" in R["rf"]["text"] and "2021-25" in R["rf"]["text"],
          {k: R[k]["text"][:200] for k in ("risk", "tplan", "accts", "dls", "rf")})
    check("e. 'think for me' with a Groq key: one request to api.groq.com without tools, the MODE: RESEARCH line + the rule list in its prompt; "
          "the model's 3 suggestions shown with their follow-up asks",
          O["smartThinkReq"]["url"].startswith("https://api.groq.com/") and not O["smartThinkReq"]["tools"] and "MODE: RESEARCH" in O["smartThinkReq"]["sys"]
          and "RULE LIST" in O["smartThinkReq"]["sys"] and R["smartThink"]["smart"] and len(R["smartThink"]["items"]) == 3
          and R["smartThink"]["items"][0]["action"] == {"type": "ask", "value": "Why no trade?"} and "Place 1 MNQ on ATLAS" in R["smartThink"]["text"], (O["smartThinkReq"]["sys"][:300], R["smartThink"]))
    check("e. a smart answer in Research mode: the MODE line in the prompt and wiki_summary / web_search offered first",
          "MODE: RESEARCH" in O["smartAskReq"]["sys"] and O["smartAskReq"]["tools"][:2] == ["wiki_summary", "web_search"], O["smartAskReq"])
    check("e. a model reply that is not a list: the rules' list instead (never an empty answer)",
          R["smartBad"]["intent"] == "think" and len(R["smartBad"]["items"]) == 3 and not R["smartBad"]["smart"], R["smartBad"])
    check("e. brain.think('business') and brain.digest(): the Business list; the digest sees the quiet days, the accounts, the to-do, the window",
          O["apiThink"]["mode"] == "business" and O["apiThink"]["n"] == 3 and O["apiThink"]["say"] and O["digest"] == {"quiet": 2, "accounts": 2, "todos": 1, "window": True}, (O["apiThink"], O["digest"]))
    check("e. every reply has `say` in plain words (no markdown, links or symbols); the key only went to api.groq.com",
          all(R[k]["say"] and not PLAIN_BAD.search(R[k]["say"]) for k in R) and set(O["keyHosts"]) <= {"https://api.groq.com"}, {k: R[k]["say"] for k in R})


def part_browser():
    """g. Chromium, the real shell: the mode row, a chip, Think for me, an item's button."""
    from tests import test_jarvis_hub as H
    tmp = tempfile.mkdtemp(prefix="le_jarvis_modes_web_")
    path = H.site(tmp, "A", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(__import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
            H.feeds(ctx, H.kalshi_feed())
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.speak', '0'); localStorage.setItem('jarvis.no3d', '1'); localStorage.setItem('jfx', 'off'); } catch (e) {}")
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "jarvis/")
            H.ready(p)
            p.wait_for_function("document.documentElement.dataset.modes === 'module' && document.documentElement.dataset.brain === 'module' && !!document.getElementById('modeRow')", timeout=60000, polling=200)
            chips = p.evaluate("[...document.querySelectorAll('#modeRow [data-mode]')].map((b) => b.dataset.mode)")
            think = p.evaluate("!!document.getElementById('thinkBtn')")
            p.wait_for_function("!document.getElementById('planBox').hidden && document.querySelectorAll('#planBox li').length > 0", timeout=45000, polling=200)
            n0 = p.evaluate("document.querySelectorAll('#planBox li').length")
            check("g. Chromium: the mode row (Auto, Trading, Research, Business, Life + Think for me); on open the list is there unasked",
                  chips == ["auto", "trading", "research", "business", "life"] and think and n0 >= 1, (chips, think, n0))
            p.click("#modeRow [data-mode=research]", timeout=45000, no_wait_after=True)
            p.wait_for_function("[...document.querySelectorAll('#talk .msg.j')].some((m) => /Research mode/.test(m.textContent))", timeout=45000, polling=200)
            head = p.inner_text("#planBox .h span")
            kept = p.evaluate("localStorage.getItem('jarvis.mode')")
            sugs = p.evaluate("[...document.querySelectorAll('#sugs .sug')].map((b) => b.textContent)")
            check("g. a chip switches the mode: pressed, kept, the greeting in the chat, the Research list, the Research quick asks",
                  "research" in head.lower() and kept == "research" and "Research findings" in sugs and p.evaluate("document.documentElement.dataset.jmode") == "research", (head, kept, sugs))
            p.click("#thinkBtn", timeout=45000, no_wait_after=True)
            p.wait_for_function("[...document.querySelectorAll('#talk .msg.me')].some((m) => /Think for me/.test(m.textContent))", timeout=45000, polling=200)
            p.wait_for_timeout(600)
            n1 = p.evaluate("document.querySelectorAll('#planBox li button').length")
            before = p.evaluate("document.querySelectorAll('#talk .msg.me').length")
            p.click("#planBox li button >> nth=0", timeout=45000, no_wait_after=True)
            p.wait_for_timeout(1200)
            after = p.evaluate("document.querySelectorAll('#talk .msg.me').length")
            opened = p.evaluate("document.documentElement.dataset.active || ''")
            check("g. Think for me fills the list with one-tap buttons; a button acts (asks Jarvis or opens the app)",
                  n1 >= 1 and (after > before or opened not in ("", "home")), (n1, before, after, opened))
            check("g. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    part_files()
    O = run_node()
    if O:
        checks(O)
    if os.environ.get("JARVIS_MODES_NO_BROWSER") != "1":
        part_browser()
    n = sum(RES)
    print(f"\njarvis modes: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
