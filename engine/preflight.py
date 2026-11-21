"""PREFLIGHT (day-nqops 2026-11-21, lead: "the bot's biggest leak is the PC being OFF or asleep in market hours"): ONE phone
summary before the week opens (Sunday 17:30 ET) and before each session (the weekday pre-session check, 01:40 ET): "Ready" or
the exact fix first.

What it checks (all read-only, all from facts engine/ops_checks already gathers; nothing new runs in the bot):
  1. the PC side: dashboard server up, bot running, heartbeat fresh (ops_checks keys server / bot / heartbeat)
  2. NinjaTrader: the order folder and the connection (nt_folder / nt_conn)
  3. the bar feed: fresh when the market is open (feed_1m / feed_5m; before the Sunday open "closed" is normal)
  4. each account's arm state: Zlarior (health.account), ATLAS (second.route.account_b), the extra accounts (health.accounts):
     LIVE + armed, or what it is instead (SIM, paper, orders disabled)
  5. the MFFU 7-day clock per account (engine/clock7: last fill, MFFU's last day, keep-alive on / off): a red one is a fix
  6. today's (on Sunday: Monday's) Tier-1 news (engine/multi_account.tier1_releases, the times the keep-alive avoids)

    python -X utf8 -m engine.preflight            prints the summary now (nothing sent)
    python -X utf8 -m engine.preflight --send     also pushes it (the same path as every ops notice: engine/ops_checks.send)

The scheduled push is engine/ops_checks.tick: due()["preflight"] (Sunday 17:30-18:15 ET, key ops:sun:<day>) and the weekday
pre-session notice (01:40-02:15 ET) which carries the same clock + news line. Never starts, stops, arms or places anything.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_PATH = os.path.join(ROOT, "data", "pc_report", "status_ext.json")    # tools/pc_report: the last ext posts (x.mf, x.k7)
PC_KEYS = ("server", "bot", "heartbeat", "nt_folder", "nt_conn", "feed_1m", "feed_5m", "internet", "clock", "disk", "kill")
OPEN_HM = 18 * 60                     # Sunday: CME opens 18:00 ET


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _et(t) -> dt.datetime:
    from .ops_checks import _et as et
    return et(t)


def last_ext(path: str = EXT_PATH) -> dict:
    """The x blocks of the PC report's last ext posts, merged ({} when none)."""
    try:
        with open(path, encoding="utf-8") as fh:
            ex = json.load(fh)
    except Exception:
        return {}
    out = {}
    for e in ex if isinstance(ex, list) else [ex]:
        for k, v in _d(_d(e).get("x")).items():
            out.setdefault(k, v)
    return out


def arms(hb: dict) -> list:
    """[(name, ok, text)] per routed account from the heartbeat (no ids: names only)."""
    h = _d(_d(hb).get("health"))
    out = []
    a = _d(h.get("account"))
    if a:
        lab = str(a.get("label") or "?")
        if a.get("enabled") is False:
            out.append(("Zlarior 50K", False, "orders DISABLED"))
        elif lab == "LIVE":
            out.append(("Zlarior 50K", bool(a.get("armed")), "LIVE, armed" if a.get("armed") else "LIVE but NOT armed"))
        else:
            out.append(("Zlarior 50K", False, f"{lab} (not your eval)"))
    ab = _d(_d(_d(_d(hb).get("second")).get("route")).get("account_b"))
    if ab:
        lab = str(ab.get("label") or ab.get("kind") or "?").upper()
        if ab.get("enabled") is False:
            out.append(("ATLAS 25K", False, "off"))
        else:
            out.append(("ATLAS 25K", bool(ab.get("armed")) and lab == "LIVE", f"{lab}, armed" if ab.get("armed") else f"{lab}, NOT armed"))
    for r in _l(h.get("accounts")):
        if not isinstance(r, dict) or str(r.get("id") or "") in ("", "blitz"):
            continue
        nm = {"b25k_2": "Zlarior 25K #2", "rapid": "Rapid EOD"}.get(str(r["id"]), str(r.get("name") or r["id"])[:30])
        if r.get("enabled") is False:
            out.append((nm, False, "off" + (f" ({str(r.get('disabled'))[:40]})" if r.get("disabled") else "")))
        else:
            out.append((nm, bool(r.get("armed")), f"{r.get('label') or '?'}, {'armed' if r.get('armed') else 'NOT armed'}"))
    return out


def news_line(now) -> str:
    """'Tier-1 news Mon: 08:30, 10:00 ET' for the session ahead ('' when none / unknown)."""
    try:
        from .keepalive import trading_day
        from .multi_account import tier1_releases
        day = trading_day(int(now) + 45 * 60)
        rel = sorted(tier1_releases(day))
        if not rel:
            return ""
        d = dt.date.fromisoformat(day)
        return f"Tier-1 news {d:%a}: " + ", ".join(f"{_et(r):%H:%M}" for r in rel[:4]) + " ET"
    except Exception:
        return ""


def build(checks: list, hb: dict | None, now, ext: dict | None = None, sunday: bool | None = None) -> dict:
    """{"ready", "title", "body", "fixes": [...], "clock": k7 rows, "arms": [...], "news"}. Never raises."""
    try:
        from . import clock7
        e = _et(now)
        sunday = (e.weekday() == 6) if sunday is None else sunday
        hb = _d(hb)
        ext = _d(ext)
        by = {c.get("key"): c for c in checks or [] if isinstance(c, dict)}
        fixes = []
        for k in PC_KEYS:
            c = by.get(k)
            if c and c.get("level") == "bad":
                fixes.append(f"{c.get('name')}: {c.get('text')}. {c.get('fix') or ''}".strip())
        nt = by.get("nt_conn")
        if nt and nt.get("level") == "warn":
            fixes.append(f"{nt.get('name')}: {nt.get('text')}. {nt.get('fix') or ''}".strip())
        A = arms(hb) if hb else []
        for nm, ok, txt in A:
            if not ok and "off" not in txt:
                fixes.append(f"{nm}: {txt}. Dashboard > that account > Arm (type your phrase yourself).")
        k7 = clock7.build(ext.get("mf"), hb.get("keepalive"), now) or _d(ext.get("k7"))
        rows = _l(_d(k7).get("a"))
        for r in rows:
            if r.get("lvl") == "bad":
                fixes.append(clock7.line(r) + ". It needs one filled trade by then: let the bot trade, place 1 MNQ by hand while "
                             "every account is flat, or KEEPALIVE_ON.bat.")
        news = news_line(now)
        ready = not fixes
        when = "Sunday's open (18:00 ET)" if sunday else "today's session"
        if ready:
            title = f"Ready for {when}"
            body = "PC, NinjaTrader and the feed OK. " + ("; ".join(f"{n}: {t}" for n, _ok, t in A) + ". " if A else "")
        else:
            title = ("Fix before 18:00 ET: " if sunday and e.hour * 60 + e.minute < OPEN_HM else "Fix now: ") + fixes[0].split(":")[0]
            body = fixes[0] + (f" (+{len(fixes) - 1} more: double-click HEALTH CHECK)" if len(fixes) > 1 else "") + " "
        warn = [clock7.line(r) for r in rows if r.get("lvl") == "warn"]
        if warn:
            body += "7-day clock: " + "; ".join(warn[:2]) + ". "
        elif rows and ready:
            body += f"7-day clock OK (next: {clock7.line(rows[0])}). "
        if news:
            body += news + "."
        return {"ready": ready, "title": title, "body": body.strip(), "fixes": fixes, "clock": rows, "arms": A, "news": news}
    except Exception as ex:  # noqa: BLE001
        return {"ready": False, "title": "Preflight could not run", "body": f"{ex.__class__.__name__}: double-click HEALTH CHECK.",
                "fixes": [], "clock": [], "arms": [], "news": ""}


def clock_line(hb, now, ext: dict | None = None) -> str:
    """' 7-day clock: ...' for the weekday pre-session notice: the amber / red accounts only ('' when all are fine)."""
    try:
        from . import clock7
        k7 = clock7.build(_d(ext if ext is not None else last_ext()).get("mf"), _d(hb).get("keepalive"), now)
        bad = [clock7.line(r) for r in _l(_d(k7).get("a")) if r.get("lvl") in ("warn", "bad")]
        return (" 7-day clock: " + "; ".join(bad[:2]) + ".") if bad else ""
    except Exception:
        return ""


def notice(checks: list, hb, now, ext: dict | None = None) -> dict:
    """The ops payload (engine/ops_checks._payload) for the Sunday preflight: key ops:sun:<ET date>, sent once."""
    from .ops_checks import _payload
    p = build(checks, hb, now, last_ext() if ext is None else ext)
    return _payload("sun", p["title"], p["body"], f"ops:sun:{_et(now).date().isoformat()}", now)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    from . import ops_checks as OC
    now = time.time()
    ctx = OC.gather(now)
    checks = OC.run_checks(ctx)
    p = build(checks, ctx.get("hb"), now, last_ext())
    print(("READY  " if p["ready"] else "FIX    ") + p["title"])
    print(p["body"])
    for f in p["fixes"][1:]:
        print(" - " + f)
    if "--send" in argv:
        st = OC.load_state()
        r = OC.send(notice(checks, ctx.get("hb"), now), st)
        OC.save_state(st)
        print("sent" if r.get("sent") else f"not sent: {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
