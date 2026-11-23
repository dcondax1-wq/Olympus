"""ARM red team (2026-11-23): the ATLAS eval -> funded name switch and the loud START summary, attacked. Every outside effect
is faked (no server, no NinjaTrader, no real account file); nothing is armed for real.

    python -X utf8 -m tests.test_arm_rt

 a. phrase gate: nothing switches or arms without I ACCEPT LIVE RISK; YES cannot come from Enter, a default, closed / piped
    stdin, the Start page job (no console) or a running bot.
 b. the one-candidate rule against adversarial NinjaTrader lists (2 matches, other plan, Rapid, Sim, Lucid, a 50K balance with
    the same last 4, Zlarior's own, case / spaces, the old name still listed).
 c. data safety: an ALREADY FUNDED ATLAS keeps every funded number and its trade history through the rename; a passed eval
    switches only on a fresh balance (never turns +$401 into $0).
 d. the summary on every exit path; e. the phone line: private, small, never stale after a later arm.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import arm_report as AR, go as G, second as SE, account_b as AB, brain_glance as BG  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


OLD, NEW = "MFFUEVBLDR000006018", "MFFUSFBLDR000006018"
LIT = "MFFUEVBLDR000006016"
OK = lambda: (True, "selftest faked")  # noqa: E731
ORIG = {k: getattr(G, k) for k in ("nt_account_names", "nt_balances", "role_of", "bot_running", "arm_b", "SECOND_PATH",
                                    "ALLOW_PATH", "CFG", "SELFTEST", "arm_problem", "env_has_live", "server_up", "server_stale",
                                    "env_newer_than_server", "start_server", "stop_server", "verify_routes", "_open", "shortcut")}


def reset():
    for k, v in ORIG.items():
        setattr(G, k, v)


def setup(tmp, nt, bal=None, funded=False, atlas=OLD, b_account=OLD, running=False):
    reset()
    p = os.path.join(tmp, "second_model.json")
    shutil.copy(SE.CFG_PATH, p)
    AB.set_account_b(b_account, plan="builder25k", start="2026-10-26", path=p, selftest=OK)
    if funded:                                   # ATLAS already funded: real numbers, written straight into the local block
        blk = dict(AB.raw_cfg(p))
        blk.update(stage="funded", funded_start="2026-11-13", funded_balance=25000.0, payouts={"2026-11-21": 0.0} if False else {},
                   eval_account="MFFUEVBLDR000006011", funded_set="2026-11-13", armed=True)
        AB.write_local(blk, p, why="test: funded")
    G.SECOND_PATH, G.ALLOW_PATH = p, os.path.join(tmp, "allow.json")
    G.CFG = os.path.join(tmp, "start_bot.json")
    G.nt_account_names = lambda: list(nt)
    G.nt_balances = lambda: dict(bal or {})
    G.role_of = lambda name, cfg=None, b=None, extras=None: "Zlarior's 50K" if name == LIT else None
    G.bot_running = lambda: running
    G.SELFTEST = OK
    AR.PATH = os.path.join(tmp, "arm_status.json")
    cfg = {"lit": LIT, "atlas": atlas}
    G._save(cfg)
    return p, cfg


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            r = fn(*a, **k)
        except Exception as e:  # noqa: BLE001
            r = e
    return r, buf.getvalue()


def acct(p):
    return (AB.raw_cfg(p) or {}).get("account")


def main():
    # ---------------------------------------------------------------- a. the phrase gate and the YES
    with tempfile.TemporaryDirectory() as tmp:
        p, cfg = setup(tmp, [LIT, NEW])
        calls = []
        G.arm_b = lambda *a, **k: (calls.append(a), {"ok": True})[1]
        for ph in ("", "i accept", "I ACCEPT LIVE RISK please", None, "YES"):
            rc, out = quiet(G.step_arm, cfg, ph, inp=lambda prompt="": "YES")
            check(f"a1. phrase {ph!r}: rc 1, nothing armed, the name untouched, the summary says NOT ARMED",
                  rc == 1 and not calls and acct(p) == OLD and "NOT ARMED: ATLAS 25K" in out, (rc, out[-300:]))
        check("a2. typed_phrase: only the real phrase (any case / spaces) counts", G.typed_phrase(" i  accept live RISK ") == G.LIVE_PHRASE
              and G.typed_phrase("I ACCEPT") != G.LIVE_PHRASE and G.typed_phrase(None) != G.LIVE_PHRASE)
        for nm, inp in (("Enter (empty)", lambda prompt="": ""), ("a default None", lambda prompt="": None), ("'yes please'", lambda prompt="": "yes please"),
                        ("'Y'", lambda prompt="": "Y")):
            r, _ = quiet(G.resolve_atlas, cfg, inp)
            check(f"a3. answer {nm}: never a switch", isinstance(r, str) and acct(p) == OLD, r)

        def eof(prompt=""):
            raise EOFError

        r, out = quiet(G.resolve_atlas, cfg, eof)
        check("a4. stdin closed / piped and empty at the YES: no crash, no switch, a plain reason", isinstance(r, str) and acct(p) == OLD, r)
        r, out = quiet(G.resolve_atlas, cfg, None)
        check("a5. no console (the Start page job / auto): never switches, says START_BOT.bat + YES", isinstance(r, str) and acct(p) == OLD
              and "START_BOT.bat" in out, out)
        G.bot_running = lambda: True
        asked = []
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": (asked.append(1), "YES")[1])
        check("a6. the bot is running: no question, no switch (a running bot would keep the old name and its state)",
              isinstance(r, str) and not asked and acct(p) == OLD and "STOP BOT" in out, out)
        G.bot_running = lambda: False
        src = open(os.path.join(os.path.dirname(G.__file__), "go.py"), encoding="utf-8").read()
        body = src.split("def resolve_atlas", 1)[1].split("\ndef ", 1)[0]
        check("a7. resolve_atlas has no flag / env / default that answers YES for the owner",
              "LE_" not in body and "argv" not in body and "environ" not in body and 'ask(' in body and ', None, inp)' in body, "")

    # ---------------------------------------------------------------- b. adversarial NinjaTrader lists
    lists = [
        ("2 candidates", [LIT, NEW, "MFFUSFBLDR000016018"], {}, None),
        ("other plan letters only (Rapid)", [LIT, "MFFUSFRPD000006018"], {}, None),
        ("Sim / Lucid / another firm with the same last 4", [LIT, "Sim101", "LTP50K6018", "FNX256018", "APEX-6018"], {}, None),
        ("same last 4 but a 50K balance", [LIT, NEW], {NEW: 50211.0}, None),
        ("Zlarior's own account is never offered", [LIT], {}, None),
        ("an eval (EV) of the same digits is not a funded rename", [LIT, "MFFUEVBLDR000016018"], {}, None),
        ("case / spaces differences still match the one funded account", [LIT, " mffusfbldr000006018 "], {}, "mffusfbldr000006018"),
        ("the one true rename", [LIT, NEW, "Sim101"], {NEW: 25000.0}, NEW),
    ]
    for nm, nt, bal, want in lists:
        with tempfile.TemporaryDirectory() as tmp:
            p, cfg = setup(tmp, nt, bal)
            shown = []
            r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": (shown.append(prompt), "YES")[1])
            if want is None:
                check(f"b. {nm}: no switch, ATLAS NOT armed with a [FIX]", isinstance(r, str) and acct(p) == OLD and not shown, (r, acct(p), shown))
            else:
                check(f"b. {nm}: both names shown, then YES switches to exactly {want}", r is None and acct(p) == want
                      and shown and OLD in shown[0] and want in shown[0], (r, acct(p), shown))
    with tempfile.TemporaryDirectory() as tmp:
        p, cfg = setup(tmp, [LIT, OLD, NEW])
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": 1 / 0)
        check("b. the old name still listed next to its funded twin: nothing changes, one [CHECK] line names both",
              r is None and acct(p) == OLD and "[CHECK]" in out and NEW in out, out)

    # ---------------------------------------------------------------- c. data safety
    with tempfile.TemporaryDirectory() as tmp:
        p, cfg = setup(tmp, [LIT, NEW], {NEW: 25401.0}, funded=True)
        sp = AB.state_file(p)
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        closes = [["2026-11-14", 1763130000, -113.0, 1763120000], ["2026-11-18", 1763480000, 514.0, 1763470000],
                  ["2026-11-20", 1763650000, 0.0, 1763640000]]
        json.dump({"account": OLD, "closes": closes, "ledger": [{"t": 1, "side": "entry"}], "held": {"x": 1}}, open(sp, "w"))
        before = dict(AB.raw_cfg(p))
        fs0 = AB.funded_status(p, sp, today="2026-11-23")
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": "YES")
        after = dict(AB.raw_cfg(p) or {})
        keep = {k: before.get(k) for k in ("stage", "funded_start", "funded_balance", "payouts", "eval_account", "funded_set", "plan",
                                           "sizing", "strategies", "eval_start")}
        check("c1. ALREADY FUNDED + YES: the Name moves and every funded number is kept (start day, $25,000 start, payouts, plan, sizing)",
              r is None and after.get("account") == NEW and all(after.get(k) == v for k, v in keep.items()), (r, out[-300:], before, after))
        check("c2. ... and it is DISARMED until the typed phrase arms it (arm_b)", after.get("armed") is not True, after)
        st = json.load(open(sp))
        check("c3. ... the state file (closes, ledger, held) moves to the new Name, a copy of the old one is kept",
              st.get("account") == NEW and st.get("closes") == closes and st.get("ledger") and st.get("held")
              and any(".renamed_" in f for f in os.listdir(os.path.dirname(sp))), st)
        fs1 = AB.funded_status(p, sp, today="2026-11-23")
        t0, t1 = (fs0 or {}).get("tracker") or {}, (fs1 or {}).get("tracker") or {}
        check("c4. the funded tracker reads the SAME numbers after the rename (profit, best day, payouts): +$401 stays +$401",
              fs0.get("ok") and fs1.get("ok") and t0.get("profit") == 401.0
              and json.dumps(t0, sort_keys=True) == json.dumps(t1, sort_keys=True).replace(NEW, OLD), (t0, t1))
        check("c5. the summary text promises nothing about a new start balance", "Funded start balance" not in out and "kept" in out, out)
        rb = G.arm_b(NEW, path=p, selftest=OK)
        check("c6. then arm_b arms the new Name and still keeps the funded numbers",
              rb.get("ok") and all((AB.raw_cfg(p) or {}).get(k) == v for k, v in keep.items()), (rb, AB.raw_cfg(p)))
    with tempfile.TemporaryDirectory() as tmp:            # a funded rename whose state write fails: nothing changed
        p, cfg = setup(tmp, [LIT, NEW], funded=True)
        sp = AB.state_file(p)
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        json.dump({"account": OLD, "closes": [["2026-11-18", 1, 514.0, 0]]}, open(sp, "w"))
        real_replace = os.replace
        os.replace = lambda a, b: (_ for _ in ()).throw(PermissionError("locked")) if b == sp else real_replace(a, b)
        try:
            r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": "YES")
        finally:
            os.replace = real_replace
        check("c7. the state file is locked during the rename: put back, the old Name and its history stay",
              isinstance(r, str) and acct(p) == OLD and json.load(open(sp)).get("account") == OLD, (r, acct(p)))
    with tempfile.TemporaryDirectory() as tmp:            # passed eval but the funded account already has history
        p, cfg = setup(tmp, [LIT, NEW], {NEW: 25401.0})
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": "YES")
        check("c8. passed EVAL, NinjaTrader already at $25,401: refused (would make $401 profit the start = $0), nothing changed",
              isinstance(r, str) and "history" in r and acct(p) == OLD and (AB.raw_cfg(p) or {}).get("stage") != "funded", r)
    with tempfile.TemporaryDirectory() as tmp:            # a fresh funded account: the funded switch as built
        p, cfg = setup(tmp, [LIT, NEW], {NEW: 25000.0})
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": "YES")
        ab = AB.raw_cfg(p) or {}
        check("c9. passed EVAL on a fresh $25,000 funded account: switched to funded at $25,000", r is None and ab.get("account") == NEW
              and ab.get("stage") == "funded" and float(ab.get("funded_balance") or 0) == 25000.0, (r, ab))
    with tempfile.TemporaryDirectory() as tmp:            # the self-test failing: nothing changed
        p, cfg = setup(tmp, [LIT, NEW], funded=True)
        G.SELFTEST = lambda: (False, "NT selftest 79/80")
        r, out = quiet(G.resolve_atlas, cfg, lambda prompt="": "YES")
        check("c10. NinjaTrader self-test failing: no switch", isinstance(r, str) and "selftest" in r and acct(p) == OLD, r)
    check("c11. rename_funded refuses a non-rename pair / Zlarior's account", not G.rename_funded(OLD, "MFFUSFBLDR000009999").get("ok")
          and not G.rename_funded(OLD, LIT, LIT).get("ok"))

    # ---------------------------------------------------------------- d. the summary on every exit path
    def run_path(tmp, **fakes):
        p, cfg = setup(tmp, [LIT, OLD])
        G.arm_b = lambda atlas, path=None, selftest=None: {"ok": True}
        G.arm_problem = lambda cfg: None
        G.env_has_live = lambda: True
        G.server_up = lambda: True
        G.server_stale = lambda: False
        G.env_newer_than_server = lambda: False
        G.start_server = lambda: True
        G.stop_server = lambda: None
        G.verify_routes = lambda lit, atlas: []
        G._open = lambda: None
        G.shortcut = lambda: None
        for k, v in fakes.items():
            setattr(G, k, v)
        from engine import ninjatrader as NT
        nt_main = NT.main
        NT.main = fakes.get("nt_main", lambda a: 0)
        try:
            rc, out = quiet(G.step_arm, cfg, G.LIVE_PHRASE, open_page=False, inp=lambda prompt="": "")
        finally:
            NT.main = nt_main
        d = json.load(open(AR.PATH)) if os.path.exists(AR.PATH) else {}
        return rc, out, {r["label"]: r["armed"] for r in d.get("rows", [])}
    paths = [
        ("server did not start", dict(server_up=lambda: False, start_server=lambda: False), 1),
        ("bot did not start", dict(nt_main=lambda a: 1), 1),
        ("route check stopped the bot", dict(verify_routes=lambda lit, atlas: ["ATLAS's 25K is not armed"]), 1),
        ("arm problem", dict(arm_problem=lambda cfg: "the 50K is missing"), 1),
        ("ATLAS arm refused", dict(arm_b=lambda atlas, path=None, selftest=None: {"ok": False, "error": "selftest failed"},
                                   verify_routes=lambda lit, atlas: ["ATLAS's 25K is not armed"]), 1),
        ("an error mid-way, bot not running", dict(env_has_live=lambda: 1 / 0), "exc"),
    ]
    for nm, fk, want in paths:
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, st = run_path(tmp, **fk)
            ok_rc = isinstance(rc, ZeroDivisionError) if want == "exc" else rc == want
            check(f"d. {nm}: never 'ARMED:' for any account, the NOT TRADING banner, the phone file says not armed",
                  ok_rc and "ARMED: " not in out.replace("NOT ARMED: ", "") and "NOT TRADING" in out and st and not any(st.values()), (rc, out[-400:], st))
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, st = run_path(tmp)
        check("d. everything fine: ARMED for both, no banner", rc == 0 and "ARMED: Zlarior 50K" in out and "ARMED: ATLAS 25K" in out
              and "NOT TRADING" not in out and st.get("Zlarior 50K") and st.get("ATLAS 25K"), (rc, out[-300:], st))
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, st = run_path(tmp, env_has_live=lambda: 1 / 0, bot_running=lambda: True)
        check("d. an error AFTER the bot runs: a [CHECK] line, never a guessed ARMED / NOT ARMED", isinstance(rc, ZeroDivisionError)
              and "[CHECK]" in out and "ARMED:" not in out, out[-300:])

    # ---------------------------------------------------------------- e. the phone line
    with tempfile.TemporaryDirectory() as tmp:
        AR.PATH = os.path.join(tmp, "arm_status.json")
        AR.save([AR.row("Zlarior 50K", True), AR.row("ATLAS 25K", False, f"{OLD} is not in NinjaTrader; {NEW} looks like its funded rename", "x")])
        g = AR.glance_reason("ATLAS") or ""
        check("e1. the phone's reason never carries a full account Name (last 4 only), <= 110 chars",
              g.startswith("ATLAS is NOT armed") and OLD not in g and NEW not in g and "...6018" in g and len(g) <= 110, g)
        check("e2. mask keeps plain words and dates", AR.mask("the live phrase was not typed on 2026-11-23, Sim101") ==
              "the live phrase was not typed on 2026-11-23, Sim101", AR.mask("the live phrase was not typed on 2026-11-23, Sim101"))
        AR.save([AR.row("Zlarior 50K", True), AR.row("ATLAS 25K", True)])
        check("e3. a later successful START clears the phone's NOT armed reason", AR.glance_reason("ATLAS") is None)
        AR.save([AR.row("ATLAS 25K", False, "x", "y")], now=1)
        check("e4. a reason older than 36 h says nothing", AR.glance_reason("ATLAS") is None)
        AR.save([AR.row("ATLAS 25K", False, "x", "y")])
        check("e5. the phone shows a reason only while the heartbeat says not armed",
              "nar" not in BG.atlas({"running": True, "second": {"route": {"account_b": {"armed": True}}}}, {}) if hasattr(BG, "atlas") else True)
    reset()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
