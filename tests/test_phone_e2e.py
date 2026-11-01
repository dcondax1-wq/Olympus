"""The owner's phone, end to end (QA 2026-11-01, owner: "make sure there is nothing wrong").

The phone runs a few Home Screen web apps from one GitHub Pages site (https://demetrades2000-coder.github.io/nq-dashboard/):
Jarvis at /jarvis/ (the hub that switches between the apps), Zenith at / (the NQ bots' app), the Planner at /planner/ and
Kalshi at /kalshi/. Each has its own service worker, and an iPhone Home Screen app is a WHITE screen while its page loads
or after a failed load (docs/CLAUDE_REFERENCE.md, Infrastructure > Jarvis hub). This test builds a faithful local copy of
the published site and drives it in Chromium at iPhone sizes over local https (service workers need https):
  - the site: a shallow, blobless, sparse clone of the Pages repo (branch main; big folders such as runs/ are fetched one
    file at a time only if a page asks for them), the planner/ folder from the branch planner-backup, and this checkout's
    tools/web_public/ laid over it as tools/build_web_dashboard.py publishes it (page, scripts, sw.js, jarvis/, kalshi/ ...);
  - live.json and kalshi.json (api.github.com / raw.githubusercontent.com) come from stubs on the same local server
    (Chromium maps those hosts to it), Google Fonts gets an empty stylesheet, every other outside host is cut off;
  - the server answers like GitHub Pages (Cache-Control max-age=600, ETag, its own 404 page) and can turn slow, drop
    every connection (offline) or answer 404 for the whole site.
It checks:
  a. the files: the overlay is what the site build publishes; each worker keeps to its own folder and caches
  b. Jarvis opens at iPhone SE / 13 / 13 Pro Max: the Jarvis screen, the bots' numbers, no sideways scroll, not white,
     interactive under 2 s locally (cold and from the saved copy)
  c. switching: Jarvis -> Zenith -> Jarvis -> Zenith (not reloaded) -> Planner -> Kalshi -> Jarvis, each one rendered and
     not white, never more than one dashboard frame alive, no sideways scroll inside the dashboards
  d. Jarvis's answers: status, room, target, P&L, BLITZ, Kalshi, the day, the market, help, "open planner"
  e. a slow network: a reopen shows the saved copy after ~3.5 s (not a white screen until the site answers)
  f. offline (every connection dropped): Jarvis, Zenith, the Planner and Kalshi inside Jarvis; no saved copy = dark Retry
  g. a 404 site (GitHub's "Site not found" for every file): the same four
  h. a service-worker update from the published workers to this checkout's (a synthetic cache-name bump when they are
     the same): the new workers take over on a reopen, the page is the new one, no worker deletes another app's caches,
     offline still works after the update
  i. no page errors, no console errors, no failed same-site requests in the normal runs
Screenshots of every state are judged by their dominant color (white = fail) and kept with --keep.

    python -X utf8 -m tests.test_phone_e2e                 the local copy with this checkout's tools/web_public (~2-3 min)
    python -X utf8 -m tests.test_phone_e2e --src <path>    overlay another checkout's tools/web_public (an integration
                                                           branch, or a `git archive <branch> tools/web_public` export)
    python -X utf8 -m tests.test_phone_e2e --live          read-only smoke test of the real published site
    --only b,c,d   run some parts · --keep  keep the temp site + screenshots · --cache <dir>  where the clone is kept
    --no-refresh   reuse the cached clone without fetching · --strict  known open bugs count as failures
Read-only: nothing is published, pushed or written outside the temp / cache folders. Paper only; no trading code is run.
"""
from __future__ import annotations

import argparse
import base64
import glob
import http.server
import io
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER, REPO = "demetrades2000-coder", "nq-dashboard"
PAGES_GIT = f"https://github.com/{OWNER}/{REPO}.git"
LIVE_SITE = f"https://{OWNER}.github.io/{REPO}/"
BASE = f"/{REPO}/"
STUB_HOSTS = ("api.github.com", "raw.githubusercontent.com", "fonts.googleapis.com", "fonts.gstatic.com", "ntfy.sh")
# the published site: every top-level file, the app folders and the pictures; runs/, writeups/, replays/ ... on demand
NQD_SPARSE = ["/*", "!/*/", "/icons/", "/jarvis/", "/kalshi/", "/charts/", "/recaps/"]
PLANNER_SPARSE = ["/planner/*", "!/planner/*/"]
# standalone Home Screen apps: the page gets the whole screen
PHONES = {
    "iPhone SE": {"viewport": {"width": 375, "height": 667}, "device_scale_factor": 2},
    "iPhone 13": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3},
    "iPhone 13 Pro Max": {"viewport": {"width": 428, "height": 926}, "device_scale_factor": 3},
}
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/18.6 Mobile/15E148 Safari/604.1")
PERF_BUDGET_MS = 2000
NAV_WAIT_S = 3.5                    # jarvis/sw.js NAV_WAIT_MS
SLOW_S = 7.0                        # the slow network: the site answers after this long
# Known open bugs on the published code (found by this test 2026-11-01, reported, not fixed here): printed as [KNOWN] and not
# counted unless --strict; a known check that passes prints [PASS] (fixed). (check-name pattern, the bug in short)
KNOWN = [
    (r"^f\. 404 site: Zenith (inside Jarvis|on its own) opens|^not white: Zenith (inside Jarvis|alone) 404 site",
     "Zenith's worker answers its page with the site's 404 instead of its saved copy (tools/web_public/sw.js, page branch)"),
    (r"^e\. slow network: Zenith (inside Jarvis shows|on its own opens)",
     "Zenith waits on the network for its page / data.json / home.json (published sw.js: no saved-copy fallback like "
     "Jarvis's 3.5 s; inside Jarvis the page and then its data each wait)"),
    (r"^f\. (offline|404 site): Kalshi inside Jarvis opens|^not white: Kalshi inside Jarvis 404 site",
     "kalshi/ has no service worker and no saved copy: offline = browser error page, 404 site = GitHub's 404 page"),
    (r"^c\. Zenith again: where the owner left it",
     "a dashboard hidden with display:none ([hidden] on its view) comes back scrolled to the top"),
]

RES = []          # (name, ok, known)
MISSING = []      # Jarvis modules not on the site (part a): their 404s are not counted again in every error check
SHOTS = {"dir": None, "n": 0}


def check(name, ok, info="", known=None):
    known = known or next((k for pat, k in KNOWN if re.search(pat, name)), None)
    tag = "[PASS] " if ok else ("[KNOWN] " if known and not ARGS.strict else "[FAIL] ")
    RES.append((name, bool(ok), bool(known) and not ARGS.strict))
    extra = "" if ok else f"  -> {str(info)[:400]}" + (f"  ({known})" if known and not ok else "")
    print(tag + name + extra, flush=True)
    return ok


def note(msg):
    print("       " + msg, flush=True)


# ---------------------------------------------------------------------------------------------------------------- the site
def git(*a, cwd=None, timeout=300):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(a[:3])}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()


def ensure_clone(dst, branch, patterns, refresh):
    """A shallow, blobless, sparse clone of the Pages repo's branch, kept in the cache between runs."""
    if not os.path.isdir(os.path.join(dst, ".git")):
        shutil.rmtree(dst, ignore_errors=True)
        git("clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", "--branch", branch, PAGES_GIT, dst)
        git("-C", dst, "sparse-checkout", "set", "--no-cone", *patterns)
        git("-C", dst, "checkout", "-q", branch)
    elif refresh:
        try:
            git("-C", dst, "fetch", "-q", "--depth", "1", "origin", branch)
            git("-C", dst, "reset", "-q", "--hard", "FETCH_HEAD")
        except Exception as e:                                    # offline: the cached copy is still a faithful copy
            note(f"could not refresh {branch} ({e}); using the cached copy")
    return git("-C", dst, "rev-parse", "HEAD"), git("-C", dst, "log", "-1", "--format=%ci %s")


def _has_ref(repo, ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", "-q", "--verify", ref], capture_output=True).returncode == 0


def link_tree(src, dst):
    for d, dirs, files in os.walk(src):
        dirs[:] = [x for x in dirs if x != ".git"]
        out = os.path.join(dst, os.path.relpath(d, src))
        os.makedirs(out, exist_ok=True)
        for f in files:
            try:
                os.link(os.path.join(d, f), os.path.join(out, f))
            except OSError:
                shutil.copy2(os.path.join(d, f), os.path.join(out, f))


def put(src, dst):
    """Copy over a (possibly hard-linked) file without touching the cached original."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        os.unlink(dst)
    shutil.copy2(src, dst)


def app_dirs(src):
    """The app folders tools/build_web_dashboard.py publishes next to the page (its `for app in (...)`), plus any
    tools/web_public/<dir>/index.html (a new app in an export without the build script)."""
    web = os.path.join(src, "tools", "web_public")
    apps = []
    b = os.path.join(src, "tools", "build_web_dashboard.py")
    if os.path.exists(b):
        m = re.search(r"for app in \(([^)]*)\):", open(b, encoding="utf-8").read())
        if m:
            apps = re.findall(r"[\"']([\w.-]+)[\"']", m.group(1))
    for d in sorted(os.listdir(web)):
        if d not in apps and os.path.isfile(os.path.join(web, d, "index.html")):
            apps.append(d)
    return apps or ["jarvis", "kalshi"]


def overlay(src, base):
    """tools/web_public as the site build publishes it: its files at the top, the app folders, the icons."""
    web = os.path.join(src, "tools", "web_public")
    n = 0
    for name in os.listdir(web):
        if os.path.isfile(os.path.join(web, name)):
            put(os.path.join(web, name), os.path.join(base, name))
            n += 1
    apps = app_dirs(src)
    for app in apps:
        d = os.path.join(web, app)
        if os.path.isdir(d):
            for name in os.listdir(d):
                if os.path.isfile(os.path.join(d, name)):
                    put(os.path.join(d, name), os.path.join(base, app, name))
                    n += 1
    kit = os.path.join(src, "tools", "kalshi_kit", "public")        # the Kalshi kit's public files, never over a page file
    if os.path.isdir(kit) and os.path.isdir(os.path.join(base, "kalshi")):
        for name in os.listdir(kit):
            if os.path.isfile(os.path.join(kit, name)) and not os.path.exists(os.path.join(base, "kalshi", name)):
                put(os.path.join(kit, name), os.path.join(base, "kalshi", name))
    icons = os.path.join(src, "web", "icons")
    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "icon.svg"):
        if os.path.exists(os.path.join(icons, name)):
            put(os.path.join(icons, name), os.path.join(base, "icons", name))
    return n, apps


def planner_addons(src, base):
    """tools/planner_patches/*.patch on top of planner-backup, as scripts/add_planner.sh does at every publish (name order,
    each on its own; one that does not apply is skipped)."""
    pdir = os.path.join(src, "tools", "planner_patches")
    patches = sorted(glob.glob(os.path.join(pdir, "*.patch")))
    if not patches:
        return None
    pl = os.path.join(base, "planner")
    for d, _dirs, files in os.walk(pl):                         # own copies: never patch the cached clone through a link
        for f in files:
            fp = os.path.join(d, f)
            data = open(fp, "rb").read()
            os.unlink(fp)
            open(fp, "wb").write(data)
    out = {"applied": [], "skipped": []}
    for pt in patches:
        name = os.path.basename(pt)[:-6]
        ok = subprocess.run(["git", "apply", "--check", pt], cwd=base, capture_output=True).returncode == 0 and \
            subprocess.run(["git", "apply", pt], cwd=base, capture_output=True).returncode == 0
        out["applied" if ok else "skipped"].append(name)
    with open(os.path.join(pl, "addons.json"), "w") as f:
        json.dump({"v": 1, **out}, f)
    note(f"planner add-ons: applied {out['applied']}, skipped {out['skipped']}")
    return out


def sw_cache(path):
    try:
        m = re.search(r"const CACHE\s*=\s*['\"]([^'\"]+)['\"]", open(path, encoding="utf-8").read())
        return m.group(1) if m else None
    except OSError:
        return None


def build_sites(work):
    cache = ARGS.cache
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    nqd, pl = os.path.join(cache, "nqd"), os.path.join(cache, "planner")
    sha, what = ensure_clone(nqd, "main", NQD_SPARSE, ARGS.refresh)
    psha, _ = ensure_clone(pl, "planner-backup", PLANNER_SPARSE, ARGS.refresh)
    tree = set(git("-C", nqd, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    LIVE_FILES.clear()
    try:                                  # the PC's other live files (Live View, Holodeck), as published on the branch live
        if ARGS.refresh or not _has_ref(nqd, "refs/remotes/origin/live"):
            git("-C", nqd, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", "live:refs/remotes/origin/live", timeout=120)
        for name in ("liveview.json", "holo.json", "holo_hist.json"):
            r = subprocess.run(["git", "-C", nqd, "show", f"refs/remotes/origin/live:{name}"], capture_output=True, timeout=120)
            if r.returncode == 0:
                LIVE_FILES[name] = r.stdout
    except Exception as e:
        note(f"(the live branch's files are not available: {e})")
    S = {"pub": os.path.join(work, "pub"), "new": os.path.join(work, "new"), "sha": sha, "what": what, "psha": psha,
         "tree": tree, "nqd": nqd}
    for k in ("pub", "new"):
        b = os.path.join(S[k], REPO)
        link_tree(nqd, b)
        if os.path.isdir(os.path.join(pl, "planner")):
            shutil.rmtree(os.path.join(b, "planner"), ignore_errors=True)
            link_tree(os.path.join(pl, "planner"), os.path.join(b, "planner"))
    n, apps = overlay(ARGS.src, os.path.join(S["new"], REPO))
    S["addons"] = planner_addons(ARGS.src, os.path.join(S["new"], REPO))
    S["apps"] = apps
    pub, new = os.path.join(S["pub"], REPO), os.path.join(S["new"], REPO)
    # the workers: (name, folder, published cache name, new cache name)
    S["workers"] = {}
    for name, rel in (("Zenith", "sw.js"), ("Jarvis", "jarvis/sw.js"), ("Planner", "planner/sw.js")):
        S["workers"][name] = {"rel": rel, "old": sw_cache(os.path.join(pub, rel)), "new": sw_cache(os.path.join(new, rel)),
                              "same": _same(os.path.join(pub, rel), os.path.join(new, rel))}
    changed = [f for f in _files(new) if not _same(os.path.join(pub, f), os.path.join(new, f))]
    S["changed"] = changed
    S["bumped"] = []
    for name, w in S["workers"].items():
        if w["same"] and w["new"] and name != "Planner":
            # nothing new to update to: a synthetic release (the same worker under a new cache name) tests the update path
            p = os.path.join(new, w["rel"])
            txt = open(p, encoding="utf-8").read().replace(f"'{w['new']}'", f"'{w['new']}-qa'", 1)
            os.unlink(p)
            open(p, "w", encoding="utf-8").write(txt + "\n// qa: synthetic release to test the update path\n")
            w["new"] = w["new"] + "-qa"
            S["bumped"].append(name)
    note(f"site: published main {sha[:8]} ({what[:60]}), planner-backup {psha[:8]}, overlay {n} files from "
         f"{os.path.relpath(ARGS.src) if ARGS.src != ROOT else 'this checkout'} (apps {', '.join(apps)}); "
         f"{len(changed)} files differ from the published site; ready in {time.time() - t0:.1f} s")
    if changed:
        note("differ: " + ", ".join(sorted(changed)[:25]) + (" ..." if len(changed) > 25 else ""))
    return S


def _files(base):
    out = []
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in (".git", "charts", "recaps")]
        out += [os.path.relpath(os.path.join(d, f), base) for f in files]
    return out


def _same(a, b):
    try:
        return os.path.samefile(a, b) or open(a, "rb").read() == open(b, "rb").read()
    except OSError:
        return False


# -------------------------------------------------------------------------------------------------------- the stub feeds
LIVE = {"v": 1, "kind": "le-live", "t": 0,
        "pc_verdict": {"code": "RUNNING", "label": "RUNNING: bot trading", "level": "good", "reason": "heartbeat fresh"},
        "board": {"running": True,
                  "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2,
                          "room": 1105.6, "to_target": 3726.2, "today_pnl": 212.5, "week_pnl": -224.5, "status": "open"},
                  "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "balance": 24750.4, "floor": 24000.0,
                            "room": 750.4, "to_target": 1749.6, "today_pnl": 0.0, "status": "open"},
                  "blitz": {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "SIM", "balance": 25112.3, "floor": 24500.0,
                            "room": 612.3, "to_target": 1387.7, "today_pnl": 95.25, "week_pnl": 140.0, "status": "open", "off": False,
                            "trades_today": 2, "waiting": "Waiting for the 14:30 check."}}}     # = tests/test_jarvis_hub.py LIVE


def kalshi_json():
    now = int(time.time())
    try:
        sys.path.insert(0, ROOT)
        from engine import kalshi_publish as kp             # the PC's status file through the real clean() (read-only)
        return kp.clean({**kp.SAMPLE, "t": now - 60})
    except Exception:
        return {"v": 1, "kind": "kalshi", "name": "Kalshi bot", "mode": "paper", "running": True, "status": "Watching 12 markets",
                "t": now - 60, "balance": 512.34, "today_pnl": 18.5, "week_pnl": 42.1, "total_pnl": 112.34,
                "positions": [{"ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes", "contracts": 10,
                               "avg_price": 0.42, "price": 0.55, "value": 5.5, "pnl": 1.3, "closes": "2026-11-02T23:59:00Z"}],
                "trades": [], "days": [["2026-10-30", 12.4], ["2026-10-31", -3.1], ["2026-11-01", 18.5]]}


# GitHub Pages' own error pages (light grey #f1f1f1: what the phone shows when the site answers 404 and nothing saved answers)
GH404 = ('<!DOCTYPE html><html><head><meta http-equiv="Content-type" content="text/html; charset=utf-8">'
         '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:;">'
         '<title>{title} &middot; GitHub Pages</title><style type="text/css" media="screen">body {{ background-color: #f1f1f1; margin: 0; '
         'font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }} .container {{ margin: 50px auto 40px auto; width: 600px; '
         'text-align: center; }} h1 {{ width: 800px; position:relative; left: -100px; letter-spacing: -1px; line-height: 60px; '
         'font-size: 60px; font-weight: 100; margin: 0px 0 50px 0; text-shadow: 0 1px 0 #fff; }} p {{ color: rgba(0, 0, 0, 0.5); '
         'margin: 20px 0; line-height: 1.6; }}</style></head><body><div class="container"><h1>404</h1><p><strong>{msg}</strong></p>'
         '</div></body></html>')
GH404_FILE = GH404.format(title="Page not found", msg="File not found").encode()
GH404_SITE = GH404.format(title="Site not found", msg="There isn't a GitHub Pages site here.").encode()


class Ctl:
    """What the local GitHub Pages answers right now."""
    def __init__(self):
        self.root = None              # the folder that holds nq-dashboard/
        self.mode = "ok"              # ok | slow | down (every connection dropped) | 404 (the whole site)
        self.prefix = BASE            # the paths the mode applies to
        self.exclude = ()             # ... except these
        self.slow_s = SLOW_S
        self.kalshi = "published"     # published | waiting (404: the PC has not published kalshi.json yet)
        self.lazy = None
        self.hits = []                # (path, status) of the site's answers
        self.lock = threading.Lock()

    def set(self, mode="ok", prefix=BASE, root=None, exclude=()):
        self.mode, self.prefix, self.exclude = mode, prefix, tuple(exclude)
        if root:
            self.root = root


CTL = Ctl()
LIVE_FILES = {}       # liveview.json, holo.json, holo_hist.json from the branch live (the real published files)


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GitHub.com"
    sys_version = ""
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json",
                      ".js": "application/javascript; charset=utf-8", ".mjs": "application/javascript; charset=utf-8",
                      ".json": "application/json; charset=utf-8", ".md": "text/markdown; charset=utf-8",
                      ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        self.directory = CTL.root
        return super().translate_path(path)

    def end_headers(self):
        if getattr(self, "_site", False):
            self.send_header("Cache-Control", "max-age=600")
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_bytes(self, code, body, ctype, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            return self.send_bytes(404, GH404_FILE, "text/html; charset=utf-8")
        return super().send_error(code, message, explain)

    def do_OPTIONS(self):
        self.send_bytes(204, b"", "text/plain", {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*",
                                                 "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        self.send_bytes(200, b"{}", "application/json", {"Access-Control-Allow-Origin": "*"})

    def stub(self, host, path):
        cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Expose-Headers": "*"}
        if host in ("api.github.com", "raw.githubusercontent.com"):
            if CTL.mode == "down":                        # offline: the feeds are gone too
                return self.drop()
            if path.endswith("/kalshi.json"):
                if CTL.kalshi != "published":
                    return self.send_bytes(404, b"404: Not Found", "text/plain; charset=utf-8", cors)
                return self.send_bytes(200, json.dumps(kalshi_json()).encode(), "application/json", cors)
            name = path.rsplit("/", 1)[-1]
            if name in LIVE_FILES:
                return self.send_bytes(200, LIVE_FILES[name], "application/json", cors)
            if path.endswith("/live.json"):
                body = json.dumps(dict(LIVE, t=int(time.time()) - 120)).encode()
                return self.send_bytes(200, body, "application/json", {**cors, "x-ratelimit-remaining": "55",
                                                                      "x-ratelimit-reset": str(int(time.time()) + 3600)})
            return self.send_bytes(404, b'{"message":"Not Found"}', "application/json", cors)
        if host == "fonts.googleapis.com":
            return self.send_bytes(200, b"/* fonts: not loaded in the test */", "text/css", cors)
        if host == "ntfy.sh":                              # the push relay's poll (alerts): no new messages
            return self.send_bytes(200, b"", "application/x-ndjson", cors)
        return self.send_bytes(404, b"", "text/plain", cors)

    def drop(self):
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        path = unquote(urlsplit(self.path).path)
        if host in STUB_HOSTS:
            return self.stub(host, path)
        hit = path.startswith(CTL.prefix) and not any(path.startswith(x) for x in CTL.exclude)
        if CTL.mode == "down" and hit:
            with CTL.lock:
                CTL.hits.append((path, "dropped"))
            return self.drop()
        if CTL.mode == "404" and hit:
            with CTL.lock:
                CTL.hits.append((path, 404))
            return self.send_bytes(404, GH404_SITE, "text/html; charset=utf-8")
        if CTL.mode == "slow" and hit:
            time.sleep(CTL.slow_s)
        self._site = True
        fs = self.translate_path(self.path)
        if not os.path.exists(fs) and CTL.lazy and path.startswith(BASE):
            CTL.lazy(path[len(BASE):])
        with CTL.lock:
            CTL.hits.append((path, 200 if os.path.exists(fs) else 404))
        try:
            return super().do_GET()
        except (ConnectionError, ssl.SSLError):
            pass


class TLSServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, certfile, keyfile):
        super().__init__(addr, handler)
        self.sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.sslctx.load_cert_chain(certfile, keyfile)

    def finish_request(self, request, client_address):             # the handshake in the request's own thread
        try:
            request = self.sslctx.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return
        self.RequestHandlerClass(request, client_address, self)

    def handle_error(self, request, client_address):
        pass


def make_cert(d):
    cert, key = os.path.join(d, "cert.pem"), os.path.join(d, "key.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cert, "-days", "2",
                    "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"],
                   check=True, capture_output=True, timeout=60)
    return cert, key


def make_lazy(S):
    """runs/, writeups/ ... are not checked out: a file a page asks for is fetched from the Pages repo on demand."""
    lock = threading.Lock()

    def lazy(rel):
        if rel not in S["tree"] or rel.startswith("planner/"):
            return
        with lock:
            dst = os.path.join(CTL.root, REPO, rel)
            if os.path.exists(dst):
                return
            r = subprocess.run(["git", "-C", S["nqd"], "show", f"HEAD:{rel}"], capture_output=True, timeout=120)
            if r.returncode == 0:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(r.stdout)
                S.setdefault("lazy", []).append(rel)
    return lazy


# --------------------------------------------------------------------------------------------------------- the browser
def chrome_exe():
    return next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)


class Phone:
    """One Home Screen app's storage (a browser context) with every error it shows."""
    def __init__(self, br, dev="iPhone 13", **kw):
        opts = dict(PHONES[dev], is_mobile=True, has_touch=True, user_agent=UA, color_scheme="dark", locale="en-US",
                    timezone_id="America/New_York", service_workers="allow", ignore_https_errors=True)
        opts.update(kw)
        self.dev = dev
        self.ctx = br.new_context(**opts)
        self.errs = []                # (kind, text, where)
        self.bad = []                 # failed same-site requests / site answers >= 400
        self.ext = set()              # outside hosts the pages tried to reach

    def page(self):
        p = self.ctx.new_page()
        p.on("pageerror", lambda e: self.errs.append(("pageerror", str(e)[:300], p.url)))
        p.on("console", lambda m: m.type == "error" and self.errs.append(("console", m.text[:300], (m.location or {}).get("url", ""))))
        p.on("requestfailed", lambda r: self._failed(r))
        p.on("response", lambda r: self._resp(r))
        return p

    def _failed(self, r):
        u = urlsplit(r.url)
        if u.hostname == "127.0.0.1":
            self.bad.append(("failed", r.url, r.failure))
        elif u.hostname not in STUB_HOSTS and u.scheme in ("http", "https"):
            self.ext.add(u.hostname)

    def _resp(self, r):
        u = urlsplit(r.url)
        if u.hostname == "127.0.0.1" and r.status >= 400:
            self.bad.append((r.status, r.url, ""))

    def mark(self):
        return len(self.errs), len(self.bad)

    def since(self, m, allow=()):
        errs = [e for e in self.errs[m[0]:] if not any(re.search(a, e[1] + " " + e[2]) for a in allow)]
        bad = [b for b in self.bad[m[1]:] if not any(re.search(a, str(b[1]) + " " + str(b[0])) for a in allow)]
        return errs, bad

    def close(self):
        try:
            self.ctx.close()
        except Exception:
            pass


READY_INIT = """(() => {
  if (window.top !== window || !/\\/jarvis\\/(index\\.html)?$/.test(location.pathname)) return;
  const ok = () => document.readyState !== 'loading' && !document.getElementById('boot')
    && document.querySelectorAll('[data-app]').length >= 3 && !!document.querySelector('input, textarea');
  const t = () => { if (ok()) { window.__qaReady = performance.now(); return; } requestAnimationFrame(t); };
  requestAnimationFrame(t);
})();"""
JARVIS_HOME = "() => { const h = document.getElementById('home'); return !!h && !h.hidden && h.getBoundingClientRect().height > 0; }"
ZENITH_READY = ("() => { const p = document.querySelector('#page'); return !!p && !p.querySelector(':scope > .skel') "
                "&& p.textContent.trim().length > 40; }")
PLANNER_READY = "() => /Planner/i.test(document.title) && document.body && document.body.innerText.trim().length > 40"
KALSHI_READY = "() => /Kalshi/i.test(document.title) && !!document.getElementById('body')"


def jarvis_url(base):
    return base + "jarvis/"


def wait_ready(p, timeout=15000):
    p.wait_for_function("() => window.__qaReady !== undefined", timeout=timeout)
    return p.evaluate("Math.round(window.__qaReady)")


def judge(png, label):
    """A screenshot -> its dominant color, the share of near-white pixels, and whether it is white."""
    from PIL import Image
    SHOTS["n"] += 1
    fn = None
    if SHOTS["dir"]:
        fn = os.path.join(SHOTS["dir"], f"{SHOTS['n']:03d}_{re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')[:60]}.png")
        with open(fn, "wb") as f:
            f.write(png)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im = im.resize((max(1, im.width // 3), max(1, im.height // 3)))
    raw = im.tobytes()
    q = {}
    white = 0
    n = len(raw) // 3
    for i in range(0, n * 3, 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        k = (r >> 4, g >> 4, b >> 4)
        q[k] = q.get(k, 0) + 1
        if r >= 224 and g >= 224 and b >= 224:
            white += 1
    dom = max(q, key=q.get)
    hexc = "#%02x%02x%02x" % tuple(c * 16 + 8 for c in dom)
    return {"dom": hexc, "dom_share": q[dom] / n, "white": white / n, "file": fn,
            "is_white": all(c * 16 + 8 >= 224 for c in dom)}


def shot(p, label, full=False):
    return judge(p.screenshot(type="png", scale="css", full_page=full, timeout=15000), label)


def cdp_shot(cdp, p, label):
    """What the screen shows right now, even in the middle of a navigation (Playwright's screenshot waits for it)."""
    vp = p.viewport_size or {"width": 390, "height": 844}
    r = cdp.send("Page.captureScreenshot", {"format": "png", "clip": {"x": 0, "y": 0, "width": vp["width"], "height": vp["height"],
                                                                     "scale": 1}})
    return judge(base64.b64decode(r["data"]), label)


def watch(p, cdp, label, until, seconds, every=0.3):
    """Screenshots until until() is true: -> (seconds until it was, seconds the screen was last white, [(t, color)])."""
    t0 = time.time()
    frames, done = [], None
    while time.time() - t0 < seconds:
        el = time.time() - t0
        try:
            s = cdp_shot(cdp, p, f"{label} t={el:.1f}s")
            frames.append((round(el, 1), s["dom"], s["is_white"]))
        except Exception:
            pass
        try:
            if until():
                done = time.time() - t0
                break
        except Exception:
            pass
        time.sleep(every)
    white_until, was_white = 0.0, False         # a white frame stays on screen until the next frame that is not white
    for t, _, w in frames:
        if w:
            was_white = True
        elif was_white:
            white_until, was_white = t, False
    if was_white:
        white_until = round(time.time() - t0, 1)
    return done, white_until, frames


def strip(frames, n=14):
    """The timeline in short: color changes only."""
    out, last = [], None
    for t, c, w in frames:
        if c != last:
            out.append(f"{t}s:{c}{'(white)' if w else ''}")
            last = c
    return " ".join(out[:n])


def not_white(p, label, light_ok=False):
    """The dominant color is not white. light_ok (an app whose own look is light, the Planner): only a blank page fails."""
    s = shot(p, label)
    bad = s["white"] >= 0.97 if light_ok else s["is_white"]
    return check(f"not {'blank ' if light_ok else ''}white: {label}", not bad, f"dominant {s['dom']} ({s['dom_share']:.0%}), "
                 f"{s['white']:.0%} near-white pixels, {s['file'] or ''}"), s


def hscroll(target):
    """[document scroll width, client width, a few elements sticking out on the right and not clipped]"""
    return target.evaluate("""() => {
      const de = document.documentElement, W = de.clientWidth, out = [];
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || r.right <= W + 1 || getComputedStyle(el).position === 'fixed') continue;
        let p = el.parentElement, clip = false;
        while (p && p !== document.body) { if (getComputedStyle(p).overflowX !== 'visible') { clip = true; break; } p = p.parentElement; }
        if (!clip) out.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '') + ' ' + Math.round(r.right));
      }
      return [de.scrollWidth, W, out.slice(0, 4)];
    }""")


def frames_alive(p):
    return p.evaluate("document.querySelectorAll('iframe').length")


def dash_frame(p, app):
    """The Frame of the dashboard `app` inside Jarvis (#v-<app> iframe)."""
    el = p.query_selector(f"#v-{app} iframe")
    return el.content_frame() if el else None


# Zenith's scroller: the document, or its first scrolling box
SCROLL_FIND = """(() => { const cand = [document.scrollingElement, ...document.querySelectorAll('.main, #page, main, .page')];
  for (const el of cand) { if (!el) continue; const cs = el === document.scrollingElement ? null : getComputedStyle(el);
    if (el.scrollHeight > el.clientHeight + 80 && (!cs || /auto|scroll/.test(cs.overflowY))) return el; } return null; })()"""
SCROLL_SET = ("() => { const el = " + SCROLL_FIND + "; if (!el) return null; el.scrollTop = 400; "
              "return [el === document.scrollingElement ? 'the page' : (el.id ? '#' + el.id : '.' + el.className.split(' ')[0]), Math.round(el.scrollTop)]; }")
SCROLL_GET = ("() => { const el = " + SCROLL_FIND + "; if (!el) return null; "
              "return [el === document.scrollingElement ? 'the page' : (el.id ? '#' + el.id : '.' + el.className.split(' ')[0]), Math.round(el.scrollTop)]; }")


def tap(p, app):
    """Tap an app in Jarvis's top bar (a mode button or an app chip). Zenith mode is full screen over the bar: the owner
    goes back to Jarvis first (its floating control), then taps the app."""
    if app != "zenith" and _ev(p, ZEN_MODULE):
        go_home(p)
        if app == "home":
            return
    loc = p.locator(f'header [data-app="{app}"]')
    (loc if loc.count() else p.locator(f'[data-app="{app}"]')).first.click(timeout=8000)


# Zenith mode (jarvis/zenith-mode.js): its full-screen layer .zm-root (may sit on <body>), or the hub's #zen view
ZEN_MODULE = ("() => { const r = document.querySelector('.zm-root'); if (r) { const cs = getComputedStyle(r); "
              "return cs.visibility === 'visible' && +cs.opacity > 0.5 && r.getBoundingClientRect().height > 0; } "
              "const z = document.getElementById('zen'); return !!z && !z.hidden && z.getBoundingClientRect().height > 0 "
              "&& (z.querySelector('iframe') ? true : z.textContent.trim().length > 40); }")
ZEN_FRAME_SEL = ".zm-root iframe, #zen iframe"


def zenith_view(p, timeout=30000, ready=True):
    """Zenith inside Jarvis: Zenith mode (zenith-mode.js mounted in #zen) or Zenith in a frame (#v-zenith iframe).
    -> (target to evaluate in, kind 'frame' | 'module')."""
    t0 = time.time()
    while True:                                   # at least one look, even with timeout=0
        try:
            if p.evaluate(ZEN_MODULE):
                el = p.query_selector(ZEN_FRAME_SEL)
                f = el.content_frame() if el else None
                if f and (not ready or _ev(f, ZENITH_READY)):
                    return f, "module-frame"
                if not el and (not ready or p.evaluate(ZEN_MODULE)):
                    return p, "module"
        except Exception:
            pass
        f = dash_frame(p, "zenith")
        if f and f.url and f.url != "about:blank" and (not ready or _ev(f, ZENITH_READY)):
            return f, "frame"
        if time.time() - t0 >= timeout / 1000:
            return None, None
        p.wait_for_timeout(150)


def _ev(target, js):
    try:
        return target.evaluate(js)
    except Exception:
        return False


def open_zenith(p, timeout=30000, ready=True):
    tap(p, "zenith")
    return zenith_view(p, timeout, ready)


def open_app(p, app, ready_js=None, timeout=20000):
    if app == "zenith":
        return open_zenith(p, timeout, bool(ready_js))[0]
    tap(p, app)
    p.wait_for_selector(f"#v-{app} iframe", state="attached", timeout=timeout)
    f = None
    t0 = time.time()
    while time.time() - t0 < timeout / 1000:
        f = dash_frame(p, app)
        if f and f.url and f.url != "about:blank":
            break
        p.wait_for_timeout(100)
    if ready_js and f:
        f.wait_for_function(ready_js, timeout=timeout)
    return f


def go_home(p):
    if _ev(p, ZEN_MODULE):                       # Zenith mode: its floating "Back to Jarvis" control
        back = p.locator('.zm-back, [aria-label="Back to Jarvis"]')
        if back.count():
            back.first.click(timeout=8000)
            p.wait_for_function(JARVIS_HOME, timeout=5000)
            p.wait_for_timeout(250)
            return
    loc = p.locator('header [data-app="home"]')
    (loc if loc.count() else p.locator('[data-app="home"]')).first.click(timeout=8000)
    p.wait_for_function(JARVIS_HOME, timeout=5000)


def mode_of(p):
    """Jarvis mode / Zenith mode (data-mode on <html>, the shell of 2026-11-01), None on the older hub."""
    return p.evaluate("document.documentElement.dataset.mode || null")


def ask(p, q):
    p.evaluate("(() => { const t = document.getElementById('talk'); if (t) t.innerHTML = ''; })()")
    p.fill("#q", q)
    p.press("#q", "Enter")
    p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=8000)
    return p.locator(".msg.j").last.inner_text()


def sw_state(p):
    return p.evaluate("""async () => {
      const regs = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistrations() : [];
      return { regs: regs.map((r) => ({ scope: r.scope, active: r.active && r.active.scriptURL, state: r.active && r.active.state,
                 waiting: !!r.waiting, installing: !!r.installing })),
               caches: (await caches.keys()).sort(),
               controller: navigator.serviceWorker && navigator.serviceWorker.controller ? navigator.serviceWorker.controller.scriptURL : null };
    }""")


def cached_text(p, cache, url):
    return p.evaluate("""async ([name, url]) => { if (!(await caches.has(name))) return null; const c = await caches.open(name);
      const r = await c.match(url, { ignoreSearch: true }); return r ? await r.text() : null; }""", [cache, url])


def has_copy(p, prefix, rel):
    """Some cache of that app (its name prefix) still holds its page."""
    return p.evaluate("""async ([prefix, rel]) => {
      const u = new URL('../' + rel, location.href).href;
      for (const k of await caches.keys()) if (k.startsWith(prefix) && await (await caches.open(k)).match(u, { ignoreSearch: true })) return true;
      return false; }""", [prefix, rel])


def wait_caches(p, want, gone=(), timeout=20000):
    """Wait until every cache in `want` exists and none in `gone` does."""
    t0 = time.time()
    st = None
    while time.time() - t0 < timeout / 1000:
        st = p.evaluate("async () => (await caches.keys()).sort()")
        if all(w in st for w in want) and not any(g in st for g in gone):
            return True, st
        p.wait_for_timeout(250)
    return False, st


def clear_http_cache(phone, p):
    """Ten minutes later: GitHub Pages' max-age=600 has run out (the browser's HTTP cache, not the workers' caches)."""
    try:
        s = phone.ctx.new_cdp_session(p)
        s.send("Network.clearBrowserCache")
        s.detach()
    except Exception as e:
        note(f"(could not clear the HTTP cache: {e})")


def no_errors(phone, m, label, allow=()):
    allow = tuple(allow) + tuple(r"/jarvis/" + re.escape(x) for x in MISSING)       # reported once by part a
    errs, bad = phone.since(m, allow)
    check(f"no page or console errors: {label}", not errs, errs[:4])
    check(f"no failed or missing same-site requests: {label}", not bad, bad[:4])


def reopen(phone, url, wait_home=True, timeout=15000):
    """The owner taps the Home Screen icon again: a fresh page that starts blank and goes to the app."""
    p = phone.page()
    p.goto(url, wait_until="commit", timeout=timeout + 30000)
    if wait_home:
        p.wait_for_function(JARVIS_HOME, timeout=timeout)
    return p


# ---------------------------------------------------------------------------------------------------------- the checks
def part_a(S):
    new = os.path.join(S["new"], REPO)
    web = os.path.join(ARGS.src, "tools", "web_public")
    for app in ("jarvis", "kalshi"):
        check(f"a. {app}/ is published with the site (tools/build_web_dashboard.py)", app in S["apps"], S["apps"])
    check("a. jarvis/ has its page, worker and manifest", all(os.path.exists(os.path.join(new, "jarvis", f)) for f in
                                                          ("index.html", "sw.js", "manifest.webmanifest")))
    check("a. the planner (planner-backup) has its page and worker", all(os.path.exists(os.path.join(new, "planner", f)) for f in
                                                                       ("index.html", "sw.js")))
    zsw = open(os.path.join(new, "sw.js"), encoding="utf-8").read()
    m = re.search(r"const OTHER_APPS = \[([^\]]*)\]", zsw)
    other = re.findall(r"'([^']+)'", m.group(1)) if m else []
    apps = [a + "/" for a in S["apps"]] + ["planner/"]
    check("a. Zenith's worker stays out of every other app's folder (OTHER_APPS)", all(a in other for a in apps), (other, apps))
    check("a. Zenith's worker deletes only its own caches", "k.startsWith('le-public-')" in zsw)
    jsw = open(os.path.join(new, "jarvis", "sw.js"), encoding="utf-8").read()
    check("a. Jarvis's worker deletes only its own caches and keeps to its folder",
          "startsWith('jarvis-')" in jsw and "startsWith(scope.pathname)" in jsw)
    # the Jarvis shell's own modules (import ... from './x.js', load('name', './x.js', ...)): each must be on the site, or every
    # open asks for a missing file (a 404 and a fallback)
    jh = open(os.path.join(new, "jarvis", "index.html"), encoding="utf-8").read()
    mods = sorted(set(re.findall(r"""(?:from|import\(|load\('\w+',)\s*['"]\./([\w.-]+\.m?js)['"]""", jh)))
    missing = [x for x in mods if not os.path.exists(os.path.join(new, "jarvis", x))]
    S["jarvis_missing"] = missing
    if mods:
        note("Jarvis modules: " + ", ".join(mods))
        check("a. every module the Jarvis page loads is on the site", not missing, f"missing: {', '.join(missing)}")
    jsw2 = open(os.path.join(new, "jarvis", "sw.js"), encoding="utf-8").read()
    shell = re.search(r"const SHELL = \[([^\]]*)\]", jsw2)
    pre = re.findall(r"'\./([^'?]+)", shell.group(1)) if shell else []
    gone = [x for x in pre if x and not os.path.exists(os.path.join(new, "jarvis", x))]
    if pre:
        check("a. every file Jarvis's worker saves at install is on the site", not gone, f"missing: {', '.join(gone)}")
    names = [w["new"] for w in S["workers"].values()]
    check("a. every worker has its own cache name", len(set(names)) == len(names) and all(names), names)
    for name, w in S["workers"].items():
        note(f"{name} worker: published {w['old']} -> new {w['new']}" + (" (synthetic bump)" if name in S["bumped"] else ""))
    # each app page has a dark first paint: the background is set before any script runs
    for rel in ("jarvis/index.html", "index.html", "kalshi/index.html"):
        h = open(os.path.join(new, rel), encoding="utf-8", errors="replace").read()
        tc = re.search(r'<meta name="theme-color" content="([^"]+)"', h)
        check(f"a. {rel}: dark theme-color", bool(tc) and tc.group(1).lower() not in ("#fff", "#ffffff", "white"), tc and tc.group(1))
    if not os.path.isdir(web):
        check("a. --src has tools/web_public", False, web)


def part_b(br, S, base):
    """Jarvis opens at the three iPhone sizes: cold (first open) and from its saved copy."""
    times = {}
    for dev in PHONES:
        ph = Phone(br, dev)
        ph.ctx.add_init_script(READY_INIT)
        try:
            m = ph.mark()
            p = ph.page()
            p.goto(jarvis_url(base), wait_until="commit")
            cold = wait_ready(p)
            p.wait_for_timeout(700)          # the live feed and Kalshi answer
            txt = p.inner_text("body")
            check(f"b. {dev}: the Jarvis screen with the bots' numbers ($1,106 room) and Kalshi ($512.34)",
                  p.evaluate(JARVIS_HOME) and "$1,106" in txt and "$512.34" in txt, txt[:300])
            w = hscroll(p)
            check(f"b. {dev}: no sideways scroll on the Jarvis screen", w[0] <= w[1] and not w[2], w)
            not_white(p, f"Jarvis home {dev}")
            p.evaluate("navigator.serviceWorker.ready.then(() => true)")
            wait_caches(p, [S["workers"]["Jarvis"]["new"]], timeout=10000)
            p2 = ph.page()
            p2.goto(jarvis_url(base), wait_until="commit")
            warm = wait_ready(p2)
            ctl = p2.evaluate("navigator.serviceWorker.controller ? navigator.serviceWorker.controller.scriptURL : null")
            times[dev] = (cold, warm)
            note(f"{dev}: interactive {cold} ms cold, {warm} ms from the saved copy (worker: {ctl and ctl.split(BASE)[-1]})")
            check(f"b. {dev}: the second open is served by Jarvis's own worker", bool(ctl) and ctl.endswith("/jarvis/sw.js"), ctl)
            no_errors(ph, m, f"Jarvis at {dev}")
        finally:
            ph.close()
    best = {d: min(t) for d, t in times.items()}
    check(f"b. perf: Jarvis home interactive under {PERF_BUDGET_MS} ms locally (cold and saved copy, every size)",
          all(max(t) < PERF_BUDGET_MS for t in times.values()), times)
    return best


def part_c(br, S, base, ph):
    """Switching between the apps inside Jarvis (one phone, kept for d / e / f / g)."""
    p = ph.page()
    m = ph.mark()
    p.goto(jarvis_url(base), wait_until="commit")
    wait_ready(p)
    p.wait_for_timeout(600)
    m0 = mode_of(p)
    zf, kind = open_zenith(p, 30000)
    note(f"Zenith inside Jarvis: {kind} (Jarvis mode attribute: {m0!r} -> {mode_of(p)!r})")
    check("c. Zenith opens inside Jarvis and draws its Home", bool(zf), kind)
    if m0 is not None:
        check("c. Jarvis mode -> Zenith mode (data-mode jarvis -> zenith)", m0 == "jarvis" and mode_of(p) == "zenith", (m0, mode_of(p)))
    check("c. the address stays the Jarvis screen (no #zenith)", "#" not in p.url, p.url)
    check("c. one dashboard view alive (Zenith)", frames_alive(p) <= 1 and (kind != "module" or frames_alive(p) == 0), frames_alive(p))
    if zf is None:
        raise RuntimeError("Zenith did not open inside Jarvis")
    w = hscroll(zf)
    check("c. no sideways scroll in Zenith inside Jarvis", w[0] <= w[1], w)
    not_white(p, "Zenith inside Jarvis")
    MARK = "(() => { window.__qaMark = 1; const z = document.querySelector('#zen > *'); if (z) z.dataset.qaMark = '1'; })()"
    MARKED = "(() => window.__qaMark === 1 && (!document.querySelector('#zen > *') || document.querySelector('#zen > *').dataset.qaMark === '1'))()"
    zf.evaluate(MARK)
    sc0 = zf.evaluate(SCROLL_SET)
    go_home(p)
    check("c. back to the Jarvis screen", p.evaluate(JARVIS_HOME))
    if m0 is not None:
        check("c. Zenith mode -> Jarvis mode (data-mode zenith -> jarvis)", mode_of(p) == "jarvis", mode_of(p))
    not_white(p, "Jarvis home after Zenith")
    check("c. one dashboard view alive (Zenith kept for a quick return)", frames_alive(p) <= 1, frames_alive(p))
    zf2, _ = open_zenith(p, 20000)
    check("c. Zenith again: not reloaded (same page kept)", bool(zf2) and _ev(zf2, MARKED))
    if sc0 and sc0[1] > 0:
        p.wait_for_timeout(300)
        sc1 = _ev(zf2, SCROLL_GET) if zf2 else None
        check(f"c. Zenith again: where the owner left it (scrolled {sc0[1]} px in {sc0[0]})", bool(sc1) and abs(sc1[1] - sc0[1]) < 5,
              f"scroll now {sc1}")
    go_home(p)
    zf3, _ = open_zenith(p, 20000)
    check("c. Jarvis -> Zenith -> Jarvis -> Zenith: still the same Zenith page", bool(zf3) and _ev(zf3, MARKED))
    pf = open_app(p, "planner", PLANNER_READY, timeout=30000)
    check("c. the Planner opens inside Jarvis", bool(pf))
    check("c. one dashboard view alive (Planner; Zenith let go)", frames_alive(p) == 1 and not p.query_selector("#v-zenith")
          and not p.evaluate(ZEN_MODULE), frames_alive(p))
    p.wait_for_timeout(500)
    w = hscroll(pf)
    check("c. no sideways scroll in the Planner inside Jarvis", w[0] <= w[1], w)
    not_white(p, "Planner inside Jarvis", light_ok=True)       # the Planner's own default look is light
    kf = open_app(p, "kalshi", "() => document.body && /\\$512\\.34/.test(document.body.textContent)", timeout=20000)
    check("c. Kalshi opens inside Jarvis with the PC's numbers ($512.34)", bool(kf))
    check("c. one dashboard view alive (Kalshi)", frames_alive(p) == 1, frames_alive(p))
    w = hscroll(kf)
    check("c. no sideways scroll in Kalshi inside Jarvis", w[0] <= w[1], w)
    not_white(p, "Kalshi inside Jarvis")
    go_home(p)
    check("c. back to Jarvis from Kalshi", p.evaluate(JARVIS_HOME))
    check("c. one dashboard view alive after Jarvis -> Zenith -> Planner -> Kalshi -> Jarvis", frames_alive(p) <= 1, frames_alive(p))
    if m0 is not None:
        # a Zenith notification tapped while Jarvis runs: Zenith's worker (sw.js v50+) posts {type: 'open', app: 'zenith', hash}
        # to the Jarvis window; Jarvis should switch to Zenith mode at that notice
        p.evaluate("navigator.serviceWorker.dispatchEvent(new MessageEvent('message', { data: { type: 'open', app: 'zenith', hash: '#/blitz' } }))")
        ok = False
        for _ in range(30):
            if mode_of(p) == "zenith":
                zfn, _k = zenith_view(p, 3000, ready=False)
                if zfn and "#/blitz" in (_ev(zfn, "location.hash") or ""):
                    ok = True
                    break
            p.wait_for_timeout(200)
        check("c. a Zenith notification tapped while Jarvis is open: Zenith mode at that notice (#/blitz)", ok,
              f"mode {mode_of(p)!r}")
        try:
            go_home(p)
        except Exception:
            pass
    no_errors(ph, m, "switching Jarvis / Zenith / Planner / Kalshi")
    return p


def part_d(p, ph):
    m = ph.mark()
    n0 = frames_alive(p)
    qa = [("How are the bots?", ["RUNNING", "$1,106", "ATLAS", "BLITZ"], []),
          ("how much room do I have", ["$1,106", "$750", "$612"], []),
          ("how far to target", ["$3,726", "$1,750", "$1,388"], []),
          ("today's p&l", ["+$213", "+$95"], []),
          ("how's blitz", ["BLITZ", "$612", "$1,388"], ["Opening", "Zlarior"]),
          ("how's kalshi", ["$512.34", "+$18.50"], ["Opening"]),
          ("is the market open", ["NQ market"], []),
          ("help", ["open planner"], [])]
    for q, want, never in qa:
        a = ask(p, q)
        check(f"d. '{q}' -> {', '.join(want)}", all(w in a for w in want) and not any(n in a for n in never), a[:300])
    check("d. answers keep the Jarvis screen (no dashboard opened)", p.evaluate(JARVIS_HOME) and frames_alive(p) <= n0,
          (frames_alive(p), n0))
    a = ask(p, "open planner")
    p.wait_for_selector("#v-planner iframe", timeout=8000)
    p.wait_for_timeout(500)
    check("d. 'open planner' opens the Planner", "Opening Planner" in a and p.locator("#v-planner").is_visible(), a)
    go_home(p)
    no_errors(ph, m, "Jarvis's answers")


APPS_IN_JARVIS = (("zenith", ZENITH_READY, "Zenith", False), ("planner", PLANNER_READY, "the Planner", True),
                  ("kalshi", KALSHI_READY, "Kalshi", False))


def frame_ready(p, app, ready, seconds):
    t0 = time.time()
    while True:
        f = dash_frame(p, app)
        try:
            if f and f.evaluate(ready):
                return f, True
        except Exception:
            pass
        if time.time() - t0 >= seconds:
            return f, False
        p.wait_for_timeout(250)


def part_e(br, S, base, ph):
    """A slow network: the site takes SLOW_S s to answer. Jarvis's saved copy shows after NAV_WAIT_S; Zenith's?"""
    m = ph.mark()
    p0 = ph.page()
    p0.goto(jarvis_url(base))
    p0.wait_for_function(JARVIS_HOME)
    w = S["workers"]["Jarvis"]["new"]
    ok, keys = wait_caches(p0, [w, S["workers"]["Zenith"]["new"]], timeout=10000)
    check(f"e. the saved copies are in place ({w}, {S['workers']['Zenith']['new']})",
          ok and cached_text(p0, w, jarvis_url(base) + "index.html") is not None, keys)
    clear_http_cache(ph, p0)
    p0.close()
    lim = NAV_WAIT_S + 2
    # Zenith opened once more in a new Jarvis start: its files now come through Zenith's worker and are saved (the first
    # open ever ran before that worker existed), as on a phone that has used Zenith inside Jarvis before
    pw = ph.page()
    pw.goto(jarvis_url(base))
    wait_ready(pw)
    open_zenith(pw, 30000)
    pw.wait_for_timeout(1500)
    go_home(pw)
    pw.close()
    try:
        # 1. reopen Jarvis (a blank page, then Jarvis) while its folder answers after SLOW_S
        CTL.set("slow", BASE + "jarvis/")
        p = ph.page()
        cdp = ph.ctx.new_cdp_session(p)
        p.evaluate(f"setTimeout(() => {{ location.href = {json.dumps(jarvis_url(base))}; }}, 0)")
        done, white, fr = watch(p, cdp, "slow Jarvis", lambda: p.evaluate("window.__qaReady !== undefined"), 2 * SLOW_S + 8)
        fp = _ev(p, "Math.round((performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime || 0)") or 0
        ia = _ev(p, "Math.round(window.__qaReady || 0)") or 0
        slowest = _ev(p, "performance.getEntriesByType('resource').filter((e) => e.name.includes('/jarvis/')).map((e) => "
                         "[e.name.split('/jarvis/')[1].slice(0, 30), Math.round(e.startTime), Math.round(e.responseEnd)])") or []
        note(f"slow network ({SLOW_S:.0f} s), Jarvis: first paint {fp} ms, interactive {ia} ms, blank white until {white:.1f} s; "
             f"its own files (start, end ms): {slowest[:6]}; {strip(fr)}")
        check(f"e. slow network: Jarvis paints from its saved copy in under {NAV_WAIT_S + 1:.1f} s (not after the site's {SLOW_S:.0f} s)",
              0 < fp < (NAV_WAIT_S + 1) * 1000, f"first paint {fp} ms")
        check(f"e. slow network: Jarvis is interactive from its saved copy in under {lim:.1f} s", 0 < ia < lim * 1000, f"interactive {ia} ms")
        if done:
            p.wait_for_timeout(300)
            not_white(p, "Jarvis on a slow network")
        # 2. Zenith inside Jarvis while Zenith's files are slow (not Jarvis's: the local server speaks HTTP/1.1, six
        # connections a host, where GitHub Pages' HTTP/2 would not queue Zenith behind Jarvis's own slow requests)
        CTL.set("slow", BASE, exclude=(BASE + "jarvis/",))
        clear_http_cache(ph, p)
        tap(p, "zenith")
        done, white, fr = watch(p, cdp, "slow Zenith in Jarvis", lambda: zenith_view(p, 0)[0] is not None, SLOW_S + 6)
        note(f"slow network, Zenith inside Jarvis: drawn after {round(done, 1) if done else f'> {SLOW_S + 6:.0f}'} s, white until {white:.1f} s; "
             f"{strip(fr)}")
        check("e. slow network: Zenith inside Jarvis is never a white frame while it loads", white == 0.0, f"white until {white:.1f} s")
        check(f"e. slow network: Zenith inside Jarvis shows its saved copy in under {lim:.1f} s", done is not None and done < lim, done)
        p.close()
        # 3. Zenith on its own (its own Home Screen app) while the site is slow
        CTL.set("ok")
        pz = ph.page()
        pz.goto(base)
        pz.wait_for_function(ZENITH_READY, timeout=30000)
        clear_http_cache(ph, pz)
        pz.close()
        CTL.set("slow", BASE)
        p = ph.page()
        cdp = ph.ctx.new_cdp_session(p)
        p.evaluate(f"setTimeout(() => {{ location.href = {json.dumps(base)}; }}, 0)")
        done, white, fr = watch(p, cdp, "slow Zenith alone", lambda: p.evaluate(ZENITH_READY), 2 * SLOW_S + 6)
        note(f"slow network, Zenith on its own: drawn after {done and round(done, 1)} s, blank white until {white:.1f} s; {strip(fr)}")
        check(f"e. slow network: Zenith on its own opens from its saved copy in under {lim:.1f} s (not white until the site answers)",
              done is not None and done < lim and white < lim, f"drawn after {done and round(done, 1)} s, white until {white:.1f} s")
        p.close()
    finally:
        CTL.set("ok")
    no_errors(ph, m, "slow network")


def part_f(br, S, base, ph, mode):
    """Offline (`down`: every connection dropped) or a 404 site (`404`), after the apps were opened once."""
    tag = "offline" if mode == "down" else "404 site"
    m = ph.mark()
    p0 = ph.page()
    p0.goto(jarvis_url(base))
    p0.wait_for_function(JARVIS_HOME)
    clear_http_cache(ph, p0)
    p0.close()
    CTL.set(mode, BASE)
    try:
        try:
            p = reopen(ph, jarvis_url(base), timeout=12000)
            ok = True
        except Exception as e:
            ok, p = False, None
            check(f"f. {tag}: Jarvis opens from its saved copy", False, str(e)[:200])
        if ok:
            p.wait_for_timeout(900)
            txt = p.inner_text("body")
            check(f"f. {tag}: Jarvis opens from its saved copy", p.evaluate(JARVIS_HOME) and "Jarvis" in p.title(), p.title())
            check(f"f. {tag}: the Zenith card shows the last numbers it saw ($1,106)", "$1,106" in txt, txt[:300])
            not_white(p, f"Jarvis {tag}")
            for app, ready, label, light in APPS_IN_JARVIS:
                try:
                    if app == "zenith":
                        tap(p, "zenith")
                        f, _k = zenith_view(p, 8000)
                        good = f is not None
                        f = f or dash_frame(p, "zenith")
                    else:
                        open_app(p, app, None, timeout=15000)
                        f, good = frame_ready(p, app, ready, 8)
                    p.wait_for_timeout(300)
                    furl = getattr(f, "url", "") if f else ""
                    title = ""
                    try:
                        title = f.title() if f else ""     # a Frame or the page
                    except Exception:
                        pass
                    check(f"f. {tag}: {label} inside Jarvis opens from its saved copy", good, f"{furl} '{title}'")
                    check(f"f. {tag}: one dashboard view alive ({label})", frames_alive(p) <= 1, frames_alive(p))
                    not_white(p, f"{label} inside Jarvis {tag}", light_ok=light)
                except Exception as e:
                    check(f"f. {tag}: {label} inside Jarvis opens from its saved copy", False, str(e)[:200])
                try:
                    go_home(p)
                except Exception:
                    pass
            p.close()
            # Zenith on its own (its own Home Screen app)
            pz = ph.page()
            try:
                pz.goto(base, wait_until="commit", timeout=30000)
                good = False
                for _ in range(30):
                    try:
                        if pz.evaluate(ZENITH_READY):
                            good = True
                            break
                    except Exception:
                        pass
                    pz.wait_for_timeout(300)
                check(f"f. {tag}: Zenith on its own opens from its saved copy", good, pz.title())
                not_white(pz, f"Zenith alone {tag}")
            except Exception as e:
                check(f"f. {tag}: Zenith on its own opens from its saved copy", False, str(e)[:200])
            pz.close()
        # no saved copy at all (the copy was dropped, the worker is still there): a dark Retry page, never white
        if mode == "down":
            CTL.set("ok")
            pz = ph.page()
            pz.goto(jarvis_url(base))
            pz.wait_for_function(JARVIS_HOME)
            pz.evaluate("async () => { for (const k of await caches.keys()) if (k.startsWith('jarvis-')) await caches.delete(k); }")
            clear_http_cache(ph, pz)
            pz.close()
            CTL.set("down", BASE)
            pr = ph.page()
            try:
                pr.goto(jarvis_url(base), wait_until="load", timeout=30000)
                body = pr.inner_text("body")
                check("f. offline, no saved copy: the dark Retry page", "Retry" in body, body[:200])
                not_white(pr, "Jarvis offline no copy")
            except Exception as e:
                check("f. offline, no saved copy: the dark Retry page", False, str(e)[:200])
            pr.close()
    finally:
        CTL.set("ok")
    # back online: the saved copies are rebuilt on the next open
    p2 = ph.page()
    p2.goto(jarvis_url(base))
    p2.wait_for_function(JARVIS_HOME)
    p2.wait_for_timeout(500)
    p2.close()
    errs, bad = ph.since(m, allow=(r"net::ERR_", r"Failed to load resource", r"dropped", r"\b404\b", r"Failed to fetch",
                                    r"NetworkError", r"ERR_EMPTY_RESPONSE", r"ERR_CONNECTION"))
    pe = [e for e in errs if e[0] == "pageerror"]
    check(f"f. {tag}: no page errors (uncaught)", not pe, pe[:4])


def part_h(br, S, base):
    """A service-worker update: the published workers first, then this checkout's."""
    ph = Phone(br, "iPhone 13")
    ph.ctx.add_init_script(READY_INIT)
    W = S["workers"]
    try:
        m = ph.mark()
        CTL.set("ok", root=S["pub"])
        p = ph.page()
        p.goto(jarvis_url(base), wait_until="commit")
        wait_ready(p)
        open_zenith(p, 30000)
        open_app(p, "planner", PLANNER_READY, timeout=30000)
        go_home(p)
        ok, keys = wait_caches(p, [W["Jarvis"]["old"], W["Zenith"]["old"], W["Planner"]["old"]], timeout=20000)
        check("h. the published workers are installed (Jarvis, Zenith, Planner caches)", ok, keys)
        before = sw_state(p)
        note("published: caches " + ", ".join(before["caches"]) + "; workers "
             + ", ".join(f"{r['scope'].split(BASE)[-1] or '/'}={r['state']}" for r in before["regs"]))
        p.close()
        # the new site is published; ten minutes later the phone opens Jarvis again
        CTL.set("ok", root=S["new"])
        p = ph.page()
        clear_http_cache(ph, p)
        p.goto(jarvis_url(base), wait_until="commit")
        p.wait_for_function(JARVIS_HOME, timeout=15000)
        jw = W["Jarvis"]
        want = [jw["new"]]
        gone = [jw["old"]] if jw["old"] != jw["new"] else []
        ok, keys = wait_caches(p, want, gone, timeout=20000)
        check(f"h. a reopen of Jarvis installs its new worker ({jw['old']} -> {jw['new']}) and drops only its old cache", ok, keys)
        check("h. Jarvis's update leaves Zenith's and the Planner's saved copies alone (le-public-*, planner-*)",
              has_copy(p, "le-public-", "index.html") and has_copy(p, "planner-", "planner/index.html"), keys)
        newtxt = open(os.path.join(S["new"], REPO, "jarvis", "index.html"), encoding="utf-8").read()
        saved = cached_text(p, jw["new"], jarvis_url(base) + "index.html")
        check("h. Jarvis's new saved copy is the new page", saved == newtxt, (saved or "")[:80])
        p.close()
        p = ph.page()
        p.goto(jarvis_url(base), wait_until="commit")
        wait_ready(p)
        ctl = p.evaluate("navigator.serviceWorker.controller && navigator.serviceWorker.controller.scriptURL")
        check("h. the next open runs under Jarvis's new worker", bool(ctl) and ctl.endswith("/jarvis/sw.js"), ctl)
        ids_new = set(re.findall(r'\bid="([\w-]+)"', newtxt))
        ids_old = set(re.findall(r'\bid="([\w-]+)"', open(os.path.join(S["pub"], REPO, "jarvis", "index.html"), encoding="utf-8").read()))
        only_new = sorted(ids_new - ids_old)
        if only_new:
            check(f"h. the page shown is the new Jarvis (#{only_new[0]})", p.evaluate(f"!!document.getElementById({json.dumps(only_new[0])})"))
        not_white(p, "Jarvis after the update")
        # Zenith inside Jarvis: its worker updates too, and never deletes Jarvis's or the Planner's caches
        clear_http_cache(ph, p)
        zf, _ = open_zenith(p, 30000)
        zw = W["Zenith"]
        ok, keys = wait_caches(p, [zw["new"]], [zw["old"]] if zw["old"] != zw["new"] else [], timeout=20000)
        check(f"h. Zenith inside Jarvis installs its new worker ({zw['old']} -> {zw['new']})", ok, keys)
        check("h. Zenith's update leaves Jarvis's and the Planner's saved copies alone (jarvis-*, planner-*)",
              has_copy(p, "jarvis-", "jarvis/index.html") and has_copy(p, "planner-", "planner/index.html"), keys)
        not_white(p, "Zenith after the update")
        go_home(p)
        after = sw_state(p)
        scopes = sorted(r["scope"].split(BASE)[-1] or "/" for r in after["regs"])
        check("h. one worker per app (Zenith /, jarvis/, planner/), none stuck waiting",
              scopes == sorted(["/", "jarvis/", "planner/"]) and not any(r["waiting"] or r["installing"] for r in after["regs"]),
              after["regs"])
        note("after the update: caches " + ", ".join(after["caches"]))
        no_errors(ph, m, "the update")
        p.close()
        # offline after the update: the new copies answer
        CTL.set("down", BASE)
        try:
            p = reopen(ph, jarvis_url(base), timeout=12000)
            check("h. offline after the update: Jarvis opens", p.evaluate(JARVIS_HOME))
            f, _ = open_zenith(p, 8000)
            check("h. offline after the update: Zenith inside Jarvis opens", f is not None)
            not_white(p, "Zenith offline after the update")
            p.close()
        except Exception as e:
            check("h. offline after the update: Jarvis opens", False, str(e)[:200])
        finally:
            CTL.set("ok")
    finally:
        CTL.set("ok", root=S["new"])
        ph.close()


def guard(part, fn, *a):
    """A part that breaks (a selector gone, a page that never loads) is one FAIL, and the next part still runs."""
    try:
        return fn(*a)
    except Exception as e:
        CTL.set("ok", root=CTL.root)
        check(f"{part}. part {part} ran to the end", False, f"{e.__class__.__name__}: {str(e).splitlines()[0][:300]}")
        return None


def run_local(S):
    from playwright.sync_api import sync_playwright
    work = S["work"]
    cert, key = make_cert(work)
    CTL.root = S["new"]
    CTL.lazy = make_lazy(S)
    srv = TLSServer(("127.0.0.1", 0), Handler, cert, key)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"https://127.0.0.1:{port}{BASE}"
    rules = ", ".join([f"MAP {h} 127.0.0.1:{port}" for h in STUB_HOSTS] + ["MAP * ~NOTFOUND", "EXCLUDE 127.0.0.1"])
    only = set((ARGS.only or "a,b,c,d,e,f,g,h").split(","))
    t0 = time.time()
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=chrome_exe(), args=["--ignore-certificate-errors", "--no-proxy-server",
                                                                    f"--host-resolver-rules={rules}"])
        try:
            part_a(S)                                    # always: it also lists the missing Jarvis modules
            MISSING[:] = S.get("jarvis_missing") or []
            if "b" in only:
                guard("b", part_b, br, S, base)
            if only & {"c", "d", "e", "f", "g"}:
                ph = Phone(br, "iPhone 13")
                ph.ctx.add_init_script(READY_INIT)
                try:
                    p = guard("c", part_c, br, S, base, ph) if only & {"c", "d"} else None
                    if "d" in only and p:
                        guard("d", part_d, p, ph)
                    if "e" in only:
                        guard("e", part_e, br, S, base, ph)
                    if "f" in only:
                        guard("f", part_f, br, S, base, ph, "down")
                    if "g" in only:
                        guard("g", part_f, br, S, base, ph, "404")
                    if ph.ext:
                        note("outside hosts the pages tried (cut off): " + ", ".join(sorted(ph.ext)))
                finally:
                    ph.close()
            if "h" in only:
                guard("h", part_h, br, S, base)
        finally:
            br.close()
            srv.shutdown()
    if S.get("lazy"):
        note(f"fetched on demand: {', '.join(S['lazy'][:8])}")
    note(f"browser part: {time.time() - t0:.0f} s")


def run_live():
    """Read-only smoke test of the real published site (after a publish)."""
    from playwright.sync_api import sync_playwright
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    base = LIVE_SITE
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=chrome_exe(), args=["--ignore-certificate-errors"],
                                **({"proxy": {"server": proxy, "bypass": "127.0.0.1,localhost"}} if proxy else {}))
        ph = Phone(br, "iPhone 13")
        ph.ctx.add_init_script(READY_INIT)
        try:
            m = ph.mark()
            p = ph.page()
            p.goto(jarvis_url(base), wait_until="commit", timeout=60000)
            t = wait_ready(p, timeout=30000)
            note(f"live: Jarvis interactive in {t} ms (over the internet)")
            check("live. Jarvis opens on the Jarvis screen", p.evaluate(JARVIS_HOME))
            p.wait_for_timeout(2500)
            txt = p.inner_text("#home")
            check("live. the Zenith card has the bots' status (live feed answered)", "Loading the bots" not in txt and "Could not reach" not in txt, txt[:300])
            not_white(p, "live Jarvis home")
            w = hscroll(p)
            check("live. no sideways scroll", w[0] <= w[1], w)
            zf, kind = open_zenith(p, 60000)
            check("live. Zenith opens inside Jarvis", bool(zf), kind)
            not_white(p, "live Zenith inside Jarvis")
            pf = open_app(p, "planner", PLANNER_READY, timeout=60000)
            check("live. the Planner opens inside Jarvis", bool(pf) and frames_alive(p) == 1)
            not_white(p, "live Planner inside Jarvis", light_ok=True)
            kf = open_app(p, "kalshi", KALSHI_READY, timeout=60000)
            check("live. Kalshi opens inside Jarvis", bool(kf) and frames_alive(p) == 1)
            not_white(p, "live Kalshi inside Jarvis")
            go_home(p)
            a = ask(p, "How are the bots?")
            check("live. Jarvis answers 'How are the bots?'", len(a) > 10 and "Still loading" not in a, a[:200])
            st = sw_state(p)
            note("live workers: " + ", ".join(f"{r['scope'].split(BASE)[-1] or '/'}={r['state']}" for r in st["regs"])
                 + "; caches " + ", ".join(st["caches"]))
            check("live. Jarvis's worker is active", any(r["scope"].endswith("/jarvis/") and r["state"] == "activated" for r in st["regs"]), st["regs"])
            errs, bad = ph.since(m)
            check("live. no page errors", not [e for e in errs if e[0] == "pageerror"], errs[:4])
            note(f"live console errors: {errs[:4]}" if errs else "live: no console errors")
        finally:
            ph.close()
            br.close()


def main(argv=None):
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default=ROOT, help="the checkout whose tools/web_public is laid over the published site")
    ap.add_argument("--live", action="store_true", help="read-only smoke test of the real published site")
    ap.add_argument("--only", default="", help="parts to run, e.g. b,c,d (a-h)")
    ap.add_argument("--keep", action="store_true", help="keep the temp site and the screenshots")
    ap.add_argument("--shots", default="", help="folder for the screenshots (default: a temp folder, kept with --keep)")
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "le_phone_e2e_cache"), help="where the clone is kept")
    ap.add_argument("--no-refresh", dest="refresh", action="store_false", help="reuse the cached clone without fetching")
    ap.add_argument("--strict", action="store_true", help="known open bugs count as failures")
    ARGS = ap.parse_args(argv)
    ARGS.src = os.path.abspath(ARGS.src)
    t0 = time.time()
    work = tempfile.mkdtemp(prefix="le_phone_e2e_")
    SHOTS["dir"] = ARGS.shots or os.path.join(work, "shots")
    os.makedirs(SHOTS["dir"], exist_ok=True)
    try:
        if ARGS.live:
            run_live()
        else:
            if not os.path.isdir(os.path.join(ARGS.src, "tools", "web_public")):
                print(f"--src {ARGS.src}: no tools/web_public")
                return 2
            S = build_sites(work)
            S["work"] = work
            run_local(S)
    finally:
        if ARGS.keep or ARGS.shots:
            print(f"screenshots: {SHOTS['dir']}" + (f"  site: {work}" if ARGS.keep else ""))
        if not ARGS.keep:
            shutil.rmtree(work, ignore_errors=True) if not ARGS.shots else shutil.rmtree(os.path.join(work, "pub"), ignore_errors=True)
    fails = [n for n, ok, known in RES if not ok and not known]
    known = [n for n, ok, k in RES if not ok and k]
    n = sum(1 for _, ok, _ in RES if ok)
    print(f"\nphone e2e: {n}/{len(RES)} pass" + (f", {len(known)} known open bugs" if known else "") + (f", {len(fails)} FAILED" if fails else "")
          + f" ({time.time() - t0:.0f} s)" + ("  ALL PASS" if not fails and not known else ""))
    return 1 if fails else 0


ARGS = None

if __name__ == "__main__":
    sys.exit(main())
