#!/usr/bin/env python3
"""Print TRAIN-side numbers only (so the held-out block is not read while the scripts are being written).
    python research/kalshi_edge_C/peek_train.py results_weather.json main
"""
import json, os, sys
r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), sys.argv[1])))
m = r["families"][sys.argv[2]] if "families" in r else r["family"]
print({k: m.get(k) for k in ("units", "days", "first_day", "last_day", "test_from", "cells_defined", "cells_eligible", "null_max_t_p95", "vol_scale", "days_with_futures_model")})
print({k: v for k, v in (m.get("brier") or {}).items() if k.startswith("train")})
for c in sorted([c for c in m["cells"] if "train_t" in c], key=lambda c: -c["train_t"])[:int(sys.argv[3]) if len(sys.argv) > 3 else 12]:
    print("%-78s n %5d days %3d edge %+.3f t %+.2f win %.3f price %.3f" % (c["cell"][:78], c["train_n"], c["train_days"], c["train_edge"], c["train_t"], c["train_win"], c["train_price"]))
