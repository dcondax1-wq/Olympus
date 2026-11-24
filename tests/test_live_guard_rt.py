"""Red team on day-zeroerr (2026-11-24): engine/live_guard never pushes about an account the owner switched off. Fakes only.

    python -X utf8 -m tests.test_live_guard_rt        (< 1 s)

1. an extra account with "enabled": false (multi_account problem "disabled in the config") gets no MISSED TRADE for a LIT entry
   (FOUND: one push per LIT entry, every day) and no NOT READY row at the 01:55 / 09:00 armed check; a broken account (a real
   start problem) still does.
"""
from __future__ import annotations

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import live_guard as G  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def acct(name, problem, enabled=True):
    return types.SimpleNamespace(name=name, label=name, problem=problem, spec={"adapter": "ninjatrader", "nt_account": name,
                                 "enabled": enabled, "armed": True}, ledger=[], blocked=set(), hedge_wait=set(), seen=set(),
                                 added_t=0, disabled_reason=lambda p=problem: p)


def main():
    t = 1795660800 + 9 * 3600            # a weekday, 09:00 UTC-ish; only the age matters
    off = acct("MFFU-OFF-1", "disabled in the config", enabled=False)
    bad = acct("MFFU-BAD-2", "adapter failed: OSError: x")
    bot = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_account": "MFFU-MAIN"}, kill=False,
                                seen={("entry", t)}, state={}, second=None, accts=types.SimpleNamespace(accounts=[off, bad]),
                                acct_b=None, acct_r=None, acct_r2=None)
    real_mc = G.missing_configured
    G.missing_configured = lambda *a, **k: []
    try:
        m = G.missed(bot, t + 300)
        accts = {x["account"] for x in m}
        check("1. the owner's disabled account: no MISSED TRADE", "MFFU-OFF-1" not in accts, m)
        check("1. a broken account (start problem): still reported", "MFFU-BAD-2" in accts, m)
        rows = G.arm_rows(bot, t, live_names=["MFFU-MAIN", "MFFU-BAD-2"])
        labels = [r["label"] for r in rows]
        check("1. the armed check lists no row for the disabled account", "MFFU-OFF-1" not in labels, rows)
    finally:
        G.missing_configured = real_mc
    ok = sum(RES)
    print(f"\nlive guard red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
