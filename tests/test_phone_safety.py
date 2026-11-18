"""ZEUS phone safety switch (engine/phone_safety.py) + the audit trail (engine/audit_trail.py). docs/ZEUS_FEATURES.md.

  a. rules     check(): OFF by default (and LE_PHONE_SAFETY=0 wins over the file), only the PC itself / the Tailscale link,
               WiFi / Funnel / another tunnel / no login refused, a cross-site page refused (no header, no JSON, another
               Origin, Sec-Fetch-Site cross-site), the second tap needed, unknown / start / arm / update 404, 8 a 10 min
  b. routes    a real FastAPI app (live_site + phone_safety) with a real RemoteControl on a fake bot: over the link PAUSE writes
               the pause file, RESUME clears it, FLATTEN calls the flatten hook once, KILL the kill hook once, each logged +
               a phone notice; the WiFi gets 403 for the page, the status and every press; any other POST over the link is
               still refused (live_site's read-only guard); the page has the four buttons and no start / arm
  c. trail     engine/audit_trail merges the phone log, hands-off, the board, the OIF orders (no account name) and updates
  d. server    server.py wires install(app, REMOTE, BOT); the module never names start / arm / update as an action

  python -X utf8 -m tests.test_phone_safety
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import audit_trail as AT  # noqa: E402
from engine import live_site as LS  # noqa: E402
from engine import phone_safety as PS  # noqa: E402
from engine import remote_ctl as RC  # noqa: E402

RES: list = []
TS_HOST = "olympus-pc.tail1234.ts.net"
LINK_H = {"x-forwarded-for": "100.101.102.103", "x-forwarded-proto": "https", "x-forwarded-host": TS_HOST,
          "tailscale-user-login": "owner@example.com", "host": TS_HOST}
PAGE_H = {"x-zeus-safety": "1", "content-type": "application/json", "origin": "https://" + TS_HOST, "sec-fetch-site": "same-origin"}
LINK_C = "100.101.102.103"


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:400]}"))
    return bool(cond)


def body(a, **kw):
    return json.dumps({"confirm": a, **kw}).encode()


class FakeBot:
    def __init__(self, tmp):
        self.running, self.kill, self.cfg = True, False, {"adapter": "ninjatrader", "sym": "NQ"}
        self.state = {"position": {"dir": 1, "qty": 2, "entry_t": 1}}
        self.state_path = os.path.join(tmp, "live_state.json")
        self._no_entries_day = None
        self.health = {}
        self.calls = []

    def _save_state(self):
        pass


# ============================================================================================== a. the rules
def rules(tmp):
    sp = os.path.join(tmp, "ps.json")
    on = {"LE_PHONE_SAFETY": ""}
    PS._HITS.clear()
    c, b = PS.check("flatten", body("flatten"), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    check("a. OFF by default (no file): 403 with the one line to turn it on", c == 403 and PS.HOW_ON in b["error"], b)
    PS.set_on(True, sp)
    c, b = PS.check("flatten", body("flatten"), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    check("a. ON + the Tailscale link + the page + confirmed: may run", c is None and b == {"confirm": "flatten"}, (c, b))
    c, _b = PS.check("flatten", body("flatten"), {**LINK_H, **PAGE_H}, LINK_C, env={"LE_PHONE_SAFETY": "0"}, state_path=sp)
    check("a. LE_PHONE_SAFETY=0 wins over the file", c == 403)
    c, _b = PS.check("pause", body("pause"), {"host": "localhost:8766", **PAGE_H, "origin": "http://localhost:8766"}, "127.0.0.1",
                     env=on, state_path=sp)
    check("a. the PC itself (loopback, Host localhost, same origin) may press", c is None, _b)
    bad = {
        "the home WiFi": ({"host": "192.168.1.20:8766", **PAGE_H, "origin": "http://192.168.1.20:8766"}, "192.168.1.50"),
        "WiFi with forged Tailscale headers": ({**LINK_H, **PAGE_H}, "192.168.1.50"),
        "Funnel (internet)": ({**LINK_H, **PAGE_H, "tailscale-funnel-request": "1"}, LINK_C),
        "another tunnel": ({**LINK_H, **PAGE_H, "cf-connecting-ip": "8.8.8.8"}, LINK_C),
        "no signed-in Tailscale user": ({**{k: v for k, v in LINK_H.items() if k != "tailscale-user-login"}, **PAGE_H}, LINK_C),
        "no X-Zeus-Safety header (a plain form post)": ({**LINK_H, **{k: v for k, v in PAGE_H.items() if k != "x-zeus-safety"}}, LINK_C),
        "not JSON": ({**LINK_H, **PAGE_H, "content-type": "text/plain"}, LINK_C),
        "another site's Origin": ({**LINK_H, **PAGE_H, "origin": "https://evil.example"}, LINK_C),
        "no Origin": ({**LINK_H, **{k: v for k, v in PAGE_H.items() if k != "origin"}}, LINK_C),
        "Sec-Fetch-Site cross-site": ({**LINK_H, **PAGE_H, "sec-fetch-site": "cross-site"}, LINK_C),
    }
    got = {k: PS.check("kill", body("kill"), h, cl, env=on, state_path=sp)[0] for k, (h, cl) in bad.items()}
    check("a. refused (403): " + ", ".join(bad), all(v == 403 for v in got.values()), got)
    c1, _ = PS.check("kill", body("flatten"), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    c2, _ = PS.check("kill", b"{}", {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    c3, _ = PS.check("kill", b"{not json", {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    c4, _ = PS.check("kill", b"x" * 2000, {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)
    check("a. the second tap is needed (confirm = the action), junk 400, too long 413", (c1, c2, c3, c4) == (400, 400, 400, 413),
          (c1, c2, c3, c4))
    nope = {a: PS.check(a, body(a), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp)[0]
            for a in ("start", "arm", "update", "restart", "present", "settings", "resume_entries")}
    check("a. no start / arm / update / restart / settings button: 404", all(v == 404 for v in nope.values()), nope)
    PS._HITS.clear()
    n = [PS.check("pause", body("pause"), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp, now=1000 + i)[0] for i in range(10)]
    later = PS.check("pause", body("pause"), {**LINK_H, **PAGE_H}, LINK_C, env=on, state_path=sp, now=1000 + PS.RATE_S + 20)[0]
    check("a. 8 presses in 10 minutes, then 429; fine again later", n[:8] == [None] * 8 and n[8:] == [429, 429] and later is None, n)
    PS._HITS.clear()
    check("a. allowed(): only POST /safety/<4 actions>, and only once installed",
          not PS.allowed("POST", "/safety/kill") or PS._S["installed"], PS._S)


# ============================================================================================== b. the routes
def routes(tmp):
    os.environ["LE_PHONE_SAFETY"] = "1"
    PS._HITS.clear()
    bot = FakeBot(tmp)
    notes, hooks = [], {"kill": [], "flatten": [], "beat": []}

    def h(name):
        def f(*a):
            hooks[name].append(a)
            if name == "kill":
                bot.kill, bot.running = True, False
            if name == "flatten":
                bot.state["position"] = None
            return {"ok": True, "had_position": True}
        return f

    rc = RC.RemoteControl(bot, hooks={"kill": h("kill"), "flatten": h("flatten"), "beat": h("beat"),
                                      "stop": lambda: {"ok": True}, "start": lambda b: (_ for _ in ()).throw(AssertionError("start"))},
                          done_path=os.path.join(tmp, "remote_done.json"), notify=lambda t, b_, k: notes.append((t, b_)),
                          log=lambda t: None, env={})
    PS.LOG_PATH = os.path.join(tmp, "phone_log.jsonl")
    app = FastAPI()
    LS.install(app)
    PS.install(app, rc, bot)
    PS.LOG_PATH = os.path.join(tmp, "phone_log.jsonl")
    link = TestClient(app, follow_redirects=False, client=(LINK_C, 0), base_url="https://" + TS_HOST)
    wifi = TestClient(app, follow_redirects=False, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8766")
    hh = {**{k: v for k, v in LINK_H.items() if k != "host"}, **PAGE_H}
    pg = link.get("/safety/", headers={k: v for k, v in LINK_H.items() if k != "host"})
    check("b. the page opens over the link with the four buttons and no start / arm button",
          pg.status_code == 200 and all(f"b-{a}" in pg.text for a in PS.ACTIONS) and "b-start" not in pg.text
          and "b-arm" not in pg.text and pg.headers.get("cache-control") == "no-store", (pg.status_code, pg.text[:200]))
    st = link.get("/safety/status", headers={k: v for k, v in LINK_H.items() if k != "host"}).json()
    check("b. status over the link: ON, running, LONG 2, new trades allowed", st.get("on") and st["running"] and st["position"] == "LONG 2"
          and st["pause"] is None, st)
    r = link.post("/safety/pause", content=body("pause"), headers=hh)
    from engine import entry_pause
    pp = entry_pause.path_for(bot)
    pa = entry_pause.active(time.time(), pp) or {}
    import datetime as dt
    ue = dt.datetime.fromtimestamp(pa.get("until") or 0, entry_pause.ET)
    check("b. PAUSE over the link: done, the pause runs to the next 4 PM ET (<= 24 h), the open trade untouched",
          r.status_code == 200 and r.json()["ok"] and (ue.hour, ue.minute) == (16, 0) and 0 < pa["until"] - time.time() <= 86400
          and not hooks["flatten"], (r.text, pa))
    r = link.post("/safety/resume", content=body("resume"), headers=hh)
    check("b. RESUME: done, the pause gone", r.json()["ok"] and entry_pause.active(time.time(), pp) is None, r.text)
    r = link.post("/safety/flatten", content=body("flatten"), headers=hh)
    check("b. FLATTEN: the flatten hook ran once, 'position closed'", r.json()["ok"] and len(hooks["flatten"]) == 1
          and "position closed" in r.json()["said"], r.text)
    r = link.post("/safety/kill", content=body("kill"), headers=hh)
    check("b. KILL: the kill hook ran once, bot stopped, 'Start it again at the PC'", r.json()["ok"] and len(hooks["kill"]) == 1
          and not bot.running and "at the PC" in r.json()["said"], r.text)
    d = RC.load_done(rc.done_path)
    check("b. each press is in remote_done (no 'running' left) + one phone notice each, titled 'Phone ...'",
          len(d["done"]) == 4 and all(v["status"] == "done" for v in d["done"].values())
          and [t for t, _ in notes] == ["Phone PAUSE: done", "Phone RESUME: done", "Phone FLATTEN: done", "Phone KILL: done"], (d, notes))
    rows = PS.recent(10)
    check("b. the phone log has the 4 presses (no account id)", [x["action"] for x in rows] == ["pause", "resume", "flatten", "kill"]
          and "Sim" not in json.dumps(rows), rows)
    w = [wifi.get("/safety/").status_code, wifi.get("/safety/status").status_code,
         wifi.post("/safety/flatten", content=body("flatten"), headers={**PAGE_H, "origin": "http://192.168.1.20:8766"}).status_code]
    check("b. the home WiFi: page, status and press all 403; the flatten hook not called again", w == [403, 403, 403]
          and len(hooks["flatten"]) == 1, w)
    o = link.post("/safety/start", content=body("start"), headers=hh)
    o2 = link.post("/api/live/start", json={"adapter": "ninjatrader"}, headers=hh)
    check("b. over the link /safety/start and any other POST (/api/live/start) are refused by the read-only guard",
          o.status_code == 403 and o2.status_code == 403, (o.status_code, o2.status_code))
    xs = link.post("/safety/flatten", content=body("flatten"), headers={**hh, "origin": "https://evil.example"})
    check("b. a cross-site post through the link: 403, nothing run", xs.status_code == 403 and len(hooks["flatten"]) == 1, xs.text)
    os.environ["LE_PHONE_SAFETY"] = "0"
    off = link.post("/safety/flatten", content=body("flatten"), headers=hh)
    check("b. switched off: 403, nothing run", off.status_code == 403 and len(hooks["flatten"]) == 1, off.text)
    os.environ.pop("LE_PHONE_SAFETY", None)


# ============================================================================================== c. the audit trail
def trail(tmp):
    t0 = 1795000000
    p = {k: os.path.join(tmp, "trail", k) for k in AT.PATHS}
    os.makedirs(os.path.join(tmp, "trail"), exist_ok=True)
    with open(p["phone"], "w") as fh:
        fh.write(json.dumps({"t": t0, "action": "flatten", "status": "done", "msg": "position closed", "src": "phone"}) + "\n")
    with open(p["handsoff"], "w") as fh:
        fh.write(json.dumps({"t": t0 + 1, "kind": "flatten", "src": "phone", "detail": "position closed"}) + "\n")
        fh.write(json.dumps({"t": t0 + 60, "kind": "manual_close", "src": "pc", "detail": "closed in NinjaTrader"}) + "\n")
        fh.write("{broken\n")
    with open(p["board"], "w") as fh:
        fh.write(json.dumps({"t": t0 - 60, "kind": "bot_started", "text": "bot started"}) + "\n")
        fh.write(json.dumps({"t": t0 - 30, "kind": "balance", "text": "x"}) + "\n")
    import datetime as dt
    stamp = dt.datetime.fromtimestamp(t0 - 10, AT.ET).strftime("%Y-%m-%d %H:%M:%S")
    with open(p["orders"], "w") as fh:
        fh.write(f"{stamp} ET  MFFUEVSECRET123  oif_le_1_1.txt  PLACE;MFFUEVSECRET123;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;id1;;\n")
        fh.write(f"{stamp} ET  MFFUEVSECRET123  oif_le_1_2.txt  CANCEL;;;;;;;;;;id1;;\n")
    with open(p["update"], "w") as fh:
        json.dump({"history": [{"t": t0 + 100, "status": "updated", "old": "a" * 40, "new": "b" * 40}, {"t": t0 + 200, "status": "up_to_date"}]}, fh)
    rows = AT.collect(p)
    whats = [r["what"] for r in rows]
    check("c. merged oldest first: started, order PLACE, CANCEL, phone FLATTEN (once), manual close, update; balance + up-to-date skipped",
          [r["src"] for r in rows] == ["bot", "orders", "orders", "phone", "pc", "update"]
          and whats[1] == "order PLACE BUY 2 MNQ 12-26 MARKET" and whats[3].startswith("phone FLATTEN: done")
          and "aaaaaaa -> bbbbbbb" in whats[5], rows)
    check("c. the account name never reaches the trail", "SECRET" not in json.dumps(rows), rows)
    check("c. missing files: an empty trail, no error", AT.collect({k: os.path.join(tmp, "none", k) for k in AT.PATHS}) == [])
    check("c. recent(): last N within the days", [r["src"] for r in AT.recent(2, now=t0 + 300, paths=p)] == ["pc", "update"])


# ============================================================================================== d. wiring
def wiring():
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    i, j = src.find("_ps.install(app, REMOTE, BOT)"), src.find('app.mount("/", _static')
    check("d. server.py installs the phone safety routes with REMOTE + BOT, before the static mount", 0 < i < j)
    mod = open(os.path.join(ROOT, "engine", "phone_safety.py"), encoding="utf-8").read()
    check("d. the action list is exactly pause / resume / flatten / kill; nothing calls start / arm / golive / ninjatrader",
          set(PS.ACTIONS) == {"pause", "resume", "flatten", "kill"} and set(PS.ACTIONS.values()) == {"pause", "resume_entries", "flatten", "kill"}
          and "_start(" not in mod and "golive" not in mod and "import ninjatrader" not in mod and "armed" not in mod)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("d. the switch file and the press log are gitignored", "data/phone_safety.json" in gi and "data/phone_safety_log.jsonl" in gi)


def main():
    tmp = tempfile.mkdtemp(prefix="phonesafety-")
    try:
        rules(tmp)
        routes(tmp)
        trail(tmp)
        wiring()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
