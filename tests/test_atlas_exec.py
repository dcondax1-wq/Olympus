"""ATLAS fast lane (engine/atlas_exec.py, big-atlasfill 2026-11-26). Offline: a fake bot, temp switch files.
  a. OFF by default -> nothing runs; ON + Sim + 5m open -> account B runs once and done() skips the regular call
  b. a real (non-Sim) account is refused even ON; outside the 5m open nothing runs; a failing tick never raises
  c. fill rows: the zeroerr field names, ticks signed by side; the ledger back-fill reads the real PC fills
    python -X utf8 -m tests.test_atlas_exec
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import atlas_exec as X  # noqa: E402

FAILS = []


def ok(c, what):
    print(("ok   " if c else "FAIL ") + what)
    if not c:
        FAILS.append(what)


class AB:
    def __init__(self, name):
        self.name = name

    def adapter_cfg(self):
        return {"nt_account": self.name}


class Bot:
    def __init__(self, name="Sim101", boom=False):
        self.acct_b, self.calls, self.errors, self.boom = AB(name), 0, [], boom

    def _account_b_tick(self, *a):
        if self.boom:
            raise RuntimeError("x")
        self.calls += 1

    def _note_error(self, s):
        self.errors.append(s)


def main():
    os.environ.pop("LE_ATLAS_EXEC", None)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "atlas_exec.json")
        t5 = 1795164300 + 3                                  # 3 s into a 5m bar
        b = Bot()
        ok(X.early(b, None, None, "NQ", t5, path=p) == "off" and b.calls == 0, "a OFF by default (no file) -> nothing runs")
        X.set_on(True, p)
        ok(X.early(b, None, None, "NQ", t5, path=p) == "ran" and b.calls == 1, "a ON + Sim101 + 5m open -> account B runs")
        ok(X.done(b, t5) and not X.done(b, t5 + 30) and not X.done(b, t5 + 60), "a done() for THIS poll only (the +32 s poll still runs account B)")
        r = Bot("MFFU...6017")
        ok(X.early(r, None, None, "NQ", t5, path=p).startswith("refused") and r.calls == 0, "b a real account is refused even ON")
        ok(X.early(b, None, None, "NQ", t5 + 120, path=p) == "not 5m open", "b 2 minutes into the bar -> nothing")
        q = Bot(); q._rapid_atlases = lambda: [AB("MFFU...R25")]
        ok(X.early(q, None, None, "NQ", t5, path=p).startswith("refused: Rapid") and q.calls == 0,
           "b a real Rapid ATLAS lane (run by the same tick) is refused too")
        e = Bot(boom=True)
        ok(X.early(e, None, None, "NQ", t5, path=p).startswith("error") and e.errors, "b a failing tick is caught and noted")
        X.set_on(False, p)
        ok(X.early(b, None, None, "NQ", t5, path=p) == "off", "b --off turns it off")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "atlas_exec.json")
        ok_, L = X.sim_week(True, p, lane_list=[("ATLAS account B", "Sim101"), ("ATLAS on the Rapid (rapid)", "MFFU...R25")])
        ok(not ok_ and not X.is_on(p) and any("MFFU...R25" in x for x in L), "d --sim-week on refuses a real Rapid lane, changes nothing")
        ok_, L = X.sim_week(True, p, lane_list=[])
        ok(not ok_ and not X.is_on(p), "d --sim-week on refuses with no account B")
        ok_, L = X.sim_week(True, p, lane_list=[("ATLAS account B", "Sim101")])
        ok(ok_ and X.is_on(p) and any("only sooner" in x for x in L), "d --sim-week on with every lane Sim -> ON, plain words")
        ok_, L = X.sim_week(False, p)
        ok(ok_ and not X.is_on(p), "d --sim-week off")
    R = X.report(rows=[X.fill_row("atlas", "sell", 1, 100.0, 99.0, signal_t=k) for k in range(3)])
    ok(R["n"] == 3 and R["avg_ticks_worse"] == 4.0 and R["vs_baseline_ticks"] == 10.0 and "14" in R["words"],
       f"e report: fills n, avg ticks worse vs the 14 baseline: {R['words']}")
    row = X.fill_row("atlas", "sell", 2, 27037.75, 27035.5, signal_t=1, send_t=2, ack_t=3, fill_t=3)
    ok(tuple(k for k in row if k in X.FIELDS) == X.FIELDS and row["ticks"] == 9.0, f"c zeroerr field names, sell 2.25 pts lower = 9 ticks worse")
    ok(X.fill_row("lit", "buy", 1, 100.0, 100.5)["ticks"] == 2.0, "c buy 0.5 higher = 2 ticks worse")
    import glob as _glob
    if not _glob.glob(os.path.join(X.ROOT, "data", "pc_days", "*", "trades.jsonl.gz")):   # the PC's day folders come from data_pull
        print("skip c the ledger back-fill: no data/pc_days in this checkout (python tools/data_pull.py --latest)")
    else:
        L = X.from_ledger()
        s = X.summary(L)
        ok(s.get("atlas", {}).get("n", 0) >= 4 and s["atlas"]["mean_ticks"] >= 9, f"c the ledger back-fill sees the real ATLAS fills: {s.get('atlas')}")
    print("ALL OK" if not FAILS else f"{len(FAILS)} FAILED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
