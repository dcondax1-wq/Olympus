"""Cloud 'Send me a test alert' (day-notify 2026-11-23, tools/alert_test.py): FAKE transports only, nothing leaves this machine.

    python -X utf8 -m tests.test_alert_test

 a. private topic (LE_NTFY_TOPIC): title "TEST: Olympus alerts work <time> ET", posted there, read back by ntfy's id -> ok, green
 b. the receipt goes to the PUBLIC status topic as kind le-alert-test: ok / channel words only, never the private topic or a token
 c. posted but not found on read-back -> "posted, not read back", red; HTTP 429 -> "failed (HTTP 429)", red
 d. no LE_NTFY_TOPIC: the test goes to the public status topic (like a real PC-silent alert) -> red + the "add the secret" note
 e. Telegram / Discord secrets: each through alert_bus.deliver on its own channel; a Telegram receipt alone = green
 f. dry run sends nothing; --last reads the newest receipt; other readers filter by kind (feed_last ignores it)
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import alert_test as A, pc_silent_check as PS  # noqa: E402

RES = []
FEED = {"ntfy": "https://ntfy.example", "topic": "public-status-topic"}
PRIV = "priv-amber-falcon-9999"
T = 1795467900                                         # Mon 2026-11-23 16:05 ET


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


class Ntfy:
    """A fake ntfy.sh: keeps posts per topic, answers polls; `drop` = posts vanish (read-back fails); `code` = refuse posts."""

    def __init__(self, drop=False, code=200):
        self.posts, self.drop, self.code, self.n = [], drop, code, 0

    def post(self, url, body, headers):
        self.posts.append((url, body.decode("utf-8"), dict(headers)))
        if self.code != 200:
            return self.code, ""
        self.n += 1
        return 200, json.dumps({"id": f"m{self.n}", "time": T, "event": "message"})

    def get(self, url):
        topic = url.split("/")[3]
        out = []
        if not self.drop:
            for i, (u, b, h) in enumerate(self.posts):
                if u.endswith("/" + topic):
                    out.append(json.dumps({"id": f"m{i + 1}", "event": "message", "time": T, "title": h.get("Title"), "message": b}))
        return 200, "\n".join(out)


def go(env, net, **k):
    out = tempfile.mkdtemp()
    said = []
    r = A.run(out, now=T, env=env, get=net.get, post=net.post, sleep=lambda s: None, say=said.append, feed=FEED, **k)
    return r, out, said


def t_private():
    net = Ntfy()
    r, out, said = go({"LE_NTFY_TOPIC": PRIV}, net, bus=None)
    first = net.posts[0]
    check("a1. title 'TEST: Olympus alerts work 4:05 PM ET', to the private topic", first[0].endswith("/" + PRIV)
          and first[2]["Title"] == "TEST: Olympus alerts work 4:05 PM ET", first)
    check("a2. read back by id -> ntfy ok, green, via ntfy", r["ok"] and r["ch"]["ntfy"] == "ok" and r["via"] == ["ntfy"]
          and r["to"] == "private", r)
    check("a3. Telegram / Discord without secrets = 'not set up'", r["ch"]["telegram"] == r["ch"]["discord"] == "not set up", r["ch"])
    rec = [p for p in net.posts if p[0].endswith("/" + FEED["topic"])]
    body = rec[0][1] if rec else ""
    j = json.loads(body or "{}")
    check("b1. ONE receipt on the PUBLIC status topic, kind le-alert-test, ok + channel words", len(rec) == 1 and j.get("kind") == A.KIND
          and j.get("ok") is True and j.get("ch", {}).get("ntfy") == "ok" and j.get("to") == "private", rec)
    check("b2. the receipt never names the private topic (nor anywhere in the log lines / saved file)", PRIV not in body
          and not any(PRIV in s for s in said) and PRIV not in open(os.path.join(out, A.OUT_NAME)).read(), body)
    check("b3. log says WORKED", said and "WORKED" in said[0], said)
    check("f2. feed_last ignores the receipt (only le-live counts as the PC's heartbeat)",
          PS.feed_last([{"message": body, "time": T}]) is None)
    check("f3. --last reads the newest receipt back", (A.last(get=net.get, feed=FEED) or {}).get("ok") is True)


def t_fail():
    r, _o, said = go({"LE_NTFY_TOPIC": PRIV}, Ntfy(drop=True), bus=None)
    check("c1. posted but never read back -> 'posted, not read back', red", not r["ok"] and r["ch"]["ntfy"] == "posted, not read back", r)
    net = Ntfy(code=429)
    r, _o, said = go({"LE_NTFY_TOPIC": PRIV}, net, bus=None)
    check("c2. ntfy refuses (HTTP 429) -> 'failed (HTTP 429)', red, DID NOT REACH YOU", not r["ok"] and r["ch"]["ntfy"] == "failed (HTTP 429)"
          and "DID NOT REACH YOU" in said[0], (r, said))
    old = A.run
    try:
        A.run = lambda *a, **k: {"ok": False}
        red = A.main(["--out", tempfile.mkdtemp()])
        A.run = lambda *a, **k: {"ok": True}
        green = A.main(["--out", tempfile.mkdtemp()])
    finally:
        A.run = old
    check("c3. exit code: red = 1 (the job shows a red X), green = 0", red == 1 and green == 0, (red, green))


def t_public():
    net = Ntfy()
    r, _o, said = go({}, net, bus=None)
    check("d1. no LE_NTFY_TOPIC: the test goes to the public status topic (as a real PC-silent alert)", net.posts[0][0].endswith("/" + FEED["topic"])
          and r["to"] == "status topic", net.posts[0][0])
    check("d2. ... and is NOT counted as reaching the owner: red + 'add the repo secret LE_NTFY_TOPIC'", not r["ok"]
          and "LE_NTFY_TOPIC" in r.get("note", ""), r)


class Bus:
    """engine/alert_bus stand-in: deliver() per channel with a fixed answer."""

    def __init__(self, ans):
        self.ans, self.calls = ans, []

    def config(self, env=None, path=None):
        return {"telegram": {"token": "x", "chat_id": 1} if "telegram" in self.ans else None,
                "discord": {"webhook": "y"} if "discord" in self.ans else None, "ntfy": False, "webpush": False}

    def deliver(self, ev, cfg=None, path=None, log_path=None):
        ch = ev["only"][0]
        self.calls.append(ev)
        ok = self.ans.get(ch)
        return {"receipts": {ch: "42"} if ok else {}, "failed": {} if ok else {ch: "HTTP 401 bot token wrong"}}

    def redact(self, s, cfg=None):
        return s


def t_bus():
    b = Bus({"telegram": True})
    r, _o, _s = go({}, Ntfy(), bus=b)
    check("e1. Telegram secret: delivered on its own channel as a test (kind test, no de-dupe record)", b.calls and b.calls[0]["only"] == ["telegram"]
          and b.calls[0]["kind"] == "test" and b.calls[0]["no_record"] is True, b.calls)
    check("e2. a Telegram receipt alone = green (owner channel), ntfy to the public topic does not count", r["ok"] and r["via"] == ["telegram"]
          and r["ch"]["discord"] == "not set up", r)
    b = Bus({"telegram": False, "discord": True})
    r, _o, _s = go({"LE_NTFY_TOPIC": PRIV}, Ntfy(), bus=b)
    check("e3. every channel is tried (a test checks all): Telegram failed with its reason, Discord ok, ntfy ok", r["ch"]["telegram"].startswith("failed (HTTP 401")
          and r["ch"]["discord"] == "ok" and r["ch"]["ntfy"] == "ok" and r["via"] == ["discord", "ntfy"], r["ch"])


def t_dry():
    net = Ntfy()
    r, _o, said = go({"LE_NTFY_TOPIC": PRIV}, net, bus=None, dry=True)
    check("f1. dry run: nothing posted, prints what it would send", not net.posts and any("[dry] TEST: Olympus alerts work" in s for s in said), said)
    src = open(os.path.join(ROOT, "tools", "alert_test.py"), encoding="utf-8").read()
    check("f4. stdlib + read-only for trading: no arm / order / start in the script", not any(w in src for w in (".arm(", "place_order", "bot.start")))


def main():
    t_private()
    t_fail()
    t_public()
    t_bus()
    t_dry()
    bad = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(bad)}/{len(RES)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
