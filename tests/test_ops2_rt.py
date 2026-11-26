"""Red team 2026-11-26 (day-ops2 roll): a shadow LE_Feed that MISSES bars never verifies (missing = different).
    python -X utf8 -m tests.test_ops2_rt
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import roll_auto as RA      # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    ET = ZoneInfo("America/New_York")
    chart, shadow, gappy = {}, {}, {}
    for day in ("2026-11-30", "2026-12-01", "2026-12-02"):
        t0 = int(dt.datetime.fromisoformat(day + "T09:30").replace(tzinfo=ET).timestamp())
        for i in range(400):
            t = t0 + 60 * i
            chart[t] = shadow[t] = (1.0, 2.0, 0.5, 1.5)
            if i % 5:
                gappy[t] = chart[t]                     # every 5th bar missing (20%)
    run_ok, _ = RA.verdict(RA.compare(chart, shadow), "2026-12-03")
    run_gap, bad = RA.verdict(RA.compare(chart, gappy), "2026-12-03")
    check("an identical shadow verifies (3 equal days)", run_ok == 3, run_ok)
    check("a shadow missing 20% of the bars never verifies", run_gap == 0 and bad is not None, (run_gap, bad))
    late = {t: v for t, v in shadow.items() if t >= min(shadow) + 120 * 60}     # installed 2 h into the first day
    run_late, _ = RA.verdict(RA.compare(chart, late), "2026-12-03")
    check("a shadow that started late is not blamed for the bars before its first one", run_late >= 2, run_late)
    return 0 if all(R) else 1




def backup_checks():
    import json as _j
    from engine.pc_backup import disarm
    env_in = b"# live switch: NINJATRADER_LIVE (written by START's phrase)\r\nOTHER=keep\r\n"
    out = disarm("bot/.env.local.ps1", env_in)
    check("backup: the .env.local.ps1 live-switch line is taken out, the rest kept", b"NINJATRADER_LIVE" not in out and b"OTHER=keep" in out, out)
    ka = disarm("bot/data/keepalive.json", _j.dumps({"accounts": ["x"], "consent": {"t": 1, "via": "start_phrase"}}).encode())
    check("backup: the keep-alive START consent is taken out, its settings kept", "consent" not in _j.loads(ka) and _j.loads(ka)["accounts"] == ["x"], ka)
    check("backup: other files untouched", disarm("bot/data/accounts.json", b'{"consent":1}') == b'{"consent":1}')


if __name__ == "__main__":
    main()
    backup_checks()
    print(f"\nops2 red team (with backup): {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    raise SystemExit(0 if all(R) else 1)
