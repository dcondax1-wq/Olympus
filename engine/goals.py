"""Goals (2026-10-25, read-only): where each account stands against the owner's goals, in plain sentences.

One pure function, build(data), over the data the cloud and the PC already have (the data.json blocks "accounts", "live",
"second", "scale", "perf"; on the PC the same blocks from the running bot) -> the goals JSON the phone's Home "Goals" card,
the PC agent (/api/next/goals) and the tests read. It never trades, never routes, never writes a file.

Owner goals (CLAUDE.md, 2026-10-17 / 10-25):
  * pass each eval within 2 weeks (10 sessions), never more than 3 (15)
  * LIT 2-4 trades a week; ATLAS 3-4 a week
  * month $ inside the backtest's expected band (engine/health_band.py, H2 bootstrap)
  * ATLAS go-live: 20 finished paper trades at / above the expected p10 (engine/second_scorecard.py)
  * then funded accounts and payouts, then scale (engine/scale_plan.py)
  * a $10,000 month by Jan / Feb 2027, then the car (owner 2026-10-26): part "money" = engine/money_goal.py

    python -X utf8 -m engine.goals [data.json]      prints the goals JSON of a built site (default site/data.json)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
NEWS_CSV = os.path.join(ROOT, "research", "hq", "news_calendar.csv")
SESSIONS_GOAL = 10                 # pass within 2 weeks
SESSIONS_MAX = 15                  # never more than 3 weeks
LIT_WEEK = (2, 4)                  # owner 2026-10-17
ATLAS_WEEK = (3, 4)                # owner 2026-10-25
ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
# account plans (MFFU Builder; the owner's prices). 50K numbers also come from the account's own eval block when it reports.
PLANS = {
    "lit50k": {"label": "MFFU Builder 50K", "strategy": "LIT", "start": 50000.0, "target": 3000.0, "mll": 2000.0, "min_days": 2,
               "price": 91.80},
    "atlas25k": {"label": "MFFU Builder 25K", "strategy": "ATLAS", "start": 25000.0, "target": 1500.0, "mll": 1000.0, "min_days": 2,
                 "price": 63.00},
}
PAYOUT_BUFFER = 2100.0             # engine/eval_life: ask for a payout only once $1,500+ sits above the $2,100 buffer
PAYOUT_ASK_ABOVE = 1500.0


# ------------------------------------------------------------------------------------------------ small helpers
def _f(x, d=None):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _money(v, sign=False) -> str:
    v = float(v or 0)
    s = f"${abs(v):,.0f}"
    if v < 0:
        return "-" + s
    return ("+" + s) if sign and v > 0 else s


def _clip(x, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, float(x)))


def _et(ts: int) -> dt.datetime:
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def trading_day(ts: int) -> str:
    """The CME trading day of a time: 18:00 ET starts the next day's session (same rule as engine/accounts.trading_day)."""
    return (_et(ts) + dt.timedelta(hours=6)).date().isoformat()


def monday(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def weekdays_between(a: str, b: str) -> int:
    """Weekdays from a to b, both included."""
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    n, d = 0, d0
    while d <= d1:
        n += d.weekday() < 5
        d += dt.timedelta(days=1)
    return n


def _plural(n, w):
    return f"{n} {w}{'' if n == 1 else 's'}"


# ------------------------------------------------------------------------------------------------ trades
def lit_trades(data: dict) -> tuple[list, str]:
    """LIT's finished trades [{day, r, usd, entry_t}] from the account Home follows (the PC's when it reports a connected
    eval, else the cloud paper ledger) and the name of that source."""
    acc = [a for a in data.get("accounts") or [] if isinstance(a, dict) and a.get("id") and not a.get("error")]
    pc = next((a for a in acc if a.get("source") == "pc" and a.get("kind") in ("eval", "funded", None)), None)
    cl = next((a for a in acc if a.get("source") == "cloud"), None)
    use = pc if pc and ((pc.get("conn") or {}).get("connected") or pc.get("trades")) else cl or pc
    rows = []
    for t in (use or {}).get("trades") or []:
        if not t.get("day"):
            continue
        rows.append({"day": str(t["day"]), "r": _f(t.get("r")), "usd": _f(t.get("pnl"), 0.0), "entry_t": t.get("entry_t")})
    if not rows and not use:                  # no accounts block: the cloud ledger in live.ledger
        for v in (data.get("live") or {}).get("ledger") or []:
            if isinstance(v, dict) and v.get("exit") not in (None, "OPEN") and v.get("taken") is not False and v.get("day"):
                rows.append({"day": str(v["day"]), "r": _f(v.get("R")), "usd": _f(v.get("usd"), 0.0), "entry_t": v.get("entry_t")})
    rows.sort(key=lambda t: (t["day"], t.get("entry_t") or 0))
    src = "none" if not use else ("PC bot" if use.get("source") == "pc" else "cloud paper")
    return rows, src


def atlas_trades(data: dict) -> list:
    """ATLAS's paper trades (EMA + MACD + S/R; finished and open) [{day, r, usd, key, open}]."""
    out, seen = [], set()
    for s in (data.get("second") or {}).get("strategies") or []:
        if not isinstance(s, dict) or s.get("key") not in ATLAS_KEYS:
            continue
        for t in s.get("trades") or []:
            if not isinstance(t, dict) or not t.get("day"):
                continue
            k = (s["key"], t.get("entry_t"))
            if k in seen:
                continue
            seen.add(k)
            op = t.get("exit_kind") in (None, "", "OPEN")
            out.append({"day": str(t["day"]), "r": _f(t.get("r")), "usd": _f(t.get("usd"), 0.0), "key": s["key"],
                        "short": s.get("short") or s["key"], "open": op, "entry_t": t.get("entry_t")})
    out.sort(key=lambda t: (t["day"], t.get("entry_t") or 0))
    return out


# ------------------------------------------------------------------------------------------------ accounts
def _sessions_left(ev: dict, used) -> int | None:
    m = re.search(r"(\d+)\s+left", str(ev.get("clock_text") or ""))
    if m:
        return int(m.group(1))
    return None if used is None else max(0, SESSIONS_GOAL - int(used))


def account_goal(key: str, ev: dict | None, stage: str, source: str, days_traded=None, name: str | None = None) -> dict:
    """One account's eval progress: profit vs target, room to the floor, sessions used of 10, days traded vs the minimum."""
    P = PLANS[key]
    ev = ev or {}
    start = _f(ev.get("start_balance"), P["start"])
    target_bal = _f(ev.get("target_balance"), _f(ev.get("target"), start + P["target"]))
    target = target_bal - start
    bal = _f(ev.get("balance"))
    profit = _f(ev.get("profit"), None if bal is None else bal - start)
    to_go = _f(ev.get("to_target"), None if profit is None else target - profit)
    mll = _f(ev.get("mll"), P["mll"])
    room = _f(ev.get("room"))
    floor = _f(ev.get("floor"), None if bal is None or room is None else bal - room)
    used = ev.get("session")
    used = int(used) if isinstance(used, (int, float)) else None
    left = _sessions_left(ev, used)
    dtr = days_traded if days_traded is not None else ev.get("days_traded")
    status = str(ev.get("status") or ("not started" if stage in ("planned", "not started") else "unknown"))
    out = {"id": key, "strategy": P["strategy"], "name": name or P["label"], "stage": stage, "source": source, "status": status,
           "start_balance": start, "target_balance": target_bal, "profit_target": target, "balance": bal, "profit": profit,
           "to_go": None if to_go is None else round(max(0.0, to_go), 2),
           "progress": None if profit is None or target <= 0 else round(_clip(profit / target), 4),
           "floor": floor, "room": room, "mll": mll, "room_frac": None if room is None or not mll else round(_clip(room / mll), 4),
           "sessions_used": used, "sessions_goal": SESSIONS_GOAL, "sessions_max": SESSIONS_MAX, "sessions_left": left,
           "days_traded": dtr, "min_days": int(ev.get("min_days") or P["min_days"]), "price": P["price"]}
    # plain sentence + level
    if status == "passed":
        out["sentence"] = f"Passed the {out['name']}: balance {_money(bal)}. Next: the funded account."
        out["level"] = "good"
    elif status == "failed":
        out["sentence"] = f"The {out['name']} failed (no room left). Buy a new one at {_money(P['price'])}."
        out["level"] = "bad"
    elif bal is None or stage in ("planned", "not started"):
        out["sentence"] = f"{out['name']} for {P['strategy']}: not started yet (target +{_money(target)}, max loss {_money(mll)})."
        out["level"] = "idle"
    else:
        bits = [f"{_money(out['to_go'])} to go on the {out['name'].replace('MFFU Builder ', '')}"]
        # owner 2026-11-03: no session counter in the sentence; the drawdown left = balance - the MFFU max-loss floor
        if room is not None:
            bits.append(f"drawdown left {_money(room)} of {_money(mll)}")
        out["sentence"] = ", ".join(bits) + "."
        late = used is not None and used > SESSIONS_GOAL
        out["level"] = "bad" if (room is not None and mll and room / mll < 0.25) or (used or 0) > SESSIONS_MAX else \
            "warn" if late or (room is not None and mll and room / mll < 0.5) else "good"
    if out["min_days"] and dtr is not None:
        out["days_text"] = f"{_plural(int(dtr), 'day')} traded of the {out['min_days']} minimum"
    return out


def _lit_account(data: dict) -> dict:
    acc = [a for a in data.get("accounts") or [] if isinstance(a, dict) and a.get("id") and not a.get("error")]
    pc = next((a for a in acc if a.get("source") == "pc" and a.get("eval")), None)
    cl = next((a for a in acc if a.get("source") == "cloud" and a.get("eval")), None)
    a = pc if pc and ((pc.get("conn") or {}).get("connected") or (pc.get("eval") or {}).get("anchor")) else (cl or pc)
    life = (data.get("live") or {}).get("eval_life") or {}
    ev = dict((a or {}).get("eval") or {})
    if not ev and life:
        ev = {"balance": life.get("balance"), "profit": life.get("profit"), "to_target": life.get("to_target"),
              "target_balance": life.get("target_balance"), "room": life.get("room"), "session": life.get("session"),
              "status": life.get("status"), "clock_text": life.get("clock_text"), "floor": life.get("floor")}
    days = None
    if a and isinstance(a.get("days"), list):
        days = sum(1 for d in a["days"] if isinstance(d, (list, tuple)) and len(d) > 1 and abs(_f(d[1], 0)) > 1e-9)
    if life.get("days_traded") is not None and (a or {}).get("source") != "pc":
        days = max(int(days or 0), int(life["days_traded"]))     # the cloud's eval clock counts the owner's day before the bot
    stage = "funded" if (a or {}).get("kind") == "funded" else "eval"
    src = "none" if not a else ("PC bot" if a.get("source") == "pc" else "cloud paper")
    g = account_goal("lit50k", ev, stage, src, days, name="MFFU Builder 50K")
    g["anchored"] = bool(ev.get("anchor"))
    return g


def _lit_start(data: dict) -> str | None:
    for a in data.get("accounts") or []:
        if isinstance(a, dict) and (a.get("eval") or {}).get("start"):
            return str(a["eval"]["start"])
    return ((data.get("live") or {}).get("eval_life") or {}).get("start")


def _atlas_account(data: dict) -> dict:
    S = data.get("second") or {}
    ab = S.get("account_b") or ((S.get("route") or {}).get("account_b") if isinstance(S.get("route"), dict) else None)
    ev = (ab or {}).get("eval") if isinstance(ab, dict) else None
    if isinstance(ev, dict) and ev.get("error"):
        ev = None
    scale_rows = (data.get("scale") or {}).get("accounts") or []
    planned = next((r for r in scale_rows if r.get("strategy") == "ATLAS"), None)
    if ev and ev.get("balance") is not None and ev.get("status") != "no eval_start":
        stage = "eval"
        src = "PC bot (account B)"
    else:
        stage = (planned or {}).get("stage") or "planned"
        if stage == "eval":
            stage = "not started"           # bought, the PC has not reported it yet
        src = "scale plan" if planned else "none"
        ev = None
    funded = isinstance(ab, dict) and ab.get("stage") == "funded" and stage == "eval"
    if funded:
        stage = "funded"                    # engine/account_b.py funded stage: the payout line is the goal now
    g = account_goal("atlas25k", ev, stage, src, (ev or {}).get("days_traded"),
                     name=str((ab or {}).get("plan_label") or "MFFU Builder 25K") if isinstance(ab, dict) else "MFFU Builder 25K")
    g["account"] = (ab or {}).get("account") if isinstance(ab, dict) else None
    g["enabled"] = (ab or {}).get("enabled") if isinstance(ab, dict) else False
    if funded:
        t = ab.get("funded") if isinstance(ab.get("funded"), dict) else {}
        st = str((ev or {}).get("status") or "funded")
        g["status"] = st
        g["tracker"] = t
        g["sentence"] = t.get("text") or f"ATLAS's funded {g['name']}: {_money(g.get('to_go'))} to the payout line."
        g["level"] = ("bad" if st in ("lost", "stuck") else "good" if t.get("ready") or st == "graduated" else
                      "warn" if t.get("status") == "consistency" else "good")
        g.pop("days_text", None)
    return g


# ------------------------------------------------------------------------------------------------ week / month
def week_goal(rows: list, today: str, lo: int, hi: int, name: str) -> dict:
    """This week's trades vs the lo-hi target: count, $, a day strip Mon-Fri and an on-pace sentence. On a weekend it is the
    coming week (with last week's count in "last_week")."""
    wkday = dt.date.fromisoformat(today).weekday()
    weekend = wkday >= 5
    mon = monday(today)
    last = None
    if weekend:
        last = sum(1 for t in rows if mon <= t["day"] <= today)
        mon = (dt.date.fromisoformat(mon) + dt.timedelta(days=7)).isoformat()
    d0 = dt.date.fromisoformat(mon)
    days = []
    for i in range(5):
        d = (d0 + dt.timedelta(days=i)).isoformat()
        T = [t for t in rows if t["day"] == d]
        days.append({"day": d, "wd": ["Mon", "Tue", "Wed", "Thu", "Fri"][i], "n": len(T), "usd": round(sum(t.get("usd") or 0 for t in T), 2),
                     "future": d > today, "today": d == today})
    W = [t for t in rows if mon <= t["day"] <= today]
    n = len(W)
    usd = round(sum(t.get("usd") or 0 for t in W), 2)
    elapsed = min(5, weekdays_between(mon, today)) if not weekend else 0
    pace = lo * max(0, elapsed - 1) / 5.0          # sessions finished before today
    if weekend:
        status, txt = "upcoming", f"{name}: the week starts Monday, goal {lo}-{hi} trades" + (f" (last week {last})." if last is not None else ".")
    elif n > hi:
        status, txt = "above", f"{name}: {n} trades this week, above the {lo}-{hi} goal."
    elif n >= lo:
        status, txt = "met", f"{name}: {n} trades this week, inside the {lo}-{hi} goal."
    elif wkday == 4 and n < lo:
        status, txt = "behind", f"{name}: {_plural(n, 'trade')} this week, today is the last session for the {lo}-{hi} goal."
    elif n + 1e-9 >= pace - 0.5:
        status, txt = "on_pace", f"{name}: {_plural(n, 'trade')} so far, {lo - n} more for the {lo}-{hi} goal ({_plural(6 - elapsed, 'session')} left incl. today)."
    else:
        status, txt = "behind", f"{name}: {_plural(n, 'trade')} so far, behind the {lo}-{hi} pace (the bot only trades A+ setups)."
    return {"name": name, "monday": mon, "n": n, "usd": usd, "lo": lo, "hi": hi, "frac": round(_clip(n / hi), 4), "status": status,
            "sentence": txt, "days": days, "last_week": last}


def month_goal(rows: list, today: str, band: dict | None = None, perf: dict | None = None, start: str | None = None) -> dict:
    """Month-to-date $ against the backtest's expected band for the same number of sessions (health_band H2). start = the
    day the bot began this account (sessions before it are not counted)."""
    m0 = max(today[:8] + "01", str(start or ""))
    M = [t for t in rows if t["day"] >= m0 and t["day"] <= today]
    usd = round(sum(t.get("usd") or 0 for t in M), 2)
    n_s = weekdays_between(m0, today)
    exp = None
    if band and (band.get("bands") or {}).get("H2"):
        try:
            from . import health_band as HB
            Bn = band["bands"]["H2"]
            b = HB.band_at(Bn, max(1, n_s), "usd_eval")
            exp = {"p10": round(b["p10"], 0), "p50": round(b["p50"], 0), "p90": round(b["p90"], 0), "sessions": n_s, "kind": "bootstrap"}
            if M:
                exp["pct"] = HB.pct_of(Bn["usd_eval"][min(len(Bn["usd_eval"]), max(1, n_s)) - 1], usd)
        except Exception:
            exp = None
    if exp is None:
        per = (((perf or {}).get("range") or {}).get("bands") or {}).get("H2", {}).get("usd_eval_per_session")
        if per is not None:
            exp = {"p50": round(float(per) * n_s, 0), "sessions": n_s, "kind": "average", "per_session": per}
    per_month = None                      # the backtest's average $ a month (21 sessions); the median path is lower (skewed)
    per = (((perf or {}).get("range") or {}).get("bands") or {}).get("H2", {}).get("usd_eval_per_session")
    if per is not None:
        per_month = round(float(per) * 21, 0)
    elif exp and exp.get("p50") is not None and n_s:
        per_month = round(exp["p50"] / n_s * 21, 0)
    lvl = None
    if exp and exp.get("p10") is not None and M:
        lvl = "good" if usd >= exp["p10"] else "warn"
    if not M:
        txt = f"No LIT trade this month yet ({_plural(n_s, 'session')} so far)."
    elif exp and exp.get("p10") is not None:
        txt = (f"{_money(usd, True)} this month after {_plural(n_s, 'session')}; the backtest's usual range is "
               f"{_money(exp['p10'], True)} to {_money(exp['p90'], True)} (middle {_money(exp['p50'], True)}).")
    elif exp:
        txt = f"{_money(usd, True)} this month; the backtest average for {_plural(n_s, 'session')} is {_money(exp['p50'], True)}."
    else:
        txt = f"{_money(usd, True)} this month."
    return {"month": today[:7], "usd": usd, "trades": len(M), "sessions": n_s, "expected": exp, "per_month_expected": per_month,
            "level": lvl, "sentence": txt}


# ------------------------------------------------------------------------------------------------ scorecard / payout / scale
def scorecard_goal(data: dict) -> dict:
    sc = ((data.get("second") or {}).get("scorecard") or {}).get("account_b") or {}
    n = int(sc.get("n") or 0)
    need = int(sc.get("need") or 20)
    kind = sc.get("kind") or "collecting"
    txt = {"ready": f"ATLAS is ready to go live: {n} paper trades inside the expected range.",
           "below": f"ATLAS is below its range after {n} trades: don't go live yet.",
           "on_track": f"ATLAS: {n} of {need} paper trades, on track ({sc.get('text') or ''}).".replace(" ()", ""),
           }.get(kind, f"ATLAS go-live check: {n} of {need} paper trades collected ({max(0, need - n)} to go).")
    return {"n": n, "need": need, "frac": round(_clip(n / need if need else 0), 4), "kind": kind, "text": sc.get("text"),
            "cum_r": sc.get("cum_r"), "usd": sc.get("usd"), "win": sc.get("win"), "pct": sc.get("pct"), "sentence": txt,
            "level": "good" if kind == "ready" else "bad" if kind == "below" else "warn" if kind == "on_track" else "idle"}


def _atlas_funded_tracker(data: dict):
    """ATLAS's funded account tracker (engine/account_b.py stage "funded": second.route.account_b.funded) or None."""
    S = data.get("second") or {}
    ab = S.get("account_b") or ((S.get("route") or {}).get("account_b") if isinstance(S.get("route"), dict) else None)
    if isinstance(ab, dict) and ab.get("stage") == "funded" and isinstance(ab.get("funded"), dict) and ab["funded"].get("status"):
        return {**ab["funded"], "id": "account_b", "name": ab.get("label") or ab["funded"].get("name")}
    return None


def payout_goal(data: dict, lit: dict) -> dict:
    acc = [a for a in data.get("accounts") or [] if isinstance(a, dict) and a.get("kind") == "funded" and not a.get("error")]
    abt = _atlas_funded_tracker(data)
    if not acc and abt:                             # only ATLAS is funded: its tracker is the payout goal
        acc_t = [abt]
        t = abt
        lvl = {"ready": "good", "graduated": "good", "lost": "bad", "consistency": "warn", "eligible": "warn"}.get(t.get("status"), "idle")
        return {"stage": "funded", "funded": 1, "balance": t.get("balance"), "ask_at": t.get("ask_at_balance"),
                "frac": t.get("buffer_frac") or 0.0, "ready": bool(t.get("ready")), "status": t.get("status"),
                "max_request": t.get("max_request"), "payouts_n": t.get("payouts_n"), "payouts_max": t.get("payouts_max"),
                "best_day_pct": t.get("best_day_pct"), "cycle_profit": t.get("cycle_profit"), "eligible_from": t.get("eligible_from"),
                "tracker": t, "trackers": acc_t, "sentence": t.get("text") or "", "level": lvl}
    if not acc:
        nxt = "after the 50K passes" if lit.get("status") != "passed" else "add the funded account (engine.eval_life --to-funded)"
        return {"stage": "eval", "funded": 0, "sentence": f"Payouts start on the funded account: {nxt}.", "level": "idle", "frac": 0.0}
    # the sim funded tracker (engine/funded_life.py, 2026-10-25): buffer, cycle, 50% consistency, 48 h, payouts n of 5
    from . import funded_life as FL
    trk = []
    for x in acc:
        try:
            t = FL.from_account(x)
        except Exception:
            t = None
        if t:
            trk.append(t)
    if abt and trk:
        trk.append(abt)                             # ATLAS's funded 25K after Zlarior's funded accounts
    if not trk:                                     # no day P&L in the section: the old balance-only view
        a = acc[0]
        ev = a.get("eval") or {}
        bal = _f(ev.get("balance"), 50000.0)
        need = 50000.0 + PAYOUT_BUFFER + PAYOUT_ASK_ABOVE
        frac = _clip((bal - 50000.0) / (need - 50000.0))
        ok = bal >= need
        return {"stage": "funded", "funded": len(acc), "balance": bal, "ask_at": need, "frac": round(frac, 4), "ready": ok,
                "sentence": (f"Payout ready: balance {_money(bal)} is above {_money(need)}." if ok else
                             f"Funded: {_money(need - bal)} more before the first payout request (at {_money(need)})."),
                "level": "good" if ok else "warn"}
    t = next((x for x in trk if x["status"] == "ready"), trk[0])
    lvl = {"ready": "good", "graduated": "good", "lost": "bad", "consistency": "warn", "eligible": "warn"}.get(t["status"], "idle")
    return {"stage": "funded", "funded": len(acc), "balance": t["balance"], "ask_at": t["ask_at_balance"], "frac": t["buffer_frac"],
            "ready": t["ready"], "status": t["status"], "max_request": t["max_request"], "payouts_n": t["payouts_n"],
            "payouts_max": t["payouts_max"], "best_day_pct": t["best_day_pct"], "cycle_profit": t["cycle_profit"],
            "eligible_from": t["eligible_from"], "tracker": t, "trackers": trk, "sentence": t["text"], "level": lvl}


def scale_goal(data: dict) -> dict:
    s = data.get("scale") or {}
    if s.get("error") or s.get("step") is None:
        return {"step": None, "sentence": "Scale plan: not built yet.", "level": "idle", "frac": 0.0}
    nx = s.get("next") or {}
    return {"step": s.get("step"), "of": s.get("of"), "action": nx.get("action"), "when": nx.get("when"),
            "progress": nx.get("progress"), "frac": round(_clip((nx.get("progress") or 0) / 100.0), 4), "ready": nx.get("ready"),
            "sentence": s.get("sentence"), "level": "good" if nx.get("ready") else "idle"}


# ------------------------------------------------------------------------------------------------ calendar
def news_rows(today: str, days: int = 14, path: str = NEWS_CSV) -> list:
    """Scheduled USD events from research/hq/news_calendar.csv between today and today + days."""
    try:
        with open(path, encoding="utf-8") as fh:
            R = list(csv.DictReader(fh))
    except OSError:
        return []
    end = (dt.date.fromisoformat(today) + dt.timedelta(days=days)).isoformat()
    out, seen = [], set()
    for r in R:
        d = (r.get("date") or "").strip()
        if today <= d <= end:
            k = (d, r.get("time_et"), r.get("event"))
            if k in seen:
                continue
            seen.add(k)
            out.append({"day": d, "time": (r.get("time_et") or "").strip(), "event": (r.get("event") or "").strip()})
    return out


def _nth_sunday(y, m, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_sunday(y, m):
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def clock_changes(today: str, days: int = 21) -> list:
    """US and UK/EU clock changes in the next weeks (the London killzone moves against ET for a week or two)."""
    t = dt.date.fromisoformat(today)
    out = []
    for y in (t.year, t.year + 1):
        for d, who, what in ((_nth_sunday(y, 3, 2), "US", "clocks go forward"), (_nth_sunday(y, 11, 1), "US", "clocks go back"),
                             (_last_sunday(y, 3), "UK / Europe", "clocks go forward"), (_last_sunday(y, 10), "UK / Europe", "clocks go back")):
            if t - dt.timedelta(days=7) <= d <= t + dt.timedelta(days=days):
                out.append({"day": d.isoformat(), "who": who, "what": what,
                            "note": "ET times in the app stay the same; London opens an hour earlier in ET until the US changes too"
                            if who != "US" else "the app shows ET, so the bot's times do not change"})
    return sorted(out, key=lambda x: x["day"])


def early_closes(today: str, days: int = 45) -> list:
    try:
        from .lit_live import early_close
    except Exception:
        return []
    out, t = [], dt.date.fromisoformat(today)
    for i in range(days + 1):
        d = t + dt.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ec = early_close(d.isoformat())
        if ec is not None:
            out.append({"day": d.isoformat(), "halt": f"{ec // 60:02d}:{ec % 60:02d}"})
    return out


# ------------------------------------------------------------------------------------------------ the whole block
def build(data: dict | None, now=None, band: dict | None = None, news_path: str | None = NEWS_CSV, money=None) -> dict:
    """data = data.json (or the PC's equivalent blocks). band = engine.health_band.load() (None: the perf average).
    money = the owner's money figures (engine/money_goal: the heartbeat's "money" block in the cloud, the local file on the
    PC; default data["money_in"]). -> the goals JSON. Never raises: a broken part becomes {"error"}."""
    data = data or {}
    if money is None:
        money = data.get("money_in")
    now = int(now or time.time())
    today = trading_day(now)
    out = {"v": VERSION, "t": now, "today": today, "goals": {"sessions": SESSIONS_GOAL, "sessions_max": SESSIONS_MAX,
                                                               "lit_week": list(LIT_WEEK), "atlas_week": list(ATLAS_WEEK), "atlas_ready_n": 20}}

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as e:                     # a page part, never the whole card
            out[name] = {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}

    lit_rows, lit_src = lit_trades(data)
    at_rows = atlas_trades(data)
    part("accounts", lambda: [_lit_account(data), _atlas_account(data)])
    part("week", lambda: {"lit": week_goal(lit_rows, today, *LIT_WEEK, "LIT"),
                          "atlas": week_goal([t for t in at_rows if not t["open"]] + [t for t in at_rows if t["open"]], today, *ATLAS_WEEK, "ATLAS")})
    part("month", lambda: month_goal(lit_rows, today, band, data.get("perf"), _lit_start(data)))
    part("scorecard", lambda: scorecard_goal(data))
    lit_acc = (out.get("accounts") or [{}])[0] if isinstance(out.get("accounts"), list) else {}
    part("payout", lambda: payout_goal(data, lit_acc))
    part("scale", lambda: scale_goal(data))
    part("calendar", lambda: {"news": news_rows(today, 14, news_path) if news_path else [], "early_close": early_closes(today),
                              "clocks": clock_changes(today)})

    def _money():                                  # Road to $10K / Stingray 3LT (engine/money_goal.py, read-only)
        from . import money_goal as MG
        return MG.build(data, money, now)
    part("money", _money)
    out["sources"] = {"lit_trades": lit_src, "lit_n": len(lit_rows), "atlas_n": len(at_rows)}
    # the top lines for Home, most important first
    lines = []
    for g in out.get("accounts") or []:
        if isinstance(g, dict) and g.get("sentence"):
            lines.append({"k": g["id"], "text": g["sentence"], "level": g.get("level")})
    for k in ("lit", "atlas"):
        w = (out.get("week") or {}).get(k)
        if isinstance(w, dict) and w.get("sentence"):
            lines.append({"k": "week_" + k, "text": w["sentence"], "level": "good" if w["status"] in ("met", "on_pace") else
                          "idle" if w["status"] == "upcoming" else "warn"})
    for k in ("scorecard", "month", "payout", "scale"):
        g = out.get(k)
        if isinstance(g, dict) and g.get("sentence"):
            lines.append({"k": k, "text": g["sentence"], "level": g.get("level")})
    mg = out.get("money")
    if isinstance(mg, dict) and isinstance(mg.get("lines"), list):   # only once the owner typed his figures in
        lines += [x for x in mg["lines"] if isinstance(x, dict) and x.get("text")]
    out["lines"] = lines
    return out


def site_block(data: dict, now=None, money=None) -> dict:
    """tools/build_web_dashboard.py: build() with the H2 health band when research/lab has it. money = the owner's money
    figures (the heartbeat's "money" block; None: data["money_in"])."""
    band = None
    try:
        from . import health_band as HB
        band = HB.load()
    except Exception:
        band = None
    return build(data, now=now, band=band, money=money)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "site", "data.json")
    with open(p, encoding="utf-8") as fh:
        print(json.dumps(site_block(json.load(fh)), indent=1, default=str))
