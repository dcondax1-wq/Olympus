"""Short emoji Telegram alerts + charts after the text (day-tgpretty 2026-11-27). A fake Telegram (alert_bus._HTTP); never the
owner's phone.

    python -X utf8 -m tests.test_tg_pretty
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

RESULTS = []
ID = "MFFUEVBLDR8812345"            # an account id: must never reach a message whole


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:900]}"), flush=True)


def emoji_first(s: str) -> bool:
    return bool(s) and ord(s[0]) >= 0x2000


def events():
    """(name, ev, title, body): every kind the bus sends, the long words the producers write."""
    long_body = "\n".join(f"line {i}: a lot of words about account {ID} and what happened next in great detail" for i in range(12))
    return [
        ("entry", {"kind": "entry", "key": "fill:1", "account": f"Zlarior 50K ({ID})", "side": "LONG", "qty": 3, "contract": "MNQ",
                   "price": 25650.0, "stop": 25630.0, "target": 25760.0, "risk": 303.0, "gain": 4557.0,
                   "more": f"LIT: swept London low; CISD confirmed on {ID}\nRisk $303 (20 pts)"}, "", ""),
        ("exit target", {"kind": "exit", "key": "out:1", "account": "Zlarior 50K", "side": "LONG", "usd": 1240.0, "R": 4.1,
                         "reason": "target", "after": "today +$1,240, balance $3,100"}, "", ""),
        ("exit stop", {"kind": "exit", "key": "out:2", "account": "ATLAS 25K", "side": "SHORT", "usd": -310.0, "R": -1.0, "reason": "stop"}, "", ""),
        ("exit BE", {"kind": "exit", "key": "out:3", "account": "ATLAS 25K", "side": "SHORT", "usd": 0.0, "R": 0.0, "reason": "breakeven"}, "", ""),
        ("setup", {"kind": "setup", "key": "setup:a"}, "Zlarior LONG swept London low 4/10", "Waiting for the CISD.\n" + long_body),
        ("armed", {"kind": "setup", "key": "setup:b"}, "ATLAS MACD ARMED", "Long above 25,700."),
        ("no trade", {"kind": "report", "key": "cond:missed:1", "notify_type": "problems"}, "No trade today: FOMC", long_body),
        ("pc silent", {"kind": "pc_silent", "minutes": 20, "since": time.time() - 1200}, "", ""),
        ("pc silent report", {"kind": "report", "key": "pc_silent:1", "notify_type": "pc_silent", "report": True}, "PC silent 25 min", long_body),
        ("bot stopped", {"kind": "bot_stopped", "bot": "Zlarior", "why": "The server is not running"}, "", ""),
        ("problem dual", {"kind": "problem", "key": "cond:no_stop:1", "dual": True, "report": True}, "Open trade with NO stop", long_body),
        ("dll", {"kind": "dll_near", "account": "ATLAS 25K", "limit": 500, "left": 90}, "", ""),
        ("dd", {"kind": "dd_near", "account": "Zlarior 50K", "limit": 2000, "left": 400}, "", ""),
        ("7 day", {"kind": "seven_day", "account": "ATLAS 25K", "day": 6, "deadline": "Tue"}, "", ""),
        ("payout", {"kind": "payout_ready", "account": "ATLAS 25K", "amount": 1000, "balance": 2150}, "", ""),
        ("hedge", {"kind": "hedge_risk", "not_flat": ["ATLAS 25K"]}, "", ""),
        ("day summary", {"kind": "report", "key": "guard:day:2026-11-27", "notify_type": "daily_summary", "report": True},
         "Day Fri Nov 27: -$26", long_body),
        ("week", {"kind": "report", "key": "guard:week:2026-11-27", "notify_type": "weekly_report", "report": True},
         "Week Nov 23-27: +$1,214", long_body),
        ("brief", {"kind": "brief", "key": "guard:brief:x", "notify_type": "morning_brief", "report": True}, "ZEUS brief", long_body),
        ("goal", {"kind": "report", "key": "guard:goal:50k:100", "report": True}, "Zlarior 50K: profit target reached ($3,000)", long_body),
        ("update", {"kind": "report", "key": "auto:update:failed:1", "report": True}, "Bot update stuck", long_body),
        ("daily rows", {"kind": "daily", "day": "Fri Nov 27", "rows": [{"account": "Zlarior 50K", "usd": 120}, {"account": "ATLAS 25K", "usd": -26}]}, "", ""),
        ("channel down", {"kind": "channel_down", "channel": "discord", "why": "Discord answered 500"}, "Alerts: Discord is not delivering", "it failed."),
        ("odd", {"kind": "report", "key": "zzz"}, f"\U0001F525\U0001F525 *** weird title {ID}", long_body),
        ("empty", {"kind": "report"}, "", ""),
    ]


def t_format():
    print("1. every message: <= 3 short lines, emoji first, no ids", flush=True)
    from engine import tg_pretty as T, alert_bus as AB
    bad = []
    for name, ev, title, body in events():
        if not title and not body:
            title, body = AB.text(ev)
        s = T.fmt(ev, title, body)
        ls = s.splitlines()
        if not (1 <= len(ls) <= 3 and emoji_first(s) and ID not in s and all(len(x) <= T.LINE_MAX + 6 for x in ls)
                and not emoji_first((ls[0].split(" ", 1) + [""])[1])):    # never two emojis in front
            bad.append((name, s))
    check("all kinds: 1-3 lines, emoji first (one), each line short, the account id masked", not bad, bad)
    s = T.fmt(*events()[0][1:])
    check("entry: '🟢 Zlarior 50K LONG in · risk $303 · target +$4,557' + size / levels + the reason",
          s.splitlines()[0].startswith("\U0001F7E2 Zlarior 50K") and "LONG in · risk $303 · target +$4,557" in s
          and "3 MNQ @ 25,650.00" in s and "swept London low" in s, s)
    s = T.fmt(*events()[1][1:])
    check("target: '✅ Target hit +$1,240'", s.startswith("✅ Target hit +$1,240"), s)
    s = T.fmt(*events()[2][1:])
    check("stop: '🛑 Stopped −$310'", s.startswith("\U0001F6D1 Stopped −$310"), s)
    s = T.fmt(*events()[4][1:])
    check("setup: '👀 Setup forming LONG: swept London low (4/10)'", s.startswith("\U0001F440 Setup forming LONG: swept London low (4/10)"), s)
    s = T.fmt(*events()[6][1:])
    check("no trade today: '⏸️ No trade today: …'", s.startswith("⏸️ No trade today"), s)
    s = T.fmt(*events()[7][1:])
    check("PC silent: '🚨 PC silent 20 min'", s.startswith("\U0001F6A8 PC silent 20 min"), s)
    check("a broken event never raises (the old title, cut)", emoji_first(T.fmt(None, "x", "y")) and emoji_first(T.fmt({"kind": "entry", "qty": "?"})))


class FakeTG:
    def __init__(self):
        self.calls, self.fail_photo, self.fail_text, self.lock = [], False, False, threading.Lock()

    def __call__(self, method, url, body, headers, timeout):
        op = url.rsplit("/", 1)[-1]
        with self.lock:
            self.calls.append((op, body, time.time()))
        if op == "sendPhoto" and self.fail_photo:
            return 500, '{"ok": false, "description": "photo refused"}'
        if op == "sendMessage" and self.fail_text:
            return 0, "URLError"
        return 200, '{"ok": true, "result": {"message_id": 9}}'

    def texts(self):
        return [json.loads(b.decode("utf-8"))["text"] for op, b, _t in self.calls if op == "sendMessage"]

    def ops(self):
        return [c[0] for c in self.calls]


def t_bus(tmp):
    print("2. the bus: text first, the chart after (own thread), failures never drop the text", flush=True)
    from engine import alert_bus as AB, tg_pretty as T
    fake = FakeTG()
    old = AB._HTTP
    AB._HTTP = fake
    cfg = {"telegram": {"token": "123456:" + "A" * 35, "chat_id": "777"}, "ntfy": False, "webpush": False}
    kw = dict(cfg=cfg, path=os.path.join(tmp, "st.json"), log_path=os.path.join(tmp, "log.jsonl"))
    keep_log = AB.LOG_PATH
    AB.LOG_PATH = kw["log_path"]                      # the chart thread's failure lines too
    try:
        T._reset_rate()
        for name, ev, title, body in events():
            e = dict(ev, title=title or ev.get("title"), body=body or ev.get("body"))
            AB.deliver(dict(e, key=""), **kw)
        bad = [x for x in fake.texts() if not (len(x.splitlines()) <= 3 and emoji_first(x) and ID not in x)]
        check(f"{len(fake.texts())} Telegram texts through the bus: each <= 3 lines, emoji first, no id", len(fake.texts()) >= 20 and not bad, bad[:3])
        check("no token / chat id inside any text", not any("AAAAAAAA" in x or "777" in x for x in fake.texts()))

        fake.calls.clear()
        png = os.path.join(tmp, "c.png")
        with open(png, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
        gate = threading.Event()

        def slow_chart():
            gate.wait(5)
            return png
        t0 = time.time()
        r = AB.deliver({"kind": "entry", "key": "fill:9", "account": "Zlarior 50K", "side": "LONG", "qty": 1, "price": 1, "stop": 0,
                        "target": 3, "risk": 2, "gain": 6, "photo_fn": slow_chart}, **kw)
        took = time.time() - t0
        check("latency: the text goes at once while the chart is still drawing (deliver returned in < 1 s, sendMessage only)",
              r["ok"] and took < 1.0 and fake.ops() == ["sendMessage"], (took, fake.ops()))
        gate.set()
        AB.drain(10)
        check("... then the chart follows as sendPhoto (silent: the text already rang)", fake.ops() == ["sendMessage", "sendPhoto"]
              and b'name="disable_notification"\r\n\r\ntrue' in fake.calls[1][1], fake.ops())

        fake.calls.clear()
        fake.fail_photo = True
        r = AB.deliver({"kind": "exit", "key": "out:9", "account": "Zlarior 50K", "usd": 50, "reason": "target", "photo": png}, **kw)
        AB.drain(10)
        check("sendPhoto refused: the text still went and counts as delivered", r["ok"] and fake.ops() == ["sendMessage", "sendPhoto"], fake.ops())
        fake.fail_photo = False

        fake.calls.clear()
        r = AB.deliver({"kind": "exit", "key": "out:10", "account": "Zlarior 50K", "usd": 50, "reason": "target",
                        "photo_fn": lambda: 1 / 0}, **kw)
        AB.drain(10)
        check("the chart crashes: the text went, no picture, nothing raised", r["ok"] and fake.ops() == ["sendMessage"], fake.ops())
        logged = open(kw["log_path"], encoding="utf-8").read() if os.path.exists(kw["log_path"]) else ""
        check("... the crash is in the failure log, without the token", "ZeroDivisionError" in logged and "AAAAAAAA" not in logged, logged[-300:])

        fake.calls.clear()
        keep = AB.PHOTO_TIMEOUT_S
        AB.PHOTO_TIMEOUT_S = 0.3
        hang = threading.Event()
        try:
            r = AB.deliver({"kind": "entry", "key": "fill:11", "account": "Zlarior 50K", "side": "LONG", "photo_fn": lambda: hang.wait(30) and png}, **kw)
            AB.drain(5)
            check("a chart that hangs: given up after the timeout, the text went", r["ok"] and fake.ops() == ["sendMessage"], fake.ops())
        finally:
            hang.set()
            AB.PHOTO_TIMEOUT_S = keep

        fake.calls.clear()
        fake.fail_text = True
        r = AB.deliver({"kind": "entry", "key": "fill:12", "account": "Zlarior 50K", "side": "LONG", "photo": png, "backoff": ()}, **kw)
        AB.drain(5)
        check("text refused: no picture sent alone (the text is the alert), the failure reported", not r["ok"] and "sendPhoto" not in fake.ops(),
              (r, fake.ops()))
        fake.fail_text = False

        fake.calls.clear()
        r = AB.deliver({"kind": "entry", "key": "fill:13:acctc", "account": "BLITZ paper", "side": "LONG"}, **kw)
        r2 = AB.deliver({"kind": "exit", "key": "out:14", "account": "Sim101", "usd": 5}, **kw)
        check("Paper / Sim / BLITZ never on Telegram (the money channel)", not fake.calls and "skipped" in str(r["receipts"]) and "skipped" in str(r2["receipts"]),
              (fake.ops(), r, r2))

        fake.calls.clear()
        T._reset_rate()
        dg = os.path.join(tmp, "digest.json")
        kd = AB.DIGEST_PATH
        AB.DIGEST_PATH = dg
        try:
            for i in range(T.RATE_N + 4):
                AB.deliver({"kind": "setup", "key": "", "title": f"Zlarior LONG step {i} 3/10", "body": "x"}, **kw)
            for i in range(3):
                AB.deliver({"kind": "entry", "key": "", "account": "Zlarior 50K", "side": "LONG"}, **kw)
                AB.deliver({"kind": "problem", "key": "", "title": f"Problem {i}", "body": "x", "report": True}, **kw)
        finally:
            AB.DIGEST_PATH = kd
        n_setup = sum(1 for x in fake.texts() if x.startswith("\U0001F440"))
        check(f"rate limit: setup steps at most {T.RATE_N} per {T.RATE_S // 60} min, the rest wait in the digest; entries + problems always go",
              n_setup == T.RATE_N and sum(1 for x in fake.texts() if x.startswith("\U0001F7E2")) == 3
              and sum(1 for x in fake.texts() if "Problem" in x) == 3 and os.path.exists(dg), (n_setup, fake.texts()[-8:]))

        fake.calls.clear()
        os.environ["LE_TG_PRETTY"] = "0"
        try:
            AB.deliver({"kind": "entry", "key": "", "account": "Zlarior 50K", "side": "LONG", "qty": 1, "price": 1}, **kw)
        finally:
            os.environ.pop("LE_TG_PRETTY", None)
        check("LE_TG_PRETTY=0: the old long text (title + body), no emoji", fake.texts() and fake.texts()[0].startswith("Zlarior 50K LONG opened"),
              fake.texts())
    finally:
        AB._HTTP = old
        AB.LOG_PATH = keep_log


def t_preview():
    print("3. /preview (owner only): one of each style + an example chart", flush=True)
    from engine import tg_cmd as C, tg_pretty as T
    c, say = C.parse_text("/preview")
    check("/preview parses (no words after it)", c == {"cmd": "preview"} and say is None and C.parse_text("/preview now")[0] is None)
    sent = []

    def http(method, url, body, headers=None, timeout=None):
        sent.append((url.rsplit("/", 1)[-1], body))
        return 200, '{"ok": true, "result": {"message_id": 1}}'
    n = C.preview_reply("TOKEN", "1", 5, http=http, photo=False)
    texts = [json.loads(b.decode())["text"] for op, b in sent if op == "sendMessage"]
    check(f"{n} preview messages: the head + {len(T.samples())} styles, each <= 3 lines, emoji first",
          n == len(T.samples()) + 1 and all(emoji_first(t) and len(t.splitlines()) <= 3 for t in texts), texts)
    want = ("\U0001F7E2", "✅ Target hit", "\U0001F6D1 Stopped", "\U0001F440 Setup forming", "⏸️ No trade today",
            "\U0001F6A8 PC silent", "\U0001F4CA Day")
    check("the styles: entry, target, stop, setup, no trade, PC silent, day", all(any(t.startswith(w) for t in texts) for w in want), texts)
    check("/preview is in /help", "/preview" in C.HELP)
    ok = C._preview_photo.__doc__ and "Never raises" in C._preview_photo.__doc__
    from engine import alert_bus as AB
    got = []
    old = AB._HTTP
    AB._HTTP = lambda m, u, b, h, t: (got.append(u.rsplit("/", 1)[-1]) or (200, '{"ok": true, "result": {"message_id": 2}}'))
    try:
        r = C._preview_photo("TOKEN", "1")
    finally:
        AB._HTTP = old
    check("the example chart: a sendPhoto (made-up candles, OLYMPUS NIGHT)", ok and r and got == ["sendPhoto"], (r, got))
    from engine import tg_cmd
    import inspect
    src = inspect.getsource(tg_cmd.TgCommands.tick)
    check("only the owner's private chat reaches /preview (is_owner runs before any command)",
          src.index("is_owner(msg, chat)") < src.index('"preview"'))


def t_legacy():
    print("4. the old chat path (engine/alerts.send) is short too", flush=True)
    from engine import alerts as A
    s = A._short("Zlarior: entered LONG 3 MNQ at 25,650. Stop 25,630, target 25,760. Risk $303 and a lot more words here.", "signal")
    check("alerts.send's Telegram text: emoji first, <= 3 lines", emoji_first(s) and len(s.splitlines()) <= 3, s)


def main():
    tmp = tempfile.mkdtemp(prefix="tgpretty_")
    t_format()
    t_bus(tmp)
    t_preview()
    t_legacy()
    n = sum(ok for _, ok in RESULTS)
    print(f"\ntg pretty: {n}/{len(RESULTS)} " + ("ALL PASS" if n == len(RESULTS) else "FAILED"))
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
