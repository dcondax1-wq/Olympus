"""Win rate and new trading windows (owner's order 2026-10-17 night): research/writeups/win-rate-and-sessions.md.

  python tools/research_winrate_sessions.py run [ids...]     # exact live-loop replays (2 processes, cached)
  python tools/research_winrate_sessions.py table [ids...]   # print the scored table
  python tools/research_winrate_sessions.py save             # store every finished variant in research/runs/

Engine options used (all default off, engine/model.py): session_clock, arm_windows, max_trades_window, stop_after_loss,
eth_slip_ticks, feat_min / feat_max; existing: entry_windows, max_trades_day, stop_after_win, partial_*, entry_mode retest,
spec.min_fvg. Every variant runs the exact live-loop replay on top of live_model.json, then live sizing (quarter size in
cold streaks, half size on late entries), costs included. Data: TradingView CME NQ1! 5m (23-hour bars).
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from tools import runlib as rl            # noqa: E402
from tools import export_backtest as ex   # noqa: E402,F401
from tools import five_year as fy         # noqa: E402

_s0 = fy._slim


def _slim_ff(t):
    """Keep every numeric plan feature (ff) so win-rate screens can use what was known at entry."""
    d = _s0(t)
    d["ff"] = {k: v for k, v in (t.get("features") or {}).items() if v is None or isinstance(v, (int, float))}
    d["zone_pts"] = abs(float(t["zone"][1]) - float(t["zone"][0])) if t.get("zone") else None
    return d


fy._slim = _slim_ff

NY = [[570, 690], [810, 930]]
NY_ARM = [480, 955]
WIN = {   # name: (entry window, arm windows when traded alone, needs the session clock, label)
    "lon": ([120, 300], [[0, 300]], False, "London 02:00-05:00"),
    "pre": ([480, 570], None, False, "NY pre-open 08:00-09:30"),
    "lunch": ([690, 810], None, False, "NY lunch 11:30-13:30"),
    "late": ([930, 955], None, False, "Late PM 15:30-15:45 (flat 15:55)"),
    "asia": ([1140, 1320], [[1080, 1320]], True, "Asia 19:00-22:00"),
}

V = {}   # id -> (title, family, question, params)


def _alone(w):
    ew, arm, sc, lab = WIN[w]
    p = {"entry_windows": [ew]}
    if arm:
        p["arm_windows"] = arm
    if sc:
        p["session_clock"] = True
    return p


def _added(w):
    ew, arm, sc, lab = WIN[w]
    p = {"entry_windows": sorted(NY + [ew])}
    if arm:
        p["arm_windows"] = arm + [NY_ARM]
    if sc:
        p["session_clock"] = True
    return p


V["ses_feat_base"] = ("Live strategy (feature-rich replay)", "other", "Baseline with every entry feature kept, for the win-rate screens",
                      {"_ff": 1})
for w, (ew, arm, sc, lab) in WIN.items():
    V[f"ses_{w}_alone"] = (f"{lab} only", "sessions", f"Does the same model work in the {lab} window on its own?", _alone(w))
    V[f"ses_{w}_add1"] = (f"NY + {lab}, 1 trade a day", "sessions", f"Add {lab} to today's windows, first setup of the day wins",
                          {**_added(w), "max_trades_day": 1})
    V[f"ses_{w}_add2"] = (f"NY + {lab}, 1 per window, 2nd only after a non-win", "sessions",
                          f"Add {lab}: up to 2 trades a day, 1 per window, stop after a win (engine default)",
                          {**_added(w), "max_trades_day": 2, "max_trades_window": 1})
    V[f"ses_{w}_add2any"] = (f"NY + {lab}, 1 per window, any outcome", "sessions",
                             f"Add {lab}: up to 2 trades a day, 1 per window, whatever the first one did",
                             {**_added(w), "max_trades_day": 2, "max_trades_window": 1, "stop_after_win": False})
for w in ("lon", "asia", "pre"):
    V[f"ses_{w}_alone_slip"] = (f"{WIN[w][3]} only, +1 tick slippage outside RTH", "sessions",
                                "Thin overnight book: one extra tick on every overnight fill and stop/time exit",
                                {**_alone(w), "eth_slip_ticks": 1})
V["ses_ny_max2"] = ("NY windows, 2 trades a day (2nd after a non-win)", "sessions", "Second trade after a loss or scratch, any window",
                    {"max_trades_day": 2})
V["ses_ny_max2_afterwin"] = ("NY windows, 2nd trade only after a win", "sessions", "Second trade only when the first one won",
                             {"max_trades_day": 2, "stop_after_win": False, "stop_after_loss": True})
V["ses_ny_max2_win1"] = ("NY windows, 1 trade per window (AM + PM)", "sessions", "One AM and one PM trade, whatever the first did",
                         {"max_trades_day": 2, "max_trades_window": 1, "stop_after_win": False})

# ---- win rate (trade construction); partials only with a new angle (pool-based), retest only new variants
V["wr_partial_pool50"] = ("Half off at the first pool on the way", "winrate", "Bank 50% at the first opposing pool >= 0.75R, stop to BE",
                          {"partial_pct": 0.5, "partial_at": "pool"})
V["wr_partial_pool50_keep"] = ("Half off at the first pool, stop stays", "winrate", "Bank 50% at the first pool, keep the stop (BE at 1R as today)",
                               {"partial_pct": 0.5, "partial_at": "pool", "be_after_partial": False})
V["wr_partial_1r50"] = ("Half off at 1R (reference)", "winrate", "The old rejected partial, on today's rules, for the table",
                        {"partial_pct": 0.5, "partial_r": 1.0})
V["wr_retest_ce"] = ("Limit entry at the middle of the gap", "winrate", "Limit at the IFVG 50% (CISD level for CISD), 6 bars",
                     {"entry_mode": "retest", "retest_level": "ce"})
V["wr_retest12"] = ("Limit entry at the gap edge, 12 bars", "winrate", "Give the retest limit an hour instead of 30 minutes",
                    {"entry_mode": "retest", "retest_bars": 12})
V["wr_fvg6"] = ("Gaps of 6+ points only (else CISD)", "winrate", "Bigger fair value gaps as triggers (min 6 pts instead of 3)",
                {"spec": {"min_fvg": 6.0}})
V["wr_fvg10"] = ("Gaps of 10+ points only (else CISD)", "winrate", "Much bigger gaps (min 10 pts): most triggers become CISD",
                 {"spec": {"min_fvg": 10.0}})

V["wr_depth_max27"] = ("Skip very deep sweeps (> 2.7 ATR)", "winrate", "Sweeps that ran more than 2.7 x ATR past the pool win least: pass on them",
                       {"feat_max": {"depth_atr": 2.67}})
V["wr_depth_max35"] = ("Skip very deep sweeps (> 3.5 ATR)", "winrate", "Looser depth limit", {"feat_max": {"depth_atr": 3.5}})
V["wr_depth_band"] = ("Sweep depth 0.5-3 ATR only", "winrate", "Neither a tiny poke nor a run-away move",
                      {"feat_min": {"depth_atr": 0.5}, "feat_max": {"depth_atr": 3.0}})
V["wr_htf4h"] = ("Only with the 4H order flow", "winrate", "Trade only when the 4H FVG order flow points the trade's way",
                 {"feat_min": {"b_4H": 1}})
V["wr_htf1h"] = ("Only with the 1H order flow", "winrate", "Trade only when the 1H FVG order flow points the trade's way",
                 {"feat_min": {"b_1H": 1}})
V["wr_htf_trend"] = ("Only with the 1H structure", "winrate", "Trade only when 1H swing structure points the trade's way",
                     {"feat_min": {"htf_trend": 1}})


def run(ids):
    for k in ids:
        t, fam, q, prm = V[k]
        raw = rl.replay(prm, procs=2, label=k, quiet=True)
        T = rl.size(raw)
        S = rl.score(T, raw)
        print(k, "|", rl.line(S, "2026"), "||", rl.line(S, "2021-25"), flush=True)


def row(s, name):
    if not s.get("n"):
        return f"{name}: no trades"
    return (f"{name}: n={s['n']} tpw={s['tpw']} wk2={s['wk2']}% win={s['win']}% PF={s['pf']} net={s['net']:+,} (${s['per_month']:,}/mo) "
            f"DD={s['dd']:,} 1mo {s['p20']}/{s['f20']} passrate={pass_rate(s)}% 2wk {s['p10']}/{s['f10']} b2b {s['b2b']}")


def by_window(T):
    """Trades / win % / net $ by entry hour block (ET) of the sized trades, per period."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    out = {}
    for t in T:
        e = dt.datetime.fromtimestamp(int(t["entry_t"]), ZoneInfo("America/New_York"))
        m = e.hour * 60 + e.minute
        w = next((n for n, (ew, *_r) in WIN.items() if ew[0] <= m < ew[1] + 5), "ny")
        if 570 <= m < 695 or 810 <= m < 935:
            w = "ny"
        per = "2026" if t["day"] >= "2026" else "21-25"
        o = out.setdefault(f"{w} {per}", [0, 0, 0.0])
        o[0] += 1; o[1] += t["r"] > 0.1; o[2] += t["pnl"]
    return {k: f"n={v[0]} win={round(100 * v[1] / v[0])}% net={v[2]:+.0f}" for k, v in sorted(out.items())}


VERDICTS = {}   # id -> (status, verdict), filled in after the runs
RULES = {}      # id -> size rule for runs that re-size the baseline


def pass_rate(s):
    p, f = s.get("p20") or 0, s.get("f20") or 0
    return round(100 * p / (p + f), 1) if p + f else None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "table"
    ids = sys.argv[2:] or list(V)
    if cmd == "run":
        run(ids)
    elif cmd == "table":
        for k in ids:
            raw = rl.replay(V[k][3], procs=2, quiet=True)
            T = rl.size(raw); S = rl.score(T, raw)
            print(k, *[row(S["spans"][sp], sp) for sp in ("2026", "2021-25")], sep="\n   ")
            if k.startswith("ses_") and "_add" in k:
                print("   by window:", by_window(T))
    elif cmd == "save":
        for k, (st, verdict) in VERDICTS.items():
            t, fam, q, prm = V[k]
            raw = rl.replay(prm, procs=2, quiet=True)
            T = rl.size(raw, rule=RULES.get(k)); S = rl.score(T, raw)
            rl.save(k, t, fam, q, params=prm, trades=T, scored=S, status=st, verdict=verdict,
                    writeup="win-rate-and-sessions", tags=["winrate-sessions-2026-10-17"])
            print("saved", k, st)
    elif cmd == "list":
        print("\n".join(V))
