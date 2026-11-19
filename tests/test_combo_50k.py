"""ATLAS + Zlarior on ONE account, the Builder 50K (engine/combo50k.py; built, OFF by default). Sim / fake NinjaTrader only
(engine/ninjatrader._FakeNT on a temp folder, ONE account Sim101 = the 50K); nothing is ever armed for a real account and
neither data/combo_50k.json nor research/lab/combo_50k.json is written (the start cfg "combo_50k" switches the harness on).

    python -X utf8 -m tests.test_combo_50k            # units + the parity replay (2 eval segments, 9 sessions) + d (~15-25 min)
    python -X utf8 -m tests.test_combo_50k --quick    # units + one segment (5 sessions)
    python -X utf8 -m tests.test_combo_50k --units    # unit checks only (~20 s)
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
    Default segments (both bots signal and conflict): Sep 2-10 with the DEFAULT rules (Zlarior first, ATLAS long skipped;
    Zlarior armed short at 03:10 on Sep 4 masks ATLAS's EMA long, so Zlarior's short goes in; 3 signals on Sep 9) and Oct 2-7
    with EXACTLY the study's rules (armed block off: ATLAS first 3 times, Zlarior skipped same side and opposite).
    The guard atlas_lit_armed_block (default on: ATLAS never enters while Zlarior has a setup armed the other way, today's
    ATLAS rule, not in the study): a signal the bot masks for it must say so in the log; the reference is then re-run without
    that one ATLAS trade (the cascade included).
 d. close_on_opposite on Sep 4: ATLAS's long is closed at market (LIT PRIORITY) before Zlarior's short goes out; the fake
    50K never holds more than one trade.
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
DEFAULT_CFG = {"conflict": "first_in"}                                   # = no research/lab/combo_50k.json: the defaults
PURE_CFG = {"conflict": "first_in", "guards": {"atlas_lit_armed_block": False}}   # exactly the study's rule set (no armed block)
SEGMENTS = {"quick": [("2026-09-02", "2026-09-10", DEFAULT_CFG)],
            "default": [("2026-09-02", "2026-09-10", DEFAULT_CFG), ("2026-10-02", "2026-10-07", PURE_CFG)],
            "full": [("2026-08-18", "2026-09-01", DEFAULT_CFG), ("2026-09-02", "2026-09-10", DEFAULT_CFG),
                     ("2026-10-02", "2026-10-07", PURE_CFG), ("2026-09-02", "2026-09-10", PURE_CFG)]}


# ================================================================================================ the reference
class Reference:
    """tools/money/combo_account: the study's trade table + its Eval book (Builder 50K, Zlarior + ATLAS, own sizing, first-in)."""

    def __init__(self):
        import combo_account as C
        self.C = C
        C.trades()
        self.S = C.sessions()
        self.D = C.combo_days("Z+A")

    def segment(self, a, z, drop=frozenset()):
        """Real sessions a..z in order on ONE fresh eval (ends at pass / fail / stuck). drop = {(s, et)} not fed (masked
        live by a declared guard). -> (rows [(day, s, et, d, q, pnl, x)], cands {day: [trade]}, end (day, result) | None)."""
        C = self.C
        ev = C.Eval(C.R("b50", "Z+A"), "Z+A")
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
    print("unit checks: rules, switch, ATLAS stream, sizing, conflict rules, locks, alert text", flush=True)
    tmp = tempfile.mkdtemp(prefix="le_combo_units_")
    try:
        # a. off = today
        n0 = CB.normalize({})
        check("a. rules: no file -> first_in, ATLAS size x1.0, armed-opposite block on, ATLAS 2 a day, $200 stop line",
              n0["conflict"] == "first_in" and n0["atlas_size_factor"] == 1.0 and n0["guards"]["atlas_lit_armed_block"] is True
              and n0["guards"]["atlas_max_per_day"] == 2 and n0["guards"]["atlas_min_room"] == 200.0 and not n0["problem"], n0)
        check("a. rules: bad conflict / factor refused, unknown guard keys listed, a 'rules' sub-dict read",
              CB.normalize({"conflict": "both"})["problem"] and CB.normalize({"atlas_size_factor": 3})["problem"]
              and CB.normalize({"guards": {"zzz": 1}})["unknown"] == ["zzz"]
              and CB.normalize({"rules": {"conflict": "lit_priority"}})["conflict"] == "lit_priority")
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
    spec = {"on": True, "account": "Sim101", "factor": 1.0, "guards": dict(CB.GUARD_DEFAULTS), "max_micros": 40}
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
    s2 = {**spec, "factor": 0.5}
    st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "wk_pnl": 0.0, "days_traded": 0}
    q1 = CB.atlas_qty(spec, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    q2 = CB.atlas_qty(s2, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    q3 = CB.atlas_qty({**spec, "factor": 2.0}, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")
    q4 = CB.atlas_qty({**spec, "guards": {**spec["guards"], "atlas_max_risk_usd": 200.0}}, {"risk_pts": 20.0, "tgt_pts": 160.0}, st, "2026-01-02")["qty"]
    loss1 = (20.0 + 0.5) * 2 + 1.9
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
    check("b. ATLAS's 50K entry blocked: Zlarior armed the other way, Zlarior entering, the 50K holds a position, an order "
          "working at NinjaTrader, ATLAS's 25K holds the other side; allowed: Zlarior armed the SAME way, ATLAS's 25K same side",
          w1 and "armed" in w1 and w2 is None and w3 and "entering" in w3 and w4 and "one position" in w4 and w5 and "working" in w5
          and w6 and "no hedging" in w6 and w6b is None, (w1, w2, w3, w4, w5, w6, w6b))
    check("b. alert / board text: 'ATLAS on Zlarior 50K: LONG opened (4 MNQ, EMA)'",
          CB.entry_text(CB.LABEL, "long", 4, "EMA") == "ATLAS on Zlarior 50K: LONG opened (4 MNQ, EMA)")
    from engine import board_events as BE
    check("b. the Board knows the kind combo_trade (not loud)", "combo_trade" in BE.KINDS and "combo_trade" not in BE.LOUD)


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


def day_bot(H, seg_dir, day, eval_start, combo_cfg):
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


def run_segment(H, R, a, z, combo_cfg, label):
    """One fresh eval a..z through the live bot; returns (live rows, reference rows, details)."""
    rows_ref, cands, end = R.segment(a, z)
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
        rows_ref, _, end = R.segment(a, z, drop=frozenset(masked))
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


def replay(segments, do_scenario=False):
    print("parity replay: the real LiveBot (Zlarior + ATLAS on one fake Sim 50K) vs tools/money/combo_account.Eval", flush=True)
    R = Reference()
    ref = TR.Ref()
    H = Harness(ref, lm_extra={"lit_sizing": lit_sizing()})
    out = {}
    try:
        for a, z, ccfg in segments:
            pure = ccfg is PURE_CFG
            label = f"c. eval from {a} ({'the study rules exactly: no armed block' if pure else 'default rules'})"
            rl, rr, det = run_segment(H, R, a, z, ccfg, label)
            k = f"{a}{' pure' if pure else ''}"
            out[k] = compare(rl, rr, label, det)
            out[k]["logs"] = det["logs"][-60:]
            if pure:
                check(f"{label}: nothing masked (the guard is off): the trade list IS the study's", not det["masked"], det["masked"])
            print(f"   {label}: {out[k]['live']} live / {out[k]['ref']} reference trades, masked {det['masked']}, eval end {det['end']}, "
                  f"{det['seconds']} s", flush=True)
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
        if "--seg" in argv:                       # one segment (tests/run_area.py runs the default ones as parts)
            day = argv[argv.index("--seg") + 1]
            segs = [x for x in SEGMENTS["default"] if x[0] == day][:1]
        out = replay(segs, do_scenario=(mode != "quick" and ("--seg" not in argv or "--scenario" in argv)))
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed ({time.time() - t0:.0f} s)")
    if out:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "checks": f"{n_ok}/{len(RESULTS)}", "segments": out}, fh, indent=1, default=str)
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
