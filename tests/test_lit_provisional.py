"""LiveBot._confirm_provisional (engine/live.py): a LIT entry routed at market on its 1m CISD close is flattened as "NO TRADE"
only when the model had the bars to judge it. While the feed has not shown the fill bar yet (LE_BarFeed / Yahoo late by a
few seconds, or the 5m bar lagging at a 5m boundary) the routed position is kept and checked again on the next poll.

    python -X utf8 -m tests.test_lit_provisional
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import live  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""), flush=True)


def bot(et_, l1, l5, forming_5m=False):
    b = live.LiveBot()
    b.clock = lambda: et_ + 62
    b.cfg = {**live.LIVE_DEFAULTS}
    b.state = {"model": "lit", "position": None, "enter_now": None, "lit": {"forming_5m": forming_5m}}
    b.health.update({"last_1m_bar_t": l1, "last_bar_t": l5})
    b._open_routed, b._open_qty = et_, 16
    b._provisional = {et_: {"qty": 16, "model_qty": 16, "dir": 1, "est": False, "target": 20100.0, "t": et_ + 2}}
    routes = []
    b._route = lambda a: routes.append(a) or {"ok": True}
    b._log = lambda *a, **k: None
    return b, routes


def main():
    et_ = 1_790_000_000 - 1_790_000_000 % 300 + 240        # fill bar = the last minute of a 5m bar (closes on the 5m boundary)
    res = {"trades": []}
    # 1. the fill bar is not in the 1m feed yet: keep the position, no verdict
    b, routes = bot(et_, l1=et_ - 60, l5=et_ - 240 - 300)
    b._confirm_provisional(None, None, res, "NQ")
    check("fill bar missing from the 1m feed: no flatten, check pending", not routes and not b._provisional[et_].get("done")
          and b._open_routed == et_, str(routes))
    # 2. the 1m feed has it but the 5m bar containing it lags (5m boundary): still no verdict
    b, routes = bot(et_, l1=et_, l5=et_ - 240 - 300)
    b._confirm_provisional(None, None, res, "NQ")
    check("1m fill bar in, its 5m bar lagging: no flatten", not routes and not b._provisional[et_].get("done"), str(routes))
    # 3. the model had every bar and the trade is not there: flattened once
    b, routes = bot(et_, l1=et_, l5=et_ - 240)
    b._confirm_provisional(None, None, res, "NQ")
    b._confirm_provisional(None, None, res, "NQ")
    check("model saw the fill bar and has no trade: one NO TRADE flatten", len(routes) == 1 and routes[0]["side"] == "exit"
          and routes[0]["reason"] == "NO TRADE" and routes[0]["qty"] == 16 and b._open_routed is None, str(routes))
    # 4. mid-5m fill bar, 5m bar forming (early mode): the model could judge it
    et2 = et_ - 120
    b, routes = bot(et2, l1=et2, l5=et2 - et2 % 300 - 300, forming_5m=True)
    b._confirm_provisional(None, None, res, "NQ")
    check("fill bar inside the forming 5m bar (early mode): judged, flattened", len(routes) == 1, str(routes))
    # 5. the trade is there: nothing routed
    b, routes = bot(et_, l1=et_, l5=et_ - 240)
    b._confirm_provisional({"entry_t": et_, "qty": 16, "target": 20100.0, "dir": 1}, None, res, "NQ")
    check("model has the trade: nothing routed", not routes and b._provisional[et_].get("done"), str(routes))
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"{n_ok}/{len(RESULTS)} passed")
    return n_ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
