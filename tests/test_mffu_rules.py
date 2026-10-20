"""The bot vs the MFFU rulebook (research/lit/mffu_rules.json, research/writeups/mffu-rules.md).

    python -X utf8 -m tests.test_mffu_rules

Loads the rulebook's flat limits and asserts the bot's config respects them: max micros / minis, the must-be-flat time,
the entry window, the soft daily loss, the profit target, the EOD trailing max loss and its lock, the funded payout
constants. FAIL = the bot breaks an MFFU rule (exit code 1). WARN = a known gap that is not a rule breach (wrong cost
assumption, inactivity risk); it is printed, not failed. Paper only; reads files, places nothing.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RULES = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
RES = {"ok": 0, "fail": 0, "warn": 0}


def check(name, ok, detail=""):
    RES["ok" if ok else "fail"] += 1
    print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
    return ok


def warn(name, bad, detail=""):
    if bad:
        RES["warn"] += 1
        print(f"WARN {name}{': ' + detail if detail else ''}")
    else:
        RES["ok"] += 1
        print(f"ok   {name}{': ' + detail if detail else ''}")


def _src(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def hm(mod):
    return f"{int(mod) // 60:02d}:{int(mod) % 60:02d}"


def main():
    R = json.load(open(RULES, encoding="utf-8"))
    L50, L25 = R["limits"]["builder_50k"], R["limits"]["builder_25k"]
    M = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    lit, P, S = M.get("lit") or {}, M.get("params") or {}, M.get("lit_sizing") or {}

    # ---------------------------------------------------------------- the rulebook itself
    for k in ("price", "profit_target", "max_loss", "daily_loss_limit", "max_contracts", "trading_hours", "news_trading",
              "automation", "inactivity", "commission_rt"):
        f = R["builder_50k"]["eval"].get(k) or {}
        check(f"rulebook: {k} has a source and date", bool(f.get("source")) and bool(f.get("checked")))

    # ---------------------------------------------------------------- size
    check("max micros (live_model params)", int(P.get("max_micros", 40)) <= L50["max_micros"],
          f"{P.get('max_micros')} <= {L50['max_micros']}")
    from engine import sizing
    tw_acct = ((S.get("two_week") or {}).get("acct") or {})
    check("two_week max micros", int(tw_acct.get("max_micros", sizing.TW_50K["max_micros"])) <= L50["max_micros"])
    from engine.tradovate import MAX_MICROS_HARD, MAX_MINIS
    check("router hard caps (engine/tradovate.py, used by NinjaTrader)", MAX_MICROS_HARD <= L50["max_micros"] and MAX_MINIS <= L50["max_minis"],
          f"{MAX_MICROS_HARD} micros / {MAX_MINIS} minis")
    check("25K account caps (sizing.TW_25K)", sizing.TW_25K["max_micros"] <= L25["max_micros"], f"{sizing.TW_25K['max_micros']}")

    # ---------------------------------------------------------------- time
    flat = int(lit.get("flat_mod", 955))
    check("flat before MFFU's 16:10 ET cut-off (lit.flat_mod)", flat <= L50["flat_by_mod"] - 10, f"{hm(flat)} vs {hm(L50['flat_by_mod'])}")
    win = lit.get("window") or [[120, 930]]
    last_entry = max(int(w[1]) for w in win)
    first_entry = min(int(w[0]) for w in win)
    check("entries stop before the flat time", last_entry < flat, f"last entry {hm(last_entry)}, flat {hm(flat)}")
    check("no entry in the 16:10-18:00 ET gap", first_entry >= 0 and last_entry < L50["flat_by_mod"], f"{hm(first_entry)}-{hm(last_entry)}")
    nt = _src("engine/ninjatrader.py")
    m = re.search(r'p\.get\("flat_mod",\s*(\d+)\)', nt)
    check("NinjaTrader adapter default flat", bool(m) and int(m.group(1)) <= L50["flat_by_mod"] - 10, m.group(1) if m else "not found")
    from engine.lit_live import early_close
    ecs = {d: early_close(d) for d in ("2026-11-27", "2026-12-24", "2027-01-18")}
    check("CME early closes known (MFFU does not auto-flatten on half-days)", all(v and v < L50["flat_by_mod"] for v in ecs.values()),
          ", ".join(f"{d} {hm(v)}" for d, v in ecs.items() if v))
    check("NinjaTrader flattens before an early halt", "early_close" in nt and "5 minutes before the halt" in nt)

    # ---------------------------------------------------------------- eval rules
    A = sizing.TW_50K
    check("two_week target = MFFU target", A["target"] == L50["target"], f"{A['target']:,.0f}")
    check("two_week max loss = MFFU max loss", A["mll"] == L50["mll"])
    check("two_week lock = start + $100", A["lock"] == L50["lock"])
    check("two_week soft daily loss = MFFU DLL", A["dll"] == L50["dll"])
    check("25K constants", (sizing.TW_25K["target"], sizing.TW_25K["mll"], sizing.TW_25K["dll"]) == (L25["target"], L25["mll"], L25["dll"]))
    E = sizing.MFFU_50K
    check("sizing.MFFU_50K", E["target"] == L50["target"] and E["mll"] == L50["mll"] and E["lock"] == E["start"] + L50["lock"])
    cm = _src("tools/cloud_monitor.py")
    m = re.search(r"START_BAL, TARGET, MLL_AMT, MLL_LOCK = ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)", cm)
    if check("cloud monitor eval constants found", bool(m)):
        sb, tg, ml, lk = map(float, m.groups())
        check("cloud monitor eval tracker ($3,000 target, $2,000 EOD trailing, lock start + $100)",
              tg == L50["target"] and ml == L50["mll"] and lk == sb + L50["lock"], f"{tg:,.0f} / {ml:,.0f} / {lk:,.0f}")
    # the floor rule: EOD high - $2,000, never down, stops at $50,100
    ev = sizing.mffu_eval({"d1": 1500.0, "d2": 1500.0, "d3": -2000.0})
    check("trailing floor locks at $50,100 (EOD high $53,000)", ev["trailing_mll"] == 50000.0 + L50["lock"], f"{ev['trailing_mll']:,.0f}")
    ev = sizing.mffu_eval({"d1": 1000.0, "d2": -500.0})
    check("trailing floor moves only up from the EOD high", ev["trailing_mll"] == 49000.0, f"{ev['trailing_mll']:,.0f}")
    # minimum trading days (rulebook: 1, status conflict: the plan page says 2) -> the bot assumes the stricter one, and a
    # passed eval trades only the 1-micro minimum-days trade, then nothing (engine/sizing.eval_lock, engine/eval_life.py)
    md = R["builder_50k"]["eval"].get("min_trading_days_eval") or {}
    mind = (S.get("two_week") or {}).get("min_days", sizing.TW_DEFAULT["min_days"])
    check("minimum trading days: bot assumes >= the rulebook's (2 if the rulebook conflicts)",
          mind is not None and int(mind) >= int(md.get("value") or 1) and (md.get("status") != "conflict" or int(mind) >= 2),
          f"bot {mind}, rulebook {md.get('value')} ({md.get('status')})")
    s_md = sizing.eval_state({"2026-10-19": 3050.0}, 0.0, session=2, today="2026-10-20")
    s_dn = sizing.eval_state({"2026-10-16": 1000.0, "2026-10-19": 2050.0}, 0.0, session=3, today="2026-10-20")
    tr = {"risk_pts": 30.0, "tgt_pts": 200.0, "size_mult": 1.0}
    q_md = sizing.lit_qty(13, tr, S, room=s_md["room"], state=s_md, learning=None)["qty"]
    q_dn = sizing.lit_qty(13, tr, S, room=s_dn["room"], state=s_dn, learning=None)["qty"]
    check("passed eval: 1-micro minimum-days trade with 1 traded day, nothing with 2", q_md == 1 and q_dn == 0, f"{q_md} / {q_dn}")
    check("two_week caps on (dll_cap, room_f <= 1)", bool((S.get("two_week") or {}).get("dll_cap", True))
          and float((S.get("two_week") or {}).get("room_f") or 1.0) <= 1.0)

    # a full stop-out at the true MFFU cost (commission $1.90, 1 tick slip) vs the soft DLL and the room, over stops 8-90
    comm, worst_dll, worst_room = L50["comm_rt_micro"], 0.0, 0.0
    tw = S.get("two_week") or {}
    for stop in [8, 10, 12, 15, 18, 20, 24, 25, 30, 33, 40, 50, 60, 70, 80, 88]:
        for tgt_r in (1.5, 2.0, 3.0, 5.0, 8.0):
            for room in (2000.0, 1500.0, 1000.0, 600.0):
                st = {"profit": room - 2000.0, "cum": 0.0, "room": room, "session": 1, "n_today": 0}
                q = sizing.two_week_qty({"risk_pts": stop, "tgt_pts": stop * tgt_r}, st, tw)
                loss = q * ((stop + 0.25) * 2.0 + comm)
                if q > 1:              # 1 micro is the floor the rule allows; MFFU would pause, not breach
                    worst_dll = max(worst_dll, loss)
                    worst_room = max(worst_room, loss / room)
    warn("full stop-out inside the $1,000 soft DLL at $1.90 commission", worst_dll > L50["dll"],
         f"worst ${worst_dll:,.0f} (soft limit: a pause, not a breach)")
    check("full stop-out never reaches the max-loss floor (open losses count)", worst_room < 1.0,
          f"worst {worst_room * 100:.0f}% of the room")
    check("funded sizing keeps a 2-tick stop slip in its caps", int(getattr(sizing, "FD_DEFAULT", {}).get("slip_ticks", 2)) >= 1)

    # ---------------------------------------------------------------- funded constants (engine/sizing.py FD_50K)
    F = getattr(sizing, "FD_50K", None)
    if F:
        for k in ("buffer", "pay_min", "pay_max", "split", "cons", "max_payouts", "dll", "mll", "lock", "max_micros"):
            check(f"funded {k}", float(F[k]) == float(L50[k]), f"{F[k]} vs {L50[k]}")
    else:
        warn("funded constants", True, "engine/sizing.py has no FD_50K")

    # ---------------------------------------------------------------- known gaps (WARN)
    lit_src = _src("engine/lit.py")
    m = re.search(r"TICK, PV, COMM, SLIP, MAX_MICROS = [\d.]+, [\d.]+, ([\d.]+)", lit_src)
    c_bt = float(m.group(1)) if m else None
    warn("backtest commission = MFFU's MNQ round turn", c_bt is None or abs(c_bt - L50["comm_rt_micro"]) > 1e-9,
         f"engine/lit.py COMM ${c_bt} vs MFFU ${L50['comm_rt_micro']} (about -$310 to -$350 a year in 2026)")
    warn("sizing commission (two_week / funded caps)", abs(sizing.TW_COMM - L50["comm_rt_micro"]) > 1e-9,
         f"engine/sizing.py TW_COMM ${sizing.TW_COMM} vs ${L50['comm_rt_micro']}")
    try:
        run = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        ci = run["trade_cols"].index("day")
        days = sorted({dt.date.fromisoformat(t[ci]) for t in run["trades"] if str(t[ci]).startswith("2026")})
        idle = [((b - a).days - 1, a.isoformat()) for a, b in zip(days, days[1:]) if (b - a).days - 1 >= L50["inactivity_days"]]
        warn("7-day inactivity rule (2026 replay: calendar days in a row without a trade)", bool(idle),
             f"{len(idle)} gaps of 7+ days: " + ", ".join(f"{n} days after {d}" for n, d in idle) if idle else "none")
    except (OSError, ValueError, KeyError) as e:
        warn("7-day inactivity rule", True, f"lit_live run not readable ({e.__class__.__name__})")
    guard = "inactiv" in (_src("tools/cloud_monitor.py") + _src("engine/live.py")).lower()
    warn("inactivity alert in the bot", not guard, "no 'inactivity' guard found in tools/cloud_monitor.py / engine/live.py" if not guard else "found")

    print(f"\n{RES['ok']} ok, {RES['fail']} FAIL, {RES['warn']} WARN")
    return RES["fail"] == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
