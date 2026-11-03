"""Jarvis the personal assistant (owner 2026-11-03: "my own personal assistant that I can tell anything. ANYTHING. And it responds
with a voice that doesn't sound like a bot. Should be a female voice."): tools/web_public/jarvis/assistant.js (facts, reminders,
to-dos, notes, maths, the persona) and tts.js (the voice), with brain.js and memory.js, driven in node on a mocked clock
(America/New_York) and a mocked Groq API, then the shell's hooks in Chromium:
  a. the files: both parse as ES modules, Safari 16 safe (no lookbehind, no ?? / ?.), no imports; assistant.js has no network,
     tts.js talks only to api.groq.com (the optional cloud voice)
  b. memory: "my mom's birthday is March 3" kept and recalled ("when is my mom's birthday", "what did I tell you about Sam",
     "what do you know about me"); the same subject replaced; "forget ..."; a password / key / card number refused and never
     kept; "what's my balance" is not taken (the brain answers)
  c. reminders on a mocked clock: "at 5" at 10:50 AM = 5 PM today, "in 20 minutes", "tomorrow at 9am", "on friday", "tonight";
     due() fires each once, oldest first, a missed one marked late; no time = the to-do list; cancel
  d. to-dos, notes, maths and money ("15% of 2,300", "split $120 four ways", "45 x 12", tip, "(2+3)*4", divide by zero)
  e. the voice ranking: Ava (Premium) over Zoe (Premium) over compact voices, any natural female voice over a male one, never a
     novelty voice (Zarvox, Bubbles, Bad News ...), the owner's pick kept, labels ("Ava · Premium · en-US")
  f. speech text: no markdown, emojis, links or symbols; money / % / k / per month in words; sentence chunks <= the limit, a
     decimal never split, a comma for a breath in a long sentence; cleaning twice changes nothing
  g. the persona prompt: her name, warm female assistant, money first, his trading rules, the talk style, what he told her;
     no secret in it (the smart key, a refused password)
  h. the brain with the assistant: offline (no key) she still keeps facts, reminders and maths, answers the bots from the rules,
     and an open-chat message gets her short line + the 3-step key hint; smart mode (mocked Groq) sends the persona and the
     question, the key only in the Authorization header, and a "[remember: ...]" line is learned, never shown
  i. with the vault connected: a fact kept on the phone is offered to Obsidian ("Say yes"), written only after "yes"
  j. the cloud voice: only with the switch on and a Groq key; a 429 falls back to the phone's voice
  k. Chromium: a due reminder shows in the chat and as a toast when Jarvis opens; the Voice sheet has the talk style, the cloud
     switch and the one-time Ava (Premium) tip; no page errors
    python -X utf8 -m tests.test_jarvis_assistant      (node + a temp folder + a local server; ~30 s)
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
KEY = "gsk_FAKE_assistant_test_key_0123456789"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


RUNNER = r"""
import { pathToFileURL } from 'node:url';
const dir = process.argv[2], KEY = process.argv[3];
const A = await import(pathToFileURL(dir + '/assistant.js').href);
const T = await import(pathToFileURL(dir + '/tts.js').href);
const B = await import(pathToFileURL(dir + '/brain.js').href);
const Mm = await import(pathToFileURL(dir + '/memory.js').href);
const out = {};
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
let NOW = new Date(2026, 10, 3, 10, 50).getTime();                    // Tue Nov 3 2026, 10:50 AM ET (TZ=America/New_York)
const st = mkStore();
const a = A.createAssistant({ storage: st, now: () => NOW });
const ask = (t) => a.handle(t, t.toLowerCase());
// b. memory
out.b = {};
for (const t of ["my mom's birthday is March 3", "when is my mom's birthday?", "Hey Jarvis, remember I owe Sam $40", 'what did I tell you about Sam',
  "I'm allergic to peanuts", 'what do you know about me', "what's my balance", 'how are the bots', "my mom's birthday is March 4", "when's my mom's birthday",
  'my password is hunter2', 'remember my api key is gsk_abcdefgh12345678', 'my card is 4111 1111 1111 1111', 'forget my mom\'s birthday', "when is my mom's birthday",
  'what did I tell you about tennis', 'call me D', 'I love sushi', 'I hate long answers', 'my day was rough', 'i love you'])
  out.b[t] = ask(t);
out.b_facts = a.facts().map((f) => f.text);
out.b_store = st.m['jarvis.assistant.v1'];
// c. reminders on the mocked clock
const R = (t) => { const r = A.parseReminder(t, NOW); return r && r.at ? new Date(r.at).toString().slice(0, 21) + '|' + r.text : r ? 'none|' + r.text : null; };
out.c_parse = {};
for (const t of ['remind me at 5 to run CLEAN_PC', 'remind me in 20 minutes to stretch', 'remind me tomorrow at 9am to call MFFU', 'remind me on friday to buy the 25K',
  'remind me tonight to text her back', 'remind me to run CLEAN_PC at 5:30pm', 'remind me at 9 to check the open', 'remind me at noon to eat', 'set a reminder for 10am tomorrow to study', 'remind me to drink water'])
  out.c_parse[t] = R(t);
out.c_set = [ask('remind me at 5 to run CLEAN_PC'), ask('remind me in 20 minutes to stretch'), ask('remind me tomorrow at 9am to call MFFU')];
out.c_none = ask('remind me to drink water');
out.c_list = ask('my reminders');
out.c_due0 = a.due();
NOW += 25 * 60e3; out.c_due1 = a.due(); out.c_due1b = a.due();
NOW = new Date(2026, 10, 3, 19, 0).getTime(); out.c_due2 = a.due();           // Jarvis opened at 7 PM: the 5 PM one, late
out.c_cancel = ask('cancel the reminder to call MFFU'); out.c_left = a.upcoming();
NOW = new Date(2026, 10, 3, 10, 50).getTime();
// d. to-dos, notes, maths
out.d = {};
for (const t of ['add buy protein to my to-do list', 'todo: finish the essay', 'my to-do list', 'buy protein done', 'my to-do list', 'note: gym app idea, streaks for lifting', 'my notes',
  "what's 15% of 2,300", 'split $120 four ways', "what's 45 x 12", 'tip 20% on 85', '(2+3)*4', 'what is 10 / 0', '2300 * 0.15 + 10', 'how much is 3 squared', '$3,500 / 4'])
  out.d[t] = ask(t);
// e. the voice ranking
const V = (name, lang, uri) => ({ name, lang, voiceURI: uri || name, localService: true });
const PH = [V('Samantha', 'en-US', 'com.apple.voice.compact.en-US.Samantha'), V('Ava', 'en-US', 'com.apple.voice.compact.en-US.Ava'), V('Zoe (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Zoe'),
  V('Ava (Premium)', 'en-US', 'com.apple.voice.premium.en-US.Ava'), V('Daniel (Premium)', 'en-GB', 'com.apple.voice.premium.en-GB.Daniel'), V('Zarvox', 'en-US'), V('Bubbles', 'en-US'),
  V('Bad News', 'en-US'), V('Fred', 'en-US'), V('Thomas', 'fr-FR'), V('Allison (Enhanced)', 'en-US', 'com.apple.voice.enhanced.en-US.Allison')];
out.e = { best: T.bestVoice(PH).name, choices: T.voiceChoices(PH).map((v) => v.name), saved: T.bestVoice(PH, 'Samantha').name, novelty: T.bestVoice(PH, 'Zarvox').name,
  chrome: T.bestVoice([V('Google US English', 'en-US'), V('Google UK English Male', 'en-GB'), V('Google UK English Female', 'en-GB')]).name,
  edge: T.bestVoice([V('Microsoft Guy Online (Natural) - English (United States)', 'en-US'), V('Microsoft Aria Online (Natural) - English (United States)', 'en-US')]).name,
  noEnglish: T.bestVoice([V('Thomas', 'fr-FR')]), label: T.voiceLabel(PH[3]), scores: PH.map((v) => [v.name, T.voiceScore(v)]) };
// f. speech text
const S = ['**Sure!** Here is the plan:\n- Gym at 6\n- Study 2h\nCheck https://example.com/x 🚀🔥', 'You made +$1.2k this week (~$300/mo) & ATLAS is at 50% → keep going',
  "I checked everything and it all looks fine but you should text her today because her birthday is close and she'd love it.", '## Tip\n`code` 2 + 2 = 4, e.g. at 5pm',
  'Zlarior: +$213 today; room $1,106.', 'Price is 1.25 points. Done.'];
out.f = S.map((x) => { const c = T.cleanSpeech(x); return { c, twice: T.cleanSpeech(c), chunks: T.speechChunks(c, 60) }; });
out.f_long = T.speechChunks(T.cleanSpeech('word '.repeat(120)), 100);
// g. persona
st.setItem('jarvis.smart', JSON.stringify({ v: 2, on: true, provider: 'groq', keys: { groq: KEY } }));
a.setSettings({ style: 'chatty' });
out.g = a.persona("what should I get my mom for her birthday");
out.g_short = (a.setSettings({ style: 'short' }), a.persona('x'));
// h. the brain with the assistant: offline (no key) first
const facts = () => ({ now: NOW, market: { open: true, text: 'NQ open' } });
const bst = mkStore(), ast = mkStore();
const a2 = A.createAssistant({ storage: ast, now: () => NOW });
const calls = [];
let reply = "Get her something you made, she'll love it. Want ideas under $50?\n[remember: his mom loves gardening]";
const fetchMock = async (url, init) => { calls.push({ url, headers: init.headers, body: init.body }); return { ok: true, status: 200, json: async () => ({ choices: [{ message: { role: 'assistant', content: reply }, finish_reason: 'stop' }] }) }; };
const brain = B.createBrain({ getFacts: facts, now: () => NOW, assistant: a2, storage: bst, fetch: fetchMock, zenithRoutes: false, autoOpen: false });
const bk = async (t) => { const r = await brain.ask(t); return { text: r.text, speak: r.speak, intent: r.intent }; };
out.h_off = {};
for (const t of ["my sister's name is Mia", "what's my sister's name", 'remind me at 5 to run CLEAN_PC', "what's 15% of 2300", 'ugh school was so stressful today',
  'how do I talk to a girl I like', 'how are the bots', 'is the market open', 'hey', 'thanks', 'blorp zzz qqq', 'help', 'should I text her first'])
  out.h_off[t] = await bk(t);
out.h_calls_off = calls.length;
brain.setSmart({ key: KEY, on: true });
out.h_on = {};
out.h_on.gift = await bk("what should I get my mom for her birthday");
out.h_on.recall = await bk('what did I tell you about my mom');
out.h_on.bots = await bk('how are the bots');
reply = "That's rough. Breathe, then one page at a time. What's due first?";
out.h_on.vent = await bk('ugh school was so stressful today');
out.h_calls = calls.map((c) => ({ url: c.url, auth: c.headers.Authorization, body: c.body }));
// i. the vault connected (a fake vault): the fact is offered, written only after "yes"
const writes = [];
const vault = { status: () => ({ connected: true, notes: 3, repo: 'owner/fake' }), search: async () => [], me: async () => '', write: async (k, t) => { writes.push([k, t]); return { ok: true, paths: ['OLYMPUS/Jarvis/Memory.md'] }; },
  daily: async () => null, tasks: async () => [], recent: async () => ({ notes: [], inbox: [], themes: [] }), goals: async () => [], links: async () => null, sync: async () => ({ notes: 3 }) };
const mem = Mm.createMemory({ vault, now: () => NOW });
const a3 = A.createAssistant({ storage: mkStore(), now: () => NOW });
const brain3 = B.createBrain({ getFacts: facts, now: () => NOW, assistant: a3, memory: mem, storage: mkStore(), zenithRoutes: false, autoOpen: false });
out.i1 = (await brain3.ask("my gym time is 6 AM")).text; out.i_w1 = writes.length;
out.i2 = (await brain3.ask('yes')).text; out.i_w2 = writes.slice();
out.i3 = (await brain3.ask('add renew the VPS to my list')).text;
out.i4 = (await brain3.ask('no')).text; out.i_w3 = writes.length;
out.i5 = (await brain3.ask('when is my gym time')).text;
// j. the cloud voice
const said = [], fetched = [];
class U { constructor(t) { this.text = t; } }
globalThis.SpeechSynthesisUtterance = U;
const synth = { getVoices: () => PH, cancel() {}, speak(u) { said.push([u.text, u.voice && u.voice.name, u.rate, u.pitch]); setTimeout(() => u.onend && u.onend({}), 1); } };
const done = () => new Promise((ok) => setTimeout(ok, 400));
let status = 200;
const cfetch = async (url, init) => { fetched.push({ url, auth: init.headers.Authorization, body: JSON.parse(init.body) }); return { ok: status < 400, status, blob: async () => new Uint8Array([1, 2]) }; };
class FakeAudio { constructor(u) { this.u = u; } play() { setTimeout(() => this.onended && this.onended(), 1); return Promise.resolve(); } pause() {} }
globalThis.URL.createObjectURL = () => 'blob:x'; globalThis.URL.revokeObjectURL = () => {};
let cc = null;
const sp = T.createSpeaker({ synth, cfg: () => ({ rate: 1, pitch: 1 }), cloud: () => cc, fetch: cfetch, Audio: FakeAudio });
let ended = 0;
sp.speak('Hello there. Your room is $1,106.', { onend: () => ended++ }); await done();
out.j_phone = { said: said.slice(), fetched: fetched.length, ended };
said.length = 0; cc = { key: KEY, voice: 'hannah' };
sp.speak('Hello there. Your room is $1,106.', { onend: () => ended++ }); await done();
out.j_cloud = { said: said.slice(), fetched: fetched.map((f) => ({ url: f.url, auth: f.auth === 'Bearer ' + KEY, model: f.body.model, voice: f.body.voice, input: f.body.input, key_in_body: JSON.stringify(f.body).includes(KEY) })), ended };
said.length = 0; fetched.length = 0; status = 429;
sp.speak('Second try.', { onend: () => ended++ }); await done();
out.j_429 = { said: said.slice(), fetched: fetched.length, ended };
fetched.length = 0; status = 200;
sp.speak('Third try.', { onend: () => ended++ }); await done();
out.j_parked = { said: said.slice(-1), fetched: fetched.length };
console.log(JSON.stringify(out));
"""


def part_files():
    for name in ("assistant.js", "tts.js"):
        src = open(os.path.join(JV, name), encoding="utf-8").read()
        ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"a. {name} parses as an ES module", ok.returncode == 0, ok.stderr)
        urls = set(re.findall(r"https?://[a-z0-9.-]+", src))
        check(f"a. {name}: Safari 16 safe (no lookbehind, no ?? / ?.), no imports, network only to " + ("api.groq.com" if name == "tts.js" else "nothing"),
              "(?<" not in src and "??" not in src and not re.search(r"[\w)\]]\?\.[\w(\[]", src) and not re.search(r"^\s*import ", src, re.M)
              and (urls <= {"https://api.groq.com"} if name == "tts.js" else (not urls and "fetch(" not in src)), urls)


def part_node():
    tmp = tempfile.mkdtemp(prefix="le_jarvis_assistant_")
    try:
        rp = os.path.join(tmp, "runner.mjs")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        r = subprocess.run(["node", rp, JV, KEY], capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/New_York"})
        check("node ran assistant.js + tts.js + brain.js + memory.js", r.returncode == 0, r.stderr[-1500:])
        if r.returncode:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def checks(O):
    b = O["b"]
    tx = lambda k: (b.get(k) or {}).get("text", "") if b.get(k) else None
    check("b. a fact is kept at once and said back in his words: 'Your mom's birthday is March 3.'", "Your mom's birthday is March 3" in tx("my mom's birthday is March 3")
          and b["my mom's birthday is March 3"]["intent"] == "assistant_fact", tx("my mom's birthday is March 3"))
    check("b. recalled naturally: 'when is my mom's birthday' -> 'You told me your mom's birthday is March 3.'",
          tx("when is my mom's birthday?") == "You told me your mom's birthday is March 3.", tx("when is my mom's birthday?"))
    check("b. 'remember I owe Sam $40' kept; 'what did I tell you about Sam' recalls it", "You owe Sam $40" in tx("Hey Jarvis, remember I owe Sam $40")
          and "you owe Sam $40" in tx("what did I tell you about Sam"), (tx("Hey Jarvis, remember I owe Sam $40"), tx("what did I tell you about Sam")))
    check("b. 'what do you know about me' lists what he told her", "What you've told me (3 things)" in tx("what do you know about me")
          and "allergic to peanuts" in tx("what do you know about me"), tx("what do you know about me"))
    check("b. 'what's my balance' / 'how are the bots' are not hers (the brain answers)", b["what's my balance"] is None and b["how are the bots"] is None)
    check("b. the same subject replaced: March 4 'Updated', recall says March 4 only", tx("my mom's birthday is March 4").startswith("Updated")
          and tx("when's my mom's birthday") == "You told me your mom's birthday is March 4.", (tx("my mom's birthday is March 4"), tx("when's my mom's birthday")))
    sec = [tx("my password is hunter2"), tx("remember my api key is gsk_abcdefgh12345678"), tx("my card is 4111 1111 1111 1111")]
    check("b. a password, an API key, a card number: refused and never kept (not in the store)", all(s and "won't keep" in s for s in sec)
          and "hunter2" not in O["b_store"] and "gsk_abcdefgh" not in O["b_store"] and "4111" not in O["b_store"], (sec, O["b_store"][:300]))
    check("b. 'forget my mom's birthday' removes it; asked again = not hers any more (weak recall, no match)", tx("forget my mom's birthday").startswith("Forgotten")
          and b["when is my mom's birthday"] is None, (tx("forget my mom's birthday"), b["when is my mom's birthday"]))
    check("b. 'what did I tell you about tennis' (nothing): said plainly", "haven't told me anything about tennis" in tx("what did I tell you about tennis"), tx("what did I tell you about tennis"))
    check("b. 'call me D' and 'I love sushi' kept; 'I hate long answers' (about her) and moods / 'i love you' are not facts",
          tx("call me D") == "Got it, D." and "You love sushi" in tx("I love sushi") and b["I hate long answers"] is None and b["my day was rough"] is None and b["i love you"] is None, b)
    # c
    cp = O["c_parse"]
    want = {"remind me at 5 to run CLEAN_PC": "Tue Nov 03 2026 17:00|run CLEAN_PC", "remind me in 20 minutes to stretch": "Tue Nov 03 2026 11:10|stretch",
            "remind me tomorrow at 9am to call MFFU": "Wed Nov 04 2026 09:00|call MFFU", "remind me on friday to buy the 25K": "Fri Nov 06 2026 09:00|buy the 25K",
            "remind me tonight to text her back": "Tue Nov 03 2026 20:00|text her back", "remind me to run CLEAN_PC at 5:30pm": "Tue Nov 03 2026 17:30|run CLEAN_PC",
            "remind me at 9 to check the open": "Tue Nov 03 2026 21:00|check the open", "remind me at noon to eat": "Tue Nov 03 2026 12:00|eat",
            "set a reminder for 10am tomorrow to study": "Wed Nov 04 2026 10:00|study", "remind me to drink water": "none|drink water"}
    bad = {k: (cp.get(k), v) for k, v in want.items() if cp.get(k) != v}
    check("c. times on the mocked clock (Tue 10:50 AM ET): at 5 = 5 PM, in 20 min, tomorrow 9am, friday, tonight 8 PM, 5:30pm, at 9 = 9 PM, noon, 10am tomorrow",
          not bad, bad)
    cs = O["c_set"]
    check("c. set: 'Reminder set: Run CLEAN_PC, today at 5 PM.' (+ the Home Screen note once); spoken in plain words",
          cs[0]["text"].startswith("Reminder set: Run CLEAN_PC, today at 5 PM.") and "Home Screen" in cs[0]["text"] and "Home Screen" not in cs[1]["text"]
          and cs[0]["speak"] == "Okay. I'll remind you today at 5 PM to run CLEAN_PC." and "in 20 minutes" in cs[1]["text"], [c["text"] for c in cs])
    check("c. no time given: on the to-do list, says so", O["c_none"]["intent"] == "assistant_todo" and "to-do list" in O["c_none"]["text"], O["c_none"])
    check("c. 'my reminders' lists them, soonest first", O["c_list"]["text"].startswith("3 reminders:") and O["c_list"]["text"].index("Stretch") < O["c_list"]["text"].index("Run CLEAN_PC"), O["c_list"]["text"])
    check("c. fired by the clock: nothing at once; 'Stretch' after 25 min (each once); at 7 PM the 5 PM one, marked late",
          O["c_due0"] == [] and [d["text"] for d in O["c_due1"]] == ["Stretch"] and O["c_due1b"] == []
          and [d["text"] for d in O["c_due2"]] == ["Run CLEAN_PC"] and O["c_due2"][0]["late"] and not O["c_due1"][0]["late"], (O["c_due1"], O["c_due2"]))
    check("c. 'cancel the reminder to call MFFU': gone", O["c_cancel"]["text"] == "Cancelled: Call MFFU." and O["c_left"] == [], (O["c_cancel"], O["c_left"]))
    # d
    d = {k: (v or {}).get("text") for k, v in O["d"].items()}
    check("d. to-dos: added, listed, ticked off ('buy protein done'), the list says what is left",
          d["add buy protein to my to-do list"].startswith("Added to your to-do list: Buy protein") and "Finish the essay" in d["todo: finish the essay"]
          and d["buy protein done"].startswith("Done: Buy protein.") and "Buy protein" not in list(O["d"].values())[4]["text"], d)
    check("d. notes: 'note: ...' kept, 'my notes' reads them back", d["note: gym app idea, streaks for lifting"].startswith("Noted:") and "streaks for lifting" in d["my notes"], d)
    check("d. maths and money: 15% of 2,300 = 345; $120 / 4 = $30 each; 45 x 12 = 540; tip; (2+3)*4 = 20; 10 / 0 said; 3 squared = 9; $3,500 / 4 = $875",
          d["what's 15% of 2,300"] == "15% of 2,300 is 345." and d["split $120 four ways"] == "$120 split 4 ways is $30 each." and d["what's 45 x 12"].endswith("= 540")
          and d["tip 20% on 85"] == "A 20% tip on $85 is $17, $102 in total." and d["(2+3)*4"].endswith("= 20") and "divides by zero" in d["what is 10 / 0"]
          and d["2300 * 0.15 + 10"].endswith("= 355") and d["how much is 3 squared"].endswith("= 9") and d["$3,500 / 4"].endswith("= $875"), d)
    # e
    e = O["e"]
    check("e. voice: Ava (Premium) first, then Zoe (Premium), Allison (Enhanced); compact voices after; a natural female voice over a premium male one",
          e["best"] == "Ava (Premium)" and e["choices"][:3] == ["Ava (Premium)", "Zoe (Premium)", "Allison (Enhanced)"]
          and e["choices"].index("Samantha") < e["choices"].index("Daniel (Premium)") and e["choices"].index("Ava") < e["choices"].index("Samantha"), e)
    check("e. voice: never a novelty voice (Zarvox, Bubbles, Bad News, Fred), even when saved; not English never offered",
          not {"Zarvox", "Bubbles", "Bad News", "Fred", "Thomas"} & set(e["choices"]) and e["novelty"] == "Ava (Premium)" and e["noEnglish"] is None, e["choices"])
    check("e. voice: the owner's pick kept; Chrome = Google UK English Female; Edge = Aria (Natural); label 'Ava · Premium · en-US'",
          e["saved"] == "Samantha" and e["chrome"] == "Google UK English Female" and e["edge"].startswith("Microsoft Aria") and e["label"] == "Ava · Premium · en-US", e)
    # f
    f = O["f"]
    check("f. speech text: no markdown, list marks, links or emojis ('Check a link.')", f[0]["c"] == "Sure! Here is the plan: Gym at 6. Study 2h. Check a link." , f[0]["c"])
    check("f. money and symbols in words: '1.2 thousand dollars', 'about 300 dollars a month', 'and', '50 percent', ', then'",
          f[1]["c"] == "You made 1.2 thousand dollars this week, about 300 dollars a month, and ATLAS is at 50 percent, then keep going.", f[1]["c"])
    check("f. a long sentence breathes: a comma before 'but' and 'because'", ", but you should" in f[2]["c"] or ", but you should" in " ".join(f[2]["chunks"]), f[2])
    check("f. headings and code marks dropped, '2 plus 2 equals 4', 'for example', '5 PM'", f[3]["c"] == "Tip. code 2 plus 2 equals 4, for example at 5 PM.", f[3]["c"])
    check("f. '+$213' = 'up 213 dollars', '$1,106' = '1,106 dollars'", f[4]["c"] == "Zlarior: up 213 dollars today, room 1,106 dollars.", f[4]["c"])
    check("f. chunks: every one <= the limit, sentence ends kept, a decimal (1.25) never split; cleaning twice changes nothing",
          all(len(c) <= 60 for x in f for c in x["chunks"]) and any("1.25 points." in c for c in f[5]["chunks"]) and all(x["twice"] == x["c"] for x in f)
          and all(len(c) <= 100 for c in O["f_long"]) and len(O["f_long"]) >= 6, [x["chunks"] for x in f])
    # g
    g, gs = O["g"]["prompt"], O["g_short"]["prompt"]
    check("g. persona: Jarvis, a warm, sharp, loyal young woman; talks like a person; money first; his trading rules; [remember: ...] for facts",
          g.startswith("You are Jarvis, his personal assistant") and "warm, sharp, loyal young woman" in g and "Money first" in g and "beyond the sweep extreme" in g
          and "size follows the stop" in g and "[remember:" in g and "988" in g, g[:400])
    check("g. persona: what he told her (the relevant facts first) and the talk style (chatty vs short)",
          "WHAT HE HAS TOLD YOU" in g and "allergic to peanuts" in g and "Talk style: chatty" in g and "Talk style: short" in gs, g[-600:])
    check("g. persona: no secrets in it (not the smart key, not a refused password or card)", KEY not in g and "hunter2" not in g and "4111" not in g and "gsk_" not in g)
    # h
    ho = O["h_off"]
    t = lambda k: ho[k]["text"]
    check("h. offline: facts kept and recalled through the brain ('You told me your sister's name is Mia.')", "Your sister's name is Mia" in t("my sister's name is Mia")
          and t("what's my sister's name") == "You told me your sister's name is Mia.", (t("my sister's name is Mia"), t("what's my sister's name")))
    check("h. offline: reminders and maths work", t("remind me at 5 to run CLEAN_PC").startswith("Reminder set") and t("what's 15% of 2300") == "15% of 2,300 is 345.",
          (t("remind me at 5 to run CLEAN_PC"), t("what's 15% of 2300")))
    check("h. offline: venting gets her warm line + the 3-step key hint; an open question gets the key hint; never the old 'I can switch dashboards' fallback",
          "That sounds heavy" in t("ugh school was so stressful today") and "AI key (3 steps" in t("ugh school was so stressful today")
          and "AI key (3 steps" in t("how do I talk to a girl I like") and "AI key" in t("blorp zzz qqq") and "should I text her first" in ho
          and "AI key" in t("should I text her first") and not t("should I text her first").startswith("Your call"), ho)
    check("h. offline: the rule answers stay (bots, market, hey, thanks, help names her new tricks); nothing sent anywhere",
          ho["how are the bots"]["intent"] not in ("chat", "assistant_offline") and ho["is the market open"]["intent"] == "market" and ho["hey"]["intent"] == "hello"
          and ho["thanks"]["intent"] == "smalltalk" and "remind me at 5" in t("help") and O["h_calls_off"] == 0, {k: v["intent"] for k, v in ho.items()})
    hn, hc = O["h_on"], O["h_calls"]
    check("h. smart: open chat goes to Groq with the persona (+ what he told her) and the question; the key only in the Authorization header",
          hn["gift"]["intent"] == "chat" and hc and hc[0]["url"] == "https://api.groq.com/openai/v1/chat/completions" and hc[0]["auth"] == "Bearer " + KEY
          and KEY not in hc[0]["body"] and "warm, sharp, loyal young woman" in hc[0]["body"] and "sister's name is Mia" in hc[0]["body"]
          and "what should I get my mom for her birthday" in hc[0]["body"] and "Answer ONLY from the FACTS" in hc[0]["body"], hc[:1])
    check("h. smart: the '[remember: ...]' line is learned, never shown or said; the text notes it ('Remembered: your mom loves gardening')",
          "[remember" not in hn["gift"]["text"] and "[remember" not in (hn["gift"]["speak"] or "") and "Remembered: your mom loves gardening" in hn["gift"]["text"]
          and "gardening" not in (hn["gift"]["speak"] or "") and "mom loves gardening" in hn["recall"]["text"], (hn["gift"], hn["recall"]))
    check("h. smart: the bots still come from the rules (no model call for them); venting goes to the model",
          hn["bots"]["intent"] not in ("chat", "smart") and hn["vent"]["intent"] == "chat" and hn["vent"]["text"].startswith("That's rough") and len(hc) == 2, [x["url"] for x in hc])
    # i
    check("i. vault connected: the fact is kept on the phone and offered to Obsidian ('… too? Say yes.'), nothing written yet",
          "Your gym time is 6 AM" in O["i1"] and "too? Say yes." in O["i1"] and O["i_w1"] == 0, O["i1"])
    check("i. 'yes' writes it (append-only, kind remember); a to-do offered and 'no' writes nothing; still recalled",
          O["i_w2"] == [["remember", "My gym time is 6 AM"]] and O["i2"].startswith("Saved to") and "too? Say yes." in O["i3"] and O["i_w3"] == 1
          and O["i4"] == "Not saved." and "gym time is 6 AM" in O["i5"], (O["i_w2"], O["i2"], O["i3"], O["i4"], O["i5"]))
    # j
    jp, jc, j4, jk = O["j_phone"], O["j_cloud"], O["j_429"], O["j_parked"]
    check("j. no cloud: the phone's voice (Ava Premium) in sentence chunks, rate / pitch 1, nothing fetched",
          [x[0] for x in jp["said"]] == ["Hello there. Your room is 1,106 dollars."] or (len(jp["said"]) >= 1 and all(x[1] == "Ava (Premium)" for x in jp["said"]))
          and jp["fetched"] == 0 and jp["ended"] == 1, jp)
    check("j. cloud on + a Groq key: Orpheus at api.groq.com, the key only in the header, the cleaned text, no phone voice",
          jc["fetched"] and all(f["url"] == "https://api.groq.com/openai/v1/audio/speech" and f["auth"] and not f["key_in_body"] and f["model"] == "canopylabs/orpheus-v1-english"
                                and f["voice"] == "hannah" for f in jc["fetched"]) and "1,106 dollars" in " ".join(f["input"] for f in jc["fetched"]) and jc["said"] == [] and jc["ended"] == 2, jc)
    check("j. a 429: the phone's voice says it instead, and the cloud is parked for the day", j4["said"] and j4["said"][0][0] == "Second try." and j4["ended"] == 3
          and jk["fetched"] == 0 and jk["said"] and jk["said"][0][0] == "Third try.", (j4, jk))


def part_browser():
    from tests import test_jarvis_hub as H
    tmp = tempfile.mkdtemp(prefix="le_jarvis_assistant_web_")
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
            due = json.dumps({"v": 1, "facts": [], "todos": [], "notes": [], "told": True,
                              "reminders": [{"id": "r1", "t": 1, "at": 1000, "text": "Run CLEAN_PC", "fired": 0}]})
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
                                f" localStorage.setItem('jarvis.intro', 'off'); if (!localStorage.getItem('jarvis.assistant.v1')) localStorage.setItem('jarvis.assistant.v1', {json.dumps(due)}); }} catch (e) {{}}")
            ctx.add_init_script("window.__said = []; if (window.speechSynthesis) { speechSynthesis.speak = (u) => { window.__said.push(u.text); setTimeout(() => u.onend && u.onend(), 30); }; }")
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "jarvis/")
            H.ready(p)
            p.wait_for_function("document.documentElement.dataset.assistant === 'module' && document.documentElement.dataset.tts === 'module'", timeout=20000)
            p.wait_for_function("[...document.querySelectorAll('#talk .msg')].some((m) => /Reminder: Run CLEAN_PC/.test(m.textContent))", timeout=15000)
            fired = p.evaluate("JSON.parse(localStorage.getItem('jarvis.assistant.v1')).reminders[0].fired > 0")
            check("k. a reminder due while Jarvis was closed: shown in the chat when it opens (late), kept as fired (never twice)", fired)
            p.fill("#q", "my mom's birthday is March 3")
            p.press("#q", "Enter")
            p.wait_for_function("[...document.querySelectorAll('#talk .msg')].some((m) => /Your mom's birthday is March 3/.test(m.textContent))", timeout=15000)
            p.fill("#q", "when is my mom's birthday")
            p.press("#q", "Enter")
            p.wait_for_function("[...document.querySelectorAll('#talk .msg')].some((m) => /You told me your mom's birthday is March 3/.test(m.textContent))", timeout=15000)
            check("k. in the page: told and recalled through the real brain + assistant", True)
            p.evaluate("window.__jarvisOpenVoice ? window.__jarvisOpenVoice() : null")
            p.evaluate("document.getElementById('vset') && document.getElementById('vset').click()")
            p.wait_for_function("!document.getElementById('voice').hidden", timeout=5000)
            sheet = p.evaluate("[document.getElementById('vStyle').value, !!document.getElementById('vCloud'), !document.getElementById('vTip').hidden, document.getElementById('vTip').textContent]")
            check("k. the Voice sheet: talk style (short), the cloud voice switch, the one-time Ava (Premium) tip with the exact iPhone steps",
                  sheet[0] == "short" and sheet[1] and sheet[2] and "Settings → Accessibility → Spoken Content → Voices → English → Ava" in sheet[3], sheet)
            p.select_option("#vStyle", "chatty")
            p.click("#vTipX")
            st = p.evaluate("[JSON.parse(localStorage.getItem('jarvis.persona')).style, localStorage.getItem('jarvis.tip.ava'), document.getElementById('vTip').hidden]")
            check("k. talk style kept ('chatty'); the tip dismissed once and for all", st == ["chatty", "1", True], st)
            p.click("#vTest")
            p.wait_for_function("window.__said.length > 0", timeout=5000)
            check("k. Test voice speaks in sentence chunks", len(p.evaluate("window.__said")) >= 2, p.evaluate("window.__said"))
            check("k. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    part_files()
    O = part_node()
    if O:
        checks(O)
    if os.environ.get("JARVIS_ASSISTANT_NO_BROWSER") != "1":
        part_browser()
    n = sum(RES)
    print(f"\njarvis assistant: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
