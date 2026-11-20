"""Test for cross_site.py (copy to tests/test_cross_site.py once engine/cross_site.py exists; LEAD_WIRES.md W1).
  a. the pure rule: a cross-site page, Origin null, another Origin, a DNS-rebinding Host are refused; the PC's own page, the phone
     on Tailscale, a LAN IP, curl / scripts, GET, the TradingView webhooks and cloud mode pass
  b. through a real FastAPI app (TestClient): a text/plain POST from evil.example to /api/live/start never reaches the route
    python -X utf8 research/handoff/2026-11-20/security/test_cross_site.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
try:
    from engine import cross_site as X          # once wired
except ImportError:
    sys.path.insert(0, HERE)
    import cross_site as X                      # noqa: E402  (the handoff copy)

RES = []


def ok(c, n):
    RES.append(bool(c))
    print(("  PASS " if c else "  FAIL ") + n)


def part_a():
    print("a. the rule")
    E = {}
    P = "/api/live/start"
    ok(X.why("POST", P, {"host": "localhost:8766", "origin": "https://evil.example", "sec-fetch-site": "cross-site"}, E),
       "a cross-site page on the PC's browser is refused")
    ok(X.why("POST", P, {"host": "localhost:8766", "origin": "https://evil.example"}, E), "another Origin (no Sec-Fetch) is refused")
    ok(X.why("POST", P, {"host": "localhost:8766", "origin": "null"}, E), "Origin null is refused")
    ok(X.why("POST", P, {"host": "rebind.evil.example:8766", "origin": "http://rebind.evil.example:8766",
                         "sec-fetch-site": "same-origin"}, E), "DNS rebinding (Host = a foreign name) is refused")
    ok(X.why("POST", P, {"host": "localhost:8766", "sec-fetch-site": "same-site", "origin": "http://localhost:9999"}, E),
       "another port on localhost (same-site) is refused")
    ok(X.why("POST", P, {"host": "localhost:8766", "origin": "http://localhost:8766", "sec-fetch-site": "same-origin"}, E) is None,
       "the PC's own dashboard passes")
    ok(X.why("POST", P, {"host": "pc.tail1234.ts.net:8444", "origin": "https://pc.tail1234.ts.net:8444", "sec-fetch-site": "same-origin"}, E)
       is None, "the phone on the Tailscale link passes")
    ok(X.why("POST", P, {"host": "192.168.1.20:8766", "origin": "http://192.168.1.20:8766"}, E) is None, "a LAN IP page (same origin) passes")
    ok(X.why("POST", P, {"host": "127.0.0.1:8766"}, E) is None, "curl / scripts on the PC (no Origin) pass")
    ok(X.why("GET", P, {"host": "evil.example", "origin": "https://evil.example"}, E) is None, "GET is never blocked here")
    ok(X.why("POST", "/api/tv/webhook", {"host": "x.trycloudflare.com"}, E) is None, "the TradingView webhooks keep their own key check")
    ok(X.why("POST", P, {"host": "app.example.com", "origin": "https://evil.example"}, {"LE_CLOUD": "1"}) is None, "cloud mode is left to cloud_guard")
    ok(X.why("POST", P, {"host": "my.dash.example:8766"}, {"LE_ALLOWED_HOSTS": "my.dash.example"}) is None, "LE_ALLOWED_HOSTS adds a name")


def part_b():
    print("b. through FastAPI")
    global Request                              # FastAPI reads the route's (string) annotation from the module globals
    try:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
    except Exception as e:  # noqa: BLE001
        print("  SKIP (no fastapi test client: %s)" % e.__class__.__name__)
        return
    app = FastAPI()
    hit = []

    @app.post("/api/live/start")
    async def start(req: Request):
        hit.append(await req.json())
        return {"ok": True}
    X.install(app)
    c = TestClient(app, base_url="http://localhost:8766")
    r = c.post("/api/live/start", content='{"adapter":"ninjatrader","armed":true}',
               headers={"content-type": "text/plain", "origin": "https://evil.example", "sec-fetch-site": "cross-site"})
    ok(r.status_code == 403 and not hit, "a text/plain cross-site POST never reaches /api/live/start")
    r = c.post("/api/live/start", json={"adapter": "paper"}, headers={"origin": "http://localhost:8766", "sec-fetch-site": "same-origin"})
    ok(r.status_code == 200 and hit[-1:] == [{"adapter": "paper"}], "the dashboard's own POST still works (%s %s)" % (r.status_code, hit))


def main():
    part_a()
    part_b()
    n = sum(RES)
    print(f"\ncross_site: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
