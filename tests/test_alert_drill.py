"""END-TO-END ALERT DRILL (lead 2026-11-21): every money-critical event, from its REAL producer to the phone, with fakes only
(no network, temp files). Three set-ups:
  telegram   ALERTS_SETUP done (Telegram) + the private ntfy topic: engine/alert_bus, Telegram first, dual events on 2 channels
  ntfy       no Telegram / Discord yet (today's PC): the old path (private ntfy + the Olympus app)
  off        Telegram set up but tools/bat/ALERTS_OFF.bat: the old path exactly, Telegram never called
Events (producer -> what reaches the phone):
  1 trade entry        push._pc_send(fill)                         'Zlarior 50K LONG opened, 4 MNQ @ 21,034.25 ... risk $178'
  2 exit with $        push._pc_send(outcome)                      'closed LONG +$312 (+1.6R, target)'
  3 the report's copy  pc_report-style "open:" / "close:" + notify.apply   -> dropped (never twice)
  4 missed trade       fill_audit._missed_problem -> notify.instant_problem   'MISSED TRADE · Zlarior'
  5 bot stopped        fast_alarm.FastAlarm._start("bot_stopped")  'Bot stopped' (rings at night)
  6 PC silent          tools/pc_silent_check.run (the cloud)       'PC stopped reporting'
  7 7-day day 5 / 6    tools/pc_guard (quiet bot) -> notify.apply -> the report's delivery
  8 payout ready       lifecycle texts ('PAYOUT READY') at the plan line ($1,000 at $2,100) -> the report's delivery
  9 hedge blocked      push._pc_send(text_payload risk "hedge_blocked:")
 10 price-limit block  push._pc_send(outcome exit "PRICE LIMIT")    'MFFU price-limit rule'
 11 keep-alive placed / failed / closed   notify.instant_problem(ka:entry / ka:refused) + the close's trade alert
Each: arrives (the right channel first), exactly once per channel, the words + $; quiet hours per notify_settings.json.
    python -X utf8 -m tests.test_alert_drill        (~3 s)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import alert_bus as AB  # noqa: E402
from engine import notify as N  # noqa: E402
from engine import push as P  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []
TOKEN = "1234567" + "89:" + "AAH" + "d" * 32
CHAT = "4242424242"
TOPIC = "olympus-drill-" + "z" * 10
DAY = dt.datetime(2026, 11, 17, 10, 31, tzinfo=ET).timestamp()        # a Tuesday, entry hours
NIGHT = dt.datetime(2026, 11, 17, 2, 5, tzinfo=ET).timestamp()        # inside the 23:00-07:00 quiet hours
ACCT = "MFFUEVBLDR" + "123456"


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:400]}]" if detail and not ok else ""))


class Phone:
    """Every delivery from every route, as the phone would show it: (channel, text, silent)."""
    def __init__(self):
        self.got = []
        self.n = 0

    # the bus's HTTP and the report's / cloud's ntfy posts
    def http(self, method, url, body=None, headers=None, timeout=10):
        headers = headers or {}
        self.n += 1
        if method == "GET":
            return 200, ""
        if "api.telegram.org" in url:
            j = json.loads(body)
            self.got.append(("telegram", j["text"], bool(j.get("disable_notification"))))
            return 200, json.dumps({"ok": True, "result": {"message_id": 100 + self.n}})
        if "discord" in url:
            j = json.loads(body)
            self.got.append(("discord", j["content"], j.get("flags") == 4096))
            return 200, json.dumps({"id": str(9000 + self.n)})
        txt = f"{headers.get('Title', '')}\n{(body or b'').decode('utf-8')}"
        self.got.append(("ntfy", txt, str(headers.get("Priority")) in ("low", "min", "1", "2")))
        return 200, json.dumps({"id": f"n{self.n}"})

    def post(self, base, topic, msg, timeout=8):            # notify._post (the old instant ntfy path)
        self.got.append(("ntfy", f"{msg['title']}\n{msg['body']}", msg.get("priority") in ("low", "min")))
        return True

    def app(self, payload, **kw):                            # push.app_send (the Olympus app)
        self.got.append(("app", f"{payload.get('title', '')}\n{payload.get('body', '')}", bool(payload.get("silent"))))
        return {"sent": 1}

    def mark(self):
        return len(self.got)

    def since(self, m):
        return self.got[m:]


class Box:
    def __init__(self, mode):
        self.mode = mode
        self.dir = tempfile.mkdtemp(prefix=f"drill_{mode}_")
        self.home = os.path.join(self.dir, "home")
        os.makedirs(self.home)
        self.env_old = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "LE_ALERT_BUS", "LE_PUSH_EXTRA")}
        os.environ["OLYMPUS_HOME"] = self.home
        os.environ.pop("LE_ALERT_BUS", None)
        os.environ.pop("LE_PUSH_EXTRA", None)
        if mode in ("telegram", "off"):
            json.dump({"telegram": {"token": TOKEN, "chat_id": CHAT}}, open(os.path.join(self.home, "alerts.json"), "w"))
        if mode == "off":
            open(os.path.join(self.home, AB.OFF_NAME), "w").close()
        json.dump({"ntfy": "https://ntfy.sh", "topic": TOPIC}, open(os.path.join(self.home, "ntfy.json"), "w"))
        self.phone = Phone()
        self.saved = (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, N.INSTANT_PATH, N._post, P.app_send, P._PC["notifier"],
                      getattr(P, "TRADE_LOG", None))
        AB.STATE_PATH = os.path.join(self.dir, "data", "alert_bus_sent.json")
        AB.LOG_PATH = os.path.join(self.dir, "data", "alert_bus.jsonl")
        AB._HTTP = self.phone.http
        AB._SLEEP = lambda s: None
        AB._PENDING.clear()
        N.INSTANT_PATH = os.path.join(self.dir, "logs", "instant_sent.json")
        N._post = self.phone.post
        P.app_send = self.phone.app
        P._PC["notifier"] = P.Notifier(path=os.path.join(self.dir, "data", "push_sent.json"), relay=None, src="pc")

    def close(self):
        AB.drain(5)
        (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, N.INSTANT_PATH, N._post, P.app_send, P._PC["notifier"], _tl) = self.saved
        for k, v in self.env_old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ the producers
def fill(t, key_sfx="acct", **kw):
    return {"kind": "fill", "key": f"fill:{int(t)}:{key_sfx}", "account": ACCT, "nm": "Zlarior 50K", "side": "LONG", "qty": 4,
            "entry": 21034.25, "stop": 21012.0, "target": 21090.5, "t": int(t), "contract": "MNQ", "src": "pc", **kw}


def outcome(t, usd, why, R=None, key_sfx="acct", **kw):
    return {"kind": "outcome", "key": f"out:{int(t)}:{key_sfx}", "account": ACCT, "nm": "Zlarior 50K", "side": "LONG", "qty": 4,
            "usd": usd, "R": R, "exit": why, "t": int(t) + 1500, "src": "pc", **kw}


def report_deliver(b, msgs, now):
    """The 15-minute report's alert step (tools/pc_report.run_once): notify.apply, then the bus or the old ntfy loop."""
    from tools import pc_report as R
    msgs = N.apply(msgs, now)
    rec, st = {"errors": []}, {"seen": {}, "guard": {"sent": {}}}
    if R._bus_alerts(msgs, rec, {"t": now}, st) is None:
        for m in msgs:
            R.ntfy_post("https://ntfy.sh", TOPIC, m["body"], title=m["title"], priority=m.get("priority"), tags=m.get("tags"),
                        http=b.phone.http)
    return msgs


def run(b, fn):
    m = b.phone.mark()
    fn()
    AB.drain(10)
    return b.phone.since(m)


def chans(got):
    return [g[0] for g in got]


def expect(b, name, got, words, dual=False, trade=False):
    """The channel order per set-up, once per channel, and the words."""
    c = chans(got)
    if b.mode == "telegram":
        want_first = "telegram"
        ok_ch = c and c[0] == "telegram" and (len(c) == 2 if dual else len(c) == 1) and len(set(c)) == len(c)
    else:
        want_first = "app" if trade else "ntfy"
        ok_ch = bool(c) and "telegram" not in c and len(set(c)) == len(c) and (set(c) == {"app", "ntfy"} if trade else c == ["ntfy"])
    check(f"[{b.mode}] {name}: arrives ({want_first} first), once per channel{' , on 2 channels' if dual and b.mode == 'telegram' else ''}",
          ok_ch, c)
    miss = [w for w in words if not all(w in g[1] for g in got)]
    check(f"[{b.mode}] {name}: the words {words}", got and not miss, (miss, [g[1] for g in got]))


def drill(mode):
    b = Box(mode)
    try:
        t = DAY
        # 1 entry, 3a the report's copy of it
        got = run(b, lambda: P._pc_send(fill(t)))
        expect(b, "1 trade entry", got, ["Zlarior 50K", "LONG", "21,034.25", "21,012.00", "$178"], dual=True, trade=True)
        got = run(b, lambda: report_deliver(b, [{"key": f"open:lit:{int(t)}", "title": "Zlarior 50K LONG opened | risk $178",
                                                  "body": "x", "entry_t": t}], t + 900))
        check(f"[{mode}] 3 the 15-minute report's copy of that entry: dropped (never twice)", got == [], chans(got))
        # 2 exit with $, 3b its report copy
        got = run(b, lambda: P._pc_send(outcome(t, 312.0, "TARGET", R=1.6)))
        expect(b, "2 exit with $", got, ["Zlarior 50K", "+$312", "target"], dual=True, trade=True)
        got = run(b, lambda: report_deliver(b, [{"key": f"close:lit:{int(t)}", "title": "Zlarior 50K closed +$312", "body": "x",
                                                  "entry_t": t}], t + 1800))
        check(f"[{mode}] 3 the report's copy of that exit: dropped", got == [], chans(got))
        got = run(b, lambda: P._pc_send(fill(t)))
        check(f"[{mode}] 1 the same entry again (a restart / a second route): nothing", got == [], chans(got))
        # 4 missed trade
        from engine import fill_audit as FA
        mp = FA._missed_problem({"key": f"exec:miss:{int(t) + 60}", "title": "Missed trade",
                                 "body": "LIT's model took LONG 4 MNQ at 10:32 ET; the bot did not route it (guards: clock)."})
        got = run(b, lambda: N.instant_problem(mp, now=t + 60))
        expect(b, "4 missed trade", got, ["MISSED TRADE", "did not route"])
        # 5 bot stopped in market hours
        from engine import fast_alarm as F
        got = run(b, lambda: F.FastAlarm(clock=lambda: t)._start("bot_stopped", "The bot is not running in the entry hours "
                                                                 "(autostart says it was). START BOT on the PC.", t + 120))
        expect(b, "5 bot stopped", got, ["Bot stopped", "START BOT"], dual=True)
        # 6 PC silent (the cloud monitor)
        got = run(b, lambda: pc_silent(b, t + 3000))
        cs = chans(got)
        if mode == "telegram":
            check("[telegram] 6 PC silent (cloud): Telegram from the repo secrets, once", cs == ["telegram"], cs)
        else:
            check(f"[{mode}] 6 PC silent (cloud): the private ntfy topic, once; Telegram never", cs == ["ntfy"], cs)
        check(f"[{mode}] 6 PC silent: the words", got and "stopped reporting" in got[0][1].lower(), [g[1] for g in got])
        # 7 the 7-day rule: day 5 (real eval: account_status, on) and day 6 (the hand-trade line)
        from tests import test_pc_guard as G
        g0 = G.at(2026, 11, 17, 10)
        for qd, words in ((5, ["no trade for 5 days", "7 days"]), (6, ["no trade for 6 days", "place 1 MNQ by hand"])):
            g0 = G.at(2026, 11, 12 + qd, 10)                 # day 5 on Tue, day 6 on Wed (one push per account and day)
            _s, gm = G.run({}, G.snap(g0, {"lit": G.lit(quiet_days=qd), "atlas": G.atlas()}))
            q = [x for x in gm if ":quiet:" in x["key"]]
            got = run(b, lambda q=q: report_deliver(b, q, g0))
            expect(b, f"7 7-day rule day {qd}", got, words)
        # 8 payout ready at the plan line
        from engine import lifecycle as L
        title, body = L.texts("payout_ready", "ATLAS 25K", {"balance": 2100.0, "payout": {"amount": 1000.0, "to_you": 800.0}})
        got = run(b, lambda: report_deliver(b, [{"key": "life:payout_ready:atlas:-:c1", "title": title, "body": body,
                                                  "priority": "default", "tags": "moneybag"}], t))
        expect(b, "8 payout ready ($1,000 at $2,100)", got, ["$1,000"])
        # 9 hedge blocked
        hp = P.text_payload("PC", "risk", "HEDGE BLOCKED: ATLAS close not confirmed", "LIT's entry at 10:31 ET was skipped: "
                            "account B's opposite position was not confirmed flat.", key=f"hedge_blocked:{int(t)}", t=int(t))
        got = run(b, lambda: P._pc_send(hp))
        expect(b, "9 hedge blocked", got, ["HEDGE BLOCKED", "skipped"], dual=True)
        # 10 price-limit block (a funded account flattened by MFFU's 2% rule)
        got = run(b, lambda: P._pc_send(outcome(t + 7200, -64.0, "PRICE LIMIT", R=-0.3, key_sfx="pl")))
        expect(b, "10 price-limit block", got, ["-$64", "price-limit"], dual=True, trade=True)
        # 11 keep-alive: placed, failed, closed (the close = its trade alert + its own line: ONE alert, not two)
        ka = {"key": f"ka:entry:lit:{int(t)}", "code": "keepalive", "soft": True, "tags": "repeat", "bot": "lit",
              "title": "Keep-alive on Zlarior 50K: BUY 1 MNQ @ 21,040.00",
              "body": "MFFU's 7-day rule: no trade for 5 days (MFFU's limit 7). Stop 21,030.00, target 21,050.00 (10 points, $20). "
                      "The bot closes it in about 5 min: about -$2.40, at most -$23."}
        got = run(b, lambda: N.instant_problem(ka, now=t))
        expect(b, "11 keep-alive placed", got, ["Keep-alive on Zlarior 50K", "1 MNQ", "$23"])
        kf = {"key": "ka:refused:lit:2026-11-17", "code": "keepalive", "title": "Keep-alive on Zlarior 50K did not go through",
              "body": "your pause blocks it. Place 1 MNQ by hand on this account before 16:05 ET (in and out, about -$2.40)."}
        got = run(b, lambda: N.instant_problem(kf, now=t))
        expect(b, "11 keep-alive failed", got, ["did not go through", "by hand", "16:05"])
        ko = outcome(t + 400, -2.5, "TIME", key_sfx="ka")
        ko.update(title="Keep-alive on Zlarior 50K: LONG closed", body="-$2.50 (expected about -$2.40, at most -$23). "
                  "MFFU's 7-day clock restarts today.", dup_of=None)
        kr = {"key": f"ka:result:lit:{int(t) + 400}", "code": "keepalive", "soft": True, "tags": "white_check_mark", "bot": "lit",
              "title": "Keep-alive on Zlarior 50K: closed LONG about -$2.50", "dup_of": ko["key"],
              "body": "1 MNQ, time (expected about -$2.40, at most -$23). MFFU's 7-day clock restarts from 2026-11-17."}
        got = run(b, lambda: (P._pc_send(ko), N.instant_problem(kr, now=t + 400)))
        cs = chans(got)
        if mode == "telegram":
            check("[telegram] 11 keep-alive closed: ONE alert (its trade exit), never a second Telegram line",
                  cs.count("telegram") == 1 and len(cs) == 2 and len(set(cs)) == 2, cs)
        else:
            check(f"[{mode}] 11 keep-alive closed: the old path (app + ntfy exit + its ntfy line), as before",
                  "telegram" not in cs and "app" in cs and "ntfy" in cs, cs)
        check(f"[{mode}] 11 keep-alive closed: -$2.50 said", any("$2.5" in g[1] for g in got), [g[1] for g in got])
        # quiet hours (the repo's notify_settings.json: 23:00-07:00 ET)
        quiet_part(b)
        if mode == "off":
            check("[off] Telegram was never called (ALERTS_OFF = the old path exactly)", "telegram" not in chans(b.phone.got))
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"[{mode}] drill raised {e.__class__.__name__}: {e}", False)
    finally:
        b.close()


def pc_silent(b, now):
    import pc_silent_check as PS
    env = {"LE_NTFY_TOPIC": TOPIC}
    if b.mode in ("telegram", "off"):
        env.update(LE_TG_TOKEN=TOKEN, LE_TG_CHAT=CHAT)
    if b.mode == "off":
        env["LE_ALERT_BUS"] = "0"
    out = os.path.join(b.dir, "pcw")
    old = PS.http_post
    PS.http_post = lambda url, body, headers, timeout=20: b.phone.http("POST", url, body, headers)
    try:
        return PS.run(out, now=now, env=env, get=lambda url, timeout=20, limit=0: (200, ""), post=None,
                      hb={"present": True, "t": now - 35 * 60}, feed={"ntfy": "https://ntfy.sh", "topic": "le-status-x"},
                      say=lambda *_: None)
    finally:
        PS.http_post = old


def quiet_part(b):
    import time as _time
    real = _time.time
    _time.time = lambda: NIGHT + 30                          # the producers read the wall clock: it is 02:05 ET now
    try:
        _quiet_part(b)
    finally:
        _time.time = real


def _quiet_part(b):
    """At 02:05 ET: an entry / exit arrive WITHOUT sound (the owner's TRADE_RING yes / no is open), a summary too; "bot
    stopped", a hedge block and a non-soft problem ring; a soft keep-alive line is silent like on the old path."""
    t = NIGHT
    got = run(b, lambda: P._pc_send(fill(t, key_sfx="n")))
    check(f"[{b.mode}] quiet: a 02:05 ET entry arrives without sound on every channel", got and all(g[2] for g in got), got)
    from engine import fast_alarm as F
    got = run(b, lambda: F.FastAlarm(clock=lambda: t)._start("bot_stopped", "Bot stopped at night.", t))
    check(f"[{b.mode}] quiet: 'bot stopped' rings", got and not any(g[2] for g in got), got)
    ka = {"key": f"ka:entry:lit:{int(t)}", "code": "keepalive", "soft": True, "title": "Keep-alive on Zlarior 50K: BUY 1 MNQ",
          "body": "about -$2.40, at most -$23."}
    got = run(b, lambda: N.instant_problem(ka, now=t))
    check(f"[{b.mode}] quiet: a soft keep-alive line is silent (as on the old path)", got and all(g[2] for g in got), got)
    mp = {"key": f"exec:miss:{int(t)}", "code": "missed", "title": "MISSED TRADE · Zlarior", "body": "not routed"}
    got = run(b, lambda: N.instant_problem(mp, now=t))
    check(f"[{b.mode}] quiet: a missed trade rings (problems ring in quiet hours)", got and not any(g[2] for g in got), got)


def main() -> int:
    for mode in ("telegram", "ntfy", "off"):
        print(f"\n--- set-up: {mode}")
        drill(mode)
    n, ok = len(RES), sum(RES)
    print(f"\nalert drill: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
