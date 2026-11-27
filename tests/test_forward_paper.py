"""Forward-paper harness (tools/forward_paper.py, research/forward/DESIGN.md). Offline: fake rules, temp files, no data.

  a. the bars: promote needs n >= 20, z >= -1 and sum > 0; demote at n >= 10 and z <= -2, or sum <= -8 R; else watching
  b. a run with fake rules: band from the backtest call, forward from FWD_FROM, events kept, a failing rule = status error
     (keeps its old numbers) while the others still score; bands reused unless the rule changed or --bands
  c. the journal: one line per rule per ISO week; a second run the same week replaces, never duplicates
  d. never a live file: live_model*.json hashes equal before / after; dry run writes nothing
  f. the S1 forward hold-out (s1_forward): rows, calibrated R, the re-judge date + checks, the journal line
  e. the seed rules: the 7 DESIGN.md ids are registered with kind / bot / source; the idea mill adapter reads paper-gate ideas
    python -X utf8 -m tests.test_forward_paper
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import forward_paper as FP  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        FAILS.append(name)


def fake_rule(bt, fw, kind="standalone"):
    def fn(a, z):
        src = bt if z <= FP.BT_TO else fw
        return [FP.ev(d, i, v) for i, (d, v) in enumerate(src) if a <= d <= z]
    return {"kind": kind, "bot": "-", "fn": fn, "source": "test", "desc": "fake " + kind, "code": []}


def main():
    band = {"mu": 0.2, "sd": 1.0}
    E = lambda vals: [{"v": v} for v in vals]  # noqa: E731
    check("a. 19 good trades: still watching (n < 20)", FP.score(E([0.3] * 19), band)["status"] == "watching")
    check("a. 20 trades inside the band, sum > 0: promote", FP.score(E([0.3] * 20), band)["status"] == "promote")
    s = FP.score(E([-0.45] * 10), band)
    check("a. 10 trades far below the band (z <= -2): demoted", s["status"] == "demoted" and s["z"] <= -2, s)
    check("a. sum <= -8R at any n: demoted", FP.score(E([-4.1, -4.0]), band)["status"] == "demoted")
    check("a. 20 trades at -0.05 (z ~ -1.1): watching, not promoted", FP.score(E([-0.05] * 20), band)["status"] == "watching")
    check("a. no forward trades: watching, n 0", FP.score([], band) == {"n": 0, "mean": None, "sum": 0, "z": None, "status": "watching"})

    tmp = tempfile.mkdtemp()
    FP.STATE, FP.BANDS, FP.JOURNAL = (os.path.join(tmp, x) for x in ("forward.json", "bands.json", "journal.jsonl"))
    calls = {"n": 0}
    good = fake_rule([("2024-01-02", 1.0), ("2025-03-04", -0.5), ("2026-11-20", 0.4)], [("2026-11-23", 0.7), ("2026-11-24", -0.2)])
    base_fn = good["fn"]

    def counted(a, z):
        calls["n"] += 1
        return base_fn(a, z)
    good["fn"] = counted

    def boom(a, z):
        raise RuntimeError("no numba")
    rules = {"good": good, "bad": {"kind": "skip", "bot": "ATLAS", "fn": boom, "source": "t", "desc": "x", "code": []}}
    days = (["2026-11-23", "2026-11-24"], "2026-11-24")
    before = FP._hash(FP.PROTECTED)
    d = FP.run(rules=rules, today=days, say=lambda *_: None)
    g = d["rules"]["good"]
    check("b. band from the backtest events (n 3, mu 0.3), forward 2 events after FWD_FROM", g["band"]["n_bt"] == 3 and abs(g["band"]["mu"] - 0.3) < 1e-9
          and g["n"] == 2 and g["sum"] == 0.5 and g["days_in"] == 2 and len(g["events"]) == 2, g)
    check("b. a failing rule shows status error, the others still score", d["rules"]["bad"]["status"] == "error"
          and "no numba" in d["rules"]["bad"]["error"] and g["status"] == "watching")
    n1 = calls["n"]
    FP.run(rules=rules, today=days, say=lambda *_: None)
    check("b. bands reused on the next night (only the forward call runs)", calls["n"] == n1 + 1, (n1, calls["n"]))
    FP.run(rules=rules, today=days, say=lambda *_: None, bands=True)
    check("b. --bands recomputes", calls["n"] == n1 + 3, calls["n"])
    J = [json.loads(x) for x in open(FP.JOURNAL, encoding="utf-8") if x.strip()]
    check("c. journal: one line per rule for the week (3 runs, 2 rules -> 2 lines)", len(J) == 2 and {j["rule"] for j in J} == {"good", "bad"}
          and J[0]["week"] == "2026-W48", J)
    check("d. live model files untouched", FP._hash(FP.PROTECTED) == before and "ALARM" not in d)
    mt = os.path.getmtime(FP.STATE)
    FP.run(rules=rules, today=days, say=lambda *_: None, dry=True)
    check("d. dry run writes nothing", os.path.getmtime(FP.STATE) == mt)
    ids = {"ict_ote_dol", "ict_mmbm_week", "atlas_skip_news", "atlas_half_off_sb", "blitz_v1_noise", "lit_second_after_stop", "lit_x15_extreme",
           "atlas_s1_gate"}     # + big-regime2026 2026-11-26: the S1 forward hold-out (research/regime2026/DESIGN_forward.md)
    check("e. the 7 seed rules of DESIGN.md + atlas_s1_gate are registered", ids == set(FP.RULES) and all(
        {"kind", "bot", "fn", "source", "desc", "code"} <= set(r) for r in FP.RULES.values()), set(FP.RULES))
    check("e. promote / demote bars = DESIGN.md", (FP.PROMOTE_N, FP.PROMOTE_Z, FP.DEMOTE_N, FP.DEMOTE_Z, FP.DEMOTE_SUM) == (20, -1.0, 10, -2.0, -8.0)
          and FP.FWD_FROM == "2026-11-23")
    im = FP.ideamill_rules()
    check("e. idea mill adapter: only paper-gate ideas become rules (ids prefixed ideamill:)", all(k.startswith("ideamill:") for k in im), list(im)[:3])
    part_f()
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    return 1 if FAILS else 0


def part_f():
    """f. the S1 forward hold-out (research/regime2026/DESIGN_forward.md): rows per session, calibrated R judged, re-judge only
    at >= 60 sessions AND on / after 2027-02-26, the four checks, the Brain journal entry (temp files, fake sources)."""
    from tools import livegap as G
    from engine import market_learn as ML
    old = (FP.s1_series, FP.asia_paper, FP.pc_atlas_real, G.atlas_twin, ML.JOURNAL, FP._C.copy())
    with tempfile.TemporaryDirectory() as td:
        try:
            import datetime as _dt
            days = [(_dt.date(2026, 11, 23) + _dt.timedelta(days=i)).isoformat() for i in range(0, 140)]
            days = [d for d in days if _dt.date.fromisoformat(d).weekday() < 5][:70]
            FP.s1_series = lambda: {d: (i % 2 == 0) for i, d in enumerate(days)}
            FP.asia_paper = lambda since: []
            FP.pc_atlas_real = lambda: {days[0]: -50.0}
            tw = [{"day": d, "entry_t": 1 + i, "exit_t": 2 + i, "dir": 1, "exit": "TARGET" if i % 2 == 0 else "STOP",
                   "r": 2.0 if i % 2 == 0 else -1.0, "risk": 40.0, "one_position_skip": False} for i, d in enumerate(days)]
            G.atlas_twin = lambda since="": tw
            ML.JOURNAL = os.path.join(td, "journal.json")
            out = os.path.join(td, "s1.json")
            d1 = FP.s1_forward(days[:30], path=out, say=lambda *_: None)
            check("f. 30 sessions: watching, progress n / 60, one row a day", d1["verdict"] == "watching" and d1["progress"] == "30 / 60 sessions"
                  and len(d1["rows"]) == 30 and d1["rows"][0]["atlas_real_usd"] == -50.0, d1["progress"])
            r = d1["rows"][1]["atlas_twin_r"][0]
            check("f. judged R = calibrated fills (12 in, 2 out on a stop, $1.90)", abs(r - (-1.0 - (3.0 + 0.5 + 0.95) / 40.0)) < 1e-4, r)
            d2 = FP.s1_forward(days, path=out, say=lambda *_: None)
            due = days[-1] >= FP.S1_REJUDGE
            check("f. 70 sessions: due only on / after 2027-02-26, then the 4 checks decide",
                  d2["due"] == due and (d2["verdict"] == ("ADOPT-CANDIDATE (owner card)" if all(d2["checks"].values()) else "REJECTED") if due
                                        else d2["verdict"] == "watching"), (d2["due"], d2["verdict"], d2["checks"]))
            check("f. OFF days hold the losers here -> every check passes", all(d2["checks"].values()), d2["checks"])
            J = json.load(open(ML.JOURNAL, encoding="utf-8"))
            check("f. the Brain journal has the trial line", any(e.get("key") == "regime2026|s1_forward" for e in J), len(J))
        finally:
            FP.s1_series, FP.asia_paper, FP.pc_atlas_real, G.atlas_twin, ML.JOURNAL = old[:5]
            FP._C.clear(); FP._C.update(old[5])


if __name__ == "__main__":
    sys.exit(main())
