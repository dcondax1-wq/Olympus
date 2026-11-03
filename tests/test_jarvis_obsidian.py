"""Jarvis x Obsidian (owner 2026-11-02: "everything connected to my Obsidian ... think like me"):
tools/web_public/jarvis/obsidian.js (the vault: GitHub index, search, append-only writes) and memory.js (what the owner says
-> confirmed writes and answers from his notes), driven in node against a mocked GitHub API holding a FAKE vault:
  a. connect: a bad repo name / a refused token are said plainly and nothing is kept; a good one indexes the vault and seeds
     OLYMPUS/Jarvis/Me.md once (never over an existing one)
  b. the index: titles, headings, tags, [[links]], frontmatter, open tasks, daily notes (by file name; Jarvis's inbox is not
     a daily note); BM25 search ranks the right note first
  c. incremental refresh: the same tree SHA = one call; one changed note = one blob fetched; a rate limit stops the calls
  d. writes: always confirmed first ("yes"), append-only (the old text kept byte for byte), into OLYMPUS/Inbox/<day>.md,
     Memory.md, Me.md and today's daily note; "no" writes nothing
  e. the token: only ever sent to https://api.github.com, never in a URL, a body, a reply or the console
  f. offline / no GitHub: a pasted note is searchable; a confirmed note waits on the phone and is sent on connect
  g. disconnect wipes the token, the index, pasted notes, the outbox and the learned list
  h. the Mind page's API: graphSnapshot() (notes with linked ids, kinds, words; learned) and onIndexChange(cb)
  i. memory.js intents: what did I write about X, today's daily note, open tasks, on my mind lately, this week's notes,
     links, my goals, a stated preference offered for Me.md
  j. the brain with memory: "remember ..." -> confirm -> saved; smart mode sends the top note snippets and Me.md (never the
     GitHub token) and cites note titles
  k. Chromium (assist-ui.js + the real IndexedDB): the proactive line (shown once per change, dismissed by its key), the free
     AI key steps, the Obsidian sheet (the 3 steps, paste a note, kept in IndexedDB-backed search), graphSnapshot() in a page
    python -X utf8 -m tests.test_jarvis_obsidian      (node + a temp folder; nothing else touched; a few seconds)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import threading
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []
TOKEN = "github_pat_FAKE0123456789abcdefTOKEN"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


# a fake vault: nothing personal, the shapes an Obsidian vault has
VAULT = {
    "Daily/2026-11-02.md": "---\ntags: [daily]\n---\n# Mon Nov 2\n- [ ] Call the MFFU support about the inactivity rule\n- [x] Gym\nFelt impatient about the evals. #discipline\nRead [[MFFU notes]].\n",
    "Daily/2026-11-01.md": "# Sun Nov 1\nPlanned the week. Kalshi bot sizing ideas. #kalshi\n- [ ] Review Kalshi strategies\n",
    "Daily/2026-10-20.md": "# Old day\nNothing much.\n",
    "Trading/MFFU notes.md": "---\ntitle: MFFU notes\ntags:\n  - trading\n  - mffu\n---\n# MFFU rules I care about\n## Trailing drawdown\nThe max loss trails at the end of the day only. Trailing drawdown locks at start + 100.\n## Inactivity\nSeven days with no trade can close the account.\nSee [[Goals]] and [[Trading/Playbook]].\n",
    "Trading/Playbook.md": "# Playbook\nStop beyond the sweep extreme. Size follows the stop. One target, no greed.\nLinks: [[MFFU notes]]\n",
    "Goals.md": "# Goals 2026\n- [ ] Pass the 50K eval in 2 weeks\n- [ ] First payout by December\n- [x] Build Jarvis\n#goals\n",
    "Ideas/Ascend.md": "# Ascend\nSelf improvement app. Habits, sleep, discipline streaks.\n",
    "OLYMPUS/Inbox/2026-11-02.md": "# Inbox 2026-11-02\n- 09:00 an older inbox line\n",
    ".obsidian/workspace.md": "# not a note\n",
    "Attachments/big.png": "binary",
}

PHRASES = ["note: call the broker", "Hey Jarvis, remember that ATLAS likes the 9:35 open", "add task renew the VPS", "add milk to my list",
           "todo: check fills", "task list", "to do today?", "what did I write about sleep?", "never mind", "I love you",
           "Always give me the dollars first", "I don't like long answers", "stop saying sir", "what links to Goals", "how are the bots"]
RUNNER = r"""
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [dir, scenPath] = process.argv.slice(2);
const scen = JSON.parse(fs.readFileSync(scenPath, 'utf8'));
const TOKEN = scen.token;
const logs = [];
for (const k of ['log', 'warn', 'error', 'info', 'debug']) { const f = console[k]; console[k] = (...a) => { logs.push(a.map(String).join(' ')); }; console['_' + k] = f; }
const O = await import(pathToFileURL(dir + '/obsidian.js').href);
const Mm = await import(pathToFileURL(dir + '/memory.js').href);
const B = await import(pathToFileURL(dir + '/brain.js').href);
const out = {};
const NOW = Date.parse('2026-11-02T18:00:00Z');          // Mon Nov 2, 1:00 PM ET
const b64 = (s) => Buffer.from(s, 'utf8').toString('base64');
const hash = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return ('0000000' + h.toString(16)).slice(-8) + s.length; };
// ---------------------------------------------------------------------------- the fake GitHub
function fakeGitHub(files, opts = {}) {
  const repo = 'owner/fake-vault', calls = [];
  const F = new Map(Object.entries(files));
  const blobs = () => new Map([...F].map(([p, t]) => [hash(p + t), [p, t]]));
  const res = (status, body, raw, headers) => ({ ok: status < 400, status, headers: { get: (k) => (headers || {})[k.toLowerCase()] ?? null },
    json: async () => body, text: async () => (raw != null ? raw : JSON.stringify(body)) });
  const fetch = async (url, init = {}) => {
    const h = init.headers || {};
    calls.push({ url, method: init.method || 'GET', auth: h.Authorization || '', body: init.body || '' });
    if (opts.rateLimit && calls.length > opts.rateLimit) return res(403, { message: 'rate limit' }, null, { 'x-ratelimit-remaining': '0', 'x-ratelimit-reset': String(Math.floor(Date.now() / 1000) + 3600) });
    if (!String(url).startsWith('https://api.github.com/')) return res(599, {});
    if (h.Authorization !== 'Bearer ' + TOKEN) return res(401, { message: 'Bad credentials' });
    const u = new URL(url), p = decodeURIComponent(u.pathname);
    if (p === `/repos/${repo}`) return res(200, { default_branch: 'main', private: true });
    if (p === `/repos/${repo}/git/trees/main`) {
      const tree = [...F].map(([path, t]) => ({ path, type: 'blob', sha: hash(path + t), size: t.length }));
      tree.push({ path: 'Daily', type: 'tree', sha: 'd1' });
      return res(200, { sha: hash(JSON.stringify(tree)), tree });
    }
    const bm = /^\/repos\/[^/]+\/[^/]+\/git\/blobs\/(.+)$/.exec(p);
    if (bm) { const b = blobs().get(bm[1]); return b ? res(200, {}, b[1]) : res(404, {}); }
    const cm = new RegExp(`^/repos/${repo}/contents/(.+)$`).exec(p);
    if (cm) {
      const path = cm[1];
      if ((init.method || 'GET') === 'GET') return F.has(path) ? res(200, { sha: hash(path + F.get(path)), content: b64(F.get(path)) }) : res(404, { message: 'Not Found' });
      if (init.method === 'PUT') {
        const body = JSON.parse(init.body), text = Buffer.from(body.content, 'base64').toString('utf8');
        if (F.has(path) && body.sha !== hash(path + F.get(path))) return res(409, { message: 'sha mismatch' });
        if (!F.has(path) && body.sha) return res(422, {});
        F.set(path, text);
        return res(F.has(path) ? 200 : 201, { content: { path } });
      }
    }
    return res(404, { message: 'Not Found' });
  };
  return { fetch, calls, F, repo };
}
function store() { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), keys: () => [...m.keys()], m }; }
function kvStore() { const m = new Map(); return { async get(k) { return m.has(k) ? JSON.parse(JSON.stringify(m.get(k))) : null; }, async set(k, v) { m.set(k, JSON.parse(JSON.stringify(v))); }, async del(k) { m.delete(k); }, m }; }

// a. connect
{
  const gh = fakeGitHub(scen.vault), st = store(), kv = kvStore();
  const v = O.createVault({ fetch: gh.fetch, storage: st, kv, now: () => NOW });
  const errs = [];
  for (const c of [{ repo: 'not a repo', token: TOKEN }, { repo: 'owner/fake-vault/../../x', token: TOKEN }, { repo: 'owner/fake-vault', token: '' }, { repo: 'owner/fake-vault', token: 'github_pat_WRONG' }]) {
    try { await v.connect(c); errs.push('connected?!'); } catch (e) { errs.push(String(e.message)); }
  }
  out.a_errors = errs; out.a_kept_after_errors = st.getItem(O.CFG_KEY);
  const s1 = await v.connect({ repo: 'https://github.com/owner/fake-vault', token: TOKEN });
  out.a_status = s1;
  out.a_me_seeded = gh.F.get('OLYMPUS/Jarvis/Me.md') || null;
  const puts1 = gh.calls.filter((c) => c.method === 'PUT').length;
  await v.connect({ repo: 'owner/fake-vault', token: TOKEN });          // a second connect never rewrites Me.md
  out.a_me_puts = [puts1, gh.calls.filter((c) => c.method === 'PUT').length];
  // b. the index and search
  const notes = await Promise.all([v.search('trailing drawdown', 5), v.search('sweep stop size', 3), v.search('kalshi', 3), v.search('zzzz', 3)]);
  out.b_search = notes.map((r) => r.map((x) => [x.title, x.score]));
  out.b_snippet = notes[0][0] && notes[0][0].snippet;
  out.b_daily = await v.daily('2026-11-02');
  out.b_daily_inbox = await v.daily('2026-11-03');
  out.b_tasks = await v.tasks();
  out.b_links = await v.links('MFFU notes');
  out.b_goals = (await v.goals()).map((n) => n.title);
  out.b_parse = O.parseNote('Trading/MFFU notes.md', scen.vault['Trading/MFFU notes.md']);
  out.b_index_paths = (await kv.get('vault.index.v1')).notes.map((n) => n.path).sort();
  // c. incremental
  const n0 = gh.calls.length;
  await v.sync();
  out.c_same_tree_calls = gh.calls.slice(n0).map((c) => c.url.replace('https://api.github.com', ''));
  gh.F.set('Ideas/Ascend.md', '# Ascend\nSelf improvement app. New: a morning routine score.\n');
  const n1 = gh.calls.length;
  await v.sync();
  out.c_changed_calls = gh.calls.slice(n1).map((c) => c.url.replace('https://api.github.com', ''));
  out.c_found_new = (await v.search('morning routine', 1)).map((x) => x.title);
  // d. writes through memory.js: confirm, append only
  const mem = Mm.createMemory({ vault: v, now: () => NOW });
  const before = gh.F.get('OLYMPUS/Inbox/2026-11-02.md'), dailyBefore = gh.F.get('Daily/2026-11-02.md');
  const putsBefore = gh.calls.filter((c) => c.method === 'PUT').length;
  const c1 = await mem.handle('note: check the ATLAS fills tonight', 'note: check the atlas fills tonight');
  out.d_confirm = c1; out.d_puts_before_yes = gh.calls.filter((c) => c.method === 'PUT').length - putsBefore;
  const y1 = await mem.handle('yes', 'yes');
  out.d_saved = y1;
  out.d_inbox = gh.F.get('OLYMPUS/Inbox/2026-11-02.md'); out.d_inbox_before = before;
  out.d_daily = gh.F.get('Daily/2026-11-02.md'); out.d_daily_before = dailyBefore;
  const c2 = await mem.handle('add task buy the BLITZ 25K', 'add task buy the blitz 25k'); const n2 = await mem.handle('no', 'no');
  out.d_no = [c2.text, n2.text, gh.F.get('OLYMPUS/Inbox/2026-11-02.md') === out.d_inbox];
  await mem.handle('remember the 2:00 AM window is the A setup', 'remember the 2:00 am window is the a setup'); out.d_remember = await mem.handle('yes', 'yes');
  out.d_memory = gh.F.get('OLYMPUS/Jarvis/Memory.md');
  const pref = await mem.handle("I don't like long answers, give me the dollars first", "i don't like long answers give me the dollars first");
  out.d_pref = pref; await mem.handle('yes', 'yes');
  out.d_me = gh.F.get('OLYMPUS/Jarvis/Me.md');
  const lg = await mem.handle('write the olympus log', 'write the olympus log', { facts: { system: { verdict: 'HEADS UP', todo: 'Both evals day 5', rows: [{ name: 'Zlarior', value: '+$0', text: 'room $1,106' }] } } });
  out.d_log_confirm = lg.text; await mem.handle('yes', 'yes'); out.d_log = gh.F.get('OLYMPUS/Logs/2026-11-02.md');
  // every PUT keeps the old text (append only), no DELETE ever
  out.d_methods = [...new Set(gh.calls.map((c) => c.method))];
  // i. the read intents
  const ask = async (t) => { const r = await mem.handle(t, t.toLowerCase()); return r && r.text; };
  out.i = {};
  for (const t of ['what did i write about trailing drawdown', "today's daily note", 'open tasks', "what's on my mind lately", "summarize this week's notes", 'what links to MFFU notes', 'what are my goals', 'is obsidian connected', 'what do you know about me', 'how are the bots'])
    out.i[t] = await ask(t);
  out.i_smart_flag = (await mem.handle('what did i write about kalshi', 'what did i write about kalshi')).smart === true;
  out.ctx = await mem.context('drawdown rules');
  // h. the Mind page's API
  let fired = 0; const off = O.onIndexChange(() => { fired++; });
  gh.F.set('Ideas/New.md', '# New idea\nLinks to [[Goals]].\n'); await v.sync(); const f1 = fired; off(); gh.F.set('Ideas/New2.md', 'x'); await v.sync();
  out.h_fired = [f1, fired]; out.h_bad_cb = typeof O.onIndexChange(null);
  out.h_snap = await O.graphSnapshot({ storage: st, kv });
  // e. the token
  out.e_urls_ok = gh.calls.every((c) => c.url.startsWith('https://api.github.com/'));
  out.e_token_in_url_or_body = gh.calls.some((c) => c.url.includes(TOKEN) || String(c.body).includes(TOKEN));
  out.e_token_in_snapshot = JSON.stringify(out.h_snap).includes(TOKEN);
  out.e_token_in_status = JSON.stringify(v.status()).includes(TOKEN);
  // g. disconnect
  await v.disconnect();
  out.g_keys = st.keys(); out.g_kv = [...kv.m.keys()]; out.g_snap = await O.graphSnapshot({ storage: st, kv }); out.g_status = v.status();
  out.g_search = await v.search('drawdown', 3);
}
// c2. a rate limit stops the calls
{
  const gh = fakeGitHub(scen.vault, { rateLimit: 3 }), st = store(), kv = kvStore();
  const v = O.createVault({ fetch: gh.fetch, storage: st, kv, now: () => NOW });
  let err = '';
  try { await v.connect({ repo: 'owner/fake-vault', token: TOKEN }); } catch (e) { err = e.message; }
  const n = gh.calls.length; await v.sync(); await v.sync();
  out.c_rate = { status: v.status(), extra_calls: gh.calls.length - n, err };
}
// f. offline: pasted notes, an outbox sent on connect
{
  const gh = fakeGitHub(scen.vault), st = store(), kv = kvStore();
  const v = O.createVault({ fetch: gh.fetch, storage: st, kv, now: () => NOW });
  const mem = Mm.createMemory({ vault: v, now: () => NOW });
  out.f_imp = v.importNote('Sleep plan', 'Bed by 23:00, no screens after 22:30. #health');
  out.f_search = (await v.search('screens bed', 3)).map((x) => [x.title, x.local]);
  out.f_mind_ask = (await mem.handle('what did I write about screens', 'what did i write about screens')).text;
  await mem.handle('note: idea for Ascend streaks', 'note: idea for ascend streaks'); out.f_saved = (await mem.handle('yes', 'yes')).text;
  out.f_calls_offline = gh.calls.length; out.f_outbox = JSON.parse(st.getItem('jarvis.vault.outbox') || '[]').length;
  out.f_snap_local = await O.graphSnapshot({ storage: st, kv });
  await v.connect({ repo: 'owner/fake-vault', token: TOKEN });
  out.f_after = { outbox: st.getItem('jarvis.vault.outbox'), inbox: gh.F.get('OLYMPUS/Inbox/2026-11-02.md') };
  const nothing = O.createVault({ storage: store(), kv: kvStore() });
  const m2 = Mm.createMemory({ vault: nothing });
  out.f_not_connected = (await m2.handle("today's daily note", "today's daily note"));
  out.f_snap_none = await O.graphSnapshot({ storage: store(), kv: kvStore() });
}
// j. the brain with memory
{
  const gh = fakeGitHub(scen.vault), st = store(), kv = kvStore();
  const v = O.createVault({ fetch: gh.fetch, storage: st, kv, now: () => NOW });
  await v.connect({ repo: 'owner/fake-vault', token: TOKEN });
  const mem = Mm.createMemory({ vault: v, now: () => NOW });
  const ai = [];
  const aiFetch = async (url, init) => { ai.push({ url, init }); return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'From [MFFU notes]: the drawdown trails at the close only.' }, finish_reason: 'stop' }] }), text: async () => '' }; };
  const bst = store();
  const brain = B.createBrain({ getFacts: () => ({ now: NOW }), memory: mem, now: () => NOW, zenithRoutes: false, storage: bst, fetch: aiFetch });
  out.j1 = (await brain.ask('remember Zlarior trades best at the open')).text;
  out.j2 = (await brain.ask('yes')).text;
  out.j_mem = gh.F.get('OLYMPUS/Jarvis/Memory.md');
  out.j3 = (await brain.ask('what did I write about trailing drawdown')).text;
  brain.setSmart({ key: 'gsk_FAKE', on: true });
  const r4 = await brain.ask('what did I write about trailing drawdown');
  out.j4 = { text: r4.text, smart: r4.smart };
  const r5 = await brain.ask('blorp zzz what would I think about this');
  out.j5 = { text: r5.text };
  const body = ai.map((x) => String(x.init.body)).join('\n');
  out.j_ai = { n: ai.length, urls: ai.map((x) => x.url), notes: body.includes('MFFU notes'), me: body.includes('HOW THE OWNER THINKS'), token: body.includes(TOKEN) || JSON.stringify(ai.map((x) => x.init.headers)).includes(TOKEN) };
}
out.parse = Object.fromEntries(scen.phrases.map((t) => [t, { w: Mm.parseWrite(t), p: Mm.parsePreference(t, t.toLowerCase()), r: Mm.parseRead(t.toLowerCase()) }]));
out.e_console = logs.filter((l) => l.includes(TOKEN));
process.stdout.write(JSON.stringify(out));
"""


PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<form id="setF"><label><select id="setProv"></select></label></form><div id="sugs"></div>
<script type="module">
import { createVault, graphSnapshot } from './obsidian.js';
import { mountObsidianSheet, mountProactive, mountKeySteps } from './assist-ui.js';
let H = { text: 'Both evals are on day 5 with no trade.', more: 1, level: 'bad', key: 'quiet5:lit5,atlas5' };
const brain = { headline: () => H };
const asked = [];
const pro = mountProactive({ brain, anchor: document.getElementById('sugs'), onAsk: (t) => asked.push(t) });
const vault = createVault();
const toasts = [];
const obs = mountObsidianSheet({ vault, toast: (t) => toasts.push(t) });
window.T = { pro, obs, vault, asked, toasts, mountKeySteps, graphSnapshot, setH: (h) => { H = h; pro.render(); } };
pro.render();
window.ready = true;
</script></body></html>"""


def part_browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                                   # pragma: no cover
        check("k. Chromium: playwright available", False, e)
        return
    tmp = tempfile.mkdtemp(prefix="le_jobs_web_")
    for f in ("obsidian.js", "assist-ui.js"):
        shutil.copy(os.path.join(JV, f), os.path.join(tmp, f))
    open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write(PAGE)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            p = br.new_page()
            errs, reqs = [], []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("request", lambda r: reqs.append(r.url))
            url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
            p.goto(url)
            p.wait_for_function("window.ready === true", timeout=10000)
            shown = p.is_visible("#proLine") and "Both evals are on day 5" in p.inner_text("#proLine")
            p.click("#proLine .t")
            asked = p.evaluate("window.T.asked")
            p.click("#proLine .x")
            hidden = not p.is_visible("#proLine")
            p.reload()
            p.wait_for_function("window.ready === true", timeout=10000)
            still_hidden = not p.is_visible("#proLine")
            p.evaluate("window.T.setH({ text: 'Zlarior is on day 6 with no trade.', more: 0, level: 'bad', key: 'quiet6:lit6' })")
            back = p.is_visible("#proLine") and "day 6" in p.inner_text("#proLine")
            p.evaluate("window.T.setH({ text: 'All quiet', level: 'ok', key: 'quiet' })")
            calm_hidden = not p.is_visible("#proLine")
            check("k. the proactive line: shown, a tap asks 'what should I do', dismissed by its key (stays dismissed after a reload), back when it changes, hidden when all quiet",
                  shown and asked == ["What should I do now?"] and hidden and still_hidden and back and calm_hidden, (shown, asked, hidden, still_hidden, back, calm_hidden))
            p.evaluate("window.T.mountKeySteps(document.getElementById('setF')); window.T.mountKeySteps(document.getElementById('setF'))")
            ks = p.inner_text("#setF")
            check("k. the free AI key steps: Groq (console.groq.com/keys, Create API Key, paste, Save), Gemini as the other free one; mounted once",
                  "console.groq.com/keys" in ks and "Create API Key" in ks and "aistudio.google.com/apikey" in ks and p.evaluate("document.querySelectorAll('#setF .jx-steps').length") == 1, ks[:300])
            p.evaluate("window.T.obs.open()")
            sh = p.inner_text("#obsSheet")
            check("k. the Obsidian sheet: not connected, three numbered steps (private repo, token with Contents read and write, the Git plugin), repo + token fields",
                  p.is_visible("#obsSheet") and "Not connected" in sh and p.evaluate("document.querySelectorAll('#obsSheet ol li').length") == 3
                  and "Contents: Read and write" in sh and "Git" in sh and p.is_visible("#obsRepo") and p.is_visible("#obsTok"), sh[:400])
            p.fill("#obsRepo", "not a repo")
            p.fill("#obsTok", "github_pat_X")
            p.click("#obsGo")
            p.wait_for_timeout(300)
            check("k. a wrong repo name: said plainly in the sheet, no request sent", "owner/name" in p.inner_text("#obsErr") and not any("api.github.com" in u for u in reqs), p.inner_text("#obsErr"))
            p.fill("#obsPT", "Morning plan")
            p.fill("#obsPB", "Wake 6:30, gym, then the 9:30 open review. #routine")
            p.click("#obsPaste")
            p.wait_for_timeout(200)
            res = p.evaluate("(async () => ({ s: await window.T.vault.search('gym open review', 2), snap: await window.T.graphSnapshot(), st: window.T.vault.status() }))()")
            check("k. paste a note (no GitHub): kept on this phone, searchable, in graphSnapshot() with what was learned; the status says so",
                  res["s"][:1] and res["s"][0]["title"] == "Morning plan" and any(n["title"] == "Morning plan" for n in res["snap"]["notes"])
                  and res["st"]["local"] == 1 and "1 pasted note" in p.inner_text("#obsSt") and p.evaluate("window.T.toasts")[-1].startswith("Saved “Morning plan”"), res)
            p.once("dialog", lambda d: d.accept())
            p.click("#obsOff")
            p.wait_for_timeout(300)
            wiped = p.evaluate("(async () => ({ keys: Object.keys(localStorage).filter((k) => k.startsWith('jarvis.vault')), snap: await window.T.graphSnapshot() }))()")
            check("k. Disconnect (after a confirm) wipes everything of the vault from the phone", wiped["keys"] == [] and wiped["snap"] is None, wiped)
            check("k. no page errors; no request leaves the page's own address", not errs and all(u.startswith(url.rsplit("/", 1)[0]) for u in reqs), (errs, [u for u in reqs if not u.startswith("http://127.0.0.1")]))
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    node = shutil.which("node")
    if not node:
        check("node is installed", False, "node not found")
        return 1
    tmp = tempfile.mkdtemp(prefix="le_jobs_")
    try:
        rp, sp = os.path.join(tmp, "runner.mjs"), os.path.join(tmp, "scen.json")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        open(sp, "w", encoding="utf-8").write(json.dumps({"vault": VAULT, "token": TOKEN, "phrases": PHRASES}))
        r = subprocess.run([node, rp, JV, sp], capture_output=True, text=True, timeout=120)
        check("node ran obsidian.js + memory.js + brain.js", r.returncode == 0, r.stderr[-1500:])
        if r.returncode:
            return 1
        O = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(JV, "obsidian.js"), encoding="utf-8").read() + open(os.path.join(JV, "memory.js"), encoding="utf-8").read()

    # the modules
    check("modules: no imports, no lookbehind (Safari 16), the only network address is api.github.com",
          not __import__("re").search(r"^\s*import\s", src, __import__("re").M) and "import(" not in src
          and "(?<" not in src and set(__import__("re").findall(r"https://[a-z0-9.-]+", src)) <= {"https://api.github.com", "https://github.com"}, "")
    # a. connect
    e = O["a_errors"]
    check("a. connect: a bad repo name, a path trick, no token, a refused token: each said plainly; nothing kept",
          "owner/name" in e[0] and "owner/name" in e[1] and "token" in e[2] and "refused the token" in e[3] and O["a_kept_after_errors"] is None
          and not any(TOKEN in x or "WRONG" in x for x in e), e)
    s1 = O["a_status"]
    check("a. connect (a pasted github.com link is fine): indexed the .md notes only (no .obsidian, no images)",
          s1["connected"] and s1["repo"] == "owner/fake-vault" and s1["branch"] == "main" and s1["state"] == "ok"
          and ".obsidian/workspace.md" not in O["b_index_paths"] and "Attachments/big.png" not in O["b_index_paths"] and "Goals.md" in O["b_index_paths"], (s1, O["b_index_paths"]))
    check("a. Me.md seeded once from the template (money first, the trading rules, OLYMPUS); a second connect never rewrites it",
          O["a_me_seeded"] and "Money first" in O["a_me_seeded"] and "beyond the sweep extreme" in O["a_me_seeded"] and "OLYMPUS" in O["a_me_seeded"]
          and O["a_me_puts"][0] == O["a_me_puts"][1], O["a_me_puts"])
    # b. the index
    pn = O["b_parse"]
    check("b. a note's frontmatter title and tags (list form), #tags, [[links]], headings",
          pn["title"] == "MFFU notes" and {"trading", "mffu"} <= set(pn["tags"]) and pn["links"] == ["Goals", "Trading/Playbook"]
          and "Trailing drawdown" in pn["headings"] and pn["words"] > 20, pn)
    sr = O["b_search"]
    check("b. BM25 search: 'trailing drawdown' -> MFFU notes first; 'sweep stop size' -> Playbook; 'kalshi' -> the daily note; junk -> nothing",
          sr[0][0][0] == "MFFU notes" and sr[1][0][0] == "Playbook" and sr[2][0][0] == "2026-11-01" and sr[3] == [] and sr[0][0][1] > (sr[0][1][1] if len(sr[0]) > 1 else 0), sr)
    check("b. the snippet shows the matching words, as plain words (no Markdown marks, [[links]] as names)", "railing drawdown" in (O["b_snippet"] or "")
          and "#" not in O["b_snippet"] and "[[" not in O["b_snippet"] and "See Goals and Trading/Playbook" in O["b_snippet"], O["b_snippet"])
    check("b. daily notes by file name; Jarvis's inbox page is not a daily note",
          O["b_daily"] and O["b_daily"]["path"] == "Daily/2026-11-02.md" and O["b_daily_inbox"] is None, O["b_daily"] and O["b_daily"]["path"])
    tk = [t["text"] for t in O["b_tasks"]]
    check("b. open tasks only ('- [ ]'), newest daily first", "Call the MFFU support about the inactivity rule" in tk and "Gym" not in tk and "Build Jarvis" not in tk
          and "Pass the 50K eval in 2 weeks" in tk and tk.index("Call the MFFU support about the inactivity rule") < tk.index("Review Kalshi strategies"), tk)
    check("b. links both ways: MFFU notes -> Goals, Playbook; back from the daily note and the Playbook",
          O["b_links"]["out"] == ["Goals", "Trading/Playbook"] and set(O["b_links"]["back"]) >= {"2026-11-02", "Playbook"}, O["b_links"])
    check("b. goals: the note titled Goals", O["b_goals"][:1] == ["Goals"], O["b_goals"])
    # c. incremental
    check("c. the same tree SHA: one call (the tree), nothing fetched", len(O["c_same_tree_calls"]) == 1 and "/git/trees/main" in O["c_same_tree_calls"][0], O["c_same_tree_calls"])
    check("c. one changed note: the tree + exactly one blob; the new text is searchable",
          len(O["c_changed_calls"]) == 2 and "/git/blobs/" in O["c_changed_calls"][1] and O["c_found_new"] == ["Ascend"], (O["c_changed_calls"], O["c_found_new"]))
    cr = O["c_rate"]
    check("c. a GitHub rate limit: said in the status, and no more calls until it resets", cr["extra_calls"] == 0 and ("rate" in (cr["status"]["error"] + cr["err"]).lower() or cr["status"]["state"] in ("error", "partial")), cr)
    # d. writes
    check("d. 'note: ...' asks first (no write before 'yes'), naming the file", O["d_puts_before_yes"] == 0 and "Save the note “check the ATLAS fills tonight” to OLYMPUS/Inbox/2026-11-02.md" in O["d_confirm"]["text"]
          and "Say yes" in O["d_confirm"]["text"], O["d_confirm"])
    check("d. 'yes': appended to the inbox page (the old text kept byte for byte) and to today's daily note",
          O["d_inbox"].startswith(O["d_inbox_before"]) and "check the ATLAS fills tonight" in O["d_inbox"][len(O["d_inbox_before"]):]
          and O["d_daily"].startswith(O["d_daily_before"]) and "check the ATLAS fills tonight (via Jarvis)" in O["d_daily"] and "Saved to OLYMPUS/Inbox/2026-11-02.md" in O["d_saved"]["text"], O["d_saved"])
    check("d. 'no' writes nothing", "Add the task" in O["d_no"][0] and O["d_no"][1] == "Not saved." and O["d_no"][2], O["d_no"])
    check("d. 'remember ...' goes to the inbox and to OLYMPUS/Jarvis/Memory.md", O["d_memory"] and "the 2:00 AM window is the A setup" in O["d_memory"] and O["d_memory"].startswith("# Jarvis memory"), O["d_memory"])
    check("d. a stated preference is offered for Me.md, then appended under the template", "Save this to your Me profile" in O["d_pref"]["text"]
          and O["d_me"].startswith(O["a_me_seeded"]) and "I don't like long answers, give me the dollars first" in O["d_me"], O["d_pref"])
    check("d. the end-of-day OLYMPUS log: confirmed, then a table of the systems in OLYMPUS/Logs/<day>.md",
          "Write today's OLYMPUS log" in O["d_log_confirm"] and O["d_log"] and "| Zlarior | +$0 | room $1,106 |" in O["d_log"] and "HEADS UP" in O["d_log"], O["d_log"])
    check("d. append only: GET and PUT, never DELETE", set(O["d_methods"]) <= {"GET", "PUT"}, O["d_methods"])
    # e. the token
    check("e. the token goes only to https://api.github.com, never in a URL or a body, a status, the snapshot or the console",
          O["e_urls_ok"] and not O["e_token_in_url_or_body"] and not O["e_token_in_snapshot"] and not O["e_token_in_status"] and O["e_console"] == [],
          {k: O[k] for k in ("e_urls_ok", "e_token_in_url_or_body", "e_token_in_snapshot", "e_token_in_status", "e_console")})
    # f. offline
    check("f. a pasted note (no GitHub): kept on the phone, searchable, answers 'what did I write about'",
          O["f_imp"]["ok"] and O["f_search"][:1] == [["Sleep plan", True]] and "Sleep plan" in O["f_mind_ask"], (O["f_search"], O["f_mind_ask"]))
    check("f. a confirmed note with no vault: saved on the phone (no network), sent on connect, the outbox emptied",
          "Saved on this phone" in O["f_saved"] and O["f_calls_offline"] == 0 and O["f_outbox"] == 1 and O["f_after"]["outbox"] is None
          and "idea for Ascend streaks" in (O["f_after"]["inbox"] or ""), (O["f_saved"], O["f_after"]))
    check("f. not connected and nothing pasted: one clear line and the setup (control 'obsidian'); graphSnapshot() null",
          O["f_not_connected"]["control"] == "obsidian" and "not connected yet" in O["f_not_connected"]["text"] and O["f_snap_none"] is None, O["f_not_connected"])
    check("f. graphSnapshot() before any connection shows the pasted note and what was learned", O["f_snap_local"] and any(n["title"] == "Sleep plan" for n in O["f_snap_local"]["notes"])
          and any("Imported" in x["text"] for x in O["f_snap_local"]["learned"]), O["f_snap_local"])
    # g. disconnect
    check("g. disconnect wipes the token, the index, pasted notes, the outbox and the learned list; nothing is searchable",
          not [k for k in O["g_keys"] if k.startswith("jarvis.vault")] and O["g_kv"] == [] and O["g_snap"] is None and not O["g_status"]["connected"] and O["g_search"] == [],
          (O["g_keys"], O["g_kv"]))
    # h. the Mind page's API
    sn = O["h_snap"] or {}
    by = {n["id"]: n for n in sn.get("notes", [])}
    m = by.get("Trading/MFFU notes.md", {})
    check("h. graphSnapshot(): v 1, notes with ids, links as note ids, kinds (daily / inbox / memory / me / note), words, mtime",
          sn.get("v") == 1 and set(m.get("links", [])) == {"Goals.md", "Trading/Playbook.md"} and by["Daily/2026-11-02.md"]["kind"] == "daily"
          and by["OLYMPUS/Inbox/2026-11-02.md"]["kind"] == "inbox" and by["OLYMPUS/Jarvis/Memory.md"]["kind"] == "memory" and by["OLYMPUS/Jarvis/Me.md"]["kind"] == "me"
          and m["kind"] == "note" and m["words"] > 20 and all(isinstance(n["mtime"], int) and n["mtime"] > 0 for n in sn["notes"]), m)
    check("h. graphSnapshot() learned: what Jarvis saved, newest last, with the note it went to",
          any("check the ATLAS fills tonight" in x["text"] and x["note"] == "OLYMPUS/Inbox/2026-11-02.md" for x in sn.get("learned", [])) and all(isinstance(x["t"], int) for x in sn.get("learned", [])), sn.get("learned"))
    check("h. onIndexChange(cb): called after a refresh, silent after unsubscribe; a junk callback is a no-op", O["h_fired"][0] >= 1 and O["h_fired"][1] == O["h_fired"][0] and O["h_bad_cb"] == "function", O["h_fired"])
    P = O["parse"]
    w = {t: (P[t]["w"] or {}) for t in PHRASES}
    check("i. what counts as a write: 'note:', 'remember (that)', 'add task', 'add X to my list', 'todo:'; never 'task list' or 'to do today?'",
          w["note: call the broker"] == {"kind": "note", "text": "call the broker"} and w["Hey Jarvis, remember that ATLAS likes the 9:35 open"] == {"kind": "remember", "text": "ATLAS likes the 9:35 open"}
          and w["add task renew the VPS"]["kind"] == "task" and w["add milk to my list"] == {"kind": "task", "text": "milk"} and w["todo: check fills"]["text"] == "check fills"
          and not w["task list"] and not w["to do today?"] and not w["what did I write about sleep?"], w)
    pf = {t: P[t]["p"] for t in PHRASES}
    check("i. what counts as a preference: 'always ...', 'I don't like ...', 'stop saying ...'; never 'never mind', 'I love you' or a question",
          pf["Always give me the dollars first"]["text"] == "Always give me the dollars first" and pf["I don't like long answers"] and pf["stop saying sir"]
          and not pf["never mind"] and not pf["I love you"] and not pf["what did I write about sleep?"] and not pf["how are the bots"], pf)
    check("i. read intents: 'what did I write about sleep?' (topic without the '?'), 'what links to Goals'; the bots' questions are not vault questions",
          P["what did I write about sleep?"]["r"] == {"name": "search", "topic": "sleep"} and P["what links to Goals"]["r"] == {"name": "links", "topic": "goals"}
          and P["how are the bots"]["r"] is None, (P["what did I write about sleep?"]["r"], P["what links to Goals"]["r"]))
    # i. memory intents
    i = O["i"]
    check("i. 'what did I write about X': the top notes with their words", i["what did i write about trailing drawdown"].startswith("Your notes on “trailing drawdown”") and "1. MFFU notes:" in i["what did i write about trailing drawdown"], i["what did i write about trailing drawdown"])
    check("i. today's daily note, with its open tasks", "Today's note (2026-11-02)" in i["today's daily note"] and "1 open task" in i["today's daily note"], i["today's daily note"])
    check("i. open tasks across the vault", "open tasks in your notes" in i["open tasks"] and "Pass the 50K eval in 2 weeks (Goals)" in i["open tasks"], i["open tasks"])
    check("i. on my mind lately: the themes of the recent notes; this week's notes: the daily notes and the inbox",
          i["what's on my mind lately"].startswith("On your mind lately:") and "This week in your notes (2026-10-27 to 2026-11-02)" in i["summarize this week's notes"]
          and "2026-10-20" not in i["summarize this week's notes"], (i["what's on my mind lately"], i["summarize this week's notes"]))
    check("i. links, goals (from the Goals note), the vault's status, what Jarvis knows about the owner",
          "MFFU notes: links to Goals, Trading/Playbook" in i["what links to MFFU notes"] and "Pass the 50K eval in 2 weeks" in i["what are my goals"]
          and i["is obsidian connected"].startswith("Obsidian connected (owner/fake-vault)") and "money first" in i["what do you know about me"]
          and "I don't like long answers" in i["what do you know about me"] and i["how are the bots"] is None, i)
    check("i. summaries are marked for smart mode (the model writes them, the list is the fallback); context = top snippets + Me.md",
          O["i_smart_flag"] and O["ctx"]["notes"][0]["title"] == "MFFU notes" and "Money first" in O["ctx"]["me"], O["ctx"]["notes"][:1])
    # j. the brain
    check("j. the brain with memory: 'remember ...' asks, 'yes' saves to Memory.md", "Remember “Zlarior trades best at the open”" in O["j1"] and O["j2"].startswith("Saved to OLYMPUS/Inbox/2026-11-02.md")
          and "Zlarior trades best at the open" in (O["j_mem"] or ""), (O["j1"], O["j2"]))
    check("j. smart off: the local list; smart on: the model gets the top notes and Me.md, never the GitHub token, and cites the note",
          O["j3"].startswith("Your notes on") and O["j4"]["smart"] is True and "[MFFU notes]" in O["j4"]["text"] and O["j_ai"]["notes"] and O["j_ai"]["me"]
          and not O["j_ai"]["token"] and all(u.startswith("https://api.groq.com/") for u in O["j_ai"]["urls"]), (O["j4"], O["j_ai"]))
    if "--no-browser" not in sys.argv:
        part_browser()
    n = sum(RES)
    print(f"\njarvis obsidian: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
