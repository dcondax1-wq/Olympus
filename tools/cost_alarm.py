"""Nightly "still profitable at the real measured costs?" alarm for ATLAS and Zlarior (2026-11-20, day-atlasedge, TOP25 #14).
ALARM ONLY: reads, re-prices, writes research/lab/costs.json; never changes a bot, a size or a setting.
Design (committed before the first run): research/second/atlas_costs_split_design.md "#14".

    python -X utf8 tools/cost_alarm.py            # -> research/lab/costs.json + one line per bot
    python -X utf8 tools/cost_alarm.py --print    # no file

Per bot:
  measured entry cost = the median ticks of its real fills vs the model price (tools/fill_cost.from_rows on the pulled PC days;
  where none are pulled, the last stored real-fill study research/second/atlas_fills_why.json), n = how many fills;
  the cost actually charged = that median + the backtest's own 1 tick on the entry, 2 ticks on a non-target exit (a resting
  stop; design #8), 0 on a target;
  trades = the bot's model trades at a fixed risk (ATLAS: run atlas_fresh_fixed; Zlarior: run lit_live + research/lab/
  edge_health.json fresh trades), each trade's net R lowered by the extra ticks / its stop distance;
  R-PF of the last 40 sessions and of 2026 H1 (the baseline) at that cost.
Flags: "not enough fills" while n < 5; RED when last-40 PF < 1.0; AMBER when PF < 1.3 or < half the 2026 baseline; else GREEN.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "costs.json")
TICK = 0.25
STOP_TICKS = 2
MIN_FILLS = 5
WIN = 40


def measured():
    """{bot: {"n", "med", "src"}}: pulled PC days first, else the stored fill study."""
    out = {}
    try:
        from tools import fill_cost as FC
        for k, b in (FC.from_rows() or {}).items():
            if b and b.get("n"):
                out[k.lower()] = {"n": int(b["n"]), "med": float(b.get("entry_slip_med") or 0.0), "src": "pulled PC days (tools/fill_cost)"}
    except Exception:  # noqa: BLE001
        pass
    p = os.path.join(ROOT, "research", "second", "atlas_fills_why.json")
    if os.path.exists(p):
        F = json.load(open(p, encoding="utf-8")).get("fills") or []
        for bot in ("ATLAS", "Zlarior"):
            v = sorted(float(f["ticks_vs_model"]) for f in F if f.get("bot") == bot and f.get("ticks_vs_model") is not None)
            if v and bot.lower() not in out:
                out[bot.lower()] = {"n": len(v), "med": v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2,
                                    "src": "research/second/atlas_fills_why.json (2026-11-20)"}
    return out


def trades(bot):
    from tools import runlib as rl
    if bot == "atlas":
        r = rl.load("atlas_fresh_fixed")
        T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
        return T, "run atlas_fresh_fixed"
    r = rl.load("lit_live")
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    last = max(t["day"] for t in T)
    try:
        e = json.load(open(os.path.join(ROOT, "research", "lab", "edge_health.json"), encoding="utf-8"))
        T += [t for t in (e.get("fresh_trades") or []) if t.get("day", "") > last]
    except Exception:  # noqa: BLE001
        pass
    return T, "run lit_live + edge_health fresh trades"


def r_at(t, extra_entry):
    risk = float(t.get("risk_pts") or 0)
    if risk <= 0:
        return None
    tgt = str(t.get("exit", "")).upper() == "TARGET"
    extra = extra_entry + (0 if tgt else STOP_TICKS - 1)
    return float(t["r"]) - extra * TICK / risk


def pf(rs):
    w, l = sum(x for x in rs if x > 0), -sum(x for x in rs if x < 0)
    return round(w / l, 2) if l > 0 else None


def sessions_to(last_day):
    """weekdays up to last_day (the last-40 window; holidays add a quiet day, never a trade)."""
    d, out = dt.date.fromisoformat(last_day), []
    while len(out) < WIN:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def check(bot, M):
    T, src = trades(bot)
    m = M.get(bot) or {"n": 0, "med": 0.0, "src": "none"}
    extra = max(0.0, float(m["med"]))                 # ticks beyond the backtest's own 1
    last = max(t["day"] for t in T)
    S = set(sessions_to(last))
    rs40 = [x for x in (r_at(t, extra) for t in T if t["day"] in S) if x is not None]
    rsH1 = [x for x in (r_at(t, extra) for t in T if "2026-01-01" <= t["day"] <= "2026-06-30") if x is not None]
    p40, pH1 = pf(rs40), pf(rsH1)
    if m["n"] < MIN_FILLS:
        flag = "NOT ENOUGH FILLS"
    elif p40 is None or p40 < 1.0:
        flag = "RED"
    elif p40 < 1.3 or (pH1 and p40 < 0.5 * pH1):
        flag = "AMBER"
    else:
        flag = "GREEN"
    name = "ATLAS" if bot == "atlas" else "Zlarior"
    line = (f"{name} at real costs: {flag} · last 40 sessions PF {p40} vs 2026 H1 {pH1} at {m['med']:+.0f} ticks a fill "
            f"(median of {m['n']}) · data to {last}")
    return {"bot": name, "flag": flag, "line": line, "fills": m, "pf40": p40, "pf_2026_h1": pH1, "n40": len(rs40),
            "data_to": last, "trades_src": src, "stop_ticks": STOP_TICKS}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args(argv)
    M = measured()
    out = {"v": 1, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "what": "Alarm only: is each bot still profitable at its real measured fill cost? Changes no bot.",
           "rule": f"RED last-40 PF < 1.0; AMBER < 1.3 or < half of 2026 H1; needs {MIN_FILLS}+ real fills", "bots": {}}
    for bot in ("atlas", "zlarior"):
        try:
            out["bots"][bot] = check(bot, M)
        except Exception as e:  # noqa: BLE001
            out["bots"][bot] = {"flag": "ERROR", "line": f"{bot}: {e.__class__.__name__}: {e}"}
        print(out["bots"][bot]["line"])
    if not a.show:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
