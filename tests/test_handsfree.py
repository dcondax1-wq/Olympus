"""day-handsfree (2026-11-25; owner: "I don't want to go on my PC and restart it every single time ... I want an easier process").

    python -X utf8 -m tests.test_handsfree            (~1-2 min: the writers sandbox runs the PC's own self-tests)
    python -X utf8 -m tests.test_handsfree --fast     (skips the sandbox, ~10 s)

a. Telegram commands (engine/tg_cmd.py): the allow-list (status / update / restart / pause / resume), never kill / stop / flatten /
   start / arm; the owner's PRIVATE chat only (a stranger gets no reply, a group id turns commands off); receipts are replies;
   each message once (offset + done ids); the same gates as the phone (trading hours, flat, supervised); '/update force' only
   from Telegram; '/restart' exits 75 after the receipt and 'PC is back up' follows after the restart.
b. Writers sandbox: in a temp worktree of this checkout, the PC's own writers run (the update's self-tests, the PC self-test,
   the state files of remote control / Telegram / pause / presence / hands-off / board / alert bus / auto-update / self-heal /
   NinjaScript sync / tick recorder) and `git status` must show only engine/generated_files paths and no untracked file.
c. Static gate: every module-level os.path.join(ROOT, ...) in engine/ + server.py that names a TRACKED file is either a
   generated file or on READ_ONLY below (read on the PC, written only by a cloud / manual build): a new one fails until sorted.
d. Auto-park backstop: tracked market data under data/ is parkable now; strategy / account / rule files are not (except force).
e. The stuck-update push names the phone fix (/update, /update force) and comes after 1 h.
f. NinjaScript sync (engine/ns_sync.py): LE_BUILD stamped, copy only outside trading hours + flat, one F5 line per build.
g. Reboot chain: the server start resumes an opted-in eval only after NinjaTrader connects (it opens NinjaTrader first), the
   supervisor sets LE_REMOTE / LE_SUPERVISED, the Telegram thread starts without the control branch.
"""
from __future__ import annotations

import ast
import datetime as dt
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import remote_ctl as rc  # noqa: E402
from engine import tg_cmd as tg  # noqa: E402

from zoneinfo import ZoneInfo  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
OWNER = "123456789"
TOKEN = "12345678:" + "A" * 35


def check(name, ok, info=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(': ' + str(info)[:300]) if info and not ok else ''}")
    RES.append(bool(ok))


def et(y, m, d, hh, mm=0) -> float:
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp()


# ------------------------------------------------------------------------------------------------ a. Telegram
class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.legs = []


class FakeBot:
    def __init__(self, running=True, position=None):
        self.running = running
        self.cfg = {"sym": "NQ", "adapter": "ninjatrader", "nt_account": "Sim101"}
        self.state = {"position": position}
        self.adapter = FakeAdapter()
        self._open_routed = None
        self.kill = False
        self.health = {}

    def _save_state(self):
        pass


class FakeTelegram:
    """getUpdates / sendMessage on an in-memory queue."""

    def __init__(self):
        self.queue, self.sent, self.next_id, self.offsets = [], [], 100, []

    def msg(self, text, chat=OWNER, frm=None, ctype="private", t=None, is_bot=False):
        self.next_id += 1
        self.queue.append({"update_id": self.next_id, "message": {
            "message_id": self.next_id * 10, "date": int(t), "text": text,
            "chat": {"id": int(chat), "type": ctype}, "from": {"id": int(frm or chat), "is_bot": is_bot}}})
        return self.next_id

    def __call__(self, method, url, body=None, headers=None):
        q = json.loads(body.decode()) if body else {}
        if url.endswith("/getUpdates"):
            off = int(q.get("offset") or 0)
            self.offsets.append(off)
            return 200, json.dumps({"ok": True, "result": [u for u in self.queue if u["update_id"] >= off]})
        if url.endswith("/sendMessage"):
            self.sent.append(q)
            return 200, json.dumps({"ok": True})
        return 404, "{}"


def tg_world(tmp, clock_t, bot=None, hooks=None, env=None):
    fake = FakeTelegram()
    exits = []
    h = {"exit": exits.append, "beat": lambda: {"ok": True}, "deliberate": lambda *_: True}
    h.update(hooks or {})
    ctl = rc.RemoteControl(bot or FakeBot(), hooks=h, cwd=tmp, done_path=os.path.join(tmp, "remote_done.json"),
                           notify=lambda *a, **k: None, log=lambda *_: None, clock=lambda: clock_t[0],
                           env=env if env is not None else {"LE_REMOTE": "1", "LE_SUPERVISED": "1"})
    cfg = {"telegram": {"token": TOKEN, "chat_id": OWNER}}
    poll = tg.TgCommands(ctl, cfg_fn=lambda: cfg, http=fake, path=os.path.join(tmp, "tg_cmd.json"), clock=lambda: clock_t[0],
                         env={}, started_at=clock_t[0])
    return fake, ctl, poll, exits, cfg


def test_telegram():
    P = tg.parse_text
    ok = all(P(t)[0] and P(t)[0]["cmd"] == c for t, c in (("/status", "status"), ("status", "status"), ("/update", "update"),
                                                           ("/restart", "restart"), ("/resume", "resume_entries"),
                                                           ("/status@OlympusBot", "status"), ("/STATUS", "status")))
    check("a1. allow-list: /status /update /restart /resume (also without '/', with @Bot, any case)", ok)
    check("a2. /pause defaults to tomorrow; /pause 14:00 / YYYY-MM-DD; junk refused",
          P("/pause")[0] == {"cmd": "pause", "until": "tomorrow"} and P("/pause 14:00")[0]["until"] == "14:00"
          and P("/pause 2026-11-27")[0]["until"] == "2026-11-27" and P("/pause now please")[0] is None)
    bad = ["/kill", "/stop", "/flatten", "/start Sim101", "/arm", "/add_account x", "/switch blitz", "buy 1 NQ", "/long", "rm -rf"]
    check("a3. never from Telegram: kill / stop / flatten / start / arm / add_account / switch / orders (all -> no command)",
          all(P(t)[0] is None and P(t)[1] for t in bad), [t for t in bad if P(t)[0]])
    check("a4. '/update force' is the only update argument", P("/update force")[0] == {"cmd": "update", "force": True}
          and P("/update now")[0] is None and P("/help")[0] is None and "/status" in P("/help")[1])

    m = {"chat": {"id": int(OWNER), "type": "private"}, "from": {"id": int(OWNER)}}
    check("a5. owner = the alerts chat id, private chat, from the owner himself",
          tg.is_owner(m, OWNER) and not tg.is_owner({**m, "from": {"id": 5}}, OWNER)
          and not tg.is_owner({**m, "chat": {"id": int(OWNER), "type": "group"}}, OWNER)
          and not tg.is_owner({**m, "from": {"id": int(OWNER), "is_bot": True}}, OWNER)
          and tg.owner_chat({"telegram": {"chat_id": "-100200"}}) is None and tg.owner_chat({}) is None)

    tmp = tempfile.mkdtemp(prefix="le_tg_")
    try:
        now = [et(2026, 11, 25, 17, 30)]                    # Wednesday, after the close
        fake, ctl, poll, exits, cfg = tg_world(tmp, now)
        fake.msg("/status", t=now[0] - 5)
        fake.msg("/status", chat="999", t=now[0] - 5)          # a stranger
        fake.msg("/flatten", t=now[0] - 5)
        out = poll.tick()
        replies = [s["text"] for s in fake.sent]
        check("a6. /status runs and the receipt is a REPLY to the owner's message",
              len(out) == 1 and out[0][1:3] == ("status", "done") and any("status" in r.lower() for r in replies)
              and all(s["chat_id"] == OWNER for s in fake.sent) and fake.sent[0].get("reply_to_message_id"), (out, fake.sent))
        check("a7. a stranger gets NO reply; /flatten gets a refusal line and runs nothing",
              len(fake.sent) == 2 and "never done from Telegram" in replies[1] and tg.load_state(poll.path).get("strangers") == 1,
              replies)
        n = len(fake.sent)
        out2 = poll.tick()
        check("a8. each message once (offset saved; a second poll runs nothing)", out2 == [] and len(fake.sent) == n
              and fake.offsets[-1] == fake.next_id + 1, fake.offsets)

        # trading hours: /restart and /update refused with the reason, as a reply
        now[0] = et(2026, 11, 25, 10, 0)
        fake.msg("/restart", t=now[0])
        fake.msg("/update", t=now[0])
        out = poll.tick()
        check("a9. trading hours: /restart and /update refused with the reason (same gates as the phone)",
              [o[2] for o in out] == ["refused", "refused"] and "trading hours" in fake.sent[-2]["text"] and not exits, out)

        # not flat: refused
        now[0] = et(2026, 11, 25, 18, 0)
        fake2, ctl2, poll2, exits2, _ = tg_world(tmp + "_b", now, bot=FakeBot(position={"side": "long", "qty": 1}))
        os.makedirs(tmp + "_b", exist_ok=True)
        fake2.msg("/restart", t=now[0])
        out = poll2.tick()
        check("a10. a trade open: /restart refused ('not flat'), nothing exits", out and out[0][2] == "refused"
              and "not flat" in fake2.sent[-1]["text"] and not exits2, out)

        # /restart: receipt BEFORE the exit, exit 75
        fake.msg("/restart", t=now[0])
        out = poll.tick()
        check("a11. /restart after hours: receipt sent, then exit 75 (run_bot.ps1 starts it again)",
              exits == [75] and "restarting" in fake.sent[-1]["text"] and out[0][2] == "done", (exits, fake.sent[-1:]))
        # the restarted server: a new poller, 'PC is back up' once after BACK_AFTER_S
        now[0] += 20
        poll_b = tg.TgCommands(ctl, cfg_fn=lambda: cfg, http=fake, path=poll.path, clock=lambda: now[0], env={}, started_at=now[0])
        k = len(fake.sent)
        poll_b.tick()
        early = len(fake.sent) == k
        now[0] += tg.BACK_AFTER_S + 1
        poll_b.tick()
        poll_b.tick()
        backs = [s for s in fake.sent[k:] if "back up" in s["text"]]
        check("a12. after the restart: ONE 'PC is back up' reply (not before 90 s, never twice)",
              early and len(backs) == 1 and backs[0].get("reply_to_message_id"), fake.sent[k:])

        # /update force only from Telegram; the control branch JSON cannot force
        seen = []
        fake3, ctl3, poll3, _, _ = tg_world(tmp + "_c", now, hooks={"update": lambda force=False: seen.append(force) or
                                                                    {"status": "up_to_date", "reason": "at abc"}})
        os.makedirs(tmp + "_c", exist_ok=True)
        fake3.msg("/update force", t=now[0])
        poll3.tick()
        d = rc.load_done(ctl3.done_path)
        ctl3._one({"id": "ph-1", "ts": int(now[0]), "cmd": "update", "force": True}, now[0])
        check("a13. '/update force' reaches the update as force=True; the same JSON from the control branch does not",
              seen == [True, False], seen)
        check("a14. remote_done keeps the Telegram receipt (notice ok) for the PC feed", (d.get("last") or {}).get("notice", {}).get("ok"),
              d.get("last"))

        # old messages after the PC was off: silent; 20 min old: told
        fake4, ctl4, poll4, _, _ = tg_world(tmp + "_d", now)
        os.makedirs(tmp + "_d", exist_ok=True)
        fake4.msg("/status", t=now[0] - 5 * 3600)
        fake4.msg("/status", t=now[0] - 20 * 60)
        out = poll4.tick()
        check("a15. after the PC was off: a 5 h old message is dropped silently, a 20 min old one is answered 'too old'",
              len(fake4.sent) == 1 and "too old" in fake4.sent[0]["text"] and [o[2] for o in out] == ["ignored"], fake4.sent)

        # a group chat id = commands off
        fake5 = FakeTelegram()
        p5 = tg.TgCommands(ctl4, cfg_fn=lambda: {"telegram": {"token": TOKEN, "chat_id": "-100123"}}, http=fake5,
                           path=os.path.join(tmp, "g.json"), clock=lambda: now[0], env={})
        fake5.msg("/restart", chat="-100123", frm=OWNER, ctype="group", t=now[0])
        check("a16. a group / channel chat id: commands off (no getUpdates, nothing runs)", p5.tick() == [] and not fake5.offsets)
        check("a17. LE_TG_CMD=0 switches it off", tg.TgCommands(ctl4, cfg_fn=lambda: cfg, http=fake5, path=p5.path,
                                                                 env={"LE_TG_CMD": "0"}).tick() == [] and not fake5.offsets)
        # the thread starts without the control branch (GitHub-free / no control branch) on the supervised server only
        ctl6 = rc.RemoteControl(FakeBot(), cwd=tmp, done_path=os.path.join(tmp, "rd6.json"), notify=lambda *a, **k: None,
                                log=lambda *_: None, env={"LE_REMOTE": "0"})
        check("a18. Telegram thread: off unless LE_REMOTE=1 (the supervised PC server)", ctl6.start_tg() is False)
    finally:
        for p in (tmp, tmp + "_b", tmp + "_c", tmp + "_d"):
            shutil.rmtree(p, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ b. writers sandbox
WRITERS = r'''
import os, sys, time, json, traceback
sys.path.insert(0, os.getcwd())
now = time.time()
bad = []
def run(name, fn):
    try:
        fn()
    except Exception as e:
        bad.append(f"{name}: {e.__class__.__name__}: {e}")
from engine import remote_ctl, tg_cmd, entry_pause, presence, handsoff, alert_bus, autoupdate, ns_sync, tickrec, board_events
run("remote_done", lambda: remote_ctl.save_done({"done": {"x": {"cmd": "status", "t": int(now)}}}))
run("tg_cmd", lambda: tg_cmd.save_state({"offset": 5}))
run("entry_pause", lambda: entry_pause.set_pause("tomorrow", now))
run("presence", lambda: presence.check_in("phone", 1, now))
run("handsoff", lambda: handsoff.record("pause", "phone", "x", now=now))
run("alert_bus state", lambda: alert_bus._save_state({"sent": {"k": now}}))
run("alert_bus log", lambda: alert_bus.log_fail({"t": now, "ch": "telegram", "err": "x"}))
run("autoupdate record", lambda: autoupdate.record({"t": int(now), "mode": "hourly", "status": "skipped", "reason": "x"}))
run("deliberate", lambda: autoupdate.mark_deliberate_restart("test"))
run("board", lambda: board_events.emit("bot_started", "pc", "sandbox", {}))
run("tickrec tiny", lambda: tickrec.write_tiny())
nt = os.environ["SANDBOX_NT"]
run("ns_sync", lambda: ns_sync.check(os.getcwd(), nt, now=time.mktime((2026, 11, 28, 12, 0, 0, 0, 0, -1)), flat=lambda: None))
print(json.dumps(bad))
'''


def _sandbox() -> tuple:
    """(worktree path, temp home). A detached worktree of HEAD + this checkout's uncommitted changes."""
    base = tempfile.mkdtemp(prefix="le_hf_")
    wt = os.path.join(base, "wt")
    subprocess.run(["git", "worktree", "add", "-q", "--detach", wt, "HEAD"], cwd=ROOT, check=True, capture_output=True)
    diff = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=ROOT, capture_output=True).stdout
    if diff.strip():
        subprocess.run(["git", "apply", "--whitespace=nowarn"], cwd=wt, input=diff, check=True, capture_output=True)
    for p in subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True,
                            text=True).stdout.split("\n"):
        if p and os.path.isfile(os.path.join(ROOT, p)) and not p.startswith(".claude"):
            os.makedirs(os.path.dirname(os.path.join(wt, p)) or wt, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, p), os.path.join(wt, p))
    subprocess.run(["git", "add", "-A"], cwd=wt, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", "sandbox base"],
                   cwd=wt, capture_output=True)
    home = os.path.join(base, "home")
    os.makedirs(home)
    return base, wt, home


def test_writers_sandbox():
    from engine.generated_files import is_generated
    base, wt, home = _sandbox()
    try:
        nt = os.path.join(home, "NinjaTrader 8")
        os.makedirs(os.path.join(nt, "bin", "Custom", "AddOns"))
        os.makedirs(os.path.join(nt, "le_ticks"))
        with open(os.path.join(nt, "bin", "Custom", "AddOns", "LE_TickRec.cs"), "w") as fh:
            fh.write("// old\n")
        env = {**os.environ, "OLYMPUS_HOME": os.path.join(home, ".olympus"), "USERPROFILE": home, "HOME": home,
               "LE_ALERT_BUS": "0", "LE_NO_PUSH": "1", "PYTHONPATH": wt, "SANDBOX_NT": nt, "LE_SELF_HEAL": "1"}
        runs = [["-m", "engine.ninjatrader", "--selftest", "--quiet"], ["-X", "utf8", "-m", "engine.sizing"],
                ["-X", "utf8", "-m", "tests.test_no_yahoo"],
                ["-X", "utf8", "-m", "engine.pc_selftest", "--mode", "update", "--quiet"],
                ["-X", "utf8", "-m", "engine.self_heal"], ["-X", "utf8", "-m", "engine.ns_sync", "--status"]]
        errs = []
        for a in runs:
            try:
                subprocess.run([sys.executable, *a], cwd=wt, env=env, capture_output=True, timeout=900)
            except subprocess.TimeoutExpired:
                errs.append(" ".join(a) + ": timeout")
        r = subprocess.run([sys.executable, "-c", WRITERS], cwd=wt, env=env, capture_output=True, text=True, timeout=300)
        bad = json.loads((r.stdout.strip().splitlines() or ["[]"])[-1]) if r.returncode == 0 else [r.stderr[-300:]]
        st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=wt, capture_output=True,
                            text=True).stdout.splitlines()
        tracked = [ln[3:] for ln in st if not ln.startswith("??")]
        untracked = [ln[3:] for ln in st if ln.startswith("??")]
        check("b1. the PC's writers ran in a temp worktree (update tests, PC self-test, self-heal, state files)", not errs and not bad,
              errs + bad)
        check("b2. git status after them: every changed tracked file is a generated file (engine/generated_files)",
              all(is_generated(p) for p in tracked), [p for p in tracked if not is_generated(p)])
        check("b3. ... and no new untracked file (all bot output is git-ignored)", not untracked, untracked[:10])
        check("b4. the sandbox really wrote (data/remote_done.json, data/tg_cmd.json exist, git-ignored)",
              os.path.isfile(os.path.join(wt, "data", "remote_done.json")) and os.path.isfile(os.path.join(wt, "data", "tg_cmd.json")))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=ROOT, capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ c. static gate
# Module-level paths in engine/ + server.py that name a TRACKED file: each is READ on the PC; the writer (if any) is a cloud /
# manual build named here. A new path constant to a tracked file fails c1 until it is a generated file or listed with its reason.
READ_ONLY = {
    "research/planner/lit_r_seed.json": "LIT R seed for the buy gate (research/planner, cloud; engine/buy_gate reads it)",
    "research/setupscore/pool.json": "similar-setup pool (big-setupscore build, cloud; engine/setup_score reads it)",
    "research/scalp/na_best_trades.json": "account C scores (cloud research)",
    "research/lit/mffu_rules.json": "MFFU rules (tools/mffu_rules build, cloud)",
    "research/payout/results.json": "12-month payout policy study (tools/money/payout_year.py, cloud)",
    "research/lit/lucid_rules.json": "Lucid rules (cloud)",
    "research/lit/structure_results.json": "advisor research (cloud)",
    "research/lit/advisor_backtest.json": "advisor backtest (cloud)",
    "research/second/atlas_v2_scorecard.json": "ATLAS v2 band (cloud)",
    "tools/web_public/business/accounts.json": "the plan (Claude)",
    "tradingview/blackouts.txt": "engine.calendar_week CLI (cloud)",
    "tradingview/liquidity_engine.pine": "the Pine script (Claude)",
    "research/WEEK_AHEAD.md": "engine.calendar_week CLI (cloud)",
    "research/props/copy_profiles.json": "copy profiles (Claude)",
    "data/draw_learner.json": "tools/train_draw_learner.py (cloud)",
    "data/shadow_ledger_seed.json": "seed (Claude)",
    "research/lab/eval_sample.json": "eval MC sample (cloud)",
    "research/props/firm_rules.json": "firm rules (cloud)",
    "tools/web_public/business/decisions.json": "Decide card (Claude)",
    "scripts/run_bot.ps1": "code", "scripts/stop_bot.ps1": "code", "tools/pc_report.py": "code",
    "scripts/pc_report_task.ps1": "code", "research/kalshi_red_team/verify.py": "code",
    "tools/kalshi_kit/public/kalshi_status_vm.py": "code",
    "research/hq/news_calendar.csv": "news (cloud)",
    "research/lab/health_band.json": "python -m engine.health_band build (cloud)",
    "dashboard_view.json": "hidden bots (Claude)",
    "data/NQ_5m.csv": "TradingView export (cloud); parkable since day-handsfree",
    "data/NQ_1m.csv": "TradingView export (cloud); parkable since day-handsfree",
    "research/lab/kalshi_adapt.json": "Kalshi adapt report (cloud)",
    "research/lab/kalshi_live_plan.json": "Kalshi plan (Claude)",
    "live_model.json": "strategy (Claude, proof rules)", "live_model_engine.json": "strategy (Claude)",
    "research/learn_queue.json": "learn queue (Claude)",
    "research/lab/backtest_live.json": "backtest (cloud)",
    "research/second/money_goal_rates.json": "rates (cloud)",
    "notify_settings.json": "phone settings (Claude)",
    "tools/web_public/push_relay.json": "relay (Claude)",
    "research/lab/rule_log.json": "python -m engine.rulelog build (cloud)",
    "research/second/scale.json": "scale plan (cloud)",
    "second_model.json": "ATLAS strategy (Claude); its account block moved to data/account_b.json",
    "research/second/scorecard.json": "python -m engine.second_scorecard build (cloud)",
    "research/lab/edge_health.json": "tools/edge_health.py (cloud; the PC writes data/edge/)",
}


def path_constants() -> list:
    """[(rel, file:line)] module-level NAME = os.path.join(ROOT, "a", "b") in engine/ + server.py."""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "engine", "**", "*.py"), recursive=True)) + [os.path.join(ROOT, "server.py")]:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = ast.parse(open(f, encoding="utf-8-sig").read())
        except (SyntaxError, OSError):
            continue
        for n in t.body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and getattr(n.value.func, "attr", "") == "join":
                a = n.value.args
                if a and isinstance(a[0], ast.Name) and a[0].id == "ROOT" and len(a) > 1 and \
                        all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in a[1:]):
                    out.append(("/".join(x.value for x in a[1:]), f"{os.path.relpath(f, ROOT)}:{n.lineno}"))
    return out


def test_static():
    from engine.generated_files import is_generated
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n"))
    rows = path_constants()
    new = [(p, w) for p, w in rows if p in tracked and not is_generated(p) and p not in READ_ONLY]
    check("c1. every module path constant to a tracked file is generated or a known read-only input", not new, new[:8])
    check("c2. the scan sees the known ones (it is not empty by mistake)", sum(1 for p, _ in rows if p in READ_ONLY) >= 30)
    ign = subprocess.run(["git", "check-ignore", "--no-index", "data/tg_cmd.json", "data/remote_done.json", "logs/self_heal/ns_sync.json",
                          "data/tickrec_tiny.json"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check("c3. today's new state files are git-ignored (data/tg_cmd.json, logs/self_heal/ns_sync.json)", len(ign) == 4, ign)


# ------------------------------------------------------------------------------------------------ d. park backstop + force
def test_park():
    from engine import self_heal as SH
    ok = all(SH.parkable(p) for p in ("data/NQ_5m.csv", "data/ES_1h.csv", "data/clean/manifest.json", "data/ltf/NQJ_5m.csv",
                                       "data/board/shared.jsonl", "data/NQ_rolls.json", "engine/x.py"))
    check("d1. tracked market data under data/ is parkable now (a bar import can never hold the update back)", ok)
    keep = ("live_model.json", "live_model_lit.json", "second_model.json", "data/accounts.json", "data/lit_journal.jsonl",
            "research/lit/mffu_rules.json", "tools/web_public/business/decisions.json", "update_source.json")
    check("d2. strategy / account / rule files still never parked by themselves", not any(SH.parkable(p) for p in keep),
          [p for p in keep if SH.parkable(p)])
    tmp = tempfile.mkdtemp(prefix="le_park_")
    try:
        def g(*a, timeout=60, env=None):
            r = subprocess.run(["git", *a], cwd=tmp, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout + r.stderr
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        for f in ("live_model.json", "engine.txt"):
            open(os.path.join(tmp, f), "w").write("{}\n")
        g("add", "-A")
        g("commit", "-q", "-m", "a")
        open(os.path.join(tmp, "live_model.json"), "w").write('{"x": 1}\n')
        sat = et(2026, 11, 28, 12)
        a = SH.park_local(tmp, g, ["live_model.json"], now=sat, flat="", push=lambda *a, **k: None, board=lambda *a, **k: None)
        b = SH.park_local(tmp, g, ["live_model.json"], now=sat, flat="", push=lambda *a, **k: None, board=lambda *a, **k: None,
                          force=True)
        clean = g("status", "--porcelain", "--untracked-files=no")[1].strip() == ""
        popped = g("stash", "pop")[0] == 0 and '"x": 1' in open(os.path.join(tmp, "live_model.json")).read()
        c = SH.park_local(tmp, g, ["../evil.txt", ".env.local"], now=sat, flat="", force=True)
        check("d3. live_model.json: kept without force; '/update force' parks it (git stash) and 'git stash pop' brings it back",
              a["parked"] == [] and "live_model.json" in a["kept"] and b["parked"] == ["live_model.json"] and clean and popped, (a, b))
        check("d4. force never parks a path outside the folder or a .env file", c["parked"] == [] and len(c["kept"]) == 2, c)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ e. stuck push
def test_stuck():
    from engine import live_guard as LG
    T = et(2026, 11, 25, 16, 10)
    au = {"last": {"t": T, "status": "skipped", "reason": "local changes in tracked files (not touched): live_model.json"}}
    st, p = LG.update_stuck(None, au, T + 60)
    st, p = LG.update_stuck(st, au, T + 3600 + 60)
    check("e1. a stuck update pushes after 1 h with the phone fix (reply /update, /update force)",
          p and "/update" in p["body"] and "/update force" in p["body"], p)
    au2 = {"last": {"t": T, "status": "skipped", "reason": "git fetch failed: x"}}
    _, p2 = LG.update_stuck(LG.update_stuck(None, au2, T)[0], au2, T + 3700)
    check("e2. a failing fetch: 'reply /update to try again' + the PC-side check", p2 and "/update" in p2["body"], p2)


# ------------------------------------------------------------------------------------------------ f. NinjaScript sync
def test_ns_sync():
    from engine import ns_sync as NS
    src = open(os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs"), encoding="utf-8").read()
    check("f1. LE_TickRec.cs carries its own build id (python -m engine.ns_sync --stamp after an edit)",
          NS.stamped(src) == NS.build_id(src) and len(NS.build_id(src)) == 10 and ',v=" + LE_BUILD' in src,
          (NS.stamped(src), NS.build_id(src)))
    check("f2. the build id ignores CRLF and its own value", NS.build_id(src.replace("\n", "\r\n")) == NS.build_id(src)
          and NS.build_id(NS.stamp_text(src.replace(NS.stamped(src), "0" * 10))) == NS.build_id(src))
    tmp = tempfile.mkdtemp(prefix="le_ns_")
    try:
        root, nt = os.path.join(tmp, "bot"), os.path.join(tmp, "nt")
        os.makedirs(os.path.join(root, "ninjatrader"))
        os.makedirs(os.path.join(nt, "bin", "Custom", "AddOns"))
        os.makedirs(os.path.join(nt, "le_ticks"))
        shutil.copy(os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs"), os.path.join(root, "ninjatrader"))
        dst = os.path.join(nt, "bin", "Custom", "AddOns", "LE_TickRec.cs")
        want = NS.build_id(src)
        wed10, wed17 = et(2026, 11, 25, 10), et(2026, 11, 25, 17)
        check("f3. not installed: nothing copied (optional add-on)", NS.check(root, nt, wed17)[0]["status"] == "skip"
              and not os.path.exists(dst))
        open(dst, "w").write("// old build\n")
        r1 = NS.check(root, nt, wed10, flat=lambda: None)[0]
        r2 = NS.check(root, nt, wed17, flat=lambda: "a trade may be open")[0]
        check("f4. a new build waits in trading hours and while a trade may be open", r1["status"] == "wait" and r2["status"] == "wait"
              and open(dst).read() == "// old build\n", (r1, r2))
        r3 = NS.check(root, nt, wed17, flat=lambda: None)[0]
        check("f5. after 16:00 ET, flat: copied into AddOns", r3["status"] == "copied" and NS.build_id(open(dst).read()) == want, r3)
        sp = os.path.join(nt, "le_ticks", "le_tickrec_status.txt")

        def status(v, t):
            open(sp, "w").write(f"2026-11-25T22:00:00Z,on=1,instruments=NQ,rows=5{',v=' + v if v is not None else ''}\n")
            os.utime(sp, (t, t))
        status(None, wed17 + 600)
        r4 = NS.check(root, nt, wed17 + 600)[0]
        status(None, wed17 + 2400)
        r5 = NS.check(root, nt, wed17 + 2400)[0]
        r6 = NS.check(root, nt, wed17 + 2500)[0]
        check("f6. old compiled code: waits 30 min for NinjaTrader's own compile, then ONE 'F5 once' line per build",
              r4["status"] == "wait" and r5["status"] == "need" and "F5" in r5["text"] and r6["status"] == "info", (r4, r5, r6))
        status(want, wed17 + 2600)
        check("f7. NinjaTrader runs the new build: ok, nothing sent", NS.check(root, nt, wed17 + 2600)[0]["status"] == "ok")
        from engine import self_heal as SH
        ctx = SH.Ctx(root=root, now=wed17 + 2700, apply=True, env={}, nt=nt, flat=lambda: None, git=lambda *a, **k: (0, ""))
        check("f8. self-heal runs it hourly (REMEDIES 'ninjascript'), quiet when in sync", "ninjascript" in dict(SH.REMEDIES)
              and SH.fix_ninjascript(ctx) == [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ g. reboot chain
def test_reboot():
    from engine import autoresume as AR
    tmp = tempfile.mkdtemp(prefix="le_boot_")
    try:
        path = os.path.join(tmp, "auto_resume.json")
        acct = "MFFUEVBLDR12345"
        r = AR.enable(acct, AR._phrase(), cfg={"adapter": "ninjatrader", "nt_account": acct}, path=path)
        check("g0. the owner's opt-in recorded (START + phrase does this)", AR.valid(AR.load(path)), r)
        cfg = {"adapter": "ninjatrader", "nt_account": acct, "sym": "NQ", "tf": "5m"}
        clock = [et(2026, 11, 26, 6, 0)]                  # a Windows Update reboot at 06:00 ET on a weekday
        conn = iter([None, None, False, False, True])      # NinjaTrader starting, logging in, then CONNECTED
        opened, pushes, started = [], [], []

        class Bot:
            running = False
            adapter = None

            def start(self, c):
                started.append(c)
                self.running = True
                return {"ok": True, "restored": "state"}

        res = AR.resume_live(Bot(), cfg, {"why": "reboot"}, notify=lambda t, b, k: pushes.append(t), log=lambda *_: None,
                             sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0], path=path,
                             state_path=os.path.join(tmp, "live_state.json"), connected_fn=lambda _c: next(conn, True),
                             env={"NINJATRADER_LIVE": "1"}, still_on=lambda: True, open_nt=lambda: opened.append(clock[0]))
        check("g1. boot -> server: NinjaTrader opened, the eval resumes ARMED only once NinjaTrader is CONNECTED",
              opened and len(started) == 1 and started[0].get("armed") is True and any("resumed" in p.lower() for p in pushes),
              (opened, started, pushes, res.get("reason")))
        stopped = AR.decide(AR.load(path), None, None, env={"NINJATRADER_LIVE": "1"}, connected=True)
        check("g2. an intentional STOP stays stopped after a reboot (no autostart record)", not stopped["resume"])
        ps = open(os.path.join(ROOT, "scripts", "run_bot.ps1"), encoding="utf-8", errors="replace").read()
        check("g3. the supervisor sets LE_REMOTE=1 and LE_SUPERVISED=1 (phone + Telegram commands, restart comes back)",
              "LE_REMOTE" in ps and "LE_SUPERVISED" in ps)
        srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
        check("g4. server start: crash net first, then auto-resume in its own thread", srv.find("AUTOUPDATE.crash_start()") <
              srv.find('target=_autostart_resume') > 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ h. red team #7 asks
def test_rt7():
    from engine import pending_switch as PS
    from engine import go as G
    from engine.go import LIVE_PHRASE
    tmp = tempfile.mkdtemp(prefix="le_rt7_")
    try:
        ps = os.path.join(tmp, "pending_switches.json")
        quiet = (lambda *_: None)

        def queue(*keys):
            PS._save([], ps)
            for k in keys:
                PS.request(k, path=ps)
        seen, asked = [], []
        queue("blitz_on", "combo_on")
        out = PS.apply_all(LIVE_PHRASE, ps, apply_one=lambda k, p: seen.append(k) or {"ok": True},
                           confirm=lambda q: asked.append(q) or "", say=quiet)
        check("h1. the phrase alone switches NOTHING on: each queued switch asked on its own line, Enter = no (BLITZ stays paper)",
              seen == [] and len(asked) == 2 and "BLITZ" in asked[0] and "Type Y" in asked[0]
              and all("Not switched on" in o for o in out) and PS.load(ps) == [], (out, asked))
        queue("blitz_on", "combo_on")
        out = PS.apply_all(LIVE_PHRASE, ps, apply_one=lambda k, p: seen.append(k) or {"ok": True},
                           confirm=lambda q: "Y" if "combo" in q else "yes please", say=quiet)
        check("h2. only an exact Y / YES switches that one on (combo Y -> on, blitz 'yes please' -> no)",
              seen == ["combo_on"] and out[1].startswith("[OK]") and out[0].startswith("[..] Not switched on"), (seen, out))

        def eof(_q):
            raise EOFError
        queue("blitz_on")
        seen.clear()
        out = PS.apply_all(LIVE_PHRASE, ps, apply_one=lambda k, p: seen.append(k) or {"ok": True}, confirm=eof, say=quiet)
        check("h3. no console (EOF): nothing switched on, the request KEPT for the next START", seen == [] and
              [x["key"] for x in PS.load(ps)] == ["blitz_on"], out)
        keep = G._ps_path
        G._ps_path = lambda: ps
        try:
            out = G.pending_apply(LIVE_PHRASE, None)          # the Start page / a job (no inp): never asks, never applies
        finally:
            G._ps_path = keep
        check("h4. START from the page (no console): no switch applied, the queue stays", [x["key"] for x in PS.load(ps)] == ["blitz_on"]
              and all("Not switched on" in o for o in out), out)
        check("h5. START's first line says it will ask (not 'the phrase turns them on')", "asked about each one" in PS.first_line(ps)
              and "turns them on too" not in PS.first_line(ps))

        # 2. update_source.json never parked, not even by force
        from engine import self_heal as SH
        r = SH.park_local(tmp, lambda *a, **k: (0, ""), ["update_source.json"], now=et(2026, 11, 28, 12), flat="", force=True)
        check("h6. '/update force' never parks update_source.json (where the PC updates from)", r["parked"] == []
              and r["kept"] == ["update_source.json"], r)

        # 3. a crash-loop rollback after a force update pops the force-park back
        from engine import autoupdate as AU
        g = os.path.join(tmp, "repo")
        os.makedirs(g)

        def git(*a):
            return subprocess.run(["git", *a], cwd=g, capture_output=True, text=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        open(os.path.join(g, "live_model.json"), "w").write('{"v": 1}\n')
        open(os.path.join(g, "bot.py"), "w").write("old\n")
        git("add", "-A")
        git("commit", "-q", "-m", "old")
        old = git("rev-parse", "HEAD").stdout.strip()
        open(os.path.join(g, "live_model.json"), "w").write('{"v": 1, "owner": true}\n')   # the owner's hand edit
        sh = AU.Shell(cwd=g)
        pk = SH.park_local(g, lambda *a, timeout=60, env=None: sh.git(*a), ["live_model.json"], now=et(2026, 11, 28, 12), flat="",
                           force=True, push=quiet, board=quiet)
        open(os.path.join(g, "live_model.json"), "w").write('{"v": 2}\n')
        open(os.path.join(g, "bot.py"), "w").write("new crashes\n")
        git("commit", "-q", "-am", "new")
        new = git("rev-parse", "HEAD").stdout.strip()
        stp = os.path.join(tmp, "autoupdate.json")
        AU.record({"t": int(et(2026, 11, 28, 12)), "mode": "manual", "status": "updated", "reason": "x", "old": old, "new": new,
                   "restart": True, "parked": pk["parked"], "stash": pk["stash"], "park_force": True}, state={}, path=stp)
        guard = AU.load_state(stp).get("crash_guard") or {}
        t = et(2026, 11, 28, 12, 5)
        pushes = []
        res = {}
        for i in range(AU.CRASH_RUNS + 1):
            res = AU.crash_check(sh, now=t + 30 * i, path=stp, notify_fn=lambda tt, b, key=None: pushes.append(b))
        txt = open(os.path.join(g, "live_model.json")).read()
        check("h7. the crash guard remembers the force park (files + stash)", guard.get("stash") == pk["stash"]
              and guard.get("parked") == ["live_model.json"] and guard.get("park_force") is True, guard)
        check("h8. crash-loop rollback after a '/update force': back on the old code AND the owner's parked edit is back",
              res.get("status") == "rolled_back" and git("rev-parse", "HEAD").stdout.strip() == old and '"owner": true' in txt
              and git("stash", "list").stdout.strip() == "" and pushes and "parked edit is back" in pushes[-1], (res, txt, pushes))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    test_rt7()
    test_telegram()
    test_static()
    test_park()
    test_stuck()
    test_ns_sync()
    test_reboot()
    if "--fast" not in a:
        test_writers_sandbox()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
