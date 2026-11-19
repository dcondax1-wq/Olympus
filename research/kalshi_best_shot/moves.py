#!/usr/bin/env python3
"""When do the big price moves happen? From the harvested hourly candles (harvest.py): for every market-hour, the mid's move
vs the hour before; counts of moves >= 5c and >= 10c by ET weekday and hour, and by hours before the close. Offline.
    python research/kalshi_best_shot/moves.py [SERIES,..] -> research/kalshi_best_shot/moves.json"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bt import BT, ET, F, T  # noqa: E402

WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def main():
    series = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(f[:-8] for f in os.listdir(BT) if f.endswith(".json.gz"))
    out = {}
    for s in series:
        d = json.load(gzip.open(os.path.join(BT, s + ".json.gz"), "rt"))
        by_wd = collections.Counter()
        by_wd_all = collections.Counter()
        by_left = collections.Counter()
        by_left_all = collections.Counter()
        for v in d["markets"].values():
            close = T(v["info"]["close_time"]) if v["info"].get("close_time") else None
            prev = None
            for c in v["candles"]:
                b, a = F(c[1]), F(c[2])
                if b is None or a is None or not (0 < b < a < 1):
                    prev = None
                    continue
                mid = (b + a) / 2
                if prev is not None:
                    mv = abs(mid - prev)
                    x = dt.datetime.fromtimestamp(c[0] + ET, dt.timezone.utc)
                    k = "%s %02d" % (WD[x.weekday()], x.hour)
                    by_wd_all[k] += 1
                    left = int((close - c[0]) // 86400) if close else -1
                    by_left_all[left] += 1
                    if mv >= 0.05 - 1e-9:
                        by_wd[k] += 1
                        by_left[left] += 1
                prev = mid
        rows = sorted(by_wd_all, key=lambda k: (WD.index(k[:3]), k[4:]))
        out[s] = {"by_et_hour": {k: [by_wd[k], by_wd_all[k]] for k in rows},
                  "by_days_left": {str(k): [by_left[k], by_left_all[k]] for k in sorted(by_left_all)}}
        top = sorted(rows, key=lambda k: -by_wd[k] / max(by_wd_all[k], 1))[:6]
        print(s, "moves>=5c per market-hour: overall %.3f;" % (sum(by_wd.values()) / max(sum(by_wd_all.values()), 1)),
              "worst ET hours:", ", ".join("%s %.2f" % (k, by_wd[k] / by_wd_all[k]) for k in top),
              "| by days to close:", " ".join("%s:%.3f" % (k, by_left[k] / by_left_all[k]) for k in sorted(by_left_all) if by_left_all[k] > 20))
    json.dump(out, open(os.path.join(HERE, "moves.json"), "w"), indent=0)


if __name__ == "__main__":
    main()
