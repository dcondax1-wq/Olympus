"""Red team #23 (2026-11-26): a leftover open leg in a state file of an account the bot no longer runs made files_flat_reason say
"not flat" forever, and "not flat" was never an update_stuck reason: every update held back, silently. Now 30 h of the same
"not flat" = ONE "Bot update stuck" line naming the file; a real trade (flat again within the day) never triggers it.
    python -X utf8 -m tests.test_flat_stuck_rt
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import live_guard as LG     # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    t0 = 1_800_000_000
    why = "not flat: an open MNQ 09-26 leg in data/ninjatrader_state_fleet_old.json (protected)"
    au = lambda t: {"last": {"status": "skipped", "reason": why, "t": t}}
    st, p = LG.update_stuck(None, au(t0), t0)
    check("first 'not flat': no alert, the clock starts", p is None and st.get("flat_since") == t0, (st, p))
    st, p = LG.update_stuck(st, au(t0 + 6 * 3600), t0 + 6 * 3600)
    check("6 h of 'not flat' (a trade can be open): still no alert", p is None, p)
    st, p = LG.update_stuck(st, au(t0 + 31 * 3600), t0 + 31 * 3600)
    check("31 h of the same 'not flat': ONE 'Bot update stuck' line naming the file",
          p is not None and "ninjatrader_state_fleet_old.json" in p["body"] and "leftover" in p["body"], p)
    st2, p2 = LG.update_stuck(st, au(t0 + 32 * 3600), t0 + 32 * 3600)
    check("... once a day (no spam)", p2 is None, p2)
    st3, p3 = LG.update_stuck(st, {"last": {"status": "updated", "reason": "", "t": t0 + 33 * 3600}}, t0 + 33 * 3600)
    check("updated: the clock resets", st3 == {} and p3 is None, (st3, p3))
    print(f"\nflat stuck red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
