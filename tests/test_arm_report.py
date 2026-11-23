"""START's armed-false fix (2026-11-22): the eval -> funded rename (one candidate / many / none / already fine / Sim untouched),
the phrase gate, the loud summary lines and the phone's reason. Every outside effect is faked; no real account is touched."""
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
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


OLD, NEW = "MFFUEVBLDR256018", "MFFUSFBLDR256018"
LIT = "MFFUEVBLDR506001"
OK = lambda: (True, "selftest faked")  # noqa: E731


def setup(tmp, nt, atlas=OLD, b_account=OLD):
    p = os.path.join(tmp, "second_model.json")
    shutil.copy(SE.CFG_PATH, p)
    AB.set_account_b(b_account, plan="builder25k", start="2026-10-26", path=p, selftest=OK)
    G.SECOND_PATH, G.ALLOW_PATH = p, os.path.join(tmp, "allow.json")
    G.CFG = os.path.join(tmp, "start_bot.json")
    G.nt_account_names = lambda: list(nt)
    G.nt_balances = lambda: {}
    G.role_of = lambda name, cfg=None, b=None, extras=None: "Zlarior's 50K" if name == LIT else None
    G.SELFTEST = OK
    G.arm_b_switch_orig = getattr(G, "arm_b_switch_orig", G.arm_b_switch)
    cfg = {"lit": LIT, "atlas": atlas}
    G._save(cfg)
    return p, cfg


def main():
    check("renamed: eval -> funded same digits", AR.renamed(OLD, NEW))
    check("renamed: other digits no", not AR.renamed(OLD, "MFFUSFBLDR256019"))
    check("renamed: other plan no", not AR.renamed(OLD, "MFFUSFRPD256018"))
    check("renamed: Sim never", not AR.renamed(OLD, "Sim101") and AR.find_funded_candidates(OLD, ["Sim101"]) == [])
    check("candidates: skip taken", AR.find_funded_candidates(OLD, [NEW], taken=lambda n: True) == [])
    L = AR.lines([AR.row("Zlarior 50K", True), AR.row("ATLAS 25K", False, "gone", "do X")])
    check("summary lines", L[0] == "ARMED: Zlarior 50K" and L[1] == "NOT ARMED: ATLAS 25K: gone -> do X"
          and any("NOT TRADING: ATLAS 25K" in x for x in L), L)
    check("summary: all armed has no banner", len(AR.lines([AR.row("Zlarior 50K", True), AR.row("ATLAS 25K", True)])) == 2)

    with tempfile.TemporaryDirectory() as tmp:             # one candidate + YES: switched, then armed
        p, cfg = setup(tmp, [LIT, "Sim101", NEW])
        shown = []
        inp = lambda prompt="": (shown.append(prompt), "YES")[1]  # noqa: E731
        r = G.resolve_atlas(cfg, inp)
        ab = AB.raw_cfg(p) or {}
        check("one candidate + YES: switched", r is None and ab.get("account") == NEW and cfg["atlas"] == NEW and ab.get("stage") == "funded", (r, ab))
        check("one candidate + YES: start config saved", G._read(G.CFG).get("atlas") == NEW)
        check("one candidate + YES: asked with both names", any(OLD in x and NEW in x for x in shown), shown)
        check("switch alone never arms", not ab.get("armed"), ab)
        rb = G.arm_b(NEW, path=p, selftest=OK)
        check("then arm_b arms the new name", rb.get("ok") and (AB.raw_cfg(p) or {}).get("armed") is True, rb)

    with tempfile.TemporaryDirectory() as tmp:             # anything but YES: untouched
        p, cfg = setup(tmp, [LIT, NEW])
        for ans in ("", "no", "y"):
            r = G.resolve_atlas(cfg, lambda prompt="", a=ans: a)
            check(f"answer {ans!r}: not switched, reason given", r and (AB.raw_cfg(p) or {}).get("account") == OLD and cfg["atlas"] == OLD, r)
        r = G.resolve_atlas(cfg, None)
        check("no console (Start page job): never switches", r and (AB.raw_cfg(p) or {}).get("account") == OLD, r)

    with tempfile.TemporaryDirectory() as tmp:             # many candidates
        p, cfg = setup(tmp, [LIT, NEW, "MFFUSFBLDR996018"])
        asked = []
        r = G.resolve_atlas(cfg, lambda prompt="": (asked.append(1), "YES")[1])
        check("many candidates: [FIX], no question, no change", r and "2 accounts" in r and not asked and (AB.raw_cfg(p) or {}).get("account") == OLD, r)

    with tempfile.TemporaryDirectory() as tmp:             # none
        p, cfg = setup(tmp, [LIT, "Sim101", "MFFUSFBLDR256019"])
        asked = []
        r = G.resolve_atlas(cfg, lambda prompt="": (asked.append(1), "YES")[1])
        check("no candidate: [FIX], no change", r and "no other account" in r and not asked and (AB.raw_cfg(p) or {}).get("account") == OLD, r)

    with tempfile.TemporaryDirectory() as tmp:             # saved name still listed: nothing to do; Sim accounts untouched
        p, cfg = setup(tmp, [LIT, OLD, NEW, "Sim101"])
        check("already listed: no switch, no question", G.resolve_atlas(cfg, lambda prompt="": 1 / 0) is None and (AB.raw_cfg(p) or {}).get("account") == OLD)
        check("NT list unknown: no switch (arm_b decides)", (setattr(G, "nt_account_names", lambda: []), G.resolve_atlas(cfg, lambda prompt="": 1 / 0))[1] is None)

    with tempfile.TemporaryDirectory() as tmp:             # start config already holds the funded name, account B the eval's
        p, cfg = setup(tmp, [LIT, NEW], atlas=NEW, b_account=OLD)
        r = G.resolve_atlas(cfg, lambda prompt="": "YES")
        check("config new / account B old: YES moves account B", r is None and (AB.raw_cfg(p) or {}).get("account") == NEW, (r, AB.raw_cfg(p)))

    with tempfile.TemporaryDirectory() as tmp:             # step_arm: the phrase gate and the summary
        p, cfg = setup(tmp, [LIT, NEW])
        armed_calls = []
        G.arm_b = lambda atlas, path=None, selftest=None: (armed_calls.append(atlas), {"ok": True})[1]
        G.arm_report_path = None
        import io
        import contextlib
        AR.PATH = os.path.join(tmp, "arm_status.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = G.step_arm(cfg, "I accept", inp=lambda prompt="": "YES")
        out = buf.getvalue()
        check("no phrase: rc 1, nothing armed, name untouched, summary says NOT ARMED",
              rc == 1 and not armed_calls and (AB.raw_cfg(p) or {}).get("account") == OLD and "NOT ARMED: ATLAS 25K" in out
              and "NOT TRADING" in out, out)
        d = json.load(open(AR.PATH))
        check("status saved for the phone", [r["armed"] for r in d["rows"]] == [False, False], d)
        check("glance reason for ATLAS", (AR.glance_reason("ATLAS") or "").startswith("ATLAS is NOT armed: the live phrase"), AR.glance_reason("ATLAS"))
        check("glance reason: stale ignored", AR.glance_reason("ATLAS", now=10 ** 11) is None)
        check("glance reason: unknown bot none", AR.glance_reason("BLITZ") is None)
        hb = {"running": True, "health": {"account": {"armed": False}}}
        lit = BG.lit(hb, {})
        check("brain glance carries nar for an unarmed bot", "nar" in lit and "NOT armed" in lit["nar"], lit.get("nar"))
        AR.save([AR.row("Zlarior 50K", True)], path=AR.PATH)
        check("brain glance: armed bot has no nar", "nar" not in BG.lit({"running": True, "health": {"account": {"armed": True}}}, {}))
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
