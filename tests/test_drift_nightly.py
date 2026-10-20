"""The nightly live-vs-backtest drift summary (engine/fill_audit.nightly): synthetic audit rows in a temp store, pushes to a list.
No broker, no network, no bars (the rows are what fill_audit.audit() makes from the backtest on the same bars).

  same day       matched trade, 0-1 tick slippage, $4 execution            -> "same", no push
  differs        matched trade whose outcome differs + 6 ticks at the entry  -> "differs", one push (key drift:<day>), once
  missed PC on   the backtest traded, the bot held it back (feed stale)      -> "differs", pushed
  missed PC off  no record of the bot that day                               -> listed as info, verdict "pc off", no push
  extra          the bot traded, the backtest did not                        -> "differs"
  qty only       eval sizing gave 3 micros vs 1: info, not a drift
Plus the stored files (nightly/<day>.json, nightly.json), the heartbeat block and which session a night run is about.

  python -X utf8 -m tests.test_drift_nightly
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

from engine import fill_audit as fa

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def row(status, day, hh, **kw):
    r = {"status": status, "day": day, "entry_t": fa._ts(day, hh, 0), "side": "LONG", "notes": []}
    r.update(kw)
    return r


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="drift_")
    try:
        sent = []
        D1, D2, D3, D4, D5 = "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"
        rows = [
            row("matched", D1, 3, entry_slip_ticks=0.0, exit_slip_ticks=1.0, slip_usd=-1.0, exec_usd=-4.0, bt_pnl=812.0, live_pnl=808.0),
            row("matched", D2, 4, entry_slip_ticks=6.0, exit_slip_ticks=0.0, slip_usd=-6.0, exec_usd=-30.0, bt_pnl=640.0, live_pnl=-410.0,
                notes=["outcome differs: backtest TARGET, bot STOP"]),
            row("missed", D3, 5, pc_on=True, reason="feed stale", missed_usd=900.0, bt_pnl=900.0),
            row("missed", D4, 3, pc_on=False, reason="PC off", missed_usd=-400.0, bt_pnl=-400.0),
            row("extra", D5, 10, live_pnl=-203.8, reason="the backtest on the same bars has no trade here"),
            row("matched", D5, 3, entry_slip_ticks=0.0, exit_slip_ticks=0.0, slip_usd=0.0, exec_usd=0.0, bt_pnl=100.0, live_pnl=300.0,
                qty_diff=2, notes=["qty 3 vs the backtest's 1 (eval sizing / weekly stop: not an execution cost)"]),
        ]
        rep = {"rows": rows, "days": {D1: {"bars": True, "bt_trades": 1, "live_trades": 1}}}
        notify = sent.append

        S1 = fa.nightly(D1, store=tmp, now=fa._ts(D1, 16, 10), rep=rep, notify=notify)
        check("same day: verdict same, no push", S1["verdict"] == "same" and not S1["pushed"] and not sent, S1)
        S2 = fa.nightly(D2, store=tmp, now=fa._ts(D2, 16, 10), rep=rep, notify=notify)
        check("outcome + 6-tick entry: differs, both reasons named",
              S2["verdict"] == "differs" and any("outcome differs" in w for w in S2["reasons"]) and any("entry +6 ticks" in w for w in S2["reasons"]), S2)
        check("differs: one push, key drift:<day>, title names the day", len(sent) == 1 and sent[0]["key"] == f"drift:{D2}"
              and D2 in sent[0]["title"] and "outcome differs" in sent[0]["body"], sent)
        fa.nightly(D2, store=tmp, now=fa._ts(D2, 16, 40), rep=rep, notify=notify)
        check("a second run the same night does not push again", len(sent) == 1, sent)
        S3 = fa.nightly(D3, store=tmp, now=fa._ts(D3, 16, 10), rep=rep, notify=notify)
        check("missed with the PC on: differs and pushed", S3["verdict"] == "differs" and len(sent) == 2 and "feed stale" in sent[-1]["body"], S3)
        S4 = fa.nightly(D4, store=tmp, now=fa._ts(D4, 16, 10), rep=rep, notify=notify)
        check("missed with the PC off: verdict 'pc off', info only, no push", S4["verdict"] == "pc off" and S4["info"] and len(sent) == 2, S4)
        S5 = fa.nightly(D5, store=tmp, now=fa._ts(D5, 16, 10), rep=rep, notify=notify)
        check("extra trade: differs; the qty difference is info, not a reason",
              S5["verdict"] == "differs" and len(S5["reasons"]) == 1 and "did not" in S5["reasons"][0]
              and any("qty 3" in i for i in S5["info"]) and len(sent) == 3, S5)
        S6 = fa.nightly("2026-10-26", store=tmp, now=fa._ts("2026-10-26", 16, 10), rep={"rows": [], "days": {}}, notify=notify)
        check("no trade either side: 'no trades', no push", S6["verdict"] == "no trades" and len(sent) == 3, S6)

        H = fa._read_json(os.path.join(tmp, "nightly.json"), [])
        check("nightly.json keeps one row per day, sorted", [x["day"] for x in H] == [D1, D2, D3, D4, D5, "2026-10-26"], [x["day"] for x in H])
        one = fa._read_json(os.path.join(tmp, "nightly", f"{D2}.json"), {})
        check("nightly/<day>.json carries the verdict and the day's rows", one.get("verdict") == "differs" and len(one.get("rows") or []) == 1, one)
        fa._write_json(os.path.join(tmp, "summary.json"), fa.summarize(rows, fa._ts(D5, 17, 0), [D1, D5]))
        hb = fa.heartbeat_block(tmp)
        check("heartbeat block carries the last nightly verdicts, newest first",
              hb and [x["day"] for x in hb.get("nightly") or []][:2] == ["2026-10-26", D5], (hb or {}).get("nightly"))

        check("night run at 16:10 ET is about today", fa.nightly_day(fa._ts("2026-10-20", 16, 10)) == "2026-10-20")
        check("a run at 09:00 ET is about the last session", fa.nightly_day(fa._ts("2026-10-20", 9, 0)) == "2026-10-19")
        check("Monday 09:00 ET -> Friday", fa.nightly_day(fa._ts("2026-10-19", 9, 0)) == "2026-10-16")
        check("Sunday -> Friday", fa.nightly_day(fa._ts("2026-10-18", 20, 0)) == "2026-10-16")
        check("the Watcher calls the nightly summary after the session",
              "nightly(e.date().isoformat(), store=self.store, now=now, rep=rep)" in open(fa.__file__, encoding="utf-8").read())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"drift nightly: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
