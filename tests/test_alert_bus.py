"""engine/alert_bus.py: ONE send(event) for every alert (owner 2026-11-21). Offline: fake HTTP, temp files, no network.

  a. order: Telegram first; its receipt (message_id) wins, nothing else is called
  b. fallback: Telegram 5xx / timeout -> Discord -> ntfy -> Web Push
  c. dual-send: entries, exits, "bot stopped" reach TWO channels (one bad channel can't hide them)
  d. de-dupe by key, across a restart (the state file)
  e. backoff: 3 retries, 2 / 8 / 30 s
  f. no secret in any file / log / print / tracked file (the branch)
  g. quiet hours: silent for a summary, entries / exits / stopped always ring
  h. the texts (golden)
  i. the .bat chain: CRLF, getpass, nothing echoed; setup + test flows with fakes
  j. the trading loop never waits on it (send returns at once, never raises)
  k. the switch: no setup / ALERTS_OFF = every call site's old path, exactly
  l. "channel X down" warning, at most once an hour
  m. the call sites: push._pc_send, notify.instant_problem, pc_report._bus_alerts
    python -X utf8 -m tests.test_alert_bus        (~2 s)
"""
from __future__ import annotations

import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402
from engine import notify as N  # noqa: E402

RES: list = []
TOKEN = "1234567" + "89:" + "AAH" + "x" * 32          # built at run time: never a token-shaped literal in the repo
CHAT = "987654321"
HOOK = "https://discord.com/api/web" + "hooks/112233445566/" + "Zz" * 20
TOPIC = "olympus-private-" + "q" * 12


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


class Net:
    """Fake HTTP: per channel 'ok' | 500 | 'timeout' | 429; records every call."""
    def __init__(self, **mode):
        self.mode = {"telegram": "ok", "discord": "ok", "ntfy": "ok", **mode}
        self.calls = []
        self.n = 0

    def chan(self, url):
        return "telegram" if "api.telegram.org" in url else "discord" if "discord" in url else "ntfy"

    def __call__(self, method, url, body, headers, timeout):
        ch = self.chan(url)
        self.calls.append((ch, method, url, body, dict(headers or {})))
        m = self.mode.get(ch)
        self.n += 1
        if m == "timeout":
            return 0, "TimeoutError"
        if isinstance(m, int):
            return m, "server error"
        if ch == "telegram":
            return 200, json.dumps({"ok": True, "result": {"message_id": 500 + self.n}})
        if ch == "discord":
            return 200, json.dumps({"id": f"13{self.n:05d}"})
        return 200, json.dumps({"id": f"nt{self.n}"})

    def hit(self):
        return [c[0] for c in self.calls]


class Box:
    def __init__(self, net=None, web=None, tg=True, dc=True):
        self.dir = tempfile.mkdtemp(prefix="alertbus_")
        self.home = os.path.join(self.dir, "home")
        os.makedirs(self.home)
        self.old_env = os.environ.get("OLYMPUS_HOME")
        os.environ["OLYMPUS_HOME"] = self.home
        raw = {}
        if tg:
            raw["telegram"] = {"token": TOKEN, "chat_id": CHAT}
        if dc:
            raw["discord"] = {"webhook": HOOK}
        with open(os.path.join(self.home, "alerts.json"), "w") as fh:
            json.dump(raw, fh)
        with open(os.path.join(self.home, "ntfy.json"), "w") as fh:
            json.dump({"ntfy": "https://ntfy.sh", "topic": TOPIC}, fh)
        self.saved = (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, N.INSTANT_PATH)
        AB.STATE_PATH = os.path.join(self.dir, "data", "alert_bus_sent.json")
        AB.LOG_PATH = os.path.join(self.dir, "data", "alert_bus.jsonl")
        N.INSTANT_PATH = os.path.join(self.dir, "logs", "instant_sent.json")
        self.net = net or Net()
        AB._HTTP = self.net
        self.sleeps = []
        AB._SLEEP = self.sleeps.append
        from engine import push as P
        self.P = P
        self.old_app = P.app_send
        self.web = web if web is not None else {"sent": 1}
        self.web_calls = []
        P.app_send = lambda payload, **k: (self.web_calls.append(payload), self.web)[1]
        AB._PENDING.clear()

    def log(self):
        try:
            return open(AB.LOG_PATH, encoding="utf-8").read()
        except OSError:
            return ""

    def close(self):
        AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, N.INSTANT_PATH = self.saved
        self.P.app_send = self.old_app
        if self.old_env is None:
            os.environ.pop("OLYMPUS_HOME", None)
        else:
            os.environ["OLYMPUS_HOME"] = self.old_env
        shutil.rmtree(self.dir, ignore_errors=True)


ENTRY = {"kind": "entry", "key": "fill:1795050000:x", "account": "Zlarior 50K", "side": "LONG", "qty": 6, "contract": "MNQ",
         "price": 21555.5, "stop": 21537.0, "target": 21600.0, "risk": 222.0, "gain": 534.0, "t": 1795050000}
REPORT = {"kind": "report", "key": "guard:day:2026-11-20", "title": "Day Fri Nov 20: +$310", "body": "Zlarior 50K +$310.",
          "report": True, "notify_type": "daily_summary"}


def part_a(b):
    r = AB.deliver(dict(REPORT))
    check("a. Telegram first: one receipt (message_id), nothing else called", r["ok"] and list(r["receipts"]) == ["telegram"]
          and b.net.hit() == ["telegram"] and re.fullmatch(r"telegram:\d+", r["receipts"]["telegram"]), str(r))
    body = json.loads(b.net.calls[0][3])
    check("a. sent to the owner's chat id only", body["chat_id"] == CHAT and "Day Fri Nov 20" in body["text"])
    check("a. only sendMessage is ever called (inbound never read)", all("/sendMessage" in c[2] for c in b.net.calls if c[0] == "telegram"))


def part_b(b):
    for mode in (500, "timeout", 429):
        b.net.calls.clear()
        b.net.mode["telegram"] = mode
        r = AB.deliver(dict(REPORT, key=f"k{mode}"))
        check(f"b. Telegram {mode} -> Discord takes it", r["ok"] and list(r["receipts"]) == ["discord"] and r["tries"] == 1, str(r))
    b.net.mode.update(telegram=500, discord="timeout")
    b.net.calls.clear()
    r = AB.deliver(dict(REPORT, key="k-nt"))
    check("b. Telegram + Discord down -> ntfy (receipt = ntfy's id)", list(r["receipts"]) == ["ntfy"] and r["receipts"]["ntfy"].startswith("ntfy:nt"), str(r))
    check("b. the ntfy fallback counts in the day's ntfy budget", N.ntfy_today() >= 1)
    b.net.mode.update(ntfy=500)
    r = AB.deliver(dict(REPORT, key="k-wp"))
    check("b. ... -> Web Push last (accepted by the app)", list(r["receipts"]) == ["webpush"] and len(b.web_calls) >= 1, str(r))


def part_c(b):
    r = AB.deliver(dict(ENTRY))
    check("c. entry: Telegram AND Discord", sorted(r["receipts"]) == ["discord", "telegram"], str(r))
    for k in ("exit", "bot_stopped"):
        r = AB.deliver({"kind": k, "key": f"{k}:1", "account": "ATLAS 25K", "usd": -120, "R": -1.0, "reason": "stop", "why": "Bot down"})
        check(f"c. {k}: two channels", len(r["receipts"]) == 2, str(r))
    b.net.mode["discord"] = 500
    b.net.calls.clear()
    r = AB.deliver(dict(ENTRY, key="fill:2"))
    check("c. Discord down: entry still on two channels (Telegram + ntfy)", sorted(r["receipts"]) == ["ntfy", "telegram"], str(r))
    r = AB.deliver(dict(REPORT, key="once"))
    check("c. a summary goes to ONE channel", len(r["receipts"]) == 1)


def part_d(b):
    out1 = AB.send(dict(REPORT, key="dd:1"), wait=True)
    out2 = AB.send(dict(REPORT, key="dd:1"), wait=True)
    importlib.reload(AB)                                   # a restart: new process memory, the same state file
    AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP = os.path.join(b.dir, "data", "alert_bus_sent.json"), os.path.join(b.dir, "data", "alert_bus.jsonl"), b.net, b.sleeps.append
    out3 = AB.send(dict(REPORT, key="dd:1"), wait=True)
    check("d. same key: once, also after a restart", (out1, out2, out3) == ("sent", "dup", "dup"), str((out1, out2, out3)))
    check("d. a new key goes", AB.send(dict(REPORT, key="dd:2"), wait=True) == "sent")
    fails = Net(telegram=500, discord=500, ntfy=500)
    AB._HTTP = fails
    b.web.update(sent=0)
    AB.send(dict(REPORT, key="dd:3", backoff=()), wait=True)
    AB._HTTP = b.net
    b.web.update(sent=1)
    check("d. an undelivered alert is NOT marked sent (the next try goes)", AB.send(dict(REPORT, key="dd:3"), wait=True) == "sent")


def part_e(b):
    b.net.mode.update(telegram=500, discord=500, ntfy=500)
    b.web.update(sent=0)
    r = AB.deliver(dict(REPORT, key="e:1"))
    check("e. backoff 2 / 8 / 30 s, 4 tries in all", b.sleeps == [2, 8, 30] and r["tries"] == 4 and not r["ok"], str((b.sleeps, r)))
    check("e. undelivered -> the failure log", '"undelivered": true' in b.log())
    b.sleeps.clear()
    b.net.mode.update(telegram=500)
    b.net.mode["discord"] = "ok"
    r = AB.deliver(dict(REPORT, key="e:2"))
    check("e. no wait when a fallback delivered", b.sleeps == [] and r["ok"])


def _secretless(s):
    return all(x not in s for x in (TOKEN, CHAT, HOOK, TOPIC, HOOK.rsplit("/", 1)[-1]))


def part_f(b):
    b.net.mode.update(telegram=500, discord=500)
    AB.deliver(dict(REPORT, key="f:1", title=f"leak {TOKEN} {HOOK}", body=f"chat {CHAT} topic {TOPIC}"))
    check("f. failure log: no token / webhook / chat id / topic", b.log() and _secretless(b.log()), b.log()[:200])
    check("f. redact() strips them from any text", _secretless(AB.redact(f"x {TOKEN} {HOOK} {CHAT} {TOPIC} /bot{TOKEN}/x", AB.config())))
    buf = io.StringIO()
    with redirect_stdout(buf):
        from tools import alerts_setup as S
        importlib.reload(S)
        S.test(cfg=AB.config())
        S.status()
    check("f. TEST_ALERT / status print no secret", _secretless(buf.getvalue()), buf.getvalue()[:300])
    files = [os.path.join(b.dir, "data", f) for f in os.listdir(os.path.join(b.dir, "data"))]
    check("f. no secret in the state file", all(_secretless(open(f, encoding="utf-8").read()) for f in files if f.endswith(".json")))
    try:
        listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.split()
    except Exception:  # noqa: BLE001
        listed = []
    tok_rx, hook_rx = re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"), re.compile(r"discord(?:app)?\.com/api/webhooks/\d{17,20}/[A-Za-z0-9_-]{60,}")
    bad = []
    for f in listed:
        if not f.endswith((".py", ".json", ".bat", ".ps1", ".md", ".js", ".yml", ".txt", ".html")):
            continue
        try:
            t = open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if tok_rx.search(t) or hook_rx.search(t):
            bad.append(f)
    check("f. no real-looking bot token / webhook in any tracked file (the branch)", listed and not bad, ",".join(bad[:5]))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("f. the bus's state + log are gitignored", "data/alert_bus.jsonl" in gi and "data/alert_bus_sent.json" in gi)


def part_g(b):
    s = N.merge({"quiet_hours": {"from": "00:00", "to": "23:59"}})
    now = time.time()
    check("g. a summary in quiet hours: silent", AB.is_silent({"kind": "daily"}, now=now, s=s))
    check("g. entries / exits / stopped always ring", not any(AB.is_silent({"kind": k}, now=now, s=s) for k in AB.DUAL))
    check("g. ring_in_quiet_hours kinds ring (pc_silent)", not AB.is_silent({"kind": "pc_silent"}, now=now, s=s))
    AB.deliver(dict(REPORT, key="g:1", kind="daily"), now=now, s=s)
    AB.deliver(dict(ENTRY, key="g:2"), now=now, s=s)
    tg = [json.loads(c[3]) for c in b.net.calls if c[0] == "telegram"]
    check("g. Telegram: disable_notification on the summary only", [x["disable_notification"] for x in tg] == [True, False], str(tg))
    b.net.mode["telegram"] = 500
    AB.deliver(dict(REPORT, key="g:3", kind="daily"), now=now, s=s)
    dc = [json.loads(c[3]) for c in b.net.calls if c[0] == "discord"]
    day = [x for x in dc if "Day Fri Nov 20" in x["content"]]
    check("g. Discord: silent flag (4096) in quiet hours", day and day[-1].get("flags") == 4096, str(dc))
    s2 = N.merge({"quiet_hours": {"from": "00:00", "to": "00:00"}})
    check("g. outside quiet hours nothing is silent", not AB.is_silent({"kind": "daily"}, now=now, s=s2))


GOLD = {
    "entry": ("Zlarior 50K LONG opened, 6 MNQ @ 21,555.50",
              "stop 21,537.00 · target 21,600.00 · risk $222 · +$534 at target · 8:00 PM ET."),
    "exit": ("Zlarior 50K closed LONG +$312 (+1.6R, target)", "today +$312, balance $49,505, $3,495 to pass."),
    "exit_loss": ("ATLAS 25K closed SHORT -$120 (-1.0R, stop)", "Trade closed."),
    "pc_silent": ("PC silent", "Your PC has not reported since 8:00 PM ET (35 min). Check it: STOP BOT, then START BOT."),
    "bot_stopped": ("Bot stopped: Zlarior", "Bot down in trading hours. Open the PC and press START BOT."),
    "dll_near": ("Zlarior 50K: daily loss limit 80% used", "$200 left of $1,000. The bot sizes down; no hand trades today."),
    "dd_near": ("ATLAS 25K: max drawdown 80% used",
                "$200 left of $1,000. One more bad day can end this account: trade small or not at all."),
    "seven_day": ("ATLAS 25K: day 5 of 7 with no trade",
                  "MFFU's 7-day rule closes an account with no trade for 7 days. Trade by Wed Nov 25 (the bot will if it gets a setup)."),
    "seven_day6": ("ATLAS 25K: day 6 of 7 with no trade",
                   "MFFU's 7-day rule closes an account with no trade for 7 days. Trade by Wed Nov 25: tomorrow is the last day."),
    "payout_ready": ("ATLAS 25K: payout ready, $1,000", "Balance $2,100 (the plan: request $1,000 at $2,100). Request it on MFFU today."),
    "hedge_risk": ("Hand trade: wait", "Not flat: ATLAS 25K. A hand trade now can hedge against the bot and break MFFU's rules. "
                   "Wait until EVERY account is flat."),
    "daily": ("Day Fri Nov 20: +$190", "Zlarior 50K: +$310 today, $2,690 to pass\nATLAS 25K: -$120 today"),
    "channel_down": ("Alerts: Telegram is not delivering", "Telegram answered 500. Your alerts are coming here instead. "
                     "Run TEST_ALERT on the PC to check."),
}


def part_h(b):
    T = 1795050000
    got = {
        "entry": AB.text(ENTRY),
        "exit": AB.text({"kind": "exit", "account": "Zlarior 50K", "side": "LONG", "usd": 312, "R": 1.6, "reason": "target",
                         "after": "today +$312, balance $49,505, $3,495 to pass"}),
        "exit_loss": AB.text({"kind": "exit", "account": "ATLAS 25K", "side": "SHORT", "usd": -120, "R": -1.0, "reason": "stop"}),
        "pc_silent": AB.text({"kind": "pc_silent", "since": T, "minutes": 35}),
        "bot_stopped": AB.text({"kind": "bot_stopped", "bot": "Zlarior", "why": "Bot down"}),
        "dll_near": AB.text({"kind": "dll_near", "account": "Zlarior 50K", "limit": 1000, "left": 200}),
        "dd_near": AB.text({"kind": "dd_near", "account": "ATLAS 25K", "limit": 1000, "left": 200}),
        "seven_day": AB.text({"kind": "seven_day", "account": "ATLAS 25K", "day": 5, "deadline": "Wed Nov 25"}),
        "seven_day6": AB.text({"kind": "seven_day", "account": "ATLAS 25K", "day": 6, "deadline": "Wed Nov 25"}),
        "payout_ready": AB.text({"kind": "payout_ready", "account": "ATLAS 25K", "amount": 1000, "balance": 2100}),
        "hedge_risk": AB.text({"kind": "hedge_risk", "not_flat": AB.hand_trade_check({"Zlarior 50K": 0, "ATLAS 25K": -2})["not_flat"]}),
        "daily": AB.text({"kind": "daily", "day": "Fri Nov 20", "rows": [{"account": "Zlarior 50K", "usd": 310, "to_pass": 2690},
                                                                         {"account": "ATLAS 25K", "usd": -120}]}),
        "channel_down": AB.text({"kind": "channel_down", "channel": "telegram", "why": "Telegram answered 500"}),
    }
    for k, want in GOLD.items():
        check(f"h. text {k}", got[k] == want, f"{got[k]!r}")
    check("h. TEST text = the owner's words", AB.text({"kind": "test", "title": AB.TEST_TITLE, "body": AB.TEST_BODY})[0]
          == "TEST: Zlarior 50K LONG opened, 6 MNQ @ 21,555.50" and "stop 21,574.00, risk $228" in AB.TEST_BODY)
    hc = AB.hand_trade_check
    check("h. hand trade only when EVERY account is flat", hc({"A": 0, "B": 0})["ok"] and not hc({"A": 0, "B": 1})["ok"]
          and not hc({"A": 0, "B": None})["ok"] and not hc({})["ok"] and not hc([{"name": "A", "qty": 0}, {"name": "B"}])["ok"])
    p = {"kind": "fill", "key": "fill:1795050000:acct", "account": "MFFUEVBLDR123456", "side": "LONG", "qty": 4, "entry": 21034.25,
         "stop": 21012.0, "target": 21090.5, "t": 1795050000, "contract": "MNQ", "nm": "Zlarior 50K"}
    ev = AB.from_trade(p, "entry")
    t, body = AB.text(ev)
    check("h. from a real fill payload: name, side, qty, price, stop, target, $ risk", t.startswith("Zlarior 50K LONG opened, 4 MNQ @ 21,034.25")
          and "stop 21,012.00" in body and "target 21,090.50" in body and "risk $178" in body, f"{t} / {body}")
    check("h. account ids never leave whole", "123456" not in t + body and "123456" not in json.dumps({k: v for k, v in ev.items() if k != "web"}))
    q = {"kind": "outcome", "key": "out:1795050000:acct", "account": "MFFUEVBLDR123456", "side": "LONG", "usd": 312.0, "R": 1.6,
         "exit": "TARGET", "t": 1795051000, "nm": "Zlarior 50K", "qty": 4}
    t, body = AB.text(AB.from_trade(q, "exit"))
    check("h. from a real outcome payload: +$, R, reason", t.startswith("Zlarior 50K closed LONG +$312 (+1.6R, target)"), t)


def part_i(b):
    for name, arg in (("ALERTS_SETUP.bat", "setup"), ("TEST_ALERT.bat", "test"), ("ALERTS_OFF.bat", "off"), ("ALERTS_ON.bat", "on")):
        raw = open(os.path.join(ROOT, name), "rb").read()
        lf = raw.count(b"\n")
        check(f"i. {name}: CRLF, calls alerts_setup.py {arg}", lf and raw.count(b"\r\n") == lf
              and f"tools\\alerts_setup.py {arg}".encode() in raw and b"echo on" not in raw.lower())
    src = open(os.path.join(ROOT, "tools", "alerts_setup.py"), encoding="utf-8").read()
    check("i. the token / webhook are read with getpass (hidden), never input()",
          "ask=getpass.getpass" in src and src.count("getpass.getpass") >= 3 and 'input("Bot' not in src and 'input("Webhook' not in src)
    check("i. the bus itself never reads inbound messages (no getUpdates)", "getUpdates" not in open(AB.__file__, encoding="utf-8").read())
    from tools import alerts_setup as S
    os.remove(os.path.join(b.home, "alerts.json"))
    out = []
    asked = iter([TOKEN, HOOK])
    r = S.setup(ask_choice=lambda _p: "3", ask=lambda _p: next(asked), say=out.append, wait=lambda tok, say=None: CHAT)
    saved = json.load(open(os.path.join(b.home, "alerts.json")))
    check("i. setup 3 = both saved in OLYMPUS_HOME/alerts.json", r == 0 and saved["telegram"]["chat_id"] == CHAT
          and saved["discord"]["webhook"] == HOOK)
    check("i. setup sent a test to each", sum(1 for c in b.net.calls if c[0] in ("telegram", "discord")) == 2)
    check("i. setup printed no secret", _secretless("\n".join(out)), "\n".join(out)[:300])
    out.clear()
    r = S.setup(ask_choice=lambda _p: "1", ask=lambda _p: "not a token", say=out.append, wait=lambda *a, **k: CHAT)
    check("i. a wrong token: nothing saved, said plainly", r == 1 and any("does not look like" in x for x in out))
    # getUpdates polling: only a private /start counts; the offset clears the queue
    fake = []

    def h(method, url, body, headers, timeout):
        fake.append(url)
        if "offset=" in url and "timeout=0" in url:
            return 200, json.dumps({"ok": True, "result": []})
        return 200, json.dumps({"ok": True, "result": [
            {"update_id": 7, "message": {"chat": {"id": -100, "type": "group"}, "text": "/start"}},
            {"update_id": 8, "message": {"chat": {"id": int(CHAT), "type": "private"}, "text": "/start"}}]})
    AB._HTTP = h
    cid = S.wait_chat_id(TOKEN, say=lambda *_: None, wait_s=5, sleep=lambda *_: None)
    AB._HTTP = b.net
    check("i. /start captured from the private chat only, queue cleared", cid == CHAT and any("offset=9" in u for u in fake))
    out.clear()
    S.switch(False, say=out.append)
    off = AB.active()
    S.switch(True, say=out.append)
    check("i. ALERTS_OFF / ALERTS_ON flip the bus", not off and AB.active())


def part_j(b):
    import threading
    slow = threading.Event()

    def slow_http(*a):
        slow.wait(3)
        return 200, json.dumps({"ok": True, "result": {"message_id": 1}})
    AB._HTTP = slow_http
    t0 = time.perf_counter()
    r = AB.send(dict(ENTRY, key="j:1"))
    dt_ = time.perf_counter() - t0
    check("j. send() returns at once while the network hangs", r == "queued" and dt_ < 0.2, f"{r} {dt_:.3f}s")
    slow.set()
    AB.drain(5)

    def boom(*a):
        raise RuntimeError("network on fire")
    AB._HTTP = boom
    try:
        r1 = AB.send(dict(ENTRY, key="j:2"))
        r2 = AB.send(None)
        r3 = AB.send({"kind": "entry", "key": object()})
        AB.drain(5)
        ok = r1 == "queued" and r2 == "bad"
    except Exception:  # noqa: BLE001
        ok = False
    check("j. send() never raises (bad events, a failing network)", ok)
    AB._HTTP = b.net


def part_k(b):
    from engine import push as P
    p = {"kind": "fill", "key": "fill:1795060000:k", "account": "MFFUEVBLDR123456", "side": "LONG", "qty": 2, "entry": 21000.0,
         "stop": 20990.0, "target": 21050.0, "t": 1795060000}
    check("k. set up: push._bus_send takes a real entry", (P._bus_send(dict(p)) or {}).get("bus") == "queued")
    AB.drain(5)
    check("k. ... and records it so the 15-minute report skips its copy", N.instant_sent(1795060000))
    check("k. paper / BLITZ never go through the bus (old path)", P._bus_send(dict(p, account="Paper1", key="fill:3")) is None)
    open(os.path.join(b.home, AB.OFF_NAME), "w").close()
    check("k. switch file: bus off -> old path exactly", not AB.active() and P._bus_send(dict(p, key="fill:4")) is None)
    os.remove(os.path.join(b.home, AB.OFF_NAME))
    os.environ["LE_ALERT_BUS"] = "0"
    check("k. LE_ALERT_BUS=0 also off", not AB.active())
    os.environ.pop("LE_ALERT_BUS")
    os.remove(os.path.join(b.home, "alerts.json"))
    check("k. no Telegram / Discord set up -> off (nothing changes before setup)", not AB.active() and AB.send(dict(REPORT, key="k:9")) == "off")
    n_calls = len(b.net.calls)
    r = N.instant_problem({"key": "cond:bot_down:1", "code": "bot_down", "title": "ZEUS not polling", "body": "x"},
                          cfg={"ntfy": "https://ntfy.sh", "topic": TOPIC}, poster=lambda *a: True)
    check("k. bus off: instant_problem takes its old ntfy post", r == "sent" and len(b.net.calls) == n_calls)


def part_l(b):
    b.net.mode["telegram"] = 500
    t0 = 1795050000
    AB.deliver(dict(REPORT, key="l:1"), now=t0)
    AB.deliver(dict(REPORT, key="l:2"), now=t0 + 600)
    AB.deliver(dict(REPORT, key="l:3"), now=t0 + 3700)
    warns = [json.loads(c[3])["content"] for c in b.net.calls if c[0] == "discord" and "not delivering" in json.loads(c[3])["content"]]
    check("l. 'Telegram is not delivering' via Discord, at most once an hour", len(warns) == 2, str(len(warns)))
    check("l. the warning names no secret", all(_secretless(w) for w in warns))


def part_m(b):
    r = N.instant_problem({"key": "cond:bot_down:9", "code": "bot_down", "cond": "bot_down", "title": "ZEUS not polling",
                           "body": "The bot stopped polling at 10:02 ET."})
    AB.drain(5)
    hits = b.net.hit()
    check("m. instant_problem -> the bus: bot down on two channels", r == "sent" and hits.count("telegram") == 1 and hits.count("discord") == 1, str(hits))
    check("m. ... recorded so the 15-minute report skips its copy", N.problem_dup({"key": "cond:bot_down:99"}))
    from tools import pc_report as R
    rec, st = {"errors": []}, {"seen": {"open:lit:1": 1}, "guard": {"sent": {}}}
    msgs = [{"key": "guard:day:2026-11-20", "title": "Day Fri Nov 20: +$310", "body": "Zlarior 50K +$310."}]
    out = R._bus_alerts(msgs, rec, {"t": 1795050000}, st)
    check("m. pc_report alerts -> the bus (Telegram), counted as sent", out is True and rec.get("sent_n") == 1 and not rec["errors"]
          and "telegram" in rec["alerts_last"]["via"], str(rec))
    b.net.mode.update(telegram=500, discord=500, ntfy=500)
    b.web.update(sent=0)
    rec, st = {"errors": []}, {"seen": {"open:lit:5": 1}, "guard": {"sent": {}}}
    R._bus_alerts([{"key": "open:lit:5", "title": "x", "body": "y", "backoff": ()}], rec, {"t": 1}, st)
    check("m. pc_report: undelivered -> forgotten, the next run retries", "open:lit:5" not in st["seen"] and rec["errors"])
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import pc_silent_check as PS
    env = {"LE_TG_TOKEN": TOKEN, "LE_TG_CHAT": CHAT}
    check("m. the cloud monitor: Telegram from repo secrets", PS._bus(env) is not None and PS._bus({}) is None)
    c = PS._bus_cfg(AB, env)
    check("m. the cloud uses Telegram / Discord only (ntfy stays its own post)", c["telegram"] and not c["ntfy"] and not c["webpush"])


def part_n(b):
    from tests import test_pc_guard as G
    t = G.at(2026, 11, 16, 10)
    _s, m = G.run({}, G.snap(t, {"lit": G.lit(quiet_days=6), "atlas": G.atlas(position={"side": "SHORT"})}))
    k = [x for x in m if x["key"].startswith("guard:quiet:lit")]
    check("n. 7-day rule day 6, ATLAS still in a trade: NO 'place 1 MNQ by hand', says wait (every account flat)",
          k and "place 1 MNQ by hand" not in k[0]["body"] and "Do NOT place a hand trade" in k[0]["body"], str(k))
    _s, m = G.run({}, G.snap(t, {"lit": G.lit(quiet_days=6), "atlas": G.atlas()}))
    k = [x for x in m if x["key"].startswith("guard:quiet:lit")]
    check("n. every account flat: the hand-trade advice stays, and the 7-day alert is account_status (on, rings)",
          k and "place 1 MNQ by hand" in k[0]["body"] and k[0].get("kind") == "account_status", str(k))


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g, part_h, part_i, part_j, part_k, part_l, part_m, part_n):
        b = Box()
        try:
            f(b)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
        finally:
            AB.drain(5)
            b.close()
    n, ok = len(RES), sum(RES)
    print(f"\nalert bus: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
