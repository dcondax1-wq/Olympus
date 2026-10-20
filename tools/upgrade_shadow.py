"""What the three LIT upgrades (t_check, scale_in, be_off) added or cost so far, live (cloud paper only).

The cloud monitor (tools/cloud_monitor.py) keeps a second paper ledger next to the live LIT one: the same LIT rules on the same
bars with the three upgrades switched off (state key "lit_base", no alerts). This module holds the pure parts:

  base_params(P)        LIT params with t_check / scale_in / be_off back at their off values (engine/lit.py DEFAULTS)
  upgrades_on(P)        which of the three are on
  seed(ledger)          the base ledger's first rows: the live ledger's finished trades (same eval state at the start)
  compare(...)          the "upgrades_live" block for state.json / data.json
  readme_rows(u)        the README section

Attribution (per trade both ledgers took, matched by entry time; "where attributable"):
  t_check   the live trade was cut at the 15-minute check (exit CUT_T15): $ saved = live $ - base $ on that trade
  scale_in  the live trade carries adds: the adds' own $ (the rest of that trade's difference goes to "other")
  be_off    a BE exit on either side (the breakeven stop at entry + be_off pts instead of the entry): live $ - base $
  other     everything else: a different size (the two_week sizing follows each ledger's own eval state), trades only one
            ledger took (the weekly stop counts STOP exits, a cut is not one)
Paper only; nothing here routes an order.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UPGRADES = ("t_check", "scale_in", "be_off")
NAMES = {"t_check": "15-minute check", "scale_in": "scale-in after BE", "be_off": "BE + costs (be_off)"}
PV, COMM = 2.0, 1.40                   # engine/lit.py: $ per point per micro, commission per micro round trip (backtest)


def _off():
    from engine import lit
    return {k: lit.DEFAULTS.get(k) for k in UPGRADES}


def is_on(k, v) -> bool:
    return bool(v) if k != "be_off" else float(v or 0.0) != 0.0


def upgrades_on(P: dict | None) -> list:
    P = P or {}
    return [k for k in UPGRADES if is_on(k, P.get(k))]


def base_params(P: dict) -> dict:
    """LIT params without the three upgrades (everything else unchanged)."""
    return {**(P or {}), **_off()}


def seed(ledger: dict) -> dict:
    """The base ledger's start: a copy of the live ledger's finished rows, so both ledgers begin from the same eval balance
    (the two_week sizing reads it). The comparison only counts trades that enter after the base ledger started."""
    out = {}
    for k, v in (ledger or {}).items():
        if v.get("exit_ts") and v.get("exit") not in (None, "OPEN"):
            out[int(k)] = {**v, "seeded": True}
    return out


def add_usd(trade: dict | None, mult: float = 1.0) -> float:
    """$ of a scale_in trade's adds (engine/lit.py: qty x (pts x $2 - commission) each), at the ledger's size multiplier."""
    adds = (trade or {}).get("adds") or []
    cm = float((trade or {}).get("comm_rt", COMM))
    return round(sum(int(a.get("qty") or 0) * (float(a.get("pts") or 0.0) * PV - cm) for a in adds) * float(mult or 0.0), 2)


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def compare(live_ledger: dict, base_ledger: dict, since: int, on: list, live_trades=None, scale_in_live: bool = False) -> dict:
    """The upgrades_live block: both ledgers' trades that entered from `since`, $ with vs without, per upgrade."""
    since = int(since)
    L = {int(k): v for k, v in (live_ledger or {}).items() if int(k) >= since and not v.get("seeded")}
    B = {int(k): v for k, v in (base_ledger or {}).items() if int(k) >= since and not v.get("seeded")}
    by_t = {int(t["entry_t"]): t for t in (live_trades or []) if t.get("entry_t") is not None}
    per = {k: {"name": NAMES[k], "on": k in on, "n": 0, "usd": 0.0} for k in UPGRADES}
    per["t_check"]["cuts"] = 0
    other = {"n": 0, "usd": 0.0}
    rows = []
    for k in sorted(set(L) | set(B)):
        lv, bv = L.get(k), B.get(k)
        lu, bu = float((lv or {}).get("usd") or 0.0), float((bv or {}).get("usd") or 0.0)
        delta = round(lu - bu, 2)
        why = []
        if lv is None or bv is None:
            other["n"] += 1; other["usd"] += delta
            why.append("only live" if bv is None else "only without upgrades")
        else:
            a = add_usd(by_t.get(k), lv.get("mult", 1.0))
            if lv.get("exit") == "CUT_T15":
                per["t_check"]["n"] += 1; per["t_check"]["cuts"] += 1; per["t_check"]["usd"] += delta
                why.append("15-min cut")
            elif a:
                per["scale_in"]["n"] += 1; per["scale_in"]["usd"] += a
                other["usd"] += delta - a
                why.append("scale-in add")
            elif "BE" in (lv.get("exit"), bv.get("exit")):
                per["be_off"]["n"] += 1; per["be_off"]["usd"] += delta
                why.append("BE + costs")
            elif delta:
                other["n"] += 1; other["usd"] += delta
                why.append("size" if lv.get("qty") != bv.get("qty") else "other")
        rows.append({"entry_t": k, "day": (lv or bv).get("day"), "entry": (lv or bv).get("entry"), "side": (lv or bv).get("side"),
                     "live_exit": (lv or {}).get("exit"), "live_usd": round(lu, 2) if lv else None, "live_qty": (lv or {}).get("qty"),
                     "base_exit": (bv or {}).get("exit"), "base_usd": round(bu, 2) if bv else None, "base_qty": (bv or {}).get("qty"),
                     "delta": delta, "why": why})
    for p in list(per.values()) + [other]:
        p["usd"] = round(p["usd"], 2)
    if not scale_in_live:
        per["scale_in"]["note"] = ("no add in the live paper ledger so far: the live loop carries adds (engine/lit_live.py "
                                   "trades keep \"adds\"), but none has fired yet (an add needs BE first, then a pullback "
                                   "and a 1m CISD), so it shows $0 here")
    lu = round(sum(float(v.get("usd") or 0.0) for v in L.values()), 2)
    bu = round(sum(float(v.get("usd") or 0.0) for v in B.values()), 2)
    return {"on": list(on), "since": since, "since_et": f"{_et(since):%Y-%m-%d %H:%M} ET",
            "trades_live": len(L), "trades_base": len(B), "usd_live": lu, "usd_base": bu, "delta": round(lu - bu, 2),
            "per_upgrade": per, "other": other, "rows": rows[-20:],
            "note": "Paper: the live LIT ledger vs the same LIT without t_check / scale_in / be_off on the same bars "
                    "(state lit_base, no alerts). Attribution is per trade where it is clear; size differences from each "
                    "ledger's own eval state go to other."}


def money(x):
    x = float(x or 0.0)
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.2f}"


def readme_rows(u: dict | None) -> list:
    """README lines: one summary row plus the per-upgrade split."""
    if not u:
        return []
    if u.get("error"):
        return ["", "## Upgrades live (t_check, scale_in, be_off)", f"Comparison unavailable: {u['error']}"]
    p = u.get("per_upgrade") or {}
    L = ["", "## Upgrades live (t_check, scale_in, be_off)",
         f"Live LIT vs the same LIT without the upgrades on the same bars (paper ledger lit_base, no alerts), since {u.get('since_et')}.",
         "| | Trades | $ |", "|---|---:|---:|",
         f"| With upgrades (live) | {u.get('trades_live', 0)} | {money(u.get('usd_live'))} |",
         f"| Without upgrades | {u.get('trades_base', 0)} | {money(u.get('usd_base'))} |",
         f"| **Upgrades added** | | **{money(u.get('delta'))}** |"]
    for k in UPGRADES:
        x = p.get(k) or {}
        extra = f" (cuts: {x['cuts']})" if k == "t_check" else ""
        L.append(f"| {x.get('name', k)}{'' if x.get('on') else ' (off)'}{extra} | {x.get('n', 0)} | {money(x.get('usd'))} |")
    o = u.get("other") or {}
    L.append(f"| Other (size from the eval state, a trade only one side took) | {o.get('n', 0)} | {money(o.get('usd'))} |")
    if (p.get("scale_in") or {}).get("note"):
        L.append(f"\nScale-in: {p['scale_in']['note']}.")
    return L
