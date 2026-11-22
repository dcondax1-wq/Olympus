"""Edge hunt lane D (2026-11-22): shared helpers. PAPER / RESEARCH ONLY: engine/ and live_model*.json are never edited.

Base = today's live LIT trades (tools/lit_edge.ctx()["T"], 631 trades, == run lit_live), scored by tools/lit_edge.evaluate:
LIT size rule (the live size, 1 tick slip + $1.40/ct costs in), the live Builder 50K eval path (two_week room_f 0.4 to session
80, engine/sizing.lit_qty = the MFFU caps) and the funded Builder 50K Monte Carlo (tools/uprisk.funded_mc, idm_cap $1,500).
Every variant is appended to research/edge_hunt/d/variant_log.jsonl (the count is reported in the write-up).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import lit_edge as E  # noqa: E402

LOG = os.path.join(HERE, "variant_log.jsonl")
SP = ("H1", "H2", "2021-25")


def log_variant(lane, name, desc, summary):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": int(time.time()), "lane": lane, "name": name, "desc": desc, "summary": summary},
                           default=float) + "\n")


def count_variants():
    if not os.path.exists(LOG):
        return 0
    names = set()
    for ln in open(LOG, encoding="utf-8"):
        r = json.loads(ln)
        names.add((r["lane"], r["name"]))
    return len(names)


def span_sum(L, sp):
    a, z = E.SPANS[sp]
    return sum(l["pnl"] for l in L if a <= l["day"] <= z)


def row(nm, s):
    """One compact printable row of E.short()."""
    L, V = s["lit"], s["eval"]
    f = lambda x: f"PF {x['pf']} {x['net']:+,} ${x['per_month']:,}/mo DD {x['dd']:,}"
    return (f"{nm[:30]:30s} LIT H1[{f(L['H1'])}] H2[{f(L['H2'])}] 21-25[{f(L['2021-25'])}] tpw {L['H1']['tpw']}/{L['H2']['tpw']} | "
            f"EVAL H1[{V['H1']['net']:+,} 2w {V['H1']['p10']}/{V['H1']['f10']} med {V['H1']['pass_med']}] "
            f"H2[{V['H2']['net']:+,} 2w {V['H2']['p10']}/{V['H2']['f10']} med {V['H2']['pass_med']}]")


def verdict(s):
    """The lane's gate: beats today's LIT in BOTH 2026 halves (LIT-size $ AND eval-path $, no more 2-week fails) AND 2021-25 LIT
    $ not worse, 2+ trades a week."""
    if "d_lit" not in s:
        return False
    ok = all(s["d_lit"][h] > 0 and s["d_eval"][h] > 0 and s["d_f10"][h] <= 0 for h in ("H1", "H2"))
    ok = ok and s["d_lit"]["2021-25"] >= 0
    ok = ok and all(s["lit"][h]["tpw"] >= 2.0 for h in ("H1", "H2"))
    return bool(ok)
