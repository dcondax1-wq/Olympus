"""A LIT entry first seen late is not chased (pre-launch audit 2026-10-24, engine/live.py LIT_MAX_LATE_S).

    python -X utf8 -m tests.test_lit_late_entry        (~2 s, PaperAdapter, no market data)

LIT fills at the open of its 1m entry bar; the PC bot routes it 2-32 s after the 1m CISD close (state "enter_now"). When the
bot first sees the entry later (a restart without today's live_state.json, a 1m bar a minute late), the open position shows
up in the model with its old stop / target: before this fix it was routed up to 16 minutes late (the 5m engine's rule).
Now: routed when seen <= 90 s after the fill bar opened (cfg lit_max_late_s), else NOT routed + logged; its later model
exit is then not routed either. The 5m engine's rule is unchanged.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import live  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""), flush=True)


def bot_at(tmp, now, name):
    b = live.LiveBot()
    b.clock = lambda: now
    b.state_path = os.path.join(tmp, name + ".json")
    r = b.start({"sym": "NQ", "tf": "5m", "adapter": "paper"}, spawn=False)
    assert r.get("ok"), r
    b.started_at = now - 3600
    b._guard_entry = lambda *a, **k: None          # guards (calendar, dup, clock) are tested elsewhere
    b._equity_qty = lambda entry_t, qty, pos=None: qty
    return b


def main():
    tmp = tempfile.mkdtemp(prefix="le_lit_late_")
    try:
        ent = int(dt.datetime(2026, 1, 7, 4, 43, tzinfo=live.ET_TZ).timestamp())
        pos = {"entry_t": ent, "dir": 1, "qty": 16, "entry": 26548.0, "stop": 26526.0, "stop0": 26526.0, "target": 26681.25,
               "tf": "1m", "be": False}
        for late, want in ((2, True), (62, True), (90, True), (91, False), (150, False), (900, False)):
            b = bot_at(tmp, ent + late, f"b{late}")
            b.state = {"model": "lit", "position": dict(pos)}
            b._route_primary({"trades": []}, "NQ", ent + late, 300)
            routed = [r for r in b.ledger if r["side"] in ("buy", "sell")]
            logged = any("not chasing" in x["text"] for x in b.log)
            check(f"LIT position first seen {late} s after its 1m fill bar opened: " + ("routed" if want else "NOT routed + logged"),
                  (len(routed) == 1) == want and logged != want, f"{routed} {[x['text'] for x in b.log][-2:]}")
            if not want:
                tr = {**pos, "exit_t": ent + 1200, "exit_reason": "TARGET", "pnl": 100.0, "exit_price": 26681.25, "pts": 133.25}
                b.state = {"model": "lit", "position": None}
                b._route_primary({"trades": [tr]}, "NQ", ent + 1300, 300)
                check(f"  ... and its model exit is not routed either (late {late} s)",
                      not [r for r in b.ledger if r["side"] == "exit"])
        b = bot_at(tmp, ent + 600, "eng")
        b.state = {"model": "engine", "position": {**pos, "tf": "5m"}}
        b._route_primary({"trades": []}, "NQ", ent + 600, 300)
        check("the 5m engine's rule is unchanged (an engine position seen 10 min after its entry bar opened is routed)",
              len([r for r in b.ledger if r["side"] in ("buy", "sell")]) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"{n}/{len(RESULTS)} checks passed")
    sys.exit(0 if n == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
