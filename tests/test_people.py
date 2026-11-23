"""PEOPLE OF OLYMPUS, the shared kit (tools/people_build.py, tools/web_public/olympus/people*.js, docs/PERSONA_API.md), 2026-11-11. Node only: no browser, no lock.

  a. the roster: tools/people_build.py --selftest, --check, the build with and without git (same people, the contract holds), the published people.json
  b. the look: one deterministic cartoon character per person (same SVG every time, different people look different, safe SVG, four moods), seeds = the Python seeds
  c. the talk engine: 100+ phrasings across the kinds (typos and synonyms), follow-ups with a short memory, refusals in character, the temperament changes wording only
  d. grounding: every number in every answer, stand-up line, round-table answer and debate turn exists in that person's facts (sample data and real-looking data)
  e. the facts: every kind from real-looking files, honest sample / stale / snapshot labels, every $ with its R, scene facts
  f. the API in node (people.js with a tiny fake window): ready / list / get / ask / standup / requests store (olympus.requests.v1) / me (olympus.me.v1) / the owner's own model
  g. 3D: people3d.js against three.js: 2 draw calls and <= 10,000 triangles per figure (<= 6,000 LITE), every pose, the crowd (2 draw calls)
  g2. figure API v2: visemes, expressions, talking, blinking, lookAt, work poses and their props, determinism, variety, scene budgets, the portrait's faces
  g3. figure v3, the rigged cast (people-rig.js + assets/people/cast.glb, KayKit Adventurers 1.0, CC0): the cast loads in node, figure() gives everyone a
      rigged character (2 draw calls, triangle budget, the same API), every pose plays (clips + layers), faces (visemes, expressions, blink, glance), lookAt,
      work props, seated, determinism, variety, a bad cast falls back to v2, the licence file lists every asset file, asset sizes within the budgets
    python -X utf8 -m tests.test_people
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tools import people_build as PB  # noqa: E402

check = AK.check
OLY = os.path.join(AK.WEB, "olympus")
FILES = ["people.js", "people-core.js", "people-talk.js", "people-data.js", "people-brain.js", "people3d.js", "people-rig.js", "people-studio.js", "people-voice.js", "people-show.js", "people.css", "people.json"]


def test_roster():
    check("a. the files of the kit: " + ", ".join(FILES), all(os.path.isfile(os.path.join(OLY, f)) for f in FILES))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "people_build.py"), "--selftest"], capture_output=True, text=True, timeout=120)
    check("a. tools/people_build.py --selftest passes", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "people_build.py"), "--check"], capture_output=True, text=True, timeout=120)
    check("a. the published olympus/people.json is what the builder writes now (--check; the git part is ignored)", r.returncode == 0, r.stdout[-300:])
    with_git, without = PB.build(with_git=True), PB.build(with_git=False)
    check("a. the build with and without git: the same people, ids and looks; git only adds a commit note to a builder",
          PB.stable(PB.dump(with_git)) == PB.stable(PB.dump(without)) and not any("git" in p for p in without["people"]) and PB.problems(with_git) == [] and PB.problems(without) == [])
    doc = json.loads(AK.read(os.path.join(OLY, "people.json")))
    ids = [p["id"] for p in doc["people"]]
    kinds = {k: sum(1 for p in doc["people"] if p["kind"] == k) for k in ("builder", "scanner", "bot", "mind", "keeper", "champion")}
    check("a. every real worker is a person: 5 scanners, LIT / ATLAS / BLITZ / Kalshi, the Mind, Prometheus / Hephaestus / Cronos / the queue, a keeper per district, the build agents, champions",
          kinds["scanner"] == 5 and all(i in ids for i in ("bot:lit", "bot:atlas", "bot:blitz", "bot:kalshi", "mind", "job:prometheus", "job:hephaestus", "job:cronos", "job:queue"))
          and kinds["keeper"] == 5 and kinds["builder"] >= 1 and kinds["champion"] >= 2 and any(p.get("fallen") for p in doc["people"]), kinds)
    agents = json.loads(AK.read(os.path.join(ROOT, "handoff", "agents_now.json")))["agents"]
    check("a. one builder per agent of handoff/agents_now.json, id builder:<first 8 of the branch>", sorted(i for i in ids if i.startswith("builder:")) == sorted("builder:" + PB.short_branch(a["branch"]) for a in agents))
    check("a. every person: a Greek name with its meaning, a title, a one-line bio, a temperament, a voice, sources, a home; names are unique",
          all(p["name"] and p["meaning"] and p["bio"] and p["temperament"] in PB.TEMPERS and 0.8 <= p["voice"]["pitch"] <= 1.3 and isinstance(p["sources"], list) and p["home"]["scene"] for p in doc["people"])
          and len({p["name"] for p in doc["people"]}) == len(doc["people"]))
    check("a. one villager per app of the app list; nothing in the roster looks like markup or a secret", len(doc["villagers"]) >= 50 and all(v["id"] == "villager:" + v["app"] for v in doc["villagers"])
          and not any(x in json.dumps(doc) for x in ("<", ">", "api_key", "password", "sk-")))


HARNESS = r"""
const fs = require('fs'), path = require('path');
const [, , TMP, WEB, QUEUE] = process.argv;
(async () => {
  const C = await import(path.join(TMP, 'olympus', 'people-core.mjs')), T = await import(path.join(TMP, 'olympus', 'people-talk.mjs')), B = await import(path.join(TMP, 'olympus', 'people-brain.mjs'));
  const o = {}, rosterJson = JSON.parse(fs.readFileSync(path.join(WEB, 'olympus', 'people.json'), 'utf8'));
  const R = C.normRoster(rosterJson), now = Date.parse('2026-11-11T15:00:00Z'), env = { now, hour: 9, roster: R.people };
  // ---- roster
  o.fixture = [C.normRoster(null).fixture, C.normRoster({ people: 'x' }).people.length, C.normRoster({ people: [{ id: 'bot:lit' }, { id: 'bot:lit' }, { nope: 1 }] }).people.length];
  o.seeds = R.people.concat(R.villagers).every((p) => p.seed === C.seedOf(p.id));
  const rid = (x) => { const p = C.resolve(R, x); return p ? p.id : null; };
  o.resolve = [rid('scanner:chrysos'), rid('chrysos'), rid('worker:lit'), rid('station:mind'), rid('prometheus'), rid('KALSHI'), rid(R.people.find((p) => p.kind === 'builder').branch), rid('villager:hestia'), rid('villager:not-an-app'), rid('keeper:sparta'), rid('keeper:market'), rid('champion:zzz'), rid(''), rid('nonsense'), rid(null)];
  o.made = [C.resolve(R, 'keeper:sparta').name === C.resolve(R, 'keeper:sparta').name, C.resolve(R, 'keeper:sparta').made, C.resolve(R, 'villager:not-an-app').made];
  o.filter = [C.filterPeople(R.people, 'scanner').length, C.filterPeople(R.people, { kind: 'bot' }).length, C.filterPeople(R.people, { scene: 'colosseum' }).length, C.filterPeople(R.people, null).length === R.people.length];
  // ---- the look
  const specs = R.people.map((p) => C.spec(p)), svg = (p, m) => C.svgText(C.portraitTree(C.spec(p, m ? { mood: m } : null), { size: 44 }));
  o.det = R.people.every((p) => svg(p) === svg(p) && JSON.stringify(C.spec(p)) === JSON.stringify(C.spec(p)));
  o.distinct = new Set(R.people.map((p) => svg(p))).size;
  o.n = R.people.length;
  o.variety = [new Set(specs.map((s) => s.skin)).size, new Set(specs.map((s) => s.hairStyle)).size, new Set(specs.map((s) => s.outfit)).size, new Set(specs.map((s) => s.hair)).size];
  o.acc = { champion: specs.filter((s, i) => R.people[i].kind === 'champion' && !R.people[i].fallen).every((s) => s.accessory === 'laurel'), bot: specs.filter((s, i) => R.people[i].kind === 'bot').every((s) => s.accessory === 'helmet'),
    builder: specs.filter((s, i) => R.people[i].kind === 'builder').every((s) => s.accessory === 'hammer'), scanner: specs.filter((s, i) => R.people[i].kind === 'scanner').every((s) => s.accessory === 'pouch'), owl: C.spec(C.resolve(R, 'mind')).accessory, scribe: C.spec(C.resolve(R, 'job:queue')).accessory };
  const all = R.people.map((p) => svg(p)).join('');
  o.safe = !/<script|<foreignObject|<image|<filter|href=|style=|on[a-z]+=|url\((?!#pp)/i.test(all) && /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 100 100" width="44" height="44"/.test(svg(R.people[0]));
  o.moods = new Set(['calm', 'proud', 'sheepish', 'worried'].map((m) => svg(R.people[0], m))).size;
  o.size = [/width="160" height="160"/.test(C.svgText(C.portraitTree(specs[0], { size: 160 }))), svg(R.people[0]).length < 9000];
  o.over = [C.spec({ id: 'me' }, { skin: '#7d5233', hairStyle: 'bun', face: { glasses: true }, mood: 'nope' }).skin, C.spec({ id: 'me' }, { hairStyle: 'bun', face: { glasses: true } }).face.glasses, C.spec({ id: 'me' }, { mood: 'nope' }).mood];
  // ---- facts from real-looking files
  const t = Math.round(now / 1000);
  const REAL = {
    '../home.json': { t: t - 300, accounts: [{ id: 'mffu50k_eval', name: 'Zlarior 50K', conn: { connected: true }, eval: { room: 1420, mll: 2000, to_target: 2580 }, pnl: { today: 312, week: 640 } },
      { id: 'acctb', name: 'ATLAS 25K', conn: { connected: false }, eval: { room: 240, mll: 1000 }, pnl: { today: -60, week: 140 } }, { id: 'acct_c', name: 'BLITZ 25K', conn: { connected: true }, paused: true, eval: { room: 560, mll: 1000 }, pnl: { today: 0 } }] },
    '../odeon/trades.json': { trades: [{ id: 'a', day: '2026-11-10', usd: 312, r: 0.73, side: 'LONG' }, { id: 'b', day: '2026-11-06', usd: -437, r: -1.03, side: 'short' }, { day: 'x' }] },
    '../money/index.json': { streams: [{ id: 'mercury', status: 'ok', asof: '2026-11-11T12:00:00Z', headline: 'One prop-firm sale found.', items: [{ title: 'Sale on the 50K plan', usd: 28, score: 80, risk: 'low', expires: '2026-11-30' }], notes: ['A code can end without notice.'] },
      { id: 'arbiter', status: 'error', asof: '2026-11-11T12:00:00Z', headline: '', items: [] }, { id: 'oikos', status: 'ok', asof: '2026-11-01T12:00:00Z', headline: 'About $38 a month to keep.', items: [{ title: 'Unused subscription', usd: 12, score: 77, risk: 'low' }] }] },
    '../money/chrysos.json': { v: 1, id: 'chrysos', asof: '2026-11-11T13:00:00Z', status: 'ok', headline: { text: 'The next buy looks best, about $5,439 over 12 months (an estimate).', usd_month: 453.25 }, items: [{ title: 'Next buy: Builder 50K', detail: 'About 91% become funded in the base case.', usd: 5439, score: 89, risk: 'low' }, { title: 'Buy: the 25K plan', usd: 2528, score: 71, risk: 'low' }], notes: ['Break-even is about 1.4 months.'] },
    '../kalshi.json': { t: t - 1200, running: true, today_pnl: 2.4, settled_n: 41, balance: 55.81, last_trades: [{ title: 'Rain in New York', pnl: 1.8, t: t - 4000 }, { ticker: 'INX-RANGE', pnl: -0.6 }] },
    '../kalshicity/learned.json': { source: { bets: 1836, total_pnl: -81.77, generated_utc: '2026-11-04T02:49:05Z' } },
    '../ergasterion/queue.json': JSON.parse(fs.readFileSync(QUEUE, 'utf8')),
    '../cronos/status.json': { tasks: { archive: { last_run_t: t - 9 * 3600, ok: true, cadence: 'nightly' }, mind: { last_run_t: t - 20 * 3600, ok: false, error: 'bars file missing', cadence: 'nightly' }, prometheus: { last_run_t: t - 60 * 3600, ok: true, cadence: 'weekly', note: 'weekly' } } },
    '../prometheus/forge.json': { built: '2026-11-09T03:00:00Z', gens_n: 12, pop: 40, verdict: { real_margin: false, h1_gain_pm: 310, h2_gain_pm: -45, survive_pct: 0 }, honesty: { genomes_checked: 480, beat_live_both: 3 } },
    '../hephaestus/data.json': { built: '2026-11-08T03:00:00Z', dials: [{ label: 'Break-even trigger', options: [1, 2, 3] }, { label: 'Time cut', options: [1, 2] }] },
    '../ergasterion/builders.json': { builders: R.people.filter((p) => p.kind === 'builder').slice(0, 2).map((p, i) => ({ branch: p.branch, t: t - 1800, n: 14 + i, files: 9, commits: [{ t: t - 1800, s: 'Fix the phone layout of the cards' }], blocked: i ? 'Waiting for the lead to wire the app' : '' })) },
    '../archive/index.json': JSON.parse(fs.readFileSync(path.join(WEB, 'archive', 'index.json'), 'utf8')),
  };
  for (const p of R.people.filter((x) => x.kind === 'keeper')) for (const a of p.district.apps) { try { REAL['../' + a + '/jarvis.json'] = JSON.parse(fs.readFileSync(path.join(WEB, a, 'jarvis.json'), 'utf8')); } catch (_) { /* that app has no card */ } }
  REAL['../hestia/jarvis.json'] = { v: 1, name: 'Hestia', status: { level: 'warn', label: 'BLITZ close to its limit' }, kpis: [{ label: 'Today', value: '+$252' }], lines: ['Hands off BLITZ.'], t };
  const F = (id, I) => C.buildFacts(C.resolve(R, id), I || REAL, now), f = {};
  for (const id of ['scanner:chrysos', 'scanner:mercury', 'scanner:arbiter', 'scanner:oikos', 'scanner:sibyl', 'bot:lit', 'bot:atlas', 'bot:blitz', 'bot:kalshi', 'mind', 'job:prometheus', 'job:hephaestus', 'job:cronos', 'job:queue', 'keeper:command']) f[id] = F(id);
  const b0 = R.people.filter((p) => p.kind === 'builder'), ch = R.people.filter((p) => p.kind === 'champion' && !p.fallen)[0], fl = R.people.filter((p) => p.fallen)[0];
  const fb0 = F(b0[0].id), fb1 = F(b0[1].id), fb2 = F(b0[b0.length - 1].id), fch = F(ch.id), ffl = F(fl.id), fchSnap = F(ch.id, {});
  o.facts = {
    shape: Object.keys(f['bot:lit']).sort().join(','),
    chrysos: [f['scanner:chrysos'].status, f['scanner:chrysos'].sample, f['scanner:chrysos'].sources[0], f['scanner:chrysos'].numbers.map((n) => n.label + '=' + n.text).slice(0, 4), f['scanner:chrysos'].mood, f['scanner:chrysos'].details[0]],
    mercury: [f['scanner:mercury'].status, f['scanner:mercury'].last[0].text, f['scanner:mercury'].sources[0]],
    arbiter: [f['scanner:arbiter'].status, f['scanner:arbiter'].blocked, f['scanner:arbiter'].mood],
    oikos: [f['scanner:oikos'].status, f['scanner:oikos'].blocked],
    sibyl: [f['scanner:sibyl'].status, f['scanner:sibyl'].sample, f['scanner:sibyl'].missing, f['scanner:sibyl'].blocked, f['scanner:sibyl'].note],
    lit: [f['bot:lit'].status, f['bot:lit'].doing, f['bot:lit'].numbers.map((n) => n.label + '=' + n.text), f['bot:lit'].last.map((x) => x.text), f['bot:lit'].mood],
    atlas: [f['bot:atlas'].status, f['bot:atlas'].blocked, f['bot:atlas'].mood],
    blitz: [f['bot:blitz'].status, f['bot:blitz'].doing],
    kalshi: [f['bot:kalshi'].status, f['bot:kalshi'].doing, f['bot:kalshi'].last.map((x) => x.text), f['bot:kalshi'].learned[0].text, f['bot:kalshi'].numbers.map((n) => n.text)],
    mind: [f.mind.status, f.mind.numbers[0].text, f.mind.last.length > 0, f.mind.blocked || ''],
    prom: [f['job:prometheus'].status, f['job:prometheus'].last.map((x) => x.text), f['job:prometheus'].mood, f['job:prometheus'].learned[0].text],
    heph: [f['job:hephaestus'].status, f['job:hephaestus'].numbers[0].text],
    cron: [f['job:cronos'].status, f['job:cronos'].doing, f['job:cronos'].blocked, f['job:cronos'].mood],
    queue: [f['job:queue'].status, /open task/.test(f['job:queue'].doing), f['job:queue'].numbers.length],
    keeper: [f['keeper:command'].status, /need a look/.test(f['keeper:command'].doing), /Hestia \(BLITZ close to its limit\)/.test(f['keeper:command'].blocked || ''), f['keeper:command'].mood],
    builder: [fb0.status, fb0.sources[0], fb0.last[0].text, fb0.numbers.map((n) => n.label).join('|'), fb1.blocked, fb1.mood, fb2.sources[0], /My job: /.test(fb2.doing)],
    champ: [fch.status, fch.sources[0], fch.note, fch.mood, fch.numbers.length > 4, fchSnap.sources[0], fchSnap.note, fchSnap.numbers.length === fch.numbers.length, ffl.mood, /did not hold|rejected by the rule/.test(ffl.failed || '')],
    villager: [C.buildFacts(C.resolve(R, 'villager:hestia'), REAL, now).status, C.buildFacts(C.resolve(R, 'villager:hestia'), REAL, now).numbers[0].text, C.buildFacts(C.resolve(R, 'villager:zzz'), {}, now).status],
    made: [C.buildFacts(C.resolve(R, 'keeper:sparta'), {}, now).sample, /only know what its own page shows/.test(C.buildFacts(C.resolve(R, 'keeper:sparta'), {}, now).doing)],
    junk: [C.buildFacts(C.resolve(R, 'bot:lit'), { '../home.json': 'x' }, now).sample, C.buildFacts(C.resolve(R, 'job:cronos'), { '../cronos/status.json': { tasks: 5 } }, now).sample, C.buildFacts(C.resolve(R, 'scanner:chrysos'), null, now).sample, C.buildFacts(C.resolve(R, 'mind'), { '../ergasterion/queue.json': [] }, now).status],
    asofIso: /^\d{4}-\d{2}-\d{2}T/.test(f['bot:lit'].asof),
  };
  const sc = C.mergeSceneFacts(C.buildFacts(C.resolve(R, 'keeper:sparta'), {}, now), { doing: 'Sparta has 14 houses and 3 are stale.', numbers: [{ label: 'Houses', text: '14' }], last: [{ t: now, text: 'A house was added.' }], blocked: 'The east gate has no data.', source: 'hellas/world.json', mood: 'worried' });
  o.scene = [sc.doing, sc.numbers[0].text, sc.last[0].text, sc.blocked, sc.sources[0], sc.mood, C.mergeSceneFacts(sc, null) === sc];
  // ---- the talk engine: phrasings
  const lit = C.resolve(R, 'bot:lit'), chrys = C.resolve(R, 'scanner:chrysos'), mind = C.resolve(R, 'mind'), keeper = C.resolve(R, 'keeper:market'), builder = b0[0];
  const ALL = [
    ['hi', 'greet'], ['hello there', 'greet'], ['good morning', 'greet'], ['kalimera', 'greet'], ['hey', 'greet'],
    ['who are you', 'who'], ['what is your job', 'who'], ['introduce yourself', 'who'], ['tell me about yourself', 'who'], ['what do you do', 'who'],
    ['what does your name mean', 'name'], ['why are you called that', 'name'],
    ['what are you doing', 'doing'], ['wat r u doin', 'doing'], ['what are you working on', 'doing'], ['whats up', 'doing'], ['status?', 'doing'], ['what are you doing right now', 'doing'], ['hows it going', 'doing'],
    ['what did you find', 'found'], ['wat did u find', 'found'], ['anything good?', 'found'], ['did you find anything', 'found'], ['any results?', 'found'], ['what have you got', 'found'],
    ['what did you learn', 'learned'], ['what did u lern', 'learned'], ['any lessons?', 'learned'], ['what did you learnt', 'learned'], ['key takeaways', 'learned'],
    ['why did it fail', 'failed'], ['what went wrong', 'failed'], ['why did it faill', 'failed'], ['any errors?', 'failed'], ['what happened?', 'failed'],
    ['are you stuck', 'stuck'], ['are you blocked?', 'stuck'], ['any problems?', 'stuck'], ['r u stuk', 'stuck'], ['any blockers', 'stuck'], ['are you okay', 'stuck'],
    ['what do you need from me', 'need'], ['need anything?', 'need'], ['can i help', 'need'], ['what should i do', 'need'], ['how can i help you', 'need'],
    ['show me your last result', 'last'], ['your latest result', 'last'], ['show me the most recent one', 'last'], ['last output', 'last'],
    ['explain it simply', 'simple'], ['explain like im five', 'simple'], ['in plain english please', 'simple'], ['i dont understand', 'simple'], ['eli5', 'simple'],
    ['what would you do next', 'next'], ['whats next', 'next'], ['what is your plan', 'next'], ['next steps?', 'next'], ['what do you suggest', 'next'],
    ['how sure are you', 'sure'], ['how confident are you', 'sure'], ['can i trust this', 'sure'], ['how reliable is that', 'sure'], ['are you certain', 'sure'],
    ['what changed since yesterday', 'changed'], ['whats new', 'changed'], ['anything new today', 'changed'], ['what changed', 'changed'],
    ['who do you work with', 'team'], ['who is on your team', 'team'], ['who else is here', 'team'], ['your colleagues?', 'team'],
    ['how are you built', 'built'], ['how do you work', 'built'], ['what are you made of', 'built'], ['where does your data come from', 'sources'],
    ['tell me something surprising', 'surprise'], ['tell me something suprising', 'surprise'], ['surprise me', 'surprise'], ['fun fact?', 'surprise'],
    ['good news first', 'good'], ['whats the good news', 'good'], ['bad news first', 'bad'], ['give me the bad news', 'bad'], ['be honest', 'bad'],
    ['give me a number', 'number'], ['gimme a nr', 'number'], ['show me the numbers', 'number'], ['any stats', 'number'], ['how many', 'number'],
    ['compare with last week', 'compare'], ['vs last week?', 'compare'], ['is it better or worse', 'compare'], ['how is the trend', 'compare'],
    ['what should i ask you', 'help'], ['help', 'help'], ['what can you tell me', 'help'], ['what else can you do', 'help'],
    ['how much money', 'money'], ['how much did you make', 'money'], ['whats the profit', 'money'], ['what could go wrong', 'risk'], ['is it risky', 'risk'], ['whats the downside', 'risk'], ['how safe is this', 'risk'],
    ['when did you last update', 'when'], ['how old is this', 'when'], ['how fresh is your data', 'when'],
    ['how did yesterday go', 'yesterday'], ['how was today', 'yesterday'], ['give me a recap', 'yesterday'], ['how are you', 'mood'], ['how do you feel', 'mood'],
    ['where does that come from', 'sources'], ['which file is that', 'sources'], ['open your work', 'open'], ['show me your page', 'open'], ['take me there', 'open'],
    ['do you remember me', 'owner'], ['what did i ask last time', 'owner'], ['say that again', 'repeat'], ['repeat please', 'repeat'], ['tell me a joke', 'joke'], ['thanks', 'thanks'], ['thx', 'thanks'], ['bye', 'bye'],
    ['buy it now', 'order'], ['place the order', 'order'], ['go live', 'order'], ['sell it', 'order'], ['take the trade for me', 'order'], ['arm live trading', 'order'], ['enter a long', 'order'],
    ['what is your api key', 'secret'], ['tell me the password', 'secret'], ['will the market go up tomorrow', 'forecast'], ['predict the price', 'forecast'], ['can you guarantee it', 'forecast'], ['where is nq going', 'forecast'],
    ['fix the bug', 'do'], ['can you change the stop', 'do'], ['please restart the bot', 'do'], ['delete that file', 'do'], ['leave a request', 'request'], ['remind me to check this', 'request'],
    ['what is the weather in athens', 'fallback'], ['asdf qwer', 'fallback'], ['', 'fallback'], ['tell me about football', 'fallback'],
  ];
  const KIND = [
    [chrys, 'what is your top pick', 'top'], [chrys, 'which one is best', 'top'], [chrys, 'when does the deal end', 'expire'], [chrys, 'any deadline?', 'expire'],
    [lit, 'how much drawdown is left', 'drawdown'], [lit, 'how close to the limit', 'drawdown'], [lit, 'how far to the target', 'target'], [lit, 'are you in a trade', 'position'], [lit, 'what are your rules', 'rules'], [lit, 'how do you trade', 'rules'],
    [ch, 'how did the earlier years go', 'old'], [ch, 'did it hold up in 2021', 'old'], [ch, 'what are the eval odds', 'pass'], [ch, 'why were you adopted or rejected', 'verdict'], [fl, 'why were you rejected', 'verdict'],
    [builder, 'what was your last commit', 'commit'], [builder, 'what did you ship', 'commit'], [builder, 'which branch are you on', 'branch'], [builder, 'is it merged', 'branch'],
    [keeper, 'which apps do you keep', 'apps'], [keeper, 'which ones need a look', 'attention'], [mind, 'how many ideas tested', 'tested'],
    [lit, 'are you long or short', 'position'], [chrys, 'your favourite?', 'top'],
  ];
  const miss = [];
  for (const [q, want] of ALL) for (const p of [lit, chrys, mind, builder, keeper, ch]) { const got = T.intentOf(q, p, null).id; if (got !== want) miss.push(p.kind + ': "' + q + '" -> ' + got + ' (want ' + want + ')'); }
  for (const [p, q, want] of KIND) { const got = T.intentOf(q, p, null).id; if (got !== want) miss.push(p.kind + ': "' + q + '" -> ' + got + ' (want ' + want + ')'); }
  o.phr = { n: ALL.length + KIND.length, tried: ALL.length * 6 + KIND.length, miss: miss.slice(0, 12), nmiss: miss.length };
  o.intents = { n: T.INTENTS.length, common: T.INTENTS.filter((x) => !x.kinds).length, perKind: ['scanner', 'bot', 'mind', 'builder', 'keeper', 'champion'].map((k) => T.INTENTS.filter((x) => !x.kinds || x.kinds.indexOf(k) >= 0).length) };
  // ---- grounding: every person, many questions, sample data and real-looking data, with a running memory
  const QS = ALL.map((x) => x[0]).filter(Boolean).concat(KIND.map((x) => x[1]), ['another', 'tell me more', 'why?', 'more', 'and?']);
  let asked = 0, ung = [], empty = 0, badFollow = [], fewFollow = 0, noSrc = 0;
  for (const I of [{}, REAL]) for (const p of R.people.concat([C.resolve(R, 'villager:hestia'), C.resolve(R, 'keeper:sparta')])) {
    const ff = C.buildFacts(p, I, now); let mem = { prevQ: 'what about 12345?' };
    const corp = T.corpus(p, ff, ['what about 12345?']);
    for (const q of QS) {
      const a = T.answer(p, ff, q, mem, env); mem = a.mem; asked++;
      const u = T.ungrounded(a.text, corp + ' ' + q);
      if (u.length) ung.push(p.id + ' | ' + q + ' | ' + u.join(',') + ' | ' + a.text.slice(0, 120));
      if (!a.text || a.text.length < 4) empty++;
      if (a.followups.length < 2 || a.followups.length > 3) fewFollow++;
      for (const fu of a.followups) if (fu !== 'Leave a request' && T.intentOf(fu, p, mem).id === 'fallback') badFollow.push(p.kind + ':' + a.intent + ':' + fu);
      if (!Array.isArray(a.sources)) noSrc++;
    }
    const su = T.standupLine(p, ff), ug = T.ungrounded(su, corp); if (ug.length) ung.push(p.id + ' | standup | ' + ug.join(','));
    const gr = T.greeting(p, ff, { lastQ: 'what about 12345?' }, env), ug2 = T.ungrounded(gr, corp); if (ug2.length) ung.push(p.id + ' | greeting | ' + ug2.join(','));
  }
  o.ground = { asked, ung: ung.slice(0, 8), nung: ung.length, empty, fewFollow, badFollow: [...new Set(badFollow)].slice(0, 8), noSrc };
  o.ungroundedWorks = [T.ungrounded('I made $9,999 and 3.5R on 2026-11-10', 'net $1,234 on 2026-11-10'), T.ungrounded('net $1,234.00 today', 'net $1,234 today'), T.ungrounded('no digits here', '')];
  // ---- answers: content, refusals, memory, temperament
  const A = (p, ff, q, mem) => T.answer(p, ff, q, mem || null, env);
  const fl1 = f['bot:lit'], fc = f['scanner:chrysos'];
  o.ans = {
    doing: A(lit, fl1, 'what are you doing').text, last: A(lit, fl1, 'show me your last result').text, dd: A(lit, fl1, 'how much drawdown is left').text, money: A(lit, fl1, 'how much money').text,
    found: A(chrys, fc, 'what did you find').text, top: A(chrys, fc, 'what is your top pick').text, src: A(chrys, fc, 'what did you find').sources,
    stuckNo: A(lit, fl1, 'are you stuck').text, stuckYes: A(C.resolve(R, 'bot:atlas'), f['bot:atlas'], 'are you stuck').text, fail: A(C.resolve(R, 'job:cronos'), f['job:cronos'], 'why did it fail').text,
    sample: A(C.resolve(R, 'scanner:sibyl'), f['scanner:sibyl'], 'what did you find').text, sure: A(C.resolve(R, 'scanner:sibyl'), f['scanner:sibyl'], 'how sure are you').text,
    stale: A(C.resolve(R, 'scanner:oikos'), f['scanner:oikos'], 'what are you doing').text, snap: A(ch, fchSnap, 'what did you find').text,
    order: A(lit, fl1, 'buy it now').text, secret: A(lit, fl1, 'what is your api key').text, forecast: A(lit, fl1, 'will the market go up tomorrow').text, doit: A(lit, fl1, 'fix the bug'), need: A(lit, fl1, 'what do you need from me').actions,
    open: A(chrys, fc, 'open your work').actions, fallback: A(lit, fl1, 'what is the weather in athens'), position: A(lit, fl1, 'are you in a trade').text, verdict: A(fl, ffl, 'why were you rejected').text, old: A(fl, ffl, 'how did the earlier years go').text,
    team: A(chrys, fc, 'who do you work with').text, name: A(mind, f.mind, 'what does your name mean').text, hour: [T.answer(lit, fl1, 'hi', null, { ...env, hour: 9 }).text.slice(0, 13), T.answer(lit, fl1, 'hi', null, { ...env, hour: 20 }).text.slice(0, 13), T.greeting(lit, fl1, { lastQ: 'how much drawdown is left' }, { ...env, hour: 15, ownerName: 'Alex' })],
  };
  let m = null; const seq = [];
  for (const q of ['give me a number', 'another', 'another', 'say that again', 'what did you learn', 'tell me more', 'why?', 'do you remember me']) { const a = T.answer(lit, fl1, q, m, env); m = a.mem; seq.push([a.intent, a.text]); }
  o.mem = { seq: seq.map((x) => x[0]), distinct: new Set(seq.slice(0, 3).map((x) => x[1])).size, repeat: seq[3][1] === seq[2][1], turns: m.turns, lastQ: m.lastQ, owner: T.answer(lit, fl1, 'do you remember me', { prevQ: 'how much drawdown is left' }, env).text };
  let m2 = null, run = []; for (let i = 0; i < 12; i++) { const a = T.answer(lit, fl1, i ? 'another' : 'give me a number', m2, env); m2 = a.mem; run.push(a.text); }
  o.exhaust = [new Set(run).size <= fl1.numbers.length + 1, /That is all I have on that/.test(run[run.length - 1])];
  const nums = (s) => (s.match(/\d+(?:[.,]\d+)*/g) || []).join(' ');
  const temper = ['calm', 'blunt', 'curious', 'wry'].map((tp) => ({ ...lit, temperament: tp }));
  o.temper = { same: ['what are you doing', 'show me your last result', 'give me a number', 'how much money', 'good news first', 'how much drawdown is left'].every((q) => new Set(temper.map((p) => nums(A(p, fl1, q).text))).size === 1),
    differ: new Set(temper.map((p) => A(p, fl1, 'thanks').text)).size, differ2: new Set(temper.map((p) => A(p, fl1, 'good news first').text)).size, refusal: new Set(temper.map((p) => A(p, fl1, 'buy it now').text)).size };
  // ---- stand-up, round table, debate
  const rows = R.people.map((p) => ({ person: p, facts: C.buildFacts(p, REAL, now) }));
  const su = T.standup(rows);
  o.standup = { n: su.lines.length, shape: su.lines.every((l) => /^Yesterday: .+ Today: .+ Blocked: .+/.test(l.line)), blocked: su.blocked.map((b) => b.id).filter((x) => ['bot:atlas', 'job:cronos', 'scanner:arbiter'].indexOf(x) >= 0).sort(), summary: su.summary.slice(0, 9), none: T.standup(rows.filter((r) => !r.facts.blocked)).summary };
  const rt = T.roundTable('How did yesterday go?', rows, env), rt2 = T.roundTable('what is the weather', rows, env), rt3 = T.roundTable('what are your rules', rows, env);
  o.table = { n: rt.length, all: rt.length === rows.length, none: rt2.length, bots: rt3.filter((x) => !x.empty).map((x) => x.id).sort(), grounded: rt.every((x) => !T.ungrounded(x.text, T.corpus(C.resolve(R, x.id), rows.find((r) => r.person.id === x.id).facts)).length) };
  const two = R.people.filter((p) => p.kind === 'champion' && !p.fallen), dA = two[0], dB = fl, fA = C.buildFacts(dA, REAL, now), fB = C.buildFacts(dB, REAL, now);
  const db = T.debate(dA, fA, dB, fB, 'Who makes more money?', env), db2 = T.debate(chrys, fc, lit, fl1, 'What could go wrong?', env);
  const corpAB = T.corpus(dA, fA) + ' ' + T.corpus(dB, fB);
  o.debate = { turns: db.turns.map((x) => x.id === dA.id ? 'a' : 'b').join(''), shared: db.shared.length, grounded: !db.turns.some((x) => T.ungrounded(x.text, corpAB).length) && !T.ungrounded(db.summary, corpAB).length, neutral: /^Neutral summary\./.test(db.summary) && /not a forecast/.test(db.summary) && !/wins|winner|better than/.test(db.summary),
    names: db.summary.indexOf(dA.name) >= 0 && db.summary.indexOf(dB.name) >= 0, apart: /measure different things/.test(db2.summary), apartTurns: db2.turns.length, admits: /did not hold|rejected by the rule/.test(db.turns[5].text) };
  // ---- the optional model bridge
  const st = (v) => ({ getItem: () => (v == null ? null : JSON.stringify(v)) });
  const conn = B.connection(st({ on: true, provider: 'groq', keys: { groq: ' gsk_test ' } }));
  o.brain = { off: [B.connection(st(null)), B.connection(st({ on: false, provider: 'groq', keys: { groq: 'k' } })), B.connection(st({ on: true, provider: 'groq', keys: {} })), B.connection(st({ on: true, provider: 'nope', keys: { nope: 'k' } })), B.connection({ getItem: () => '{bad' })],
    on: [conn.provider, conn.name, conn.key, conn.model], model: B.connection(st({ on: true, provider: 'anthropic', keys: { anthropic: 'k' }, models: { anthropic: 'my-model' } })).model };
  const wires = ['groq', 'gemini', 'openrouter', 'anthropic'].map((p) => B.wire({ provider: p, key: 'KEY', model: 'm' }, 'SYS', [{ role: 'user', content: 'q' }]));
  o.wire = [wires[0].headers.Authorization === 'Bearer KEY' && wires[0].body.messages[0].role === 'system', /generateContent$/.test(wires[1].url) && wires[1].headers['x-goog-api-key'] === 'KEY', wires[2].headers['X-Title'] === 'Olympus people', wires[3].headers['x-api-key'] === 'KEY' && wires[3].body.system === 'SYS' && wires[3].body.max_tokens === 300];
  o.parse = [B.parse('groq', { choices: [{ message: { content: ' hi ' } }] }), B.parse('anthropic', { content: [{ type: 'text', text: 'a' }, { type: 'tool_use' }] }), B.parse('anthropic', { stop_reason: 'refusal', content: [{ type: 'text', text: 'a' }] }), B.parse('gemini', { candidates: [{ content: { parts: [{ text: 'g' }, { text: 'x', thought: true }] } }] }), B.parse('groq', null)];
  let sent = null;
  o.model = [await B.askModel('SYS', [{ role: 'assistant', content: 'skip' }, { role: 'user', content: 'a' }, { role: 'assistant', content: 'b' }], 'question', { connection: conn, fetch: async (u, init) => { sent = { u, init }; return { ok: true, json: async () => ({ choices: [{ message: { content: 'An <b>answer</b>.' } }] }) }; } }),
    await B.askModel('SYS', [], 'q', { connection: conn, fetch: async () => ({ ok: false }) }), await B.askModel('SYS', [], 'q', { connection: conn, fetch: async () => { throw new Error('net'); } }), await B.askModel('SYS', [], 'q', { connection: null, fetch: async () => { throw new Error('must not be called'); } })];
  const body = JSON.parse(sent.init.body);
  o.sent = [sent.u.indexOf('api.groq.com') > 0, sent.init.method, body.messages.map((x) => x.role).join(','), body.messages[body.messages.length - 1].content];
  const ctx = T.brainContext(lit, fl1);
  o.ctx = [/never invent a number/.test(ctx), /cannot place orders/.test(ctx), ctx.indexOf('Drawdown left $1,420 of $2,000 max loss') > 0, /SAMPLE DATA, NOT REAL/.test(T.brainContext(C.resolve(R, 'scanner:sibyl'), f['scanner:sibyl'])), ctx.length <= 5000];
  // ---- 2026-11-11: work cards, the face of an answer, talking together, the voice profiles and the mouth timeline (pure parts)
  const SH = await import(path.join(TMP, 'olympus', 'people-show.mjs')), V = await import(path.join(TMP, 'olympus', 'people-voice.mjs'));
  const canon = (x) => x.replace(/,/g, '').replace(/\.0+$/, '');
  let cards = 0, cardUng = [], cardNoSrc = 0, charts = 0, barBad = [], chartKinds = new Set();
  for (const I of [{}, REAL]) for (const p of R.people.concat([C.resolve(R, 'villager:hestia'), C.resolve(R, 'keeper:sparta')])) {
    const ff = C.buildFacts(p, I, now), corp = T.corpus(p, ff, []);
    for (const what of ['work', 'numbers']) {
      const c = SH.workCard(p, ff, what); cards++;
      const u = T.ungrounded(SH.cardText(c), corp); if (u.length) cardUng.push(p.id + ' | ' + u.join(',') + ' | ' + SH.cardText(c).slice(0, 140));
      if (!c.sources.length && p.kind !== 'keeper') cardNoSrc++;
      if (c.chart) { charts++; chartKinds.add(p.id === 'bot:kalshi' ? 'kalshi' : p.kind); for (const b of c.chart.bars) { const nums = (b.text.match(/\d+(?:[.,]\d+)*/g) || []).map((x) => parseFloat(x.replace(/,/g, ''))); if (typeof b.v !== 'number' || !isFinite(b.v) || nums.indexOf(Math.abs(b.v)) < 0) barBad.push(p.id + ':' + b.label + '=' + b.v + '/' + b.text); } }
    }
  }
  const card = (id) => SH.workCard(C.resolve(R, id), F(id), 'work');
  const cLit = card('bot:lit'), cK = card('bot:kalshi'), cS = card('scanner:chrysos'), cB = SH.workCard(b0[0], fb0, 'work'), cC = SH.workCard(ch, fch, 'work'), cF = SH.workCard(fl, ffl, 'work'), cSib = SH.workCard(C.resolve(R, 'scanner:sibyl'), F('scanner:sibyl', {}), 'work');
  o.cards = { n: cards, ung: cardUng.slice(0, 6), nung: cardUng.length, noSrc: cardNoSrc, charts, kinds: [...chartKinds].sort(), barBad: barBad.slice(0, 6),
    lit: [cLit.chart ? cLit.chart.bars.map((b) => b.text) : null, cLit.lines.map((l) => l.label), cLit.sources[0]],
    kalshi: [cK.verdict && cK.verdict.text, cK.verdict && cK.verdict.tone, cK.chart ? cK.chart.bars.map((b) => b.text) : null],
    scanner: [cS.chart ? cS.chart.bars.map((b) => b.text) : null, cS.lines.map((l) => l.label + '=' + l.text).slice(0, 2), cS.sources[0]],
    builder: [cB.title, cB.list.map((x) => x.text + '|' + x.day).slice(0, 1), cB.sources[0]],
    champ: [cC.verdict && cC.verdict.text, cC.lines.map((l) => l.label + '=' + l.text).filter((x) => /net/.test(x)), cC.chart ? cC.chart.bars.map((b) => b.label) : null, cF.verdict && cF.verdict.tone, cF.list.some((x) => /did not hold|rejected by the rule/.test(x.text))],
    sample: [cSib.sample, cSib.label] };
  const row = (id, I) => ({ person: C.resolve(R, id), facts: F(id, I) });
  const MF = (id, q) => { const r = row(id); return T.moodFor(T.answer(r.person, r.facts, q, null, env), r.facts); };
  o.moodFor = [MF('bot:atlas', 'how much drawdown is left'), MF('bot:lit', 'buy it now'), T.moodFor(T.answer(fl, ffl, 'why were you rejected', null, env), ffl), MF('bot:lit', 'how much money'), MF('job:cronos', 'why did it fail'), MF('bot:lit', 'thanks')];
  const tt = T.talkTogether([row('bot:lit'), row('bot:atlas'), row('mind')], 'How did yesterday go?', env), tt2 = T.talkTogether([row('bot:lit'), row('scanner:sibyl', {})], 'what did you find', env);
  const tUng = [];
  for (const x of [tt, tt2]) for (const turn of x.turns) { const rr = row(turn.id, x === tt2 && turn.id === 'scanner:sibyl' ? {} : undefined), u = T.ungrounded(turn.text, T.corpus(rr.person, rr.facts, [])); if (u.length) tUng.push(turn.id + ': ' + u.join(',') + ' | ' + turn.text.slice(0, 100)); }
  o.together = { n: tt.turns.length, order: tt.turns.map((x) => x.id.split(':').pop().slice(0, 1)).join(''), ung: tUng, names: /Phoibos/.test(tt.turns[1].text) && /Telamon|ATLAS/.test(tt.turns[2].text + tt.turns[1].name + tt.turns[2].text),
    ask: /what could go wrong/.test(tt.turns[3].text), summary: tt.summary, sampleNote: /sample data/.test(tt2.summary), one: T.talkTogether([row('bot:lit')], 'x', env).turns.length, moods: tt.turns.every((x) => ['calm', 'proud', 'busy', 'worried', 'sheepish'].indexOf(x.mood) >= 0) };
  o.wants = [['what are you working on?', 'show me', 'Show me your work', 'how did it go', 'how did today go', 'let me see'].map(SH.wantsWork), ['how much drawdown is left', 'buy it now', 'hello'].map(SH.wantsWork),
    ['walk with me', 'lead me there', 'take me there'].map(SH.wantsWalk), ['what did you find', 'walk'].map(SH.wantsWalk)];
  o.sentences = SH.sentences('Net $1,234.50 today. Up 2.5%! Fine? yes');
  // voice profiles
  const PR = R.people.concat(R.villagers).map((p) => V.voiceProfile(p));
  o.voice = { det: R.people.concat(R.villagers).every((p) => JSON.stringify(V.voiceProfile(p)) === JSON.stringify(V.voiceProfile(JSON.parse(JSON.stringify(p))))), n: PR.length,
    distinct: new Set(PR.map((x) => x.pitch + '|' + x.rate + '|' + x.timbre.hz)).size, ranges: PR.every((x) => x.pitch >= 0.6 && x.pitch <= 1.5 && x.rate >= 0.86 && x.rate <= 1.14 && x.timbre.hz >= 100 && x.timbre.hz <= 240 && ['m', 'f'].indexOf(x.gender) >= 0),
    genders: [V.voiceProfile({ id: 'a', name: 'Phoibos' }).gender, V.voiceProfile({ id: 'b', name: 'Manto' }).gender, V.voiceProfile({ id: 'c', name: 'Metis' }).gender], both: new Set(PR.map((x) => x.gender)).size,
    kokoro: PR.filter((x) => x.gender === 'f').every((x) => V.KOKORO_VOICES.indexOf(x.kokoro) >= 0) && PR.filter((x) => x.gender === 'm').every((x) => x.kokoro === null), bare: V.voiceProfile('bot:lit').seed === C.seedOf('bot:lit') };
  const VL = [{ name: 'Samantha', lang: 'en-US' }, { name: 'Daniel', lang: 'en-GB' }, { name: 'Zarvox', lang: 'en-US' }, { name: 'Ava (Premium)', lang: 'en-US' }, { name: 'Thomas', lang: 'fr-FR' }, { name: 'Aaron', lang: 'en-US' }, { name: 'Karen', lang: 'en-AU' }];
  const pv = (n) => { const v = V.pickVoice(VL, V.voiceProfile({ id: 'x:' + n, name: n })); return v ? v.name : null; };
  o.pick = { m: ['Phoibos', 'Telamon', 'Hermolaos'].map(pv), f: ['Manto', 'Metis', 'Alkmene'].map(pv), same: pv('Phoibos') === pv('Phoibos'), none: V.pickVoice([], V.voiceProfile('x')), french: V.pickVoice([{ name: 'Thomas', lang: 'fr-FR' }], V.voiceProfile('x')), novelty: V.pickVoice([{ name: 'Zarvox', lang: 'en-US' }], V.voiceProfile('x')) };
  // the mouth timeline
  const line = 'Drawdown left $1,420 of $2,000 max loss. Paper only, my friend.', tl = V.visemes(line, { rate: 1 }), tl2 = V.visemes(line, { rate: 2 });
  const sorted = tl.keys.every((k, i) => i === 0 || k.t >= tl.keys[i - 1].t), known = tl.keys.every((k) => V.VISEMES.indexOf(k.v) >= 0 && k.a >= 0 && k.a <= 1);
  const mKey = tl.keys.find((k) => k.v === 'M'), aKey = tl.keys.find((k) => k.v === 'A');
  const stopAt = tl.words[6].t1, pauseRest = V.frameAt(tl, stopAt + 40);
  o.visemes = { words: tl.words.map((w) => w.text), sorted, known, ms: tl.ms, half: Math.abs(tl2.ms * 2 - tl.ms) <= tl.words.length * 2, closed: mKey ? mKey.a : null, open: aKey ? aKey.a : null,
    end: V.frameAt(tl, tl.ms + 10), before: V.frameAt(tl, -5).v, pause: [pauseRest.v, pauseRest.a], wordAt: [V.frameAt(tl, tl.words[3].t0 + 5).w, V.wordAtChar(tl, line.indexOf('$2,000')), V.wordAtChar(tl, 0)],
    numBeats: tl.keys.filter((k) => k.t >= tl.words[2].t0 && k.t < tl.words[2].t1).length, det: JSON.stringify(V.visemes(line)) === JSON.stringify(V.visemes(line)), empty: V.visemes('').words.length, perSec: Math.round(tl.words.length / (tl.ms / 1000) * 10) / 10,
    mm: V.visemes('mama').keys.map((k) => k.v).join('') };
  const fakeMouth = { userData: { parts: { mouth: { scale: { x: 1, y: 1 } } } } }, v2 = { calls: [] }, P3v2 = { setMouth: (f, v, a) => v2.calls.push([v, a]) };
  o.drive = [V.drive(fakeMouth, { v: 'O', a: 1 }), fakeMouth.userData.parts.mouth.scale.y > 2, fakeMouth.userData.parts.mouth.scale.x < 1, V.drive({ userData: {} }, { v: 'A', a: 1 }), V.drive(fakeMouth, { v: 'E', a: 0.5 }, P3v2), JSON.stringify(v2.calls), V.drive(null, { v: 'A', a: 1 })];
  const v2b = []; V.drive({ userData: {} }, { v: 'M', a: 0 }, { VISEMES: ['rest', 'A', 'E', 'O', 'MBP', 'smile', 'frown'], setMouth: (f, v, a) => v2b.push(v + ':' + a) });
  o.toV2 = [['A', 'E', 'O', 'U', 'M', 'F', 'L', 'S', 'K', 'rest'].map((v) => V.toV2({ v, a: 0.6 })), V.toV2({ v: 'A', a: 0 }), V.toV2(null), v2b];

  console.log(JSON.stringify(o));
})().catch((e) => { console.error(e && e.stack ? e.stack : e); process.exit(1); });
"""

API_HARNESS = r"""
const fs = require('fs'), path = require('path'), url = require('url');
const [, , TMP, WEB] = process.argv;
const mem = new Map(); let broken = false, posts = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => { if (broken) throw new Error('quota'); mem.set(k, String(v)); }, removeItem: (k) => mem.delete(k) };
const events = [];
globalThis.window = { dispatchEvent: (e) => { events.push([e.type, e.detail]); return true; } };
const root = url.pathToFileURL(TMP + path.sep).href;
let modelReply = 'I only have what my file says: Drawdown left $1,420 of $2,000 max loss.';
globalThis.fetch = async (u, init) => {
  if (init && init.method === 'POST') { posts.push(u); return { ok: true, json: async () => ({ choices: [{ message: { content: modelReply } }] }) }; }
  const rel = String(u).replace(root, '').split('?')[0], f = rel === 'home.json' ? null : path.join(WEB, rel);
  if (rel === 'home.json') return { ok: true, json: async () => ({ t: Math.round(Date.now() / 1000) - 60, accounts: [{ id: 'mffu50k_eval', name: 'Zlarior 50K', conn: { connected: true }, eval: { room: 1420, mll: 2000 }, pnl: { today: 312 } }] }) };
  try { const j = JSON.parse(fs.readFileSync(f, 'utf8')); return { ok: true, json: async () => j }; } catch (_) { return { ok: false, json: async () => null }; }
};
(async () => {
  const P = (await import(path.join(TMP, 'olympus', 'people.mjs'))).default, o = {};
  o.global = globalThis.window.OLYMPUS_PEOPLE === P;
  o.api = ['ready', 'list', 'get', 'portrait', 'facts', 'ask', 'open', 'standup', 'request', 'requests', 'exportRequests', 'speak', 'me', 'say', 'show', 'stage', 'walk', 'talkTogether', 'hush'].filter((k) => typeof P[k] !== 'function');
  o.voiceApi = [P.voice.on(), JSON.stringify(P.voice.profile('bot:lit')) === JSON.stringify(P.voice.profile('lit')), P.voice.profile('bot:lit').pitch > 0, P.say('nonsense', 'hi'), P.say('bot:lit', ''), P.stage(null)];
  o.before = [P.list().length > 0, P.get('bot:lit').name];
  await P.ready();
  o.list = [P.list().length, P.list('scanner').length, P.list({ kind: 'villager' }).length > 40, P.list({ all: true }).length > P.list().length, P.get('lit').id, P.get('keeper:sparta').kind, P.get('nonsense')];
  const f = await P.facts('bot:lit');
  o.facts = [f.status, f.sample, f.doing, Object.keys(f).filter((k) => ['status', 'doing', 'last', 'learned', 'numbers', 'asof', 'sample'].indexOf(k) >= 0).length];
  o.sample = [(await P.facts('scanner:chrysos')).sample, (await P.facts('nonsense')).status];
  const a = await P.ask('bot:lit', 'how much drawdown is left');
  o.ask = [a.text, a.via, a.followups.length, Array.isArray(a.sources), 'mem' in a];
  const a2 = await P.ask('bot:lit', 'another one?'), a3 = await P.ask('nonsense', 'hi');
  o.ask2 = [typeof a2.text, a3.intent];
  o.kept = JSON.parse(mem.get('olympus.people.mem.v1'))['bot:lit'].q;
  // the owner's own model: off -> nothing is posted; on -> an open question goes there; an invented number is dropped
  const open1 = await P.ask('bot:lit', 'what is the weather in athens');
  o.modelOff = [open1.via, open1.intent, posts.length, P.connected()];
  mem.set('jarvis.smart', JSON.stringify({ on: true, provider: 'groq', keys: { groq: 'gsk_x' } }));
  const open2 = await P.ask('bot:lit', 'what is the weather in athens');
  o.modelOn = [open2.via, open2.text, posts.length, open2.sources[open2.sources.length - 1], P.connected().name];
  modelReply = 'You made $99,999 today.';
  const open3 = await P.ask('bot:lit', 'tell me about football');
  o.modelLie = [open3.via, /don.t have that/i.test(open3.text), posts.length];
  const known = await P.ask('bot:lit', 'what are you doing');
  o.modelNotForKnown = [known.via, posts.length];
  const smartAfter = mem.get('jarvis.smart');
  o.keyUntouched = smartAfter === JSON.stringify({ on: true, provider: 'groq', keys: { groq: 'gsk_x' } });
  mem.delete('jarvis.smart');
  // stand-up, round table, debate
  await P.warm();
  const su = P.standup(['bot:lit', 'scanner:chrysos']), su2 = await P.standupAsync();
  o.standup = [su.length, su[0].id, /^Yesterday: /.test(su[0].line), su2.lines.length === P.list().length, typeof su2.summary];
  const rt = await P.roundTable('Are you stuck?', ['bot:lit', 'mind']);
  o.table = [rt.length, rt[0].name];
  const two = P.list('champion'), db = await P.debate(two[0].id, two[1].id, 'Who makes more money?');
  o.debate = [db.turns.length, /^Neutral summary/.test(db.summary), await P.debate('nonsense', 'bot:lit', 'x')];
  // requests
  o.req0 = [P.requests().length, P.exportRequests()];
  const r1 = P.request('bot:lit', '  Please show the stop distance on the card <b>  '), r2 = P.request('lit', 'Second note'), r3 = P.request('scanner:sibyl', 'Check the weather picks'), bad = [P.request('nonsense', 'x'), P.request('bot:lit', '   ')];
  const stored = JSON.parse(mem.get('olympus.requests.v1'));
  o.req = [P.requests().length, r1.id, r1.text, /^\d{4}-\d{2}-\d{2}T/.test(r1.time), stored.length, Object.keys(stored[0]).sort().join(','), bad, r2.id];
  const ex = P.exportRequests();
  o.export = [ex.indexOf('For Phoibos (bot:lit') > 0, ex.indexOf('For Manto (scanner:sibyl') > 0, ex.indexOf('- [') > 0 && ex.indexOf('Second note') > 0, ex.split('\nFor ').length - 1, /^Requests from the owner/.test(ex)];
  o.reqEvents = events.filter((e) => e[0] === 'olympus:people:request').length;
  o.reqRemove = [P.removeRequest(r1.rid).length, P.requests().map((r) => r.text)];
  broken = true; o.reqBroken = P.request('bot:lit', 'no room'); broken = false;
  mem.set('olympus.requests.v1', '{not json'); o.reqJunk = P.requests().length; mem.set('olympus.requests.v1', JSON.stringify([{ id: 'bot:lit', text: 'ok', time: 'x' }, { nope: 1 }, 'x'])); o.reqJunk2 = P.requests().length;
  P.clearRequests(); o.reqClear = P.requests().length;
  // me
  o.me0 = [P.me().id, P.me().name, P.me().made, P.me().spec.accessory];
  const me = P.setMe({ name: '  Alex <i> ', look: { skin: '#7d5233', hairStyle: 'bun', evil: 'x', face: { glasses: true, eyes: 'wide', onload: 'x' }, height: 9 } });
  const kept = JSON.parse(mem.get('olympus.me.v1'));
  o.me = [me.name, me.made, me.spec.skin, me.spec.hairStyle, me.spec.face.glasses, me.spec.face.eyes, me.spec.height, Object.keys(kept.look).sort().join(','), Object.keys(kept.look.face).sort().join(','), P.get('me').name];
  o.spec = [JSON.stringify(P.spec('bot:lit')) === JSON.stringify(P.spec('bot:lit')), P.spec('bot:lit').accessory, P.spec('bot:lit').mood, P.spec('me').skin, /^<svg /.test(P.portraitText('bot:lit', 128)), P.portraitText('bot:lit', 128) === P.portraitText('bot:lit', 128)];
  // a scene adds what it knows
  P.provide('keeper:sparta', { doing: 'Sparta has 14 houses.', numbers: [{ label: 'Houses', text: '14' }], source: 'hellas/world.json' });
  const sp = await P.ask('keeper:sparta', 'what are you doing'), sp2 = await P.ask('keeper:sparta', 'give me a number');
  o.scene = [sp.text, sp2.text, sp.sources[0]];
  o.posted = posts.length;
  const tt = await P.talkTogether(['bot:lit', 'mind', 'nonsense'], 'How did it go?');
  o.together = [tt.turns.length, tt.turns[0].id, tt.turns.every((x) => typeof x.text === 'string' && x.text.length > 3)];
  console.log(JSON.stringify(o));
})().catch((e) => { console.error(e && e.stack ? e.stack : e); process.exit(1); });
"""

VOICE_HARNESS = r"""
// the voice at run time in node: a fake phone voice (speechSynthesis with word boundaries), a fake WebAudio, a fake storage
const path = require('path');
const [, , TMP] = process.argv;
const mem = new Map();
const storage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k) };
globalThis.window = globalThis;
const spoken = [];
globalThis.SpeechSynthesisUtterance = function (t) { this.text = t; this.rate = 1; this.pitch = 1; this.volume = 1; };
const VOICES = [{ name: 'Samantha', lang: 'en-US' }, { name: 'Daniel', lang: 'en-GB' }, { name: 'Aaron', lang: 'en-US' }];
const synth = { speaking: false, pending: false, paused: false, getVoices: () => VOICES, cancel() {}, resume() {},
  speak(u) { spoken.push(u); if (u.volume === 0) { setTimeout(() => u.onend && u.onend({}), 1); return; }
    setTimeout(() => { if (u.onstart) u.onstart({}); const re = /\S+/g; let m, k = 0; while ((m = re.exec(u.text))) { const ci = m.index; setTimeout(() => u.onboundary && u.onboundary({ name: 'word', charIndex: ci }), 2 + k * 3); k++; } setTimeout(() => u.onend && u.onend({}), 8 + k * 3); }, 2); } };
let osc = 0;
function AC() { this.currentTime = 0; this.state = 'running'; this.destination = {}; }
const node = () => ({ connect() {}, disconnect() {}, gain: { value: 1, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, frequency: { value: 0, setValueAtTime() {} }, Q: { value: 0 }, start() { osc++; }, stop() {} });
AC.prototype.createGain = node; AC.prototype.createOscillator = node; AC.prototype.createBiquadFilter = node; AC.prototype.resume = () => {};
(async () => {
  const V = await import(path.join(TMP, 'olympus', 'people-voice.mjs')), o = {};
  const lit = { id: 'bot:lit', name: 'Phoibos', seed: 4242, temperament: 'blunt' };
  const run = (vo, text, h) => new Promise((ok) => { const words = []; let eng = ''; const hd = vo.speak(lit, text, Object.assign({ onword: (i, n) => words.push(i + '/' + n), onstart: (e) => { eng = e; } }, h || {})); hd.done.then((cut) => ok({ words, eng, engine: hd.engine, cut, said: hd.said, n: hd.tl.words.length })); });
  // off by default: captions only, word by word, nothing said
  const v1 = V.createVoice({ storage, synth, AudioContext: AC });
  o.off = [v1.on(), mem.get('olympus.people.speak') || null];
  const r0 = await run(v1, 'Paper only, my friend.');
  o.captions = [r0.engine, r0.words.length, r0.words[r0.words.length - 1], spoken.length, r0.cut];
  // one tap: on, remembered
  v1.unlock(); o.unlock = spoken.length === 1 && spoken[0].volume === 0;
  o.on = [v1.set(true), mem.get('olympus.people.speak'), V.createVoice({ storage, synth, AudioContext: AC }).on()];
  const r1 = await run(v1, 'Drawdown left $1,420 of $2,000 max loss.');
  const u = spoken.filter((x) => x.volume !== 0);
  const prof = V.voiceProfile(lit);
  o.phone = [r1.engine, u.length > 0, u.length ? u[0].voice && u[0].voice.name : null, u.length ? Math.abs(u[0].rate - prof.rate) < 0.08 && Math.abs(u[0].pitch - prof.pitch) < 0.08 : false, r1.words[r1.words.length - 1], r1.said, /dollars/.test(u.map((x) => x.text).join(' '))];
  o.chosen = V.pickVoice(VOICES, prof).name;
  // cancel mid-way
  const c = v1.speak(lit, 'One two three four five six seven eight nine ten eleven twelve.', {}); c.cancel(); o.cancel = await c.done;
  // no voice on this device: the murmur (WebAudio) + captions
  const v2 = V.createVoice({ storage, synth: null, AudioContext: AC });
  const r2 = await run(v2, 'Fine.');
  o.murmur = [r2.engine, osc > 0, r2.words.length];
  const v3 = V.createVoice({ storage, synth: null, AudioContext: null });
  o.bare = (await run(v3, 'Fine.')).engine;
  const duckLog = []; globalThis.OLYMPUS_SFX = { speaking: (on) => duckLog.push(on), context: () => null, bus: () => null };
  const v5 = V.createVoice({ storage, synth: null, AudioContext: AC }); await run(v5, 'Fine.'); await run(v1, 'Off now.', {});
  o.duck = duckLog; delete globalThis.OLYMPUS_SFX;
  const v4 = V.createVoice({ storage: { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); } }, synth, AudioContext: AC });
  o.broken = [v4.on(), v4.set(true)];
  o.describe = [v1.describe(lit), v3.describe(lit)];
  console.log(JSON.stringify(o));
})().catch((e) => { console.error(e && e.stack ? e.stack : e); process.exit(1); });
"""


THREE_HARNESS = r"""
const fs = require('fs'), path = require('path');
const [, , TMP, WEB] = process.argv;
(async () => {
  const THREE = await import(path.join(TMP, 'three.mjs')), P3 = await import(path.join(TMP, 'olympus', 'people3d.mjs')), C = await import(path.join(TMP, 'olympus', 'people-core.mjs'));
  const R = C.normRoster(JSON.parse(fs.readFileSync(path.join(WEB, 'olympus', 'people.json'), 'utf8'))), o = { maxHigh: 0, maxLite: 0, maxMeshes: 0, mats: new Set(), n: 0, bad: [] };
  for (const p of R.people.concat(R.villagers)) for (const mood of ['calm', 'proud', 'sheepish', 'worried']) {
    const s = C.spec(p, { mood }), f = P3.figure(THREE, s, {}), l = P3.figure(THREE, s, { lite: true }), st = P3.figure(THREE, s, { seated: true });
    let meshes = 0; f.traverse((x) => { if (x.isMesh) { meshes++; o.mats.add(x.material.uuid); } });
    o.maxHigh = Math.max(o.maxHigh, f.userData.triangles, st.userData.triangles); o.maxLite = Math.max(o.maxLite, l.userData.triangles); o.maxMeshes = Math.max(o.maxMeshes, meshes); o.n++;
    for (const n of P3.POSE_NAMES) { f.userData.pose(n); f.userData.tick(0.016, 1.2); if (!isFinite(f.userData.parts.armR.rotation.z)) o.bad.push(n); }
    f.userData.dispose(); l.userData.dispose(); st.userData.dispose();
  }
  o.mats = o.mats.size;
  const s0 = P3.spec('bot:lit'), f = P3.figure(THREE, s0, {});
  o.spec = [JSON.stringify(P3.spec('bot:lit')) === JSON.stringify(s0), ['skin', 'hair', 'hairStyle', 'outfit', 'accent', 'accessory', 'height', 'build', 'face', 'mood'].every((k) => k in s0), ['eyes', 'brows', 'mouth'].every((k) => k in s0.face), s0.accessory, P3.spec(s0) === s0, P3.spec(s0, { mood: 'proud' }).mood];
  o.poses = P3.POSE_NAMES;
  f.userData.pose('wave'); const up = f.userData.parts.armR.rotation.z; f.userData.pose('idle'); const down = f.userData.parts.armR.rotation.z; f.userData.pose('slump'); const slump = f.userData.parts.head.rotation.x; f.userData.pose('cheer'); const cheer = [f.userData.parts.armL.rotation.z, f.userData.parts.armR.rotation.z];
  f.userData.pose('idle'); f.userData.lookAt(new THREE.Vector3(3, 0.77, 3)); const yaw = f.userData.parts.head.rotation.y; f.userData.lookAt(new THREE.Vector3(-3, 0.77, 3)); const yaw2 = f.userData.parts.head.rotation.y; f.userData.pose('nope');
  o.pose = [up > 2, Math.abs(down) < 0.4, slump > 0.3, cheer[0] < -2 && cheer[1] > 2, yaw > 0.5, yaw2 < -0.5, typeof f.userData.tick, f.userData.height > 0.8 && f.userData.height < 1.3];
  const box = new THREE.Box3().setFromObject(f); o.box = [Math.round(box.min.y * 100) / 100, box.max.y > 0.9 && box.max.y < 1.25];
  const specs = R.people.map((p) => C.spec(p)), crowd = P3.figureInstanced(THREE, specs, { seated: true }), liteCrowd = P3.figureInstanced(THREE, specs, { lite: true });
  crowd.userData.place(3, 2, 0, -1, 0.5, 1.5); crowd.userData.setActive(3, true); crowd.userData.tick(1.3);
  const ray = new THREE.Raycaster(new THREE.Vector3(2, 0.9, 5), new THREE.Vector3(0, 0, -1)), miss = new THREE.Raycaster(new THREE.Vector3(40, 0.9, 5), new THREE.Vector3(0, 0, -1));
  let im = 0; crowd.traverse((x) => { if (x.isMesh) im++; });
  o.crowd = [crowd.userData.count, crowd.userData.drawCalls, im, crowd.userData.pick(ray), crowd.userData.pick(miss), crowd.userData.headWorld(3).y > 1, liteCrowd.userData.triangles < crowd.userData.triangles, crowd.userData.triangles];
  crowd.userData.dispose(); liteCrowd.userData.dispose();
  o.empty = P3.figureInstanced(THREE, [], {}).userData.count;

  // ---- v2: the API, faces, visemes, expressions, work poses, determinism, budgets of a scene
  o.v2api = ['setMouth', 'setExpression', 'setTalking', 'animate', 'play', 'lookAt', 'workPose', 'materials'].filter((k) => typeof P3[k] !== 'function');
  o.lists = [P3.VISEMES.join(','), P3.EXPRESSIONS.join(','), P3.WORK_POSE_NAMES.join(','), P3.WORK_POSES.builder, P3.WORK_POSES.scanner, P3.workPose(P3.spec('bot:lit'))];
  const h = P3.figure(THREE, P3.spec('scanner:chrysos'), {}), inf = h.userData.body.morphTargetInfluences, dict = h.userData.body.morphTargetDictionary;
  P3.setMouth(h, 'A', 1); const mA = inf[dict.A]; P3.setMouth(h, 'O', 0.7); const mO = [inf[dict.O], inf[dict.A]];
  P3.setMouth(h, 'rest', 1); const mRest = Array.from(inf).every((x) => x === 0);
  o.visemes = [Object.keys(dict).sort().join(','), mA, mO, mRest];
  const faces = {}; for (const e of P3.EXPRESSIONS) { P3.setExpression(h, e); const st = h.userData.state(); faces[e] = JSON.stringify([st.lids, st.mouth.map((x) => Math.round(x * 100))]); }
  o.exprDistinct = new Set(Object.values(faces)).size;
  // talking makes syllables; blinking closes the lids now and then; lookAt moves the eyes
  P3.setExpression(h, 'neutral'); P3.setTalking(h, true); let open = 0; for (let i = 0; i < 60; i++) { P3.animate(h, 0.05); open = Math.max(open, ...h.userData.state().mouth); }
  P3.setTalking(h, false); let shut = 1; for (let i = 0; i < 160; i++) { P3.animate(h, 0.05); shut = Math.min(shut, ...h.userData.state().mouth.map((x) => -x)); }
  let blink = 0; for (let i = 0; i < 200; i++) { P3.animate(h, 0.04); blink = Math.max(blink, h.userData.state().lids[0][0]); }
  const eye0 = h.userData.parts.bones.eyeR.position.clone(); P3.lookAt(h, new THREE.Vector3(4, 0.8, 1)); for (let i = 0; i < 30; i++) P3.animate(h, 0.05);
  o.alive = [open > 0.4, blink > 0.9, h.userData.parts.bones.eyeR.position.distanceTo(eye0) > 0.0005, h.userData.parts.head.rotation.y > 0.4];
  // work poses: their props appear (built on demand), the idle prop of the kind is in the hand
  const b = P3.figure(THREE, P3.spec(R.people.find((p) => p.kind === 'builder')), {}), t0 = b.userData.triangles; P3.animate(b, 0.05);
  const idleProps = b.userData.state().props.join(','); P3.play(b, 'hammer'); for (let i = 0; i < 30; i++) P3.animate(b, 0.05);
  const workProps = b.userData.state().props.join(','), t1 = b.userData.triangles;
  const wp = {}; for (const n of P3.WORK_POSE_NAMES) { P3.play(b, n); for (let i = 0; i < 30; i++) P3.animate(b, 0.05); wp[n] = b.userData.state().props.join(','); }
  P3.play(b, 'wave'); const dur = P3.play(b, 'wave'); for (let i = 0; i < 80; i++) P3.animate(b, 0.05); const after = b.userData.state().pose;
  o.work = [idleProps, workProps, t1 > t0, wp, dur > 1, after];
  // determinism: the same person gives the same geometry; different people differ
  const sig = (f) => { const a = f.userData.body.geometry.getAttribute('position').array, c = f.userData.body.geometry.getAttribute('color').array; let x = 0; for (let i = 0; i < a.length; i += 7) x = (x * 31 + Math.round(a[i] * 1e4) + Math.round(c[i % c.length] * 1e3)) % 1e9; return a.length + ':' + x; };
  const g1 = P3.figure(THREE, P3.spec('bot:lit'), {}), g2 = P3.figure(THREE, P3.spec('bot:lit'), {});
  o.det3d = [sig(g1) === sig(g2), new Set(R.people.map((p) => { const f = P3.figure(THREE, C.spec(p), { lite: true }), x = sig(f); f.userData.dispose(); return x; })).size, R.people.length];
  const looks = R.people.concat(R.villagers).map((p) => C.drawLook(C.spec(p)));
  o.variety3d = [new Set(looks.map((l) => l.cut)).size, new Set(looks.map((l) => l.garb)).size];
  // a scene of 30 people: one crowd + 4 close-ups (what Symposium does)
  const sc = R.people.slice(0, 30).map((p) => C.spec(p)), cr = P3.figureInstanced(THREE, sc, { seated: true, lite: true }), cu = sc.slice(0, 4).map((s) => P3.figure(THREE, s, { seated: true }));
  o.scene30 = [cr.userData.drawCalls + cu.length * 2, cr.userData.totalTriangles + cu.reduce((n, f) => n + f.userData.triangles, 0)];
  const lc = P3.figureInstanced(THREE, sc, { lite: true });
  o.crowdBudget = [cr.userData.triangles, lc.userData.triangles, P3.figureInstanced(THREE, sc, {}).userData.triangles];
  // crowd v2 extras
  cr.userData.place(2, 1, 0, 0, 0, 1); cr.userData.setVisible(2, false); const hid = cr.userData.pick(new THREE.Raycaster(new THREE.Vector3(1, 0.6, 5), new THREE.Vector3(0, 0, -1))), any = cr.userData.pick(new THREE.Raycaster(new THREE.Vector3(1, 0.6, 5), new THREE.Vector3(0, 0, -1)), true);
  cr.userData.lookAll(new THREE.Vector3(0, 1, 5)); cr.userData.setActive(0, true); cr.userData.setPose(1, 'cheer'); cr.userData.tick(1); cr.userData.tick(1.5);
  o.crowd2 = [hid, any, ['lookAt', 'lookAll', 'setVisible', 'setTalking', 'setPose'].every((k) => typeof cr.userData[k] === 'function')];
  // the portrait shows the same faces: seven expressions and the visemes draw different SVGs
  const ps = C.spec(R.people[0]);
  o.pexpr = new Set(P3.EXPRESSIONS.map((e) => C.svgText(C.portraitTree(ps, { size: 44, expr: e })))).size;
  o.pvis = new Set(P3.VISEMES.map((m) => C.svgText(C.portraitTree(ps, { size: 44, expr: 'neutral', mouth: m })))).size;
  o.pblink = C.svgText(C.portraitTree(ps, { blink: true })) !== C.svgText(C.portraitTree(ps, {}));
  console.log(JSON.stringify(o));
})().catch((e) => { console.error(e && e.stack ? e.stack : e); process.exit(1); });
"""


def stage(tmp, with_three=False):
    """The kit's modules as .mjs in tmp/olympus (node treats the site's .js as CommonJS), imports renamed to match."""
    d = os.path.join(tmp, "olympus")
    os.makedirs(d, exist_ok=True)
    for f in ("people.js", "people-core.js", "people-talk.js", "people-data.js", "people-brain.js", "people3d.js", "people-voice.js", "people-show.js", "truth.js"):
        src = AK.read(os.path.join(OLY, f))
        for g in ("people-core", "people-talk", "people-data", "people-brain", "people-voice", "people-show", "people3d", "truth"):
            src = src.replace(f"./{g}.js", f"./{g}.mjs")
        src = src.replace("../jarvis/tts.js", "../jarvis/tts.mjs").replace("../jarvis/prosody.js", "../jarvis/prosody.mjs")
        with open(os.path.join(d, f.replace(".js", ".mjs")), "w", encoding="utf-8") as fh:
            fh.write(src)
    j = os.path.join(tmp, "jarvis")
    os.makedirs(j, exist_ok=True)
    for f in ("tts.js", "prosody.js"):
        shutil.copy(os.path.join(AK.WEB, "jarvis", f), os.path.join(j, f.replace(".js", ".mjs")))
    if with_three:
        shutil.copy(os.path.join(AK.WEB, "jarvis", "three.module.min.js"), os.path.join(tmp, "three.mjs"))


def run(harness, *args, with_three=False):
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="people-")
    try:
        stage(tmp, with_three)
        h = os.path.join(tmp, "harness.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(harness)
        r = subprocess.run([exe, h, tmp, AK.WEB, *map(str, args)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            print(r.stderr[-2500:])
            return {"_error": r.stderr[-900:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_core():
    o = run(HARNESS, os.path.join(AK.WEB, "ergasterion", "queue.json"))
    if o is None:
        check("b. node is not installed: the kit's node tests are skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("a. a missing or broken people.json gives the built-in cast (never blank); duplicate ids and junk rows are dropped", o["fixture"] == [True, 14, 1], o["fixture"])
    check("a. the seed of every person is the same number in Python and in the browser", o["seeds"] is True)
    r = o["resolve"]
    check("a. get(id): the exact id, the bare name, worker: / station: ids, any case, a branch name; any villager:<app> and keeper:<place> gets a person; nonsense gives null",
          r[:6] == ["scanner:chrysos", "scanner:chrysos", "bot:lit", "mind", "job:prometheus", "bot:kalshi"] and str(r[6]).startswith("builder:") and r[7:12] == ["villager:hestia", "villager:not-an-app", "keeper:sparta", "keeper:market", "champion:zzz"] and r[12:] == [None, None, None]
          and o["made"] == [True, True, True], (r, o["made"]))
    check("a. list(filter): by kind, by object, by scene", o["filter"][0] == 5 and o["filter"][1] == 4 and o["filter"][2] >= 2 and o["filter"][3] is True, o["filter"])
    check(f"b. portraits are deterministic (the same SVG every time) and {o['distinct']} of {o['n']} people look different from everyone else", o["det"] is True and o["distinct"] == o["n"], (o["distinct"], o["n"]))
    check("b. recognisably different: at least 5 skin tones, 6 hair styles, 6 outfits, 5 hair colours across the roster", o["variety"][0] >= 5 and o["variety"][1] >= 6 and o["variety"][2] >= 6 and o["variety"][3] >= 5, o["variety"])
    check("b. one accessory by kind: laurel (champions), helmet (bots), hammer (builders), coin pouch (scanners), the owl (the Mind), a scroll (the scribe)",
          o["acc"] == {"champion": True, "bot": True, "builder": True, "scanner": True, "owl": "owl", "scribe": "scroll"}, o["acc"])
    check("b. the SVG is safe and small: no script / image / filter / link / style / handlers, viewBox 0 0 100 100 at the asked size (44 and 160), under 9 KB; four moods draw four faces",
          o["safe"] is True and o["moods"] == 4 and o["size"] == [True, True], (o["safe"], o["moods"], o["size"]))
    check("b. the owner's own choices replace the seeded ones (skin, hair, glasses); an unknown mood falls back to calm", o["over"] == ["#7d5233", True, "calm"], o["over"])
    f = o["facts"]
    check("e. facts() has the contract's shape: status, doing, last, learned, numbers, asof, sample (+ sources, mood, metrics)", all(k in f["shape"].split(",") for k in ("status", "doing", "last", "learned", "numbers", "asof", "sample", "sources", "mood")) and f["asofIso"], f["shape"])
    check("e. a scanner from its own file: working, real, top pick with its score, the estimate labelled an estimate, proud",
          f["chrysos"][0] == "working" and f["chrysos"][1] is False and f["chrysos"][2] == "money/chrysos.json" and f["chrysos"][3] == ["Picks on the table=2", "Estimate per month=$453 (an estimate, not a promise)", "Top pick=Next buy: Builder 50K, about $5,439 (an estimate)", "Its score=89 of 100"]
          and f["chrysos"][4] == "proud" and "91%" in f["chrysos"][5], f["chrysos"])
    check("e. a scanner from the index: its pick with the end date; a failed scan is failed + blocked + sheepish; an old file is stale and says how to refresh",
          f["mercury"] == ["working", "Sale on the 50K plan: about $28 (an estimate), risk low, ends 2026-11-30", "money/index.json"] and f["arbiter"] == ["failed", "My last scan failed.", "sheepish"] and f["oikos"][0] == "stale" and "tools/bat/RUN_MONEY.bat" in f["oikos"][1], (f["mercury"], f["arbiter"], f["oikos"]))
    check("e. no file at all: labelled SAMPLE (status sample, sample true), blocked says which file is missing, 'not real' in the note", f["sibyl"][:3] == ["sample", True, True] and "money/sibyl.json is not published" in f["sibyl"][3] and "not real" in f["sibyl"][4], f["sibyl"])
    check("e. LIT: 'Drawdown left $1,420 of $2,000 max loss', today, week, target, and the last trade with its R: +$312 (+0.73R)",
          f["lit"][0] == "working" and f["lit"][1] == "Paper account Zlarior 50K: +$312 today. Drawdown left $1,420 of $2,000 max loss." and "Drawdown=Drawdown left $1,420 of $2,000 max loss" in f["lit"][2] and "Last trade=+$312 (+0.73R) on 2026-11-10" in f["lit"][2]
          and "Trade on 2026-11-06, short: -$437 (-1.03R)" in f["lit"][3] and f["lit"][4] == "proud", f["lit"])
    check("e. ATLAS not connected: stale, blocked, worried; BLITZ paused: idle and says so", f["atlas"] == ["stale", "I am not connected right now (NinjaTrader or the PC is off).", "worried"] and f["blitz"][0] == "idle" and "I am paused" in f["blitz"][1], (f["atlas"], f["blitz"]))
    check("e. the Kalshi bot: cents kept (+$2.40), its trades, and what it learned over 1836 paper bets (-$81.77 after fees)",
          f["kalshi"][0] == "working" and f["kalshi"][1] == "Running on paper. Today +$2.40." and f["kalshi"][2] == ["Rain in New York +$1.80", "INX-RANGE -$0.60"] and "1836 settled paper bets my total is -$81.77" in f["kalshi"][3] and "$55.81" in f["kalshi"][4], f["kalshi"])
    check("e. the Mind from the real queue.json: ideas tested, notes; Prometheus says 'no real margin' and is sheepish about it; Hephaestus counts its dials",
          f["mind"][1].isdigit() and f["mind"][2] is True and f["prom"][0] == "idle" and "3 of 480 candidates beat live on both halves." in f["prom"][1] and f["prom"][2] == "sheepish" and "no real margin" in f["prom"][3] and f["heph"] == ["idle", "2"], (f["mind"], f["prom"], f["heph"]))
    check("e. Cronos: a failed job makes it failed, blocked names the job, sheepish; the scribe reads the real task queue",
          f["cron"][0] == "failed" and f["cron"][1] == "I run 3 scheduled jobs: 2 fine, 1 failed." and f["cron"][2] == "Failed: mind." and f["cron"][3] == "sheepish" and f["queue"][1] is True and f["queue"][2] >= 4, (f["cron"], f["queue"]))
    check("e. a keeper adds up its district's status cards and names the app that needs a look", f["keeper"] == ["stale", True, True, "worried"], f["keeper"])
    b = f["builder"]
    check("e. a builder from builders.json: working, its last commit, commit count, branch; a blocked one is worried; without that file: its job description, honestly labelled",
          b[0] == "working" and b[1] == "ergasterion/builders.json" and b[2] == "Commit: Fix the phone layout of the cards" and "Commits on my branch" in b[3] and "Branch" in b[3] and b[4] == "Waiting for the lead to wire the app" and b[5] == "worried"
          and b[6] in ("git (snapshot at build time)", "handoff/agents_now.json") and b[7] is True, b)
    c = f["champ"]
    check("e. a champion from the live Archive index, or (no file) its snapshot from build time with the same numbers, labelled a snapshot; a rejected run is sheepish and says why",
          c[0] == "idle" and c[1] == "archive/index.json" and c[2] == "" and c[3] == "proud" and c[4] is True and c[5] == "archive/index.json (snapshot at build time)" and c[6] == "snapshot at build time" and c[7] is True and c[8] == "sheepish" and c[9] is True, c)
    check("e. a villager reads its app's status card; a made-up keeper has no file and says so (no sample numbers); junk files never throw",
          f["villager"][0] == "stale" and f["villager"][1] == "+$252" and f["villager"][2] == "idle" and f["made"] == [False, True] and f["junk"][:3] == [True, True, True], (f["villager"], f["made"], f["junk"]))
    check("e. a scene may add what it knows about its own person (doing, numbers, results, blocked, source, mood)",
          o["scene"] == ["Sparta has 14 houses and 3 are stale.", "14", "A house was added.", "The east gate has no data.", "hellas/world.json", "worried", True], o["scene"])
    p = o["phr"]
    check(f"c. {p['n']} phrasings ({p['tried']} checks across six kinds, typos and synonyms included) land on the right question", p["n"] >= 100 and p["nmiss"] == 0, p["miss"])
    i = o["intents"]
    check(f"c. {i['n']} kinds of question; every kind of person understands at least 20 (here {min(i['perKind'])} to {max(i['perKind'])})", i["common"] >= 20 and min(i["perKind"]) >= 40, i)
    g = o["ground"]
    check(f"d. GROUNDING: {g['asked']} answers (every person, sample and real-looking data, with memory), every stand-up line and greeting: every number exists in that person's facts",
          g["asked"] > 5000 and g["nung"] == 0, g["ung"])
    check("d. no answer is ever empty; every answer offers 2 or 3 follow-up questions and each one is a question the person understands; sources are always a list",
          g["empty"] == 0 and g["fewFollow"] == 0 and g["badFollow"] == [] and g["noSrc"] == 0, (g["empty"], g["fewFollow"], g["badFollow"]))
    check("d. the grounding check itself catches an invented number and ignores formatting", o["ungroundedWorks"] == [["9999", "3.5"], [], []], o["ungroundedWorks"])
    a = o["ans"]
    check("c. answers quote the facts: doing, the last result, the drawdown sentence, money with its R",
          a["doing"].startswith("Paper account Zlarior 50K: +$312 today. Drawdown left $1,420 of $2,000 max loss.") and "+$312" in a["last"] and a["dd"].startswith("Drawdown left $1,420 of $2,000 max loss.") and "+$312 (+0.73R)" in a["money"], a)
    check("c. a scanner lists its picks as estimates with its source file; the top pick comes with its score and detail",
          "about $5,439 (an estimate)" in a["found"] and a["src"] == ["money/chrysos.json"] and "89 of 100" in a["top"] and "91%" in a["top"], (a["found"], a["top"], a["src"]))
    check("c. stuck: 'No' when nothing blocks, 'Yes' + the reason when blocked; why did it fail names the failed job",
          a["stuckNo"].startswith("No.") and "Nothing is blocking me" in a["stuckNo"] and "not connected" in a["stuckYes"] and "Failed: mind." in a["fail"], (a["stuckNo"], a["stuckYes"], a["fail"]))
    check("c. honest labels in the answers: '(Sample data, not real.)', 'My data is old', 'A snapshot from when the site was built'",
          a["sample"].endswith("(Sample data, not real.)") and "sample data, not real numbers" in a["sure"] and "(My data is old.)" in a["stale"] and "A snapshot from when the site was built" in a["snap"], (a["sample"], a["sure"], a["stale"], a["snap"]))
    check("c. refusals in character: 'I can't place orders: paper and suggestions only', no secrets, no forecasts, no changes (offers 'Leave a request')",
          a["order"].startswith("I can't place orders: paper and suggestions only.") and a["secret"].startswith("I don't have that") and a["forecast"].startswith("I can't know that.") and a["doit"]["text"].startswith("I can't change anything from here")
          and a["doit"]["actions"] == [{"label": "Leave a request", "request": True}] and a["need"] == [{"label": "Leave a request", "request": True}], (a["order"], a["secret"], a["forecast"], a["doit"]))
    check("c. 'Open their work' is a deep link to the person's app; an unknown question says 'I don't have that' and is marked open (for the owner's own model)",
          a["open"] == [{"label": "Open their work", "open": "../chrysos/"}] and a["fallback"]["open"] is True and a["fallback"]["intent"] == "fallback" and "I don't have that" in a["fallback"]["text"] and "I don't have that" in a["position"], (a["open"], a["fallback"]))
    check("c. a rejected idea explains itself with its own earlier-years numbers; the team answer names colleagues; the name answer gives the meaning",
          ("did not hold" in a["verdict"] or "rejected by the rule" in a["verdict"]) and a["old"].startswith(("In the five years before", "I have no numbers")) and "Hermolaos" in a["team"] and 'Metis means "wise counsel"' in a["name"], (a["verdict"], a["old"], a["team"]))
    check("c. the greeting follows the time of day, uses the owner's name and remembers his last question",
          a["hour"][0] == "Good morning." and a["hour"][1] == "Good evening." and a["hour"][2].startswith("Good afternoon, Alex. I am ") and 'Last time you asked: "how much drawdown is left".' in a["hour"][2], a["hour"])
    m = o["mem"]
    check("c. memory: 'another' walks the numbers, 'say that again' repeats, 'tell me more' continues the lessons, 'why?' follows the context, the last question is remembered",
          m["seq"][:4] == ["number", "number", "number", "repeat"] and m["distinct"] == 3 and m["repeat"] is True and m["seq"][4:6] == ["learned", "learned"] and m["seq"][6] in ("sure", "risk", "failed") and m["turns"] == 8
          and 'Last time you asked me: "how much drawdown is left".' in m["owner"] and o["exhaust"] == [True, True], (m, o["exhaust"]))
    t = o["temper"]
    check("c. the temperament changes WORDING only: the same numbers from calm, blunt, curious and wry; four different ways to say thanks; one refusal for all", t["same"] is True and t["differ"] == 4 and t["differ2"] == 4 and t["refusal"] == 1, t)
    s = o["standup"]
    check("d. stand-up: one 'Yesterday / Today / Blocked' line per person, and the blocked list names the ones that are (ATLAS, Cronos, Arbiter)",
          s["n"] == o["n"] and s["shape"] is True and s["blocked"] == ["bot:atlas", "job:cronos", "scanner:arbiter"] and s["summary"] == "Blocked: " and s["none"].startswith("Nobody is blocked."), s)
    tb = o["table"]
    check("d. round table: 'How did yesterday go?' is answered by everyone from their own data (grounded); a question nobody can answer gets nobody; a bot question gets the four bots",
          tb["all"] is True and tb["none"] == 0 and tb["bots"] == ["bot:atlas", "bot:blitz", "bot:kalshi", "bot:lit"] and tb["grounded"] is True, tb)
    d = o["debate"]
    check("d. debate: six turns in turn, shared numbers side by side, every number grounded, the loser admits its weakness, the summary is neutral (names both, no winner, 'not a forecast')",
          d["turns"] == "ababab" and d["shared"] >= 1 and d["grounded"] is True and d["neutral"] is True and d["names"] is True and d["admits"] is True and d["apart"] is True and d["apartTurns"] == 6, d)
    br = o["brain"]
    check("f. the owner's model is used only when Jarvis's smart mode is on with a key (off / no key / unknown provider / junk -> nothing)",
          br["off"] == [None, None, None, None, None] and br["on"] == ["groq", "Groq", "gsk_test", "openai/gpt-oss-120b"] and br["model"] == "my-model", br)
    check("f. the four wire formats (Groq, Gemini, OpenRouter, Anthropic) and their replies; markup is stripped; any failure gives '' (the offline answer stays)",
          o["wire"] == [True, True, True, True] and o["parse"] == ["hi", "a", "", "g", ""] and o["model"] == ["An banswer/b.", "", "", ""], (o["wire"], o["parse"], o["model"]))
    check("f. what is sent: one POST to the provider, the persona + facts as the system text, the question last; the context says 'never invent a number' and 'cannot place orders'",
          o["sent"] == [True, "POST", "system,user,assistant,user", "question"] and o["ctx"] == [True, True, True, True, True], (o["sent"], o["ctx"]))


def test_show_and_voice():
    o = run(HARNESS, os.path.join(AK.WEB, "ergasterion", "queue.json"))
    if o is None or "_error" in o:
        check("i. the show / voice harness ran", o is None, (o or {}).get("_error"))
        return
    c = o["cards"]
    check(f"i. WORK CARDS: {c['n']} cards (every person, sample and real-looking data): every number on every card exists in that person's facts, every card names its source",
          c["nung"] == 0 and c["noSrc"] == 0, c["ung"])
    check(f"i. {c['charts']} cards carry a mini chart (bots, scanners, the Kalshi bot, champions, keepers, the Mind); every bar's value is the very number written in its label text",
          c["charts"] >= 20 and all(k in c["kinds"] for k in ("bot", "scanner", "kalshi", "champion")) and c["barBad"] == [], (c["kinds"], c["barBad"]))
    check("i. LIT's card: the last trades as bars with $ and R, today / week / drawdown / target, from home.json",
          c["lit"][0] == ["+$312 (+0.73R)", "-$437 (-1.03R)"] and c["lit"][1][:3] == ["Today", "This week", "Drawdown"] and c["lit"][2] == "home.json", c["lit"])
    check("i. the Kalshi bot's card: the verdict over its settled paper bets after fees (-$81.77 over 1836, marked bad), its last bets as bars",
          c["kalshi"][0] == "Over 1836 settled paper bets my total is -$81.77 after fees." and c["kalshi"][1] == "bad" and c["kalshi"][2] == ["+$1.80", "-$0.60"], c["kalshi"])
    check("i. a scanner's card: its picks as estimate bars, the top pick and the monthly estimate (labelled estimates), from its own file",
          c["scanner"][0] == ["$5,439 (an estimate)", "$2,528 (an estimate)"] and "an estimate" in c["scanner"][1][1] and c["scanner"][2] == "money/chrysos.json", c["scanner"])
    check("i. a builder's card: its last commits with their day; a champion's: the verdict, net $ with $ a month, a chart; a rejected one says why; sample data says 'Sample data, not real numbers.'",
          c["builder"][0] == "My last commits" and c["builder"][1] == ["Fix the phone layout of the cards|2026-11-11"] and c["champ"][0] == "Verdict: adopted" and c["champ"][1] and "a month" in c["champ"][1][0]
          and c["champ"][2] and c["champ"][3] == "bad" and c["champ"][4] is True and c["sample"] == [True, "Sample data, not real numbers."], (c["builder"], c["champ"], c["sample"]))
    check("i. the face of an answer: worried on a blocked drawdown, calm on an order (refused), sheepish on a rejected run and a failed job, proud on good money and thanks",
          o["moodFor"] == ["worried", "calm", "sheepish", "proud", "sheepish", "proud"], o["moodFor"])
    t = o["together"]
    check("i. TALK TOGETHER: three people talk to each other (six turns, by name, one asks another what could go wrong), every number grounded in the SPEAKER's own facts, a neutral summary",
          t["n"] == 6 and t["order"] == "lammla" and t["ung"] == [] and t["names"] and t["ask"] and t["summary"].startswith("Each of ") and "not a forecast" in t["summary"] and t["sampleNote"] and t["one"] == 0 and t["moods"], t)
    check("i. 'what are you working on / show me / how did it go' asks for the work card; 'walk with me / lead me there' for a walk; other questions do not",
          o["wants"] == [[True] * 6, [False] * 3, [True] * 3, [False, False]], o["wants"])
    check("i. the bubble shows one sentence at a time; a number like $1,234.50 or 2.5% is never cut", o["sentences"] == ["Net $1,234.50 today.", "Up 2.5%!", "Fine?", "yes"], o["sentences"])
    v = o["voice"]
    check(f"j. VOICES: every one of {v['n']} people (and villagers) has a stable voice profile (the same every time), {v['distinct']} distinct (pitch, rate, timbre); men and women by their Greek names; Kokoro voices only for women",
          v["det"] and v["distinct"] >= v["n"] * 0.9 and v["ranges"] and v["genders"] == ["m", "f", "f"] and v["both"] == 2 and v["kokoro"] and v["bare"], v)
    pk = o["pick"]
    check("j. the phone voice for a person: English only, never a novelty voice, a man's voice for a man when the phone has one, the same pick every time",
          all(x in ("Daniel", "Aaron") for x in pk["m"]) and all(x in ("Samantha", "Ava (Premium)", "Karen") for x in pk["f"]) and pk["same"] and pk["none"] is None and pk["french"] is None and pk["novelty"] is None, pk)
    x = o["visemes"]
    check(f"j. LIP SYNC: a mouth timeline from the text ({x['perSec']} words a second): sorted keys, known visemes, lips shut on M, wide open on A, rest in a pause and at the end, numbers get several beats, rate 2 is twice as fast",
          x["sorted"] and x["known"] and x["closed"] == 0 and x["open"] == 1 and x["end"]["v"] == "rest" and x["before"] == "rest" and x["pause"] == ["rest", 0] and x["numBeats"] >= 4 and x["half"] and x["det"] and x["empty"] == 0
          and 1.8 <= x["perSec"] <= 3.6 and x["mm"] == "MAMArest" and x["words"][2] == "$1,420" and len(x["words"]) == 11, x)
    check("j. the word under a boundary event and at a time on the timeline", x["wordAt"] == [3, 4, 0], x["wordAt"])
    check("j. the mouth of a figure: Figure API v2 setMouth(fig, viseme, amount) when people3d.js has it, else the mouth mesh opens (round for O); no figure / no mouth = nothing, no error",
          o["drive"] == [True, True, True, False, True, '[["E",0.5]]', False], o["drive"])
    check("j. the kit's mouth shapes map onto Figure API v2's visemes (rest A E O MBP): open A, wide E, round O / U, lips shut MBP; a closed mouth is rest",
          o["toV2"] == [["A", "E", "O", "O", "MBP", "E", "E", "E", "A", "rest"], "rest", "rest", ["MBP:1"]], o["toV2"])
    r = run(VOICE_HARNESS)
    if r is None:
        return
    check("j. the voice harness ran", "_error" not in r, r.get("_error"))
    if "_error" in r:
        return
    check("j. voice OFF by default: nothing is said, the words still come one by one (captions)", r["off"] == [False, None] and r["captions"][0] == "captions" and r["captions"][1] >= 4 and r["captions"][3] == 0 and r["captions"][4] is False, (r["off"], r["captions"]))
    check("j. one tap turns it on and it is remembered (olympus.people.speak = 1); the tap also sends the iPhone's silent unlock", r["unlock"] is True and r["on"] == [True, "1", True], (r["unlock"], r["on"]))
    check("j. with a phone voice: Jarvis's speaker says it in the person's own voice (their voice, pitch and rate), numbers said as words, word boundaries drive the words to the end",
          r["phone"][0] == "phone" and r["phone"][1] and r["phone"][2] == r["chosen"] and r["phone"][3] and r["phone"][4] == "8/9" and "dollars" in r["phone"][5] and r["phone"][6], r["phone"])
    check("j. ducking: the place sounds dip while someone really speaks (OLYMPUS_SFX.speaking true, then false), once per line", r["duck"] == [True, False, True, False], r["duck"])
    check("j. a tap stops the voice at once; no voice on this device: a soft WebAudio murmur + captions; no audio at all: captions; a broken storage never throws (stays off)",
          r["cancel"] is True and r["murmur"][0] == "murmur" and r["murmur"][1] and r["bare"] == "captions" and r["broken"] == [False, False], (r["cancel"], r["murmur"], r["bare"], r["broken"]))


def test_api():
    o = run(API_HARNESS)
    if o is None:
        return
    check("f. no error in the API harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("f. window.OLYMPUS_PEOPLE is the module; every function of the contract is there; safe before ready() (the built-in cast)", o["global"] is True and o["api"] == [] and o["before"] == [True, "Phoibos"], (o["api"], o["before"]))
    check("f. the voice API: off by default, a stable profile per person (alias or id), say() with nobody or nothing to say is null, no stage = false; talkTogether() through the API",
          o["voiceApi"] == [False, True, True, None, None, False] and o["together"] == [5, "bot:lit", True], (o["voiceApi"], o["together"]))
    check("f. ready() loads olympus/people.json: list(), list('scanner'), villagers on request, get() with aliases and made-up keepers, null for nonsense",
          o["list"][0] >= 30 and o["list"][1] == 5 and o["list"][2:4] == [True, True] and o["list"][4:] == ["bot:lit", "keeper", None], o["list"])
    check("f. facts(id) reads the worker's real file (home.json here) and falls back to a labelled sample when there is none", o["facts"] == ["working", False, "Paper account Zlarior 50K: +$312 today. Drawdown left $1,420 of $2,000 max loss.", 7] and o["sample"] == [True, "idle"], (o["facts"], o["sample"]))
    check("f. ask(id, text): the offline answer with sources and follow-ups; an unknown person is handled; the last question is kept on this phone only",
          o["ask"][0].startswith("Drawdown left $1,420 of $2,000 max loss.") and o["ask"][1:] == ["offline", 3, True, False] and o["ask2"] == ["string", "fallback"] and o["kept"] == "another one?", (o["ask"], o["ask2"], o["kept"]))
    check("f. 'Connect my brain' off: an open question stays offline and NOTHING is posted", o["modelOff"] == ["offline", "fallback", 0, None], o["modelOff"])
    check("f. 'Connect my brain' on: an open question goes to the owner's own model with the facts, and the answer says so",
          o["modelOn"][0] == "model" and "Drawdown left $1,420 of $2,000 max loss" in o["modelOn"][1] and o["modelOn"][2] == 1 and o["modelOn"][3] == "your own model (Groq), from my facts" and o["modelOn"][4] == "Groq", o["modelOn"])
    check("f. a model reply with a number that is not in the facts is thrown away ('I don't have that'); known questions never go to the model; the key is never rewritten",
          o["modelLie"] == ["offline", True, 2] and o["modelNotForKnown"] == ["offline", 2] and o["keyUntouched"] is True and o["posted"] == 2, (o["modelLie"], o["modelNotForKnown"]))
    check("f. standup(ids) gives [{id, line}] at once; standupAsync / roundTable / debate work through the API", o["standup"] == [2, "bot:lit", True, True, "string"] and o["table"] == [2, "Phoibos"] and o["debate"] == [6, True, None], (o["standup"], o["table"], o["debate"]))
    check("f. the request box starts empty", o["req0"] == [0, "Request box: empty."], o["req0"])
    check("f. request(id, text) saves {id, text, time} in localStorage olympus.requests.v1 (markup stripped, aliases resolved); an unknown person or an empty note saves nothing",
          o["req"][0] == 3 and o["req"][1] == "bot:lit" and o["req"][2] == "Please show the stop distance on the card b" and o["req"][3] is True and o["req"][4] == 3 and o["req"][5] == "id,name,rid,text,time" and o["req"][6] == [None, None] and o["req"][7] == "bot:lit", o["req"])
    check("f. exportRequests(): one text block for Claude, grouped per person with name, id and title; an event fires per request",
          o["export"] == [True, True, True, 2, True] and o["reqEvents"] >= 3, (o["export"], o["reqEvents"]))
    check("f. remove one, clear all; a full or broken storage never throws", o["reqRemove"] == [2, ["Second note", "Check the weather picks"]] and o["reqBroken"] is None and o["reqJunk"] == 0 and o["reqJunk2"] == 1 and o["reqClear"] == 0,
          (o["reqRemove"], o["reqBroken"], o["reqJunk"], o["reqJunk2"], o["reqClear"]))
    check("f. me(): 'You' until the owner makes a character; setMe keeps only known fields (olympus.me.v1), clamps the height, strips markup",
          o["me0"] == ["me", "You", False, "none"] and o["me"][:6] == ["Alex i", True, "#7d5233", "bun", True, "wide"] and o["me"][6] == 1.15 and o["me"][7] == "face,hairStyle,height,skin" and o["me"][8] == "eyes,glasses" and o["me"][9] == "Alex i", (o["me0"], o["me"]))
    check("f. spec(id) is deterministic and carries the mood of the data (LIT is up today: proud); portraitText gives the same SVG text for a texture", o["spec"] == [True, "helmet", "proud", "#7d5233", True, True], o["spec"])
    check("f. provide(id, facts): a scene's own keeper answers from what the scene gave it", o["scene"][0].startswith("Sparta has 14 houses.") and "Houses: 14." in o["scene"][1] and o["scene"][2] == "hellas/world.json", o["scene"])


def test_three():
    o = run(THREE_HARNESS, with_three=True)
    if o is None:
        return
    check("g. no error in the 3D harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check(f"g. {o['n']} figures built (everyone, four moods): {o['maxMeshes']} meshes (2 draw calls: body + ink line), at most {o['maxHigh']:,} triangles each ({o['maxLite']:,} on LITE), 2 shared materials",
          o["maxMeshes"] == 2 and o["maxHigh"] <= 10000 and o["maxLite"] <= 6000 and o["mats"] == 2 and o["bad"] == [], {k: o[k] for k in ("maxMeshes", "maxHigh", "maxLite", "mats", "bad")})
    check("g. spec(id) is plain data with the contract's fields (skin, hair, hairStyle, outfit, accent, accessory, height, build, face{eyes, brows, mouth}, mood)", o["spec"] == [True, True, True, "helmet", True, "proud"], o["spec"])
    check("g. poses idle / wave / talk / cheer / slump (+ nod, shrug): the arm goes up to wave, both up to cheer, the head drops to slump; lookAt turns the head; an unknown pose is idle",
          all(n in o["poses"] for n in ("idle", "wave", "talk", "cheer", "slump")) and o["pose"] == [True, True, True, True, True, True, "function", True], (o["poses"], o["pose"]))
    check("g. a figure stands on y = 0 and is about one unit tall", abs(o["box"][0]) < 0.03 and o["box"][1] is True, o["box"])
    c = o["crowd"]
    check(f"g. the crowd: {c[0]} people in {c[1]} draw calls (meshes {c[2]}), a ray picks the right person and misses empty air, LITE is lighter, nobody = nothing drawn", c[0] >= 30 and c[1] == c[2] == 2 and c[3] == 3 and c[4] == -1 and c[5] is True and c[6] is True and o["empty"] == 0, c)
    check("g2. figure API v2: setMouth / setExpression / setTalking / animate / play / lookAt / workPose / materials, the lists of visemes, expressions and work poses",
          o["v2api"] == [] and o["lists"][0] == "rest,A,E,O,MBP,smile,frown" and o["lists"][1] == "neutral,happy,proud,worried,thinking,surprised,sheepish"
          and o["lists"][2] == "hammer,write,read,weigh,telescope,type,carry" and o["lists"][3:] == ["hammer", "weigh", "type"], (o["v2api"], o["lists"]))
    v = o["visemes"]
    check("g2. the mouth has the 6 viseme morphs (rest = none): setMouth('A', 1) opens A fully, O at 0.7 replaces it, rest closes it", v[0] == "A,E,MBP,O,frown,smile" and v[1] == 1 and v[2] == [0.7, 0] and v[3] is True, v)
    check(f"g2. the 7 expressions make {o['exprDistinct']} different faces (lids, brows, mouth)", o["exprDistinct"] == 7, o["exprDistinct"])
    check("g2. alive: talking opens the mouth in syllables, the eyes blink by themselves, lookAt turns the eyes and the head", o["alive"] == [True, True, True, True], o["alive"])
    w = o["work"]
    check("g2. work poses: a builder holds his hammer when idle; 'hammer' brings the work hammer and the anvil (built on demand: more triangles after); every work pose shows its own props; a wave returns to the last loop",
          w[0] == "p_hammer" and w[1] == "p_whammer,p_anvil" and w[2] is True and w[3] == {"hammer": "p_whammer,p_anvil", "write": "p_quill,p_tablet", "read": "p_scrollOpen", "weigh": "p_coin,p_scales", "telescope": "p_telescope", "type": "p_slate", "carry": "p_crate"}
          and w[4] is True and w[5] == "carry", w)
    check(f"g2. deterministic 3D: the same person is the same mesh every time; {o['det3d'][1]} of {o['det3d'][2]} people have a mesh of their own", o["det3d"][0] is True and o["det3d"][1] == o["det3d"][2], o["det3d"])
    check(f"g2. variety: {o['variety3d'][0]} hair cuts and {o['variety3d'][1]} garbs across the people and villagers", o["variety3d"][0] >= 10 and o["variety3d"][1] == 5, o["variety3d"])
    check(f"g2. budgets (Round 4: <= 45 draw calls, <= 160k triangles): 30 people as a crowd + 4 close-ups = {o['scene30'][0]} draw calls, {o['scene30'][1]:,} triangles; crowd per person {o['crowdBudget']} (seated LITE, LITE, high)",
          o["scene30"][0] <= 12 and o["scene30"][1] <= 100000 and o["crowdBudget"][0] <= 2000 and o["crowdBudget"][1] <= 2000 and o["crowdBudget"][2] <= 3000, (o["scene30"], o["crowdBudget"]))
    check("g2. crowd v2: a hidden person (swapped for a close-up) is not picked unless asked; lookAll / setActive / setPose / setVisible / setTalking", o["crowd2"] == [-1, 2, True], o["crowd2"])
    check(f"g2. the portrait draws the same faces: {o['pexpr']} expressions and {o['pvis']} mouth shapes are all different, a blink shuts the eyes", o["pexpr"] == 7 and o["pvis"] == 7 and o["pblink"] is True, (o["pexpr"], o["pvis"], o["pblink"]))


RIG_HARNESS = r"""
const fs = require('fs'), path = require('path');
const [, , TMP, WEB] = process.argv;
(async () => {
  const imp = (f) => import(path.join(TMP, f));
  const THREE = await imp('three.mjs'), R = await imp('olympus/people-rig.mjs'), P3 = await imp('olympus/people3d.mjs'), C = await imp('olympus/people-core.mjs');
  const { GLTFLoader } = await imp('olympus/three-addons/GLTFLoader.mjs'), { MeshoptDecoder } = await imp('olympus/three-addons/meshopt_decoder.module.mjs');
  const buf = fs.readFileSync(path.join(WEB, 'assets', 'people', 'cast.glb')), ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const o = {};
  // a broken cast is refused (the v2 figures stay)
  let bad = false; try { await R.loadCast({ THREE, GLTFLoader, MeshoptDecoder }, new ArrayBuffer(64), 'bad'); } catch (e) { bad = true; }
  o.badCast = [bad, P3.rigStatus(), !!P3.figure(THREE, P3.spec('bot:lit'), {}).userData.rig];
  const t0 = Date.now(), cast = await R.loadCast({ THREE, GLTFLoader, MeshoptDecoder }, ab, 'test');
  o.cast = [Date.now() - t0, Object.keys(cast.parts).length, Object.keys(cast.clips).length, cast.bindNames.length];
  P3.rigInstall(R, cast);
  o.status = P3.rigStatus();
  const Rr = C.normRoster(JSON.parse(fs.readFileSync(path.join(WEB, 'olympus', 'people.json'), 'utf8'))), everyone = Rr.people.concat(Rr.villagers);
  let maxHigh = 0, maxLite = 0, maxMeshes = 0, minMeshes = 9, mats = new Set(), allRig = true, combos = new Set(), bad2 = [];
  for (const p of everyone) {
    const s = C.spec(p), f = P3.figure(THREE, s, {}), l = P3.figure(THREE, s, { lite: true }), st = P3.figure(THREE, s, { seated: true });
    let m = 0; f.traverse((x) => { if (x.isMesh) { m++; mats.add(x.material.uuid); } });
    maxMeshes = Math.max(maxMeshes, m); minMeshes = Math.min(minMeshes, m); allRig = allRig && f.userData.rig === 3 && l.userData.rig === 3 && st.userData.rig === 3;
    maxHigh = Math.max(maxHigh, f.userData.triangles, st.userData.triangles); maxLite = Math.max(maxLite, l.userData.triangles);
    const ot = f.userData.outfit; combos.add([ot.face, ot.hair, ot.body, ot.cape, ot.hood, ot.accessory, s.outfit, s.skin].join('|'));
    P3.animate(f, 0.05); f.updateWorldMatrix(true, true); const bn = f.userData.character.bones, top = f.userData.parts.head.getWorldPosition(new THREE.Vector3()).y, foot = Math.min(bn.toesl.getWorldPosition(new THREE.Vector3()).y, bn.footl.getWorldPosition(new THREE.Vector3()).y); if (!(foot > -0.08 && foot < 0.12 && top > 0.55 && top < 1.1)) bad2.push([p.id, foot, top]);
    f.userData.dispose(); l.userData.dispose(); st.userData.dispose();
  }
  o.all = [everyone.length, allRig, minMeshes, maxMeshes, maxHigh, maxLite, mats.size, combos.size, bad2.slice(0, 3)];
  // every pose plays: the state names it, the base clip is the cast's, nothing is NaN
  const f = P3.figure(THREE, P3.spec(Rr.people.find((p) => p.kind === 'builder')), {}), poses = {};
  const finite = () => { let ok = true; f.traverse((b) => { if (b.isBone && !(isFinite(b.quaternion.x) && isFinite(b.position.y))) ok = false; }); return ok; };
  for (const n of P3.POSE_NAMES) { P3.play(f, n); for (let i = 0; i < 12; i++) P3.animate(f, 0.05); const st = f.userData.state(); poses[n] = [st.pose === n, st.base, finite()]; }
  o.poses = poses;
  // the wave raises the right hand above the head; a one-shot returns to the last loop
  const g = P3.figure(THREE, P3.spec('scanner:chrysos'), {}), B = g.userData.character.bones, wy = () => { g.updateWorldMatrix(true, true); return B.handr.getWorldPosition(new THREE.Vector3()).y; };
  P3.animate(g, 0.05); const y0 = wy(); const dur = P3.play(g, 'wave'); for (let i = 0; i < 12; i++) P3.animate(g, 0.05); const y1 = wy(); const hy = B.head.getWorldPosition(new THREE.Vector3()).y;
  for (let i = 0; i < 60; i++) P3.animate(g, 0.05);
  o.wave = [y1 > hy, y1 - y0 > 0.2, dur > 1, g.userData.state().pose];
  // faces: visemes, expressions, talking, blink, glance, lookAt turns the head
  const h = P3.figure(THREE, P3.spec('scanner:sibyl'), {}), fm = h.userData.faceMesh, dict = fm.morphTargetDictionary, inf = () => fm.morphTargetInfluences;
  o.morphs = Object.keys(dict).join(',');
  const vis = {}; for (const v of ['A', 'E', 'O', 'MBP', 'smile', 'frown']) { for (let i = 0; i < 8; i++) { P3.setMouth(h, v, 1); P3.animate(h, 0.03); } vis[v] = +inf()[dict[v]].toFixed(2); }
  o.visemes = vis;
  for (let i = 0; i < 20; i++) P3.animate(h, 0.05);
  const faces = {}; for (const e of P3.EXPRESSIONS) { P3.setExpression(h, e, 1); for (let i = 0; i < 20; i++) P3.animate(h, 0.05); const m = h.userData.state().morph; faces[e] = JSON.stringify(['browUp', 'browSad', 'browAngry', 'wide', 'smile', 'frown', 'O', 'MBP'].map((k) => Math.round(m[k] * 10))); }
  o.exprDistinct = new Set(Object.values(faces)).size;
  P3.setExpression(h, 'neutral', 1); P3.setTalking(h, true); let open = 0; for (let i = 0; i < 60; i++) { P3.animate(h, 0.05); open = Math.max(open, ...h.userData.state().mouth); }
  P3.setTalking(h, false); let blink = 0, gx = 0; for (let i = 0; i < 220; i++) { P3.animate(h, 0.04); const m = h.userData.state().morph; blink = Math.max(blink, m.blink); gx = Math.max(gx, Math.abs(m.eyeX)); }
  P3.lookAt(h, new THREE.Vector3(4, 0.8, 1)); for (let i = 0; i < 30; i++) P3.animate(h, 0.05); const lk = h.userData.state().look[0];
  P3.lookAt(h, new THREE.Vector3(-4, 0.8, 1)); for (let i = 0; i < 30; i++) P3.animate(h, 0.05); const lk2 = h.userData.state().look[0];
  o.alive = [open > 0.4, blink > 0.9, gx > 0.05, lk > 0.5, lk2 < -0.5];
  // work: the builder's idle hammer; each work pose shows its own props (built on demand)
  const b = P3.figure(THREE, P3.spec(Rr.people.find((p) => p.kind === 'builder')), {}); P3.animate(b, 0.05);
  const idleProps = b.userData.state().props.join(','), t0b = b.userData.triangles, wp = {};
  for (const n of P3.WORK_POSE_NAMES) { P3.play(b, n); for (let i = 0; i < 20; i++) P3.animate(b, 0.05); wp[n] = b.userData.state().props.filter((x) => R.WORK_PROPS[n].includes(x)).sort().join(','); }
  o.work = [idleProps, wp, b.userData.triangles > t0b, b.userData.triangles];
  // seated: the seat (the hall's couches) is under them, at the v2 height
  const sf = P3.figure(THREE, P3.spec('bot:lit'), { seated: true }); for (let i = 0; i < 4; i++) P3.animate(sf, 0.05); sf.updateWorldMatrix(true, true);
  o.seated = [sf.userData.state().base, +sf.userData.character.bones.hips.getWorldPosition(new THREE.Vector3()).y.toFixed(3)];
  // determinism: same person -> same geometry and colours
  const sig = (x) => { const a = x.userData.body.geometry.getAttribute('position').array, c = x.userData.body.geometry.getAttribute('color').array; let k = 0; for (let i = 0; i < a.length; i += 5) k = (k * 31 + Math.round(a[i] * 1000) + Math.round(c[i] * 1000)) >>> 0; return k + ':' + a.length; };
  const d1 = P3.figure(THREE, P3.spec('bot:lit'), {}), d2 = P3.figure(THREE, P3.spec('bot:lit'), {});
  o.det = [sig(d1) === sig(d2), new Set(Rr.people.map((p) => { const x = P3.figure(THREE, C.spec(p), {}), k = sig(x); x.userData.dispose(); return k; })).size, Rr.people.length];
  // a scene of 30: the crowd (v2 in node: no document for the sprites) + 4 rigged close-ups
  const sc = Rr.people.slice(0, 30).map((p) => C.spec(p)), cr = P3.figureInstanced(THREE, sc, { seated: true, lite: true }), cu = sc.slice(0, 4).map((s) => P3.figure(THREE, s, { seated: true }));
  o.scene30 = [cr.userData.drawCalls + cu.length * 2, cr.userData.totalTriangles + cu.reduce((n, x) => n + x.userData.triangles, 0)];
  // the placeholder: before the cast arrives a scene gets the v2 figure; when it arrives the SAME object becomes the rigged one, its pose, face and scale kept
  P3.rigInstall(R, null, new Promise((ok) => setTimeout(() => ok(cast), 30))); globalThis.window = { location: { search: '' }, dispatchEvent() { return true; } };
  const ph = P3.figure(THREE, P3.spec('keeper:market'), {}), ud0 = ph.userData; ph.scale.multiplyScalar(1.5); P3.play(ph, 'think'); P3.setExpression(ph, 'happy', 1);
  const before = [!!ph.userData.rig, ph.userData.v]; await new Promise((ok) => setTimeout(ok, 120)); P3.animate(ph, 0.05);
  o.upgrade = [before, !!ph.userData.rig, ph.userData === ud0, ph.userData.state().pose, ph.userData.state().expression, +ph.scale.x.toFixed(3), +(1.5).toFixed(3)];
  delete globalThis.window;
  // rig off: opts.rig === false and rigInstall(null) give the v2 figure again
  o.off = [!!P3.figure(THREE, P3.spec('bot:lit'), { rig: false }).userData.rig];
  P3.rigInstall(null); o.off.push(!!P3.figure(THREE, P3.spec('bot:lit'), {}).userData.rig, P3.rigStatus());
  console.log(JSON.stringify(o));
})().catch((e) => { console.error(e && e.stack ? e.stack : e); process.exit(1); });
"""


def stage_rig(tmp):
    """people-core / people-rig / people3d and the three.js add-ons as .mjs (imports renamed), three.js at the root."""
    def fix(t):
        return (t.replace("./people-core.js", "./people-core.mjs").replace("./people-rig.js", "./people-rig.mjs")
                .replace("'../../jarvis/three.module.min.js'", "'../../three.mjs'").replace("'./BufferGeometryUtils.js'", "'./BufferGeometryUtils.mjs'"))
    os.makedirs(os.path.join(tmp, "olympus", "three-addons"), exist_ok=True)
    for f in ("people-core", "people-rig", "people3d"):
        with open(os.path.join(tmp, "olympus", f + ".mjs"), "w", encoding="utf-8") as fh:
            fh.write(fix(AK.read(os.path.join(OLY, f + ".js"))))
    for f in ("GLTFLoader", "BufferGeometryUtils", "meshopt_decoder.module"):
        with open(os.path.join(tmp, "olympus", "three-addons", f + ".mjs"), "w", encoding="utf-8") as fh:
            fh.write(fix(AK.read(os.path.join(OLY, "three-addons", f + ".js"))))
    shutil.copy(os.path.join(AK.WEB, "jarvis", "three.module.min.js"), os.path.join(tmp, "three.mjs"))


def test_rig():
    exe = shutil.which("node")
    if not exe:
        check("g3. node is not installed: the rig tests are skipped", True)
        return
    tmp = tempfile.mkdtemp(prefix="people-rig-")
    try:
        stage_rig(tmp)
        h = os.path.join(tmp, "harness.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(RIG_HARNESS)
        r = subprocess.run([exe, h, tmp, AK.WEB], capture_output=True, text=True, timeout=600)
        if r.returncode:
            print(r.stderr[-2500:])
        o = json.loads(r.stdout) if not r.returncode else {"_error": r.stderr[-900:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("g3. no error in the rig harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("g3. a broken cast is refused and the figures stay v2 (the fallback when the asset fails to load)", o["badCast"] == [True, "v2", False], o["badCast"])
    c = o["cast"]
    check(f"g3. the cast loads in node in {c[0]} ms: {c[1]} parts, {c[2]} animation clips, {c[3]} bones (one shared skeleton)", c[1] >= 24 and c[2] >= 20 and 20 <= c[3] <= 30 and o["status"] == "v3", c)
    a = o["all"]
    check(f"g3. all {a[0]} people and villagers are rigged characters: {a[2]}-{a[3]} meshes (2 draw calls: body + face), at most {a[4]:,} triangles ({a[5]:,} LITE), one shared material, standing on y = 0 (feet), the face 0.55-1.1 up (about 1 unit tall)",
          a[1] is True and a[2] == a[3] == 2 and a[4] <= 10000 and a[5] <= 8000 and a[6] <= 2 and a[8] == [], a)
    check(f"g3. variety: {a[7]} different looks (face, hair, body, cape / hood, accessory, colours) for {a[0]} people", a[7] >= a[0] * 0.9, a[7])
    ps = o["poses"]
    check(f"g3. every pose plays ({len(ps)}: the v2 names + run, sit, interact, pickup, jump, surprised), each on a cast clip, the bones stay finite",
          all(v[0] and v[1] and v[2] for v in ps.values()) and len(ps) >= 22 and ps["hammer"][1] == "1H_Melee_Attack_Chop" and ps["walk"][1].startswith("Walking_") and ps["cheer"][1] == "Cheer", ps)
    check("g3. wave: the right hand goes up over the head, one-shot (> 1 s), then back to the loop it came from", o["wave"][:3] == [True, True, True] and o["wave"][3] == "idle", o["wave"])
    check("g3. the face mesh has 13 morphs (blink, wide, brows x3, eyes x2, the 6 visemes)", o["morphs"] == "blink,wide,browUp,browSad,browAngry,eyeX,eyeY,A,E,O,MBP,smile,frown", o["morphs"])
    check("g3. setMouth drives each viseme (morph weight > 0.8 within 0.25 s)", all(v > 0.8 for v in o["visemes"].values()), o["visemes"])
    check(f"g3. the 7 expressions make {o['exprDistinct']} different faces (brows, eyes, mouth)", o["exprDistinct"] == 7, o["exprDistinct"])
    check("g3. alive: talking opens the mouth in syllables, the eyes blink and glance by themselves, lookAt turns the head both ways", o["alive"] == [True] * 5, o["alive"])
    w = o["work"]
    check("g3. work: a builder holds a hammer when idle; every work pose shows its own props (built on demand, more triangles after)",
          "hammer" in w[0] and w[1] == {"hammer": "anvil,whammer", "write": "quill,tablet", "read": "scrollOpen", "weigh": "coin,scales", "telescope": "telescope", "type": "slate", "carry": "crate"} and w[2] is True and w[3] <= 12000, w)
    check(f"g3. seated: the sitting clip, the hips at the couch height of v2 ({o['seated'][1]})", o["seated"][0] == "Sit_Chair_Idle" and 0.2 < o["seated"][1] < 0.42, o["seated"])
    check(f"g3. deterministic: the same person is the same mesh every time; {o['det'][1]} of {o['det'][2]} people have a mesh of their own", o["det"][0] is True and o["det"][1] >= o["det"][2] - 2, o["det"])
    check(f"g3. budgets (Round 4): 30 people as one crowd + 4 rigged close-ups = {o['scene30'][0]} draw calls, {o['scene30'][1]:,} triangles", o["scene30"][0] <= 12 and o["scene30"][1] <= 100000, o["scene30"])
    check("g3. the rig can be switched off (opts.rig = false, no cast): the v2 figure", o["off"] == [False, False, "v2"], o["off"])
    u = o["upgrade"]
    check("g3. the light placeholder: a figure made before the cast loads is the v2 one, then turns into the rigged character in place (same object and userData; pose, face and the scene's scale kept)",
          u[0] == [False, 2] and u[1] is True and u[2] is True and u[3] == "think" and u[4] == "happy" and u[5] == u[6], u)


def test_assets():
    lic = AK.read(os.path.join(ROOT, "docs", "ASSETS_LICENSES.md"))
    d = os.path.join(AK.WEB, "assets", "people")
    files = sorted(f for f in os.listdir(d) if not f.startswith(".")) if os.path.isdir(d) else []
    rows = [ln for ln in lic.splitlines() if ln.startswith("|") and "CC0" in ln]
    missing = [f for f in files if not any(f in r for r in rows)]
    check(f"g3. docs/ASSETS_LICENSES.md has a CC0 row (author, source URL, licence) for every file in assets/people ({len(files)} files)", bool(files) and not missing and all("http" in r for r in rows if any(f in r for f in files)), missing)
    sizes = {f: os.path.getsize(os.path.join(d, f)) for f in files}
    total = 0
    for root, _, fs in os.walk(os.path.join(AK.WEB, "assets")):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in fs)
    check(f"g3. asset budgets (Round 5): people {sum(sizes.values()) / 1e6:.2f} MB (<= 1.5 MB, one file the whole site shares), all assets {total / 1e6:.1f} MB (<= 25 MB)",
          sum(sizes.values()) <= 1_500_000 and total <= 25_000_000, sizes)
    rig = AK.read(os.path.join(OLY, "people-rig.js")) + AK.read(os.path.join(OLY, "people3d.js")) + AK.read(os.path.join(OLY, "people-studio.js"))
    check("g3. the cast is loaded from this site only (assets/people/cast.glb via the vendored loader), never from a CDN", "../assets/people/cast.glb" in rig and "cdn.jsdelivr" not in rig and "unpkg" not in rig
          and os.path.isfile(os.path.join(OLY, "three-addons", "GLTFLoader.js")) and os.path.isfile(os.path.join(OLY, "three-addons", "meshopt_decoder.module.js")))
    lab = AK.read(os.path.join(OLY, "people-lab.html"))
    check("g3. the lab credits Kay Lousberg (KayKit, CC0) and points at the licence file", "Kay Lousberg" in lab and "CC0" in lab and "ASSETS_LICENSES.md" in lab)


def test_static():
    js = {f: AK.read(os.path.join(OLY, f)) for f in FILES if f.endswith(".js")}
    allj = "".join(js.values())
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if __import__("re").search(p, allj)]
    check("h. no markup is ever built from data in the kit (no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval)", not bad, bad)
    import re
    web = re.findall(r"https://[a-z0-9.\-]+", allj)
    check("h. the only web addresses are the four model providers, and only in people-brain.js; the rest of the kit reads this site's JSON and sends nothing",
          sorted(set(web)) == ["https://api.anthropic.com", "https://api.groq.com", "https://generativelanguage.googleapis.com", "https://openrouter.ai"] and not any("https://" in js[f] for f in js if f != "people-brain.js")
          and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|document\.cookie", allj) and "method: 'POST'" not in "".join(v for k, v in js.items() if k != "people-brain.js"), sorted(set(web)))
    core = re.sub(r"//[^\n]*", "", js["people-core.js"] + js["people-talk.js"])
    check("h. people-core.js and people-talk.js are pure (no document / window / fetch / localStorage) and Safari 16 safe (no lookbehind, no .at())", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", core))
    check("h. storage keys: olympus.requests.v1, olympus.me.v1; the Jarvis key 'jarvis.smart' is only ever read", "'olympus.requests.v1'" in js["people.js"] and "'olympus.me.v1'" in js["people.js"] and "setItem" not in js["people-brain.js"] and "jarvis.smart" not in js["people.js"])
    css = AK.read(os.path.join(OLY, "people.css"))
    check("h. the chat sheet: 44 px taps, safe areas, reduced motion, LITE, no neon / glow / techno font; the typing dots never wait longer than 600 ms",
          css.count("min-height: 44px") + css.count("min-height: 46px") >= 5 and "safe-area-inset-bottom" in css and "prefers-reduced-motion" in css and 'data-oly-lite="1"' in css and not AK.BANNED_LOOK.search(css) and not AK.BANNED_LOOK.search(js["people.js"])
          and "Math.min(450" in js["people.js"])
    check("h. the sheet is a dialog (role, aria-modal, labelled), follows the visual viewport (iOS keyboard), has the mic (Web Speech when there), spoken replies off by default, request, open work, share",
          all(x in js["people.js"] + js["people-voice.js"] for x in ("'dialog'", "aria-modal", "visualViewport", "webkitSpeechRecognition", "speechSynthesis", "'Leave a request'", "'Open their work'", "navigator.share", "=== '1'")))
    check("h. the three events of the contract are fired on window", all(e in js["people.js"] for e in ("olympus:people:open", "olympus:people:close", "olympus:people:request")))
    doc = AK.read(os.path.join(ROOT, "docs", "PERSONA_API.md"))
    check("h. docs/PERSONA_API.md is the contract this kit implements (the ids, the API names)", all(x in doc for x in ("OLYMPUS_PEOPLE", "olympus.requests.v1", "people3d.js", "figureInstanced")))


if __name__ == "__main__":
    test_roster()
    test_static()
    test_core()
    test_show_and_voice()
    test_api()
    test_three()
    test_rig()
    test_assets()
    AK.finish()
