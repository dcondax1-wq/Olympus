"""Red team 2026-11-25 for engine/setup_progress.py: a choppy ATLAS day (the EMA member's "Armed" text carries the live EMA 50)
must not re-send one setup every 5m bar, and ATLAS lines must leave room for the LIT lines. Fake sends only.

    python -X utf8 -m tests.test_setup_progress_rt
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

from engine import setup_progress as SP           # noqa: E402
from tests.test_setup_progress import ts, brain, make_bot   # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def ema_second(e50, stage="armed"):
    txt = (f"Armed (long): price is at the 5m EMA 50 ({e50:,.2f}); waiting for a swing low to be swept and a 5m CISD close back up"
           if stage == "armed" else f"Trend up (longs only): waiting for a pullback to the 5m EMA 50 ({e50:,.2f}, 12 pts away)")
    return {"strategies": {"ema": {"short": "EMA", "state": {"stage": stage, "text": txt}, "brain": {}}}}


def main():
    sent = []
    tmp = tempfile.mkdtemp()
    sp = SP.SetupProgress(send=lambda ev: (sent.append(ev), "sent")[1], state_path=os.path.join(tmp, "sp.json"))
    SP.atlas_keys = lambda bot: ["ema"]
    SP._open_hours = lambda now: True
    t0 = ts(2026, 11, 25, 9, 40)
    for i in range(40):                                   # 40 five-minute bars, the EMA moves, armed <-> waiting
        e50 = 25500 + i * 1.75
        bot = make_bot(brain("wait", 2, "Waiting", "-"), second=ema_second(e50, "armed" if i % 3 else "waiting"), price=None)
        sp.step(bot, t0 + i * 300)
    armed = [e for e in sent if e["key"].endswith(":armed")]
    check("EMA armed with a moving EMA 50: one line, not one per bar", len(armed) == 1, [e["key"] for e in armed])
    # ATLAS cap leaves room for LIT
    sp2 = SP.SetupProgress(send=lambda ev: (sent.append(ev), "sent")[1], state_path=os.path.join(tmp, "sp2.json"))
    sent.clear()
    lv = [{"name": f"L{j}", "label": f"L{j}", "px": 25500 + j * 100, "stage": "watching"} for j in range(10)]
    for j in range(10):
        sec = {"strategies": {"ema": {"short": "SR", "state": {"stage": "waiting", "text": "w"}, "brain": {"levels": lv}}}}
        sp2.step(make_bot(brain("wait", 2, "Waiting", "-"), second=sec, price=25500 + j * 100 + 5), t0 + j * 60)
    na = len([e for e in sent if e["key"].startswith("setup:atlas:")])
    check(f"ATLAS stops at {SP.ATLAS_MAX} a day", na == SP.ATLAS_MAX, na)
    sp2.step(make_bot(brain("setup", 5, "5m CISD", "waiting for the limit"), second=None), t0 + 900)
    check("a LIT step-5 line still goes after a busy ATLAS morning", any(e["key"].startswith("setup:lit:") for e in sent),
          [e["key"] for e in sent][-3:])
    print(f"\nsetup_progress red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
