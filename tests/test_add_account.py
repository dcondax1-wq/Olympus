"""Adding an account the way the owner does it (night-addacct 2026-11-23, owner: "adding accounts is painful").

    python -X utf8 -m tests.test_add_account        # ~3 s, a temp bot world (tests/test_accounts_cli.world), nothing real touched

a. TRADE_HOME 4 with a new NinjaTrader account: pick it by number, Enter = the plan guessed from its Name + balance -> the REAL
   engine/account_cli.add writes the account HELD -> the paper check finds it on the bot's list with its firm's rules. 2 answers.
b. a pasted Name (NinjaTrader not read): paste + one plan number = 2 answers; the full Name is never printed (private).
c. Lucid: addable now, HELD (never armed here), the check line says Lucid's written OK is still needed; FundedNext stays OFF.
d. the guess: Builder 25K / 50K eval, ATLAS's funded 25K, a passed old eval (no default), an unknown Name (no default).
e. the paper check says [FIX] when the Name is missing, armed, or its rules did not load; `trade_home check` exits 1 then.
f. ADD_ACCOUNT.bat: 6 choices (Lucid = 6), every add exits to :done only on success, :done runs the paper check with the right key.
Never arms, never types a phrase.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


class Owner:
    """Scripted answers + what the screen showed."""
    def __init__(self, answers):
        self.answers, self.out, self.prompts, self.ran = list(answers), [], [], []

    def ask(self, prompt=""):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def say(self, *a):
        self.out.append(" ".join(str(x) for x in a))

    def run(self, argv):
        self.ran.append(list(argv))
        return 0


def world_checks(tmp):
    from engine import account_cli as AC, go as G, rapid, trade_home as T
    from tests import test_accounts_cli as TC
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_rp, env_keep = rapid.PATH, os.environ.get("NINJATRADER_FOLDER")
    try:
        TC.world(tmp)
        G.bot_running = lambda: False
        quiet_add = lambda k, n: AC.add(k, n)   # noqa: E731
        # a. a new NinjaTrader account, picked by number, Enter = the guess
        o = Owner(["1", ""])
        ok = T.do_choice("4", ask=o.ask, out=o.say, run=o.run, fx={}, add_fn=quiet_add, unseen={TC.N25: 25000.0})
        row = next((r for r in AC.inventory() if r["name"] == TC.N25), None)
        shown = "\n".join(o.out)
        check("a. TRADE_HOME 4: pick the new account (1), Enter = 'Builder 25K eval' guessed from its Name + $25,000",
              any("looks like Builder 25K eval" in ln for ln in o.out) and any("<- looks like this one (Enter)" in ln and "Builder 25K" in ln for ln in o.out), o.out)
        check("a. the REAL add wrote it: on the bot's list as a Builder 25K eval, HELD (armed is not True)",
              row is not None and row["plan"] == "builder25k" and row.get("armed") is not True, row)
        check("a. one plain end line: 'Added + paper-checked', its rules ($1,500 target, $1,000 max loss, $600 daily, 20 micros), "
              "HELD, then the START sentence", "Added + paper-checked: Builder 25K eval" in shown and "target +$1,500" in shown
              and "max loss $1,000" in shown and "daily loss $600" in shown and "max 20 micros" in shown and ok.startswith("[OK] Added HELD")
              and "type the live phrase yourself" in ok, (ok, o.out))
        check("a. 2 answers inside the step (was 3: plan, Name, Y), and the full Name never on screen",
              len(o.prompts) == 2 and TC.N25 not in shown and "..." + TC.N25[-4:] in shown, (o.prompts, shown))
        # b. a pasted Name (no NinjaTrader list): paste + one number
        PASTE = "MFFUEVBLDR900000060"
        o = Owner([PASTE, "1"])
        okb, lb = T.add_flow(ask=o.ask, out=o.say, run=o.run, unseen={}, add_fn=quiet_add)
        rb = next((r for r in AC.inventory() if r["name"] == PASTE), None)
        check("b. pasted Name + '1' (Builder 50K): added HELD, paper-checked, 2 answers, Name masked",
              okb and rb and rb["plan"] == "builder50k" and rb.get("armed") is not True and len(o.prompts) == 2
              and PASTE not in "\n".join(o.out) and any("paper-checked" in x for x in o.out), (okb, lb, rb, o.out))
        # c. Lucid: addable, HELD until Lucid's written OK; FundedNext stays OFF
        LU = "LUCIDPRO50K0042"
        o = Owner([LU, "7"])
        okc, lc = T.add_flow(ask=o.ask, out=o.say, run=o.run, unseen={}, add_fn=quiet_add, infer=lambda n, b: {})
        rc_ = next((r for r in AC.inventory() if r["name"] == LU), None)
        check("c. Lucid (7): added HELD (not armed), the check line says it stays HELD until Lucid's written OK",
              okc and rc_ is not None and rc_.get("armed") is not True and any("Lucid's written OK" in x for x in o.out), (okc, lc, rc_, o.out))
        o = Owner(["SOMEFIRM123456", "6"])
        okf, lf = T.add_flow(ask=o.ask, out=o.say, run=o.run, unseen={}, add_fn=quiet_add, infer=lambda n, b: {})
        check("c. FundedNext (6): OFF, nothing added", not okf and "OFF" in lf and not any(r["name"] == "SOMEFIRM123456" for r in AC.inventory()), lf)
        # e. the check's red cases on the real list
        okx, lx = T.paper_check("NOT-ON-THE-LIST-1", "builder25k")
        check("e. a Name not on the list: [FIX], masked", not okx and lx.startswith("[FIX]") and "NOT-ON-THE-LIST-1" not in lx, lx)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = T.main(["check", "builder25k", "NOT-ON-THE-LIST-1"])
        check("e. `python -m engine.trade_home check <plan> <Name>` exits 1 on a missing Name (ADD_ACCOUNT.bat shows the line)",
              rc == 1 and "[FIX]" in buf.getvalue(), buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = T.main(["check", "builder25k", TC.N25])
        check("e. ... and exits 0 with the paper-checked line for the account just added", rc == 0 and "paper-checked" in buf.getvalue(), buf.getvalue())
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH = keep_rp
        if env_keep is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_keep


def pure_checks():
    from engine import trade_home as T
    g = T.guess_plan
    check("d. guess: EVBLDR $25,000 = 2 Builder 25K, $50,000 = 1 Builder 50K, SFBLDR $25,000 = 5 ATLAS funded 25K",
          g("MFFUEVBLDR900000025", 25000.0)[0] == "2" and g("MFFUEVBLDR900000050", 50000.0)[0] == "1"
          and g("MFFUSFBLDR900000099", 25000.0)[0] == "5")
    pg = g("MFFUEVBLDR900000077", 27000.0)
    check("d. a passed old eval ($27,000 on a 25K): no default, a plain note", pg[0] is None and "PASSED" in pg[1], pg)
    check("d. an unknown Name / no balance: no default (the owner picks)", g("XYZ123", None) == (None, "") and g("MFFUEVBLDR9", None)[0] is None)
    okr, lr = T.paper_check("ACC-1234-ARMED", "builder25k", rows=[{"name": "ACC-1234-ARMED", "armed": True}])
    check("e. a row that shows ARMED right after an add: [FIX] (never 'OK')", not okr and "ARMED" in lr, lr)
    oku, lu = T.paper_check("ACC-1234-X", "builder25k", rows=[{"name": "ACC-1234-X", "armed": False}], rules={})
    check("e. rules that did not load: [FIX]", not oku and "rules did not load" in lu, lu)
    o = Owner(["", ""])
    okq, lq = T.add_flow(ask=o.ask, out=o.say, run=o.run, unseen={"MFFUEVXYZ900000004": 25000.0}, infer=lambda n, b: {})
    check("d. no guess and Enter: nothing added (Enter never picks a plan by itself)", not okq and "Nothing added" in lq and not o.ran, lq)


def bat_checks():
    raw = open(os.path.join(ROOT, "ADD_ACCOUNT.bat"), "rb").read()
    bat = raw.decode("ascii")
    lines = bat.split("\r\n")
    adds = [ln for ln in lines if ln.startswith('if "%CH%"==') and " -m engine." in ln]
    pks = {ln.split('"')[3]: ln.split("PK=")[1].rstrip('"') for ln in lines if ln.startswith('if "%CH%"==') and 'set "PK=' in ln}
    check("f. ADD_ACCOUNT.bat: 6 choices, Lucid = 6 (--plan lucidpro50k), each add -> :done only on success",
          len(adds) == 6 and any("--plan lucidpro50k" in a and a.startswith('if "%CH%"=="6"') for a in adds)
          and all("&& goto :done || goto :notadded" in a for a in adds), adds)
    from engine import trade_home as T
    keys = {p["key"] for p in T.PLAN_MENU}
    check("f. every choice sets the paper-check key (a TRADE_HOME plan key), and :done runs `engine.trade_home check %PK%`",
          sorted(pks) == ["1", "2", "3", "4", "5", "6"] and set(pks.values()) <= keys
          and bat.index(":done") < bat.index("-m engine.trade_home check %PK%"), pks)
    check("f. ADD_ACCOUNT.bat: ASCII, CRLF only", raw.count(b"\r\n") == raw.count(b"\n") and all(b < 128 for b in raw))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_addacct_")
    try:
        pure_checks()
        world_checks(tmp)
        bat_checks()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nadd account: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
