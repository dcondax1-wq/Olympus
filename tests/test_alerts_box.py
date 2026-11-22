"""The Phone alerts box (engine/alerts_box.py, owner 2026-11-21 "setup phone alerts with just my phone quickly").

    python -X utf8 -m tests.test_alerts_box          # ~3 s

Fake Telegram HTTP (engine/alert_bus._HTTP), temp OLYMPUS_HOME + temp log: never the network, nothing in the repo tree written.
  a. the page + status open on the PC and over the signed-in Tailscale link; refused from the home WiFi, Funnel, cloud mode
  b. a POST needs this page's header, JSON, same Origin, a tiny body, the rate limit; refused ones never reach Telegram
  c. a bad token gives a plain reason + the one fix (not a token / Telegram says wrong / no internet / Telegram error)
  d. Connect: getMe -> "Open @bot" link; the /start wait (tools/alerts_setup.wait_chat_id) -> the Telegram test -> saved with
     save_raw (the same file ALERTS_SETUP option 1 writes, Discord kept, 0600) -> ALERTS_OFF undone (= ALERTS_ON) -> done
  e. no START in time / the test not delivered / Cancel / a crash in the wait: nothing saved, a plain reason
  f. the token: never in a reply, a status, the log, stdout / stderr or an exception text; the status = booleans + state words only
  g. the test button = TEST_ALERT (every channel, {channel: true/false} only); the links + the server.py block; nothing in the repo
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []
TOKEN = "1234567" + "89:" + "AAH" + "k" * 32              # built at run time: never a token-shaped literal in the repo
WRONG = "98765" + "4321:" + "AAF" + "q" * 32
CHAT = "5550" + "123456"
BOT = "olympus_alerts_7731_bot"
HOOK = "https://discord.com/api/webhooks/" + "1" * 18 + "/" + "z" * 68


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:400]), file=sys.__stdout__, flush=True)


class TG:
    """Telegram's Bot API, faked: getMe, getUpdates (the /start after a few polls), sendMessage."""

    def __init__(self):
        self.calls, self.sent, self.mode, self.polls = [], [], {}, 0
        self.code, self.stranger = None, False                  # day-security3: the page's one-time START code; a stranger's /start

    def __call__(self, method, url, body, headers, timeout):
        self.calls.append(url)
        if not url.startswith("https://api.telegram.org/bot"):
            return 0, "URLError"                                 # ntfy / Discord in the test button: not reachable
        tok = url.split("/bot", 1)[1].split("/", 1)[0]
        if url.endswith("/getMe"):
            m = self.mode.get("getme", "ok")
            if m == "boom":
                raise RuntimeError("boom " + url)
            if m == 0:
                return 0, "URLError"
            if m == 500:
                return 500, '{"ok":false,"description":"Internal Server Error"}'
            if tok != TOKEN:
                return 401, '{"ok":false,"error_code":401,"description":"Unauthorized"}'
            return 200, json.dumps({"ok": True, "result": {"id": 7731, "is_bot": True, "first_name": "Olympus Alerts", "username": BOT}})
        if "/getUpdates" in url:
            if "timeout=0" in url:
                return 200, '{"ok":true,"result":[]}'
            time.sleep(0.01)
            m = self.mode.get("updates", "start")
            if m == "boom":
                raise RuntimeError("boom " + url)
            if m == 401:
                return 401, '{"ok":false,"error_code":401,"description":"Unauthorized"}'
            self.polls += 1
            if m == "start" and self.polls >= 3:
                first = ({"update_id": 40, "message": {"chat": {"id": 999000111, "type": "private"}, "text": "/start"}} if self.stranger
                         else {"update_id": 40, "message": {"chat": {"id": -1001, "type": "group"}, "text": "/start"}})
                return 200, json.dumps({"ok": True, "result": [first,
                    {"update_id": 41, "message": {"chat": {"id": int(CHAT), "type": "private"},
                                                  "text": "/start" + (" " + self.code if self.code else "")}}]})
            return 200, '{"ok":true,"result":[]}'
        if url.endswith("/sendMessage"):
            if self.mode.get("send") == 500:
                return 500, '{"ok":false,"description":"Internal Server Error"}'
            self.sent.append(json.loads(body))
            return 200, json.dumps({"ok": True, "result": {"message_id": 77 + len(self.sent)}})
        return 404, "{}"

    def n(self, part):
        return sum(1 for u in self.calls if part in u)


def until(cond, s=5.0):
    end = time.time() + s
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def repo_marks():
    """What a run could touch in the repo: the press log, the bus's files, and git's own view of the tree."""
    marks = {}
    for rel in ("data/alerts_box.jsonl", "data/alert_bus.jsonl", "data/alert_bus_sent.json", "alerts.json", "data/alerts.json"):
        p = os.path.join(ROOT, rel)
        marks[rel] = os.path.getmtime(p) if os.path.exists(p) else None
    try:
        marks["git"] = subprocess.run(["git", "status", "--porcelain", "--", "data", "engine", "tools", "alerts.json"], cwd=ROOT,
                                      capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        marks["git"] = None
    return marks


def main() -> int:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import alert_bus as AB, alerts_box as AL, live_site as LS, push as P
    from tools import alerts_setup as S
    from tests import test_phone_safety as TPS
    tmp = tempfile.mkdtemp(prefix="alertsbox_")
    home = os.path.join(tmp, "home")
    os.makedirs(home)
    keep_env = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "LE_CLOUD", "LE_ALERT_BUS")}
    keep = (AB._HTTP, AB.STATE_PATH, AB.LOG_PATH, P.app_send)
    before = repo_marks()
    out, err = io.StringIO(), io.StringIO()
    texts = []                                                   # every reply / status / page text, for f.
    tg = TG()
    try:
        os.environ["OLYMPUS_HOME"] = home
        os.environ.pop("LE_CLOUD", None)
        os.environ.pop("LE_ALERT_BUS", None)
        AB._HTTP = tg
        AB.STATE_PATH = os.path.join(tmp, "data", "alert_bus_sent.json")
        AB.LOG_PATH = os.path.join(tmp, "data", "alert_bus.jsonl")
        P.app_send = lambda payload, **k: {"sent": 1}
        AL._S.update(log=os.path.join(tmp, "alerts_box.jsonl"), wait_s=5, sleep=lambda s: time.sleep(0.01))
        AL._HITS.clear()
        app = FastAPI()
        LS.install(app)
        AL.install(app)
        link = dict(TPS.LINK_H)
        page_h = {"x-olympus-alerts": "1", "content-type": "application/json", "origin": "https://" + TPS.TS_HOST,
                  "sec-fetch-site": "same-origin"}
        H = {**link, **page_h}
        c = TestClient(app, follow_redirects=False, client=(TPS.LINK_C, 0), base_url="https://" + TPS.TS_HOST)
        pc = TestClient(app, follow_redirects=False, client=("127.0.0.1", 50000), base_url="http://localhost:8766")
        wifi = TestClient(app, follow_redirects=False, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8766")
        pc_h = {"x-olympus-alerts": "1", "content-type": "application/json", "origin": "http://localhost:8766",
                "sec-fetch-site": "same-origin"}

        def post(path, body=None, h=None, cl=None, raw=None):
            r = (cl or c).post(path, headers=h or H, content=raw if raw is not None else json.dumps(body or {}).encode())
            texts.append(r.text + json.dumps(dict(r.headers)))
            try:                                                 # the owner taps the page's Open link: "/start <this connect's code>"
                lk = str(r.json().get("link") or "")
                if "?start=" in lk:
                    tg.code = lk.split("?start=", 1)[1]
            except Exception:  # noqa: BLE001
                pass
            return r

        def status(cl=None, h=None):
            r = (cl or c).get("/alerts/status", headers=link if h is None else h)
            texts.append(r.text)
            return r.json()

        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            # a. who may open it
            p = c.get("/alerts/", headers=link)
            texts.append(p.text)
            check("a. page opens over the signed-in Tailscale link (no-store, CSP, no frames)", p.status_code == 200
                  and "Phone alerts" in p.text and "no-store" in p.headers.get("cache-control", "")
                  and "frame-ancestors 'none'" in p.headers.get("content-security-policy", ""), p.status_code)
            check("a. page opens on the PC itself", pc.get("/alerts/").status_code == 200)
            check("a. /alerts redirects to /alerts/", pc.get("/alerts").status_code == 307)
            check("a. refused from another device on the home WiFi", wifi.get("/alerts/").status_code == 403
                  and wifi.get("/alerts/status").status_code == 403)
            check("a. refused through Funnel (internet)",
                  c.get("/alerts/", headers={**link, "tailscale-funnel-request": "1"}).status_code == 403)
            nolog = {k: v for k, v in link.items() if k != "tailscale-user-login"}
            check("a. refused without a signed-in Tailscale user", c.get("/alerts/status", headers=nolog).status_code == 403)
            os.environ["LE_CLOUD"] = "1"
            check("a. refused in cloud mode (page + status + POST)", pc.get("/alerts/").status_code == 403
                  and pc.get("/alerts/status").status_code == 403 and post("/alerts/test", {}, pc_h, pc).status_code == 403)
            os.environ.pop("LE_CLOUD", None)
            t = p.text
            check("a. the page: the BotFather steps, a hidden token box, Connect, the START step",
                  all(w in t for w in ("BotFather", "/newbot", "Olympus Alerts", "ends in <code>bot</code>", "long-press it",
                                       'type="password"', 'autocomplete="off"', ">Connect<", "tap START", "https://t.me/BotFather")))
            check("a. the page: Olympus Night (black, #16131e cards, violet lines, gold, mint), 44 px taps, phone width",
                  all(w in t for w in ("--bg:#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89", "min-height:44px",
                                       "min-height:48px", "width=device-width", "max-width:560px")))
            check("a. the page carries every plain reason + fix", all(v[0] in t and v[1] in t for v in AL.REASONS.values()))
            st = status()
            check("a. status before setup: not set up, bus on the old path, idle", st.get("ok") and st["state"] == "idle"
                  and st["telegram_set_up"] is False and st["bus_on"] is False, st)

            # b. who may press it
            n0 = len(tg.calls)
            good = json.dumps({"token": TOKEN}).encode()
            for what, h, cl in (("no page header", {**link, "content-type": "application/json", "origin": "https://" + TPS.TS_HOST}, c),
                                ("another web site (Origin)", {**H, "origin": "https://evil.example"}, c),
                                ("cross-site fetch", {**H, "sec-fetch-site": "cross-site"}, c),
                                ("no Origin", {k: v for k, v in H.items() if k != "origin"}, c),
                                ("form post (not JSON)", {**H, "content-type": "application/x-www-form-urlencoded"}, c),
                                ("Funnel (internet)", {**H, "tailscale-funnel-request": "1"}, c),
                                ("home WiFi", pc_h, wifi),
                                ("home WiFi with forged Tailscale headers", {**H, "host": TPS.TS_HOST}, wifi)):
                r = post("/alerts/connect", h=h, cl=cl, raw=good)
                check(f"b. refused: {what}", r.status_code == 403 and len(tg.calls) == n0, (r.status_code, r.text[:160]))
            r = post("/alerts/connect", raw=b'{"token":"' + b"x" * 600 + b'"}')
            check("b. refused: body too long (413)", r.status_code == 413 and len(tg.calls) == n0, r.status_code)
            r = post("/alerts/arm", {})
            check("b. no other button (/alerts/arm)", r.status_code in (403, 404) and len(tg.calls) == n0, r.status_code)
            r = post("/alerts/connect", raw=b"[1,2]")
            check("b. not JSON -> 400", r.status_code == 400, r.status_code)
            check("b. nothing saved by a refused press", not os.path.exists(S.cfg_path()))
            other = post("/api/next/start/arm", {"confirm": "I ACCEPT LIVE RISK"})
            check("b. the PC's arm / start POSTs stay refused over the link", other.status_code == 403, other.status_code)

            # c. a bad token: a plain reason + the fix
            AL._HITS.clear()
            r = post("/alerts/connect", {"token": "hello 1234"}).json()
            check("c. not a token: bad_format, Telegram never called", r == {"ok": False, "state": "failed", "reason": "bad_format"}
                  and len(tg.calls) == n0, r)
            r = post("/alerts/connect", {"token": WRONG}).json()
            check("c. Telegram says the token is wrong (getMe 401): token_refused", r.get("reason") == "token_refused"
                  and tg.n("/getMe") == 1, r)
            tg.mode["getme"] = 0
            r = post("/alerts/connect", {"token": TOKEN}).json()
            check("c. the PC has no internet: no_internet", r.get("reason") == "no_internet", r)
            tg.mode["getme"] = 500
            r = post("/alerts/connect", {"token": TOKEN}).json()
            check("c. Telegram 500: telegram_error", r.get("reason") == "telegram_error", r)
            tg.mode["getme"] = "boom"
            r = post("/alerts/connect", {"token": TOKEN})
            check("c. the HTTP helper raises (its text holds the URL + token): a reason word only", r.status_code == 200
                  and r.json().get("reason") == "no_internet" and TOKEN not in r.text, r.text[:200])
            tg.mode.pop("getme")
            st = status()
            check("c. the status shows the last reason as a word", st["state"] == "failed" and st["reason"] == "no_internet", st)
            check("c. every reason is plain words + one fix", all(len(v) == 2 and v[0].endswith(".") and v[1] for v in AL.REASONS.values()))
            check("c. nothing saved after the bad tokens", not os.path.exists(S.cfg_path()))

            # d. the happy path
            AL._HITS.clear()
            with open(os.path.join(home, AB.OFF_NAME), "w") as fh:
                fh.write("off\n")                               # ALERTS_OFF was pressed once: Connect switches the bus back on
            with open(S.cfg_path(), "w", encoding="utf-8") as fh:
                json.dump({"discord": {"webhook": HOOK, "on": True}}, fh)
            tg.polls = 0
            r = post("/alerts/connect", {"token": TOKEN})
            d = r.json()
            check("d. Connect: getMe ok -> waiting for START, the bot's t.me link", d.get("ok") and d["state"] == "waiting_start"
                  and d["bot"] == "@" + BOT and d["link"].startswith("https://t.me/" + BOT + "?start=") and d["wait_s"] == 5 and "_mask" not in d, d)
            check("d. status while waiting: waiting, a state word only", status()["state"] in ("waiting_start", "done"))
            check("d. the /start arrives -> done", until(lambda: AL._W["state"] != "waiting_start") and AL._W["state"] == "done",
                  dict(AL._W))
            saved = json.load(open(S.cfg_path(), encoding="utf-8"))
            check("d. saved {telegram: token, chat_id (the private chat, not the group), on} + Discord kept",
                  saved == {"discord": {"webhook": HOOK, "on": True}, "telegram": {"token": TOKEN, "chat_id": CHAT, "on": True}}, saved)
            check("d. saved in OLYMPUS_HOME/alerts.json only, 0600", os.path.dirname(S.cfg_path()) == home
                  and (os.name == "nt" or (os.stat(S.cfg_path()).st_mode & 0o077) == 0))
            check("d. the Telegram test went to that chat: 'Olympus alerts are ON'", len(tg.sent) == 1
                  and str(tg.sent[0]["chat_id"]) == CHAT and tg.sent[0]["text"].startswith("Olympus alerts are ON"), tg.sent)
            check("d. the read updates were cleared (offset past the /start)", any("offset=42" in u for u in tg.calls))
            check("d. the bus is ON (ALERTS_OFF's switch file removed, = ALERTS_ON)", not os.path.exists(os.path.join(home, AB.OFF_NAME))
                  and AB.active())
            st = status()
            check("d. status: Connected, test delivered, set up, bus on", st["state"] == "done" and st["test_delivered"] is True
                  and st["telegram_set_up"] and st["discord_set_up"] and st["bus_on"] and st["reason"] is None, st)
            # the same file ALERTS_SETUP option 1 writes from the same start
            home2 = os.path.join(tmp, "home2")
            os.makedirs(home2)
            with open(os.path.join(home2, "alerts.json"), "w", encoding="utf-8") as fh:
                json.dump({"discord": {"webhook": HOOK, "on": True}}, fh)
            os.environ["OLYMPUS_HOME"] = home2
            rc = S.setup(ask_choice=lambda _p: "1", ask=lambda _p: TOKEN, say=lambda *_a: None, wait=lambda tok, say=None: CHAT)
            bat = json.load(open(os.path.join(home2, "alerts.json"), encoding="utf-8"))
            os.environ["OLYMPUS_HOME"] = home
            check("d. the saved file = what ALERTS_SETUP option 1 writes (same keys, same shape)", rc == 0 and bat == saved, (bat, saved))

            # e. the paths where nothing is saved
            def fresh():
                os.remove(S.cfg_path())
                tg.polls, tg.sent[:] = 0, []
                AL._HITS.clear()

            fresh()
            tg.mode["updates"] = "empty"
            AL._S["wait_s"] = 0.3
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            check("e. no START in time -> no_start, nothing saved", until(lambda: AL._W["state"] != "waiting_start")
                  and AL._W["state"] == "failed" and AL._W["reason"] == "no_start" and not os.path.exists(S.cfg_path()), dict(AL._W))
            tg.mode["updates"] = "start"
            tg.mode["send"] = 500
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            check("e. the test not delivered -> test_failed, nothing saved (as ALERTS_SETUP)",
                  until(lambda: AL._W["state"] != "waiting_start") and AL._W["reason"] == "test_failed"
                  and not os.path.exists(S.cfg_path()), dict(AL._W))
            tg.mode.pop("send")
            tg.mode["updates"] = 401
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            check("e. Telegram refuses the token mid-wait -> token_refused", until(lambda: AL._W["state"] != "waiting_start")
                  and AL._W["reason"] == "token_refused" and not os.path.exists(S.cfg_path()), dict(AL._W))
            tg.mode["updates"] = "boom"
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            check("e. a crash in the wait (its text holds the token) -> failed, nothing printed", until(
                  lambda: AL._W["state"] != "waiting_start") and AL._W["reason"] == "failed" and not os.path.exists(S.cfg_path()), dict(AL._W))
            tg.mode["updates"] = "empty"
            AL._S["wait_s"] = 30
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            until(lambda: tg.polls >= 2)
            cx = post("/alerts/cancel", {}).json()
            time.sleep(0.15)
            n1 = tg.n("/getUpdates")
            time.sleep(0.15)
            check("e. Cancel: the wait stops polling Telegram, nothing saved", cx == {"ok": True, "state": "cancelled", "reason": "cancelled"}
                  and AL._W["state"] == "cancelled" and tg.n("/getUpdates") == n1 and not os.path.exists(S.cfg_path()), (cx, dict(AL._W)))
            check("e. Cancel with nothing waiting: says so", post("/alerts/cancel", {}).json().get("reason") is None)
            # a second Connect drops the first wait (the first never saves)
            tg.polls = 0
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            g1 = AL._W["gen"]
            tg.mode["updates"] = "start"
            AL._HITS.clear()
            post("/alerts/connect", {"token": TOKEN})
            check("e. a second Connect replaces the first wait: one save, one test", until(lambda: AL._W["state"] == "done")
                  and AL._W["gen"] == g1 + 1 and len(tg.sent) == 1, (dict(AL._W), len(tg.sent)))
            AL._S["wait_s"] = 5

            # g. the test button (TEST_ALERT) + the rate limit
            AL._HITS.clear()
            r = post("/alerts/test", {}).json()
            check("g. Send a test alert = TEST_ALERT: every channel, {channel: true/false} only",
                  set(r.get("channels", {})) == {"telegram", "ntfy", "webpush"} and r["channels"]["telegram"] is True
                  and r["channels"]["ntfy"] is False and r["delivered"] == 2 and r["total"] == 3 and r["ok"] is True
                  and all(isinstance(v, bool) for v in r["channels"].values()), r)
            check("g. the test text is TEST_ALERT's", tg.sent and tg.sent[-1]["text"].startswith(AB.TEST_TITLE))
            AL._HITS.clear()
            codes = [post("/alerts/cancel", {}).status_code for _ in range(9)]
            check("b. rate limit: the 9th press in 10 minutes is refused", codes[:8] == [200] * 8 and codes[8] == 429, codes)
            AL._HITS.clear()

        # f. the secrets
        log = open(AL._S["log"], encoding="utf-8").read()
        st = status()
        allt = "\n".join(texts) + log + out.getvalue() + err.getvalue() + json.dumps(st) + repr(AL._W)
        check("f. the token is in no reply, status, page, log, stdout / stderr or exception text", TOKEN not in allt
              and TOKEN.split(":")[1] not in allt and "/bot" not in log, [x for x in texts if TOKEN in x][:1])
        check("f. the chat id is in no reply, status or the log", CHAT not in allt)
        check("f. the log masks the bot's name (never the whole username)", BOT not in log and "@ol…bot" in log, log[-300:])
        check("f. the log: one line per press, action + ok + a reason word", all({"action", "ok", "why"} <= set(json.loads(x))
                                                                                for x in log.splitlines()), log[-200:])
        words = re.compile(r"^[a-z_]+$")
        check("f. the status = booleans + state words only (no token / chat id / bot name)",
              all(isinstance(v, bool) or v is None or (isinstance(v, str) and words.match(v)) for v in st.values())
              and BOT not in json.dumps(st), st)
        check("f. nothing printed by a crash (no traceback on stderr)", "Traceback" not in err.getvalue(), err.getvalue()[-300:])

        # g. the wires
        from engine import account_box, phone_safety
        check("g. the Add account page links to /alerts/", 'href="/alerts/"' in account_box.PAGE)
        check("g. the ZEUS Safety page links to /alerts/", 'href="/alerts/"' in phone_safety.PAGE)
        src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
        i_ab, i_al, i_st = src.find("# ---- END ADD ACCOUNT BOX ----"), src.find("# ---- PHONE ALERTS BOX ----"), src.find("_static = StaticFiles")
        check("g. server.py installs it right after the ADD ACCOUNT BOX, before the static mount, in a try/except",
              0 < i_ab < i_al < i_st and "_alb.install(app)" in src[i_al:i_st] and "except Exception as _alb_err" in src[i_al:i_st])
        doc = open(os.path.join(ROOT, "docs", "ALERTS.md"), encoding="utf-8").read()
        check("g. docs/ALERTS.md: From your phone (the /alerts/ link)", "From your phone" in doc and ":8444/alerts/" in doc)
        gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
        check("g. the press log is gitignored", "data/alerts_box.jsonl" in gi)
    finally:
        AB._HTTP, AB.STATE_PATH, AB.LOG_PATH, P.app_send = keep
        AL._W["gen"] += 1
        AL._S.update(log=None, wait_s=AL.WAIT_S, sleep=time.sleep)
        AL._HITS.clear()
        for k, v in keep_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        time.sleep(0.05)
        shutil.rmtree(tmp, ignore_errors=True)
    check("g. nothing in the repo tree was written", repo_marks() == before, (before, repo_marks()))
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
