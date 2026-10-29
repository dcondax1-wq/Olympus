"""Fix the account Names the bot sends when NinjaTrader says they do not exist (2026-10-27: every order of both MFFU
evals went to "MFFUEVBLD602936016" / "...017"; NinjaTrader's Log: "account does not exist 'MFFUEVBLD602936016'"; its
Accounts tab shows MFFUEVBLDR602936016 / ...017, with an R after BLD).

fix(): run by server.py at its start, before the bot can start. Reads NinjaTrader's logs of the last LOOK_DAYS days
(<NinjaTrader 8>\\log\\log.*.txt); for every name NinjaTrader called non-existent that matches MFFUEVBLD<digits>, the name
MFFUEVBLDR<digits> replaces it in the bot's own local files (FILES, gitignored: start names, ATLAS's block, allowlist,
eval anchors, extra accounts, the autostart record). Each changed file is backed up first (data/rename_backup/). The
owner's auto-resume opt-in (data/auto_resume.json) is never touched: it was given for the old Name, so the next Run asks
for the live phrase once (the owner arms; nothing is armed here). Idempotent; never raises.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("start_bot.json", "account_b.json", "nt_accounts_allow.json", "eval_anchor.json", "accounts.json", "autostart.json")
LOOK_DAYS = 7
_MISSING = re.compile(r"account does not exist '([^']+)'", re.I)
_BLD = re.compile(r"^MFFUEVBLD(\d{6,})$")


def missing_names(folder: str | None = None, now: float | None = None) -> set:
    """Account Names NinjaTrader's Log called non-existent in the last LOOK_DAYS days."""
    if not folder:
        from .ninjatrader import default_folder
        folder = default_folder()
    cut = (time.time() if now is None else now) - LOOK_DAYS * 86400
    out = set()
    for f in glob.glob(os.path.join(folder, "log", "log.*.txt")):
        try:
            if os.path.getmtime(f) < cut:
                continue
            with open(f, encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    m = _MISSING.search(ln)
                    if m:
                        out.add(m.group(1).strip())
        except Exception:
            continue
    return out


def renames(missing) -> dict:
    """{old: new} for the MFFU Builder names NinjaTrader does not know (MFFUEVBLD<digits> -> MFFUEVBLDR<digits>)."""
    out = {}
    for n in missing:
        m = _BLD.match(n)
        if m:
            out[n] = f"MFFUEVBLDR{m.group(1)}"
    return out


def apply(mapping: dict, data_dir: str | None = None) -> list:
    """Replace each old Name (as a JSON string or key) by the new one in FILES; returns the files changed."""
    data_dir = data_dir or os.path.join(ROOT, "data")
    changed = []
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    for name in FILES:
        p = os.path.join(data_dir, name)
        try:
            with open(p, encoding="utf-8") as fh:
                txt = fh.read()
        except Exception:
            continue
        new = txt
        for old, nw in mapping.items():
            new = new.replace(json.dumps(old), json.dumps(nw))
        if new == txt:
            continue
        try:
            json.loads(new)
        except Exception:
            continue                                   # never write a file that would not parse
        bdir = os.path.join(data_dir, "rename_backup")
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(p, os.path.join(bdir, f"{name}.{stamp}"))
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(new)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, p)
        changed.append(name)
    return changed


def fix(folder: str | None = None, data_dir: str | None = None, now: float | None = None) -> dict:
    """The server-start fix. {"ok", "renames", "changed", "say"}."""
    try:
        mp = renames(missing_names(folder, now))
        if not mp:
            return {"ok": True, "renames": {}, "changed": [], "say": "account names ok"}
        ch = apply(mp, data_dir)
        say = ("NinjaTrader did not know " + ", ".join(mp) + ": renamed to " + ", ".join(mp.values())
               + (f" in {', '.join(ch)}" if ch else " (nothing left to change)"))
        if ch:
            try:
                with open(os.path.join(data_dir or os.path.join(ROOT, "data"), "account_rename.json"), "w", encoding="utf-8") as fh:
                    json.dump({"t": int(time.time()), "renames": mp, "changed": ch}, fh, indent=1)
            except Exception:
                pass
        return {"ok": True, "renames": mp, "changed": ch, "say": say}
    except Exception as e:
        return {"ok": False, "renames": {}, "changed": [], "say": f"account name check failed: {e.__class__.__name__}: {e}"}
