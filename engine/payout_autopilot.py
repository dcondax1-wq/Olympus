"""PAYOUT AUTOPILOT (night-payout 2026-11-22, lead: "the owner needs every payout taken on time and safely").

Read-only towards MFFU and the broker: it NEVER requests a payout (the owner does, in the MFFU dashboard), never arms, never
routes, never sizes. It reads the PC's own numbers (the same trackers the dashboards use) and tells the phone, once:

  1. PAYOUT READY   each CME trading day after the close (16:10 ET; a half day: its halt, 13:00 / 13:15 ET), per funded
                    account: may a payout be requested under MFFU's rules, and how much -> ONE alert
                    "Payout ready: ATLAS 25K can request $1,000 now ($800 to you)" + the MFFU dashboard clicks.
                    Builder (engine/funded_life.track): $1,100 / $2,100 buffer, $250 / $500 min, $1,000 / $2,000 max, the first
                    one 48 h after the first funded trade, >= 2 traded days in the cycle, best day <= 50% of the cycle, and the
                    owner's plan (ask only at the max: each Builder gets only 4 payouts, see 2, so a small one wastes a slot).
                    Rapid EOD (engine/rapid.payout_advice): daily, $500 min, no max, above the buffer + the bot's cushion, the
                    25K's $250 net since the last payout, once a day, 90% to you.
  2. PAYOUT #4/#5   (research/writeups/fleet-plan-2026-11-22.md) a Builder's 5th payout makes MFFU move you to live and puts
                    EVERY sim account to sleep: never suggest it. Payout #4 ready = "this is the LAST one: after it close the
                    account"; 4 recorded = ONE alert "Do not take payout #5: close after payout 4"; later, when MFFU would pay
                    a 5th, one alert per cycle "Payout #5 available: do NOT take it". The phone card says it too (block()).
  3. RAPID $10K DAY a plain Rapid moves to live at $10,000 net in one day (ACCOUNT_RULES 6). The bot's sizing keeps far below,
                    but if a Rapid's day ever reaches WARN_10K_AT ($6,000) one alert at once, any hour of the session.
  4. RECORD         record(key, amount, day): the owner's "I took it" (TRADE_HOME -> P) goes to the account's own record
                    (account_b / eval_life / rapid --payout, as before) AND the payout ledger data/payout_ledger.json, which the
                    Money pipeline / Corvette fund counts (engine/money_goal.build merges its Rapid rows; Builders already flow).

Alerts go through engine/alert_bus.send_critical (Telegram / Discord when set up, else ntfy + the Olympus app); each key once
(data/payout_autopilot.json, gitignored). Run by tools/pc_report.py every 15 minutes (tick()).

  python -X utf8 -m engine.payout_autopilot              every funded account now, plain words
  python -X utf8 -m engine.payout_autopilot --tick       one tick (sends what is due)
Tests: python -X utf8 -m tests.test_payout_autopilot
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "payout_autopilot.json")     # gitignored: keys sent (kept for good: the #5 guard is once)
LEDGER_PATH = os.path.join(ROOT, "data", "payout_ledger.json")       # gitignored: the payouts the owner confirmed
CLOSE_MIN = 16 * 60 + 10            # MFFU's daily close (flat time) on a full day
SESSION_FROM = 18 * 60              # the session opens 18:00 ET the evening before
BUILDER_LAST = 4                    # take payouts 1-4, never the 5th (fleet plan 2026-11-22)
LIVE_DAY_USD = 10000.0              # a plain Rapid: one $10,000 net day = MFFU moves it live
WARN_10K_AT = 6000.0                # warn at 60% of it
# MFFU's help center (checked 2026-11-23): the dashboard's left panel has "Payouts: Request and track your earnings"
# (help.myfundedfutures.com/en/articles/8229980); "Visit the MFFU payout dashboard to submit your request", first time KYC under
# "Personal Settings > KYC", a Riseworks account, then the Riseworks agreements by email; "processed in 6-12 business hours"
# (help.myfundedfutures.com/en/articles/11542406). The request button's own name is NOT on those pages: the words below say
# only what they say.
STEPS = ("In the MFFU dashboard (myfundedfutures.com): left menu Payouts -> request {amt} from {acct}. First payout only: "
         "Personal Settings > KYC done, a Riseworks account, and sign the Riseworks agreements MFFU emails you. Paid in 6-12 "
         "business hours. Then tell Olympus you took it: TRADE_HOME -> P.")


def _f(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def usd(x) -> str:
    v = _f(x, 0.0)
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


# ------------------------------------------------------------------------------------------------ the calendar
def close_of(day) -> int | None:
    """ET minute of MFFU's close on this date: 16:10, a CME half day's halt, None = no trading (weekend / full closure)."""
    d = day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day)[:10])
    if d.weekday() >= 5:
        return None
    try:
        from . import cme_calendar as C
        if C.full_closure(d):
            return None
        e = C.early_close(d)
        return int(e) if e is not None else CLOSE_MIN
    except Exception:
        return CLOSE_MIN


def after_close(now) -> str | None:
    """The trading date whose close has passed (the payout check runs then), else None. Until the 18:00 ET reopen."""
    e = _et(now)
    c = close_of(e.date())
    m = e.hour * 60 + e.minute
    if c is None or m < c or m >= SESSION_FROM:
        return None
    return e.date().isoformat()


def in_session(now) -> str | None:
    """The trading date when the session runs now (18:00 ET the evening before -> the close), else None."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    d = e.date() + dt.timedelta(days=1) if m >= SESSION_FROM else e.date()
    c = close_of(d)
    if c is None or (d == e.date() and m >= c):
        return None
    return d.isoformat()


# ------------------------------------------------------------------------------------------------ the pure rules
def builder(t: dict, key: str, name: str | None = None) -> dict:
    """One Builder funded tracker (engine/funded_life.track / account_b.compact_tracker) -> the autopilot's view."""
    t = t or {}
    nm = name or t.get("name") or "Builder"
    n = int(_f(t.get("payouts_n"), 0) or 0)
    elig, amt = bool(t.get("eligible")), _f(t.get("max_request"), 0.0) or 0.0
    split = _f(t.get("split"), 0.8) or 0.8
    out = {"key": key, "name": nm, "kind": "builder", "payouts_n": n, "next_n": n + 1, "ready": False, "amount": 0.0,
           "to_you": 0.0, "guard": None, "why": list(t.get("why") or [])[:3], "cycle": str(t.get("cycle_start") or ""),
           "lost": bool(t.get("lost")), "mffu_would_pay": amt if elig else 0.0, "acct_start": str(t.get("start") or "")}
    if t.get("lost"):
        out["why"] = ["the funded account is lost"]
        return out
    if n >= BUILDER_LAST + 1:
        out["guard"] = "live"
        out["why"] = [f"{n} payouts taken: MFFU moves you to live (every sim account sleeps)"]
        return out
    if n == BUILDER_LAST:
        out["guard"] = "stop"
        out["why"] = ["4 payouts taken: do NOT take payout #5 (MFFU moves you to live and every sim account sleeps); close it"]
        return out
    ready = elig and bool(t.get("ready"))                 # MFFU's rules AND the owner's plan (the max request)
    if elig and not ready:
        out["why"] = [f"MFFU would pay {usd(amt)} now; your plan waits for the max {usd(t.get('ask_amount'))} "
                      f"(only 4 payouts per Builder: a small one wastes a slot)"] + out["why"]
    if ready:
        out.update(ready=True, amount=float(int(amt)), to_you=round(float(int(amt)) * split, 2))
        if n + 1 == BUILDER_LAST:
            out["guard"] = "last"
    return out


def rapid(st: dict, key: str, name: str | None = None, split: float = 0.9) -> dict:
    """One Rapid EOD status (engine/rapid.status) -> the autopilot's view; today_net feeds the $10k-day check."""
    st = st or {}
    a = st.get("payout") or {}
    nm = name or st.get("label") or "Rapid EOD"
    tn = _f(st.get("today_net"), 0.0) or 0.0
    out = {"key": key, "name": nm, "kind": "rapid", "ready": bool(a.get("ready")) and st.get("stage") == "funded",
           "amount": float(_f(a.get("request"), 0.0) or 0.0), "to_you": float(_f(a.get("to_you"), 0.0) or 0.0), "guard": None,
           "why": [], "cycle": "", "today_net": tn, "near_live": tn >= WARN_10K_AT, "lost": False}
    if not out["ready"]:
        out["amount"] = out["to_you"] = 0.0
        if st.get("stage") == "funded":
            out["why"] = [f"{usd(a.get('since_short'))} more net since the last payout (MFFU's rule)" if a.get("since_short")
                          is not None else f"{usd(a.get('to_next'))} to go (the bot keeps {usd(a.get('keep_at'))} in)"]
    return out


def alerts(views: list, now, sent: dict | None = None) -> list:
    """The alerts due now ({"key", "title", "body", "kind"}), each key once (sent). Pure."""
    sent = sent or {}
    out = []
    day_after = after_close(now)
    day_sess = in_session(now)

    def add(key, title, body, kind="payout_ready"):
        if key not in sent and all(a["key"] != key for a in out):
            out.append({"key": key, "title": title[:120], "body": body[:600], "kind": kind})

    for v in views:
        nm = v["name"]
        if v["kind"] == "rapid" and v.get("near_live") and (day_sess or day_after):
            d = day_sess or day_after
            add(f"rapid10k:{v['key']}:{d}", f"{nm}: {usd(v['today_net'])} today, near MFFU's $10,000 live line",
                f"One day of $10,000 net moves a Rapid to LIVE and puts every MFFU sim account to sleep. Today is "
                f"{usd(v['today_net'])}. Do not add hand trades today; tell Claude to check the sizing.", "problem")
        if v.get("guard") == "stop":
            add(f"payout5:stop:{v['key']}:{v.get('acct_start') or '-'}", f"{nm}: do not take payout #5: close after payout 4",
                "4 payouts are in. Payout #5 makes MFFU move you to live and every sim account (all evals, ATLAS, the Rapids) "
                "goes to sleep. Stop here: let the bot finish the day, then close this account in MFFU and buy the next eval.")
            if v.get("mffu_would_pay") and day_after:
                add(f"payout5:offer:{v['key']}:{v.get('cycle')}", f"{nm}: payout #5 is available: do NOT take it",
                    f"MFFU would pay {usd(v['mffu_would_pay'])}, but the 5th payout moves you to live and stops every sim account. "
                    "Close the account instead.")
        if not day_after or not v.get("ready") or v.get("amount", 0) <= 0:
            continue
        cyc = v.get("cycle") if v["kind"] == "builder" else day_after
        last = v.get("guard") == "last"
        title = f"Payout ready: {nm} can request {usd(v['amount'])} now" + (" (payout #4, the LAST)" if last else "")
        body = (f"{usd(v['to_you'])} reaches you. " + STEPS.format(acct=nm, amt=usd(v["amount"]))
                + (" This is payout #4: after it, close the account (never take #5: MFFU moves you to live). First check MFFU's "
                    "Payouts page shows exactly 3 paid: if it shows 4, do NOT request (that would be #5)." if last else "")
                + (f" Payout {v['next_n']} of 4." if v["kind"] == "builder" and not last else ""))
        add(f"payout:{v['key']}:{cyc}", title, body)
    return out


# ------------------------------------------------------------------------------------------------ the PC's numbers
def gather(today: str | None = None) -> list:
    """Every funded account the PC knows -> views. Each source on its own (a broken one is skipped). Never raises."""
    views = []
    try:
        from . import account_b as AB
        s = AB.funded_status(today=today)
        if s.get("ok"):
            views.append(builder(s.get("tracker") or {}, "atlas"))
    except Exception:
        pass
    try:
        from . import funded_life as FL
        for t in FL.local_status(today=today):
            views.append(builder(t, f"x:{t.get('id')}"))
    except Exception:
        pass
    try:
        from . import rapid as R
        for slot in R.SLOTS:
            st = R.status(slot=slot)
            if st.get("on") and st.get("stage") == "funded":
                views.append(rapid(st, slot, R.plan_info(R.read(R.slot_path(slot)) or {}).get("label")))
    except Exception:
        pass
    return views


def _read(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(path, d) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    os.replace(tmp, path)


def tick(now=None, views=None, sender=None, path: str | None = None) -> dict:
    """One run (tools/pc_report, every 15 min): the alerts due, sent once each. sender(alert) -> True when it went out
    (default: engine/alert_bus.send_critical). A failed send is tried again next run. Never raises."""
    now = time.time() if now is None else now
    path = path or STATE_PATH
    try:
        st = _read(path)
        sent = st.setdefault("sent", {})
        today = (in_session(now) or after_close(now) or _et(now).date().isoformat())
        v = gather(today) if views is None else views
        due = alerts(v, now, sent)
        out = []
        for a in due:
            ok = (sender or _send)(a)
            if ok:
                sent[a["key"]] = int(now)
            out.append({**a, "sent": bool(ok)})
        st["last"] = {"t": int(now), "views": [{k: x.get(k) for k in ("key", "name", "ready", "amount", "guard", "payouts_n")}
                                               for x in v]}
        _write(path, st)
        return {"alerts": out, "views": v}
    except Exception as e:  # noqa: BLE001
        return {"error": e.__class__.__name__, "alerts": []}


def _send(a: dict) -> bool:
    try:
        from . import alert_bus as AB
        r = AB.send_critical({"kind": "report" if a["kind"] == "payout_ready" else "problem", "key": a["key"], "title": a["title"],
                              "body": a["body"], "notify_type": "account_status" if a["kind"] == "payout_ready" else "problems",
                              "report": True}, wait=True)
        return r in ("sent", "queued", "dup")
    except Exception:
        return False


def block(views: list) -> dict:
    """The phone card (small, no ids): per account one line; the #5 guard in words."""
    rows = []
    for v in views:
        if v.get("guard") in ("stop", "live"):
            line = "STOP: do not take payout #5, close after payout 4" if v["guard"] == "stop" else v["why"][0]
        elif v.get("ready"):
            line = f"request {usd(v['amount'])} now ({usd(v['to_you'])} to you)" + (" - the LAST one (#4)" if v.get("guard") == "last" else "")
        else:
            line = (v.get("why") or ["building"])[0]
        rows.append({"name": v["name"], "line": str(line)[:140], "ready": bool(v.get("ready")), "stop": v.get("guard") == "stop"})
    return {"v": 1, "rows": rows}


# ------------------------------------------------------------------------------------------------ the owner's "I took it"
def record(key: str, amount, day: str | None = None, ledger_path: str | None = None, recorders: dict | None = None) -> dict:
    """Record a payout the owner TOOK (MFFU paid it): the account's own record + the payout ledger (the Money pipeline).
    key: "atlas" | "x:<id>" | "rapid" | "rapid2". -> {"ok", "say"} | {"ok": False, "error"}. Never requests anything."""
    try:
        amt = round(float(amount), 2)
        if not amt > 0:
            raise ValueError
        day = day or dt.datetime.now(ET).date().isoformat()
        dt.date.fromisoformat(day)
    except (TypeError, ValueError):
        return {"ok": False, "error": "give the amount in $ (e.g. 1000) and the day as yyyy-mm-dd"}
    spec = f"{day}={amt}"
    rec = recorders or {}
    kind, split, warn = "builder", 0.8, None
    try:
        if key == "atlas":
            from . import account_b as A
            r = (rec.get("atlas") or A.record_payout)(spec)
        elif key.startswith("x:"):
            from . import eval_life as E
            rc = (rec.get("x") or E.record_payout)(spec, key[2:])
            r = {"ok": rc == 0} if isinstance(rc, int) else rc
        elif key in ("rapid", "rapid2"):
            from . import rapid as R
            kind, split = "rapid", R.SPLIT
            r = (rec.get("rapid") or (lambda s: R.record_payout(s, p=R.slot_path(key))))(spec)
        else:
            return {"ok": False, "error": f"unknown account {key!r}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"recording failed: {e.__class__.__name__}"}
    if not (r or {}).get("ok"):
        return {"ok": False, "error": (r or {}).get("error") or "the account did not take it"}
    lp = ledger_path or LEDGER_PATH
    L = _read(lp)
    rows = [x for x in L.get("rows") or [] if isinstance(x, dict) and not (x.get("key") == key and x.get("day") == day)]
    rows.append({"key": key, "day": day, "gross": amt, "to_you": round(amt * split, 2), "kind": kind, "t": int(time.time())})
    n = sum(1 for x in rows if x.get("key") == key)
    if kind == "builder":                    # red team 2026-11-23: a 2nd funded ATLAS (after a new eval) is a NEW account: count its
        own = _own_count(key, rec)           # payouts from its own record, else only the ledger rows since its funded start
        if own is not None:
            n = own
    if kind == "builder" and n >= BUILDER_LAST + 1:
        warn = "That was payout #5: MFFU moves you to live and every sim account sleeps. Tell Claude now."
    elif kind == "builder" and n == BUILDER_LAST:
        warn = "That was payout #4, the last: close this account in MFFU; never take #5."
    L["rows"] = sorted(rows, key=lambda x: (x["day"], x["key"]))[-400:]
    _write(lp, L)
    say = f"Recorded {usd(amt)} ({usd(amt * split)} to you) on {day}; the Money pipeline counts it."
    return {"ok": True, "say": say + (f" {warn}" if warn else ""), "warn": warn, "n": n}


def _own_count(key: str, rec: dict | None = None) -> int | None:
    """Payouts recorded on the CURRENT funded account of this slot (after record()): the tracker's payouts_n. None = unknown."""
    try:
        if rec and rec.get("count"):
            return int(rec["count"](key))
        if key == "atlas":
            from . import account_b as A
            s = A.funded_status()
            return int((s.get("tracker") or {}).get("payouts_n")) if s.get("ok") else None
        if key.startswith("x:"):
            from . import funded_life as FL
            for t in FL.local_status():
                if str(t.get("id")) == key[2:]:
                    return int(t.get("payouts_n"))
    except Exception:  # noqa: BLE001
        return None
    return None


def ledger_rows(path: str | None = None, kinds=("rapid",)) -> list:
    """The ledger's rows for the Money pipeline ({day, gross, to_you, type, name}); Builders already flow from their own
    account files (engine/money_goal.real_accounts), so only the Rapid rows by default. Never raises."""
    out = []
    for x in _read(path or LEDGER_PATH).get("rows") or []:
        if isinstance(x, dict) and x.get("kind") in kinds and _f(x.get("gross")):
            out.append({"day": str(x.get("day")), "gross": float(x["gross"]), "to_you": float(_f(x.get("to_you"), 0.0)),
                        "type": "rapid", "name": "Rapid EOD"})
    return out


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if "--tick" in a:
        r = tick()
        for x in r.get("alerts") or []:
            print(("SENT  " if x["sent"] else "RETRY ") + x["title"])
        print(f"{len(r.get('alerts') or [])} alert(s) due")
        return 0
    v = gather()
    if not v:
        print("No funded account on this PC yet.")
    for row in block(v)["rows"]:
        print(f"{row['name']}: {row['line']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
