"""BOTS_BACK.bat + scripts/bots_back.ps1 + tools/bots_back.py + tools/pc_report.py + scripts/pc_report_task.ps1 + the site's
tools/web_public/pc_feed.js (docs/BOTS_BACK.md, owner 2026-11-12: the bots and their reporting back without GitHub).

Never the real network: every HTTP call goes to a fake (and LE_PR_NO_NET=1 makes the real one refuse); every Windows-only step
(open NinjaTrader, start the server, Task Scheduler) is written to a log file by the scripts' test hook LE_BB_T_LOG; the python the
PowerShell script calls is a fake that records its arguments. Temp folders only.

  1. static     the .bat files (CRLF, ASCII, the right script, pause), ASCII .ps1, the safety strings (no live phrase, no START_BOT /
                engine.go, no live_model writes), .gitignore, status_feed.json
  2. pc_report  the lite status (< 4 KB, the live.json shape the site reads, t = the bot's own heartbeat time, no secrets), alerts
                (first run only records, a new trade pushes once, a failed push is retried, bot down / FEED STALE / NinjaTrader once +
                a 3-hour reminder + back to normal, nothing while the market is closed), the six-line card, dry run sends nothing
  3. bots_back  resume only a paper / Sim start (a real account, an account-less NinjaTrader start and Tradovate are never started),
                the feed wait
  4. pwsh       (skipped without pwsh) 5.1 lint; a full run; twice (idempotent); a running server is left alone; -DryRun changes
                nothing; -Remove undoes only what BOTS_BACK made; an old folder is refused; the git sign-in setting and its undo
  5. node       (skipped without node) pc_feed.js: parse, merge, overlay; the PC's real lite status through truth.js canonHome

  python -X utf8 -m tests.test_bots_back
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"                   # the real HTTP helper refuses: only the fakes below answer

from tests.test_live_publish import account_c_block, hb_payload  # noqa: E402
from tools import bots_back as BB  # noqa: E402
from tools import pc_report as R  # noqa: E402

RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:600]})" if info and not cond else ""))
    return bool(cond)


def rb(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return fh.read()


# ============================================================================================== 1 static
def static():
    for name, script, extra in (("BOTS_BACK.bat", b'scripts\\bots_back.ps1" %* & echo. & pause & exit /b', b":old"),
                                ("UNDO_BOTS_BACK.bat", b'scripts\\bots_back.ps1" -Remove & echo. & pause & exit /b', b"")):
        b = rb(name)
        check(f"{name}: CRLF line endings, ASCII", b"\n" not in b.replace(b"\r\n", b"") and b.endswith(b"\r\n") and all(c < 128 for c in b))
        check(f"{name}: runs scripts\\bots_back.ps1 with -ExecutionPolicy Bypass and pauses", script in b and b"-ExecutionPolicy Bypass" in b, b[-300:])
        if extra:
            check(f"{name}: an old folder without the script gets the UPDATE_FROM_ZIP fix, nothing else", extra in b and b"UPDATE_FROM_ZIP.bat" in b)
    for rel in ("scripts/bots_back.ps1", "scripts/pc_report_task.ps1"):
        check(f"{rel}: ASCII only (Windows PowerShell 5.1 reads it without a BOM)", all(c < 128 for c in rb(rel)))
    ps = rb("scripts/bots_back.ps1").decode()
    code = "\n".join(ln for ln in ps.splitlines() if not ln.lstrip().startswith("#"))
    check("bots_back.ps1: never START_BOT / engine.go / the live phrase / NINJATRADER_LIVE / auto-resume opt-in (paper only)",
          not re.search(r"START_BOT\.bat\"|engine\.go|I ACCEPT LIVE RISK|NINJATRADER_LIVE|enable-auto-resume|stop_bot\.ps1", code.split("<#")[0] + code.split("#>")[-1]))
    check("bots_back.ps1: starts the server only through scripts\\run_bot.ps1 (the UPDATE.bat start), never stops one",
          "run_bot.ps1" in ps and "Stop-Process" not in ps and "stop_bot" not in ps.split("#>")[-1])
    for rel in ("tools/bots_back.py", "tools/pc_report.py"):
        src = rb(rel).decode()
        body = src.split('"""', 2)[-1]
        check(f"{rel}: no live_model / engine file writes, no live phrase, no order route",
              "live_model" not in body and "I ACCEPT LIVE RISK" not in src and "LIVE_PHRASE" not in body and "/api/live/kill" not in src
              and not re.search(r"open\([^)]*engine", body))
    check("bots_back.py: the only POST is /api/live/start on 127.0.0.1", rb("tools/bots_back.py").decode().count('"POST"') == 1
          and "127.0.0.1" in rb("tools/bots_back.py").decode())
    gi = rb(".gitignore").decode()
    check(".gitignore: data/pc_report/, data/bots_back.json, ntfy.json, .olympus/", all(x in gi for x in ("data/pc_report/", "data/bots_back.json", "ntfy.json", ".olympus/")))
    feed = json.loads(rb("tools/web_public/status_feed.json"))
    check("status_feed.json: https ntfy base and a long random public topic, no key-like field",
          feed["ntfy"].startswith("https://") and re.fullmatch(r"olympus-nq-status-[0-9a-f]{16}", feed["topic"])
          and not any(k in feed for k in ("token", "key", "secret", "password")), feed)
    doc = rb("docs/BOTS_BACK.md").decode()
    steps = re.search(r"## Your 3 steps\n(.*?)\n## ", doc, re.S)
    n = len(re.findall(r"^\d\. ", steps.group(1), re.M)) if steps else 0
    cmds = re.findall(r"`(python [^`]*|powershell [^`]*|pwsh [^`]*)`", steps.group(1)) if steps else []
    check("docs/BOTS_BACK.md: the owner's steps on top, at most 3, at most one copy-paste line",
          steps is not None and doc.index("## Your 3 steps") < doc.index("## What breaks") and 1 <= n <= 3 and len(cmds) <= 1
          and "```" not in steps.group(1), (n, cmds))


# ============================================================================================== fakes
class FakeHTTP:
    """http(method, url, body, headers, timeout) -> (status, text): the bot server's ping and ntfy.sh, recorded."""

    def __init__(self, server=True, ntfy_status=200):
        self.server, self.ntfy_status, self.calls = server, ntfy_status, []

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        self.calls.append({"m": method, "url": url, "body": (body or b"").decode("utf-8") if isinstance(body, bytes) else body, "h": dict(headers or {})})
        if url.startswith("http://127.0.0.1"):
            return (200, '{"ok": true}') if self.server else (0, "ConnectionRefusedError")
        if url.startswith("https://ntfy.sh/"):
            return self.ntfy_status, "{}"
        return 0, "unexpected host"

    def posts(self, topic=None):
        return [c for c in self.calls if c["m"] == "POST" and (topic is None or c["url"].endswith("/" + topic))]


class Box:
    """A temp bot folder + settings folder; env for the reporter."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="bb_", dir=os.environ.get("LE_TEST_TMP") or None)
        self.root = os.path.join(self.dir, "root")
        self.work = os.path.join(self.dir, "work")
        os.makedirs(os.path.join(self.root, "logs", "pc_hb"))
        self.env = {"OLYMPUS_HOME": os.path.join(self.dir, "home"), "LE_PR_T_NT": "1", "LE_PR_T_MARKET": "1"}

    def hb(self, payload):
        with open(os.path.join(self.root, "logs", "pc_hb", "heartbeat.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def run(self, http, now, **kw):
        old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        try:
            return R.run_once(work=self.work, http=http, root=self.root, now=now, feed_problem=lambda: None, say=lambda *_: None, **kw)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def topic(self):
        old = os.environ.get("OLYMPUS_HOME")
        os.environ["OLYMPUS_HOME"] = self.env["OLYMPUS_HOME"]
        try:
            return R.ensure_topic()
        finally:
            if old is None:
                os.environ.pop("OLYMPUS_HOME", None)
            else:
                os.environ["OLYMPUS_HOME"] = old

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def weekday_10am_et():
    """A fixed Thursday 10:00 ET (entry hours, market open) as unix seconds."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    return int(dt.datetime(2026, 11, 12, 10, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())


# ============================================================================================== 2 pc_report
def reporter():
    now = weekday_10am_et()
    feed = R.status_feed()
    b = Box()
    try:
        cfg = b.topic()
        check("topic: three words + four digits, saved outside the repo, file mode 600 where it applies",
              re.fullmatch(r"nq-[a-z]+-[a-z]+-[a-z]+-\d{4}", cfg["topic"]) and not R.inside_repo(cfg["path"])
              and (os.name == "nt" or stat.S_IMODE(os.stat(cfg["path"]).st_mode) == 0o600), cfg)
        check("topic: made once (a second setup keeps it)", b.topic()["topic"] == cfg["topic"])
        # ---- no heartbeat at all
        h = FakeHTTP(server=False)
        rec = b.run(h, now)
        check("no heartbeat ever: no status posted (nothing honest to show), the problem is said, bot-down alert seeded as a condition",
              not h.posts(feed["topic"]) and any("never reported" in e for e in rec["errors"]) and "bot_down" in rec["problems"], (rec, h.calls))
        check("first run: a condition is pushed (bot down), never a trade", [c["h"].get("Title") for c in h.posts(cfg["topic"])] == ["Bot down"], h.posts(cfg["topic"]))
        shutil.rmtree(b.work)
        # ---- a running bot, in a trade, BLITZ on account C
        hb = hb_payload(now - 120)
        hb["account_c"] = account_c_block(now)
        b.hb(hb)
        h = FakeHTTP()
        rec = b.run(h, now)
        st = json.load(open(os.path.join(b.work, "status.json"), encoding="utf-8"))
        raw = json.dumps(st, separators=(",", ":"), ensure_ascii=False)
        check("status: under 3,900 bytes (ntfy keeps it a message, not a file)", len(raw.encode("utf-8")) <= R.MAX_STATUS_BYTES, len(raw.encode()))
        check("status: the live.json shape (kind le-live, lite, pc, pc_verdict, board.lit / blitz cards, accounts with id + conn + empty lists)",
              st["kind"] == "le-live" and st["lite"] is True and st["pc"]["running"] is True and st["pc_verdict"]["code"] == "TRADING"
              and st["board"]["lit"]["room"] == 2000.0 and st["board"]["lit"]["mll"] == 2000.0 and st["board"]["blitz"]["room"] == 1000.0
              and st["accounts"][0]["id"] and st["accounts"][0]["conn"]["t"] and st["accounts"][0]["trades"] == [] and st["accounts"][0]["days"] == [], st)
        check("status: t is the bot's own heartbeat time, not now; reporter.t is now", st["t"] == now - 120 and st["reporter"]["t"] == now
              and st["pc"]["t"] == now - 120, (st.get("t"), st.get("reporter")))
        check("status: no secret, no confirm phrase, no push key, no local path",
              not re.search(r"ghp_|I ACCEPT|push_pk|BPUBLICKEY|C:\\\\Users|token", raw), re.findall(r"ghp_\w+|push_pk|C:\\\\Users", raw))
        sp = h.posts(feed["topic"])
        check("status: posted once to the public status topic with priority min, as the plain body",
              len(sp) == 1 and sp[0]["h"].get("Priority") == "min" and json.loads(sp[0]["body"])["t"] == now - 120, sp)
        check("first run with trades: what is there is only recorded (no trade push)", not [c for c in h.posts(cfg["topic"]) if "trade" in c["h"].get("Title", "")],
              h.posts(cfg["topic"]))
        check("a fresh first run with a healthy bot pushes nothing", not h.posts(cfg["topic"]), h.posts(cfg["topic"]))
        rows = rec["card"]
        check("card: six lines + NEXT; bots, feed, trade, room, report, window", [r[1] for r in rows] == ["BOTS", "FEED", "TRADE", "ROOM", "REPORT", "WINDOW", "NEXT"]
              and "LIT running" in rows[0][2] and "SHORT 6" in rows[2][2] and "LIT $2,000 of $2,000" in rows[3][2] and cfg["topic"] in rows[4][2], rows)
        # ---- a huge payload still fits
        big = hb_payload(now - 60, n_trades=60)
        big["account_c"] = account_c_block(now)
        snap = R.gather(now, root=b.root, env=b.env, http=FakeHTTP(), feed_problem=lambda: None)
        snap["hb"], snap["hb_t"] = big, now - 60
        from engine import live_publish
        snap["live"] = live_publish.build(big, now=now - 60)
        for a in snap["live"].get("accounts") or []:
            a["name"] = "N" * 900
        lt = R.lite(snap)
        check("status: a much bigger payload is trimmed to fit, still with the LIT card", R._size(lt) <= R.MAX_STATUS_BYTES and lt.get("trimmed")
              and lt["board"]["lit"]["room"] == 2000.0, R._size(lt))
        # ---- the trade closes: one push, with $ and R; the status moves on
        hb2 = json.loads(json.dumps(hb))
        hb2["acct"]["trades"].append({"day": "2026-11-12", "entry_t": now - 1500, "exit_t": now + 700, "side": "SHORT", "qty": 6, "entry": 25100.25,
                                      "exit_px": 25000.0, "pnl": 1203.0, "r": 3.4, "exit": "TARGET"})
        hb2["acct"]["position"], hb2["position"], hb2["t"] = None, False, now + 780
        b.hb(hb2)
        h = FakeHTTP()
        rec = b.run(h, now + 900)
        ps = h.posts(cfg["topic"])
        check("trade closed: exactly one push, title with $, body with R and the account kind",
              len(ps) == 1 and ps[0]["h"]["Title"].startswith("LIT trade closed +$") and "+3.4R" in ps[0]["body"] and "Real account" in ps[0]["body"], ps)
        check("push headers are ASCII (HTTP headers)", all(all(ord(ch) < 128 for ch in v) for c in ps for v in c["h"].values()))
        hb2["t"] = now + 1740
        b.hb(hb2)
        h = FakeHTTP()
        b.run(h, now + 1800)
        check("the same trade is never pushed twice", not h.posts(cfg["topic"]), h.posts(cfg["topic"]))
        # ---- a failed push is retried
        hb3 = json.loads(json.dumps(hb2))
        hb3["acct"]["trades"].append({"day": "2026-11-12", "entry_t": now + 2000, "exit_t": now + 2300, "side": "LONG", "qty": 3, "entry": 25010.0,
                                      "exit_px": 25000.0, "pnl": -60.0, "r": -1.0, "exit": "STOP"})
        hb3["t"] = now + 2400
        b.hb(hb3)
        h = FakeHTTP(ntfy_status=429)
        rec = b.run(h, now + 2500)
        check("ntfy rate limit: soft, said plainly", any("rate limit" in e for e in rec["errors"]) and rec["ok"] is False, rec["errors"])
        hb3["t"] = now + 3340
        b.hb(hb3)
        h = FakeHTTP()
        b.run(h, now + 3400)
        ps = h.posts(cfg["topic"])
        check("a push that failed is sent on the next run", len(ps) == 1 and "-$60" in ps[0]["h"]["Title"] and "-1.0R" in ps[0]["body"], ps)
        # ---- the bot server stops answering, the market is open
        h = FakeHTTP(server=False)
        rec = b.run(h, now + 3600)
        ps = h.posts(cfg["topic"])
        st = json.load(open(os.path.join(b.work, "status.json"), encoding="utf-8"))
        check("bot down: one push, the status says DOWN and reporter.server false (t stays the heartbeat's)",
              [c["h"]["Title"] for c in ps] == ["Bot down"] and st["pc_verdict"]["code"] == "DOWN" and st["reporter"]["server"] is False
              and st["t"] == now + 3340, (ps, st.get("pc_verdict")))
        check("card: BOTS is FIX and NEXT says BOTS_BACK.bat", rec["card"][0][0] == "FIX" and "BOTS_BACK.bat" in rec["card"][-1][2], rec["card"])
        h = FakeHTTP(server=False)
        b.run(h, now + 4500)
        check("bot down: not repeated within 3 hours", not h.posts(cfg["topic"]), h.posts(cfg["topic"]))
        h = FakeHTTP(server=False)
        b.run(h, now + 3600 + R.REMIND_S + 60)
        check("bot down: one reminder after 3 hours", [c["h"]["Title"] for c in h.posts(cfg["topic"])] == ["Bot down (still)"], h.posts(cfg["topic"]))
        b.env["LE_PR_T_MARKET"] = "0"
        h = FakeHTTP(server=False)
        b.run(h, now + 3600 + 2 * R.REMIND_S + 120)
        check("market closed: the problem is not a problem (back to normal, no reminder)", [c["h"]["Title"] for c in h.posts(cfg["topic"])] == ["Back to normal"],
              h.posts(cfg["topic"]))
        b.env["LE_PR_T_MARKET"] = "1"
        # ---- FEED STALE and NinjaTrader closed
        hb4 = json.loads(json.dumps(hb3))
        hb4["t"] = now + 20000
        hb4["health"]["feed"].update(age_1m_s=420, stale=True)
        b.hb(hb4)
        h = FakeHTTP()
        rec = b.run(h, now + 20030)
        check("FEED STALE: one push, card FEED is FIX", [c["h"]["Title"] for c in h.posts(cfg["topic"])] == ["FEED STALE"] and rec["card"][1][0] == "FIX",
              (h.posts(cfg["topic"]), rec["card"][1]))
        b.env["LE_PR_T_NT"] = "0"
        h = FakeHTTP()
        rec = b.run(h, now + 20100)
        titles = sorted(c["h"]["Title"] for c in h.posts(cfg["topic"]))
        check("NinjaTrader closed: its own push (and the feed line is replaced by it)", titles == ["Back to normal", "NinjaTrader closed"], titles)
        b.env["LE_PR_T_NT"] = "1"
        # ---- an old trade seen for the first time after the PC was off is recorded, not pushed
        hb5 = json.loads(json.dumps(hb4))
        hb5["health"]["feed"].update(age_1m_s=20, stale=False)
        hb5["acct"]["trades"].append({"day": "2026-11-10", "entry_t": now - 3 * 86400, "exit_t": now - 3 * 86400 + 600, "side": "LONG", "qty": 2,
                                      "entry": 25000.0, "exit_px": 25010.0, "pnl": 40.0, "r": 0.4, "exit": "CUT"})
        b.hb(hb5)
        h = FakeHTTP()
        b.run(h, now + 20200)
        check("a trade older than 6 hours is recorded, never pushed late", not [c for c in h.posts(cfg["topic"]) if "trade" in c["h"]["Title"]],
              h.posts(cfg["topic"]))
        # ---- dry run
        h = FakeHTTP()
        b.run(h, now + 21000, dry=True)
        check("--dry-run: no POST at all", not h.posts(), h.posts())
        check("the real HTTP helper refuses while LE_PR_NO_NET=1 (tests never reach the internet)", R.default_http("GET", "https://ntfy.sh/x")[0] == 0)
    finally:
        b.cleanup()
    inside = os.path.join(ROOT, "data", "pc_report_test_home")
    old = os.environ.get("OLYMPUS_HOME")
    os.environ["OLYMPUS_HOME"] = inside
    try:
        try:
            R.ensure_topic()
            ok = False
        except RuntimeError:
            ok = True
        check("the alert topic is never saved inside the repo", ok and not os.path.exists(inside))
    finally:
        shutil.rmtree(inside, ignore_errors=True)
        if old is None:
            os.environ.pop("OLYMPUS_HOME", None)
        else:
            os.environ["OLYMPUS_HOME"] = old


# ============================================================================================== 3 bots_back.py
def helpers():
    d = tempfile.mkdtemp(prefix="bbh_")
    real = BB.HTTP
    try:
        def fake(running, server=True, start_ok=True):
            calls = []

            def http(method, path, body=None, port=None, timeout=5):
                calls.append((method, path, body))
                if not server:
                    return 0, {}
                if path == "/api/health/ping":
                    return 200, {"ok": True}
                if path == "/api/live/state":
                    return 200, {"running": running}
                if path == "/api/live/start":
                    return (200, {"ok": True}) if start_ok else (200, {"ok": False, "error": "kill switch on"})
                return 404, {}
            return http, calls

        def rec(cfg):
            p = os.path.join(d, "autostart.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"saved_at": time.time() - 9 * 86400, "cfg": cfg, "mode": "x"}, fh)
            return p

        nosleep = lambda s: None  # noqa: E731
        BB.HTTP, calls = fake(True)
        check("resume: a running bot is left alone (no start)", BB.resume_paper(path=rec({"adapter": "paper"}), sleep=nosleep, wait_s=0) == 0
              and not [c for c in calls if c[0] == "POST"], calls)
        for label, cfg, want in (("paper", {"adapter": "paper", "sym": "NQ"}, True),
                                 ("NinjaTrader Sim101", {"adapter": "ninjatrader", "nt_account": "Sim101"}, True),
                                 ("a real NinjaTrader account", {"adapter": "ninjatrader", "nt_account": "MFFUEVBLDR123456"}, False),
                                 ("NinjaTrader without its own account name (could be the eval from .env.local.ps1)", {"adapter": "ninjatrader"}, False),
                                 ("Tradovate (counted as live)", {"adapter": "tradovate"}, False)):
            BB.HTTP, calls = fake(False)
            rc = BB.resume_paper(path=rec(cfg), sleep=nosleep, wait_s=0)
            posts = [c for c in calls if c[0] == "POST"]
            if want:
                check(f"resume: stopped + last start {label} -> started with exactly that start", rc == 0 and posts == [("POST", "/api/live/start", cfg)], (rc, calls))
            else:
                check(f"resume: stopped + last start {label} -> NEVER started (START_BOT.bat is the owner's)", rc == 3 and not posts, (rc, calls))
        BB.HTTP, calls = fake(False)
        check("resume: no saved start (the last stop was on purpose) -> stays stopped", BB.resume_paper(path=os.path.join(d, "none.json"), sleep=nosleep, wait_s=0) == 3
              and not [c for c in calls if c[0] == "POST"])
        BB.HTTP, calls = fake(False, server=False)
        check("resume: server down -> 2, nothing sent", BB.resume_paper(path=rec({"adapter": "paper"}), sleep=nosleep, wait_s=0) == 2 and len(calls) == 1)
        BB.HTTP, calls = fake(False, start_ok=False)
        check("resume: a refused start is reported (exit 1)", BB.resume_paper(path=rec({"adapter": "paper"}), sleep=nosleep, wait_s=0) == 1)
        seq = iter(["stale 9 min", "stale 9 min", None])
        check("feed: fresh at once -> 0", BB.wait_feed(5, problem=lambda: None, is_open=lambda: True, sleep=nosleep) == 0)
        check("feed: market closed and old bars -> 0 (normal), no wait", BB.wait_feed(5, problem=lambda: "old", is_open=lambda: False, sleep=nosleep) == 0)
        check("feed: comes back while waiting -> 0", BB.wait_feed(3600, problem=lambda: next(seq), is_open=lambda: True, sleep=nosleep) == 0)
        check("feed: still stale after the wait -> 1", BB.wait_feed(0, problem=lambda: "stale", is_open=lambda: True, sleep=nosleep) == 1)
    finally:
        BB.HTTP = real
        shutil.rmtree(d, ignore_errors=True)


# ============================================================================================== 4 pwsh
FAKE_PY = """#!/bin/sh
echo "PY $*" >> "$FAKE_LOG"
case "$*" in
  *--server-up*) exit ${FAKE_SERVER:-1};;
  *--wait-feed*) echo "  [OK] fake feed fresh";;
  *--wait-server*) echo "  [OK] fake server answers";;
  *--resume-paper*) echo "  [OK] fake bot running";;
  *--test*) echo "  [OK] fake test push";;
  *pc_report.py) echo "  [OK] BOTS   fake card";;
esac
exit 0
"""


def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


class PsBox:
    def __init__(self, new_code=True):
        self.dir = tempfile.mkdtemp(prefix="bbps_")
        self.root = os.path.join(self.dir, "root")
        os.makedirs(os.path.join(self.root, "scripts"))
        os.makedirs(os.path.join(self.root, "tools"))
        shutil.copy(os.path.join(ROOT, "scripts", "bots_back.ps1"), os.path.join(self.root, "scripts"))
        if new_code:
            shutil.copy(os.path.join(ROOT, "scripts", "pc_report_task.ps1"), os.path.join(self.root, "scripts"))
            for n in ("bots_back.py", "pc_report.py"):
                open(os.path.join(self.root, "tools", n), "w").close()
        open(os.path.join(self.root, "scripts", "run_bot.ps1"), "w").close()
        self.py = os.path.join(self.dir, "fakepy")
        with open(self.py, "w") as fh:
            fh.write(FAKE_PY)
        os.chmod(self.py, 0o755)
        self.home = os.path.join(self.dir, "home")
        self.pylog, self.winlog = os.path.join(self.dir, "py.log"), os.path.join(self.dir, "win.log")

    def run(self, pwsh, args=(), server=False, nt=False):
        env = {**os.environ, "FAKE_LOG": self.pylog, "LE_BB_T_LOG": self.winlog, "LE_BB_T_NT": "1" if nt else "0", "OLYMPUS_HOME": self.home,
               "FAKE_SERVER": "0" if server else "1"}
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-NonInteractive", "-File", os.path.join(self.root, "scripts", "bots_back.ps1"),
                            "-Python", self.py, *args], capture_output=True, text=True, timeout=180, env=env)
        return r.returncode, r.stdout + r.stderr

    def lines(self, p):
        try:
            with open(p) as fh:
                return [ln.strip() for ln in fh if ln.strip()]
        except OSError:
            return []

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def pwsh_runs(pwsh):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(ROOT, "tests", "win_harness", "lint51.ps1"),
                        os.path.join(ROOT, "scripts", "bots_back.ps1"), os.path.join(ROOT, "scripts", "pc_report_task.ps1")],
                       capture_output=True, text=True, timeout=300)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint: no PowerShell-7-only syntax in bots_back.ps1 / pc_report_task.ps1", r.returncode == 0 and not found, found or r.stderr)
    b = PsBox()
    try:
        rc, out = b.run(pwsh, ["-DryRun"])
        check("-DryRun: says the five steps, changes nothing (no marker, no log, no python call)",
              rc == 0 and "DRY RUN" in out and not os.path.exists(b.home) and not b.lines(b.winlog) and not b.lines(b.pylog)
              and not os.path.exists(os.path.join(b.root, "data")), out)
        rc, out = b.run(pwsh)
        py = [ln.split("tools/")[-1] for ln in b.lines(b.pylog)]
        win = b.lines(b.winlog)
        check("full run: exit 0, five steps then the card", rc == 0 and all(f"{i}/5" in out for i in (1, 2, 3)) and "4/5 report task" in out and "fake card" in out, out)
        check("full run: GitHub-free marker made in the settings folder", os.path.exists(os.path.join(b.home, "no_github")))
        check("full run: python steps in order (feed, server, wait, resume paper, test push, report)",
              py == ["bots_back.py --wait-feed 300", "bots_back.py --server-up", "bots_back.py --wait-server 120", "bots_back.py --resume-paper",
                     "pc_report.py --test", "pc_report.py"], py)
        check("full run: NinjaTrader opened (it was closed), the server started through run_bot.ps1, the task registered every 15 min",
              len(win) == 3 and win[0].startswith("START NT") and win[1].startswith("START SERVER") and win[1].endswith("run_bot.ps1")
              and win[2].startswith("TASK REGISTER OlympusPCReport every 15 min") and "pc_report.py\" --quiet" in win[2], win)
        check("full run: never START_BOT / engine.go / a live phrase", not re.search(r"engine\.go|START_BOT|ACCEPT", " ".join(py + win)))
        open(b.pylog, "w").close()
        open(b.winlog, "w").close()
        rc, out = b.run(pwsh, server=True, nt=True)
        py = [ln.split("tools/")[-1] for ln in b.lines(b.pylog)]
        win = b.lines(b.winlog)
        check("second run (server up, NinjaTrader open): the running bot is left alone, nothing started twice, task replaced",
              rc == 0 and "already running (left alone)" in out and "--wait-server" not in " ".join(py) and win == [w for w in win if w.startswith("TASK REGISTER")]
              and len(win) == 1 and "GitHub-free mode already on" in out, (out, win, py))
        open(b.pylog, "w").close()
        open(b.winlog, "w").close()
        rc, out = b.run(pwsh, ["-NoResume"], server=True, nt=True)
        py = [ln.split("tools/")[-1] for ln in b.lines(b.pylog)]
        check("-NoResume (GO_LIVE_EVAL.bat part 1): no paper start resumed, the rest the same, still never a live phrase",
              rc == 0 and "--resume-paper" not in " ".join(py) and "no paper start resumed" in out and "pc_report.py" in py
              and not re.search(r"engine\.go|START_BOT|ACCEPT", " ".join(py)), (out, py))
        rc, out = b.run(pwsh, ["-Remove"])
        check("-Remove: the task and the marker BOTS_BACK made are gone; the bot is not touched",
              rc == 0 and b.lines(b.winlog)[-1] == "TASK REMOVE OlympusPCReport" and not os.path.exists(os.path.join(b.home, "no_github"))
              and not [ln for ln in b.lines(b.pylog) if "--" in ln and "Remove" in ln], out)
        os.makedirs(b.home, exist_ok=True)
        with open(os.path.join(b.home, "no_github"), "w") as fh:
            fh.write("made by PUBLISH_NQ")
        rc, out = b.run(pwsh, server=True, nt=True)
        rc, out = b.run(pwsh, ["-Remove"])
        check("-Remove: a marker someone else made (PUBLISH_NQ.bat) is kept", os.path.exists(os.path.join(b.home, "no_github")) and "left as it was" in out, out)
        git = shutil.which("git")
        if git:
            subprocess.run([git, "init", "-q", b.root], capture_output=True, timeout=60)
            rc, out = b.run(pwsh, server=True, nt=True)
            g = subprocess.run([git, "-C", b.root, "config", "--local", "--get", "credential.interactive"], capture_output=True, text=True).stdout.strip()
            rc, out = b.run(pwsh, ["-Remove"])
            g2 = subprocess.run([git, "-C", b.root, "config", "--local", "--get", "credential.interactive"], capture_output=True, text=True).stdout.strip()
            check("git: credential.interactive=never set in this folder only (no GitHub sign-in window), undone by -Remove", g == "never" and g2 == "", (g, g2))
    finally:
        b.cleanup()
    old = PsBox(new_code=False)
    try:
        rc, out = old.run(pwsh)
        check("an old folder (no tools\\bots_back.py): refused with the UPDATE_FROM_ZIP fix, nothing changed",
              rc == 1 and "UPDATE_FROM_ZIP.bat" in out and not os.path.exists(old.home) and not old.lines(old.winlog), out)
    finally:
        old.cleanup()


# ============================================================================================== 5 node
NODE_TEST = r"""
import { createRequire } from 'module';
import { pathToFileURL } from 'url';
const require = createRequire(import.meta.url);
const [feedPath, truthPath, litePath] = process.argv.slice(2);
const F = require(feedPath);
const T = await import(pathToFileURL(truthPath).href);
const fs = require('fs');
const lite = JSON.parse(fs.readFileSync(litePath, 'utf8'));
const out = {};
const line = (j, time) => JSON.stringify({ id: 'x' + time, time, event: 'message', topic: 't', message: JSON.stringify(j) });
const older = { ...lite, t: lite.t - 600, reporter: { ...lite.reporter, t: lite.reporter.t - 900 }, board: { ...lite.board, lit: { ...lite.board.lit, room: 1 } } };
const nd = [JSON.stringify({ event: 'open' }), 'junk', line({ kind: 'other', t: 5 }, 1), line(older, 2), line(lite, 3), line({ kind: 'le-live', t: null }, 4)].join('\n');
out.parsed = F.parseLatest(nd);
out.parsedEmpty = F.parseLatest('');
out.urls = F.feedUrls({ ntfy: 'https://ntfy.sh/', topic: 'olympus-nq-status-0123456789abcdef' });
out.badUrls = [F.feedUrls({ ntfy: 'http://evil', topic: 'a' }), F.feedUrls({ topic: '../x' }), F.feedUrls(null)];
const site = { built: '2026-11-07T10:00:00Z', live: { pc: { t: lite.t - 5 * 86400, running: true, host: 'PC' } },
  board: { t: lite.t - 5 * 86400, data_t: lite.t - 5 * 86400, map: { levels: [1, 2] }, progress: { lit: {} }, trades: [{ acct: 'lit', entry_t: 1, usd: 5 }],
           lit: { id: 'lit', name: 'Zlarior', room: 100, mll: 2000, balance: 48100, stages: ['x'] } },
  accounts: [] };
const home = F.overlayHome(site, lite, lite.reporter.t);
out.home = { pcT: home.live.pc.t, running: home.live.pc.running, verdict: (home.live.pc_verdict || {}).code, map: home.board.map, progress: !!home.board.progress,
  litRoom: home.board.lit.room, stages: home.board.lit.stages, trades: home.board.trades.length, siteUntouched: site.board.lit.room === 100 };
const canon = T.canonHome(home, lite.reporter.t);
out.canon = { room: canon.truth.accounts.lit.room, t: canon.truth.accounts.lit.t, age: canon.truth.ages.pc.age, line: canon.truth.ages.line };
const newer = { ...site, live: { pc: { t: lite.t + 100 } } };
out.notOlder = F.overlayHome(newer, lite) === newer;
out.mergeSiteNewer = F.mergeBoard({ data_t: lite.t + 10, lit: { room: 7 } }, lite.board).lit.room;
out.toLive = F.toLive(lite, site.board).board.map;
const calls = [];
const fake = async (u) => { calls.push(u); if (u.endsWith('status_feed.json')) return { ok: true, json: async () => ({ ntfy: 'https://ntfy.sh', topic: 'olympus-nq-status-0123456789abcdef' }) };
  if (u.includes('since=latest')) return { ok: false, status: 400 }; return { ok: true, text: async () => nd }; };
out.fetched = (await F.fetchLatest({ fetch: fake })) ? (await F.fetchLatest({ fetch: fake })).t : null;
out.fetchCalls = calls.slice(0, 3);
out.fetchFail = await F.fetchLatest({ fetch: async () => { throw new Error('offline'); } });
console.log(JSON.stringify(out));
"""


def node_runs(node):
    now = weekday_10am_et()
    b = Box()
    try:
        b.topic()
        hb = hb_payload(now - 120)
        b.hb(hb)
        b.run(FakeHTTP(), now)
        lite_path = os.path.join(b.work, "status.json")
        mjs = os.path.join(b.dir, "t.mjs")
        with open(mjs, "w") as fh:
            fh.write(NODE_TEST)
        r = subprocess.run([node, mjs, os.path.join(ROOT, "tools", "web_public", "pc_feed.js"), os.path.join(ROOT, "tools", "web_public", "olympus", "truth.js"),
                            lite_path], capture_output=True, text=True, timeout=120)
        if not check("node: pc_feed.js runs", r.returncode == 0, r.stderr[-800:]):
            return
        o = json.loads(r.stdout.strip().splitlines()[-1])
        lite = json.load(open(lite_path, encoding="utf-8"))
        check("parseLatest: the newest PC status wins, junk / other kinds / t null are ignored", o["parsed"]["t"] == lite["t"] and o["parsed"]["board"]["lit"]["room"] == 2000
              and o["parsedEmpty"] is None, o["parsed"].get("t"))
        check("feedUrls: since=latest then a 30-minute window; http / odd topics refused",
              o["urls"] == ["https://ntfy.sh/olympus-nq-status-0123456789abcdef/json?poll=1&since=latest",
                            "https://ntfy.sh/olympus-nq-status-0123456789abcdef/json?poll=1&since=30m"] and o["badUrls"] == [[], [], []], o["urls"])
        h = o["home"]
        check("overlayHome: the PC's numbers over a 5-day-old home.json; the site's map / progress / trades / extra card keys kept; input unchanged",
              h["pcT"] == lite["t"] and h["running"] is True and h["verdict"] == "TRADING" and h["map"] == {"levels": [1, 2]} and h["progress"]
              and h["litRoom"] == 2000 and h["stages"] == ["x"] and h["trades"] >= 1 and h["siteUntouched"], h)
        check("truth.js canonHome on it: drawdown left and the PC report age come from the PC status",
              o["canon"]["room"] == 2000 and o["canon"]["t"] == lite["t"] and o["canon"]["age"] == 120 and "2 minutes" in o["canon"]["line"], o["canon"])
        check("an older PC status never replaces newer site numbers", o["notOlder"] is True and o["mergeSiteNewer"] == 7)
        check("toLive keeps the site's board sections for board.js", o["toLive"] == {"levels": [1, 2]})
        check("fetchLatest: status_feed.json, then ntfy (since=latest refused -> the 30-minute window); offline -> null",
              o["fetched"] == lite["t"] and o["fetchCalls"][0] == "status_feed.json" and "since=latest" in o["fetchCalls"][1] and "since=30m" in o["fetchCalls"][2]
              and o["fetchFail"] is None, o)
    finally:
        b.cleanup()


def go_live_static():
    """GO_LIVE_EVAL.bat (owner 2026-11-12: Zlarior + ATLAS on the eval tonight): part 1 = bots_back.ps1 -NoResume, part 2 = engine.go
    (START BOT, where the owner types the live phrase himself); the file never types or holds the phrase and never sets the live switch."""
    bat = rb("GO_LIVE_EVAL.bat").decode("ascii")
    code = [ln for ln in bat.splitlines() if ln.strip() and not ln.lower().startswith("rem ")]
    body = "\n".join(code)
    i1, i2 = body.find("bots_back.ps1\" -NoResume"), body.find("-m engine.go")
    check("GO_LIVE_EVAL.bat: CRLF, bots_back.ps1 -NoResume first, then engine.go (START BOT); old folder -> UPDATE_FROM_ZIP first",
          "\r\n" in bat and 0 < i1 < i2 and "UPDATE_FROM_ZIP.bat" in bat, (i1, i2))
    check("GO_LIVE_EVAL.bat: never arms by itself (no live phrase to type, no NINJATRADER_LIVE, no --arm)",
          not [ln for ln in code if "ACCEPT" in ln or "NINJATRADER_LIVE" in ln or "--arm" in ln], code)


def main() -> int:
    go_live_static()
    static()
    reporter()
    helpers()
    pwsh = find_pwsh()
    if pwsh:
        pwsh_runs(pwsh)
    else:
        print("[SKIP] pwsh not found: the PowerShell runs were skipped")
    node = shutil.which("node")
    if node:
        node_runs(node)
    else:
        print("[SKIP] node not found: the pc_feed.js checks were skipped")
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


def test_bots_back():                       # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
