"""NinjaTrader's own log lines about the bot's orders, for the heartbeat (2026-10-27: both MFFU accounts' first real orders,
ATLAS 03:30 and Zlarior 06:12, were picked up by NinjaTrader but never confirmed, and the reason is only in NinjaTrader's
Log tab, which the owner cannot open away from the PC).

lines(folder): the newest NinjaTrader log files (<NinjaTrader 8>\\log\\log.*.txt, the Log tab), their last 512 KB, the
lines of today and yesterday that mention one of the bot's order ids (LE...), an order rejection / error, the Automated
Trading Interface, an order-instruction file or an account the bot trades. At most MAX_LINES, each MAX_LEN characters,
file paths and e-mail addresses removed. Read-only; cached on the files' size + modified time; never raises.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re

MAX_LINES = 40
MAX_LEN = 240
TAIL_BYTES = 512 * 1024
_KEY = re.compile(r"LE1\d{9}|reject|automated trading|\bATI\b|order instruction|\boif\b|\.txt'?\s*(not|could)|error|failed|"
                  r"MFFU|Sim10\d", re.I)
_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_CACHE: dict = {}


def _clean(s: str) -> str:
    from .accounts import _PATH
    s = _MAIL.sub("<mail>", _PATH.sub("<path>", s)).replace("\r", " ").replace("\t", " ").strip()
    return s[:MAX_LEN]


def files(folder: str, n: int = 2) -> list:
    try:
        fs = glob.glob(os.path.join(folder, "log", "log.*.txt"))
        return sorted(fs, key=os.path.getmtime)[-n:]
    except Exception:
        return []


def _tail(path: str) -> str:
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - TAIL_BYTES))
        return fh.read().decode("utf-8", "replace")


def lines(folder: str | None, today: dt.date | None = None) -> dict:
    """{"files": n, "lines": [...], "error"?}; nothing found = an empty list."""
    try:
        if not folder:
            from .ninjatrader import default_folder
            folder = default_folder()
        fs = files(folder)
        if not fs:
            return {"files": 0, "lines": [], "note": "no NinjaTrader log file found"}
        key = tuple((f, os.path.getsize(f), os.path.getmtime(f)) for f in fs)
        if _CACHE.get("key") == key:
            return _CACHE["out"]
        today = today or dt.date.today()
        days = {today.isoformat(), (today - dt.timedelta(days=1)).isoformat()}
        out = []
        for f in fs:
            for ln in _tail(f).splitlines():
                if ln[:10] in days and _KEY.search(ln):
                    out.append(_clean(ln))
        res = {"files": len(fs), "lines": out[-MAX_LINES:]}
        _CACHE.update(key=key, out=res)
        return res
    except Exception as e:
        return {"files": 0, "lines": [], "error": f"{e.__class__.__name__}"}


def hb_block(bot) -> dict | None:
    """The heartbeat's "nt_log" block (NinjaTrader bots only)."""
    cfg = getattr(bot, "cfg", None) or {}
    if cfg.get("adapter") != "ninjatrader":
        return None
    return lines(cfg.get("nt_folder"))
