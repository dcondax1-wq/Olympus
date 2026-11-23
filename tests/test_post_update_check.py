"""Post-update check (night-verify 2026-11-23, engine/post_update_check.py): fakes only, nothing sent, nothing changed.

    python -X utf8 -m tests.test_post_update_check

 a. all green -> "Update verified: N/N OK" (+ "k not installed yet"), one red -> "Update: <piece> needs you -> <fix>"
 b. a piece missing on this checkout = "not installed", never a failure; a broken one = FIX
 c. Windows: OlympusClock missing -> FIX with the exact one click; 2 PC report tasks -> FIX; Task Scheduler silent -> FIX
 d. bounded: a hung check is skipped at its time box, the whole run stays within the budget, a raising check = one FIX row
 e. read-only: the bot folder's files are unchanged after a run (only logs/post_update.json when saved); the send is ONE
    message keyed by the update's sha; after_restart never raises and waits before it checks
 g. day-notify: ONE 'Update installed, alerts OK' push a day (fake alert bus), its receipt, FIX always, ALERTS_OFF = old path
 f. the hooks: server.py starts it in a thread only after an update restart; UPDATE.bat's after_update prints it; Trading Home
"""
import hashlib
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import post_update_check as P, trade_home as TH  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def ok_check(c):
    return [P.row("A", P.OK, "fine")]


def bad_check(c):
    return [P.row("Clock task", P.FIX, "missing", P.CLOCK_FIX)]


def t_summary():
    r = P.run(P.Ctx(windows=False), checks=(ok_check, ok_check, lambda c: [P.row("X", P.NOT_INSTALLED, "not on this version yet")]))
    check("a1. all green: 'Update verified: 2/2 OK (1 not installed yet)'", r["ok"] and r["message"] == "Update verified: 2/2 OK (1 not installed yet)", r["message"])
    r = P.run(P.Ctx(windows=False), checks=(ok_check, bad_check, bad_check))
    check("a2. red: 'Update: Clock task needs you -> right-click FIX_CLOCK.bat ...' (+1 more)", not r["ok"]
          and r["message"].startswith("Update: Clock task needs you -> right-click FIX_CLOCK.bat") and "(+1 more)" in r["message"], r["message"])


def t_optional():
    def imp(m):
        if m == "engine.win_guard":
            raise ModuleNotFoundError(f"No module named '{m}'", name=m)
        if m == "tools.rules_watch":
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")
        if m == "engine.state_pulse":
            raise SyntaxError("bad")
        return object()
    rows = {r["name"]: r for r in P.c_optional(P.Ctx(windows=False, imp=imp))}
    check("b1. not on this checkout -> 'not installed' (never a failure)", rows["Win guard"]["status"] == P.NOT_INSTALLED, rows["Win guard"])
    check("b2. installed but a package missing -> FIX (UPDATE.bat installs it)", rows["Rules watch"]["status"] == P.FIX
          and "UPDATE.bat" in rows["Rules watch"]["fix"], rows["Rules watch"])
    check("b3. installed but broken -> FIX", rows["State pulse"]["status"] == P.FIX and rows["Payout autopilot"]["status"] == P.OK, rows)


def t_windows():
    def run_no_clock(cmd, timeout=6):
        return (1, "") if "OlympusClock" in cmd else (0, "")
    r = P.c_clock(P.Ctx(windows=True, run=run_no_clock))[0]
    check("c1. OlympusClock missing -> FIX with the exact one click", r["status"] == P.FIX and r["fix"] == P.CLOCK_FIX, r)
    r = P.c_clock(P.Ctx(windows=True, run=lambda cmd, timeout=6: (0, "")))[0]
    check("c2. OlympusClock there -> OK", r["status"] == P.OK, r)
    two = '"PC","\\OlympusPCReport","x","python tools\\pc_report.py"\n"PC","\\OlympusPCReport2","x","python tools\\pc_report.py"\n"PC","\\Other","x","y"\n'
    r = P.c_tasks(P.Ctx(windows=True, run=lambda cmd, timeout=6: (0, two)))[0]
    check("c3. two PC report tasks -> FIX (double posts), names shown", r["status"] == P.FIX and "2 copies" in r["text"], r)
    one = '"PC","\\OlympusPCReport","x","python tools\\pc_report.py"\n'
    check("c4. one task -> OK", P.c_tasks(P.Ctx(windows=True, run=lambda cmd, timeout=6: (0, one)))[0]["status"] == P.OK)
    check("c5. Task Scheduler silent -> FIX", P.c_tasks(P.Ctx(windows=True, run=lambda cmd, timeout=6: (1, "")))[0]["status"] == P.FIX)
    check("c6. not Windows -> info, not counted", P.c_clock(P.Ctx(windows=False))[0]["status"] == P.INFO)


def t_bounded():
    def hang(c):
        time.sleep(5)
        return [P.row("late", P.OK, "x")]

    def boom(c):
        raise RuntimeError("exploded")
    t0 = time.monotonic()
    r = P.run(P.Ctx(windows=False), checks=(hang, boom, ok_check), budget_s=3.0, check_s=1.0)
    dt_ = time.monotonic() - t0
    names = [x["name"] for x in r["rows"]]
    check("d1. a hung check is skipped at its time box; the run stays inside the budget", dt_ < 2.5 and r["rows"][0]["status"] == P.INFO
          and "did not answer" in r["rows"][0]["text"], (dt_, r["rows"]))
    check("d2. a raising check = one FIX row, the others still run", r["rows"][1]["status"] == P.FIX and "exploded" in r["rows"][1]["text"]
          and "A" in names, r["rows"])
    r = P.run(P.Ctx(windows=False), checks=(hang, ok_check, ok_check), budget_s=0.5, check_s=5.0)
    check("d3. the budget runs out: the rest is 'skipped (time box)'", any("time box" in x["text"] for x in r["rows"]), r["rows"])


def _snap(root):
    out = {}
    for d in ("data", "live_model.json", "second_model.json", "live_model_lit.json"):
        p = os.path.join(root, d)
        files = [p] if os.path.isfile(p) else [os.path.join(a, f) for a, _, fs in os.walk(p) for f in fs] if os.path.isdir(p) else []
        for f in files:
            try:
                out[f] = hashlib.sha1(open(f, "rb").read()).hexdigest()
            except OSError:
                pass
    return out


def t_readonly():
    before = _snap(ROOT)
    r = P.run(P.Ctx(windows=False, connect=lambda h, port=443, timeout=3.0: True))
    after = _snap(ROOT)
    check("e1. a real run (this checkout): data/ and the model files unchanged; < 30 s", before == after and r["secs"] < 30,
          (set(before.items()) ^ set(after.items()), r["secs"]))
    check("e2. the real run lists every check, none raised out", len(r["rows"]) >= 10 and r["message"], r["message"])
    sent = []
    tmp = tempfile.mkdtemp()
    old, old_sp = P.OUT, P.SENT_PATH
    P.SENT_PATH = os.path.join(tmp, "post_update_sent.json")
    s = P.send(r, sha="abc1234", poster=lambda p: sent.append(p) or "sent")
    check("e3. ONE message keyed by the update's sha, title = the phone line (summary, or 'Update installed, alerts OK')",
          s == "sent" and len(sent) == 1 and sent[0]["key"] == "post_update:abc1234"
          and sent[0]["title"] == P.phone_text(r, "abc1234")[0], sent)
    os.path.exists(P.SENT_PATH) and os.remove(P.SENT_PATH)
    slept = []
    P.OUT = os.path.join(tmp, "post_update.json")
    try:
        res = P.after_restart("abc1234", delay_s=90, sleep=slept.append, ctx=P.Ctx(windows=False, connect=lambda *a, **k: True),
                              poster=lambda p: "sent")
        check("e4. after_restart waits first (the bot resumes), checks, saves, sends; never raises", slept == [90] and res
              and res["sent"] == "sent" and P.last(P.OUT)["sha"] == "abc1234", (slept, res and res.get("sent")))
        check("e5. after_restart with a broken check list still returns (never raises)",
              P.after_restart("x", delay_s=0, sleep=lambda s: (_ for _ in ()).throw(RuntimeError("x"))) is None)
    finally:
        P.OUT, P.SENT_PATH = old, old_sp


class FakeBus:
    """engine/alert_bus stand-in: records send_critical, answers with the given receipts (no network)."""

    def __init__(self, receipts=("ntfy", "webpush"), r="sent"):
        self.calls, self.digest, self.receipts, self.r = [], [], receipts, r

    def send_critical(self, ev, on_done=None, wait=False, **k):
        self.calls.append((ev, wait))
        if on_done and self.r in ("sent", "failed"):
            on_done({"ok": self.r == "sent", "receipts": {c: "id" for c in self.receipts} if self.r == "sent" else {}})
        return self.r

    def digest_add(self, title, body="", key=""):
        self.digest.append((title, body, key))
        return True


def t_daynotify():
    """day-notify 2026-11-23: ONE 'Update installed, alerts OK' push after the landing, with its delivery receipt."""
    tmp = tempfile.mkdtemp()
    sp = os.path.join(tmp, "sent.json")
    green = P.summarize([P.row("A", P.OK, "fine"), P.row("Phone alerts", P.OK, "ntfy reachable")])
    t16 = 1795467900                                   # Mon 2026-11-23 16:05 ET
    b = FakeBus()
    s = P.send(green, sha="abc1234def", bus=b, now=t16, sent_path=sp)
    ev, wait = b.calls[0]
    check("g1. all green: title 'Update installed, alerts OK', body names the version + checks", ev["title"] == "Update installed, alerts OK"
          and "abc1234" in ev["body"] and "2/2 checks OK" in ev["body"] and "alerts work" in ev["body"], ev)
    check("g2. through alert_bus.send_critical (both no-secret channels), WAITS for the receipts, key = the sha", wait is True
          and ev["key"] == "post_update:abc1234def" and ev["kind"] == "problem", ev)
    check("g3. the receipt: 'sent via ntfy + the Olympus app', res['receipts'] = the channels", s == "sent via ntfy + the Olympus app"
          and green.get("receipts") == ["ntfy", "webpush"], (s, green.get("receipts")))
    b2 = FakeBus()
    s2 = P.send(P.summarize([P.row("A", P.OK, "fine")]), sha="fff9999", bus=b2, now=t16 + 3600, sent_path=sp)
    check("g4. a 2nd green update the same ET day: no 2nd buzz, one digest line", not b2.calls and s2.startswith("digest") and len(b2.digest) == 1,
          (s2, b2.calls))
    b3 = FakeBus()
    s3 = P.send(P.summarize([P.row("A", P.OK, "fine")]), sha="eee1111", bus=b3, now=t16 + 86400, sent_path=sp)
    check("g5. the next day: the OK push goes again", len(b3.calls) == 1 and s3.startswith("sent"), s3)
    b4 = FakeBus()
    red = P.summarize([P.row("Phone alerts", P.FIX, "cannot reach ntfy", "check the PC's internet")])
    P.send(red, sha="ddd2222", bus=b4, now=t16 + 86400 + 60, sent_path=sp)
    check("g6. a FIX always goes (never the digest), title = the 'needs you' line, never 'alerts OK'", len(b4.calls) == 1
          and b4.calls[0][0]["title"].startswith("Update: Phone alerts needs you") and "alerts OK" not in b4.calls[0][0]["title"], b4.calls)
    b5 = FakeBus(r="failed")
    sp5 = os.path.join(tmp, "sent5.json")
    s5 = P.send(P.summarize([P.row("A", P.OK, "fine")]), sha="ccc3333", bus=b5, now=t16, sent_path=sp5)
    check("g7. no channel answered: 'not delivered', the day is NOT used up (the next update tries again)",
          s5.startswith("not delivered") and not os.path.exists(sp5), s5)
    calls = []
    import engine.notify as N
    old = N.instant_problem
    N.instant_problem = lambda p: calls.append(p) or "sent"
    try:
        s6 = P.send(P.summarize([P.row("A", P.OK, "fine")]), sha="bbb4444", bus=FakeBus(r="off"), now=t16, sent_path=os.path.join(tmp, "s6.json"))
    finally:
        N.instant_problem = old
    check("g8. ALERTS_OFF ('off'): the old notify.instant_problem path, same key + title", s6 == "sent" and calls
          and calls[0]["key"] == "post_update:bbb4444" and calls[0]["title"] == "Update installed, alerts OK", (s6, calls))


def t_hooks():
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    i = src.index("marker = _au.take_restart_marker()")
    blk = src[i:i + 500]
    check("f1. server.py: started in a background thread only when the restart follows an update (the marker)",
          "if marker:" in blk and "_puc.start_bg(" in blk and "except Exception" in blk)
    ops = open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read().split("def after_update", 1)[1].split("\ndef ", 1)[0]
    check("f2. UPDATE.bat (ops_checks --after-update) prints the same lines", "post_update_check" in ops and "_puc.lines(res)" in ops)
    L, _p = TH.status_screen(now=1000, bot={"running": True, "last_poll": 1000}, accounts=[], keepalive={"lit": True}, alerts=(True, False, True),
                             clock=None, upd={"t": 940, "message": "Update verified: 9/9 OK"})
    check("f3. Trading Home status shows the last check's one line", any("Update   : Update verified: 9/9 OK (60 s ago)" in x for x in L), L)
    L, _p = TH.status_screen(now=1000, bot={"running": True, "last_poll": 1000}, accounts=[], keepalive={"lit": True}, alerts=(True, False, True),
                             clock=None, upd=None)
    check("f4. no check yet: no line", not any(x.startswith("  Update") for x in L), L)
    src = open(os.path.join(ROOT, "engine", "post_update_check.py"), encoding="utf-8").read()
    check("f5. never arms / starts / sends a test: no arm, start, --confirm or alert test in the module",
          not any(w in src for w in ("--confirm", ".arm(", "bot.start", "send_test", "alerts.send(")))


def t_rt2():
    """red team 2: every OPTIONAL path is a real module of tonight's branches (a wrong path reads 'not installed' for ever)."""
    known = {"engine/fleet_mgr.py", "tools/rules_watch.py", "tools/task_audit.py", "engine/payout_autopilot.py", "engine/state_pulse.py",
             "engine/win_guard.py", "engine/monday.py", "engine/recovery.py", "engine/fault_note.py"}     # on origin night-* 2026-11-23
    paths = {m.replace(".", "/") + ".py" for _l, m in P.OPTIONAL}
    check("rt2. OPTIONAL names the real module paths (engine.fleet_mgr, tools.rules_watch, tools.task_audit)", paths <= known,
          sorted(paths - known))


def main():
    t_summary()
    t_optional()
    t_windows()
    t_bounded()
    t_readonly()
    t_daynotify()
    t_hooks()
    t_rt2()
    bad = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(bad)}/{len(RES)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
