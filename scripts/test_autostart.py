"""Offline checks for the unattended-run pieces (no network, no real bot thread, nothing written under data/).

    python -X utf8 scripts/test_autostart.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine import watchdog as wd  # noqa: E402

PHRASE = "I ACCEPT LIVE RISK"
tmp = tempfile.mkdtemp(prefix="le_autostart_")
P = os.path.join(tmp, "autostart.json")
now = time.time()
n_ok = 0


def check(cond, label):
    global n_ok
    assert cond, label
    n_ok += 1
    print(f"  ok  {label}")


print("decide_resume")
r = wd.save({"sym": "NQ", "tf": "5m", "adapter": "paper", "params": {"risk_usd": 350}, "clear_kill": True,
             "webhook_url": "https://x", "confirm": PHRASE}, "demo", P, now=now - 3600, phrases=(PHRASE,))
check(r["mode"] == "paper" and "webhook_url" not in r["cfg"] and "confirm" not in r["cfg"] and "clear_kill" not in r["cfg"],
      "save strips webhook_url / confirm / clear_kill")
check(PHRASE not in open(P, encoding="utf-8").read(), "confirm phrase never written to disk")
d = wd.decide_resume(wd.load(P), now, "demo")
check(d["resume"] and d["cfg"]["adapter"] == "paper" and d["cfg"]["params"]["risk_usd"] == 350, "paper resumes")
check(not wd.decide_resume(wd.load(P), now + 8 * 86400, "demo")["resume"], "record older than 7 days does not resume")

wd.save({"adapter": "tradovate-demo", "armed": True}, "demo", P, now=now)
check(wd.decide_resume(wd.load(P), now, "demo")["resume"], "tradovate-demo resumes")
wd.save({"adapter": "tradovate", "armed": True}, "demo", P, now=now)
check(wd.decide_resume(wd.load(P), now, "demo")["resume"], "tradovate on demo env resumes")
check(not wd.decide_resume(wd.load(P), now, "live")["resume"], "tradovate while TRADOVATE_ENV=live does NOT resume")
wd.save({"adapter": "tradovate-live", "armed": True, "confirm": PHRASE, "autoresume_live": True}, "live", P, now=now, phrases=(PHRASE,))
d = wd.decide_resume(wd.load(P), now, "live")
check(not d["resume"] and d["mode"] == "live", "tradovate-live never resumes (even with autoresume_live in the body)")
wd.save({"adapter": "traderspost"}, "demo", P, now=now)
check(not wd.decide_resume(wd.load(P), now, "demo")["resume"], "traderspost does not resume")
check(not wd.decide_resume(None, now)["resume"], "no record -> no resume")
open(P, "w").write("{not json")
check(not wd.decide_resume(wd.load(P), now)["resume"], "corrupt record -> no resume")
wd.save({"adapter": "paper"}, "demo", P, now=now)
check(wd.clear(P) and wd.load(P) is None and not wd.decide_resume(wd.load(P), now)["resume"], "stop clears -> no resume")


print("watchdog conditions")


class FakeThread:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive


class FakeBot:
    running = True
    cfg = {"poll_sec": 60}
    started_at = None
    thread = FakeThread()

    def __init__(self):
        self.health = {"last_ok_poll": None, "stale": False}


sent = []
b = FakeBot()
t0 = 1792069200  # 2026-10-15 (Thu) 09:00 ET
b.started_at = t0
w = wd.Watchdog(b, send=sent.append, clock=lambda: t0, log=lambda *_: None)
b.health["last_ok_poll"] = t0
check(w.check(t0 + 60) == [] and not sent, "fresh poll -> no issue")
iss = w.check(t0 + 200)
check([i["key"] for i in iss] == ["poll_overdue"] and len(sent) == 1, "poll older than 3 x poll_sec -> one alert")
w.check(t0 + 500)
check(len(sent) == 1, "same condition is rate-limited (30 min)")
w.check(t0 + 200 + 1801)
check(len(sent) == 2, "re-alerts after 30 min")
b.health["last_ok_poll"] = t0 + 2100
w.check(t0 + 2110)
check(len(sent) == 3 and "recovered" in sent[-1], "recovery message once")
b.health["stale"] = True
w.check(t0 + 2120)
b.health["last_ok_poll"] = t0 + 2120 + 300
w.check(t0 + 2120 + 300)
check(len(sent) == 3, "stale < 10 min -> no alert")
b.health["last_ok_poll"] = t0 + 2120 + 700
w.check(t0 + 2120 + 700)
check(len(sent) == 4 and "stale" in sent[-1], "stale > 10 min in 09:00-16:00 ET weekday -> alert")
sat = 1792328400  # 2026-10-18 Sun 09:00 ET
w2 = wd.Watchdog(b, send=sent.append, log=lambda *_: None)
b.health["last_ok_poll"] = sat
w2.check(sat)
b.health["last_ok_poll"] = sat + 900
w2.check(sat + 900)
check(len(sent) == 4, "stale on a weekend -> no alert")
b.thread = FakeThread(False)
check("thread_dead" in [i["key"] for i in w2.evaluate(sat + 900)], "dead poll thread detected")
b.running = False
check(w2.evaluate(sat + 99999) == [], "bot stopped -> no issues")


print("server endpoints (TestClient, autostart path redirected to a temp dir)")
os.environ["LE_NO_AUTOSTART"] = "1"
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

server._AUTOSTART["path"] = P
alerts_sent = []
server._autostart_alert = alerts_sent.append
with TestClient(server.app) as c:
    j = c.get("/api/health/ping").json()
    check(j["ok"] is True and "uptime_s" in j, f"/api/health/ping -> {j}")
    j = c.get("/api/health/watchdog").json()
    check(set(["ok", "issues", "server_started_at", "uptime_s", "autostart"]) <= set(j), f"/api/health/watchdog keys {sorted(j)}")
    print("     watchdog:", {k: j[k] for k in ("ok", "issues", "uptime_s", "autostart", "bot_running", "thread_alive")})
    # kill clears the record (kill on a stopped bot: no orders, no state file since cfg is empty)
    wd.save({"adapter": "paper"}, "demo", P, now=time.time())
    real_kill = server.BOT.kill_switch
    server.BOT.kill_switch = lambda: {"ok": True}
    try:
        check(c.post("/api/live/kill").status_code == 200 and wd.load(P) is None, "POST /api/live/kill clears autostart.json")
    finally:
        server.BOT.kill_switch = real_kill
    wd.save({"adapter": "paper"}, "demo", P, now=time.time())
    real_stop = server.BOT.stop
    server.BOT.stop = lambda: {"ok": True}
    try:
        check(c.post("/api/live/stop").status_code == 200 and wd.load(P) is None, "POST /api/live/stop clears autostart.json")
    finally:
        server.BOT.stop = real_stop

# startup resume path with BOT.start stubbed
started = []
real_start = server.BOT.start
server.BOT.start = lambda cfg: (started.append(cfg), {"ok": True, "restored": None})[1]
try:
    wd.save({"sym": "NQ", "tf": "5m", "adapter": "paper"}, "demo", P, now=time.time())
    server._autostart_resume()
    check(started and started[-1]["adapter"] == "paper" and server.WATCHDOG.autostart_info["resumed"]
          and any("auto-resumed" in a for a in alerts_sent), "startup resumes paper + sends alert")
    wd.save({"adapter": "tradovate-live", "armed": True}, "live", P, now=time.time())
    n = len(started)
    server._autostart_resume()
    check(len(started) == n and not server.WATCHDOG.autostart_info["resumed"] and "NOT resumed" in alerts_sent[-1],
          "startup does not resume live, alerts instead")
finally:
    server.BOT.start = real_start
    wd.clear(P)

print(f"PASS ({n_ok} checks)")
