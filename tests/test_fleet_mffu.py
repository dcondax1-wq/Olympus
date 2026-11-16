"""A second MFFU Builder 50K that copies Zlarior (team E, 2026-11-16): the one-command path, end to end, Sim / paper only.

    python -X utf8 -m tests.test_fleet_mffu        (~10 s; temp files only: never data/fleet.json, live_model*.json, NinjaTrader)

The owner's one line (docs/MORE_ACCOUNTS.md, "A second MFFU 50K"):
    python -X utf8 -m engine.fleet --add --id mffu50b --lead zlarior --plan mffu_builder_50k --account "<Name>" --start today

Covers: the add on a Sim Name (no arming, the MFFU rules re-read 2026-11-16: copying your own accounts allowed, 1 funded
Builder 50K a person, 5 sim-funded in all); the copy sized by Zlarior's two_week eval sizing on the Builder 50K (<= 40 micros,
a full stop fits the $1,000 soft daily loss and the room); never opposite Zlarior; no entry 5 min before MFFU's 16:10 flat;
the eval lifecycle (passed at +$3,000 -> no new entry + the --to-funded push); --to-funded refused while Zlarior holds the
funded Builder 50K (from live_model.json / the running bot), allowed once the owner says it ended (--held); the funded rules
(buffer $2,100, $500 more, 2 traded days, best day <= 50%, 80%, <= $2,000); the running bot blocks a funded copy over the
slot and MFFU's 5-account total; a real Name is never armed by --add.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import copy_accounts as CA  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import fleet as FL  # noqa: E402
from tests.test_fleet import Bot, Rec, ents, fol, make, ts  # noqa: E402

RES = []
DAY = "2026-11-17"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)
    return bool(ok)


def held_root(tmp, lit_mode="two_week", atlas_stage=None):
    """A folder that looks like the PC for the command line: live_model.json lit_sizing mode, data/account_b.json stage."""
    r = os.path.join(tmp, f"pc_{lit_mode}_{atlas_stage}")
    os.makedirs(os.path.join(r, "data"), exist_ok=True)
    json.dump({"lit_sizing": {"mode": lit_mode}}, open(os.path.join(r, "live_model.json"), "w"))
    if atlas_stage:
        json.dump({"account": "Sim199", "plan": "builder25k", "stage": atlas_stage}, open(os.path.join(r, "data", "account_b.json"), "w"))
    return r


def cli(tmp):
    p = os.path.join(tmp, "cli", "fleet.json")
    out = []

    def run(*a, root=None):
        FL.HELD_ROOT = root or held_root(tmp)
        rc, lines = FL.run(list(a) + ["--file", p, "--now", str(ts(DAY, 9, 0))])
        out.append(lines)
        return rc, lines
    rc, lines = run("--add", "--id", "mffu50b", "--lead", "zlarior", "--plan", "mffu_builder_50k", "--account", "Sim102", "--start", "today")
    d = FL.load_file(p)
    r = d["accounts"][0]
    check("one command adds the copy: Sim Name, Zlarior's lead, MFFU Builder 50K eval, start today = the session's day, not armed",
          rc == 0 and r["plan"] == "mffu_builder_50k" and r["stage"] == "eval" and r["nt_account"] == "Sim102" and r["start"] == DAY
          and r["armed"] is False and r["lead"] == "zlarior", (rc, lines, r))
    txt = "\n".join(lines)
    check("... it says SIM, no arming needed, and no 'ask MFFU about copying' warning (allowed per MFFU's help center 2026-11-16)",
          "SIM follows Zlarior on MyFundedFutures (MFFU) Builder 50K (eval)" in txt and "no arming needed" in txt
          and "copying between your own accounts" not in txt, lines)
    check("... and no funded-slot warning while Zlarior is still in its eval", "funded later" not in txt, lines)
    rc2, lines2 = run("--add", "--id", "mffu50c", "--lead", "zlarior", "--plan", "mffu_builder_50k", "--account", "Sim103", "--start", "today",
                      root=held_root(tmp, "funded"))
    check("Zlarior FUNDED (live_model.json lit_sizing mode funded): the add still saves the eval copy but says MFFU will not fund "
          "it while Zlarior's funded Builder 50K is active", rc2 == 0 and any("funded later" in x and "allows 1 funded Builder 50K" in x for x in lines2), lines2)
    run("--remove", "mffu50c")
    rc3, lines3 = run("--add", "--id", "real", "--lead", "zlarior", "--plan", "mffu_builder_50k", "--account", "MFFUEVBLDR999", "--start", "today")
    check("a real MFFU Name is saved NOT armed (only --arm + the typed phrase arms it)", rc3 == 0 and "NOT armed" in "\n".join(lines3)
          and FL.load_file(p)["accounts"][-1]["armed"] is False, lines3)
    run("--remove", "real")
    rc4, lines4 = run("--to-funded", "mffu50b", "--account", "Sim104", "--start", "2026-12-01", root=held_root(tmp, "funded"))
    check("--to-funded refused while Zlarior holds MFFU's one funded Builder 50K (plain words + the --held line)",
          rc4 == 1 and "NOT switched" in lines4[0] and "--held mffu_builder_50k=0" in lines4[0]
          and FL.load_file(p)["accounts"][0]["stage"] == "eval", lines4)
    rc5, _ = run("--held", "mffu_builder_50k=0", root=held_root(tmp, "funded"))
    rc6, lines6 = run("--to-funded", "mffu50b", "--account", "Sim104", "--start", "2026-12-01", root=held_root(tmp, "funded"))
    a = FL.load_file(p)["accounts"][0]
    check("--held mffu_builder_50k=0 (the owner: Zlarior's funded account ended) -> --to-funded works: funded, new Name, disarmed",
          rc5 == 0 and rc6 == 0 and a["stage"] == "funded" and a["nt_account"] == "Sim104" and a["funded_start"] == "2026-12-01"
          and a["armed"] is False and FL.load_file(p)["held_funded"] == {"mffu_builder_50k": 0}, (lines6, a))
    rc7, _ = run("--held", "no_such_plan=1")
    check("--held refuses an unknown plan", rc7 == 1)
    rc8, lines8 = run("--payout", "mffu50b", "2026-12-08=1000")
    check("--payout records the request on the copy", rc8 == 0 and FL.load_file(p)["accounts"][0]["payouts"] == {"2026-12-08": 1000.0}, lines8)
    FL.HELD_ROOT = None


def rules():
    E, F = FM.profile("mffu_builder_50k", "eval"), FM.profile("mffu_builder_50k", "funded")
    check("MFFU Builder 50K eval (re-read 2026-11-16): $3,000 target, $2,000 EOD trailing locking at +$100, $1,000 soft daily, 40 micros, "
          "no best-day rule, news unrestricted, flat by 16:10, no hedge across accounts",
          (E["target"], E["dd_amount"], E["dd_type"], E["lock"], E["dll"], E["dll_type"], FM.max_micros(E), E["consistency"], E["news"],
           E["flat_by"], E["hedging"]) == (3000.0, 2000.0, "eod", 100.0, 1000.0, "soft", 40, "none", "none", "16:10", "banned_all_accounts"), E)
    po = F["payout"]
    check("MFFU Builder 50K funded: buffer $2,100, $500-$2,000 a request, 80%, best day <= 50% of the cycle, 2 traded days, 5 payouts, "
          "1 funded per person",
          (po["buffer"], po["min"], po["max"], po["split"], po["consistency"], po["min_days"], po["max_payouts"], F["max_active"])
          == (2100.0, 500.0, 2000.0, 0.8, 0.5, 2, 5, 1), (po, F.get("max_active")))
    check("MFFU firm: bots allowed, copying your own accounts allowed (both verified 2026-11-16), 5 sim-funded in all",
          F["bots"] == "allowed" and F["copy_trading"] == "allowed" and F["verified"]["copy_trading"] is True
          and CA.firm_limits("mffu")["max_funded_total"] == 5)
    R = json.load(open(os.path.join(ROOT, "research", "props", "firm_research.json"), encoding="utf-8"))
    check("firm_research.json carries the dated MFFU sources (copy article, Builder 50K / 25K guides)",
          all(k in R["sources"] for k in ("mffu_copy", "mffu_b50", "mffu_b25")) and R["firms"]["mffu"]["copy_trading"]["date"] == "2026-11-16")


def copy_run(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "mffu50b", "name": "MFFU 50K #2", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY,
            "adapter": "ninjatrader", "nt_account": "Sim102"}]
    b, fl, ads, notes = make(os.path.join(tmp, "run"), acc, now, factory=lambda f, c: Rec(c, broker=True))
    f = fol(fl, "mffu50b")
    check("the copy is built and ready on Sim (SIM label, no live gate)", f.problem is None and f.adapter is not None and f.spec["label"] == "SIM",
          f.problem)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, qty=30)
    b.t = now + 3
    fl.tick("NQ", b.t)
    e = ents(ads["mffu50b"])
    one = (20 + FM.SLIP_PTS) * 2 + FM.COMM
    q = e[0]["qty"] if e else 0
    check("Zlarior's entry copied once: same side, stop and target, the NinjaTrader adapter on Sim102",
          len(e) == 1 and e[0]["side"] == "buy" and e[0]["stop"] == 19980.0 and e[0]["target"] == 20120.0, e)
    check("sized by Zlarior's two_week eval sizing on the Builder 50K: 1..40 micros, a full stop-out fits the $1,000 soft daily loss "
          "and the $2,000 room", 0 < q <= 40 and q * one <= 1000 and q * one <= 2000, (q, f.last_size))
    check("never opposite Zlarior: the copy is long with the lead", fl.opposite_open(-1) is not None and f.pos["dir"] == 1)
    b.t += 900
    b.lit_exit(30 * (120 * 2 - FM.COMM), "TARGET", qty=30)
    fl.tick("NQ", b.t)
    check("the lead's target exit closes the copy and books its own micros", f.pos is None and abs(f.closes[-1][2] - round((120 * 2 - FM.COMM) * q, 2)) < 0.02,
          f.closes)
    # MFFU's flat time: no new entry 5 min before 16:10 ET
    acc2 = [{"id": "late", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}]
    t2 = ts(DAY, 16, 7)
    b2, fl2, ads2, _ = make(os.path.join(tmp, "flat"), acc2, t2)
    b2.lit_enter(1, 20000.0, 19980.0, 20120.0, t=t2)
    b2.t = t2 + 2
    fl2.tick("NQ", b2.t)
    check("no copy 3 minutes before MFFU's 16:10 flat (the firm's flat time, checked per order)", not ents(ads2["late"])
          and fol(fl2, "late").skips and ("16:10" in fol(fl2, "late").skips[-1]["why"] or "flat" in fol(fl2, "late").skips[-1]["why"]),
          fol(fl2, "late").skips)


def lifecycle(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "mffu50b", "name": "MFFU 50K #2", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-11-10", "prior_pnl": 2800.0}]
    b, fl, ads, notes = make(os.path.join(tmp, "life"), acc, now)
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    q = ents(ads["mffu50b"])[0]["qty"] if ents(ads["mffu50b"]) else 0
    b.t = now + 1200
    b.lit_exit(10 * (120 * 2 - FM.COMM), "TARGET")
    fl.tick("NQ", b.t)
    f = fol(fl, "mffu50b")
    check("eval: +$2,800 before + today's copy >= $3,000 -> PASSED, push with the --to-funded line",
          q > 0 and f.view(b.t)["status"]["status"] == "passed" and any("EVAL PASSED" in n[0] and "--to-funded mffu50b" in n[1] for n in notes),
          (q, f.view(b.t)["status"], notes))
    b.t = now + 86400
    b.lit_enter(1, 20000.0, 19980.0, 20120.0, t=b.t)
    fl.tick("NQ", b.t + 2)
    check("a passed eval takes no new entry (until the owner switches it to funded)", len(ents(ads["mffu50b"])) == 1 and "passed" in f.skips[-1]["why"])
    # funded: payout readiness the MFFU way
    P = CA.profile_for({"plan": "mffu_builder_50k", "stage": "funded"})
    st = FM.book(50000.0, [("2026-12-01", 1, 1400.0), ("2026-12-02", 2, 1300.0)], "2026-12-03")
    s = FM.status(P, st)["payout"]
    check("funded: +$2,700 over 2 days ($600 over the $2,100 buffer, best day 52%) -> NOT ready: the best-day rule (trade more days)",
          s["above_buffer"] == 600.0 and s["consistency_ok"] is False and s["ready"] is False, s)
    st2 = FM.book(50000.0, [("2026-12-01", 1, 900.0), ("2026-12-02", 2, 900.0), ("2026-12-03", 3, 900.0)], "2026-12-04")
    s2 = FM.status(P, st2)["payout"]
    check("funded: +$2,700 over 3 even days -> READY ($600 above the buffer, >= $500, 2+ traded days, best day 33%)",
          s2["ready"] is True and s2["above_buffer"] == 600.0 and s2["split"] == 0.8, s2)
    st3 = FM.book(50000.0, [("2026-12-01", 1, 1200.0), ("2026-12-02", 2, 1200.0)], "2026-12-03")
    s3 = FM.status(P, st3)["payout"]
    check("funded: +$2,400 -> not ready ($300 above the buffer, $200 short of MFFU's $500)", s3["ready"] is False and s3["above_buffer"] == 300.0, s3)


def slots(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": "f50", "lead": "zlarior", "plan": "mffu_builder_50k", "stage": "funded", "funded_start": "2026-11-01"}]
    bot = Bot(os.path.join(tmp, "slot"), now)
    bot._lit_sizing = {**bot._lit_sizing, "mode": "funded"}
    b, fl, ads, notes = make(os.path.join(tmp, "slot"), acc, now, bot=bot)
    check("copy_accounts.lead_held: Zlarior in LIT's funded mode holds one funded MFFU Builder 50K", CA.lead_held(b) == {"mffu_builder_50k": 1},
          CA.lead_held(b))
    why = fol(fl, "f50").why_not(now)
    check("the running bot blocks a funded Builder 50K copy while Zlarior's own funded Builder 50K is active (MFFU: 1 a person)",
          why and "over the firm's account limit" in why and "1 already" in why, why)
    check("... and the Fleet page warns (your own bot's account counted)", any("of your own bots'" in w for w in fl.api(now)["warnings"]),
          fl.api(now)["warnings"])
    b.lit_enter(1, 20000.0, 19980.0, 20120.0)
    fl.tick("NQ", now + 3)
    check("... so Zlarior's entry is NOT copied there", not ents(ads["f50"]))
    b2, fl2, ads2, _ = make(os.path.join(tmp, "slot2"), acc, now, bot=copy.copy(bot))
    fl2.cfg["held_funded"] = {"mffu_builder_50k": 0}
    check("the owner's word wins (data/fleet.json held_funded {mffu_builder_50k: 0}): the funded copy may trade",
          fol(fl2, "f50").why_not(now) is None, fol(fl2, "f50").why_not(now))
    bot3 = Bot(os.path.join(tmp, "slot3"), now)
    bot3.acct_b = type("B", (), {"spec": {"stage": "funded", "plan": "builder25k"}, "name": "Sim199"})()
    check("ATLAS in its funded stage holds a funded Builder 25K", CA.lead_held(bot3) == {"mffu_builder_25k": 1}, CA.lead_held(bot3))
    acc3 = [{"id": "r50", "lead": "zlarior", "plan": "mffu_rapid_50k", "stage": "funded", "funded_start": "2026-11-01"}]
    b3, fl3, _, _ = make(os.path.join(tmp, "slot3"), acc3, now, bot=bot3)
    fl3.cfg["held_funded"] = {"mffu_builder_50k": 1, "mffu_rapid_eod_50k": 3}
    why3 = fol(fl3, "r50").why_not(now)
    check("MFFU's 5 sim-funded in all: Zlarior 50K + ATLAS 25K + 3 more held -> a 6th funded MFFU copy is blocked",
          why3 and "allows 5 funded accounts" in why3, why3)
    check("slot_full (the command line's check): one more Builder 50K is full with Zlarior funded, free without",
          CA.slot_full("mffu_builder_50k", {"mffu_builder_50k": 1}) and CA.slot_full("mffu_builder_50k", {}) is None
          and CA.slot_full("mffu_builder_25k", {"mffu_builder_25k": 1}) is None and CA.slot_full("mffu_builder_25k", {"mffu_builder_25k": 2}))
    check("held_from_files: nothing funded on a fresh PC, Zlarior + ATLAS when their files say funded",
          CA.held_from_files(held_root(tmp)) == {} and CA.held_from_files(held_root(tmp, "funded", "funded")) == {"mffu_builder_50k": 1, "mffu_builder_25k": 1})


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_fleet_mffu_")
    from engine import ninjatrader as NT
    keep_allow = NT.ALLOW_PATH
    NT.ALLOW_PATH = os.path.join(tmp, "allow.json")
    try:
        rules()
        cli(tmp)
        copy_run(tmp)
        lifecycle(tmp)
        slots(tmp)
    finally:
        NT.ALLOW_PATH = keep_allow
        FL.HELD_ROOT = None
        shutil.rmtree(tmp, ignore_errors=True)
    n_fail = RES.count(False)
    print(f"fleet_mffu: {len(RES) - n_fail}/{len(RES)} " + ("OK" if not n_fail else "FAILED"))
    return 0 if not n_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
