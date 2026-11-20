"""One line per new MFFU account (engine/account_cli.py, `python -X utf8 -m engine.accounts ...`, docs/NEW_ACCOUNT.md).

    python -X utf8 -m tests.test_accounts_cli        (temp files only, made-up / Sim names; nothing armed for real, ~5 s)

  a. add builder25k / builder50k / rapideod: the research defaults (25K = LIT, ATLAS only once funded and OFF; 50K = LIT;
     Rapid = LIT + ATLAS via engine/rapid.py), DISARMED, allowlisted (real names only), the phrase never in a file
  b. refused: unknown plan, bots not offered, a Name already used, a 25K Name on a 50K plan, a 2nd Rapid
  c. MFFU limits at add: 10 evals; funded Builder 50K 1, Builder 25K 2, Rapid 3, 5 in all; Sim never counts
  d. arming: only arm(<the typed phrase>) (START BOT) arms the added accounts; --start then hands them the phrase in memory
  e. no hedging across accounts: the router refuses an order opposite to an added account's open position
  f. remove / list / status, and the `python -m engine.accounts` entry point
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import account_cli as AC  # noqa: E402
from engine import go as G  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import rapid  # noqa: E402
from engine import second as SE  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

RES = []
L50, L25 = "MFFUEVBLDR500000001", "MFFUEVBLDR500000002"        # Zlarior's 50K, ATLAS's 25K (made up)
N25, N50, NR = "MFFUEVBLDR500000025", "MFFUEVBLDR500000050", "MFFUEVRPD500000003"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def world(tmp):
    G.CFG = os.path.join(tmp, "start_bot.json")
    G.SECOND_PATH = os.path.join(tmp, "second_model.json")
    shutil.copy(SE.CFG_PATH, G.SECOND_PATH)
    AB.set_account_b(None, path=G.SECOND_PATH)
    AB.set_account_b(L25, plan="builder25k", start="2026-10-27", path=G.SECOND_PATH)
    G.ALLOW_PATH = os.path.join(tmp, "allow.json")
    G.ACCOUNTS_PATH = os.path.join(tmp, "accounts.json")
    G.ANCHOR_PATH = os.path.join(tmp, "eval_anchor.json")
    G._save({"lit": L50, "atlas": L25})
    rapid.PATH = os.path.join(tmp, "rapid.json")
    nt = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(os.path.join(nt, "le_feed"), exist_ok=True)
    now = int(time.time())
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "w") as fh:
        fh.write("name,time,cash,realized,unrealized,netliq\n"
                 f"{L50},{now},49192.78,0,0,49192.78\n{L25},{now},26946.10,0,0,26946.10\n{N25},{now},25000,0,0,25000\n")
    os.environ["NINJATRADER_FOLDER"] = nt


def file_rows():
    return MA.load_file(G.ACCOUNTS_PATH)


def allowed():
    try:
        return set(json.load(open(G.ALLOW_PATH)).get("accounts") or [])
    except Exception:
        return set()


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


def main():
    tmp = tempfile.mkdtemp(prefix="le_acctcli_")
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_rp, env_keep = rapid.PATH, os.environ.get("NINJATRADER_FOLDER")
    try:
        world(tmp)
        G.bot_running = lambda: False
        L = AC.limits()
        check("MFFU limits from research/lit/mffu_rules.json: 10 evals, 5 funded (Builder 50K 1, 25K 2, Rapid EOD 3)",
              (L["evals"], L["funded"], L["builder50k"], L["builder25k"], L["rapideod"]) == (10, 5, 1, 2, 3), L)
        inv = AC.inventory()
        check("inventory: Zlarior's 50K (LIT) and ATLAS's 25K (ATLAS), both evals",
              [(r["name"], r["bots"], r["stage"]) for r in inv] == [(L50, "lit", "eval"), (L25, "atlas", "eval")], inv)

        # a. the three plans
        r = AC.add("builder25k", N25)
        row = next((x for x in file_rows() if x.get("nt_account") == N25), {})
        n = MA.normalize(row)
        check("builder25k: LIT on the eval (preset mffu_builder_25k, two_week), DISARMED, allowlisted, ATLAS not on",
              r["ok"] and n["problem"] is None and n["preset"] == "mffu_builder_25k" and n["mode"] == "two_week"
              and row.get("armed") is False and row["cli"]["bots"] == "lit" and row["cli"]["atlas_when_funded"] is False
              and N25 in allowed(), (r, row))
        check("builder25k: the ATLAS-once-funded note is shown", any("ATLAS $250" in x for x in r.get("notes") or []), r)
        check("the added account's display name is the plan, not the MFFU account id", N25 not in row.get("name", ""), row)
        r = AC.add("builder50k", N50, start="2026-11-18")
        row = next((x for x in file_rows() if x.get("nt_account") == N50), {})
        check("builder50k: LIT (preset mffu_builder_50k, two_week from the given day), DISARMED, allowlisted",
              r["ok"] and row.get("preset") == "mffu_builder_50k" and row.get("eval_start") == "2026-11-18"
              and row.get("armed") is False and N50 in allowed(), (r, row))
        r = AC.add("rapideod", NR)
        blk = rapid.read()
        check("rapideod: engine/rapid.py's block (LIT + ATLAS on one account), DISARMED, allowlisted",
              r["ok"] and blk and blk["account"] == NR and blk.get("armed") is False and NR in allowed(), (r, blk))
        r = AC.add("builder25k", "Sim102", bots="lit+atlas")
        row = next((x for x in file_rows() if x.get("nt_account") == "Sim102"), {})
        check("a Sim account: added (owner's test), never allowlisted, ATLAS-once-funded yes saved",
              r["ok"] and "Sim102" not in allowed() and row.get("cli", {}).get("atlas_when_funded") is True, (r, row))

        # b. refusals
        bad = [("unknown plan", AC.add("lucid50k", "X1")),
               ("--bots atlas on a 50K", AC.add("builder50k", "MFFUEVBLDR500000051", bots="atlas")),
               ("--bots lit on the Rapid", AC.add("rapideod", "MFFUEVRPD500000004", bots="lit")),
               ("ATLAS already has its 25K", AC.add("builder25k", "MFFUEVBLDR500000026", bots="atlas")),
               ("a Name used twice", AC.add("builder25k", N25)),
               ("Zlarior's own Name", AC.add("builder50k", L50)),
               ("a Name that says 25K on a 50K plan", AC.add("builder50k", "MFFU25K-EVAL-9")),
               ("an empty Name", AC.add("builder25k", "  "))]
        r2 = AC.add("rapideod", "MFFUEVRPD500000005")          # day-multirapid: a 2nd Rapid = slot 2, a 3rd is refused
        bad.append(("a 3rd Rapid (both slots taken)", AC.add("rapideod", "MFFUEVRPD500000007")))
        for what, rr in bad:
            check(f"refused: {what}", rr.get("ok") is False and rr.get("error"), rr)
        check("a 2nd Rapid is added as Rapid #2, disarmed", r2.get("ok") is True and r2.get("slot") == "rapid2", r2)
        AC.remove("MFFUEVRPD500000005")

        # c. MFFU limits
        s = AC.slots()
        check("slots: Sim never counts (5 real evals: 50K, 25K, new 25K, new 50K, Rapid)", s["evals"] == 5 and s["funded"] == 0, s)
        names = [f"MFFUEVBLDR5000001{i:02d}" for i in range(6)]
        rs = [AC.add("builder50k", nm) for nm in names]
        check("10 evals: the 6th extra (11th eval) is refused with MFFU's limit",
              all(x["ok"] for x in rs[:5]) and rs[5]["ok"] is False and "10 evals" in rs[5]["error"], [x.get("error") for x in rs])
        check("eval add while the Builder 50K funded slot is free: no warning", not any("cannot be activated" in x for x in rs[0]["notes"]), rs[0])
        rows = AC.inventory()
        f1 = AC.add("builder50k", "MFFUFDBLDR600000001", start="2026-11-20", funded=True)
        f2 = AC.add("builder50k", "MFFUFDBLDR600000002", start="2026-11-20", funded=True)
        check("funded Builder 50K: 1 allowed (mode funded, funded.start), the 2nd refused",
              f1["ok"] and f2["ok"] is False and "1 funded Builder 50K" in f2["error"]
              and next(x for x in file_rows() if x.get("nt_account") == "MFFUFDBLDR600000001")["mode"] == "funded", (f1, f2))
        g = [AC.add("builder25k", f"MFFUFDBLDR6000000{i}", start="2026-11-20", funded=True) for i in (11, 12, 13)]
        check("funded Builder 25K: 2 allowed, the 3rd refused", g[0]["ok"] and g[1]["ok"] and g[2]["ok"] is False, [x.get("error") for x in g])
        fake = rows + [{"name": f"F{i}", "plan": p, "stage": "funded", "sim": False, "role": "extra", "id": f"f{i}"}
                       for i, p in enumerate(["builder50k", "builder25k", "builder25k", "rapideod", "rapideod"])]
        check("5 funded in all: a 3rd Rapid funded is refused by the total cap",
              "5 funded accounts" in (AC.limit_problem("rapideod", "funded", "MFFUFD9", fake) or ""), AC.limit_problem("rapideod", "funded", "MFFUFD9", fake))
        check("Sim accounts are never refused by a limit", AC.limit_problem("builder50k", "funded", "Sim101", fake) is None)

        # d. arming
        before = [x.get("armed") for x in file_rows()]
        check("arm(): a wrong phrase arms nothing", AC.arm("i accept") == [] and [x.get("armed") for x in file_rows()] == before)
        lines = AC.arm(LIVE_PHRASE)
        rows_f = file_rows()
        check("arm(<the typed phrase>) = START BOT: every added account armed", lines and all(x.get("armed") is True for x in rows_f), (lines, rows_f))
        raw = open(G.ACCOUNTS_PATH, encoding="utf-8").read()
        check("the phrase never lands in data/accounts.json", LIVE_PHRASE not in raw)
        body = MA.merge_into_start({"adapter": "ninjatrader", "nt_account": L50}, LIVE_PHRASE, path=G.ACCOUNTS_PATH)
        specs = MA.specs_from_cfg(body)
        n25 = next(x for x in specs if x["nt_account"] == N25)
        check("--start hands the phrase to each armed added account in memory; they route with no problem",
              n25["armed"] and n25["confirm"] == LIVE_PHRASE and n25["problem"] is None, n25)
        check("the Rapid stays disarmed until START BOT's own rapid.arm", rapid.read().get("armed") is False)
        src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
        i_arm, i_start = src.find("account_cli.arm(phrase)"), src.find('ninjatrader.main(["--start", "--account", cfg["lit"], "--confirm", phrase')
        check("START BOT (engine/go.step_arm) arms them after the typed phrase, before the bot starts", 0 < i_arm < i_start)

        # e. no hedging across accounts
        class Bot:
            cfg, state, ledger, state_path, _open_routed = {"adapter": "paper"}, {}, [], os.path.join(tmp, "live_state.json"), None
            clock = staticmethod(time.time)

            def _log(self, k, t):
                pass
        paper = [{**x, "adapter": "paper", "confirm": ""} for x in file_rows() if x.get("cli")]
        router = MA.AccountRouter(Bot(), MA.specs_from_cfg({"adapter": "paper", "accounts": paper}), state_path=os.path.join(tmp, "acc_state.json"))
        a0 = router.accounts[0]
        a0.open_t = 1_000
        a0.ledger.append({"side": "buy", "entry_t": 1_000, "qty": 2})
        check("hedging guard: a SHORT anywhere is refused while an added account holds a LONG",
              "hedging guard" in (router.opposite_open(-1) or "") and router.opposite_open(1) is None, router.opposite_open(-1))
        check("hedging guard: another added account cannot go SHORT either",
              "hedging guard" in (router.opposite_open(-1, exclude=router.accounts[1]) or ""))

        # f. remove / list / status / entry point
        rc, out = quiet(AC.main, ["list"])
        check("list: one row per account + the slots line", rc == 0 and N25 in out and "MFFU slots: evals" in out, out)
        rc, out = quiet(AC.main, ["status"])
        check("status: balances, slots and the no-hedge / LIT-first / arming rules", rc == 0 and "No hedging" in out
              and "LIT first" in out and "$25,000.00" in out, out)
        r = AC.remove(N25)
        check("remove an added account: off the file and the allowlist", r["ok"] and not any(x.get("nt_account") == N25 for x in file_rows())
              and N25 not in allowed(), r)
        r = AC.remove(NR)
        check("remove the Rapid: engine/rapid.py OFF, off the allowlist", r["ok"] and rapid.read() is None and NR not in allowed(), r)
        check("remove an unknown Name: refused", AC.remove("nope")["ok"] is False)
        rc, out = quiet(AC.main, ["add", "--plan", "builder25k", "--name", N25, "--funded"])
        check("CLI: --funded without --start is refused", rc == 1 and "--start" in out, out)
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.accounts", "add", "--help"], cwd=ROOT, capture_output=True,
                           text=True, timeout=60)
        check("`python -X utf8 -m engine.accounts add --help` works (--plan --name --bots)",
              p.returncode == 0 and "--plan" in p.stdout and "--bots" in p.stdout, p.stdout + p.stderr)
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH = keep_rp
        if env_keep is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_keep
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
