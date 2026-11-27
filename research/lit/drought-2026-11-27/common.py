"""Shared loader for the LIT drought study (research only)."""
import json, os, sys, csv, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from tools import lit_final as lf  # noqa
from engine import lit  # noqa

def live_P():
    return json.load(open(os.path.join(ROOT, "live_model.json")))["lit"]

def sessions():
    """weekdays with RTH bars (09:30-16:00 ET) in data/NQ_5m.csv (ET date of the bar)."""
    M, _ = lf.market(live_P()["ref"], live_P()["extra_boxes"])
    out = set()
    import numpy as np
    for d, m, w in zip(M.dates, M.mod, M.dow):
        if 570 <= m < 960 and w < 5:
            out.add(str(d))
    return sorted(out)
