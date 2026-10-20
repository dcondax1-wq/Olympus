"""The trade sample for the live eval Monte Carlo (engine/eval_mc.py, morning brief): every 2026 session of the live LIT
replay (tools/lit_final.run on live_model.json "lit" = run lit_live) with its trade per 1 micro.

    python -X utf8 tools/lit_eval_sample.py      -> research/lab/eval_sample.json (~20 KB, committed: the cloud has no cache)
Rerun after a change of the live "lit" params (the golden-numbers test pins the replay). Read-only research.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "eval_sample.json")
PV = 2.0


def to_sample(T):
    """{sess, trades} for engine/eval_mc from lit_final.run trades (2026 sessions)."""
    from tools import lit_final as F
    T = [t for t in T if t["day"] >= "2026-01-01"]
    sess = [d for d in F.SESS if d >= "2026-01-01"]
    out = []
    for t in T:
        q = int(t["qty"]) or 1
        risk = float(t["risk_pts"])
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "risk": round(risk, 2),
                    "tgt": round(abs(float(t["target_px"]) - float(t["entry_px"])), 2),
                    "pts": round(float(t["pnl"]) / (q * PV), 4),                 # net of the replay's costs, per micro
                    "w1": round(-float(t["mae"]) * risk, 4), "exit": t["exit"],
                    # the model's micros and multiplier as the live loop hands them to sizing.lit_qty (weekly stop, idm_size)
                    "q": int(t["qty"]), "sm": round(float(t.get("size_mult", t.get("mult", 1.0)) or 1.0), 6),
                    **{k: t[k] for k in ("idm_m", "idm_cap", "wk_m") if t.get(k) is not None}})
    return {"sess": sess, "trades": out}


def build():
    from engine import lit
    from tools import lit_final as F
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **lm["lit"]}
    S = to_sample(F.run(P))
    sess, out = S["sess"], S["trades"]
    return {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "tools/lit_eval_sample.py: tools/lit_final.run on "
            "live_model.json lit (run lit_live), 2026 sessions; pts = replay P&L per micro after costs, w1 = -MAE x stop",
            "sess": sess, "trades": out}


if __name__ == "__main__":
    d = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(d, fh, separators=(",", ":"))
    print(f"{len(d['sess'])} sessions, {len(d['trades'])} trades, net/1 micro {sum(t['pts'] for t in d['trades']) * PV:+,.0f} -> "
          f"{os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT) // 1024} KB)")
