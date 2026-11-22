"""Lucid lane dry run (day-nqdash3 2026-11-22, the second firm): the full fleet rehearsal (tools/fleet_dryrun.py -> tools/rehearse_day.py,
the real LiveBot, PAPER, one simulated NinjaTrader) run twice on the same days, without and with a LucidPro 50K lane, and every
EXISTING lane's trades compared row by row (account, time, side, size, exit, $). Proof that adding Lucid changes nothing for
Zlarior, the 25K #2, ATLAS and the Rapid lanes, and that the Lucid lane itself trades LIT's entries, same side, inside its limits.

    python -X utf8 tools/lucid_dryrun.py --days 2026-10-06,2026-10-13 --quick --out research/handoff/2026-11-22/lucid/dryrun.json

Temp files only, never the owner's NinjaTrader folder; armed only inside the fake. Never a real order.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUCID = "LucidPro 50K (lucid)"


def run(days, quick, lucid, tmp) -> dict:
    out = os.path.join(tmp, f"fd_{'lucid' if lucid else 'base'}.json")
    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "fleet_dryrun.py"), "--root", ROOT, "--days", days, "--rapid",
           "--out", out] + (["--quick"] if quick else []) + (["--lucid"] if lucid else [])
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
    try:
        res = json.load(open(out, encoding="utf-8"))
    except Exception:
        res = {"rc": p.returncode, "result": {}, "stderr": p.stderr[-2000:]}
    res["stdout_tail"] = p.stdout[-1500:]
    return res


def lanes_rows(res) -> dict:
    key = next((k for k in (res.get("result") or {}) if k.startswith("with_rapid")), None)
    days = ((res.get("result") or {}).get(key) or {}).get("days") or []
    out = {}
    for d in days:
        for r in d.get("trades") or []:
            out.setdefault(r["acct"], []).append((d["day"], r["t"], r["side"], r.get("qty"), r.get("reason"), r.get("pnl"), r.get("ok")))
    return out, ((res.get("result") or {}).get(key) or {})


def compare(base, luc) -> dict:
    B, bsum = lanes_rows(base)
    L, lsum = lanes_rows(luc)
    same = {k: B[k] == L.get(k) for k in B}
    diffs = {k: {"base": B[k][:6], "with_lucid": (L.get(k) or [])[:6]} for k, v in same.items() if not v}
    lit = [(d, t, s) for (d, t, s, *_r) in L.get("Zlarior 50K (main)", []) if s in ("buy", "sell")]
    lu = [(d, t, s) for (d, t, s, *_r) in L.get(LUCID, []) if s in ("buy", "sell")]
    return {"existing_lanes": sorted(B), "unchanged": all(same.values()) and set(B) <= set(L), "diffs": diffs,
            "lucid_rows": L.get(LUCID, []), "lucid_entries": len(lu),
            "lucid_same_side_as_lit": all(any(x[0] == y[0] and x[2] == y[2] for y in lit) for x in lu),
            "checks": {"base": [bsum.get("passed"), bsum.get("checks")], "with_lucid": [lsum.get("passed"), lsum.get("checks")]},
            "failed_with_lucid": [c.get("name") for c in (lsum.get("failed") or [])][:20],
            "failed_base": [c.get("name") for c in (bsum.get("failed") or [])][:20]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", required=True)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    tmp = tempfile.mkdtemp(prefix="le_lucid_dry_")
    base = run(a.days, a.quick, False, tmp)
    luc = run(a.days, a.quick, True, tmp)
    rep = {"days": a.days, "quick": a.quick, **compare(base, luc)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=str)
    print(json.dumps({k: rep[k] for k in ("existing_lanes", "unchanged", "lucid_entries", "lucid_same_side_as_lit", "checks",
                                          "failed_with_lucid", "failed_base")}, indent=1, default=str))
    return 0 if rep["unchanged"] and rep["lucid_same_side_as_lit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
