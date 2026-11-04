"""Bridge ingest + job library (JOB 24, 2026-11-04): tools/bridge_ingest.py, tools/bridge_jobs_build.py, bridge/jobs.json, bridge_sync.suggest().

  a. the job library: >= 40 jobs, every field, unique ids, every prompt carries the ONBOARD rules (only handoff/inbox/<id>/, no secrets, no bot / engine
     edits, paper only, DONE.md, QUESTION.md), every category the owner listed is there, jobs.json is exactly what the generator writes
  b. validation negative controls: a .js with fetch / eval / XHR / import() is rejected; secret-like strings (GitHub token, sk- key, private key,
     key = value) are rejected; oversize files are rejected; disallowed types (html, py, exe, sh), fake images, bad JSON, SVG with a script or
     an event handler are rejected; clean png / webp / svg / json / md / txt / small js are approved
  c. a job folder: DONE.md decides 'done'; symlinks, hidden files, odd names, deep folders and too many files are handled; one bad file never hides the others
  d. prepare: approved images are copied to olympus/assets/<id>/ with a manifest and an index; rejected files and scripts are never copied; the site copy has a budget
  e. never executes: the ingest source has no exec / eval / compile / import of delivered files / subprocess
  f. suggest(): the weekly rules (question first, in progress, first win, category of the week, gap, quick), at most 5, no duplicates, changes by week
    python -X utf8 -m tests.test_bridge_ingest
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bridge_ingest as I  # noqa: E402
from tools import bridge_jobs_build as G  # noqa: E402
from tools import bridge_sync as B  # noqa: E402

RES = []
TMPS = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else "  -> " + str(info)[:400]))


def tmp():
    d = tempfile.mkdtemp(prefix="le_ingest_")
    TMPS.append(d)
    return d


def png(w=4, h=4):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x7f\x20\xc0" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def webp(w=8, h=6):
    body = b"VP8X" + struct.pack("<I", 10) + b"\x00\x00\x00\x00" + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def put(d, rel, data):
    p = os.path.join(d, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return p


def ok_(name, data):
    return I.validate_bytes(name, data)[0]


def why_(name, data):
    return I.validate_bytes(name, data)[1]


def part_library():
    doc = json.load(open(os.path.join(ROOT, "tools", "web_public", "bridge", "jobs.json"), encoding="utf-8"))
    js = doc["jobs"]
    ids = [j["id"] for j in js]
    check("a. the library has at least 40 ready jobs, unique plain ids", len(js) >= 40 and len(set(ids)) == len(ids) and all(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", i) for i in ids), len(js))
    need = {"id", "cat", "title", "makes", "tool", "prompt", "files", "lands", "minutes", "difficulty"}
    check("a. every job has id, category, title, what it makes, the exact prompt, files, where it lands, minutes and difficulty",
          all(need <= set(j) and j["title"] and j["makes"] and len(j["prompt"]) > 300 and isinstance(j["minutes"], int) and 1 <= j["minutes"] <= 60
              and j["difficulty"] in ("easy", "medium", "hard") for j in js), [j["id"] for j in js if not need <= set(j)])
    check("a. every job lands in handoff/inbox/<id>/ and lists DONE.md among its files", all(j["lands"] == f"handoff/inbox/{j['id']}/" and "DONE.md" in j["files"] and len(j["files"]) >= 2 for j in js))
    rules = ["only add files under handoff/inbox/" + "{id}" + "/", "never edit the bots", "live_model*.json", "engine/", "no secrets", "paper trading only", "DONE.md", "QUESTION.md", "chatgpt/{id}"]
    bad = [j["id"] for j in js if not all(r.replace("{id}", j["id"]).lower() in j["prompt"].lower() for r in rules)]
    check("a. every prompt carries the ONBOARD rules (only handoff/inbox/<id>/, no bots / engine edits, no secrets, paper only, DONE.md, QUESTION.md)", not bad, bad[:5])
    check("a. every prompt starts with its job id and names every file it expects", all(j["prompt"].startswith(f"Job {j['id']}.") and all(f in j["prompt"] for f in j["files"] if f != "DONE.md") for j in js))
    cats = {c["id"] for c in doc["cats"]}
    want = {"textures", "art", "logo", "sound", "copy", "lore", "obsidian", "strategy", "research", "fixtures", "docs", "mockup", "names"}
    check("a. all 13 categories the owner listed exist and every category has at least 3 jobs", want <= cats and all(sum(1 for j in js if j["cat"] == c) >= 3 for c in want),
          {c: sum(1 for j in js if j["cat"] == c) for c in want})
    money = [j for j in js if j["cat"] == "money"]
    mids = {j["id"] for j in money}
    check("a. money and prop-firm jobs (>= 20): their own category, ids money-*, only .md / .json files back, each says how Claude ingests it (tools/bridge_ingest.py), where it lands, and fits the page's 400-character cap",
          "money" in cats and len(money) >= 20 and all(i.startswith("money-") for i in mids) and all(j["ingest"].count("tools/bridge_ingest.py") == 1 and 40 < len(j["ingest"]) <= 400 for j in money)
          and all(f.endswith((".md", ".json")) for j in money for f in j["files"]) and all(j["lands"] == f"handoff/inbox/{j['id']}/" for j in money), [j["id"] for j in money if "ingest" not in j])
    bad_m = [j["id"] for j in money if not all(w in j["prompt"] for w in ("not financial, tax or legal advice", "UNVERIFIED", "Never ask me for passwords", "source", "ask a CPA", "paper only"))]
    check("a. every money prompt: not financial / tax / legal advice, 'ask a CPA' for anything personal, official sources with dates, UNVERIFIED when unsure, never asks for secrets or personal ids, paper only", not bad_m, bad_m[:5])
    tax = [j for j in money if any(w in j["id"] for w in ("tax", "business"))]
    check("a. the tax jobs (set-aside, dependent, records, business setup) are framed as questions for a CPA for a US 18-year-old, never as a tax percentage",
          len(tax) >= 4 and all("CPA" in j["prompt"] and "US" in j["prompt"] for j in tax) and "Do NOT give me a tax percentage" in next(j for j in tax if j["id"] == "money-tax-setaside")["prompt"], [j["id"] for j in tax])
    check("a. the money topics asked for are all there: prop-firm comparison, discount codes, payout rules, tax set-aside, NQ news / session calendar, Kalshi fees and scan, content ideas",
          all(any(w in i for i in mids) for w in ("prop-compare", "discount", "payout", "tax", "nq-events", "cme-holidays", "kalshi-fees", "kalshi-scan", "content")), sorted(mids))
    text = " ".join(j["title"].lower() + " " + j["id"] for j in js)
    check("a. the named textures (marble, gold, bronze, parchment, fire, water) are all in", all(w in text for w in ("marble", "gold", "bronze", "parchment", "fire", "water")))
    check("a. research jobs ask for sources; fixtures jobs say synthetic; strategy jobs say text only / paper",
          all("source" in j["prompt"].lower() for j in js if j["cat"] == "research") and all("synthetic" in j["prompt"].lower() or "fake" in j["prompt"].lower() for j in js if j["cat"] == "fixtures"))
    check("a. no prompt holds a secret-looking string or a script ask (the library passes its own scanner)", not [j["id"] for j in js if I._first(I.SECRETS, j["prompt"])])
    check("a. jobs.json is exactly what tools/bridge_jobs_build.py writes (edit the generator, not the file)",
          open(os.path.join(ROOT, "tools", "web_public", "bridge", "jobs.json"), encoding="utf-8").read() == G.dumps(G.build()))
    check("a. the library ids are part of the job total, and none collides with a card id", len(B.job_ids()) == len(set(B.job_ids())) and set(ids) <= set(B.job_ids()))


def part_validate():
    js_fetch = "const r = await fetch('https://evil.example/x');\nexport default r;"
    check("b. NEGATIVE: a .js that calls fetch() is rejected", not ok_("a.js", js_fetch.encode()) and "fetch" in why_("a.js", js_fetch.encode()), why_("a.js", js_fetch.encode()))
    bads = {"eval": "eval('1+1')", "XMLHttpRequest": "var x = new XMLHttpRequest();", "WebSocket": "new WebSocket('wss://a.b')", "import()": "import('./x.js')", "new Function": "new Function('return 1')",
            "innerHTML": "el.innerHTML = '<b>x</b>'", "sendBeacon": "navigator.sendBeacon('/x', 'y')", "localStorage": "localStorage.setItem('a', 'b')", "a web address": "var u = 'https://x.y/z';",
            "document.write": "document.write('x')", "string timer": "setTimeout('alert(1)', 5)", "require": "const fs = require('fs');"}
    miss = [k for k, v in bads.items() if ok_("m.js", v.encode())]
    check("b. NEGATIVE: scripts that eval, use XHR / WebSocket / import() / Function / innerHTML / beacons / storage / URLs / timers with text / require are all rejected", not miss, miss)
    fakes = {"GitHub token": "token ghp_" + "a1B2c3D4e5" * 4, "sk key": "key: sk-" + "Ab1" * 12, "private key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----",
             "key = value": "api_key = \"" + "x9Y8z7W6" * 3 + "\"", "AWS": "AKIA" + "ABCDEFGHIJKLMNOP", "Slack": "xoxb-1234567890-abcdefghij", "JWT": "eyJhbGciOiJIUzI1" + "." + "eyJzdWIiOiIxMjM0NTY3" + "." + "SflKxwRJSMeKKF2QT4fw",
             "Telegram": "123456789:" + "AAH" + "x" * 32}
    miss = [k for k, v in fakes.items() if ok_("n.md", v.encode())]
    check("b. NEGATIVE: a secret-like string (GitHub token, sk- key, private key, key = value, AWS, Slack, JWT, Telegram) is rejected in md / txt / json / js / svg",
          not miss and not any(ok_(n, ("x " + fakes["GitHub token"]).encode()) for n in ("a.md", "a.txt", "a.js", "a.svg")) and not ok_("a.json", json.dumps({"k": fakes["sk key"]}).encode()), miss)
    check("b. a normal sentence about tokens / keys is fine (no false alarm on 'API key' as a word)", ok_("a.md", b"# Notes\nStore the API key in GitHub Secrets, never in the repo. A token is short-lived."))
    big = {"a.png": png() + b"\0" * (5 * 1024 * 1024), "a.webp": webp() + b"\0" * (5 * 1024 * 1024), "a.svg": b"<svg>" + b"a" * (201 * 1024) + b"</svg>", "a.json": b"[" + b"1," * (600 * 1024) + b"1]",
           "a.md": b"a" * (201 * 1024), "a.txt": b"a" * (201 * 1024), "a.js": b"var a=1;" * (13 * 1024)}
    miss = [k for k, v in big.items() if ok_(k, v) or "too big" not in why_(k, v)]
    check("b. NEGATIVE: oversize files are rejected per type (png / webp 5 MB, svg / md / txt 200 KB, json 1 MB, js 100 KB)", not miss, miss)
    for name in ("a.html", "a.py", "a.exe", "a.sh", "a.bat", "a.ps1", "a.php", "a.zip", "a.pdf", "a.gif", "a.jpg", "a", "a.mjs", "a.jsx"):
        if ok_(name, b"print(1)"):
            check("b. NEGATIVE: file type is rejected: " + name, False)
            break
    else:
        check("b. NEGATIVE: html, py, exe, sh, bat, ps1, php, zip, pdf, gif, jpg, mjs and extension-less files are rejected (only png / webp / svg / json / md / txt / js)", True)
    check("b. NEGATIVE: a fake PNG (text named .png), a PNG with a wrong signature, a truncated WebP, a 20000 px PNG are rejected",
          not ok_("a.png", b"hello world, not an image at all, just some text") and not ok_("a.png", b"\x89PNX\r\n\x1a\n" + png()[8:]) and not ok_("a.webp", b"RIFF\0\0\0\0WEBP") and not ok_("a.png", png(20000, 10)))
    check("b. NEGATIVE: bad JSON, binary in a .txt, non UTF-8 and an empty file are rejected", not ok_("a.json", b"{not json") and not ok_("a.txt", b"ab\x00cd") and not ok_("a.md", b"\xff\xfe\xfa") and not ok_("a.md", b""))
    svg_bad = ['<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', '<svg onload="x()"></svg>', '<svg><a href="javascript:alert(1)"><rect/></a></svg>',
               '<svg><foreignObject><div/></foreignObject></svg>', '<svg><image href="https://evil.example/p.png"/></svg>', '<!DOCTYPE svg [<!ENTITY a "b">]><svg/>', '<svg><style>@import url(x.css);</style></svg>',
               '<svg><use href="other.svg#a"/></svg>', "hello, not an svg"]
    miss = [s[:30] for s in svg_bad if ok_("a.svg", s.encode())]
    check("b. NEGATIVE: an SVG with a script, event handler, javascript:, foreignObject, external image, entity, @import, outside <use>, or no <svg> is rejected", not miss, miss)
    md_bad = ["<script>alert(1)</script>", "[x](javascript:alert(1))", "<iframe src=x></iframe>"]
    check("b. NEGATIVE: markdown with a script, javascript: link or iframe is rejected", not any(ok_("a.md", s.encode()) for s in md_bad))
    good = {"a.png": png(), "a.webp": webp(), "a.svg": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#f5c96a"/></svg>', "a.json": b'{"trades": [1, 2]}',
            "a.md": b"# Title\n\n- one\n- two\n", "a.txt": b"plain words", "a.js": b"export const GODS = ['Zeus', 'Hera'];\nexport function pick(i) { return GODS[i % GODS.length]; }\n", "DONE.md": b"Made 4 maps. Wire nothing."}
    miss = [k for k, v in good.items() if not ok_(k, v)]
    check("c. CONTROL: clean png / webp / svg / json / md / txt / small js / DONE.md are approved (with size, hash and pixel size in the meta)", not miss
          and I.validate_bytes("a.png", png(4, 4))[2].get("w") == 4 and I.validate_bytes("a.webp", webp(8, 6))[2].get("h") == 6 and len(I.validate_bytes("a.txt", b"x")[2]["sha256"]) == 64, miss)


def part_scan():
    inbox = tmp()
    j = os.path.join(inbox, "tex-test")
    put(j, "good.png", png())
    put(j, "notes.md", "# Hello\n- a")
    put(j, "evil.js", "fetch('https://x.y')")
    put(j, "leak.txt", "ghp_" + "a1B2c3D4e5" * 4)
    put(j, "page.html", "<h1>x</h1>")
    put(j, ".hidden.png", png())
    put(j, "bad name!.png", png())
    put(j, "sub/inner.png", png())
    put(j, "a/b/c/d/deep.png", png())
    put(j, "DONE.md", "Made 1 png, wire as a skybox.")
    try:
        os.symlink("/etc/hostname", os.path.join(j, "link.txt"))
    except OSError:
        pass
    put(inbox, "README.md", "not a folder")
    put(os.path.join(inbox, "q-test"), "QUESTION.md", "Which size?")
    put(os.path.join(inbox, "wip-test"), "a.png", png())
    put(os.path.join(inbox, "Bad_Folder"), "DONE.md", "x")
    res = I.scan(inbox)
    r = res["tex-test"]
    by = {f["name"]: f for f in r["files"]}
    check("c. DONE.md = done; QUESTION.md = question; neither = in progress; files at the inbox root and oddly named folders are ignored",
          r["state"] == "done" and res["q-test"]["state"] == "question" and res["wip-test"]["state"] == "in progress" and "README.md" not in res and "Bad_Folder" not in res, {k: v["state"] for k, v in res.items()})
    check("c. one bad file never hides the others: good.png, notes.md, DONE.md and sub/inner.png approved", all(by[n]["ok"] for n in ("good.png", "notes.md", "DONE.md", "sub/inner.png")), {n: by[n] for n in by if not by[n]["ok"]})
    check("c. NEGATIVE: evil.js (fetch), leak.txt (token), page.html, .hidden.png and 'bad name!.png' are each rejected with a reason",
          all(not by[n]["ok"] and by[n]["reason"] for n in ("evil.js", "leak.txt", "page.html", ".hidden.png", "bad name!.png")), {n: by.get(n) for n in ("evil.js", "leak.txt", "page.html", ".hidden.png")})
    check("c. a symlink is never followed (rejected), and a folder deeper than 3 levels is not read", ("link.txt" not in by or not by["link.txt"]["ok"]) and "a/b/c/d/deep.png" not in by, list(by))
    check("c. counts: approved images / text count without DONE.md; rejected counted", r["approved"] == 3 and r["rejected"] >= 5, (r["approved"], r["rejected"]))
    many = os.path.join(inbox, "many-files")
    for i in range(I.MAX_FILES + 5):
        put(many, f"f{i:03d}.txt", "x")
    put(many, "DONE.md", "x")
    rm = I.scan_job(many)
    check("c. NEGATIVE: more than 80 files: only the first 80 are checked and the page is told", len(rm["files"]) <= I.MAX_FILES and any("limit" in s for s in rm["issues"]), rm["issues"])
    rep = I.report(res)
    check("c. the report names every rejected file with its reason", "REJECTED evil.js" in rep and "fetch" in rep and "REJECTED leak.txt" in rep)
    d = I.deliveries(inbox, res)
    dj = d["jobs"]["tex-test"]
    check("c. deliveries(): only DONE jobs; images listed with size; text previews for md; a DONE line; rejects with reasons; nothing for question / in progress jobs",
          set(d["jobs"]) == {"tex-test"} and {i["name"] for i in dj["images"]} >= {"good.png", "sub/inner.png"} and any(t["name"] == "notes.md" and "Hello" in t["text"] for t in dj["text"])
          and "wire as a skybox" in dj["done"] and any(x["name"] == "evil.js" for x in dj["rejects"]), dj)
    check("c. a rejected script's text never reaches the previews", not any("fetch" in t["text"] for t in dj["text"]) and not any("ghp_" in t["text"] for t in dj["text"]))
    big = put(os.path.join(inbox, "big-test"), "huge.png", png() + b"\0" * (6 * 1024 * 1024))
    put(os.path.join(inbox, "big-test"), "DONE.md", "x")
    rb = I.scan_job(os.path.dirname(big))
    check("c. NEGATIVE: an oversize file on disk is rejected without being read whole", not [f for f in rb["files"] if f["name"] == "huge.png"][0]["ok"] and "too big" in [f for f in rb["files"] if f["name"] == "huge.png"][0]["reason"])
    return inbox, res


def part_prepare(inbox, res):
    assets = os.path.join(tmp(), "assets")
    done = I.apply_assets(inbox, assets, res)
    got = sorted(os.listdir(os.path.join(assets, "tex-test"))) if os.path.isdir(os.path.join(assets, "tex-test")) else []
    check("d. approved images are copied to assets/<id>/ with a manifest.json; scripts, text, rejects and nested files are not", done.get("tex-test") == 1 and got == ["good.png", "manifest.json"], got)
    man = json.load(open(os.path.join(assets, "tex-test", "manifest.json"), encoding="utf-8"))
    check("d. the manifest has name, kind, size, sha256 and pixel size per image, plus the rejected list", man["id"] == "tex-test" and man["files"][0]["name"] == "good.png" and man["files"][0]["w"] == 4
          and len(man["files"][0]["sha256"]) == 64 and any(r["name"] == "evil.js" for r in man["rejected"]), man)
    idx = json.load(open(os.path.join(assets, "index.json"), encoding="utf-8"))
    check("d. assets/index.json lists the jobs with images; a job with no approved image gets no folder; running twice is the same", idx["jobs"] == {"tex-test": 1} and not os.path.exists(os.path.join(assets, "q-test"))
          and I.apply_assets(inbox, assets, res) == done)
    site = os.path.join(tmp(), "site")
    n = I.copy_for_site(site, inbox, res)
    check("d. the site copy (thumbnails for the Deliveries tab) holds only approved top-level images of DONE jobs", n == 1 and os.listdir(os.path.join(site, "tex-test")) == ["good.png"], os.listdir(site) if os.path.isdir(site) else None)
    n2 = I.copy_for_site(os.path.join(tmp(), "s2"), inbox, res, budget=10)
    check("d. the site copy respects its size budget", n2 == 0)
    # the page data: status.json + deliveries.json through bridge_sync.publish with a fake root
    import pathlib
    fake = pathlib.Path(tmp())
    shutil.copytree(inbox, str(fake / "handoff" / "inbox"))
    old = B.ROOT
    B.ROOT = fake
    try:
        st = B.status()
        out = tmp()
        msg = B.publish(out)
    finally:
        B.ROOT = old
    dl = json.load(open(os.path.join(out, "bridge", "deliveries.json"), encoding="utf-8"))
    check("d. status.json lists the delivery (brief: counts, image names, text names, the DONE line); deliveries.json holds the previews", "tex-test" in st["deliveries"] and st["deliveries"]["tex-test"]["images"][:1] == ["good.png"]
          and "text" not in st["deliveries"]["tex-test"] and dl["jobs"]["tex-test"]["text"], st["deliveries"])
    check("d. publish() also copies the approved images next to the page (bridge/deliveries/<id>/) and says so",
          os.path.exists(os.path.join(out, "bridge", "deliveries", "tex-test", "good.png")) and "delivered images" in msg, msg)
    return fake


def part_never_runs():
    src = open(os.path.join(ROOT, "tools", "bridge_ingest.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    code = re.sub(r'(?s)""".*?"""', "", code)
    # the pattern lists name the dangerous words on purpose; look only outside the string patterns of the lists
    body = re.sub(r"(?s)^(SECRETS|JS_BAD|SVG_BAD|MD_BAD) = \[.*?^\]|^MD_BAD = .*$", "", code, flags=re.M)
    body = body.replace("re.compile(", "RECOMP(")          # regular expressions are fine; compiling code is not
    bad = [w for w in ("exec(", "eval(", "compile(", "__import__", "importlib", "subprocess", "runpy", "os.system", "popen", "pickle", "marshal", "ctypes", "socket", "urllib", "requests", "webbrowser") if w in body]
    check("e. the ingest never executes anything: no exec / eval / compile / importlib / subprocess / sockets / urllib in its code", not bad, bad)
    check("e. it only reads bytes and text and copies bytes (shutil.copyfile), and rejects links", "shutil.copyfile" in src and "followlinks=False" in src and "islink" in src)
    s = open(os.path.join(ROOT, "tools", "bridge_sync.py"), encoding="utf-8").read()
    check("e. bridge_sync reaches the ingest only through its read-only functions (deliveries / copy_for_site), inside try / except", "_ingest().deliveries" in s and "_ingest().copy_for_site" in s)


def part_suggest():
    lib = B.library()
    cats = [c["id"] for c in json.load(open(os.path.join(ROOT, "tools", "web_public", "bridge", "jobs.json"), encoding="utf-8"))["cats"]]
    d1, d2 = datetime.date(2026, 11, 4), datetime.date(2026, 11, 11)
    n1 = B.suggest({}, lib, d1, cats)
    check("f. suggest(): at most 5, no duplicates, every item has title / why / minutes / difficulty / rule, all from the library", 1 <= len(n1) <= 5 and len({n["id"] for n in n1}) == len(n1)
          and all(n["id"] in {j["id"] for j in lib} and n["title"] and n["why"] and n["rule"] in ("question", "finish", "first", "week", "gap", "quick") for n in n1), n1)
    check("f. an empty inbox starts with the 'first' win (an easy job)", n1[0]["rule"] == "first" and n1[0]["difficulty"] == "easy", n1[0])
    n2 = B.suggest({}, lib, d2, cats)
    check("f. the category of the week changes with the week (rule 'week' picks differ between 2026-11-04 and 2026-11-11)", [n["id"] for n in n1 if n["rule"] == "week"] != [n["id"] for n in n2 if n["rule"] == "week"]
          and B.suggest({}, lib, d1, cats) == n1, ([n["id"] for n in n1], [n["id"] for n in n2]))
    ids = [j["id"] for j in lib]
    jobs = {ids[0]: {"state": "question", "files": 0}, ids[1]: {"state": "in progress", "files": 2}, ids[2]: {"state": "done", "files": 3}}
    n3 = B.suggest(jobs, lib, d1, cats)
    check("f. a question comes first, then a job still in progress; a delivered job is never suggested again; no 'first' rule once something is delivered",
          n3[0]["id"] == ids[0] and n3[0]["rule"] == "question" and n3[1]["id"] == ids[1] and n3[1]["rule"] == "finish" and ids[2] not in [n["id"] for n in n3] and all(n["rule"] != "first" for n in n3), n3)
    alld = {j["id"]: {"state": "done", "files": 1} for j in lib}
    check("f. everything delivered -> an empty list, not an error; an empty library -> an empty list", B.suggest(alld, lib, d1, cats) == [] and B.suggest({}, [], d1, cats) == [])
    st = B.status()
    check("f. status() carries 'next' (the same rules) and 'deliveries', and keeps the old keys and count names", isinstance(st["next"], list) and isinstance(st["deliveries"], dict)
          and set(st["counts"]) == {"total", "done", "question", "in_progress", "files"} and st["counts"]["total"] == len(B.job_ids()), st["counts"])


def main():
    part_library()
    part_validate()
    inbox, res = part_scan()
    part_prepare(inbox, res)
    part_never_runs()
    part_suggest()
    for d in TMPS:
        shutil.rmtree(d, ignore_errors=True)
    n = sum(RES)
    print(f"\nbridge ingest: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
