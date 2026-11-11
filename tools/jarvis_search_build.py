"""Jarvis global search index (2026-11-11, JARVIS BRAIN v3): everything worth finding on the site -> jarvis/search-index.json.

One small file (under 350 KB) that jarvis/search.js searches offline: "find ...", "search ...", "where is ...",
"what did we test about VWAP". What goes in:

    app       every app: id, name, what it is, its district (olympus/apps-list.js + docs/OLYMPUS_MAP.md)
    writeup   every research write-up: title + first paragraph (archive/index.json + research/writeups/*.md)
    run       the Archive's headline runs: title, family, verdict (archive/index.json)
    rejected  ideas tested and rejected (archive/index.json)
    event     Pythia's dated events (pythia/events.json)
    quiz      the Lyceum question bank (lyceum/lyceumcore.js)
    money     the money machines' item titles (money/<id>.json when published, else the bundled fixture, marked sample)
    kalshi    the Kalshi engine's stop / do-more / watch lists (kalshicity/edges.json)
    term      glossary words (olympus/glossary*.js + strategy-facts.json)
    rule      the live strategy's rules (strategy-facts.json, from STRATEGY.md)

    python tools/jarvis_search_build.py                 write tools/web_public/jarvis/search-index.json
    python tools/jarvis_search_build.py --site DIR      read the built site in DIR (falls back to the repo) and write DIR/jarvis/search-index.json
    python tools/jarvis_search_build.py --check         the file on disk is valid, small enough, and has every app (exit 1 if not);
                                                        prints "stale" when a fresh build differs (exit 1 only with --strict)
    python tools/jarvis_search_build.py --selftest      build in memory from the repo and check the parts

Stdlib only, no network, deterministic: the same inputs give the same bytes (no clock in the file).
A doc is a row [kind, title, text, open, route, source]: `open` is an app id and `route` a deep link inside it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
MAX_BYTES = 350_000
KINDS = ["app", "writeup", "run", "rejected", "event", "quiz", "money", "kalshi", "term", "rule"]
MONEY_IDS = ["sibyl", "mercury", "chrysos", "oikos", "arbiter"]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jarvis_facts_build as facts_build  # noqa: E402


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def rjson(p: str):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def one(s, n: int) -> str:
    s = re.sub(r"<[^>]*>", " ", str(s or ""))
    s = re.sub(r"[`*#|]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ,;:.(-") + "…"


class Src:
    """reads a file from the built site when it is there, else from the repo's tools/web_public"""

    def __init__(self, site: str | None):
        self.site = site

    def path(self, rel: str) -> str | None:
        for base in ([self.site] if self.site else []) + [WP]:
            p = os.path.join(base, *rel.split("/"))
            if os.path.exists(p):
                return p
        return None

    def json(self, rel: str):
        p = self.path(rel)
        return rjson(p) if p else None

    def text(self, rel: str) -> str:
        p = self.path(rel)
        return read(p) if p else ""


# ------------------------------------------------------------------------------------------------ the parts
def apps(src: Src) -> list:
    js = src.text("olympus/apps-list.js")
    rows = [json.loads(m) for m in re.findall(r"^\s*(\{\"id\".*\}),?\s*$", js, re.M)]
    district, reads = {}, {}
    mp = os.path.join(ROOT, "docs", "OLYMPUS_MAP.md")
    if os.path.exists(mp):
        for m in re.finditer(r"^\|\s*[^|]*\(`([a-z0-9_]+)`\)\s*\|\s*([^|]+?)\s*\|\s*[^|]*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", read(mp), re.M):
            district[m.group(1)] = m.group(2)
            reads[m.group(1)] = m.group(4)
    out = []
    for r in rows:
        d = district.get(r["id"], "")
        text = one(r.get("purpose", ""), 110) + (". %s district" % d if d else "") + (", %s" % r.get("groupName") if r.get("groupName") else "")
        out.append(["app", r.get("name") or r["id"], text, r["id"], "", "the apps list" + (" + OLYMPUS_MAP.md" if d else "")])
    return out


def first_paragraph(md: str) -> str:
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b or b.startswith("#") or b.startswith("|") or b.startswith("```") or b.startswith("---"):
            continue
        return b
    return ""


def writeups(src: Src) -> list:
    idx = src.json("archive/index.json") or {}
    wdir = os.path.join(ROOT, "research", "writeups")
    seen, out = set(), []
    for w in idx.get("writeups") or []:
        slug = str(w.get("slug") or "")
        if not slug:
            continue
        seen.add(slug)
        p = os.path.join(wdir, slug + ".md")
        para = first_paragraph(read(p)) if os.path.exists(p) else ""
        text = one(para or w.get("summary") or "", 200)
        fam = str(w.get("family") or "")
        out.append(["writeup", one(w.get("title") or slug, 110), (fam + ". " if fam and fam != "other" else "") + text, "archive", "#find=" + slug, "research/writeups/%s.md" % slug])
    if os.path.isdir(wdir):                       # write-ups the Archive index does not hold yet
        for name in sorted(os.listdir(wdir)):
            slug = name[:-3]
            if not name.endswith(".md") or slug in seen:
                continue
            md = read(os.path.join(wdir, name))
            t = re.search(r"^#\s+(.+)$", md, re.M)
            out.append(["writeup", one(t.group(1) if t else slug, 110), one(first_paragraph(md), 200), "archive", "#find=" + slug, "research/writeups/%s.md" % slug])
    return out


def runs(src: Src) -> list:
    idx = src.json("archive/index.json") or {}
    cols = idx.get("cols") or []
    verdicts = [str((v.get("name") if isinstance(v, dict) else v) or "") for v in idx.get("verdicts") or []]
    fams = [str(f.get("name") or "") for f in idx.get("families") or []]
    out = []
    try:
        ci = {c: cols.index(c) for c in ("id", "title", "family", "verdict", "status")}
    except ValueError:
        return out
    for r in idx.get("runs") or []:
        if not isinstance(r, list) or len(r) <= max(ci.values()):
            continue
        fam = r[ci["family"]]
        fam = fams[fam] if isinstance(fam, int) and 0 <= fam < len(fams) else str(fam or "")
        v = r[ci["verdict"]]
        v = verdicts[v] if isinstance(v, int) and 0 <= v < len(verdicts) else ""
        text = ", ".join(x for x in (fam, v or str(r[ci["status"]] or "")) if x)
        out.append(["run", one(r[ci["title"]], 78), one(str(r[ci["id"]]) + ". " + text, 70), "archive", "#find=" + str(r[ci["id"]]), "archive/index.json"])
    return out


def rejected(src: Src) -> list:
    idx = src.json("archive/index.json") or {}
    return [["rejected", one(r.get("title"), 90), one(r.get("text"), 220), "archive", "#find=" + one(r.get("title"), 40), one(r.get("src") or "archive/index.json", 40)]
            for r in idx.get("rejected") or [] if isinstance(r, dict) and r.get("title")]


def events(src: Src) -> list:
    j = src.json("pythia/events.json") or {}
    out = []
    for e in j.get("events") or []:
        if isinstance(e, dict) and e.get("title") and e.get("date"):
            out.append(["event", one(e["title"], 80), one("%s%s ET, %s impact%s" % (e["date"], " " + e["time"] if e.get("time") else "", e.get("impact") or "low", ", date not verified" if e.get("verify") else ""), 80), "pythia", "", "pythia/events.json"])
    for w in j.get("weekly") or []:
        if isinstance(w, dict) and w.get("title"):
            out.append(["event", one(w["title"], 80), one("every week%s ET, %s impact" % (" " + w["time"] if w.get("time") else "", w.get("impact") or "low"), 80), "pythia", "", "pythia/events.json"])
    return out


def quiz(src: Src) -> list:
    js = src.text("lyceum/lyceumcore.js")
    out = []
    for m in re.finditer(r"\{\s*id:\s*'([^']+)',\s*topic:\s*'([^']+)',\s*q:\s*'((?:[^'\\]|\\.)*)'.*?why:\s*'((?:[^'\\]|\\.)*)'\s*\}", js):
        un = lambda s: s.replace("\\'", "'")
        out.append(["quiz", one(un(m.group(3)), 110), one(un(m.group(4)), 170), "lyceum", "#quiz", "the Lyceum question bank (%s)" % m.group(2)])
    return out


def money(src: Src) -> list:
    out = []
    for mid in MONEY_IDS:
        j, sample = src.json("money/%s.json" % mid), False
        if not isinstance(j, dict):
            j, sample = src.json("%s/fixture.json" % mid), True
        if not isinstance(j, dict):
            continue
        sample = sample or j.get("status") == "sample"
        tag = " [sample data]" if sample else ""
        head = j.get("headline") if isinstance(j.get("headline"), dict) else {}
        if head.get("text"):
            out.append(["money", "%s: the headline" % mid.capitalize(), one(head["text"], 150) + tag, mid, "", ("%s/fixture.json" % mid) if sample else ("money/%s.json" % mid)])
        for i in (j.get("items") or [])[:14]:
            if isinstance(i, dict) and i.get("title"):
                out.append(["money", one(i["title"], 80), one(i.get("detail") or "", 110) + tag, mid, "", ("%s/fixture.json" % mid) if sample else ("money/%s.json" % mid)])
    return out


def kalshi(src: Src) -> list:
    j = src.json("kalshicity/edges.json") or {}
    edges = {e.get("id"): e for e in j.get("edges") or [] if isinstance(e, dict)}
    lists = j.get("lists") if isinstance(j.get("lists"), dict) else {}
    names = {"stop": "STOP list", "do_more": "do-more list", "watch": "watch list"}
    out = []
    for key in ("stop", "do_more", "watch"):
        for eid in (lists.get(key) or [])[:12]:
            e = edges.get(eid) or {}
            label = one(e.get("label") or " ".join(x for x in str(eid).split("~") if x and x != "*"), 70)
            bits = []
            if isinstance(e.get("n"), (int, float)):
                bits.append("n=%d bets" % e["n"])
            if isinstance(e.get("pnl"), (int, float)):
                bits.append("%s$%.2f after fees" % ("-" if e["pnl"] < 0 else "+", abs(e["pnl"])))
            out.append(["kalshi", "Kalshi %s: %s" % (names[key], label), one(", ".join(bits) or "no numbers yet", 90), "kalshicity", "", "kalshicity/edges.json"])
    return out


def terms_and_rules(src: Src) -> list:
    f = facts_build.build()
    out = []
    lite = src.text("olympus/glossary-lite.js")
    extra = {}
    for a, b, c in re.findall(r"^\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z0-9_]+))\s*:\s*['\"]", lite, re.M):
        extra[a or b or c] = 1
    for name, t in f["terms"].items():
        rules = t.get("rules") or []
        d = t.get("def") or ("Your rule %s in STRATEGY.md." % ", ".join(str(n) for n in rules))
        out.append(["term", name, one(d, 190), "athena", "", t.get("src") or "STRATEGY.md"])
    for s in f["sections"]:
        out.append(["rule", "LIT rule %d: %s" % (s["n"], s["title"]), one(" ".join(s["lines"][:3]), 230), "athena", "", "STRATEGY.md rule %d" % s["n"]])
    return out


def build(site: str | None = None) -> dict:
    src = Src(site)
    docs = []
    for part in (apps, writeups, runs, rejected, events, quiz, money, kalshi, terms_and_rules):
        docs.extend(part(src))
    docs = [d for d in docs if d[1]]
    counts = {k: sum(1 for d in docs if d[0] == k) for k in KINDS}
    rows = [[KINDS.index(d[0]), d[1], d[2], d[3], d[4], d[5]] for d in docs]
    body = {"v": 1, "kinds": KINDS, "counts": counts, "docs": rows}
    body["sha"] = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return body


def dumps(body: dict) -> str:
    head = {k: v for k, v in body.items() if k != "docs"}
    lines = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in body["docs"])
    return json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1] + ',"docs":[\n' + lines + "\n]}\n"


def problems(body: dict, text: str) -> list:
    bad = []
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        bad.append("too big: %d bytes (limit %d)" % (size, MAX_BYTES))
    c = body.get("counts") or {}
    floor = {"app": 50, "writeup": 100, "run": 100, "rejected": 20, "event": 5, "quiz": 10, "money": 5, "term": 20, "rule": 9}
    for k, n in floor.items():
        if c.get(k, 0) < n:
            bad.append("only %d %s docs (expected at least %d)" % (c.get(k, 0), k, n))
    ids = {d[3] for d in body.get("docs") or [] if d[0] == 0}
    want = {json.loads(m)["id"] for m in re.findall(r"^\s*(\{\"id\".*\}),?\s*$", read(os.path.join(WP, "olympus", "apps-list.js")), re.M)}
    if want - ids:
        bad.append("apps missing from the index: %s" % sorted(want - ids)[:8])
    for d in body.get("docs") or []:
        if not (isinstance(d, list) and len(d) == 6 and isinstance(d[0], int) and all(isinstance(x, str) for x in d[1:])):
            bad.append("bad row: %r" % (d,))
            break
    if re.search(r"gsk_[A-Za-z0-9]{8}|AIza[A-Za-z0-9]{8}|github_pat_|api[_-]?key\s*[:=]", text, re.I):
        bad.append("something that looks like a key is in the index")
    return bad


def selftest() -> int:
    b = build()
    text = dumps(b)
    bad = problems(b, text)
    if json.loads(text) != b:
        bad.append("the compact writer does not round-trip")
    if dumps(build()) != text:
        bad.append("not deterministic")
    titles = " ".join(d[1] for d in b["docs"]).lower()
    for w in ("helios", "archive", "cpi", "sweep", "kelly", "lit rule 6"):
        if w not in titles:
            bad.append("expected %r in a title" % w)
    for x in bad:
        print("[FAIL] " + x)
    print("jarvis_search_build selftest: %d docs %s, %d bytes: %s" % (len(b["docs"]), json.dumps(b["counts"]), len(text.encode("utf-8")), "FAIL" if bad else "ok"))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", help="the built site directory (reads its published JSON, writes <site>/jarvis/search-index.json)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true", help="with --check: a stale file is an error")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    path = os.path.join(a.site or WP, "jarvis", "search-index.json")
    body = build(a.site)
    text = dumps(body)
    if a.check:
        if not os.path.exists(path):
            print("search-index.json is missing: run python tools/jarvis_search_build.py")
            return 1
        disk_text = read(path)
        try:
            disk = json.loads(disk_text)
        except Exception as e:
            print("search-index.json does not parse: %s" % e)
            return 1
        bad = problems(disk, disk_text)
        stale = disk_text != text
        for x in bad:
            print("[FAIL] " + x)
        print("search-index.json: %d docs, %d bytes, %s" % (len(disk.get("docs") or []), len(disk_text.encode("utf-8")), "stale (a source changed: rebuild)" if stale else "up to date"))
        return 1 if bad or (stale and a.strict) else 0
    bad = problems(body, text)
    if bad:
        for x in bad:
            print("[FAIL] " + x)
        return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s: %d docs, %d bytes" % (os.path.relpath(path, ROOT) if path.startswith(ROOT) else path, len(body["docs"]), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
