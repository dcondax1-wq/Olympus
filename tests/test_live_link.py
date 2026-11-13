"""LIVE LINK: the real, always-current dashboard on the owner's iPhone through Tailscale (docs/LIVE_DASHBOARD.md, owner 2026-11-12:
"I want everything connected. I want an actual dashboard"). engine/live_site.py (server.py serves the whole site at /site/ with the
bot's live numbers, read-only over the link), LIVE_LINK.bat + scripts/live_link.ps1 (+ UNDO_LIVE_LINK.bat), the Gate's live card.

Never the real network, never the real Tailscale: a fake `tailscale` (a shell script with a state file) answers the PowerShell
script; Windows-only steps (open a page, Task Scheduler, clipboard, a background build) go to the test log LE_LL_T_LOG. Temp folders.

  1. guard     a proxied request (tailscale serve headers) may only GET / HEAD / OPTIONS; Funnel refused; the webhook-key page hidden;
               the PC's own requests unchanged
  2. site      /site/... from the newest built site, fallback tools/web_public; no "..", no hidden files, no symlink out; folders
               redirect to a slash; content types; / over the link -> the Gate
  3. live      /api/site/live.json (cached, 503 without the bot), /site/home.json = built home.json + the live numbers, the Python
               overlay equals tools/web_public/pc_feed.js overlayHome in node (same input, same output)
  4. feeds     /site/kalshi.json from the setting's file / https address (cached) / the site; /site/money/*.json from money_out/
  5. server    server.py installs it before its static mount (try / except); the real app in a child process: POST refused over the
               link, the PC dashboard at / unchanged on the PC, the Gate over the link, live.json is the bot's
  6. static    the .bat files (CRLF, ASCII, the right script, pause), ASCII .ps1, never Funnel / an order / the live phrase, the doc's
               steps (at most 3, one copy-paste line)
  7. pwsh      (skipped without pwsh) 5.1 lint; not installed -> download page; not signed in -> sign-in; HTTPS off -> the admin page;
               the serve command; Funnel switched off when found; the URL card; twice = no second serve; -DryRun; -Remove
  8. gate      (skipped without node) the Gate's live card reads /api/site/live.json only when served from the PC

  python -X utf8 -m tests.test_live_link          (--fast: skips 5's child process and 7)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import live_site as LS  # noqa: E402

RES: list = []
FAST = "--fast" in sys.argv
TMP_BASE = os.environ.get("LE_TEST_TMP") or None
LINK = {"X-Forwarded-For": "100.101.102.103", "X-Forwarded-Host": "olympus-pc.tail1234.ts.net", "X-Forwarded-Proto": "https",
        "Tailscale-User-Login": "owner@example.com"}
LINK_LC = {k.lower(): v for k, v in LINK.items()}       # what Starlette's case-insensitive headers give the guard


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""), flush=True)
    return bool(cond)


def rb(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return fh.read()


def live_fixture(t, running=True, trade_t=None):
    return {"v": 1, "kind": "le-live", "t": t, "every_s": 60, "host": "OLYMPUS-PC",
            "pc_verdict": {"code": "TRADING", "label": "TRADING", "level": "ok", "reason": "LIT watching", "t": t},
            "pc": {"running": running, "adapter": "ninjatrader", "position": False, "present": True, "t": t, "age_s": 0},
            "board": {"t": t, "data_t": t, "where": "live", "running": running,
                      "lit": {"id": "lit", "name": "Zlarior", "room": 1890.0, "mll": 2000.0, "today_pnl": 140.0},
                      "trades": [{"acct": "lit", "entry_t": trade_t or t - 3600, "side": "long", "usd": 140.0}]},
            "accounts": [{"id": "lit", "name": "Zlarior"}]}


def home_fixture(t):
    return {"built": "2026-11-12T14:00:00Z", "live": {"pc": {"running": True, "t": t - 7200, "host": "OLYMPUS-PC"}, "x": 1},
            "board": {"t": t - 7200, "data_t": t - 7200, "lit": {"room": 1750.0, "mll": 2000.0, "balance": 50250.0},
                      "atlas": {"room": 900.0, "mll": 1000.0}, "map": {"keep": True},
                      "trades": [{"acct": "lit", "entry_t": t - 90000, "usd": -110.0}, {"acct": "lit", "entry_t": t - 3600, "usd": 120.0}]},
            "apps": {"keep": "me"}}


# ============================================================================================== 1 guard
def guard():
    g = LS.guard
    check("1. the PC's own requests are untouched (POST /api/live/start, GET /api/tv/status)",
          g("POST", "/api/live/start", {}) is None and g("GET", "/api/tv/status", {"host": "localhost:8766"}) is None)
    for m in ("POST", "PUT", "PATCH", "DELETE"):
        r = g(m, "/api/live/start", LINK_LC)
        check(f"1. over the link {m} is refused with 403 before any route", r is not None and r[0] == 403 and "read only" in r[1]["error"], r)
    check("1. over the link GET / HEAD / OPTIONS go through", all(g(m, "/api/live/state", LINK_LC) is None for m in ("GET", "HEAD", "OPTIONS")))
    check("1. one proxy header is enough (X-Forwarded-For alone, Tailscale-User-Login alone)",
          g("POST", "/api/live/kill", {"x-forwarded-for": "100.1.2.3"}) is not None and g("POST", "/x", {"tailscale-user-login": "a@b"}) is not None)
    r = g("GET", "/site/gate/", {**LINK_LC, "tailscale-funnel-request": "?1"})
    check("1. a Tailscale Funnel (internet) request is refused, even a GET", r is not None and r[0] == 403 and "private" in r[1]["error"], r)
    r = g("GET", "/api/tv/status", LINK_LC)
    check("1. the TradingView webhook-key page is hidden over the link", r is not None and r[0] == 403, r)
    src = rb("engine/live_site.py").decode()
    body = src.split('"""', 2)[-1]
    check("1. live_site.py: no POST route, no file write, no order / arm / live phrase, no live_model",
          "router.post" not in body and "app.post" not in body and not re.search(r"open\([^)]*['\"][wa]b?['\"]", body)
          and not re.search(r"I ACCEPT|LIVE_PHRASE|live_model|place_order|/api/live/arm", body))


# ============================================================================================== 2 site
class Site:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="ll_", dir=TMP_BASE)
        self.site = os.path.join(self.dir, "site")
        for rel, text in (("index.html", "<!doctype html><title>dash</title>"), ("gate/index.html", "<!doctype html><title>gate</title>"),
                          ("gate/gate.js", "var a=1;"), ("gate/manifest.webmanifest", "{}"), ("olympus/truth.js", "export const x=1;"),
                          ("nq/index.html", "<!doctype html>nq"), ("data.json", "{}"), (".secret/x.json", "{}"), ("kalshi.json", '{"src":"site"}'),
                          ("money/index.json", '{"kind":"sample"}')):
            p = os.path.join(self.site, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
        self.now = int(time.time())
        with open(os.path.join(self.site, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(home_fixture(self.now), fh)
        outside = os.path.join(self.dir, "outside.txt")
        with open(outside, "w") as fh:
            fh.write("never")
        try:
            os.symlink(outside, os.path.join(self.site, "link.txt"))
            self.symlink = True
        except (OSError, NotImplementedError):
            self.symlink = False
        self.money = os.path.join(self.dir, "money_out")
        os.makedirs(self.money)

    def client(self, live=None, kalshi_cfg=None):
        app = FastAPI()

        @app.get("/")
        def pc_dash():
            return {"pc": "dashboard"}

        @app.post("/api/live/start")
        def start():
            return {"started": True}

        LS.install(app, live=live, kalshi_cfg=kalshi_cfg if kalshi_cfg is not None else {})
        return TestClient(app, follow_redirects=False)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def site():
    s = Site()
    old = os.environ.get("LE_SITE_DIR")
    os.environ["LE_SITE_DIR"] = s.site
    try:
        c = s.client()
        r = c.get("/", headers=LINK)
        check("2. / over the link goes to the Gate (/site/gate/)", r.status_code == 307 and r.headers["location"] == "/site/gate/", (r.status_code, r.headers))
        r = c.get("/")
        check("2. / on the PC itself stays the PC dashboard", r.status_code == 200 and r.json() == {"pc": "dashboard"}, r.text)
        r = c.post("/api/live/start", headers=LINK)
        check("2. a real POST route over the link: 403, the route never ran", r.status_code == 403 and "started" not in r.text, r.text)
        check("2. the same POST from the PC itself still works (nothing changed on the PC)", c.post("/api/live/start").json() == {"started": True})
        r = c.get("/site/gate/", headers=LINK)
        check("2. /site/gate/ -> the built Gate, text/html", r.status_code == 200 and "gate" in r.text and r.headers["content-type"].startswith("text/html"), r.text)
        r = c.get("/site/gate")
        check("2. a folder without its slash redirects to it (relative links work)", r.status_code == 307 and r.headers["location"] == "/site/gate/", r.headers)
        r = c.get("/site/nq?x=1")
        check("2. ... and keeps the query", r.status_code == 307 and r.headers["location"] == "/site/nq/?x=1", r.headers)
        check("2. /site -> /site/gate/", c.get("/site").headers.get("location") == "/site/gate/")
        r = c.get("/site/gate/gate.js")
        check("2. JavaScript as text/javascript (ES modules on Windows need it)", r.headers["content-type"].startswith("text/javascript"), r.headers)
        check("2. the manifest as application/manifest+json", c.get("/site/gate/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json"))
        r = c.get("/site/olympus/gate-catalog.js")
        check("2. a file the build does not have comes from tools/web_public", r.status_code == 200 and "OLYMPUS_GATE" in r.text, r.status_code)
        r = c.head("/site/nq/index.html")
        check("2. HEAD works (the Gate asks HEAD for every app)", r.status_code == 200, r.status_code)
        check("2. a missing app is a 404 (the Gate marks it)", c.head("/site/nope/index.html").status_code == 404)
        bad = [c.get(u).status_code for u in ("/site/../server.py", "/site/%2e%2e/server.py", "/site/.secret/x.json", "/site/gate/..%2f..%2fserver.py",
                                              "/site/C:/Windows/win.ini")]
        check("2. no way out: .., encoded .., hidden folders, a drive letter are refused", all(x in (400, 404) for x in bad), bad)
        if s.symlink:
            check("2. a symlink that points outside the site is not served", c.get("/site/link.txt").status_code == 404)
        hidden = LS.resolve("a/../b", [s.site])[0]
        check("2. resolve(): '..' is bad", hidden == "bad", hidden)
        st = c.get("/api/site/status").json()
        check("2. /api/site/status: the built site, its time, the fallback, no live", st["site"]["built"] and st["site"]["built_t"] and st["live"] is False
              and st["site"]["fallback"] == "tools/web_public" and st["home"] == "/site/gate/", st)
        os.environ["LE_SITE_DIR"] = os.path.join(s.dir, "nothing")
        c2 = s.client()
        r = c2.get("/site/gate/")
        check("2. no built site yet: the Gate still opens from tools/web_public", r.status_code == 200 and "Olympus" in r.text, r.status_code)
        r = c2.get("/site/home.json")
        check("2. ... and home.json is a plain 404 that says why (no bot numbers either)", r.status_code == 404 and "15 minutes" in r.text, r.text)
        os.environ["LE_SITE_DIR"] = s.site
        # the newest of the two default build folders wins
        a, b = os.path.join(s.dir, "a"), os.path.join(s.dir, "b")
        for d, t in ((a, 1000), (b, 2000)):
            os.makedirs(d)
            open(os.path.join(d, "index.html"), "w").close()
            os.utime(os.path.join(d, "index.html"), (t, t))
        old_c = LS.SITE_CANDIDATES
        LS.SITE_CANDIDATES = (a, b)
        saved = os.environ.pop("LE_SITE_DIR")
        try:
            d = LS.site_dirs()
            check("2. two built sites (PUBLISH_NQ's and LIVE_LINK's): the newer one is served, web_public last", d == [b, LS.WEB_PUBLIC], d)
        finally:
            LS.SITE_CANDIDATES = old_c
            os.environ["LE_SITE_DIR"] = saved
    finally:
        if old is None:
            os.environ.pop("LE_SITE_DIR", None)
        else:
            os.environ["LE_SITE_DIR"] = old
        s.cleanup()


# ============================================================================================== 3 live
def norm(x):
    """JSON numbers as JS sees them (1890.0 == 1890), keys sorted: for comparing node's output with Python's."""
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [norm(v) for v in x]
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def node_overlay(cases):
    exe = shutil.which("node")
    if not exe:
        return None
    js = ("const F=require(process.argv[1]);const C=JSON.parse(require('fs').readFileSync(0,'utf8'));"
          "process.stdout.write(JSON.stringify(C.map(c=>F.overlayHome(c.home,c.lite,c.now))));")
    r = subprocess.run([exe, "-e", js, os.path.join(ROOT, "tools", "web_public", "pc_feed.js")], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else {"_error": r.stderr[-400:]}


def live():
    s = Site()
    old = os.environ.get("LE_SITE_DIR")
    os.environ["LE_SITE_DIR"] = s.site
    calls = []

    def fn():
        calls.append(1)
        return live_fixture(s.now - 30, trade_t=s.now - 3600)
    try:
        c = s.client(live=fn)
        r = c.get("/api/site/live.json", headers=LINK)
        j = r.json()
        check("3. /api/site/live.json over the link: the bot's live.json (kind le-live), no-store", r.status_code == 200 and j["kind"] == "le-live"
              and j["board"]["lit"]["room"] == 1890.0 and "no-store" in r.headers.get("cache-control", ""), r.text[:300])
        c.get("/api/site/live.json")
        check("3. built at most once every 15 s (two requests, one build)", len(calls) == 1, calls)
        r = c.get("/site/home.json", headers=LINK)
        h = r.json()
        check("3. /site/home.json = the built home.json + the live numbers (pc.t, room, today), the rest kept",
              r.status_code == 200 and h["live"]["pc"]["t"] == s.now - 30 and h["live"]["pc"]["live"] is True and h["board"]["lit"]["room"] == 1890.0
              and h["board"]["lit"]["balance"] == 50250.0 and h["board"]["atlas"]["room"] == 900.0 and h["board"]["map"] == {"keep": True}
              and h["apps"] == {"keep": "me"} and h["live"]["x"] == 1 and h["live"]["pc_verdict"]["code"] == "TRADING"
              and r.headers.get("x-olympus-source") == "built+live", h)
        check("3. trades merged once each, newest first", [t.get("usd") for t in h["board"]["trades"]] == [140.0, -110.0], h["board"]["trades"])
        st = c.get("/api/site/status").json()
        check("3. /api/site/status says live", st["live"] is True, st)
        # the bot is not there (no LIVEPUB, or it raises)
        c3 = s.client(live=lambda: (_ for _ in ()).throw(RuntimeError("bot gone")))
        r = c3.get("/api/site/live.json")
        check("3. live numbers missing: 503 with the reason, never a crash", r.status_code == 503 and "bot gone" in r.text, r.text)
        r = c3.get("/site/home.json")
        check("3. ... and home.json is the built one, unchanged", r.status_code == 200 and r.json() == home_fixture(s.now), r.text[:200])
        c4 = s.client(live=lambda: {"kind": "something else"})
        check("3. a payload that is not le-live is not served", c4.get("/api/site/live.json").status_code == 503)
        # parity with pc_feed.js overlayHome
        now = s.now
        cases = [{"home": home_fixture(now), "lite": live_fixture(now - 30, trade_t=now - 3600), "now": now},
                 {"home": home_fixture(now), "lite": live_fixture(now - 9000), "now": now},              # older than home's pc: home unchanged
                 {"home": home_fixture(now), "lite": {**live_fixture(now - 5000), "board": {"t": now - 99999, "lit": {"room": 1.0}}}, "now": now},
                 {"home": home_fixture(now), "lite": {**live_fixture(now - 3000), "reporter": {"t": now, "server": True}}, "now": now + 3000},
                 {"home": {"built": "x"}, "lite": live_fixture(now - 10), "now": now},
                 {"home": home_fixture(now), "lite": {**live_fixture(now - 20), "board": {"error": "boom"}}, "now": now},
                 {"home": {"board": {"error": "x"}}, "lite": {**live_fixture(now), "board": None}, "now": now + 0.5},
                 {"home": home_fixture(now), "lite": {"kind": "le-live", "t": "nope"}, "now": now},
                 {"home": home_fixture(now), "lite": {**live_fixture(now - 1), "board": {**live_fixture(now)["board"],
                                                       "trades": [{"acct": "lit", "day": "2026-11-12", "usd": 5.0}, {"acct": None, "entry_t": 7}]}}, "now": now}]
        js = node_overlay(cases)
        if js is None:
            print("[SKIP] node not found: the pc_feed.js parity check was skipped")
        else:
            py = [LS.overlay_home(json.loads(json.dumps(c["home"])), json.loads(json.dumps(c["lite"])), c["now"]) for c in cases]
            js_n, py_n = (norm(js) if isinstance(js, list) else js), norm(py)
            same = isinstance(js, list) and js_n == py_n
            diff = None if same or not isinstance(js, list) else next((i for i, (a, b) in enumerate(zip(js_n, py_n)) if a != b), None)
            check(f"3. overlay_home (Python) == pc_feed.js overlayHome (node) on {len(cases)} cases", same,
                  js if not isinstance(js, list) else (diff, js_n[diff] if diff is not None else None, py_n[diff] if diff is not None else None))
    finally:
        if old is None:
            os.environ.pop("LE_SITE_DIR", None)
        else:
            os.environ["LE_SITE_DIR"] = old
        s.cleanup()


# ============================================================================================== 4 feeds
class FakeResp:
    def __init__(self, raw):
        self.raw = raw

    def read(self, n=-1):
        return self.raw if n < 0 else self.raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def feeds():
    s = Site()
    old = os.environ.get("LE_SITE_DIR")
    os.environ["LE_SITE_DIR"] = s.site
    try:
        kf = os.path.join(s.dir, "kalshi_vm.json")
        with open(kf, "w") as fh:
            json.dump({"src": "file", "bot": "on"}, fh)
        c = s.client(kalshi_cfg={"kalshi_file": kf})
        r = c.get("/site/kalshi.json", headers=LINK)
        check("4. kalshi.json from the setting's file (the VM's feed copied / synced to the PC), fresh on every request",
              r.status_code == 200 and r.json()["src"] == "file" and r.headers.get("x-olympus-source") == "file", r.text)
        with open(kf, "w") as fh:
            fh.write("{broken")
        r = c.get("/site/kalshi.json")
        check("4. a broken file falls back to the site's copy", r.json() == {"src": "site"} and r.headers.get("x-olympus-source") == "site", r.text)
        opened = []

        def opener(req):
            opened.append(req.full_url)
            return FakeResp(b'{"src": "url"}')
        LS._KAL.update(at=0.0, raw=None, src=None, url=None)
        clock = [1000.0]
        raw, src = LS.kalshi(s.site, cfg={"kalshi_feed_url": "https://kalshi-feed.example.org/kalshi.json"}, opener=opener, clock=lambda: clock[0])
        raw2, _ = LS.kalshi(s.site, cfg={"kalshi_feed_url": "https://kalshi-feed.example.org/kalshi.json"}, opener=opener, clock=lambda: clock[0] + 30)
        check("4. kalshi.json from the owner's https address, cached 60 s (two looks, one fetch)",
              json.loads(raw) == {"src": "url"} and src == "url" and raw2 == raw and len(opened) == 1, (raw, src, opened))

        def broken(req):
            raise OSError("offline")
        raw3, src3 = LS.kalshi(s.site, cfg={"kalshi_feed_url": "https://kalshi-feed.example.org/kalshi.json"}, opener=broken, clock=lambda: clock[0] + 999)
        check("4. the address is down: the last good copy, said so", raw3 == raw and src3 == "url (last good)", (raw3, src3))
        raw4, src4 = LS.kalshi(s.site, cfg={"kalshi_feed_url": "http://evil.example.org/k.json"}, opener=opener)
        check("4. a plain-http address is never fetched (site copy instead)", src4 == "site" and len(opened) == 1, (src4, opened))
        empty = os.path.join(s.dir, "empty")
        os.makedirs(empty)
        r5 = LS.kalshi(empty, cfg={})
        check("4. no feed anywhere: (None, None) -> the route says 404 in plain words", r5 == (None, None), r5)
        # money: money_out wins over the build's sample
        old_m = LS.MONEY_OUT
        LS.MONEY_OUT = s.money
        try:
            r = c.get("/site/money/index.json")
            check("4. no money_out yet: the site's (sample) money/index.json", r.json() == {"kind": "sample"}, r.text)
            with open(os.path.join(s.money, "index.json"), "w") as fh:
                json.dump({"kind": "real"}, fh)
            with open(os.path.join(s.money, "mercury_state.json"), "w") as fh:
                fh.write("{}")
            r = c.get("/site/money/index.json")
            check("4. RUN_MONEY.bat's money_out/index.json is served live", r.json() == {"kind": "real"} and r.headers.get("x-olympus-source") == "money_out", r.text)
            check("4. a scanner's state file is never served from money_out", c.get("/site/money/mercury_state.json").status_code == 404)
            check("4. /api/site/status: money from money_out, Kalshi from the site", c.get("/api/site/status").json()["money"] == "money_out")
        finally:
            LS.MONEY_OUT = old_m
    finally:
        if old is None:
            os.environ.pop("LE_SITE_DIR", None)
        else:
            os.environ["LE_SITE_DIR"] = old
        s.cleanup()


# ============================================================================================== 5 server
CHILD = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["LE_PREWARM"] = "0"
import server
from fastapi.testclient import TestClient
c = TestClient(server.app, follow_redirects=False)
L = json.loads(sys.argv[1])
out = {}
out["link_root"] = [c.get("/", headers=L).status_code, c.get("/", headers=L).headers.get("location")]
out["pc_root"] = [c.get("/").status_code, c.get("/").headers.get("content-type")]
out["link_posts"] = [c.post(p, json={"adapter": "paper"}, headers=L).status_code for p in ("/api/live/start", "/api/live/stop", "/api/live/kill",
    "/api/live/arm", "/api/live/golive", "/api/next/start/go", "/api/alerts", "/api/data/refresh")]
out["gate"] = [c.get("/site/gate/", headers=L).status_code, "Right now" in c.get("/site/gate/", headers=L).text]
lj = c.get("/api/site/live.json", headers=L)
out["live"] = [lj.status_code, (lj.json() if lj.status_code == 200 else {}).get("kind")]
out["state"] = c.get("/api/live/state", headers=L).status_code
out["home"] = c.get("/site/home.json", headers=L).status_code
print("RESULT " + json.dumps(out))
"""


def server_wiring():
    src = rb("server.py").decode()
    i, j = src.find("_ls.install(app, live=LIVEPUB.payload)"), src.find('app.mount("/", _static')
    check("5. server.py installs live_site with the bot's live.json before the static mount, inside try / except",
          0 < i < j and src.rfind("try:", 0, i) > src.rfind("\n\n", 0, i) - 400 and "except Exception as _ls_err" in src[i:j], (i, j))
    if FAST:
        print("[SKIP] --fast: the real server.py child process was skipped")
        return
    env = {**os.environ, "LE_PREWARM": "0", "LE_SITE_DIR": os.path.join(tempfile.gettempdir(), "ll-no-site-here")}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, json.dumps(LINK)], cwd=ROOT, capture_output=True, text=True, timeout=600, env=env)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
    if not check("5. the real server.py loads with live_site (child process)", line is not None, (r.stdout[-400:], r.stderr[-800:])):
        return
    o = json.loads(line[7:])
    check("5. real server: / over the link -> the Gate; / on the PC -> the PC dashboard (html)", o["link_root"] == [307, "/site/gate/"]
          and o["pc_root"][0] == 200 and o["pc_root"][1].startswith("text/html"), o)
    check("5. real server: start / stop / kill / arm / go-live / Start-page go / settings / refresh over the link: all 403",
          o["link_posts"] == [403] * 8, o["link_posts"])
    check("5. real server: the Gate, the bot's live.json, /api/live/state and home.json over the link",
          o["gate"] == [200, True] and o["live"] == [200, "le-live"] and o["state"] == 200 and o["home"] == 200, o)


def main():
    guard()
    site()
    live()
    feeds()
    server_wiring()
    try:
        from tests import test_live_link_ps as PS   # the PowerShell / Gate parts (6-8)
        PS.run(check, fast=FAST)
    except ImportError:
        pass
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
