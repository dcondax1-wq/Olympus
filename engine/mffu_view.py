"""MFFU VIEW (owner 2026-11-18: "I want a page where I can see exact accounts just like the MFFU site, the exact stats, dates,
pass, all of that exactly how MFFU shows it"; night-mffu2: "everything on the accounts to the point where I barely even have to
open MFFU on Safari"). The SMALL extra the PC adds to its ntfy status post so the phone page tools/web_public/business/mffu.html
can draw one MFFU-style card per account. Read only: it never trades, arms or sizes.

compact(L) -> {"t", "a": [row, ...]} or None, from the PC's full live.json L (engine/live_publish.build): its "accounts"
(the bot's own ledgers: eval start, P&L per day, closed trades, stats) and the board's ATLAS card (account B: start, the
funded payout tracker, its live trades). One row per real account, keyed by the PC id the pages match on:
  id   PC id (mffu50k_eval, b25k_2, atlas ...)        l4   the broker account's last 4 digits only (never the full id)
  nm   the owner's name of the account (owner_name: "Zlarior 50K", "Zlarior 25K #2", "ATLAS 25K funded"), never an id
  sd   start date (YYYY-MM-DD)                       td   trading days (days with a closed trade)
  lt   the last traded day (MFFU's 7-day inactivity rule counts from it; from sd when there is none)
  n/w  closed trades / winners since the start       bd/wd  best / worst day [YYYY-MM-DD, $]   (td / n / w left out when 0)
  pf / aw / al   profit factor, average win $, average loss $      bt / wt  best / worst trade $      ct  contracts traded
       (MFFU's stats dashboard: best and worst trades, average wins and losses, trade count, contracts, win rate, profit factor)
  eq   end-of-day P&L since the start (balance - start balance), last EQ_N days, whole $; the first point = before the first shown day
  f    funded payout tracker: cp cycle profit, bd best day, cd cycle days, ef eligible from, pn payouts taken, mr max request,
       st the tracker's status (building / consistency / eligible / ready / lost / graduated), ft first funded trade day,
       pt $ paid to you so far (left out when 0)
Only what changes when a trade closes or a day ends rides here (the ext post's news hash, tools/pc_report.ext_hash): the live
balance, floor, today's $ and the open position stay in the core post (board cards, accounts) every 15 minutes.
Typical size ~200-280 bytes an account (3 accounts ~770); tools/pc_report trims with cut_eq: 4 equity points, then cut_eq(0) = no equity line and no
dashboard stats (pf / aw / al / bt / wt / ct), then the whole block, before the accounts block of the core.
Tests: tests/test_mffu_view.py (size, fields, no ids, names, the split), tests/test_live_publish.py (mffu_checks).
"""
from __future__ import annotations

import re

EQ_N = 8
STATS = ("pf", "aw", "al", "bt", "wt", "ct")       # the dashboard stats cut_eq(0) drops


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _i(v):
    x = _f(v)
    return None if x is None else int(round(x))


def last4(name) -> str | None:
    m = re.findall(r"\d", str(name or ""))
    return "".join(m[-4:]) if len(m) >= 4 else None


def _day(s) -> str | None:
    s = str(s or "")[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def owner_name(acct_id=None, name=None, plan=None, stage=None) -> str:
    """The owner's name of an account (owner 2026-11-18: "Zlarior 50K", "Zlarior 25K #2", "ATLAS 25K funded"): the bot that
    trades it (ATLAS on ATLAS's own account, Rapid EOD on a Rapid, else Zlarior = LIT), the plan size, "#n" when the account's
    name carries one (#2 and up), "funded" once funded. Built from words only: never a broker id (an id's digits are not a size).
    The page's twin: tools/web_public/business/mffucenter.js ownerName (tests run both on the same cases)."""
    try:
        i, n, p = str(acct_id or "").strip().lower(), str(name or ""), str(plan or "")
        rapid = bool(re.search(r"\brapid\b", f"{n} {p}", re.I)) or i.startswith("rapid")
        bot = "Rapid EOD" if rapid else "ATLAS" if (i in ("atlas", "acct_b") or re.search(r"\batlas\b", n, re.I)) else "Zlarior"
        m = re.search(r"(?<![\w$])(\d{2,3})\s*k\b", p, re.I) or re.search(r"(?<![\w$])(\d{2,3})\s*k\b", n, re.I) \
            or re.fullmatch(r"[a-z]*?(\d{2,3})k(?:_[a-z0-9]+)?", i)
        size = f" {m.group(1)}K" if m else ""
        h = re.search(r"#\s*(\d{1,2})\b", n)
        num = f" #{h.group(1)}" if h and h.group(1) not in ("0", "1") else ""
        funded = " funded" if str(stage or "").strip().lower() in ("funded", "payout_ready", "lost", "sim funded") else ""
        return f"{bot}{size}{num}{funded}"
    except Exception:  # noqa: BLE001
        return "Account"


def _days_stats(days: list, balance, start, start_bal=None) -> dict:
    """days = [[day, $], ...] oldest first (traded days)."""
    real = [(d, v) for d, v in ((_day(x[0]), _f(x[1])) for x in days if isinstance(x, (list, tuple)) and len(x) >= 2)
            if d and v is not None and (not start or d >= start)]
    traded = [d for d, v in real if abs(v) > 0.005]
    out = {"td": len(traded)}
    if traded:
        out["lt"] = max(traded)
    if real:
        b = max(real, key=lambda x: x[1])
        w = min(real, key=lambda x: x[1])
        out["bd"] = [b[0], _i(b[1])]
        out["wd"] = [w[0], _i(w[1])]
    bal = _f(balance)
    if bal is not None and _f(start_bal) is not None:
        bal -= _f(start_bal)
    if bal is not None and real:
        pts = [bal]
        for _, v in reversed(real[-EQ_N:]):
            pts.append(pts[-1] - v)
        out["eq"] = [_i(x) for x in reversed(pts)]
    return out


def _trade_stats(rows: list, st: dict | None = None) -> dict:
    """rows = [($, qty, day), ...] closed trades -> pf / aw / al / bt / wt / ct (the ledger's own stats win for pf / aw / al)."""
    pn = [x[0] for x in rows if x[0] is not None]
    w, lo = [x for x in pn if x > 0], [x for x in pn if x < 0]
    out = {}
    if pn:
        out["bt"], out["wt"] = _i(max(pn)), _i(min(pn))
    if w:
        out["aw"] = _i(sum(w) / len(w))
    if lo:
        out["al"] = _i(sum(lo) / len(lo))
    if w and lo:
        out["pf"] = round(sum(w) / -sum(lo), 2)
    ct = sum(abs(x[1]) for x in rows if x[1])
    if ct:
        out["ct"] = int(ct)
    st = _d(st)
    for k, sk in (("pf", "pf"), ("aw", "avg_win"), ("al", "avg_loss")):
        v = _f(st.get(sk))
        if v is not None:
            out[k] = round(v, 2) if k == "pf" else _i(v)
    days = [x[2] for x in rows if x[2]]
    if days:
        out["lt"] = max(days)
    return out


def _funded(t) -> dict | None:
    t = _d(t)
    if not t:
        return None
    st = str(t.get("status") or "")[:12] or None
    pt = _i(t.get("paid_to_you"))
    out = {"cp": _i(t.get("cycle_profit")), "bd": _i(t.get("best_day")), "cd": _i(t.get("cycle_days")), "ef": _day(t.get("eligible_from")),
           "pn": _i(t.get("payouts_n")), "mr": _i(t.get("max_request")), "st": st if st and re.fullmatch(r"[a-z_]+", st) else None,
           "ft": _day(t.get("first_trade")), "pt": pt if pt else None}
    return {k: v for k, v in out.items() if v is not None} or None


def _merge_lt(row: dict, *days) -> None:
    ds = [d for d in [row.get("lt"), *days] if _day(d)]
    if ds:
        row["lt"] = max(ds)


def _row_of_account(a: dict) -> dict | None:
    if not a.get("id") or a.get("error") or a.get("kind") not in ("eval", "funded") or a.get("source") in ("cloud", "pc_blitz") \
            or a.get("id") == "acct_c":
        return None
    ev = _d(a.get("eval"))
    start = _day(ev.get("start"))
    days = _l(a.get("days"))
    if not start and days:
        start = _day(days[0][0]) if isinstance(days[0], (list, tuple)) and days[0] else None
    row = {"id": str(a["id"])[:24], "nm": owner_name(a.get("id"), a.get("name"), a.get("plan"), a.get("kind")), "sd": start}
    l4 = last4(a.get("broker_account"))
    if l4:
        row["l4"] = l4
    row.update(_days_stats(days, ev.get("balance"), start, ev.get("start_balance")))
    st = _d(a.get("stats"))
    trades = [t for t in _l(a.get("trades")) if isinstance(t, dict) and _f(t.get("pnl")) is not None
              and (not start or not _day(t.get("day")) or _day(t.get("day")) >= start)]
    if _i(st.get("n")) is not None:
        row["n"], row["w"] = _i(st.get("n")), _i(st.get("wins")) or 0
    else:
        row["n"], row["w"] = len(trades), sum(1 for t in trades if _f(t.get("pnl")) > 0)
    ts = _trade_stats([(_f(t.get("pnl")), _i(t.get("qty")), _day(t.get("day"))) for t in trades], st)
    lt = ts.pop("lt", None)
    row.update(ts)
    _merge_lt(row, lt)
    f = _funded(a.get("funded"))
    if f:
        row["f"] = f
    return row


def _row_of_atlas(L: dict) -> dict | None:
    """ATLAS's own account (account B): the board card + its routed trades (the board's trade list)."""
    bd = _d(L.get("board"))
    c = _d(bd.get("atlas"))
    if not c or c.get("error") or _f(c.get("balance")) is None:
        return None
    S = _d(_d(L.get("pc")).get("second"))
    ab = _d(_d(S.get("route")).get("account_b")) or _d(S.get("account_b"))
    ev = _d(ab.get("eval"))
    start = _day(c.get("eval_start")) or _day(ev.get("start"))
    funded = str(c.get("status") or "").lower() == "funded" or str(c.get("stage") or "").lower() == "funded"
    row = {"id": "atlas", "nm": owner_name("atlas", "ATLAS", c.get("plan") or "Builder 25K", "funded" if funded else "eval"), "sd": start}
    l4 = last4(c.get("broker") or ab.get("account"))
    if l4:
        row["l4"] = l4
    trades = [t for t in _l(bd.get("trades")) if isinstance(t, dict) and t.get("acct") == "atlas" and t.get("src") != "paper"
              and not t.get("open") and _f(t.get("usd")) is not None and (not start or str(t.get("day") or "") >= start)]
    per = {}
    for t in trades:
        d = _day(t.get("day"))
        if d:
            per[d] = per.get(d, 0.0) + float(t["usd"])
    sb = (_f(c.get("balance")) - _f(c.get("profit"))) if _f(c.get("profit")) is not None else None
    row.update(_days_stats(sorted([[d, v] for d, v in per.items()]), c.get("balance"), start, sb))
    if _i(ev.get("days_traded")) is not None:
        row["td"] = max(row.get("td") or 0, _i(ev.get("days_traded")))
    row["n"], row["w"] = len(trades), sum(1 for t in trades if float(t["usd"]) > 0)
    ts = _trade_stats([(_f(t.get("usd")), _i(t.get("qty")), _day(t.get("day"))) for t in trades])
    lt = ts.pop("lt", None)
    row.update(ts)
    _merge_lt(row, lt)
    f = _funded(c.get("funded"))
    if f:
        row["f"] = f
    return row


def compact(L: dict | None) -> dict | None:
    """The "mf" block of the ntfy status post. Never raises; None when there is nothing to say."""
    try:
        L = _d(L)
        rows = []
        for a in _l(L.get("accounts")):
            r = _row_of_account(_d(a))
            if r:
                rows.append(r)
        r = _row_of_atlas(L)
        if r and not any(x["id"] == "atlas" for x in rows):
            rows.append(r)
        if not rows:
            return None
        return {"t": _i(_d(L.get("board")).get("data_t")) or _i(L.get("t")),        # zero td / n / w are left out (= 0)
                "a": [{k: v for k, v in x.items() if v is not None and not (k in ("td", "n", "w") and v == 0)} for x in rows][:6]}
    except Exception:  # noqa: BLE001
        return None


def cut_eq(mf: dict | None, n: int) -> None:
    """Keep only the last n equity points (0 = none) of every row, in place. n <= 0 also drops the dashboard stats (STATS):
    the last cut before tools/pc_report leaves the whole block out. Never raises."""
    try:
        for r in _l(_d(mf).get("a")):
            if isinstance(r, dict):
                if n <= 0:
                    r.pop("eq", None)
                    for k in STATS:
                        r.pop(k, None)
                elif "eq" in r:
                    r["eq"] = _l(r["eq"])[-n:]
    except Exception:  # noqa: BLE001
        pass
