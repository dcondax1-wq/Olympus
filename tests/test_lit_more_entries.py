"""More LIT entries (research/writeups/lit-more-entries.md): the default-off engine options "second" / "sess_m" and the
all-hours candidates through the live loop (engine/lit_live.py = what the PC bot and the cloud monitor run) must give the
backtest's trades (engine/lit.py run_x on the whole history, tools/lit_more_entries.py run) on every 2026 session.

    python -X utf8 -m tests.test_lit_more_entries            # day-end replay of both variants + the LiveBot on 2-trade days
    python -X utf8 -m tests.test_lit_more_entries --days     # day-end replay only

Variants (the two closest candidates of the study, switch JSON in the write-up):
  asia_slot   18:00-15:30, 1 Asia trade (18:00-02:00, its own bank at 3R) + 1 trade 02:00-15:30 (per_session), all_hours
  lonny_c120  02:00-15:30, 1 London trade (02:00-08:00) + 1 NY trade (08:00-15:30) that starts >= 120 min after the first exit
Option off (live_model.json as it is) = today: python -X utf8 -m tests.test_lit_live --days (120/120).
The LiveBot part runs engine/live.py (PaperAdapter, guards on, "guards": {"max_per_day": 2}) on sessions with 2 trades: both
entries are routed once, in order, one position at a time, and both exits are routed once (asia_slot: reported only, the
PC calendar guard refuses 18:00-24:00 entries today). One process.
"""
from __future__ import annotations

import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import lit_live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402
from tests import test_lit_live as TL  # noqa: E402
from tools import lit_more_entries as X  # noqa: E402

VARIANTS = {"asia_slot": "asiaslotn_rr3_x1.0", "lonny_c120": "lonny_c120_x1.0"}
ROUTE_READY = {"lonny_c120"}      # asia_slot: the LiveBot part is reported only (guards block evening entries today)


def day_end(P, REF, sess, df5, b1):
    T5 = df5["time"].values
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    same = ex_same = 0
    miss, extra, wrong = [], [], []
    for d in sess:
        now = TL.day_close(d)
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        res = lit_live.run(cut5, P, one_min=cut1, now=now, early=True)
        gk = {TL.key(t): t for t in res["trades"] if t["day"] == d}
        for w in by_day.get(d, []):
            g = gk.pop(TL.ref_key(w), None)
            if g is None:
                miss.append((d, int(w["entry_t"])))
                continue
            same += 1
            if (g["exit_reason"], g["exit_t"], round(g["pnl"], 2)) == TL.ref_exit(w):
                ex_same += 1
            else:
                wrong.append((d, g["exit_reason"], TL.ref_exit(w)))
        extra += [(d, k[0]) for k in gk]
    return {"want": len(REF), "entries": same, "identical": ex_same, "missing": miss[:10], "extra": extra[:10], "exit_differs": wrong[:10],
            "ok": same == ex_same == len(REF) and not extra}


def main():
    sess = [d for d in X.F.SESS if d >= "2026-01-01"]
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= TL.day_close(sess[0]) - 120 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    V = X.variants()
    ok = True
    for lab, vn in VARIANTS.items():
        P = {k: v for k, v in V[vn].items()}
        REF = [t for t in X.run(P) if t["day"] >= "2026-01-01"]
        r = day_end(P, REF, sess, df5, b1)
        n2 = sum(1 for c in collections.Counter(t["day"] for t in REF).values() if c >= 2)
        print(f"{lab}: day-end replay {r['identical']}/{r['want']} trades identical (entries {r['entries']}, missing {len(r['missing'])}, "
              f"extra {len(r['extra'])}); {n2} days with 2 trades", flush=True)
        if not r["ok"]:
            print("  ", r)
        ok &= r["ok"]
        if "--days" in sys.argv:
            continue
        by_day = collections.defaultdict(list)
        for t in REF:
            by_day[t["day"]].append(t)
        two = [d for d, v in sorted(by_day.items()) if len(v) >= 2 and d >= "2026-08-17"][:2]
        if not two:
            continue
        b = TL.bot_replay(P, by_day, tuple(two), lm_extra={"guards": {"max_per_day": 2}})
        print(f"  LiveBot (paper, guards max 2 a day) on {two}: entries {b['entries_ok']}/{b['want']} exits {b['exits_ok']}/{b['want']}, "
              f"extra {b['extra']}, not routed {b['not_routed']}, errors {b['errors']}", flush=True)
        if lab in ROUTE_READY:
            ok &= bool(b["ok"])
        else:
            print("   (known gap, not failed: the PC guards refuse 18:00-24:00 entries; see lit-more-entries.md 'PC route')")
    print("OK" if ok else "DIFFERENCES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
