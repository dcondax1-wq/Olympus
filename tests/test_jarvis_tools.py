"""Jarvis tools (owner 2026-11-03: "whenever I say something, it needs to be smart. It needs to have an answer to everything ...
add to the Obsidian, write notes down, do a ton of stuff"): tools/web_public/jarvis/tools.js with brain.js, assistant.js,
memory.js and obsidian.js, driven in node on a mocked clock (America/New_York) with ONE mocked fetch for every host (GitHub,
open-meteo, Wikipedia, the dictionary, Groq, Gemini, OpenRouter), and checks:
  a. the files: tools.js parses as an ES module, Safari 16 safe, no imports; its only network hosts are the free key-less ones;
     the schema has every tool, in OpenAI, Gemini and Anthropic form
  b. no key: weather (Boston), "and tomorrow?", "no, I meant Miami", time in Tokyo, 5 km in miles, define, "who is ..." from
     Wikipedia, plus the one-time free-key offer (once only), "set up smart mode" opens the setup; the old rule answers stay
  c. notes without a key, vault not connected: write down / note that / make a note called X / add to my gym note / log today
     kept on the phone and queued; connecting the vault sends each to its file (Inbox, OLYMPUS/Notes/Gym plan.md, the owner's
     own Gym.md appended, never overwritten)
  d. reminders still work (set, due once)
  e. Groq tool round trip: the model asks obsidian_create_note -> "Save this to OLYMPUS/Notes/Leg day.md? Say yes or no." ->
     nothing written -> "yes" -> one PUT, a new file; a second write answered "no" writes nothing
  f. a weather answer through the tool (the result goes back as a role 'tool' message, the model's words are the answer)
  g. Gemini (functionCall / functionResponse) for a Wikipedia answer; OpenRouter (sk-or- key) for calc
  h. multi-turn: the follow-up carries the earlier turns
  i. every key and the GitHub token go only to their own API host
  j. `say` on every reply: plain words, no markdown, links, emojis or symbols
    python -X utf8 -m tests.test_jarvis_tools      (node + a temp folder; ~5 s)
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
GROQ, GEM, OR_KEY, GH = "gsk_FAKE_tools_groq_0123456789", "AIza-FAKE-tools-gemini-0123", "sk-or-v1-FAKE-tools-openrouter", "github_pat_FAKE_tools_token_0123"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


RUNNER = r"""
import { pathToFileURL } from 'node:url';
const dir = process.argv[2], K = JSON.parse(process.argv[3]);
const A = await import(pathToFileURL(dir + '/assistant.js').href);
const B = await import(pathToFileURL(dir + '/brain.js').href);
const Mm = await import(pathToFileURL(dir + '/memory.js').href);
const O = await import(pathToFileURL(dir + '/obsidian.js').href);
const T = await import(pathToFileURL(dir + '/tools.js').href);
const out = { defs: T.DEFS.map((d) => d.name), schema: { openai: T.toolSchema('openai').length, gemini: T.toolSchema('gemini')[0].functionDeclarations.length,
  anthropic: T.toolSchema('anthropic')[0].input_schema.type, gtype: T.toolSchema('gemini')[0].functionDeclarations[0].parameters.type } };
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
let NOW = new Date(2026, 10, 3, 10, 50).getTime();                   // Tue Nov 3 2026, 10:50 AM ET
const now = () => NOW;
const facts = () => ({ now: NOW, market: { open: true, text: 'NQ open' } });

// ------------------------------------------------------------------ one fetch for every host
const CALLS = [];
const files = {};                                                     // the GitHub repo: path -> text
const puts = [];
const llm = { groq: [], gemini: [], openrouter: [] };                 // scripted model replies, first in first out
const json = (j, status) => ({ ok: (status || 200) < 400, status: status || 200, json: async () => j, text: async () => JSON.stringify(j), headers: { get: () => null } });
const b64 = (t) => Buffer.from(t, 'utf8').toString('base64');
const days = ['2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09'];
const PLACES = { boston: { name: 'Boston', latitude: 42.36, longitude: -71.06, timezone: 'America/New_York', country_code: 'US', admin1: 'Massachusetts' },
  miami: { name: 'Miami', latitude: 25.77, longitude: -80.19, timezone: 'America/New_York', country_code: 'US', admin1: 'Florida' } };
const WIKI = { Elon_Musk: 'Elon Reeve Musk is a businessman known for his leadership of Tesla and SpaceX. He is one of the wealthiest people in the world. He was born in Pretoria.',
  Ada_Lovelace: 'Augusta Ada King, Countess of Lovelace, was an English mathematician and writer. She is often regarded as the first computer programmer. She worked with Charles Babbage.' };
async function fetchAll(url, init) {
  init = init || {};
  const u = new URL(url), body = typeof init.body === 'string' ? init.body : '';
  CALLS.push({ url: String(url), origin: u.origin, method: init.method || 'GET', headers: init.headers || {}, body });
  if (u.origin === 'https://api.github.com') {
    const p = u.pathname;
    if (p === '/repos/o/vault') return json({ default_branch: 'main' });
    if (p.startsWith('/repos/o/vault/git/trees/')) return json({ sha: 't' + Object.keys(files).length + puts.length, tree: Object.keys(files).map((f, i) => ({ path: f, type: 'blob', sha: 'b' + i + '_' + files[f].length, size: files[f].length })) });
    if (p.startsWith('/repos/o/vault/git/blobs/')) { const i = +p.split('/').pop().slice(1).split('_')[0]; return { ok: true, status: 200, text: async () => files[Object.keys(files)[i]] }; }
    if (p.startsWith('/repos/o/vault/contents/')) {
      const path = decodeURIComponent(p.slice('/repos/o/vault/contents/'.length));
      if ((init.method || 'GET') === 'PUT') { const b = JSON.parse(body); const text = Buffer.from(b.content, 'base64').toString('utf8'); puts.push({ path, text, old: files[path] || null }); files[path] = text; return json({ content: { sha: 'n' } }, 201); }
      return files[path] != null ? json({ sha: 's_' + path, content: b64(files[path]) }) : json({ message: 'Not Found' }, 404);
    }
    return json({ message: 'Not Found' }, 404);
  }
  if (u.origin === 'https://geocoding-api.open-meteo.com') { const g = PLACES[(u.searchParams.get('name') || '').toLowerCase()]; return json(g ? { results: [g] } : {}); }
  if (u.origin === 'https://api.open-meteo.com') {
    const miami = +u.searchParams.get('latitude') < 30;
    return json({ timezone: 'America/New_York', current: { temperature_2m: miami ? 81 : 52, apparent_temperature: miami ? 85 : 47, weather_code: miami ? 1 : 61, wind_speed_10m: 12 },
      daily: { time: days, weather_code: [61, 3, 0, 2, 80, 0, 1], temperature_2m_max: [55, 58, 60, 57, 54, 52, 50], temperature_2m_min: [44, 46, 47, 45, 43, 41, 40], precipitation_probability_max: [80, 20, 0, 10, 60, 5, 0] } });
  }
  if (u.origin === 'https://en.wikipedia.org') {
    const t = decodeURIComponent(u.pathname.split('/').pop());
    return WIKI[t] ? json({ type: 'standard', title: t.replace(/_/g, ' '), description: 'test', extract: WIKI[t] }) : json({ title: 'Not found.' }, 404);
  }
  if (u.origin === 'https://api.dictionaryapi.dev') return json([{ word: 'serendipity', meanings: [{ partOfSpeech: 'noun', definitions: [{ definition: 'An unsought, unintended, and unexpected but fortunate discovery.', example: 'Meeting her there was pure serendipity.' }] }] }]);
  const who = u.origin === 'https://api.groq.com' ? 'groq' : u.origin === 'https://generativelanguage.googleapis.com' ? 'gemini' : u.origin === 'https://openrouter.ai' ? 'openrouter' : null;
  if (who) { const r = llm[who].shift(); if (!r) return json({ error: 'no scripted reply' }, 500); return json(r); }
  return json({ message: 'unexpected host' }, 599);
}
const groqText = (t) => ({ choices: [{ message: { role: 'assistant', content: t }, finish_reason: 'stop' }] });
const groqCall = (name, args, id) => ({ choices: [{ message: { role: 'assistant', content: '', tool_calls: [{ id: id || 'call_1', type: 'function', function: { name, arguments: JSON.stringify(args) } }] }, finish_reason: 'tool_calls' }] });
const all = [];                                                       // every reply, for the say check
const mk = (vault) => {
  const store = mkStore();
  const a = A.createAssistant({ storage: store, now });
  const memory = vault ? Mm.createMemory({ vault, now }) : null;
  const tools = T.createTools({ fetch: fetchAll, storage: store, now });
  const brain = B.createBrain({ getFacts: facts, now, assistant: a, memory, tools, storage: store, fetch: fetchAll, zenithRoutes: false, autoOpen: false });
  const ask = async (t) => { const r = await brain.ask(t); all.push({ q: t, say: r.say, text: r.text }); return { text: r.text, say: r.say, speak: r.speak, intent: r.intent, control: r.control, pending: !!r.pending, tools: r.tools, smart: !!r.smart, offerKey: !!r.offerKey }; };
  return { a, memory, tools, brain, ask, store };
};

// ------------------------------------------------------------------ b. no key
{
  const vault = O.createVault({ fetch: fetchAll, storage: mkStore(), kv: { m: new Map(), async get(k) { return this.m.get(k) || null; }, async set(k, v) { this.m.set(k, v); }, async del(k) { this.m.delete(k); } }, now });
  const J = mk(vault);
  out.b = {};
  for (const t of ["what's the weather in Boston", 'and tomorrow?', 'no, I meant Miami', 'what time is it in Tokyo', 'convert 5 km to miles', 'how many pounds is 80 kg', '70 f to c',
    'define serendipity', 'who is Elon Musk', 'tell me about ada lovelace', 'blorp zzz qqq', 'set up smart mode', 'how are the bots', "what's 15% of 2300", 'is the market open', 'what can you not do'])
    out.b[t] = await J.ask(t);
  out.b_offer = J.store.m['jarvis.keyOffer'] ? true : false;
  out.b_calls_llm = CALLS.filter((c) => /groq|googleapis|openrouter/.test(c.origin)).length;
}

// ------------------------------------------------------------------ c. notes without a key, the vault not connected, then connected
{
  files['Gym.md'] = '# Gym\n\n- bench 3x5\n';
  const vst = mkStore(), kv = { m: new Map(), async get(k) { return this.m.get(k) || null; }, async set(k, v) { this.m.set(k, v); }, async del(k) { this.m.delete(k); } };
  const vault = O.createVault({ fetch: fetchAll, storage: vst, kv, now });
  const J = mk(vault);
  out.c = {};
  for (const t of ['write down buy chalk', 'note that the gym opens at 6', 'make a note called Gym plan: bench Monday, squat Wednesday', 'add deadlift 3x5 to my gym note',
    'log today: slept 8 hours, felt great', 'make a note called Ideas', 'my notes'])
    out.c[t] = await J.ask(t);
  out.c_outbox = JSON.parse(vst.getItem('jarvis.vault.outbox') || '[]').map((w) => [w.kind, w.title || '', w.text]);
  out.c_puts0 = puts.length;
  await vault.connect({ repo: 'o/vault', token: K.gh });
  out.c_puts = puts.map((p) => ({ path: p.path, text: p.text, old: p.old }));
  out.c_outbox_after = JSON.parse(vst.getItem('jarvis.vault.outbox') || 'null');
}

// ------------------------------------------------------------------ d. reminders
{
  const J = mk(null);
  out.d1 = await J.ask('remind me in 20 minutes to stretch');
  out.d_due0 = J.a.due();
  NOW += 25 * 60e3; out.d_due1 = J.a.due(); out.d_due2 = J.a.due(); NOW -= 25 * 60e3;
}

// ------------------------------------------------------------------ e-h. with keys
{
  puts.length = 0;
  for (const k of Object.keys(files)) delete files[k];
  files['Gym.md'] = '# Gym\n\n- bench 3x5\n';
  const vst = mkStore(), kv = { m: new Map(), async get(k) { return this.m.get(k) || null; }, async set(k, v) { this.m.set(k, v); }, async del(k) { this.m.delete(k); } };
  const vault = O.createVault({ fetch: fetchAll, storage: vst, kv, now });
  await vault.connect({ repo: 'o/vault', token: K.gh });
  const seeded = puts.length;                                          // Me.md seeded on connect
  const J = mk(vault);
  J.brain.setSmart({ key: K.groq, on: true });
  const mark = () => CALLS.length;
  // e. the write round trip
  llm.groq.push(groqCall('obsidian_create_note', { title: 'Leg day', text: '## Leg day\n- Squat 5x5\n- RDL 3x8' }));
  let m0 = mark();
  out.e1 = await J.ask('make me a leg day plan and save it to my obsidian');
  out.e_req = CALLS.slice(m0).filter((c) => c.origin === 'https://api.groq.com').map((c) => JSON.parse(c.body));
  out.e_puts1 = puts.length - seeded;
  out.e2 = await J.ask('yes');
  out.e_puts2 = puts.slice(seeded).map((p) => ({ path: p.path, text: p.text, old: p.old }));
  llm.groq.push(groqCall('obsidian_append_note', { target: 'note', title: 'Gym', text: 'Felt strong today' }));
  out.e3 = await J.ask('add to my gym log that I felt strong today');
  out.e4 = await J.ask('no');
  out.e_puts3 = puts.length - seeded;
  // f. weather through the tool
  llm.groq.push(groqCall('get_weather', { place: 'Boston', day: 'tomorrow' }, 'call_w'), groqText('Tomorrow in Boston: cloudy, 46 to 58, a 20 percent chance of rain. A light jacket will do.'));
  m0 = mark();
  out.f1 = await J.ask('should I wear a jacket in Boston tomorrow');
  out.f_req = CALLS.slice(m0).filter((c) => c.origin === 'https://api.groq.com').map((c) => JSON.parse(c.body));
  out.f_tools = CALLS.slice(m0).filter((c) => c.origin !== 'https://api.groq.com').map((c) => c.origin);
  // h. multi-turn
  llm.groq.push(groqText('France won it, beating Croatia 4-2 in the final.'), groqText('Argentina, on penalties against France.'));
  await J.ask('who won the 2018 world cup');
  m0 = mark();
  out.h1 = await J.ask('and 2022?');
  out.h_req = CALLS.slice(m0).filter((c) => c.origin === 'https://api.groq.com').map((c) => JSON.parse(c.body));
  // j. markdown from the model
  llm.groq.push(groqText('**Sure!** Here is the plan:\n- Bench at 6\n- Study 2h\nSee https://example.com/x 🚀 `code`'));
  out.j1 = await J.ask('give me a plan for tonight, gym and study');
  // g. Gemini (Wikipedia) and OpenRouter (calc)
  J.brain.setSmart({ provider: 'gemini', key: K.gem, on: true });
  llm.gemini.push({ candidates: [{ content: { role: 'model', parts: [{ functionCall: { name: 'wiki_summary', args: { topic: 'Ada Lovelace' } }, thoughtSignature: 'sig1' }] }, finishReason: 'STOP' }] },
    { candidates: [{ content: { role: 'model', parts: [{ text: 'Ada Lovelace was an English mathematician, often called the first computer programmer.' }] }, finishReason: 'STOP' }] });
  m0 = mark();
  out.g1 = await J.ask('who was the first programmer ever, explain it to me');
  out.g_req = CALLS.slice(m0).filter((c) => c.origin === 'https://generativelanguage.googleapis.com').map((c) => ({ url: c.url, body: JSON.parse(c.body) }));
  J.brain.setSmart({ key: K.or, on: true });
  out.g_or_smart = J.brain.smart;
  llm.openrouter.push(groqCall('calc', { expression: '15% of 2300' }, 'call_c'), groqText('That is 345 dollars.'));
  m0 = mark();
  out.g2 = await J.ask('if I tip 15 percent on a 2300 dollar bill what do I owe in tips, think about it');
  out.g_or = CALLS.slice(m0).filter((c) => c.origin === 'https://openrouter.ai').map((c) => ({ url: c.url, auth: c.headers.Authorization, body: JSON.parse(c.body) }));
  // the key test (Test button)
  llm.groq.push(groqText('OK'));
  out.g_test = await J.brain.testKey({ provider: 'groq', key: K.groq });
  out.g_test_bad = await J.brain.testKey({ provider: 'anthropic', key: '' });
}
out.calls = CALLS.map((c) => ({ origin: c.origin, url: c.url, headers: c.headers, body: c.body }));
out.all = all;
console.log(JSON.stringify(out));
"""


def part_files():
    src = open(os.path.join(JV, "tools.js"), encoding="utf-8").read()
    ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
    check("a. tools.js parses as an ES module", ok.returncode == 0, ok.stderr)
    urls = set(re.findall(r"https?://[a-z0-9.-]+", src))
    free = {"https://api.open-meteo.com", "https://geocoding-api.open-meteo.com", "https://en.wikipedia.org", "https://api.dictionaryapi.dev", "https://api.duckduckgo.com"}
    check("a. tools.js: Safari 16 safe (no lookbehind, no ?? / ?.), no imports, only the free key-less hosts (open-meteo, Wikipedia, the dictionary, DuckDuckGo)",
          "(?<" not in src and "??" not in src and not re.search(r"[\w)\]]\?\.[\w(\[]", src) and not re.search(r"^\s*import ", src, re.M) and urls <= free
          and not re.search(r"Authorization|x-api-key|x-goog-api-key|token", src.split("export function createTools")[1].split("async function geocode")[0]), urls)


def run_node():
    tmp = tempfile.mkdtemp(prefix="le_jarvis_tools_")
    try:
        rp = os.path.join(tmp, "runner.mjs")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        keys = json.dumps({"groq": GROQ, "gem": GEM, "or": OR_KEY, "gh": GH})
        r = subprocess.run(["node", rp, JV, keys], capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/New_York"})
        check("node ran tools.js + brain.js + assistant.js + memory.js + obsidian.js", r.returncode == 0, r.stderr[-2000:])
        if r.returncode:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def checks(O):
    want = {"obsidian_append_note", "obsidian_create_note", "obsidian_search", "obsidian_read", "add_task", "list_tasks", "set_reminder", "remember_fact", "recall",
            "get_bots_status", "get_money", "open_app", "get_weather", "wiki_summary", "web_search", "calc", "define", "time_in"}
    check("a. the tool schema: all 18 tools; OpenAI / Gemini (upper-case types) / Anthropic forms", set(O["defs"]) == want and O["schema"]["openai"] == 18
          and O["schema"]["gemini"] == 18 and O["schema"]["anthropic"] == "object" and O["schema"]["gtype"] == "OBJECT", O["schema"])
    b = O["b"]
    t = lambda k: (b.get(k) or {}).get("text", "")  # noqa: E731
    check("b. no key, the weather: 'Boston right now: 52°F (feels like 47°F), light rain, wind 12 mph.' + today's range",
          t("what's the weather in Boston").startswith("Boston right now: 52°F (feels like 47°F), light rain, wind 12 mph.") and "44-55°F, 80% chance of rain" in t("what's the weather in Boston"),
          t("what's the weather in Boston"))
    check("b. follow-up 'and tomorrow?' = Boston tomorrow; correction 'no, I meant Miami' = Miami, still tomorrow",
          t("and tomorrow?").startswith("Boston tomorrow: cloudy, 46-58°F") and t("no, I meant Miami").startswith("Miami tomorrow: cloudy, 46-58°F"), (t("and tomorrow?"), t("no, I meant Miami")))
    check("b. time in Tokyo (14 hours ahead), units (5 km = 3.11 miles, 80 kg = 176 pounds, 70°F = 21.1°C)",
          re.match(r"It's \d{1,2}:\d\d [AP]M in Tokyo \(Wednesday\), 14 hours ahead of New York\.", t("what time is it in Tokyo") or "")
          and t("convert 5 km to miles") == "5 km is 3.11 miles." and t("how many pounds is 80 kg") == "80 kg is 176 pounds." and t("70 f to c") == "70°F is 21.1°C.",
          (t("what time is it in Tokyo"), t("convert 5 km to miles"), t("how many pounds is 80 kg"), t("70 f to c")))
    check("b. define (the dictionary) and 'who is Elon Musk' (Wikipedia) answered without a key",
          t("define serendipity").startswith("Serendipity (noun): An unsought") and t("who is Elon Musk").startswith("Elon Reeve Musk is a businessman")
          and "(Wikipedia: Elon Musk)" in t("who is Elon Musk") and "Ada Lovelace" in t("tell me about ada lovelace"), (t("define serendipity"), t("who is Elon Musk")))
    offers = [k for k, v in b.items() if v.get("offerKey")]
    check("b. the free-key offer comes once, after a useful answer ('set up smart mode'), never again; 'set up smart mode' opens the setup",
          offers == ["who is Elon Musk"] and 'say "set up smart mode"' in t("who is Elon Musk") and "set up smart mode" not in t("tell me about ada lovelace")
          and b["set up smart mode"]["control"] == "ai_setup" and O["b_offer"], (offers, b["set up smart mode"]))
    check("b. no generic wall: junk gets the offline line with the key hint; bots, maths and the market stay the rule answers; nothing went to a model",
          "AI key" in t("blorp zzz qqq") and b["how are the bots"]["intent"] not in ("fallback", "assistant_offline") and t("what's 15% of 2300") == "15% of 2,300 is 345."
          and b["is the market open"]["intent"] == "market" and "weather" not in t("what can you not do") and O["b_calls_llm"] == 0, {k: v["intent"] for k, v in b.items()})
    c = O["c"]
    ct = lambda k: (c.get(k) or {}).get("text", "")  # noqa: E731
    check("c. notes without a key: 'write down', 'note that', 'make a note called X: ...', 'add ... to my gym note', 'log today: ...' all kept, said plainly",
          ct("write down buy chalk").startswith("Noted: Buy chalk.") and ct("note that the gym opens at 6").startswith("Noted: The gym opens at 6.")
          and ct("make a note called Gym plan: bench Monday, squat Wednesday").startswith('New note "Gym plan": Bench Monday, squat Wednesday.')
          and ct("add deadlift 3x5 to my gym note").startswith("Added to your Gym note: Deadlift 3x5.") and ct("log today: slept 8 hours, felt great").startswith("Logged for today: Slept 8 hours")
          and "What goes in your Ideas note?" in ct("make a note called Ideas") and "Gym plan" in ct("my notes"), c)
    check("c. not connected: each one says it goes to Obsidian on connect, and waits in the outbox with its kind and title",
          all("once you connect it" in ct(k) for k in list(c)[:5]) and O["c_outbox"] == [["note", "", "buy chalk"], ["note", "", "the gym opens at 6"], ["create", "Gym plan", "bench Monday, squat Wednesday"],
                                                                                     ["append", "Gym", "deadlift 3x5"], ["daily", "", "slept 8 hours, felt great"]] and O["c_puts0"] == 0, O["c_outbox"])
    cp = O["c_puts"]
    paths = [p["path"] for p in cp]
    gp = next((p for p in cp if p["path"] == "OLYMPUS/Notes/Gym plan.md"), {})
    gym = [p for p in cp if p["path"] == "Gym.md"]
    check("c. connecting sends them: the Inbox, a NEW OLYMPUS/Notes/Gym plan.md, his own Gym.md appended (old text kept byte for byte), the outbox emptied",
          "OLYMPUS/Inbox/2026-11-03.md" in paths and gp.get("old") is None and gp.get("text", "").startswith("# Gym plan\n\nbench Monday, squat Wednesday")
          and gym and gym[-1]["text"].startswith("# Gym\n\n- bench 3x5\n") and "- deadlift 3x5 (2026-11-03)" in gym[-1]["text"] and O["c_outbox_after"] is None, cp)
    check("d. reminders: set ('in 20 minutes'), due once after 25 minutes", O["d1"]["text"].startswith("Reminder set: Stretch, in 20 minutes") and O["d_due0"] == []
          and [x["text"] for x in O["d_due1"]] == ["Stretch"] and O["d_due2"] == [], (O["d1"], O["d_due1"]))
    # e
    er = O["e_req"]
    check("e. Groq gets the tools (18, tool_choice auto) and the tool prompt", er and len(er[0].get("tools", [])) == 18 and er[0].get("tool_choice") == "auto"
          and "TOOLS:" in er[0]["messages"][0]["content"], er[:1])
    check("e. the model's write becomes a question naming the file; nothing written before 'yes'",
          O["e1"]["text"].startswith("Save this to OLYMPUS/Notes/Leg day.md? Say yes or no.") and O["e1"]["pending"] and O["e1"]["intent"] == "memory_confirm" and O["e_puts1"] == 0
          and O["e1"]["say"] == "Save this to Leg day? Yes or no.", O["e1"])
    ep = O["e_puts2"]
    check("e. 'yes' writes one new file OLYMPUS/Notes/Leg day.md (title + the plan); a second write answered 'no' writes nothing",
          len(ep) == 1 and ep[0]["path"] == "OLYMPUS/Notes/Leg day.md" and ep[0]["old"] is None and ep[0]["text"] == "# Leg day\n\n## Leg day\n- Squat 5x5\n- RDL 3x8\n"
          and O["e2"]["text"].startswith("Saved to OLYMPUS/Notes/Leg day.md") and O["e3"]["text"].startswith("Save this to Gym.md?") and O["e4"]["text"] == "Not saved." and O["e_puts3"] == 1,
          (ep, O["e2"], O["e3"], O["e4"]))
    fr = O["f_req"]
    tool_msg = [m for m in (fr[1]["messages"] if len(fr) > 1 else []) if m.get("role") == "tool"]
    check("f. weather by tool: open-meteo fetched, the result goes back as a 'tool' message (with the call id), the model's words are the answer",
          len(fr) == 2 and tool_msg and tool_msg[0]["tool_call_id"] == "call_w" and '"place":"Boston, Massachusetts"' in tool_msg[0]["content"]
          and any(m.get("tool_calls") for m in fr[1]["messages"]) and "https://api.open-meteo.com" in O["f_tools"]
          and O["f1"]["text"].startswith("Tomorrow in Boston: cloudy") and O["f1"]["tools"] == ["get_weather"], (fr[1:] and fr[1]["messages"][-2:], O["f1"]))
    gr = O["g_req"]
    fresp = [p for c in (gr[1]["body"]["contents"] if len(gr) > 1 else []) for p in c.get("parts", []) if "functionResponse" in p]
    check("g. Gemini: functionDeclarations sent; the model's functionCall turn echoed (thought signature kept), the Wikipedia result as functionResponse",
          len(gr) == 2 and gr[0]["body"]["tools"][0]["functionDeclarations"] and fresp and fresp[0]["functionResponse"]["name"] == "wiki_summary"
          and "first computer programmer" in json.dumps(fresp) and any(p.get("thoughtSignature") == "sig1" for c in gr[1]["body"]["contents"] for p in c.get("parts", []))
          and O["g1"]["text"].startswith("Ada Lovelace was an English mathematician"), (gr[1:] and gr[1]["body"]["contents"][-2:], O["g1"]))
    go = O["g_or"]
    check("g. OpenRouter (sk-or- key picks it): its address, the Bearer key, a free model, tools; calc ran locally ('345')",
          O["g_or_smart"]["provider"] == "openrouter" and len(go) == 2 and go[0]["url"] == "https://openrouter.ai/api/v1/chat/completions" and go[0]["auth"] == "Bearer " + OR_KEY
          and go[0]["body"]["model"].endswith(":free") and len(go[0]["body"]["tools"]) == 18 and "345" in json.dumps(go[1]["body"]["messages"][-1])
          and O["g2"]["text"] == "That is 345 dollars.", (go[:1], O["g2"]))
    check("g. the Test button: a working key says ok (and how fast); an empty one asks for a key", O["g_test"]["ok"] is True and O["g_test"]["provider"] == "groq"
          and O["g_test_bad"]["ok"] is False and "Paste a key" in O["g_test_bad"]["error"], (O["g_test"], O["g_test_bad"]))
    hr = O["h_req"]
    hm = hr[0]["messages"] if hr else []
    check("h. multi-turn: the follow-up 'and 2022?' carries the earlier question and answer, the follow-up last",
          hm and any(m.get("content") == "who won the 2018 world cup" for m in hm) and any("France won it" in str(m.get("content")) for m in hm)
          and hm[-1] == {"role": "user", "content": "and 2022?"} and O["h1"]["text"].startswith("Argentina"), hm[-4:])
    # i. tokens
    host = {GROQ: "https://api.groq.com", GEM: "https://generativelanguage.googleapis.com", OR_KEY: "https://openrouter.ai", GH: "https://api.github.com"}
    leaks, used = [], {k: 0 for k in host}
    for c in O["calls"]:
        blob = c["url"] + json.dumps(c["headers"]) + (c["body"] or "")
        for k, h in host.items():
            if k in blob:
                used[k] += 1
                if c["origin"] != h:
                    leaks.append((k[:8], c["origin"]))
    free_with_auth = [c["origin"] for c in O["calls"] if c["origin"] in ("https://api.open-meteo.com", "https://geocoding-api.open-meteo.com", "https://en.wikipedia.org", "https://api.dictionaryapi.dev")
                      and any(h.lower() in ("authorization", "x-api-key", "x-goog-api-key") for h in c["headers"])]
    check("i. every key and the GitHub token go only to their own API host (each used); the free tools send no credentials", not leaks and all(used.values()) and not free_with_auth, (leaks, used, free_with_auth))
    # j. say
    bad = [(x["q"], x["say"]) for x in O["all"] if x["say"] and re.search(r"\*\*|__|`|#|\[|\]\(|https?:|•|\||[\U0001F300-\U0001FAFF]|°|→|⋯", x["say"])]
    check("j. `say` on every reply is plain spoken words (no markdown, links, emojis, symbols)", not bad and all("say" in x for x in O["all"]), bad[:5])
    j1 = O["j1"]["say"]
    check("j. markdown from the model: 'Sure! Here is the plan: Bench at 6. Study 2 hours ...' with no link or emoji", j1.startswith("Sure! Here is the plan:") and "example.com" not in j1
          and "🚀" not in j1 and "*" not in j1, j1)


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    part_files()
    O = run_node()
    if O:
        checks(O)
    n = sum(RES)
    print(f"\njarvis tools: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
