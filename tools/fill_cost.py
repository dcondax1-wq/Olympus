"""FILL COST (night-atlasfills 2026-11-20): "real slippage so far: N ticks over K fills" for each bot, as data for the phone.

The PC already measures every real NinjaTrader entry against the model's price (engine/zeus_learn.fills: the last 20 live
fills, median ticks worse, worst) and ships it in the day folder's learn.json (data branch -> data/pc_days/<day>/learn.json).
This turns that into one plain line per bot and puts it on the ZEUS page's cloud card (tools/learn_night.card_doc ->
tools/web_public/hub/learned.json, bots[].fills). When the PC's learn.json lacks it (an older PC), the line is rebuilt
here from the ledger rows of the pulled days (data/pc_days/*/trades.jsonl.gz, the broker legs' fill_px vs the row's model
entry). Read only, stdlib only, never raises; no account name or number in the output.

    words(fl)            {"n", "entry_slip_med", "worst"} -> "Real fills so far: 11 ticks worse than the backtest price (median of 3; worst 15)"
    from_rows(pc_days)   {bot: {"n", "entry_slip_med", "worst", "mean", "usd_per_micro"}} from the ledger rows (live only)
    block(fl)            the card's per-bot dict {"n", "med", "worst", "line", "assumed": 1}
    python -X utf8 tools/fill_cost.py      # print the lines for the pulled days
Tests: python -X utf8 -m tests.test_fill_cost.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC_DAYS = os.path.join(ROOT, "data", "pc_days")
TICK, PV = 0.25, 2.0
ASSUMED = 1                    # ticks the backtests count on a market entry (live_model.json costs, tools/atlas_* SLIP 0.25)
LAST_N = 20                    # = engine/zeus_learn.fills
BOT_OF = {"zlarior": "zlarior", "atlas": "atlas"}       # ledger "bot" -> key (BLITZ / ATLAS v2 hidden: never shown)
HIDDEN = re.compile(r"blitz|acctc|acct_c|atlas_v2", re.I)


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _t(x: float) -> str:
    return f"{x:g}" if abs(x - round(x)) > 1e-9 else str(int(round(x)))


def words(fl) -> str | None:
    """the phone's one line, or None (no real fill yet)"""
    if not isinstance(fl, dict) or not fl.get("n") or _f(fl.get("entry_slip_med")) is None:
        return None
    n, med = int(fl["n"]), float(fl["entry_slip_med"])
    worst = _f(fl.get("worst"))
    how = "worse" if med > 0 else ("better" if med < 0 else "the same as")
    head = (f"Real fills so far: {_t(abs(med))} tick{'s' if abs(med) != 1 else ''} {how} than the backtest price"
            if med else "Real fills so far: at the backtest price")
    tail = f"median of {n} fill{'s' if n != 1 else ''}" if n > 1 else "1 fill"
    if worst is not None and n > 1:
        tail += f"; worst {_t(worst)}"
    usd = round(abs(med) * TICK * PV, 2)
    money = f", about ${usd:,.2f} a micro a trade" if med > 0 else ""
    return f"{head} ({tail}{money}; the backtest already counts {ASSUMED})"


def block(fl) -> dict | None:
    line = words(fl)
    if not line:
        return None
    return {"n": int(fl["n"]), "med": _f(fl.get("entry_slip_med")), "worst": _f(fl.get("worst")), "assumed": ASSUMED, "line": line}


def _rows(path: str) -> list:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]
    except Exception:  # noqa: BLE001
        return []


def from_rows(pc_days: str = PC_DAYS) -> dict:
    """{bot: {"n", "entry_slip_med", "worst", "mean", "usd_per_micro"}} over the last LAST_N live fills of the pulled days."""
    S = {}
    try:
        days = sorted(p for p in os.listdir(pc_days) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p))
    except OSError:
        return {}
    for d in days:
        for r in _rows(os.path.join(pc_days, d, "trades.jsonl.gz")):
            if not isinstance(r, dict) or r.get("mode") != "live" or r.get("side") not in ("buy", "sell"):
                continue
            if HIDDEN.search(str(r.get("bot") or "")) or HIDDEN.search(str(r.get("src") or "")):
                continue
            key = BOT_OF.get(str(r.get("bot") or ""))
            plan = _f(r.get("entry"))
            res = r.get("result") if isinstance(r.get("result"), dict) else {}
            legs = [lg for lg in (res.get("legs") or []) if isinstance(lg, dict) and lg.get("filled") and _f(lg.get("fill_px"))]
            if not key or plan is None or not legs or res.get("ok") is False:
                continue
            q = sum(int(lg["filled"]) for lg in legs)
            px = sum(float(lg["fill_px"]) * int(lg["filled"]) for lg in legs) / q
            dr = 1 if r["side"] == "buy" else -1
            S.setdefault(key, []).append((int(_f(r.get("entry_t")) or 0), round(dr * (px - plan) / TICK, 2)))
    out = {}
    for k, xs in S.items():
        v = [x for _, x in sorted(xs)][-LAST_N:]
        med = statistics.median(v)
        out[k] = {"n": len(v), "entry_slip_med": round(med, 2), "worst": max(v), "mean": round(sum(v) / len(v), 2),
                  "usd_per_micro": round(med * TICK * PV, 2)}
    return out


def main(argv=None) -> int:
    for k, fl in sorted(from_rows().items()):
        print(f"{k:8s} {words(fl)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
