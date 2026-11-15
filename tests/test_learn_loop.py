"""The nightly learning loop (engine/learn_loop.py): fast checks, no data run, no browser, no network, no real child.

  * the clock guard (weekdays from 17:00 ET, Saturday, Sunday until 17:00 ET), once a day, the switch, the lock, and
    "skipped while a trade is open" (bot state with a LIT / account-B position, or the files when the server is down)
  * the rule language (validation, H1 cut points, missing facts = x1)
  * the gates: LIT (tools/lit_edge.gate + 2-4 a week + trades changed + placebo), ATLAS (atlas_v2.verdict + trades changed)
  * the queue: the committed one is valid (6-8 pre-registered experiments, each with its gate), bad rows are left out,
    tonight's pick (new first, then stale, never up-to-date ones, at most N)
  * one night with fake runners in a temp root: summary.json + latest.md + history, ONE phone line for a NEW candidate
    (not again the next night), a protected file changed during the run = not trusted + no push, the real live files
    untouched, the module never writes a live file nor imports a broker / order module
  * the pc_report hook (LE_PR_NO_NET = never a child), research/learn/ gitignored

    python -X utf8 -m tests.test_learn_loop
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import learn_loop as LL  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def ts(y, m, d, hh, mm):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


# 2026-11-16 is a Monday
MON_1659, MON_1700, MON_1000 = ts(2026, 11, 16, 16, 59), ts(2026, 11, 16, 17, 0), ts(2026, 11, 16, 10, 0)
FRI_2330, SAT_0900 = ts(2026, 11, 20, 23, 30), ts(2026, 11, 21, 9, 0)
SUN_1659, SUN_1700 = ts(2026, 11, 22, 16, 59), ts(2026, 11, 22, 17, 0)
ON = {"LE_LEARN": "1"}


def t_window():
    print("window")
    check("Monday 16:59 ET: no (trading day before 17:00)", not LL.window_ok(MON_1659)[0])
    check("Monday 17:00 ET: yes", LL.window_ok(MON_1700)[0])
    check("Monday 10:00 ET: no", not LL.window_ok(MON_1000)[0])
    check("Friday 23:30 ET: yes", LL.window_ok(FRI_2330)[0])
    check("Saturday 09:00 ET: yes", LL.window_ok(SAT_0900)[0])
    check("Sunday 16:59 ET: yes", LL.window_ok(SUN_1659)[0])
    check("Sunday 17:00 ET: no (the week opens at 18:00)", not LL.window_ok(SUN_1700)[0])


def t_guard(tmp):
    print("guard")
    flat = lambda: None                                        # noqa: E731
    od = os.path.join(tmp, "g")
    check("LE_LEARN=0 switches it off", LL.guard(MON_1700, od, env={"LE_LEARN": "0"}, open_fn=flat) == (False, "switched off (LE_LEARN=0)"))
    if os.name != "nt":
        check("not on Windows and not forced: no", not LL.guard(MON_1700, od, env={}, open_fn=flat)[0])
    check("in the window, flat: yes", LL.guard(MON_1700, od, env=ON, open_fn=flat) == (True, "ok"))
    check("before 17:00 ET: no", not LL.guard(MON_1659, od, env=ON, open_fn=flat)[0])
    ok, why = LL.guard(MON_1700, od, env=ON, open_fn=lambda: "a position is open")
    check("a trade open: skipped, says why", not ok and "position is open" in why, why)
    LL._write_json(os.path.join(od, "state.json"), {"day": LL.learn_day(MON_1700)})
    check("already ran today: no", LL.guard(MON_1700 + 3600, od, env=ON, open_fn=flat) == (False, "already ran today"))
    check("... the next day: yes", LL.guard(MON_1700 + 86400, od, env=ON, open_fn=flat)[0])
    LL._write_json(os.path.join(od, "running.json"), {"pid": os.getpid(), "t": MON_1700 + 86400})
    check("a live lock (running pid): no", LL.guard(MON_1700 + 86400 + 60, od, env=ON, open_fn=flat) == (False, "already running"))
    LL._write_json(os.path.join(od, "running.json"), {"pid": os.getpid(), "t": MON_1700 + 86400 - LL.STALE_LOCK_S - 10})
    check("a stale lock is ignored", LL.guard(MON_1700 + 86400, od, env=ON, open_fn=flat)[0])
    LL._write_json(os.path.join(od, "running.json"), {"pid": 999999999, "t": MON_1700 + 86400})
    check("a lock of a dead pid is ignored", LL.guard(MON_1700 + 86400, od, env=ON, open_fn=flat)[0])
    check("--force skips the clock, never the flat check",
          LL.guard(MON_1000, od, env=ON, open_fn=lambda: "a NinjaTrader bracket is Working", force=True)[0] is False
          and LL.guard(MON_1000, od, env=ON, open_fn=flat, force=True)[0] is True)


def t_trade_open(tmp):
    print("trade open")
    snap_pos = {"running": True, "state": {"position": {"dir": 1, "qty": 2}}}
    snap_b = {"running": True, "state": {}, "account_b": {"state": {"position": {"side": "LONG"}}}}
    snap_flat = {"running": True, "state": {"position": None, "setups": []}, "open_routed": None}
    snap_pending = {"running": True, "state": {"setups": [{"k": 1}]}}
    check("LIT position -> not flat", "position" in (LL.trade_open(tmp, http=lambda u: snap_pos) or ""))
    check("account B (ATLAS) position -> not flat", LL.trade_open(tmp, http=lambda u: snap_b) is not None)
    check("a LIT entry pending -> not flat", "pending" in (LL.trade_open(tmp, http=lambda u: snap_pending) or ""))
    check("flat bot -> None", LL.trade_open(tmp, http=lambda u: snap_flat) is None)
    root = os.path.join(tmp, "files")
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    check("server down, no state files -> flat (files check)", LL.trade_open(root, http=lambda u: None) is None)
    import time as _t
    json.dump({"saved_at": _t.time(), "open_routed": {"dir": 1}}, open(os.path.join(root, "data", "live_state.json"), "w"))
    check("server down, today's state has a routed position -> not flat", LL.trade_open(root, http=lambda u: None) is not None)
    open(os.path.join(root, "data", "live_state.json"), "w").write("{torn")
    check("server down, unreadable state -> not flat (unsure = skip)", LL.trade_open(root, http=lambda u: None) is not None)


def t_rules():
    print("rules")
    good = [{"feature": "vix_chg", "op": ">=", "h1_q": 0.6667, "mult": 0.75}]
    check("a good rule has no errors", LL.rule_errors(good) == [], LL.rule_errors(good))
    bad = LL.rule_errors([{"feature": "x", "op": "~", "mult": 3}, {"op": ">="}, {"feature": "y", "op": ">", "mult": 1.0}])
    check("bad op / mult / missing feature / missing value are named", len(bad) >= 4, bad)
    check("an empty rule is an error", LL.rule_errors([]) != [])
    R = LL.resolve(good, lambda f, q: 1.5 if (f, q) == ("vix_chg", 0.6667) else 0)
    check("h1_q resolves through the H1 quantile function", R[0]["value"] == 1.5 and "value" not in good[0])
    check("above the cut -> x0.75", LL.rule_mult(R, {"vix_chg": 2.0}) == 0.75)
    check("below the cut -> x1", LL.rule_mult(R, {"vix_chg": 1.0}) == 1.0)
    check("missing / None / NaN fact -> x1", LL.rule_mult(R, {}) == 1.0 and LL.rule_mult(R, {"vix_chg": None}) == 1.0
          and LL.rule_mult(R, {"vix_chg": float("nan")}) == 1.0)
    B = [{"feature": "lit_opp_lost", "op": "true", "mult": 1.25}]
    check("bool true / false / missing", LL.rule_mult(B, {"lit_opp_lost": True}) == 1.25 and LL.rule_mult(B, {"lit_opp_lost": False}) == 1.0
          and LL.rule_mult(B, {}) == 1.0)
    S = [{"feature": "lvl_type", "op": "==", "value": "Asia box", "mult": 0.5}]
    check("string compare", LL.rule_mult(S, {"lvl_type": "Asia box"}) == 0.5 and LL.rule_mult(S, {"lvl_type": "build-up"}) == 1.0)
    F = [{"feature": "a", "op": ">", "value": 1, "mult": 1.25}, {"feature": "a", "op": ">", "value": 0, "mult": 0.5}]
    check("the first matching step wins", LL.rule_mult(F, {"a": 2}) == 1.25 and LL.rule_mult(F, {"a": 0.5}) == 0.5)


def _short(d_lit, d_eval, d_f10, tpw=(2.5, 2.5), pm=(5000, 2600, 20), epm=(5000, 3000)):
    sp = lambda n, t, p: {"n": n, "tpw": t, "wk2": 50, "win": 50, "pf": 2, "net": 1000, "per_month": p, "dd": -500, "p10": 40, "f10": 1}  # noqa: E731
    ev = lambda p: {"n": 50, "tpw": 2.5, "pf": 2, "net": 1000, "per_month": p, "dd": -500, "p10": 40, "f10": 1, "dec10": 41,  # noqa: E731
                    "p15": 50, "f15": 2, "slow_pass": 10, "pass_med": 8, "b2b": "", "mc_p10": 40, "mc_f10": 1}
    s = {"lit": {"H1": sp(60, tpw[0], pm[0]), "H2": sp(40, tpw[1], pm[1]), "2021-25": sp(500, 2.4, pm[2])},
         "eval": {"H1": ev(epm[0]), "H2": ev(epm[1])}}
    if d_lit is not None:
        s.update(d_lit=dict(zip(("H1", "H2", "2021-25"), d_lit)), d_eval=dict(zip(("H1", "H2"), d_eval)),
                 d_f10=dict(zip(("H1", "H2"), d_f10)), d_p10={"H1": 0, "H2": 0})
    return s


def t_gates():
    print("gates")
    base = _short(None, None, None, pm=(5000, 2500, 20), epm=(4800, 2900))
    good = _short((900, 300, -50), (700, 200), (0, 0), pm=(5150, 2550, 18), epm=(4900, 2950))
    hits = {"H1": 12, "H2": 6}
    r = LL.judge_lit(good, base, hits, {"H1": 0.05, "H2": 0.1})
    check("LIT: better both halves, fails flat, beats random -> candidate", r["status"] == "candidate", r)
    check("LIT: $ a month = the smaller half (+$50)", r["usd_month"] == 50 and r["usd_month_by"]["H2"] == 50, r)
    check("LIT: 2021-25 worse is NOT a gate (reference only)", r["usd_month_by"]["2021-25"] < 0 and r["status"] == "candidate")
    r = LL.judge_lit(good, base, hits, None)
    check("LIT: no placebo yet -> never a candidate", r["status"] == "rejected")
    r = LL.judge_lit(good, base, hits, {"H1": 0.05, "H2": 0.4})
    check("LIT: random sizes beat it in Jul-Oct -> rejected", r["status"] == "rejected" and "random" in r["why"], r)
    r = LL.judge_lit(_short((900, -10, 0), (700, 200), (0, 0)), base, hits, {"H1": 0, "H2": 0})
    check("LIT: worse in the check half -> rejected, says Jul-Oct", r["status"] == "rejected" and "Jul-Oct" in r["why"], r)
    r = LL.judge_lit(_short((900, 300, 0), (700, 200), (0, 1.7)), base, hits, {"H1": 0, "H2": 0})
    check("LIT: more 2-week fails -> rejected", r["status"] == "rejected" and "fails" in r["why"], r)
    r = LL.judge_lit(_short((900, 300, 0), (700, 200), (0, 0), tpw=(2.5, 1.8)), base, hits, {"H1": 0, "H2": 0})
    check("LIT: under 2 trades a week -> rejected", r["status"] == "rejected" and "trades a week" in r["why"], r)
    r = LL.judge_lit(good, base, {"H1": 12, "H2": 2}, {"H1": 0, "H2": 0})
    check("LIT: too few trades changed in Jul-Oct -> rejected", r["status"] == "rejected" and "too few" in r["why"], r)
    ob = {s: {"per_month": 100} for s in ("H1", "H2", "2025", "2021-24")}
    oo = {"H1": {"per_month": 160}, "H2": {"per_month": 130}, "2025": {"per_month": 90}, "2021-24": {"per_month": 100}}
    v = {"h1": True, "h2": True, "both": True, "ref": "B", "freq": True, "pass": True}
    r = LL.judge_atlas(v, oo, ob, hits)
    check("ATLAS: v2 pass + enough trades -> candidate, $ = smaller half (+$30)", r["status"] == "candidate" and r["usd_month"] == 30, r)
    r = LL.judge_atlas({**v, "h2": False, "pass": False}, oo, ob, hits)
    check("ATLAS: not better in Jul-Oct -> rejected", r["status"] == "rejected" and "Jul-Oct" in r["why"], r)
    r = LL.judge_atlas({**v, "ref": "-", "pass": False}, oo, ob, hits)
    check("ATLAS: 2021-25 worse than today -> rejected", r["status"] == "rejected" and "2021-25" in r["why"], r)
    r = LL.judge_atlas({**v, "freq": False, "pass": False}, oo, ob, hits)
    check("ATLAS: under 2 signals a week -> rejected", r["status"] == "rejected")
    r = LL.judge_atlas(v, oo, ob, {"H1": 3, "H2": 9})
    check("ATLAS: too few trades changed -> rejected", r["status"] == "rejected")


def t_queue(tmp):
    print("queue")
    Q, errs = LL.load_queue()
    check("the committed queue loads with no errors", errs == [], errs)
    check("6-8 experiments", 6 <= len(Q) <= 8, len(Q))
    check("LIT and ATLAS both queued", {e["bot"] for e in Q} == {"lit", "atlas"})
    raw = json.load(open(LL.QUEUE_PATH, encoding="utf-8"))
    check("every kind has its gate written in the queue", all(raw["gates"].get(e["kind"]) for e in Q))
    check("every experiment says how it is judged, when it was registered and why", all(e.get("judged_by") and e.get("registered") and len(e.get("hypothesis", "")) > 40 for e in Q))
    check("cut points are picked on 2026 H1 (h1_q) or are yes/no facts", all(("h1_q" in s) or s["op"] in ("true", "false") for e in Q for s in e["rule"]))
    rej = open(os.path.join(ROOT, "docs", "CLAUDE_REFERENCE.md"), encoding="utf-8").read()
    rej = rej[rej.index("## Tested and rejected"):rej.index("## Key commands")]
    feats = {s["feature"] for e in Q for s in e["rule"]}
    check("no queued fact is one 'Tested and rejected' names as tried", not any(f in rej for f in feats), [f for f in feats if f in rej])
    bad = {"experiments": [{"id": "a", "bot": "lit", "kind": "nope", "rule": [], "title": "t", "hypothesis": "h", "judged_by": "j", "registered": "r"},
                           {"id": "b", "bot": "lit", "kind": "lit_tilt", "rule": [{"feature": "f", "op": "true", "mult": 1.25}], "title": "t",
                            "hypothesis": "h", "judged_by": "lit_tilt", "registered": "2026-11-15"},
                           {"id": "b", "bot": "lit", "kind": "lit_tilt", "rule": [{"feature": "f", "op": "true", "mult": 1.25}], "title": "t",
                            "hypothesis": "h", "judged_by": "lit_tilt", "registered": "2026-11-15"},
                           {"id": "c", "bot": "es", "kind": "lit_tilt", "rule": [{"feature": "f", "op": "true", "mult": 1.25}], "title": "t",
                            "hypothesis": "h", "judged_by": "lit_tilt", "registered": "2026-11-15"},
                           {"id": "d", "on": False, "bot": "lit", "kind": "lit_tilt", "rule": [{"feature": "f", "op": "true", "mult": 1.25}],
                            "title": "t", "hypothesis": "h", "judged_by": "lit_tilt", "registered": "2026-11-15"}]}
    p = os.path.join(tmp, "q.json")
    json.dump(bad, open(p, "w"))
    q, e = LL.load_queue(p)
    check("bad kind / duplicate id / bad bot left out and named; switched-off row skipped", [x["id"] for x in q] == ["b"] and len(e) == 3, (q, e))
    check("a missing queue file is an error, not a crash", LL.load_queue(os.path.join(tmp, "none.json"))[0] == [])
    # pick
    E = [{"id": i, "kind": "lit_tilt", "bot": "lit", "rule": [{"feature": i, "op": "true", "mult": 0.5}]} for i in "abcd"]
    R = {"a": {"hash": LL.exp_hash(E[0]), "data_key": "K", "t": 5, "status": "rejected"},
         "b": {"hash": LL.exp_hash(E[1]), "data_key": "OLD", "t": 3, "status": "rejected"},
         "c": {"hash": "changed", "data_key": "K", "t": 9, "status": "rejected"}}
    check("pick: never-run / changed first, then stale, up-to-date never", [e["id"] for e in LL.pick(E, R, "K", 5)] == ["c", "d", "b"])
    check("pick: at most N a night", len(LL.pick(E, R, "K", 2)) == 2 and len(LL.pick(E, {}, "K", 0)) == 0)
    R2 = {**R, "a": {**R["a"], "status": "error", "tries": 1}}
    check("pick: an error is retried (up to 3 tries)", "a" in [e["id"] for e in LL.pick(E, R2, "K", 5)]
          and "a" not in [e["id"] for e in LL.pick(E, {**R, "a": {**R["a"], "status": "error", "tries": 3}}, "K", 5)])


def _fake_root(tmp):
    root = os.path.join(tmp, "root")
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    os.makedirs(os.path.join(root, "research", "lit"), exist_ok=True)
    for rel in LL.PROTECTED:
        with open(os.path.join(root, rel), "w") as fh:
            fh.write('{"x": 1}')
    q = {"experiments": [
        {"id": "good", "bot": "lit", "kind": "fake", "title": "Fake good idea", "hypothesis": "h" * 50, "judged_by": "lit_tilt",
         "registered": "2026-11-15", "rule": [{"feature": "f", "op": "true", "mult": 1.25}]},
        {"id": "bad", "bot": "atlas", "kind": "fake", "title": "Fake bad idea", "hypothesis": "h" * 50, "judged_by": "atlas_tilt",
         "registered": "2026-11-15", "rule": [{"feature": "g", "op": "true", "mult": 0.5}]},
        {"id": "boom", "bot": "lit", "kind": "fake", "title": "Fake crash", "hypothesis": "h" * 50, "judged_by": "lit_tilt",
         "registered": "2026-11-15", "rule": [{"feature": "h", "op": "true", "mult": 0.5}]}]}
    json.dump(q, open(os.path.join(root, "queue.json"), "w"))
    return root


def t_night(tmp):
    print("one night (fake runners)")
    root = _fake_root(tmp)
    od = os.path.join(tmp, "out")
    pushes = []

    def fake(e, C):
        if e["id"] == "boom":
            raise RuntimeError("synthetic crash")
        if e["id"] == "good":
            return {"status": "candidate", "why": "better both halves", "usd_month": 312, "usd_month_by": {"H1": 500, "H2": 312, "2021-25": 10}}
        return {"status": "rejected", "why": "not better in Jul-Oct (check)", "usd_month": -40, "usd_month_by": {"H1": 20, "H2": -40, "2021-24": -5}}
    LL.RUNNERS["fake"] = fake
    real0 = LL.protected_hashes(ROOT)
    try:
        kw = dict(out_dir=od, root=root, queue_path=os.path.join(root, "queue.json"), refresh_fn=lambda C: {"lit": {}},
                  drift_fn=lambda C: {"flags": [], "level": "ok"}, push_fn=lambda line: (pushes.append(line), (True, "ok"))[1])
        LL.RUNNERS["fake"] = fake
        S = LL.run(n_max=3, now=MON_1700, **{**kw, "runners": {"fake": fake}})
        check("ran 3: one candidate, one rejected, one error (the crash is caught)",
              sorted(r["status"] for r in S["ran"]) == ["candidate", "error", "rejected"], S["ran"])
        check("ONE phone line, in the owner's words", pushes == ["Candidate: Fake good idea, +$312/month in both halves - review"], pushes)
        for f in ("summary.json", "latest.md", "state.json", "history.jsonl", "drift.jsonl", "results/good.json"):
            check(f"writes {f}", os.path.exists(os.path.join(od, f)))
        check("the lock is gone after the run", not os.path.exists(os.path.join(od, "running.json")))
        Sj = json.load(open(os.path.join(od, "summary.json")))
        check("summary is small (< 20 KB) and says paper only + protected ok", os.path.getsize(os.path.join(od, "summary.json")) < 20000
              and Sj["paper_only"] and Sj["protected_ok"] and Sj["candidates"][0]["id"] == "good", Sj)
        md = open(os.path.join(od, "latest.md"), encoding="utf-8").read()
        check("latest.md: a plain table, every experiment listed, a next step for the candidate",
              "| What | Result |" in md and "Fake bad idea" in md and "Fake crash" in md and "review the learn candidates" in md, md[:400])
        check("state: once today (the guard says already ran)", LL.guard(MON_1700 + 600, od, env=ON, open_fn=lambda: None) == (False, "already ran today"))
        S2 = LL.run(n_max=3, now=MON_1700 + 86400, **{**kw, "runners": {"fake": fake}})
        check("next night: up-to-date results are not re-run (only the crashed one is retried)", [r["id"] for r in S2["ran"]] == ["boom"], S2["ran"])
        check("next night: no second push for the same candidate", len(pushes) == 1, pushes)
        # data changed -> stale -> re-run, still a candidate -> still no new push
        open(os.path.join(root, "data", "NQ_5m.csv"), "w").write("time,open\n1,2\n")
        S3 = LL.run(n_max=3, now=MON_1700 + 2 * 86400, **{**kw, "runners": {"fake": fake}})
        check("new bars -> the judged experiments are re-checked", {"good", "bad"} <= {r["id"] for r in S3["ran"]}, S3["ran"])
        check("a candidate that stays a candidate is not pushed again", len(pushes) == 1)

        # a runner that touches a protected file: the run is not trusted, nothing pushed
        def evil(e, C):
            with open(os.path.join(root, "live_model.json"), "w") as fh:
                fh.write('{"x": 2}')
            return {"status": "candidate", "why": "x", "usd_month": 1, "usd_month_by": {"H1": 1, "H2": 1}}
        od2 = os.path.join(tmp, "out2")
        S4 = LL.run(n_max=1, now=MON_1700, **{**kw, "out_dir": od2, "runners": {"fake": evil}})
        check("a protected file changed -> protected_ok false, no push, an error says so",
              S4["protected_ok"] is False and S4["pushed"] == [] and any("protected" in x for x in S4["errors"]) and len(pushes) == 1, S4)
    finally:
        LL.RUNNERS.pop("fake", None)
    check("the repo's real live files are untouched by the tests", LL.protected_hashes(ROOT) == real0)


def t_static():
    print("never touches live files")
    src = open(os.path.join(ROOT, "engine", "learn_loop.py"), encoding="utf-8").read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    check("no broker / order / NinjaTrader import", not re.search(r"import .*(ninjatrader|tradovate|broker|order|multi_account)|from \.(ninjatrader|tradovate)", code))
    check("no rl.save (research/runs is tracked: the PC tree stays clean)", "rl.save" not in code and "runlib" not in code)
    writes = re.findall(r'(_write_json|_append|open)\(([^)]*)', code)
    bad = [w for w in writes if re.search(r"live_model|second_model|account_b|lit_final|QUEUE_PATH|queue_path", w[1]) and ('"w"' in w[1] or w[0] != "open")]
    check("never writes a live file nor the queue", not bad, bad)
    check("the protected list covers every live file", {"live_model.json", "live_model_lit.json", "second_model.json", "data/account_b.json"} <= set(LL.PROTECTED))
    check("outputs go to research/learn/ (gitignored)", "research/learn/" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
          and LL.OUT_DIR.endswith(os.path.join("research", "learn")))
    pr = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("the PC's 15-minute report task calls the hook", "learn_loop" in pr and "_ll.maybe_run" in pr)


def t_hook(tmp):
    print("hook")
    od = os.path.join(tmp, "hook")
    spawned = []
    check("LE_PR_NO_NET=1 (the PC report's tests): never a child", LL.maybe_run(MON_1700, say=lambda *_: None, env={"LE_PR_NO_NET": "1", "LE_LEARN": "1"},
                                                                             out_dir=od, open_fn=lambda: None) is None)
    pid = LL.maybe_run(MON_1700, say=lambda *_: None, env=ON, out_dir=od, open_fn=lambda: None,
                       spawn_fn=lambda b, o: (spawned.append((b, o)), os.getpid())[1])
    check("in the window and flat: one child with the budget", pid == os.getpid() and spawned and spawned[0][0] == LL.BUDGET_S, spawned)
    check("its lock is written", (LL._read_json(os.path.join(od, "running.json"), {}) or {}).get("pid") == os.getpid())
    LL.maybe_run(MON_1700 + 900, say=lambda *_: None, env=ON, out_dir=od, open_fn=lambda: None,
                 spawn_fn=lambda b, o: (spawned.append((b, o)), 1)[1])
    check("15 minutes later while it runs: no second child", len(spawned) == 1)
    os.remove(os.path.join(od, "running.json"))
    LL.maybe_run(MON_1000, say=lambda *_: None, env=ON, out_dir=od, open_fn=lambda: None, spawn_fn=lambda b, o: (spawned.append(1), 1)[1])
    check("during trading hours: no child", len(spawned) == 1)
    LL.maybe_run(MON_1700, say=lambda *_: None, env=ON, out_dir=od, open_fn=lambda: "a position is open",
                 spawn_fn=lambda b, o: (spawned.append(1), 1)[1])
    check("trade open: no child", len(spawned) == 1)
    od3 = os.path.join(tmp, "hook3")
    n0 = len(spawned)
    for k in range(5):                                   # a child that dies at once: the lock pid is dead every time
        LL.maybe_run(SAT_0900 + 900 * k, say=lambda *_: None, env=ON, out_dir=od3, open_fn=lambda: None,
                     spawn_fn=lambda b, o: (spawned.append(1), 999999999)[1])
    check(f"a child that keeps crashing is started at most {LL.MAX_TRIES} times a day", len(spawned) - n0 == LL.MAX_TRIES, len(spawned) - n0)
    check("a crash inside the hook never raises", LL.maybe_run(MON_1700, say=lambda *_: None, env=ON, out_dir=od, open_fn=lambda: 1 / 0) is None)
    check("phone line format", LL.phone_line({"title": "X", "usd_month": 1234.4}) == "Candidate: X, +$1,234/month in both halves - review")
    check("push without a topic / network off never raises", LL.push_phone("x", env={"LE_PR_NO_NET": "1"})[0] is False)


def main():
    tmp = tempfile.mkdtemp(prefix="learn_loop_")
    try:
        t_window()
        t_guard(tmp)
        t_trade_open(tmp)
        t_rules()
        t_gates()
        t_queue(tmp)
        t_night(tmp)
        t_static()
        t_hook(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\nlearn_loop: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
