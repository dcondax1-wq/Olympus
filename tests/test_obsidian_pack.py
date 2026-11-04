"""The Obsidian starter vault (tools/obsidian_pack.py -> tools/web_public/mind/starter/, the Mind page's Teach screen, the Mind demo brain).

  a. facts: spot checks of the notes against the files they were built from (STRATEGY.md, research/lit/mffu_rules.json, plutus/plans.json,
     athena/library.json, research/writeups/*.md, jarvis/obsidian.js): the numbers in the notes are the numbers in the sources
  b. links: every [[wikilink]] resolves (by note name or path), no note is an orphan, the whole vault is reachable from 00 Home, frontmatter and
     tags on every note, the graph is dense (links per note)
  c. safety: no secret-like string (the Bridge ingest patterns + more), no account numbers / long digit runs / emails / local paths; no open
     "- [ ]" task and no dated file name (Jarvis would list them as his tasks / daily notes); Jarvis reads the paths the pack uses
  d. the build: deterministic, the committed files equal a fresh build, JSON = JS module, the manifest matches, the python zip is valid
  e. the JS side in node: the store-only ZIP writer (CRC-32 of "123456789" = 0xCBF43926, UTF-8 names, empty files, every note), unzipped with
     python's zipfile and compared with the notes; the one-file markdown splits back into the same notes; folder list, previews, loadPack
  f. the Mind page in Chromium (390 x 844): the Teach page has the Starter pack card with 3 steps and the folder list with previews, Download
     as .zip gives a real zip of all notes, Copy as one markdown file puts the text on the clipboard, nothing is written to storage, no errors,
     no request leaves the origin; the demo brain now holds the pack's notes (rich, linked) while the old demo checks still stand
    python -X utf8 -m tests.test_obsidian_pack            (--no-browser: parts a-e only)
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bridge_ingest as BI  # noqa: E402
from tools import obsidian_pack as OP  # noqa: E402

MIND = os.path.join(ROOT, "tools", "web_public", "mind")
STARTER = os.path.join(MIND, "starter")
RES: list[bool] = []
LINK = re.compile(r"\[\[([^\]|#]{1,200})(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:600]})" if detail and not cond else ""), flush=True)
    return bool(cond)


def rd(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


PACK = json.loads(open(os.path.join(STARTER, "starter_pack.json"), encoding="utf-8").read())
NOTES = {n["path"]: n["text"] for n in PACK["notes"]}
TITLES = {p.rsplit("/", 1)[-1][:-3]: p for p in NOTES}
usd = OP.usd


def by_type(t):
    return [p for p, x in NOTES.items() if re.search(rf"^type: {t}$", x, re.M)]


# ============================================================================================== a. facts
def facts():
    lib = json.loads(rd("tools/web_public/athena/library.json"))
    rules = json.loads(rd("research/lit/mffu_rules.json"))
    plans = json.loads(rd("tools/web_public/plutus/plans.json"))
    strat = rd("STRATEGY.md")
    check("a. about 225 notes in the layout the owner asked for (Home, Trading, Playbooks, Research, Money, Templates, Jarvis)", len(NOTES) >= 200
          and "00 Home.md" in NOTES and all(any(p.startswith(f + "/") for p in NOTES) for f in ("Trading", "Playbooks", "Research", "Money", "Templates", "OLYMPUS")), Counter(p.split("/")[0] for p in NOTES))
    kinds = Counter(e["kind"] for e in lib["entries"])
    check("a. one note per library entry: every glossary term, MFFU rule, playbook, 'what we learned', rejected idea, Kalshi and app guide",
          len(by_type("term")) == kinds["words"] and len(by_type("playbook")) == kinds["playbook"] and len(by_type("rejected")) == kinds["rejected"]
          and len(by_type("rule")) == kinds["mffu"] + 1 and len(by_type("app-guide")) == kinds["olympus"] and len(by_type("kalshi")) == kinds["kalshi"]
          and len([p for p in by_type("research") if p.startswith("Research/What we learned/")]) == kinds["learned"],
          (kinds, {t: len(by_type(t)) for t in ("term", "playbook", "rejected", "rule", "app-guide", "kalshi", "research")}))
    liq = next(e for e in lib["entries"] if e["id"] == "liquidity")
    check("a. a glossary entry is its own note with the library's plain words and links back up (Glossary, Home)", liq["short"] in NOTES["Trading/Glossary/Liquidity.md"]
          and "[[Glossary]]" in NOTES["Trading/Glossary/Liquidity.md"] and "[[00 Home]]" in NOTES["Trading/Glossary/Liquidity.md"])
    # the strategy, against STRATEGY.md
    s6 = next(p for p in NOTES if p.endswith("Step 6 - the stop.md"))
    s7 = next(p for p in NOTES if p.endswith("Step 7 - the target.md"))
    check("a. strategy facts match STRATEGY.md: stop 1 tick beyond the sweep, no trade under 8 or over 80 points; target at least 1.5R, banked at 8R",
          "beyond the sweep extreme" in strat and "under 8 or over 80 points" in strat and "1 tick" in NOTES[s6] and "8 points" in NOTES[s6] and "80 points" in NOTES[s6]
          and "1.5R" in strat and "1.5R" in NOTES[s7] and "8R" in strat and "8R" in NOTES[s7], NOTES[s6][:300])
    dr = NOTES["Playbooks/Daily routine.md"]
    check("a. the day matches STRATEGY.md: entries 02:00 to 15:30 ET, flat by 15:55 (Daily routine and the After checklist)",
          "02:00" in strat and "15:30" in strat and "15:55" in strat and "02:00 to 15:30" in dr and "15:55" in NOTES["Trading/Checklists/After the session checklist.md"], dr[:300])
    check("a. the nine steps are in order with Before / Next links, and the strategy note lists all nine",
          all(f"Step {i} - " in NOTES["Trading/Zlarior LIT strategy.md"] for i in range(1, 10)) and "Next: [[Step 2 - wait for a sweep]]" in NOTES[next(p for p in NOTES if p.endswith("Step 1 - mark the levels.md"))])
    # MFFU, against research/lit/mffu_rules.json
    m = NOTES["Trading/MFFU rules that matter.md"]
    l50, l25 = rules["limits"]["builder_50k"], rules["limits"]["builder_25k"]
    want = [f"${l50['target']:,.0f}", f"${l50['mll']:,.0f}", f"${l50['dll']:,.0f}", f"{l50['max_micros']} micros", f"${l50['buffer']:,.0f}", f"${l50['pay_min']:,.0f} to ${l50['pay_max']:,.0f}",
            f"{l50['split'] * 100:.0f}%", f"{l50['inactivity_days']} calendar days", f"${l25['target']:,.0f}", f"${l25['mll']:,.0f}", f"${l25['dll']:,.0f}", f"{l25['max_micros']} micros",
            usd(rules["builder_50k"]["eval"]["price"]["value"]["owner_paid"]), usd(rules["builder_50k"]["eval"]["price"]["value"]["list"]), "16:10 ET"]
    check("a. MFFU rules that matter: every number is the one in research/lit/mffu_rules.json (target, max loss, daily limit, size, buffer, payouts, split, 7 days, 25K, prices)",
          all(w in m for w in want), [w for w in want if w not in m])
    check("a. the MFFU note keeps the caveat (re-check before the first live payout) and the 3-account cap text from plans.json", "re-check before the first live payout" in m
          and plans["strategy"]["mffu_caps"]["text"] in m)
    # money, against plutus/plans.json
    acc = NOTES["Money/Accounts plan.md"]
    rows = [f"| {k} | {usd(v['H1']['per_month'])} a month | {usd(v['H2']['per_month'])} a month |" for k, v in plans["strategy"]["by_count"].items()]
    check("a. Accounts plan: the eight account-set rows are plans.json's per-month numbers, the three accounts and the prices ($91.80, $43, $63)",
          all(r in acc for r in rows) and "$91.80" in acc and "$43" in acc and "$63" in acc, [r for r in rows if r not in acc])
    pn = NOTES["Money/Plutus numbers.md"]
    check("a. Plutus numbers: the four plans' prices and targets, the trio per month for all three spans",
          all(usd(p["price"]) in pn and usd(p["target"]) in pn for p in plans["plans"]) and all(f"${v['net_per_month']:,}" in pn for v in plans["trio"].values()), pn[:400])
    sec = NOTES["Trading/Second strategies.md"]
    a, b = {x["id"]: x for x in plans["strategy"]["accounts"]}["atlas_25k"], {x["id"]: x for x in plans["strategy"]["accounts"]}["blitz_25k"]
    check("a. Second strategies: ATLAS and BLITZ eval pass rates and monthly numbers are plans.json's", f"{a['eval_2w_pass']['H1']:g}%" in sec and f"{a['funded_per_month']['H2']:,}" in sec
          and f"{b['eval_2w_pass']['H2']:g}%" in sec and f"${b['net_per_month_from_purchase']['H2']:,}" in sec)
    # writeups carry the file's own status line
    ok_w = []
    for f, title, _ in OP.WRITEUPS:
        st = OP.parse_writeup(f)["status"]
        note = NOTES[f"Research/Writeups/{title}.md"] if f"Research/Writeups/{title}.md" in NOTES else ""
        ok_w.append(bool(note) and (st[:50] in note if st else True) and f"research/writeups/{f}" in note and os.path.exists(os.path.join(ROOT, "research", "writeups", f)))
    check("a. the seven writeup notes (Kalshi edges, LIT ideas rounds, second strategies, ATLAS, BLITZ, money plan) carry their file's own status and name their source", all(ok_w), ok_w)
    # Jarvis's own paths
    obs = rd("tools/web_public/jarvis/obsidian.js")
    me_path = re.search(r"me: '([^']+)'", obs).group(1)
    mem_path = re.search(r"memory: '([^']+)'", obs).group(1)
    tmpl = re.search(r"export const ME_TEMPLATE = `(.*?)`;", obs, re.S).group(1)
    me = NOTES[me_path]
    check("a. Jarvis's note names: the pack has 'Me' and 'Memory' at the exact paths obsidian.js reads (OLYMPUS/Jarvis/Me.md, Memory.md)", me_path == "OLYMPUS/Jarvis/Me.md" and me_path in NOTES
          and mem_path in NOTES, (me_path, mem_path))
    pos = 0
    ok_me = True
    for ln in [x for x in tmpl.splitlines() if x.strip()]:
        i = me.find(ln, pos)
        ok_me &= i >= 0
        pos = max(pos, i)
    check("a. the Me note IS Jarvis's own starter profile (every line of ME_TEMPLATE, in order), ends with 'Preferences Jarvis learned' for him to append to, and links the vault",
          ok_me and me.rstrip().endswith("## Preferences Jarvis learned") and "[[Zlarior LIT strategy]]" in me, me[-300:])
    t = NOTES["Templates/Trade journal entry.md"]
    check("a. the Trade journal entry template has the owner's fields: setup, size, plan followed, emotion, lesson (frontmatter AND headings)",
          all(re.search(rf"^{k}: ", t, re.M) for k in ("setup", "size", "plan_followed", "emotion", "lesson")) and all(h in t for h in ("## Setup", "## Size", "## Plan followed?", "## Emotion", "## Lesson")))
    check("a. the five templates exist: Daily note, Trade journal entry, Weekly review, Kalshi bet review, Idea note",
          all(f"Templates/{n}.md" in NOTES for n in ("Daily note", "Trade journal entry", "Weekly review", "Kalshi bet review", "Idea note")))
    check("a. the Playbooks cover what to do when: a loss, inactivity, an eval fail, a payout", all(f"Playbooks/{n}.md" in NOTES for n in ("When I have a loss",))
          and any("inactiv" in p.lower() or "idle" in p.lower() or "7 days" in NOTES[p] for p in NOTES if p.startswith("Playbooks/"))
          and any(("fail" in p.lower()) for p in NOTES if p.startswith("Playbooks/")) and any(("payout" in p.lower()) for p in NOTES if p.startswith("Playbooks/")), [p for p in NOTES if p.startswith("Playbooks/")])
    goals = [p for p in NOTES if re.search(r"\bgoals?\b", TITLE(p), re.I)]
    check("a. a Goals note exists (Jarvis finds goals by the word in a title, tag or heading) and says the owner's goals (eval in 2 weeks, 2-4 trades a week)",
          goals and "within 2 weeks" in NOTES["Goals.md"] and "2 to 4 trades a week" in NOTES["Goals.md"], goals)


def TITLE(p):
    return p.rsplit("/", 1)[-1][:-3]


# ============================================================================================== b. links and frontmatter
def links():
    bad, out, inbound = [], {}, Counter()
    for p, t in NOTES.items():
        tg = []
        for raw in LINK.findall(t):
            name = raw.strip()
            tgt = TITLES.get(name) or (name + ".md" if name + ".md" in NOTES else None)
            if not tgt:
                bad.append((p, name))
            else:
                tg.append(tgt)
        out[p] = tg
        for x in set(tg):
            if x != p:
                inbound[x] += 1
    check("b. EVERY [[wikilink]] resolves to a note (by name or path)", not bad, bad[:8])
    total = sum(len(v) for v in out.values())
    check(f"b. the graph is dense: {total} links over {len(NOTES)} notes (at least 4 a note on average)", total >= 4 * len(NOTES), total / len(NOTES))
    orphans = [p for p in NOTES if inbound[p] == 0 and p != "00 Home.md"]
    check("b. no orphan: every note except the Home has at least one note linking to it", not orphans, orphans[:8])
    seen, q = {"00 Home.md"}, deque(["00 Home.md"])
    while q:
        for n in out[q.popleft()]:
            if n not in seen:
                seen.add(n)
                q.append(n)
    check("b. the whole vault is reachable by clicking from 00 Home", len(seen) == len(NOTES), sorted(set(NOTES) - seen)[:8])
    check("b. every note links somewhere (no dead ends) and the Home links every hub", all(out[p] for p in NOTES)
          and all(h in out["00 Home.md"] for h in ("Trading/Trading hub.md", "Playbooks/Playbooks.md", "Research/Research hub.md", "Money/Money hub.md", "Templates/Templates.md", "OLYMPUS/Apps/OLYMPUS apps.md")))
    nofm = [p for p, t in NOTES.items() if not t.startswith("---\n")]
    check("b. every note starts with frontmatter", not nofm, nofm[:5])
    notags = [p for p, t in NOTES.items() if not re.search(r"^tags: \[.+\]$", t.split("\n---\n")[0], re.M)]
    check("b. every note has tags in its frontmatter (tags: [a, b], the form Jarvis and Obsidian both read)", not notags, notags[:5])
    hubs = [p for p in NOTES if "type: moc" in NOTES[p][:60]]
    check("b. maps of content (type: moc) exist for every area, each listing at least 5 notes", len(hubs) >= 10 and all(len(out[h]) >= 3 for h in hubs if h != "Trading/Checklists/Trading checklists.md"), [(h, len(out[h])) for h in hubs])
    names = [TITLE(p).lower() for p in NOTES]
    check("b. note names are unique and plain (no characters Obsidian links choke on), under 90 characters", len(set(names)) == len(names) and all(not re.search(r'[\\/:*?"<>|#^\[\]]', TITLE(p)) and len(TITLE(p)) < 90 for p in NOTES))


# ============================================================================================== c. safety and Jarvis compatibility
def safety():
    hits = []
    for p, t in NOTES.items():
        why = BI._first(BI.SECRETS, t)
        if why:
            hits.append((p, why))
        for pat, w in ((r"\b\d{9,}\b", "a long number"), (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[a-z]{2,}", "an email"), (r"[A-Z]:\\Users\\", "a local path"),
                       (r"/home/[a-z]+/", "a local path"), (r"\b(?:MFFU|PAMFFU|EVAL|FUNDED|SIM)[A-Z]*\d{4,}\b", "an account id"), (r"(?i)\b(?:password|passwd)\s*[:=]\s*\S+", "a password"),
                       (r"(?i)Bearer\s+[A-Za-z0-9._-]{16,}", "a bearer token"), (r"\b(?:\d[ -]?){13,19}\b", "a card number")):
            if re.search(pat, t):
                hits.append((p, w))
    check("b. SAFETY: no secret-like string (the Bridge scanner's patterns), no long numbers / emails / local paths / account ids / passwords / card numbers in any note", not hits, hits[:6])
    tasks = [(p, ln) for p, t in NOTES.items() for ln in t.splitlines() if re.match(r"^\s*[-*+]\s+\[([ xX/-])\]\s+(.+)$", ln)]
    check("c. Jarvis would list every '- [ ]' line as his task: the pack has none (checklists are numbered lists; the templates only describe the form)", not tasks, tasks[:4])
    dated = [p for p in NOTES if re.search(r"(^|[^0-9])20\d\d-\d\d-\d\d([^0-9]|$)", TITLE(p))]
    check("c. no file is named with a date (Jarvis treats those as the owner's daily notes): the Daily note is a template", not dated, dated)
    check("c. the accounts are 'the 50K' / 'the 25K' / Builder plan names only (no account numbers anywhere); the public eval names appear", "Builder 50K" in NOTES["Trading/MFFU rules that matter.md"]
          and not any(re.search(r"\b\d{6,}\b", t) for t in NOTES.values()))
    check("c. the paper-only rule is stated (never arm live for the owner) and no note tells the reader to place real orders", any("Paper" in t or "paper" in t for t in NOTES.values())
          and "Never arm live trading" in NOTES["Trading/Checklists/Never checklist.md"])
    j = NOTES["OLYMPUS/Jarvis/How Jarvis reads this vault.md"]
    obs = rd("tools/web_public/jarvis/obsidian.js")
    check("c. 'How Jarvis reads this vault' matches obsidian.js: inbox / notes / logs paths, appends only, tasks, goals, daily notes in a Daily folder",
          all(x in obs for x in ("OLYMPUS/Inbox", "OLYMPUS/Notes", "OLYMPUS/Logs")) and all(x in j for x in ("OLYMPUS/Inbox", "OLYMPUS/Notes", "OLYMPUS/Logs", "appends", "Goals", "Daily")) and "journal|dailies" in obs.replace("(daily|journal|dailies", "journal|dailies"))


# ============================================================================================== d. the build
def build():
    pack, man = OP.build()
    pack2, _ = OP.build()
    check("d. the build is deterministic (no clock, no randomness): two builds are identical", pack == pack2)
    data = OP.dump(pack, man)
    stale = [n for n, d in data.items() if open(os.path.join(STARTER, n), encoding="utf-8", newline="").read() != d]
    check("d. the committed starter_pack.json, starter_pack.js and manifest.json equal a fresh build (run python tools/obsidian_pack.py after the sources change)", not stale, stale)
    js = open(os.path.join(STARTER, "starter_pack.js"), encoding="utf-8").read()
    m = re.search(r"export default (\{.*\});\s*$", js, re.S)
    check("d. starter_pack.js is the same notes as starter_pack.json (one default export, loaded on demand)", m and json.loads(m.group(1)) == PACK and js.count("export default") == 1)
    man2 = json.load(open(os.path.join(STARTER, "manifest.json"), encoding="utf-8"))
    check("d. the manifest lists every note once (path, title, type, tags, words, links) and its counts match", [n["path"] for n in man2["notes"]] == sorted(NOTES) and man2["counts"]["notes"] == len(NOTES)
          and man2["counts"]["links"] == sum(len(LINK.findall(t)) for t in NOTES.values()) and sum(man2["counts"]["folders"].values()) == len(NOTES) and man2["sha"] == PACK["sha"]
          and all(s in OP.SRC.values() or s.startswith("research/writeups/") for s in man2["sources"]) and all(os.path.exists(os.path.join(ROOT, s)) for s in man2["sources"]))
    z = OP.zip_bytes(PACK)
    zf = zipfile.ZipFile(io.BytesIO(z))
    names = zf.namelist()
    check("d. the python zip (obsidian_pack.zip for the build) is valid, store-only, every note under 'OLYMPUS Starter Vault/', contents equal the notes",
          zf.testzip() is None and len(names) == len(NOTES) and all(i.compress_type == 0 for i in zf.infolist()) and all(n.startswith("OLYMPUS Starter Vault/") for n in names)
          and all(zf.read("OLYMPUS Starter Vault/" + p).decode("utf-8") == t for p, t in NOTES.items()))
    check("d. the zip is the same bytes every time", OP.zip_bytes(PACK) == z)
    d = tempfile.mkdtemp(prefix="le_op_")
    try:
        msg = OP.publish(d)
        check("d. publish(out_dir) writes the three files and obsidian_pack.zip under mind/starter/", all(os.path.exists(os.path.join(d, "mind", "starter", n)) for n in
              ("starter_pack.json", "starter_pack.js", "manifest.json", "obsidian_pack.zip")) and "notes" in msg, msg)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "obsidian_pack.py"), "--check"], capture_output=True, text=True, timeout=120)
    check("d. 'obsidian_pack.py --check' says the committed pack is up to date (exit 0)", r.returncode == 0, r.stdout + r.stderr)
    sz = os.path.getsize(os.path.join(STARTER, "starter_pack.js"))
    check(f"d. the module the page loads is under 400 KB ({sz // 1024} KB)", sz < 400 * 1024)


# ============================================================================================== e. the JS side, in node
NODE_JS = r"""
import fs from 'node:fs';
import { zipStore, bundleMarkdown, folderGroups, preview, loadPack } from '__MIND__/starter.js';
const out = process.argv[2];
const pack = await loadPack();
const notes = pack.notes;
fs.writeFileSync(out + '/pack.zip', zipStore(notes));
fs.writeFileSync(out + '/one.zip', zipStore([{ path: 'a.txt', text: '123456789' }], ''));
fs.writeFileSync(out + '/uni.zip', zipStore([{ path: 'Ünï/çode ✓.md', text: 'héllo ✓ wörld' }, { path: 'empty.md', text: '' }, { path: 'b/c.md', text: 'x'.repeat(70000) }], 'R/'));
const md = bundleMarkdown(notes);
fs.writeFileSync(out + '/bundle.md', md);
const g = folderGroups(notes);
const home = notes.find((n) => n.path === '00 Home.md');
const res = { n: notes.length, sha: pack.sha, groups: g.map((x) => [x.folder, x.notes.length]), sorted: g.every((x) => x.notes.every((n, i) => !i || x.notes[i - 1].title <= n.title)),
  pv: preview(home), pv2: preview({ text: '---\ntags: [a]\n---\n# T\n> **bold** [[A|a]] and [[B]]\n' + 'word '.repeat(300) }, 50), first: g[0].folder,
  tags: g.flatMap((x) => x.notes).find((n) => n.path === 'Trading/Risk rules.md').tags, again: (await loadPack()) === pack };
console.log(JSON.stringify(res));
"""


def node_side():
    node = shutil.which("node")
    if not node:
        print("[SKIP] node parts: node not found")
        return
    d = tempfile.mkdtemp(prefix="le_op_js_")
    try:
        f = os.path.join(d, "t.mjs")
        open(f, "w", encoding="utf-8").write(NODE_JS.replace("__MIND__", "file://" + MIND))
        r = subprocess.run([node, f, d], capture_output=True, text=True, timeout=120)
        if not check("e. node runs starter.js (zipStore, bundleMarkdown, folderGroups, preview, loadPack) without error", r.returncode == 0 and r.stdout.strip(), r.stderr[-600:]):
            return
        res = json.loads(r.stdout.strip().splitlines()[-1])
        check("e. loadPack() imports the starter module (cached: the second call is the same object) and has every note", res["n"] == len(NOTES) and res["again"] and res["sha"] == PACK["sha"], res["n"])
        one = open(os.path.join(d, "one.zip"), "rb").read()
        crc = int.from_bytes(one[14:18], "little")
        zo = zipfile.ZipFile(io.BytesIO(one))
        check("e. CRC-32 of '123456789' is the standard check value 0xCBF43926 (local header and central directory), the stored size equals the text",
              crc == 0xCBF43926 and zo.testzip() is None and zo.namelist() == ["a.txt"] and zo.read("a.txt") == b"123456789" and zo.infolist()[0].CRC == 0xCBF43926 and zo.infolist()[0].file_size == 9, hex(crc))
        zu = zipfile.ZipFile(io.BytesIO(open(os.path.join(d, "uni.zip"), "rb").read()))
        infos = {i.filename: i for i in zu.infolist()}
        check("e. UTF-8 names (flag bit 11) and text round-trip; an empty file has CRC 0; a 70,000-byte file is fine; no entry is compressed",
              zu.testzip() is None and "R/Ünï/çode ✓.md" in infos and zu.read("R/Ünï/çode ✓.md").decode() == "héllo ✓ wörld" and infos["R/empty.md"].CRC == 0 and zu.read("R/empty.md") == b""
              and infos["R/b/c.md"].file_size == 70000 and all(i.compress_type == 0 and i.flag_bits & 0x800 for i in zu.infolist()), list(infos))
        z = zipfile.ZipFile(os.path.join(d, "pack.zip"))
        got = {n[len("OLYMPUS Starter Vault/"):]: z.read(n).decode("utf-8") for n in z.namelist()}
        check("e. the JS zip of the whole pack opens with python's zipfile: testzip() clean, every note byte for byte, sorted, under 'OLYMPUS Starter Vault/'",
              z.testzip() is None and got == NOTES and z.namelist() == sorted(z.namelist()) and all(i.compress_type == 0 for i in z.infolist()), len(got))
        unz = os.path.join(d, "unz")
        z.extractall(unz)
        check("e. extracting the zip gives the folder tree (files on disk, one folder 'OLYMPUS Starter Vault')", os.listdir(unz) == ["OLYMPUS Starter Vault"]
              and os.path.exists(os.path.join(unz, "OLYMPUS Starter Vault", "00 Home.md")) and os.path.isdir(os.path.join(unz, "OLYMPUS Starter Vault", "Trading", "Glossary")))
        ti = subprocess.run(["unzip", "-tq", os.path.join(d, "pack.zip")], capture_output=True, text=True) if shutil.which("unzip") else None
        if ti is not None:
            check("e. the system 'unzip -t' agrees the zip is fine", ti.returncode == 0 and "No errors" in ti.stdout, ti.stdout[-200:])
        md = open(os.path.join(d, "bundle.md"), encoding="utf-8").read()
        parts = re.split(r"<!-- file: (.+?) -->\n\n", md)
        back = {parts[i]: parts[i + 1].rsplit("\n---\n", 1)[0].rstrip() if i + 2 < len(parts) else parts[i + 1].rstrip() for i in range(1, len(parts), 2)}
        check("e. the one-file markdown starts with a title and the count, and splits back into every note at its 'file:' marker",
              md.startswith(f"# OLYMPUS Starter Vault ({len(NOTES)} notes)") and set(back) == set(NOTES) and all(back[p].rstrip() == NOTES[p].rstrip() for p in NOTES))
        check("e. folderGroups: every folder with its notes (Top first), notes sorted by name, tags read from the frontmatter", res["first"] == "Top" and sum(c for _, c in res["groups"]) == len(NOTES)
              and res["sorted"] and "trading" in res["tags"] and ["Trading", sum(1 for p in NOTES if p.startswith("Trading/"))] in res["groups"], res["groups"])
        check("e. preview(): no frontmatter, no markup, no [[brackets]], cut at the word with '...'", "---" not in res["pv"] and "[[" not in res["pv"] and "#" not in res["pv2"] and "**" not in res["pv2"]
              and res["pv2"].startswith("T bold a and B word") and res["pv2"].endswith("...") and len(res["pv2"]) <= 54 and len(res["pv"]) <= 424, (res["pv"][:100], res["pv2"]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ============================================================================================== the page's static rules
def static_page():
    st = open(os.path.join(MIND, "starter.js"), encoding="utf-8").read()
    pn = open(os.path.join(MIND, "panels.js"), encoding="utf-8").read()
    dt = open(os.path.join(MIND, "data.js"), encoding="utf-8").read()
    dm = open(os.path.join(MIND, "demo.js"), encoding="utf-8").read()
    code = re.sub(r"//.*", "", st)
    check("f. starter.js: no network API, no storage, no markup, no keys (the page never writes into a vault), no outside URL; Safari-16 ES2020 (no import statements)",
          not re.search(r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|innerHTML|insertAdjacentHTML|document\.|https?://|token|secret|password", code, re.I)
          and not re.search(r"^import ", st, re.M))
    check("f. panels.js imports the five functions in one line and the Teach page builds the Starter pack card (3 steps, Download as .zip, Copy as one markdown file)",
          "import { loadPack, zipStore, bundleMarkdown, folderGroups, preview } from './starter.js';" in pn and "Download as .zip" in pn and "Copy as one markdown file" in pn
          and pn.count("<li") == 0 and "starter.root" in pn and "starter.init()" in pn)
    check("f. data.js adds the pack to the demo brain once, only when the demo is shown (never in live mode); demo.js has addPack", "demo.addPack(pk)" in dt and "if (!packed)" in dt
          and "addPack(pack)" in dm and "function packInto" in dm)
    tm = open(os.path.join(ROOT, "tests", "test_mind_page.py"), encoding="utf-8").read()
    check("f. tests/test_mind_page.py checks starter.js with the other modules (no dead exports, no network API)", '"starter.js"' in tm)


# ============================================================================================== f. the page, in Chromium
def browser():
    import glob
    import http.server
    import threading
    from tests import test_mind_page as M
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), M.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_port}"
    from playwright.sync_api import sync_playwright
    M.MOCK["js"] = None
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        try:
            ctx, p, log = M.new_page(br, origin, (390, 844))
            ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            p.goto(origin + "/mind/?q=off&home=1")
            M.ready(p)
            p.wait_for_function(f"mind.stats.notes > {len(NOTES)}", timeout=20000)
            st = p.evaluate("({mode: mind.mode, notes: mind.stats.notes, links: mind.stats.links, clusters: mind.stats.clusters})")
            check(f"f. the demo brain holds the pack: {st['notes']} notes, {st['links']} links, {st['clusters']} galaxies (the old fake notes are still there)",
                  st["mode"] == "demo" and st["notes"] > len(NOTES) + 80 and st["links"] > 900 and st["clusters"] >= 8, st)
            p.fill("#q", "Zlarior LIT")
            p.wait_for_selector("#results li[data-id]", timeout=5000)
            first_hit = p.get_attribute("#results li[data-id]", "data-id")
            p.press("#q", "Enter")
            p.wait_for_function("mind.focus === 'Trading/Zlarior LIT strategy.md'", timeout=5000)
            p.wait_for_selector("#card", state="visible")
            check("f. a pack note is searchable in the demo brain and opens a card with its preview (Zlarior LIT strategy: the nine steps)",
                  first_hit == "Trading/Zlarior LIT strategy.md" and "nine steps" in p.inner_text("#card").lower(), (first_hit, p.inner_text("#card")[:200]))
            p.keyboard.press("Escape")
            M.open_panel(p, "teach")
            p.wait_for_selector("#starter .st-group", timeout=10000)
            txt = p.inner_text("#starter")
            check("f. Teach page: the Starter pack card says how many notes and links, has the 3 plain steps (download, open in Obsidian, open Home / connect Jarvis)",
                  f"{len(NOTES)} notes" in txt and p.locator("#starter ol li").count() == 3 and "Files app" in txt and "Open folder as vault" in txt and "00 Home" in txt, txt[:500])
            n_folders = len({(x.split("/")[0] if "/" in x else "Top") for x in NOTES})
            check("f. the folder list: one group per folder with its count; nothing is built until a group opens", p.locator("#starter .st-group").count() == n_folders and p.locator("#starter .st-row").count() == 0)
            p.click("#starter .st-group:has-text('Playbooks') summary")
            p.wait_for_selector("#starter .st-row")
            first = p.locator("#starter .st-row").first
            first.click()
            pv = p.locator("#starter .st-pv:not([hidden])")
            check("f. a group opens its notes; tapping a note shows its preview as plain words (no markup, no frontmatter)", pv.count() == 1 and len(pv.first.inner_text()) > 40 and "[[" not in pv.first.inner_text()
                  and "---" not in pv.first.inner_text() and first.get_attribute("aria-expanded") == "true", pv.first.inner_text()[:100])
            with p.expect_download(timeout=20000) as dl:
                p.click("#st-zip")
            path = dl.value.path()
            z = zipfile.ZipFile(path)
            got = {n[len("OLYMPUS Starter Vault/"):]: z.read(n).decode("utf-8") for n in z.namelist()}
            check("f. Download as .zip: a real file 'OLYMPUS Starter Vault.zip' of ALL notes, valid, byte for byte the pack", dl.value.suggested_filename == "OLYMPUS Starter Vault.zip" and z.testzip() is None and got == NOTES, dl.value.suggested_filename)
            check("f. a message says how many notes were downloaded", "Downloaded %d notes" % len(NOTES) in p.inner_text("#starter"))
            p.click("#st-md")
            p.wait_for_function("document.querySelector('#starter .msg').textContent.includes('Copied')", timeout=5000)
            clip = p.evaluate("navigator.clipboard.readText()")
            check("f. Copy as one markdown file: the clipboard holds the whole vault as one text with a file marker for every note", clip.startswith(f"# OLYMPUS Starter Vault ({len(NOTES)} notes)")
                  and clip.count("<!-- file: ") == len(NOTES) and "<!-- file: 00 Home.md -->" in clip, clip[:120])
            ls = p.evaluate("(() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k).length; } return o; })()")
            check("f. nothing was written to storage by the pack (only the page's own 'mind.' keys and the kit's 3D quality, no Jarvis key), nothing was sent anywhere", all(k.startswith("mind.") or k == "jfx" for k in ls) and not M.OUTSIDE
                  and p.evaluate("(window.__net || []).filter((u) => !/starter_pack|obsidian\\.js/.test(u)).length") == 0, (ls, M.OUTSIDE, p.evaluate("window.__net")))
            check("f. no sideways scroll at 390 px, the card's buttons are at least 44 px tall", p.evaluate("document.scrollingElement.scrollWidth <= innerWidth")
                  and all(p.evaluate(f"document.querySelector('{s}').getBoundingClientRect().height") >= 44 for s in ("#st-zip", "#st-md")))
            check("f. no console errors or page errors on the way", not M.real_errors(log), M.real_errors(log))
            ctx.close()
            # an older site without the pack: the card says so, nothing breaks
            ctx, p, log = M.new_page(br, origin, (390, 844))
            ctx.route("**/mind/starter/starter_pack.js*", lambda r: r.fulfill(status=404, body="not here"))
            p.goto(origin + "/mind/?q=off&home=1")
            M.ready(p)
            M.open_panel(p, "teach")
            p.wait_for_function("document.querySelector('#starter .sub').textContent.includes('not on this site')", timeout=8000)
            st2 = p.evaluate("({n: mind.stats.notes, mode: mind.mode, dis: document.getElementById('st-zip').disabled})")
            check("f. without the pack file: the demo brain is the old one (no break), the card says 'not on this site yet' and the buttons stay off",
                  st2["mode"] == "demo" and 80 < st2["n"] < 200 and st2["dis"], st2)
            errs = [e for e in M.real_errors(log) if "starter_pack" not in e and "404" not in e]
            check("f. ... and no page error", not errs, errs)
            ctx.close()
        finally:
            br.close()
            srv.shutdown()


def main():
    facts()
    links()
    safety()
    build()
    node_side()
    static_page()
    if "--no-browser" not in sys.argv:
        browser()
    n = sum(RES)
    print(f"\nobsidian pack: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
