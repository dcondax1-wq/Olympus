"""Earlier eval days whose booked P&L never happened at the broker (2026-10-27: every order went to a Name NinjaTrader
does not have, "account does not exist", yet the 50K's eval ledger kept -$965.20 for that day after it rolled into the
previous days at 18:00 and the per-trade void, engine/live.py _void_unplaced_exits, could no longer see it).

void_days(days, folder): the earlier trading days (YYYY-MM-DD keys of LiveBot._eval_prev) to set to $0: NinjaTrader's Log
for that calendar date (<NinjaTrader 8>\\log\\log.YYYYMMDD.*.txt) refused at least one of the bot's PLACE orders with
"account does not exist" and shows no Execution at all (nothing filled on any account). A day without its log file, or
with any fill, is left as booked. Read-only; never raises.
"""
from __future__ import annotations

import glob
import os


def _log_text(folder: str, day: str) -> str | None:
    fs = glob.glob(os.path.join(folder, "log", f"log.{day.replace('-', '')}.*.txt"))
    if not fs:
        return None
    out = []
    for f in fs:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                out.append(fh.read())
        except Exception:
            return None
    return "\n".join(out)


def refused_day(folder: str, day: str) -> bool:
    txt = _log_text(folder, day)
    if not txt:
        return False
    low = txt.lower()
    return "place;" in low and "account does not exist" in low and "execution=" not in low


def void_days(days: dict, folder: str | None) -> list:
    """Days (with a non-zero booked P&L) whose NinjaTrader Log proves nothing was filled; [] when unsure."""
    try:
        if not folder:
            from .ninjatrader import default_folder
            folder = default_folder()
        return [d for d, v in sorted((days or {}).items())
                if d != "0000-00-00" and abs(float(v or 0)) > 1e-9 and refused_day(folder, d)]
    except Exception:
        return []
