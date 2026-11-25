"""NEW STRATEGY scaffold (day-zerotouch2 2026-11-24, owner: "adding strategies ... should all be done way quicker"). docs/NEW_STRATEGY.md.

    python -X utf8 tools/new_strategy.py <id> --label "One plain line" [--dry-run]

Makes, for a research lane that is about to be proven (id = lower-case letters, digits, _):
  engine/lanes/<id>.py               the switch: OFF by default (data/lanes/<id>.json, gitignored); set_on(phrase) only with the typed
                                     live phrase AND research/lanes/<id>/PROOF.json "passed": true; set_off(); is_on(); signal() stub
  research/lanes/<id>/proof.py       fills PROOF.json from the strategy-test bars (both 2026 halves + 2021-25, 2-4 trades/week, costs in);
                                     "passed" only when every bar holds (tools / .claude/skills/strategy-test)
  research/lanes/<id>/decide_card.json   the Decide card for the lead to add (a YES on the phone queues lane:<id> for the next START)
  tests/test_lane_<id>.py            off by default, wrong phrase refused, no proof refused, proof + phrase = on, off again
It never touches live_model*.json, second_model.json or the live loop: wiring signal() into a bot is the lead's reviewed step.
Refuses an id that exists. Tests: tests/test_zerotouch2.py g.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID_OK = re.compile(r"^[a-z][a-z0-9_]{1,30}$")

LANE = '''"""Lane {id}: {label} (made by tools/new_strategy.py; docs/NEW_STRATEGY.md). OFF by default.
Switch file data/lanes/{id}.json (gitignored). On only with the typed live phrase AND research/lanes/{id}/PROOF.json "passed": true.
signal() is a stub: the lead wires it into a bot only after the proof (STRATEGY rules in CLAUDE.md)."""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABEL = {label!r}
SWITCH = os.path.join(ROOT, "data", "lanes", "{id}.json")
PROOF = os.path.join(ROOT, "research", "lanes", "{id}", "PROOF.json")


def _read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def is_on(path: str | None = None) -> bool:
    d = _read(path or SWITCH)
    return isinstance(d, dict) and d.get("on") is True


def proof_ok(path: str | None = None) -> bool:
    d = _read(path or PROOF)
    return isinstance(d, dict) and d.get("passed") is True


def _write(on: bool, path: str | None = None):
    p = path or SWITCH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({{"on": on, "t": int(time.time())}}, fh)


def set_on(phrase: str, path: str | None = None, proof: str | None = None) -> dict:
    from engine.go import LIVE_PHRASE, typed_phrase
    if typed_phrase(str(phrase or "")) != LIVE_PHRASE:
        return {{"ok": False, "error": "the live phrase was not typed: nothing switched on"}}
    if not proof_ok(proof):
        return {{"ok": False, "error": "research/lanes/{id}/PROOF.json has not passed the strategy-test bars yet"}}
    _write(True, path)
    return {{"ok": True, "say": "{id} ON"}}


def set_off(path: str | None = None) -> dict:
    _write(False, path)
    return {{"ok": True, "say": "{id} OFF"}}


def signal(bars, now=None):
    """The lane's entry decision: None = no trade. Filled in by the research; wired by the lead after the proof."""
    return None
'''

PROOF_PY = '''"""Proof for lane {id} ({label}): fill in run() with the lane's backtest (futures data only: data/ TradingView NQ1!/ES1! + NinjaTrader
bars; costs in), then  python -X utf8 research/lanes/{id}/proof.py  writes PROOF.json. "passed" only when EVERY bar holds."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = {{"tpw_min": 2.0, "tpw_max": 4.0}}


def run() -> dict:
    """-> {{"h1_2026": {{"net": $, "pf": x, "tpw": n, "dd": $}}, "h2_2026": {{...}}, "y2021_25": {{...}}}}. Replace this stub."""
    return {{}}


def verdict(r: dict) -> dict:
    parts = [r.get(k) or {{}} for k in ("h1_2026", "h2_2026", "y2021_25")]
    ok = len(parts) == 3 and all(p.get("net", 0) > 0 and p.get("pf", 0) > 1 and BARS["tpw_min"] <= p.get("tpw", 0) <= BARS["tpw_max"]
                                 for p in parts)
    return {{"lane": "{id}", "passed": bool(ok), "results": r, "bars": "both 2026 halves + 2021-25 positive, PF > 1, 2-4 trades/week, costs in"}}


if __name__ == "__main__":
    v = verdict(run())
    with open(os.path.join(HERE, "PROOF.json"), "w", encoding="utf-8") as fh:
        json.dump(v, fh, indent=1)
    print(("PASSED" if v["passed"] else "NOT passed") + ": " + v["bars"])
'''

TEST = '''"""Lane {id} switch (tools/new_strategy.py). python -X utf8 -m tests.test_lane_{id}"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.lanes import {id} as L  # noqa: E402
from engine.go import LIVE_PHRASE  # noqa: E402


def main() -> int:
    d = tempfile.mkdtemp()
    sw, pr = os.path.join(d, "sw.json"), os.path.join(d, "proof.json")
    res = [not L.is_on(sw), not L.set_on("yes", sw, pr)["ok"], not L.set_on(LIVE_PHRASE, sw, pr)["ok"] and not L.is_on(sw)]
    json.dump({{"passed": True}}, open(pr, "w"))
    res += [L.set_on(LIVE_PHRASE, sw, pr)["ok"] and L.is_on(sw), L.set_off(sw)["ok"] and not L.is_on(sw), L.signal([]) is None]
    print(f"lane {id}: {{sum(res)}}/{{len(res)}} passed")
    return 0 if all(res) else 1


if __name__ == "__main__":
    sys.exit(main())
'''


def plan(lane_id: str, label: str, root: str = ROOT) -> dict:
    """{relative path: text} of every file the scaffold writes."""
    card = {"id": f"lane-{lane_id}", "status": "open", "title": f"Switch on lane {lane_id}?", "what": label,
            "proof": f"research/lanes/{lane_id}/PROOF.json", "yes": f"queues lane:{lane_id}: it turns on at your next START after the phrase",
            "no": "stays off (paper research only)"}
    f = {"label": label, "id": lane_id}
    return {f"engine/lanes/{lane_id}.py": LANE.format(**f), f"research/lanes/{lane_id}/proof.py": PROOF_PY.format(**f),
            f"research/lanes/{lane_id}/decide_card.json": json.dumps(card, indent=1) + "\n", f"tests/test_lane_{lane_id}.py": TEST.format(**f)}


def make(lane_id: str, label: str, root: str = ROOT, dry: bool = False) -> dict:
    if not ID_OK.match(str(lane_id or "")):
        return {"ok": False, "error": "id: lower-case letters, digits and _ (2-31), starting with a letter"}
    label = " ".join(str(label or "").split())[:80]
    if not label:
        return {"ok": False, "error": "give --label \"one plain line\""}
    files = plan(lane_id, label, root)
    have = [p for p in files if os.path.exists(os.path.join(root, *p.split("/")))]
    if have:
        return {"ok": False, "error": f"already there: {', '.join(have)}"}
    if not dry:
        for p, text in files.items():
            full = os.path.join(root, *p.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
    return {"ok": True, "files": list(files), "dry": dry}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="scaffold a switchable strategy lane (OFF by default)")
    ap.add_argument("id")
    ap.add_argument("--label", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    r = make(a.id, a.label, dry=a.dry_run)
    if not r["ok"]:
        print(f"[FIX] {r['error']}")
        return 1
    print(("Would write" if r["dry"] else "Wrote") + ":\n  " + "\n  ".join(r["files"]))
    print(f"Next: fill research/lanes/{a.id}/proof.py run(), run it, python -X utf8 -m tests.test_lane_{a.id}; the lead adds the Decide card.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
