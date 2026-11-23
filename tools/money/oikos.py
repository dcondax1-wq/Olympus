#!/usr/bin/env python3
"""OIKOS, the household: money machine #4. Reads the Ledger app's JSON export and finds where money leaks (2026-11-10).

  python tools/money/oikos.py --out DIR                 # sample ledger (works offline), writes DIR/oikos.json
  python tools/money/oikos.py --out DIR --ledger X.json # a Ledger export (Ledger app -> Export JSON)
  python tools/money/oikos.py --out DIR                 # with no --ledger: your bank exports' ledger when tools/money_import.py has built one
                                                        # (%USERPROFILE%\\.olympus\\money\\oikos_ledger.json), else the sample
  python tools/money/oikos.py --selftest

Stdlib only, offline, read only: it reads one file and writes one file. It never trades, never calls a service, never touches the bot.
The maths here is mirrored line for line in tools/web_public/oikos/oikoscore.js (the page computes the same numbers with no feed);
tests/test_oikos_page.py runs both on the same ledger and fails if they differ.

Everything it prints is an ESTIMATE from what you recorded. The tax line is a generic set-aside, NOT tax advice.
Data contract (docs/NIGHT_BRIEF.md): {"v":1,"id":"oikos","asof","mode":"paper","status","headline":{text,usd_month},"items":[...],"notes":[...]}
plus "ledger" (the cleaned ledger the numbers came from) and "analysis" (every number).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "oikos_sample.json")

KINDS = {  # kind -> direction (-1 costs, +1 income, 0 not in net)
    "fee": -1, "reset": -1, "activation": -1, "expense": -1, "payout_in": 1, "payout_req": 0, "income": 1,
    "deposit": 0, "withdrawal": 0, "tax": 0,
}
EVERY = ("week", "month", "year")
NOT_ACCOUNTS = ("general", "kalshi", "")
DEFAULTS = {"tax": 0.30, "emergency": 0.25, "reinvest": 0.20, "living": 2500.0, "em_months": 3.0, "em_saved": 0.0, "cap": 6, "proj_re": 0.5, "months": 12, "account_cost": 0.0}
SCEN = (("conservative", 0.5), ("base", 1.0), ("optimistic", 1.5))
DEFAULT_ACCOUNT_COST = 91.8      # the owner's real Builder 50K price, used only when the ledger has no eval fee
NOTE_TAX = "Not tax advice. A generic set-aside percentage; ask an accountant what applies to you."


# ----------------------------------------------------------------------------- small helpers (mirrored in oikoscore.js)
def r2(x):
    return math.floor(x * 100 + 0.5) / 100


def r4(x):
    return math.floor(x * 10000 + 0.5) / 10000


def clamp(x, lo, hi):
    return min(hi, max(lo, x))


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
        return x if math.isfinite(x) else None
    return None


def text(v, n=200):
    if isinstance(v, str):
        s = v
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        s = str(v)
    else:
        s = ""
    return " ".join(s.split())[:n]


def is_date(s):
    if not isinstance(s, str) or len(s) != 10:
        return False
    try:
        return dt.date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


def dn(s):
    return dt.date.fromisoformat(s).toordinal()


def add_days(s, n):
    return (dt.date.fromisoformat(s) + dt.timedelta(days=n)).isoformat()


def days_between(a, b):
    return dn(b) - dn(a)


def add_months(s, n):
    y, m, d = (int(x) for x in s.split("-"))
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    last = (dt.date(y + (m // 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return "%04d-%02d-%02d" % (y, m, min(d, last))


def money(v):
    v = r2(v)
    body = "{:,}".format(int(abs(v))) if v == int(v) else "{:,.2f}".format(abs(v))
    return ("-$" if v < 0 else "$") + body


# ----------------------------------------------------------------------------- the ledger in
def clean_entry(e, today):
    if not isinstance(e, dict) or e.get("kind") not in KINDS:
        return None
    amount = num(e.get("amount"))
    if amount is None or amount <= 0 or amount > 1e9:
        return None
    date = e.get("date") if is_date(e.get("date")) else None
    if date is None:
        off = num(e.get("off"))
        if off is not None and abs(off) < 20000:
            date = add_days(today, int(off))
    if date is None:
        return None
    out = {"id": text(e.get("id"), 40), "kind": e["kind"], "amount": r2(amount), "date": date, "cat": text(e.get("cat"), 40) or e["kind"],
           "acct": text(e.get("acct"), 40) or "general", "note": text(e.get("note"), 160)}
    rec = e.get("rec")
    if isinstance(rec, dict) and rec.get("every") in EVERY:
        out["rec"] = {"every": rec["every"], "until": rec["until"] if is_date(rec.get("until")) else None}
    return out


def normalize(raw, today):
    """Any of: a Ledger export {entries, settings, accounts?}, a bare list of entries, a JSON string. Never throws. Returns the cleaned ledger."""
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if isinstance(raw, list):
        raw = {"entries": raw}
    out = {"entries": [], "settings": {"taxPct": 30.0}, "accounts": {}, "skipped": 0, "demo": False, "note": "", "opts": {}}
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        return out
    seen = set()
    for i, e in enumerate(raw["entries"][:5000]):
        c = clean_entry(e, today)
        if not c:
            out["skipped"] += 1
            continue
        if not c["id"] or c["id"] in seen:
            c["id"] = "n%d" % i
        seen.add(c["id"])
        out["entries"].append(c)
    st = raw.get("settings")
    if isinstance(st, dict) and num(st.get("taxPct")) is not None:
        out["settings"]["taxPct"] = clamp(num(st["taxPct"]), 0.0, 60.0)
    if isinstance(raw.get("accounts"), list):
        for a in raw["accounts"][:100]:
            if isinstance(a, dict) and text(a.get("id"), 40):
                out["accounts"][text(a["id"], 40)] = text(a.get("name"), 60) or text(a["id"], 40)
    if isinstance(raw.get("opts"), dict):
        out["opts"] = {k: v for k, v in raw["opts"].items() if k in DEFAULTS and num(v) is not None}
    out["demo"] = raw.get("demo") is True
    out["source"] = text(raw.get("source"), 20)
    out["note"] = text(raw.get("note"), 200)
    return out


def occurrences(e, today):
    if "rec" not in e:
        return [e["date"]] if e["date"] <= today else []
    rec = e["rec"]
    stop = rec["until"] if rec.get("until") and rec["until"] < today else today
    out = []
    for i in range(1200):
        if rec["every"] == "week":
            d = add_days(e["date"], 7 * i)
        elif rec["every"] == "month":
            d = add_months(e["date"], i)
        else:
            d = add_months(e["date"], 12 * i)
        if d > stop:
            break
        out.append(d)
    return out


def expand(entries, today):
    out = []
    for e in entries:
        for d in occurrences(e, today):
            c = dict(e)
            c["date"] = d
            out.append(c)
    return out


def monthly_of(e):
    k = 52 / 12 if e["rec"]["every"] == "week" else 1.0 if e["rec"]["every"] == "month" else 1 / 12
    return e["amount"] * k


def merge_opts(o):
    d = dict(DEFAULTS)
    if isinstance(o, dict):
        for k in d:
            v = num(o.get(k))
            if v is not None:
                d[k] = v
    d["tax"] = clamp(d["tax"], 0.0, 0.6)
    d["emergency"] = clamp(d["emergency"], 0.0, 1.0)
    d["reinvest"] = clamp(d["reinvest"], 0.0, 1.0)
    if d["tax"] + d["emergency"] + d["reinvest"] > 1:          # the pay-yourself share is what is left; trim reinvest first, then emergency
        d["reinvest"] = max(0.0, 1 - d["tax"] - d["emergency"])
        d["emergency"] = max(0.0, 1 - d["tax"] - d["reinvest"])
    d["living"] = clamp(d["living"], 0.0, 1e6)
    d["em_months"] = clamp(d["em_months"], 0.0, 36.0)
    d["em_saved"] = clamp(d["em_saved"], 0.0, 1e9)
    d["cap"] = int(clamp(math.floor(d["cap"]), 1, 20))
    d["proj_re"] = clamp(d["proj_re"], 0.0, 1.0)
    d["months"] = int(clamp(math.floor(d["months"]), 1, 36))
    d["account_cost"] = clamp(d["account_cost"], 0.0, 100000.0)
    return d


# ----------------------------------------------------------------------------- the leaks
def analyze(ledger, today, opts=None):
    want = {"tax": ledger["settings"].get("taxPct", 30.0) / 100}
    want.update(ledger.get("opts") or {})
    want.update(opts or {})
    o = merge_opts(want)
    ex = expand(ledger["entries"], today)
    d90, d365 = add_days(today, -90), add_days(today, -365)
    mkey = today[:7]

    def tot(kinds, since=None, pred=None):
        return r2(sum(e["amount"] for e in ex if e["kind"] in kinds and (since is None or e["date"] > since) and (pred is None or pred(e))))

    payouts, other_inc = tot(("payout_in",)), tot(("income",))
    fees, resets, activation, expenses = tot(("fee",)), tot(("reset",)), tot(("activation",)), tot(("expense",))
    income, costs = r2(payouts + other_inc), r2(fees + resets + activation + expenses)
    net = r2(income - costs)
    inc90, cost90 = tot(("payout_in", "income"), d90), tot(("fee", "reset", "activation", "expense"), d90)
    net90 = r2(inc90 - cost90)
    monthly_net, monthly_income = r2(net90 / 3), r2(inc90 / 3)
    net365 = r2(tot(("payout_in", "income"), d365) - tot(("fee", "reset", "activation", "expense"), d365))
    mtd_net = r2(sum((1 if KINDS[e["kind"]] > 0 else -1) * e["amount"] for e in ex if KINDS[e["kind"]] != 0 and e["date"][:7] == mkey))

    # accounts
    ids = []
    for e in ex:
        if e["acct"] not in NOT_ACCOUNTS and e["kind"] in ("fee", "reset", "activation", "payout_in", "payout_req") and e["acct"] not in ids:
            ids.append(e["acct"])
    accounts = []
    for a in ids:
        mine = [e for e in ex if e["acct"] == a]
        cost = r2(sum(e["amount"] for e in mine if e["kind"] in ("fee", "reset", "activation")))
        got = r2(sum(e["amount"] for e in mine if e["kind"] == "payout_in"))
        resets_a = [e for e in mine if e["kind"] == "reset"]
        cost_dates = [e["date"] for e in mine if e["kind"] in ("fee", "reset", "activation")]
        first = min(cost_dates) if cost_dates else min(e["date"] for e in mine)
        age = days_between(first, today)
        reset_cost = r2(sum(e["amount"] for e in resets_a))
        after = 0.0
        if resets_a:
            fr = min(e["date"] for e in resets_a)
            after = r2(sum(e["amount"] for e in mine if e["kind"] == "payout_in" and e["date"] >= fr))
        if cost > 0 and got >= cost:
            status = "paid"
        elif cost > 0 and got == 0 and age >= 30:
            status = "never"
        elif cost > 0 and got < cost and age >= 60:
            status = "behind"
        else:
            status = "young"
        accounts.append({"id": a, "name": ledger["accounts"].get(a, a), "cost": cost, "received": got, "net": r2(got - cost), "first": first, "age": age,
                         "resets": len(resets_a), "reset_cost": reset_cost, "after_reset": after, "status": status})

    # subscriptions (recurring costs still running)
    subs = []
    for e in ledger["entries"]:
        if "rec" in e and KINDS[e["kind"]] < 0 and not (e["rec"].get("until") and e["rec"]["until"] < today) and e["date"] <= today:
            m = r2(monthly_of(e))
            subs.append({"name": e["note"] or e["cat"], "cat": e["cat"], "monthly": m, "annual": r2(m * 12), "share": r2(m / max(1.0, monthly_income))})
    burn = r2(sum(s["monthly"] for s in subs))

    leaks = []
    fee_all = r2(fees + resets + activation)
    ratio = fee_all / payouts if payouts > 0 else None
    if fee_all > 0:
        if ratio is None:
            score, risk, det = 90, "high", "You paid %s in fees and resets and nothing has been paid out yet." % money(fee_all)
        else:
            score = int(clamp(math.floor(ratio * 80 + 0.5), 0, 100))
            risk = "low" if ratio < 0.25 else "med" if ratio < 0.6 else "high"
            det = "Fees and resets cost %s against %s of payouts received: %s of every $1 paid out went on fees (estimate)." % (money(fee_all), money(payouts), "$%.2f" % r2(ratio))
        leaks.append({"id": "fees", "title": "Fees against payouts", "detail": det, "usd": fee_all, "score": score, "risk": risk})
    for a in accounts:
        if a["resets"] > 0:
            gap = r2(a["reset_cost"] - a["after_reset"])
            if gap > 0:
                leaks.append({"id": "reset:" + a["id"], "title": "Resets that did not pay back: " + a["name"], "usd": gap,
                              "detail": "%d reset%s cost %s; this account paid out %s since the first one, so %s is still unrecovered." % (a["resets"], "" if a["resets"] == 1 else "s", money(a["reset_cost"]), money(a["after_reset"]), money(gap)),
                              "score": int(clamp(math.floor(40 + 15 * a["resets"] + 30 * (gap / a["reset_cost"]) + 0.5), 0, 100)), "risk": "high" if a["resets"] >= 2 else "med"})
        if a["status"] in ("never", "behind"):
            miss = r2(a["cost"] - a["received"])
            if a["status"] == "never":
                det, score, risk = "%s of cost and no payout in %d days: it has never covered its cost." % (money(a["cost"]), a["age"]), 70 + int(min(30, a["age"] // 6)), "high"
            else:
                det, score, risk = "%s of cost, %s paid back in %d days: %s still to recover." % (money(a["cost"]), money(a["received"]), a["age"], money(miss)), 45, "med"
            leaks.append({"id": "never:" + a["id"], "title": ("Never covered its cost: " if a["status"] == "never" else "Still behind: ") + a["name"], "detail": det, "usd": miss, "score": int(clamp(score, 0, 100)), "risk": risk})
    for s in subs:
        sc = int(clamp(math.floor(s["share"] * 400 + 0.5), 0, 100))
        risk = "low" if s["share"] < 0.03 else "med" if s["share"] < 0.10 else "high"
        det = "%s a month (%s a year) is %d%% of the %s a month coming in." % (money(s["monthly"]), money(s["annual"]), int(math.floor(s["share"] * 100 + 0.5)), money(monthly_income))
        leaks.append({"id": "sub:" + s["name"], "title": "Subscription: " + s["name"], "detail": det, "usd": s["annual"], "score": sc, "risk": risk})
    leaks.sort(key=lambda x: (-x["score"], x["id"]))
    flagged = r2(sum(s["monthly"] for s in subs if s["share"] >= 0.03))
    lossy90 = r2(sum(e["amount"] for e in ex if e["kind"] in ("fee", "reset", "activation") and e["date"] > d90 and any(a["id"] == e["acct"] and a["status"] in ("never", "behind") for a in accounts)))
    leak_month = r2(flagged + lossy90 / 3)

    # tax set-aside (generic)
    base = max(0.0, net365)
    set_aside = r2(base * o["tax"])
    paid = r2(sum(e["amount"] for e in ex if e["kind"] == "tax"))
    tax = {"pct": o["tax"], "base": r2(base), "set_aside": set_aside, "paid": paid, "still": r2(max(0.0, set_aside - paid)), "month": r2(max(0.0, mtd_net) * o["tax"]), "note": NOTE_TAX}

    # buckets
    M = max(0.0, monthly_net)
    pay_pct = max(0.0, 1 - o["tax"] - o["emergency"] - o["reinvest"])
    alloc = {"tax": r2(M * o["tax"]), "emergency": r2(M * o["emergency"]), "reinvest": r2(M * o["reinvest"]), "pay": r2(M * pay_pct)}
    prog = clamp(mtd_net / M, 0.0, 1.0) if M > 0 else 0.0
    fees_only = [e["amount"] for e in ex if e["kind"] == "fee"]
    acct_cost = r2(o["account_cost"]) if o["account_cost"] > 0 else r2(sum(fees_only) / len(fees_only)) if fees_only else DEFAULT_ACCOUNT_COST
    raw_b = [
        ("tax", "Tax set-aside", tax["set_aside"], paid),
        ("emergency", "Emergency fund", r2(o["em_months"] * o["living"]), o["em_saved"]),
        ("pay", "Pay yourself", alloc["pay"], r2(alloc["pay"] * prog)),
        ("reinvest", "Next account", acct_cost, r2(max(0.0, net90) * o["reinvest"])),
    ]
    buckets = []
    for k, label, target, saved in raw_b:
        got = min(saved, target)
        buckets.append({"id": k, "label": label, "target": r2(target), "saved": r2(got), "fill": r4(got / target) if target > 0 else None})
    tt = sum(b["target"] for b in buckets)
    fill = r4(sum(b["saved"] for b in buckets) / tt) if tt > 0 else 0.0

    # compounding projector
    recent = {e["acct"] for e in ex if e["kind"] == "fee" and e["acct"] not in NOT_ACCOUNTS and e["date"] > add_days(today, -120)}
    n0 = max(1, len(recent))
    proj = {"n0": n0, "account_cost": acct_cost, "monthly_profit": r2(M), "per_account": r2(M / n0), "cap": o["cap"], "months": o["months"], "scenarios": []}
    for name, mult in SCEN:
        y = M / n0 * mult
        # withdraw: the same n0 accounts, everything after tax is kept
        kept_w, n_r, kept_r, carry = 0.0, float(n0), 0.0, 0.0
        sw, sr, nr = [], [], []
        for _ in range(o["months"]):
            kept_w += y * n0 * (1 - o["tax"])
            after = y * n_r * (1 - o["tax"])
            put = after * o["proj_re"]
            kept_r += after - put
            budget = carry + put
            room = o["cap"] - n_r
            buy = max(0, int(min(room, math.floor(budget / acct_cost + 1e-9)))) if room > 0 else 0
            budget -= buy * acct_cost
            if n_r + buy >= o["cap"]:            # at the cap there is nothing more to buy: the rest goes to the household
                kept_r += budget
                budget = 0.0
            carry = budget
            n_r += buy
            sw.append(r2(kept_w))
            sr.append(r2(kept_r + carry))
            nr.append(int(n_r))
        proj["scenarios"].append({"id": name, "mult": mult, "withdraw": sw, "reinvest": sr, "accounts": nr, "end_withdraw": sw[-1], "end_reinvest": sr[-1],
                                  "end_accounts": nr[-1], "monthly_end_withdraw": r2(y * n0 * (1 - o["tax"])), "monthly_end_reinvest": r2(y * nr[-1] * (1 - o["tax"]))})
    totals = {"income": income, "payouts": payouts, "fees": fees, "resets": resets, "activation": activation, "expenses": expenses, "costs": costs, "net": net,
              "net90": net90, "net365": net365, "mtd_net": mtd_net}
    return {"today": today, "opts": o, "totals": totals, "monthly": {"net": monthly_net, "income": monthly_income, "burn": burn}, "accounts": accounts, "subs": subs,
            "leaks": leaks, "leak_month": leak_month, "tax": tax, "alloc": alloc, "buckets": buckets, "fill": fill, "projector": proj}


def headline(a):
    n = len([x for x in a["leaks"] if x["risk"] in ("med", "high")])
    if not a["leaks"]:
        return {"text": "No leaks found yet: add fees, payouts and subscriptions to your ledger and OIKOS will check them.", "usd_month": 0.0}
    return {"text": "%d leak%s worth watching; about %s a month is going out without paying back (estimate)." % (n, "" if n == 1 else "s", money(a["leak_month"])), "usd_month": a["leak_month"]}


def build(ledger, today, status, opts=None, asof=None):
    a = analyze(ledger, today, opts)
    items = [{"title": x["title"], "detail": x["detail"], "usd": x["usd"], "score": x["score"], "risk": x["risk"]} for x in a["leaks"]]
    t = a["tax"]
    items.append({"title": "Tax set-aside (generic, not tax advice)", "detail": "At %d%% of the last 12 months' net profit (%s) put aside %s; %s moved so far." % (int(math.floor(t["pct"] * 100 + 0.5)), money(t["base"]), money(t["set_aside"]), money(t["paid"])),
                  "usd": t["set_aside"], "score": 30, "risk": "low"})
    base = next(s for s in a["projector"]["scenarios"] if s["id"] == "base")
    items.append({"title": "Reinvest or withdraw (base case, estimate)", "detail": "In %d months: %s kept if you withdraw, %s kept plus %d accounts if you reinvest half of what is left after tax, if each new account earns what the current ones do." % (a["projector"]["months"], money(base["end_withdraw"]), money(base["end_reinvest"]), base["end_accounts"]),
                  "usd": r2(base["end_reinvest"] - base["end_withdraw"]), "score": 20, "risk": "med"})
    notes = ["Everything is an estimate from the entries you recorded in the Ledger; nothing here moves money or trades.",
             NOTE_TAX,
             "The projector is not a promise: new accounts run the same strategy, so they win and lose together, and a bad month cuts every account at once.",
             "Sample ledger (not yours) - export your own from the Ledger app and run again with --ledger." if status == "sample" else
             "Built from your bank exports (tools/money_import.py, category level)." if ledger.get("source") == "money_import" else "Built from your Ledger export."]
    if ledger["skipped"]:
        notes.append("%d row%s in the file could not be read and %s skipped." % (ledger["skipped"], "" if ledger["skipped"] == 1 else "s", "was" if ledger["skipped"] == 1 else "were"))
    return {"v": 1, "id": "oikos", "asof": asof or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "paper", "status": status,
            "headline": headline(a), "items": items, "notes": notes,
            "ledger": {"entries": ledger["entries"], "settings": ledger["settings"], "accounts": [{"id": k, "name": v} for k, v in ledger["accounts"].items()], "opts": ledger["opts"], "demo": ledger["demo"], "note": ledger["note"]},
            "analysis": a}


def bank_ledger(env=None):
    """the household ledger tools/money_import.py builds from your own bank exports (<OLYMPUS_HOME or %USERPROFILE%\\.olympus>/money/
    oikos_ledger.json, private, outside the repo), when it exists; the default when no --ledger is given (tools/bat/RUN_MONEY.bat runs the importer first)"""
    env = os.environ if env is None else env
    home = env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")
    p = os.path.join(home, "money", "oikos_ledger.json")
    return p if os.path.isfile(p) else None


def load_file(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------- selftest: hand-checked numbers
def selftest():
    bad = []

    def chk(name, got, want):
        ok = got == want
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else "  got %r want %r" % (got, want)))
        if not ok:
            bad.append(name)

    today = "2026-11-10"
    chk("add_months clamps 31 Jan + 1 month to 28 Feb", add_months("2027-01-31", 1), "2027-02-28")
    chk("add_days across a year", add_days("2026-12-31", 1), "2027-01-01")
    chk("r2 rounds half up", (r2(2.675), r2(-1.005), r2(0.1 + 0.2)), (2.68, -1.0, 0.3))
    chk("junk ledger gives an empty one", normalize("not json", today)["entries"], [])
    chk("bad rows are skipped and counted", (normalize({"entries": [{"kind": "fee", "amount": -3, "date": today}, {"kind": "zzz"}, {"kind": "fee", "amount": "$91.80", "date": today}]}, today)["skipped"]), 2)
    # a tiny ledger worked by hand
    led = normalize({"entries": [
        {"id": "a", "kind": "fee", "amount": 100, "date": "2026-08-15", "acct": "A"},
        {"id": "b", "kind": "reset", "amount": 50, "date": "2026-09-01", "acct": "A"},
        {"id": "c", "kind": "payout_in", "amount": 300, "date": "2026-09-20", "acct": "A"},
        {"id": "d", "kind": "fee", "amount": 40, "date": "2026-09-05", "acct": "B"},
        {"id": "e", "kind": "expense", "amount": 30, "date": "2026-08-10", "acct": "general", "note": "Feed", "rec": {"every": "month"}},
        {"id": "f", "kind": "payout_in", "amount": 600, "date": "2026-10-20", "acct": "A"},
        {"id": "g", "kind": "tax", "amount": 50, "date": "2026-10-25"},
    ]}, today)
    a = analyze(led, today, {"tax": 0.25})
    t = a["totals"]
    # feed on 08-10, 09-10, 10-10, 11-10 = 4 x 30 = 120
    chk("totals: payouts 900, fees 140, resets 50, expenses 120, net 590", (t["payouts"], t["fees"], t["resets"], t["expenses"], t["net"]), (900.0, 140.0, 50.0, 120.0, 590.0))
    chk("last 90 days (after 2026-08-12): income 900, costs 100+50+40+90 = 280 -> net 620; 206.67 a month", (t["net90"], a["monthly"]["net"]), (620.0, 206.67))
    chk("subscription: 30 a month, 360 a year", (a["subs"][0]["monthly"], a["subs"][0]["annual"]), (30.0, 360.0))
    acc = {x["id"]: x for x in a["accounts"]}
    chk("account A cost 150 got 900 -> paid; B cost 40 got 0 age 66 -> never", (acc["A"]["status"], acc["A"]["net"], acc["B"]["status"], acc["B"]["age"]), ("paid", 750.0, "never", 66))
    chk("a reset that paid back is not a leak (A: 50 reset, 900 after)", any(x["id"] == "reset:A" for x in a["leaks"]), False)
    chk("a never-covered account is a high leak of $40", [(x["usd"], x["risk"]) for x in a["leaks"] if x["id"] == "never:B"], [(40.0, "high")])
    chk("fees against payouts: 190 / 900 -> score 17, low", [(x["usd"], x["score"], x["risk"]) for x in a["leaks"] if x["id"] == "fees"], [(190.0, 17, "low")])
    chk("tax at 25% of net365 590 = 147.50, 50 moved, 97.50 still to set aside", (a["tax"]["set_aside"], a["tax"]["paid"], a["tax"]["still"]), (147.5, 50.0, 97.5))
    chk("buckets: pay = 206.67 x 0.30 = 62; reinvest target = average fee 70", (a["alloc"]["pay"], a["buckets"][3]["target"]), (62.0, 70.0))
    p = a["projector"]
    chk("projector: 2 accounts bought in the last 120 days -> n0 2, 206.67 / 2 = 103.34 a month each", (p["n0"], p["per_account"]), (2, 103.34))
    base = p["scenarios"][1]
    chk("withdraw base: 206.67 x 0.75 = 155.00 a month, 12 months = 1860.03", (base["withdraw"][0], base["end_withdraw"]), (155.0, 1860.03))
    chk("reinvest never beats the cap and never shows fewer accounts", (base["accounts"][-1] <= p["cap"], base["accounts"][-1] >= p["n0"]), (True, True))
    chk("conservative <= base <= optimistic at the end", p["scenarios"][0]["end_withdraw"] <= base["end_withdraw"] <= p["scenarios"][2]["end_withdraw"], True)
    # a loss-making household never shows a positive projection
    neg = analyze(normalize({"entries": [{"kind": "fee", "amount": 90, "date": "2026-10-01", "acct": "Z"}]}, today), today)
    chk("loss only: monthly net negative, projector flat at 0, tax 0", (neg["monthly"]["net"], neg["projector"]["scenarios"][1]["end_withdraw"], neg["tax"]["set_aside"]), (-30.0, 0.0, 0.0))
    # the sample
    s = build(normalize(load_file(SAMPLE), today), today, "sample", asof="2026-11-10T00:00:00Z")
    chk("sample builds: status sample, a headline, items with the contract keys", (s["status"], bool(s["headline"]["text"]), all(set(i) == {"title", "detail", "usd", "score", "risk"} for i in s["items"])), ("sample", True, True))
    chk("sample leaks include a reset gap and a never-covered account", ({"reset:demoB", "never:demoC"} <= {x["id"] for x in s["analysis"]["leaks"]}), True)
    chk("empty ledger still gives a headline and a projector", (build(normalize({}, today), today, "ok")["headline"]["usd_month"], len(build(normalize({}, today), today, "ok")["analysis"]["projector"]["scenarios"])), (0.0, 3))
    print("\n%d failed" % len(bad) if bad else "\nall selftests passed")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="OIKOS: find the leaks in a Ledger export (paper, offline).")
    ap.add_argument("--out", help="folder to write oikos.json into")
    ap.add_argument("--fixture", action="store_true", help="use the bundled sample ledger")
    ap.add_argument("--ledger", help="a Ledger app JSON export")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--tax", type=float, help="tax set-aside percent (default: the ledger's setting, 30)")
    ap.add_argument("--selftest", action="store_true")
    ns = ap.parse_args(argv)
    if ns.selftest:
        return selftest()
    today = ns.today if ns.today and is_date(ns.today) else dt.datetime.now(dt.timezone.utc).date().isoformat()
    status, raw = "sample", None
    path = ns.ledger or (None if ns.fixture else bank_ledger())
    if path and not ns.fixture:
        try:
            raw = load_file(path)
            status = "ok"
        except (OSError, ValueError) as e:
            print("could not read %s (%s): using the sample" % (path, e), file=sys.stderr)
    if raw is None:
        raw = load_file(SAMPLE)
    led = normalize(raw, today)
    if status == "ok" and isinstance(raw, dict) and isinstance(raw.get("exported"), str) and is_date(raw["exported"][:10]) and days_between(raw["exported"][:10], today) > 45:
        status = "stale"
    if status != "sample" and not led["entries"]:
        status = "stale"
    doc = build(led, today, status, {"tax": ns.tax / 100} if ns.tax is not None else None)
    if ns.out:
        os.makedirs(ns.out, exist_ok=True)
        with open(os.path.join(ns.out, "oikos.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
        print("wrote %s (%s): %s" % (os.path.join(ns.out, "oikos.json"), status, doc["headline"]["text"]))
    else:
        print(json.dumps(doc["headline"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
