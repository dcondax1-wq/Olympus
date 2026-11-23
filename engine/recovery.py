"""What brings the bot back BY ITSELF, one plain line per way it can stop (night-zerotouch 2026-11-22, owner: "make this
automatic. I shouldn't need to do anything").

    python -X utf8 -m engine.recovery        the matrix for this PC: [OK] comes back by itself / [FIX] the one step

Each row = (what happens, comes back by itself?, how, the one fix when it does not). Read-only: it never starts, arms,
opens or changes anything. The pieces it reads (all existing):
  * auto-resume (engine/autoresume.py, data/auto_resume.json): made when the owner types I ACCEPT LIVE RISK at a START; a
    server start resumes exactly the accounts he armed then. No expiry date; it ends with the kill switch, HOLD TO KILL,
    --disable-auto-resume or STOP BOT (an intentional stop stays stopped). Refused on a day with the kill switch used or a
    -$1,000 day, for 10 minutes after a failed start, and until NinjaTrader shows CONNECTED (it opens NinjaTrader and keeps
    waiting while the dashboard switch is on Run); every resume / refusal pushes the phone.
  * the run_bot.ps1 supervisor: restarts a crashed server with back-off; an update restart (exit 75) at once.
  * engine/keepawake.py: the PC does not sleep while the bot runs (process-scoped); tools/pc_always_on.py --check: the
    power plan, Windows Update, the logon task, the NinjaTrader Startup shortcut, auto-login.
  * engine/self_heal.py (hourly, the 15-minute PC report task): a stale pid, a stuck git lock, NinjaTrader closed while the
    bot should run (opened), the clock; a server that stays down = an alert with BOTS_BACK.bat.
  * the 7-day keep-alive switches (data/keepalive.json) are files: they survive every restart.
Tests: python -X utf8 -m tests.test_recovery
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pc_checks():
    """tools/pc_always_on.check() on Windows: [(green, what, fix)]; [] elsewhere / on an error."""
    if os.name != "nt":
        return []
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import pc_always_on
        return pc_always_on.check()
    except Exception:
        return []


def _find(checks, *words):
    """(green, fix) of the first pc_always_on line whose text has every word; None = not checked."""
    for g, what, fix in checks or []:
        w = str(what).lower()
        if all(x.lower() in w for x in words):
            return bool(g), str(fix or "")
    return None


def _ok(v):
    return None if v is None else bool(v[0])


def matrix(checks=None, resume=None, ka=None) -> list:
    """[{"what", "ok" (True / False / None = not checked here), "how", "fix"}]. checks = pc_always_on.check() rows,
    resume = engine/autoresume.status(), ka = {key: bool} keep-alive switches. Never raises."""
    if checks is None:
        checks = _pc_checks()
    if resume is None:
        try:
            from . import autoresume
            resume = autoresume.status()
        except Exception:
            resume = {}
    if ka is None:
        try:
            from . import keepalive
            ka = keepalive.load_config(None).get("accounts") or {}
        except Exception:
            ka = {}
    ar = bool((resume or {}).get("on"))
    ar_fix = "START BOT (or MONDAY_SETUP.bat) and type I ACCEPT LIVE RISK yourself"
    logon = _find(checks, "task liquidityengine ")
    ntsc = _find(checks, "ninjatrader startup shortcut")
    autol = _find(checks, "auto-login")
    wu = _find(checks, "windows update", "restart")
    sleep = _find(checks, "sleep", "hibernat")

    def need(*parts):
        """the first missing piece's fix ('' = none missing); a not-checked piece (None) is not counted as missing."""
        for p in parts:
            if p is not None and not p[0]:
                return p[1] or "double-click ONE_TIME_SETUP.bat"
        return ""
    rows = []
    boot_fix = (ar_fix if not ar else "") or need(autol, logon, ntsc)
    boot_ok = ar and all(_ok(p) is not False for p in (autol, logon, ntsc))
    rows.append({"what": "PC restart / power cut", "ok": boot_ok,
                 "how": "signs in, starts NinjaTrader + the bot server, auto-resume re-arms the accounts you armed once "
                        "NinjaTrader connects", "fix": boot_fix})
    rows.append({"what": "Windows Update restart", "ok": boot_ok and _ok(wu) is not False,
                 "how": "no forced restart while signed in; if it restarts anyway: as a PC restart",
                 "fix": boot_fix or need(wu)})
    rows.append({"what": "Bot server crash / crash loop", "ok": ar,
                 "how": "the supervisor restarts it (back-off), auto-resume re-arms; still down: phone alert + BOTS_BACK.bat",
                 "fix": "" if ar else ar_fix})
    rows.append({"what": "Update / rollback restart", "ok": ar,
                 "how": "the update restarts the server on the new (or the rolled-back) code, auto-resume re-arms",
                 "fix": "" if ar else ar_fix})
    rows.append({"what": "NinjaTrader closed / disconnected", "ok": ar,
                 "how": "self-heal opens it within the hour (auto-resume at once after a restart); the bot reconnects when "
                        "NinjaTrader's saved log-in connects; phone alert 'NinjaTrader closed'",
                 "fix": "" if ar else ar_fix})
    rows.append({"what": "Sleep / power save", "ok": _ok(sleep) is not False,
                 "how": "the bot keeps the PC awake while it runs; the power plan never sleeps on AC",
                 "fix": need(sleep)})
    on = [k for k, v in (ka or {}).items() if v is True]
    rows.append({"what": "MFFU 7 days without a trade", "ok": bool(on),
                 "how": f"keep-alive ON for {len(on)} account(s): one 1-MNQ trade only when 7 days would pass" if on else
                        "keep-alive is off: the phone warns from day 5",
                 "fix": "" if on else "START BOT and type I ACCEPT LIVE RISK (it turns the keep-alive on too)"})
    rows.append({"what": "Kill switch / -$1,000 day", "ok": True,
                 "how": "stays stopped ON PURPOSE (the day's loss is never chased); the kill switch also ends auto-resume",
                 "fix": ""})
    return rows


def lines(rows=None) -> list:
    rows = matrix() if rows is None else rows
    out = []
    for r in rows:
        tag = "[OK]" if r["ok"] else "[FIX]"
        out.append(f"{tag} {r['what']}: " + (r["how"] if r["ok"] else (r["fix"] or r["how"])))
    return out


def main(argv=None) -> int:
    print(" What comes back by itself:")
    rows = matrix()
    for ln in lines(rows):
        print("  " + ln)
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
