"""One signal, many accounts (engine/copy_accounts.py + its hooks in engine/fleet.py). Temp dirs only: never the real
data/, the allowlist or live_model*.json; paper / recording adapters, no NinjaTrader, nothing armed for real.

    python -X utf8 -m tests.test_copy_accounts          (~10 s)

Covers: OFF by default (no fleet file = nothing built, engine.live does not load this module); the firm profiles as data
(MFFU Builder 25K / 50K values, placeholder firms never trade, the field docs); owner values only ever tighten a verified
firm rule (more contracts / a bigger max loss / a looser floor refused), unknown values may be filled; each account's own
limits (day stop, week stop, max contracts, max $ risk) and a bad "own" block; never more contracts than the firm allows;
the firm's account limits (MFFU: 1 funded 50K + 2 funded 25K per person, the owner's accounts outside the fleet counted);
the owner's stop-for-today switch; arming needs the phrase typed for THAT account Name (wrong / none / closed console =
not armed; a hand-set "armed": true or a changed Name is refused by the live gate); a simulated session with 3 accounts at
different rooms (different micros on the same signal, one account stopping for the day on its own day stop while the
other two keep copying) for Zlarior (LIT) and ATLAS.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import copy_accounts as CA  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import fleet as FL  # noqa: E402
from engine.ninjatrader import LIVE_ENV  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests.test_fleet import Bot, Lead, ents, fol, make, ts  # noqa: E402

RES = []
DAY = "2026-10-21"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)
    return bool(ok)


def loss1(risk_pts):
    """$ a micro at a full stop-out the firm's way (2 ticks of slippage + costs)."""
    return (risk_pts + FM.SLIP_PTS) * 2.0 + FM.COMM


# ------------------------------------------------------------------------------------------------------------- off
def off_checks(tmp):
    b = Bot(tmp, ts(DAY, 9, 0))
    check("OFF: no fleet block / no accounts -> nothing built", FL.build(b, None) is None and FL.build(b, {"accounts": []}) is None)
    check("OFF: a missing data/fleet.json reads as no accounts", FL.load_file(os.path.join(tmp, "none", "fleet.json"))["accounts"] == [])
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys, engine.live; print('engine.copy_accounts' in sys.modules, "
                        "'engine.fleet' in sys.modules)"], cwd=ROOT, capture_output=True, text=True, timeout=180)
    check("OFF: importing the live bot loads neither the fleet nor this module (they load only when a fleet file has accounts)",
          r.stdout.strip().endswith("False False"), (r.stdout[-300:], r.stderr[-300:]))
    src = open(os.path.join(ROOT, "engine", "copy_accounts.py"), encoding="utf-8").read()
    check("engine/copy_accounts.py never routes, sets NINJATRADER_LIVE or writes a file",
          "os.environ[" not in src and ".send(" not in src and ', "w"' not in src and "write(" not in src)


# ------------------------------------------------------------------------------------------------------------- data
def profile_checks():
    p50 = CA.tighten("mffu_builder_50k", "eval")
    p25 = CA.tighten("mffu_builder_25k", "eval")
    f50 = CA.tighten("mffu_builder_50k", "funded")
    f25 = CA.tighten("mffu_builder_25k", "funded")
    check("MFFU Builder 50K eval: $3,000 target, $2,000 EOD, locks at +$100, $1,000 soft daily, 40 micros, no best-day rule",
          (p50["target"], p50["dd_type"], p50["dd_amount"], p50["lock"], p50["dll"], p50["dll_type"], FM.max_micros(p50), p50["consistency"])
          == (3000.0, "eod", 2000.0, 100.0, 1000.0, "soft", 40, "none"), p50)
    check("MFFU Builder 25K eval: $1,500 target, $1,000 EOD, $600 soft daily, 20 micros",
          (p25["target"], p25["dd_amount"], p25["dll"], FM.max_micros(p25)) == (1500.0, 1000.0, 600.0, 20), p25)
    check("MFFU funded: 1 Builder 50K and 2 Builder 25K per person (verified, enforced as max_active)",
          f50.get("max_active") == 1 and f25.get("max_active") == 2 and f50["verified"].get("max_active") is True, (f50.get("max_active"), f25.get("max_active")))
    d = json.load(open(CA.PROFILES_PATH, encoding="utf-8"))
    flds = d["fields"]
    check("copy_profiles.json documents every plan field, the firm fields, the own limits and the switches",
          all(k in flds["plan (eval / funded block)"] for k in ("dd_type", "dd_amount", "lock", "dll", "max_micros", "consistency", "max_active"))
          and any("own" in k for k in flds) and "accounts.max_funded_total" in flds["firm"])
    ph = CA.base_profile("bulenox_eod_50k", "eval")
    check("placeholder plan (Bulenox) loads from copy_profiles.json, marked placeholder, max loss unknown",
          ph is not None and ph.get("placeholder") and ph.get("dd_amount") is None and "placeholder" in ph["warn"][0], ph)
    chk = FM.check(ph, FM.book(50000.0, [], DAY), {"sym": "NQ", "side": "buy", "qty": 1, "entry": 20000.0, "stop": 19980.0, "target": 20100.0})
    check("a placeholder plan never trades (no room assumed until the max loss is filled)", chk["ok"] is False and chk["max_qty"] == 0
          and any("max loss amount unknown" in x for x in chk["block"]), chk)
    check("firm_rules.json wins over a placeholder of the same id (none collide today)",
          not set(d["plans"]) & set((FM.load().get("plans") or {})))
    uf = dict(CA.unfilled())
    check("--unfilled lists the placeholder fields still to fill (from the firm research)", "dd_amount" in uf.get("new_firm_50k", [])
          and "accounts.max_funded_total" in uf.get("firm mffu", []), uf)
    check("firm account limits: Lucid 5 (the smaller reading), MFFU firm total unknown, Bulenox 3",
          CA.firm_limits("lucid")["max_funded_total"] == 5 and CA.firm_limits("mffu")["max_funded_total"] is None
          and CA.firm_limits("bulenox")["max_funded_total"] == 3)
    check("CLI --show prints a plan with the own limits", CA.main(["--show", "mffu_builder_25k", "--own", "day_stop_usd=250,max_micros=6"]) == 0
          and CA.main(["--show", "no_such_plan"]) == 1 and CA.main(["--show", "mffu_builder_25k", "--own", "day_stop_usd=-1"]) == 1)


def tighten_checks():
    P = CA.tighten("mffu_builder_50k", "eval", rules={"max_micros": 100, "dd_amount": 5000, "dd_type": "static", "lock": 50, "dll": 3000})
    check("owner values that LOOSEN a verified firm rule are refused (100 micros, $5,000 max loss, static floor, lower lock, $3,000 daily)",
          FM.max_micros(P) == 40 and P["dd_amount"] == 2000.0 and P["dd_type"] == "eod" and P["lock"] == 100.0 and P["dll"] == 1000.0
          and len(P["owner_refused"]) == 5 and any("owner value refused" in w for w in P["warn"]), P["owner_refused"])
    P = CA.tighten("mffu_builder_50k", "eval", rules={"max_micros": 10, "dd_type": "intraday", "dll": 500, "consistency": 0.4})
    check("owner values that TIGHTEN are kept (10 micros, intraday floor, $500 daily, a 40% best-day rule)",
          FM.max_micros(P) == 10 and P["dd_type"] == "intraday" and P["dll"] == 500 and P["consistency"] == 0.4
          and not P["owner_refused"] and P["verified"]["max_micros"] == "owner")
    P = CA.tighten("lucid_pro_50k", "funded", rules={"payout": {"buffer": 2100}})
    check("payout values and unknown / unverified rules may still be filled by the owner (as before)", P["payout"].get("buffer") == 2100)
    P = CA.tighten("mffu_builder_25k", "eval", own={"day_stop_usd": 250, "week_stop_usd": 500, "max_micros": 6, "max_risk_usd": 150})
    check("own limits: the smaller of the firm's and the owner's (day $250 < $600, week $500, 6 < 20 micros, $150 a trade)",
          P["dll"] == 250 and P["dll_type"] == "own day stop" and P["firm_dll"] == 600.0 and P["weekly_stop"] == 500
          and FM.max_micros(P) == 6 and P["max_risk_usd"] == 150, P.get("own_applied"))
    P = CA.tighten("mffu_builder_25k", "eval", own={"day_stop_usd": 5000, "max_micros": 99})
    check("an own limit looser than the firm's changes nothing (the firm's $600 / 20 micros stay)",
          P["dll"] == 600.0 and P["dll_type"] == "soft" and FM.max_micros(P) == 20 and P["own_applied"] == {})
    for bad in ({"day_stop_usd": -5}, {"max_micros": 2.5}, {"daily": 300}, "x", {"max_risk_usd": "lots"}):
        n = FL.normalize({"id": "o", "plan": "mffu_builder_50k", "start": DAY, "own": bad})
        if not check(f"a bad own block {bad!r} = the account never trades (problem named)", n["problem"] and "own" in n["problem"], n["problem"]):
            break
    n = FL.normalize({"id": "o", "plan": "mffu_builder_50k", "start": DAY, "own": {"day_stop_usd": 300}})
    check("a good own block is kept on the follower", n["problem"] is None and n["own"] == {"day_stop_usd": 300}, n)
    st = FM.book(25000.0, [], DAY)
    P = CA.tighten("mffu_builder_25k", "eval", rules={"max_micros": 400})
    c = FM.check(P, st, {"sym": "NQ", "side": "buy", "qty": 400, "entry": 20000.0, "stop": 19999.0, "target": 20003.0})
    check("never more contracts than the firm allows: 400 asked on a 25K (owner tried 400) -> at most 20", c["max_qty"] <= 20, c)


def slot_checks(tmp):
    now = ts(DAY, 9, 40)
    acc = [{"id": f"f{i}", "lead": "zlarior", "plan": "mffu_builder_25k", "stage": "funded", "funded_start": "2026-10-01"} for i in range(3)]
    acc.append({"id": "e1", "lead": "zlarior", "plan": "mffu_builder_25k", "start": DAY})
    b, fl, ads, notes = make(os.path.join(tmp, "slot"), acc, now)
    w = {f.id: f.why_not(now) for f in fl.followers}
    check("MFFU: 2 funded Builder 25K followers trade, the 3rd is over the firm's limit; an eval is not counted",
          w["f0"] is None and w["f1"] is None and "account limit" in (w["f2"] or "") and w["e1"] is None, w)
    b, fl, ads, notes = make(os.path.join(tmp, "slot2"), acc[:2], now)
    fl.cfg["held_funded"] = {"mffu_builder_25k": 1}
    w = {f.id: f.why_not(now) for f in fl.followers}
    check("held_funded: a 25K the owner already holds outside the fleet takes a slot (the 2nd follower is over)",
          w["f0"] is None and "account limit" in (w["f1"] or ""), w)
    b, fl, ads, notes = make(os.path.join(tmp, "slot3"), [{"id": "z", "lead": "zlarior", "plan": "mffu_builder_50k", "stage": "funded",
                                                         "funded_start": "2026-10-01"}], now)
    fl.cfg["held_funded"] = {"mffu_builder_50k": 1}
    check("LIT's own funded 50K listed as held: a funded 50K follower is refused (MFFU allows 1)", "allows 1" in (fol(fl, "z").why_not(now) or ""))
    acc_l = [{"id": f"l{i}", "lead": "zlarior", "plan": ("lucid_pro_50k" if i % 2 else "lucid_pro_25k"), "stage": "funded",
              "funded_start": "2026-10-01"} for i in range(6)]
    b, fl, ads, notes = make(os.path.join(tmp, "slot4"), acc_l, now)
    w = [f.why_not(now) for f in fl.followers]
    check("firm total: Lucid 5 funded in all (unverified, the smaller reading): the 6th is over", all(x is None for x in w[:5]) and "5 funded" in (w[5] or ""), w)
    # the slot check reaches the copy itself: the over-limit follower skips the lead's entry with the reason
    b, fl, ads, notes = make(os.path.join(tmp, "slot5"), acc[:3], now)
    b.lit_enter(1, 20000.0, 19985.0, 20090.0, qty=20)
    b.t = now + 3
    fl.tick("NQ", b.t)
    check("... and on a real lead entry the 3rd funded 25K is not copied (skip says why), the first two are",
          len(ents(ads["f0"])) == 1 and len(ents(ads["f1"])) == 1 and not ents(ads["f2"]) and "account limit" in fol(fl, "f2").skips[-1]["why"],
          [fol(fl, "f2").skips])


def switch_checks(tmp):
    p = os.path.join(tmp, "cli", "fleet.json")
    run = lambda *a: FL.run(list(a) + ["--file", p])
    rc, _ = run("--add", "--id", "m25", "--plan", "mffu_builder_25k", "--account", "Sim120", "--start", DAY, "--daily-stop", "250",
                "--max-micros", "6")
    d = FL.load_file(p)
    check("CLI --add a prop account with its own limits (--daily-stop / --max-micros) -> 'own', never armed",
          rc == 0 and d["accounts"][0].get("own") == {"day_stop_usd": 250.0, "max_micros": 6} and d["accounts"][0]["armed"] is False, d)
    rc, ln = run("--stop-today", "m25", "--now", str(ts(DAY, 10, 0)))
    d = FL.load_file(p)
    check("CLI --stop-today writes this session's day", rc == 0 and d["accounts"][0].get("stop_day") == DAY, (rc, ln, d))
    n = FL.normalize(d["accounts"][0])
    now = ts(DAY, 10, 5)
    b, fl, ads, notes = make(os.path.join(tmp, "stop"), [d["accounts"][0]], now)
    f = fol(fl, "m25")
    check("stopped for today: no new entry today, the reason says it resumes", "stopped for today" in (f.why_not(now) or ""), f.why_not(now))
    check("... the next session it trades again by itself", f.why_not(ts("2026-10-22", 9, 40)) is None, f.why_not(ts("2026-10-22", 9, 40)))
    rc, _ = run("--resume-today", "m25")
    check("CLI --resume-today clears it", rc == 0 and not FL.load_file(p)["accounts"][0].get("stop_day") and n["problem"] is None)
    rc, ln = run("--stop-today", "nobody")
    check("CLI --stop-today of an unknown id fails", rc == 1)
    # the own kill switch still flattens just that account
    acc = [{"id": "k1", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}, {"id": "k2", "lead": "zlarior", "plan": "mffu_builder_50k", "start": DAY}]
    now = ts(DAY, 9, 40)
    b, fl, ads, notes = make(os.path.join(tmp, "kill"), acc, now)
    b.lit_enter(1, 20000.0, 19985.0, 20090.0, qty=20)
    b.t = now + 3
    fl.tick("NQ", b.t)
    fol(fl, "k1").spec["killed"] = True
    b.t += 30
    fl.tick("NQ", b.t)
    check("own kill switch: the killed account is flattened, the other keeps its copy", fol(fl, "k1").pos is None and fol(fl, "k2").pos is not None
          and fol(fl, "k1").closes[-1][4] == "KILL SWITCH")


def arm_checks(tmp):
    p = os.path.join(tmp, "arm", "fleet.json")
    from engine import ninjatrader as NT
    run = lambda inp, *a: FL.run(list(a) + ["--file", p], inp=inp)
    FL.run(["--add", "--id", "r1", "--plan", "mffu_builder_25k", "--account", "MFFUEVAL25K-9", "--start", DAY, "--file", p])
    FL.run(["--add", "--id", "s1", "--plan", "mffu_builder_25k", "--account", "Sim121", "--start", DAY, "--file", p])
    asked = []

    def eof(prompt):
        asked.append(prompt)
        raise EOFError
    for label, inp in (("nothing typed (closed console)", eof), ("a wrong line", lambda _p: "yes"), ("the phrase in lower case missing a word", lambda _p: "i accept risk")):
        rc, ln = run(inp, "--arm", "r1")
        a = FL.load_file(p)["accounts"][0]
        if not check(f"--arm a real account with {label}: NOT armed, the allowlist untouched", rc == 1 and a["armed"] is False and not a.get("armed_for")
                     and "MFFUEVAL25K-9" not in NT.allowed_accounts(), (rc, ln, a)):
            break
    check("the prompt names the account it arms", asked and "MFFUEVAL25K-9" in asked[0], asked)
    rc, ln = run(lambda _p: "  i accept   live risk ", "--arm", "r1")
    raw = open(p, encoding="utf-8").read()
    a = FL.load_file(p)["accounts"][0]
    check("--arm with the phrase typed (any case / spaces): armed for THIS Name, allowlisted, the phrase never stored",
          rc == 0 and a["armed"] is True and a["armed_for"] == "MFFUEVAL25K-9" and "MFFUEVAL25K-9" in NT.allowed_accounts()
          and LIVE_PHRASE not in raw, (rc, ln, a))
    rc, ln = run(eof, "--arm", "s1")
    check("--arm a Sim account needs no phrase (it never trades real money)", rc == 0 and FL.load_file(p)["accounts"][1]["armed"] is True)
    rc, _ = run(None, "--disarm", "r1")
    a = FL.load_file(p)["accounts"][0]
    check("--disarm clears armed and armed_for", rc == 0 and a["armed"] is False and "armed_for" not in a, a)
    # the live gate: a real follower needs armed + armed_for == its Name + the phrase at the bot's start + NINJATRADER_LIVE=1
    saved = os.environ.get(LIVE_ENV)
    os.environ[LIVE_ENV] = "1"
    try:
        real = {"id": "r1", "plan": "mffu_builder_25k", "start": DAY, "adapter": "ninjatrader", "nt_account": "MFFUEVAL25K-9", "armed": True}
        cfg = {"confirm": LIVE_PHRASE}
        g0 = FL.live_gate(FL.normalize(real), cfg)
        g1 = FL.live_gate(FL.normalize({**real, "armed_for": "MFFUEVAL25K-1"}), cfg)
        g2 = FL.live_gate(FL.normalize({**real, "armed_for": "mffueval25k-9"}), cfg)
        g3 = FL.live_gate(FL.normalize({**real, "armed_for": "MFFUEVAL25K-9"}), {"confirm": ""})
        check("live gate: a hand-set \"armed\": true (no typed arming for this Name) is refused", g0 and "typed phrase" in g0, g0)
        check("live gate: armed for another Name (the Name changed after arming) is refused", g1 and "typed phrase" in g1, g1)
        check("live gate: armed for this Name + the phrase at the bot's start + NINJATRADER_LIVE=1 -> may trade", g2 is None, g2)
        check("live gate: armed for this Name but no phrase at the bot's start -> refused (the start phrase is still needed)", g3 and "phrase" in g3, g3)
        b = Bot(os.path.join(tmp, "gate"), ts(DAY, 9, 40), cfg={"confirm": LIVE_PHRASE})
        made = []
        _, fl, _, _ = make(os.path.join(tmp, "gate"), [real], ts(DAY, 9, 40), bot=b, factory=lambda f, c: made.append(f.id))
        check("a new real account in the fleet file with \"armed\": true but no typed arming gets no adapter (never trades)",
              fol(fl, "r1").adapter is None and not made and "typed phrase" in (fol(fl, "r1").problem or ""), fol(fl, "r1").problem)
    finally:
        if saved is None:
            os.environ.pop(LIVE_ENV, None)
        else:
            os.environ[LIVE_ENV] = saved
    rc, _ = FL.run(["--to-funded", "r1", "--account", "MFFUFUNDED25K-9", "--start", "2026-11-20", "--file", p])
    a = FL.load_file(p)["accounts"][0]
    check("--to-funded disarms (armed and armed_for cleared: the funded Name is armed again by the owner)", a["armed"] is False and "armed_for" not in a, a)


# ------------------------------------------------------------------------------------------------------------- session
def session_lit(tmp):
    """One LIT signal, 3 accounts at different rooms: different micros, each within its firm's and its own limits."""
    now = ts(DAY, 9, 40)
    acc = [{"id": "a50", "name": "50K fresh", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-10-19"},
           {"id": "b50", "name": "50K near floor", "lead": "zlarior", "plan": "mffu_builder_50k", "start": "2026-10-19", "prior_pnl": -1500.0},
           {"id": "c25", "name": "25K own $250 day", "lead": "zlarior", "plan": "mffu_builder_25k", "start": "2026-10-19", "own": {"day_stop_usd": 250}}]
    b, fl, ads, notes = make(os.path.join(tmp, "s_lit"), acc, now)
    b.lit_enter(1, 20000.0, 19985.0, 20090.0, qty=30)
    b.t = now + 3
    fl.tick("NQ", b.t)
    q = {i: (ents(ads[i])[0]["qty"] if ents(ads[i]) else 0) for i in ads}
    print(f"      LIT signal (15-pt stop): micros {q}  (room a50 $2,000 / b50 $500 / c25 $1,000 with an own $250 day stop)")
    check("LIT session: all 3 accounts copy the one signal, each with its own micros (different rooms -> different sizes)",
          all(q[i] > 0 for i in q) and len(set(q.values())) == 3, q)
    check("the account near its floor ($500 room) takes fewer micros than the fresh 50K, and a full stop-out stays above the floor",
          q["b50"] < q["a50"] and q["b50"] * loss1(15) < 500, q)
    check("the 25K's copy fits its own $250 day stop (not only the firm's $600) and its 20-micro cap", q["c25"] * loss1(15) <= 250 and q["c25"] <= 20, q)
    check("no account above its firm's contracts (50K: 40, 25K: 20)", q["a50"] <= 40 and q["b50"] <= 40 and q["c25"] <= 20, q)
    b.t += 900
    b.lit_exit(-30 * (15 * 2 + FM.COMM), "STOP", qty=30)
    fl.tick("NQ", b.t)
    got = {f.id: f.closes[-1][2] for f in fl.followers if f.closes}
    check("the lead's stop-out closes every copy at the lead's $ a micro x its own micros",
          all(abs(got[i] + q[i] * (15 * 2 + FM.COMM)) < 0.05 for i in q), got)


def session_atlas(tmp):
    """ATLAS (2 a day): the first signal stops out; the 25K reaches its own day stop and stops for the day, the two 50Ks
    copy the second signal, each sized from the room it has left."""
    now = ts(DAY, 9, 40)
    acc = [{"id": "a50", "name": "50K fresh", "lead": "atlas", "plan": "mffu_builder_50k", "start": "2026-10-19"},
           {"id": "b50", "name": "50K near floor", "lead": "atlas", "plan": "mffu_builder_50k", "start": "2026-10-19", "prior_pnl": -1500.0},
           {"id": "c25", "name": "25K own $250 day", "lead": "atlas", "plan": "mffu_builder_25k", "start": "2026-10-19", "own": {"day_stop_usd": 250}}]
    b, fl, ads, notes = make(os.path.join(tmp, "s_atlas"), acc, now)
    b.acct_b = Lead("Sim102")
    b.acct_b.enter(now, 1, 3, 20000.0, 19985.0, 20090.0)
    b.t = now + 3
    fl.tick("NQ", b.t)
    q1 = {i: (ents(ads[i])[0]["qty"] if ents(ads[i]) else 0) for i in ads}
    check("ATLAS signal 1: the 3 accounts copy with different micros", all(q1[i] > 0 for i in q1) and len(set(q1.values())) == 3, q1)
    b.t = ts(DAY, 10, 5)
    b.acct_b.exit(b.t, -3 * (15 * 2 + FM.COMM), "STOP")
    fl.tick("NQ", b.t)
    day = {f.id: f.state(b.t)["day_pnl"] for f in fl.followers}
    b.t = ts(DAY, 11, 0)
    b.acct_b.enter(b.t, 1, 3, 20010.0, 19995.0, 20100.0)
    fl.tick("NQ", b.t + 2)
    q2 = {i: (ents(ads[i])[1]["qty"] if len(ents(ads[i])) > 1 else 0) for i in ads}
    c = fol(fl, "c25")
    print(f"      ATLAS signal 1 micros {q1}; day P&L after its stop-out {day}; signal 2 micros {q2}")
    print(f"      c25 skip: {c.skips[-1]['why'] if c.skips else None}")
    check("ATLAS signal 2: the 25K stopped for the day (its own $250 day stop has less than one micro's stop-out left)",
          q2["c25"] == 0 and c.skips and "own day stop" in c.skips[-1]["why"], c.skips[-1:])
    check("... while both 50Ks keep copying", q2["a50"] > 0 and q2["b50"] > 0, q2)
    check("... the 50K near its floor sizes signal 2 from the room left after the loss (fewer micros than signal 1)",
          q2["b50"] < q1["b50"] and q2["b50"] * loss1(15) < 500 + day["b50"], (q1, q2, day))
    check("... and the fresh 50K, with the most room left, still takes the biggest copy (each account its own room)",
          q2["a50"] > q2["b50"] > q2["c25"], (q1, q2))
    rows = {r["id"]: r for r in fl.api(b.t + 2)["accounts"]}
    check("the Fleet rows show each account's own day left (the 25K at its own day stop)", rows["c25"]["day_left"] is not None
          and rows["c25"]["day_left"] < loss1(15) and rows["a50"]["day_left"] > rows["c25"]["day_left"], {k: v["day_left"] for k, v in rows.items()})


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_copy_")
    keep_path = FL.FLEET_PATH
    FL.FLEET_PATH = os.path.join(tmp, "no_fleet", "fleet.json")      # never the real data/fleet.json
    from engine import ninjatrader as NT
    keep_allow = NT.ALLOW_PATH
    NT.ALLOW_PATH = os.path.join(tmp, "nt_accounts_allow.json")      # never the real allowlist (--arm adds a real Name)
    saved = {k: os.environ.get(k) for k in (LIVE_ENV, "LE_LIT_LEARNING")}
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    os.environ.pop(LIVE_ENV, None)
    try:
        off_checks(tmp)
        profile_checks()
        tighten_checks()
        slot_checks(tmp)
        switch_checks(tmp)
        arm_checks(tmp)
        session_lit(tmp)
        session_atlas(tmp)
    finally:
        FL.FLEET_PATH = keep_path
        NT.ALLOW_PATH = keep_allow
        CA.INPUT = None
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"copy_accounts: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
