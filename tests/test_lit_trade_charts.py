"""LIT trade charts: the chart records and the PNGs carry the exact trade prices.

  python -X utf8 -m tests.test_lit_trade_charts          # 10 trades (biggest win / loss, every exit kind, both sides)

Reads research/lab/replays.json "charts" (tools/export_replays.py) and research/lab/backtest_live.json (tools/export_backtest.py),
two independent exports of the same engine run, then
  1. every 2026 LIT replay trade has a chart record, with the same entry, stop, target, exit price, sweep extreme, CISD level,
     micros and $ as the backtest row;
  2. the record's bars contain the fill bar (entry time) and the exit bar, and the entry / exit prices lie inside those bars;
  3. 10 PNGs are rendered (tools/lit_trade_charts.py) and every price label drawn on them (axis tags, title, levels) is the
     backtest's price rounded to the 0.25 tick.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    from tools import lit_trade_charts as L
    from tools.lit_chart_data import trade_id, unpack
    rp = json.load(open(os.path.join(ROOT, "research", "lab", "replays.json"), encoding="utf-8"))
    bt = [t for t in json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))["trades"]
          if t["day"] >= "2026-01-01"]
    R = rp.get("charts") or {}
    fails = []
    ok = lambda c, m: c or fails.append(m)
    for t in bt:
        k = trade_id(t["day"], t["entry_t"], t["side"])
        r = R.get(k)
        if not ok(r is not None, f"{k}: no chart record"):
            continue
        for a, b, nm in ((t["entry"], r["entry"]["px"], "entry"), (t["stop"], r["stop"], "stop"), (t["target"], r["target"], "target"),
                         (t["exit_price"], r["exit"]["px"], "exit"), (t["sweep_ext"], r["sweep"]["ext_px"], "sweep"),
                         (t["cisd_level"], r["cisd5"]["px"], "cisd"), (t["qty"], r["qty"], "qty"), (t["pnl"], r["pnl"], "pnl")):
            ok(abs(a - b) < 1e-6, f"{k}: {nm} {a} != {b}")
        ok(t["exit_t"] == r["exit"]["t_end"], f"{k}: exit time")
        bars = unpack(r["b1"]) if r["tf"] == 1 else unpack(r["b5"])
        fill = [b for b in bars if b[0] == t["entry_t"]]
        ok(bool(fill), f"{k}: fill bar missing")
        if fill:
            ok(fill[0][3] - 0.25 <= t["entry"] <= fill[0][2] + 0.25, f"{k}: entry {t['entry']} outside its fill bar {fill[0]}")
        b5 = unpack(r["b5"])
        ok(b5[0][0] <= r["sweep"]["t"] - 7200 + 300 and b5[-1][0] >= min(t["exit_t"], b5[-1][0]), f"{k}: 5m window")
        ex = [b for b in b5 if b[0] <= r["exit"]["t"] < b[0] + 300]
        ok(bool(ex) and ex[0][3] - 0.25 <= t["exit_price"] <= ex[0][2] + 0.25, f"{k}: exit {t['exit_price']} outside its 5m bar")
    print(f"records: {len(bt)} trades checked, {len(fails)} problems")
    # 10 PNGs: the biggest win and loss, two of each exit kind, both sides
    rows = sorted(bt, key=lambda t: t["pnl"])
    pick = [rows[0], rows[-1]]
    for kind in ("TARGET", "STOP", "BE", "TIME"):
        pick += [t for t in bt if t["exit"] == kind and t not in pick][:2]
    pick = pick[:10]
    fmt = lambda p: f"{round(p * 4) / 4:,.2f}"
    with tempfile.TemporaryDirectory() as td:
        for t in pick:
            k = trade_id(t["day"], t["entry_t"], t["side"])
            texts = []
            orig = L.plt.Figure.savefig

            def grab(fig, *a, **kw):
                for ax in fig.axes:
                    texts.extend(x.get_text() for x in ax.texts)
                texts.extend(x.get_text() for x in fig.texts)
                return orig(fig, *a, **kw)
            L.plt.Figure.savefig = grab
            try:
                L.render(R[k], os.path.join(td, k + ".png"), dpi=80)
            finally:
                L.plt.Figure.savefig = orig
            blob = "\n".join(texts)
            need = {"entry": fmt(t["entry"]), "stop": fmt(t["stop"]), "target": fmt(t["target"]), "sweep": fmt(t["sweep_ext"]),
                    "cisd": fmt(t["cisd_level"]), "pnl": f"${abs(t['pnl']):,.0f}", "qty": f"{t['qty']} MNQ"}
            miss = [f"{n} {v}" for n, v in need.items() if v not in blob]
            ok(not miss, f"{k}: PNG lacks {miss}")
            ok(os.path.getsize(os.path.join(td, k + ".png")) > 20000, f"{k}: PNG too small")
            print(f"  {k:24s} {t['exit']:6s} entry {need['entry']} stop {need['stop']} target {need['target']} "
                  f"sweep {need['sweep']} CISD {need['cisd']} {t['pnl']:+,.0f}$ -> {'ok' if not miss else 'MISSING ' + ', '.join(miss)}")
    print(f"{'PASS' if not fails else 'FAIL'}: {len(fails)} problems" + ("".join("\n  " + f for f in fails[:20])))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
