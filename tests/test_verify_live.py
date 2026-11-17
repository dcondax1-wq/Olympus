"""tools/verify_live.py against a LOCAL http.server over a fixture site (no network): a good deploy is VERIFIED; a stale worker, a 404 app, a stale card, a wrong
icon size, bad JSON, a silent or unarmed bot heartbeat and a missing kit tag are each caught and named; weekend and outside-hours rules; a missing manifest is only
a warning; a flaky 500 is retried; at most 4 requests at once; the report file is the one table + the verdict line; the tool never writes anywhere else.
    python -X utf8 -m tests.test_verify_live
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import verify_live as V  # noqa: E402

RES = []
NY = ZoneInfo("America/New_York")
WED = datetime(2026, 11, 4, 14, 0, tzinfo=NY).timestamp()          # a weekday, market hours
SAT = datetime(2026, 11, 7, 14, 0, tzinfo=NY).timestamp()
NIGHT = datetime(2026, 11, 4, 22, 0, tzinfo=NY).timestamp()


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def png(n):
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * n for _ in range(n))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")


def w(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:
        fh.write(data)


APPS = [{"id": "zenith", "path": "", "live": False}, {"id": "alpha", "path": "alpha/", "live": True}, {"id": "beta", "path": "beta/", "live": False}, {"id": "gamma", "path": "gamma/", "live": True}]
PAGE = ('<!doctype html><html><head><meta name="viewport" content="width=device-width, viewport-fit=cover"><link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="touch.png"><link rel="stylesheet" href="../olympus/olympus.css?v=o7"><script src="../olympus/olympus.js?v=o9" data-app="{id}"></script></head><body>{id}</body></html>')
MAN = {"name": "x", "short_name": "x", "start_url": "./", "scope": "./", "display": "standalone", "icons": [{"src": "i192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                                                                                                          {"src": "i512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}


def build(tmp, now=WED):
    """repo/ (what the build should publish) and site/ (what the server serves): identical at first."""
    repo, site = os.path.join(tmp, "repo"), os.path.join(tmp, "site")
    wp = os.path.join(repo, "tools", "web_public")
    w(os.path.join(wp, "olympus", "apps-list.js"), "/* generated */\nwindow.OLYMPUS_APPS_LIST = " + json.dumps(APPS) + ";\n")
    for a in APPS:
        pg = PAGE.format(id=a["id"])
        if a["id"] == "gamma":                                           # an app that has no manifest and no touch icon link at all (a home-screen gap)
            pg = pg.replace('<link rel="manifest" href="manifest.webmanifest">', "").replace('<link rel="apple-touch-icon" href="touch.png">', "")
        w(os.path.join(wp, a["path"], "index.html"), pg)
    w(os.path.join(wp, "sw.js"), "const CACHE = 'le-public-v60';\n")
    w(os.path.join(wp, "jarvis", "sw.js"), "const CACHE = 'jarvis-v24';\n")
    w(os.path.join(wp, "kalshi", "sw.js"), "const CACHE = 'kalshi-k18';\n")
    shutil.copytree(wp, site)
    os.remove(os.path.join(site, "olympus", "apps-list.js"))
    for a in APPS:
        d = os.path.join(site, a["path"])
        if a["id"] != "gamma":                                           # gamma has no manifest and no touch icon: a home-screen gap, a warning only
            w(os.path.join(d, "manifest.webmanifest"), json.dumps(MAN))
            w(os.path.join(d, "touch.png"), png(180)); w(os.path.join(d, "i192.png"), png(192)); w(os.path.join(d, "i512.png"), png(512))
        if a["live"]:
            w(os.path.join(d, "jarvis.json"), json.dumps({"v": 1, "name": a["id"], "t": int(now - 3600)}))
    for rel in V.DATA_FILES:
        w(os.path.join(site, rel), json.dumps({"ok": True, "n": [1, 2, 3]}))
    w(os.path.join(site, "hb", "heartbeat.json"), json.dumps({"t": int(now - 120), "running": True, "health": {"account": {"armed": True}}, "kill": False}))
    return repo, site


class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json", ".json": "application/json"}
    flaky, live, peak, lock, hits = set(), 0, 0, threading.Lock(), []

    def log_message(self, *a):
        pass

    def do_GET(self):
        cls = type(self)
        with cls.lock:
            cls.live += 1
            cls.peak = max(cls.peak, cls.live)
            cls.hits.append(self.path)
        try:
            time.sleep(0.01)
            if self.path in cls.flaky:
                cls.flaky.discard(self.path)
                self.send_error(500)
                return
            super().do_GET()
        finally:
            with cls.lock:
                cls.live -= 1


def serve(site):
    H.flaky, H.live, H.peak, H.hits = set(), 0, 0, []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def go(repo, base, now=WED, **kw):
    net = V.Net(timeout=5, sleep=lambda s: None)
    return V.run(base, repo=repo, hb_url=base + "hb/heartbeat.json", now=now, net=net, **kw)


def row(rows, name):
    return next(r for r in rows if r[0] == name)


def main():
    tmp = tempfile.mkdtemp(prefix="le_vl_")
    try:
        repo, site = build(tmp)
        srv, base = serve(site)
        rows, v = go(repo, base)
        gamma_ok = row(rows, "app gamma")
        check("a good deploy: every app page, manifest, icons, cards, workers, data files and the heartbeat pass (the fixture's gamma has no manifest: a warning only)",
              v == "VERIFIED" and all(r[1] in ("PASS", "WARN") for r in rows) and row(rows, "app alpha")[1] == "PASS" and gamma_ok[1] == "WARN" and "home-screen gap" in gamma_ok[2], [r for r in rows if r[1] != "PASS"])
        check("the rows are dynamic: one per app of apps-list.js (4), 3 workers + the optional PC worker, every data file, the heartbeat", sum(r[0].startswith("app ") for r in rows) == 4
              and sum(r[0].startswith("data ") for r in rows) == len(V.DATA_FILES) and row(rows, "bot heartbeat") and row(rows, "PC dashboard worker")[1] in ("PASS", "WARN"), [r[0] for r in rows])
        check("polite: never more than 4 requests at once, and each file is fetched once per run", H.peak <= 4 and len(H.hits) == len(set(H.hits)), (H.peak, len(H.hits), len(set(H.hits))))
        srv.shutdown()

        # ---- stale worker + a 404 app + a stale card + a wrong icon size + a missing kit tag + bad JSON
        repo, site = build(tmp + "/c2")
        w(os.path.join(site, "jarvis", "sw.js"), "const CACHE = 'jarvis-v23';\n")
        shutil.rmtree(os.path.join(site, "gamma"))
        w(os.path.join(site, "alpha", "jarvis.json"), json.dumps({"v": 1, "t": int(WED - 40 * 3600)}))
        w(os.path.join(site, "beta", "i192.png"), png(180))
        w(os.path.join(site, "beta", "index.html"), PAGE.format(id="beta").replace("olympus.js?v=o9", "olympus.js?v=o1"))
        w(os.path.join(site, "home.json"), "{not json")
        srv, base = serve(site)
        rows, v = go(repo, base)
        wk, g, al, be, hj = row(rows, "Jarvis worker"), row(rows, "app gamma"), row(rows, "app alpha"), row(rows, "app beta"), row(rows, "data home.json")
        check("a stale worker is caught and named: live jarvis-v23 against the repo's jarvis-v24 = STALE DEPLOY (the other workers pass)", wk[1] == "FAIL" and "STALE DEPLOY" in wk[2] and "jarvis-v23" in wk[2] and "jarvis-v24" in wk[2]
              and row(rows, "root worker")[1] == "PASS", wk)
        check("a 404 app is a problem with the status code in the detail", g[1] == "FAIL" and "404" in g[2], g)
        check("a card older than 30 h fails (40 h old); an icon whose real PNG size differs from the manifest fails; a kit tag the repo has but the live page lacks fails",
              al[1] == "FAIL" and "40.0 h old" in al[2] and be[1] == "FAIL" and "manifest says 192x192" in be[2] and "olympus.js?v=o9" in be[2], (al, be))
        check("a data file that is not valid JSON fails", hj[1] == "FAIL" and "not valid JSON" in hj[2], hj)
        check("one problem makes the whole run PROBLEMS (exit code 1)", v == "PROBLEMS" and V.main(["--base", base, "--repo", repo, "--hb-url", base + "hb/heartbeat.json", "--no-write"]) == 1)
        srv.shutdown()

        # ---- weekend allowance, a card's own stale_after, the heartbeat rules
        repo, site = build(tmp + "/c3", now=SAT)
        w(os.path.join(site, "alpha", "jarvis.json"), json.dumps({"v": 1, "t": int(SAT - 40 * 3600)}))
        srv, base = serve(site)
        rows, v = go(repo, base, now=SAT)
        check("weekend-aware: a 40 h old card passes on a Saturday (allowance 72 h) and the heartbeat is not required fresh", row(rows, "app alpha")[1] == "PASS" and v == "VERIFIED", row(rows, "app alpha"))
        w(os.path.join(site, "alpha", "jarvis.json"), json.dumps({"v": 1, "t": int(WED - 40 * 3600), "stale_after": 259200}))
        net = V.Net(timeout=5, sleep=lambda s: None)
        check("a card that sets its own stale_after (72 h) is judged by it, on a weekday too", V.check_app(net, base, repo, APPS[1], WED, 30.0)[0] == "PASS")
        srv.shutdown()
        for label, hb, now, want in (("silent 30 min in market hours", {"t": int(WED - 1800), "running": True, "health": {"account": {"armed": True}}}, WED, "FAIL"),
                                     ("running but NOT armed in market hours", {"t": int(WED - 60), "running": True, "health": {"account": {"armed": False}}}, WED, "FAIL"),
                                     ("not running in market hours", {"t": int(WED - 60), "running": False, "health": {"account": {"armed": True}}}, WED, "FAIL"),
                                     ("kill switch on", {"t": int(WED - 60), "running": True, "kill": True, "health": {"account": {"armed": True}}}, WED, "FAIL"),
                                     ("armed only in launch.facts (older shape) and fresh", {"t": int(WED - 60), "running": True, "launch": {"facts": {"lit_armed": True}}}, WED, "PASS"),
                                     ("30 min old at 22:00 ET (the PC is allowed to sleep)", {"t": int(NIGHT - 1800), "running": True, "health": {"account": {"armed": True}}}, NIGHT, "PASS"),
                                     ("not the expected JSON", {"x": 1}, WED, "FAIL")):
            repo, site = build(tmp + "/hb")
            w(os.path.join(site, "hb", "heartbeat.json"), json.dumps(hb))
            srv, base = serve(site)
            r = V.check_heartbeat(V.Net(timeout=5, sleep=lambda s: None), base + "hb/heartbeat.json", now, 10.0)
            check(f"heartbeat: {label} -> {want}", r[0] == want, r)
            srv.shutdown()
            shutil.rmtree(tmp + "/hb")

        # ---- retries, a dead server, the report
        repo, site = build(tmp + "/c5")
        srv, base = serve(site)
        H.flaky = {"/alpha/manifest.webmanifest"}
        rows, v = go(repo, base)
        check("a flaky 500 on one file is retried (twice at most) and the check passes", row(rows, "app alpha")[1] == "PASS" and "/alpha/manifest.webmanifest" not in H.flaky, row(rows, "app alpha"))
        out = os.path.join(tmp, "out", "verify_live.md")
        rc = V.main(["--base", base, "--repo", repo, "--hb-url", base + "hb/heartbeat.json", "--out", out])
        txt = open(out, encoding="utf-8").read()
        check("the report file has ONE table (| check | result | detail |) and ends with the VERIFIED / PROBLEMS line; exit code 0", rc == 0 and txt.count("| check | result | detail |") == 1 and "VERIFIED: " in txt.strip().splitlines()[-1], txt[-200:])
        srv.shutdown()
        t0 = time.time()
        net = V.Net(timeout=2, sleep=lambda s: None)
        st = net.get("http://127.0.0.1:9/x")
        check("an unreachable server is a clean failure (status 0 + the reason), not a crash", st[0] == 0 and st[3] != "" and time.time() - t0 < 30, st)
        src = open(os.path.join(ROOT, "tools", "verify_live.py"), encoding="utf-8").read()
        check("read only: GET only (no POST / PUT / DELETE, no data= body), no key or token is read", "method=" not in src and "data=" not in src and "token" not in src.lower().replace("tokens", ""), None)
        check("the repo's own olympus/apps-list.js drives the real tool (30+ apps) and the real repo has the cache names it compares",
              len(V.apps_list(ROOT)) >= 25 and all(V.tag(V.read(ROOT, rel), rx) for _, rel, _, rx in V.WORKERS + [V.PC_WORKER] if os.path.isfile(os.path.join(ROOT, rel))), None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nverify_live: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
