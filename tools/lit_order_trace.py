"""One chronological order trace of a real 2026 LIT trade day through the PC live loop (pre-launch audit, 2026-10-24).

    python -X utf8 tools/lit_order_trace.py [--day 2026-01-07]      -> research/lit/order_trace.md

engine/live.LiveBot (model LIT = live_model.json "lit", adapter ninjatrader, account Sim101) is polled on its own aligned
schedule (2 s and 32 s after each minute) from 75 min before the backtest's entry to 2 min after its exit, with a fake clock
and engine/ninjatrader._FakeNT as NinjaTrader 8 on a temp folder (it consumes incoming/oif*.txt, fills MARKET orders at the
current price, works STOPMARKET / LIMIT orders and writes the outgoing/ order + position files). Between polls the fake
NinjaTrader price walks every closed 1m bar (open, the stop-side extreme, the other extreme, close; the conservative
stop-first order of the backtest), and during a poll it sits at the open of the minute that is forming (what a MARKET order
sent a few seconds into that minute fills near). Paper / Sim only: nothing is armed for a real account.

The trace records every change of the model's LIT state (setup armed at the 5m CISD close, limit level tapped, waiting for the
1m CISD, ENTERING, IN TRADE, breakeven), every OIF line the adapter writes (exact text), and the fake NinjaTrader's order /
position files after each write. It also asserts what the reviewer asked: no order file before the 1m CISD close (the
"limit at the CISD level for 30 min" is a virtual condition in the model, never a working order at NinjaTrader) and exactly
one entry order.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import live  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lit", "order_trace.md")


def hms(t):
    return dt.datetime.fromtimestamp(float(t), ET).strftime("%H:%M:%S") + (f".{int(round((float(t) % 1) * 10))}" if float(t) % 1 else "")


def main():
    from tests.test_lit_timing import Clock
    from tests.test_live_dryrun import Replay
    from tools import lit_final as F
    def arg(name, default=None):
        return next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == name and i + 1 < len(sys.argv)), default)
    day = arg("--day", "2026-01-07")
    out = os.path.join(ROOT, arg("--out")) if arg("--out") else OUT
    py_restart = float(arg("--py-restart")) * 60 if arg("--py-restart") else None     # minutes after the entry: Python restart
    nt_restart = float(arg("--nt-restart")) * 60 if arg("--nt-restart") else None     # NinjaTrader restart: outgoing wiped
    nt_back = float(arg("--nt-back")) * 60 if arg("--nt-back") else None              # ... and its position file written again
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    t = next(x for x in F.run(P) if x["day"] == day)
    d, ent, ext = int(t["dir"]), int(t["entry_t"]), int(t["exit_t"])
    os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT order trace", "lit": P,
                                              "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40}})
    for k in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
        os.environ.pop(k, None)
    rp = Replay()
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    rp.frames[("NQ", "1m")] = df1[df1["time"] >= ent - 70 * 86400].reset_index(drop=True)
    bars = {int(r.time): (float(r.open), float(r.high), float(r.low), float(r.close)) for r in
            df1[(df1["time"] >= ent - 6 * 3600) & (df1["time"] <= ext + 3600)].itertuples()}
    clock = Clock()

    def forming_1m(sym, interval, period="5d"):
        m = int(clock()) - int(clock()) % 60
        if sym == "NQ" and interval == "1m" and m in bars:
            o = bars[m][0]
            return pd.DataFrame([{"time": m, "open": o, "high": o, "low": o, "close": o, "volume": 0.0}])
        return pd.DataFrame()
    rp.recent_hook = forming_1m
    rp.install_globals()
    tmp = tempfile.mkdtemp(prefix="le_order_trace_")
    ev = []                                   # (t, kind, text)
    try:
        folder = os.path.join(tmp, "NinjaTrader 8")
        a, z = ent - 75 * 60, ext + 120
        fake = nt._FakeNT(folder, price=bars.get(a - a % 60 - 60, (t["entry_px"] * d,))[0])
        rp.now = a - 60
        clock.base, clock.running = float(a - 60), False
        oif_rows = []

        def make_bot():
            bot = live.LiveBot()
            bot.clock = clock
            bot.read_hist, bot.fetch_recent = rp.read_hist, rp.fetch_recent
            bot.state_path = os.path.join(tmp, "live_state.json")
            bot._remember = lambda *a_, **kw: None
            r = bot.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_folder": folder,
                           "nt_account": "Sim101", "model": "lit", "model_params": P, "params": {"max_micros": 40, "flat_mod": 955},
                           "nt_state_path": os.path.join(tmp, "nt_state.json"), "nt_audit_log": os.path.join(tmp, "oif.log")},
                          spawn=False)
            assert r.get("ok"), r
            ad = bot.adapter
            ad.clock = clock
            if not ad.legs:
                ad._restore()        # the adapter restored its state on the wall clock's day; read it again on the replay's
            ad._alert_fn = lambda text: ev.append((clock(), "ALERT", "phone alert: " + text))

            def nt_sleep(s_):
                fake.process()
                clock.base += s_
            ad._sleep = nt_sleep
            orig_write = ad._write_oif

            def rec_write(lines, label):
                res = orig_write(lines, label)
                tw = clock()
                oif_rows.append((tw, label, list(lines)))
                ev.append((tw, "OIF", f"adapter writes `{res.get('file', '?')}` ({label}):\n" + "\n".join(f"    {ln}" for ln in lines)))
                return res
            ad._write_oif = rec_write
            return bot, r
        bot, _ = make_bot()
        ad_seen = {"n": 0}
        orig_process = fake.process

        def rec_process(*_):
            before = {k: (o["state"], o["filled"]) for k, o in fake.orders.items()}
            n0 = len(fake.files)
            orig_process()
            if len(fake.files) > n0:
                ch = []
                for k, o in fake.orders.items():
                    if before.get(k) != (o["state"], o["filled"]):
                        ch.append(f"{k} {o['type']} {o['action']} {o['qty']} -> {o['state']}"
                                  + (f" filled {o['filled']} @ {o['avg']:.2f}" if o["filled"] else ""))
                pos = "; ".join(f"{inst} {acct}: {q:+d} @ {avg:.2f}" for (acct, inst), (q, avg) in fake.pos.items()) or "flat"
                ev.append((clock(), "NT", "fake NinjaTrader processed the file at price "
                           f"{fake.price:.2f}: " + ("; ".join(ch) or "no order change") + f" | position {pos}"))
        fake.process = rec_process

        def nt_move(px, when):
            before = {k: (o["state"], o["filled"]) for k, o in fake.orders.items()}
            fake.move(px)
            for k, o in fake.orders.items():
                if before.get(k) != (o["state"], o["filled"]) and o["state"] in ("FILLED", "PARTFILLED", "CANCELLED"):
                    ev.append((when, "NT", f"market trades {px:.2f}: {k} {o['type']} {o['action']} {o['qty']} -> {o['state']}"
                               + (f" @ {o['avg']:.2f}" if o.get("avg") else "")))

        last_ms, last_setup, last_bar = None, {}, a - a % 60 - 60
        wake = live.next_wake(a)
        polls, t_run = 0, time.time()
        while wake <= z:
            rp.now = int(wake)
            m_now = int(wake) - int(wake) % 60
            # the market between the polls: every 1m bar that closed since the last poll (stop-side extreme first)
            for m in range(last_bar + 60, m_now, 60):
                if m in bars:
                    o, h, l, c = bars[m]
                    for px in ((o, l, h, c) if d == 1 else (o, h, l, c)):
                        nt_move(px, m + 59.9)
                last_bar = m
            if m_now in bars:
                nt_move(bars[m_now][0], m_now)           # the forming minute's first trade
            if py_restart is not None and wake >= ent + py_restart:
                py_restart = None
                bot, r = make_bot()                      # the old LiveBot is dropped (a crash): same live_state / nt_state files
                ad_seen["n"] = 0
                ev.append((wake, "RESTART", f"PYTHON RESTART: a new LiveBot starts on the same live_state.json / ninjatrader_state.json "
                           f"(restored: {json.dumps(r.get('restored'))}; adapter legs restored: "
                           f"{[(lg['entry_id'], lg['status']) for lg in bot.adapter.legs]})"))
            if nt_restart is not None and wake >= ent + nt_restart:
                nt_restart = None
                for fn in os.listdir(fake.out):
                    os.remove(os.path.join(fake.out, fn))
                ev.append((wake, "RESTART", "NINJATRADER RESTART: every file in outgoing deleted (the broker keeps the position and "
                           "the working stop / target; NinjaTrader does not rewrite the order files)"))
            if nt_back is not None and wake >= ent + nt_back:
                nt_back = None
                fake._write("Tradovate.txt", "CONNECTED")
                for acct, inst in list(fake.pos):
                    fake._write_pos(acct, inst)
                ev.append((wake, "RESTART", "NinjaTrader connected again: it writes the position file (not the order files)"))
            clock.base, clock.t0, clock.running = wake, clock.src(), True
            try:
                bot.poll_once()
            except Exception as e:
                ev.append((clock(), "ERROR", f"poll failed: {e.__class__.__name__}: {e}"))
            clock.running = False
            polls += 1
            tr = list(bot.adapter.trace)
            for x in tr[ad_seen["n"]:]:
                if x["type"] in ("risk", "error", "warn") or (x["type"] == "system" and "NinjaTrader:" in x["text"]):
                    ev.append((x["t"] + 0.05, "ADAPTER", f"{x['type']}: {x['text']}"))
            ad_seen["n"] = len(tr)
            st = bot.state or {}
            ms = st.get("model_state")
            setups = st.get("setups") or {}
            for s, v in setups.items():
                sk = json.dumps({k: v.get(k) for k in ("arm_t", "limit", "stop", "target", "expires_t", "tapped_t")}, sort_keys=True)
                if sk != last_setup.get(s):
                    last_setup[s] = sk
                    ev.append((wake, "MODEL", f"setup {s.upper()}: armed at the close of the 5m CISD bar ({hms(v['arm_t'])}), "
                               f"virtual limit {v['limit']:,.2f}, stop {v['stop']:,.2f}, "
                               f"target {v['target']:,.2f}" + (f", valid until {hms(v['expires_t'])}" if v.get("expires_t") else "")
                               + (f"; level TAPPED by the 1m bar opening {hms(v['tapped_t'])}, waiting for a 1m CISD" if v.get("tapped_t")
                                  else "; waiting for price to tap the level") + " (no order at NinjaTrader)"))
            if ms != last_ms:
                ev.append((wake, "STATE", f"poll {hms(wake)}: {ms}"))
                last_ms = ms
            clock.base = wake
            wake = live.next_wake(max(wake, clock.base))
        led = [{k: r_.get(k) for k in ("t", "side", "qty", "stop", "target", "entry", "reason", "pnl")} | {"ok": (r_.get("result") or {}).get("ok")}
               for r_ in bot.ledger]
        logs = [x for x in bot.log if any(s in x["text"] for s in ("MARKET entry sent", "NinjaTrader:", "bracket closed", "NOT routed"))]
        audit = open(os.path.join(tmp, "oif.log"), encoding="utf-8").read() if os.path.exists(os.path.join(tmp, "oif.log")) else ""
    finally:
        os.environ.pop("LE_LIVE_MODEL", None)
        rp.cleanup()
        shutil.rmtree(tmp, ignore_errors=True)

    entries = [(tw, ln) for tw, _, ls in oif_rows for ln in ls if ln.startswith("PLACE;") and ";MARKET;" in ln]
    before = [(tw, ln) for tw, _, ls in oif_rows for ln in ls if tw < ent]
    stop_l = [ln for _, _, ls in oif_rows for ln in ls if ";STOPMARKET;" in ln]
    tgt_l = [ln for _, _, ls in oif_rows for ln in ls if ln.startswith("PLACE;") and ";LIMIT;" in ln]
    checks = [
        ("no order file before the 1m CISD candle closed (the 30-min limit is virtual)", not before),
        ("exactly one entry order (PLACE ... MARKET), no second entry", len(entries) == 1),
        ("entry side / micros = the backtest's", bool(entries) and entries[0][1].split(";")[3] == ("BUY" if d == 1 else "SELL")
         and int(entries[0][1].split(";")[4]) == int(t["qty"])),
        ("stop STOPMARKET at the backtest's stop (tick-rounded)", bool(stop_l) and abs(float(stop_l[0].split(";")[7]) - live.tick_px(t["stop_px"], d)) < 1e-6),
        ("target LIMIT at the backtest's target (tick-rounded)", bool(tgt_l) and abs(float(tgt_l[0].split(";")[6]) - live.tick_px(t["target_px"], d, target=True)) < 1e-6),
        ("stop and target placed only after NinjaTrader reported the entry fill", bool(entries) and bool(stop_l)
         and min(tw for tw, _, ls in oif_rows if any(";STOPMARKET;" in x for x in ls)) > entries[0][0]),
        ("one bracket only (no second stop / target pair)", len(stop_l) == 1 and len(tgt_l) == 1),
        ("the trade's exit is routed exactly once", sum(1 for x in led if x["side"] == "exit") == 1),
    ]
    ev.sort(key=lambda x: x[0])
    cmd = " ".join(sys.argv[1:])
    L = [f"# LIT order trace: {day} ({'LONG' if d == 1 else 'SHORT'} {t['qty']} MNQ, backtest exit {t['exit']})", "",
         "Built by `python -X utf8 tools/lit_order_trace.py " + cmd + "` (pre-launch audit 2026-10-24). The PC live loop "
         "(`engine/live.LiveBot`, model LIT = `live_model.json` \"lit\", NinjaTrader adapter on Sim101) polled on its own "
         "schedule (2 s and 32 s after each minute) against a fake NinjaTrader folder (`engine/ninjatrader._FakeNT`). The fake "
         "market walks the real TradingView NQ1! 1m bars (stop-side extreme first); a MARKET order fills at the forming minute's "
         "open. Times are ET. Size here = the plain LIT size rule (no eval caps), as in `tests/test_lit_oif.py`.", "",
         "How to read it: the \"limit at the CISD level for 30 min\" is a price the model watches (MODEL rows: armed, tapped, "
         "waiting for the 1m CISD); nothing is sent to NinjaTrader until the 1m CISD candle closes. Then ONE MARKET entry, "
         "and only after NinjaTrader reports its fill, ONE STOPMARKET + LIMIT pair sharing an OCO id. One trade a day, and the "
         "adapter refuses any entry while a bracket is open or NinjaTrader shows a position. The CLOSEPOSITION after a "
         "bracket fill is the bot's sync flatten of the model's exit (harmless when already flat).", "",
         f"Backtest (tools/lit_final.run, live_model.json \"lit\"): entry bar {hms(ent)} at {t['entry_px'] * d if t['entry_px'] > 0 else t['entry_px']}"
         f" (fill = that 1m bar's open + 1 tick), stop {t['stop_px']}, target {t['target_px']}, {t['qty']} micros, exit {t['exit']} "
         f"at {hms(ext)}, ${t['pnl']:+,.2f}.", "",
         "## Checks", ""] + [f"- [{'PASS' if ok else 'FAIL'}] {n}" for n, ok in checks] + [
         "", "## Timeline", "", "| ET | who | what |", "|---|---|---|"]
    for tw, kind, text in ev:
        if "\n" in text:
            head, body = text.split("\n", 1)
            L.append(f"| {hms(tw)} | {kind} | {head} <br>" + " <br>".join(f"`{x.strip()}`" for x in body.splitlines()) + " |")
        else:
            L.append(f"| {hms(tw)} | {kind} | {text.replace('|', '/')} |")
    L += ["", "## Bot ledger (live_state.json rows)", "", "```"] + [json.dumps(x) for x in led] + ["```", "",
          "## Adapter / bot log lines (order route)", "", "```"] + [f"{hms(x['t'])} {x['type']}: {x['text']}" for x in logs] + \
         ["```", "", "## OIF audit log (logs/ninjatrader_oif.log format; stamps are this machine's wall clock)", "", "```", audit.strip(), "```", "",
          f"{polls} polls in {time.time() - t_run:.0f} s.", ""]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    for n, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}")
    print(f"{sum(ok for _, ok in checks)}/{len(checks)} -> {os.path.relpath(out, ROOT)} ({polls} polls)")
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main()
