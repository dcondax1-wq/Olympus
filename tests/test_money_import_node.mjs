// node half of tests/test_money_import.py: the Oikos household card core (oikos/householdcore.js) and Jarvis's household answers
// (router.js + skills.js reading money/household.json). Args: <household.json> <old household.json (age 60 days)>. Prints one JSON object.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WP = path.join(ROOT, 'tools', 'web_public');
const C = await import(pathToFileURL(path.join(WP, 'oikos', 'householdcore.js')).href);
const R = await import(pathToFileURL(path.join(WP, 'jarvis', 'router.js')).href);
const SK = await import(pathToFileURL(path.join(WP, 'jarvis', 'skills.js')).href);
const doc = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), old = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const NOW = Date.parse('2026-11-14T17:00:00Z');
const out = {};
const v = C.view(doc);
out.view = { state: v.state, pill: v.pill, kpis: v.kpis.map((k) => [k.label, k.value]), cats: v.cats.map((c) => [c.name, c.usd]), subs: v.subs.map((s) => [s.name, s.usd, s.every, s.next]), leaks: v.leaks.length, lines: v.lines, notes: v.notes };
out.off = [C.view(null).state, C.view({ kind: 'other' }).state, C.view({ kind: 'olympus-household', status: 'empty', data: { rows: 0 } }).state, C.view(old).state, C.view(null).lines[0]];
out.usd = [C.usd(1234.5), C.usd(-12.5), C.usd(15.49), C.usd(0), C.usd(null), C.usd(50, true)];
const store = new Map();
const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, x) => store.set(k, String(x)), removeItem: (k) => store.delete(k) };
const mk = (S) => SK.createSkills({ getSources: async () => S, storage, now: () => NOW, apps: () => [] });
const sk = mk({ household: doc, at: { household: NOW - 600000 } });
const qs = ['how much did I spend on food this month', 'what subscriptions do I have', 'how long can I live on my savings', 'how much did I spend this month', 'whats my net worth', 'what did I spend on gas last month'];
out.routes = qs.map((q) => { const r = R.route(q, { apps: [] }); return r ? r.intent : null; });
out.answers = [];
for (const q of qs) { const r = await sk.handle(q, null, { now: NOW }); out.answers.push(r ? { intent: r.intent, text: r.text, missing: !!r.missing } : null); }
const none = mk({ at: {} });
const r0 = await none.handle('how much did I spend on food this month', null, { now: NOW });
out.missing = r0 ? { missing: !!r0.missing, text: r0.text } : null;
console.log(JSON.stringify(out));
