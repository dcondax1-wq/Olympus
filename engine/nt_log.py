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


def files(folder: str, n: int = 2, sub: str = "log") -> list:
    try:
        fs = glob.glob(os.path.join(folder, sub, f"{sub}.*.txt"))
        return sorted(fs, key=os.path.getmtime)[-n:]
    except Exception:
        return []


def _tail(path: str) -> str:
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - TAIL_BYTES))
        return fh.read().decode("utf-8", "replace")


def lines(folder: str | None, today: dt.date | None = None, sub: str = "log") -> dict:
    """{"files": n, "lines": [...], "error"?}; nothing found = an empty list. sub "trace" = NinjaTrader's trace files
    (<NinjaTrader 8>\\trace\\trace.*.txt: the ATI's own processing lines)."""
    try:
        if not folder:
            from .ninjatrader import default_folder
            folder = default_folder()
        fs = files(folder, sub=sub)
        if not fs:
            return {"files": 0, "lines": [], "note": f"no NinjaTrader {sub} file found"}
        key = tuple((f, os.path.getsize(f), os.path.getmtime(f)) for f in fs)
        if _CACHE.get(sub, {}).get("key") == key:
            return _CACHE[sub]["out"]
        today = today or dt.date.today()
        days = {today.isoformat(), (today - dt.timedelta(days=1)).isoformat()}
        out = []
        for f in fs:
            for ln in _tail(f).splitlines():
                if ln[:10] in days and _KEY.search(ln):
                    out.append(_clean(ln))
        res = {"files": len(fs), "lines": out[-MAX_LINES:]}
        _CACHE[sub] = {"key": key, "out": res}
        return res
    except Exception as e:
        return {"files": 0, "lines": [], "error": f"{e.__class__.__name__}"}


def outgoing_summary(folder: str | None) -> dict:
    """What NinjaTrader's outgoing\\ folder shows, names only: its connection files (<name>.txt holding CONNECTED /
    DISCONNECTED), the accounts it wrote position files for, how many order files (ours = LE...) it holds, and the
    newest LE order files (the bot's ids, e.g. whether NinjaTrader answered an entry at all)."""
    try:
        if not folder:
            from .ninjatrader import default_folder
            folder = default_folder()
        d = os.path.join(folder, "outgoing")
        names = os.listdir(d)
    except Exception as e:
        return {"error": e.__class__.__name__}
    pos_accts, conns, ours, other = {}, [], [], 0
    for n in names:
        low = n.lower()
        if low.endswith("_position.txt"):
            acct = n[:-len("_position.txt")].rsplit("_", 1)[-1]
            pos_accts[acct] = pos_accts.get(acct, 0) + 1
        elif n.startswith("LE") and low.endswith(".txt"):
            ours.append(n)
        elif low.endswith(".txt") and "_" not in n and len(n) < 60:
            try:
                txt = open(os.path.join(d, n), encoding="utf-8", errors="replace").read(40).strip().upper()
            except Exception:
                txt = ""
            if txt in ("CONNECTED", "DISCONNECTED", "CONNECTION LOST"):
                conns.append(f"{n[:-4]}={txt}")
            else:
                other += 1
        else:
            other += 1
    ours.sort(key=lambda n: os.path.getmtime(os.path.join(d, n)) if os.path.exists(os.path.join(d, n)) else 0)
    out = {"files": len(names), "connections": conns, "position_accounts": pos_accts, "le_orders": len(ours),
           "le_newest": [_clean(x) for x in ours[-8:]], "other": other}
    try:
        # the connection files alone can say "Simulation=CONNECTED" only while the MFFU connection is up (a file is
        # written on a state change): NinjaTrader's live accounts and live bars complete the picture (2026-11-03)
        from .ninjatrader import connection_view
        cv = connection_view({c.split("=", 1)[0]: c.split("=", 1)[1] for c in conns if "=" in c}, folder)
        out.update({"connected": cv["connected"], "connected_via": cv["via"], "live_accounts": cv["live_accounts"]})
        if cv.get("note"):
            out["note"] = _clean(cv["note"])
    except Exception:
        pass
    return out


def hb_block(bot) -> dict | None:
    """The heartbeat's "nt_log" block (NinjaTrader bots only): the Log-tab lines + the outgoing\\ summary."""
    cfg = getattr(bot, "cfg", None) or {}
    if cfg.get("adapter") != "ninjatrader":
        return None
    out = dict(lines(cfg.get("nt_folder")))
    tr = lines(cfg.get("nt_folder"), sub="trace")
    out["trace"] = tr.get("lines", [])[-20:]
    out["outgoing"] = outgoing_summary(cfg.get("nt_folder"))
    return out
