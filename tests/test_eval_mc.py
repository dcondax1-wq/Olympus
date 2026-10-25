"""Live eval Monte Carlo (engine/eval_mc.py) + its line in the morning brief.

  python -X utf8 -m tests.test_eval_mc
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import eval_mc, lit_brief  # noqa: E402

LS = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def main():
    D = eval_mc.sample()
    check("sample: 2026 sessions and trades", len(D["sess"]) > 150 and len(D["trades"]) > 80, f"{len(D['sess'])} / {len(D['trades'])}")
    fresh = eval_mc.from_clock({"status": "open", "session": 1, "profit": 0.0, "room": 2000.0}, LS, n=1000, seed=3)
    # research reference (lit-two-week-eval.md / lit_eventual.py): 2-week pass ~50-57%, eventual ~77-80%
    check("fresh eval: 2-week pass 35-70%", 35 <= fresh["h2"]["p10"] <= 70, fresh["h2"]["p10"])
    check("fresh eval: eventual pass 60-95%", 60 <= fresh["h2"]["pass"] <= 95, fresh["h2"]["pass"])
    check("shares add to 100", abs(fresh["pass"] + fresh["fail"] + fresh["open"] - 100) < 0.3)
    again = eval_mc.from_clock({"status": "open", "session": 1, "profit": 0.0, "room": 2000.0}, LS, n=1000, seed=3)
    check("same seed, same odds", again["p10"] == fresh["p10"] and again["h2"] == fresh["h2"])
    near = eval_mc.simulate(3, 2900.0, 2000.0, LS, n=500, seed=1)
    thin = eval_mc.simulate(3, -1850.0, 150.0, LS, n=500, seed=1)
    check("$100 from the target passes more than a fresh eval", near["p10"] > fresh["p10"], near["p10"])
    # since the sizing cap invariant (15cb560, 2026-10-24: skip when 1 micro's stop-out does not fit the room, no min 1
    # micro) a thin eval no longer stops out to a FAIL: it mostly can not trade and stays open (stuck) instead
    check("$150 of room passes less and gets stuck (open) more than a fresh eval",
          thin["pass"] < fresh["pass"] and thin["open"] > fresh["open"], {k: thin.get(k) for k in ("pass", "fail", "open")})
    late = eval_mc.from_clock({"status": "open", "session": 12, "profit": 500.0, "room": 1800.0}, LS, n=500, seed=1)
    check("past session 10: no 2-week odds, text says so", late["p10"] == 0 and "past the 2-week clock" in late["text"], late["text"][:80])
    check("closed / unknown clock -> None", eval_mc.from_clock({"status": "passed", "session": 4}, LS) is None
          and eval_mc.from_clock(None, LS) is None)
    b = {"day": "2026-10-20", "at": "Tue 07:31 ET", "morning": {"stage": "full", "built": "07:31", "plan": "p", "overnight": {"text": "o"},
         "vix": {"text": "v"}, "news_text": "n", "monday": {}, "boxes": [], "levels": [], "eval": {"text": "e", "mc": fresh}}}
    L = lit_brief.readme_lines(b)
    check("README: Eval odds line", any(x.startswith("- Eval odds: Monte Carlo from today") for x in L))
    print(f"eval_mc: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
