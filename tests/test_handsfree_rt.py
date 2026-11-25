"""Red team 2026-11-25 (day-handsfree): a forwarded Telegram message is never a command; the '/update force' receipt names
the parked files and says loudly when a strategy / rule file now runs the repo's version.

    python -X utf8 -m tests.test_handsfree_rt
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import tg_cmd as T            # noqa: E402
from engine.remote_ctl import parked_line  # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    me = {"chat": {"type": "private", "id": 42}, "from": {"id": 42, "is_bot": False}, "text": "/update force"}
    check("the owner's own message is a command", T.is_owner(me, "42"))
    for k, v in (("forward_origin", {"type": "user"}), ("forward_from", {"id": 7}), ("forward_date", 1700000000),
                 ("via_bot", {"id": 9}), ("forward_sender_name", "x")):
        check(f"a message with {k} is never a command", not T.is_owner({**me, k: v}, "42"))
    check("a group is never a command", not T.is_owner({**me, "chat": {"type": "group", "id": 42}}, "42"))
    ln = parked_line(["live_model.json", "live_model_lit.json", "tools/x.py"])
    check("the receipt names a parked live_model and says the repo's version runs",
          "live_model.json" in ln and "STRATEGY" in ln and "git stash pop" in ln, ln)
    check("no parked file: no extra words", parked_line([]) == "" and parked_line(None) == "")
    check("a code-only park: no strategy warning", "STRATEGY" not in parked_line(["engine/x.py"]))
    print(f"\nhandsfree red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
