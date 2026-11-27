"""Every LIT setup since 2021 with its features (known at the 5m CISD bar) and outcome (taken R, or what it WOULD have made with
every gate open), from tools/lit_setups_learn.funnel (the real engine). PAPER RESEARCH ONLY.
    python -X utf8 research/setupscore/rows.py    -> research/setupscore/rows.json.gz
"""
import gzip, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "setupscore", "rows.json.gz")


def build():
    import logging
    logging.disable(logging.WARNING)
    from tools import lit_setups_learn as LS
    E = LS.Engine()
    T_live = E.run()
    T_open = E.run(LS.OPEN_ALL)
    rows = LS.funnel(E, T_live, T_open)
    return rows, T_live, T_open


if __name__ == "__main__":
    t0 = time.time()
    rows, TL, TO = build()
    print(len(rows), "rows", time.time() - t0, "s")
    print(rows[0])
    keep = []
    for r in rows:
        keep.append({k: r.get(k) for k in r if k not in ("swept",)})
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(keep, fh, default=float)
