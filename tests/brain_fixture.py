"""THE BRAIN's bundled SAMPLE (tools/web_public/brain/fixture.json): the War Room's 'forming' morning (Tue 2026-11-24 09:52 ET, a London-low
sweep and a 5m CISD long forming) + the per-bot fields session day-brain-feed adds to the PC report (think, next, levels). Account ids,
the glance's 'mode' and 'what' are never copied. The page shows it only while no PC post has arrived, always labelled SAMPLE.
    python -X utf8 -m tests.brain_fixture          write it
    python -X utf8 -m tests.brain_fixture --check  exit 1 when stale
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "brain", "fixture.json")
KEEP_BOT = ("id", "name", "on", "armed", "stage", "wait", "why", "lv", "arm", "chk", "day", "room", "mll", "log", "lobes", "pos", "atr")


def make(kind="forming"):
    from tests import test_warroom as T
    now = T.NOW
    core = T.core_post(kind, now)
    bars, _ = T.bars_post(kind, now)
    bots = []
    for b in core["pc"]["glance"]["bots"]:
        bots.append({k: b[k] for k in KEEP_BOT if k in b})
    lit, atl = bots[0], bots[1]
    lit["name"], atl["name"] = "Zlarior", "ATLAS"
    lit["think"] = [["09:51", "Checks 6 of 9 passed; stop 1 tick under the sweep extreme 26,178.25 = 54.5 pts"],
                    ["09:50", "5m CISD closed through 26,232.50 -> LONG setup forming"],
                    ["09:50", "Displacement up: body 0.9 ATR back above the London low"],
                    ["09:45", "Inducement: the 09:35 swing low taken first"],
                    ["09:40", "Swept the London low 26,190.25 by 12.0 pts (1.2 ATR) -> waiting for displacement"],
                    ["09:31", "VIX band 3 (25+) -> target 3.1R, banked at 8R"],
                    ["09:12", "Mapping: 11 levels, nearest London low 26,190.25"]]
    lit["next"] = {"setup": "LONG after the London low sweep", "steps": [{"label": "Sweep", "state": "done"}, {"label": "Inducement", "state": "done"},
                   {"label": "Displacement", "state": "done"}, {"label": "5m CISD", "state": "done"}, {"label": "Limit", "state": "now"},
                   {"label": "1m CISD", "state": "wait"}, {"label": "Entry", "state": "wait"}],
                   "waiting_for": "the checks to pass, then a limit at 26,232.50 (valid 30 min)", "dist_pts": 3.5, "window": "open until 15:30 ET",
                   "limit": 26232.5, "stop": 26178.0, "target": 26401.5}
    lit["levels"] = [{"k": "sweep", "p": 26190.25, "label": "London low (swept)"}, {"k": "limit", "p": 26232.5, "label": "limit"},
                     {"k": "stop", "p": 26178.0, "label": "stop"}, {"k": "target", "p": 26401.5, "label": "target 3.1R"},
                     {"k": "fvg", "p": 26205.0, "p2": 26214.75, "label": "5m FVG"}, {"k": "leg", "p": 26178.25, "p2": 26262.0, "label": "expansion leg"}]
    atl["think"] = [["09:41", "EMA: trend pullback armed long"], ["09:31", "S/R: window open, levels pdh 26,370.75 / pdl 26,120.00"],
                    ["09:30", "MACD: watching for a LIT level swept with divergence"]]
    t = core["t"]
    post = {"v": 1, "kind": core.get("kind", "lite"), "lite": True, "t": t, "price": core["price"], "reporter": {"t": t},
            "pc": {"running": True, "t": t, "glance": {"v": 1, "t": core["pc"]["glance"]["t"], "bots": bots}},
            "glog": {"lit": lit["log"], "atlas": atl.get("log", [])},
            "tr": {"on": True, "d": 23, "of": 60, "bf": "running", "o": "2026-09-14", "l": "2026-11-23", "t": t - 600}}
    return {"_about": "SAMPLE only (tests/brain_fixture.py): a recorded-style morning, never real numbers. The page labels it SAMPLE.",
            "now": now, "at": "Tue 2026-11-24 09:52 ET", "lite": post, "bars": bars}


def main(argv):
    txt = json.dumps(make(), indent=None, separators=(",", ":"), ensure_ascii=False) + "\n"
    if "--check" in argv:
        try:
            old = open(OUT, encoding="utf-8").read()
        except OSError:
            old = ""
        print("brain/fixture.json " + ("fresh" if old == txt else "STALE"))
        return 0 if old == txt else 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    print("wrote", os.path.relpath(OUT, ROOT), len(txt), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
