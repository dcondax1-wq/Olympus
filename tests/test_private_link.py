"""PRIVATE LINK (team Q2 "privacy and security audit", 2026-11-14): the PC's private data reaches only the PC itself and the owner's
Tailscale link, never another device on the home WiFi. docs/PRIVACY.md. The bot server listens on 0.0.0.0:8766 (server.py HOST), and
engine/live_site.guard only looks at PROXIED requests, so before this a phone / laptop / TV on the same WiFi could read
http://<pc>:8766/site/day/day.json (calendars, shifts), /site/money/household.json (bank exports), agency.json (clients' money) and
post to /inbox/day. engine/live_site.private_why() is the one rule; day_inbox and the money inbox server follow it.

  a. rule      private_why: the PC itself (loopback, no proxy header, Host localhost) and tailscale serve (a tailnet X-Forwarded-For, a
               signed-in Tailscale-User-Login, Host <pc>.<tailnet>.ts.net; with uvicorn's own proxy-header rewrite or without) pass;
               the WiFi, the WiFi with forged headers, DNS rebinding (Host evil), Funnel, the internet, another tunnel, no login refused
  b. routes    a real FastAPI app (live_site + day_inbox): day.json / inbox.json / household / agency / the real money_out files for
               the PC and the link; 403 (or the public sample copy) for the WiFi; a public page still works on the WiFi
  c. paths     traversal (.., %2e%2e, backslashes, NUL, case, an absolute path) never reaches money_out / data/day / a file outside
  d. inbox     POST /inbox/<kind>: the WiFi refused, Funnel refused, oversize refused from its Content-Length (and never read past
               2 KB), malformed / deep JSON 400, unknown kind 404, no header 403, 30 per 10 minutes then 429, over the real route
  e. money     tools/money_inbox_server.py: a DNS-rebinding Host refused, the Tailscale name allowed, a stalled client dropped (15 s),
               it only ever listens on 127.0.0.1
  f. server    (skipped with --fast) the real server.py in a child process, called as a WiFi device: every private route 403, the
               inbox POST 403, start / stop / kill still answer only as before (the bot API is not changed here: see docs/PRIVACY.md)

  python -X utf8 -m tests.test_private_link [--fast]
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import day_inbox as DI  # noqa: E402
from engine import live_site as LS  # noqa: E402

RES: list = []
FAST = "--fast" in sys.argv
PC = {"client": ("127.0.0.1", 50000), "base_url": "http://localhost:8766"}
WIFI = {"client": ("192.168.1.50", 50000), "base_url": "http://192.168.1.20:8766"}
TS_HOST = "olympus-pc.tail1234.ts.net"
LINK_H = {"X-Forwarded-For": "100.101.102.103", "X-Forwarded-Proto": "https", "X-Forwarded-Host": TS_HOST, "Tailscale-User-Login": "owner@example.com"}
LINK = {"client": ("100.101.102.103", 0), "base_url": "https://" + TS_HOST}          # uvicorn reports the tailnet address (proxy headers)
LINK_RAW = {"client": ("127.0.0.1", 50001), "base_url": "https://" + TS_HOST}        # without uvicorn's rewrite: tailscaled's loopback


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""), flush=True)
    return bool(cond)


# ------------------------------------------------------------------------------------------------ a. the rule
def rule():
    W = LS.private_why
    th = {k.lower(): v for k, v in LINK_H.items()}
    ok = [W("127.0.0.1", {"host": "localhost:8766"}), W("::1", {"host": "[::1]:8766"}), W("127.0.0.1", {"host": "127.0.0.1:8766"}),
          W("100.101.102.103", {**th, "host": TS_HOST}), W("127.0.0.1", {**th, "host": TS_HOST}),
          W("100.101.102.103", {**th, "x-forwarded-for": "fd7a:115c:a1e0::53", "host": TS_HOST}), W("127.0.0.1", {**th, "host": "localhost:8766"})]
    check("a. allowed: the PC itself (localhost / 127.0.0.1 / ::1) and the Tailscale link (with and without uvicorn's rewrite, IPv6 tailnet)",
          ok == [None] * len(ok), ok)
    bad = {
        "the WiFi": W("192.168.1.50", {"host": "192.168.1.20:8766"}),
        "the WiFi, forged Tailscale headers": W("192.168.1.50", {**th, "host": TS_HOST}),
        "the WiFi, forged loopback XFF": W("192.168.1.50", {"x-forwarded-for": "127.0.0.1", "host": "localhost"}),
        "a tailnet device straight to :8766 (no serve)": W("100.101.102.103", {"host": "100.70.0.1:8766"}),
        "DNS rebinding (Host evil)": W("127.0.0.1", {"host": "evil.example:8766"}),
        "DNS rebinding with forged link headers": W("127.0.0.1", {**th, "host": "evil.example:8766"}),
        "Funnel": W("127.0.0.1", {**th, "tailscale-funnel-request": "?1", "host": TS_HOST}),
        "the internet through serve": W("127.0.0.1", {**th, "x-forwarded-for": "8.8.8.8", "host": TS_HOST}),
        "a mixed forward chain": W("127.0.0.1", {**th, "x-forwarded-for": "8.8.8.8, 100.101.102.103", "host": TS_HOST}),
        "no signed-in Tailscale user": W("127.0.0.1", {"x-forwarded-for": "100.101.102.103", "host": TS_HOST}),
        "another tunnel (Cloudflare)": W("127.0.0.1", {**th, "cf-connecting-ip": "8.8.8.8", "host": TS_HOST}),
        "no client address": W("", {"host": "localhost"}),
    }
    check("a. refused: the WiFi (also with forged headers), a direct tailnet hit, DNS rebinding, Funnel, the internet, a mixed chain, no login, another tunnel",
          all(isinstance(v, str) and v.startswith("private:") for v in bad.values()), {k: v for k, v in bad.items() if not v})
    check("a. the reason is plain words (what to do instead)", "Tailscale" in bad["the WiFi"] and "localhost:8766" in bad["the WiFi"], bad["the WiFi"])


# ------------------------------------------------------------------------------------------------ b. the routes
class Box:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="privlink-")
        self.site = os.path.join(self.dir, "site")
        self.money = os.path.join(self.dir, "money_out")
        self.day = os.path.join(self.dir, "day")
        self.inbox = os.path.join(self.dir, "inbox")
        for d in (os.path.join(self.site, "money"), os.path.join(self.site, "gate"), self.money, self.day, self.inbox):
            os.makedirs(d, exist_ok=True)
        self.w(self.site, "index.html", "<!doctype html>")
        self.w(self.site, "gate/index.html", "<!doctype html><title>Gate</title>")
        self.w(self.site, "money/index.json", json.dumps({"kind": "sample"}))
        self.w(self.site, "money/oikos.json", json.dumps({"kind": "sample"}))
        self.w(self.money, "index.json", json.dumps({"kind": "real"}))
        self.w(self.money, "oikos.json", json.dumps({"kind": "real", "ledger": {"entries": [{"cat": "rent", "usd": -1450}]}}))
        self.w(self.money, "household.json", json.dumps({"kind": "olympus-household", "month": {"out": 3100}}))
        self.w(self.money, "agency.json", json.dumps({"kind": "agency", "mrr": 900}))
        self.w(self.day, "day.json", json.dumps({"kind": "olympus-day", "today": "2026-11-16", "shifts": [{"start": "09:00"}]}))
        self.w(self.day, "inbox.json", json.dumps({"kind": "olympus-inbox", "items": [{"text": "Call the bank"}]}))
        self.old = {k: os.environ.get(k) for k in ("LE_SITE_DIR", "LE_DAY_DIR", "LE_INBOX_DIR")}
        os.environ.update(LE_SITE_DIR=self.site, LE_DAY_DIR=self.day, LE_INBOX_DIR=self.inbox)
        self.old_money = LS.MONEY_OUT
        LS.MONEY_OUT = self.money
        LS.POST_ALLOW.clear()
        DI._S["installed"] = False
        DI._HITS.clear()
        self.app = FastAPI()
        LS.install(self.app, kalshi_cfg={})

        @self.app.post("/api/live/stop")
        def _stop():
            return {"stopped": True}
        DI.install(self.app)

    @staticmethod
    def w(base, rel, text):
        p = os.path.join(base, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def c(self, who):
        return TestClient(self.app, follow_redirects=False, **who)

    def close(self):
        LS.MONEY_OUT = self.old_money
        LS.POST_ALLOW.clear()
        DI._S["installed"] = False
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


PRIVATE = ("/site/day/day.json", "/site/day/inbox.json", "/site/money/household.json", "/site/money/agency.json")


def routes(b: Box):
    pc, link, raw, wifi = b.c(PC), b.c(LINK), b.c(LINK_RAW), b.c(WIFI)
    for name, cl, h in (("the PC itself", pc, {}), ("the Tailscale link", link, LINK_H), ("the Tailscale link (no uvicorn rewrite)", raw, LINK_H)):
        got = {p: cl.get(p, headers=h) for p in PRIVATE}
        check(f"b. {name}: day.json, inbox.json, household.json, agency.json are served (200, no-store)",
              all(r.status_code == 200 and r.headers.get("cache-control") == "no-store" for r in got.values()),
              {p: (r.status_code, r.headers.get("cache-control")) for p, r in got.items()})
        m = cl.get("/site/money/oikos.json", headers=h)
        check(f"b. {name}: the real money_out/oikos.json (built from the bank exports) is the one served", m.json().get("kind") == "real", m.text)
    got = {p: wifi.get(p) for p in PRIVATE}
    check("b. the WiFi: every private file is 403 with a plain reason", all(r.status_code == 403 and "private" in r.json()["error"] for r in got.values()),
          {p: r.status_code for p, r in got.items()})
    check("b. the WiFi: nothing private in the refusals (no shift, no amount)", not any(x in r.text for r in got.values() for x in ("09:00", "3100", "900", "bank")))
    m, i = wifi.get("/site/money/oikos.json"), wifi.get("/site/money/index.json")
    check("b. the WiFi: the money pages get the build's public sample copy (like Netlify), never money_out", m.json() == {"kind": "sample"} and i.json() == {"kind": "sample"}
          and m.headers.get("x-olympus-source") != "money_out", (m.text, i.text))
    forged = {p: wifi.get(p, headers={**LINK_H, "Host": TS_HOST}).status_code for p in PRIVATE}
    check("b. the WiFi with forged Tailscale headers: still 403", set(forged.values()) == {403}, forged)
    reb = pc.get("/site/day/day.json", headers={"Host": "evil.example:8766"})
    check("b. DNS rebinding (a web page that renamed itself to 127.0.0.1): 403", reb.status_code == 403, reb.status_code)
    fun = raw.get("/site/money/household.json", headers={**LINK_H, "Tailscale-Funnel-Request": "?1"})
    check("b. a Funnel (internet) request: 403", fun.status_code == 403, fun.status_code)
    unk = wifi.get("/site/day/calendars.json")
    check("b. the WiFi cannot even learn which day files exist (403 before 404)", unk.status_code == 403, unk.status_code)
    g = wifi.get("/site/gate/")
    check("b. a public page still opens on the WiFi (the same as the Netlify site)", g.status_code == 200 and "Gate" in g.text, g.status_code)


# ------------------------------------------------------------------------------------------------ c. paths
def paths(b: Box):
    pc, wifi = b.c(PC), b.c(WIFI)
    trav = ["/site/day/%2e%2e/money/household.json", "/site/money/..%2fhousehold.json", "/site/%2e%2e/data/day/day.json",
            "/site/money/%2e%2e%2f%2e%2e%2fmoney_out%2fhousehold.json", "/site/day/..%5c..%5cmoney_out%5chousehold.json",
            "/site/money/household.json%00.png", "/site//" + b.money.lstrip("/") + "/household.json", "/site/%2e%2e/money_out/agency.json"]
    alias = ["/site/DAY/day.json", "/site/Money/Household.json", "/site/./day/day.json", "/site/money/./household.json", "/site/day//day.json"]
    priv = ("3100", "olympus-household", "09:00", "olympus-day", '"mrr"')
    leaks = []
    for who, cl in (("pc", pc), ("wifi", wifi)):
        for t in trav + (alias if who == "wifi" else []):
            r = cl.get(t)
            if r.status_code == 200 and (any(x in r.text for x in priv) or '"real"' in r.text):
                leaks.append((who, t, r.status_code))
    check("c. traversal (.., %2e%2e, %2f, backslash, NUL, a doubled slash to an absolute path) serves no private file to anyone; other case, ./ and //"
          " give the WiFi nothing private", not leaks, leaks)
    check("c. live_site.money_file / day_file accept only exact known names", LS.money_file("../household.json", b.money) is None
          and LS.money_file("household.json/x", b.money) is None and LS.day_file("../day.json", {"LE_DAY_DIR": b.day}) is None
          and LS.day_file("calendars.json", {"LE_DAY_DIR": b.day}) is None)


# ------------------------------------------------------------------------------------------------ d. the inbox
def inbox(b: Box):
    pc, link, wifi = b.c(PC), b.c(LINK), b.c(WIFI)
    H = {**LINK_H, "X-Olympus-Inbox": "1"}
    DI._HITS.clear()
    r_link = link.post("/inbox/day", json={"text": "From the Shortcut"}, headers=H)
    r_pc = pc.post("/inbox/day", json={"text": "From the PC"}, headers={"X-Olympus-Inbox": "1"})
    r_wifi = wifi.post("/inbox/day", json={"text": "From a guest"}, headers={"X-Olympus-Inbox": "1"})
    r_forged = wifi.post("/inbox/day", json={"text": "Forged"}, headers={**H, "Host": TS_HOST})
    lines = open(os.path.join(b.inbox, "day.jsonl"), encoding="utf-8").read()
    check("d. the link and the PC may add to the day (200); the WiFi, also with forged headers, may not (403) and nothing of theirs is written",
          (r_link.status_code, r_pc.status_code, r_wifi.status_code, r_forged.status_code) == (200, 200, 403, 403) and "guest" not in lines and "Forged" not in lines,
          (r_link.status_code, r_pc.status_code, r_wifi.status_code, r_forged.status_code))
    fun = link.post("/inbox/day", json={"text": "x"}, headers={**H, "Tailscale-Funnel-Request": "?1"})
    nohdr = link.post("/inbox/day", json={"text": "x"}, headers=LINK_H)
    over = [link.post(p, json={"text": "buy 10 NQ"}, headers=H).status_code for p in ("/inbox/trading", "/inbox/DAY", "/inbox/%2e%2e", "/api/live/stop")]
    on_pc = [pc.post(p, json={"text": "x"}, headers={"X-Olympus-Inbox": "1"}).status_code for p in ("/inbox/trading", "/inbox/DAY", "/inbox/%2e%2e")]
    check("d. refused: Funnel 403, no X-Olympus-Inbox header 403; over the link an unknown kind (trading, DAY, ..) or any other POST is 403 (the read-only"
          " guard), on the PC an unknown kind is 404", (fun.status_code, nohdr.status_code) == (403, 403) and over == [403] * 4 and on_pc == [404] * 3,
          (fun.status_code, nohdr.status_code, over, on_pc))
    big = link.post("/inbox/day", content=b"x" * 3000, headers={**H, "Content-Type": "text/plain"})
    t0 = time.time()
    huge = link.post("/inbox/day", content=b"{" + b"x" * (8 * 1024 * 1024), headers={**H, "Content-Type": "application/json"})
    took = time.time() - t0
    check("d. over 2 KB: 413 (8 MB too, refused from its Content-Length)", big.status_code == 413 and huge.status_code == 413 and took < 10, (big.status_code, huge.status_code, round(took, 1)))
    src = open(DI.__file__, encoding="utf-8").read()
    check("d. the route never calls request.body() (reads at most 2 KB from the stream)", "await request.body()" not in src and "request.stream()" in src)
    bad = [link.post("/inbox/day", content=b"{not json", headers={**H, "Content-Type": "application/json"}).status_code,
           link.post("/inbox/day", content=b"[" * 2000, headers={**H, "Content-Type": "application/json"}).status_code,
           link.post("/inbox/day", content=(b"[" * 1000 + b"]" * 1000), headers={**H, "Content-Type": "application/json"}).status_code,
           link.post("/inbox/day", json={"text": "   "}, headers=H).status_code,
           link.post("/inbox/day", content=b"\xff\xfe\x00", headers={**H, "Content-Type": "text/plain"}).status_code]
    check("d. malformed: broken JSON, unclosed deep JSON, deep valid JSON (not an object), empty text, bad bytes -> 400 (never a 500)",
          bad[:4] == [400, 400, 400, 400] and bad[4] in (200, 400), bad)
    DI._HITS.clear()
    codes = [link.post("/inbox/day", content=b"spam %d" % i, headers={**H, "Content-Type": "text/plain"}).status_code for i in range(31)]
    check("d. the rate limit holds over the real route: 30 in 10 minutes, then 429", codes[:30] == [200] * 30 and codes[30] == 429, codes[-3:])
    DI._HITS.clear()


# ------------------------------------------------------------------------------------------------ e. the money inbox server
def money_server():
    from tools import money_inbox_server as IB
    tmp = tempfile.mkdtemp(prefix="privmoney-")
    try:
        srv = IB.serve(os.path.join(tmp, "home"), 0)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        def post(headers):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            body = json.dumps({"amount": 5, "what": "x"}).encode()
            c.request("POST", "/inbox", body=body, headers={"Content-Type": "application/json", "Content-Length": str(len(body)), **headers})
            r = c.getresponse()
            r.read()
            c.close()
            return r.status
        TS = {"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "owner@example.com"}
        st = [post({}), post({"Host": "evil.example:%d" % port}), post({**TS, "Host": TS_HOST + ":8443"}), post({**TS, "Host": "evil.example"})]
        check("e. money inbox: the PC (127.0.0.1) 200, DNS rebinding (Host evil) 403, the Tailscale name 200, forged headers + Host evil 403",
              st == [200, 403, 200, 403], st)
        H = IB.make_handler(IB.Inbox(os.path.join(tmp, "home")))
        check("e. money inbox: a client that stalls is dropped after 15 s (the handler's socket timeout)", getattr(H, "timeout", None) == 15)
        try:
            IB.serve(os.path.join(tmp, "home"), 0, host="0.0.0.0")
            ok = False
        except SystemExit:
            ok = True
        check("e. money inbox: it refuses to listen on anything but 127.0.0.1 (the WiFi cannot reach it at all)", ok)
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ f. the real server.py
CHILD = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["LE_PREWARM"] = "0"
import server
from fastapi.testclient import TestClient
wifi = TestClient(server.app, follow_redirects=False, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8766")
pc = TestClient(server.app, follow_redirects=False, client=("127.0.0.1", 50000), base_url="http://localhost:8766")
out = {}
out["wifi_private"] = [wifi.get(p).status_code for p in ("/site/day/day.json", "/site/day/inbox.json", "/site/money/household.json", "/site/money/agency.json")]
out["wifi_inbox"] = wifi.post("/inbox/day", json={"text": "guest"}, headers={"X-Olympus-Inbox": "1"}).status_code
out["pc_day"] = pc.get("/site/day/day.json").status_code
out["wifi_gate"] = wifi.get("/site/gate/").status_code
print("RESULT " + json.dumps(out))
"""


def real_server():
    tmp = tempfile.mkdtemp(prefix="privsrv-")
    try:
        env = {**os.environ, "LE_PREWARM": "0", "LE_SITE_DIR": os.path.join(tmp, "no-site"), "LE_DAY_DIR": os.path.join(tmp, "day"),
               "LE_INBOX_DIR": os.path.join(tmp, "inbox")}
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD], cwd=ROOT, capture_output=True, text=True, timeout=600, env=env)
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if not check("f. the real server.py loads with the private rule (child process)", line is not None, (r.stdout[-400:], r.stderr[-800:])):
            return
        o = json.loads(line[7:])
        check("f. real server, called from the WiFi: day.json, inbox.json, household.json, agency.json all 403; the inbox POST 403",
              o["wifi_private"] == [403] * 4 and o["wifi_inbox"] == 403, o)
        check("f. real server: the PC itself gets the plain 404 (no calendar yet), a public page opens on the WiFi", o["pc_day"] == 404 and o["wifi_gate"] in (200, 307), o)
        check("f. nothing was written by the WiFi's inbox POST", not os.path.exists(os.path.join(tmp, "inbox", "day.jsonl")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def static():
    src = open(os.path.join(ROOT, "engine", "live_site.py"), encoding="utf-8").read()
    di = open(os.path.join(ROOT, "engine", "day_inbox.py"), encoding="utf-8").read()
    check("g. live_site: every private route goes through private_why (day/, money_out, the private money names)",
          "why = private_why(_client(request), request.headers)" in src and "if why is None else None" in src and '"household", "agency"' in src)
    check("g. day_inbox: the route passes the client to accept(), which asks private_why", "client=client" in di and "live_site.private_why(client" in di)
    check("g. live_site stays read only (no POST route, no file write)", "router.post" not in src.split('"""', 2)[-1] and "open(" not in src.split("def private_why", 1)[1].split("def _client", 1)[0])


def main() -> int:
    rule()
    b = Box()
    try:
        routes(b)
        paths(b)
        inbox(b)
    finally:
        b.close()
    money_server()
    static()
    if FAST:
        print("[SKIP] --fast: the real server.py child process (f) was skipped")
    else:
        real_server()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
