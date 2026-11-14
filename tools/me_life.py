"""ME LIFE (team ME1, 2026-11-14, docs/ME_HUB.md): the four "find more" parts of the Me hub, small and solid. Pure functions over the files
other tools already make, plus what you type once on the PC.

  Freedom   (quit-my-job tracker) side income (prop-firm payouts minus fees from your bank exports + the agency's MRR) against your paycheck:
            the % it covers, months to freedom at the last 6 months' pace, and how long savings last if you quit today
  Dates     birthdays and important days: the ones you type (yearly) + calendar entries that look important (birthday, appointment, renewal,
            flight ...) from data/day/day.json + the car's renewals. Reminders 7 days and 1 day before a birthday, 3 days and 1 day before the rest
  Car       mileage you type now and then, the oil change by miles or months (whichever comes first), registration / inspection / insurance
            dates. Reminders: oil within 300 miles or 7 days; a date 14 and 3 days before
  Streaks   counted for you from the Apple Watch days (no typing): steps, exercise, stand, move and sleep goals, days in a row and the best

  python tools/me_life.py --paycheck 3200 --agency 800        your pay a month and the agency's MRR (else they are read from files)
  python tools/me_life.py --date "Mom's birthday=03-14"       yearly (MM-DD); a one-off is YYYY-MM-DD; --date-remove NAME
  python tools/me_life.py --car-miles 48210                   the odometer now (a few times a month is plenty)
  python tools/me_life.py --car-oil-done [MILES]              the oil was changed today (at the odometer you give, else the estimate)
  python tools/me_life.py --car-oil-every 5000 --car-oil-months 6
  python tools/me_life.py --car-date registration=2027-03-31  also inspection, insurance or any name
  python tools/me_life.py                                    the four parts as a card

Private: %USERPROFILE%\\.olympus\\me\\ freedom.json, dates.json, car.json (outside the repo). Estimates, not advice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import me_core as M  # noqa: E402

AGENCY_DIR = os.path.join(ROOT, "data", "agency")
IMPORTANT_RX = re.compile(r"\b(birthday|bday|b-day|anniversary|wedding|appointment|appt|dentist|doctor|dr\.?|vet|renew\w*|expir\w*|registration|"
                          r"deadline|due|flight|trip|vacation|interview|exam|court|closing|moving|surgery|check-?up|party|graduation|funeral|lease)\b", re.I)
BDAY_RX = re.compile(r"\b(birthday|bday|b-day|anniversary)\b", re.I)
DATE_KINDS = ("birthday", "anniversary", "renewal", "appointment", "other")
HORIZON = 60
CAR_DEFAULT_MPM = 1000.0       # miles a month when there is only one reading (about the US average)
OIL_SOON_MI, OIL_SOON_D = 300, 7
CONNECT = {
    "freedom": "Import your bank exports (RUN_MONEY.bat) or type your pay on the PC: python tools\\me_life.py --paycheck 3200",
    "dates": "On the PC: python tools\\me_life.py --date \"Mom's birthday=03-14\" (calendars connected with CONNECT_DAY.bat count too)",
    "car": "On the PC: python tools\\me_life.py --car-miles 48210 --car-date registration=2027-03-31",
    "streaks": "Counted for you once the Apple Watch days arrive (the 'Health to PC' Shortcut)",
}


def pfile(name: str, env=None) -> str:
    return os.path.join(M.me_dir(env), name)


def load(name: str, env=None) -> dict:
    return M.obj(M.read_json(pfile(name, env), {}))


# ------------------------------------------------------------------------------------------------ Freedom
def agency_mrr(folder: str = AGENCY_DIR):
    """the agency's monthly recurring revenue when data/agency/ has it: a number under mrr / mrr_usd / monthly_recurring, or the sum of
    clients[].mrr. None when there is no such file."""
    best = None
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        d = M.read_json(p, None)
        if not isinstance(d, dict):
            continue
        for k in ("mrr", "mrr_usd", "monthly_recurring", "monthly_recurring_usd"):
            v = M.num(d.get(k))
            if v is not None:
                best = (best or 0.0) + v
                break
        else:
            cl = [M.num(M.obj(c).get("mrr")) for c in M.arr(d.get("clients"))]
            cl = [v for v in cl if v is not None]
            if cl:
                best = (best or 0.0) + sum(cl)
    return round(best, 2) if best is not None else None


def slope(ys: list) -> float | None:
    """least-squares $ per month of a monthly series (oldest first)"""
    pts = [(i, y) for i, y in enumerate(ys) if y is not None]
    if len(pts) < 3:
        return None
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    den = sum((p[0] - mx) ** 2 for p in pts)
    return round(sum((p[0] - mx) * (p[1] - my) for p in pts) / den, 2) if den else None


def freedom(household: dict | None, day: dict | None, typed: dict | None, agency=None) -> dict:
    H, D, T = M.obj(household), M.obj(day), M.obj(typed)
    full = [m for m in M.arr(H.get("months")) if isinstance(m, dict) and not m.get("partial") and m.get("n")][-6:]
    cat = lambda m, k: M.num(M.obj(m.get("by_cat")).get(k)) or 0.0  # noqa: E731
    trade = [round(cat(m, "prop_payout") - cat(m, "prop_fees"), 2) for m in full]
    other = [cat(m, "income_other") for m in full]
    pay_bank = round(sum(cat(m, "income") for m in full[-3:]) / len(full[-3:]), 2) if full and any(cat(m, "income") for m in full[-3:]) else None
    pay_day = M.num(M.obj(M.obj(D.get("week")).get("pay")).get("month_usd"))
    pay, pay_src = (M.num(T.get("paycheck_month")), "typed") if M.num(T.get("paycheck_month")) else (pay_day, "your shifts x your pay (calendars)") if pay_day else (pay_bank, "paychecks in your bank exports") if pay_bank else (None, "")
    ag = M.num(T.get("agency_mrr")) if M.num(T.get("agency_mrr")) is not None else agency
    ag_src = "typed" if M.num(T.get("agency_mrr")) is not None else ("data/agency" if agency is not None else "")
    spend = M.num(M.obj(H.get("avg3")).get("out"))
    tr3 = round(sum(trade[-3:]) / len(trade[-3:]), 2) if trade else None
    side = round((tr3 or 0.0) + (ag or 0.0), 2) if (tr3 is not None or ag is not None) else None
    target = M.num(T.get("target_month")) or pay or spend
    tgt_src = "typed" if M.num(T.get("target_month")) else ("your paycheck" if pay else "your spending" if spend else "")
    cover = round(side / target * 100.0, 1) if side is not None and target else None
    sl = slope(trade)
    if side is not None and target and side >= target:
        months, when = 0, "Now: your side income covers it"
    elif side is not None and target and sl and sl > 0:
        months = int(math.ceil((target - side) / sl))
        when = f"About {months} months at +{M.money(sl)} a month more each month" if months <= 120 else "Over 10 years at this pace"
    else:
        months, when = None, "No date yet: side income is not growing in your bank data"
    liquid = M.num(M.obj(H.get("networth")).get("liquid"))
    gap = (spend or target or 0.0) - (side or 0.0)
    runway = round(liquid / gap, 1) if liquid is not None and gap > 0 else None
    no_gap = liquid is not None and gap <= 0
    has = bool(target) and side is not None
    return {"has": has, "paycheck": pay, "paycheck_src": pay_src, "agency": ag, "agency_src": ag_src, "trading_3m": tr3, "trading_months": trade,
            "months": [m.get("month") for m in full], "other_3m": round(sum(other[-3:]) / len(other[-3:]), 2) if other else None,
            "side": side, "spend": spend, "target": target, "target_src": tgt_src, "cover_pct": cover, "slope": sl, "months_to": months, "when": when,
            "liquid": liquid, "gap": round(gap, 2) if gap else 0.0, "runway_months": runway, "no_gap": no_gap}


def freedom_section(F: dict, t=None) -> dict:
    base = {"id": "freedom", "title": "Freedom", "connect": CONNECT["freedom"], "src": {"name": "Bank exports + what you typed", "t": t}}
    if not F["has"]:
        return {**base, "state": "empty", "line": "Not enough to work it out yet", "cards": []}
    cov = F["cover_pct"]
    lvl = "ok" if cov is not None and cov >= 100 else "warn" if cov is not None and cov >= 50 else ""
    rows = [{"k": "Your paycheck", "v": f"{M.money(F['paycheck'])} a month" if F["paycheck"] else "-", "s": F["paycheck_src"] or "type it: --paycheck 3200"},
            {"k": "Trading (payouts minus fees)", "v": f"{M.money(F['trading_3m'])} a month" if F["trading_3m"] is not None else "-", "s": "the last 3 full months, from your bank"},
            {"k": "Agency", "v": f"{M.money(F['agency'])} a month" if F["agency"] is not None else "-", "s": F["agency_src"] or "type it: --agency 800"},
            {"k": "Other money in", "v": f"{M.money(F['other_3m'])} a month" if F["other_3m"] else "-", "s": "not counted (refunds, gifts ...)"},
            {"k": "You spend", "v": f"{M.money(F['spend'])} a month" if F["spend"] else "-", "s": "the last 3 full months"}]
    cover = {"id": "cover", "title": "Side income vs " + ("paycheck" if F["target_src"] == "your paycheck" else "your target"),
             "value": M.pct(cov) if cov is not None else "-", "sub": f"{M.money(F['side'])} of {M.money(F['target'])} a month",
             "lvl": lvl, "pct": min(100.0, cov) if cov is not None else None, "rows": rows,
             "note": "Cash that reached your bank only (paper P&L is never counted). Plan for taxes and health insurance before you quit."}
    tmax = max([abs(x) for x in F["trading_months"]] + [F["target"] or 1])
    mrows = [{"k": m, "v": M.money(v + (F["agency"] or 0.0)), "s": f"trading {M.money(v, True)}" + (f" + agency {M.money(F['agency'])}" if F["agency"] else ""),
              "pct": max(0.0, min(100.0, (v + (F["agency"] or 0.0)) / tmax * 100.0)), "lvl": "ok" if v + (F["agency"] or 0.0) >= (F["target"] or 0) else ""}
             for m, v in zip(F["months"], F["trading_months"])]
    when = {"id": "when", "title": "Months to freedom", "value": "Now" if F["months_to"] == 0 else (f"{F['months_to']} months" if F["months_to"] else "No date yet"),
            "sub": F["when"], "lvl": "ok" if F["months_to"] == 0 else "", "rows": mrows,
            "note": "A straight line through your last 6 months of trading cash: payouts are lumpy, so this moves a lot."}
    rw, ng = F["runway_months"], F["no_gap"]
    run = {"id": "runway", "title": "If you quit today", "value": ("No gap" if ng else f"{rw:.1f} months" if rw is not None else "-"),
           "sub": ("your side income already covers your spending" if ng else
                   f"your savings ({M.money(F['liquid'])}) cover the gap ({M.money(F['gap'])} a month)" if rw is not None else "add your balances: python tools\\money_import.py --balance \"Checking=2500\""),
           "lvl": "ok" if ng or (rw or 0) >= 6 else "warn" if rw is not None else "", "rows": [],
           "note": "Savings = checking + savings + cash in your balances. Estimates, not advice."}
    return {**base, "state": "ok", "line": f"Side income covers {M.pct(cov)} · {when['value']}", "cards": [cover, when, run]}


# ------------------------------------------------------------------------------------------------ Dates
def kind_of(name: str) -> str:
    n = name.lower()
    if re.search(r"\b(birthday|bday|b-day)\b", n):
        return "birthday"
    if "anniversary" in n:
        return "anniversary"
    if re.search(r"renew|insurance|registration|expir|license|passport|inspection|lease", n):
        return "renewal"
    if re.search(r"appointment|appt|dentist|doctor|vet|check-?up", n):
        return "appointment"
    return "other"


def parse_date_arg(s: str):
    """'Mom's birthday=03-14' (yearly) or 'Car insurance=2026-12-15' -> ({name, date, kind, yearly}, '')"""
    name, _, d = str(s or "").rpartition("=")
    name = M.clean(name.strip().strip('"'), 60)
    d = d.strip()
    if not name:
        return None, "use NAME=MM-DD (yearly) or NAME=YYYY-MM-DD"
    if re.fullmatch(r"\d{2}-\d{2}", d):
        try:
            dt.date(2024, int(d[:2]), int(d[3:]))
        except ValueError:
            return None, f"{d}: not a day of the year"
        return {"name": name, "date": d, "kind": kind_of(name), "yearly": True}, ""
    if M.parse_day(d) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return {"name": name, "date": d, "kind": kind_of(name), "yearly": False}, ""
    return None, f"{d!r}: use MM-DD (every year) or YYYY-MM-DD (once)"


def next_of(rec: dict, today: str):
    """the next date of a typed entry (yearly: this year's or next year's; Feb 29 is Feb 28 in other years)"""
    d = str(rec.get("date") or "")
    if rec.get("yearly") or re.fullmatch(r"\d{2}-\d{2}", d):
        t = dt.date.fromisoformat(today)
        mm, dd = int(d[-5:-3]), int(d[-2:])
        for y in (t.year, t.year + 1):
            try:
                c = dt.date(y, mm, dd)
            except ValueError:
                c = dt.date(y, mm, 28)
            if c >= t:
                return c.isoformat()
        return None
    return d if M.parse_day(d) else None


def dates(typed: dict | None, day: dict | None, car_dates: list | None, today: str, horizon: int = HORIZON) -> list:
    """[{name, day, in, kind, src}] of the next `horizon` days, soonest first"""
    out, seen = [], set()
    for r in M.arr(M.obj(typed).get("dates")):
        if not isinstance(r, dict) or not r.get("name"):
            continue
        n = next_of(r, today)
        if n and 0 <= M.days_between(today, n) <= horizon:
            out.append({"name": M.clean(r["name"], 60), "day": n, "in": M.days_between(today, n), "kind": r.get("kind") or kind_of(r["name"]), "src": "typed"})
    D = M.obj(day)
    cal = [(e.get("day"), e.get("title")) for e in M.arr(D.get("events")) if isinstance(e, dict) and not e.get("work")]
    for d, info in M.obj(D.get("days")).items():
        for title in M.arr(M.obj(info).get("all_day")):
            cal.append((d, title))
    for d, title in cal:
        title = M.clean(title, 60)
        if not d or not title or not IMPORTANT_RX.search(title) or not M.parse_day(d):
            continue
        n = M.days_between(today, d)
        if 0 <= n <= horizon:
            out.append({"name": title, "day": d, "in": n, "kind": kind_of(title), "src": "calendar"})
    for c in M.arr(car_dates):
        if 0 <= c["in"] <= horizon:
            out.append({**c, "src": "car"})
    res = []
    for x in sorted(out, key=lambda x: (x["day"], x["name"].lower())):
        k = (x["day"], x["name"].lower())
        if k not in seen:
            seen.add(k)
            res.append(x)
    return res


def date_reminders(items: list) -> list:
    out = []
    for x in items:
        offs = (7, 1) if x["kind"] in ("birthday", "anniversary") else (3, 1)
        if x["in"] > max(offs) or x["src"] == "car":
            continue
        slot = min(o for o in offs if x["in"] <= o)
        h = hashlib.sha1(x["name"].lower().encode("utf-8")).hexdigest()[:8]
        extra = " A card or a gift?" if x["kind"] in ("birthday", "anniversary") and x["in"] >= 2 else ""
        out.append({"key": f"date:{h}:{x['day']}:{slot}", "also": [f"date:{h}:{x['day']}:{o}" for o in offs if o > slot],
                    "title": f"{x['name']} {M.in_days(x['in'])}"[:110], "body": f"{x['name']}: {M.short_day(x['day'])} ({M.in_days(x['in'])}).{extra}",
                    "priority": "default", "tags": "date"})
    return out


def dates_section(items: list, t=None) -> dict:
    base = {"id": "dates", "title": "Dates", "connect": CONNECT["dates"], "src": {"name": "Your dates + calendars", "t": t}}
    if not items:
        return {**base, "state": "empty", "line": f"Nothing in the next {HORIZON} days", "cards": []}
    nx = items[0]
    bdays = [x for x in items if x["kind"] in ("birthday", "anniversary")]
    rest = [x for x in items if x["kind"] not in ("birthday", "anniversary")]
    row = lambda x: {"k": x["name"], "v": M.short_day(x["day"]), "s": M.in_days(x["in"]) + {"typed": "", "calendar": " · from your calendar", "car": " · your car"}[x["src"]],  # noqa: E731
                     "lvl": "warn" if x["in"] <= 1 else ""}
    cards = [{"id": "next", "title": "Next", "value": nx["name"], "sub": f"{M.short_day(nx['day'])} · {M.in_days(nx['in'])}", "lvl": "warn" if nx["in"] <= 1 else "",
              "rows": [row(x) for x in items[:12]], "note": "Reminders on your phone: 7 days and 1 day before a birthday, 3 days and 1 day before the rest."}]
    if bdays:
        cards.append({"id": "bdays", "title": "Birthdays", "value": bdays[0]["name"], "sub": f"{M.short_day(bdays[0]['day'])} · {M.in_days(bdays[0]['in'])}", "lvl": "",
                      "rows": [row(x) for x in bdays[:10]]})
    if rest:
        cards.append({"id": "other", "title": "Appointments and renewals", "value": rest[0]["name"], "sub": f"{M.short_day(rest[0]['day'])} · {M.in_days(rest[0]['in'])}", "lvl": "",
                      "rows": [row(x) for x in rest[:10]]})
    return {**base, "state": "ok", "line": f"Next: {nx['name']} {M.in_days(nx['in'])}", "cards": cards}


# ------------------------------------------------------------------------------------------------ Car
def car_state(car: dict | None, today: str) -> dict:
    C = M.obj(car)
    reads = sorted([r for r in M.arr(C.get("readings")) if M.parse_day(M.obj(r).get("day")) and M.num(M.obj(r).get("miles")) is not None], key=lambda r: r["day"])
    per_day, pace_src = None, ""
    if len(reads) >= 2:
        a, b = reads[0], reads[-1]
        days = M.days_between(a["day"], b["day"])
        if days >= 14 and b["miles"] > a["miles"]:
            per_day, pace_src = (b["miles"] - a["miles"]) / days, f"from your readings ({a['day']} to {b['day']})"
    if per_day is None:
        per_day, pace_src = (M.num(C.get("miles_per_month")) or CAR_DEFAULT_MPM) / 30.4, ("typed" if M.num(C.get("miles_per_month")) else "about the US average (add a second reading)")
    est = None
    if reads:
        est = round(reads[-1]["miles"] + per_day * max(0, M.days_between(reads[-1]["day"], today)))
    oil = M.obj(C.get("oil"))
    every_mi, every_mo = M.num(oil.get("every_miles")) or 5000, M.num(oil.get("every_months")) or 6
    o = None
    if M.num(oil.get("last_miles")) is not None or M.parse_day(oil.get("last_day")):
        last_mi, last_day = M.num(oil.get("last_miles")), oil.get("last_day")
        by_mi = by_mi_day = None
        if last_mi is not None and est is not None:
            by_mi = round(last_mi + every_mi - est)
            by_mi_day = M.add_days(today, int(max(-999, by_mi) / per_day)) if per_day else None
        by_time = None
        if M.parse_day(last_day):
            ld = dt.date.fromisoformat(last_day)
            y, m = ld.year + (ld.month - 1 + int(every_mo)) // 12, (ld.month - 1 + int(every_mo)) % 12 + 1
            by_time = M.on_day_of_month(y, m, ld.day).isoformat()
        due_day = min([d for d in (by_mi_day, by_time) if d] or [None]) if (by_mi_day or by_time) else None
        o = {"miles_left": by_mi, "by_miles_day": by_mi_day, "by_time_day": by_time, "due_day": due_day,
             "in": M.days_between(today, due_day) if due_day else None, "every_miles": every_mi, "every_months": every_mo,
             "last_miles": last_mi, "last_day": last_day,
             "soon": bool((by_mi is not None and by_mi <= OIL_SOON_MI) or (due_day and M.days_between(today, due_day) <= OIL_SOON_D))}
    ds = []
    for name, d in M.obj(C.get("dates")).items():
        if M.parse_day(d):
            ds.append({"name": f"Car {M.clean(name, 30).replace('_', ' ')}", "day": d, "in": M.days_between(today, d), "kind": "renewal"})
    ds.sort(key=lambda x: x["day"])
    return {"has": bool(reads or o or ds), "name": M.clean(C.get("name") or "Car", 30), "readings": reads[-8:], "per_month": round(per_day * 30.4),
            "pace_src": pace_src, "miles_now": est, "oil": o, "dates": ds}


def car_reminders(S: dict) -> list:
    out = []
    o = S.get("oil")
    if o and o["soon"]:
        key = f"car:oil:{int((o['last_miles'] or 0) + o['every_miles'])}:{o['by_time_day']}"
        left = f"about {o['miles_left']:,} miles left" if o["miles_left"] is not None and o["miles_left"] > 0 else "it is due now"
        out.append({"key": key, "also": [], "title": f"{S['name']}: oil change soon", "body": f"{S['name']}: oil change, {left} (every {o['every_miles']:,.0f} mi or {o['every_months']:g} months).",
                    "priority": "default", "tags": "car"})
    for x in S["dates"]:
        offs = (14, 3)
        if x["in"] < 0 or x["in"] > max(offs):
            continue
        slot = min(v for v in offs if x["in"] <= v)
        h = hashlib.sha1(x["name"].lower().encode("utf-8")).hexdigest()[:8]
        out.append({"key": f"car:{h}:{x['day']}:{slot}", "also": [f"car:{h}:{x['day']}:{v}" for v in offs if v > slot],
                    "title": f"{x['name']} {M.in_days(x['in'])}", "body": f"{x['name']}: {M.short_day(x['day'])} ({M.in_days(x['in'])}).", "priority": "default", "tags": "car"})
    return out


def car_section(S: dict, t=None) -> dict:
    base = {"id": "car", "title": "Car", "connect": CONNECT["car"], "src": {"name": "What you typed (PC)", "t": t}}
    if not S["has"]:
        return {**base, "state": "empty", "line": "No car details yet", "cards": []}
    cards = []
    o = S["oil"]
    if o:
        val = ("Due now" if (o["miles_left"] is not None and o["miles_left"] <= 0) or (o["in"] is not None and o["in"] <= 0) else
               f"in {o['miles_left']:,} mi" if o["miles_left"] is not None else M.in_days(o["in"]))
        cards.append({"id": "oil", "title": "Oil change", "value": val, "sub": (f"about {M.short_day(o['due_day'])} · " if o["due_day"] else "") + f"every {o['every_miles']:,.0f} mi or {o['every_months']:g} months",
                      "lvl": "warn" if o["soon"] else "", "rows": [{"k": "Last change", "v": (f"{o['last_miles']:,.0f} mi" if o["last_miles"] is not None else "-"), "s": M.short_day(o["last_day"]) if o["last_day"] else ""},
                                                                   {"k": "By miles", "v": M.short_day(o["by_miles_day"]) if o["by_miles_day"] else "-", "s": ""},
                                                                   {"k": "By months", "v": M.short_day(o["by_time_day"]) if o["by_time_day"] else "-", "s": ""}],
                      "note": "Whichever comes first. Done? python tools\\me_life.py --car-oil-done"})
    if S["dates"]:
        nx = S["dates"][0]
        cards.append({"id": "dates", "title": "Registration and renewals", "value": M.short_day(nx["day"]), "sub": f"{nx['name']} · {M.in_days(nx['in'])}",
                      "lvl": "warn" if 0 <= nx["in"] <= 14 else "bad" if nx["in"] < 0 else "", "rows": [{"k": x["name"], "v": M.short_day(x["day"]), "s": M.in_days(x["in"]),
                                                                                                         "lvl": "bad" if x["in"] < 0 else "warn" if x["in"] <= 14 else ""} for x in S["dates"]]})
    if S["miles_now"] is not None:
        cards.append({"id": "miles", "title": "Mileage", "value": f"{S['miles_now']:,} mi", "sub": f"estimated today · about {S['per_month']:,} mi a month",
                      "lvl": "", "rows": [{"k": M.short_day(r["day"]), "v": f"{r['miles']:,.0f} mi", "s": "typed"} for r in reversed(S["readings"])],
                      "note": f"Pace {S['pace_src']}. Add a reading now and then: python tools\\me_life.py --car-miles 48210"})
    line = " · ".join(c["title"] + " " + c["value"] for c in cards[:2])
    return {**base, "state": "ok", "line": line, "cards": cards}


# ------------------------------------------------------------------------------------------------ Streaks (from the Apple Watch days)
STREAKS = (("steps", "steps", "Steps", lambda g: f"{g:,.0f}+ steps"), ("active_kcal", "move", "Move", lambda g: f"{g:,.0f}+ kcal"),
           ("exercise_min", "exercise", "Exercise", lambda g: f"{g:g}+ min"), ("stand_h", "stand", "Stand", lambda g: f"{g:g}+ hours"),
           ("sleep_h", "sleep", "Sleep", lambda g: f"{g:g}+ h"))


def streaks(health: dict | None, today: str) -> list:
    Hh = M.obj(health)
    rows = {r.get("date"): r for r in M.arr(Hh.get("days")) if isinstance(r, dict) and r.get("date")}
    goals = {**{"move": 500, "exercise": 30, "stand": 12, "steps": 8000, "sleep": 7.5}, **M.obj(Hh.get("goals"))}
    out = []
    for key, g, label, words in STREAKS:
        goal = M.num(goals.get(g))
        hit = lambda d: M.num(M.obj(rows.get(d)).get(key)) is not None and M.num(rows[d][key]) >= goal  # noqa: E731
        if not goal or not any(M.num(M.obj(r).get(key)) is not None for r in rows.values()):
            continue
        start = today if hit(today) else M.add_days(today, -1)          # today is not over yet: it never breaks a streak
        cur, d = 0, start
        while hit(d):
            cur += 1
            d = M.add_days(d, -1)
        best = run = 0
        for i in range(59, -1, -1):
            if hit(M.add_days(today, -i)):
                run += 1
                best = max(best, run)
            else:
                run = 0
        out.append({"id": g, "label": label, "goal": goal, "goal_words": words(goal), "current": cur, "best": best, "today": hit(today)})
    return out


def streaks_section(items: list, t=None) -> dict:
    base = {"id": "streaks", "title": "Streaks", "connect": CONNECT["streaks"], "src": {"name": "Apple Watch days", "t": t}}
    if not items:
        return {**base, "state": "empty", "line": "No days yet", "cards": []}
    cards = [{"id": x["id"], "title": x["label"], "value": M.plural(x["current"], "day"), "sub": f"in a row at {x['goal_words']} · best {x['best']} in 60 days" + (" · done today" if x["today"] else ""),
              "lvl": "ok" if x["current"] >= 3 else "", "pct": min(100.0, x["current"] / max(1, x["best"]) * 100.0) if x["best"] else 0.0, "rows": []} for x in items]
    top = max(items, key=lambda x: x["current"])
    line = f"Best now: {top['label']} {M.plural(top['current'], 'day')} in a row" if top["current"] else "No streak running: one goal met today starts one"
    return {**base, "state": "ok", "line": line, "cards": cards}


# ------------------------------------------------------------------------------------------------ the CLI
def main(argv=None, env=None, say=print, now_s: float | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freedom, dates, car and streaks for the Me hub (private, on this PC).")
    ap.add_argument("--paycheck", help="your take-home pay a month in $")
    ap.add_argument("--agency", help="the agency's monthly recurring revenue in $")
    ap.add_argument("--target", help="the side income a month you want before you quit (default: your paycheck)")
    ap.add_argument("--date", action="append", default=[], metavar="NAME=MM-DD|YYYY-MM-DD")
    ap.add_argument("--date-remove", action="append", default=[], metavar="NAME")
    ap.add_argument("--car-name")
    ap.add_argument("--car-miles")
    ap.add_argument("--car-oil-done", nargs="?", const="", default=None, metavar="MILES")
    ap.add_argument("--car-oil-every")
    ap.add_argument("--car-oil-months")
    ap.add_argument("--car-date", action="append", default=[], metavar="NAME=YYYY-MM-DD")
    a = ap.parse_args(argv)
    now_s = time.time() if now_s is None else now_s
    today = M.ny_day(now_s)
    if a.paycheck or a.agency or a.target:
        f = load("freedom.json", env)
        for k, v, lo, hi in (("paycheck_month", a.paycheck, 0, 100000), ("agency_mrr", a.agency, 0, 1000000), ("target_month", a.target, 0, 100000)):
            if v is None:
                continue
            x = M.num(v)
            if x is None or not lo <= x <= hi:
                say(f"  [FIX] {k}: a number of $ a month")
                return 2
            f[k] = x
        M.write_json(pfile("freedom.json", env), f)
        say("  [OK]  saved your pay / agency numbers")
    if a.date or a.date_remove:
        d = load("dates.json", env)
        lst = [x for x in M.arr(d.get("dates")) if isinstance(x, dict)]
        for s in a.date:
            rec, why = parse_date_arg(s)
            if not rec:
                say(f"  [FIX] {s!r}: {why}")
                return 2
            lst = [x for x in lst if str(x.get("name", "")).lower() != rec["name"].lower()] + [rec]
            say(f"  [OK]  {rec['name']}: {rec['date']} ({'every year' if rec['yearly'] else 'once'}, {rec['kind']})")
        for n in a.date_remove:
            before = len(lst)
            lst = [x for x in lst if str(x.get("name", "")).lower() != n.strip().lower()]
            say(f"  [OK]  removed {n!r}" if len(lst) < before else f"  [..] no date called {n!r}")
        M.write_json(pfile("dates.json", env), {"v": 1, "dates": sorted(lst, key=lambda x: str(x.get("date")))})
    if any(v is not None for v in (a.car_name, a.car_miles, a.car_oil_done, a.car_oil_every, a.car_oil_months)) or a.car_date:
        c = load("car.json", env)
        if a.car_name:
            c["name"] = M.clean(a.car_name, 30)
        if a.car_miles:
            x = M.num(a.car_miles)
            if x is None or not 0 <= x <= 2_000_000:
                say("  [FIX] --car-miles: the odometer in miles")
                return 2
            c["readings"] = [r for r in M.arr(c.get("readings")) if M.obj(r).get("day") != today] + [{"day": today, "miles": x}]
        oil = M.obj(c.get("oil"))
        for k, v in (("every_miles", a.car_oil_every), ("every_months", a.car_oil_months)):
            if v:
                x = M.num(v)
                if x is None or x <= 0:
                    say(f"  [FIX] {k}: a number")
                    return 2
                oil[k] = x
        if a.car_oil_done is not None:
            S = car_state(c, today)
            x = M.num(a.car_oil_done) if a.car_oil_done else S["miles_now"]
            oil.update(last_day=today, last_miles=x)
        c["oil"] = oil
        ds = M.obj(c.get("dates"))
        for s in a.car_date:
            k, _, v = s.partition("=")
            if not k.strip() or not (M.parse_day(v.strip()) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip())):
                say(f"  [FIX] {s!r}: use registration=2027-03-31")
                return 2
            ds[M.clean(k, 30).lower().replace(" ", "_")] = v.strip()
        c["dates"] = ds
        M.write_json(pfile("car.json", env), c)
        say("  [OK]  car saved")
    from tools import me_hub
    doc = me_hub.build(now_s, env)
    for sec in doc["sections"]:
        if sec["id"] in ("freedom", "dates", "car", "streaks"):
            say(f"  {sec['title']}: {sec.get('line') or ''}" + ("" if sec["state"] != "empty" else f"  ({sec['connect']})"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
