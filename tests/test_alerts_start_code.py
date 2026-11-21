"""The /alerts/ page's one-time START code (day-security3 2026-11-21; tools/alerts_setup.wait_chat_id(code=), engine/alerts_box).
  a. with the page's code: a stranger's plain "/start" (or a wrong code) sent first is ignored, the owner's "/start <code>" wins
  b. a plain "/start" only (the owner opened the bot by hand, or only a stranger pressed START): no chat, nothing saved
  c. without a code (ALERTS_SETUP.bat on the PC, the owner at the keyboard): the plain /start works as before
  d. the page's link carries a fresh code each Connect; the code is never in the box's log
    python -X utf8 -m tests.test_alerts_start_code
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import alert_bus as AB  # noqa: E402
from engine import alerts_box as AL  # noqa: E402
from tools import alerts_setup as S  # noqa: E402

RES = []
TOKEN = "123456789:AA" + "k" * 33


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:300]}"))


def fake(updates):
    def h(method, url, body, headers, timeout):
        if "/getUpdates" in url:
            return 200, json.dumps({"ok": True, "result": [] if "timeout=0" in url else updates})
        if url.endswith("/getMe"):
            return 200, json.dumps({"ok": True, "result": {"username": "olympus_alerts_bot"}})
        return 404, "{}"
    return h


def upd(i, chat, text, kind="private"):
    return {"update_id": i, "message": {"chat": {"id": chat, "type": kind}, "text": text}}


def main():
    t = [0.0]
    clock = lambda: t.__setitem__(0, t[0] + 1) or t[0]            # noqa: E731
    real = AB._HTTP
    try:
        print("a. with the page's code")
        AB._HTTP = fake([upd(1, 999, "/start"), upd(2, 888, "/start WRONGCODE"), upd(3, 555, "/start ABC123")])
        got = S.wait_chat_id(TOKEN, say=lambda *_: None, wait_s=5, sleep=lambda s: None, clock=clock, code="ABC123")
        ok(got == "555", "a stranger's /start and a wrong code are ignored; the owner's '/start <code>' wins", got)
        print("b. no code in any /start")
        t[0] = 0.0
        AB._HTTP = fake([upd(1, 999, "/start"), upd(2, 777, "/start", "group")])
        got = S.wait_chat_id(TOKEN, say=lambda *_: None, wait_s=5, sleep=lambda s: None, clock=clock, code="ABC123")
        ok(got is None, "only plain /start (a stranger, or the bot opened by hand): no chat, nothing will be saved", got)
        print("c. the PC's ALERTS_SETUP (no code)")
        t[0] = 0.0
        AB._HTTP = fake([upd(1, 777, "/start", "group"), upd(2, 555, "/start")])
        got = S.wait_chat_id(TOKEN, say=lambda *_: None, wait_s=5, sleep=lambda s: None, clock=clock)
        ok(got == "555", "without a code the plain private /start works as before (the owner is at the PC)", got)
        print("d. the page's link")
        with tempfile.TemporaryDirectory() as d:
            AL._S["log"] = os.path.join(d, "box.jsonl")
            AL._S["wait_s"] = 0
            AB._HTTP = fake([])
            r1 = AL.do_connect({"token": TOKEN})
            r2 = AL.do_connect({"token": TOKEN})
            c1 = str(r1.get("link", "")).split("?start=")[-1]
            c2 = str(r2.get("link", "")).split("?start=")[-1]
            ok(r1.get("ok") and "?start=" in r1["link"] and len(c1) >= 10 and c1 != c2 and all(ch.isalnum() for ch in c1),
               "each Connect: a fresh code in the t.me link (letters and digits, Telegram's start parameter)", (r1.get("link"), r2.get("link")))
            AL.log({"t": 1, "action": "connect", "ok": True, "why": "", "bot": r1.get("_mask")})
            raw = open(AL._S["log"], encoding="utf-8").read() if os.path.exists(AL._S["log"]) else ""
            ok(c1 not in raw and TOKEN not in raw, "the code and the token are never in the box's log")
            AL.do_cancel()
    finally:
        AB._HTTP = real
    n = sum(RES)
    print(f"\nalerts_start_code: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
