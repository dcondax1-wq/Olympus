"""THE OLYMPUS HERALD (tools/web_public/herald/, AGORA look, 2026-11-11) and its builder tools/herald_build.py: a daily newspaper written only from what OLYMPUS publishes.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the demo edition, the builder (--check, --selftest, stdlib, offline), the new_apps row
  b. the honesty checks: EVERY number printed in every article of the committed edition (and of the demo) is one of its facts, and every fact is found in the file it names
     (a value at its place, a quote word for word, a count recomputed here); the page's own audit (node) agrees; the same files and date give the same bytes; missing data = no story
  c. Chromium 390 x 844 and 375 x 667: the front page, the newsstand (WebGL scroll / flat), tap a story, where the numbers come from, share as text, read it to me (off by default),
     older / newer editions by button and by swipe, the quiz, interviews with portraits or initials, honest marks, an empty edition -> the demo, taps >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_herald_page            (--static: parts a and b only)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_herald_page
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from tests import agora_kit as AK  # noqa: E402
import herald_build as HB  # noqa: E402

APP, NAME = "herald", "Herald"
check = AK.check
D = os.path.join(AK.WEB, APP)


def edition():
    return json.load(open(os.path.join(D, "edition.json"), encoding="utf-8"))


def arts(ed):
    return ([ed["lead"]] if ed.get("lead") else []) + ed.get("articles", [])


def test_static():
    AK.static_kit(APP, NAME, reads=("./edition.json", "./editions/index.json"))
    js, core, scene, html, css = (AK.read(os.path.join(D, n)) for n in ("herald.js", "heraldcore.js", "heraldscene.js", "index.html", "herald.css"))
    check("a. a past edition can only be asked for by its date (safeDate before the fetch); two fetch calls in all; nothing is stored", "if (!C.safeDate(date)) return null" in js and len(re.findall(r"\bfetch\(", js)) == 2 and not re.search(r"localStorage|sessionStorage|indexedDB", js + core), None)
    check("a. the 3D scene: a marble newsstand from three (local copy), WebGL optional (returns null -> the flat scroll), draws only while the scroll moves, no bloom or composer",
          "../jarvis/three.module.min.js" in scene and "createStand" in js and "return null" in scene and "drawFlat" in js and "if (!moving && !dirty) return" in scene and not re.search(r"Bloom|EffectComposer|innerHTML|eval\(", scene), None)
    ids = ('id="stand"', 'id="older"', 'id="newer"', 'id="readMe"', 'id="mastTitle"', 'id="built"', 'id="lead"', 'id="stories"', 'id="numbers"', 'id="wx"', 'id="corrections"', 'id="classifieds"', 'id="quiz"', 'id="interviews"',
           'id="skipped"', 'id="reader"', 'id="rFacts"', 'id="rShare"', 'id="rSpeak"')
    check("a. the page has every part: newsstand, older / newer, read it to me, masthead, 'edition built', lead, stories, by the numbers, weather, corrections, classifieds, quiz, interviews, not-written list, the reader with facts, share and voice",
          all(x in html for x in ids), [x for x in ids if x not in html])
    check("a. a real newspaper grid that falls to one column on a phone: CSS columns with rules, a drop cap, a double rule under the masthead, serif headlines", "column-width: 270px" in css and "column-rule: 1px solid" in css and "::first-letter" in css
          and "3px double" in css and "var(--ag-serif)" in css and "break-inside: avoid" in css, None)
    check("a. 'Read it to me' is off by default and uses the phone's own voice (speechSynthesis); portraits come from the optional people kit, with initials as the fallback",
          'aria-pressed="false">Read it to me: off' in html and "speechSynthesis" in js and "voice: false" in js and "OLYMPUS_PEOPLE" in js and "portrait(id, 44)" in js and "C.initials(name)" in js and "../olympus/people.js" in html, None)
    src = AK.read(os.path.join(ROOT, "tools", "herald_build.py"))
    check("a. the builder is stdlib only and offline (no network module, no engine / bot import); git is optional and only feeds the 'shipped' list",
          not re.search(r"^\s*(?:import|from)\s+(?:urllib|requests|http|socket|ccxt|ninja|engine|numpy|pandas)", src, re.M) and "git is never required" in src and 'e.pop("press", None)' in src, None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = HB.selftest()
    check("a. python tools/herald_build.py --selftest passes (audit, a full sample newsroom, determinism, missing data, new apps, the 14-edition archive, --check)", rc == 0, buf.getvalue()[-900:])
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "herald_build.py"), "--check"], capture_output=True, text=True)
    check("a. python tools/herald_build.py --check: the committed edition.json and fixture.json are what the builder writes now for that date", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    ed = edition()
    n = len(arts(ed))
    check(f"a. the committed edition: a lead and 6 to 10 stories in all ({n}), each with a headline, a standfirst and 3 to 6 sentences; masthead with date and number; the archive has it too",
          6 <= n <= 11 and all(a["headline"] and a["standfirst"] and 3 <= len(a["body"]) <= 6 for a in arts(ed)) and ed["masthead"]["title"] == "The Olympus Herald" and ed["number"] >= 1
          and os.path.isfile(os.path.join(D, "editions", ed["date"] + ".json")) and ed["date"] in [e["date"] for e in json.load(open(os.path.join(D, "editions", "index.json"), encoding="utf-8"))["editions"]], n)
    check("a. the boxes are there: by the numbers, corrections, classifieds (marked sample: Mercury's file here is its fixture), weather (calm / busy / careful), a 3-question quiz, 3 interviews with persona ids",
          len(ed["numbers"]) >= 4 and len(ed["corrections"]) >= 2 and ed["classifieds"]["sample"] is True and ed["classifieds"]["items"] and ed["weather"]["level"] in ("calm", "busy", "careful") and len(ed["quiz"]) == 3
          and len(ed["interviews"]) == 3 and all(re.match(r"^(mind|scanner:[a-z]+|builder:[a-z0-9]{8}|bot:[a-z]+)$", i["id"]) for i in ed["interviews"]), [i["id"] for i in ed["interviews"]])
    check("a. stories whose file is not in the repo copy (home.json, money/index.json) are NOT written and the edition says why", {"bots", "money"} <= {s["article"] for s in ed["skipped"]} and all("site build" in s["why"] for s in ed["skipped"] if s["article"] in ("bots", "money"))
          and "home.json" in ed["sources"]["missing"], ed["skipped"])
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    check("a. the demo edition is a full paper (lead + 9 stories, every box) and is marked demo inside the edition too", fx["edition"]["demo"] is True and len(fx["edition"]["articles"]) == 9 and fx["edition"]["weather"] and fx["edition"]["classifieds"]["items"] and "DEMO" in fx["edition"]["label"], None)
    apps = json.load(open(os.path.join(ROOT, "tools", "new_apps.json"), encoding="utf-8"))["apps"]
    row = next((a for a in apps if a["id"] == APP), None)
    scenes = "stars smoke coins embers neurons skyline torches threads streaks bars leaves columns shards rings maze".split()
    check("a. the row in tools/new_apps.json (an existing intro scene, a description under 80 characters) and the wiring section with the build line", row is not None and row["name"] == NAME and len(row["description"]) < 80 and row["flavour"][0] in scenes
          and "# Wiring HERALD" in AK.read(os.path.join(ROOT, "docs", "NEW_APPS_WIRING.md")) and "python tools/herald_build.py --web site" in AK.read(os.path.join(ROOT, "docs", "NEW_APPS_WIRING.md")), row)


# ------------------------------------------------------------------------------------------------ b. every number has a source
def source_path(rel, root=ROOT, web=AK.WEB):
    p = os.path.join(root, rel)
    return p if rel.startswith(("handoff/", "research/")) else os.path.join(web, rel)


def squash(s):
    return re.sub(r"\s+", " ", s).strip()


def strings_of(node, out):
    if isinstance(node, str):
        out.append(squash(node))
    elif isinstance(node, dict):
        for k, v in node.items():
            out.append(k)
            strings_of(v, out)
    elif isinstance(node, list):
        for v in node:
            strings_of(v, out)
    elif node is not None and not isinstance(node, bool):
        out.append(str(node))
    return out


def recount(how, src, date, root=ROOT, web=AK.WEB, prev_apps=None):
    """An independent recount of every 'worked out' fact, by its plain-words recipe. None = unknown recipe (a failure)."""
    p = source_path(src, root, web)
    if how == "count of kalshi_edge_*.md write-ups read":
        return len([f for f in os.listdir(os.path.join(root, "research", "writeups")) if re.match(r"kalshi_edge_.*\.md$", f)])
    if src == "jarvis/apps.js":
        ids = set(re.findall(r"app\('([a-z0-9_]+)',\s*'[^']*'", open(p, encoding="utf-8").read()))
        return len(ids) if how == "count of app ids in jarvis/apps.js" else len(ids - set(prev_apps or [])) if how == "count of app ids not in the last edition's list" else None
    doc = json.load(open(p, encoding="utf-8"))
    if how == "count of agents":
        return len(doc["agents"])
    if how == "count of different areas":
        return len({a["area"] for a in doc["agents"] if a.get("area")})
    if how == "count of items with verdict stop":
        return sum(1 for i in doc["items"] if i.get("verdict") == "stop")
    if how == "count of accounts with a P&L today":
        return sum(1 for a in doc["accounts"] if isinstance((a.get("pnl") or {}).get("today"), (int, float)))
    if how == "sum of pnl/today over the accounts named":
        return round(sum(a["pnl"]["today"] for a in doc["accounts"] if isinstance((a.get("pnl") or {}).get("today"), (int, float))), 2)
    if src == "archive/index.json":
        cols, verd = doc["cols"], doc["verdicts"]
        bi, vi = cols.index("built"), cols.index("verdict")
        newest = max(str(r[bi]) for r in doc["runs"])
        todays = [r for r in doc["runs"] if str(r[bi]) == newest]
        if how == "count of runs in the index with the newest built stamp":
            return len(todays)
        m = re.match(r"count of those with verdict (\w+)$", how)
        if m:
            return sum(1 for r in todays if verd[r[vi]] == m.group(1))
    return None


def verify(ed, root=ROOT, web=AK.WEB, prev_apps=None):
    """[(article, problem)] for an edition: stray numbers, values that are not at their place, quotes that are not in the file, counts that do not recount."""
    bad, n_val, n_quote, n_calc = [], 0, 0, 0
    cache = {}
    for a in arts(ed):
        for t in HB.audit(a):
            bad.append((a["id"], f"number {t} has no fact"))
        for f in a["facts"]:
            p = source_path(f["src"], root, web)
            if f["src"] not in a["sources"] or not os.path.isfile(p):
                bad.append((a["id"], f"source {f['src']} missing"))
                continue
            if p not in cache:
                raw = open(p, encoding="utf-8").read()
                doc = json.loads(raw) if p.endswith(".json") else None
                cache[p] = (raw, doc, set(strings_of(doc, [])) if doc is not None else None)
            raw, doc, strs = cache[p]
            if "at" in f:
                n_val += 1
                got = HB.at(doc, f["at"])
                shown = {HB.money(got), HB.num(got), HB.pct(got), ("+" if got > 0 else "") + f"{got:.2f}R"} if isinstance(got, (int, float)) and not isinstance(got, bool) else {str(got)}
                if got != f["raw"] or f["t"] not in shown:
                    bad.append((a["id"], f"value {f['t']} is not what {f['src']} holds at {f['at']} ({got!r})"))
            elif f.get("quote"):
                n_quote += 1
                q = squash(f["t"]).rstrip("…").rstrip()
                plain = squash(re.sub(r"[*`]", "", raw))
                if not (any(q in s for s in strs) if strs is not None else q in plain):
                    bad.append((a["id"], f"quote not found in {f['src']}: {q[:60]}"))
            else:
                n_calc += 1
                want = recount(f["calc"], f["src"], ed["date"], root, web, prev_apps)
                if want is None or want != f["raw"] or f["t"] not in (HB.num(want), HB.money(want)):
                    bad.append((a["id"], f"count '{f['calc']}' = {want!r}, the paper printed {f['t']}"))
    return bad, (n_val, n_quote, n_calc)


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const ed = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), fx = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).edition, out = {};
  const all = (e) => (e.lead ? [e.lead] : []).concat(e.articles);
  out.audit = all(ed).map((a) => [a.id, C.audit(a)]); out.auditDemo = all(fx).map((a) => [a.id, C.audit(a)]);
  const bad = JSON.parse(JSON.stringify(ed.lead)); bad.body.push('Then 4,242 more turned up, 77.5% of them late.'); out.stray = C.audit(bad);
  out.tokens = C.tokens('1,836 buys at 4.7% on 2026-11-10, -$248.30');
  const n = C.normalizeEdition(ed), d = C.normalizeEdition(fx);
  out.norm = [n.date, n.number, C.allArticles(n).length, n.lead.facts.length > 0, n.lead.facts[0].kind, n.quiz.length, n.interviews.length, n.weather.level, n.classifieds.sample, n.skipped.length, C.printable(n), d.demo, C.allArticles(d).length];
  out.junk = [C.normalizeEdition(null), C.normalizeEdition({ date: 'tomorrow' }), C.normalizeEdition([1]), C.printable(C.normalizeEdition({ date: '2026-11-11' })),
    C.normalizeEdition({ date: '2026-11-11', lead: { id: 'x', headline: 'h', body: ['one', 'two'] } }).lead, C.normalizeEdition({ date: '2026-11-11', weather: { level: 'stormy' }, quiz: [{ q: 'q', o: ['a'], a: 0 }, { q: 'q', o: ['a', 'b'], a: 5 }], number: 'x' }).weather,
    C.normalizeEdition({ date: '2026-11-11', quiz: [{ q: 'q', o: ['a'], a: 0 }, { q: 'q', o: ['a', 'b'], a: 5 }, { q: 'ok', o: ['a', 'b'], a: 1 }] }).quiz.length];
  const long = { date: '2026-11-11', lead: { id: 'x', headline: 'H'.repeat(900), standfirst: 's', body: ['a\u0007b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'], facts: [{ t: 5, src: 'f.json', calc: 'count' }, { t: 'q', src: 'f.md', quote: true }, { t: '1', src: 'f.json', at: 'a/b' }] } };
  const ln = C.normalizeEdition(long).lead; out.clip = [ln.headline.length, ln.body.length, ln.body[0], ln.facts.map((f) => f.kind + ':' + f.how)];
  const text = C.articleText(n.lead, n); out.share = [text.split('\n')[0], text.indexOf(n.lead.headline.toUpperCase()) > 0, n.lead.body.every((b) => text.indexOf(b) > 0), /Sources: /.test(text), C.articleText(d.lead, d).split('\n')[0]];
  const sp = C.speechText(n.lead, n); out.speech = [sp.indexOf(n.lead.headline) === 0, sp.indexOf('Sources') < 0, C.speechText(d.lead, d).slice(0, 13), C.speechText({ headline: 'A', standfirst: 'b', body: ['Lost -$60 today'], sample: true }, n)];
  const ds = ['2026-11-09', '2026-11-11', '2026-11-10', 'junk', '2026-11-10'];
  out.nb = [C.neighbours(ds, '2026-11-10'), C.neighbours(ds, '2026-11-09'), C.neighbours(ds, '2026-11-11'), C.neighbours(ds, '2026-11-12'), C.neighbours([], '2026-11-12'), C.indexDates({ editions: [{ date: '2026-11-10' }, { date: 'x' }, 5] }), C.indexDates(null)];
  const quiz = [{ a: 0 }, { a: 1 }, { a: 2 }]; out.grade = [C.grade(quiz, []).words, C.grade(quiz, [0, 1]).words, C.grade(quiz, [0, 0, 2]).words, C.grade(quiz, [0, 1, 2]).right];
  out.words = [C.initials('The Mind'), C.initials('Kalshi team C'), C.initials('Mercury'), C.initials(''), C.money(-248.3), C.money(73.44), C.money(2000), C.money(-0.001), C.builtWords('2026-11-11T01:10:00Z', Date.UTC(2026, 10, 11, 11, 30)),
    C.builtWords('2026-11-08', Date.UTC(2026, 10, 11, 12)), C.builtWords('', 5), C.builtWords('2026-11-11T01:10:00Z', Date.UTC(2026, 10, 11, 2, 0)), C.safeDate('2026-11-11'), C.safeDate('../x'), C.safeDate('2026-11-11.json')];
  out.wrap = [C.wrap('2 Kalshi edge hunts report: no edge found', 20, 4), C.wrap('word '.repeat(40), 20, 3).length, C.wrap('', 20, 4)];
  console.log(JSON.stringify(out));
});
"""


def test_honesty():
    ed = edition()
    bad, (nv, nq, nc) = verify(ed)
    n = len(arts(ed))
    check(f"b. the committed edition: every number in all {n} articles is one of its facts, and all facts check out against the files they name ({nv} values at their place, {nq} quotes word for word, {nc} counts recounted here)",
          not bad and nv >= 15 and nq >= 20 and nc >= 5, bad[:6])
    lie = copy.deepcopy(ed)
    lie["lead"]["body"][0] = lie["lead"]["body"][0].rstrip(".") + ", up 31% on last week."
    lie["articles"][1]["facts"][0]["raw"] = 999
    lie["articles"][1]["facts"][0]["t"] = "999"
    lie["articles"][0]["facts"][1]["t"] = "An agent that does not exist"
    got = {(a, p.split(" ")[0]) for a, p in verify(lie)[0]}
    check("b. the check has teeth: an invented '31%', a value changed to 999 and a made-up quote are each caught", (lie["lead"]["id"], "number") in got and (lie["articles"][1]["id"], "value") in got or (lie["articles"][1]["id"], "count") in got and (lie["articles"][0]["id"], "quote") in got, sorted(got))
    check("b. ... all three of them", len(got) >= 3, sorted(got))
    # a full newsroom (with home.json, the money index, an earlier edition): the same checks on a temp repo
    with tempfile.TemporaryDirectory() as tmp:
        web = HB.sample_root(tmp)
        full = HB.build(tmp, web, "2026-11-10", {"number": 6, "apps": ["alpha", "beta"]}, with_git=False)
        b2, c2 = verify(full, tmp, web, ["alpha", "beta"])
        ids = [a["id"] for a in arts(full)]
        check("b. a full newsroom (home.json, money index, a new app): all 10 stories are written and every number and fact checks out against the sample files, P&L in $ with its R, drawdown 'left $X of $max loss'",
              not b2 and ids == ["bots", "kalshi-research", "builders", "kalshi-stop", "money", "archive", "calendar", "queue", "mind", "new-apps"] and "(+0.73R)" in " ".join(full["lead"]["body"])
              and "drawdown left $1,420 of $2,000 max loss" in " ".join(full["lead"]["body"]), (b2[:4], ids))
        a1 = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import herald_build as H; print(H.dump(H.build(sys.argv[2], sys.argv[3], '2026-11-10', None, with_git=False)))",
                             os.path.join(ROOT, "tools"), tmp, web], capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="7")).stdout
        a2 = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import herald_build as H; print(H.dump(H.build(sys.argv[2], sys.argv[3], '2026-11-10', None, with_git=False)))",
                             os.path.join(ROOT, "tools"), tmp, web], capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="99")).stdout
        check("b. deterministic for a given date: two separate runs (different hash seeds) write the same bytes; the clock is not in the file", len(a1) > 5000 and a1 == a2 and "built" in json.loads(a1) and json.loads(a1)["built"] == "2026-11-10T13:00:00Z", len(a1))
        other = HB.build(tmp, web, "2026-11-12", None, with_git=False)
        check("b. another date gives another paper from the same files (the calendar moves on, the weather is recomputed) and it still checks out", other["weather"]["level"] == "calm" and other["masthead"]["date_words"] == "Thursday, 12 November 2026"
              and not verify(other, tmp, web)[0] and [e for e in other["articles"] if e["id"] == "calendar"][0]["body"][0].startswith("Example holiday"), other["weather"])
        os.remove(os.path.join(web, "home.json"))
        os.remove(os.path.join(web, "money", "index.json"))
        os.remove(os.path.join(web, "kalshicity", "suggestions.json"))
        less = HB.build(tmp, web, "2026-11-10", None, with_git=False)
        txt = json.dumps(less)
        check("b. missing data: with home.json, the money index and the Kalshi list gone, those three stories are not written (each named with its reason), nothing of them leaks into the paper, the rest still checks out",
              [a["id"] for a in arts(less)] == ["kalshi-research", "builders", "archive", "calendar", "queue", "mind"] and {"bots", "money", "kalshi-stop"} <= {s["article"] for s in less["skipped"]}
              and "$312" not in txt and "310.5" not in txt and "Example habit" not in txt and not verify(less, tmp, web)[0] and len(less["corrections"]) == 1, [a["id"] for a in arts(less)])
    o = AK.node(APP, HARNESS, os.path.join(D, "edition.json"), os.path.join(D, "fixture.json"))
    if o is None:
        check("b. node is not installed: the page rules were not checked", True)
        return
    check("b. no error in the node harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. the page's own audit (heraldcore.js) agrees: no article of the edition or of the demo prints a number without a fact; a stray '4,242' and '77.5%' are caught", all(not x[1] for x in o["audit"]) and len(o["audit"]) == n
          and all(not x[1] for x in o["auditDemo"]) and o["stray"] == ["4242", "77.5"] and o["tokens"] == ["1836", "4.7", "2026", "11", "10", "248.30"], (o["audit"], o["stray"]))
    nm = o["norm"]
    check("b. the edition as the page reads it: date, number, every article, facts with their kind, quiz, interviews, weather, the sample mark, the not-written list; the demo is marked demo",
          nm[0] == ed["date"] and nm[1] == ed["number"] and nm[2] == n and nm[3] is True and nm[4] in ("value", "quote", "calc") and nm[5:8] == [3, 3, ed["weather"]["level"]] and nm[8] is True and nm[9] == len(ed["skipped"]) and nm[10] is True
          and nm[11] is True and nm[12] == 10, nm)
    check("b. junk editions: null, a bad date and a list are refused; no lead = not printable; a story under 3 sentences is dropped; an unknown weather word and broken quiz rows are dropped", o["junk"] == [None, None, None, False, None, None, 1], o["junk"])
    check("b. over-long or odd text is clipped: a 900-letter headline to 160, 8 sentences to 6, control characters to spaces; fact kinds are read (calc, quote, value)", o["clip"] == [160, 6, "a b", ["calc:count", "quote:", "value:a/b"]], o["clip"])
    sh = o["share"]
    check("b. share as text: a masthead line with the date and edition, the headline, every sentence, the sources; the demo says 'DEMO: not real' in its first line",
          sh[0] == f"The Olympus Herald, {ed['masthead']['date_words']} (edition {ed['number']})" and sh[1:4] == [True, True, True] and "[DEMO: not real]" in sh[4], sh)
    check("b. read aloud: the headline first, no file names, the demo and sample warnings spoken first, '-$60' said as 'minus $60'", o["speech"][:3] == [True, True, "Demo edition."] and o["speech"][3] == "This story rests on sample data. A. b Lost minus $60 today", o["speech"])
    nb = o["nb"]
    check("b. older / newer: sorted, doubles and junk dropped; the ends have no neighbour; a date outside the list finds the nearest", (nb[0]["older"], nb[0]["newer"], nb[0]["index"], nb[0]["total"]) == ("2026-11-09", "2026-11-11", 1, 3) and nb[1]["older"] == ""
          and nb[2]["newer"] == "" and (nb[3]["older"], nb[3]["index"]) == ("2026-11-11", -1) and nb[4]["total"] == 0 and nb[5] == ["2026-11-10"] and nb[6] == [], nb)
    check("b. the quiz score: '0 of 3 answered', '2 of 3 answered', '2 of 3 right', 3 right", o["grade"] == ["0 of 3 answered", "2 of 3 answered", "2 of 3 right", 3], o["grade"])
    w = o["words"]
    check("b. words: initials (TM... M for 'The Mind'), $ with sign and no '-$0', 'built from data as of ... (10 hours old)', STALE after 3 days, no stamp says so, a date is the only thing that can name an edition",
          w[:8] == ["M", "KC", "M", "?", "-$248.30", "$73.44", "$2,000", "$0"] and w[8] == "Edition built from data as of 2026-11-11 01:10 UTC (10 hours old)." and "3 days old: STALE" in w[9] and "not known" in w[10]
          and "under two hours old" in w[11] and w[12:] == [True, False, False], w)
    check("b. the scroll wraps the headline into short lines (at most 4, the last cut with an ellipsis)", o["wrap"][0] == ["2 Kalshi edge hunts", "report: no edge", "found"] and o["wrap"][1] == 3 and o["wrap"][2] == [], o["wrap"])


# ------------------------------------------------------------------------------------------------ c. the page
FRONT = "() => [document.querySelector('#demo').hidden, document.querySelector('#mastTitle').textContent, document.querySelector('#mastDate').textContent, document.querySelector('#mastNo').textContent, document.querySelector('#built').textContent, document.querySelector('#lead h2').textContent, document.querySelectorAll('#lead .body p').length, document.querySelectorAll('#stories .story').length, document.querySelector('#status').textContent, document.querySelector('#label').textContent, document.querySelector('#navWhen').textContent]"
BOXES = "() => ({ numbers: document.querySelectorAll('#numbers li').length, wx: document.querySelector('#wx').textContent, corr: document.querySelectorAll('#corrections li').length, cls: [...document.querySelectorAll('#classifieds li b')].map((x) => x.textContent), clsNote: document.querySelector('#classNote').textContent, quiz: document.querySelectorAll('#quiz li').length, iv: [...document.querySelectorAll('#interviews .iv')].map((r) => [r.dataset.id, r.querySelector('.face').dataset.kind, r.querySelector('.face').textContent, r.querySelectorAll('dt').length]), skipped: [...document.querySelectorAll('#skipped li b')].map((x) => x.textContent), shipHidden: document.querySelector('#shipBox').hidden })"
SWIPE = """(dx) => { const el = document.querySelector('#paper'), r = el.getBoundingClientRect(), y = Math.min(innerHeight - 40, Math.max(40, r.top + 80)), x0 = innerWidth / 2 - dx / 2;
  const mk = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: y });
  el.dispatchEvent(new TouchEvent('touchstart', { changedTouches: [mk(x0)], touches: [mk(x0)], bubbles: true }));
  el.dispatchEvent(new TouchEvent('touchend', { changedTouches: [mk(x0 + dx)], touches: [], bubbles: true })); }"""


def older_editions(ed):
    """Two earlier editions made from the committed one (other dates, numbers and lead headlines) so the page has something to page through."""
    out = {}
    for i, day in enumerate(("2026-11-09", "2026-11-10")):
        e = copy.deepcopy(ed)
        e["date"], e["number"], e["masthead"]["date_words"] = day, i + 1, HB.date_words(day)
        e["lead"], e["articles"] = e["articles"][i], [e["lead"]] + [a for j, a in enumerate(e["articles"]) if j != i]
        out[day] = e
    return out


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    ed = copy.deepcopy(edition())
    ed["date"], ed["number"], ed["masthead"]["date_words"] = "2026-11-11", 3, HB.date_words("2026-11-11")
    old = older_editions(ed)
    index = {"v": 1, "keep": 14, "editions": [{"date": d, "number": e["number"], "headline": e["lead"]["headline"]} for d, e in list(old.items()) + [("2026-11-11", ed)]]}
    over = {"/herald/edition.json": json.dumps(ed), "/herald/editions/index.json": json.dumps(index), "/herald/editions/2026-11-11.json": json.dumps(ed), "/herald/editions/2026-11-09.json": json.dumps(old["2026-11-09"]),
            "/herald/editions/2026-11-10.json": json.dumps(old["2026-11-10"])}
    srv, origin = AK.serve(over)
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))["edition"]
    now = "&now=2026-11-11T11:30:00Z"
    try:
        with AK.browser() as br:
            # ---------------------------------------------------------------- 1. the demo edition
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1" + now)
            f = p.evaluate(FRONT)
            check("c. DEMO (?demo=1): the chip, the masthead with date and edition number, 'DEMO edition', a lead with its sentences, 9 more stories, older / newer switched off, never blank",
                  f[0] is False and f[1] == "The Olympus Herald" and f[2] == "Tuesday, 10 November 2026" and f[3] == "Edition No. 7" and f[5] == fx["lead"]["headline"] and f[6] == len(fx["lead"]["body"]) and f[7] == 9 and "DEMO" in f[8] and "DEMO" in f[9]
                  and f[10] == "Demo edition" and p.evaluate("() => document.querySelector('#older').disabled && document.querySelector('#newer').disabled"), f)
            b = p.evaluate(BOXES)
            check("c. DEMO boxes: by the numbers, the weather pill 'Careful' on a high-impact day, 3 corrections, classifieds without the offer that ran out, 3 quiz questions, 3 interviews drawn with initials (no people kit here), the not-written list is empty",
                  b["numbers"] >= 5 and b["wx"].startswith("Careful ") and b["corr"] == 3 and b["cls"] == ["Example: 30% off an eval", "Example: free reset"] and b["quiz"] == 3 and [x[0] for x in b["iv"]][:2] == ["mind", "scanner:mercury"]
                  and all(x[1] == "initials" and len(x[2]) in (1, 2) and x[3] == 3 for x in b["iv"]) and b["skipped"] == [], b)
            mode = p.evaluate("() => window.HERALD.S.sceneMode")
            if mode == "webgl":
                p.wait_for_timeout(1600)
                sc = p.evaluate("() => { const s = window.HERALD.scene(); return [s.open(), s.frames(), !document.querySelector('#stand').hidden, document.querySelector('#standFlat').hidden]; }")
                f0 = sc[1]
                p.wait_for_timeout(600)
                f1 = p.evaluate("() => window.HERALD.scene().frames()")
                check("c. 3D: the marble newsstand is drawn (WebGL) and its scroll has unrolled with the headline; once open it draws nothing more (no idle frames)", sc[0] == 1 and sc[1] > 3 and sc[2] and sc[3] and f1 == f0, (sc, f1))
            else:
                fb = p.evaluate("() => [document.querySelectorAll('#standFlat text').length, !document.querySelector('#standFlat').hidden]")
                check("c. WebGL is not available here: the flat scroll with the headline is drawn instead (never blank)", fb[0] >= 2 and fb[1], fb)
            AK.shot(p, "herald-demo")
            view_shot(p, "herald-front", top=True)
            font = p.evaluate("() => [getComputedStyle(document.querySelector('#mastTitle')).fontFamily, getComputedStyle(document.body).backgroundColor, getComputedStyle(document.querySelector('#lead h2')).fontFamily, getComputedStyle(document.querySelector('#stories')).columnCount, document.querySelector('#stories').getBoundingClientRect().width]")
            check("c. AGORA look: a serif masthead and serif headlines on the warm night body; on a phone the story grid is one column", all(any(x in fam for x in ("Palatino", "Iowan", "Georgia")) for fam in (font[0], font[2])) and font[1] == "rgb(20, 17, 14)"
                  and p.evaluate("() => { const s = [...document.querySelectorAll('#stories .story')].map((e) => Math.round(e.getBoundingClientRect().left)); return new Set(s).size; }") == 1, font)
            t = AK.taps(p)
            check("c. front page: every tap target is at least 44 x 44 px, no sideways scroll, Jarvis's corner is free, no console error, nothing off the origin", not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:5], errs[:3], off[:3]))
            # read it to me is off by default
            v0 = p.evaluate("() => [window.HERALD.S.voice, window.HERALD.S.spoken.length, document.querySelector('#readMe').getAttribute('aria-pressed'), document.querySelector('#readMe').textContent]")
            check("c. 'Read it to me' is off by default: nothing has been spoken", v0 == [False, 0, "false", "Read it to me: off"], v0)
            # tap a story
            p.evaluate("() => window.scrollTo(0, 0)")
            second = fx["articles"][2]
            p.locator(f"#stories .story[data-id={second['id']}]").click()
            p.wait_for_timeout(250)
            r = p.evaluate("() => [document.querySelector('#reader').hidden, document.querySelector('#rHead').textContent, document.querySelectorAll('#rBody p').length, document.querySelector('#rStand').textContent, document.querySelector('#rFactsSum').textContent, document.querySelector('#rSample').textContent, window.HERALD.S.spoken.length, getComputedStyle(document.querySelector('#rBody p')).fontFamily]")
            check("c. tap a story: the reader opens with the headline, standfirst and every sentence; it says how many facts and files stand behind it; the demo mark is on it; still nothing spoken",
                  r[0] is False and r[1] == second["headline"] and r[2] == len(second["body"]) and r[3] == second["standfirst"] and r[4] == f"Where every number comes from ({len(second['facts'])} facts, {len(second['sources'])} {'file' if len(second['sources']) == 1 else 'files'})"
                  and "DEMO edition" in r[5] and r[6] == 0, r)
            p.locator("#rFactsBox summary").click()
            p.wait_for_timeout(150)
            fa = p.evaluate("() => [...document.querySelectorAll('#rFacts li')].map((li) => li.textContent)")
            check("c. 'Where every number comes from': one line per fact with the file and the place in it (read at / copied from / worked out)", len(fa) == len(second["facts"]) and all(second["sources"][0] in x or any(s in x for s in second["sources"]) for x in fa)
                  and any("read at" in x for x in fa) and any("copied from" in x or "worked out" in x for x in fa), fa[:3])
            tr = AK.taps(p)
            check("c. the reader: every tap target is at least 44 x 44 px and no sideways scroll", not tr and AK.no_sideways(p), tr[:5])
            p.locator("#rShare").click()
            p.wait_for_timeout(400)
            shr = p.evaluate("() => [document.querySelector('#rShareFld').hidden, document.querySelector('#rShareOut').value, document.querySelector('#status').textContent]")
            check("c. Share as text: the whole story as plain text (masthead line marked DEMO, the headline, every sentence, the sources), copied or left in a box to copy", shr[0] is False and shr[1].startswith("The Olympus Herald, Tuesday, 10 November 2026 (edition 7) [DEMO: not real]")
                  and second["headline"].upper() in shr[1] and all(s in shr[1] for s in second["body"]) and "Sources: " in shr[1] and ("copied" in shr[2] or "box below" in shr[2] or "Shared" in shr[2]), (shr[1][:120], shr[2]))
            p.locator("#rSpeak").click()
            p.wait_for_timeout(200)
            sp = p.evaluate("() => window.HERALD.S.spoken")
            check("c. 'Read it to me' in the reader hands the story to the phone's voice: demo warning, then the headline, standfirst and sentences, no file names", len(sp) == 1 and sp[0].startswith("Demo edition. Not real numbers. " + second["headline"]) and second["body"][-1] in sp[0]
                  and ".json" not in sp[0].replace(second["body"][-1], "").replace(" ".join(second["body"]), ""), sp[0][:140] if sp else sp)
            view_shot(p, "herald-reader")
            p.locator("#rClose").click()
            p.wait_for_timeout(150)
            check("c. Close: back on the front page", p.evaluate("() => document.querySelector('#reader').hidden && document.body.style.overflow === ''"), None)
            p.locator("#readMe").click()
            p.wait_for_timeout(200)
            on = p.evaluate("() => [window.HERALD.S.voice, document.querySelector('#readMe').getAttribute('aria-pressed'), window.HERALD.S.spoken.length, window.HERALD.S.spoken[1].slice(0, 30)]")
            p.locator("#leadOpen").click()
            p.wait_for_timeout(200)
            on2 = p.evaluate("() => [window.HERALD.S.spoken.length, document.querySelector('#rHead').textContent]")
            p.keyboard.press("Escape")
            p.locator("#readMe").click()
            p.wait_for_timeout(150)
            offv = p.evaluate("() => [window.HERALD.S.voice, document.querySelector('#readMe').textContent]")
            check("c. switch 'Read it to me' on: the lead is read, and each story you open is read too; Escape closes the reader; switched off again it stays quiet", on[0] is True and on[1] == "true" and on[2] == 2 and on[3].startswith("Demo edition.")
                  and on2 == [3, fx["lead"]["headline"]] and offv == [False, "Read it to me: off"], (on, on2, offv))
            # the quiz
            qz = fx["quiz"]
            p.locator(f"#quiz .opt[data-q='0'][data-o='{qz[0]['a']}']").click()
            wrong = (qz[1]["a"] + 1) % len(qz[1]["o"])
            p.locator(f"#quiz .opt[data-q='1'][data-o='{wrong}']").click()
            p.wait_for_timeout(150)
            qq = p.evaluate("() => [document.querySelector('#quizScore').textContent, document.querySelectorAll('#quiz .opt.right').length, document.querySelectorAll('#quiz .opt.wrong').length, document.querySelectorAll('#quiz .why').length, getComputedStyle(document.querySelector('#quiz .q'), '::before').content]")
            p.locator(f"#quiz .opt[data-q='2'][data-o='{qz[2]['a']}']").click()
            p.wait_for_timeout(150)
            qs = p.evaluate("() => document.querySelector('#quizScore').textContent")
            check("c. the mini quiz (Lyceum questions set as numbered 'Across' clues): a right answer, a wrong one (the right one is then marked and the reason shown), then the score '2 of 3 right'",
                  qq[0].startswith("2 of 3 answered") and qq[1] == 2 and qq[2] == 1 and qq[3] == 2 and "Across" in qq[4] and qs.startswith("2 of 3 right"), (qq, qs))
            check("c. the whole demo run raised no console error and sent nothing off the site", not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            # ---------------------------------------------------------------- 2. the real edition (served as edition 3 with two older ones to page through)
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.add_init_script("window.OLYMPUS_PEOPLE = { portrait(id, size) { if (id === 'mind') throw new Error('unknown person'); const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 44 44'); s.setAttribute('data-person', id); s.setAttribute('width', size); return s; } };")
            AK.open_app(p, origin, APP, "?x=1" + now)
            f = p.evaluate(FRONT)
            n = len(arts(ed))
            check(f"c. the real edition: no DEMO chip, 'Wednesday, 11 November 2026', 'Edition No. 3', 'built from data as of ... (10 hours old)', the lead and {n - 1} more stories, '3 of 3 kept'",
                  f[0] is True and f[2] == "Wednesday, 11 November 2026" and f[3] == "Edition No. 3" and f[4] == "Edition built from data as of 2026-11-11 01:10 UTC (10 hours old)." and f[5] == ed["lead"]["headline"] and f[7] == n - 1
                  and f"{n} stories" in f[8] and "Nothing is invented" in f[9] and f[10].endswith("3 of 3 kept"), f)
            b = p.evaluate(BOXES)
            check("c. honest marks on the real page: classifieds say SAMPLE offers (Mercury's file here is its fixture), the weather is the builder's word, and 'Not in today's paper' lists bots, money and new-apps with the reason",
                  "SAMPLE offers." in b["clsNote"] and "mercury/fixture.json" in b["clsNote"] and b["wx"].lower().startswith(ed["weather"]["level"]) and b["skipped"] == [s["article"] + ": " for s in ed["skipped"]] and b["shipHidden"] == (not ed["press"]["shipped"]), b)
            check("c. portraits: with the people kit loaded each interview shows portrait(id, 44); a person the kit does not know falls back to initials",
                  [(x[0], x[1]) for x in b["iv"]] == [(i["id"], "initials" if i["id"] == "mind" else "portrait") for i in ed["interviews"]] and p.evaluate("() => document.querySelectorAll('#interviews svg[data-person]').length") == 2, b["iv"])
            view_shot(p, "herald-real", top=True)
            p.evaluate("() => document.querySelector('#numbersBox').scrollIntoView()")
            view_shot(p, "herald-boxes")
            p.evaluate("() => window.scrollTo(0, 0)")
            p.locator("#leadOpen").click()
            p.wait_for_timeout(200)
            lf = p.evaluate("() => [document.querySelector('#rFactsSum').textContent, document.querySelector('#rSample').hidden]")
            check("c. the real lead in the reader: every number has a fact (no warning), no sample mark", lf[0].startswith("Where every number comes from (") and lf[1] is True, lf)
            p.locator("#rClose").click()
            # older / newer
            p.locator("#older").click()
            p.wait_for_function("() => window.HERALD.S.ed.date === '2026-11-10'", timeout=20000)
            p.wait_for_timeout(200)
            o1 = p.evaluate(FRONT)
            check("c. Older: yesterday's edition is fetched from the archive by its date: its own date line, number 2 and lead", o1[2] == "Tuesday, 10 November 2026" and o1[3] == "Edition No. 2" and o1[5] == old["2026-11-10"]["lead"]["headline"] and o1[10].endswith("2 of 3 kept")
                  and any(u.endswith("/herald/editions/2026-11-10.json") for u in seen), o1[:6])
            p.evaluate(SWIPE, 160)
            p.wait_for_function("() => window.HERALD.S.ed.date === '2026-11-09'", timeout=20000)
            p.wait_for_timeout(200)
            o2 = p.evaluate("() => [window.HERALD.S.ed.number, document.querySelector('#older').disabled, document.querySelector('#newer').disabled, document.querySelector('#lead h2').textContent]")
            check("c. swipe right on the paper: one edition older (No. 1, the oldest kept: 'Older' is switched off)", o2 == [1, True, False, old["2026-11-09"]["lead"]["headline"]], o2)
            p.evaluate(SWIPE, -160)
            p.wait_for_function("() => window.HERALD.S.ed.date === '2026-11-10'", timeout=20000)
            p.evaluate(SWIPE, 30)
            p.wait_for_timeout(200)
            still = p.evaluate("() => window.HERALD.S.ed.date")
            p.locator("#newer").click()
            p.wait_for_function("() => window.HERALD.S.ed.date === '2026-11-11'", timeout=20000)
            p.wait_for_timeout(200)
            o3 = p.evaluate("() => [window.HERALD.S.ed.number, document.querySelector('#newer').disabled, document.querySelector('#lead h2').textContent]")
            check("c. swipe left: one newer; a short drag does nothing; Newer: back on today's edition", still == "2026-11-10" and o3 == [3, True, ed["lead"]["headline"]], (still, o3))
            t = AK.taps(p)
            check("c. real front page: every tap target is at least 44 x 44 px, no sideways scroll, Jarvis's corner is free, no console error, nothing off the origin", not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:5], errs[:3], off[:3]))
            ctx.close()
            # a wide screen: the grid is a real broadsheet
            ctx, p, errs, seen, off = AK.page(br, origin, w=1100, h=800)
            AK.open_app(p, origin, APP, "?x=1" + now)
            cols = p.evaluate("() => new Set([...document.querySelectorAll('#stories .story')].map((e) => Math.round(e.getBoundingClientRect().left))).size")
            check("c. on a wide screen the same page is a broadsheet: the stories run in 3 columns with rules between them", cols == 3 and "solid" in p.evaluate("() => getComputedStyle(document.querySelector('#stories')).columnRuleStyle") and AK.no_sideways(p) and not errs, cols)
            view_shot(p, "herald-wide", top=True)
            ctx.close()
            # an edition with no story, and no edition at all -> the demo
            empty = dict(ed, lead=None, articles=[])
            for name, body, frag in (("an edition with no story (its sources were missing)", json.dumps(empty), "has no story"), ("no edition.json at all (404)", None, "could not be read")):
                srv2, origin2 = AK.serve({"/herald/edition.json": body, "/herald/editions/index.json": None})
                ctx, p, errs, seen, off = AK.page(br, origin2)
                AK.open_app(p, origin2, APP, "?x=1" + now)
                e = p.evaluate(FRONT)
                check(f"c. {name} -> the DEMO edition with a plain reason, never blank, no console error", e[0] is False and frag in e[8] and "DEMO" in e[8] and e[7] == 9 and not errs, (e[8], errs[:2]))
                ctx.close()
                srv2.shutdown()
            # ---------------------------------------------------------------- 3. 375 x 667, LITE, reduced motion
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?q=low" + now)
            lt = p.evaluate("() => [window.HERALD.S.sceneMode, document.querySelector('#lite').hidden, document.querySelector('#stand').hidden, [...document.querySelectorAll('#standFlat text')].map((x) => x.textContent).slice(1).join(' ')]")
            check("c. 375 x 667, LITE, reduced motion: the flat scroll (no WebGL at all) carries the whole headline; the LITE chip", lt[:3] == ["flat", False, True] and lt[3].rstrip("…")[:30] == ed["lead"]["headline"][:30], lt)
            check("c. 375 x 667 front page: no sideways scroll, every tap >= 44 px, Jarvis's corner free, no error", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            p.evaluate("() => window.scrollTo(0, 0)")
            p.locator("#stories .story").first.click()
            p.wait_for_timeout(200)
            check("c. 375 x 667 reader: open, no sideways scroll, every tap >= 44 px, no error", p.evaluate("() => !document.querySelector('#reader').hidden") and AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            view_shot(p, "herald-375")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.add_init_script("delete window.speechSynthesis; Object.defineProperty(window, 'speechSynthesis', { value: undefined });")
            AK.open_app(p, origin, APP, "?flat=1" + now)
            p.locator("#readMe").click()
            p.wait_for_timeout(200)
            nv = p.evaluate("() => [window.HERALD.S.sceneMode, document.querySelector('#status').textContent]")
            check("c. ?flat=1 draws the flat scroll; a browser with no voice says so in plain words and the page keeps working", nv[0] == "flat" and "no voice" in nv[1] and not errs, (nv, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


def view_shot(p, name, top=False):
    """What the phone shows right now (only when AGORA_SHOTS=<dir> is set); any full-screen overlay of the kit is hidden for the picture only."""
    d = os.environ.get("AGORA_SHOTS")
    if not d:
        return
    os.makedirs(d, exist_ok=True)
    if top:
        p.evaluate("() => window.scrollTo(0, 0)")
    p.evaluate("() => { for (const e of document.querySelectorAll('body *')) { const cs = getComputedStyle(e); if (cs.position === 'fixed' && e.getBoundingClientRect().height >= innerHeight * 0.9 && !e.closest('#app')) e.style.visibility = 'hidden'; } }")
    p.wait_for_timeout(600)
    p.screenshot(path=os.path.join(d, name + ".png"))


if __name__ == "__main__":
    test_static()
    test_honesty()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
