"""Risk invariants, pre-launch audit A4 (2026-10-25, research/handoff/2026-10-25/A4_eval_risk.md). Paper only: no adapter
is armed, no file outside a temp folder is written, live_model*.json / second_model.json are only read.

  1. skip after ALL caps: on every sizing path (LIT engine/sizing.lit_qty in every eval mode on the live lit_sizing, ATLAS on
     LIT's account sizing.second_qty, account B engine/account_b.qty 25K / 50K need / safe, an extra account
     engine/multi_account.Account.qty_for 25K / 50K) the routed micros x (stop + 1 tick) x $2 + $1.90 fit the room (strict),
     the soft daily loss and (when on) the weekly loss; when not even 1 micro fits -> 0, never 1
  2. worst-case contract cap: a model asking for 100 micros never gets more than the plan's 40 (50K) / 20 (25K)
  3. pending / in-flight reservations: no account ever holds two exposures, so the one-position rule IS the reservation:
     LIT's account blocks a second-strategy entry while LIT holds / enters / has a limit armed / waits for its 1m CISD /
     still has a routed position; account B does not even probe while its own entry (sent, pending or open) is on
  4. commission + 1 tick in every cap ($1.90, 0.25 pt); the known gap engine/lit.py books routed LIT P&L at $1.40
  5. tick rounding: stops to the nearest tick (the 2026 data is on the 0.25 grid, so a stop 1 tick beyond a sweep extreme is
     never moved), targets toward the entry
  6. the structural stop is never widened: a broker stop move only tightens (long and short); every 2026 STOP exit of run
     lit_live lost exactly the sized stop + 1 tick + costs
  7. short breakeven direction: BE = entry - 1.25 for a short (entry + 1.25 long): every BE exit made +1.0 pt a micro on both
     sides; the broker modify for a short BE is accepted and labelled BE; the live loop's short position shows it
  8. post-pass lock: target reached -> 0 on every path (LIT's 1-micro minimum-days trade only when it fits)
  9. unknown inputs -> unresolved, never "no cap": stop distance unknown / 0 / NaN in an eval mode -> 0 (BUG_FIX 2026-10-25,
     sizing.ceilings), an extra account without eval state -> 0 (BUG_FIX 2026-10-25, multi_account.qty_for), account B /
     ATLAS without state or room -> 0, a sizing exception on LIT's eval -> 0 (LiveBot._equity_qty fails closed)

    python -X utf8 -m tests.test_risk_invariants          # ~20 s (part 7's live-loop poll loads the 1m bars)
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.disable(logging.CRITICAL)
from engine import account_b as AB  # noqa: E402
from engine import lit  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import sizing as sz  # noqa: E402

RESULTS = []
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
from tests.sizing_pins import PINNED  # noqa: E402
EVAL_MODES = ("two_week", "eval", "safe_eval", "fast_eval")


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def L1(risk):
    return (float(risk) + 0.25) * 2.0 + 1.90


def st_of(profit=0.0, cum=0.0, room=2000.0, session=1, n_today=0, days_traded=0, wk_pnl=None):
    s = {"profit": profit, "cum": cum, "room": room, "session": session, "n_today": n_today, "days_traded": days_traded}
    if wk_pnl is not None:
        s["wk_pnl"] = wk_pnl
    return s


class _Router:
    def base_sizing(self):
        return dict(LSZ)

    def log(self, *a):
        pass

    def notify(self, *a):
        pass

    def killed(self):
        return False


def extra_account(preset, mode, start="2026-10-19"):
    sp = MA.normalize({"id": "t", "name": "SimX", "preset": preset, "mode": mode, "adapter": "paper", "eval_start": start})
    return MA.Account(sp, _Router())


NOW = 1792591200          # 2026-10-21 ~10:00 ET


# ------------------------------------------------------------------------------------------------ 1 + 2
def lit_caps(rnd, n, base, label):
    """LIT ceilings on `base`: the room (strict), the $1,000 soft daily loss and, when base has wk_loss_usd, the weekly loss."""
    wl = base.get("wk_loss_usd")
    bad, bad1, maxq_bad = [], [], []
    for _ in range(n):
        mode = rnd.choice(EVAL_MODES)
        cfg = {**base, "mode": mode}
        risk = rnd.choice([6.0, 9.5, 14.0, 20.0, 33.0, 50.0, 70.0, 88.0, 120.0])
        room = rnd.choice([30.0, 75.0, 140.0, 260.0, 600.0, 1200.0, 2000.0, 3100.0])
        cum = rnd.choice([0.0, -250.0, -700.0, -960.0, 180.0])
        wk = rnd.choice([None, 0.0, -600.0, -1100.0, -1190.0])
        s = st_of(profit=rnd.choice([-1500.0, -300.0, 0.0, 1200.0, 2900.0]), cum=cum, room=room,
                  session=rnd.choice([1, 4, 9, 10, 11, 14]), wk_pnl=wk)
        q0 = rnd.choice([1, 5, 40, 100])
        r = sz.lit_qty(q0, {"risk_pts": risk, "tgt_pts": rnd.choice([1.5 * risk, 3 * risk, 200.0]), "size_mult": 1.0}, cfg,
                       room=room, state=s, learning=None)
        q = int(r["qty"])
        lims = [(room, True), (1000.0 + cum, False)] + ([(float(wl) + wk, False)] if wl and wk is not None else [])
        if mode == "two_week" and s["session"] <= int(base.get("two_week_until") or 10):
            lims.append((float((base.get("two_week") or {}).get("room_f") or 1.0) * room, False))   # the room share (0.8 live)
        fits1 = all((L1(risk) < lim) if strict else (L1(risk) <= lim + 1e-9) for lim, strict in lims)
        if q and not all((q * L1(risk) < lim) if strict else (q * L1(risk) <= lim + 1e-9) for lim, strict in lims):
            bad.append((mode, risk, room, cum, wk, q))
        if q and not fits1:
            bad1.append((mode, risk, room, cum, wk, q))
        if q > 40:
            maxq_bad.append((mode, q0, q))
    wk_txt = f"the ${float(wl):,.0f} weekly loss" if wl else "no weekly stop (wk_loss_usd null)"
    check(f"1 LIT ({n} random eval states, {label}, every eval mode): qty x (stop + 1 tick, $1.90) inside the room, "
          f"the two_week room share, the $1,000 soft daily loss and {wk_txt}", not bad, bad[:4])
    check(f"1 LIT ({label}): when 1 micro does not fit a ceiling the entry is skipped (never 1 micro)", not bad1, bad1[:4])
    check(f"2 LIT ({label}): a model asking for 100 micros never routes more than 40", not maxq_bad, maxq_bad[:4])


def part_caps(n=3000, seed=25):
    rnd = random.Random(seed)
    # the live config (owner 2026-10-25: room_f 0.8, no weekly stop) and the pinned one with the $1,200 weekly stop ON
    lit_caps(rnd, n, LSZ, "live lit_sizing")
    lit_caps(rnd, n, PINNED, "pinned: room_f 0.55 + $1,200 weekly stop")
    # ATLAS on LIT's account
    bad = []
    for _ in range(n):
        mode = rnd.choice(EVAL_MODES)
        risk = rnd.choice([6.0, 15.0, 30.0, 60.0, 120.0, 240.0, 260.0])
        room = rnd.choice([40.0, 120.0, 400.0, 1500.0, 2500.0])
        cum = rnd.choice([0.0, -400.0, -980.0])
        r = sz.second_qty(risk, 500.0, {**LSZ, "mode": mode}, state=st_of(cum=cum, room=room, wk_pnl=rnd.choice([None, -900.0])),
                          max_micros=40)
        q = r["qty"]
        if q and not (q * L1(risk) <= 0.6 * room + 1e-9 and q * L1(risk) < room and q * L1(risk) <= 1000 + cum + 1e-9
                      and L1(risk) <= 500.0 and q <= 40):
            bad.append((mode, risk, room, cum, q))
    check(f"1 ATLAS on LIT's account ({n} states): qty x loss inside 60% room, the room, the soft daily loss, $500, 40 micros",
          not bad, bad[:4])
    # account B
    bad = []
    for plan in ("builder25k", "builder50k"):
        for sizing in ("need", "safe"):
            sp = AB.normalize({"account": "SimB", "plan": plan, "eval_start": "2026-10-19", "sizing": sizing}, scfg={"strategies": {}})
            dll, mx = float(sp["rules"]["dll"]), int(sp["rules"]["max_micros"])
            for _ in range(n // 4):
                risk = rnd.choice([6.0, 12.0, 20.0, 35.0, 50.0, 88.0, 110.0])
                room = rnd.choice([40.0, 90.0, 150.0, 300.0, 700.0, 1000.0, 2000.0])
                cum = rnd.choice([0.0, -200.0, -dll + 40.0, 100.0])
                q = AB.qty(sp, {"risk_pts": risk, "tgt_pts": rnd.choice([60.0, 200.0, 400.0])},
                           st_of(profit=rnd.choice([-900.0, 0.0, 600.0]), cum=cum, room=room, session=rnd.choice([1, 5, 11, 13])),
                           base=LSZ)["qty"]
                if q and not (q * L1(risk) < room and q * L1(risk) <= dll + cum + 1e-6 and q <= mx):
                    bad.append((plan, sizing, risk, room, cum, q))
    check("1+2 account B (25K / 50K, need / safe): inside the room, the plan's soft daily loss, 20 / 40 micros", not bad, bad[:4])
    # extra account
    bad = []
    for preset, dll, mx in (("mffu_builder_25k", 600.0, 20), ("mffu_builder_50k", 1000.0, 40)):
        for mode in ("two_week", "safe_eval", "eval"):
            a = extra_account(preset, mode)
            for _ in range(150):
                risk = rnd.choice([8.0, 20.0, 40.0, 70.0])
                loss = rnd.choice([0.0, -300.0, -float(a.rules["mll"]) + 120.0, -float(a.rules["mll"]) + 400.0])
                today = rnd.choice([0.0, -dll + 60.0, -200.0])
                a.closes = [("2026-10-20", NOW - 86400, loss, NOW - 90000)] + ([("2026-10-21", NOW - 600, today, NOW - 900)] if today else [])
                st = a.state("2026-10-21")
                q = a.qty_for({"qty": 100, "risk_pts": risk, "tgt_pts": 3 * risk, "entry_t": NOW, "dir": 1}, NOW)
                if q and not (q * L1(risk) < st["room"] and q * L1(risk) <= dll + today + 1e-6 and q <= mx):
                    bad.append((preset, mode, risk, loss, today, q, st["room"]))
    check("1+2 extra accounts (25K / 50K, two_week / safe_eval / eval, model 100 micros): inside the room, the account's daily "
          "loss and its 20 / 40 micros", not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ 3
def fake_bot(**kw):
    b = types.SimpleNamespace(state=kw.get("state") or {}, _open_routed=kw.get("open_routed"), _open_src=kw.get("open_src"),
                              ledger=kw.get("ledger") or [], accts=None, cfg={"adapter": "paper", "sym": "NQ"}, health={},
                              kill=False, state_path=None, logs=[], pushed=[], _no_entries_day=None)
    b.clock = lambda: NOW
    b._log = lambda kind, text, **k: b.logs.append((kind, text))
    b._note_error = lambda text: b.logs.append(("error", text))
    b._push_send = lambda p: b.pushed.append(p)
    return b


def part_reservations():
    busy = lambda **kw: live.LiveBot._lit_busy(fake_bot(**kw))
    check("3 LIT's account: a second-strategy entry waits while LIT holds a trade / is entering / has a limit armed / waits "
          "for its 1m CISD / still has a routed position",
          busy(state={"position": {"dir": 1}}) and busy(state={"enter_now": {"dir": -1}})
          and "limit" in (busy(state={"setups": {"long": {"tapped_t": None}}}) or "")
          and "1m CISD" in (busy(state={"setups": {"short": {"tapped_t": NOW - 60}}}) or "")
          and busy(open_routed=NOW - 300, open_src=None) and busy() is None)
    import pandas as pd
    tmp = tempfile.mkdtemp()
    sp = AB.normalize({"account": "SimB", "plan": "builder25k", "eval_start": "2026-10-19"}, scfg={"strategies": {}})
    B = AB.AccountB(fake_bot(), sp, state_path=os.path.join(tmp, "b.json"))
    B.adapter = live.PaperAdapter({})
    tb = NOW - NOW % 300
    df5 = pd.DataFrame({"time": [tb - 300], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]})
    B.open_t = tb - 600                                # an entry sent (pending at the broker, or filled)
    B.bot.clock = lambda: tb + 2
    B.entry(df5, None, {"strategies": {}}, ["ema_lon_vix"], "NQ", tb + 2)
    check("3 account B: while its own entry is sent / pending / open it does not even probe a new one (one position)",
          ("probe", tb) not in B.seen and not B.ledger, (B.seen, B.ledger))
    sp50 = extra_account("mffu_builder_50k", "two_week")
    sp50.adapter = live.PaperAdapter({})
    sp50.ledger = [{"side": "buy", "entry_t": NOW - 1200, "t": NOW - 1200, "qty": 3, "result": {"ok": True}}]
    check("3 extra account: 1 entry a day (an entry already sent today blocks the next)",
          "1 trade a day" in (sp50.entry_block(NOW) or ""), sp50.entry_block(NOW))


# ------------------------------------------------------------------------------------------------ 4 + 5
def part_costs_ticks():
    check("4 every cap prices 1 micro at (stop + 1 tick) x $2 + $1.90 (sizing.loss_1micro, TW_COMM, SECOND_COMM, account B)",
          abs(sz.loss_1micro(20.0) - 42.4) < 1e-9 and sz.TW_COMM == 1.90 and sz.SECOND_COMM == 1.90 and sz.TW_SLIP == 0.25
          and sz.SECOND_TICK == 0.25 and AB.COMM == 1.90)
    r = sz.lit_qty(10, {"risk_pts": 20.0, "tgt_pts": 100.0}, {**LSZ, "mode": "safe_eval"}, room=100.0, state=st_of(room=100.0, session=12))
    check("4 safe_eval: room $100, 20-pt stop: 60% = $60 fits 1 micro at $42.40 (not 2 at $40 without costs)", r["qty"] == 1, r)
    check("4 KNOWN GAP (not changed): engine/lit.py books routed LIT P&L at $1.40 a micro, MFFU charges $1.90 "
          "(the eval anchor corrects the book; research/handoff/2026-10-25/COMMISSION_DRIFT.csv)", lit.COMM == 1.40)
    rnd = random.Random(3)
    ok = True
    for _ in range(4000):
        px = round(rnd.uniform(15000, 30000), rnd.choice([2, 3, 4]))
        for d in (1, -1):
            s = live.tick_px(px, d)
            g = live.tick_px(px, d, target=True)
            ok &= abs(s * 4 - round(s * 4)) < 1e-9 and abs(s - px) <= 0.125 + 1e-9
            ok &= abs(g * 4 - round(g * 4)) < 1e-9 and (g <= px + 1e-9 if d == 1 else g >= px - 1e-9) and abs(g - px) < 0.25
    on = all(live.tick_px(x / 4.0, d) == x / 4.0 for x in range(80000, 80100) for d in (1, -1))
    check("5 tick rounding: stops to the nearest 0.25 tick (an on-grid stop is never moved), targets toward the entry",
          ok and on)
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    df = df[df["time"] >= 1767225600]                 # 2026
    off = int(sum(((df[c] * 4 - (df[c] * 4).round()).abs() > 1e-6).sum() for c in ("open", "high", "low", "close")))
    check(f"5 the 2026 NQ 1m bars are on the 0.25 grid ({len(df):,} bars, {off} off-grid prices): a stop 1 tick beyond a "
          "sweep extreme is on the grid, tick_px never moves it", off == 0, off)


# ------------------------------------------------------------------------------------------------ 6 + 7
def stop_mover(last_stop, d, entry):
    sent = []
    b = types.SimpleNamespace(ledger=[{"entry_t": 1, "side": "buy" if d == 1 else "sell", "stop": last_stop}], _modify_gaveup=set(),
                              adapter=types.SimpleNamespace(has_open_bracket=lambda et: True), _open_qty=2,
                              _route=lambda a: sent.append(a), _log=lambda *a, **k: None)
    b._broker_stop = lambda et: live.LiveBot._broker_stop(b, et)
    return b, sent


def part_stops():
    out = []
    for d, entry, stop0 in ((1, 20000.0, 19980.0), (-1, 20000.0, 20020.0)):
        for new, want in ((stop0 - 5 * d, False), (stop0 + 5 * d, True), (entry + 1.25 * d, True)):
            b, sent = stop_mover(stop0, d, entry)
            live.LiveBot._route_stop_move(b, {"entry_t": 1, "dir": d, "stop": new, "entry": entry, "qty": 2}, "NQ")
            out.append((d, new, want, bool(sent), sent[0]["reason"] if sent else None))
    check("6 broker stop moves only tighten: a wider stop (long lower / short higher) is never sent, a tighter one is",
          all(w == s for _, _, w, s, _ in out), out)
    be = [x for x in out if abs(x[1] - (20000.0 + 1.25 * x[0])) < 1e-9]
    check("7 short breakeven: the modify to entry - 1.25 (long entry + 1.25) is accepted and labelled BE",
          len(be) == 2 and all(x[3] and x[4] == "BE" for x in be), be)
    from tools import runlib as rl
    r = rl.load("lit_live")
    T = [dict(zip(r["trade_cols"], x)) for x in r["trades"] if x[0] >= "2026-01-01"]
    stp = [t for t in T if t["exit"] == "STOP"]
    bad = [t for t in stp if abs(t["pnl"] - t["qty"] * (-(t["risk_pts"] + lit.SLIP) * lit.PV - lit.COMM)) > 0.02 * t["qty"] + 0.01]
    check(f"6 every 2026 STOP exit of run lit_live ({len(stp)}: {sum(t['dir'] == 1 for t in stp)} long / "
          f"{sum(t['dir'] == -1 for t in stp)} short) lost exactly the sized stop + 1 tick + costs (stop never widened)",
          stp and not bad, bad[:3])
    bes = [t for t in T if t["exit"] == "BE"]
    badb = [t for t in bes if abs(t["pnl"] / t["qty"] - ((1.25 - lit.SLIP) * lit.PV - lit.COMM)) > 0.011]
    check(f"7 every 2026 BE exit ({len(bes)}: {sum(t['dir'] == 1 for t in bes)} long / {sum(t['dir'] == -1 for t in bes)} short) "
          "made +1.0 pt a micro (BE at entry + 1.25 in the trade's favour, 1 tick slippage) on both sides",
          bes and not badb and any(t["dir"] == -1 for t in bes), badb[:3])
    # the live loop itself on a 2026 short BE trade: one poll on the open of its exit bar shows the stop at entry - 1.25
    try:
        import numpy as np
        import pandas as pd
        from engine import lit_live
        from engine.data import load, load_ltf
        from tools import lit_adopt_combo as AC
        P = {**AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF}
        t = next(t for t in bes if t["dir"] == -1 and t["day"] >= "2026-03-01" and t["exit_t"] - t["entry_t"] >= 600)
        df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        df5 = df5[(df5["time"] >= t["entry_t"] - 70 * 86400)].reset_index(drop=True)
        b1, _ = load_ltf("NQ", load("NQ", "5m"))
        b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
        now = int(t["exit_t"]) - 60                    # exit_t = the exit bar's close: poll 1 minute before it
        now = now - now % 60 + 5
        cut5 = df5.iloc[:int(np.searchsorted(df5["time"].values + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        pos = lit_live.run(cut5, P, one_min=cut1, now=now, early=True)["state"].get("position") or {}
        e, s = float(pos.get("entry") or 0), float(pos.get("stop") or 0)
        check(f"7 live loop, short {t['day']} (BE exit): the open position's stop {s:.2f} = entry {e:.2f} - 1.25 (below the entry)",
              int(pos.get("dir") or 0) == -1 and abs(s - (e - 1.25)) < 0.13 and s < e, pos)
    except StopIteration:
        check("7 live loop: a 2026 short BE trade to poll", False)


# ------------------------------------------------------------------------------------------------ 8
def part_lock():
    c = dict(LSZ)
    out = {m: sz.lit_qty(10, {"risk_pts": 20.0, "tgt_pts": 60.0}, {**c, "mode": m}, room=2500.0,
                         state=st_of(profit=3010.0, room=2500.0, session=s, days_traded=3), learning=None)["qty"]
           for m, s in (("two_week", 4), ("two_week", 12), ("eval", 4), ("safe_eval", 4), ("fast_eval", 4))}
    md = sz.lit_qty(10, {"risk_pts": 20.0, "tgt_pts": 60.0}, c, room=2500.0, state=st_of(profit=3010.0, room=2500.0, session=4, days_traded=1),
                    learning=None)
    md0 = sz.lit_qty(10, {"risk_pts": 30.0, "tgt_pts": 60.0}, c, room=50.0, state=st_of(profit=3010.0, room=50.0, session=4, days_traded=1),
                     learning=None)
    check("8 LIT passed (+$3,010): 0 micros in every eval mode (also after session 10); the minimum-days trade is 1 micro "
          "and is skipped when it does not fit", not any(out.values()) and md["qty"] == 1 and md0["qty"] == 0, (out, md, md0))
    s2 = sz.second_qty(20.0, 500.0, {**c, "mode": "two_week"}, state=st_of(profit=3010.0, room=2500.0))
    sp = AB.normalize({"account": "SimB", "plan": "builder25k", "eval_start": "2026-10-19"}, scfg={"strategies": {}})
    b = AB.qty(sp, {"risk_pts": 20.0, "tgt_pts": 60.0}, st_of(profit=1510.0, room=1500.0, days_traded=3), base=LSZ)
    a = extra_account("mffu_builder_25k", "two_week")
    a.closes = [("2026-10-20", NOW - 86400, 1600.0, NOW - 90000), ("2026-10-19", NOW - 2 * 86400, 10.0, NOW - 2 * 86400 - 60)]
    q = a.qty_for({"qty": 10, "risk_pts": 20.0, "tgt_pts": 60.0, "entry_t": NOW, "dir": 1}, NOW)
    check("8 passed -> 0 on ATLAS on LIT's account, account B 25K (+$1,510) and an extra 25K account (+$1,610)",
          s2["qty"] == 0 and b["qty"] == 0 and q == 0, (s2, b, q, a.last_size))


# ------------------------------------------------------------------------------------------------ 9
def part_unknown():
    nan = float("nan")
    res = {}
    for m in EVAL_MODES:
        for lab, tr in (("none", {"tgt_pts": 60.0}), ("zero", {"risk_pts": 0.0, "tgt_pts": 60.0}), ("nan", {"risk_pts": nan, "tgt_pts": 60.0}),
                        ("empty", {})):
            try:
                res[(m, lab)] = sz.lit_qty(10, tr, {**LSZ, "mode": m}, room=60.0, state=st_of(room=60.0, session=3), learning=None)["qty"]
            except (ValueError, TypeError):
                res[(m, lab)] = "raises"
    check("9 BUG_FIX LIT eval modes: stop distance unknown / 0 / NaN -> 0 micros or an exception (the live caller fails "
          "closed), never the model's 10 micros uncapped (was 10 with a $60 room)",
          all(v in (0, "raises") for v in res.values()), res)
    n = sz.lit_qty(10, {}, {"mode": "normal"}, learning=None)["qty"]
    check("9 mode normal is unchanged by the fix (no eval ceilings: the model's micros)", n == 10, n)
    a = extra_account("mffu_builder_25k", "two_week", start="")
    q = a.qty_for({"qty": 30, "risk_pts": 10.0, "tgt_pts": 40.0, "entry_t": NOW, "dir": 1}, NOW)
    check("9 BUG_FIX extra account in an eval mode without eval_start (state unknown) -> 0 (was the eval fallback with no room "
          "cap, up to the 20-micro max)", q == 0, a.last_size)
    sp = AB.normalize({"account": "SimB", "plan": "builder25k", "eval_start": "2026-10-19"}, scfg={"strategies": {}})
    check("9 account B: eval state unknown -> 0; ATLAS on LIT's account: room unknown in an eval mode -> 0",
          AB.qty(sp, {"risk_pts": 20.0, "tgt_pts": 60.0}, None)["qty"] == 0
          and sz.second_qty(20.0, 500.0, {**LSZ, "mode": "two_week"}, state=None, room=None)["qty"] == 0)
    # LiveBot._equity_qty: a sizing exception on an eval account -> 0 (never the engine's size)
    bot = live.LiveBot()
    bot.state_path = os.path.join(tempfile.mkdtemp(), "live_state.json")
    bot.state = {"model": "lit"}
    bot._lit_sizing = dict(LSZ)
    bot.cfg = {"eval_start": "2026-10-19"}
    old = sz.lit_qty

    def boom(*a, **k):
        raise ValueError("cannot convert float NaN to integer")
    sz.lit_qty = boom
    try:
        q = bot._equity_qty(NOW, 12, {"entry": 20000.0, "stop": 19980.0, "target": 20100.0, "dir": 1, "entry_t": NOW})
    finally:
        sz.lit_qty = old
    check("9 LIT on its eval: a sizing exception (e.g. a NaN in the eval state) routes 0, not the engine's 12 micros", q == 0, q)
    r = bot.eval_room()
    check(f"9 LIT live path always prices the room: LiveBot.eval_room() on an empty ledger = ${r:,.0f} (a number, never None)",
          isinstance(r, float) and math.isfinite(r), r)


def main():
    part_caps()
    part_reservations()
    part_costs_ticks()
    part_stops()
    part_lock()
    part_unknown()
    print(f"risk invariants: {sum(RESULTS)}/{len(RESULTS)} passed")
    return all(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
