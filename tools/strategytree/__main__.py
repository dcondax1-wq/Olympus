"""DAPHNE command line.

  python -X utf8 -m tools.strategytree                 # all 80 roots + 1 placebo -> research/strategytree/tree.json,
                                                       # the page's copy, and runs strategytree_top1 / _top5
  python -X utf8 -m tools.strategytree --quick         # 8 roots, small budget, no runs saved (a smoke test)
  python -X utf8 -m tools.strategytree --placebos 3 --expand 300
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from tools.strategytree import report, roots as rx, search as sx, sessions


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="8 roots, 40 expansions, nothing written outside --out")
    ap.add_argument("--placebos", type=int, default=1, help="placebo searches on shuffled conditions")
    ap.add_argument("--expand", type=int, default=sx.SearchConfig.max_expand, help="node expansions per root")
    ap.add_argument("--min-n", type=int, default=sx.SearchConfig.min_n, help="train trades a rule needs")
    ap.add_argument("--procs", type=int, default=min(4, os.cpu_count() or 1), help="parallel searches")
    ap.add_argument("--out", default=report.OUT_DIR, help="folder for tree.json")
    ap.add_argument("--no-runs", action="store_true", help="do not store run-library runs")
    a = ap.parse_args(argv)
    t0 = time.time()
    m = sessions.load_market()
    roots = rx.all_roots()
    cfg = sx.SearchConfig(min_n=a.min_n, max_expand=a.expand)
    if a.quick:
        roots = [r for r in roots if r.level in ("ORH", "ORL")][:8]
        cfg = sx.SearchConfig(min_n=a.min_n, max_expand=40)
    print(f"{len(m.days)} days {m.days['date'].iloc[0]} .. {m.days['date'].iloc[-1]}, {len(roots)} roots", flush=True)
    doc = report.build(m, cfg, roots, placebos=0 if a.quick else a.placebos, procs=a.procs)
    page = None if (a.quick or os.path.abspath(a.out) != os.path.abspath(report.OUT_DIR)) else report.PAGE_JSON
    path = report.write(doc, a.out, page)
    meta, real = doc["meta"], doc["honesty"]["real"]
    print(f"nodes {meta['nodes']:,}  cut {meta['cut_pct']}%  shown {meta['shown']:,}  "
          f"best rules holding out of sample {real['hold']}/{real['best_rules']}", flush=True)
    for p in doc["honesty"]["placebo"]:
        print(f"placebo: {p['hold']}/{p['best_rules']} hold ({p['hold_pct']}%)")
    for i, r in enumerate(doc["top"][:5], 1):
        tr, te, y = r["train"], r["test"], r["y2026"]
        print(f"#{i} {r['key']} {' > '.join(r['steps'])}\n    train ${tr['mean']}/tr n={tr['n']} | test ${te.get('mean')}/tr "
              f"n={te['n']} | 2026 ${y.get('mean')}/tr n={y['n']} | holds={r['holds']}")
    if not (a.quick or a.no_runs):
        print("runs:", ", ".join(report.save_runs(doc, m)))
    print(f"{path} ({os.path.getsize(path) / 1e6:.2f} MB) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
