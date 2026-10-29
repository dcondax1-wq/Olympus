"""Holodeck front-end fixture (2026-10-29): a realistic holo.json + holo_hist.json built from the real data, for the UI tests
and screenshots until engine/holo_api.py's own fixture lands.

    python tests/make_holo_fe_fixture.py        -> tests/fixtures/holo_fe_sample.json  ({"holo": ..., "hist": ...})

Bars: data/NQ_1m.csv (TradingView CME NQ1!, 2026). Trades: the LIT live-settings replay (research/lab/backtest_live.json), the
ATLAS research ledgers (research/second/{ema,md,sr}_best.json) and BLITZ (research/scalp/mo_best_trades.json). The "real"
Zlarior fills are mocked 1 tick worse than the model (the twin), the stop moves to break-even (+1.25 pts costs) at 1R, and
the thoughts are narrator-like lines at each step. Shape = the holo.json contract (v 1, kind le-holo). Mock data: PAPER only.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ET = ZoneInfo("America/New_York")
TICK = 0.25
DAYS = ["2026-10-13", "2026-10-07", "2026-10-01", "2026-09-23"]
BOTS = {"lit": {"name": "Zlarior", "color": "#4f9bff", "account": "MFFU Builder 50K", "real": True, "plan": "LIT: sweep -> inducement -> displacement -> 5m CISD -> limit, then 1m CISD"},
        "atlas": {"name": "ATLAS", "color": "#ff9a3d", "account": "paper (account B)", "real": False, "plan": "EMA 21/50 pullback + MACD divergence + S/R reclaim"},
        "blitz": {"name": "BLITZ", "color": "#b388ff", "account": "paper (BLITZ 25K, off)", "real": False, "plan": "09:30 noise band scalp, 30-minute checks, time exit"}}


def et(day: str, hm: str, prev: bool = False) -> int:
    d = datetime.strptime(day + " " + hm, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    if prev:
        d -= timedelta(days=1)
    return int(d.timestamp())


def load_1m(t0: int, t1: int) -> list:
    out = []
    with open(ROOT / "data" / "NQ_1m.csv") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            t = int(row[0])
            if t < t0:
                continue
            if t >= t1:
                break
            out.append([t, float(row[1]), float(row[2]), float(row[3]), float(row[4]), int(float(row[5]))])
    return out


def agg5(b1: list) -> list:
    out = {}
    for t, o, h, l, c, v in b1:
        k = t - t % 300
        if k not in out:
            out[k] = [k, o, h, l, c, v]
        else:
            x = out[k]
            x[2] = max(x[2], h); x[3] = min(x[3], l); x[4] = c; x[5] += v
    return [out[k] for k in sorted(out)]


def rnd(x: float) -> float:
    return round(round(x / TICK) * TICK, 2)


def atr5(b5: list, t: int, n: int = 14) -> float:
    rows = [b for b in b5 if b[0] < t][-n - 1:]
    if len(rows) < 2:
        return 20.0
    tr = [max(b[2] - b[3], abs(b[2] - a[4]), abs(b[3] - a[4])) for a, b in zip(rows, rows[1:])]
    return sum(tr) / len(tr)


def rng_hl(b1: list, a: int, b: int):
    xs = [x for x in b1 if a <= x[0] < b]
    if not xs:
        return None, None
    return max(x[2] for x in xs), min(x[3] for x in xs)


def first_cross(b1: list, t_from: int, px: float, up: bool):
    for x in b1:
        if x[0] < t_from:
            continue
        if (up and x[2] >= px) or (not up and x[3] <= px):
            return x[0]
    return None


def lit_levels(day: str, b1: list, b5: list) -> list:
    lv = []
    spans = [("Asia", et(day, "20:00", True), et(day, "00:00")), ("Frankfurt", et(day, "02:00"), et(day, "03:00")),
             ("London", et(day, "03:00"), et(day, "05:00"))]
    for name, a, b in spans:
        hi, lo = rng_hl(b1, a, b)
        if hi is None:
            continue
        lv.append({"bot": "lit", "px": hi, "label": f"{name} high", "t0": a, "t1": b, "taken_t": first_cross(b1, b, hi, True)})
        lv.append({"bot": "lit", "px": lo, "label": f"{name} low", "t0": a, "t1": b, "taken_t": first_cross(b1, b, lo, False)})
    o18 = next((x[1] for x in b1 if x[0] >= et(day, "18:00", True)), b1[0][1])
    lv.append({"bot": "lit", "px": o18, "label": "18:00 open", "t0": et(day, "18:00", True), "t1": None, "taken_t": None})
    return lv


def mk_trade_lit(day: str, tr: dict, b1: list, b5: list, fid: list, thoughts: list, orders: list, fills: list, idx: int):
    short = tr["side"] == "SHORT"
    sgn = -1 if short else 1
    risk = abs(tr["entry"] - tr["stop"])
    qty = max(1, min(15, round(900 / (risk * 2))))
    tid = f"lit-{day}-{idx}"
    t_entry = tr["entry_t"] + 7
    real_entry = rnd(tr["entry"] + sgn * TICK)      # 1 tick worse than the model: a SELL fills lower, a BUY higher
    a5 = atr5(b5, tr["entry_t"])
    ext = tr.get("sweep_ext") or (tr["stop"] + sgn * TICK)
    win = [x for x in b1 if tr["entry_t"] - 4 * 3600 <= x[0] < tr["entry_t"]]
    # the sweep: the bar that made the extreme before the entry
    sw = min(win, key=lambda x: abs((x[2] if short else x[3]) - ext)) if win else b1[0]
    t_sweep = sw[0] + 30
    depth = tr.get("depth_atr") or 1.0
    level = rnd(ext + sgn * min(depth * a5, 0.35 * risk))      # the swept level: just inside the extreme
    pools = tr.get("pools") or ["level"]
    swept = [{"px": rnd(level + sgn * k * 3.5), "label": p} for k, p in enumerate(pools)]
    pre = [x for x in b1 if t_sweep - 50 * 60 <= x[0] < t_sweep - 6 * 60]
    idm = (max(pre, key=lambda x: x[2]) if short else min(pre, key=lambda x: x[3])) if pre else sw
    t_idm = idm[0] + 30
    cisd = tr.get("cisd_level") or rnd(tr["entry"] - sgn * 5)
    post5 = [x for x in b5 if t_sweep - 300 <= x[0] < tr["entry_t"]]
    t_cisd = next((x[0] + 300 for x in post5 if (x[4] < cisd if short else x[4] > cisd)), tr["entry_t"] - 600)
    disp = max([x for x in post5 if x[0] < t_cisd] or post5 or [sw], key=lambda x: abs(x[4] - x[1]))
    t_disp = disp[0] + 150
    # BE: the first 1m bar that reached 1R in favour moves the stop to entry + 1.25 (costs)
    one_r = tr["entry"] + sgn * risk
    be_t = None
    for x in b1:
        if tr["entry_t"] <= x[0] <= tr["exit_t"]:
            if (short and x[3] <= one_r) or (not short and x[2] >= one_r):
                be_t = x[0] + 41
                break
    be_px = rnd(tr["entry"] + sgn * 1.25)
    stop_path = [[t_entry, tr["stop"]]] + ([[be_t, be_px]] if be_t else [])
    ex_kind = {"TARGET": "target", "STOP": "stop", "BE": "stop"}.get(tr["exit"], "exit")
    ex_px = tr["exit_price"]
    if ex_kind == "stop":
        ex_px = rnd(ex_px - sgn * TICK)              # stop: 1 tick slippage
    t_exit = tr["exit_t"] + (0 if ex_kind == "target" else 3)
    usd = round((ex_px - real_entry) * sgn * 2 * qty - 1.24 * qty, 2)
    model_usd = round((tr["exit_price"] - tr["entry"]) * sgn * 2 * qty - 1.24 * qty, 2)
    side_in, side_out = ("SELL", "BUY") if short else ("BUY", "SELL")
    fid[0] += 1
    fills.append({"id": f"f{fid[0]}", "t": t_entry, "px": real_entry, "qty": qty, "side": side_in, "kind": "entry", "bot": "lit", "acct": "MFFU 50K",
                  "real": True, "src": "ninjatrader", "model_px": tr["entry"], "slip_ticks": 1, "trade": tid})
    fid[0] += 1
    fills.append({"id": f"f{fid[0]}", "t": t_exit, "px": ex_px, "qty": qty, "side": side_out, "kind": ex_kind, "bot": "lit", "acct": "MFFU 50K",
                  "real": True, "src": "ninjatrader", "model_px": tr["exit_price"], "slip_ticks": round(abs(ex_px - tr["exit_price"]) / TICK), "trade": tid})
    # orders: the 30-minute limit after the 5m CISD (tapped, then the 1m CISD market entry), the stop (moved to BE), the target
    lim_px = rnd(cisd - sgn * 2.0)
    orders.append({"t": t_cisd + 5, "t_end": min(t_cisd + 1800, tr["entry_t"]), "bot": "lit", "acct": "MFFU 50K", "type": "LIMIT", "side": side_in,
                   "px": lim_px, "qty": qty, "state": "CANCELLED", "why": "5m CISD limit (30 min): tapped, then the 1m CISD entry at market"})
    orders.append({"t": t_entry, "t_end": be_t or t_exit, "bot": "lit", "acct": "MFFU 50K", "type": "STOP", "side": side_out, "px": tr["stop"], "qty": qty,
                   "state": "CANCELLED" if be_t else ("FILLED" if ex_kind == "stop" else "CANCELLED"), "why": "protective stop 1 tick beyond the sweep extreme"})
    if be_t:
        orders.append({"t": be_t, "t_end": t_exit, "bot": "lit", "acct": "MFFU 50K", "type": "STOP", "side": side_out, "px": be_px, "qty": qty,
                       "state": "FILLED" if ex_kind == "stop" else "CANCELLED", "why": "break-even at 1R: entry + 1.25 pts (costs)"})
    orders.append({"t": t_entry, "t_end": t_exit, "bot": "lit", "acct": "MFFU 50K", "type": "LIMIT", "side": side_out, "px": tr["target"], "qty": qty,
                   "state": "FILLED" if ex_kind == "target" else "CANCELLED", "why": "target: 18:00 open +/- 1 VIX day move"})
    f = lambda x: f"{x:,.2f}"
    S = "short" if short else "long"
    thoughts += [
        {"t": t_idm, "bot": "lit", "stage": "inducement", "title": "Inducement", "text": f"A swing at {f(idm[2] if short else idm[3])} sits inside 1 ATR of the level: the inducement the sweep should run through.", "level": "dim", "px": idm[2] if short else idm[3]},
        {"t": t_sweep, "bot": "lit", "stage": "sweep", "title": "Sweep", "text": f"Swept {', '.join(pools)} (extreme {f(ext)}, {depth:.2f} ATR past the level). Waiting for a displacement back.", "level": "warn", "px": ext},
        {"t": t_disp, "bot": "lit", "stage": "displacement", "title": "Displacement", "text": f"Biggest body {tr.get('disp') or 1.0:.2f} ATR away from the sweep: real sellers." if short else f"Biggest body {tr.get('disp') or 1.0:.2f} ATR off the low: real buyers.", "level": "info", "px": disp[4]},
        {"t": t_cisd, "bot": "lit", "stage": "cisd", "title": "5m CISD", "text": f"5m close through {f(cisd)}: limit {side_in} {qty} MNQ @ {f(lim_px)} for 30 min.", "level": "good", "px": cisd},
        {"t": t_entry, "bot": "lit", "stage": "entry", "title": f"In {S}", "text": f"1m CISD: {side_in} {qty} MNQ filled @ {f(real_entry)} (model {f(tr['entry'])}, 1 tick slip). Stop {f(tr['stop'])}, target {f(tr['target'])}.", "level": "good", "px": real_entry},
        {"t": t_entry + 15 * 60, "bot": "lit", "stage": "check", "title": "15-minute check", "text": "Passed: the trade reached +0.5R or is not 0.3R under water. Holding.", "level": "info", "px": None},
    ]
    if be_t:
        thoughts.append({"t": be_t, "bot": "lit", "stage": "be", "title": "Break-even", "text": f"+1R reached: stop moved to {f(be_px)} (entry + 1.25 pts costs). The trade can no longer lose.", "level": "good", "px": be_px})
    thoughts.append({"t": t_exit, "bot": "lit", "stage": "exit", "title": {"target": "Target hit", "stop": "Stopped" if not be_t else "Break-even exit"}.get(ex_kind, "Exit"),
                     "text": f"{tr['exit']} @ {f(ex_px)}: {'+' if usd >= 0 else '-'}${abs(usd):,.0f} ({tr['r']:+.2f}R). Done for the day (1 trade a day).", "level": "good" if usd > 0 else "bad", "px": ex_px})
    return {"id": tid, "bot": "lit", "acct": "MFFU 50K", "real": True, "side": tr["side"], "qty": qty, "entry": {"t": t_entry, "px": real_entry},
            "exit": {"t": t_exit, "px": ex_px, "reason": tr["exit"]}, "stop_path": stop_path, "target": tr["target"], "risk_usd": round(risk * 2 * qty, 2),
            "usd": usd, "r": tr["r"], "model": {"entry_t": tr["entry_t"], "entry": tr["entry"], "exit_t": tr["exit_t"], "exit": tr["exit_price"], "usd": model_usd},
            "setup": {"kind": "LIT", "t_sweep": t_sweep, "sweep_ext": ext, "swept": swept, "t_idm": t_idm, "t_disp": t_disp, "t_cisd": t_cisd, "cisd": cisd,
                      "notes": (tr.get("report") or {}).get("why") or []}}


def mk_trade_paper(bot: str, day: str, k: int, d: dict, fid: list, thoughts: list, orders: list, fills: list) -> dict:
    short = d["dir"] in (-1, "short")
    sgn = -1 if short else 1
    tid = f"{bot}-{day}-{k}"
    qty = int(d.get("qty") or 4)
    side_in, side_out = ("SELL", "BUY") if short else ("BUY", "SELL")
    t_in, t_out = int(d["entry_t"]) + 2, int(d["exit_t"]) + 1
    kind = {"TARGET": "target", "stop": "stop", "STOP": "stop", "BE": "stop", "flat": "flatten"}.get(d.get("exit_kind"), "exit")
    for t, px, sd, kd in [(t_in, d["entry"], side_in, "entry"), (t_out, d["exit"], side_out, kind)]:
        fid[0] += 1
        fills.append({"id": f"f{fid[0]}", "t": t, "px": px, "qty": qty, "side": sd, "kind": kd, "bot": bot, "acct": "paper", "real": False, "src": "paper",
                      "model_px": px, "slip_ticks": 0, "trade": tid})
    usd = round((d["exit"] - d["entry"]) * sgn * 2 * qty, 2)
    name = BOTS[bot]["name"]
    setup = d.get("setup") or ("noise-band scalp" if bot == "blitz" else "ATLAS")
    thoughts.append({"t": t_in - 40, "bot": bot, "stage": "signal", "title": f"{name} signal", "text": f"{setup}: {'short' if short else 'long'} @ {d['entry']:,.2f}, stop {d['stop']:,.2f}" + (f", target {d['target']:,.2f}" if d.get("target") else ", time exit") + ". PAPER only.", "level": "info", "px": d["entry"]})
    thoughts.append({"t": t_out, "bot": bot, "stage": "exit", "title": f"{name} {kind}", "text": f"PAPER exit @ {d['exit']:,.2f}: {'+' if usd >= 0 else '-'}${abs(usd):,.0f} ({(d.get('r') or 0):+.2f}R).", "level": "good" if usd > 0 else "bad" if usd < 0 else "dim", "px": d["exit"]})
    orders.append({"t": t_in, "t_end": t_out, "bot": bot, "acct": "paper", "type": "STOP", "side": side_out, "px": d["stop"], "qty": qty, "state": "FILLED" if kind == "stop" else "CANCELLED", "why": "paper stop"})
    sp = [[t_in, d["stop"]]]
    if d.get("exit_kind") == "BE":
        sp.append([max(t_in + 60, t_out - 900), d["entry"]])
    return {"id": tid, "bot": bot, "acct": "paper", "real": False, "side": "SHORT" if short else "LONG", "qty": qty, "entry": {"t": t_in, "px": d["entry"]},
            "exit": {"t": t_out, "px": d["exit"], "reason": str(d.get("exit_kind") or "exit").upper()}, "stop_path": sp, "target": d.get("target"),
            "risk_usd": round(abs(d["entry"] - d["stop"]) * 2 * qty, 2), "usd": usd, "r": d.get("r"), "model": None,
            "setup": {"kind": setup, "t_sweep": None, "sweep_ext": None, "swept": [], "t_idm": None, "t_disp": None, "t_cisd": None, "cisd": None, "notes": [setup]}}


def build_day(day: str, lit_tr: list, atlas_tr: list, blitz_tr: list) -> dict:
    t0, t1 = et(day, "01:00"), et(day, "16:15")
    b1 = load_1m(et(day, "18:00", True), t1)
    b5 = agg5(b1)
    fills, orders, thoughts, trades, fid = [], [], [], [], [0]
    levels = lit_levels(day, b1, b5)
    for i, tr in enumerate(lit_tr):
        trades.append(mk_trade_lit(day, tr, b1, b5, fid, thoughts, orders, fills, i))
    for k, d in enumerate(atlas_tr):
        trades.append(mk_trade_paper("atlas", day, k, d, fid, thoughts, orders, fills))
    for k, d in enumerate(blitz_tr):
        trades.append(mk_trade_paper("blitz", day, k, d, fid, thoughts, orders, fills))
    # ATLAS S/R: the prior day's last two swing extremes; BLITZ: the 09:30 open +/- sigma band
    hi_p, lo_p = rng_hl(b1, et(day, "09:30", True), et(day, "16:00", True))
    if hi_p is not None:
        levels.append({"bot": "atlas", "px": hi_p, "label": "S/R prior day high", "t0": t0, "t1": None, "taken_t": first_cross(b1, t0, hi_p, True)})
        levels.append({"bot": "atlas", "px": lo_p, "label": "S/R prior day low", "t0": t0, "t1": None, "taken_t": first_cross(b1, t0, lo_p, False)})
    o930 = next((x[1] for x in b1 if x[0] >= et(day, "09:30")), None)
    if o930:
        sig = rnd(a5 * 2.2) if (a5 := atr5(b5, et(day, "09:30"))) else 30
        levels.append({"bot": "blitz", "px": rnd(o930 + sig), "label": "BLITZ band up", "t0": et(day, "09:30"), "t1": et(day, "16:00"), "taken_t": first_cross(b1, et(day, "09:30"), o930 + sig, True)})
        levels.append({"bot": "blitz", "px": rnd(o930 - sig), "label": "BLITZ band low", "t0": et(day, "09:30"), "t1": et(day, "16:00"), "taken_t": first_cross(b1, et(day, "09:30"), o930 - sig, False)})
    thoughts += [
        {"t": et(day, "01:05"), "bot": "sys", "stage": "feed", "title": "Feed live", "text": "NinjaTrader MNQ bars arriving every minute; TradingView export merged.", "level": "dim", "px": None},
        {"t": et(day, "02:00"), "bot": "lit", "stage": "window", "title": "Entry window open", "text": "02:00 ET: watching Asia, Frankfurt and London levels for a sweep.", "level": "info", "px": None},
        {"t": et(day, "09:30"), "bot": "blitz", "stage": "band", "title": "Noise band set", "text": f"09:30 open {o930:,.2f}: band +/- {sig:,.2f} pts, checks every 30 minutes (PAPER)." if o930 else "Waiting for the 09:30 open.", "level": "info", "px": o930},
        {"t": et(day, "08:40"), "bot": "atlas", "stage": "trend", "title": "EMA trend", "text": "5m EMA 21 / 50 lined up: only pullbacks in the trend's direction.", "level": "dim", "px": None},
        {"t": et(day, "15:55"), "bot": "sys", "stage": "flat", "title": "Flat 15:55", "text": "Every bot flat before the close. Day saved to the archive.", "level": "dim", "px": None},
    ]
    thoughts.sort(key=lambda x: x["t"])
    fills.sort(key=lambda x: x["t"])
    orders.sort(key=lambda x: x["t"])
    trades.sort(key=lambda x: x["entry"]["t"])
    bars1 = [x for x in b1 if t0 <= x[0] < t1]
    try:
        from engine import structure as ST
        stb = ST.block(b1=[x[:5] for x in b1], b5=[x[:5] for x in b5], now=t1, price=bars1[-1][4], key="holo-fe-" + day)
    except Exception as e:      # the fixture still works without the structure block
        print("structure unavailable:", e)
        stb = None
    return {"day": day, "bars": {"1m": bars1, "5m": [x for x in b5 if t0 <= x[0] < t1]}, "fills": fills, "orders": orders, "thoughts": thoughts,
            "levels": levels, "trades": trades, "structure": stb}


def now_panels(D: dict) -> dict:
    lt = next((t for t in reversed(D["trades"]) if t["bot"] == "lit"), None)
    return {
        "lit": {"stage": {"label": "DONE FOR DAY" if lt else "WAITING FOR SWEEP", "n": 10 if lt else 1},
                "headline": (f"Done for the day: {lt['exit']['reason']} {lt['r']:+.2f}R, {'+' if lt['usd'] >= 0 else '-'}${abs(lt['usd']):,.0f}" if lt else "Watching the LIT levels for a sweep"),
                "detail": "1 trade a day. Next window opens 02:00 ET.",
                "stages": [{"label": s, "done": True} for s in ["Sweep", "Inducement", "Displacement", "5m CISD", "Limit", "1m CISD", "In trade", "Exit"]],
                "checklist": [{"ok": True, "text": "Stop 1 tick beyond the sweep extreme"}, {"ok": True, "text": "Size follows the stop"}, {"ok": True, "text": "BE at 1R (+1.25 pts)"}]},
        "atlas": {"stage": {"label": "PAPER"}, "headline": "EMA 21/50 down, waiting for a pullback to the 21; S/R reclaim armed above the prior day low.",
                  "checklist": [{"ok": True, "text": "Trend aligned"}, {"ok": None, "text": "Pullback to the 21 EMA"}]},
        "blitz": {"stage": {"label": "PAPER"}, "headline": "Inside the noise band: no signal at the last check.", "checklist": [{"ok": False, "text": "Close outside the band at a 30-minute check"}]},
    }


def main():
    lit = json.load(open(ROOT / "research/lab/backtest_live.json"))["trades"]
    atlas = []
    for f in ["ema_best", "md_best", "sr_best"]:
        atlas += json.load(open(ROOT / f"research/second/{f}.json"))["trades"]
    blitz = []
    for d in json.load(open(ROOT / "research/scalp/mo_best_trades.json"))["trades"]:
        t_in = int(datetime.strptime(d["entry_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET).timestamp())
        t_out = int(datetime.strptime(d["exit_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET).timestamp())
        blitz.append({**d, "day": d["entry_t"][:10], "entry_t": t_in, "exit_t": t_out, "qty": 3, "setup": "noise-band scalp"})
    days = []
    for day in DAYS:
        D = build_day(day, [t for t in lit if t["day"] == day], [t for t in atlas if t["day"] == day][:2], [t for t in blitz if t["day"] == day][:3])
        days.append(D)
        print(day, "bars", len(D["bars"]["1m"]), "fills", len(D["fills"]), "trades", len(D["trades"]), "thoughts", len(D["thoughts"]), "orders", len(D["orders"]))
    D = days[0]
    holo = {"v": 1, "kind": "le-holo", "t": D["bars"]["1m"][-1][0] + 60, "day": D["day"], "live": False, "bars": D["bars"], "bots": BOTS,
            "fills": D["fills"], "trades": D["trades"], "orders": D["orders"], "thoughts": D["thoughts"], "levels": D["levels"], "structure": D["structure"],
            "now": now_panels(D)}
    hist = {"v": 1, "kind": "le-holo-hist", "t": holo["t"], "days": []}
    for X in days:
        lo = min(t["entry"]["t"] for t in X["trades"]) - 3 * 3600 if X["trades"] else X["bars"]["1m"][0][0]
        hi = max((t["exit"] or t["entry"])["t"] for t in X["trades"]) + 1800 if X["trades"] else X["bars"]["1m"][-1][0]
        hist["days"].append({"day": X["day"], "trades": X["trades"], "fills": X["fills"], "thoughts": X["thoughts"],
                             "bars": {"1m": [b for b in X["bars"]["1m"] if lo <= b[0] <= hi]}})
    out = ROOT / "tests" / "fixtures" / "holo_fe_sample.json"
    out.write_text(json.dumps({"holo": holo, "hist": hist}, separators=(",", ":")))
    print("wrote", out, round(out.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
