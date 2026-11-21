"""Jarvis money answers (lead 2026-11-21: "the owner asks Jarvis money questions by voice; wrong numbers cost trust and money"). The 60
questions the owner actually asks, each with what the TRUE answer must say (and must never say), for two fixtures of the PC's status post:
  A  live: the PC reported 2 min ago (Zlarior 50K eval $49,193; Zlarior 25K #2 eval $25,000; ATLAS 25K sim FUNDED at +$401 in MFFU terms)
  B  silent: the same post, but its last report was 2 days ago: an answer must say how old the numbers are, never present them as live
Truth: docs/ACCOUNT_RULES.md + research/lit/mffu_rules.json (funded starts at $0; the $1,000 ask at +$2,100 on a 25K; buffer $1,100;
earliest $250 at +$1,350; 80% split; 5 sim payouts; 7 calendar days inactivity; daily loss soft: $1,000 50K / $600 25K).
Runs the real Jarvis page (Chromium, 390 x 844): each question typed into Jarvis, the reply read from the chat.
    python -X utf8 -m tests.test_jarvis_money_answers            (~4 min)
    python -X utf8 -m tests.test_jarvis_money_answers --dump     every answer printed (no checks)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RESULTS = []


def check(name, ok, info=None):
    RESULTS.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def fixture(age_s):
    """the PC's status post (tests/fixtures/jarvis_zeus_lite.json), its report time `age_s` ago; ATLAS funded at +$401 (NinjaTrader 25,401)"""
    d = json.load(open(os.path.join(ROOT, "tests", "fixtures", "jarvis_zeus_lite.json"), encoding="utf-8"))
    t = int(time.time()) - age_s
    d["t"] = t
    for k in ("pc", "pc_verdict"):
        if isinstance(d.get(k), dict):
            d[k]["t"] = t
    d["board"]["t"] = t
    a = d["board"]["atlas"]
    a.update(balance=25401.0, room=1401.0, today_pnl=120.0, profit=401.0)
    return d


# (id, question, must say (all, regexes, live fixture), never (any, regexes, both fixtures))
NEVER = [r"27,100", r"\$25,401"]                     # the NinjaTrader number is never MFFU's
Q = [
    # payout
    ("pay1", "when is my payout", [r"\+?\$401", r"\$2,100", r"\$1,699"], NEVER),
    ("pay2", "how much can I withdraw", [r"\$1,000|\$250"], NEVER),
    ("pay3", "am I eligible for a payout", [r"not yet|no\b|need", r"\$1,350|\$949"], NEVER),
    ("pay4", "how far am I from my first payout", [r"\$1,699|\$949"], NEVER),
    ("pay5", "how much will I get from my first payout", [r"\$800"], NEVER),
    ("pay6", "what is the earliest payout", [r"\$250", r"\$1,350"], NEVER),
    ("pay7", "can I request a payout today", [r"not yet|no\b|need"], NEVER),
    ("pay8", "how many payouts do I have left", [r"\b5\b"], NEVER),
    ("pay9", "what is the payout split", [r"80\s?%"], NEVER),
    ("pay10", "how much do I keep from a $1,000 payout", [r"\$800", r"\$560|30\s?%"], NEVER),
    # room / drawdown
    ("room1", "how much room do I have", [r"\$1,025", r"\$1,401|\$1,000"], NEVER),
    ("room2", "how much can I lose today", [r"\$1,000|\$600"], NEVER),
    ("room3", "how much drawdown is left on Zlarior", [r"\$1,025"], NEVER),
    ("room4", "how much room does ATLAS have", [r"\$1,401"], NEVER),
    ("room5", "what is my daily loss limit", [r"\$1,000|\$600"], NEVER),
    ("room6", "how close am I to the max loss", [r"\$1,025|\$1,401|\$1,000"], NEVER),
    ("room7", "where is the floor on ATLAS", [r"-?\$1,000|−\$1,000"], NEVER),
    ("room8", "how much can Zlarior lose before it fails", [r"\$1,025"], NEVER),
    # pass
    ("pass1", "how far am I from passing", [r"\$3,807", r"\$1,500"], NEVER),
    ("pass2", "how much to pass Zlarior", [r"\$3,807"], NEVER),
    ("pass3", "when will Zlarior pass", [r"\$3,807|Dec|Jan|Feb"], NEVER),
    ("pass4", "what is the profit target on the 25K", [r"\$1,500|\$26,500"], NEVER),
    ("pass5", "how much to pass the 25K number 2", [r"\$1,500"], NEVER),
    ("pass6", "has ATLAS passed", [r"funded|passed"], NEVER),
    # trades
    ("tr1", "did zeus trade today", [r"no\b|not|none|0 trades|no trade"], NEVER),
    ("tr2", "did a trade happen today", [r"no\b|not|none|0 trades|no trade"], NEVER),
    ("tr3", "what was my last trade", [r"ATLAS|Zlarior"], NEVER),
    ("tr4", "is a bot in a trade", [r"flat|no\b|not in"], NEVER),
    ("tr5", "how many trades today", [r"\b0\b|no trade|none"], NEVER),
    ("tr6", "what is my P&L today", [r"\+?\$120|\$0"], NEVER),
    # week / month / overview
    ("wk1", "how much did I make this week", [r"\$"], NEVER),
    ("wk2", "how much did I make this month", [r"\$"], NEVER),
    ("wk3", "what is my P&L this week", [r"\$"], NEVER),
    ("wk4", "how did Zlarior do this week", [r"−?\$129|-\$129"], NEVER),
    ("wk5", "how are my accounts", [r"\$49,19\d", r"\+\$401", r"\$25,000"], NEVER),
    # 7-day inactivity
    ("in1", "when do I need to trade ATLAS by", [r"7|Nov|Dec|day"], NEVER),
    ("in2", "what is the 7 day rule", [r"7", r"day"], NEVER),
    ("in3", "which account is close to the inactivity limit", [r"ATLAS|Zlarior|day"], NEVER),
    ("in4", "when was the last trade on ATLAS", [r"Nov|day|ago"], NEVER),
    ("in5", "do I need to trade to keep my accounts", [r"7", r"day"], NEVER),
    # which next
    ("nx1", "which account should I focus on", [r"Zlarior|ATLAS"], NEVER),
    ("nx2", "which account is closest to passing", [r"Zlarior"], NEVER),
    ("nx3", "what is next for my accounts", [r"Zlarior|ATLAS"], NEVER),
    ("nx4", "which account trades next", [r"Zlarior|ATLAS|London|02:00"], NEVER),
    # taxes
    ("tx1", "how much should I set aside for taxes", [r"30\s?%|\$240|\$300"], NEVER),
    ("tx2", "what is my tax pot", [r"30\s?%|\$"], NEVER),
    ("tx3", "when are estimated taxes due", [r"Jan|Apr|Jun|Sep"], NEVER),
    # kalshi
    ("ks1", "how is kalshi doing", [r"Kalshi"], NEVER),
    ("ks2", "kalshi status", [r"Kalshi"], NEVER),
    ("ks3", "is the kalshi bot running", [r"Kalshi"], NEVER),
    # the PC
    ("pc1", "is the pc on", [r"yes|on|reported|checked in"], NEVER),
    ("pc2", "when did the pc last report", [r"min|just now|ago"], NEVER),
    ("pc3", "is ninjatrader connected", [r"NinjaTrader"], NEVER),
    ("pc4", "is zeus running", [r"running|yes|on"], NEVER),
    # armed
    ("ar1", "is the bot armed", [r"live|armed|LIVE"], NEVER),
    ("ar2", "is it live or paper", [r"live|LIVE"], NEVER),
    ("ar3", "is zlarior trading live", [r"live|LIVE"], NEVER),
    # rules
    ("ru1", "how many contracts can I trade on the 25K", [r"2 minis|20 micros"], NEVER),
    ("ru2", "can I trade news on ATLAS", [r"allowed|yes"], NEVER),
    ("ru3", "what is the consistency rule", [r"50\s?%|30\s?%"], NEVER),
]
# rules / taxes / Kalshi (its own feed, its own age): not the PC's live numbers, so no age is required when the PC is silent
STATIC = {"pay9", "pay10", "tx1", "tx2", "tx3", "in2", "ru1", "ru2", "ru3", "ks1", "ks2", "ks3"}
STALE = r"last report|not reported|has not reported|days? ago|2 days|silent|old|may be old|stale|since"


def ask_all(p, questions):
    out = {}
    for qid, q, _, _ in questions:
        p.evaluate("document.querySelectorAll('#talk .msg').forEach((m) => { m.dataset.seen = '1'; })")   # the chat keeps 8 messages: mark, not count
        if not p.locator("#q").is_visible():           # an answer opened something (an app, a sheet): back to Jarvis's home first
            print("  (q hidden before", qid, ")", p.evaluate("[document.documentElement.dataset.mode, location.hash, !!document.querySelector('.sheet:not([hidden])')]"))
            p.keyboard.press("Escape")
            p.evaluate("() => { const b = document.querySelector('.bar [data-app=\"home\"]'); if (b) b.click(); }")
            p.wait_for_timeout(600)
        p.fill("#q", q)
        p.press("#q", "Enter")
        try:
            p.wait_for_function("!!document.querySelector('#talk .msg.j:not([data-seen])')", timeout=30000, polling=100)
        except Exception:                               # noqa: BLE001 - recorded as no answer
            out[qid] = ""
            continue
        out[qid] = p.evaluate("(() => { const m = document.querySelectorAll('#talk .msg.j:not([data-seen])'); return m[m.length - 1].textContent; })()")
    return out


def run(age_s, label, br, base):
    lite = fixture(age_s)
    line = json.dumps({"id": "x", "time": lite["t"], "event": "message", "topic": "t", "message": json.dumps(lite)}) + "\n"
    ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
    ctx.route(re.compile(r"^https://ntfy\.sh/.*"), lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=line))
    ctx.add_init_script("try { ['jarvis.tour.seen','olympus.tour.done','jarvis.pinHint'].forEach((k) => localStorage.setItem(k, '1'));"
                        " localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.speak', 'off');"
                        " localStorage.setItem('jarvis.alerts.v1', JSON.stringify({ speak: false, brief: false })); localStorage.setItem('jfx', 'off');"
                        " sessionStorage.setItem('jarvis.booted', '1'); } catch (e) {}")
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base + "jarvis/", wait_until="load")
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
    p.wait_for_timeout(1500)
    ans = ask_all(p, Q)
    ctx.close()
    return ans, errs


def main():
    dump = "--dump" in sys.argv
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            A, ea = run(120, "live", br, base)
            B, eb = run(2 * 86400, "silent", br, base)
            br.close()
    finally:
        srv.shutdown()
    if dump:
        out = {qid: {"q": q, "live": A.get(qid, ""), "silent": B.get(qid, "")} for qid, q, _, _ in Q}
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0
    for qid, q, must, never in Q:
        a, b = A.get(qid, ""), B.get(qid, "")
        miss = [m for m in must if not re.search(m, a, re.I)]
        bad = [x for x in never if re.search(x, a) or re.search(x, b)]
        check(f"live  {qid}: {q}", a and not miss and not bad, {"missing": miss, "never": bad, "answer": a[:300]})
        stale_ok = qid in STATIC or (not re.search(r"\$\d", b)) or re.search(STALE, b, re.I)
        check(f"silent {qid}: {q} (numbers carry their age)", b and stale_ok and not bad, {"answer": b[:300]})
    check("no page errors", not ea and not eb, (ea + eb)[:3])
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\njarvis money answers: {len(RESULTS) - len(bad)}/{len(RESULTS)} {'ALL PASS' if not bad else 'FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(main())
