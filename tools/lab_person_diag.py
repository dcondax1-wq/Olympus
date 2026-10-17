"""PERSON track diagnostics on a plain backtest: skip reasons, target tiers, exit mix, R reached (dev period by default).

  python tools/lab_person_diag.py <variant[,variant]> [days_from days_to]
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")
from engine.backtest import run  # noqa: E402
from tools.lab_person_run import BASE, VARIANTS  # noqa: E402

names = sys.argv[1].split(",")
a, z = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("2026-01-02", "2026-06-30")
for k in names:
    p = {**BASE, **VARIANTS[k], "days_from": a, "days_to": z}
    r = run("NQ", "5m", p, light=False)
    tr = r["trades"]
    sk = collections.Counter()
    for e in r["events"]:
        if e["type"] in ("skip",):
            txt = re.sub(r"[-+]?\d[\d,.]*", "#", e["text"])
            txt = re.sub(r"\[.*?\]", "[..]", txt)[:80]
            sk[txt] += 1
    ex = collections.Counter(t.get("exit_reason", "?") for t in tr)
    tiers = collections.Counter((t.get("draw") or {}).get("tier", "-") for t in tr)
    lab = collections.Counter("cap" if "cap" in str(t.get("target_label")) else ("2R" if str(t.get("target_label", "")).startswith("2") else "pool") for t in tr)
    tp1 = [t for t in tr if t.get("partial_draw")]
    hit1 = sum(1 for t in tp1 if any(str(x["reason"]).startswith("TP1") for x in t["exits"]))
    pn = [t["pnl"] for t in tr]
    print(f"\n== {k} [{a}..{z}] n={len(tr)} net={sum(pn):+.0f} wr={100 * sum(x > 0 for x in pn) / max(1, len(pn)):.0f}% "
          f"avgR={sum(t['pnl_r'] for t in tr) / max(1, len(tr)):+.3f}")
    print("  exits:", dict(ex.most_common()))
    print("  target kind:", dict(lab), "tiers:", dict(tiers), f"tp1 planned={len(tp1)} filled={hit1}")
    rr = sorted(t["rr"] for t in tr)
    mfe = sorted(round(t["mfe"], 1) for t in tr)
    if rr:
        print(f"  planned R: med {rr[len(rr) // 2]} p25 {rr[len(rr) // 4]} p75 {rr[3 * len(rr) // 4]} | MFE med {mfe[len(mfe) // 2]} "
              f"| risk pts med {sorted(t['risk_pts'] for t in tr)[len(tr) // 2]:.1f}")
    for txt, n in sk.most_common(12):
        print(f"  skip {n:4d}  {txt}")
