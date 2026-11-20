"""ATLAS funded switches (2026-11-20, day-atlasedge): the two OFF-by-default funded-stage rules of
research/handoff/2026-11-20/atlasedge/APPLY_ON_YES.md (engine/account_b.py FUNDED_ON):
  "funded_room_pct": 0.4  -> Decide card atlas-funded-room-40 (risk 40% of the room a trade, not the preset's 60%)
  "streak_shrink": 2      -> Decide card atlas-funded-streak-1micro (after 2 losing trades in a row, 1 micro until a winner)

Runs on the patched engine: the repo's own engine/account_b.py once the lead applied the patch, else a temp copy of
engine/ with research/handoff/2026-11-20/atlasedge/account_b.patch applied (git apply; the repo is never touched).
Temp files only; nothing armed, nothing routed.

    python -X utf8 -m tests.test_atlas_funded_switches

 a. OFF by default: FUNDED_ON all None; a funded block without the keys has neither in its spec and sizes exactly like
    engine/sizing.funded_qty on the 25K preset (60%) + the soft daily loss, on a grid of rooms / stops / day P&L;
    bad values are a problem (not traded); the eval stage never uses them.
 b. the streak counter: counts only losing closes in a row at the end (by exit time), since the funded start; a winner
    (or a scratch >= $0) resets it; it is derived from the saved closes, so it survives a restart; another account's
    state file is never read (only ATLAS's own closes on that account count).
 c. the streak size: at streak >= N a size of 2+ becomes 1, a size of 1 stays 1, 0 stays 0: never below 1 micro, never
    above today's size (grid); below N nothing changes.
 d. room 40% on a replay: every ATLAS trade of the real 2026 day order (and 2021-25), at the state the research engine
    (tools/atlas_risk PGF3, the engine of atlas-risk-real-fills-2026-11-20.md) had at that trade, sizes exactly as the
    research sizing at pct 0.4 (+ the same soft daily loss guard); the research room-40 path itself is re-run and its
    $ / trades printed against the stored atlas_risk numbers' sign.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH = os.path.join(ROOT, "research", "handoff", "2026-11-20", "atlasedge", "account_b.patch")
RESULTS = []


def check(name, ok, info=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not ok else ""), flush=True)
    return bool(ok)


def patched_root():
    """-> (root to import engine from, tmp dir to clean or None)."""
    src = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    if "FUNDED_ON" in src:
        return ROOT, None
    tmp = tempfile.mkdtemp(prefix="atlas_sw_")
    shutil.copytree(os.path.join(ROOT, "engine"), os.path.join(tmp, "engine"), ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("live_model.json", "live_model_lit.json", "second_model.json"):
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
    r = subprocess.run(["git", "apply", "--unsafe-paths", PATCH], cwd=tmp, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"the patch does not apply to today's engine/account_b.py: {r.stderr[-400:]}")
    return tmp, tmp


# ================================================================================================ inner (patched engine)
def inner():
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    sys.path.insert(0, os.environ["ATLAS_SW_ROOT"])           # the patched engine wins
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    from engine import account_b as AB
    from engine import multi_account as MA
    from engine import second
    from engine import sizing as SZ
    from tests.test_account_b_funded import FakeBot, funded_block, eval_block, ts
    from engine import live
    assert hasattr(AB, "FUNDED_ON"), "not the patched engine"
    sc = second.load_cfg()
    base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    R25 = MA.rules_of({"preset": "mffu_builder_25k"})
    P25 = MA.PRESETS["mffu_builder_25k"]["sizing"]["funded"]
    A25 = {"mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20}

    def want(risk, tgt, st, pct=None):
        cfg = P25 if pct is None else {**P25, "pct": pct}
        q = SZ.funded_qty({"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0}, dict(st), cfg, acct=A25)
        return int(AB.dll_guard({"qty": min(20, q), "reasons": []}, risk, R25, st)["qty"])

    def st_of(room, cum=0.0, streak=0):
        return {"room": room, "cum": cum, "locked": False, "balance": 24000.0 + room - cum, "floor": 24000.0, "loss_streak": streak}

    grid = [(room, risk, tgt, cum) for room in (60, 150, 300, 500, 887, 1200, 2000, 3500) for risk in (8.0, 20.0, 35.0, 60.0)
            for tgt in (None, 40.0, 120.0) for cum in (0.0, -250.0)]

    # ---- a. OFF by default
    print("a. OFF by default", flush=True)
    # 2026-11-20 lead: FUNDED_ON flipped ON after the owner's YES (both cards; skeptic code review skeptic-live-patches-2026-11-20.md).
    # "OFF = today" is now proved with an explicit null in the block (the per-account off switch), not with the repo default.
    check("a. FUNDED_ON ships ON after the owner's YES: room 40% + 1 micro after 2 losses", AB.FUNDED_ON == {"funded_room_pct": 0.4, "streak_shrink": 2}, AB.FUNDED_ON)
    sd = AB.normalize(funded_block(), sc)
    check("a. a funded 25K block without the keys gets the repo defaults (0.4, 2), no problem", sd and not sd.get("problem")
          and sd.get("funded_room_pct") == 0.4 and sd.get("streak_shrink") == 2, sd and (sd.get("problem"), sd.get("funded_room_pct"), sd.get("streak_shrink")))
    s50 = AB.normalize({**funded_block(), "plan": "builder50k"}, sc)
    check("a. a Builder 50K block (e.g. a funded combo 50K) never gets the repo defaults (no card covers it)", s50 is not None
          and "funded_room_pct" not in s50 and "streak_shrink" not in s50, s50 and (s50.get("funded_room_pct"), s50.get("streak_shrink")))
    s0 = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), sc)   # OFF for this account = today's sizing
    check("a. a funded block with null keys: neither key in the spec, no problem", s0 and not s0.get("problem")
          and "funded_room_pct" not in s0 and "streak_shrink" not in s0, s0 and s0.get("problem"))
    bad = [(room, risk, tgt, cum) for room, risk, tgt, cum in grid
           if int(AB.funded_qty(s0, {"risk_pts": risk, "tgt_pts": tgt}, st_of(room, cum, streak=9), base=base)["qty"]) != want(risk, tgt, st_of(room, cum))]
    check(f"a. OFF sizes exactly like today (60% preset + soft daily loss) on {len(grid)} states, even at a 9-loss streak", not bad, bad[:5])
    for k, v in (("funded_room_pct", 0.05), ("funded_room_pct", 0.9), ("funded_room_pct", "x"), ("streak_shrink", 0), ("streak_shrink", 2.5), ("streak_shrink", 11)):
        sp = AB.normalize(funded_block(**{k: v}), sc)
        check(f"a. bad {k}={v!r} -> a problem (not traded)", bool(sp.get("problem")) and k in sp["problem"], sp.get("problem"))
    sn = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), sc)
    check("a. null in the block = OFF", "funded_room_pct" not in sn and "streak_shrink" not in sn and not sn.get("problem"))
    old = dict(AB.FUNDED_ON)
    try:
        AB.FUNDED_ON.update(funded_room_pct=0.4, streak_shrink=2)
        sf = AB.normalize(funded_block(), sc)
        so = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), sc)
        check("a. the lead's one-line switch (FUNDED_ON) turns both on; a null in the block still turns them off for that account",
              sf.get("funded_room_pct") == 0.4 and sf.get("streak_shrink") == 2 and "funded_room_pct" not in so and "streak_shrink" not in so, (sf.get("funded_room_pct"), sf.get("streak_shrink")))
    finally:
        AB.FUNDED_ON.clear()
        AB.FUNDED_ON.update(old)
    se = AB.normalize(eval_block(streak_shrink=2, funded_room_pct=0.4), sc)
    st_e = {"room": 900.0, "cum": 0.0, "locked": False, "balance": 25000.0, "floor": 24100.0, "n_today": 0, "loss_streak": 9,
            "session": 3, "profit": 0.0, "target": 1500.0}
    q_e1 = AB.qty(se, {"risk_pts": 20.0, "tgt_pts": 60.0}, dict(st_e), base=base)
    q_e0 = AB.qty(AB.normalize(eval_block(), sc), {"risk_pts": 20.0, "tgt_pts": 60.0}, dict(st_e), base=base)
    check("a. the eval stage never uses them (same size with or without the keys)", q_e1.get("qty") == q_e0.get("qty"), (q_e1.get("qty"), q_e0.get("qty")))

    # ---- b. the streak counter
    print("b. the streak counter", flush=True)
    F0 = "2026-11-09"
    c = lambda d, h, p, e=None: [d, ts(d, h), float(p), int(e if e is not None else ts(d, h) - 600)]  # noqa: E731
    ls = AB.loss_streak
    check("b. [win, loss, loss] -> 2", ls([c("2026-11-10", 9, 120), c("2026-11-11", 9, -80), c("2026-11-12", 9, -95)], F0) == 2)
    check("b. a winner resets: [loss, loss, win] -> 0", ls([c("2026-11-10", 9, -80), c("2026-11-11", 9, -95), c("2026-11-12", 9, 40)], F0) == 0)
    check("b. a scratch (>= $0) resets: [loss, loss, $0] -> 0", ls([c("2026-11-10", 9, -80), c("2026-11-11", 9, -95), c("2026-11-12", 9, 0.0)], F0) == 0)
    check("b. ordered by exit time, not list order", ls([c("2026-11-12", 9, -95), c("2026-11-10", 9, 50), c("2026-11-11", 9, -80)], F0) == 2)
    check("b. closes before the funded start never count (the eval's losses)",
          ls([c("2026-11-05", 9, -80), c("2026-11-06", 9, -80), c("2026-11-10", 9, -40)], F0) == 1)
    check("b. two losses the same day count as two", ls([c("2026-11-12", 4, -80), c("2026-11-12", 10, -60)], F0) == 2)
    tmp = tempfile.mkdtemp(prefix="atlas_sw_state_")
    try:
        spec = AB.normalize(funded_block(streak_shrink=2), sc)
        now = ts("2026-11-13", 8)
        p = os.path.join(tmp, "acctb_state.json")
        B = AB.AccountB(FakeBot(now), spec, state_path=p)
        B.adapter = live.PaperAdapter({})
        B.closes = [c("2026-11-10", 9, 150), c("2026-11-11", 9, -110), c("2026-11-12", 9, -90)]
        B.save()
        B2 = AB.AccountB(FakeBot(now), spec, state_path=p)
        B2._load()
        st2 = B2._funded_state("2026-11-13")
        check("b. survives a restart: a fresh AccountB on the saved state file reads streak 2", st2 and st2.get("loss_streak") == 2, st2 and st2.get("loss_streak"))
        q2 = int(B2.size({"risk_pts": 20.0, "tgt_pts": 60.0}, dict(st2))["qty"])
        check("b. ... and sizes 1 micro after the restart", q2 == 1, q2)
        other = AB.normalize({**funded_block(streak_shrink=2), "account": "MFFUSFBLD25KOTHER"}, sc)
        B3 = AB.AccountB(FakeBot(now), other, state_path=p)
        B3._load()
        st3 = B3._funded_state("2026-11-13")
        check("b. only this account's own closes: another account Name never reads that file (streak 0)", B3.closes == [] and st3.get("loss_streak") == 0, (len(B3.closes), st3.get("loss_streak")))
        s_off = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), sc)
        B4 = AB.AccountB(FakeBot(now), s_off, state_path=p)
        B4._load()
        check("b. switch OFF: the funded state has no loss_streak key (today's state, unchanged)", "loss_streak" not in (B4._funded_state("2026-11-13") or {}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- c. the streak size
    print("c. the streak size", flush=True)
    s2 = AB.normalize(funded_block(streak_shrink=2, funded_room_pct=None), sc)   # the streak alone vs today's 60%
    errs, n_shrunk = [], 0
    for room, risk, tgt, cum in grid:
        q_today = want(risk, tgt, st_of(room, cum))
        for k in (0, 1, 2, 3, 6):
            q = int(AB.funded_qty(s2, {"risk_pts": risk, "tgt_pts": tgt}, st_of(room, cum, streak=k), base=base)["qty"])
            exp = q_today if k < 2 else min(q_today, 1)
            if q != exp or q > q_today or (q_today >= 1 and q < 1):
                errs.append((room, risk, tgt, cum, k, q_today, q))
            n_shrunk += int(k >= 2 and q_today > 1)
    check(f"c. on {len(grid) * 5} states: streak < 2 = today's size; streak >= 2 = 1 micro when today's is 2+, 1 stays 1, 0 stays 0"
          f" ({n_shrunk} shrunk)", not errs and n_shrunk > 0, errs[:5])
    r = AB.funded_qty(s2, {"risk_pts": 20.0, "tgt_pts": 60.0}, st_of(887, 0.0, streak=2), base=base)
    check("c. the reason says why (phone / log)", any("loss streak" in x for x in r.get("reasons") or []), r.get("reasons"))
    lost = AB.funded_qty(s2, {"risk_pts": 20.0, "tgt_pts": 60.0}, st_of(-5.0, 0.0, streak=4), base=base)
    check("c. a lost account stays 0 (the streak never adds a micro)", int(lost["qty"]) == 0)

    # ---- d. room 40% on a replay of the research engine
    print("d. room 40% on a replay (tools/atlas_risk PGF3)", flush=True)
    from tools import atlas_edge as E
    from tools import atlas_revive as RV
    AR, AM = E.AR(), E.AM()
    s40 = AB.normalize(funded_block(funded_room_pct=0.4), sc)
    check("d. spec funded_room_pct 0.4 -> the funded preset's share 0.4 (25K preset: 0.6 today)",
          AB.funded_cfg(s40, base)["funded"]["pct"] == 0.4 and AB.funded_cfg(s0, base)["funded"]["pct"] == P25["pct"] == 0.6,
          (AB.funded_cfg(s40, base)["funded"].get("pct"), P25.get("pct")))
    S = AM.sessions()
    PG = AR.pgf3()
    rows = []

    class Rec(PG):
        def qty(self, t, st):
            q = super().qty(t, st)
            rows.append((t, dict(st), q, self.dead))
            return q
    out = {}
    for n in (1, 10):
        T = E.to_T(E.opt_units("base", n)[0])
        BY = RV.by_session(T, S)
        for lab, a, z in (("2026", "2026-01-01", "2026-10-16"), ("2021-25", "2021-11-01", "2025-12-31")):
            seq = [i for i, d in enumerate(S) if a <= d <= z]
            for start in ("fresh", "today"):
                rows.clear()
                f = Rec({"stuck": 0.0, "pct": 0.4})
                if start == "today":
                    AM.at_today(f)
                owner = 0.0
                for si in seq:
                    ev, x = f.step(BY[si])
                    if ev in ("paid", "grad"):
                        owner += x
                    if ev in ("lost", "grad") or f.dead:
                        break
                mism, n_q = [], 0
                for t, st, q_res, dead in rows:
                    if dead:
                        continue
                    risk = float(t["risk"])
                    tgt = t["tgt"] if t.get("tgt") else 2.0 * risk
                    exp = int(AB.dll_guard({"qty": int(q_res), "reasons": []}, risk, R25, st)["qty"])
                    got = int(AB.funded_qty(s40, {"risk_pts": risk, "tgt_pts": tgt}, st, base=base)["qty"])
                    n_q += 1
                    if got != exp:
                        mism.append((t["day"], risk, round(st["room"]), q_res, exp, got))
                out[f"{n}t {lab} {start}"] = {"trades_sized": n_q, "mismatch": len(mism), "owner_usd": round(owner), "end": f.state}
                check(f"d. {n}t {lab} from {start}: account_b funded_room_pct 0.4 sizes every research trade exactly as the research pct 0.4 "
                      f"(+ the same soft daily loss) ({n_q} trades)", n_q > 20 and not mism, mism[:4])
    print("   replay paths (research engine, room 40%):", json.dumps(out), flush=True)
    try:
        ar = json.load(open(os.path.join(ROOT, "research", "second", "atlas_risk.json"), encoding="utf-8"))
        o1 = ar["funded"]["O1_room40"]["10t"]
        check("d. the stored research numbers this card quotes are the room-40% rows (atlas_risk.json O1 at 10 ticks: $527 / $393 a month, lost 11.0 / 14.0%)",
              (o1["H1"]["usd_m"], o1["H2"]["usd_m"], o1["H1"]["lost_6m"], o1["H2"]["lost_6m"]) == (527, 393, 11.0, 14.0),
              {k: (o1[k]["usd_m"], o1[k]["lost_6m"]) for k in ("H1", "H2")})
    except Exception as e:  # noqa: BLE001
        check("d. research/second/atlas_risk.json readable", False, f"{e.__class__.__name__}: {e}")


def main():
    if os.environ.get("ATLAS_SW_ROOT"):
        inner()
        n, ok = len(RESULTS), sum(RESULTS)
        print(f"atlas funded switches: {ok}/{n} {'ALL PASS' if ok == n else 'FAILED'}")
        return 0 if ok == n else 1
    root, tmp = patched_root()
    try:
        env = {**os.environ, "ATLAS_SW_ROOT": root, "PYTHONPATH": os.pathsep.join([root, ROOT])}
        print(f"engine: {'the repo (patch applied)' if tmp is None else 'temp copy + ' + os.path.relpath(PATCH, ROOT)}", flush=True)
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__)], env=env, cwd=ROOT)
        return r.returncode
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
