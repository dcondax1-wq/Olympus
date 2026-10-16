"""CLI: python bt.py NQ 5m [json-params]"""
import json
import sys
import time

from engine import backtest

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
tf = sys.argv[2] if len(sys.argv) > 2 else "5m"
params = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
t0 = time.time()
r = backtest.run(sym, tf, params)
s = r["stats"]
print(f"{sym} {tf} {r['range'][0]} -> {r['range'][1]}  ({time.time() - t0:.1f}s)")
for k in ["trades", "trades_per_week", "win_rate", "profit_factor", "net", "expectancy", "avg_r", "total_r", "max_dd",
          "sharpe", "best_day", "worst_day", "best_day_pct", "longs", "shorts", "long_net", "short_net", "avg_mfe", "avg_mae",
          "exit_reasons", "commissions"]:
    print(f"  {k:16s} {s[k]}")
print("  eval:", r["eval"]["result"], r["eval"]["days"], "days | rolling pass-rate:", r["rolling"]["pass_rate"],
      f"({r['rolling']['pass']}/{r['rolling']['completed']}) avg days {r['rolling']['avg_days_to_pass']}")
if "-v" in sys.argv:
    for t in r["trades"]:
        print(f"   {t['day']} {'L' if t['dir'] == 1 else 'S'} {t['trigger']:4s} sc{t['score']} {t['qty_label']:10s} "
              f"e{t['entry']:.2f} sl{t['stop']:.2f} tp{t['target']:.2f}({t['target_label']}) "
              f"{t['exit_reason']:8s} {t['pnl_r']:+.2f}R ${t['pnl']:+.0f}  {','.join(t['pools'])} | {','.join(t['conf_tags'])}")
for k in ("trigger", "score", "conf", "pool", "hour", "dir", "target"):
    print(" ", k, [(x["key"], x["n"], x["wr"], round(x["pnl"])) for x in r["breakdowns"][k]])
