"""Owner 2026-11-03: the eval texts say "Drawdown left $X of $2,000" with the REAL MFFU account's numbers (the PC heartbeat),
not the cloud paper ledger's own room. Display only. Run: python -X utf8 -m tests.test_eval_real_text"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import eval_life as EL, readiness as R   # noqa: E402
from tools import cloud_monitor as cm                # noqa: E402

fails = []


def check(name, ok, info=""):
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {info}"))
    if not ok:
        fails.append(name)


PC = {"launch": {"facts": {"broker": {"fresh": True, "cash": 49313.54, "floor": 48168.2, "room": 1132.7}}},
      "brain": {"sizing": {"eval": {"room": 1132.7, "to_target": 3699.1}}}}
r = cm.real_eval(PC)
check("real_eval: broker balance, drawdown left $1,132.70 of $2,000, $3,686.46 to the target",
      r and r["room"] == 1132.7 and r["mll"] == 2000.0 and r["balance"] == 49313.54 and r["to_target"] == 3686.46, r)
PC2 = json.loads(json.dumps(PC))
PC2["launch"]["facts"]["broker"]["fresh"] = False
r2 = cm.real_eval(PC2)
check("real_eval: broker stale -> the bot's anchored room", r2 and r2["room"] == 1132.7 and r2["to_target"] == 3699.1, r2)
check("real_eval: no heartbeat -> None (the paper text stays)", cm.real_eval(None) is None and cm.real_eval({}) is None)

v = EL.view({"2026-11-02": -726.2}, "2026-10-19", "2026-11-03", {"mode": "two_week"})
check("eval_life text: 'drawdown left $X of $2,000', no 'room $'", "drawdown left $" in v["text"] and "of $2,000" in v["text"]
      and "room $" not in v["text"], v["text"])
check("readiness line: drawdown left, no 'eval day N of 10'",
      R.account_line("Zlarior 50K", {"room": 1132.7, "mll": 2000, "session": 12, "sessions": 10}) == "Zlarior 50K: drawdown left $1,133 of $2,000")

print(f"eval real text: {'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
sys.exit(1 if fails else 0)
