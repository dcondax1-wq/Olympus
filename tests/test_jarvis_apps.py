"""Jarvis apps (tools/web_public/jarvis/apps.js, owner 2026-11-01: "make Jarvis an app platform"): the app registry, the
Jarvis status contract (an app's jarvis.json -> a live card on the Jarvis screen), the Ascend slot, and the brief for
whoever builds a dashboard (docs/JARVIS_APPS.md). Runs the real module in Chromium on a local copy of the site layout,
with two local servers (two sites, for CORS), and checks:
  a. files: the module parses as an ES module, nothing newer than iPhone Safari 16, standalone; the brief has the 5-line
     box, frames / viewport / safe areas / dark theme / CORS / the one-paste add, and a full jarvis.json example
  b. registry: the built-ins, add / remove, ids unique and stable (collisions), names capped, bad links refused,
     the same link twice, a name made from the link, adds mirrored for an older Jarvis, the same-site warning
  c. migration from the old keys (jarvis.extra, jarvis.links): nothing lost, old keys untouched, nothing imported twice,
     later additions picked up, removals stick
  d. the contract: the brief's example, missing fields, wrong types, over 8 KB, HTML, control characters, open off-site
  e. renderCard: a card's text never becomes HTML, a button with data-app and a full aria-label, stale shown; inside the
     real Jarvis page: fits the phone, the Jarvis look, a tap opens the app (an app added here shows in today's Jarvis)
  f. fetching: <app>jarvis.json or a statusUrl, another site with / without CORS, the 5 s timeout, failures keep the last
     good card, stale after 30 min, built-ins never fetched, one request at a time, cards posted by an open app
  g. Ascend: hidden until enabled, one tap only from its known link (nothing guessed, never a same-site link), one pasted
     link (a same-site one with the warning), a new link replaces the old, CORS needed on another site
  h. the phone refusing to save: the session keeps working; no page errors
  i. OLYMPUS (2026-11-03): the built-ins come from one table (BUILT_INS: id, name, group, colour; Data City, Mind, Daphne next
     to Zenith, the Planner, Kalshi), listed by group (TRADING, LIFE, MONEY, then the added ones), byGroup's sections, their
     live cards from <folder>/jarvis.json, a folder not on the site = missing() (never a throw), their ids reserved and their
     folders "ours" (no same-site warning), a hand-added copy of a built-in shown once
    python -X utf8 -m tests.test_jarvis_apps      (temp folder + two local servers; nothing else touched, ~20 s)
Screenshots of the cards inside Jarvis: set JARVIS_APPS_SHOTS=<folder>.
"""
from __future__ import annotations

import copy
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys

from tests import browser_kit as BK  # noqa: E402  (shared launch, load-scaled timeouts)
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
APPS = os.path.join(JV, "apps.js")
DOC = os.path.join(ROOT, "docs", "JARVIS_APPS.md")
RES = []
ERRS = []
LOG = []                 # every path the two local sites answered ("<port><path>")
SLOW = {"s": 0.0}        # seconds the /slow/ paths wait before answering


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass

    def end_headers(self):
        if "/cors/" in self.path:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        LOG.append(f"{self.server.server_address[1]}{self.path}")
        if "/slow/" in self.path and SLOW["s"]:
            time.sleep(SLOW["s"])
        return super().do_GET()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):      # a request the page gave up on (the timeout tests)
        pass


def serve(root):
    srv = Server(("127.0.0.1", 0), functools.partial(Handler, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def put(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body if isinstance(body, str) else json.dumps(body))


def card(name, t=None, level="ok", **kw):
    c = {"v": 1, "name": name, "status": {"level": level, "label": "All good"},
         "kpis": [{"label": "Balance", "value": "$1,250", "delta": "+3%"}], "lines": ["Next check 6 PM"],
         "t": int(time.time()) - 60 if t is None else t}
    c.update(kw)
    return c


HARNESS = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
           "<title>apps.js harness</title></head><body><script type='module'>import * as A from './apps.js'; window.A = A; window.ready = true;</script></body></html>")
PUSH = "<!doctype html><title>push</title><script>window.parent.postMessage({jarvis: 1%s, card: %s}, '*');</script>"


def site(tmp):
    base = os.path.join(tmp, "nq-dashboard")
    shutil.copytree(JV, os.path.join(base, "jarvis"))
    put(os.path.join(base, "jarvis", "apps_harness.html"), HARNESS)
    put(os.path.join(base, "index.html"), "<!doctype html><title>Zenith stub</title><h1>Zenith stub</h1>")
    os.makedirs(os.path.join(base, "icons"))
    shutil.copy(os.path.join(JV, "icon-192.png"), os.path.join(base, "icons", "icon-192.png"))
    put(os.path.join(tmp, "clip", "index.html"), "<!doctype html><title>Clip</title><h1 id='c'>Clip stub</h1>")
    return tmp


def fresh(p, harness, extra=None, links=None):
    p.goto(harness)
    p.wait_for_function("window.ready === true")
    p.evaluate("() => localStorage.clear()")
    if extra is not None:
        p.evaluate("(v) => localStorage.setItem('jarvis.extra', v)", json.dumps(extra))
    if links is not None:
        p.evaluate("(v) => localStorage.setItem('jarvis.links', v)", json.dumps(links))
    p.reload()
    p.wait_for_function("window.ready === true")


# ---------------------------------------------------------------------------------------------------- a. files
def part_a():
    src = open(APPS, encoding="utf-8").read()
    check("a. jarvis/apps.js sits next to index.html (the site build publishes every file in jarvis/)", os.path.exists(APPS))
    node = shutil.which("node")
    if node:
        d = tempfile.mkdtemp(prefix="le_apps_syntax_")
        try:
            shutil.copy(APPS, os.path.join(d, "apps.mjs"))
            r = subprocess.run([node, "--check", os.path.join(d, "apps.mjs")], capture_output=True, text=True)
            check("a. apps.js parses as an ES module (node --check)", r.returncode == 0, r.stderr)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        acorn = next(iter(sorted(glob.glob("/opt/node-tools/node_modules/acorn/dist/acorn.js"))), None)
        if acorn:                      # a real parser held to ES2020 (Safari 14+), where this machine has one
            js = (f"require({json.dumps(acorn)}).parse(require('fs').readFileSync({json.dumps(APPS)}, 'utf8'), "
                  "{ecmaVersion: 2020, sourceType: 'module'})")
            r = subprocess.run([node, "-e", js], capture_output=True, text=True)
            check("a. apps.js parses as ES2020 (acorn): nothing newer than iPhone Safari 16 can parse", r.returncode == 0, r.stderr)
    else:
        print("[SKIP] a. node not installed: the browser import below still checks the syntax")
    code = re.sub(r"/\*.*?\*/", "", re.sub(r"(?m)^\s*//.*$", "", src), flags=re.S)
    newer = [t for t in ("(?<=", "(?<!", "static {", "Object.groupBy", "Map.groupBy", "Promise.withResolvers", "Array.fromAsync", "isWellFormed",
                         "toWellFormed", "AbortSignal.timeout", "AbortSignal.any", "Symbol.dispose", "structuredClone", "with { type", "/v.test")
             if t in code]
    check("a. nothing newer than iPhone Safari 16 (no lookbehind, static blocks, groupBy, AbortSignal.timeout ...)", not newer, newer)
    check("a. plain ASCII source (escapes, no literal line separators that would break a regex)", all(ord(c) < 128 for c in src),
          [(i, hex(ord(c))) for i, c in enumerate(src) if ord(c) >= 128][:5])
    globals_used = re.findall(r"(?<![\w.$])(?:document|window)\s*\.", code)
    check("a. standalone: no imports; no page globals (document only as renderCard's argument, window only as listen's default)",
          not re.search(r"(?m)^\s*import\b", code) and not globals_used and code.count("typeof document") == 1, globals_used)
    doc = open(DOC, encoding="utf-8").read()
    blocks = re.findall(r"```(\w*)\n(.*?)```", doc, re.S)
    box = [ln for ln in (blocks[0][1] if blocks else "").splitlines() if ln.strip()]
    check("a. the brief opens with a 5-line 'send this to ChatGPT' box: its own site (never under the owner's github.io), jarvis.json with CORS",
          "Send this to ChatGPT" in doc[:200] and len(box) == 5 and doc.index("```") < 300 and "never under demetrades2000-coder.github.io" in box[1]
          and "jarvis.json" in box[3] and "Access-Control-Allow-Origin: *" in box[3], box)
    keys = ("X-Frame-Options", "frame-ancestors", "viewport-fit=cover", "safe-area-inset", "#0b0b0d", "manifest.webmanifest")
    check("a. the brief: let it be framed, phone viewport, safe areas, the dark theme, Home Screen manifest", all(k in doc for k in keys), [k for k in keys if k not in doc])
    keys = ("Netlify", "Vercel", "Cloudflare Pages", "another account", "shares one origin with Jarvis", "could read the keys")
    check("a. the brief: Ascend on its own site (Netlify, Vercel, Cloudflare Pages, another account's Pages), the one-line why; "
          "no same-site address suggested, no storage key names", all(k in doc for k in keys) and "github.io/ascend" not in doc
          and "jarvis.smart" not in doc and "planner.sync" not in doc, [k for k in keys if k not in doc])
    keys = ("Access-Control-Allow-Origin: *", "_headers", "vercel.json", "8 KB", "Plain text only", "30 minutes", "Add Ascend", "postMessage")
    check("a. the brief: CORS is needed (and how: _headers, vercel.json), 8 KB, plain text, the 30-minute grey, the one-paste add",
          all(k in doc for k in keys), [k for k in keys if k not in doc])
    ex = next((b for lang, b in blocks if lang == "json"), "{}")
    example = json.loads(ex)
    check("a. the brief's jarvis.json example has every field of the contract", all(k in example for k in ("v", "name", "status", "kpis", "lines", "t", "open")), example)
    return example


# ---------------------------------------------------------------------------------------------------- b. registry
WARN = "same-site apps can read Jarvis's saved keys"


def part_b(p, harness, oa, ob):
    fresh(p, harness)
    ids = p.evaluate("() => A.listApps().map((a) => [a.id, a.url, a.builtin, a.removable].join('|'))")
    want = p.evaluate("() => A.BUILT_INS.map((b) => [b.id, b.url, true, false].join('|'))")
    check("b. built in: Zenith ../, Planner ../planner/, Kalshi ../kalshi/ (as the Jarvis page has them) and every OLYMPUS app, not removable",
          sorted(ids) == sorted(want) and {"zenith|../|true|false", "planner|../planner/|true|false", "kalshi|../kalshi/|true|false"} <= set(ids), ids)
    nb = len(want)
    h = p.evaluate("() => A.listApps({hidden: true}).find((a) => a.id === 'ascend')")
    check("b. the Ascend slot is registered but hidden (enabled false, no link)", h and h["enabled"] is False and h["url"] == "" and h["hidden"] is True, h)
    clip = oa + "/clip/"
    r1 = p.evaluate("(u) => A.addApp({name: 'Clipper', url: u})", clip)
    check("b. add: id x-clipper, its card at <link>jarvis.json, removable",
          r1["ok"] and r1["app"]["id"] == "x-clipper" and r1["app"]["statusUrl"] == clip + "jarvis.json" and r1["app"]["removable"] and r1["app"]["glyph"] == "C", r1)
    adds = p.evaluate("""() => [A.addApp({name: 'Clipper', url: 'https://clip2.example/'}), A.addApp({name: 'clipper!!', url: 'https://clip3.example/'}),
        A.addApp({name: 'My App', url: 'https://a.example/'}), A.addApp({name: 'my-app', url: 'https://b.example/'}),
        A.addApp({name: '\u00dcn\u00efcode Caf\u00e9', url: 'https://c.example/'}), A.addApp({name: '\u65e5\u672c\u8a9e', url: 'https://d.example/'}),
        A.addApp({name: '\u65e5\u672c', url: 'https://e.example/'}), A.addApp({name: 'Home', url: 'https://f.example/'}),
        A.addApp({name: 'Zenith', url: 'https://g.example/'})].map((r) => r.app.id)""")
    check("b. id collisions: the same name, or names that read alike, get -2, -3 (never a built-in's id)",
          adds == ["x-clipper-2", "x-clipper-3", "x-my-app", "x-my-app-2", "x-unicode-cafe", "x-app", "x-app-2", "x-home", "x-zenith"], adds)
    all_ids = p.evaluate("() => A.listApps().map((a) => a.id)")
    check("b. every id is unique and safe in an element id / selector", len(all_ids) == len(set(all_ids)) and all(re.fullmatch(r"[a-z0-9-]+", i) for i in all_ids), all_ids)
    long_ = p.evaluate("() => A.addApp({name: '  A very\\nlong\\tdashboard name that keeps going on  ', url: 'https://h.example/'}).app.name")
    check("b. names are capped at 24 characters, on one line", long_ == "A very long dashboard na", long_)
    same = p.evaluate("(u) => [A.addApp({name: 'Clip again', url: u}), A.listApps().length]", clip)
    check("b. the same link twice: the app already there (existed), no second entry",
          same[0]["ok"] and same[0]["existed"] and same[0]["app"]["id"] == "x-clipper" and same[1] == len(all_ids) + 1, same)
    check("b. a link on Jarvis's own origin outside our pages is added, with the warning in the result and on the app (even when it existed)",
          p.evaluate("() => A.SAME_SITE_WARN") == WARN and r1.get("warn") == WARN and r1["app"].get("warn") == WARN and same[0].get("warn") == WARN, (r1, same[0]))
    bads = p.evaluate("""() => [A.addApp({name: 'x', url: 'javascript:alert(1)'}), A.addApp({name: 'x', url: 'ftp://files.example/'}),
        A.addApp({name: 'x', url: 'data:text/html,<b>hi</b>'}), A.addApp({name: 'x', url: 'https://user:pw@secret.example/'}),
        A.addApp({name: 'x', url: ''}), A.addApp({name: 'x'}), A.addApp(null),
        A.addApp({name: 'x', url: 'https://ok.example/', statusUrl: 'javascript:alert(1)'}),
        A.addApp({name: 'x', url: 'https://ok.example/', icon: 'data:image/png;base64,AAAA'})].map((r) => (r.ok ? 'ok' : r.field) + (r.error ? '' : '!'))""")
    check("b. refused, with a plain reason: javascript:, ftp:, data:, a link with a password, no link; a bad status link or icon",
          bads == ["url"] * 7 + ["statusUrl", "icon"], bads)
    bare = p.evaluate("() => A.addApp({name: 'Bare', url: 'example.org/dash'}).app.url")
    check("b. a link pasted without https:// works", bare == "https://example.org/dash", bare)
    auto = p.evaluate("() => A.addApp({url: 'https://lift.example/lift-log/'}).app")
    check("b. no name: one is made from the link ('Lift log')", auto["name"] == "Lift log" and auto.get("autoName") is True and auto["id"] == "x-lift-log", auto)
    before = p.evaluate("() => A.listApps().map((a) => a.id + '=' + a.name + '=' + a.url)")
    p.reload()
    p.wait_for_function("window.ready === true")
    after = p.evaluate("() => A.listApps().map((a) => a.id + '=' + a.name + '=' + a.url)")
    check("b. ids, names and order are the same after a reload", before == after, (before, after))
    rm = p.evaluate("() => [A.removeApp('x-clipper-2'), A.removeApp('zenith'), A.removeApp('nope'), A.removeApp('ascend'), A.removeApp(42), A.listApps().some((a) => a.id === 'x-clipper-2')]")
    check("b. remove: an added app goes; a built-in, an unknown id and the hidden Ascend stay (false)", rm == [True, False, False, False, False, False], rm)
    ex = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.extra'))")
    check("b. adds and removals are mirrored into jarvis.extra as an older Jarvis writes it ({id, name, url})",
          {"id": "x-clipper", "name": "Clipper", "url": clip} in ex and not any(e["id"] == "x-clipper-2" for e in ex) and all(set(e) == {"id", "name", "url"} for e in ex)
          and len(ex) == len(after) - nb - 1, ex)
    ws = p.evaluate("""([oa, ob]) => [oa + '/nq-dashboard/ascend/', oa + '/ascend/', oa + '/nq-dashboard/next/', oa + '/nq-dashboard/planner/week/',
        oa + '/nq-dashboard/planner', oa + '/nq-dashboard/kalshi/history.html', oa + '/nq-dashboard/jarvis/other.html', oa + '/nq-dashboard/index.html',
        ob + '/x/', 'https://ascend.example/'].map((u) => { const r = A.addApp({name: 'W', url: u}); return [r.ok, r.warn === A.SAME_SITE_WARN, A.sameSiteRisk(u)]; })""", [oa, ob])
    check("b. the warning only on Jarvis's origin outside Zenith's page, planner/, kalshi/ and jarvis/ (never another site); all are added",
          [w[1] for w in ws] == [True] * 3 + [False] * 7 and [w[2] for w in ws] == [w[1] for w in ws] and all(w[0] for w in ws), ws)
    flagged = p.evaluate("() => A.listApps().filter((a) => a.warn).map((a) => a.id)")
    check("b. listApps marks those apps (warn) so the page can show it; built-ins never", "x-clipper" in flagged and len(flagged) == 4
          and not any(i in flagged for i in ("zenith", "planner", "kalshi")), flagged)


# ---------------------------------------------------------------------------------------------------- c. migration
def part_c(p, harness, oa):
    planner = oa + "/nq-dashboard/planner/"
    extra = [
        {"id": "x-clipper", "name": "Clipper", "url": "https://clip.example/"},
        {"id": "x-clipper", "name": "Clipper two", "url": "https://clip2.example/"},      # the same id twice
        {"id": "x-bad", "name": "Bad", "url": "javascript:alert(1)"},                      # never shown: left as it is
        {"id": "x-ascend", "name": "Ascend", "url": "https://asc.example/"},
        {"name": "No id", "url": "https://noid.example/"},
        {"id": "x-long", "name": "A very long dashboard name indeed", "url": "https://long.example/", "note": "kept"},
        {"id": "zenith", "name": "Zenith 2", "url": "https://z2.example/"},                 # a reserved id
    ]
    links = {"kalshi": "https://my-kalshi.example/", "planner": planner, "foo_bar": "https://foo.example/"}
    fresh(p, harness, extra=extra, links=links)
    raw0 = p.evaluate("() => [localStorage.getItem('jarvis.extra'), localStorage.getItem('jarvis.links')]")
    apps = p.evaluate("() => A.listApps().map((a) => ({id: a.id, name: a.name, url: a.url}))")
    got = {a["url"]: a for a in apps}
    want = ["https://clip.example/", "https://clip2.example/", "https://asc.example/", "https://noid.example/", "https://long.example/",
            "https://z2.example/", "https://my-kalshi.example/", "https://foo.example/"]
    check("c. nothing lost: every entry an older Jarvis saved (jarvis.extra and jarvis.links) is in the list", all(u in got for u in want), [u for u in want if u not in got])
    ids = [a["id"] for a in apps]
    check("c. ids kept where free; the same id twice and a reserved id get new unique ids",
          got["https://clip.example/"]["id"] == "x-clipper" and got["https://clip2.example/"]["id"] == "x-clipper-two" and got["https://long.example/"]["id"] == "x-long"
          and got["https://noid.example/"]["id"] == "x-no-id" and got["https://z2.example/"]["id"] == "x-zenith-2" and len(ids) == len(set(ids)), apps)
    check("c. 'Ascend' fills the Ascend slot; a Kalshi link pasted before Kalshi was built in stays as 'Kalshi link'",
          got["https://asc.example/"]["id"] == "ascend" and got["https://my-kalshi.example/"]["name"] == "Kalshi link" and got["https://foo.example/"]["name"] == "Foo bar", apps)
    core = {a["id"]: a["url"] for a in apps if a["id"] in ("zenith", "planner", "kalshi")}
    check("c. the built-ins keep their own links (a saved link equal to the built-in's adds nothing)",
          core == {"zenith": "../", "planner": "../planner/", "kalshi": "../kalshi/"} and planner not in got, apps[:8])
    check("c. names capped at 24", got["https://long.example/"]["name"] == "A very long dashboard na", got["https://long.example/"])
    raw1 = p.evaluate("() => [localStorage.getItem('jarvis.extra'), localStorage.getItem('jarvis.links')]")
    check("c. non-destructive: moving them leaves the old keys untouched, byte for byte", raw0 == raw1, (raw0, raw1))
    reg = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.apps'))")
    check("c. the registry is saved under jarvis.apps (v 1)", reg and reg["v"] == 1 and len(reg["apps"]) == 7 and reg["ascend"]["url"] == "https://asc.example/", reg)
    p.reload()
    p.wait_for_function("window.ready === true")
    apps2 = p.evaluate("() => A.listApps().map((a) => ({id: a.id, name: a.name, url: a.url}))")
    check("c. a second load imports nothing twice (same list, same ids)", apps2 == apps, apps2)
    p.evaluate("() => { const x = JSON.parse(localStorage.getItem('jarvis.extra')); x.push({id: 'x-new', name: 'New', url: 'https://new.example/'}); localStorage.setItem('jarvis.extra', JSON.stringify(x)); }")
    check("c. an app an older copy of Jarvis adds later is picked up", p.evaluate("() => A.listApps().some((a) => a.id === 'x-new' && a.url === 'https://new.example/')"))
    p.evaluate("() => A.removeApp('x-clipper')")
    p.reload()
    p.wait_for_function("window.ready === true")
    left = p.evaluate("() => [A.listApps().some((a) => a.url === 'https://clip.example/'), JSON.parse(localStorage.getItem('jarvis.extra'))]")
    check("c. a removed app stays removed after a reload (gone from jarvis.extra; the other entries, even the one it cannot show, stay)",
          left[0] is False and not any(e.get("url") == "https://clip.example/" for e in left[1]) and any(e.get("id") == "x-bad" for e in left[1])
          and any(e.get("url") == "https://clip2.example/" for e in left[1]) and any(e.get("note") == "kept" for e in left[1]), left)
    p.evaluate("() => { const x = JSON.parse(localStorage.getItem('jarvis.extra')); x.push({id: 'x-clipper', name: 'Clipper', url: 'https://clip.example/'}); localStorage.setItem('jarvis.extra', JSON.stringify(x)); }")
    check("c. an older Jarvis adding it again brings it back", p.evaluate("() => A.listApps().some((a) => a.url === 'https://clip.example/' && a.id === 'x-clipper')"))
    asc = p.evaluate("() => [A.removeApp('ascend'), A.ascendSlot().enabled, JSON.parse(localStorage.getItem('jarvis.extra')).some((e) => e.url === 'https://asc.example/'), A.listApps().length]")
    check("c. removing Ascend hides it again (its old entry goes too)", asc[:3] == [True, False, False] and asc[3] == len(apps), asc)
    fresh(p, harness, extra=[{"id": "x-ascend-2", "name": "Ascend 2", "url": "https://asc2.example/"}, {"id": "x-ascend", "name": "ASCEND", "url": "https://asc3.example/"}])
    a2 = p.evaluate("() => [A.ascendSlot().url, A.listApps().filter((a) => a.name === 'Ascend 2').map((a) => a.id)]")
    check("c. only an entry named Ascend fills the slot ('Ascend 2' stays its own app)", a2 == ["https://asc3.example/", ["x-ascend-2"]], a2)


# ---------------------------------------------------------------------------------------------------- d. the contract
DEL = object()


def part_d(p, harness, oa, example):
    fresh(p, harness)
    now = int(time.time())
    base = oa + "/clip/"
    good = dict(copy.deepcopy(example), t=now - 60)
    r = p.evaluate("([j, b]) => A.validateStatus(j, {base: b})", [good, base])
    k = r.get("card", {}).get("kpis", [{}, {}, {}])
    check("d. the brief's example passes: values as text (82 -> '82', -3 -> '-3' down, '+1' up), open inside the app",
          r["ok"] and k[2]["value"] == "82" and k[2]["delta"] == "-3" and k[2]["trend"] == "down" and k[0]["trend"] == "up" and "delta" not in k[1]
          and r["card"]["openUrl"] == base + "#today" and set(r["card"]) == {"v", "name", "status", "kpis", "lines", "t", "open", "openUrl", "theme"} and r["card"]["theme"] == "#0b0b0d", r)
    bt = p.evaluate("([j, b]) => [A.validateStatus(Object.assign({}, j, {theme: 'red'}), {base: b}).ok, A.validateStatus(Object.assign({}, j, {theme: '#0B0B0D '}), {base: b}).card.theme]", [good, base])
    sa = p.evaluate("([j, b]) => [A.validateStatus(Object.assign({}, j, {stale_after: 259200}), {base: b}).card.stale_after, A.validateStatus(Object.assign({}, j, {stale_after: 5}), {base: b}).ok, A.validateStatus(Object.assign({}, j, {stale_after: 'x'}), {base: b}).ok]", [good, base])
    check("d. stale_after (2026-11-03, CRONOS): seconds kept (60 s - 14 days), anything else refused", sa == [259200, False, False], sa)
    check("d. theme (2026-11-02): only a #rrggbb colour (its top colour inside Jarvis), kept lower-case", bt == [False, "#0b0b0d"], bt)
    check("d. the same as text, as it is fetched", p.evaluate("([j, b]) => A.validateStatus(JSON.stringify(j), {base: b}).ok", [good, base]) is True)

    def m(path, value):
        c = copy.deepcopy(good)
        *head, last = path
        x = c
        for key in head:
            x = x[key]
        if value is DEL:
            del x[last]
        else:
            x[last] = value
        return c
    cases = [
        ("missing v", m(["v"], DEL), "v must be 1"), ("missing name", m(["name"], DEL), "name must be text"),
        ("missing status", m(["status"], DEL), "status is missing"), ("missing status.level", m(["status", "level"], DEL), "status.level"),
        ("missing status.label", m(["status", "label"], DEL), "status.label must be text"), ("missing t", m(["t"], DEL), "t is missing"),
        ("missing kpi label", m(["kpis", 0, "label"], DEL), "kpis[0].label"), ("missing kpi value", m(["kpis", 1, "value"], DEL), "kpis[1].value"),
        ("v as text", m(["v"], "1"), "v must be 1"), ("v 2", m(["v"], 2), "v must be 1"), ("name a number", m(["name"], 5), "name must be text"),
        ("status as text", m(["status"], "ok"), "status is missing"), ("level green", m(["status", "level"], "green"), "status.level"),
        ("t as text", m(["t"], str(now)), "t is missing"), ("t in ms", m(["t"], now * 1000), "not milliseconds"),
        ("t an hour ahead", m(["t"], now + 3600), "future"), ("kpis an object", m(["kpis"], {}), "kpis must be a list"),
        ("4 kpis", m(["kpis"], good["kpis"] + good["kpis"][:1]), "at most 3"), ("kpi value an object", m(["kpis", 0, "value"], {}), "text or a number"),
        ("kpi value true", m(["kpis", 0, "value"], True), "text or a number"), ("lines as text", m(["lines"], "one line"), "lines must be a list"),
        ("4 lines", m(["lines"], ["a", "b", "c", "d"]), "at most 3"), ("a line a number", m(["lines"], [1]), "lines[0] must be text"),
        ("open a number", m(["open"], 5), "open must be"), ("open another site", m(["open"], "https://evil.example/"), "stay inside the app"),
        ("open javascript:", m(["open"], "javascript:alert(1)"), "stay inside the app"), ("empty name", m(["name"], "  "), "name is empty"),
        ("name 41 characters", m(["name"], "N" * 41), "longer than 40"), ("label 49", m(["status", "label"], "L" * 49), "longer than 48"),
        ("kpi value 25", m(["kpis", 0, "value"], "9" * 25), "longer than 24"), ("line 121", m(["lines"], ["x" * 121]), "longer than 120"),
        ("a list", [good], "not a JSON object"), ("null", None, "not a JSON object"),
        ("over 8 KB", m(["pad"], "x" * 9000), "8 KB"),
        ("HTML in name", m(["name"], "<b>Ascend</b>"), "HTML"), ("HTML in label", m(["status", "label"], "All <i>good</i>"), "HTML"),
        ("HTML in a kpi label", m(["kpis", 0, "label"], "<img src=x onerror=alert(1)>"), "HTML"),
        ("script in a kpi value", m(["kpis", 0, "value"], "<script>alert(1)</script>"), "HTML"),
        ("an entity in a line", m(["lines"], ["a &amp; b"]), "HTML"), ("a numeric entity", m(["lines"], ["&#60;script&#62;"]), "HTML"),
        ("a comment", m(["lines"], ["<!-- x -->"]), "HTML"), ("a closing tag", m(["kpis", 0, "delta"], "</b>"), "HTML"),
        ("a line break", m(["lines"], ["two\nlines"]), "control characters"), ("right-to-left override", m(["name"], "Asc\u202eend"), "control characters"),
    ]
    out = p.evaluate("([cs, b]) => cs.map((j) => A.validateStatus(j, {base: b}))", [[c[1] for c in cases], base])
    wrong = [(c[0], o) for c, o in zip(cases, out) if o["ok"] or c[2] not in o["error"]]
    check(f"d. {len(cases)} bad files refused with the field named (missing fields, wrong types, over 8 KB, HTML, control characters, open off-site)",
          not wrong and len(out) == len(cases), wrong)
    texts = p.evaluate("() => [A.validateStatus('x'.repeat(9000)).error, A.validateStatus('{not json').error, A.validateStatus('').error]")
    check("d. as text: over 8 KB, not JSON, empty", "8 KB" in texts[0] and "JSON" in texts[1] and "JSON" in texts[2], texts)
    okc = p.evaluate("""([g, b]) => [A.validateStatus(Object.assign({}, g, {lines: ['a < b and c > d', 'R&D', 'Q&A: 5 > 3']}), {base: b}).ok,
        A.validateStatus({v: 1, name: 'Bare', status: {level: 'off', label: 'Paused'}, t: g.t}).card,
        A.validateStatus(Object.assign({}, g, {t: g.t - 7200}), {base: b}).ok, A.validateStatus(Object.assign({}, g, {open: '#a', kpis: null, lines: null})).card]""", [good, base])
    check("d. allowed: a lone < or & in text, no kpis / lines (empty), an old t (stale later, not refused), open without a base",
          okc[0] is True and okc[1]["kpis"] == [] and okc[1]["lines"] == [] and okc[2] is True and okc[3]["open"] == "#a" and "openUrl" not in okc[3], okc)


# ---------------------------------------------------------------------------------------------------- e. renderCard
def part_e(p, harness):
    fresh(p, harness)
    now = int(time.time())
    evil = {"app": "x-evil", "name": '<img src=x onerror="window.pwned=1">', "status": {"level": "bad", "label": "<script>window.pwned=2</script>"},
            "kpis": [{"label": '"><svg onload=window.pwned=3>', "value": "<b>1</b>", "delta": "<i>2</i>", "trend": "up"}],
            "lines": ["<iframe src=javascript:window.pwned=4></iframe>", "&lt;b&gt;"], "t": now - 60, "icon": "javascript:window.pwned=5",
            "openUrl": "javascript:window.pwned=6", "sub": "<u>x</u>", "glyph": "<"}
    out = p.evaluate("""async (c) => {
        const n = A.renderCard(c, document); document.body.appendChild(n);
        await new Promise((r) => setTimeout(r, 200));
        const all = [n, ...n.querySelectorAll('*')];
        return {tag: n.tagName, type: n.getAttribute('type'), tags: all.map((x) => x.tagName.toLowerCase()), attrs: all.flatMap((x) => [...x.attributes].map((a) => a.name)),
                text: n.textContent, html: n.innerHTML, open: n.getAttribute('data-open'), app: n.getAttribute('data-app'), label: n.getAttribute('aria-label'),
                glyphHidden: n.querySelector('svg.glyph').getAttribute('aria-hidden'), goHidden: n.querySelector('.go').getAttribute('aria-hidden'),
                pwned: window.pwned === undefined ? null : window.pwned};
    }""", evil)
    shape = ["button", "div", "svg", "rect", "text", "circle", "div", "b", "small", "span", "span", "div", "div", "span", "strong", "em", "ul", "li", "span", "li", "span"]
    check("e. renderCard: a card's text never becomes HTML (only the card's own elements, no on* attribute, nothing ran)",
          out["tags"] == shape and out["pwned"] is None and not any(a.startswith("on") for a in out["attrs"]) and out["open"] is None and out["tags"].count("svg") == 1
          and '<img src=x onerror="window.pwned=1">' in out["text"] and "<script>window.pwned=2</script>" in out["text"], out)
    check("e. it is escaped in the markup (&lt;img, &lt;script&gt;)", "&lt;img src=x" in out["html"] and "&lt;script&gt;" in out["html"] and "&amp;lt;b&amp;gt;" in out["html"], out["html"][:400])
    check("e. accessible: a <button type=button data-app>, its aria-label reads the card (name, level word, label, kpis, lines), icons hidden",
          out["tag"] == "BUTTON" and out["type"] == "button" and out["app"] == "x-evil" and out["label"].startswith('<img src=x onerror="window.pwned=1">. Problem: <script>')
          and "&lt;b&gt;." in out["label"] and out["label"].endswith("Opens <img src=x onerror=\"window.pwned=1\">.") and out["glyphHidden"] == "true" and out["goHidden"] == "true", out["label"])
    st = p.evaluate("""(t) => { const n = A.renderCard({app: 'x-a', name: 'Ascend', status: {level: 'ok', label: 'On track'}, kpis: [], lines: [], t: t}, document);
        const a = A.renderCard({name: 'Preview', status: {level: 'warn', label: 'Check'}, t: t + 1800}, document);
        return [n.className, n.querySelector('.pill').className, n.querySelector('.pill').textContent, n.getAttribute('aria-label'), a.tagName, a.hasAttribute('data-app'),
                a.querySelector('.pill').className, document.querySelectorAll('#jx-apps-css').length]; }""", now - 31 * 60)
    check("e. stale (t over 30 min old): grey pill 'not updated for 31 min', said in the aria-label too",
          "jx-stale" in st[0] and st[1] == "pill" and st[2] == "On track \u00b7 not updated for 31 min" and st[3].startswith("Ascend. Not updated for 31 min. Last status OK: On track."), st)
    check("e. a card with no app is an <article> (not tappable); the card styles are added once", st[4] == "ARTICLE" and st[5] is False and st[6] == "pill warn" and st[7] == 1, st)


def part_e_shell(br, shell, oa, shots):
    """The cards inside the real Jarvis page (its CSS): fit the phone, the Jarvis look, a tap opens the app."""
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())
    p = ctx.new_page()
    p.on("pageerror", lambda e: ERRS.append("shell: " + str(e)))
    p.goto(shell)
    p.wait_for_selector("#cards .card")
    p.evaluate("(u) => import('./apps.js').then((A) => A.addApp({name: 'Clip', url: u}))", oa + "/clip/")
    p.reload()
    p.wait_for_selector("#cards .card")
    check("e. today's Jarvis page shows an app added through apps.js (mirrored into jarvis.extra)", "Clip" in p.inner_text("#apps"), p.inner_text("#apps"))
    now = int(time.time())
    good = {"app": "x-clip", "appName": "Clip", "name": "Ascend", "sub": "127.0.0.1", "status": {"level": "ok", "label": "On track"},
            "kpis": [{"label": "This week", "value": "4 of 5", "delta": "+1", "trend": "up"}, {"label": "Streak", "value": "12 days"},
                     {"label": "Score", "value": "82", "delta": "-3", "trend": "down"}],
            "lines": ["Next: review at 6:30 PM", "2 tasks due today, and a much longer third line that has to wrap onto a second line on a phone"],
            "t": now - 120, "age": 120, "stale": False, "cached": False, "openUrl": oa + "/clip/#today"}
    stale = dict(good, t=now - 31 * 60, age=31 * 60, stale=True, kpis=good["kpis"][:2], lines=[])
    out = p.evaluate("""async ([c, s]) => {
        const A = await import('./apps.js');
        const box = document.getElementById('cards');
        const n = A.renderCard(c, document), m = A.renderCard(s, document);
        box.prepend(m); box.prepend(n);
        await new Promise((r) => setTimeout(r, 150));
        const col = (q) => getComputedStyle(n.querySelector(q)).color;
        return {w: [document.documentElement.scrollWidth, document.documentElement.clientWidth],
                right: Math.max(n.getBoundingClientRect().right, m.getBoundingClientRect().right), pill: n.querySelector('.pill').className,
                pillText: n.querySelector('.pill').textContent, up: col('.jx-delta.up'), down: col('.jx-delta.down'), bg: getComputedStyle(n).backgroundColor,
                kv: getComputedStyle(n.querySelector('.kv')).gridTemplateColumns.split(' ').length, kv2: getComputedStyle(m.querySelector('.kv')).gridTemplateColumns.split(' ').length,
                staleCls: m.className, open: n.getAttribute('data-open'), h: Math.round(n.getBoundingClientRect().height)};
    }""", [good, stale])
    if shots:
        os.makedirs(shots, exist_ok=True)
        p.screenshot(path=os.path.join(shots, "jarvis_app_cards.png"))
    check("e. inside Jarvis at phone width: no sideways scroll, the cards fit the gutter", out["w"][0] <= out["w"][1] and out["right"] <= 390 - 15.5, out)
    check("e. the Jarvis look (AGORA bronze since e02d070): its card panel, green pill, green / red deltas, 3 kpis in a row (2 when 2)",
          out["bg"] == "rgb(29, 25, 20)" and out["pill"] == "pill ok" and out["pillText"] == "On track \u00b7 2 min ago" and out["up"] == "rgb(171, 181, 104)"
          and out["down"] == "rgb(207, 132, 110)" and out["kv"] == 3 and out["kv2"] == 2 and "jx-stale" in out["staleCls"] and out["open"] == oa + "/clip/#today", out)
    p.click("#cards .jx-card[data-app='x-clip']")
    p.wait_for_timeout(700)
    check("e. tapping the card opens its app inside Jarvis (the page's own data-app switch)",
          p.locator("#v-x-clip").is_visible() and p.frame_locator("#v-x-clip iframe").locator("#c").inner_text() == "Clip stub", p.url)
    ctx.close()


# ---------------------------------------------------------------------------------------------------- f. fetching
def part_f(p, harness, oa, ob, tmp):
    fresh(p, harness)
    now = int(time.time())
    put(f"{tmp}/clip/jarvis.json", card("Clip", t=now - 60))
    app = p.evaluate("(u) => A.addApp({name: 'Clip', url: u}).app", oa + "/clip/")
    LOG.clear()
    c = p.evaluate("(a) => A.appStatus(a)", app)
    check("f. same site: the card from <app>/jarvis.json (fresh: not stale, not cached), with the app's id and name",
          c and c["name"] == "Clip" and c["status"]["level"] == "ok" and c["stale"] is False and c["cached"] is False and c["app"] == "x-clip"
          and c["appName"] == "Clip" and c["kpis"][0]["value"] == "$1,250" and 50 <= c["age"] <= 120, c)
    hits = [x for x in LOG if "/clip/jarvis.json" in x]
    check("f. read from the app's folder, with a minute cache buster (GitHub Pages' CDN)", len(hits) == 1 and "?jt=" in hits[0], LOG)
    kept = p.evaluate("() => JSON.parse(localStorage.getItem('jarvis.cards'))")
    check("f. the last good card is kept on the phone (jarvis.cards)", kept and kept["x-clip"]["card"]["name"] == "Clip" and kept["x-clip"]["url"] == oa + "/clip/jarvis.json", kept)
    p.reload()
    p.wait_for_function("window.ready === true")
    rc = p.evaluate("() => A.cachedStatus('x-clip')")
    check("f. after a reload it is there at once, before any fetch (cachedStatus)", rc and rc["cached"] is True and rc["name"] == "Clip" and rc["stale"] is False, rc)
    put(f"{tmp}/cors/app/jarvis.json", card("Other", t=now - 30))
    put(f"{tmp}/nocors/app/jarvis.json", card("NoCors", t=now - 30))
    oc = p.evaluate("([u, s]) => A.appStatus(A.addApp({name: 'Other', url: u, statusUrl: s}).app)", [ob + "/other/", ob + "/cors/app/jarvis.json"])
    check("f. another site sending Access-Control-Allow-Origin: * (here through a statusUrl): read", oc and oc["name"] == "Other" and oc["app"] == "x-other", oc)
    nc = p.evaluate("async (u) => { const a = A.addApp({name: 'NoCors', url: u}).app; const c = await A.appStatus(a); return [c, A.statusError(a)]; }", ob + "/nocors/app/")
    check("f. another site without CORS: no card (null), the reason kept, nothing thrown", nc[0] is None and nc[1], nc)
    put(f"{tmp}/clip/jarvis.json", "{not json")
    c2 = p.evaluate("async (a) => [await A.appStatus(a), A.statusError(a)]", app)
    check("f. a broken file: the last good card (cached: true) and the reason", c2[0] and c2[0]["cached"] is True and c2[0]["name"] == "Clip" and "JSON" in c2[1], c2)
    os.remove(f"{tmp}/clip/jarvis.json")
    c3 = p.evaluate("async (a) => [await A.appStatus(a), A.statusError(a)]", app)
    check("f. no file (404): the last good card", c3[0] and c3[0]["cached"] is True and "404" in c3[1], c3)
    put(f"{tmp}/clip/jarvis.json", dict(card("Clip", t=now), pad="x" * 9000))
    c4 = p.evaluate("async (a) => [await A.appStatus(a), A.statusError(a)]", app)
    check("f. a file over 8 KB: refused, the last good card", c4[0] and c4[0]["cached"] is True and "8 KB" in c4[1], c4)
    put(f"{tmp}/clip/jarvis.json", card("Clip", t=now - 5, lines=["<b>bold</b>"]))
    c5 = p.evaluate("async (a) => [await A.appStatus(a), A.statusError(a)]", app)
    check("f. a file with HTML: refused, the last good card", c5[0] and c5[0]["cached"] is True and c5[0]["lines"] == ["Next check 6 PM"] and "HTML" in c5[1], c5)

    put(f"{tmp}/slow/app/jarvis.json", card("Slow", t=now - 10))
    sl = p.evaluate("(u) => A.addApp({name: 'Slow', url: u}).app", oa + "/slow/app/")
    SLOW["s"] = 0
    first = p.evaluate("(a) => A.appStatus(a)", sl)
    SLOW["s"] = 3
    t0 = time.time()
    r = p.evaluate("async (a) => [await A.appStatus(a, {timeoutMs: 600}), A.statusError(a)]", sl)
    dt = time.time() - t0
    check("f. a slow site: Jarvis stops waiting at the timeout and shows the last good card", first and first["cached"] is False and dt < 2.0
          and r[0] and r[0]["cached"] is True and r[1] == "timeout", (dt, r))
    SLOW["s"] = 7
    t0 = time.time()
    r = p.evaluate("async (a) => [await A.appStatus(a), A.TIMEOUT_MS]", sl)
    dt = time.time() - t0
    SLOW["s"] = 0
    check("f. the default wait is 5 s", r[1] == 5000 and 4.5 <= dt < 6.8 and r[0] and r[0]["cached"] is True, (round(dt, 2), r))
    SLOW["s"] = 1.0
    gone = p.evaluate("""async (a) => { const pr = A.appStatus(a); await new Promise((r) => setTimeout(r, 250)); A.removeApp(a.id); const c = await pr;
        return [c && c.name, Object.keys(JSON.parse(localStorage.getItem('jarvis.cards') || '{}')).includes(a.id)]; }""", sl)
    SLOW["s"] = 0
    check("f. an app removed while its card loads: the card is shown to the caller but not kept", gone == ["Slow", False], gone)

    put(f"{tmp}/old/jarvis.json", card("Old", t=now - 31 * 60))
    old = p.evaluate("(u) => A.addApp({name: 'Old', url: u}).app", oa + "/old/")
    s1 = p.evaluate("(a) => A.appStatus(a)", old)
    put(f"{tmp}/old/jarvis.json", card("Old", t=now - 29 * 60))
    s2 = p.evaluate("(a) => A.appStatus(a)", old)
    s3 = p.evaluate("(a) => A.cachedStatus(a, {now: Date.now() + 2.5 * 60e3})", old)
    check("f. stale: t 31 min old -> stale; 29 min -> not; the same card 2.5 min later -> stale",
          s1 and s1["stale"] is True and s1["cached"] is False and s2 and s2["stale"] is False and s3 and s3["stale"] is True and s3["cached"] is True, (s1, s2, s3))
    put(f"{tmp}/old/jarvis.json", card("Old", t=now - 40 * 60))
    s4 = p.evaluate("(a) => A.appStatus(a)", old)
    check("f. an older file than the card kept (a CDN copy) does not replace it", s4 and s4["t"] == now - 29 * 60, s4)

    LOG.clear()
    z = p.evaluate("() => Promise.all([A.appStatus('zenith'), A.appStatus({id: 'kalshi', url: '../kalshi/'}), A.appStatus(A.getApp('ascend')), A.appStatus('nope'), A.appStatus(null)])")
    check("f. built-ins (they have their own cards), the hidden Ascend, unknown apps: null, nothing fetched", z == [None] * 5 and not LOG, (z, LOG))
    put(f"{tmp}/clip/jarvis.json", card("Clip", t=now))
    LOG.clear()
    three = p.evaluate("(a) => Promise.all([A.appStatus(a), A.appStatus(a), A.appStatus(a)])", app)
    check("f. three asks at once: one request, the same card", len([x for x in LOG if "/clip/jarvis.json" in x]) == 1 and all(x and x["t"] == now for x in three), LOG)
    put(f"{tmp}/lift-log/jarvis.json", card("Lift Log Pro", t=now))
    nm = p.evaluate("async (u) => { const a = A.addApp({url: u}).app; const b = a.name; await A.appStatus(a); const g = A.getApp(a.id); return [b, g.name, g.autoName === undefined]; }", oa + "/lift-log/")
    check("f. a name made from the link gives way to the app's own name (once)", nm == ["Lift log", "Lift Log Pro", True], nm)

    # cards posted by an app open inside Jarvis (no server): same site, another site, a spoof, a bad card
    put(f"{tmp}/pushapp/index.html", PUSH % ("", json.dumps(card("Pushed", t=now - 5))))
    put(f"{tmp}/cors/pushx/index.html", PUSH % (", href: location.href", json.dumps(card("PushedX", t=now - 5))))
    put(f"{tmp}/cors/spoof/index.html", PUSH % (", href: " + json.dumps(oa + "/clip/"), json.dumps(card("Spoof", t=now))))
    put(f"{tmp}/cors/badpush/index.html", PUSH % (", href: location.href", json.dumps(card("<b>Bad</b>", t=now))))
    got = p.evaluate("""async ([u, x, s, b]) => {
        A.addApp({name: 'Push', url: u}); A.addApp({name: 'PushX', url: x}); A.addApp({name: 'BadPush', url: b});
        window.got = [];
        A.listen(window, (c) => window.got.push(c.app + ':' + c.name));
        for (const src of [u, x, s, b]) { const f = document.createElement('iframe'); f.src = src; document.body.appendChild(f); }
        await new Promise((r) => setTimeout(r, 1500));
        return [window.got.slice().sort(), A.cachedStatus('x-push'), A.cachedStatus('x-pushx'), A.cachedStatus('x-clip').name, A.statusError('x-badpush')];
    }""", [oa + "/pushapp/", ob + "/cors/pushx/", ob + "/cors/spoof/", ob + "/cors/badpush/"])
    check("f. no server: a card an app posts while open inside Jarvis is taken and kept (same site and another site)",
          got[0] == ["x-push:Pushed", "x-pushx:PushedX"] and got[1] and got[1]["name"] == "Pushed" and got[1]["cached"] is True and got[2] and got[2]["name"] == "PushedX", got)
    check("f. posted cards: another site cannot speak for an app on this site; a bad card is refused with its reason",
          got[3] == "Clip" and "HTML" in got[4], got[3:])
    same = p.evaluate("""async ([u, c]) => {
        const before = JSON.parse(localStorage.getItem('jarvis.cards'))['x-push'].at;
        await new Promise((r) => setTimeout(r, 30));
        const got = A.acceptMessage({data: {jarvis: 1, href: u, card: c}, origin: new URL(u).origin, source: null});
        return [got && got.name, JSON.parse(localStorage.getItem('jarvis.cards'))['x-push'].at === before];
    }""", [oa + "/pushapp/", card("Pushed", t=now - 5)])
    check("f. the same card posted again is not written again (an app that posts often)", same == ["Pushed", True], same)


# ---------------------------------------------------------------------------------------------------- g. Ascend
def part_g(p, harness, oa, ob, tmp):
    fresh(p, harness)
    s0 = p.evaluate("() => A.ascendSlot()")
    LOG.clear()
    nf = p.evaluate("() => A.findAscend()")
    check("g. Ascend: pre-registered and hidden; with no known link the one tap asks for the link at once (nothing guessed or fetched)",
          s0["enabled"] is False and s0["known"] == "" and "guesses" not in s0 and nf["ok"] is False and nf["field"] == "url" and "Paste" in nf["error"]
          and not LOG and not p.evaluate("() => A.ascendSlot().enabled || A.listApps().some((a) => a.id === 'ascend')"), (s0, nf, LOG))
    asc = ob + "/cors/ascend/"
    put(f"{tmp}/cors/ascend/index.html", "<!doctype html><title>Ascend</title><h1>Ascend</h1>")
    put(f"{tmp}/cors/ascend/jarvis.json", card("Ascend", t=int(time.time()) - 30))
    p.evaluate("() => A.addApp({name: 'Clipper', url: 'https://clip.example/'})")
    f1 = p.evaluate("(u) => A.findAscend({url: u})", asc)
    order = p.evaluate("() => A.listApps().map((a) => a.id)")
    life = p.evaluate("() => A.BUILT_INS.filter((b) => b.group === 'life').map((b) => b.id)")
    check("g. with its known link (ASCEND_URL, on its own site) the one tap adds it in LIFE right after its built-ins, no warning",
          f1["ok"] and f1["app"]["id"] == "ascend" and f1["app"]["url"] == asc and "warn" not in f1 and f1["app"]["group"] == "life"
          and order.index("ascend") == order.index(life[-1]) + 1 and order[-1] == "x-clipper", (f1, order))
    ac = p.evaluate("() => A.appStatus('ascend')")
    check("g. Ascend's live card from jarvis.json on its own site (sent with Access-Control-Allow-Origin: *)",
          ac and ac["name"] == "Ascend" and ac["app"] == "ascend" and ac["stale"] is False, ac)
    ss = p.evaluate("async (u) => [await A.findAscend({url: u}), A.ascendSlot().url]", oa + "/ascend/")
    check("g. a known link on Jarvis's own site is refused by the one tap (it could read Jarvis's keys); Ascend keeps its link",
          ss[0]["ok"] is False and ss[0]["field"] == "url" and ss[0]["warn"] == WARN and ss[1] == asc, ss)
    p.evaluate("() => A.removeApp('ascend')")
    pa = p.evaluate("(u) => A.addApp({name: 'ascend', url: u})", asc)
    p.evaluate("() => A.removeApp('ascend')")
    pb = p.evaluate("(u) => A.addApp({url: u}).app.id", asc)
    n_asc = p.evaluate("() => A.listApps().filter((a) => /ascend/i.test(a.name)).length")
    check("g. or one pasted link: named 'ascend', or the bare link (.../ascend/), fills the Ascend slot (never a second Ascend)",
          pa["ok"] and pa["app"]["id"] == "ascend" and "warn" not in pa and pb == "ascend" and n_asc == 1, (pa, pb, n_asc))
    sp = p.evaluate("(u) => { const r = A.addApp({name: 'Ascend', url: u}); return [r, A.ascendSlot().url, A.getApp('ascend').warn]; }", oa + "/ascend/")
    check("g. a pasted same-site Ascend link is still taken, with the warning (in the result and on the app)",
          sp[0]["ok"] and sp[0]["app"]["id"] == "ascend" and sp[0]["warn"] == WARN and sp[1] == oa + "/ascend/" and sp[2] == WARN, sp)
    plain = ob + "/plain/ascend/"
    put(f"{tmp}/plain/ascend/jarvis.json", card("Ascend", t=int(time.time())))
    r = p.evaluate("""async (u) => { const r = A.enableAscend(u); const c = await A.appStatus('ascend');
        return [r.ok, A.ascendSlot().url, c, A.statusError('ascend'), JSON.parse(localStorage.getItem('jarvis.extra')).filter((e) => e.name === 'Ascend').length]; }""", plain)
    check("g. a new Ascend link replaces the old (one entry); on another site without CORS its card cannot be read (null, the reason kept)",
          r[0] and r[1] == plain and r[2] is None and r[3] and r[4] == 1, r)


# ---------------------------------------------------------------------------------------------------- h. storage refused
def part_h(p, harness):
    fresh(p, harness)
    r = p.evaluate("""() => { Storage.prototype.setItem = function () { throw new Error('QuotaExceededError'); };
        const a = A.addApp({name: 'Offline', url: 'https://off.example/'});
        return [a.ok, A.listApps().some((x) => x.id === 'x-offline'), A.removeApp('x-offline'), A.listApps().some((x) => x.id === 'x-offline')]; }""")
    check("h. the phone refusing to save (private mode, full): add and remove still work for the session, nothing thrown", r == [True, True, True, False], r)


def part_i(p, harness, oa, tmp):
    """OLYMPUS: the built-ins from one table, by group; live cards from their folders; a folder not on the site."""
    fresh(p, harness)
    t = p.evaluate("""() => ({ rows: A.BUILT_INS.map((b) => ({ id: b.id, name: b.name, group: b.group, accent: b.accent, url: b.url, live: b.live })),
        groups: A.GROUPS.map((g) => g.id), order: A.listApps().map((a) => a.id + ':' + a.group) })""")
    rows = {r["id"]: r for r in t["rows"]}
    check("i. one table: Data City, Mind and Daphne built in (names, group, colour, ../<id>/, live card) next to Zenith, Kalshi and the Planner (live card since af40226)",
          all(rows.get(i, {}).get("name") == n and rows[i]["group"] == g and rows[i]["url"] == f"../{i}/" and rows[i]["live"] is True
              and re.fullmatch(r"#[0-9a-f]{6}", rows[i]["accent"] or "") for i, n, g in (("datacity", "Data City", "trading"), ("mind", "Mind", "life"), ("tree", "Daphne", "trading")))
          and rows["zenith"]["live"] is False and rows["planner"]["live"] is True and rows["kalshi"]["live"] is False
          and t["groups"] == ["trading", "life", "money", "more"] and all(r["group"] in t["groups"] for r in t["rows"]), t["rows"])
    ranks = [t["groups"].index(x.split(":")[1]) for x in t["order"]]
    check("i. listApps by group (TRADING, LIFE, MONEY), each group in the table's order", ranks == sorted(ranks)
          and [x.split(":")[0] for x in t["order"]] == [r["id"] for g in t["groups"] for r in t["rows"] if r["group"] == g], t["order"])
    sec = p.evaluate("""() => { A.addApp({name: 'Clipper', url: 'https://clip.example/'});
        return A.byGroup([{id: 'home'}].concat(A.listApps()).concat([{id: 'odd', group: 'nope'}])).map((s) => [s.group ? s.group.id : null, s.apps.map((a) => a.id)]); }""")
    check("i. byGroup: Jarvis first on its own, then the groups in order, an unknown group in MORE with the added apps, no empty group",
          sec[0] == [None, ["home"]] and [s[0] for s in sec[1:]] == ["trading", "life", "money", "more"] and sec[-1][1] == ["x-clipper", "odd"], sec)
    su = p.evaluate("() => A.BUILT_INS.map((b) => [b.id, A.statusUrlOf(b.id), A.statusUrlOf({id: b.id, url: b.url})])")
    check("i. a live built-in's card is <its folder>/jarvis.json (the page's own site); Zenith, the Planner, Kalshi: none (their own cards)",
          all((u1.endswith(f"/nq-dashboard/{i}/jarvis.json") and u1 == u2) if rows[i]["live"] else (u1 == "" and u2 == "") for i, u1, u2 in su), su)
    os.makedirs(os.path.join(tmp, "nq-dashboard", "datacity"), exist_ok=True)
    put(os.path.join(tmp, "nq-dashboard", "datacity", "jarvis.json"), card("Data City", t=int(time.time()) - 60, theme="#05060f"))
    shutil.rmtree(os.path.join(tmp, "nq-dashboard", "tree"), ignore_errors=True)
    r = p.evaluate("""async () => { const dc = await A.appStatus('datacity'), tr = await A.appStatus('tree');
        return { dc: dc && [dc.name, dc.app, dc.theme], tr, missDc: A.missing('datacity'), missTr: A.missing('tree'), err: A.statusError('tree'), zen: A.missing('zenith'), nope: A.missing('nope') }; }""")
    check("i. Data City's live card from its folder (its theme = its top colour); Daphne's folder not on the site: no card, missing() true, "
          "never a throw; Zenith / an unknown id: not missing",
          r["dc"] == ["Data City", "datacity", "#05060f"] and r["tr"] is None and r["missTr"] is True and r["missDc"] is False and r["err"] == "http 404"
          and r["zen"] is False and r["nope"] is False, r)
    put(os.path.join(tmp, "nq-dashboard", "tree", "jarvis.json"), card("DAPHNE", t=int(time.time()) - 60))
    r2 = p.evaluate("async () => { const c = await A.appStatus('tree'); return [!!c, A.missing('tree')]; }")
    check("i. once its folder is published the app is no longer missing (its card arrives)", r2 == [True, False], r2)
    ss = p.evaluate("""(oa) => [A.sameSiteRisk(oa + '/nq-dashboard/datacity/'), A.sameSiteRisk(oa + '/nq-dashboard/mind/x.html'),
        A.sameSiteRisk(oa + '/nq-dashboard/tree'), A.sameSiteRisk(oa + '/nq-dashboard/other/')]""", oa)
    check("i. the built-ins' folders are ours (no same-site warning); another folder on the site still warns", ss == [False, False, False, True], ss)
    ids = p.evaluate("""() => [A.addApp({name: 'Data City', url: 'https://dc.example/'}).app.id, A.addApp({name: 'Mind', url: 'https://mind.example/'}).app.id,
        A.addApp({name: 'x', url: '../datacity/'}), A.listApps().filter((a) => a.url.endsWith('/datacity/') || a.url === '../datacity/').length]""")
    check("i. a built-in's name added again gets its own x- id; its own folder added by hand returns the built-in (existed)",
          ids[0] == "x-data-city" and ids[1] == "x-mind" and ids[2]["ok"] and ids[2].get("existed") and ids[2]["app"]["id"] == "datacity" and ids[3] == 1, ids)
    # an older Jarvis's jarvis.extra holding a built-in's own folder (added by hand before it was built in): shown once
    p.evaluate("(u) => { localStorage.clear(); localStorage.setItem('jarvis.extra', JSON.stringify([{id: 'x-mind', name: 'Mind', url: u}])); }", oa + "/nq-dashboard/mind/")
    p.reload()
    p.wait_for_function("window.ready === true")
    once = p.evaluate("() => A.listApps().filter((a) => /\\/mind\\/$/.test(new URL(a.url, location.href).href)).map((a) => a.id)")
    check("i. a hand-added copy of a built-in (the same folder) is shown once, as the built-in", once == ["mind"], once)


def run_browser(oa, ob, tmp, example):
    from playwright.sync_api import sync_playwright
    harness = oa + "/nq-dashboard/jarvis/apps_harness.html"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = BK.launch(pw)
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())      # nothing leaves this machine
        p = ctx.new_page()
        p.on("pageerror", lambda e: ERRS.append(str(e)))
        part_b(p, harness, oa, ob)
        part_c(p, harness, oa)
        part_d(p, harness, oa, example)
        part_e(p, harness)
        part_f(p, harness, oa, ob, tmp)
        part_g(p, harness, oa, ob, tmp)
        part_h(p, harness)
        part_i(p, harness, oa, tmp)
        ctx.close()
        part_e_shell(br, oa + "/nq-dashboard/jarvis/", oa, os.environ.get("JARVIS_APPS_SHOTS"))
        check("h. no page errors", not ERRS, ERRS)
        br.close()


def main():
    example = part_a()
    tmp = site(tempfile.mkdtemp(prefix="le_jarvis_apps_"))
    a, b = serve(tmp), serve(tmp)
    try:
        run_browser(f"http://127.0.0.1:{a.server_address[1]}", f"http://127.0.0.1:{b.server_address[1]}", tmp, example)
    finally:
        a.shutdown()
        b.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis apps: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
