"""Every 2026 LIT trade through the PC loop to a NinjaTrader order file (owner, 2026-10-18: "when there's a signal it needs to
send an entry"). Paper / Sim only: the NinjaTrader side is engine/ninjatrader._FakeNT (the self-test's simulated
NinjaTrader 8 on a temp folder, account Sim101); nothing is ever armed for a real account.

    python -X utf8 -m tests.test_lit_oif                         # all 2026 trades (~30 min, one process)
    python -X utf8 -m tests.test_lit_oif --only=2026-01-02,2026-04-29

For each backtest trade (tools/lit_final.py run on live_model.json "lit" = run lit_live), a fresh LiveBot (engine/live.py,
model LIT, adapter ninjatrader, Sim101) is polled on its own minute-aligned schedule (engine/live.next_wake: 2 s and 32 s
after each minute) from 6 min before the entry to 90 s after it, with a clock that runs on during each poll (the real
compute time counts). Bars appear as they close; the 1m feed shows the minute that has just started from its open (as
Yahoo / LE_BarFeed's MNQ_1m_open.csv do). Checks per trade:
  - the MARKET entry order file (PLACE ... BUY/SELL n MARKET) is written once, <= LIMIT_S after the 1m CISD candle closed,
    i.e. at the start of the backtest's entry bar (its open is the backtest's fill)
  - side and micros are the backtest's, and the bracket follows (STOPMARKET at the stop, LIMIT at the target, tick-rounded)
  - no other entry is written in the window
Reports median / max delay and the missed count -> research/lit/live_oif.json. Exit code 1 on any miss.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import live  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from tests.test_lit_timing import Clock, hm  # noqa: E402

LIMIT_S = 10.0
OUT = os.path.join(ROOT, "research", "lit", "live_oif.json")


def main():
    from tests.test_live_dryrun import Replay
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    T = [t for t in F.run(P) if t["day"] >= "2026-01-01" and (not only or t["day"] in only)]
    print(f"{len(T)} backtest trades to replay", flush=True)
    os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT OIF test", "lit": P,
                                              "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40}})
    for k in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
        os.environ.pop(k, None)
    rp = Replay()
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    rp.frames[("NQ", "1m")] = df1[df1["time"] >= min(t["entry_t"] for t in T) - 70 * 86400].reset_index(drop=True)
    o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))
    c1 = dict(zip(df1["time"].astype("int64"), df1["close"].astype(float)))
    clock = Clock()

    def forming_1m(sym, interval, period="5d"):
        t = int(clock()) - int(clock()) % 60
        if sym == "NQ" and interval == "1m" and t in o1:
            return pd.DataFrame([{"time": t, "open": o1[t], "high": o1[t], "low": o1[t], "close": o1[t], "volume": 0.0}])
        return pd.DataFrame()
    rp.recent_hook = forming_1m
    rp.install_globals()
    tmp = tempfile.mkdtemp(prefix="le_lit_oif_")
    rows, t_all = [], time.time()
    try:
        for n, t in enumerate(T):
            d, ent = int(t["dir"]), int(t["entry_t"])
            folder = os.path.join(tmp, t["day"], "NinjaTrader 8")
            fake = nt._FakeNT(folder, price=float(o1.get(ent, t["entry_px"] * d)))
            a, z = ent - 360, ent + 90
            rp.now = a - 60
            bot = live.LiveBot()
            bot.clock = clock
            clock.base, clock.running = float(a - 60), False
            bot.read_hist, bot.fetch_recent = rp.read_hist, rp.fetch_recent
            bot.state_path = os.path.join(tmp, t["day"], "live_state.json")
            bot._remember = lambda *a_, **kw: None
            r = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_folder": folder, "nt_account": "Sim101",
                           "model": "lit", "model_params": P, "params": {"max_micros": 40, "flat_mod": 955},
                           "nt_state_path": os.path.join(tmp, t["day"], "nt_state.json"),
                           "nt_audit_log": os.path.join(tmp, t["day"], "oif.log")}, spawn=False)
            ad = bot.adapter
            ad.clock = clock
            ad._alert_fn = lambda *a_, **kw: None

            def nt_sleep(s_, fake=fake):
                fake.process()
                clock.base += s_
            ad._sleep = nt_sleep
            written = []
            orig_write = ad._write_oif

            def rec_write(lines, label, orig_write=orig_write, written=written):
                written.append((clock(), list(lines)))
                return orig_write(lines, label)
            ad._write_oif = rec_write
            errors, durs = [], []
            wake = live.next_wake(a)
            while wake <= z:
                rp.now = int(wake)
                clock.base, clock.t0, clock.running = wake, time.perf_counter(), True
                last = int(wake) - int(wake) % 60 - 60
                if last in c1:
                    fake.move(c1[last])                       # NinjaTrader fills a market order at the last price
                p0 = time.perf_counter()
                try:
                    bot.poll_once()
                except Exception as e:
                    errors.append(f"{hm(wake)} {e.__class__.__name__}: {e}")
                clock.running = False
                durs.append((round(time.perf_counter() - p0, 2), round(clock() - wake, 2), hm(wake)))
                wake = live.next_wake(max(wake, clock.base))
            side = "BUY" if d == 1 else "SELL"
            entries = [(tw, ln) for tw, ls in written for ln in ls if ln.startswith("PLACE;") and ";MARKET;" in ln]
            ok_side = [(tw, ln) for tw, ln in entries if ln.split(";")[3] == side]
            first = ok_side[0] if ok_side else None
            delay = round(first[0] - ent, 2) if first else None
            qty = int(first[1].split(";")[4]) if first else None
            stop_l = [ln for _, ls in written for ln in ls if ";STOPMARKET;" in ln]
            tgt_l = [ln for _, ls in written for ln in ls if ln.startswith("PLACE;") and ";LIMIT;" in ln]
            stop_ok = bool(stop_l) and abs(float(stop_l[0].split(";")[7]) - live.tick_px(t["stop_px"], d)) < 1e-6
            tgt_ok = bool(tgt_l) and abs(float(tgt_l[0].split(";")[6]) - live.tick_px(t["target_px"], d, target=True)) < 1e-6
            ok = first is not None and 0 <= delay <= LIMIT_S and qty == int(t["qty"]) and len(entries) == 1 and stop_ok and tgt_ok
            row = {"day": t["day"], "entry_bar": hm(ent), "dir": d, "qty": int(t["qty"]), "oif_t": hm(first[0]) if first else None,
                   "delay_s": delay, "oif_qty": qty, "entries_written": len(entries), "stop_ok": stop_ok, "target_ok": tgt_ok,
                   "ok": ok, "errors": errors[:3], "polls": len(durs), "poll_real_s_max": max(d_[0] for d_ in durs) if durs else None,
                   "entry_poll": next(([d_[0], d_[1]] for d_ in durs if d_[2] == hm(live.next_wake(ent - 1))), None),
                   "why": None if ok else [x["text"] for x in list(bot.log)[:6]]}
            rows.append(row)
            if not ok or n % 10 == 0:
                print(f"  {n + 1}/{len(T)} {json.dumps(row) if not ok else t['day'] + ' ok ' + str(delay) + ' s'} "
                      f"({time.time() - t_all:.0f}s)", flush=True)
    finally:
        os.environ.pop("LE_LIVE_MODEL", None)
        rp.cleanup()
        shutil.rmtree(tmp, ignore_errors=True)
    dl = np.array([r["delay_s"] for r in rows if r["delay_s"] is not None], float)
    missed = [r["day"] for r in rows if not r["ok"]]
    res = {"trades": len(rows), "routed_ok": len(rows) - len(missed), "missed": missed, "limit_s": LIMIT_S,
           "delay_s": {"median": round(float(np.median(dl)), 2) if len(dl) else None, "max": round(float(dl.max()), 2) if len(dl) else None,
                       "mean": round(float(dl.mean()), 2) if len(dl) else None},
           "seconds": round(time.time() - t_all), "rows": rows}
    if not only:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"LIT -> NinjaTrader OIF: {res['routed_ok']}/{len(rows)} entries written at the backtest's entry bar "
          f"(median {res['delay_s']['median']} s, max {res['delay_s']['max']} s after the 1m CISD close); missed {len(missed)} "
          f"{missed[:10]} in {res['seconds']}s", flush=True)
    sys.exit(0 if not missed else 1)


if __name__ == "__main__":
    main()
