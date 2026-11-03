"""OLYMPUS Wrapped: the recap the HERMES page tells as stories. Pure functions, no I/O, no clock: same input, same output.

build(data, home=None, live=None, now=...) -> the wrapped.json object:
  {"v", "kind": "olympus-wrapped", "t", "demo", "today",
   "periods": {"week" | "month" | "all": {
       "key", "label", "from", "to", "net", "per_month", "trades", "wins", "losses", "won_usd", "lost_usd", "win_pct",
       "days": [[day, net], ...], "bots": [{"id", "name", "net", "trades", "paper"}], "paper_twin": {"net", "trades"} | None,
       "best": trade | None, "worst": trade | None, "discipline": {"score", "rules": [...]}}},
   "eval": [{"name", "balance", "profit", "target", "progress", "room", "mll", "floor", ...}], "odds": {...} | None,
   "learned": [{"tag", "text"}], "next": {"goal", "why"}}
jarvis_card(w) -> the Jarvis status card (docs/JARVIS_APPS.md): "This week: +$X".

Money rules (owner): net $ and $ per month always, losses shown as they are. Which accounts count: every account the PC bot
reports (Zlarior on the MFFU 50K, ATLAS, BLITZ). The cloud's "Paper (cloud)" ledger is Zlarior's paper twin: it is counted
only when no PC account has a trade (else it would count the same trades twice) and is then marked paper.
Times: trading days as the accounts write them ("day"), clock checks in New York time.
"""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
VERSION = 1
KIND = "olympus-wrapped"
PAPER_IDS = ("cloud_paper",)
TRADING_DAYS_PER_MONTH = 21
ENTRY_FROM, ENTRY_TO, FLAT_BY = 2 * 60, 15 * 60 + 30, 15 * 60 + 56     # LIT: entries 02:00-15:30, flat 15:55 (+1 min grace)
MANUAL_WORDS = ("manual", "user", "hand", "override", "flatten by", "closed by you")
THEME = "#12081f"
BOT_KEYS = {"lit": "Zlarior", "atlas": "ATLAS", "atlas_v2": "ATLAS v2", "blitz": "BLITZ", "second": "ATLAS"}


# ------------------------------------------------------------------------------------------------------------ small helpers
def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _day(s) -> str | None:
    s = str(s or "")[:10]
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return None
    return s


def _et(ts) -> dt.datetime | None:
    x = _num(ts)
    return dt.datetime.fromtimestamp(int(x), NY) if x else None


def trading_day(ts) -> str:
    """The trading day of a unix time: 18:00 ET starts the next day (engine/accounts.trading_day's rule)."""
    e = _et(ts)
    if e.hour >= 18:
        e += dt.timedelta(days=1)
    while e.weekday() >= 5:
        e += dt.timedelta(days=1)
    return e.date().isoformat()


def usd(x, sign=True) -> str:
    """'+$1,234' / '-$56', whole dollars rounded half up (ASCII minus: the Jarvis card colours a delta by its first character)."""
    v = _num(x) or 0.0
    x = math.floor(abs(v) + 0.5) * (1 if v >= 0 else -1)
    s = f"${abs(x):,.0f}"
    return ("-" + s) if x < 0 else ("+" + s) if (sign and x > 0) else s


def weekdays_between(a: str, b: str) -> int:
    """Weekdays from a to b, both included (0 when b < a)."""
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    n = 0
    while d0 <= d1:
        n += d0.weekday() < 5
        d0 += dt.timedelta(days=1)
    return n


def bot_name(acct: dict) -> str:
    """The bot behind an account: Zlarior (LIT) by default, ATLAS / BLITZ by name, the cloud ledger is the paper twin."""
    key = " ".join(str(acct.get(k) or "") for k in ("id", "name", "plan", "method")).lower()
    if str(acct.get("id")) in PAPER_IDS:
        return "Paper twin"
    if "blitz" in key or "account c" in key:
        return "BLITZ"
    if "atlas" in key or "account b" in key:
        return "ATLAS"
    if "kalshi" in key:
        return "Kalshi"
    return "Zlarior"


# ------------------------------------------------------------------------------------------------------------ the trades
def collect(data: dict) -> tuple[list, list]:
    """(counted trades, paper-twin trades): closed trades of every account, each with its bot, account and side."""
    pc, paper = [], []
    for a in (data or {}).get("accounts") or []:
        if not isinstance(a, dict) or a.get("error"):
            continue
        is_paper = str(a.get("id")) in PAPER_IDS or a.get("source") == "cloud"
        for t in a.get("trades") or []:
            if not isinstance(t, dict):
                continue
            pnl, day = _num(t.get("pnl")), _day(t.get("day")) or (trading_day(t["entry_t"]) if _num(t.get("entry_t")) else None)
            if pnl is None or not day:
                continue
            row = {**t, "pnl": round(pnl, 2), "day": day, "bot": bot_name(a), "account": str(a.get("name") or a.get("id") or ""),
                   "account_id": str(a.get("id") or ""), "orders": a.get("orders") or []}
            (paper if is_paper else pc).append(row)
    key = lambda t: (t["day"], _num(t.get("entry_t")) or 0, t["account_id"])  # noqa: E731
    pc.sort(key=key)
    paper.sort(key=key)
    return pc, paper


def counted(data: dict) -> tuple[list, list, bool]:
    """(the trades that count, the paper twin's, paper_only): the twin counts only when the PC has no trade at all."""
    pc, paper = collect(data)
    if pc:
        return pc, paper, False
    return [{**t, "paper": True} for t in paper], [], bool(paper)


# ------------------------------------------------------------------------------------------------------------ periods
def bounds(key: str, today: str, trades: list) -> tuple[str, str, str]:
    """(from, to, label) of a period. Week = Monday to Sunday, month = the calendar month, all = since the first trade.
    Early in a week (Mon / Tue) or a month (day 1-5) with no trade yet, the recap is the last full one."""
    d = dt.date.fromisoformat(today)
    days = [t["day"] for t in trades]
    if key == "week":
        mon = d - dt.timedelta(days=d.weekday())
        a, b = mon.isoformat(), (mon + dt.timedelta(days=6)).isoformat()
        if d.weekday() <= 1 and not any(a <= x <= b for x in days):
            mon -= dt.timedelta(days=7)
            a, b = mon.isoformat(), (mon + dt.timedelta(days=6)).isoformat()
            return a, b, "Last week"
        return a, b, "This week"
    if key == "month":
        first = d.replace(day=1)
        nxt = (first + dt.timedelta(days=32)).replace(day=1)
        a, b = first.isoformat(), (nxt - dt.timedelta(days=1)).isoformat()
        if d.day <= 5 and not any(a <= x <= b for x in days):
            last = first - dt.timedelta(days=1)
            return last.replace(day=1).isoformat(), last.isoformat(), last.strftime("%B %Y")
        return a, b, d.strftime("%B %Y")
    a = min(days) if days else today
    return a, max(today, a), "All time"


def per_month(net: float, start: str, end: str) -> float:
    """$ per month at this pace: net over the weekdays of the period so far, times 21 trading days."""
    n = weekdays_between(start, end)
    return round(net / n * TRADING_DAYS_PER_MONTH, 2) if n else 0.0


def period(key: str, today: str, trades: list, paper: list, paper_only: bool, data: dict) -> dict:
    a, b, label = bounds(key, today, trades)
    T = [t for t in trades if a <= t["day"] <= b]
    P = [t for t in paper if a <= t["day"] <= b]
    pn = [t["pnl"] for t in T]
    net = round(sum(pn), 2)
    won, lost = round(sum(x for x in pn if x > 0), 2), round(sum(x for x in pn if x < 0), 2)
    wins, losses = sum(1 for x in pn if x > 0), sum(1 for x in pn if x < 0)
    days = {}
    for t in T:
        days[t["day"]] = round(days.get(t["day"], 0.0) + t["pnl"], 2)
    bots = {}
    for t in T:
        b_ = bots.setdefault((t["bot"], t["account_id"]), {"id": t["account_id"], "name": t["bot"], "account": t["account"],
                                                           "net": 0.0, "trades": 0, "paper": bool(t.get("paper"))})
        b_["net"] = round(b_["net"] + t["pnl"], 2)
        b_["trades"] += 1
    end = min(b, today)
    best = max(T, key=lambda t: (t["pnl"], t["day"])) if T else None
    worst = min(T, key=lambda t: (t["pnl"], t["day"])) if T else None
    eq, run = [], 0.0
    for d in sorted(days):
        run = round(run + days[d], 2)
        eq.append(run)
    return {"key": key, "label": label, "from": a, "to": b, "net": net, "per_month": per_month(net, a, end) if end >= a else 0.0,
            "trades": len(T), "wins": wins, "losses": losses, "won_usd": won, "lost_usd": lost,
            "win_pct": round(wins / len(T) * 100, 1) if T else None, "paper_only": paper_only,
            "days": [[d, days[d]] for d in sorted(days)], "equity": eq,
            "bots": sorted(bots.values(), key=lambda x: (-x["net"], x["name"])),
            "paper_twin": {"net": round(sum(t["pnl"] for t in P), 2), "trades": len(P)} if P else None,
            "best": trade_card(best, data, "best") if best is not None and best["pnl"] > 0 else None,
            "worst": trade_card(worst, data, "worst") if worst is not None and worst["pnl"] < 0 else None,
            "discipline": discipline(T)}


# ------------------------------------------------------------------------------------------------------------ one trade
def _bars(data: dict) -> list:
    """The recent 5m bars the site carries ([t, o, h, l, c]); the PC's live.json bars override nothing here."""
    live = (data or {}).get("live") or {}
    out = []
    for b in live.get("bars") or []:
        if isinstance(b, (list, tuple)) and len(b) >= 5 and all(_num(x) is not None for x in b[:5]):
            out.append([int(b[0]), float(b[4])])
    return out


def spark(t: dict, data: dict) -> dict:
    """The mini replay: real closes from the site's bars when they cover the trade, else the trade's own path (entry, the
    best point it reached when known, exit), marked "schematic" so the page never shows it as a chart of prices."""
    side = 1 if str(t.get("side") or "LONG").upper().startswith(("L", "B")) else -1
    e0, e1 = _num(t.get("entry_t")), _num(t.get("exit_t"))
    lv = {k: _num(t.get(k)) for k in ("entry", "stop", "target", "exit_px")}
    if e0 and e1:
        pts = [c for (ts, c) in _bars(data) if e0 - 1800 <= ts <= e1 + 600]
        if len(pts) >= 4:
            return {"kind": "bars", "points": [round(c, 2) for c in pts][-60:], **lv}
    pts = [lv["entry"]]
    mfe, risk = _num(t.get("mfe")), _num(t.get("risk_pts"))
    if lv["entry"] is not None and mfe and risk:
        pts.append(round(lv["entry"] + side * mfe * risk, 2))
    pts.append(lv["exit_px"])
    pts = [p for p in pts if p is not None]
    return {"kind": "schematic", "points": pts, **lv} if len(pts) >= 2 else {"kind": "none", "points": [], **lv}


def _exit_kind(t: dict) -> str:
    ex = str(t.get("exit") or t.get("exit_reason") or "").lower()
    for k, words in (("manual", MANUAL_WORDS), ("target", ("target", "tp", "bank")), ("be", ("be", "breakeven", "break-even")),
                     ("cut", ("cut", "time")), ("flat", ("flat", "eod", "close", "15:55")), ("stop", ("stop", "sl"))):
        if any(w == ex or w in ex.split() or (len(w) > 3 and w in ex) for w in words):
            return k
    return "other"


def lesson(t: dict, data: dict) -> str:
    """One plain line on what the losing trade teaches: the Mind's review of it when there is one, else from its exit."""
    for r in ((((data or {}).get("live") or {}).get("pc") or {}).get("mind") or {}).get("reviews") or []:
        tr = r.get("trade") if isinstance(r, dict) else None
        same = isinstance(tr, dict) and _num(tr.get("entry_t")) and _num(tr.get("entry_t")) == _num(t.get("entry_t"))
        same = same or (str(tr) == str(t.get("entry_t")) and tr is not None)
        if same and r.get("lesson"):
            return str(r["lesson"])[:200]
    cause = str(t.get("cause") or "")
    labels = {"news_spike": "A news release hit the trade. Check the calendar before the entry window.",
              "wick_then_target": "A wick took the stop, then price went to the target. The stop was in the right place; it happens.",
              "opp_extreme_in": "The day's other extreme was already in. Late setups have less room to run.",
              "es_no_confirm": "ES did not confirm the sweep. The best setups have ES sweeping too.",
              "stale_trap": "The inducement was old (over 50 min). Fresh traps work better.",
              "late_london": "Late in the London move (05:00-08:00). The easy part was already done.",
              "wide_stop": "A wide stop (over 47 pts): the size was small, so the loss stayed in plan.",
              "against_4h_draw": "It traded against the 4H draw. The bigger picture was pulling the other way.",
              "not_turning_point": "Price ran straight through the sweep. Not every sweep is the day's turn.",
              "be_scratch": "It went +1R then came back. Breakeven protected it.",
              "eod_fade": "Flat at 15:55 with a loss: the move never came that day."}
    if cause in labels:
        return labels[cause]
    r, k = _num(t.get("r")), _exit_kind(t)
    if k == "manual":
        return "Closed by hand. The rules say hands off: the stop and the target do the work."
    if r is not None and r < -1.15:
        return f"Lost {abs(r):.1f}R, more than the planned 1R: slippage or a gap. Size follows the stop for this reason."
    if k == "stop":
        return "Stopped beyond the sweep, a planned 1R loss. The stop did its job; one winner at 8R pays for several."
    if k == "cut":
        return "The 15-minute cut got it out early, for less than a full 1R."
    if k == "flat":
        return "Flat at the close without the move. Some days the target is not in play."
    return "A planned loss inside the rules. The next setup is a new trade."


def trade_card(t: dict, data: dict, which: str) -> dict:
    e = _et(t.get("entry_t"))
    out = {"bot": t["bot"], "account": t["account"], "day": t["day"], "time": e.strftime("%H:%M") if e else None,
           "side": str(t.get("side") or "").upper() or None, "pnl": t["pnl"], "r": _num(t.get("r")), "qty": _num(t.get("qty")),
           "exit": str(t.get("exit") or "")[:30] or None, "risk_pts": _num(t.get("risk_pts")), "paper": bool(t.get("paper")),
           "spark": spark(t, data)}
    if which == "worst":
        out["lesson"] = lesson(t, data)
    return out


# ------------------------------------------------------------------------------------------------------------ discipline
def discipline(T: list) -> dict:
    """The rules the data can check, each kept / checked: one trade a day (Zlarior), a stop on every trade (beyond the
    sweep extreme when the trade carries it), entries 02:00-15:30 ET, flat by 15:55 ET, hands off (no manual exit or order).
    score = kept / checked over every rule, 0-100; None with no trade."""
    rules = []

    def add(rid, label, kept, total, note):
        if total:
            rules.append({"id": rid, "label": label, "kept": kept, "total": total, "ok": kept == total, "text": note})

    z = [t for t in T if t["bot"] in ("Zlarior", "Paper twin")]
    per = {}
    for t in z:
        per[(t["account_id"], t["day"])] = per.get((t["account_id"], t["day"]), 0) + 1
    add("one_a_day", "1 trade a day", sum(1 for n in per.values() if n <= 1), len(per),
        "Zlarior days with at most one trade")
    stops = []
    for t in T:
        st, en, sw = _num(t.get("stop")), _num(t.get("entry")), _num(t.get("sweep_ext"))
        side = 1 if str(t.get("side") or "LONG").upper().startswith(("L", "B")) else -1
        ok = st is not None and (en is None or (st - en) * side < 0)
        if ok and sw is not None:
            ok = (st - sw) * side <= 0                       # long: stop at or below the sweep low; short: at or above the high
        stops.append(ok)
    add("stop", "Stop beyond the sweep", sum(stops), len(stops), "trades with the stop on the far side of the sweep")
    ins = [t for t in z if _et(t.get("entry_t"))]
    add("window", "Entries 02:00-15:30", sum(1 for t in ins if ENTRY_FROM <= _et(t["entry_t"]).hour * 60 + _et(t["entry_t"]).minute <= ENTRY_TO),
        len(ins), "Zlarior entries inside the window (New York time)")
    outs = [t for t in z if _et(t.get("exit_t"))]
    add("flat", "Flat by 15:55", sum(1 for t in outs if _et(t["exit_t"]).hour * 60 + _et(t["exit_t"]).minute <= FLAT_BY
                                     or _et(t["exit_t"]).hour >= 18), len(outs), "Zlarior exits before the close")

    def manual(t):
        if _exit_kind(t) == "manual":
            return True
        for o in t.get("orders") or []:
            ot = _num((o or {}).get("t"))
            if ot and trading_day(ot) == t["day"] and any(w in str((o or {}).get("text") or "").lower() for w in MANUAL_WORDS):
                return True
        return False
    add("hands_off", "Hands off", sum(1 for t in T if not manual(t)), len(T), "trades the bot opened and closed by itself")
    kept, total = sum(r["kept"] for r in rules), sum(r["total"] for r in rules)
    return {"score": round(kept / total * 100) if total else None, "kept": kept, "checked": total, "rules": rules}


# ------------------------------------------------------------------------------------------------------------ eval, learned
def evals(data: dict, home: dict | None) -> list:
    """Each prop account's eval: progress to the target, the room above the trailing floor, the session clock."""
    out = []
    for a in (data or {}).get("accounts") or (home or {}).get("accounts") or []:
        if not isinstance(a, dict) or str(a.get("id")) in PAPER_IDS or a.get("kind") == "paper" or a.get("error"):
            continue
        ev = a.get("eval") if isinstance(a.get("eval"), dict) else None
        if not ev or _num(ev.get("balance")) is None:
            continue
        start, bal = _num(ev.get("start_balance")) or 0.0, _num(ev.get("balance"))
        tgt = (_num(ev.get("target_balance")) or start) - start
        out.append({"id": str(a.get("id")), "name": str(a.get("name") or a.get("id")), "bot": bot_name(a),
                    "plan": a.get("plan"), "badge": a.get("badge"), "balance": round(bal, 2),
                    "profit": round(_num(ev.get("profit")) or bal - start, 2), "target": round(tgt, 2),
                    "to_target": round(_num(ev.get("to_target")) or 0.0, 2),
                    "progress": max(0.0, min(1.0, _num(ev.get("progress")) or 0.0)),
                    "floor": _num(ev.get("floor")), "room": _num(ev.get("room")), "mll": _num(ev.get("mll")),
                    "room_frac": round(max(0.0, min(1.0, (_num(ev.get("room")) or 0) / (_num(ev.get("mll")) or 1))), 4),
                    "session": ev.get("session"), "sessions": ev.get("sessions"), "status": ev.get("status"),
                    "clock": str(ev.get("clock_text") or "")[:120] or None})
    return out


def odds(data: dict, home: dict | None) -> dict | None:
    """The backtest's two-week odds at the live sizing (data.json extras.two_week.eval, H2 = the check half)."""
    tw = (((data or {}).get("extras") or {}).get("two_week") or ((home or {}).get("extras") or {}).get("two_week") or {})
    ev = (tw.get("eval") or {}) if isinstance(tw, dict) else {}
    for k in ("H2", "2026", "H1"):
        r = ev.get(k) if isinstance(ev, dict) else None
        if isinstance(r, dict) and _num(r.get("p10")) is not None:
            return {"p10": _num(r["p10"]), "f10": _num(r.get("f10")), "span": k, "pass_med": _num(r.get("pass_med")),
                    "source": "backtest at the live sizing"}
    return None


def learned(data: dict, live: dict | None) -> list:
    """Up to 4 plain lines on what the bots learned: the Mind's latest lessons and research proposals (live.json pc.mind,
    else data.json live.pc.mind), live-vs-backtest gap (live learning), the month's top loss cause. Read-only facts."""
    out = []
    mind = ((live or {}).get("pc") or {}).get("mind") or ((((data or {}).get("live") or {}).get("pc") or {}).get("mind")) or {}
    for r in (mind.get("reviews") or [])[:2]:
        if isinstance(r, dict) and r.get("lesson"):
            out.append({"tag": f"Mind · {r.get('bot') or 'review'}", "text": str(r["lesson"])[:200]})
    for p in (mind.get("proposals") or [])[:1]:
        if isinstance(p, dict) and p.get("idea"):
            st = f" ({p['status']})" if p.get("status") else ""
            out.append({"tag": "Mind · research", "text": f"{str(p['idea'])[:150]}{st}"})
    ll = (data or {}).get("learning_live") or {}
    wk = (ll.get("weekly") or [None])[0] if isinstance(ll, dict) else None
    if isinstance(wk, dict):
        for b, v in sorted((wk.get("bots") or {}).items()):
            if isinstance(v, dict) and _num(v.get("live_usd")) is not None:
                gap = round((_num(v.get("live_usd")) or 0) - (_num(v.get("twin_usd")) or 0), 2)
                out.append({"tag": "Live learning", "text": f"{wk.get('label') or 'Last week'}: {BOT_KEYS.get(b, b)} made {usd(v.get('live_usd'))} live vs "
                            f"{usd(v.get('twin_usd'))} in the backtest twin ({usd(gap)} gap)."})
                break
    for s in (ll.get("suggest") or [])[:1] if isinstance(ll, dict) else []:
        if isinstance(s, dict) and s.get("title") and s.get("kind") != "error":
            out.append({"tag": "Suggestion (needs your OK)", "text": str(s["title"])[:160]})
    cm = ((data or {}).get("learning") or {}).get("causes_month") or {}
    bc = cm.get("by_cause") or []
    if bc and isinstance(bc[0], dict):
        c = bc[0]
        out.append({"tag": "Loss causes", "text": f"Top loss cause this month: {str(c.get('label') or c.get('cause'))[:110]} "
                    f"({c.get('n')} trade{'s' if c.get('n') != 1 else ''}, {usd(c.get('usd'))})."})
    return out[:4]


def next_goal(week: dict, ev: list) -> dict:
    """The one goal for next week (the closing card)."""
    d = week.get("discipline") or {}
    broken = [r for r in d.get("rules") or [] if not r["ok"]]
    if broken:
        r = broken[0]
        return {"goal": f"Keep \"{r['label']}\" every time", "why": f"{r['kept']} of {r['total']} last time. Rules first, money second."}
    e = next((x for x in ev if x["to_target"] > 0), None)
    if e:
        return {"goal": f"Bank {usd(e['to_target'], False)} to pass the {e['plan'] or e['name']}",
                "why": f"{usd(e['room'], False) if e['room'] is not None else 'the'} room above the floor. 2-4 trades, one clear target."}
    if week.get("trades", 0) < 2:
        return {"goal": "2-4 clean trades", "why": "The plan is 2-4 trades a week, stops beyond the sweep, banked at 8R."}
    return {"goal": "Same rules, same edge", "why": "Size follows the stop, one target, no greed."}


# ------------------------------------------------------------------------------------------------------------ the whole
def build(data: dict | None, home: dict | None = None, live: dict | None = None, now: float = 0, demo: bool = False) -> dict:
    data = data or {}
    today = _et(now).date().isoformat() if now else dt.date.today().isoformat()     # the calendar day in New York
    T, P, paper_only = counted(data)
    periods = {k: period(k, today, T, P, paper_only, data) for k in ("week", "month", "all")}
    ev = evals(data, home)
    return {"v": VERSION, "kind": KIND, "t": int(now), "demo": bool(demo), "today": today, "theme": THEME,
            "periods": periods, "eval": ev, "odds": odds(data, home), "learned": learned(data, live),
            "next": next_goal(periods["week"], ev)}


def jarvis_card(w: dict) -> dict:
    """The Jarvis card (docs/JARVIS_APPS.md): plain text, at most 3 kpis / 3 lines, 'This week: +$X'."""
    wk, mo = w["periods"]["week"], w["periods"]["month"]
    d = (wk.get("discipline") or {}).get("score")
    if w.get("demo"):
        level, label = "off", "Demo data"
    elif not wk["trades"]:
        level, label = "off", "No trades yet"
    else:
        level, label = ("ok" if wk["net"] >= 0 else "warn"), f"{wk['label']}: {usd(wk['net'])}"
    lines = [f"{wk['label']}: {usd(wk['net'])} on {wk['trades']} trade{'s' if wk['trades'] != 1 else ''}, "
             f"{usd(wk['per_month'])} a month at this pace"]
    if wk.get("best"):
        b = wk["best"]
        lines.append(f"Best: {b['bot']} {usd(b['pnl'])} on {b['day']}")
    if w.get("next"):
        lines.append(f"Next: {w['next']['goal']}"[:120])
    return {"v": 1, "name": "HERMES", "status": {"level": level, "label": label[:48]},
            "kpis": [{"label": wk["label"][:20], "value": usd(wk["net"])[:24]},
                     {"label": "Per month", "value": usd(mo["per_month"])[:24]},
                     {"label": "Discipline", "value": f"{d}%" if d is not None else "—"}],
            "lines": [x[:120] for x in lines[:3]], "t": int(w["t"]), "open": "#week", "theme": THEME}
