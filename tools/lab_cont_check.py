"""CONT track: mechanics check for tools/lab_models/continuation.py (1H aggregation, causality, trade sanity).
Not a performance run - it prints trade-level mechanics for a 2-week window only."""
import datetime as dt
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pandas as pd  # noqa: E402

from tools import strategy_lab as sl  # noqa: E402
from tools.lab_models import continuation as m  # noqa: E402

ET = ZoneInfo("America/New_York")


def ts(x):
    return dt.datetime.fromtimestamp(int(x), ET).strftime("%m-%d %H:%M")


def main(sym="NQ", a="2026-03-02", z="2026-03-13"):
    b = sl.bars(sym, "5m", a, z, warmup_days=10)
    print("bars", len(b), b["day"].iloc[0], b["day"].iloc[-1])
    # 1) 1H aggregation vs the TradingView 1H file
    sim = m._Sim(b, m._params({"variant": "IFVG", "sym": sym}))
    sim.run()
    h1 = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_1h.csv")).drop_duplicates("time").set_index("time")
    mism = chk = 0
    for k in range(len(sim.hH)):
        t0 = int(sim.t[sim.hA[k]])
        t0h = t0 - (t0 % 3600)
        if t0h in h1.index:
            r = h1.loc[t0h]
            chk += 1
            if abs(r["high"] - sim.hH[k]) > 0.01 or abs(r["low"] - sim.hL[k]) > 0.01 or abs(r["close"] - sim.hC[k]) > 0.01:
                mism += 1
                if mism <= 5:
                    print("  1H mismatch", ts(t0h), "tv", r["high"], r["low"], r["close"], "mine", sim.hH[k], sim.hL[k], sim.hC[k])
    print(f"1H bars checked {chk}, mismatches {mism}")
    # 2) trade mechanics per variant
    for v in ("FVG", "IFVG", "IFVG_AMPM"):
        t0 = time.time()
        tr = [t for t in m.run(b, {"variant": v, "sym": sym}) if t["day"] >= a]
        print(f"\n{v}: {len(tr)} trades in the window ({time.time() - t0:.1f}s)")
        for t in tr[:8]:
            print(f"  {t['day']} {ts(t['entry_t'])}->{ts(t['exit_t'])} {t['setup']:6s} e={t['entry']:.2f} s={t['stop']:.2f} "
                  f"tg={t['target']:.2f} x={t['exit']:.2f} {t['exit_kind']:6s} q={t['qty']} riskpts={t['risk_pts']} "
                  f"leg=[{t['leg_lo']},{t['leg_hi']}] eq={t['eq']} rrplan={t['rr_plan']} r={t['r']}")
    # 3) causality: truncate the data right after each entry -> the same entry must appear
    for v, off in (("IFVG", -300), ("FVG", 0)):
        full = m.run(b, {"variant": v, "sym": sym})
        ok = 0
        for t in full[:8]:
            cut = b[b["time"] <= t["entry_t"] + off].reset_index(drop=True)
            tr2 = m.run(cut, {"variant": v, "sym": sym})
            ok += any(x["entry_t"] == t["entry_t"] and abs(x["entry"] - t["entry"]) < 1e-9 for x in tr2)
        print(f"{v}: truncated reruns reproduce {ok} of {min(8, len(full))} entries")
    st = m.state(b, {"variant": "IFVG", "sym": sym})
    print("state:", st["status"], "| trend", st["htf_trend"], "| leg", {k: st["leg"][k] for k in ("dir", "origin", "extreme", "eq")} if st["leg"] else None)


def funnel(sym="NQ", a="2026-01-02", z="2026-06-30", variant="IFVG"):
    """How many killzone days reach each rule step (counts only, no P&L)."""
    b = sl.bars(sym, "5m", a, z, warmup_days=20)
    p = m._params({"variant": variant, "sym": sym, "_debug": True})
    sim = m._Sim(b, p)
    tr = [t for t in sim.run() if t["day"] >= a]
    days = {d: s for d, s in sim.dbg.items() if d >= a}
    n = len(days)
    print(f"{sym} {variant} {a}..{z}: killzone days {n}, trades {len(tr)}")
    for k in ("kz", "leg", "disc", "tap", "inv", "rr_fail"):
        c = sum(1 for s in days.values() if k in s)
        print(f"  {k:8s} {c:4d} days ({100 * c / max(n, 1):.0f}%)")
    for x in sim.dbg_rr[:12]:
        if dt.datetime.fromtimestamp(x["t"], ET).strftime("%Y-%m-%d") < a:
            continue
        print(f"  rr_fail {ts(x['t'])} d={x['d']:+d} leg {x['lo']:.2f}->{x['hi']:.2f} (size {abs(x['hi'] - x['lo']):.0f}) "
              f"pb {x['pb']:.2f} entry {x['entry']:.2f} risk {x['risk']:.1f} reward {x['reward']:.1f} "
              f"retrace {abs(x['hi'] - x['pb']) / abs(x['hi'] - x['lo']):.2f} inverted tops {[round(v, 2) for v in x['inv_tops']]}")
    lens = [abs(t["leg_hi"] - t["leg_lo"]) for t in tr]
    if lens:
        print("  leg size at entry (pts): median", sorted(lens)[len(lens) // 2], "risk pts median", sorted(t["risk_pts"] for t in tr)[len(tr) // 2])


def show(sym="NQ", variant="IFVG_AMPM", nth="0"):
    """Print one trade with the 5m bars around it (from research/lab/CONT_trades)."""
    import json
    tr = json.load(open(os.path.join(ROOT, "research", "lab", "CONT_trades", f"CONT_{sym}_{variant}.json"), encoding="utf-8"))
    t = tr[int(nth)]
    print({k: t[k] for k in ("day", "setup", "entry", "stop", "target", "exit", "exit_kind", "qty", "risk_pts", "pnl", "r",
                             "leg_lo", "leg_hi", "eq", "rr_plan")})
    b = sl.bars(sym, "5m", t["day"], t["day"])
    w = b[(b["time"] >= t["entry_t"] - 3600 * 2) & (b["time"] <= t["exit_t"] + 600)]
    for _, r in w.iterrows():
        mark = " <entry" if r["time"] + 300 == t["entry_t"] or r["time"] == t["entry_t"] else (" <exit" if r["time"] + 300 == t["exit_t"] else "")
        print(f"  {ts(r['time'])} o {r['open']:.2f} h {r['high']:.2f} l {r['low']:.2f} c {r['close']:.2f}{mark}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "funnel":
        funnel(*sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "show":
        show(*sys.argv[2:])
    else:
        main(*(sys.argv[1:] or []))
