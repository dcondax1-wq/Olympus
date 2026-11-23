"""ZERO-TOUCH (night-zerotouch 2026-11-22): the START phrase = keep-alive consent, MONDAY_SETUP.bat, the recovery matrix and the
NinjaTrader reopen. Temp folders and fakes only: nothing is armed, no order, no phone, no Windows command runs.

    python -X utf8 -m tests.test_zerotouch

 a. keepalive.start_consent: no / wrong phrase = nothing written; the phrase = ON for exactly the armed real accounts (Sim and
    accounts not armed untouched); the phrase is never on disk, only a consent flag; KEEPALIVE_OFF (--off all / --off key)
    sticks against a later START; --on all clears it.
 b. engine/go: step_arm's happy path prints "Keep-alive ON for: ..." and writes next to the (temp) start config; every failed
    START changes nothing; a running bot offers the phrase once for an account still off, Enter = nothing.
 c. engine/monday: update -> clock -> start -> alert test in order, one line each; idempotent (clock skipped once set); UAC
    refused = everything else still runs; an administrator window never runs the update or the start.
 d. engine/recovery: the matrix rows and their one fix.  e. engine/self_heal.fix_nt.  f. Trading Home + the .bat files.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import keepalive as K, go as G, monday as M, recovery as R, self_heal as SH, trade_home as TH  # noqa: E402

RES = []
PH = "I ACCEPT LIVE RISK"
LIT, ATL, SIM = "MFFUEVBLDR000006016", "MFFUEVBLDR000006018", "Sim101"


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


ARMED = [("lit", "Zlarior 50K ..6016", LIT), ("atlas", "ATLAS 25K ..6018", ATL), ("x:simx", "added Sim", SIM)]


def t_consent():
    print("a. the START phrase = keep-alive consent", flush=True)
    old_cp, old_sp = K.CONFIG_PATH, K.state_path_for
    with tempfile.TemporaryDirectory() as tmp:
        try:
            K.CONFIG_PATH = os.path.join(tmp, "keepalive.json")
            K.state_path_for = lambda bot=None: os.path.join(tmp, "keepalive_state.json")
            for ph in (None, "", "i accept", "I ACCEPT LIVE RISK please", "KEEP ALIVE ON"):
                r = K.start_consent(ph, ARMED)
                check(f"a1. phrase {ph!r}: nothing written, nothing ON", not os.path.exists(K.CONFIG_PATH) and not r["on"], r)
            K.save_config({"accounts": {"rapid": False, "x:b25k_2": False}})
            r = K.start_consent(PH, ARMED, now=1795000000)
            C = K.load_config(None)
            txt = open(K.CONFIG_PATH, encoding="utf-8").read()
            check("a2. the phrase: ON for exactly the armed real accounts (lit, atlas); the Sim one and the not-armed rapid / "
                  "x:b25k_2 untouched", C["accounts"] == {"rapid": False, "x:b25k_2": False, "lit": True, "atlas": True}, C["accounts"])
            check("a3. one summary line with the accounts + the plain rule + the opt-out", r["line"].startswith("Keep-alive ON for: Zlarior 50K ..6016, ATLAS 25K ..6018")
                  and "would otherwise hit 7 days without a trade" in r["line"] and "KEEPALIVE_OFF.bat" in r["line"], r["line"])
            check("a4. the phrase is never on disk; only a consent flag (time, day, accounts)", "ACCEPT" not in txt.upper()
                  and C["consent"] == {"t": 1795000000, "day": K._cal(1795000000), "accounts": ["lit", "atlas"], "via": "start_phrase"}, txt)
            r2 = K.start_consent(PH, ARMED)
            check("a5. twice = the same (idempotent)", K.load_config(None)["accounts"] == C["accounts"] and r2["on"] == r["on"], r2)
            rc, out = quiet(K.main, ["--off", "all"])
            C = K.load_config(None)
            check("a6. KEEPALIVE_OFF.bat (--off all) still turns every account OFF and records the opt-out",
                  rc == 0 and not any(C["accounts"].values()) and "*" in C["owner_off"] and "keeps it OFF" in out, (rc, out, C))
            r = K.start_consent(PH, ARMED)
            C = K.load_config(None)
            check("a7. a START with the phrase after OFF: stays OFF, the line says so", not any(C["accounts"].values()) and not r["on"]
                  and r["kept_off"] and "stays OFF" in r["line"], (r, C))
            quiet(K.main, ["--on", "all", "--yes"])
            check("a8. KEEPALIVE_ON.bat (--on all --yes) clears the opt-out", not K.load_config(None)["owner_off"], K.load_config(None))
            quiet(K.main, ["--off", "lit"])
            K.save_config({**K.load_config(None), "accounts": {"lit": False}})
            r = K.start_consent(PH, ARMED)
            C = K.load_config(None)
            check("a9. --off lit sticks for lit only: the next START turns ATLAS on, leaves lit off",
                  C["accounts"].get("lit") is False and C["accounts"].get("atlas") is True and r["kept_off"] == ["Zlarior 50K ..6016"], (r, C))
            check("a10. a Sim-only START turns nothing on", not K.start_consent(PH, [("x:s", "Sim", SIM), ("lit", "z", "Sim102")])["on"])
        finally:
            K.CONFIG_PATH, K.state_path_for = old_cp, old_sp


def t_go():
    print("b. engine/go: step_arm + the running-bot offer", flush=True)
    keep = {k: getattr(G, k) for k in ("CFG", "armed_accounts", "arm_problem", "resolve_atlas", "arm_b", "env_has_live", "server_up",
                                        "server_stale", "env_newer_than_server", "start_server", "stop_server", "bot_running",
                                        "verify_routes", "checklist_lines", "_open", "shortcut", "startup_shortcuts", "mixup",
                                        "keepalive_missing", "keepalive_consent", "names")}
    from engine import ninjatrader as NT, rapid as RP, account_cli as AC, arm_report as AR
    keep_mod = (NT.main, RP.arm, AC.arm, AC.resume_optin, AR.PATH, time.sleep)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            G.CFG = os.path.join(tmp, "start_bot.json")
            AR.PATH = os.path.join(tmp, "arm_status.json")
            kp = os.path.join(tmp, "keepalive.json")
            check("b1. the keep-alive file follows the start config (a test harness never writes the real one)", G._ka_path() == kp, G._ka_path())
            G.armed_accounts = lambda main_on=True: list(ARMED)
            for k, v in dict(arm_problem=lambda cfg: None, resolve_atlas=lambda cfg, inp=None: None, arm_b=lambda a: {"ok": True},
                             env_has_live=lambda: True, server_up=lambda: True, server_stale=lambda: False,
                             env_newer_than_server=lambda: False, start_server=lambda: True, stop_server=lambda: None,
                             bot_running=lambda: False, verify_routes=lambda a, b: [], checklist_lines=lambda: ([], 0),
                             _open=lambda: None, shortcut=lambda: None, startup_shortcuts=lambda: None).items():
                setattr(G, k, v)
            RP.arm = lambda phrase, path=None: {"off": True}
            AC.arm = lambda phrase: []
            AC.resume_optin = lambda phrase: []
            time.sleep = lambda s: None
            cfg = {"lit": LIT, "atlas": ATL}
            for nm, fk in (("no phrase", {}), ("bot did not start", {"nt": 1}),
                           ("route check stopped it", {"routes": ["ATLAS's 25K is not armed"]}),
                           ("arm problem", {"arm": "the 50K is missing"})):
                NT.main = lambda a, rc=fk.get("nt", 0): rc
                G.verify_routes = lambda a, b, p=fk.get("routes", []): p
                G.arm_problem = lambda c, p=fk.get("arm"): p
                rc, out = quiet(G.step_arm, cfg, "" if nm == "no phrase" else PH, open_page=False, inp=lambda p="": "")
                check(f"b2. {nm}: rc 1, the keep-alive file untouched", rc == 1 and not os.path.exists(kp) and "Keep-alive ON" not in out,
                      (rc, out[-300:]))
            NT.main = lambda a: 0
            G.verify_routes = lambda a, b: []
            G.arm_problem = lambda c: None
            rc, out = quiet(G.step_arm, cfg, PH, open_page=False, inp=lambda p="": "")
            C = K.load_config(None, path=kp)
            check("b3. a full START with the phrase: rc 0, 'Keep-alive ON for: ...' before WHAT HAPPENED, lit + atlas ON, Sim not",
                  rc == 0 and "[OK] Keep-alive ON for: Zlarior 50K ..6016, ATLAS 25K ..6018" in out
                  and out.index("Keep-alive ON") < out.index("WHAT HAPPENED")
                  and C["accounts"] == {"lit": True, "atlas": True}, (rc, out[-600:], C))
            src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
            body = src.split("def resume_now", 1)[1].split("\ndef ", 1)[0]
            check("b4. 'Start trading' without the phrase (resume_now) never touches the keep-alive", "keepalive" not in body)
            # the running bot: offered once, only for an account still off
            G._save({"lit": LIT, "atlas": ATL})
            G.bot_running = lambda: True
            G.mixup = lambda a, b, balances=None: None
            calls = []
            G.keepalive_consent = lambda p, main_on=True: calls.append(p) or ""
            G.keepalive_missing = lambda: ["ATLAS 25K ..6018"]
            for ans, want in (("", 0), ("no", 0), (" i accept live risk ", 1)):
                calls.clear()
                rc, out = quiet(G.run, inp=lambda p="", a=ans: a, pull=False)
                check(f"b5. bot running, keep-alive off for ATLAS, answer {ans!r}: {'switched on' if want else 'nothing'}",
                      rc == 0 and len(calls) == want and "not on yet for: ATLAS 25K ..6018" in out, (rc, calls, out[-300:]))
            G.keepalive_missing = lambda: []
            asked = []
            rc, out = quiet(G.run, inp=lambda p="": asked.append(p) or "", pull=False)
            check("b6. bot running, every keep-alive already on: no question", rc == 0 and not any("keep-alive" in str(a) for a in asked)
                  and "not on yet" not in out, (asked, out[-200:]))
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        NT.main, RP.arm, AC.arm, AC.resume_optin, AR.PATH, time.sleep = keep_mod


class FakePC:
    def __init__(self, admin=False, task=False, uac=True, start_rc=0, upd=(("aaa1111", "bbb2222"), 0)):
        self.admin, self.task, self.uac, self.start_rc = admin, task, uac, start_rc
        self.heads, self.upd_rc = list(upd[0]), upd[1]
        self.ran = []

    def is_admin(self):
        return self.admin

    def head(self):
        return self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]

    def update(self):
        self.ran.append("update")
        return self.upd_rc

    def clock_task(self):
        return self.task

    def fix_clock(self, elevated):
        self.ran.append(f"clock:{'admin' if elevated else 'uac'}")
        if elevated or self.uac:
            self.task = True
            return 0
        return 1

    def start(self):
        self.ran.append("start")
        return self.start_rc

    def alert_test(self):
        self.ran.append("alert")
        return 0

    def keepalive(self):
        return {"on": ["Zlarior 50K ..6016", "ATLAS 25K ..6018"], "off": []}

    def recovery(self):
        return ["[OK] PC restart / power cut: ..."]


def t_monday():
    print("c. MONDAY_SETUP", flush=True)
    pc = FakePC()
    out = []
    r = M.run(pc, out=out.append)
    txt = "\n".join(out)
    check("c1. update -> clock -> start -> alert test, in that order, one line each", pc.ran == ["update", "clock:uac", "start", "alert"]
          and [s[0] for s in r["steps"]] == ["1/4 Update", "2/4 Clock", "3/4 Start", "4/4 Alert test"]
          and all(ok for _n, ok, _t in r["steps"]), (pc.ran, r))
    check("c2. the start line names the keep-alive accounts; the recovery list follows", "Keep-alive ON for: Zlarior 50K ..6016, ATLAS 25K ..6018"
          in txt and "What comes back by itself" in txt and "bbb2222"[:7] in txt, txt)
    pc.ran.clear()
    pc.heads = ["bbb2222"]
    r = M.run(pc, out=lambda s: None)
    check("c3. run twice: the clock is skipped (task there), the update says already newest, start + alert run again (safe)",
          pc.ran == ["update", "start", "alert"] and "already" in r["steps"][1][2] and "already" in r["steps"][0][2], (pc.ran, r))
    pc = FakePC(uac=False)
    r = M.run(pc, out=lambda s: None)
    check("c4. 'No' at the administrator question: clock = [FIX] with the right-click step, update / start / alert still run",
          pc.ran == ["update", "clock:uac", "start", "alert"] and r["steps"][1][1] is False and "Run as administrator" in r["steps"][1][2], r)
    pc = FakePC(admin=True)
    r = M.run(pc, out=lambda s: None)
    check("c5. an administrator window: the clock + the alert test only (the bot never starts elevated)",
          pc.ran == ["clock:admin", "alert"] and r["steps"][0][1] is None and r["steps"][2][1] is None, (pc.ran, r))
    pc = FakePC(start_rc=1, upd=(("x",), 1))
    r = M.run(pc, out=lambda s: None)
    check("c6. a failed update / start: [FIX] lines, the next steps still run", r["steps"][0][1] is False and r["steps"][2][1] is False
          and pc.ran[-1] == "alert", r)
    src = open(os.path.join(ROOT, "engine", "monday.py"), encoding="utf-8").read()
    check("c7. monday.py never types / holds the phrase (START BOT's own prompt asks the owner)", "ACCEPT" not in src.split('"""', 2)[2], "")
    raw = open(os.path.join(ROOT, "MONDAY_SETUP.bat"), "rb").read()
    check("c8. MONDAY_SETUP.bat: ASCII, CRLF, runs engine.monday from a %TEMP% copy (the update may rewrite it)",
          all(b < 128 for b in raw) and b"\r\n" in raw and raw.count(b"\n") == raw.count(b"\r\n") and b"-m engine.monday" in raw
          and b"--from-temp" in raw, raw[:200])


def t_recovery():
    print("d. the recovery matrix", flush=True)
    green = [(True, "Never sleeps / hibernates on its own when plugged in", ""), (True, "Task LiquidityEngine starts the bot at logon", ""),
             (True, "NinjaTrader Startup shortcut present", ""), (True, "Windows Update: no forced restart while signed in", ""),
             (True, "Auto-login is on (after a power cut the PC signs itself in)", "")]
    rows = R.matrix(checks=green, resume={"on": True}, ka={"lit": True})
    check("d1. everything set: every row [OK] (kill switch / -$1,000 day stays stopped on purpose)", all(r["ok"] for r in rows)
          and len(rows) == 8 and any("ON PURPOSE" in r["how"] for r in rows), rows)
    rows = R.matrix(checks=green, resume={"on": False}, ka={})
    bad = {r["what"]: r["fix"] for r in rows if not r["ok"]}
    check("d2. auto-resume off: restart / crash / update / NinjaTrader rows say START BOT + the phrase; keep-alive row too",
          set(bad) == {"PC restart / power cut", "Windows Update restart", "Bot server crash / crash loop", "Update / rollback restart",
                       "NinjaTrader closed / disconnected", "MFFU 7 days without a trade"}
          and all("I ACCEPT LIVE RISK" in f for f in bad.values()), bad)
    al_off = [x if "Auto-login" not in x[1] else (False, "Auto-login is off: ...", "Guidance only: docs/PC_ALWAYS_ON.md step 2 (netplwiz).")
              for x in green]
    sl_off = [x if "sleeps" not in x[1] else (False, "Sleep/hibernate timers on AC: sleep=900s hibernate=0s (0 = never)", "powercfg ...")
              for x in green]
    r1 = {r["what"]: r for r in R.matrix(checks=al_off, resume={"on": True}, ka={"lit": True})}
    r2 = {r["what"]: r for r in R.matrix(checks=sl_off, resume={"on": True}, ka={"lit": True})}
    check("d3. auto-login off: the PC restart row is [FIX] with the netplwiz step; sleep timers: the sleep row [FIX] with powercfg",
          not r1["PC restart / power cut"]["ok"] and "netplwiz" in r1["PC restart / power cut"]["fix"]
          and not r2["Sleep / power save"]["ok"] and "powercfg" in r2["Sleep / power save"]["fix"], (r1, r2))
    check("d4. not checked (not Windows): never a guessed [FIX] for the PC rows", R.matrix(checks=[], resume={"on": True}, ka={"a": True})[0]["ok"])
    ln = R.lines(R.matrix(checks=green, resume={"on": False}, ka={}))
    check("d5. lines: [OK] / [FIX] + the one fix", ln[0].startswith("[FIX] PC restart") and ln[-1].startswith("[OK] Kill switch"), ln)


def t_nt():
    print("e. self-heal: NinjaTrader closed while the bot should run", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "data"))
        opened = []

        def ctx(apply=True, procs=((1, "python.exe"),), win=True, ok=True):
            return SH.Ctx(root=tmp, now=1795000000, apply=apply, procs=list(procs), is_windows=win, git=lambda *a, **k: (0, ""),
                          ping=lambda: True, nt=None, open_nt=lambda: opened.append(1) or ok)
        check("e1. no autostart record (stopped on purpose): nothing", SH.fix_nt(ctx()) == [] and not opened)
        with open(os.path.join(tmp, "data", "autostart.json"), "w") as fh:
            json.dump({"cfg": {}}, fh)
        check("e2. NinjaTrader running: nothing", SH.fix_nt(ctx(procs=((1, "python.exe"), (2, "ninjatrader.exe")))) == [] and not opened)
        check("e3. process list unreadable / not Windows: never guessed", SH.fix_nt(ctx(procs=())) == [] and SH.fix_nt(ctx(win=False)) == []
              and not opened)
        it = SH.fix_nt(ctx(apply=False))
        check("e4. dry run: 'would open', nothing opened", it and it[0]["status"] == "would" and not opened, it)
        it = SH.fix_nt(ctx())
        check("e5. closed: opened once, status fixed", it and it[0]["status"] == "fixed" and opened == [1], it)
        it = SH.fix_nt(ctx(ok=False))
        check("e6. NinjaTrader.exe not found: 'need' with the one step (alerts)", it and it[0]["status"] == "need" and "log in" in it[0]["step"], it)
        check("e7. it is in the hourly remedies", "nt" in [n for n, _f in SH.REMEDIES])


def t_home():
    print("f. Trading Home + readiness + the .bat files", flush=True)
    L, P = TH.status_screen(now=1, bot={"running": True, "last_poll": 1}, accounts=[], keepalive={"lit": True, "atlas": True},
                            alerts=(True, False, True), clock=None)
    check("f1. status: 'Keep-alive: ON for Zlarior 50K, ATLAS 25K' + the opt-out", any("ON for Zlarior 50K, ATLAS 25K" in x and "KEEPALIVE_OFF" in x for x in L), L)
    L, P = TH.status_screen(now=1, bot={"running": True, "last_poll": 1}, accounts=[], keepalive={}, alerts=(True, False, True), clock=None)
    check("f2. keep-alive off: the fix is START with the phrase (menu 2)", any(m == "2" and "turns the keep-alive on too" in t for m, t in P), P)
    check("f3. menu k = KEEPALIVE_OFF.bat (the opt-out in TRADE_HOME)", TH.ACTIONS["k"][1] == "KEEPALIVE_OFF.bat"
          and any("Keep-alive OFF" in m for m in TH.MENU))
    off = open(os.path.join(ROOT, "KEEPALIVE_OFF.bat"), "rb").read()
    check("f4. KEEPALIVE_OFF.bat still runs --off all, ASCII CRLF", b"--off all" in off and all(b < 128 for b in off)
          and off.count(b"\n") == off.count(b"\r\n"))
    src = open(os.path.join(ROOT, "engine", "readiness.py"), encoding="utf-8").read()
    check("f5. readiness's 7-day fix says START / MONDAY_SETUP with the phrase", "MONDAY_SETUP.bat (or START BOT) and type I ACCEPT LIVE RISK" in src)


def main():
    t_consent()
    t_go()
    t_monday()
    t_recovery()
    t_nt()
    t_home()
    bad = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(bad)}/{len(RES)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
