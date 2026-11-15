"""ME HUB (team ME1, 2026-11-14, docs/ME_HUB.md): the one organized place for your personal life, made on the PC for the phone's Me hub
(hub/?h=me). It reads what the other tools already make, adds what you typed once, and writes ONE file, data/me/me.json:

  tiles     the 4 status tiles on top: Money left this month, Health today, Home OK / issue, Next important date (each: value, one line,
            its source and the time of its data, the section it opens, and the one line that says how to connect it when it is empty)
  sections  Money (spending this month vs last by category, subscriptions + next charges, bills in the next 14 days, net worth;
            money_out/household.json from tools/money_import.py), Cards (tools/me_cards.py), Health (data/me/health.json, tools/me_health.py),
            Home & WiFi (data/me/home.json, tools/me_home.py), Freedom, Dates, Car, Streaks (tools/me_life.py). Each: a short stack of
            cards, each card a value, a line and its detail rows (one tap on the phone).

The PC report (tools/pc_report.py, every 15 minutes) calls maybe_run(): the home checks (me_home), the health file (me_health), me.json,
then the reminders on your private ntfy topic (the PC report's own, %USERPROFILE%\\.olympus\\ntfy.json): a card due in 5 days and 1 day, a
birthday in 7 days and 1 day (other dates 3 and 1), the car (oil soon, renewals 14 and 3 days), a new device on your Wi-Fi, the internet
back after an outage, the disk almost full. Reminders only 08:00-21:00 New York; each one once (data/me/state.json). A push carries a
nickname and a date, never a balance, an IP or a MAC.

PRIVATE: data/me/ (gitignored) is served only by the PC's own link (engine/live_site.py /site/me/), never copied to a site folder, never
published (PUBLISH_NQ, Netlify, GitHub Pages). LE_ME=0 turns the hook off; LE_PR_NO_NET=1 (the tests) skips every network check.

  python tools/me_hub.py               build me.json now (home checks included) and print the four tiles
  python tools/me_hub.py --dry-run     the same, printing the pushes instead of sending them
  python tools/me_hub.py --no-home     without the home checks (no network)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import me_cards, me_health, me_home, me_life  # noqa: E402
from tools import me_core as M  # noqa: E402

OUT_NAME = "me.json"
STATE = "state.json"
QUIET = (8, 21)                 # reminders between 08:00 and 21:00 New York
KEEP_SENT_DAYS = 120
STALE_BANK_DAYS = 10
CONNECT = {
    "money": "On the PC: put a bank or card CSV in %USERPROFILE%\\.olympus\\money_inbox\\ and double-click RUN_MONEY.bat (docs/CONNECT_MONEY.md)",
    "cards": me_cards.CONNECT,
    "health": me_health.CONNECT,
    "home": me_home.CONNECT,
    **me_life.CONNECT,
}
TITLES = {"money": "Money", "cards": "Cards", "health": "Health", "home": "Home & WiFi", "freedom": "Freedom", "dates": "Dates", "car": "Car", "streaks": "Streaks"}
ORDER = ("money", "cards", "health", "home", "freedom", "dates", "car", "streaks")


# ------------------------------------------------------------------------------------------------ the inputs
def household_doc(env=None):
    e = os.environ if env is None else env
    for p in ([os.path.join(e["LE_MONEY_OUT"], "household.json")] if e.get("LE_MONEY_OUT") else [os.path.join(ROOT, "money_out", "household.json")]) + \
             [os.path.join(M.olympus_dir(env), "money", "household.json")]:
        d = M.read_json(p)
        if isinstance(d, dict) and d.get("kind") == "olympus-household":
            return d
    return None


def day_doc(env=None):
    e = os.environ if env is None else env
    d = M.read_json(os.path.join(e.get("LE_DAY_DIR") or os.path.join(ROOT, "data", "day"), "day.json"))
    return d if isinstance(d, dict) and d.get("kind") == "olympus-day" else None


def mtime(p):
    try:
        return int(os.path.getmtime(p))
    except OSError:
        return None


def gather(env=None) -> dict:
    """every input of build(), from the files (tests pass their own dict)"""
    return {"household": household_doc(env), "cards": me_cards.load(env), "cards_t": mtime(me_cards.path(env)),
            "health": M.read_json(os.path.join(M.out_dir(env), me_health.OUT_NAME)), "home": M.read_json(os.path.join(M.out_dir(env), me_home.OUT_NAME)),
            "day": day_doc(env), "dates": me_life.load("dates.json", env), "dates_t": mtime(me_life.pfile("dates.json", env)),
            "car": me_life.load("car.json", env), "car_t": mtime(me_life.pfile("car.json", env)), "freedom": me_life.load("freedom.json", env),
            "agency": me_life.agency_mrr(money_out=(os.environ if env is None else env).get("LE_MONEY_OUT"))}


def _ok(doc, kind):
    return isinstance(doc, dict) and doc.get("kind") == kind and doc.get("status", "ok") in ("ok",)


# ------------------------------------------------------------------------------------------------ Money (money/household.json)
def money_part(H, today: str) -> tuple:
    """(section, tile)"""
    base = {"id": "money", "title": TITLES["money"], "connect": CONNECT["money"]}
    tile = {"id": "money", "label": "Money left this month", "to": "money", "src": "Bank exports", "connect": CONNECT["money"]}
    if not _ok(H, "olympus-household"):
        return ({**base, "state": "empty", "line": "Not connected", "src": {"name": "Bank exports", "t": None}, "cards": []},
                {**tile, "empty": True, "value": "Not connected", "sub": "", "lvl": "", "t": None, "short": ""})
    data = M.obj(H.get("data"))
    last_day = data.get("last")
    src_t = M.day_epoch(last_day) if M.parse_day(last_day) else M.num(H.get("t"))
    age = M.days_between(last_day, today) if M.parse_day(last_day) else None
    cur, prev = M.obj(H.get("this_month")), M.obj(H.get("last_month"))
    cats = {k: M.obj(v) for k, v in M.obj(H.get("categories")).items()}
    spend = [c for c, v in cats.items() if v.get("kind") == "spend"]
    tb, lb = M.obj(cur.get("by_cat")), M.obj(prev.get("by_cat"))
    crow = sorted([(c, M.num(tb.get(c)) or 0.0, M.num(lb.get(c)) or 0.0) for c in spend if (M.num(tb.get(c)) or 0) > 0 or (M.num(lb.get(c)) or 0) > 0],
                  key=lambda x: (-x[1], -x[2]))
    top = max([x[1] for x in crow] + [x[2] for x in crow] + [1.0])
    so_far = " so far" if cur.get("partial") else ""
    rows = [{"k": cats[c].get("name") or c, "v": M.money(v), "s": f"last month {M.money(lv)}" + (" · more" if v > lv and lv else ""),
             "pct": round(v / top * 100.0, 1), "lvl": "warn" if lv and v > lv else ""} for c, v, lv in crow[:12]]
    c_spend = {"id": "spend", "title": f"Spending this month{so_far}", "value": M.money(M.num(cur.get("out")) or 0),
               "sub": f"all of last month {M.money(M.num(prev.get('out')) or 0)} · {M.money(M.num(cur.get('in')) or 0)} in{so_far}",
               "lvl": "warn" if (M.num(cur.get("out")) or 0) > (M.num(prev.get("out")) or 0) > 0 else "", "rows": rows,
               "note": "By category, biggest first; the bar is the biggest of the two months. Transfers and card payments are left out."}
    subs = [s for s in M.arr(M.obj(H.get("subscriptions")).get("items")) if isinstance(s, dict) and s.get("active")]
    subs.sort(key=lambda s: (str(s.get("next") or "9999"), str(s.get("label") or "")))
    srows = [{"k": M.clean(s.get("merchant") or s.get("label"), 40), "v": f"{M.money(s.get('usd'))} a {s.get('every') or 'month'}",
              "s": f"next {M.short_day(s['next'])}" + (" · bill" if s.get("type") == "bill" else "") + (f" · up {M.money(s['price_up'])}" if M.num(s.get("price_up")) else ""),
              "lvl": "warn" if M.num(s.get("price_up")) else ""} for s in subs if s.get("next")]
    nxt = next((s for s in subs if s.get("next") and s["next"] >= today), None)
    c_subs = {"id": "subs", "title": "Subscriptions and bills", "value": f"{M.money(M.obj(H.get('subscriptions')).get('usd_month') or 0)} a month",
              "sub": f"{M.plural(len(subs), 'running charge')}" + (f" · next {M.clean(nxt.get('label'), 30)} {M.short_day(nxt['next'])}" if nxt else ""),
              "lvl": "", "rows": srows[:20], "note": "Found from 2-3 months of charges at the same store for the same amount."}
    end14 = M.add_days(today, 14)
    due = [s for s in subs if s.get("next") and today <= s["next"] <= end14]
    drows = [{"k": M.clean(s.get("merchant") or s.get("label"), 40), "v": M.money(s.get("usd")), "s": f"{M.short_day(s['next'])} · {M.in_days(M.days_between(today, s['next']))}",
              "lvl": "warn" if M.days_between(today, s["next"]) <= 2 else ""} for s in due]
    c_due = {"id": "due", "title": "Due in the next 14 days", "value": M.money(sum(M.num(s.get("usd")) or 0 for s in due)),
             "sub": f"{M.plural(len(due), 'charge')}" + (f" · first {M.short_day(due[0]['next'])}" if due else ""), "lvl": "", "rows": drows,
             "note": "Your recurring charges whose next date falls in the next 14 days (estimated from their last charge)."}
    nw = M.obj(H.get("networth"))
    arows = [{"k": M.clean(a.get("name"), 40), "v": M.money(a.get("usd")), "s": str(a.get("kind") or "") + (f" · {a['updated']}" if a.get("updated") else "")}
             for a in M.arr(nw.get("accounts")) if isinstance(a, dict)]
    c_nw = {"id": "networth", "title": "Net worth", "value": M.money(nw.get("total")) if nw.get("total") is not None else "Add balances",
            "sub": (f"{M.money(nw.get('change_30d'), True)} in 30 days · " if nw.get("change_30d") is not None else "") + (f"{M.money(nw.get('assets'))} assets, {M.money(nw.get('debts'))} owed" if nw.get("total") is not None else "python tools\\money_import.py --balance \"Checking=2500\""),
            "lvl": "", "rows": arows, "note": M.clean(M.obj(H.get("runway")).get("text"), 300)}
    # the tile: what is left of a usual month's money in, after the spending so far and the charges still due this month
    a3 = M.obj(H.get("avg3"))
    usual = max(M.num(a3.get("in")) or 0.0, M.num(cur.get("in")) or 0.0) if a3.get("months") else (M.num(cur.get("in")) or 0.0)
    rest = [s for s in subs if s.get("next") and today < s["next"] <= M.month_end(today)]
    still = round(sum(M.num(s.get("usd")) or 0 for s in rest), 2)
    out = M.num(cur.get("out")) or 0.0
    if usual > 0:
        left = round(usual - out - still, 2)
        lvl = "bad" if left < 0 else "warn" if left < 0.1 * usual else "ok"
        tile = {**tile, "empty": False, "value": M.money(left), "lvl": lvl, "short": f"{M.money(left)} left",
                "sub": f"of your usual {M.money(usual)} in · {M.money(out)} spent · {M.money(still)} still due"}
    else:
        tile = {**tile, "empty": False, "value": M.money(M.num(cur.get("net")) or 0, True), "lvl": "", "short": "Money in / out",
                "sub": "no money in yet this month: it needs a month of bank data"}
    tile["t"] = src_t
    stale = age is not None and age > STALE_BANK_DAYS
    sec = {**base, "state": "stale" if stale else "ok", "src": {"name": "Bank exports", "t": src_t, "note": f"newest row {last_day}" if last_day else ""},
           "line": f"{M.money(out)} spent{so_far} · {M.money(M.obj(H.get('subscriptions')).get('usd_month') or 0)} a month of charges",
           "stale_note": f"Your newest bank row is {age} days old: download a fresh export (step 1 of docs/CONNECT_MONEY.md)." if stale else "",
           "cards": [c_spend, c_subs, c_due, c_nw]}
    return sec, tile


# ------------------------------------------------------------------------------------------------ Health (me/health.json)
def _n(v, nd=0):
    x = M.num(v)
    return "-" if x is None else (f"{x:,.0f}" if nd == 0 else f"{x:,.{nd}f}")


def health_part(HJ, today: str) -> tuple:
    base = {"id": "health", "title": TITLES["health"], "connect": CONNECT["health"]}
    tile = {"id": "health", "label": "Health today", "to": "health", "src": "Apple Watch", "connect": CONNECT["health"]}
    if not _ok(HJ, "olympus-health"):
        return ({**base, "state": "empty", "line": "Not connected", "src": {"name": "Apple Watch (Shortcut)", "t": None}, "cards": []},
                {**tile, "empty": True, "value": "Not connected", "sub": "", "lvl": "", "t": None, "short": ""})
    tr, lr = M.obj(HJ.get("today_row")), M.obj(HJ.get("last_row"))
    is_today = bool(tr)
    row = tr if is_today else lr
    rings = M.arr(HJ.get("today_rings") if is_today else HJ.get("last_rings"))
    goals = M.obj(HJ.get("goals"))
    rec = M.obj(HJ.get("recovery"))
    trd = M.obj(HJ.get("trends"))
    when = "Today" if is_today else (M.short_day(row.get("date")) if row.get("date") else "-")
    rrows = [{"k": r["label"], "v": (f"{_n(r['value'], 1 if r['unit'] == 'h' else 0)} of {_n(r['goal'], 1 if r['unit'] == 'h' and r['goal'] % 1 else 0)} {r['unit']}".strip() if r.get("value") is not None else "-"),
              "s": ("done" if r.get("done") else f"{r['pct']:.0f}%" if r.get("pct") is not None else "no number"), "pct": min(100.0, r["pct"]) if r.get("pct") is not None else None,
              "lvl": "ok" if r.get("done") else ""} for r in rings]
    c_day = {"id": "today", "title": when if is_today else f"Last day ({when})", "value": f"{_n(row.get('steps'))} steps",
             "sub": " · ".join(x for x in (f"move {_n(row.get('active_kcal'))} kcal" if row.get("active_kcal") is not None else "", f"{_n(row.get('exercise_min'))} min exercise" if row.get("exercise_min") is not None else "",
                                           f"stand {_n(row.get('stand_h'))} h" if row.get("stand_h") is not None else "") if x) or "no activity numbers",
             "lvl": "ok" if any(r.get("done") for r in rings[:3]) else "", "rows": rrows,
             "note": "Rings-style goals: Move, Exercise and Stand from your watch (your own goals when the export had them), Steps and Sleep yours: python tools\\me_health.py --goal steps=10000"}
    sl = M.num(M.obj(tr).get("sleep_h"))
    week = M.arr(HJ.get("week"))
    sgoal = M.num(goals.get("sleep")) or 7.5
    srows = [{"k": f"{w['dow']} {w['date'][5:]}", "v": f"{w['sleep_h']:.1f} h" if w.get("sleep_h") is not None else "-", "pct": min(100.0, w["sleep_h"] / sgoal * 100.0) if w.get("sleep_h") is not None else None,
              "lvl": "ok" if (w.get("sleep_h") or 0) >= sgoal else ""} for w in week if not w.get("future")]
    c_sleep = {"id": "sleep", "title": "Last night", "value": f"{sl:.1f} h" if sl is not None else "Not yet",
               "sub": (" · ".join(x for x in (f"deep {M.num(tr.get('sleep_deep_h')):.1f} h" if M.num(tr.get("sleep_deep_h")) is not None else "", f"REM {M.num(tr.get('sleep_rem_h')):.1f} h" if M.num(tr.get("sleep_rem_h")) is not None else "",
                                              f"7-day average {M.obj(trd.get('sleep_h')).get('d7'):.1f} h" if M.obj(trd.get("sleep_h")).get("d7") is not None else "") if x) if sl is not None else "the Shortcut sends it each evening"),
               "lvl": "ok" if sl is not None and sl >= sgoal else "warn" if sl is not None and sl < sgoal - 1 else "", "rows": srows, "note": f"Goal {sgoal:g} h a night."}
    sgoal_steps = M.num(goals.get("steps")) or 8000
    ws = [w for w in week if w.get("steps") is not None and not w.get("future")]
    wrows = [{"k": f"{w['dow']} {w['date'][5:]}", "v": _n(w.get("steps")) if w.get("steps") is not None else "-", "s": f"{_n(w.get('exercise_min'))} min exercise" if w.get("exercise_min") is not None else "",
              "pct": min(100.0, w["steps"] / sgoal_steps * 100.0) if w.get("steps") is not None else None, "lvl": "ok" if (w.get("steps") or 0) >= sgoal_steps else ""} for w in week if not w.get("future")]
    c_week = {"id": "week", "title": "This week", "value": f"{_n(sum(w['steps'] for w in ws))} steps",
              "sub": (f"about {_n(sum(w['steps'] for w in ws) / len(ws))} a day · goal {_n(sgoal_steps)}" if ws else "no steps this week yet"), "lvl": "", "rows": wrows,
              "note": "Monday to today."}
    t_rhr, t_hrv, t_w = M.obj(trd.get("rhr")), M.obj(trd.get("hrv_ms")), M.obj(trd.get("weight_lb"))
    hrows = [{"k": "Resting heart rate", "v": f"{_n(t_rhr.get('d7'))} bpm" if t_rhr.get("d7") is not None else "-", "s": f"30 days {_n(t_rhr.get('d30'))} · {t_rhr.get('way', 'flat')} (down is good)", "lvl": t_rhr.get("lvl", "")},
             {"k": "HRV", "v": f"{_n(t_hrv.get('d7'))} ms" if t_hrv.get("d7") is not None else "-", "s": f"30 days {_n(t_hrv.get('d30'))} · {t_hrv.get('way', 'flat')} (up is good)", "lvl": t_hrv.get("lvl", "")}]
    if t_w.get("d7") is not None:
        hrows.append({"k": "Weight", "v": f"{_n(t_w.get('d7'), 1)} lb", "s": f"30 days {_n(t_w.get('d30'), 1)}"})
    c_rec = {"id": "recovery", "title": "Recovered?", "value": rec.get("word") or "-", "sub": M.clean(rec.get("text"), 220), "lvl": rec.get("level") or "", "rows": hrows,
             "note": "Your own 7-day numbers against your 30-day normal. Plain numbers, not medical advice."}
    wk = M.arr(HJ.get("workouts"))
    krows = [{"k": f"{M.short_day(w['date'])}", "v": M.clean(w.get("type"), 60), "s": " · ".join(x for x in (f"{_n(w.get('min'))} min" if w.get("min") is not None else "", f"{_n(w.get('kcal'))} kcal" if w.get("kcal") is not None else "",
                                                                                                       f"{_n(w.get('km'), 1)} km" if w.get("km") else "") if x)} for w in wk[:12]]
    n7 = sum(1 for w in wk if M.days_between(w["date"], today) < 7)
    c_wk = {"id": "workouts", "title": "Workouts", "value": f"{n7} this week", "sub": (M.clean(wk[0].get("type"), 40) + f" {M.short_day(wk[0]['date'])}" if wk else "none in the last 2 weeks"), "lvl": "", "rows": krows}
    cards = [c_day, c_sleep, c_week, c_rec, c_wk]
    src_t = M.num(HJ.get("src_t"))
    parts = [f"{_n(row.get('steps'))} steps"] if row.get("steps") is not None else []
    if sl is not None:
        parts.append(f"slept {sl:.1f} h")
    elif row.get("exercise_min") is not None:
        parts.append(f"{_n(row.get('exercise_min'))} min exercise")
    tile = {**tile, "empty": False, "t": src_t, "value": f"{_n(row.get('steps'))} steps" if row.get("steps") is not None else (rec.get("word") or "-"),
            "sub": (" · ".join(parts[1:] + ([rec["word"]] if rec.get("level") else [])) if is_today else f"from {when}: today's numbers come with the evening Shortcut"),
            "lvl": rec.get("level") or "", "short": parts[0] if parts else (rec.get("word") or "")}
    return ({**base, "state": "ok", "src": {"name": "Apple Watch (Shortcut)", "t": src_t, "note": "export imported" if M.obj(M.obj(HJ.get("sources")).get("export")).get("imported_t") else ""},
             "line": f"{when}: " + " · ".join(parts) if parts else when, "cards": cards}, tile)


# ------------------------------------------------------------------------------------------------ Home (me/home.json)
def home_part(HM, today: str) -> tuple:
    base = {"id": "home", "title": TITLES["home"], "connect": CONNECT["home"]}
    tile = {"id": "home", "label": "Home", "to": "home", "src": "PC checks", "connect": CONNECT["home"]}
    if not (isinstance(HM, dict) and HM.get("kind") == "olympus-home"):
        return ({**base, "state": "empty", "line": "Not checked yet", "src": {"name": "PC checks", "t": None}, "cards": []},
                {**tile, "empty": True, "value": "Not checked yet", "sub": "", "lvl": "", "t": None, "short": ""})
    st, net, outs, dv, pc = (M.obj(HM.get(k)) for k in ("status", "internet", "outages", "devices", "pc"))
    last, avg = M.obj(net.get("last")), M.obj(net.get("avg7"))
    tests = M.arr(net.get("tests"))
    top = max([M.num(x.get("down_mbps")) or 0 for x in tests] + [1.0])
    trows = [{"k": M.ny_dt(x["t"]).strftime("%a %H:%M"), "v": f"{_n(x.get('down_mbps'))} / {_n(x.get('up_mbps'))} Mbps", "s": f"ping {_n(x.get('ping_ms'))} ms",
              "pct": round((M.num(x.get("down_mbps")) or 0) / top * 100.0, 1)} for x in reversed(tests[-12:]) if x.get("t")]
    on = net.get("online")
    c_net = {"id": "internet", "title": "Internet", "value": ("Down" if on is False else f"{_n(last.get('down_mbps'))} Mbps" if last else "Up" if on else "-"),
             "sub": (f"down · {_n(last.get('up_mbps'))} up · ping {_n(last.get('ping_ms'))} ms" + (f" · usual {_n(avg.get('down_mbps'))}" if avg.get("down_mbps") else "") if last and on is not False else
                     "no speed test yet (every 4 hours)" if on else "the PC cannot reach the internet"),
             "lvl": "bad" if on is False else "", "rows": trows, "note": "A light test against Cloudflare's free speed endpoints every 4 hours (24 MB at most): often a bit below a full speed test on a fast line."}
    orows = [{"k": M.ny_dt(o["from"]).strftime("%a %b %d %H:%M"), "v": ("still down" if o.get("open") else "a short drop" if o.get("blip") else f"about {o.get('mins')} min"),
              "s": ("since then" if o.get("open") else "back " + M.ny_dt(o["to"]).strftime("%H:%M")), "lvl": "bad" if o.get("open") else "warn"} for o in M.arr(outs.get("list"))[:12]]
    c_out = {"id": "outages", "title": "Outages", "value": f"{outs.get('today', 0)} today", "sub": f"{outs.get('week', 0)} in the last 7 days", "lvl": "warn" if (outs.get("today") or 0) else "",
             "rows": orows, "note": "Checked every 15 minutes while the PC is on: a drop shorter than that can be missed."}
    drows = [{"k": d.get("name"), "v": ("NEW" if d.get("new") else "online" if d.get("online") else "away"),
              "s": " · ".join(x for x in (d.get("vendor") if d.get("vendor") not in (d.get("name"), None) else "", d.get("hint") if not d.get("named") else "", d.get("ip") or "", "…" + str(d.get("mac_tail") or "")) if x),
              "lvl": "warn" if d.get("new") else "ok" if d.get("online") else ""} for d in M.arr(dv.get("list"))[:40]]
    c_dev = {"id": "devices", "title": "Devices on your Wi-Fi", "value": M.plural(dv.get("n") or 0, "device"), "sub": f"{dv.get('online', 0)} online now · {dv.get('new', 0)} new",
             "lvl": "warn" if dv.get("new") else "", "rows": drows,
             "note": "Name one on the PC: python tools\\me_home.py --devices, then --name <id>=\"Mom's iPad\". A phone with a private Wi-Fi address can show up as new when it changes it."}
    prow = [{"k": "Disk", "v": f"{_n(pc.get('disk_free_gb'), 1)} GB free" if pc.get("disk_free_gb") is not None else "-", "s": f"{_n(pc.get('disk_free_pct'))}% of {_n(pc.get('disk_total_gb'))} GB",
             "pct": round(100.0 - (M.num(pc.get("disk_free_pct")) or 0), 1) if pc.get("disk_free_pct") is not None else None, "lvl": "warn" if (M.num(pc.get("disk_free_pct")) or 100) < me_home.DISK_LOW_PCT else ""},
            {"k": "Memory", "v": f"{_n(pc.get('mem_used_pct'))}% used" if pc.get("mem_used_pct") is not None else "-"},
            {"k": "Up since", "v": M.ny_dt(pc["boot_t"]).strftime("%a %b %d %H:%M") if pc.get("boot_t") else "-", "s": f"{_n(M.num(pc.get('uptime_h')) / 24.0 if pc.get('uptime_h') is not None else None, 1)} days" if pc.get("uptime_h") is not None else ""},
            {"k": "CPU temperature", "v": f"{_n(pc.get('cpu_temp_c'))} °C" if pc.get("cpu_temp_c") is not None else "not given", "s": "" if pc.get("cpu_temp_c") is not None else "Windows often hides it without admin"}]
    c_pc = {"id": "pc", "title": "This PC", "value": f"{_n(pc.get('disk_free_gb'), 1)} GB free" if pc.get("disk_free_gb") is not None else "-",
            "sub": f"up {_n(M.num(pc.get('uptime_h')) / 24.0, 1)} days" if pc.get("uptime_h") is not None else "", "lvl": prow[0]["lvl"], "rows": prow}
    t = M.num(HM.get("t"))
    ok_sub = " · ".join(x for x in (f"{_n(last.get('down_mbps'))} Mbps down" if last else "", f"{dv.get('online', 0)} devices online" if dv.get("n") else "") if x)
    sub = ok_sub if st.get("lvl") == "ok" and ok_sub else (st.get("text") or "")
    tile = {**tile, "empty": False, "t": t, "value": st.get("short") or "-", "sub": sub, "lvl": st.get("lvl") or "", "short": st.get("short") or ""}
    return ({**base, "state": "ok", "src": {"name": "PC checks", "t": t, "note": "every 15 minutes"}, "line": st.get("text") or "", "cards": [c_net, c_out, c_dev, c_pc]}, tile)


# ------------------------------------------------------------------------------------------------ the file
def build(now_s: float | None = None, env=None, inputs: dict | None = None) -> dict:
    now_s = time.time() if now_s is None else now_s
    I = inputs if inputs is not None else gather(env)
    today = M.ny_day(now_s)
    H = I.get("household")
    money, t_money = money_part(H, today)
    accts = M.arr(M.obj(M.obj(H).get("networth")).get("accounts")) if _ok(H, "olympus-household") else []
    cards = me_cards.section(M.obj(I.get("cards")) or {"cards": []}, today, accts, I.get("cards_t"))
    health, t_health = health_part(I.get("health"), today)
    home, t_home = home_part(I.get("home"), today)
    F = me_life.freedom(H if _ok(H, "olympus-household") else None, I.get("day"), I.get("freedom"), I.get("agency"))
    freedom = me_life.freedom_section(F, M.num(M.obj(H).get("t")))
    car_s = me_life.car_state(I.get("car"), today)
    car = me_life.car_section(car_s, I.get("car_t"))
    items = me_life.dates(I.get("dates"), I.get("day"), car_s["dates"], today)
    dates = me_life.dates_section(items, max([x for x in (M.num(M.obj(I.get("day")).get("t")), I.get("dates_t")) if x] or [None]) if (I.get("day") or I.get("dates_t")) else None)
    streaks = me_life.streaks_section(me_life.streaks(I.get("health"), today), M.num(M.obj(I.get("health")).get("src_t")))
    nx = items[0] if items else None
    t_date = {"id": "date", "label": "Next important date", "to": "dates", "src": "Your dates + calendars", "connect": CONNECT["dates"], "t": dates["src"]["t"],
              "empty": nx is None, "value": (nx["name"] if nx else "Nothing soon"), "sub": (f"{M.short_day(nx['day'])} · {M.in_days(nx['in'])}" if nx else f"nothing in the next {me_life.HORIZON} days"),
              "lvl": "warn" if nx and nx["in"] <= 1 else "", "short": (f"{nx['name'][:18]} {M.in_days(nx['in'])}" if nx else "")}
    if nx is None and not (I.get("dates_t") or I.get("day")):
        t_date.update(value="Not connected", sub="")
    secs = {"money": money, "cards": cards, "health": health, "home": home, "freedom": freedom, "dates": dates, "car": car, "streaks": streaks}
    for k, s in secs.items():
        s.pop("summary", None)
    doc = {"v": 1, "kind": "olympus-me", "t": int(now_s), "built": dt.datetime.fromtimestamp(now_s, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "today": today, "private": True, "paper_only": True,
           "about": "Your money, cards, health, home and dates in one place, made on your PC. Private: only the PC's own link serves it, never the public site.",
           "tiles": [t_money, t_health, t_home, t_date], "sections": [secs[k] for k in ORDER],
           "connected": {k: secs[k]["state"] != "empty" for k in ORDER}}
    return M.scrub_doc(doc)


def write(doc: dict, env=None) -> str:
    return M.write_json(os.path.join(M.out_dir(env), OUT_NAME), doc, compact=True)


# ------------------------------------------------------------------------------------------------ the reminders
def reminders(I: dict, today: str) -> list:
    car_s = me_life.car_state(I.get("car"), today)
    items = me_life.dates(I.get("dates"), I.get("day"), car_s["dates"], today)
    return me_cards.reminders(M.obj(I.get("cards")) or {"cards": []}, today) + me_life.date_reminders(items) + me_life.car_reminders(car_s)


def quiet_ok(now_s: float) -> bool:
    h = M.ny_dt(now_s).hour
    return QUIET[0] <= h < QUIET[1]


def send(msgs: list, state: dict, now_s: float, env=None, http=None, dry=False, say=print) -> tuple:
    """(new state, sent count): each key once; 'also' keys are marked with it (a 1-day reminder retires its 5-day one)"""
    st = {"sent": {k: v for k, v in M.obj(M.obj(state).get("sent")).items() if now_s - (M.num(v) or 0) <= KEEP_SENT_DAYS * 86400}}
    todo = [m for m in msgs if m["key"] not in st["sent"]]
    if not todo:
        return st, 0
    from tools import pc_report as PR
    cfg = PR.load_cfg(env)
    sent = 0
    for m in todo:
        if dry:
            say(f"  [dry] push: {m['title']}: {m['body']}")
            continue
        if not cfg.get("topic") or not cfg.get("on"):
            break
        ok, why = PR.ntfy_post(cfg["ntfy"], cfg["topic"], m["body"], title=m["title"], priority=m.get("priority"), tags=m.get("tags"), http=http)
        if not ok:
            say(f"  [..] Me hub push not sent: {why}")
            continue
        sent += 1
        for k in [m["key"]] + list(m.get("also") or []):
            st["sent"][k] = int(now_s)
    return st, sent


def maybe_run(now_s: float | None = None, env=None, say=print, http=None, dry: bool = False, home: bool = True, home_kw: dict | None = None) -> dict | None:
    """the hook tools/pc_report.py calls every 15 minutes. Never raises."""
    try:
        e = os.environ if env is None else env
        if str(e.get("LE_ME", "1")) == "0":
            return None
        now_s = time.time() if now_s is None else now_s
        events = []
        if home and str(e.get("LE_PR_NO_NET", "")) != "1":
            try:
                _d, events = me_home.maybe_run(now_s, env, **(home_kw or {}))
            except Exception as ex:  # noqa: BLE001
                say(f"  [..] home checks skipped: {ex.__class__.__name__}")
        try:
            me_health.build_and_write(now_s, env)
        except Exception as ex:  # noqa: BLE001
            say(f"  [..] health file skipped: {ex.__class__.__name__}")
        I = gather(env)
        doc = build(now_s, env, I)
        write(doc, env)
        msgs = list(events) + (reminders(I, doc["today"]) if quiet_ok(now_s) else [])
        sp = os.path.join(M.out_dir(env), STATE)
        st, n = send(msgs, M.read_json(sp, {}) or {}, now_s, env, http, dry, say)
        if not dry:
            M.write_json(sp, st, compact=True)
        say("  [OK]  Me hub: " + " · ".join(f"{t['label']}: {t['value']}" for t in doc["tiles"]) + (f" ({n} pushed)" if n else ""))
        return doc
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] Me hub skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The Me hub's file for the phone (private, on this PC).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-home", action="store_true")
    a = ap.parse_args(argv)
    doc = maybe_run(dry=a.dry_run, home=not a.no_home)
    if doc:
        for t in doc["tiles"]:
            print(f"  {t['label']:<24} {t['value']:<22} {t.get('sub') or t.get('connect') or ''}")
        print(f"  -> {os.path.join(M.out_dir(), OUT_NAME)} (served only by the PC's own link: /site/me/me.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
