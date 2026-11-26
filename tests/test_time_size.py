"""engine/account_b time_size (OFF by default): ATLAS x0.5 outside the Silver Bullet hours (03, 10, 14 ET) on the Builder EVAL
combo lanes only (engine/combo50k.atlas_qty stage "eval": Zlarior's 50K + the 25K #2). Research card B2,
research/writeups/ict-lab-proof-2026-11-25.md. Temp folders only: the real data/account_b.json is never read or written.

    python -X utf8 -m tests.test_time_size        (~5 s)

 a. OFF = today: no key / {"on": false} / unusable values -> None; atlas_qty with no time_size == today on a grid of
    sizes x rooms x entry times; combo50k.build / combo25.spec_for add no "time_size" key when OFF.
 b. ON: inside 03 / 10 / 14 ET (whole hour) = today's micros; outside = max(1, floor(q x 0.5)); 1 micro stays 1; 0 stays 0;
    the funded stage is unchanged; no entry_t = unchanged; a DST date (ET clock) and the 50K + 25K #2 presets.
 c. the switch: ON needs the typed live phrase; OFF never does; the "account_b" block is kept byte for byte; a missing file
    gets no "account_b" key (second_model.json still counts); write_local (every other account_b writer) keeps time_size.
 d. the harnesses: the combo start cfg / account entry "time_size" reaches the spec; ATLAS's own 25K (account_b.qty) and the
    Rapid lane never read it.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.disable(logging.WARNING)
from engine import account_b as AB  # noqa: E402
from engine import combo50k as CB  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + ("" if ok or info is None else f"  {str(info)[:300]}"))


def ts_at(day, hh, mm=0):
    return int(dt.datetime(*map(int, day.split("-")), hh, mm, tzinfo=ET).timestamp())


def main() -> int:
    TS = {"hours_et": [3, 10, 14], "in_mult": 1.0, "out_mult": 0.5}
    # a. normalization / OFF
    check("a. absent / on:false / bad -> None (OFF)", AB.time_size_norm(None) is None and AB.time_size_norm({"on": False}) is None
          and AB.time_size_norm({"out_mult": 1.5}) is None and AB.time_size_norm({"out_mult": 0}) is None
          and AB.time_size_norm({"hours_et": []}) is None and AB.time_size_norm({"hours_et": [25]}) is None
          and AB.time_size_norm({"hours_et": "x"}) is None)
    check("a. defaults = 03/10/14 ET, x1 in, x0.5 out", AB.time_size_norm({}) == TS)
    base = {"on": True, "account": "Sim101", "atlas_size_factor": {"eval": 1.0, "funded": 1.0}, "guards": dict(CB.GUARD_DEFAULTS),
            "max_micros": 40}
    sp25 = {**base, "plan": "builder25k"}
    times = [ts_at("2026-03-04", h, m) for h, m in ((2, 55), (3, 0), (3, 55), (4, 0), (9, 30), (10, 5), (11, 0), (14, 30), (15, 10))]
    same, grid = [], 0
    for spec in (base, sp25):
        for room in (150.0, 400.0, 900.0, 2000.0, 2900.0):
            st = {"profit": 3000.0 - room, "cum": 0.0, "room": room, "session": 3, "n_today": 0, "wk_pnl": 0.0, "days_traded": 2}
            for rp in (5.0, 12.0, 25.0, 48.0):
                for t in times:
                    grid += 1
                    a = CB.atlas_qty(spec, {"risk_pts": rp, "tgt_pts": 6 * rp}, dict(st), "2026-01-02")
                    b = CB.atlas_qty(spec, {"risk_pts": rp, "tgt_pts": 6 * rp, "entry_t": t}, dict(st), "2026-01-02")
                    if a != b:
                        same.append((spec.get("plan"), room, rp, t, a["qty"], b["qty"]))
    check(f"a. OFF: atlas_qty with entry_t == without it, identical result dict ({grid} cases, 50K + 25K)", not same, same[:3])
    # b. ON
    bad, n_in, n_out, ones = [], 0, 0, 0
    for spec0 in (base, sp25):
        spec = {**spec0, "time_size": TS}
        for room in (150.0, 400.0, 900.0, 2000.0, 2900.0):
            st = {"profit": 3000.0 - room, "cum": 0.0, "room": room, "session": 3, "n_today": 0, "wk_pnl": 0.0, "days_traded": 2}
            for rp in (5.0, 12.0, 25.0, 48.0):
                for t in times:
                    q0 = CB.atlas_qty(spec0, {"risk_pts": rp, "tgt_pts": 6 * rp}, dict(st), "2026-01-02")["qty"]
                    q1 = CB.atlas_qty(spec, {"risk_pts": rp, "tgt_pts": 6 * rp, "entry_t": t}, dict(st), "2026-01-02")["qty"]
                    inside = dt.datetime.fromtimestamp(t, ET).hour in (3, 10, 14)
                    want = q0 if (inside or q0 == 0) else max(1, int(math.floor(0.5 * q0 + 1e-9)))
                    n_in += inside
                    n_out += not inside
                    ones += q0 == 1 and not inside
                    if q1 != want:
                        bad.append((spec.get("plan"), room, rp, t, q0, q1, want))
    check(f"b. ON: inside the hours = today, outside = max(1, floor(q/2)) ({n_in} inside, {n_out} outside, {ones} 1-micro cases)",
          not bad and ones > 0, bad[:3])
    spec = {**base, "time_size": TS}
    st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "wk_pnl": 0.0, "days_traded": 0}
    out_t = ts_at("2026-03-04", 9, 30)
    f0 = CB.atlas_qty(base, {"risk_pts": 12.0, "tgt_pts": 60.0}, dict(st), "2026-01-02", stage="funded")
    f1 = CB.atlas_qty(spec, {"risk_pts": 12.0, "tgt_pts": 60.0, "entry_t": out_t}, dict(st), "2026-01-02", stage="funded")
    check("b. the funded stage is unchanged (eval only)", f0 == f1, (f0, f1))
    e0 = CB.atlas_qty(base, {"risk_pts": 12.0, "tgt_pts": 60.0}, dict(st), "2026-01-02")
    e1 = CB.atlas_qty(spec, {"risk_pts": 12.0, "tgt_pts": 60.0}, dict(st), "2026-01-02")
    check("b. no entry_t = today's size", e0 == e1, (e0, e1))
    e2 = CB.atlas_qty(spec, {"risk_pts": 12.0, "tgt_pts": 60.0, "entry_t": out_t}, dict(st), "2026-01-02")
    check(f"b. the reason says it ({e2['reasons'][-1:]})", any("time_size x0.5" in r for r in e2["reasons"]), e2)
    # DST: 10:15 ET in July and in January are both inside; 09:55 outside
    check("b. ET clock across DST (Jul + Jan 10:15 in, 09:55 out)",
          AB.time_size_mult(TS, ts_at("2026-07-08", 10, 15)) == 1.0 and AB.time_size_mult(TS, ts_at("2026-01-08", 10, 15)) == 1.0
          and AB.time_size_mult(TS, ts_at("2026-07-08", 9, 55)) == 0.5 and AB.apply_time_size(0, TS, out_t)[0] == 0)
    # c. the switch file
    with tempfile.TemporaryDirectory() as d:
        cfg = os.path.join(d, "second_model.json")
        json.dump({"account_b": None}, open(cfg, "w"))
        lp = AB.local_path(cfg)
        r0 = AB.set_time_size(True, "no", path=cfg)
        check("c. ON without the phrase is refused, nothing written", not r0["ok"] and not os.path.exists(lp), r0)
        r1 = AB.set_time_size(True, "I ACCEPT LIVE RISK", path=cfg, today="2026-11-25")
        c1 = json.load(open(lp))
        check("c. ON with the phrase; a missing file gets NO account_b key (second_model.json still counts)",
              r1["ok"] and "account_b" not in c1 and AB.read_time_size(cfg) == TS and AB.read_local(cfg) == (False, None), c1)
        blk = {"account": "Sim25", "plan": "builder25k", "eval_start": "2026-11-01", "stage": "funded"}
        AB.write_local(blk, cfg, why="test")
        c2 = json.load(open(lp))
        check("c. write_local (every account_b writer) keeps time_size", c2.get("account_b") == blk and AB.read_time_size(cfg) == TS, c2)
        raw = json.dumps(c2["account_b"], sort_keys=True)
        r2 = AB.set_time_size(False, "", path=cfg)
        c3 = json.load(open(lp))
        check("c. OFF needs no phrase, removes only time_size, account_b byte for byte",
              r2["ok"] and "time_size" not in c3 and json.dumps(c3["account_b"], sort_keys=True) == raw and AB.read_time_size(cfg) is None, c3)
        r3 = AB.set_time_size(False, "", path=cfg)
        check("c. OFF again = already off", r3["ok"] and "already" in r3["say"])
    # d. harness specs + other routes
    class Bot:
        cfg = {"combo_50k": {"conflict": "first_in", "time_size": {"out_mult": 0.5}}, "nt_account": "Sim101"}
        state_path = os.path.join(tempfile.gettempdir(), "nq_ts_test_state.json")
    sp = CB.build(Bot())
    class Bot0:
        cfg = {"combo_50k": {"conflict": "first_in"}, "nt_account": "Sim101"}
        state_path = Bot.state_path
    sp0 = CB.build(Bot0())
    check("d. combo50k harness: time_size reaches the spec when given, absent when not; rules unchanged",
          sp and sp.get("time_size") == TS and sp0 and "time_size" not in sp0
          and {k: v for k, v in sp.items() if k != "time_size"} == sp0, (sp, sp0))
    from engine import combo25 as C25
    import inspect
    src = inspect.getsource(C25.spec_for)
    check("d. combo25.spec_for: Rapid / LIT lanes return before time_size; harness + switch both normalized",
          src.index('if s.get("lane")') < src.index("time_size") and "AB.time_size_norm" in src and "AB.read_time_size()" in src)
    qsrc = inspect.getsource(AB.qty) + inspect.getsource(AB.funded_qty)
    from engine import rapid as RP
    check("d. ATLAS's own 25K (account_b.qty / funded_qty) and the Rapid lane never read time_size",
          "time_size" not in qsrc and "time_size" not in inspect.getsource(RP))
    fails = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(fails)}/{len(RES)} OK" + (f"  FAIL: {fails}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
