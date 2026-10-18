"""Unit tests of the LIT learning loop (engine/lit_learn.py): cause codes, shrinkage, guardrails, apply / revert, the
journal (append-only, merge by source) and the sizing hook (engine/sizing.py lit_qty).

    python -X utf8 -m tests.test_lit_learn
No market data needed (synthetic journal records); about 10 s.
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit_learn as LL  # noqa: E402
from engine import sizing  # noqa: E402

F_BASE = {"idm_age": 4.0, "n_swept": 2.0, "major": 1.0, "obst_r": 3.0, "news_next": 600.0, "mod": 200.0, "vix": 17.0,
          "es_swept": 1.0, "h4_draw": 1.0, "stop_pts": 30.0}


def rec(day, r, f=None, exit_="STOP", risk=30.0, post=None, source="backtest", hour=3):
    """A synthetic journal record: r = R after costs per unit; one micro's P&L = r x risk x $2."""
    t0 = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hour, 0), LL.ET).timestamp())
    ff = {**F_BASE, **(f or {})}
    pnl_pm = r * risk * LL.PV
    x = {"v": 1, "key": f"{day}|{t0}|1", "source": source, "day": day, "entry_t": t0, "exit_t": t0 + 3600, "dir": 1,
         "exit": exit_, "risk_pts": risk, "r": r, "pnl_pm": pnl_pm, "wk_mult": 1.0, "q_pre": LL.q_pre_of(risk),
         "mae": 1.0 if exit_ == "STOP" else 0.2, "f": ff, "buckets": LL.buckets(ff), "post": post or {}}
    x["qty"] = x["q_pre"]
    x["pnl"] = pnl_pm * x["q_pre"]
    x["cause"], x["tags"] = LL.cause_codes(x)
    return x


def weekdays(a, n):
    d = dt.date.fromisoformat(a)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


# ------------------------------------------------------------------------------------------------ cause codes
def test_causes():
    w = rec("2026-03-02", 3.0, exit_="TARGET")
    assert w["cause"] is None and w["tags"] == []
    s = rec("2026-03-02", -1.02)
    assert s["cause"] == "not_turning_point" and s["tags"] == ["not_turning_point"], s["tags"]
    s = rec("2026-03-02", -1.02, f={"es_swept": 0.0, "mod": 330.0, "idm_age": 14.0, "stop_pts": 55.0})
    assert s["cause"] == "es_no_confirm" and s["tags"] == ["es_no_confirm", "stale_trap", "late_london", "wide_stop",
                                                           "not_turning_point"], s["tags"]
    s = rec("2026-03-02", -1.02, f={"es_swept": 0.0}, post={"opp_ext_in": True})
    assert s["cause"] == "opp_extreme_in" and "es_no_confirm" in s["tags"]
    s = rec("2026-03-02", -1.02, f={"h4_draw": -1.0})
    assert s["cause"] == "against_4h_draw"
    s = rec("2026-03-02", -1.02, f={"es_swept": 0.0}, post={"target_after_stop": True})
    assert s["cause"] == "wick_then_target" and "es_no_confirm" in s["tags"]
    s = rec("2026-03-02", -1.02, post={"news_in_trade": True, "target_after_stop": True})
    assert s["cause"] == "news_spike"
    s = rec("2026-03-02", -1.02, post={"opp_ext_in": True})
    assert s["cause"] == "opp_extreme_in"
    b = rec("2026-03-02", -0.02, exit_="BE", f={"es_swept": 0.0})
    assert b["cause"] == "be_scratch" and "es_no_confirm" in b["tags"] and "not_turning_point" not in b["tags"]
    e = rec("2026-03-02", -0.3, exit_="EOD")
    assert e["cause"] == "eod_fade"
    e = rec("2026-03-02", 0.6, exit_="EOD")
    assert e["cause"] is None
    # a target after a BE exit is not a "stopped by a wick" loss
    b = rec("2026-03-02", -0.02, exit_="BE", post={"target_after_stop": True})
    assert "wick_then_target" not in b["tags"]


def test_buckets_grade():
    bk = LL.buckets(F_BASE)
    assert bk == {"trap": "fresh", "levels": "multi", "session": "lon_early", "vix": "mid", "grade": "A", "es": "confirm",
                  "h4": "with"}, bk
    g = LL.buckets({**F_BASE, "idm_age": 9.0, "n_swept": 1.0, "major": 0.0, "obst_r": 1.0, "mod": 600.0, "vix": 25.0,
                    "es_swept": None, "h4_draw": 0.0})
    assert g == {"trap": "stale", "levels": "single", "session": "ny", "vix": "high", "grade": "C", "es": None, "h4": "none"}, g
    assert LL.trader_grade({**F_BASE, "obst_r": 1.0}) == "B"
    assert LL.buckets({}) == {k: None for k in LL.FAMILIES}
    # the grade equals the research's (tools/lit_select_rules.trader_grade) on random features
    try:
        from tools.lit_select_rules import trader_grade as tg
    except Exception:
        tg = None
    if tg is not None:
        rng = random.Random(1)
        for _ in range(500):
            f = {"idm_age": rng.choice([2, 6, 7, 20]), "n_swept": rng.choice([1, 2, 3]), "major": rng.choice([0, 1]),
                 "obst_r": rng.choice([0.5, 1.5, 4]), "news_next": rng.choice([30, 60, 61, 600]), "mod": rng.choice([150, 479, 480, 700])}
            assert tg(f) == LL.trader_grade(f), f


# ------------------------------------------------------------------------------------------------ shrinkage
def test_shrinkage():
    days = weekdays("2026-01-05", 80)
    R = [rec(d, 1.0, f={"idm_age": 4.0}) for d in days[:40]] + [rec(d, 0.2, f={"idm_age": 9.0}) for d in days[40:80]]
    est = LL.estimate(R)
    assert abs(est["rbar"] - 0.6) < 1e-9
    fr, st = est["fam"]["trap"]["fresh"], est["fam"]["trap"]["stale"]
    # post = (n x mean + 20 x rbar) / (n + 20)
    assert abs(fr["post_r"] - (40 * 1.0 + 20 * 0.6) / 60) < 1e-3 and abs(st["post_r"] - (40 * 0.2 + 20 * 0.6) / 60) < 1e-3
    assert abs(fr["target"] - 1.25) < 1e-9                          # 0.867 / 0.6 = 1.44 -> clipped at 1.25
    assert abs(st["target"] - round((40 * 0.2 + 20 * 0.6) / 60 / 0.6, 3)) < 1e-3     # 0.333 / 0.6 = 0.556
    # a tiny bucket barely moves: 2 trades at +5R next to 60 at +0.5R
    R2 = [rec(d, 0.5, f={"mod": 600.0}) for d in days[:60]] + [rec(d, 5.0, f={"mod": 350.0}) for d in days[60:62]]
    e2 = LL.estimate(R2)
    x = e2["fam"]["session"]["lon_late"]
    assert x["n"] == 2 and x["target"] <= 1.25 and abs(x["post_r"] - (10 + 20 * e2["rbar"]) / 22) < 1e-3
    assert x["post_r"] < 1.2                                        # shrunk far below the raw +5R
    # the overall mean <= 0: no edge to allocate, every target 1.0
    e3 = LL.estimate([rec(d, -0.5) for d in days[:30]])
    assert all(b["target"] == 1.0 for bs in e3["fam"].values() for b in bs.values())
    # skip only with >= 15 trades that lost money
    R4 = [rec(d, 0.8, f={"vix": 17.0}) for d in days[:40]] + [rec(d, -0.3, f={"vix": 25.0}) for d in days[40:54]]
    assert not LL.estimate(R4)["fam"]["vix"]["high"]["skip_ok"]     # 14 trades
    R4.append(rec(days[54], -0.3, f={"vix": 25.0}))
    assert LL.estimate(R4)["fam"]["vix"]["high"]["skip_ok"]         # 15 trades, lost money
    # proposal steps: at most 0.25 a review, on the 0.05 grid, inside the bounds
    assert LL.proposal_value(1.0, 1.25) == 1.25 and LL.proposal_value(1.0, 0.5) == 0.75 and LL.proposal_value(0.75, 0.5) == 0.5
    assert LL.proposal_value(1.0, 1.07) == 1.05 and LL.proposal_value(1.2, 2.0) == 1.25 and LL.proposal_value(0.6, 0.1) == 0.5


# ------------------------------------------------------------------------------------------------ guardrails + review
def _two_bucket_history(good_r=1.6, bad_r=-0.15, n_days=180, seed=5):
    """Fresh traps win, stale traps lose, every half of the year the same: the learner should cut the stale bucket."""
    rng = random.Random(seed)
    out = []
    for i, d in enumerate(weekdays("2026-01-05", n_days)):
        if i % 2:                                  # ~2.5 trades a week
            continue
        fresh = rng.random() < 0.5
        r = good_r if fresh else bad_r
        r += rng.choice([-0.05, 0.0, 0.05])
        out.append(rec(d, r, f={"idm_age": 3.0 if fresh else 12.0}, exit_="TARGET" if r > 0.05 else "BE"))
    return out


def test_review_moves_one_knob():
    R = _two_bucket_history()
    L, d = LL.review(R, LL.default_learning("apply"), "2026-09-06")
    assert d["action"] == "mult", d
    assert d["fam"] is not None and abs(d["after"]["mult"] - d["before"]["mult"]) <= LL.STEP_MAX + 1e-9
    # exactly one knob changed
    ch = [(f, b) for f, bs in L["knobs"].items() for b in bs]
    assert len(ch) == 1, ch
    c = d["evidence"]["checks"]
    assert c["walk_forward"]["pass"] and c["walk_forward"]["active_blocks"] >= LL.WF_MIN_ACTIVE and c["walk_forward"]["delta_usd"] > 0
    assert c["halves"]["pass"] and all(h["delta"] > 0 for h in c["halves"]["halves"])
    assert c["eval_fail_2wk"]["pass"] and c["trades_week"]["pass"]
    assert d["numbers"]["recent"]["before"]["net"] < d["numbers"]["recent"]["after"]["net"]
    assert d["applied"] is True
    # the next review may move another (or the same) knob, again only one
    L2, d2 = LL.review(R, L, "2026-09-13")
    ch2 = [(f, b, k["mult"]) for f, bs in L2["knobs"].items() for b, k in bs.items()]
    assert len(ch2) <= 2 and sum(1 for x in ch2 if x not in [(f, b, k["mult"]) for f, bs in L["knobs"].items() for b, k in bs.items()]) <= 1


def test_review_refuses_noise():
    # no difference between buckets (pure noise): nothing may pass the walk-forward + both-halves gates every week
    rng = random.Random(11)
    R = []
    for i, d in enumerate(weekdays("2026-01-05", 190)):
        if i % 2:
            continue
        r = rng.choice([-1.02, -1.02, -1.02, -0.02, -0.02, 4.0])
        R.append(rec(d, r, f={"idm_age": rng.choice([3.0, 12.0]), "mod": rng.choice([200.0, 350.0, 600.0]),
                              "vix": rng.choice([14.0, 18.0, 25.0])}, exit_="TARGET" if r > 0 else "STOP"))
    L = LL.default_learning("apply")
    changes = 0
    for s in ("2026-07-05", "2026-07-12", "2026-07-19", "2026-07-26", "2026-08-02", "2026-08-09", "2026-08-16", "2026-08-23",
              "2026-08-30", "2026-09-06"):
        L, d = LL.review(R, L, s)
        changes += d["action"] != "none"
        for fam, bs in L["knobs"].items():
            for b, k in bs.items():
                assert LL.MULT_LO <= k.get("mult", 1.0) <= LL.MULT_HI
    assert changes <= 3, changes                    # a few may slip through on chance, never a run of them
    assert len(L["decisions"]) == 10 and all(x["reason"] for x in L["decisions"])


def test_guardrail_eval_fail():
    # a size-up of a bucket that wins on average but carries the big losses: the 2-week fail gate must be able to say no
    R = _two_bucket_history()
    V = LL._visible(R, "2026-09-06")
    wf = LL._wf_blocks(V, "2026-09-06")
    g = LL.guardrails(V, {}, {"fam": "trap", "b": "fresh", "kind": "mult", "value": 1.25}, "2026-09-06", wf)
    ch = g["checks"]["eval_fail_2wk"]
    assert ch["recent_after"] is not None and "pass" in ch
    # trades a week: skipping half of the trades of a 2.5/wk history drops below 2/wk -> refused
    g2 = LL.guardrails(V, {}, {"fam": "trap", "b": "stale", "kind": "skip", "value": None}, "2026-09-06", wf)
    assert not g2["checks"]["trades_week"]["pass"] and not g2["pass"], g2["checks"]["trades_week"]
    # max step
    g3 = LL.guardrails(V, {}, {"fam": "trap", "b": "stale", "kind": "mult", "value": 0.5}, "2026-09-06", wf)
    assert not g3["checks"]["max_step"]["pass"] and not g3["pass"]


def test_not_enough_data():
    R = _two_bucket_history(n_days=20)
    L, d = LL.review(R, None, "2026-02-01")
    assert d["action"] == "none" and "not enough trades" in d["reason"] and L["knobs"] == {}


def test_no_lookahead_in_review():
    # trades after the review date never change the decision
    R = _two_bucket_history()
    asof = "2026-06-07"
    _, d1 = LL.review([r for r in R if r["day"] < asof], LL.default_learning("apply"), asof)
    junk = [rec(d, -1.02, f={"idm_age": 3.0}) for d in weekdays("2026-06-08", 60)]
    _, d2 = LL.review(R + junk, LL.default_learning("apply"), asof)
    k = ("action", "fam", "bucket", "after")
    assert {x: d1[x] for x in k} == {x: d2[x] for x in k}


# ------------------------------------------------------------------------------------------------ apply / observe / revert
def test_apply_observe_revert():
    R = _two_bucket_history()
    L, d = LL.review(R, LL.default_learning("apply"), "2026-09-06")
    fam, b = d["fam"], d["bucket"]
    tr = {"risk_pts": 20.0, "size_mult": 1.0, "learn": {"buckets": {**{k: None for k in LL.FAMILIES}, fam: b}}}
    m = LL.learn_mult(tr, L)
    assert abs(m["mult"] - d["after"]["mult"]) < 1e-9 and m["mode"] == "apply" and m["reasons"]
    Lo = LL.set_mode(L, "observe")
    mo = LL.learn_mult(tr, Lo)
    assert mo["mult"] == 1.0 and not mo["skip"] and abs(mo["would"] - d["after"]["mult"]) < 1e-9 and not mo["reasons"]
    Lr, dr = LL.revert(L, d["id"], "test")
    assert dr["action"] == "revert" and dr["of"] == d["id"]
    assert LL.learn_mult(tr, Lr)["mult"] == 1.0 and b not in (Lr["knobs"].get(fam) or {})
    assert L["knobs"][fam][b]["mult"] == d["after"]["mult"]          # the original state is not mutated
    try:
        LL.revert(L, "d9999")
        raise AssertionError("revert of an unknown id must fail")
    except ValueError:
        pass
    # skip in apply mode
    Ls = copy.deepcopy(L)
    Ls["knobs"] = {"vix": {"high": {"mult": 1.0, "skip": True}}}
    t2 = {"risk_pts": 20.0, "learn": {"buckets": {"vix": "high"}}}
    assert LL.learn_mult(t2, Ls)["skip"] and not LL.learn_mult(t2, LL.set_mode(Ls, "observe"))["skip"]
    # the combined multiplier stays inside the bounds
    Lb = {"mode": "apply", "knobs": {"trap": {"fresh": {"mult": 1.25}}, "vix": {"mid": {"mult": 1.25}},
                                     "grade": {"C": {"mult": 0.5}}, "session": {"ny": {"mult": 0.5}}}}
    assert LL.mult_of({"trap": "fresh", "vix": "mid"}, Lb["knobs"])[0] == 1.25
    assert LL.mult_of({"grade": "C", "session": "ny"}, Lb["knobs"])[0] == 0.5


def test_sizing_hook():
    t = {"risk_pts": 44.0, "size_mult": 1.0}
    E = {"mode": "eval", "eval_ref_stop": 25.0, "safe_cap": 0.6}
    base = sizing.lit_qty(3, t, E, room=2000.0, learning=None)
    assert base["qty"] == 5 and "learn" not in base                   # 800*25/44 / 88 = 5.2
    assert sizing.lit_qty(3, t, E, room=2000.0, learning={})["qty"] == 5
    L = {"mode": "apply", "knobs": {"trap": {"stale": {"mult": 0.75}, "fresh": {"mult": 1.25}}, "vix": {"high": {"skip": True}}}}
    tf = {**t, "learn": {"buckets": {"trap": "fresh"}}}
    ts = {**t, "learn": {"buckets": {"trap": "stale"}}}
    assert sizing.lit_qty(3, tf, E, room=2000.0, learning=L)["qty"] == 6          # 5.2 x 1.25 = 6.5 -> 6 (one rounding)
    assert sizing.lit_qty(3, ts, E, room=2000.0, learning=L)["qty"] == 3          # 5.2 x 0.75 = 3.9 -> 3
    tw = {**ts, "size_mult": 0.5}
    assert sizing.lit_qty(3, tw, E, room=2000.0, learning=L)["qty"] == 1          # 5.2 x 0.375 = 1.9 -> 1 (one rounding)
    r = sizing.lit_qty(3, {**t, "learn": {"buckets": {"vix": "high"}}}, E, room=2000.0, learning=L)
    assert r["qty"] == 0 and r["mult"] == 0.0 and any("learned skip" in x for x in r["reasons"])
    # a size-up never risks more than $900: 10-pt stop -> base 40 (cap 40); 1.25x stays 40; 22-pt stop: 18 micros x1.25
    # = 22 -> $900 / 45.4 = 19
    t22 = {"risk_pts": 22.0, "size_mult": 1.0, "learn": {"buckets": {"trap": "fresh"}}}
    assert sizing.lit_qty(3, {**t22, "learn": None}, E, room=5000.0, learning=L)["qty"] == 18
    assert sizing.lit_qty(3, t22, E, room=5000.0, learning=L)["qty"] == 19
    # the room cap still applies after the learning step
    assert sizing.lit_qty(3, tf, E, room=300.0, learning=L)["qty"] == 2           # 0.6 x 300 / 88 = 2
    # observe mode: unchanged size, the would-be multiplier reported
    ro = sizing.lit_qty(3, tf, E, room=2000.0, learning={**L, "mode": "observe"})
    assert ro["qty"] == 5 and ro["learn"]["would"] == 1.25 and ro["learn"]["mult"] == 1.0
    # normal mode: one rounding from the $800/20 base (47-pt stop: 800*20/47 / 94 = 3.6 -> 3 micros; x0.75 = 2.7 -> 2)
    N = {"mode": "normal"}
    t47 = {"risk_pts": 47.0, "size_mult": 1.0, "learn": {"buckets": {"trap": "stale"}}}
    assert sizing.lit_qty(3, {**t47, "learn": None}, N, learning=L)["qty"] == 3
    assert sizing.lit_qty(3, t47, N, learning=L)["qty"] == 2
    # no features on the trade: nothing changes
    assert sizing.lit_qty(3, t, E, room=2000.0, learning=L)["qty"] == 5


# ------------------------------------------------------------------------------------------------ journal
def test_journal_append_merge():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "j.jsonl")
        a = rec("2026-03-02", 1.0, source="backtest")
        b = rec("2026-03-02", 0.9, source="cloud")
        c = rec("2026-03-02", 0.95, source="pc")
        e = rec("2026-03-03", -1.0, source="cloud")
        assert LL.append_journal([a, e], p) == 2
        assert LL.append_journal([a], p) == 0                      # never written twice
        assert LL.append_journal([b, c], p) == 2
        J = LL.load_journal(p)
        assert len(J) == 4
        M = LL.merged(J)
        assert len(M) == 2 and M[0]["source"] == "pc" and M[1]["source"] == "cloud"
        with open(p, "a") as fh:
            fh.write("not json\n")
        assert len(LL.load_journal(p)) == 4                       # a broken line is skipped
        s = LL.summary(LL.default_learning(), J, "2026-03-20")
        assert s["mode"] == "observe" and s["causes_month"]["losses"] == 1 and s["journal"]["n"] == 2
        assert s["causes_month"]["by_cause"][0]["cause"] == "not_turning_point"


def test_record_from_live_trade():
    t = {"entry_t": 1760000000, "exit_t": 1760003600, "dir": -1, "entry": 25000.0, "exit_price": 25030.25, "stop": 25030.0,
         "target": 24900.0, "qty": 4, "pnl": -247.6, "pnl_r": -1.03, "exit_reason": "STOP", "day": "2025-10-09",
         "risk_pts": 30.0, "mfe": 0.2, "mae": 1.0, "bars_held": 40, "size_mult": 1.0, "swept": ["PDH"]}
    r = LL.record(t, "cloud", f=F_BASE, post={"target_after_stop": False}, qty=4, pnl=-247.6, learn={"mult": 1.0})
    assert r["exit"] == "STOP" and abs(r["pnl_pm"] - (-61.9)) < 1e-6 and r["q_pre"] == LL.q_pre_of(30.0)
    assert abs(r["r"] - (-61.9 / 60.0)) < 1e-3 and r["cause"] == "not_turning_point" and r["grade"] == "A"
    assert r["key"] == "2025-10-09|1760000000|-1"
    t2 = {**t, "exit_reason": "TIME", "pnl": 40.0}
    assert LL.record(t2, "pc")["exit"] == "EOD"


def test_review_due():
    assert LL.last_sunday(dt.date(2026, 10, 18)) == "2026-10-18"
    assert LL.last_sunday(dt.date(2026, 10, 19)) == "2026-10-18"
    assert LL.last_sunday(dt.date(2026, 10, 24)) == "2026-10-18"
    assert LL.review_due(None, dt.date(2026, 10, 19)) == "2026-10-18"
    assert LL.review_due({"last_review": {"asof": "2026-10-18"}}, dt.date(2026, 10, 23)) is None
    assert LL.review_due({"last_review": {"asof": "2026-10-11"}}, dt.date(2026, 10, 19)) == "2026-10-18"


TESTS = [test_causes, test_buckets_grade, test_shrinkage, test_review_moves_one_knob, test_review_refuses_noise,
         test_guardrail_eval_fail, test_not_enough_data, test_no_lookahead_in_review, test_apply_observe_revert,
         test_sizing_hook, test_journal_append_merge, test_record_from_live_trade, test_review_due]


def run_all() -> bool:
    bad = 0
    for t in TESTS:
        try:
            t()
            print("ok  ", t.__name__)
        except Exception as e:                         # noqa: BLE001
            bad += 1
            import traceback
            traceback.print_exc()
            print("FAIL", t.__name__, e)
    print(f"lit_learn tests: {len(TESTS) - bad}/{len(TESTS)} passed")
    return bad == 0


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
