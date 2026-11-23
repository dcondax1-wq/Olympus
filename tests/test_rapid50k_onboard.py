"""Buying the Rapid EOD 50K is a zero-friction event (night-r50k 2026-11-23, decide card plan-rapid50k-max2-rebuys). Fakes only:
temp files, made-up MFFU-style Names, a fake bot; nothing real armed or routed.

  a. recognition: the owner's Rapid 25K already runs as "MFFUEV<code><digits>", so a new $50,000 Name with the SAME code is
     "New Rapid EOD 50K eval ...: Zlarior + ATLAS?" with ONE button (no "pick one"); a Builder code stays Builder; a code seen on
     both kinds is not trusted; with no Rapid on the PC the old "pick one" (Rapid 50K first) stays
  b. the tap (engine/onboard.do -> account_cli.add): slot rapid2, preset mffu_rapid_eod_50k, DISARMED, the 25K untouched
  c. sizing = TODAY's approved Rapid 50K defaults (no LIT x0.5, ATLAS $500 / 30% of the room, LIT on the two_week eval
     sizing): the one-account-book proposal is a note for the owner, not code
  d. arming: only the typed phrase arms it (a wrong phrase arms nothing)
  e. keep-alive: the 2nd Rapid is its own key "rapid2" (its LIT lane + its ATLAS lane = ONE target, apart from the 25K), its
     MFFU plan is the Rapid EOD 50K, the consent file accepts "rapid2"
  f. readiness lists it by name; the payout autopilot reads both Rapid slots; lifecycle's re-buy price says $165
    python -X utf8 -m tests.test_rapid50k_onboard
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import onboard as OB, rapid  # noqa: E402

RES: list = []
R25, R50 = "MFFUEVREOD99001", "MFFUEVREOD99002"      # made-up Names in MFFU's shape (EV + letters + digits)


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:400]}]" if detail and not ok else ""))


def part_a():
    known = OB.known_codes(rows=[{"name": "MFFUEVBLDR11", "plan": "builder50k"}], rapid_names=[R25])
    check("a. learned: REOD = rapid (the owner's own Rapid 25K), BLDR = builder", known == {"REOD": "rapid", "BLDR": "builder"}, known)
    i = OB.infer(R50, 50000.0, known=known)
    o = OB.offers(i)
    s = OB.say(i, o)
    check("a. $50,000 + the known Rapid code -> Rapid EOD 50K, a fresh eval, not a guess",
          i["plan"] == "rapideod" and i["kind"] == "fresh_eval" and not i["guess"], i)
    check("a. ONE right button first: 'Zlarior + ATLAS' (add:rapideod), plus 'Not for the bot'",
          o[0] == {"act": "add:rapideod", "label": "Zlarior + ATLAS", "primary": True} and len(o) == 2, o)
    check("a. the Start page says 'New Rapid EOD 50K eval ... Zlarior + ATLAS?', no 'Pick one'",
          s.startswith("New Rapid EOD 50K eval") and "Pick one" not in s, s)
    i25 = OB.infer("MFFUEVREOD99003", 25000.0, known=known)
    check("a. the same code at $25,000 -> Rapid EOD 25K", i25["plan"] == "rapideod25" and i25["kind"] == "fresh_eval", i25)
    ib = OB.infer("MFFUEVBLDR77", 50000.0, known=known)
    check("a. a Builder Name stays Builder 50K", ib["plan"] == "builder50k" and ib["kind"] == "fresh_eval", ib)
    both = OB.known_codes(rows=[{"name": "MFFUEVREOD1", "plan": "builder25k"}], rapid_names=["MFFUEVREOD2"])
    check("a. a code seen as Builder AND Rapid is not trusted", "REOD" not in both, both)
    # integration 2026-11-23: night-startfix made EVREOD MFFU's confirmed Rapid EOD prefix (seen on the owner's PC), so the
    # "no Rapid known yet: still a choice" case is a guess-only Rapid code (RPD); EVREOD at $50,000 alone = Rapid EOD 50K
    i0 = OB.infer("MFFUEVRPD99002", 50000.0, known={})
    o0 = OB.offers(i0)
    check("a. no Rapid on the PC yet: still a choice (not confirmed), Rapid EOD 50K first",
          i0["kind"] == "unknown" and o0[0]["act"] == "add:rapideod" and "Pick one" in OB.say(i0, o0), (i0, o0))
    ir = OB.infer(R50, 50000.0, known={})
    check("a. EVREOD (MFFU's Rapid EOD prefix, night-startfix) at $50,000 with nothing learned = Rapid EOD 50K, not a guess",
          ir["plan"] == "rapideod" and ir["kind"] == "fresh_eval" and not ir["guess"], ir)
    check("a. the Start page passes the learned codes (status -> infer(..., known))",
          "known_codes() if cands" in open(os.path.join(ROOT, "engine", "onboard.py"), encoding="utf-8").read())


def part_b_c_d(tmp):
    from engine import account_cli as AC, go as G
    from engine.tradovate import LIVE_PHRASE
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_r = rapid.PATH
    w = os.path.join(tmp, "world")
    os.makedirs(w, exist_ok=True)
    try:
        rapid.PATH = os.path.join(w, "rapid.json")
        G.CFG, G.SECOND_PATH = os.path.join(w, "go.json"), os.path.join(w, "account_b.json")
        G.ALLOW_PATH, G.ACCOUNTS_PATH = os.path.join(w, "allow.json"), os.path.join(w, "accounts.json")
        G.ANCHOR_PATH, G.bot_running = os.path.join(w, "anchor.json"), (lambda: False)
        r1 = AC.add("rapideod25", R25)
        raw1 = open(rapid.path(), "rb").read()
        r2 = AC.add("rapideod", R50)
        b2 = rapid.read(rapid.slot_path("rapid2")) or {}
        check("b. the tap's add -> slot rapid2, Rapid EOD 50K preset, DISARMED", r1.get("ok") and r2.get("ok") and r2.get("slot") == "rapid2"
              and b2.get("plan") == "mffu_rapid_eod_50k" and b2.get("armed") is False and b2.get("stage") == "eval", (r1, r2, b2))
        check("b. the Rapid 25K's file is untouched", open(rapid.path(), "rb").read() == raw1)
        check("b. the owner's sentence says NOT armed + START + the phrase", "NOT armed" in str(r2.get("say")), r2.get("say"))
        known = OB.known_codes(rapid_names=[b["account"] for _s, b in rapid.read_all()])
        check("b. after the add both Names teach the code (the next one is one tap too)", known.get("REOD") == "rapid", known)
        # c. sizing = today's defaults
        P = rapid.plan_info(b2)
        lane = rapid.lane_spec(b2, {"adapter": "ninjatrader"}, slot="rapid2")
        at = rapid.atlas_block(b2)
        check("c. ATLAS lane = today's approved $500 at 30% of the room", P["atlas_usd"] == 500.0 and rapid.ATLAS_F == 0.3, (P, at))
        check("c. LIT lane = today's two_week eval sizing, preset Rapid 50K, no x0.5 multiplier", lane["mode"] == "two_week"
              and lane["preset"] == "mffu_rapid_eod_50k" and not any(k in lane for k in ("lit_mult", "lit_scale", "scale")), lane)
        note = os.path.join(ROOT, "research", "handoff", "2026-11-23", "RAPID50K_SETTINGS.md")
        txt = open(note, encoding="utf-8").read() if os.path.exists(note) else ""
        check("c. the one-account-book change is written for the owner (not in code)", "x0.5" in txt and "yes" in txt.lower(), note)
        # d. arming
        AC.arm("i accept")
        check("d. a wrong phrase arms nothing", (rapid.read(rapid.slot_path("rapid2")) or {}).get("armed") is False)
        AC.arm(LIVE_PHRASE)
        check("d. the owner's typed phrase (START BOT) arms the Rapid 50K", (rapid.read(rapid.slot_path("rapid2")) or {}).get("armed") is True)
        # f. payout autopilot reads both slots
        from engine import payout_autopilot as PA
        seen = []
        keep_st = rapid.status
        rapid.status = lambda slot="rapid", **k: (seen.append(slot), {"on": True, "stage": "funded", "payout": {"ready": False},
                                                                       "today_net": 0.0})[1]
        try:
            PA.gather("2026-11-24")
        finally:
            rapid.status = keep_st
        check("f. the payout autopilot reads both Rapid slots", seen == ["rapid", "rapid2"], seen)
        from engine import keepalive as KA
        check("e. keep-alive consent knows the key 'rapid2' once the slot is set", "rapid2" in KA.known_keys(os.path.join(w, "ka.json")))
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH = keep_r


class Ad:
    name = "ninjatrader"


class Obj:
    def __init__(self, name=None, spec=None, slot=None):
        self.name, self.spec, self.adapter, self.problem = name, spec or {}, Ad(), None
        if slot:
            self.slot = slot
        self.id = (spec or {}).get("id")


def part_e():
    from engine import keepalive as KA

    class Accts:
        pass

    class Bot:
        cfg = {"model": "lit"}
        state = {"model": "lit"}
        adapter = None
    b = Bot()
    b.acct_b = None
    b.acct_c = None
    b.fleet = None
    b.acct_r = Obj(R25)
    b.acct_r2 = Obj(R50, slot="rapid2")
    a = Accts()
    a.accounts = [Obj(spec={"id": "rapid", "lane": "rapid", "preset": "mffu_rapid_eod_25k", "nt_account": R25, "adapter": "ninjatrader"}),
                  Obj(spec={"id": "rapid2", "lane": "rapid", "slot": "rapid2", "preset": "mffu_rapid_eod_50k", "nt_account": R50,
                            "adapter": "ninjatrader"})]
    b.accts = a
    keys = sorted(ln["key"] for ln in KA.lanes(b))
    check("e. lanes: the 2nd Rapid's LIT + ATLAS lanes are keyed rapid2 (its ATLAS lane is listed)",
          keys == ["rapid", "rapid", "rapid2", "rapid2"], keys)
    tg = KA.targets(b)
    by = {g["key"]: g for g in tg}
    check("e. two targets: the Rapid 25K and the Rapid 50K apart, two lanes each", set(by) == {"rapid", "rapid2"}
          and all(len(g["lanes"]) == 2 for g in tg) and by["rapid2"]["nt"] == R50, [(g["key"], g["nt"], len(g["lanes"])) for g in tg])
    check("e. the 50K target's MFFU plan = mffu_rapid_eod_50k (the keep-alive knows its 7-day rule)",
          KA._plan_id(by["rapid2"]) == "mffu_rapid_eod_50k" and KA._plan_id(by["rapid"]) == "mffu_rapid_eod_25k")


def part_f():
    from engine import lifecycle as LC
    from engine import preflight as PF
    t, body = LC.texts("failed", "Rapid EOD 50K", {"balance": 47900, "floor": 48000})
    check("f. a failed Rapid 50K's re-buy line says $165 (not 'about $94')", "$165" in body and "$94" not in body, body)
    t, body = LC.texts("failed", "Rapid EOD 25K", {"balance": 23900, "floor": 24000})
    check("f. ... and the Rapid 25K's says $97.20", "$97.20" in body, body)
    rows = PF.arms({"health": {"accounts": [{"id": "rapid", "name": "Rapid EOD 25K", "armed": True, "label": "LIVE"},
                                            {"id": "rapid2", "name": "Rapid EOD 50K", "armed": False, "label": "LIVE"}]}})
    check("f. readiness's armed check lists the Rapid EOD 50K by name (NOT armed shows)",
          ("Rapid EOD 50K", False, "LIVE, NOT armed") in rows, rows)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="r50k_")
    try:
        for f in (part_a, lambda: part_b_c_d(tmp), part_e, part_f):
            try:
                f()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"raised {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\nrapid 50K onboarding: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
