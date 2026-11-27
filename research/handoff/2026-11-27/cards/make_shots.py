"""night-nq-cards 2026-11-27: the sample card pictures in shots/ (fake bars + the test snapshot; never the owner's data).
    python -X utf8 research/handoff/2026-11-27/cards/make_shots.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")

from engine import trade_card as TC      # noqa: E402
from tests import test_trade_cards as T  # noqa: E402

OUT = os.path.join(HERE, "shots")


def bars(t_from, t_to, seed=0.0):
    out, px = [], 25520.0
    for i, t in enumerate(range(t_from - t_from % 60, t_to, 60)):
        o = px
        px += math.sin(i / 11 + seed) * 2.2 + math.sin(i * 1.7) * 1.6 - (6 if 112 <= i <= 118 else 0) + (3 if i > 120 else 0)
        out.append((t, o, max(o, px) + abs(math.sin(i)) * 2 + 0.5, min(o, px) - abs(math.cos(i)) * 2 - 0.5, px))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="shots_")
    TC.CARD_DIR = os.path.join(tmp, "cards")
    et0 = T.ET0
    b = bars(et0 - 7200, et0 + 3600)
    entry = round(b[120][4], 2)
    stop, target = entry - 20.0, entry + 60.0
    bot = SimpleNamespace(brain={"setups": [{"dir": 1, "status": "filled", "swept": ["London low"], "ext": stop + 0.25,
                                             "status_text": f"Filled 09:52 at {entry:,.2f} - still open"}]}, second={}, cfg={})
    fill = {"kind": "fill", "key": f"fill:{et0}", "side": "LONG", "qty": 2, "entry": entry, "stop": stop, "target": target, "t": et0,
            "account": "Zlarior 50K"}
    times = {}
    t = time.perf_counter()
    c = TC.build(fill, "entry", now=et0 + 600, bot=bot, bars_fn=lambda a, z: [x for x in b if a <= x[0] <= z])
    times["entry"] = time.perf_counter() - t
    os.replace(c["photo"], os.path.join(OUT, "entry_card.png"))
    out = {"kind": "outcome", "key": f"out:{et0}", "side": "LONG", "qty": 2, "exit_px": target, "usd": 240.0, "exit": "TARGET",
           "t": et0 + 3000, "account": "Zlarior 50K"}
    t = time.perf_counter()
    c2 = TC.build(out, "exit", now=et0 + 3010, bot=SimpleNamespace(brain={}, second={}, cfg={}),
                  bars_fn=lambda a, z: [x for x in b if a <= x[0] <= z])
    times["exit"] = time.perf_counter() - t
    os.replace(c2["photo"], os.path.join(OUT, "exit_card.png"))
    from tools import pc_guard as G
    n2 = T.ts(2026, 11, 24, 16, 21)
    m = G.day_summary(T._snap(n2), n2, {})
    t = time.perf_counter()
    p = TC.summary_photo(m[0]["card"], m[0]["key"])
    times["day"] = time.perf_counter() - t
    os.replace(p, os.path.join(OUT, "day_summary.png"))
    rp = os.path.join(tmp, "reviews.jsonl")
    rows = [{"bot": "lit", "day": "2026-11-23", "status": "matched", "live": {"usd": 240.0, "r": 3.0}, "twin": {"usd": 250.0, "r": 3.1},
             "cause": "slippage"},
            {"bot": "lit", "day": "2026-11-25", "status": "missed", "twin": {"usd": -129.4, "r": -1}, "gap_usd": 129.4, "cause": "PC off"},
            {"bot": "atlas", "day": "2026-11-24", "status": "matched", "live": {"usd": 514.18, "r": 2.0}, "twin": {"usd": 500.0, "r": 2.0}}]
    with open(rp, "w") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in rows)
    fr = T.ts(2026, 11, 27, 17, 5)
    w = G.weekly_report(T._snap(fr), fr, {}, reviews_path=rp)
    t = time.perf_counter()
    p = TC.summary_photo(w[0]["card"], w[0]["key"])
    times["week"] = time.perf_counter() - t
    os.replace(p, os.path.join(OUT, "week_report.png"))
    for f in sorted(os.listdir(OUT)):
        print(f"{f:20s} {os.path.getsize(os.path.join(OUT, f)) // 1024:4d} KB")
    print({k: f"{v * 1000:.0f} ms" for k, v in times.items()})


if __name__ == "__main__":
    main()
