"""Builds tests/fixtures/holo_sample.json, the Holodeck sample day for the 3D page and its tests (engine/holo_api.py).

A busy 2026 day from the real futures data (data/NQ_5m.csv + data/NQ_1m.csv, TradingView CME): the LIT backtest's trade,
the ATLAS members' research trades (engine/second.run) and the BLITZ backtest's paper trades of that day, seen by a fake PC
bot at 16:10 ET of that day (live = true, so the "now" panels are filled). The LIT trade and two ATLAS trades are given fake
NinjaTrader Sim fills 1 tick off the model (entry 1 tick worse; the BE stop of the ATLAS short 1 tick worse; targets fill at
their limit), one ATLAS order on account B is refused (never a fill). Writes nothing else: the fake bot's logs go to a temp
folder.

    python -X utf8 tools/holo_fixture.py [--day 2026-10-13] [--out tests/fixtures/holo_sample.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class FakeAdapter:
    name = "ninjatrader"

    def __init__(self, account):
        self.account = account
        self.legs: list = []
        self.history: list = []
        self.folder = None


class FakeAcct:
    def __init__(self, name, label, plan):
        self.name, self.label = name, label
        self.spec = {"plan_label": plan, "plan": plan}
        self.adapter = FakeAdapter(name)
        self.ledger: list = []

    def disabled_reason(self):
        return None

    def info(self, now=None):
        return {"label": self.label, "account": self.name, "open": None, "routed": []}


class FakeBot:
    def __init__(self, now):
        self._now = now
        self.running = True
        self.kill = False
        self.cfg = {"adapter": "ninjatrader", "sym": "NQ"}
        self.state = {}
        self.health = {}
        self.adapter = FakeAdapter("Sim101")
        self.ledger: list = []
        self.brain = None
        self.second = None
        self.blitz = None
        self.acct_b = None
        self.acct_c = None
        self.bars_tail: list = []
        self._lit_1m_store = None
        self.log: list = []

    def clock(self):
        return self._now

    def _push_account(self):
        return "Sim101"


def leg(entry_t, d, qty, fill, mtime, stop0, stop, target, tag):
    base = f"LE{entry_t}{tag}M"
    return {"instrument": "MNQ 12-26", "qty": qty, "side": "BUY" if d == 1 else "SELL", "dir": d, "entry_t": entry_t, "stop": stop,
            "target": target, "entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "oco": base + "O",
            "status": "closed", "filled": qty, "fill_px": fill, "fill_mtime": mtime, "bracket_qty": qty, "stop0": stop0,
            "sent_at": entry_t + 1.2, "closed": "filled"}


def tick(px, d=1):
    return round(round(float(px) / 0.25) * 0.25, 2)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-10-13")
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "fixtures", "holo_sample.json"))
    a = ap.parse_args(argv)
    from engine import blitz as BZ, brain as BR, fill_audit as FA, holo_api as H, lit_live, narrator as N, second
    day = a.day
    now = FA._ts(day, 16, 10)
    d5, d1 = FA.load_bars()
    P = FA._params()
    tmp = tempfile.mkdtemp(prefix="holo_fix_")
    H.STORE, H.NARR_DIR, H.BRAIN_DIR, H.STATE_PATH = tmp, tmp, tmp, os.path.join(tmp, "live_state.json")
    H.LIVE_REPLAY = True
    bot = FakeBot(now)
    # the bot's own bars: 12 days of 1m, the last 400 5m bars
    bot._lit_1m_store = d1[(d1["time"] >= now - 12 * 86400) & (d1["time"] < now)].reset_index(drop=True)
    t5 = d5[(d5["time"] < now)].tail(400)
    bot.bars_tail = [{"time": int(r.time), "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close),
                      "volume": int(r.volume)} for r in t5.itertuples()]
    bot.state = {"price": float(t5["close"].iloc[-1])}
    # the Brain at 16:10 (the live loop's own build)
    keep: dict = {}
    res = lit_live.run(d5[d5["time"] < now], P, one_min=d1[d1["time"] < now], now=now, keep=keep)
    bot.brain = BR.build(res, P, now, keep=keep, mode="live")
    # ATLAS paper (engine/second.run on the same bars) and BLITZ paper (its backtest of that day)
    bot.second = second.run(d5[d5["time"] < now], d1[d1["time"] < now], now=now, cfg=second.load_cfg(), lit=res["trades"])
    bz = [r for r in BZ.backtest(d1[(d1["time"] >= now - 40 * 86400) & (d1["time"] < now)], filtered=False) if r.get("day") == day]
    rows = []
    for n, r in enumerate(bz):
        q = BZ._fixed_q(float(r["risk_pm"]))
        rows.append({"id": f"bz{n}", "day": day, "entry_t": int(r["entry_t"]), "dir": int(r["dir"]), "side": "LONG" if r["dir"] == 1 else "SHORT",
                     "qty": q, "entry": round(float(r["entry"]), 2), "stop": round(float(r["stop"]), 2), "stop_now": round(float(r["stop"]), 2),
                     "exit_t": int(r["exit_t"]), "exit": round(float(r["exit"]), 2), "exit_kind": str(r["exit_kind"]).upper(),
                     "usd": round(float(r["pnl_pm"]) * q, 2), "r": round(float(r["r"]), 3)})
    bot.blitz = {"t": now, "ledger": rows, "ledger50": []}
    # LIT: the model's trade with a real Sim fill 1 tick worse, BE moved at +1R, the target filled at its limit
    orders = []
    lt = [t for t in res["trades"] if t.get("day") == day]
    for t in lt:
        et_, d, q = int(t["entry_t"]), int(t["dir"]), int(t["qty"])
        fill = round(float(t["entry"]) - d * 0.25 * -1, 2) if False else round(float(t["entry"]) + d * 0.25, 2)
        mt = et_ + 2.731
        be_t = FA._bt_be_time(t, d1)
        be_px = tick(float(t["entry"]) + d * 1.25)
        lg = leg(et_, d, q, fill, mt, float(t["stop"]), be_px if be_t else float(t["stop"]), float(t["target"]), "K7QZ")
        bot.adapter.history.append(lg)
        act = {"sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": q, "stop": float(t["stop"]), "target": float(t["target"]),
               "entry": float(t["entry"]), "entry_t": et_}
        bot.ledger.append({"t": et_ + 1, **act, "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim101", "env": "sim",
                                                            "side": act["side"].upper(),
                                                            "legs": [{"instrument": "MNQ 12-26", "qty": q, "filled": q, "fill_px": fill, "ok": True}]}})
        orders.append({"id": lg["entry_id"], "state": "FILLED", "filled": q, "avg": fill, "mtime": mt, "seen": et_ + 5})
        if be_t:
            bot.ledger.append({"t": be_t + 2, "sym": "NQ", "side": "modify", "qty": q, "stop": be_px, "reason": "BE", "entry_t": et_,
                               "result": {"ok": True, "adapter": "ninjatrader", "stop": be_px}})
        xt = int(t["exit_t"]) + 23.418
        kind = "T" if t["exit_reason"] == "TARGET" else "S"
        xpx = float(t["exit_price"]) if kind == "T" else round(float(t["exit_price"]) + d * -0.25, 2)
        orders.append({"id": lg["target_id"] if kind == "T" else lg["stop_id"], "state": "FILLED", "filled": q, "avg": xpx, "mtime": xt,
                       "seen": int(xt) + 4})
        orders.append({"id": lg["stop_id"] if kind == "T" else lg["target_id"], "state": "CANCELLED", "filled": 0, "avg": None,
                       "mtime": xt + 0.4, "seen": int(xt) + 4})
        pnl = round((xpx - fill) * d * 2.0 * q - 1.90 * q, 2)       # NinjaTrader routes every model exit (a harmless close when flat)
        bot.ledger.append({"t": int(t["exit_t"]) + 61, "sym": "NQ", "side": "exit", "qty": q, "reason": t["exit_reason"], "pnl": pnl,
                           "entry_t": et_, "exit_t": int(t["exit_t"]), "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim101"}})
    # ATLAS on account B (Sim102): two research trades routed, real fills 1 tick off; one refused order
    B = FakeAcct("Sim102", "Account B Sim102", "ATLAS · MFFU Builder 25K (Sim)")
    bot.acct_b = B
    picks = []
    for k in ("sr_nyreclaim", "ema_lon_vix"):
        for t in (bot.second["strategies"].get(k) or {}).get("trades") or []:
            if t.get("day") == day:
                picks.append((k, t))
    for n, (k, t) in enumerate(picks[:2]):
        et_, d, q = int(t["entry_t"]), int(t["dir"]), int(t["qty"])
        fill = round(float(t["entry"]) + d * 0.25, 2)
        mt = et_ + 1.904
        stop_now = float(t["stop"])
        be = str(t.get("exit_kind")) == "BE"
        if be:
            stop_now = tick(float(t["exit"]) + d * 0.25)
        lg = leg(et_, d, q, fill, mt, float(t["stop"]), stop_now, float(t["target"]), f"B{n}X9")
        B.adapter.history.append(lg)
        sc = bot.second["strategies"][k]
        act = {"sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": q, "stop": float(t["stop"]), "target": float(t["target"]),
               "entry": float(t["entry"]), "entry_t": et_, "src": k, "strategy": sc.get("short") or k}
        B.ledger.append({"t": et_ + 1, **act, "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim102", "env": "sim",
                                                          "legs": [{"instrument": "MNQ 12-26", "qty": q, "filled": q, "fill_px": fill, "ok": True}]}})
        orders.append({"id": lg["entry_id"], "state": "FILLED", "filled": q, "avg": fill, "mtime": mt, "seen": et_ + 5})
        xt = int(t["exit_t"]) + 11.27
        if be:
            bt = {"entry_t": et_, "exit_t": int(t["exit_t"]), "dir": d, "entry": float(t["entry"]), "stop": float(t["stop"])}
            bet = FA._bt_be_time(bt, d1) or (et_ + 600)
            B.ledger.append({"t": bet + 2, "sym": "NQ", "side": "modify", "qty": q, "stop": stop_now, "reason": "BE", "entry_t": et_,
                             "src": k, "result": {"ok": True, "adapter": "ninjatrader", "stop": stop_now}})
            orders.append({"id": lg["stop_id"], "state": "FILLED", "filled": q, "avg": round(stop_now + d * -0.25, 2), "mtime": xt, "seen": int(xt) + 3})
            orders.append({"id": lg["target_id"], "state": "CANCELLED", "filled": 0, "avg": None, "mtime": xt + 0.3, "seen": int(xt) + 3})
        else:
            orders.append({"id": lg["target_id"], "state": "FILLED", "filled": q, "avg": float(t["exit"]), "mtime": xt, "seen": int(xt) + 3})
            orders.append({"id": lg["stop_id"], "state": "CANCELLED", "filled": 0, "avg": None, "mtime": xt + 0.3, "seen": int(xt) + 3})
        xpx = orders[-2]["avg"]
        B.ledger.append({"t": int(t["exit_t"]) + 62, "sym": "NQ", "side": "exit", "qty": q, "reason": t["exit_kind"], "entry_t": et_,
                         "exit_t": int(t["exit_t"]), "src": k, "strategy": sc.get("short") or k,
                         "pnl": round((xpx - fill) * d * 2.0 * q - 1.90 * q, 2), "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim102"}})
    rt = FA._ts(day, 11, 5)
    B.ledger.append({"t": rt + 1, "sym": "NQ", "side": "buy", "qty": 3, "stop": 30701.0, "target": 30842.0, "entry": 30748.25, "entry_t": rt,
                     "src": "macd_sweep", "strategy": "MACD",
                     "result": {"ok": False, "adapter": "ninjatrader", "account": "Sim102",
                                "error": "MNQ 12-26: entry REJECTED (NinjaTrader: order rejected: account does not exist)",
                                "legs": [{"instrument": "MNQ 12-26", "qty": 3, "ok": False, "state": "REJECTED"}]}})
    with open(os.path.join(tmp, "orders.jsonl"), "w", encoding="utf-8") as fh:
        for o in orders:
            fh.write(json.dumps(o) + "\n")
    N.NARRATOR.observe(bot, now)                                  # today's feed in memory (no files, no pushes)
    out = H.build(bot, None, now)
    out["fixture"] = {"day": day, "note": "Sample day for the Holodeck: real futures bars (TradingView CME exports), the LIT backtest, "
                                          "ATLAS research trades (engine/second.run) and BLITZ backtest trades of that day; the NinjaTrader "
                                          "Sim fills (1 tick off the model), the account names and the refused order are FAKE.",
                      "made_by": "python -X utf8 tools/holo_fixture.py"}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), default=str)
    sz = os.path.getsize(a.out)
    print(f"{a.out}: {sz / 1024:.0f} KB · {len(out['bars']['1m'])} 1m bars · {len(out['fills'])} fills · {len(out['trades'])} trades · "
          f"{len(out['orders'])} orders · {len(out['thoughts'])} thoughts · {len(out['levels'])} levels · build {out.get('build_ms')} ms · "
          f"errors {out['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
