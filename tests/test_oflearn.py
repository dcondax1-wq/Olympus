"""day-oflearn 2026-11-26: the order-flow pipeline proven end to end on SYNTHETIC ticks with known planted effects, before real
tick days arrive (research/orderflow/DESIGN3.md). Simulator (research/orderflow/of_sim.py) -> engine/ofsum summaries (+ the new
sac / imb1 / ofi columns) -> battery (OF1, OF4) -> v3 features -> of_forward (idea mill `of` grammar, 36 families) -> of_learn
(log, learn, placebo, words) -> research/learn journal lines -> the Brain's Order Flow room. And the NULL world (nothing planted)
must give no lead. No data/ written, no network, nothing that can trade.
    python -X utf8 -m tests.test_oflearn
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import contextlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OF = os.path.join(ROOT, "research", "orderflow")
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "server")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def mod(name):
    sp = importlib.util.spec_from_file_location(f"t_{name}", os.path.join(OF, name + ".py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def main():
    import pandas as pd
    from engine import ofsum, brain_feed
    S, V3, LRN, FWD = mod("of_sim"), mod("of_v3"), mod("of_learn"), mod("of_forward")
    B = FWD.B
    # ---- units
    check("of_v3 selftest (finite, sign symmetry, no look-ahead)", quiet(V3.selftest))
    check("ofsum selftest still OK (sums, footprint, sides)", quiet(ofsum.selftest))
    bi = np.array([0] * 30 + [1] * 30); sd = np.r_[np.ones(30), np.tile([1, -1], 15)].astype(int)
    sac, runs = ofsum.sign_persistence(bi, sd, 2)
    check("sign_persistence: one-sided bar = '' (no variance), alternating bar = -1", sac[0] == "" and abs(sac[1] + 1) < 1e-9 and runs[1] == 1.0, (sac, runs))
    check("wilson 7 of 9 at 90%", LRN.wilson(7, 9) == (0.504, 0.924), LRN.wilson(7, 9))
    check("BH: [0.001, 0.04, 0.5] at q 0.10 -> first two", list(LRN.bh([0.001, 0.04, 0.5])) == [True, True, False])
    # ---- planted world
    W = S.world(64, "planted", depth_last=42, seed=21)
    days = W["days"]
    rows = [W["R"][d]["meta"]["rows"] for d in days]
    lit = W["lit"]
    kinds = S.describe(W)
    check("simulator: 64 days of ~80k trades, quote-rule sides, 3 sweeps a day", min(rows) >= 50_000 and len(lit) >= 120
          and W["R"][days[0]]["meta"]["sides"]["quote_rule"] > 0.99, (min(rows), len(lit)))
    wa, wt = kinds["absorbed"]["won"] / kinds["absorbed"]["n"], kinds["thin"]["won"] / kinds["thin"]["n"]
    check("planted truth: absorbed sweeps win more than thin ones", wa > wt + 0.25, kinds)
    b0 = W["R"][days[0]]["bars"]
    check("new bars column sac present and mostly positive (P_SAME 0.70 -> ~0.4)", "sac" in b0 and 0.2 < pd.to_numeric(b0.sac, errors="coerce").median() < 0.6,
          pd.to_numeric(b0.sac, errors="coerce").median())
    dep = W["R"][days[-1]]["depth"]
    check("depth days carry imb1 / ofi / dep1", dep is not None and {"imb1", "ofi", "dep1"} <= set(dep.columns) and dep.ofi.abs().sum() > 0)
    # ---- battery (OF1 / OF4 on the real footprint)
    with tempfile.TemporaryDirectory() as td:
        out = quiet(B.run, raw=W["R"], lit=(lit, "2099-01-01"), atlas=(W["atlas"], "2099-01-01"), write=False, out_dir=td)
    o1 = out.get("OF1 LIT only when absorbed", {})
    check("battery runs on the simulated days (look 2 at 64 days)", out.get("state") == "ran" and out.get("look") == 2, out.get("state"))
    check("battery OF1 finds the planted absorption (kept > all in both halves, PASS)", str(o1.get("verdict", "")).startswith("PASS")
          and o1["Discovery"]["gain$"] > 0 and o1["Confirm"]["gain$"] > 0, {k: o1.get(k) for k in ("Discovery", "Confirm", "verdict", "skip_placebo_p")})
    # ---- learner
    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "journal.json")
        json.dump([], open(jp, "w"))
        r1 = LRN.run(R={d: W["R"][d] for d in days[:6]}, lit=lit, atlas=W["atlas"], out_dir=td, journal=jp, today="2026-11-26", say=lambda *_: None)
        r2 = LRN.run(R=W["R"], lit=lit, atlas=W["atlas"], out_dir=td, journal=jp, today="2026-11-27", say=lambda *_: None)
        r3 = LRN.run(R=W["R"], lit=lit, atlas=W["atlas"], out_dir=td, journal=jp, today="2026-11-28", say=lambda *_: None)
        J = json.load(open(jp))
        sig = [json.loads(x) for x in open(os.path.join(td, LRN.SIGNALS))]
        st = json.load(open(os.path.join(td, LRN.STATE)))
        check("learner night 1 (6 days): 'too few to act' wording", "too few to act" in (r1["line"] or ""), r1["line"])
        check("learner logs each signal once (append-only, nights 2-3 add nothing twice)", r3["added"] == 0 and
              len(sig) == len({(s["bot"], s["t"]) for s in sig}) == r2["signals"]["LIT"] + r2["signals"]["ATLAS"], (r3["added"], len(sig)))
        ab = r2["bots"]["LIT"]["absorbed"]
        check("learner: LIT 'absorbed' = LEAD on the planted world", ab["status"] == "lead", ab)
        check("learner: placebo leads < real leads", r2["placebo_leads"]["LIT"] < r2["real_leads"]["LIT"], (r2["real_leads"], r2["placebo_leads"]))
        check("learner medians frozen on night 2 and not moved on night 3", st["medians"]["LIT"]["since"] == "2026-11-27")
        keys = {e["key"]: e for e in J}
        e = keys.get("of|LIT|absorbed")
        check("journal: of|LIT|absorbed line, lens 'order flow', confirmed after the 'too few' night (2 dated entries)",
              e and e["lens"] == "order flow" and e["status"] == "confirmed" and sum(1 for x in J if x["key"] == "of|LIT|absorbed") == 2, e)
        check("journal lines are plain words with counts", e and "OF said absorbed at the sweep:" in e["noticed"] and " of " in e["noticed"], e and e["noticed"])
        # brain room
        os.makedirs(os.path.join(td, "logs", "orderflow"))
        json.dump(st, open(os.path.join(td, "logs", "orderflow", LRN.STATE), "w"))
        ob = brain_feed.of_bot(td, {})
        txt = json.dumps(ob)
        check("Brain Order Flow room shows the learner line", "learner:" in txt and "absorbed" in txt, ob)
    # ---- of_forward (idea mill `of` grammar) with v3 families, provisional at 64 days
    with tempfile.TemporaryDirectory() as td:
        FWD.SPLIT, FWD.TRIALS = os.path.join(td, "s.json"), os.path.join(td, "t.jsonl")
        fo = FWD.run(W["R"], lit=lit, atlas=W["atlas"], say=lambda *_: None, write=False)
    fams = {f["family"] for f in fo.get("families", [])}
    check("of_forward: provisional, v3 families scored (I / J / K), L scored with >= 40 depth days", fo["state"] == "provisional"
          and {"LIT|I", "LIT|J", "LIT|K", "LIT|L"} <= fams | {f["family"] for f in fo.get("families", [])} and fo["depth_days"] >= 40,
          (fo["state"], sorted(fams)[:40], fo.get("depth_days")))
    passA = {f["family"] for f in fo["families"] if f["stageA"]}
    check("of_forward: the planted absorption passes the family FDR (gate A) in a footprint / level / stop-run family of LIT",
          passA & {"LIT|B", "LIT|F", "LIT|K", "LIT|I"}, sorted(passA))
    c = fo["counts"]
    check("of_forward: real gate A/B counts > placebo (placebo ~0); C-E stay closed at 38 Discovery days (DSR >= 0.95 is strict by design)",
          c["real"]["A"] > c["placebo"]["A"] and c["real"]["B"] > c["placebo"]["B"] and c["real"]["E"] == 0, c)
    # ---- null world
    N = S.world(64, "null", seed=22)
    with tempfile.TemporaryDirectory() as td:
        rn = LRN.run(R=N["R"], lit=N["lit"], atlas=N["atlas"], out_dir=td, journal=None, today="2026-11-27", say=lambda *_: None)
    abn = rn["bots"]["LIT"]["absorbed"]
    check("null world: 'absorbed' is NOT a lead", abn["status"] != "lead", abn)
    check("null world: at most 1 lead per bot in total (chance)", all(v <= 1 for v in rn["real_leads"].values()), rn["real_leads"])
    # ---- PC nightly hook (engine/tickrec.autopilot -> oflearn_kick)
    import datetime as dt
    from engine import tickrec
    from zoneinfo import ZoneInfo
    et = dt.datetime(2026, 11, 26, 18, 30, tzinfo=ZoneInfo("America/New_York"))
    os.environ["LE_OFLEARN"] = "0"
    check("PC hook: LE_OFLEARN=0 = off", tickrec.oflearn_kick(et).get("off") is True)
    os.environ.pop("LE_OFLEARN")
    check("PC hook: never within 30 min of 02:00 ET", "skipped" in tickrec.oflearn_kick(et.replace(hour=1, minute=40) + dt.timedelta(days=1)))
    with tempfile.TemporaryDirectory() as td:
        r = tickrec.oflearn_kick(et, root=td)
        check("PC hook: no summaries yet -> skipped, nothing written, no error", r.get("skipped") and not os.path.exists(os.path.join(td, "logs", "orderflow")), r)
        os.makedirs(os.path.join(td, "logs", "orderflow"))
        json.dump({"updated": "2026-11-26"}, open(os.path.join(td, "logs", "orderflow", LRN.STATE), "w"))
        check("PC hook: once a day", tickrec.oflearn_kick(et, root=td).get("skipped") == "already ran today")
    # ---- safety
    import ast
    for f in ("of_v3.py", "of_learn.py", "of_sim.py"):
        t = ast.parse(open(os.path.join(OF, f), encoding="utf-8").read())
        imp = {a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names} | \
              {n.module or "" for n in ast.walk(t) if isinstance(n, ast.ImportFrom)}
        check(f"{f} imports nothing that can trade", not any(i.startswith(b) for i in imp for b in BANNED), imp)
    src = open(os.path.join(OF, "of_learn.py"), encoding="utf-8").read()
    check("of_learn never writes a live / model file", not any(x in src for x in ("live_model", "data/live_state", "second_model")))
    ok = all(RES)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
