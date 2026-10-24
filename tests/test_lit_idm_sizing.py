"""Inducement-count sizing (engine/lit.py option idm_size) on the eval / funded sizing and the PC route (2026-10-19):
engine/lit.py puts idm_m / idm_cap / wk_m on each trade, engine/lit_live.py carries them on the trades, the open position and
the enter-now entry, engine/live.py (primary) and engine/multi_account.py (extra accounts) hand that dict to
engine/sizing.lit_qty, which applies the multiplier before the eval caps. Option off -> no field, the old micros.

    python -X utf8 -m tests.test_lit_idm_sizing           # unit + route checks + one real 2026 day through lit_live (~20 s)
    python -X utf8 -m tests.test_lit_idm_sizing --quick   # unit + route checks only (~3 s)
Paper only: simulated NinjaTrader folder, paper accounts, temp state files.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit_live, sizing as sz  # noqa: E402
from engine.ninjatrader import _FakeNT  # noqa: E402
from tests import test_multi_account as TM  # noqa: E402

RESULTS = []
IDM = {"atr": 2.0, "bars": 48, "n": 2, "up": 1.5, "down": 0.75, "cap_usd": 990}
LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
LSZ = LM["lit_sizing"]
TW = {"mode": "two_week", "two_week": LSZ["two_week"], "two_week_until": 10, "after_mode": "safe_eval", "safe_cap": 0.6}
UP = {"idm_m": 1.5, "idm_cap": 990.0, "idm_n": 3, "wk_m": 1.0, "size_mult": 1.5}
DN = {"idm_m": 0.75, "idm_cap": 990.0, "idm_n": 1, "wk_m": 1.0, "size_mult": 0.75}
FRESH = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0}


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def unit():
    t = {"risk_pts": 30.0, "tgt_pts": 200.0}
    q0 = sz.lit_qty(3, t, TW, room=2000.0, state=FRESH, learning=None)["qty"]
    qu = sz.lit_qty(3, {**t, **UP}, TW, room=2000.0, state=FRESH, learning=None)["qty"]
    qd = sz.lit_qty(3, {**t, **DN}, TW, room=2000.0, state=FRESH, learning=None)["qty"]
    check("two_week: x1.5 / x0.75 on the one-winner size (30-pt stop, 200-pt target: 8 -> 12 / 6)", (q0, qu, qd) == (8, 12, 6), (q0, qu, qd))
    # after a -$1,500 day the 60% room cap (300 / 62.4 = 4: 30 pts + 1 tick, $1.90 since 2026-10-24) binds on the size-up too
    st = {"profit": -1500.0, "cum": 0.0, "room": 500.0, "session": 2, "n_today": 0}
    check("two_week: the 60% room cap still binds a size-up",
          sz.lit_qty(3, {**t, **UP}, TW, room=500.0, state=st, learning=None)["qty"] == sz.lit_qty(3, t, TW, room=500.0, state=st, learning=None)["qty"] == 4)
    # today -$800: soft daily loss left $200 / 61.9 = 3 -> a size-up stays at 3
    st = {**FRESH, "cum": -800.0, "room": 1200.0}
    check("two_week: the $1,000 soft daily loss left still binds a size-up",
          sz.lit_qty(3, {**t, **UP}, TW, state=st, learning=None)["qty"] == 3)
    # cap_usd: 10-pt stop, 40-pt target wants 39 -> x1.5 = 40 (max; $990 / 22.4 = 44); with cap $500: 22 -> 39 (never below q)
    t10 = {"risk_pts": 10.0, "tgt_pts": 40.0}
    TWn = {**TW, "two_week": {**TW["two_week"], "dll_cap": False, "room_f": None}}
    a = sz.lit_qty(3, t10, TWn, state=FRESH, learning=None)["qty"]
    b = sz.lit_qty(3, {**t10, **UP}, TWn, state=FRESH, learning=None)["qty"]
    c = sz.lit_qty(3, {**t10, **UP, "idm_cap": 500.0}, TWn, state=FRESH, learning=None)["qty"]
    check("max 40 micros and idm_cap (a size-up never below the base size)", (a, b, c) == (39, 40, 39), (a, b, c))
    # after session 10 (safe_eval): the model's micros carry it already (60% room cap after)
    s11 = {**FRESH, "session": 11}
    check("safe_eval after session 10: the model's micros (which carry the multiplier) are routed",
          sz.lit_qty(7, {**t, **UP}, TW, room=2000.0, state=s11, learning=None)["qty"] == 7)
    # funded: x0.75 cut / x1.5 up on the funded size, caps after
    F = {"mode": "funded", "funded": LSZ["funded"]}
    fs = sz.funded_state({})
    f0 = sz.lit_qty(3, {"risk_pts": 30.0, "tgt_pts": 60.0}, F, state=fs, learning=None)["qty"]
    fu = sz.lit_qty(3, {"risk_pts": 30.0, "tgt_pts": 60.0, **UP}, F, state=fs, learning=None)["qty"]
    fd = sz.lit_qty(3, {"risk_pts": 30.0, "tgt_pts": 60.0, **DN}, F, state=fs, learning=None)["qty"]
    check("funded: the multiplier on the funded size (x1.5 up, x0.75 cut)", fu == int(f0 * 1.5) and fd == int(f0 * 0.75), (f0, fu, fd))
    # option off / absent: identical to the old call
    check("no idm_m on the trade: the old micros", sz.lit_qty(3, {**t, "size_mult": 0.5}, TW, state=FRESH, learning=None)["qty"] == q0)
    # lit_live shapes carry the fields (and only when the option set them)
    base = {"entry_t": 1, "cisd_t": 1, "exit_t": 2, "dir": 1, "qty": 9, "stop_px": 100.0, "target_px": 300.0, "entry_px": 130.0,
            "exit_px": 130.0, "pnl": 0.0, "r": 0.0, "exit": "BE", "day": "2026-01-02", "risk_pts": 30.0, "risk_usd": 540.0}
    en = lit_live._enter_now({**base, **UP})
    tr = lit_live._trade({**base, **UP})
    check("lit_live: the enter-now entry and the finished trade carry idm_m / idm_cap / wk_m",
          all(en.get(k) == UP[k] and tr.get(k) == UP[k] for k in ("idm_m", "idm_cap", "wk_m")))
    check("lit_live: option off -> no idm field", not any(k in lit_live._enter_now(base) or k in lit_live._trade(base) for k in lit_live.IDM_KEYS))
    check("lit_live: enter-now sized like the backtest trade by lit_qty",
          sz.lit_qty(en["qty"], en, TW, state=FRESH, learning=None)["qty"]
          == sz.lit_qty(9, {"risk_pts": 30.0, "tgt_pts": 170.0, **UP}, TW, state=FRESH, learning=None)["qty"]
          != sz.lit_qty(9, {"risk_pts": 30.0, "tgt_pts": 170.0}, TW, state=FRESH, learning=None)["qty"])


def route(tmp):
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    fake = _FakeNT(os.path.join(tmp, "NinjaTrader 8"))
    clock = TM.Clock(TM.T0 + 290)
    accts = [{"id": "p2w", "name": "Paper eval", "adapter": "paper", "preset": "paper_50k", "mode": "two_week", "eval_start": TM.DAY},
             {"id": "fund", "name": "Paper funded", "adapter": "paper", "preset": "mffu_builder_50k", "mode": "funded",
              "funded": {"start": "2026-10-01", "payouts": {}}}]
    got = {}
    for lab, extra in (("off", {}), ("up", UP), ("down", DN)):
        clock.t = TM.T0 + 290
        b = TM.make_bot(os.path.join(tmp, lab), fake, clock, accts)
        b._lit_sizing = dict(TW)
        b.eval_state = lambda: dict(FRESH)
        b.eval_room = lambda: 2000.0
        clock.t = TM.T0 + 305
        p = {**TM.pos_at(TM.T0, qty=13), **extra}
        TM.signal(b, p)
        got[lab] = {"primary": [r["qty"] for r in TM.entries(b.ledger)],
                    **{a.id: [r["qty"] for r in TM.entries(a.ledger)] for a in b.accts.accounts}}
    want_p = {k: [sz.lit_qty(13, {**TM.pos_at(TM.T0, qty=13), **x}, TW, room=2000.0, state=FRESH, learning=None)["qty"]]
              for k, x in (("off", {}), ("up", UP), ("down", DN))}
    check("PC primary (engine/live.py _equity_qty): two_week micros = lit_qty of the position dict incl. idm_m",
          all(got[k]["primary"] == want_p[k] for k in want_p) and want_p["up"] != want_p["off"] != want_p["down"], (got, want_p))
    o, u, d = got["off"]["p2w"][0], got["up"]["p2w"][0], got["down"]["p2w"][0]
    check("extra account two_week (engine/multi_account.py qty_for): x0.75 cut, x1.5 up within its caps",
          d == max(1, int(o * 0.75)) and o < u <= int(o * 1.5), (o, u, d))
    fq = {k: sz.funded_qty({"risk_pts": 30.0, "tgt_pts": 200.0, **x}, {"room": 2000.0, "cum": 0.0, "locked": False},
                           TM.PRESET_FUNDED, acct={"dll": 1000.0, "max_micros": 40}) for k, x in (("off", {}), ("up", UP), ("down", DN))}
    fq60 = {k: sz.funded_qty({"risk_pts": 30.0, "tgt_pts": 60.0, **x}, {"room": 2000.0, "cum": 0.0, "locked": False},
                             TM.PRESET_FUNDED, acct={"dll": 1000.0, "max_micros": 40}) for k, x in (("off", {}), ("up", UP), ("down", DN))}
    check("extra account funded: funded_qty of the position dict incl. idm_m (the best-day cap binds at a 200-pt target; "
          "at 60 pts the multiplier shows)", all(got[k]["fund"] == [fq[k]] for k in fq) and fq60["down"] < fq60["off"] < fq60["up"],
          (got, fq, fq60))


def engine_day():
    """One real 2026 day through engine/lit_live.run with idm_size on: the intraday position and the day's trade carry the
    same idm fields as the backtest trade (engine/lit.py run_x)."""
    import numpy as np
    import pandas as pd
    from engine.data import load, load_ltf
    from tests import test_lit_live as TL
    from tools import lit_final as F
    P = {**LM["lit"], "idm_size": IDM}
    T = [t for t in F.run(P) if t["day"] >= "2026-09-01" and t["exit_t"] - t["entry_t"] >= 1800]
    t0 = next(t for t in T if t.get("idm_m") == 1.5)
    t1 = next(t for t in T if t.get("idm_m") == 0.75)
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= TL.day_close("2026-09-01") - 70 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    T5 = df5["time"].values
    for t in (t0, t1):
        for now in (int(t["entry_t"]) + 900, TL.day_close(t["day"])):
            cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
            cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
            res = lit_live.run(cut5, P, one_min=cut1, now=now)
            pos = (res.get("state") or {}).get("position")
            got = [x for x in res["trades"] if x["entry_t"] == int(t["entry_t"])]
            src = pos if pos and pos.get("entry_t") == int(t["entry_t"]) else (got[0] if got else None)
            kind = "open position" if src is pos else "finished trade"
            check(f"lit_live {t['day']} ({kind}, x{t['idm_m']:g}): idm_m / idm_cap / wk_m == the backtest trade's, qty the same",
                  src is not None and all(src.get(k) == t.get(k) for k in ("idm_m", "idm_cap", "wk_m")) and src["qty"] == t["qty"],
                  (src and {k: src.get(k) for k in ("idm_m", "idm_cap", "wk_m", "qty")}, {k: t.get(k) for k in ("idm_m", "idm_cap", "wk_m", "qty")}))
    P0 = LM["lit"]
    now = TL.day_close(t0["day"])
    cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
    cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
    res = lit_live.run(cut5, P0, one_min=cut1, now=now)
    check("lit_live with the option off: no idm field on any trade", not any(k in x for x in res["trades"] for k in lit_live.IDM_KEYS))


def main():
    unit()
    with tempfile.TemporaryDirectory() as tmp:
        route(tmp)
    if "--quick" not in sys.argv:
        engine_day()
    print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
    return all(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
