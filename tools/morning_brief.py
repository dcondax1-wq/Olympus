"""MORNING BRIEF (2026-11-18; night-brief 2026-11-23; night-briefv2 2026-11-23: the PUSHED message is build() = the day in
5 lines, money first: Yesterday $ per account + total / Room to max loss (LOW under $500) / Keep-alive act days today / News +
the T1 blackout / Bot READY + armed. The detailed version below is build_full(), the PC's dry look):
  READY / NOT READY + the first blocker's fix (engine/readiness via the "rd" block; a PC problem / an old report = NOT READY)
  one line per account: armed, $, room, yesterday's $ (the previous CME session), $ to pass / to payout / payout READY $, the MFFU
  7-day deadline when 3 days or fewer are left
  Today: the bots' hours, today's big news, the T1 ban times (Rapid funded: flat -2/+2 min), an early close, overnight trades
  Next money move: engine/fleet_mgr's next move
  Edge · Needs you · Decide cards waiting: N (tools/web_public/business/decisions.json)
The evening half is tools/pc_guard.day_summary (16:15 ET): the day's $ per account + the payouts ready + "Tomorrow: <next move>" +
the day's low-priority lines (engine/alert_bus.digest_peek), ONE message (the 16:20 digest sends nothing on a trading day).
Tests: python -X utf8 -m tests.test_daily_brief, tests.test_notify (section h).

The 2026-11-18 version (kept below for the sources): one short ZEUS push at about 07:30 ET on CME trading days, in the owner's "important only" set
(notify_settings.json type morning_brief, ON by default; morning_brief_at = the time). Four lines, phone-sized:

  ZEUS - Wed Nov 18 - PC ok                                                  (the title)
  Zlarior 50K $49,193 ($3,807 to pass) · 25K #2 $25,000 ($1,500 to pass) · ATLAS 25K funded $401 ($1,699 to payout: $1,000 at $2,100)
  Overnight: no trades · Today: Zlarior till 15:30, ATLAS till 12:00 · CPI 08:30
  Edge: GREEN · Needs you: none

Sources = the bot's own state the PC report already has (the same as the 16:15 day summary, tools/pc_guard.day_summary): the
accounts as the Board shows them (engine/board_events rows fed by the PC's live cards + accounts, matched by PC id like
tools/board.lite_live), the funded payout tracker (engine/funded_life via the cards), the edge light (data/edge/tiny.json, the
status key "eh"), today's big US news (engine/notify.news_on), the CME calendar (engine/cme_calendar: full closures skipped,
an early close shortens the windows), the contract roll (engine/roll_watch) and the PC's problems (tools/pc_report.conditions).
No account id: names only, any long digit run cut to its last 4.

Called by tools/pc_guard.guard every report run (15 min); the key guard:brief:<day> is sent once (pc_report keeps it in its
state.json, so a restart never repeats it; a failed POST is retried by the next run). Window: morning_brief_at (07:30) up to
09:30 ET, weekdays that are not a CME full closure. Also ONE Board event a day (kind "brief", engine/board_events.emit), only
from the real report (LE_PC_REPORT=1, set by pc_report.main) or a test's own LE_BOARD_DIR, never twice for the same day.
Read only: it never places, changes or arms anything. Tests: python -X utf8 -m tests.test_notify (section h).
"""
from __future__ import annotations

import datetime as dt
import os
import re
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PREFIX = "guard:brief:"
BRIEF_FROM, BRIEF_TO = 7 * 60 + 30, 9 * 60 + 30
HB_FRESH_S = 900
LIT_WINDOW = (120, 930)
ATLAS_WINDOWS = {"ema_lon_vix": [(180, 570)], "macd_sweep": [(120, 300), (570, 660)], "sr_nyreclaim": [(570, 720)]}
ATLAS_NO_MONDAY = {"ema_lon_vix"}
try:                                                  # the bots' real entry hours (one source); the copies above if it fails
    from engine.live_board import ATLAS_NO_MONDAY, ATLAS_WINDOWS, LIT_WINDOW  # noqa: F811
except Exception:  # noqa: BLE001
    pass
COND_WORD = {"bot_down": ("bot down", "STOP BOT, START BOT"), "bot_stopped": ("bot stopped", "START BOT"),
             "nt_down": ("NinjaTrader closed", "open NinjaTrader"), "feed_stale": ("FEED STALE", "re-add LE_BarFeed")}
WORD = {"G": "GREEN", "A": "AMBER", "R": "RED"}
CARD_NAME = {"lit": "Zlarior", "atlas": "ATLAS"}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = _f(x)
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def signed(x) -> str:
    v = _f(x)
    return "-" if v is None else ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(round(v)))


def _hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def safe(s, n: int = 40) -> str:
    """A name for the phone: any run of 5+ digits (a broker account id) cut to its last 4."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return re.sub(r"[A-Za-z]*\d{5,}", lambda m: "..." + re.sub(r"\D", "", m.group(0))[-4:], s)[:n]


def _settings() -> dict:
    try:
        from engine import notify
        return notify.settings()
    except Exception:  # noqa: BLE001
        return {}


def _et(now) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(now), ET)


def due(now, s: dict | None = None) -> bool:
    """07:30 (morning_brief_at) up to 09:30 ET on a weekday that is not a CME full closure."""
    e = _et(now)
    try:
        from engine import notify
        frm = notify.hm_min((s or _settings()).get("morning_brief_at"), BRIEF_FROM)
    except Exception:  # noqa: BLE001
        frm = BRIEF_FROM
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (frm <= m < max(BRIEF_TO, frm + 60)):
        return False
    try:
        from engine import cme_calendar
        return not cme_calendar.full_closure(e.date())
    except Exception:  # noqa: BLE001
        return True


def key(now) -> str:
    return PREFIX + _et(now).date().isoformat()


# ------------------------------------------------------------------------------------------------ the accounts (Board rows)
def _plan_accounts(plan_doc) -> list:
    return [a for a in _l(_d(plan_doc).get("accounts")) if isinstance(a, dict) and a.get("key")]


def _sources(L: dict, pa: list) -> dict:
    """{plan key: the PC's own card / account dict} (the payout tracker, the position, the quiet days)."""
    from engine import board_events as B
    out = {}
    bd = _d(L.get("board"))
    for ck in ("lit", "atlas"):
        c = _d(bd.get(ck))
        if c and not c.get("error"):
            out.setdefault(B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck), {**c, "_card": ck})
    for a in _l(L.get("accounts")):
        a = _d(a)
        if a.get("id") and a.get("kind") in ("eval", "funded") and a.get("source") not in ("cloud", "pc_blitz") and a.get("id") != "acct_c":
            k = B.plan_key(pa, a.get("id"), a.get("name")) or str(a["id"])
            out.setdefault(k, {**a, "_acct": str(a["id"])})
    return out


def rows(snap: dict, now: int, plan_doc=None, events=None) -> list:
    """The Board's account rows (engine/board_events.build) with the PC's live numbers, planned rows and rows without a
    balance left out, each with its PC source under "_src"."""
    from engine import board_events as B
    try:
        from tools import board as TB
    except Exception:  # noqa: BLE001
        TB = None
    plan_doc = B.plan() if plan_doc is None else plan_doc
    pa = _plan_accounts(plan_doc)
    L = _d(snap.get("live"))
    live = TB.lite_live(L, pa) if TB else {}
    if snap.get("hb_t"):
        for v in live.values():
            v["t"] = max(_f(v.get("t")) or 0, float(snap["hb_t"]))
    board = B.build(events=events, plan_doc=plan_doc, live=live, pc={"t": snap.get("hb_t"), "via": "this PC"}, now=now)
    src = _sources(L, pa)
    out = []
    for r in board.get("accounts") or []:
        if r.get("chip") == "planned" or _f(r.get("balance")) is None:
            continue
        out.append({**r, "_src": src.get(r.get("key")) or {}})
    first = {}                                        # the same bot's accounts side by side ("Zlarior 50K · 25K #2 · ATLAS ...")
    for r in out:
        first.setdefault(label(r).split(" ")[0], len(first))
    return sorted(out, key=lambda r: first[label(r).split(" ")[0]])


def label(r: dict) -> str:
    name = safe(r.get("name") or r.get("key"), 30)
    size = re.search(r"(\d+K)", str(r.get("plan") or ""))
    if size and size.group(1).lower() not in name.lower():
        name = f"{name} {size.group(1)}"
    return name


def short_labels(rs: list) -> list:
    """'Zlarior 50K', 'Zlarior 25K #2' -> 'Zlarior 50K', '25K #2' (the name once in a row)."""
    out, prev = [], None
    for r in rs:
        lab = label(r)
        first = lab.split(" ", 1)
        if prev and len(first) == 2 and first[0] == prev:
            out.append(first[1])
        else:
            out.append(lab)
        prev = first[0]
    return out


def funded_part(r: dict) -> tuple:
    """(' ($2,100 to payout)' / ' (payout READY $1,000)', need-you text or None) from the funded payout tracker."""
    s = _d(r.get("_src"))
    f = _d(s.get("funded"))
    if not f:
        return "", None
    if f.get("lost"):
        return " (floor reached)", None
    if f.get("ready"):
        amt = _f(f.get("max_request"))
        return f" (payout READY {money(amt)})", f"request the {label(r)} payout" + (f" {money(amt)}" if amt else "")
    ta = _f(f.get("to_ask"))
    if ta is None:
        ta = _f(s.get("to_target")) if s.get("_card") == "atlas" else None
    return (f" ({money(ta)} to payout)" if ta is not None and ta > 0 else ""), None


def payday_line(rs: list) -> str:
    """'REQUEST PAYOUT TODAY: ATLAS 25K $1,000 ($800 to you) - MFFU dashboard > Payouts, then TRADE_HOME -> P' for every funded account
    whose tracker says ready (MFFU's rules AND the owner's plan: the max request), else ''. A Builder's #5 is never ready (funded_life)."""
    out = []
    for r in rs:
        f = _d(_d(r.get("_src")).get("funded"))
        amt = _f(f.get("max_request"))
        if f.get("ready") and not f.get("lost") and amt and amt > 0:
            ty = _f(f.get("to_you"))
            out.append(f"{label(r)} {money(amt)}" + (f" ({money(ty)} to you)" if ty else ""))
    if not out:
        return ""
    return "REQUEST PAYOUT TODAY: " + ", ".join(out) + " - MFFU dashboard > Payouts, then TRADE_HOME -> P"


def accounts_line(rs: list, hb_fresh: bool = True) -> tuple:
    """(line, [needs you]). hb_fresh False (the bot's last report is old): a keep-alive "cover" never hides the 7-day line."""
    parts, needs = [], []
    for r, lab in zip(rs, short_labels(rs)):
        bal = money(r.get("balance"))
        st = str(r.get("stage") or "eval")
        if r.get("locked"):
            parts.append(f"{lab} LOCKED {bal}")
            needs.append(f"{label(r)} locked: check MFFU")
        elif st == "failed":
            parts.append(f"{lab} failed")
        elif st == "passed":
            parts.append(f"{lab} PASSED {bal}")
            needs.append(f"{label(r)} passed: send Claude the funded name")
        elif st == "funded":
            tail, need = funded_part(r)
            parts.append(f"{lab} funded {bal}{tail}")
            if need:
                needs.append(need)
        else:
            tp = _f(r.get("to_pass"))
            parts.append(f"{lab} {bal}" + (f" ({money(tp)} to pass)" if tp is not None and tp > 0 else ""))
        q = _f(_d(r.get("_src")).get("quiet_days"))      # (counts a keep-alive / hand trade noted: engine/keepalive)
        ka_cover = hb_fresh and bool(_d(_d(r.get("_src")).get("keepalive")).get("cover"))   # the RUNNING bot's keep-alive
        #                                                    warns for it itself (the board card's cover is fresh-checked too)
        if q is not None and q >= 6 and st in ("eval", "funded") and not r.get("locked") and not ka_cover:
            needs.append(f"{label(r)} {int(q)} days without a trade: 1 MNQ by hand")
    return (" · ".join(parts) if parts else "No account numbers in the last report"), needs


# ------------------------------------------------------------------------------------------------ overnight
def session_start(now) -> int:
    """18:00 ET the evening before today's CME trading date."""
    e = _et(now)
    d = e.date() if e.hour < 18 else e.date() + dt.timedelta(days=1)
    s = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(18, 0), ET)
    return int(s.timestamp())


def prev_session(now) -> tuple:
    """(t0, t1) of the trading session before today's: 18:00 ET the evening before the previous CME trading date -> its 17:00."""
    try:
        from engine import cme_calendar as C
        closed = C.full_closure
    except Exception:  # noqa: BLE001
        closed = lambda d: False  # noqa: E731
    d = dt.datetime.fromtimestamp(session_start(now), ET).date() + dt.timedelta(days=1)    # today's trading date
    p = d - dt.timedelta(days=1)
    while p.weekday() >= 5 or closed(p):
        p -= dt.timedelta(days=1)
    t0 = int(dt.datetime.combine(p - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
    return t0, int(dt.datetime.combine(p, dt.time(17, 0), ET).timestamp())


def day_pnl(snap: dict, now: int, rs: list, plan_doc=None, t0=None, t1=None) -> dict:
    """{board key: (n trades, $)} of the CLOSED real trades between t0 and t1 (paper left out). Never raises."""
    try:
        per, _o, _n = _trades(snap, now if t1 is None else t1, rs, plan_doc, t0)
        return per
    except Exception:  # noqa: BLE001
        return {}


def overnight(snap: dict, now: int, rs: list, plan_doc=None) -> str:
    """'no trades' / 'Zlarior +$605 (1 trade)' / '... · ATLAS SHORT open' since 18:00 ET (paper left out)."""
    per, opened, nm = _trades(snap, now, rs, plan_doc, session_start(now))
    bits = [f"{nm(k)} {signed(s)} ({n} trade{'s' if n != 1 else ''})" for k, (n, s) in per.items()]
    bits += [f"{nm(k)} {side or 'trade'} open".replace("  ", " ") for k, side in opened]
    return ", ".join(bits) if bits else "no trades"


def _trades(snap: dict, now: int, rs: list, plan_doc, t0) -> tuple:
    """(per {key: (n, $)}, opened [(key, side)], name fn) of the real trades between t0 and now."""
    from engine import board_events as B
    pa = _plan_accounts(plan_doc if plan_doc is not None else B.plan())
    names = dict(zip([r.get("key") for r in rs], short_labels(rs)))
    L = _d(snap.get("live"))
    per, seen, opened = {}, set(), []

    def add(k, t):
        t = _d(t)
        if str(t.get("src") or "") == "paper":
            return
        et_ = int(_f(t.get("entry_t")) or 0)
        xt = int(_f(t.get("exit_t")) or 0)
        if max(et_, xt) < t0 or max(et_, xt) > now:
            return
        if (k, et_) in seen:
            return
        seen.add((k, et_))
        if t.get("open") or str(t.get("exit_kind") or t.get("exit") or "").upper() == "OPEN":
            opened.append((k, str(t.get("side") or "").upper()))
            return
        v = _f(t.get("usd"))
        v = _f(t.get("pnl")) if v is None else v
        if v is None:
            return
        n, s = per.get(k, (0, 0.0))
        per[k] = (n + 1, s + v)

    bd = _d(L.get("board"))
    for t in _l(bd.get("trades")):
        ck = str(_d(t).get("acct") or "")
        add(B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck), t)
    for a in _l(L.get("accounts")):
        a = _d(a)
        if not a.get("id") or a.get("source") in ("cloud", "pc_blitz") or a.get("id") == "acct_c":
            continue
        k = B.plan_key(pa, a.get("id"), a.get("name")) or str(a["id"])
        for t in _l(a.get("trades")):
            add(k, t)
    for ck in ("lit", "atlas"):                      # an open position the trade list does not carry yet
        p = _d(_d(bd.get(ck)).get("position"))
        k = B.plan_key(pa, ck, "") or {"lit": "zlarior"}.get(ck, ck)
        if p and not any(x[0] == k for x in opened):
            opened.append((k, str(p.get("side") or "").upper()))
    nm = lambda k: names.get(k) or CARD_NAME.get(k) or safe(k, 20)   # noqa: E731
    return per, opened, nm


# ------------------------------------------------------------------------------------------------ today
def _merge(rs: list) -> list:
    out = []
    for a, z in sorted(rs):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], z)
        else:
            out.append([a, z])
    return out


def windows_line(now: int) -> str:
    """'Zlarior till 15:30, ATLAS till 12:00' (what is left of today's entry hours; an early close ends them 15 min before)."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    try:
        from engine import cme_calendar
        cut = cme_calendar.entry_cut(e.date(), 24 * 60)
    except Exception:  # noqa: BLE001
        cut = 24 * 60
    bots = (("Zlarior", [LIT_WINDOW]),
            ("ATLAS", [w for k, ws in ATLAS_WINDOWS.items() for w in ws if not (e.weekday() == 0 and k in ATLAS_NO_MONDAY)]))
    out = []
    for name, ws in bots:
        left = [[max(a, m), min(z, cut)] for a, z in ws if min(z, cut) > max(a, m)]
        segs = _merge(left)
        if not segs:
            out.append(f"{name} done")
            continue
        out.append(name + " " + ", ".join(("till " + _hm(z)) if a <= m else f"{_hm(a)}-{_hm(z)}" for a, z in segs))
    return ", ".join(out)


def news_today(now: int, root: str | None = None, n: int = 2) -> str:
    """'CPI 08:30' (today's high-impact US releases, the big ones first, n at most) or ''."""
    try:
        from engine import notify
        rs = notify.news_on(_et(now).date(), root or notify.ROOT)
        big = [r for r in rs if any(w in r[1].lower() + " " for w in notify.NEWS_WORDS)] or rs
    except Exception:  # noqa: BLE001
        return ""
    paren = re.compile(r"\s*\(.*?\)")
    txt = ", ".join((paren.sub("", title).strip()[:24] + " " + t).strip() for t, title in big[:n])
    return txt + (f" (+{len(big) - n})" if len(big) > n else "")


def early_note(now: int) -> str:
    try:
        from engine import cme_calendar
        ec = cme_calendar.early_close(_et(now).date())
    except Exception:  # noqa: BLE001
        ec = None
    return f"early close {_hm(ec)}" if ec else ""


# ------------------------------------------------------------------------------------------------ edge, PC, roll
def edge_text(snap: dict) -> str:
    eh = _d(snap.get("eh"))
    z, a = _l(eh.get("z")), _l(eh.get("a"))
    lz = WORD.get(z[0]) if z else None
    la = WORD.get(a[0]) if a else None
    if not lz:
        return "no reading"
    if not la or la == lz:
        return lz
    return f"Zlarior {lz}, ATLAS {la}"


def pc_text(snap: dict) -> tuple:
    """('PC ok' / 'PC: bot down' / 'PC: last report 40 min old', [needs you])."""
    cond = _d(snap.get("cond"))
    age = snap.get("hb_age")
    needs = [f"{COND_WORD[c][0]}: {COND_WORD[c][1]}" for c in COND_WORD if c in cond]
    if needs:
        return "PC: " + COND_WORD[next(c for c in COND_WORD if c in cond)][0], needs
    if age is None:
        return "PC: no bot report", ["check the PC: tools/bat/STATUS.bat"]
    if age > HB_FRESH_S:
        return f"PC: last report {int(age) // 60} min old", ["check the PC: tools/bat/STATUS.bat"]
    return "PC ok", []


def roll_needs(snap: dict, now: int) -> list:
    try:
        from engine import roll_watch
        st = snap.get("roll")
        st = st if isinstance(st, dict) else roll_watch.fact(None, {}, now)
        ms = roll_watch.countdown(st, now)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in ms:
        k = str(m.get("key") or "")
        if k.startswith("roll:late:"):
            out.append("contract roll late: tools/bat/ROLL.bat")
        elif k.startswith("roll:soon:") and m.get("priority") == "high":
            out.append("contract roll tonight: tools/bat/ROLL.bat after 16:00")
    return out


# ------------------------------------------------------------------------------------------------ the message
MAX_LINES = 8                       # night-brief 2026-11-23: the owner reads ONE message and does nothing else
IDLE_LIMIT = 7                      # MFFU's inactivity rule (calendar days)
IDLE_SHOW = 3                       # show the 7-day deadline when 3 days or fewer are left


def ready_line(snap: dict, pc: str, pc_needs: list) -> tuple:
    """('READY for 02:00' / 'NOT READY: <blocker>. Fix: <fix>', title word) from engine/readiness's last verdict (the status post's
    "rd" block: s ok | warn | no, w, b, f); a PC problem (bot down, NinjaTrader closed) or an old report wins."""
    if pc != "PC ok":
        fix = pc_needs[0].split(": ", 1)[-1] if pc_needs else "check the PC: tools/bat/STATUS.bat"
        return f"NOT READY: {pc.replace('PC: ', '')}. Fix: {fix}", "NOT READY"
    rd = _d(snap.get("rd"))
    st, w = rd.get("s"), (f" for {rd['w']}" if rd.get("w") else "")
    if st == "no":
        return (f"NOT READY{w}: {safe(rd.get('b') or 'see the PC', 80)}. Fix: {safe(rd.get('f') or 'double-click HEALTH_CHECK.bat', 90)}",
                "NOT READY")
    if st == "warn":
        return f"READY{w}, 1 to watch: {safe(rd.get('b') or 'see the PC', 80)}", "READY"
    if st == "ok":
        return f"READY{w}: PC, clock, NinjaTrader, bars and accounts checked", "READY"
    return "PC ok (no readiness check in the last report)", "PC ok"


def account_line(r: dict, lab: str, yday, hb_fresh: bool) -> tuple:
    """'Zlarior 50K armed · $49,193 · room $1,025 · yesterday +$300 · $3,807 to pass' (+ the payout / 7-day parts). -> (line, needs)."""
    src = _d(r.get("_src"))
    ev = _d(src.get("eval"))
    badge = str(src.get("badge") or "").upper()
    st = str(r.get("stage") or "eval")
    needs = []
    bits = [lab + (" armed" if badge == "LIVE" else f" NOT armed ({badge.lower()})" if badge else "")]
    bits.append(money(r.get("balance")))
    room = _f(src.get("room"))
    room = _f(ev.get("room")) if room is None else room
    if r.get("locked"):
        bits.append("LOCKED by MFFU")
        needs.append(f"{label(r)} locked: check MFFU")
    elif st == "failed":
        bits.append("failed")
    elif st == "passed":
        bits.append("PASSED")
        needs.append(f"{label(r)} passed: tap it on the Start page when MFFU issues it")
    if room is not None and st in ("eval", "funded") and not r.get("locked"):
        bits.append(f"room {money(room)}")
    if yday is not None:
        bits.append(f"yesterday {signed(yday[1])}" + (f" ({yday[0]} trades)" if yday[0] > 1 else ""))
    if st == "funded":
        tail, need = funded_part(r)
        if tail:
            bits.append(tail.strip(" ()"))
        if need:
            needs.append(need)
    elif st == "eval":
        tp = _f(r.get("to_pass"))
        if tp is not None and tp > 0:
            bits.append(f"{money(tp)} to pass")
    q = _f(src.get("quiet_days"))
    ka_cover = hb_fresh and bool(_d(src.get("keepalive")).get("cover"))
    if q is not None and st in ("eval", "funded") and not r.get("locked"):
        left = IDLE_LIMIT - int(q)
        if left <= IDLE_SHOW and not ka_cover:
            bits.append(f"MFFU 7-day: trade within {max(0, left)} day(s)")
            if left <= 1:
                needs.append(f"{label(r)} {int(q)} days without a trade: 1 MNQ by hand")
    return " · ".join(bits), needs


def news_bans(now: int) -> str:
    """'T1 news ban (Rapid funded, flat -2/+2 min): 08:30' or '' (engine/multi_account.tier1_releases)."""
    try:
        from engine.multi_account import tier1_releases
        rel = sorted(tier1_releases(_et(now).date().isoformat()))
        if not rel:
            return ""
        return "T1 news ban (Rapid funded, flat -2/+2 min): " + ", ".join(f"{_et(r):%H:%M}" for r in rel[:3])
    except Exception:  # noqa: BLE001
        return ""


def fleet_line() -> str:
    """The fleet manager's next money move (engine/fleet_mgr: its last tick's tiny), '' when none."""
    try:
        from engine import fleet_mgr as FM
        t = FM.read_tiny() or {}
        s = str(t.get("s") or "")
        return s.split("Next: ", 1)[1] if "Next: " in s else ""
    except Exception:  # noqa: BLE001
        return ""


def cards_waiting(path: str | None = None) -> int:
    """Decide cards still open (tools/web_public/business/decisions.json). 0 when unreadable."""
    try:
        from engine import fleet_mgr as FM
        return sum(1 for v in FM.cards(path).values() if v == "open")
    except Exception:  # noqa: BLE001
        return 0


def build_full(snap: dict, now: int | None = None, plan_doc=None, events=None, root: str | None = None, fleet: str | None = None,
               waiting: int | None = None, lvb: str | None = None) -> dict:
    """The detailed brief (night-brief, up to 8 lines; the PC's dry look and TRADE_HOME): {"title", "body", "lines" (<= MAX_LINES), "day"}: line 1 READY / NOT READY (+ the fix), one line per account (armed, $,
    room, yesterday $, $ to pass / to payout / payout READY, the MFFU 7-day deadline when <= 3 days), Today (hours, news, the T1
    ban, an early close), the next money move (engine/fleet_mgr), then edge + needs you + decide cards waiting. Never raises on
    a bad snapshot (a part that fails says so)."""
    now = int(now if now is not None else snap.get("t"))
    e = _et(now)
    pc, needs = pc_text(snap)
    try:
        rs = rows(snap, now, plan_doc, events)
    except Exception as x:  # noqa: BLE001
        rs = []
        needs.append(f"brief: accounts not readable ({x.__class__.__name__})")
    age = snap.get("hb_age")
    fresh = age is not None and age <= HB_FRESH_S
    rl, word = ready_line(snap, pc, needs)
    t0, t1 = prev_session(now)
    yd = day_pnl(snap, now, rs, plan_doc, t0, t1)
    acc = []
    for r, lab in zip(rs, short_labels(rs)):
        ln, n2 = account_line(r, label(r), yd.get(r.get("key")), fresh)
        if not fresh and age is not None:        # red team 2: never an old number shown as today's
            ln += f" · as of {int(age) // 3600} h {int(age) % 3600 // 60} min ago"
        acc.append(ln)
        needs += n2
    if not acc:
        acc = ["No account numbers in the last report"]
    # night-payday 2026-11-23 (lead: "money in hand is the goal"): a payout MFFU pays today is its own line, right under READY, in the
    # same words as the phone push ("REQUEST PAYOUT TODAY: ATLAS 25K $1,000"); every brief until the owner records it (TRADE_HOME -> P)
    pay = payday_line(rs) if fresh else ""
    if pay:
        needs = [n for n in needs if not str(n).startswith("request the ")]
    if lvb is None:                                  # night-livevsbt: live vs backtest, from the last daily check (read only)
        try:
            from engine import live_vs_bt as _lvb
            lvb = _lvb.last_line(now)
        except Exception:  # noqa: BLE001
            lvb = ""
    keep = MAX_LINES - 4 - (1 if pay else 0) - (1 if lvb else 0)   # READY + Today + Next + Needs (+ payout, + live vs backtest)
    if len(acc) > keep:
        acc = acc[:keep - 1] + [f"+{len(acc) - keep + 1} more accounts: TRADE_HOME -> 1 (Status)"]
    try:
        ov = overnight(snap, now, rs, plan_doc)
    except Exception:  # noqa: BLE001
        ov = "not readable"
    extra = [x for x in (news_today(now, root), news_bans(now), early_note(now)) if x]
    today = f"Today: {windows_line(now)}" + "".join(f" · {x}" for x in extra) + (f" · overnight {ov}" if ov != "no trades" else "")
    mv = fleet_line() if fleet is None else fleet
    needs += roll_needs(snap, now)
    nd = ", ".join(needs[:2]) + (f" (+{len(needs) - 2} more)" if len(needs) > 2 else "") if needs else "none"
    nw = cards_waiting() if waiting is None else int(waiting)
    lines = [rl] + ([pay] if pay else []) + acc + ([lvb] if lvb else []) + [today] + ([f"Next money move: {mv}"] if mv else []) + \
            [f"Edge {edge_text(snap)} · Needs you: {nd}" + (f" · Decide cards waiting: {nw}" if nw else "")]
    title = f"ZEUS - {e:%a %b} {e.day} - {word}" + (" - REQUEST PAYOUT TODAY" if pay else "")
    lines = [ln[:400] for ln in lines[:MAX_LINES]]       # red team 2: the body = the 8 lines, under the 4,096 B push limit
    return {"title": title, "body": "\n".join(lines)[:3900], "lines": lines, "day": e.date().isoformat(), "needs": len(needs)}


# ------------------------------------------------------------------------------------------------ the 5-line brief (night-briefv2)
FIVE = 5
LOW_ROOM = 500.0                      # "near max loss": room to MFFU's floor under this (about one full LIT stop-out at eval size)


def _ka_today(r: dict, now: int):
    """(act today?, on?, window text) for one account from its card's keep-alive block (last fill / hand day) or its quiet days,
    through engine/keepalive.plan (the same act day the bot uses). (False, ..) when unknown. Never raises."""
    try:
        from engine import keepalive as KA
        src = _d(r.get("_src"))
        kb = _d(src.get("keepalive"))
        last = kb.get("last")
        q = _f(src.get("quiet_days"))
        if not last and q is not None:
            last = (_et(now).date() - dt.timedelta(days=int(q))).isoformat()
        if not last:
            return False, bool(kb.get("on")), ""
        P = KA.plan(last, now)
        today = _et(now).date().isoformat()
        act = str(P.get("act_day") or "") == today or bool(P.get("late"))
        w = KA.window(_et(now).date())
        return act, bool(kb.get("on")), (f"{_hm(w[0])}-{_hm(w[1])}" if w else "")
    except Exception:  # noqa: BLE001
        return False, False, ""


def _room(r: dict):
    src = _d(r.get("_src"))
    room = _f(src.get("room"))
    return _f(_d(src.get("eval")).get("room")) if room is None else room


def build(snap: dict, now: int | None = None, plan_doc=None, events=None, root: str | None = None, fleet: str | None = None,
          waiting: int | None = None, lvb: dict | None = None) -> dict:
    """THE pushed brief (night-briefv2 2026-11-23, owner: the day in 5 lines, money first). Same sources as build_full:
      1 Yesterday: $ per account (the previous CME session) and the total
      2 Room to max loss: every account's room in $, the ones under LOW_ROOM first and marked LOW
      3 Keep-alive today: the accounts whose 7-day act day is today (ON: the window; OFF: trade 1 MNQ by hand), else none due
      4 News: today's big news + the T1 blackout (Rapid funded, flat -2/+2 min) + an early close, else none
      5 Bot: READY / NOT READY (+ the fix), armed / NOT armed per account
      (+ line 1 ends with " · live vs bt: LIT -$8 ok" from engine/live_vs_bt; a 6th line only when that check flags a bot)
    {"title", "body", "lines" (5, or 6 with a live-vs-backtest flag), "day", "needs"}. Never raises on a bad snapshot."""
    now = int(now if now is not None else snap.get("t"))
    e = _et(now)
    pc, needs = pc_text(snap)
    try:
        rs = rows(snap, now, plan_doc, events)
    except Exception as x:  # noqa: BLE001
        rs = []
        needs.append(f"accounts not readable ({x.__class__.__name__})")
    age = snap.get("hb_age")
    fresh = age is not None and age <= HB_FRESH_S
    old = "" if fresh or age is None else f" (numbers {int(age) // 3600} h {int(age) % 3600 // 60} min old)"
    labs = [label(r) for r in rs]
    # 1 money
    t0, t1 = prev_session(now)
    try:
        yd = day_pnl(snap, now, rs, plan_doc, t0, t1)
    except Exception:  # noqa: BLE001
        yd = {}
    parts, tot = [], 0.0
    for r, lb in zip(rs, labs):
        v = yd.get(r.get("key"))
        usd = float(v[1]) if v else 0.0
        tot += usd
        parts.append(f"{lb} {signed(usd)}")
    l1 = ("Yesterday: " + " · ".join(parts) + f" · total {signed(tot)}") if parts else "Yesterday: no account numbers in the last report"
    # 2 room
    rooms = []
    for r, lb in zip(rs, labs):
        st = str(r.get("stage") or "eval")
        rm = _room(r)
        if r.get("locked"):
            rooms.append((-1, f"{lb} LOCKED by MFFU"))
        elif rm is not None and st in ("eval", "funded"):
            rooms.append((rm, f"{lb} {money(rm)}" + (" LOW" if rm < LOW_ROOM else "")))
    rooms.sort(key=lambda x: x[0])
    low = [t for v, t in rooms if v < LOW_ROOM]
    l2 = ("Room to max loss: " + " · ".join(t for _, t in rooms)) if rooms else "Room to max loss: not in the last report"
    if low:
        needs.append(f"near max loss: {low[0]}")
    # 3 keep-alive
    ka = []
    for r, lb in zip(rs, labs):
        act, on, win = _ka_today(r, now)
        if act:
            ka.append(f"{lb} {'(keep-alive trades ' + win + ' ET)' if on else '(keep-alive OFF: 1 MNQ by hand before 16:05 ET)'}")
            if not on:
                needs.append(f"{lb}: 1 MNQ by hand today")
    l3 = ("Keep-alive today: " + " · ".join(ka)) if ka else "Keep-alive today: no account is due"
    # 4 news
    nw = [x for x in (news_today(now, root), news_bans(now), early_note(now)) if x]
    l4 = ("News: " + " · ".join(nw)) if nw else "News: no big release today"
    # 5 bot
    rl, word = ready_line(snap, pc, needs)
    arm, notarm = [], []
    for r, lb in zip(rs, labs):
        badge = str(_d(r.get("_src")).get("badge") or "").upper()
        (arm if badge == "LIVE" else notarm).append(lb if badge in ("LIVE", "") else f"{lb} ({badge.lower()})")
    l5 = f"Bot: {rl}" + (f" · armed: {', '.join(arm)}" if arm else "") + (f" · NOT armed: {', '.join(notarm)}" if notarm else "")
    # night-livevsbt: live vs backtest (engine/live_vs_bt's last daily check, read only) on line 1; a 6th line only when it flags
    if lvb is None:
        try:
            from engine import live_vs_bt as _lvb
            lvb = _lvb.last(now) or {}
        except Exception:  # noqa: BLE001
            lvb = {}
    bots = {k: v for k, v in (_d(lvb).get("bots") or {}).items() if isinstance(v, dict) and v.get("n")}
    if bots:
        l1 += " · live vs bt: " + ", ".join(f"{k} {'+' if v['gap'] >= 0 else '-'}{money(abs(v['gap']))} {'FLAG' if v.get('flag') else 'ok'}"
                                            for k, v in bots.items())
    flagged = [v["line"] for v in bots.values() if v.get("flag")]
    six = [" · ".join(flagged)] if flagged else []
    if flagged:
        needs.append("live drifts from the backtest")
    # integration 2026-11-23: night-payday's line ("REQUEST PAYOUT TODAY: ATLAS 25K $1,000 - ...") rides the 5-line brief too, first
    # (money in hand first), until the owner records the payout (TRADE_HOME -> P); the title says it, as in build_full
    pay = payday_line(rs) if fresh else ""
    lines = [ln[:400] for ln in (*([pay] if pay else []), l1 + old, l2 + old, l3, l4, l5, *six)]
    title = f"ZEUS - {e:%a %b} {e.day} - {word}" + (f" - {signed(tot)} yesterday" if parts else "") + (" - REQUEST PAYOUT TODAY" if pay else "")
    return {"title": title, "body": "\n".join(lines)[:3900], "lines": lines, "day": e.date().isoformat(), "needs": len(needs)}


def board_post(b: dict, env=None) -> dict | None:
    """ONE Board event (kind "brief") per day: only from the real PC report (LE_PC_REPORT=1) or a test's LE_BOARD_DIR, and
    never when that day's brief is already in data/board/events.jsonl. Never raises."""
    env = os.environ if env is None else env
    if env.get("LE_PC_REPORT") != "1" and not env.get("LE_BOARD_DIR"):
        return None
    try:
        from engine import board_events as B
        path = os.path.join(B.dirs(env)[0], B.EVENTS)
        if any(r.get("kind") == "brief" and _d(r.get("data")).get("day") == b["day"] for r in B.read_jsonl(path)[-400:]):
            return None
        return B.emit("brief", "", " | ".join(b["lines"]), {"day": b["day"], "needs": b.get("needs") or 0})
    except Exception:  # noqa: BLE001
        return None


def pushes(snap: dict, sent: dict, now: int, plan_doc=None, events=None) -> list:
    """tools/pc_guard.guard's hook: [the brief push] once a day inside the window, else []."""
    if not due(now):
        return []
    k = key(now)
    if k in (sent or {}):
        return []
    b = build(snap, now, plan_doc, events)
    board_post(b)
    return [{"key": k, "kind": "morning_brief", "title": b["title"], "body": b["body"], "priority": "default", "tags": "sunrise"}]


if __name__ == "__main__":                       # a dry look on the PC: python -X utf8 -m tools.morning_brief
    import time
    from tools import pc_report as R
    s = R.gather(int(time.time()))
    s["cond"] = R.conditions(s)
    print("\n".join(build(s)["lines"]))
    print("--- detailed ---")
    print("\n".join(build_full(s)["lines"]))
