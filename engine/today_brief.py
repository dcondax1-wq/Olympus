"""'Where are we' in one Telegram reply (day-guard2 2026-11-26): engine/tg_cmd's /today. READ-ONLY: it only reads the running
server's live view (engine/live_site cache = what the phone shows), the payout autopilot's views and the news calendar.

  Today Thu Nov 26 · 11:20 ET
  PC: bot running (LIVE)
  Zlarior 50K: $49,193 · today +$0 · $3,807 to pass · $1,025 left (floor)
  ATLAS 25K funded: $26,946 · today +$120 · $890 left (floor) · payout requestable now: $1,000 ($800 to you)
  Open trade: none
  Setup: LIT watching the levels
  News today: none big · Tomorrow (Fri): no big US news.
Hidden bots (BLITZ) are never named; account names are the owner's words (ids masked). Never raises: a missing part says so.
Tests: tests/test_guard2.py.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MAX_CHARS = 1500
STAGES = {"levels": "LIT watching the levels", "sweep": "LIT: a sweep, waiting for the shift", "limit": "LIT setup ARMED: limit order waiting",
          "cisd1m": "LIT setup ARMED: waiting for the 1m confirmation", "trade": "LIT in a trade", "done": "LIT done for today",
          "closed": "market closed"}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _f(x):
    try:
        return None if x is None or isinstance(x, bool) else float(x)
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = _f(x)
    return "?" if v is None else ("-" if v < 0 else "") + f"${abs(v):,.0f}"


def signed(x) -> str:
    v = _f(x)
    return "?" if v is None else ("+" if v >= 0 else "-") + f"${abs(v):,.0f}"


def _news_today(now, root=None) -> str:
    try:
        from . import notify
        day = dt.datetime.fromtimestamp(int(now), ET).date()
        rows = notify.news_on(day, root) if root else notify.news_on(day)
        hm = dt.datetime.fromtimestamp(int(now), ET).strftime("%H:%M")
        left = [f"{title} {t}" for t, title in rows if str(t) >= hm][:3]
        today = ("News today: " + ", ".join(left)) if left else "News today: none big left"
        return today + " · " + (notify.news_line(now, root) if root else notify.news_line(now))
    except Exception:  # noqa: BLE001
        return "News: calendar not readable"


def text(live, now=None, views=None, root=None, plan_rows=None) -> str:
    """The /today reply + the payout forecast (big-payout, engine/payout_engine) + the PC's key line (red team 2026-11-26,
    key_line). Never raises."""
    out = _text(live, now, views, root)
    pl = payout_forecast(plan_rows)
    kl = key_line()
    tail = "\n".join(x for x in (pl, kl) if x)
    return (out[:MAX_CHARS - len(tail) - 1] + "\n" + tail) if tail else out


def payout_forecast(rows=None) -> str:
    """big-payout 2026-11-26: for each funded account NOT ready today, the next payout's $, the date at its own pace (an
    estimate), the buffer to keep and what blocks it (engine/payout_engine, read-only). '' when there is nothing to say."""
    try:
        from . import payout_engine as PE
        rows = PE.gather() if rows is None else rows
        out = []
        for r in rows:
            if r.get("ready") or not r.get("next_date"):
                continue
            b = "; ".join((r.get("blocks") or [])[:1])
            out.append(f"Next payout {r['name']}: {PE.usd(r.get('next_amount'))} about {r['next_date']} "
                       f"({PE.usd(r.get('to_you'))} to you), keep {PE.usd(r.get('keep_balance'))}" + (f"; {b}" if b else ""))
        return "\n".join(out[:3])
    except Exception:  # noqa: BLE001
        return ""


def _text(live, now=None, views=None, root=None) -> str:
    """The /today reply. live = the server's live view (None = the bot server has no numbers). Never raises."""
    import time
    now = int(now or time.time())
    e = dt.datetime.fromtimestamp(now, ET)
    lines = [f"Today {e:%a %b %d} · {e:%H:%M} ET"]
    try:
        live = _d(live)
        if not live:
            lines.append("PC: the bot server has no live numbers right now (stopped or starting). /status says more.")
            lines.append(_news_today(now, root))
            return "\n".join(lines)[:MAX_CHARS]
        pc = _d(live.get("pc"))
        mode = str(live.get("mode") or "").upper()
        run = pc.get("running")
        lines.append("PC: " + ("bot running" if run else "bot STOPPED" if run is False else "bot state unknown")
                     + (f" ({mode})" if mode else ""))
        from . import risk_alarm
        dist = {r["id"]: r for r in risk_alarm.rows(live)}
        hide = set(risk_alarm._hidden())
        bd = _d(live.get("board"))
        accts = []
        for k, nm in (("lit", "Zlarior 50K"), ("atlas", "ATLAS 25K")):
            c = _d(bd.get(k))
            if not c or k in hide or c.get("error") or c.get("off") or (k != "lit" and c.get("configured") is False):
                continue
            funded = str(c.get("status") or "").lower() == "funded" or c.get("stage") == "funded"
            accts.append((k, nm + (" funded" if funded else ""), c.get("balance"), c.get("today_pnl"),
                          None if funded else c.get("to_target"), funded, c.get("status")))
        for a in live.get("accounts") or []:
            a = _d(a)
            aid = str(a.get("id") or "")
            if not a.get("extra") or not aid or aid in hide or aid == "acct_c" or a.get("kind") not in ("eval", "funded"):
                continue
            ev = _d(a.get("eval"))
            try:
                from . import mffu_view, notify
                nm = notify.mask_ids(mffu_view.owner_name(aid, a.get("name"), a.get("plan"), a.get("kind")))[:40]
            except Exception:  # noqa: BLE001
                nm = "Extra account"
            funded = a.get("kind") == "funded"
            accts.append((aid, nm, ev.get("balance"), _d(a.get("pnl")).get("today", ev.get("today")),
                          None if funded else ev.get("to_target"), funded, ev.get("status")))
        if not accts:
            lines.append("Accounts: none with numbers yet")
        for aid, nm, bal, td, to_pass, funded, status in accts:
            bits = [f"{nm}: {money(bal)}", f"today {signed(td)}"]
            st = str(status or "").lower()
            if st in ("passed", "failed", "lost"):
                bits.append(st.upper())
            elif to_pass is not None:
                bits.append(f"{money(to_pass)} to pass")
            r = dist.get(aid)
            if r:
                bits.append(f"{money(r['left'])} left ({'daily limit' if r['limit'] == 'day' else 'floor'})")
            if funded:
                pl = risk_alarm.payout_line(aid, views)
                if pl:
                    bits.append(pl)
            lines.append(" · ".join(bits))
        pos = _d(pc.get("position"))
        if pos:
            side = str(pos.get("side") or pos.get("dir") or "").upper()
            qty = pos.get("qty") or pos.get("size")
            px = _f(pos.get("entry") or pos.get("avg_price"))
            un = _f(pos.get("unrealized_usd"))
            lines.append("Open trade: " + " ".join(x for x in (side, f"{qty} MNQ" if qty else "", f"@ {px:,.2f}" if px else "",
                                                             f"({signed(un)} open)" if un is not None else "") if x))
        else:
            lines.append("Open trade: none")
        stage = str(_d(_d(pc.get("health")).get("lit")).get("stage") or "")
        lines.append("Setup: " + (STAGES.get(stage) or (str(pc.get("model_state") or "")[:90] or "no setup info")))
        lines.append(_news_today(now, root))
    except Exception as ex:  # noqa: BLE001
        lines.append(f"(part of the summary failed: {ex.__class__.__name__})")
    out = "\n".join(lines)
    try:
        from . import notify
        out = notify.mask_ids(out)
    except Exception:  # noqa: BLE001
        pass
    return out[:MAX_CHARS]


def key_line() -> str:
    """red team 2026-11-26: this PC's status-signing key, first 6 letters (public, never the private key). The phone's 'Your PC's
    signing key changed?' banner (tools/web_public/pc_key_trust.js) names a new key by the same 6 letters: /today comes from the
    owner's own Telegram chat, so it is the one place an attacker cannot fake to compare. '' when the PC has no key."""
    try:
        import os
        import sys
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools import status_sign as S
        k = S.load_key()
        return f"PC signing key: {S.vk_of(k)[:6]}" if k else ""
    except Exception:  # noqa: BLE001
        return ""
