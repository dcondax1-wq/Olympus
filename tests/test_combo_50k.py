"""ATLAS + Zlarior on ONE account, the Builder 50K (engine/combo50k.py; built, OFF by default). Sim / fake NinjaTrader only
(engine/ninjatrader._FakeNT on a temp folder, ONE account Sim101 = the 50K); nothing is ever armed for a real account and
neither data/combo_50k.json nor research/lab/combo_50k.json is written (the start cfg "combo_50k" switches the harness on).

    python -X utf8 -m tests.test_combo_50k            # units + the parity replay (2 eval segments, 9 sessions) + d (~15-25 min)
    python -X utf8 -m tests.test_combo_50k --quick    # units + one segment (5 sessions)
    python -X utf8 -m tests.test_combo_50k --units    # unit checks only (~20 s)
    python -X utf8 -m tests.test_combo_50k --extra    # units + e only (the extra accounts, ~4 min)
    python -X utf8 -m tests.test_combo_50k --full     # + Aug 18 - Sep 1 (a 3rd eval, 9 more sessions)
    python -X utf8 -m tests.test_combo_50k --seg 2026-10-02 [--scenario]   # units + that segment (+ d); run_area nq: by parts

 a. OFF = today: no switch file -> combo50k.build None; LiveBot.combo None; the guards' day counts / texts unchanged; the
    switch refuses without the typed phrase, a real Name without the Decide card's yes, a failing self-test, ATLAS's own 25K.
 b. ATLAS's raw stream (combo50k.atlas_pick == tools/money/combo_account._atlas_rows: one ATLAS trade at a time, 2 a day,
    member order on a tie); ATLAS's size on the 50K = engine/account_b.qty builder50k on the shared state x the factor
    (== the reference Book.size); the conflict rules first_in / lit_priority / close_on_opposite on Zlarior's entry; ATLAS's
    one-position lock (position, Zlarior entering, an order working at NinjaTrader) and the ONE-direction lock (account B,
    extra accounts, followers); the alert / board text "ATLAS on Zlarior 50K: LONG opened".
 c. PARITY (the "make it work" guarantee): 2026 sessions fed bar by bar through the REAL LiveBot (LIT's lit_live loop +
    ATLAS's engine/second members, fake NinjaTrader, both bots on one Sim 50K, a fresh eval per segment, the bot restarted
    every morning on the same state) == tools/money/combo_account.Eval on the same days: the same entries taken and skipped,
    the same micros, the same exits and $, the same eval end; never two positions, never more than one bracket working.
    Default segments (both bots signal and conflict): Sep 2-10 with the RESEARCH RULES research/lab/combo_50k.json
    (night-comboplus a50_eval: first in, ATLAS x0.5 in the eval = the simulator's max(1, floor(0.5 q)); Zlarior first, ATLAS
    long skipped; ATLAS long first, Zlarior short skipped; 3 signals on Sep 9) and Oct 2-7 with the main-branch study
    (first in, ATLAS x1.0: ATLAS first 3 times, Zlarior skipped same side and opposite, the eval passes Oct 7).
    --full adds Aug 18 - Sep 1 and Oct 2-7 at a50, Sep 2-10 at x1.0, and Sep 2-10 with this build's optional guard
    atlas_lit_armed_block (off in the research rules): a signal the bot masks for it must say so in the log; the reference
    is then re-run without that one ATLAS trade (the cascade included).
 d. close_on_opposite on Sep 4: ATLAS's long is closed at market (LIT PRIORITY) before Zlarior's short goes out; the fake
    50K never holds more than one trade.
 e. (every replay mode but the run_area "sep" part) the multi_account router's extra accounts (Zlarior 25K #2, Rapid EOD 25K, paper): ATLAS's combo
    entry on the 50K never reaches them, only Zlarior's own LIT signals do (Oct 2: the same-side one skipped on the 50K is
    routed there, as today; Sep 4: the opposite one is refused on every account).
 f. (units) the fleet: a Zlarior follower copies Zlarior's own trades only, never ATLAS's combo trade on the 50K (the
    'zlarior' lead snapshot drops ledger rows "combo"); the 50K's ATLAS position still counts for the no-hedge view.
Results -> research/lab/combo_50k_check.json.
"""
from __future__ import annotations

import collections
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import account_b as AB  # noqa: E402
from engine import combo50k as CB  # noqa: E402
from engine import guards as G  # noqa: E402
from engine import live  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from tests import test_second_route as TR  # noqa: E402
from tests.test_second_route import Harness, at, hm  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "combo_50k_check.json")
RESULTS = TR.RESULTS
check = TR.check
RULES_FILE = os.path.join(ROOT, CB.RULES_REL)


def research_cfg() -> dict:
    """research/lab/combo_50k.json as the live bot reads it (night-comboplus pick a50_eval: first in, ATLAS x0.5 in the eval,
    x1.0 funded, every eval guard off); absent -> the same values written out."""
    try:
        return json.load(open(RULES_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"conflict": "first", "atlas_size_factor": {"eval": 0.5, "funded": 1.0}, "variant": "a50_eval",
                "guards": {"atlas_in_eval": True, "atlas_eval_min_room_usd": None, "eval_day_stop_usd": None, "one_position": True,
                           "soft_day_usd_both_bots": 1000.0, "max_micros": 40, "flat_by": "16:10 ET"}}


# (start, end, the bot's rules, the reference's ATLAS eval share, its label)
A50 = "a50"            # the research rules (combo_50k.json): ATLAS x0.5 in the eval
STUDY = "study"        # the main-branch study: first in, ATLAS x1.0
ARMED = "armed"        # the study + this build's optional atlas_lit_armed_block guard (a mask must name it; the reference re-run)
CASES = {A50: (lambda: research_cfg(), 0.5), STUDY: (lambda: {"conflict": "first", "atlas_size_factor": 1.0}, 1.0),
         ARMED: (lambda: {"conflict": "first", "atlas_size_factor": 1.0, "guards": {"atlas_lit_armed_block": True}}, 1.0)}
SEGMENTS = {"quick": [("2026-09-02", "2026-09-10", A50)],
            "default": [("2026-09-02", "2026-09-10", A50), ("2026-10-02", "2026-10-07", STUDY)],
            "full": [("2026-08-18", "2026-09-01", A50), ("2026-09-02", "2026-09-10", A50), ("2026-10-02", "2026-10-07", STUDY),
                     ("2026-09-02", "2026-09-10", STUDY), ("2026-09-02", "2026-09-10", ARMED), ("2026-10-02", "2026-10-07", A50)]}


# ================================================================================================ the reference
class Reference:
    """tools/money/combo_account: the study's trade table + its Eval book (Builder 50K, Zlarior + ATLAS, own sizing, first-in)."""

    def __init__(self):
        import combo_account as C
        self.C = C
        C.trades()
        self.S = C.sessions()
        self.D = C.combo_days("Z+A")

    def book(self, a_f=1.0):
        """The study's Eval book; a_f < 1 = ATLAS's share of its own size in the eval (night-comboplus a50_eval). The
        simulator after the merge takes it as the cell's "a_f"; on a branch without it the same rule is applied here,
        word for word: q = max(1, floor(a_f x q)) on every ATLAS size (tools/money/combo_account.Book.trade_day)."""
        import math
        C = self.C
        cell = {**C.R("b50", "Z+A"), "conflict": "first", "a_f": {"eval": a_f, "funded": 1.0}}
        ev = C.Eval(cell, "Z+A")
        if a_f < 1.0 and not hasattr(ev, "a_f"):
            base = ev.size

            def size(t, room, cum, st, base=base):
                q = base(t, room, cum, st)
                return max(1, int(math.floor(a_f * q + 1e-9))) if t["s"] == "A" and q > 0 else q
            ev.size = size
        return ev

    def segment(self, a, z, drop=frozenset(), a_f=1.0):
        """Real sessions a..z in order on ONE fresh eval (ends at pass / fail / stuck). drop = {(s, et)} not fed (masked
        live by a declared guard). -> (rows [(day, s, et, d, q, pnl, x)], cands {day: [trade]}, end (day, result) | None)."""
        ev = self.book(a_f)
        rows, cands, end = [], {}, None
        for si, day in enumerate(self.S):
            if day < a or day > z:
                continue
            ts = [t for t in self.D[si] if (t["s"], int(t["et"])) not in drop]
            cands[day] = list(self.D[si])
            keep = []
            r, _ = ev.step(ts, keep)
            for t, q, pnl in keep:
                rows.append((day, t["s"], int(t["et"]), int(t["d"]), int(q), round(float(pnl), 2), t["x"], int(t["xt"])))
            if r:
                end = (day, r)
                break
        return rows, cands, end


# ================================================================================================ unit checks
def units():
    print("unit checks: rules, switch, ATLAS stream, sizing, conflict rules, locks, alert text, fleet", flush=True)
    fleet_checks()
    tmp = tempfile.mkdtemp(prefix="le_combo_units_")
    try:
        # a. off = today
        n0 = CB.normalize({})
        check("a. rules: no file -> first_in, ATLAS size x1.0, armed-opposite block off, ATLAS 2 a day, $200 stop line",
              n0["conflict"] == "first_in" and n0["atlas_size_factor"] == {"eval": 1.0, "funded": 1.0}
              and n0["guards"]["atlas_lit_armed_block"] is False
              and n0["guards"]["atlas_max_per_day"] == 2 and n0["guards"]["atlas_min_room"] == 200.0 and not n0["problem"], n0)
        check("a. rules: bad conflict / factor refused, unknown guard keys listed, a 'rules' sub-dict read",
              CB.normalize({"conflict": "both"})["problem"] and CB.normalize({"atlas_size_factor": 3})["problem"]
              and CB.normalize({"guards": {"zzz": 1}})["unknown"] == ["zzz"]
              and CB.normalize({"rules": {"conflict": "lit_priority"}})["conflict"] == "lit_priority")
        rf = CB.normalize(research_cfg())
        check("a. the research file research/lab/combo_50k.json (night-comboplus a50_eval): conflict first = first_in, ATLAS x0.5 "
              "eval / x1.0 funded, null guards off, one position, $1,000 both bots, 40 micros, no problem, no unknown key",
              rf["conflict"] == "first_in" and rf["atlas_size_factor"] == {"eval": 0.5, "funded": 1.0} and not rf["problem"]
              and not rf["unknown"] and rf["guards"]["atlas_eval_min_room_usd"] is None and rf["guards"]["eval_day_stop_usd"] is None
              and rf["guards"]["atlas_in_eval"] is True and rf["guards"]["soft_day_usd_both_bots"] == 1000.0
              and rf["guards"]["max_micros"] == 40 and os.path.exists(RULES_FILE), rf)
        check("a. rules: aliases zprio = close_on_opposite, zfull = lit_priority; a number factor = both stages; one_position false "
              "/ another account / a bot list without ATLAS refused",
              CB.normalize({"conflict": "zprio"})["conflict"] == "close_on_opposite" and CB.normalize({"conflict": "zfull"})["conflict"] == "lit_priority"
              and CB.normalize({"atlas_size_factor": 0.75})["atlas_size_factor"] == {"eval": 0.75, "funded": 0.75}
              and CB.normalize({"guards": {"one_position": False}})["problem"] and CB.normalize({"account": "builder25k"})["problem"]
              and CB.normalize({"bots": ["lit"]})["problem"])
        check("a. the switch: no data/combo_50k.json in a fresh root -> off", CB.read_switch(tmp) == {"on": False})

        class FB:
            pass
        fb = FB()
        fb.cfg, fb.state_path, fb.adapter = {"nt_account": "Sim101"}, live.STATE_PATH, None
        real_sw = CB.read_switch()
        check("a. the real bot with no switch file (this repo): build() = None (combo OFF)",
              CB.build(fb) is None if not real_sw.get("on") else True, real_sw)
        fb.cfg = {"nt_account": "Sim101", "combo_50k": {"conflict": "first_in"}}
        check("a. a harness start cfg never switches the REAL bot on", CB.build(fb) is None if not real_sw.get("on") else True)
        fb.state_path = os.path.join(tmp, "live_state.json")
        sp = CB.build(fb)
        check("a. a harness (own state file) with the start cfg: on, first_in, the 3 ATLAS members", bool(sp and sp.get("on"))
              and sp["conflict"] == "first_in" and sp["keys"] == list(CB.MEMBERS), sp)
        ok = lambda: (True, "ok")
        bad = lambda: (False, "FAILED 3/90")
        r0 = CB.set_on("Sim101", "yes please", root=tmp, selftest=ok)
        r1 = CB.set_on("Sim101", "i accept   live risk", root=tmp, selftest=bad)
        r2 = CB.set_on("MFFU50K-REAL", "I ACCEPT LIVE RISK", root=tmp, selftest=ok)
        check("a. switch ON refused: no typed phrase / failing self-test / a real Name before the Decide card's yes",
              not r0["ok"] and "phrase" in r0["error"] and not r1["ok"] and "selftest" in r1["error"] and not r2["ok"]
              and CB.DECIDE_ID in r2["error"] and CB.read_switch(tmp) == {"on": False}, (r0, r1, r2))
        r3 = CB.set_on("Sim101", "I ACCEPT LIVE RISK", root=tmp, selftest=ok, today="2026-11-20")
        sw = CB.read_switch(tmp)
        r4 = CB.set_off(root=tmp, today="2026-11-21")
        check("a. switch ON for Sim101 with the phrase + self-test (no Decide needed for Sim), OFF again",
              r3["ok"] and sw["on"] and sw["account"] == "Sim101" and sw["sim"] is True and r4["ok"] and not CB.read_switch(tmp)["on"],
              (r3, sw))
        os.makedirs(os.path.join(tmp, "tools", "web_public", "business"), exist_ok=True)
        with open(os.path.join(tmp, CB.DECISIONS_REL), "w", encoding="utf-8") as fh:
            json.dump({"items": [{"id": CB.DECIDE_ID, "status": "yes"}]}, fh)
        r5 = CB.set_on("MFFU50K-REAL", "I ACCEPT LIVE RISK", root=tmp, selftest=ok, today="2026-11-22")
        check("a. a real 50K Name: ON only after the Decide card says yes (+ the phrase)", r5["ok"] and CB.read_switch(tmp)["sim"] is False, r5)
        # guards: off = the old day counts and text
        class GB:
            pass
        gb = GB()
        gb.cfg, gb.ledger, gb._second_routed, gb.state = {"guards": {}}, [], [], {}
        c0 = G.config(gb)
        gb._second_routed = ["ema_lon_vix"]
        c1 = G.config(gb)
        gb.combo = {"guards": {"atlas_max_per_day": 2}}
        c2 = G.config(gb)
        check("a. guards: combo off = max 1 / 2 a day as before (no second_max); on = Zlarior 1 + ATLAS 2 = 3",
              c0["max_per_day"] == 1 and "second_max" not in c0 and c1["max_per_day"] == 2 and "second_max" not in c1
              and c2["max_per_day"] == 3 and c2["second_max"] == 2, (c0["max_per_day"], c1["max_per_day"], c2.get("max_per_day")))
        t0 = at("2026-10-01", 4, 0)
        gb.ledger = [{"side": "buy", "entry_t": t0, "src": "ema_lon_vix", "t": t0}]
        p1 = G.dup_problem(gb, t0 + 3600, c2, {}, src="macd_sweep")
        gb.ledger.append({"side": "sell", "entry_t": t0 + 3600, "src": "macd_sweep", "t": t0 + 3600})
        p2 = G.dup_problem(gb, t0 + 7200, c2, {}, src="sr_nyreclaim")
        p3 = G.dup_problem(gb, t0 + 7300, c2, {}, src=None)
        del gb.combo
        p4 = G.dup_problem(gb, t0 + 7400, {**c1, "max_per_day": 5}, {}, src="sr_nyreclaim")
        check("a. guards: ATLAS's 2nd entry on the 50K allowed, a 3rd refused, Zlarior's own 1 still free; off text unchanged",
              p1 is None and p2 and "ATLAS max 2" in p2 and p3 is None and p4 == "2 second-strategy entry already routed today (max 1 a day: the other slot is LIT's)",
              (p1, p2, p3, p4))
        gb.combo = {"guards": {**CB.GUARD_DEFAULTS, "eval_day_stop_usd": 400.0, "soft_day_usd_both_bots": 800.0}}
        gb._combo_stage = lambda: "eval"
        c3 = G.config(gb)
        gb._combo_stage = lambda: "funded"
        c4 = G.config(gb)
        check("a. guards: soft_day_usd_both_bots lowers the soft daily loss both bots count against; eval_day_stop_usd only in "
              "the eval (null = off)", c3["daily_loss_usd"] == 800.0 and c3.get("combo_day_stop") == 400.0
              and "combo_day_stop" not in c4 and "combo_day_stop" not in c2 and c2["daily_loss_usd"] == 1000.0, (c3, c4))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # b. ATLAS's stream = combo_account._atlas_rows
    def tr(k, et_, xt, d=1, open_=False):
        return {"day": "2026-09-09", "entry_t": et_, "exit_t": None if open_ else xt, "dir": d, "exit_kind": "OPEN" if open_ else "TARGET",
                "target": 1.0, "entry": 0.0, "stop": 0.0}
    b0 = at("2026-09-09", 3, 0)
    run = {"strategies": {"ema_lon_vix": {"trades": [tr("e", b0, b0 + 1800)]},
                          "macd_sweep": {"trades": [tr("m", b0 + 900, b0 + 2400), tr("m", b0 + 3600, 0, open_=True)]},
                          "sr_nyreclaim": {"trades": [tr("s", b0 + 1800, b0 + 2100), tr("s", b0 + 3600, 0, -1, open_=True)]}}}
    pk, why, sg = CB.atlas_pick(run, list(CB.MEMBERS), b0 + 3600, "2026-09-09")
    check("b. ATLAS stream: EMA 03:00, MACD 03:15 skipped (EMA open), S/R 03:30 = 2nd -> the 04:00 signals are past 2 a day",
          pk is None and "2 trades today" in (why or "") and len(sg) == 2, (pk, why))
    run["strategies"]["sr_nyreclaim"]["trades"] = [tr("s", b0 + 3600, 0, -1, open_=True)]
    pk, why, sg = CB.atlas_pick(run, list(CB.MEMBERS), b0 + 3600, "2026-09-09")
    check("b. ATLAS stream: a tie at 04:00 -> the member order (MACD before S/R)", pk is not None and pk[0] == "macd_sweep", (pk, why))
    pk, why, sg = CB.atlas_pick({"strategies": {"ema_lon_vix": {"trades": [tr("e", b0, 0, open_=True), tr("e", b0 + 300, 0, open_=True)]}}},
                                list(CB.MEMBERS), b0 + 300, "2026-09-09")
    check("b. ATLAS stream: its own earlier trade still OPEN -> busy", pk is None and "still open" in (why or ""), why)
    ok, bad_ = _stream_parity()
    check(f"b. ATLAS stream on the stored member trades == combo_account._atlas_rows for 2026 ({ok} trades)", not bad_, bad_[:5])

    # b. ATLAS's size = the reference Book.size (engine/account_b.qty, builder50k)
    import combo_account as C
    C.trades()
    bk = C.Eval(C.R("b50", "Z+A"), "Z+A")
    spec = {"on": True, "account": "Sim101", "atlas_size_factor": {"eval": 1.0, "funded": 1.0}, "guards": dict(CB.GUARD_DEFAULTS),
            "max_micros": 40}
    A = [t for ts in C.trades() for t in ts if t["s"] == "A" and t["day"] >= "2026-01-01"][:80]
    diff = []
    for i, t in enumerate(A):
        st = {"profit": [0.0, 900.0, -1200.0, 2500.0][i % 4], "cum": [0.0, -300.0, 450.0, 0.0][i % 4], "room": [2000.0, 1100.0, 650.0, 2900.0][i % 4],
              "session": 1 + i % 12, "n_today": i % 2, "wk_pnl": 0.0, "days_traded": i % 5}
        a = CB.atlas_qty(spec, {"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, st, "2026-01-02")["qty"]
        b = bk.size(t, st["room"], st["cum"], st)
        if a != b:
            diff.append((t["day"], t["risk"], st["room"], a, b))
    check(f"b. ATLAS's micros on the 50K == the study's Book.size (account_b.qty builder50k) on {len(A)} trades x 4 states", not diff, diff[:4])
    s2 = {**spec, "atlas_size_factor": {"eval": 0.5, "funded": 1.0}}
    st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "wk_pnl": 0.0, "days_traded": 0}
    q1 = CB.atlas_qty(spec, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    q2 = CB.atlas_qty(s2, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    q3 = CB.atlas_qty({**spec, "atlas_size_factor": {"eval": 2.0, "funded": 1.0}}, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")
    q4 = CB.atlas_qty({**spec, "guards": {**spec["guards"], "atlas_max_risk_usd": 200.0}}, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    loss1 = (20.0 + 0.5) * 2 + 1.9
    import math
    halves = [(n, max(1, int(math.floor(0.5 * n + 1e-9)))) for n in range(1, 41)]
    pairs, bad_r = [], []
    for room in (60.0, 120.0, 300.0, 700.0, 1500.0, 2400.0):
        stx = {**st, "room": room, "profit": 3000.0 - 0.9 * room}
        for rp in (6.0, 14.0, 33.0):
            a1 = CB.atlas_qty(spec, {"risk_pts": rp, "tgt_pts": 8 * rp}, stx, "2026-01-02")["qty"]
            a5 = CB.atlas_qty(s2, {"risk_pts": rp, "tgt_pts": 8 * rp}, stx, "2026-01-02")["qty"]
            pairs.append((a1, a5))
            if a5 != (max(1, int(math.floor(0.5 * a1 + 1e-9))) if a1 > 0 else 0):
                bad_r.append((room, rp, a1, a5))
    z0 = CB.atlas_qty({**spec, "atlas_size_factor": {"eval": 0.0, "funded": 1.0}}, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")
    check(f"b. eval x0.5 = the simulator's rounding max(1, floor(0.5 q)) on 18 sizes ({sorted(set(pairs))[:6]}...); funded x1.0; "
          "a factor 0 = no trade", not bad_r and any(a1 == 1 for a1, _ in pairs) and CB.factor_of(s2, "funded") == 1.0
          and z0["qty"] == 0, (bad_r, pairs))
    check(f"b. atlas_size_factor 0.5 halves ({q1} -> {q2}); x2 stays inside 60% room + the $1,000 day + 40 micros; risk cap $200",
          q2 == max(1, int(q1 * 0.5)) and q3["qty"] <= 40 and q3["qty"] * loss1 <= 1000.0 + 1e-6 and q3["qty"] * loss1 <= 0.6 * 2000 + 1e-6
          and q4 == int(200.0 / loss1), (q1, q2, q3, q4))
    check("b. no eval state -> 0 (fails closed)", CB.atlas_qty(spec, {"risk_pts": 20.0, "tgt_pts": 160.0}, None, "2026-01-02")["qty"] == 0)

    # b. conflict rules + locks on a LiveBot with no data (pure state)
    lb = live.LiveBot()
    now = at("2026-09-04", 3, 30)
    lb.clock = lambda: now
    lb.cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper"}
    lb.state_path = os.path.join(tempfile.gettempdir(), "le_combo_unit_state.json")
    tb = at("2026-09-04", 3, 10)
    lb._open_routed, lb._open_src = tb, "ema_lon_vix"
    lb._second_prov = {tb: {"key": "ema_lon_vix", "short": "EMA", "dir": 1, "combo": True, "qty": 9, "day": "2026-09-04"}}
    zs, zl = {"entry_t": now, "dir": -1}, {"entry_t": now, "dir": 1}
    res = {}
    for rule in CB.CONFLICTS:
        lb.combo = {"conflict": rule, "guards": dict(CB.GUARD_DEFAULTS)}
        res[rule] = (bool(lb._combo_lit_skip(zs)), bool(lb._combo_lit_skip(zl)))
    check("b. Zlarior's entry while ATLAS holds the 50K LONG: first_in skips both sides; lit_priority routes both (ATLAS closed "
          "first); close_on_opposite routes the SHORT (ATLAS closed first), skips the LONG",
          res == {"first_in": (True, True), "lit_priority": (False, False), "close_on_opposite": (False, True)}, res)
    lb._second_prov[tb]["combo"] = False
    check("b. a routed second strategy that is not the combo's: never skipped here (today's LIT PRIORITY)", lb._combo_lit_skip(zs) is None)
    lb._open_routed, lb._open_src, lb._second_prov = None, None, {}
    lb.combo = {"conflict": "first_in", "guards": dict(CB.GUARD_DEFAULTS)}
    lb.state = {"setups": {"short": {"tapped_t": None}}}
    w0 = lb._combo_block(1, tb, now)
    lb.combo = {"conflict": "first_in", "guards": {**CB.GUARD_DEFAULTS, "atlas_lit_armed_block": True}}
    w1 = lb._combo_block(1, tb, now)
    lb.state = {"setups": {"long": {}}}
    w2 = lb._combo_block(1, tb, now)
    lb.state = {"enter_now": {"dir": -1}}
    w3 = lb._combo_block(1, tb, now)
    lb.state = {}
    lb._open_routed = tb - 600
    w4 = lb._combo_block(1, tb, now)
    lb._open_routed = None

    class Ad:
        legs = [{"status": "entry_sent", "entry_t": tb - 60}]
    lb.adapter = Ad()
    w5 = lb._combo_block(1, tb, now)
    lb.adapter = None

    class FakeB:
        open_t = tb - 900
        prov = {tb - 900: {"dir": -1}}

        def closing_open(self):
            return []
    lb.acct_b = FakeB()
    w6 = lb._combo_block(1, tb, now)
    w6b = lb._combo_block(-1, tb, now)
    lb.acct_b = None
    check("b. ATLAS's 50K entry blocked: Zlarior armed the other way (only with the optional guard on; the research rules: "
          "allowed), Zlarior entering, the 50K holds a position, an order working at NinjaTrader, ATLAS's 25K holds the other "
          "side; allowed: Zlarior armed the SAME way, ATLAS's 25K same side",
          w0 is None and w1 and "armed" in w1 and w2 is None and w3 and "entering" in w3 and w4 and "one position" in w4 and w5 and "working" in w5
          and w6 and "no hedging" in w6 and w6b is None, (w1, w2, w3, w4, w5, w6, w6b))
    lb.combo = {"conflict": "first_in", "guards": {**CB.GUARD_DEFAULTS, "eval_day_stop_usd": 400.0}}
    lb._lit_sizing = {"mode": "two_week"}
    lb.ledger = [{"t": now - 3000, "side": "exit", "pnl": -450.0, "entry_t": now - 4000}]
    w7 = lb._combo_block(1, tb, now)
    lb.combo["guards"]["eval_day_stop_usd"] = None
    w8 = lb._combo_block(1, tb, now)
    lb.ledger, lb._lit_sizing = [], None
    check("b. eval_day_stop_usd: ATLAS blocked once today's closed P&L of both bots <= -$400 in the eval; null = off",
          w7 and "eval day stop" in w7 and w8 is None, (w7, w8))
    check("b. alert / board text: 'ATLAS on Zlarior 50K: LONG opened (4 MNQ, EMA)'",
          CB.entry_text(CB.LABEL, "long", 4, "EMA") == "ATLAS on Zlarior 50K: LONG opened (4 MNQ, EMA)")
    from engine import board_events as BE
    check("b. the Board knows the kind combo_trade (not loud)", "combo_trade" in BE.KINDS and "combo_trade" not in BE.LOUD)
    # the instant alerts: NinjaTrader's own fill push (legs carry "who" only while the combo is on) and the bot's paper push
    from engine import push as PU

    class FA:
        got = []

        def _push_account(self):
            return "MFFU 50K"

        def _push(self, make):
            self.got.append(make(PU))
        clock = staticmethod(lambda: at("2026-09-09", 11, 40))
    fa = FA()
    lg = {"instrument": "MNQ 12-26", "dir": 1, "filled": 8, "entry_t": at("2026-09-09", 11, 20), "fill_px": 29700.0, "stop": 29680.75,
          "target": 29854.75, "stop0": 29680.75, "bracket_qty": 8}
    nt.NinjaTraderAdapter._push_fill(fa, dict(lg))
    nt.NinjaTraderAdapter._push_fill(fa, {**lg, "who": CB.LABEL})
    nt.NinjaTraderAdapter._push_exit(fa, {**lg, "who": CB.LABEL}, "TARGET", {"avg": 29854.75, "filled": 8})
    t0_, t1_, t2_ = [p.get("title") for p in fa.got]
    check("b. NinjaTrader's fill push: today's title without the combo; 'ATLAS on Zlarior 50K: LONG opened' / '... closed' with it",
          t0_ == "LONG · MFFU 50K" and t1_ == "ATLAS on Zlarior 50K: LONG opened" and t2_ == "ATLAS on Zlarior 50K: LONG closed", (t0_, t1_, t2_))
    sent = []
    lb2 = live.LiveBot()
    lb2.cfg = {"sym": "NQ", "adapter": "paper"}
    lb2._push_send = sent.append
    lb2._push_account = lambda: "MFFU 50K"
    pos = {"dir": -1, "entry_t": at("2026-09-09", 2, 54), "entry": 29900.0, "stop": 29920.0, "target": 29700.0}
    lb2._push_fill(pos, 4, "NQ", {"ok": True})
    lb2._push_fill(pos, 4, "NQ", {"ok": True}, who=CB.ZLABEL)
    check("b. the bot's own entry push (paper): unchanged without who; 'Zlarior on its 50K: SHORT opened' with it",
          [p["title"] for p in sent] == ["SHORT · MFFU 50K", "Zlarior on its 50K: SHORT opened"], [p.get("title") for p in sent])


def fleet_checks():
    """The fleet (engine/fleet.py, OFF by default): Zlarior's followers copy Zlarior's OWN trades on the 50K, never ATLAS's
    combo trades there (ledger rows "combo"); the 50K's ATLAS position still counts for the no-hedge rule."""
    from engine import fleet as FL
    day = "2026-10-02"
    t_a, x_a = at(day, 3, 10), at(day, 8, 35)          # ATLAS EMA LONG on the 50K (combo)
    t_z, x_z = at(day, 9, 35), at(day, 10, 20)         # a later Zlarior LONG on the 50K
    bot = FL._DryBot()
    snap0 = FL.lead_snapshot(bot, "zlarior")
    tmp = tempfile.mkdtemp(prefix="le_combo_fleet_")
    try:
        fl = FL.Fleet(bot, {"accounts": [{"id": "f1", "lead": "zlarior", "plan": "mffu_builder_50k", "start": day}]},
                      state_path=os.path.join(tmp, "live_state_fleet.json"), parallel=False, sleep=lambda s_: None,
                      notify=lambda *a_: None).start()
        row = lambda t_, side, **kw: {"t": t_, "sym": "NQ", "side": side, "entry_t": kw.pop("et", t_), "result": {"ok": True}, **kw}
        bot.now = t_a
        bot.ledger.append(row(t_a, "buy", qty=4, entry=24800.0, stop=24780.0, target=24960.0, src="ema_lon_vix", combo="atlas50k", who=CB.LABEL))
        bot._open_routed = t_a
        snap_a = FL.lead_snapshot(bot, "zlarior")
        pos_a = FL.lead_positions(bot)
        fl.tick("NQ", t_a + 5)
        bot.now = x_a
        bot.ledger.append(row(x_a, "exit", et=t_a, qty=4, reason="TARGET", pnl=1270.0, exit_t=x_a, src="ema_lon_vix", combo="atlas50k", who=CB.LABEL))
        bot._open_routed = None
        fl.tick("NQ", x_a + 5)
        bot.now = t_z
        bot.ledger.append(row(t_z, "buy", qty=5, entry=24900.0, stop=24885.0, target=25020.0, who=CB.ZLABEL))
        bot._open_routed = t_z
        snap_z = FL.lead_snapshot(bot, "zlarior")
        fl.tick("NQ", t_z + 5)
        bot.now = x_z
        bot.ledger.append(row(x_z, "exit", et=t_z, qty=5, reason="TARGET", pnl=1190.5, exit_t=x_z, who=CB.ZLABEL))
        bot._open_routed = None
        fl.tick("NQ", x_z + 5)
        f = fl.followers[0]
        ents = [int(r["entry_t"]) for r in f.ledger if r.get("side") in ("buy", "sell")]
        snap_end = FL.lead_snapshot(bot, "zlarior")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("f. fleet: while ATLAS holds Zlarior's 50K the 'zlarior' lead shows NO open trade and no ATLAS close; the no-hedge "
          "view still sees the 50K's LONG", snap0 is not None and snap_a["open"] is None and t_a not in snap_a["closes"]
          and any(p["dir"] == 1 for p in pos_a) and t_a not in snap_end["closes"] and t_z in snap_end["closes"]
          and (snap_z["open"] or {}).get("entry_t") == t_z, (snap_a, pos_a, snap_end))
    check("f. fleet: a Zlarior follower copied Zlarior's own 09:35 trade only, never ATLAS's 03:10 combo trade",
          ents == [t_z], [(hm(e), r.get("side")) for e, r in zip(ents, f.ledger)])


def _stream_parity():
    """combo50k.atlas_pick on the stored member trades (second_mix.units: the research trades engine/second.py reproduces) for
    every 2026 5m open with a signal == the reference's ATLAS rows."""
    import combo_account as C
    from tools import second_mix as M
    U = M.units()
    name = {"EMA": "ema_lon_vix", "MD": "macd_sweep", "SR": "sr_nyreclaim"}
    by = collections.defaultdict(list)
    for nm in ("EMA", "MD", "SR"):
        for u in U[nm]:
            if u["day"] >= "2026-01-01":
                by[u["day"]].append((name[nm], u))
    want = {(r["day"], int(r["et"])) for r in C._atlas_rows() if r["day"] >= "2026-01-01"}
    got, bad = set(), []
    for day, us in by.items():
        for tb in sorted({int(u["entry_t"]) for _, u in us}):
            run = {"strategies": {k: {"trades": [{"day": day, "entry_t": int(u["entry_t"]),
                                                  "exit_t": int(u["exit_t"]) if int(u["entry_t"]) < tb else None,
                                                  "exit_kind": "OPEN" if int(u["entry_t"]) >= tb else str(u["exit"]).upper(),
                                                  "dir": u["dir"], "target": 1.0} for kk, u in us if kk == k and int(u["entry_t"]) <= tb]}
                                  for k in CB.MEMBERS}}
            pk, _, _ = CB.atlas_pick(run, list(CB.MEMBERS), tb, day)
            if pk:
                got.add((day, tb))
    for x in sorted(want ^ got):
        bad.append((x, "reference" if x in want else "live pick"))
    return len(got), bad


# ================================================================================================ the parity replay
def lit_sizing():
    """live_model.json lit_sizing for a FRESH eval (no prior P&L, the eval start comes from the start cfg)."""
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
    return {k: v for k, v in ls.items() if k not in ("eval_prior_pnl", "eval_start")}


def day_bot(H, seg_dir, day, eval_start, combo_cfg, extra=None):
    """A LiveBot started at 01:45 ET on `day` (the PC bot's morning start) on the segment's state file (yesterday's eval days
    carry over), a fresh fake NinjaTrader folder for the day, Sim101 = the one 50K."""
    d = os.path.join(H.tmp, seg_dir)
    nd = os.path.join(d, day)
    folder = os.path.join(nd, "NinjaTrader 8")
    fake = nt._FakeNT(folder, price=25000.0)
    start_t = at(day, 1, 45)
    H.rp.now = int(start_t)
    H.clock.base, H.clock.running = float(start_t), False
    b = live.LiveBot()
    b.clock = H.clock
    b.read_hist, b.fetch_recent = H.rp.read_hist, H.rp.fetch_recent
    b.state_path = os.path.join(d, "live_state.json")
    b._remember = lambda *a_, **kw: None
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_folder": folder, "nt_account": "Sim101",
           "model": "lit", "model_params": H.ref.lit_p, "params": {"max_micros": 40, "flat_mod": 955},
           "nt_state_path": os.path.join(nd, "nt_state.json"), "nt_audit_log": os.path.join(nd, "oif.log"),
           "eval_start": eval_start}
    if combo_cfg is not None:
        cfg["combo_50k"] = combo_cfg
    cfg.update(extra or {})
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    ad = b.adapter
    ad.clock = H.clock
    ad._alert_fn = lambda *a_, **kw: None
    clock = H.clock

    def nt_sleep(s_, fake=fake):
        fake.process()
        clock.base += s_
    ad._sleep = nt_sleep
    return b, fake


def poll_times(day, cands):
    """Every 5m close (+2 s) 01:50-16:10 and every minute (+2 s) from 10 min before to 5 min after each candidate entry of
    either bot (Zlarior's 1m CISD entries) and from 5 min before to 5 min after each candidate exit (the account freed at
    the exit's minute), as the PC bot polls each minute there. Between them the 5m polls: the decisions are a pure function
    of the bars (every booked $ is the model's), so a minute poll inside a long hold changes nothing in the trade list."""
    a, z = at(day, 1, 50), at(day, 16, 10)
    T = set(range(a, z + 1, 300))
    for t in cands:
        T |= set(range(int(t["et"]) - 600, int(t["et"]) + 301, 60)) | set(range(int(t["xt"]) - 300, int(t["xt"]) + 301, 60))
    return sorted(x + 2 for x in T if a <= x <= z)


def live_rows(b, day):
    """The 50K's trades of `day` from the bot's ledger: [(day, s, entry_t, dir, qty, pnl, reason)] (Z = Zlarior, A = ATLAS)."""
    led = b.ledger
    out = []
    for e in led:
        if e.get("side") not in ("buy", "sell") or not e.get("entry_t") or live.trading_day(int(e["entry_t"])) != day:
            continue
        x = [r for r in led if r.get("side") == "exit" and r.get("entry_t") == e["entry_t"]]
        pnl = round(sum(float(r.get("pnl") or 0) for r in x), 2)
        out.append((day, "A" if e.get("combo") else "Z", int(e["entry_t"]), 1 if e["side"] == "buy" else -1, int(e["qty"]), pnl,
                    x[-1].get("reason") if x else None, bool(e.get("src")), e.get("who")))
    return out


def masked_armed(b, day, cands):
    """ATLAS candidates the bot did not route because Zlarior had a setup armed the other way (the declared guard): the log
    line must name it."""
    out = []
    for t in cands:
        if t["s"] != "A":
            continue
        tag = f"at the {live._et(int(t['et'])):%H:%M} ET open NOT routed on the 50K: no hedging: Zlarior has a"
        if any(tag in x["text"] for x in b.log):
            out.append(("A", int(t["et"])))
    return out


def run_segment(H, R, a, z, combo_cfg, label, a_f=1.0):
    """One fresh eval a..z through the live bot; returns (live rows, reference rows, details)."""
    rows_ref, cands, end = R.segment(a, z, a_f=a_f)
    days = sorted(cands)
    if end:
        days = [d for d in days if d <= end[0]]
    seg = f"seg_{a}_{abs(hash(json.dumps(combo_cfg, sort_keys=True))) % 10**6}"
    rows_live, errors, legs_max, masked, two_pos, logs = [], [], 0, [], [], []
    t0 = time.time()
    for day in days:
        cs = cands.get(day) or []
        if not cs:
            continue
        b, fake = day_bot(H, seg, day, a, combo_cfg)
        errs = []
        mx = H.run(b, fake, poll_times(day, cs), errs)
        legs_max = max(legs_max, mx)
        errors += [f"{day} {e}" for e in errs]
        rows_live += live_rows(b, day)
        masked += masked_armed(b, day, cs)
        logs += [f"{day} {x['text']}" for x in b.log if ("50K" in x["text"] or "NOT routed" in x["text"] or "ROUTED" in x["text"])]
        # never two positions on the account: no entry while another routed entry of the account is open
        bad = TR.one_position(b)
        if bad:
            two_pos.append((day, bad))
        b.stop()
        print(f"   {label} {day}: {len([r for r in rows_live if r[0] == day])} trade(s) on the 50K, {time.time() - t0:.0f} s", flush=True)
    if masked:
        rows_ref, _, end = R.segment(a, z, drop=frozenset(masked), a_f=a_f)
    return rows_live, rows_ref, {"end": end, "errors": errors, "legs_max": legs_max, "masked": masked, "two_pos": two_pos,
                                 "logs": logs[-400:], "seconds": round(time.time() - t0)}


def compare(rows_live, rows_ref, label, det):
    key = lambda r: (r[1], r[2])
    L = {key(r): r for r in rows_live}
    F = {key(r): r for r in rows_ref}
    taken_ok = set(L) == set(F)
    check(f"{label}: the same entries taken (and so the same skipped) as the study's simulator: {len(F)} trades "
          f"({sum(1 for r in rows_ref if r[1] == 'Z')} Zlarior, {sum(1 for r in rows_ref if r[1] == 'A')} ATLAS)", taken_ok,
          {"live_only": [(k[0], hm(k[1])) for k in sorted(set(L) - set(F))], "ref_only": [(k[0], hm(k[1])) for k in sorted(set(F) - set(L))]})
    both = sorted(set(L) & set(F), key=lambda k: k[1])
    side = [(k[0], hm(k[1]), L[k][3], F[k][3]) for k in both if L[k][3] != F[k][3]]
    qty = [(k[0], hm(k[1]), L[k][4], F[k][4]) for k in both if L[k][4] != F[k][4]]
    check(f"{label}: the same side and micros on every common trade", not side and not qty, {"side": side, "qty": qty})
    usd = [(k[0], hm(k[1]), L[k][5], F[k][5], L[k][6], F[k][6]) for k in both
           if abs(L[k][5] - F[k][5]) > max(0.06, 0.02 * F[k][4])]
    check(f"{label}: the same exit $ on every common trade (booked on the 50K = the study's $ at those micros)", not usd, usd)
    lab = [(k[0], hm(k[1])) for k in both if (L[k][1] == "A") != bool(L[k][8] == CB.LABEL) or (L[k][1] == "Z" and L[k][8] != CB.ZLABEL)]
    check(f"{label}: every 50K entry says which bot traded it (ATLAS rows '{CB.LABEL}', Zlarior rows '{CB.ZLABEL}')", not lab, lab)
    check(f"{label}: never two positions on the 50K, at most one bracket working at the fake NinjaTrader",
          not det["two_pos"] and det["legs_max"] <= 2, (det["two_pos"][:3], det["legs_max"]))
    check(f"{label}: no error in the live loop", not det["errors"], det["errors"][:3])
    return {"live": len(L), "ref": len(F), "masked_armed": [(m[0], hm(m[1])) for m in det["masked"]], "end": det["end"],
            "seconds": det["seconds"], "rows": [{"day": r[0], "bot": r[1], "entry": hm(r[2]), "dir": r[3], "qty": r[4], "usd": r[5],
                                                 "exit": r[6]} for r in sorted(rows_live, key=lambda r: r[2])]}


def scenario_close_on_opposite(H, R, day="2026-09-04"):
    """d. conflict rule close_on_opposite (no armed block) on 2026-09-04: ATLAS's EMA LONG 03:10 holds the 50K, Zlarior
    enters SHORT 03:26 -> ATLAS closed at market FIRST (LIT PRIORITY), then Zlarior's order; never two positions."""
    label = f"d. close_on_opposite {day}"
    b, fake = day_bot(H, "sc_coo", day, day, {"conflict": "close_on_opposite", "guards": {"atlas_lit_armed_block": False}})
    cs = R.segment(day, day)[1].get(day) or []
    seen = []

    def on_poll(bot, w):
        seen.append((int(w), sum(q for (ac, _), (q, _x) in fake.pos.items() if ac == "Sim101")))
    errs = []
    t0 = time.time()
    H.run(b, fake, poll_times(day, cs), errs, on_poll=on_poll)
    led = b.ledger
    ea = next((r for r in led if r.get("side") == "buy" and r.get("combo") and r.get("entry_t") == at(day, 3, 10)), None)
    xa = next((r for r in led if r.get("side") == "exit" and r.get("combo") and r.get("entry_t") == at(day, 3, 10)), None)
    ez = next((r for r in led if r.get("side") == "sell" and not r.get("src") and r.get("entry_t") == at(day, 3, 26)), None)
    ok = ea is not None and xa is not None and ez is not None and xa.get("reason") == "LIT PRIORITY" and float(xa["t"]) <= float(ez["t"]) \
        and led.index(xa) < led.index(ez)
    check(f"{label}: ATLAS LONG 03:10 on the 50K, Zlarior SHORT 03:26 closes it at market first (LIT PRIORITY), then routes",
          ok, ([(r.get("side"), r.get("reason"), hm(r["t"]), r.get("src")) for r in led if r.get("side") in ("buy", "sell", "exit")]))
    qa, qz = int((ea or {}).get("qty") or 0), int((ez or {}).get("qty") or 0)
    worst = [(hm(w), p) for w, p in seen if p > qa or p < -qz]
    check(f"{label}: the fake 50K never holds more than one trade's size (long {qa} or short {qz}), never long + short added",
          not worst and not TR.one_position(b), (worst[:4], TR.one_position(b)))
    check(f"{label}: no error", not errs, errs[:3])
    b.stop()
    return {"atlas": ea and ea.get("qty"), "atlas_exit": xa and xa.get("reason"), "zlarior": ez and ez.get("qty"),
            "seconds": round(time.time() - t0)}


EXTRA = [{"id": "z25b", "name": "Zlarior 25K #2", "adapter": "paper", "preset": "mffu_builder_25k", "mode": "two_week"},
         {"id": "reod", "name": "Rapid EOD 25K", "adapter": "paper", "preset": "mffu_rapid_eod_25k", "mode": "two_week"}]


def scenario_extra_accounts(H, R, days=("2026-10-02", "2026-09-04")):
    """e. the multi_account router's extra accounts (the owner's Zlarior 25K #2 and the Rapid EOD 25K): an ATLAS combo entry
    on the 50K is NEVER routed to them; only Zlarior's own LIT signals go there, as today, and never against the 50K's
    ATLAS position (Oct 2: ATLAS long 03:10 holds the 50K, Zlarior's long 03:34 skipped there but routed on the extra
    accounts; Sep 4: ATLAS long 03:10, Zlarior's short 03:26 refused on every account)."""
    out = {}
    for day in days:
        label = f"e. extra accounts {day}"
        accts = [{**a, "eval_start": day} for a in EXTRA]
        b, fake = day_bot(H, f"sc_extra_{day}", day, day, research_cfg(), extra={"accounts": accts})
        cs = R.segment(day, day)[1].get(day) or []
        errs = []
        H.run(b, fake, poll_times(day, cs), errs)
        A = {int(r["entry_t"]) for r in b.ledger if r.get("side") in ("buy", "sell") and r.get("combo")}
        lit = {int(t["entry_t"]): int(t["dir"]) for t in H.ref.lit.get(day, [])}
        rows = {}
        for acc in (getattr(b.accts, "accounts", None) or []):
            rows[acc.id] = [(int(r["entry_t"]), 1 if r["side"] == "buy" else -1) for r in acc.ledger if r.get("side") in ("buy", "sell")]
        leak = [(k, hm(et_)) for k, rs in rows.items() for et_, _ in rs if et_ in A or et_ not in lit]
        check(f"{label}: ATLAS's combo entry on the 50K ({', '.join(hm(x) for x in sorted(A)) or 'none'}) is on NO extra account; "
              "every extra-account entry is one of Zlarior's own LIT signals", bool(A) and len(rows) == 2 and not leak, (rows, A, leak))
        dirs = {et_: d for et_, d in ((int(r["entry_t"]), 1 if r["side"] == "buy" else -1) for r in b.ledger
                                     if r.get("side") in ("buy", "sell") and r.get("combo"))}
        a_dir = next(iter(dirs.values()), 0)
        opp = [(k, hm(et_)) for k, rs in rows.items() for et_, d in rs if d == -a_dir]
        if day == "2026-10-02":
            same = [k for k, rs in rows.items() if any(et_ in lit and d == a_dir for et_, d in rs)]
            check(f"{label}: Zlarior's same-side LIT signal (skipped on the 50K while ATLAS holds it) still went to the extra "
                  "accounts, as today", bool(same) and not opp, (rows, same))
        else:
            check(f"{label}: no extra account went against ATLAS's 50K LONG (Zlarior's opposite signal refused there too)",
                  not opp and not any(rs for rs in rows.values()), rows)
        check(f"{label}: no error", not errs, errs[:3])
        out[day] = {"atlas_50k": sorted(hm(x) for x in A), "extra": {k: [(hm(e), d) for e, d in v] for k, v in rows.items()}}
        b.stop()
    return out


def replay(segments, do_scenario=False, do_extra=True):
    print("parity replay: the real LiveBot (Zlarior + ATLAS on one fake Sim 50K) vs tools/money/combo_account.Eval", flush=True)
    R = Reference()
    ref = TR.Ref()
    H = Harness(ref, lm_extra={"lit_sizing": lit_sizing()})
    out = {}
    try:
        for a, z, case in segments:
            mk, a_f = CASES[case]
            ccfg = mk()
            label = f"c. eval from {a} ({ {A50: 'the research rules combo_50k.json: ATLAS x0.5 in the eval', STUDY: 'the study: first in, ATLAS x1.0', ARMED: 'the study + the optional armed-opposite guard'}[case] })"
            rl, rr, det = run_segment(H, R, a, z, ccfg, label, a_f=a_f)
            k = f"{a} {case}"
            out[k] = compare(rl, rr, label, det)
            out[k]["logs"] = det["logs"][-60:]
            out[k]["rules"] = ccfg
            if case != ARMED:
                check(f"{label}: nothing masked (no armed guard): the trade list IS the simulator's", not det["masked"], det["masked"])
            if case == A50:
                half = [r for r in rr if r[1] == "A"]
                check(f"{label}: ATLAS's {len(half)} trade(s) at the simulator's eval share (sizes halved, rounded down, min 1)",
                      bool(half), half)
            print(f"   {label}: {out[k]['live']} live / {out[k]['ref']} reference trades, masked {det['masked']}, eval end {det['end']}, "
                  f"{det['seconds']} s", flush=True)
        if do_extra:
            out["extra_accounts"] = scenario_extra_accounts(H, R)
        if do_scenario:
            out["close_on_opposite"] = scenario_close_on_opposite(H, R)
    finally:
        H.close()
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    t0 = time.time()
    units()
    out = {}
    if "--units" not in argv:
        mode = "full" if "--full" in argv else "quick" if "--quick" in argv else "default"
        segs = SEGMENTS[mode]
        if "--extra" in argv:                     # only e (the extra accounts), no eval segment
            segs = []
        if "--seg" in argv:                       # one segment (tests/run_area.py runs the default ones as parts)
            day = argv[argv.index("--seg") + 1]
            case = argv[argv.index("--case") + 1] if "--case" in argv else None
            segs = [x for x in SEGMENTS["full"] if x[0] == day and (case is None or x[2] == case)][:1] if case else \
                [x for x in SEGMENTS["default"] if x[0] == day][:1]
        part = "--seg" not in argv or "--scenario" in argv          # run_area: e + d ride with the oct part only
        out = replay(segs, do_scenario=(mode != "quick" and part and "--extra" not in argv), do_extra=part)
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed ({time.time() - t0:.0f} s)")
    if out:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "checks": f"{n_ok}/{len(RESULTS)}", "segments": out}, fh, indent=1, default=str)
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
