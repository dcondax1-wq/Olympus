"""Mind (engine/mind.py, read-only thinking layer): memory, honest calibration, regime + trend-day odds, game plans, trade
reviews, nightly self-research, the contract block and its wiring (liveview / phone / heartbeat / holo / narrator / API).

Real data for the numbers (research/mind/store.json + calibration.json from tools/mind_build.py on data/NQ_5m.csv), temp
dirs for every file Mind writes, fake bots (a Bot Brain replayed from the stored 2026 bars, synthetic ledgers). Checks:
  * the live feature path (a 45-day bar window, like the PC bot) gives the SAME features as the research store
  * the calibration says out loud whether similarity predicts (fit 2026 H1 -> 2026 H2 / 2021-25), and a non-predictive
    memory never claims confidence; the validation machinery does detect a real signal on synthetic data
  * the trend-day model's accuracy is reported for 2026 H2 and 2021-25
  * the block matches the contract (also the committed sample and the compact cut, < 12 KB)
  * plans at 01:45 / 10:45 ET, one per bot per day, journaled; reviews once per trade (also after a restart); research
    proposals never adopt anything, a candidate needs both 2026 halves (LIT) / + 2021-25 (ATLAS, BLITZ)
  * read-only: the bot is unchanged, engine/mind.py imports no broker / order module; pc_tick only starts a thread

    python -X utf8 -m tests.test_mind
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import mind as MD  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def T(day, h, m):
    d = dt.date.fromisoformat(day)
    return int(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ET).timestamp())


_H = {}


def full_hist():
    if "H" not in _H:
        import pandas as pd
        _H["df"] = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        _H["H"] = MD.hist_from_frame(_H["df"])
    return _H["H"]


def fake_bot(now, brain=None, **kw):
    b = SimpleNamespace(brain=brain, bars_tail=[], _lit_1m_store=None, second=None, blitz=None, ledger=[], cfg={}, state={},
                        running=True, kill=False, health={}, clock=lambda: now)
    for k, v in kw.items():
        setattr(b, k, v)
    return b


# ------------------------------------------------------------------------------------------------ 1. memory + calibration
def t_store_calibration():
    S, C = MD.load_store(), MD.load_calib()
    n = {k: len((S.get("bots") or {}).get(k, {}).get("rows") or []) for k in MD.BOTS}
    print("   store:", n)
    check("store: every bot has its history (LIT >= 600 with 2021-25 + 2026, ATLAS >= 1000, BLITZ >= 300)",
          n["lit"] >= 600 and n["atlas"] >= 1000 and n["blitz"] >= 300, n)
    lit = S["bots"]["lit"]
    days = [r[0] for r in lit["rows"]]
    check("store: LIT rows cover 2021-25 and both 2026 halves", any(d < "2026" for d in days) and any("2026-01" <= d <= "2026-06-30" for d in days)
          and any(d >= "2026-07-01" for d in days))
    check("store: the features the brief asks for are stored (depth, displacement, inducements, time, killzone, VIX, 15m/1h "
          "structure, R to the band, prior-day range; member for ATLAS; first-hour range for BLITZ)",
          {"depth", "disp", "idm_n", "mod", "kz", "vix", "tr15", "tr1h", "rr", "prev_rng"} <= set(lit["cols"])
          and "member" in S["bots"]["atlas"]["cols"] and "fh_ratio" in S["bots"]["blitz"]["cols"])
    sim = C.get("similar") or {}
    for bot in MD.BOTS:
        c = sim.get(bot) or {}
        sp = c.get("spans") or {}
        v, note = MD.judge(sp)
        check(f"calibration {bot}: fit 2026 H1, checked on {', '.join(sp)}; the stored verdict = judge() ({'valid' if v else 'not predictive'})",
              c.get("fit") == "2026 H1" and "H2" in sp and c.get("valid") == v and c.get("note") == note, c)
        print(f"   {bot}: valid={c.get('valid')} " + " | ".join(f"{k}: rho {x.get('spearman')}, top-bot {x.get('spread_r')}R, p {x.get('p_perm')}"
                                                         for k, x in sp.items()))
    check("calibration: LIT and ATLAS are also checked on 2021-25", "2021-25" in sim["lit"]["spans"] and "2021-25" in sim["atlas"]["spans"])
    line = MD.calibration_line(C)
    check("calibration line: says plainly which memories do NOT predict (context only)",
          all((("does NOT predict" in line.split(nm + ":")[1][:20]) != bool(sim[b]["valid"])) for b, nm in MD.BOTS.items()), line)
    dtm = C.get("daytype") or {}
    rep = dtm.get("report") or {}
    check("trend-day model: fit on 2026 H1, accuracy reported on 2026 H2 and 2021-25 (AUC, Brier vs base rate)",
          dtm.get("fit") == "2026 H1" and all(k in rep and rep[k].get("auc") is not None and rep[k].get("brier_base") is not None
                                              for k in ("H2", "2021-25")), rep)
    print("   trend-day:", {k: (v.get("auc"), v.get("brier"), v.get("brier_base"), v.get("base_rate")) for k, v in rep.items()})


def t_validation_machinery():
    """The checks are able to say yes: a synthetic store where R follows a feature -> valid; pure noise -> not valid."""
    rng = np.random.default_rng(3)
    cols = MD.ROW0 + ["depth", "disp", "idm_n", "stop_atr", "rr", "mod", "vix", "tr15", "tr1h", "prev_rng", "day_pos", "atr_r", "kz", "lvl"]
    days = [str(np.datetime64("2026-01-02") + np.timedelta64(i, "D")) for i in range(0, 290)] + [str(np.datetime64("2023-01-02") + np.timedelta64(i, "D")) for i in range(0, 300)]

    def mk(signal):
        rows = []
        for i, d in enumerate(days):
            x = float(rng.normal())
            r = (1.5 * x if signal else 0.0) + float(rng.normal()) * 0.6
            rows.append([d, 1000 + i, 1, round(r, 3), r * 100, "X", "t", x, *[float(rng.normal()) for _ in range(11)], "london", "asia"])
        return rows
    out = {}
    for nm, sig in (("signal", True), ("noise", False)):
        rows = mk(sig)
        dd = np.array([r[0] for r in rows])
        fit = (dd >= MD.H1[0]) & (dd <= MD.H1[1])
        mem = MD.Memory("lit", cols, rows, fit=fit)
        sp = {k: MD.evaluate(mem, fit, (dd >= a) & (dd <= z)) for k, (a, z) in (("H2", MD.H2), ("2021-25", MD.R2125))}
        out[nm] = MD.judge(sp)[0]
    check("validation: a real signal is found (valid), noise is not", out == {"signal": True, "noise": False}, out)
    check("confidence: never above 'low' when not valid", MD.conf_of(40, 2.0, 0.5, False) == "low" and MD.conf_of(40, 2.0, 0.5, True) == "high")


# ------------------------------------------------------------------------------------------------ 2. live features == research features
def t_feature_parity():
    import pandas as pd
    H = full_hist()
    df = _H["df"]
    S = MD.load_store()
    blk = S["bots"]["lit"]
    ci = {c: j for j, c in enumerate(blk["cols"])}
    picks = [r for r in blk["rows"] if r[0] >= "2026-09-01"][:6] + [r for r in blk["rows"] if "2024-03" <= r[0] < "2024-04"][:3]
    bad = []
    for r in picks:
        e = dt.datetime.fromtimestamp(int(r[ci["t"]]), ET)
        # decision time = the 5m CISD close: rebuild it from mod (minutes since 18:00)
        mod = (int(r[ci["mod"]]) + 1080) % 1440
        day = dt.date.fromisoformat(r[0])
        base = dt.datetime(day.year, day.month, day.day, tzinfo=ET) - (dt.timedelta(days=1) if mod >= 1080 else dt.timedelta(0))
        Td = int((base + dt.timedelta(minutes=mod)).timestamp())
        win = df[(df["time"] >= Td - MD.HIST_DAYS * 86400) & (df["time"] + 300 <= Td)]
        Hl = MD.hist_from_frame(win)
        fl, ff = Hl.ctx(Td, int(r[ci["dir"]])), H.ctx(Td, int(r[ci["dir"]]))
        for c in ("mod", "kz", "vix", "tr15", "tr1h", "prev_rng", "day_pos"):
            if fl.get(c) != r[ci[c]] or ff.get(c) != r[ci[c]]:
                bad.append((r[0], e.strftime("%H:%M"), c, r[ci[c]], fl.get(c), ff.get(c)))
        if r[ci["atr_r"]] is not None and abs((fl.get("atr_r") or 0) - r[ci["atr_r"]]) > 0.02:
            bad.append((r[0], "atr_r", r[ci["atr_r"]], fl.get("atr_r")))
    check(f"features: a 45-day live window gives the stored research features ({len(picks)} LIT trades, 2024 + 2026)", not bad, bad[:6])
    _ = pd


# ------------------------------------------------------------------------------------------------ 3. memory queries
def t_memory():
    S = MD.load_store()
    mem = MD.memory("lit", S, log_dir=tempfile.mkdtemp())
    j = 500
    f = {c: mem.rows[j][mem.ci[c]] for c in mem.num + mem.cat}
    q = mem.query(f)
    check("memory: a stored setup's own row is its nearest neighbour (distance 0), k = 15", q["idx"][0] == j and q["d"][0] < 1e-9 and q["n"] == 15, q)
    q2 = mem.query(f, exclude_day=mem.days[j])
    check("memory: exclude_day never returns that day", all(mem.days[i] != mem.days[j] for i in q2["idx"]))
    check("memory: deterministic", mem.query(f)["idx"] == q["idx"])
    s = MD.similar("lit", {"f": f, "what": "test"}, 300.0, S, MD.load_calib(), tempfile.mkdtemp())
    check("similar: contract fields; $ at today's size = avg R x today's risk; 3 examples",
          set(s) >= {"n", "win", "avg_r", "usd", "conf", "valid", "examples"} and abs(s["usd"] - round(s["avg_r"] * 300.0)) <= 1
          and len(s["examples"]) == 3, s)


# ------------------------------------------------------------------------------------------------ 4. regime + day type
def t_regime():
    H = full_hist()
    C = MD.load_calib()
    r1 = MD.regime(H, T("2026-10-14", 10, 50), C)
    r0 = MD.regime(H, T("2026-10-14", 9, 50), C)
    print("   10:50:", r1["label"], "|", r1["day_type"]["label"], "|", r1["why"])
    check("regime: label / trend / vol / why from structure + ATR + VIX", r1["trend"] in ("up", "down", "range") and r1["vol"] in ("high", "normal", "quiet")
          and "15m structure" in r1["why"] and "ATR" in r1["why"], r1)
    check("day type: odds from 10:30 ET (a probability), before 10:30 none, with the accuracy note",
          isinstance(r1["day_type"]["p_trend"], float) and 0 <= r1["day_type"]["p_trend"] <= 1 and r0["day_type"]["p_trend"] is None
          and "AUC" in r1["day_type"]["acc_note"], (r0["day_type"], r1["day_type"]))
    check("day type: none on a weekend", MD.regime(H, T("2026-10-10", 11, 0), C)["day_type"] is None)
    # the 10:30 features only use bars that closed by 10:30
    k = int(H.k_of[H.idx(T("2026-10-14", 10, 31))])
    x = MD.daytype_x(H, k)
    import pandas as pd
    df = _H["df"]
    cut = df[df["time"] + 300 <= T("2026-10-14", 10, 30)]
    Hc = MD.hist_from_frame(cut[cut["time"] >= T("2026-10-14", 10, 30) - 45 * 86400])
    xc = MD.daytype_x(Hc, int(Hc.k_of[Hc.idx(T("2026-10-14", 10, 30))]))
    check("day type: no look-ahead (features at 10:30 from bars cut at 10:30 = from the full file)",
          all(abs((x[c] or 0) - (xc[c] or 0)) < 1e-9 for c in MD.DT_FEATS), (x, xc))
    _ = pd


# ------------------------------------------------------------------------------------------------ 5. the block on a replayed day
def t_block_replay():
    from engine import brain as BR
    ld = tempfile.mkdtemp()
    now = T("2026-10-14", 1, 50)
    b = BR.replay("2026-10-14", now)
    bot = fake_bot(now, b)
    before = copy.deepcopy((bot.brain, bot.ledger))
    M = MD.Mind(log_dir=ld)
    t0 = time.perf_counter()
    blk = M.compute(bot, now)
    ms = (time.perf_counter() - t0) * 1000
    print(f"   compute {ms:.0f} ms (first, cold bars); err {M.err}")
    check("block: matches the contract", blk is not None and not MD.contract_errors(blk), MD.contract_errors(blk) if blk else M.err)
    check("block: Zlarior plan after 01:45 with two if-then scenarios (a sweep above = short, below = long), $ and odds",
          "lit" in blk["plans"] and len(blk["plans"]["lit"]["scenarios"]) == 2 and "SHORT" in blk["plans"]["lit"]["scenarios"][0]["then"]
          and blk["plans"]["lit"]["change_mind"], blk["plans"].get("lit"))
    sl = blk["similar"]["lit"]
    valid = MD.load_calib()["similar"]["lit"]["valid"]
    check("block: similar setups for Zlarior's forming setup; not predictive -> conf low + 'Context only'",
          sl is not None and sl["valid"] == valid and (valid or (sl["conf"] == "low" and "Context only" in sl["text"])), sl)
    pj = MD._jl_read(os.path.join(ld, "plans.jsonl"))
    check("plan: frozen once per bot per day in the journal (temp dir) + a narrator event", len(pj) == 1 and pj[0]["bot"] == "lit"
          and any(e["kind"] == "plan" for e in M.events), pj)
    M.key = None
    M.compute(bot, now + 300)
    check("plan: not frozen twice the same day", len(MD._jl_read(os.path.join(ld, "plans.jsonl"))) == 1)
    check("read-only: the bot's brain / ledger unchanged", copy.deepcopy((bot.brain, bot.ledger)) == before)
    c = MD.compact(blk)
    sz = len(json.dumps(c, separators=(",", ":"), default=str))
    check(f"compact: contract shape and < 12 KB ({sz} bytes)", not MD.contract_errors(c) and sz < 12_000, MD.contract_errors(c))
    sample = json.load(open(os.path.join(ROOT, "tests", "fixtures", "mind_sample.json"), encoding="utf-8"))
    check("the committed sample (tests/fixtures/mind_sample.json) matches the contract", not MD.contract_errors(sample), MD.contract_errors(sample))
    # 10:50: the regime has day-type odds; the BLITZ plan needs BLITZ's state (absent here) -> no BLITZ plan
    now2 = T("2026-10-14", 10, 50)
    b2 = BR.replay("2026-10-14", now2)
    blk2 = MD.Mind(log_dir=tempfile.mkdtemp()).compute(fake_bot(now2, b2), now2)
    check("10:50: day-type odds in the regime; no BLITZ plan without BLITZ's state", blk2["regime"]["day_type"]["p_trend"] is not None
          and "blitz" not in blk2["plans"] and not MD.contract_errors(blk2), blk2["regime"])
    return blk


# ------------------------------------------------------------------------------------------------ 6. reviews
def ledger_trade(et, xt, d=-1, entry=30785.75, stop=30862.0, target=30495.25, qty=1, pnl=579.48, reason="TARGET"):
    side = "buy" if d == 1 else "sell"
    return [{"t": et, "side": side, "entry_t": et, "qty": qty, "entry": entry, "stop": stop, "target": target, "result": {"ok": True}},
            {"t": xt, "side": "exit", "entry_t": et, "exit_t": xt, "qty": qty, "pnl": pnl, "reason": reason}]


def t_reviews():
    ld = tempfile.mkdtemp()
    et, xt = 1791969840, 1791986280                            # LIT's 2026-10-14 short (run lit_live, 05:24 ET): TARGET +3.8R
    now = T("2026-10-14", 16, 30)
    led = ledger_trade(et, xt)
    blz = {"ledger": [{"id": 1, "entry_t": T("2026-10-14", 11, 0), "exit_t": T("2026-10-14", 11, 31), "dir": 1, "entry": 30650.0,
                       "stop": 30620.0, "exit": 30630.0, "exit_kind": "stop", "r": -0.67, "qty": 4, "usd": -170.0}]}
    sec = {"strategies": {"ema_lon_vix": {"short": "EMA", "state": {"stage": "done"}, "trades": [
        {"day": "2026-10-14", "entry_t": T("2026-10-14", 4, 0), "exit_t": T("2026-10-14", 5, 0), "dir": -1, "entry": 30800.0,
         "stop": 30830.0, "target": 30700.0, "exit_kind": "BE", "r": 0.0, "usd": 0.0}]}}}
    bot = fake_bot(now, None, ledger=led, blitz=blz, second=sec)
    before = copy.deepcopy((bot.ledger, bot.blitz, bot.second))
    M = MD.Mind(log_dir=ld)
    blk = M.compute(bot, now)
    R = {r["bot"]: r for r in blk["reviews"]}
    print("   reviews:", {k: (v["grade"], v["luck"], v["why"]) for k, v in R.items()})
    check("reviews: one per closed trade (Zlarior real, ATLAS member paper, BLITZ paper), grade A-F, luck / skill, lesson",
          set(R) == {"lit", "atlas", "blitz"} and all(v["grade"] in "ABCDF" and v["luck"] in ("luck", "skill", "mixed") and v["lesson"]
                                                      for v in R.values()), blk["reviews"])
    check("review: the +3.8R target winner that followed the plan grades A or B", R["lit"]["grade"] in ("A", "B") and abs(R["lit"]["r"] - 3.8) < 0.05,
          R["lit"])
    check("review: the BLITZ stop-out grades below the LIT winner", "ABCDF".index(R["blitz"]["grade"]) > "ABCDF".index(R["lit"]["grade"]), R["blitz"])
    js = MD._jl_read(os.path.join(ld, "reviews.jsonl"))
    lr = MD.live_rows("lit", ld)
    check("journal: reviews in <log>/reviews.jsonl; the closed trade joins the memory (<log>/lit_live.jsonl, store columns)",
          len(js) == 3 and len(lr) == 1 and len(lr[0]) == len(MD.load_store()["bots"]["lit"]["cols"]), (len(js), lr))
    M.key = None
    M.compute(bot, now + 300)
    M2 = MD.Mind(log_dir=ld)
    M2.compute(bot, now + 600)
    check("reviews: never twice (same Mind, and a restart reading the journal)", len(MD._jl_read(os.path.join(ld, "reviews.jsonl"))) == 3)
    mem = MD.memory("lit", MD.load_store(), ld)
    check("memory: includes the live row", len(mem.rows) == len(MD.load_store()["bots"]["lit"]["rows"]) + 1)
    check("read-only: ledgers / paper runs unchanged", copy.deepcopy((bot.ledger, bot.blitz, bot.second)) == before)
    check("reviews: narrator events kind review (today's trades)", sum(1 for e in M.events if e["kind"] == "review") == 3)


# ------------------------------------------------------------------------------------------------ 7. self-research
def t_research():
    ld = tempfile.mkdtemp()
    t0 = time.perf_counter()
    out = MD.research(600, log_dir=ld, now=T("2026-10-29", 16, 10))
    took = time.perf_counter() - t0
    st = {p["status"] for p in out["proposals"]}
    print(f"   research on the real store: {out['tested']} tests in {took:.2f} s; statuses {sorted(st)}; "
          f"{sum(p['status'] == 'candidate' for p in out['proposals'])} candidates")
    for o in out["observations"][:4]:
        print("     noticed:", o["text"])
    check("research: observations -> hypotheses -> tests, statuses testing / candidate / rejected, << 10 min",
          out["tested"] > 0 and st <= {"testing", "candidate", "rejected"} and took < 600 and out["observations"], out["observations"][:2])
    check("research: every proposal carries H1 / H2 / 2021-25 evidence and $ a month; only candidates carry a change",
          all(p["evidence"]["h1"] and p["evidence"]["h2"] and (p["change"] is None) == (p["status"] != "candidate") for p in out["proposals"]))
    check("research: written to the log dir (proposals.json), nothing else", sorted(os.listdir(ld)) == ["proposals.json"], os.listdir(ld))
    # a synthetic store where London trades lose in both halves and 2021-25 -> a candidate; LIT judged on the 2026 halves only
    cols = MD.ROW0 + ["kz", "mod", "qty", "dow", "tr1h"]
    rows = []
    for i in range(400):
        d = str(np.datetime64("2026-01-05") + np.timedelta64(i % 280, "D")) if i < 280 else str(np.datetime64("2024-01-08") + np.timedelta64(i - 280, "D"))
        lon = i % 3 == 0
        r = -1.0 if lon else (2.0 if i % 4 else -1.0)
        r5 = (1.0 if lon else r) if d < "2026" else r                     # 2021-25: London does fine
        t = int(np.datetime64(d, "s").astype(np.int64)) + 14 * 3600
        rows.append([d, t, 1, r5, r5 * 100.0, "X", "t", "london" if lon else "ny_am", 600 if lon else 900, 2, 1, 1])
    st2 = {"bots": {"lit": {"cols": cols, "rows": rows}, "atlas": {"cols": cols, "rows": rows}}}
    o2 = MD.research(60, store=st2, log_dir=tempfile.mkdtemp(), now=T("2026-10-29", 16, 10))
    P = {p["id"]: p for p in o2["proposals"]}
    lit_c = [p for p in o2["proposals"] if p["bot"] == "lit" and p["status"] == "candidate"]
    atl_c = [p for p in o2["proposals"] if p["bot"] == "atlas" and p["status"] == "candidate"]
    print("   synthetic:", [(k, v["status"]) for k, v in P.items()][:8])
    check("research: a rule that helps both 2026 halves is a LIT candidate with the exact change to approve (never adopted)",
          any("london" in p["id"] for p in lit_c) and all("approves" in (p["change"] or "") for p in lit_c), lit_c[:1])
    check("research: the same rule is rejected for ATLAS because it hurts 2021-25", not any("london" in p["id"] for p in atl_c), atl_c[:1])
    # the shipped seed proposals (the first research run) match the contract
    seed = MD._read_json(MD.SEED_PROPOSALS) or {}
    check("seed proposals: committed, contract shape", seed.get("proposals") is not None and
          not MD.contract_errors({**MD.skeleton(1), "proposals": seed["proposals"][:12]}), MD.contract_errors({**MD.skeleton(1), "proposals": seed.get("proposals") or []}))


# ------------------------------------------------------------------------------------------------ 8. hooks + wiring
def t_hooks(blk):
    from engine import narrator as N
    ld = tempfile.mkdtemp()
    M = MD.Mind(log_dir=ld)
    now = T("2026-10-14", 16, 10)
    bot = fake_bot(now, None)
    spawned = []
    orig = MD.spawn_research
    MD.spawn_research = lambda budget, log_dir=None: spawned.append((budget, log_dir)) or 4242
    try:
        t0 = time.perf_counter()
        s1 = MD.pc_tick(bot, now, mind=M)
        dt_ms = (time.perf_counter() - t0) * 1000
        M.thread.join(30) if M.thread else None
        s2 = MD.pc_tick(bot, now + 30, mind=M)
        MD.pc_tick(bot, now + 400, mind=M)
        M.thread.join(30) if M.thread else None
    finally:
        MD.spawn_research = orig
    print(f"   pc_tick on the poll thread: {dt_ms:.1f} ms (starts the thread only)")
    check("pc_tick: starts one background compute per 5m bar, returns at once", s1 is True and s2 is False and dt_ms < 50, (s1, s2, dt_ms))
    check("pc_tick: after 16:05 ET the nightly research starts once a day (budget 600 s, low priority child)",
          spawned == [(600, ld)] and MD._read_json(os.path.join(ld, "research_last.json"))["day"] == "2026-10-14", spawned)
    os.environ["LE_MIND"] = "0"
    try:
        check("LE_MIND=0 switches Mind off", MD.pc_tick(bot, now + 900, mind=M) is None)
    finally:
        os.environ.pop("LE_MIND", None)
    src = open(os.path.join(ROOT, "engine", "mind.py"), encoding="utf-8").read()
    imp = re.findall(r"^\s*(?:from\s+\S+\s+)?import\s+([^\n]+)", src, re.M)
    bad = [x for x in imp if re.search(r"ninjatrader|tradovate|adapter|account_b|account_c|accounts\b|autopilot|golive", x)]
    check("read-only: engine/mind.py imports no broker / order / account module", not bad, bad)
    check("no external model / paid API in engine/mind.py", not re.search(r"openai|anthropic|requests\.post|urllib\.request", src))
    # narrator: Mind events become kind "brain" messages; never pushed by default
    M.events.clear()
    M._event("mind:plan:lit:2026-10-14", T("2026-10-14", 1, 45), "lit", "plan", "Zlarior game plan", "IF ... THEN ...")
    orig_m = MD.MIND
    MD.MIND = M
    try:
        msgs, _ = N.derive(SimpleNamespace(ledger=[], brain=None, clock=lambda: now, cfg={}), now, {})
        bm = [m for m in msgs if m["kind"] == "brain"]
        v = None
        try:
            from engine import liveview_api as LV
            LV.CSV_FALLBACK = False
            M.block = blk
            v = LV.view(fake_bot(now, None), "1m", now, narr=N.Narrator())
            pv = LV.phone_view(fake_bot(now, None), now, narr=N.Narrator())
        finally:
            M.block = None
    finally:
        MD.MIND = orig_m
    check("narrator: Mind's plan as kind 'brain' (strat lit), push off by default", len(bm) == 1 and bm[0]["strat"] == "lit"
          and N.push_prefs().get("brain") is False, bm)
    check("liveview view()['mind'] = the cached block; phone_view gets the compact cut", v is not None and v.get("mind") is blk
          and pv.get("mind", {}).get("compact") is True, (v or {}).get("mind") is blk)
    from engine import heartbeat as HB
    orig_m = MD.MIND
    MD.MIND = MD.Mind(log_dir=tempfile.mkdtemp())
    try:
        none_before = HB._mind(bot) is None
        MD.MIND.block = blk
        hb = HB._mind(bot)
    finally:
        MD.MIND = orig_m
    hb_sz = len(json.dumps(hb, separators=(",", ":"), default=str)) if hb else 0
    check(f"heartbeat 'mind': absent before the first compute, compact after ({hb_sz} bytes < 12 KB)", none_before and hb and hb_sz < 12_000)
    # the API answer (no bars -> a skeleton block, the calibration report, never raises)
    a = MD.api_view(fake_bot(now, None), now, mind=MD.Mind(log_dir=tempfile.mkdtemp()))
    check("GET /api/next/mind: block + history + calibration, read-only note", {"block", "history", "calibration", "read_only"} <= set(a)
          and not MD.contract_errors(a["block"]), MD.contract_errors(a["block"]))
    check("server.py mounts the Mind router with one line", "from engine.mind import router as mind_router; app.include_router(mind_router)"
          in open(os.path.join(ROOT, "server.py"), encoding="utf-8").read())


def t_never_raises():
    """Junk everywhere (a broken brain, odd ledgers, a half BLITZ state, no bars): compute still returns a contract block or
    None, pc_tick / view_block / compact / api_view never raise."""
    now = T("2026-10-14", 10, 50)
    junk = [
        fake_bot(now, "garbage"),
        fake_bot(now, {"setups": [{"t": "x", "dir": "?"}, None, 5], "watch": [{"swept": ["x"], "dir": None}], "levels": [{"price": "?"}],
                       "stage": {"key": "trade"}}, ledger=[{"side": "exit"}, {"t": "bad"}, None], second={"strategies": {"ema_x": None, "macd": {"state": None}}},
                 blitz={"eng": {"date": "x"}, "ledger": [{"exit_kind": "OPEN"}], "signals": [{"t": None}]}),
        fake_bot(now, {}, bars_tail=[[1, 2, 3]], _lit_1m_store="not a frame"),
    ]
    ok = True
    errs = []
    for b in junk:
        try:
            M = MD.Mind(log_dir=tempfile.mkdtemp())
            blk = M.compute(b, now)
            if blk is not None and MD.contract_errors(blk):
                ok = False
                errs.append(MD.contract_errors(blk))
            MD.compact(blk)
            MD.view_block(b, now, M)
            MD.pc_tick(b, now, background=False, spawn=False, mind=MD.Mind(log_dir=tempfile.mkdtemp()))
            MD.api_view(b, now, mind=MD.Mind(log_dir=tempfile.mkdtemp()))
        except Exception as e:
            ok = False
            errs.append(f"{e.__class__.__name__}: {e}")
    check("never raises: junk brains / ledgers / paper states / bars -> a contract block or None", ok, errs)
    CSV0 = MD.CSV_HIST
    MD.CSV_HIST = False
    try:
        blk = MD.Mind(log_dir=tempfile.mkdtemp()).compute(fake_bot(now, None), now)
    finally:
        MD.CSV_HIST = CSV0
    check("no bars at all: the regime says so, the block keeps the contract", blk is not None and blk["regime"]["label"] == "No bars yet"
          and not MD.contract_errors(blk), (blk or {}).get("regime"))


def t_compact_cap():
    big = MD.skeleton(1)
    rv = {"t": 1, "bot": "lit", "trade": "x" * 100, "grade": "B", "right": ["r" * 300] * 5, "wrong": ["w" * 300] * 5, "lesson": "l" * 900, "luck": "mixed"}
    big["reviews"] = [rv] * 50
    big["proposals"] = [{"id": f"p{i}", "bot": "lit", "idea": "i" * 400, "evidence": {"h1": "h" * 400, "h2": "h" * 400, "r2125": "h" * 400, "usd_month": 1.0},
                         "status": "rejected", "t": 1, "change": None} for i in range(60)]
    big["alerts"] = [{"t": 1, "bot": "lit", "text": "a" * 400, "level": "info"}] * 30
    big["plans"] = {k: {"t": 1, "headline": "h" * 900, "change_mind": "c" * 900,
                        "scenarios": [{"if": "i" * 900, "then": "t" * 900, "levels": [1.0, 2.0], "exp_usd": None, "odds": None}] * 6} for k in MD.BOTS}
    c = MD.compact(big)
    sz = len(json.dumps(c, separators=(",", ":"), default=str))
    check(f"compact: a huge block still fits under 12 KB ({sz} bytes) and keeps the contract", sz < 12_000 and not MD.contract_errors(c), MD.contract_errors(c))


def main():
    t_store_calibration()
    t_validation_machinery()
    t_feature_parity()
    t_memory()
    t_regime()
    blk = t_block_replay()
    t_reviews()
    t_research()
    t_hooks(blk)
    t_never_raises()
    t_compact_cap()
    n, ok = len(RES), sum(RES)
    print(f"\nmind: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
