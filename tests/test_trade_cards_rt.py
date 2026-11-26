"""Red team 2026-11-26 (day-cards): a Telegram caption over 1024 characters never cuts the alert's $ lines (legend dropped first,
then the full text message); the chart reads NinjaTrader's files only when the bot's own history has no bars.
    python -X utf8 -m tests.test_trade_cards_rt
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import alert_bus as AB      # noqa: E402
from engine import trade_card as TC     # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def main():
    calls = []
    op, ot = AB.send_telegram_photo, AB.send_telegram
    AB.send_telegram_photo = lambda c, p, cap, s: (calls.append(("photo", len(cap))), ("telegram:1", "ok"))[1]
    AB.send_telegram = lambda c, t, b, s: (calls.append(("text", len(t) + len(b))), ("telegram:2", "ok"))[1]
    try:
        cfg = {"telegram": {"token": "x", "chat_id": "1"}}
        ev = {"photo": "p.png", "legend": "L" * 100}
        AB._one("telegram", cfg, ev, "T", "b" * 500, False)
        AB._one("telegram", cfg, ev, "T", "b" * 960, False)
        AB._one("telegram", cfg, ev, "T", "b" * 1100, False)
    finally:
        AB.send_telegram_photo, AB.send_telegram = op, ot
    check("short: the photo with the legend", calls[0] == ("photo", 1 + 1 + 500 + 1 + 100), calls)
    check("over 1024 with the legend: the photo WITHOUT the legend", calls[1] == ("photo", 1 + 1 + 960), calls)
    check("over 1024 without it: the full text message (no cut $ lines)", calls[2][0] == "text", calls)

    import pandas as pd
    nt_reads = []

    class Bot:
        cfg = {"sym": "NQ"}

        def _read_hist(self, sym, tf):
            return pd.DataFrame({"time": range(0, 600, 60), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    import engine.ninjatrader as NT
    orig = NT.NinjaTraderBars

    class Fake:
        def __init__(self, *_a):
            pass

        def recent_bars(self, *_a):
            nt_reads.append(1)
            return None, "x", None
    NT.NinjaTraderBars = Fake
    try:
        b = TC.bars(0, 600, Bot())
    finally:
        NT.NinjaTraderBars = orig
    check("history has the bars: NinjaTrader's files are not read", len(b) == 10 and not nt_reads, (len(b), nt_reads))
    print(f"\ntrade cards red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
