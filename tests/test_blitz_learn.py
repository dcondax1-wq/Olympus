"""BLITZ learns from its mistakes (research/blitz/learn.py): research + reporting only. Fakes only, temp files (< 5 s).

    python -X utf8 -m tests.test_blitz_learn

  a. tags: each reason on a made-up trade; winners tagged too; "other" only on a loser with no reason
  b. lessons.jsonl: one row per BLITZ trade, never twice (idempotent), from the PC's day-bundle signals
  c. ranking by NET R; pick = the top tags with a testable fix; a passed fix / a fresh reject is not picked again
  d. the fresh test: < 30 fresh trades = waiting (never a pass); the data before fresh_from never counts; the bar rises with k
  e. the weekly run: spans + fresh both needed; one Decide card + one phone line once; every test logged; live files untouched
  f. Sunday only, once an ISO week; the learn_night step runs it
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "research", "blitz"))
import learn as BL  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def T(day, hh, mm, pts, risk=40.0, dur=15, usd=None, slip=None, d=1):
    t0 = int(dt.datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}").replace(tzinfo=BL.ET).timestamp())
    x = {"strat": "BLITZ", "day": day, "entry_t": t0, "exit_t": t0 + dur * 60, "risk": risk, "pts": pts, "dir": d}
    if usd is not None:
        x["usd"] = usd
    if slip is not None:
        x["slip_ticks"] = slip
    return x


def part_a():
    D = "2026-11-02"
    base = {"lit": [], "news": [], "prev": [], "risk_med": 40.0, "day_usd": None}
    t = T(D, 10, 0, -40.0)
    check("a. a full stop-out -> stopped_at_sweep", BL.tags_of(t, base) == ["stopped_at_sweep"], BL.tags_of(t, base))
    t2 = T(D, 10, 0, -10.0, risk=70.0)
    check("a. stop 70 vs median 40 (> 1.5x) -> wide_stop", "wide_stop" in BL.tags_of(t2, base))
    check("a. filled 2 ticks worse -> chased", "chased" in BL.tags_of(T(D, 10, 0, -5.0, slip=2.0), base))
    n = T(D, 10, 0, -5.0)
    check("a. a release 10 min after the entry (inside the trade) -> news",
          "news" in BL.tags_of(n, {**base, "news": [n["entry_t"] + 600]}))
    check("a. a release 20 min before the entry -> not news", "news" not in BL.tags_of(n, {**base, "news": [n["entry_t"] - 1200]}))
    check("a. LIT exited 20 min before -> overlap_lit",
          "overlap_lit" in BL.tags_of(n, {**base, "lit": [(n["entry_t"] - 3600, n["entry_t"] - 1200)]}))
    check("a. LIT exited 40 min before -> not overlap_lit",
          "overlap_lit" not in BL.tags_of(n, {**base, "lit": [(n["entry_t"] - 3600, n["entry_t"] - 2400)]}))
    check("a. an earlier loser today -> after_loss", "after_loss" in BL.tags_of(n, {**base, "prev": [{"pts": -3.0}]}))
    check("a. 15:10 ET entry -> late_day", "late_day" in BL.tags_of(T(D, 15, 10, -5.0), base))
    check("a. day already +$250 (>= 50% of $427.50) -> best_day_cap", "best_day_cap" in BL.tags_of(n, {**base, "day_usd": 250.0}))
    check("a. a small loser with no reason -> other", BL.tags_of(n, base) == ["other"], BL.tags_of(n, base))
    check("a. a winner with no reason: no tag", BL.tags_of(T(D, 10, 0, 30.0), base) == [])
    check("a. a late winner is tagged late_day too (net R stays honest)", BL.tags_of(T(D, 15, 30, 30.0), base) == ["late_day"])
    L = BL.lesson(T(D, 10, 0, -20.0), base, "paper")
    check("a. lesson row: key, R = pts / risk, loser, primary tag", L["key"].startswith("paper|") and L["r"] == -0.5 and not L["win"]
          and L["primary"] == "other", L)


def part_b(tmp):
    from engine import zeus_learn as ZL
    p = os.path.join(tmp, "lessons.jsonl")
    sig = [{"strat": "blitz", "day": "2026-11-03", "entry_t": 1793000000, "exit_t": 1793000900, "dir": 1, "r": -1.0, "risk_pts": 30.0,
            "usd": -61.9, "slip_ticks": 0.0, "mode": "paper"},
           {"strat": "blitz", "day": "2026-11-03", "entry_t": 1793003600, "exit_t": 1793004500, "dir": 1, "r": 1.2, "risk_pts": 30.0,
            "usd": 70.0, "slip_ticks": 0.0, "mode": "paper"},
           {"strat": "zlarior", "day": "2026-11-03", "entry_t": 1792990000, "exit_t": 1792999000, "dir": 1, "r": 1.0, "risk_pts": 40.0}]
    real = ZL.signals
    ZL.signals = lambda days: sig
    try:
        r1 = BL.tag_new([{"day": "2026-11-03"}], p, news=[])
        r2 = BL.tag_new([{"day": "2026-11-03"}], p, news=[])
    finally:
        ZL.signals = real
    rows = BL.read_jsonl(p)
    check("b. 2 BLITZ trades -> 2 lessons (LIT is context, not a lesson)", r1["new"] == 2 and len(rows) == 2, (r1, rows))
    check("b. run again: nothing added twice", r2["new"] == 0 and len(BL.read_jsonl(p)) == 2, r2)
    check("b. the loser: full stop + LIT exited 10 min before -> stopped_at_sweep, overlap_lit",
          set(rows[0]["tags"]) >= {"stopped_at_sweep", "overlap_lit"} and rows[0]["mode"] == "paper", rows[0])
    check("b. the second trade knows the first lost (after_loss)", "after_loss" in rows[1]["tags"], rows[1])


def _lessons(tag, n, r, day0="2026-10-01", mode="paper", step=1):
    out = []
    d0 = dt.date.fromisoformat(day0)
    for i in range(n):
        d = (d0 + dt.timedelta(days=i * step)).isoformat()
        t = T(d, 10, 0, r * 40.0)
        out.append({"key": f"{mode}|{t['entry_t']}|1", "mode": mode, "day": d, "entry_t": t["entry_t"], "exit_t": t["exit_t"],
                    "risk": 40.0, "pts": r * 40.0, "r": r, "win": r > 0, "tags": [tag], "dir": 1})
    return out


def part_c():
    L = _lessons("late_day", 10, -0.5, "2026-11-01") + _lessons("news", 10, -0.2, "2026-11-01") + _lessons("chased", 10, -0.9, "2026-11-01") \
        + _lessons("overlap_lit", 10, 0.3, "2026-11-01")
    rk = BL.rank(L, "2026-11-22")
    check("c. ranked by net R: chased (-9) first, overlap_lit (+3) last", [x["tag"] for x in rk["tags"]][0] == "chased"
          and rk["tags"][-1]["tag"] == "overlap_lit", rk["tags"])
    pk = BL.pick(rk, {}, "2026-11-22")
    check("c. pick: chased has no testable fix -> late_day (no_late) then news (no_news); a winning tag never", pk == ["no_late", "no_news"], pk)
    pk2 = BL.pick(rk, {"candidates": {"no_late": {"status": "rejected", "last_test": "2026-11-15"}}}, "2026-11-22")
    check("c. a fix rejected 1 week ago waits 4 weeks", pk2 == ["no_news"], pk2)
    pk3 = BL.pick(rk, {"candidates": {"no_late": {"status": "passed"}}}, "2026-11-22")
    check("c. a passed fix (waiting for the owner) is not re-run", "no_late" not in pk3, pk3)
    few = BL.rank(L[:5], "2026-11-22", backtest=lambda: _lessons("late_day", 12, -0.4, "2026-11-01", mode="backtest"))
    check("c. fewer than 20 paper/live lessons: ranked on the backtest, and it says so", "backtest" in few["source"] and few["lessons"] == 12, few)
    sw = BL.rank(_lessons("stopped_at_sweep", 30, -1.0, "2026-11-01"), "2026-11-22")
    check("c. stopped_at_sweep (every full stop, by definition) is never picked", BL.pick(sw, {}, "2026-11-22") == [], sw["tags"])
    old = BL.rank(_lessons("late_day", 30, -1.0, "2026-01-01"), "2026-11-22")
    check("c. lessons older than 8 weeks are out of the window", old["lessons"] == 0, old)


def part_d():
    L = _lessons("late_day", 40, 0.5, "2026-09-01")                      # before fresh_from: never counts
    late = []
    for i in range(40):
        d = (dt.date(2026, 11, 2) + dt.timedelta(days=i)).isoformat()
        t = T(d, 15, 20, -20.0)                                        # late losers the fix removes
        late.append({"day": d, "entry_t": t["entry_t"], "exit_t": t["exit_t"], "risk": 40.0, "pts": -20.0, "r": -0.5})
        t2 = T(d, 10, 0, 10.0)
        late.append({"day": d, "entry_t": t2["entry_t"], "exit_t": t2["exit_t"], "risk": 40.0, "pts": 10.0, "r": 0.25})
    w = BL.fresh_test("no_late", L + late[:20], "2026-11-01", 1, news=[])
    check("d. 20 fresh trades (< 30): waiting, never a pass", not w["pass"] and "waiting" in w["why"] and w["n"] == 20, w)
    f = BL.fresh_test("no_late", L + late, "2026-11-01", 1, news=[])
    check("d. 80 fresh trades: the 40 removed late losers (-20 R) pass at k=1; the 40 old winners never counted",
          f["pass"] and f["n"] == 80 and f["removed"] == 40 and f["removed_r"] == -20.0, f)
    noisy = []
    for i, r in enumerate([-1.0, 0.9] * 20):
        d = (dt.date(2026, 11, 2) + dt.timedelta(days=i)).isoformat()
        t = T(d, 15, 20, r * 40.0)
        noisy.append({"day": d, "entry_t": t["entry_t"], "exit_t": t["exit_t"], "risk": 40.0, "pts": r * 40.0, "r": r})
    f1 = BL.fresh_test("no_late", noisy, "2026-11-01", 1, news=[])
    f9 = BL.fresh_test("no_late", noisy, "2026-11-01", 9, news=[])
    check("d. a noisy removal (-2 R over 40, coin flips) does not pass", not f1["pass"], f1)
    check("d. the bar rises with the number of tests (alpha 0.05 / k)", f9["alpha"] < f1["alpha"] and f9["k"] == 9, (f1["alpha"], f9["alpha"]))
    win = BL.fresh_test("no_late", [dict(x, pts=-x["pts"], r=-x["r"]) for x in late], "2026-11-01", 1, news=[])
    check("d. the removed trades made money: no pass", not win["pass"] and "made" in win["why"], win)


def _ev(gain_h1=60, gain_h2=40, fail_h1=0.0, ref=0):
    base = {"H1": {"pass": 83.0, "fail": 1.2, "med_days": 30, "per_month": 1928}, "H2": {"pass": 91.2, "fail": 2.5, "med_days": 21, "per_month": 891},
            "REF": {"pass": 13.0, "fail": 79.8, "med_days": 25, "per_month": -51}}
    fix = {"H1": {**base["H1"], "per_month": 1928 + gain_h1, "fail": 1.2 + fail_h1}, "H2": {**base["H2"], "per_month": 891 + gain_h2},
           "REF": {**base["REF"], "per_month": -51 + ref}}
    return base, fix


def part_e(tmp):
    base, fix = _ev()
    ok, why = BL.spans_pass(base, fix)
    check("e. spans: +$60 / +$40 a month, fail not worse -> pass", ok, why)
    b2, f2 = _ev(gain_h2=10)
    check("e. spans: Jul-Oct only +$10 -> no", not BL.spans_pass(b2, f2)[0])
    b3, f3 = _ev(fail_h1=0.8)
    check("e. spans: Jan-Jun fail +0.8 pt -> no", not BL.spans_pass(b3, f3)[0])
    b4, f4 = _ev(ref=-40)
    check("e. spans: 2021-25 -$40 a month -> no", not BL.spans_pass(b4, f4)[0])

    d = os.path.join(tmp, "e")
    os.makedirs(os.path.join(d, "tools", "web_public", "business"), exist_ok=True)
    dec = os.path.join(d, "tools", "web_public", "business", "decisions.json")
    shutil.copy(os.path.join(ROOT, "tools", "web_public", "business", "decisions.json"), dec)
    n_dec = len(json.load(open(dec, encoding="utf-8"))["items"])
    kw = {k: os.path.join(d, f) for k, f in (("lessons_path", "lessons.jsonl"), ("tests_path", "tests.jsonl"), ("state_path", "state.json"),
                                              ("weekly_path", "weekly.json"))}
    # week 1: late losers in the window -> no_late picked; no fresh data yet -> waiting, no card
    BL.append_jsonl(kw["lessons_path"], _lessons("late_day", 24, -0.6, "2026-10-14", step=1))
    pushed = []
    pusher = lambda line: pushed.append(line) or (True, "ok")  # noqa: E731
    w1 = BL.weekly("2026-11-08", decisions=dec, evaluator=lambda c: {"base": base, **{x: fix for x in c}}, backtest=lambda: [],
                   pusher=pusher, news=[], **kw)
    st = BL.read_json(kw["state_path"])
    check("e. week 1: no_late picked, spans pass, fresh data missing -> waiting, no card, no push",
          w1["picked"] == ["no_late"] and not w1["results"]["no_late"]["pass"] and st["candidates"]["no_late"]["status"] == "waiting"
          and st["candidates"]["no_late"]["fresh_from"] == "2026-11-09" and not pushed and not w1["cards"], (w1["picked"], st))
    # fresh trades after 11-09: 40 late losers the fix removes + 40 morning winners
    fr = []
    for i in range(40):
        dd = (dt.date(2026, 11, 9) + dt.timedelta(days=i % 13)).isoformat()
        a = T(dd, 15, 5 + i % 40, -24.0)
        b = T(dd, 10, i % 50, 10.0)
        fr += [{"key": f"paper|{a['entry_t']}|1", "mode": "paper", "day": dd, "entry_t": a["entry_t"], "exit_t": a["exit_t"], "risk": 40.0,
                "pts": -24.0, "r": -0.6, "win": False, "tags": ["late_day"], "dir": 1},
               {"key": f"paper|{b['entry_t']}|1", "mode": "paper", "day": dd, "entry_t": b["entry_t"], "exit_t": b["exit_t"], "risk": 40.0,
                "pts": 10.0, "r": 0.25, "win": True, "tags": [], "dir": 1}]
    BL.append_jsonl(kw["lessons_path"], fr)
    w2 = BL.weekly("2026-11-22", decisions=dec, evaluator=lambda c: {"base": base, **{x: fix for x in c}}, backtest=lambda: [],
                   pusher=pusher, news=[], **kw)
    D = json.load(open(dec, encoding="utf-8"))
    card = [i for i in D["items"] if i.get("id") == "blitz-learned-no-late"]
    check("e. week 3: fresh data (80 trades) + spans pass -> ONE Decide card 'BLITZ learned ...: +$Y/mo, fails Z%'",
          w2["results"]["no_late"]["pass"] and len(card) == 1 and card[0]["question"].startswith("BLITZ learned no late: +$40/mo, fails 1.2%")
          and card[0]["status"] == "open" and card[0]["options"] == ["yes", "no", "later"] and "$" in card[0]["impact"]
          and isinstance(card[0]["impact_usd"], int) and len(D["items"]) == n_dec + 1, (w2["results"]["no_late"]["fresh"], card))
    check("e. ONE phone line, the card's words", pushed == ["BLITZ learned no late: +$40/mo, fails 1.2%"], pushed)
    w3 = BL.weekly("2026-11-29", decisions=dec, evaluator=lambda c: {"base": base, **{x: fix for x in c}}, backtest=lambda: [],
                   pusher=pusher, news=[], **kw)
    check("e. the next week: the passed fix is not re-run, no second card or push", "no_late" not in w3["picked"]
          and len(json.load(open(dec, encoding="utf-8"))["items"]) == n_dec + 1 and len(pushed) == 1, (w3["picked"], pushed))
    T_ = BL.read_jsonl(kw["tests_path"])
    check("e. every test is logged with its k (1, 2, ...)", [r["k"] for r in T_] == list(range(1, len(T_) + 1)) and len(T_) >= 2, T_)
    check("e. live files untouched (hashed before / after)", w1["protected_ok"] and w2["protected_ok"])


def part_f(tmp):
    sun = dt.datetime(2026, 11, 29, 19, 0, tzinfo=BL.ET)
    check("f. Sunday ET, not run this week -> due", BL.is_sunday_due(sun, {}))
    check("f. Sunday, already run this ISO week -> not due", not BL.is_sunday_due(sun, {"last_week": list(sun.date().isocalendar()[:2])}))
    check("f. Saturday -> not due", not BL.is_sunday_due(sun - dt.timedelta(days=1), {}))
    import argparse
    from tools import learn_night as LN
    P = LN.plan(argparse.Namespace(no_pull=True, wait=None, skip="", full=False, fetch=False, dry_run=False))
    step = dict(P).get("blitz")
    check("f. tools/learn_night.py runs 'research/blitz/learn.py night' (its own step, after hub)",
          step == [["research/blitz/learn.py", "night"]] and [s for s, _ in P][-1] == "blitz", P)
    src = open(os.path.join(ROOT, "research", "blitz", "learn.py"), encoding="utf-8").read()
    check("f. research only: learn.py never imports the live bot or writes a live model",
          "engine.live" not in src and "import live" not in src and "live_model" not in src.replace('"live_model.json", "live_model_lit.json", '
                                                                                                   '"live_model_engine.json"', ""))


def main():
    tmp = tempfile.mkdtemp(prefix="le_blitzlearn_")
    try:
        part_a()
        part_b(tmp)
        part_c()
        part_d()
        part_e(tmp)
        part_f(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(RES)
    print(f"\nblitz learn: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
