"""Data for the PC dashboard's hub pages (Prop Firms, Business, Market, Learn, System) and the phone export.

Pure, read-only functions over the repo's files (no orders, no state writes, no secrets). engine/hub_api.py serves them on
the PC (with the PC bot's live account and logs when it runs); `python tools/hub_data.py` writes the phone export
research/props/hub.json (no bot), which tools/build_web_dashboard.py passes through as data.json "hub".

  firms_view()                 research/props/firms.json + LIT fit per plan (research/lit/funded_firms.json) + flat table
  eval_odds(profit, session)   Monte Carlo (research/lab/montecarlo.json paths) conditioned on $ to go and sessions left
  business_view(acct)          payout calendar, live-move guide, fees + net P&L, tax set-aside, goal, eval odds, floor
                               gauge, MFFU compliance, scaling + withdrawal planner inputs
  market_view(brief)           week calendar, mega-cap earnings, CME holidays, roll countdown, VIX / VXN regime + target
                               band, overnight recap, weekly / monthly levels
  learn_view()                 strategy versions, research library, LIT glossary + steps, trade gallery, upgrades
  system_view(bot)             discipline log, PC uptime, data quality

  python tools/hub_data.py [--out research/props/hub.json] [--no-fetch]
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import math
import os
import re
import statistics as stx
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
PROPS = os.path.join(ROOT, "research", "props")
LAB = os.path.join(ROOT, "research", "lab")
LIT_DOCS = os.path.join(ROOT, "research", "lit")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
DATA = os.path.join(ROOT, "data")
LOGS = os.path.join(ROOT, "logs")
VERSION = 1
_lock = threading.Lock()
_cache: dict = {}


# ------------------------------------------------------------------------------------------------ helpers
def _mt(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _json(path, default=None):
    """Parsed JSON, cached per mtime; default when missing or unreadable."""
    mt = _mt(path)
    if mt is None:
        return default
    with _lock:
        hit = _cache.get(("j", path))
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            val = json.load(fh)
    except Exception:
        return default
    with _lock:
        _cache[("j", path)] = (mt, val)
    return val


def _memo(key, deps, fn, ttl=None):
    """fn() cached until one of the dep files changes (and ttl seconds pass, when given)."""
    k = tuple(_mt(p) for p in deps)
    now = time.time()
    with _lock:
        hit = _cache.get(("m", key))
    if hit and hit[0] == k and (ttl is None or now - hit[2] < ttl):
        return hit[1]
    val = fn()
    with _lock:
        _cache[("m", key)] = (k, val, now)
    return val


def safe(fn, *a, **kw):
    """Never let one panel break the page: {"error": ...} instead of an exception."""
    try:
        return fn(*a, **kw)
    except Exception as e:                                   # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}


def _today(now=None) -> dt.date:
    return dt.datetime.fromtimestamp(now or time.time(), ET).date()


def _f(x, nd=2):
    try:
        v = float(x)
        return None if math.isnan(v) else round(v, nd)
    except (TypeError, ValueError):
        return None


def _trading_days(a: dt.date, n: int) -> list:
    """The next n CME trading days on/after a (weekdays without the full closures)."""
    from engine import sizing
    out, d = [], a
    shut = set()
    for y in (a.year, a.year + 1, a.year + 2):
        shut |= sizing._full_closures(y)
    while len(out) < n:
        if d.weekday() < 5 and d not in shut:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def firms_raw() -> dict:
    return _json(os.path.join(PROPS, "firms.json"), {}) or {}


def business_raw() -> dict:
    """research/business/prop_business.xlsx (sheets expenses / payouts, or the tracker's Fees / Payouts / Settings) when
    present, else research/props/business.json."""
    b = dict(_json(os.path.join(PROPS, "business.json"), {}) or {})
    xl = os.path.join(ROOT, "research", "business", "prop_business.xlsx")
    if os.path.exists(xl):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(xl, read_only=True, data_only=True)
            for sheet in ("expenses", "payouts"):
                if sheet in wb.sheetnames:
                    rows = list(wb[sheet].iter_rows(values_only=True))
                    hdr = [str(h or "").strip().lower() for h in rows[0]] if rows else []
                    out = []
                    for r in rows[1:]:
                        rec = dict(zip(hdr, r))
                        if rec.get("usd") is None:
                            continue
                        d = rec.get("date")
                        rec["date"] = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10]
                        rec["usd"] = float(rec["usd"])
                        out.append(rec)
                    b[sheet] = out
            _tracker_sheets(wb, b)                       # the business tracker's own layout (tools/build_business_tracker.py)
            b["source"] = "research/business/prop_business.xlsx"
        except Exception as e:                               # noqa: BLE001
            b["source_error"] = f"prop_business.xlsx unreadable: {e.__class__.__name__}"
    b.setdefault("source", "research/props/business.json")
    try:                                                     # the owner's CSV logs (tools/business.py, item 7 of the business tools)
        from tools import business as _biz
        b = _biz.merge_logs(b)
    except Exception as e:                                   # noqa: BLE001
        b["logs_error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    return b


def _tracker_sheets(wb, b):
    """research/business/prop_business.xlsx as tools/build_business_tracker.py writes it: sheets Fees (header row 3: Date,
    Firm, Account / nickname, Type, Description, Amount ($)), Payouts (Date received, ..., Received ($)) and Settings (Goal
    name, Goal price ($), Tax set-aside). Filled-in rows replace business.json's expenses / payouts; the goal and tax % follow
    the sheet so the Business page and the tracker agree. Formulas without cached values (never opened in Excel) read None."""
    def table(name, date_col, usd_col):
        if name not in wb.sheetnames:
            return None
        rows = list(wb[name].iter_rows(values_only=True))
        hi = next((i for i, r in enumerate(rows[:8]) if r and str(r[0] or "").strip().lower().startswith("date")), None)
        if hi is None:
            return None
        hdr = [str(h or "").strip() for h in rows[hi]]
        out = []
        for r in rows[hi + 1:]:
            rec = dict(zip(hdr, r))
            v, d = rec.get(usd_col), rec.get(date_col)
            if not isinstance(v, (int, float)) or d is None:
                continue
            out.append({"date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10],
                        "item": rec.get("Description") or rec.get("Account / nickname") or rec.get("Firm") or name[:-1].lower(),
                        "usd": float(v), "kind": (str(rec.get("Type") or "").lower().split() or [None])[0], "firm": rec.get("Firm"),
                        "account": rec.get("Account / nickname")})
        return out
    fees, pays = table("Fees", "Date", "Amount ($)"), table("Payouts", "Date received", "Received ($)")
    if fees:
        b["expenses"] = fees + [e for e in b.get("expenses") or [] if e.get("planned")]
    if pays:
        b["payouts"] = pays
    if "Settings" in wb.sheetnames:
        kv = {str(r[0]).strip(): r[1] for r in wb["Settings"].iter_rows(max_col=2, values_only=True) if r and r[0]}
        g = dict(b.get("goal") or {})
        if kv.get("Goal name"):
            g["name"] = kv["Goal name"]
        if isinstance(kv.get("Goal price ($)"), (int, float)):
            g["usd"] = float(kv["Goal price ($)"])
        b["goal"] = g
        t = kv.get("Tax set-aside (% of positive net)")
        if isinstance(t, (int, float)):
            b["tax"] = {**(b.get("tax") or {}), "set_aside_pct": round(float(t) * 100 if t <= 1 else float(t), 1)}


# ------------------------------------------------------------------------------------------------ 1. prop firms
def _lit_plan(pid):
    ff = _json(os.path.join(LIT_DOCS, "funded_firms.json"), {}) or {}
    return next((p for p in ff.get("plans") or [] if p.get("id") == pid), None)


def lit_fit(pid) -> dict | None:
    """LIT on this plan (research/lit/funded_firms.json): eval exact p10 / f10 / eventual, funded $/month, 6-month net."""
    p = _lit_plan(pid)
    if not p:
        return None
    r = p.get("results") or {}
    ev, mc, fu, life = r.get("eval") or {}, r.get("eval_mc") or {}, r.get("funded") or {}, r.get("life") or {}
    out = {"plan": pid, "source": "research/lit/funded_firms.json"}
    for h in ("H1", "H2", "2021-25"):
        e = ev.get(h) or {}
        out[h] = {"p10": e.get("p10"), "f10": e.get("f10"), "p15": e.get("p15"), "p60": e.get("p60"), "f60": e.get("f60"),
                  "pass_med": e.get("pass_med"), "mc_p10": (mc.get(h) or {}).get("p10"), "mc_p60": (mc.get(h) or {}).get("p60"),
                  "funded_month": (fu.get(h) or {}).get("per_month"), "funded_lost_6m": (fu.get(h) or {}).get("loss_6m"),
                  "first_pay_sessions": (fu.get(h) or {}).get("first_med"),
                  "net_month_6m": (life.get(h) or {}).get("net_per_month"), "months4_6": (life.get(h) or {}).get("months4_6_per_month"),
                  "neg_6m": (life.get(h) or {}).get("neg_6m")}
    out["cost_per_funded"] = r.get("cost_per_funded")
    out["eligible"], out["why"] = p.get("eligible"), p.get("why")
    return out


def _fv(x):
    return x.get("v") if isinstance(x, dict) else x


def firms_view() -> dict:
    deps = [os.path.join(PROPS, "firms.json"), os.path.join(LIT_DOCS, "funded_firms.json")]
    return _memo("firms", deps, _firms_view)


def _firms_view() -> dict:
    F = firms_raw()
    if not F:
        return {"error": "research/props/firms.json missing"}
    out = {k: F.get(k) for k in ("title", "built", "searched", "writeup", "how_to_read", "owner", "sources", "excluded", "next")}
    firms, table = [], []
    for f in F.get("firms") or []:
        f2 = dict(f)
        plans = []
        for p in f.get("plans") or []:
            p2 = dict(p)
            p2["lit"] = lit_fit(p.get("lit_id")) if p.get("lit_id") else None
            plans.append(p2)
            pr = p.get("price") or {}
            ev, po = p.get("eval") or {}, p.get("payouts") or {}
            h2 = ((p2["lit"] or {}).get("H2")) or {}
            h1 = ((p2["lit"] or {}).get("H1")) or {}
            table.append({
                "firm": f.get("name"), "firm_id": f.get("id"), "plan": p.get("name"), "plan_id": p.get("id"), "size": p.get("size"),
                "status": p.get("status"), "bot": f.get("bot_friendly"),
                "price_list": _fv(pr.get("list")), "price_real": pr.get("owner") or pr.get("with_code"),
                "price_kind": "owner" if pr.get("owner") else "code" if pr.get("with_code") else "list", "price_type": pr.get("type"),
                "target": _fv(ev.get("target")), "max_loss": _fv(ev.get("max_loss")), "daily_loss": _fv(ev.get("daily_loss")),
                "eval_consistency": _fv(ev.get("consistency")), "payout_split": _fv(po.get("split")),
                "payout_consistency": _fv(po.get("consistency")), "payout_freq": _fv(po.get("frequency")),
                "payout_cap": _fv(po.get("min_max")), "news": _fv(p.get("news")),
                "live_when": _fv((f.get("live") or {}).get("when")),
                "p10_h1": h1.get("p10"), "p10_h2": h2.get("p10"), "f10_h2": h2.get("f10"), "p60_h2": h2.get("p60"),
                "pass_med_h2": h2.get("pass_med"), "funded_month_h2": h2.get("funded_month"), "net_month_h2": h2.get("net_month_6m"),
                "net_month_h1": h1.get("net_month_6m"), "cost_per_funded": ((p2["lit"] or {}).get("cost_per_funded") or {}).get("H2"),
            })
        f2["plans"] = plans
        firms.append(f2)
    out["firms"], out["table"] = firms, table
    ff = _json(os.path.join(LIT_DOCS, "funded_firms.json"), {}) or {}
    combos = []
    for c in ff.get("combos") or []:
        if c.get("span") != "H2":
            continue
        h1 = next((x for x in ff["combos"] if x.get("plans") == c.get("plans") and x.get("span") == "H1"), {})
        combos.append({"plans": c.get("plans"), "net_month_h2": c.get("net_per_month"), "net_month_h1": h1.get("net_per_month"),
                       "months4_6_h2": c.get("months4_6_per_month"), "neg_6m_h2": c.get("neg_6m"),
                       "all_lost": c.get("all_lost_one_funded"), "p_ge_2000": c.get("p_months4_6_ge_2000")})
    combos.sort(key=lambda c: -(c.get("net_month_h2") or -1e9))
    out["combos"] = combos[:12]
    out["counts"] = {"facts": sum(1 for _ in _iter_facts(F)), **_fact_counts(F)}
    return out


def _iter_facts(o):
    if isinstance(o, dict):
        if "st" in o and "v" in o:
            yield o
        else:
            for v in o.values():
                yield from _iter_facts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _iter_facts(v)


def _fact_counts(F):
    c = {"confirmed": 0, "unconfirmed": 0, "conflict": 0}
    for x in _iter_facts(F.get("firms")):
        c[x.get("st")] = c.get(x.get("st"), 0) + 1
    return c


# ------------------------------------------------------------------------------------------------ eval odds (Monte Carlo)
MC_TARGET, MC_MLL, MC_LOCK, MC_START = 3000.0, 2000.0, 100.0, 50000.0


def _mc_states():
    """Every (profit, room, day, outcome-ahead) state of the stored Monte Carlo eval paths."""
    mc = _json(os.path.join(LAB, "montecarlo.json"), {}) or {}
    rows = []
    for p in mc.get("paths") or []:
        days = [float(x) - MC_START for x in p.get("days") or []]
        res = p.get("result")
        n = len(days)
        peak, floor = 0.0, -MC_MLL
        for i, prof in enumerate(days):
            peak = max(peak, prof)
            floor = min(max(floor, peak - MC_MLL), MC_LOCK)
            if prof >= MC_TARGET or prof <= floor:
                break
            rows.append((prof, prof - floor, i, n - 1 - i, res))     # sessions until the path ended
    return rows, mc


def eval_odds(profit: float, session: int = 1, room: float | None = None, limit: int = 10) -> dict:
    """P(pass / fail) from this state: the Monte Carlo paths' states within a $ band of `profit` (and of `room` when
    given), each counted by what happened after it. Pass / fail within the sessions left to session `limit` (2 weeks) and
    within 20 more, plus eventually (60-session paths)."""
    rows, mc = _memo("mc_states", [os.path.join(LAB, "montecarlo.json")], _mc_states)
    if not rows:
        return {"error": "research/lab/montecarlo.json has no paths"}
    left = max(1, int(limit) - int(session or 1) + 1)
    pick, band = [], 150.0
    while band <= 1200:
        pick = [r for r in rows if abs(r[0] - profit) <= band and (room is None or abs(r[1] - room) <= band * 1.5)]
        if len(pick) >= 60:
            break
        band *= 1.6
    if len(pick) < 15:
        pick = [r for r in rows if abs(r[0] - profit) <= band]
    n = len(pick)
    if not n:
        return {"error": "no Monte Carlo state near this balance", "profit": profit}

    def share(cond):
        return round(100.0 * sum(1 for r in pick if cond(r)) / n, 1)
    out = {"profit": round(profit, 2), "to_go": round(MC_TARGET - profit, 2), "room": room, "session": session, "left": left,
           "n_states": n, "band_usd": round(band),
           "pass_left": share(lambda r: r[4] == "PASS" and r[3] <= left), "fail_left": share(lambda r: r[4] == "FAIL" and r[3] <= left),
           "pass_20": share(lambda r: r[4] == "PASS" and r[3] <= 20), "fail_20": share(lambda r: r[4] == "FAIL" and r[3] <= 20),
           "pass_ever": share(lambda r: r[4] == "PASS"), "fail_ever": share(lambda r: r[4] == "FAIL"),
           "med_sessions_to_pass": stx.median([r[3] for r in pick if r[4] == "PASS"]) if any(r[4] == "PASS" for r in pick) else None,
           "method": ("states of the 300 stored Monte Carlo eval paths (research/lab/montecarlo.json: "
                      f"{mc.get('paths_pool') or '2026 sessions'}; built {mc.get('built')}) within ${round(band)} of this profit"
                      + (" and room" if room is not None else "") + "; outcome counted from that state on"),
           "sizing_note": "paths use the sizing the Monte Carlo was built with (montecarlo.json 'strategy'), not necessarily today's two_week mode",
           "strategy": mc.get("strategy")}
    return out


def odds_grid() -> dict:
    """eval_odds on a grid (phone lookup): profit -1,750 .. +2,750 step 250 x session 1..10."""
    profits = list(range(-1750, 3000, 250))
    rows = []
    for p in profits:
        r = []
        for s in range(1, 11):
            o = eval_odds(p, s)
            r.append([o.get("pass_left"), o.get("fail_left"), o.get("pass_ever")] if not o.get("error") else None)
        rows.append(r)
    return {"profits": profits, "sessions": list(range(1, 11)), "cols": ["pass_by_s10", "fail_by_s10", "pass_ever"], "rows": rows}


# ------------------------------------------------------------------------------------------------ 2. business
def _eval_from_business(b, now=None):
    from engine import accounts
    a = next((x for x in b.get("accounts") or [] if x.get("stage") == "eval"), None)
    if not a:
        return None
    today = _today(now).isoformat()
    ev = accounts.eval_view({"0000-00-00": float(a.get("prior_pnl") or 0)}, a.get("start"), today, now)
    ev["source"] = "research/props/business.json (no PC bot: closed trades unknown)"
    return ev


def payout_calendar(b, ev, now=None) -> dict:
    """Per account: stage, what must happen before the first payout, an estimated date (LIT median sessions, H2), and the
    MFFU rules of eligibility. Funded accounts with funded_start get a countdown to the 2-day cycle."""
    lm_rules = (_json(os.path.join(LIT_DOCS, "mffu_rules.json"), {}) or {}).get("limits") or {}
    today = _today(now)
    rows = []
    for a in b.get("accounts") or []:
        fit = lit_fit(a.get("lit_id")) or {}
        h2 = fit.get("H2") or {}
        lim = lm_rules.get("builder_25k" if "25" in str(a.get("plan")) else "builder_50k") or {}
        r = {"id": a.get("id"), "firm": a.get("firm"), "plan": a.get("plan"), "stage": a.get("stage"), "start": a.get("start"),
             "rules": {"buffer": lim.get("buffer"), "pay_min": lim.get("pay_min"), "pay_max": lim.get("pay_max"), "split": lim.get("split"),
                       "cycle_days": lim.get("cycle_days"), "consistency": lim.get("cons"), "max_payouts": lim.get("max_payouts")}}
        if a.get("stage") == "funded" and a.get("funded_start"):
            r["need"] = (f"balance above ${(lim.get('buffer') or 0) + (lim.get('pay_min') or 0):,.0f} profit and "
                         f"{lim.get('cycle_days') or 2} winning days in the cycle, best day <= 50%")
            fs = dt.date.fromisoformat(a["funded_start"])
            est = _trading_days(max(fs, today), int(h2.get("first_pay_sessions") or 25))[-1]
            r.update(first_payout_est=est.isoformat(), countdown_days=(est - today).days)
        else:
            to_go = (ev or {}).get("to_target") if a.get("stage") == "eval" and ev else (lim.get("target") or 3000)
            sess_pass = int(h2.get("pass_med") or 7)
            start = dt.date.fromisoformat(a["start"]) if a.get("start") else today
            base = max(start, today)
            done = (ev or {}).get("session") or 0 if a.get("stage") == "eval" else 0
            pass_est = _trading_days(base, max(1, sess_pass - (done - 1 if done else 0)))[-1]
            first = _trading_days(pass_est + dt.timedelta(days=1), int(h2.get("first_pay_sessions") or 25))[-1]
            r.update(to_target=to_go, pass_est=pass_est.isoformat(), first_payout_est=first.isoformat(),
                     countdown_days=(first - today).days,
                     need=f"pass the eval (${(to_go or 0):,.0f} to go), then ${(lim.get('buffer') or 0) + (lim.get('pay_min') or 0):,.0f}"
                          f" of funded profit (buffer ${lim.get('buffer') or 0:,.0f} + ${lim.get('pay_min') or 0:,.0f}), 48 h after the first trade")
        r["est_basis"] = (f"LIT H2 medians: pass in {h2.get('pass_med')} sessions, first payout {h2.get('first_pay_sessions')} sessions "
                          "after funding (research/lit/funded_firms.json). An estimate, not a promise.")
        rows.append(r)
    return {"rows": rows}


def live_guide() -> dict:
    F = firms_raw()
    rows = []
    for f in F.get("firms") or []:
        lv = f.get("live") or {}
        rows.append({"firm": f.get("name"), "id": f.get("id"), "bot": f.get("bot_friendly"),
                     **{k: lv.get(k) for k in ("when", "how", "changes", "closes_others", "risk_rules", "reports")}})
    steps = [
        "Sim-funded first: every firm here pays from a simulated account until its risk team moves you.",
        "The trigger is a payout count (MFFU Builder 5, LucidPro 5, Tradeify 3-5, Bulenox 3, FundedNext 15 rewards) or a review.",
        "Expect KYC (ID check) and a contract: a live account is real money at a broker.",
        "Rules change: different split (Tradeify 80/20), daily payouts (MFFU, Lucid), a static floor, a reserve held back.",
        "Some moves close or merge your other accounts (Bulenox merges, FundedNext's old structure disabled all, Tradeify: sources conflict).",
        "Bots: Topstep bans bots on Live; MFFU requires the owner present for live and CME-compliant automation. Never arm live for the bot.",
        "Ask in writing before accepting: what happens to my other accounts, the split, the floor, the contract cap.",
    ]
    return {"rows": rows, "steps": steps}


def pnl_view(b) -> dict:
    ex = [e for e in b.get("expenses") or []]
    po = [p for p in b.get("payouts") or []]
    paid = sum(float(e.get("usd") or 0) for e in ex if not e.get("planned"))
    planned = sum(float(e.get("usd") or 0) for e in ex if e.get("planned"))
    got = sum(float(p.get("usd") or 0) for p in po)
    rec = sum(float(r.get("usd_month") or 0) for r in b.get("recurring") or [])
    months = {}
    for e in ex:
        if e.get("planned"):
            continue
        m = str(e.get("date"))[:7]
        months.setdefault(m, {"fees": 0.0, "payouts": 0.0})["fees"] += float(e.get("usd") or 0)
    for p in po:
        m = str(p.get("date"))[:7]
        months.setdefault(m, {"fees": 0.0, "payouts": 0.0})["payouts"] += float(p.get("usd") or 0)
    mrows = [{"month": m, **{k: round(v, 2) for k, v in d.items()}, "net": round(d["payouts"] - d["fees"], 2)} for m, d in sorted(months.items())]
    return {"fees_paid": round(paid, 2), "fees_planned": round(planned, 2), "payouts": round(got, 2), "net": round(got - paid, 2),
            "recurring_month": rec, "expenses": ex, "payouts_rows": po, "months": mrows, "source": b.get("source")}


def tax_view(b, pnl) -> dict:
    t = b.get("tax") or {}
    pct = float(t.get("set_aside_pct") or 30)
    base = max(0.0, pnl["net"])
    return {"pct": pct, "taxable_est": round(base, 2), "set_aside": round(base * pct / 100, 2), "on_payouts": round(pnl["payouts"] * pct / 100, 2),
            "note": t.get("note") or "Not tax advice.", "label": "Estimate only - not tax advice"}


def goal_view(b, pnl, plan_month=None) -> dict:
    g = b.get("goal") or {}
    target = float(g.get("usd") or 0)
    saved = max(0.0, pnl["net"]) * (1 - float((b.get("tax") or {}).get("set_aside_pct") or 30) / 100)
    rate = plan_month or 0
    keep = float((b.get("withdraw") or {}).get("keep_pct") or 50) / 100
    taxk = 1 - float((b.get("tax") or {}).get("set_aside_pct") or 30) / 100
    per_month_goal = rate * taxk * keep
    left = max(0.0, target - saved)
    months = (left / per_month_goal) if per_month_goal > 0 else None
    dp = float(g.get("down_payment_usd") or 0)
    return {"name": g.get("name"), "target": target, "saved": round(saved, 2), "pct": round(100 * saved / target, 2) if target else None,
            "plan_month": rate, "to_goal_month": round(per_month_goal, 2), "months_to_goal": round(months, 1) if months else None,
            "down_payment": dp, "months_to_down": round(max(0.0, dp - saved) / per_month_goal, 1) if per_month_goal > 0 and dp else None,
            "note": g.get("note"), "basis": "plan $/month (H2, 6 months net of fees) x (1 - tax set-aside) x keep %"}


def floor_gauge(ev) -> dict:
    """Distance to the trailing floor and how many typical / worst LIT stop-outs it holds."""
    if not ev:
        return {"error": "no eval state"}
    room = float(ev.get("room") or 0)
    bt = _json(os.path.join(LAB, "backtest_live.json"), {}) or {}
    risks = []
    for t in bt.get("trades") or []:
        if str(t.get("day") or t.get("date") or "")[:4] == "2026":
            r = t.get("risk_usd") or (abs(float(t.get("r_usd"))) if t.get("r_usd") else None)
            if r:
                risks.append(float(r))
    normal_med = stx.median(risks) if risks else None
    # live sizing is two_week: median $450-660 at risk, about $990 at most (CLAUDE.md, lit-two-week-eval.md)
    typ, worst = 555.0, 990.0
    o = eval_odds(float(ev.get("profit") or 0), int(ev.get("session") or 1), room)
    level = "safe" if room >= 1500 else "watch" if room >= 800 else "danger"
    return {"room": room, "floor": ev.get("floor"), "balance": ev.get("balance"), "typical_risk": round(typ, 2), "worst_risk": round(worst, 2),
            "stopouts_typical": round(room / typ, 1) if typ else None, "stopouts_worst": round(room / worst, 1) if worst else None,
            "ruin_ever": o.get("fail_ever"), "ruin_2wk": o.get("fail_left"), "level": level,
            "sizing_cap": "two_week sizing never risks more than 60% of the room or the $1,000 soft daily loss on one trade",
            "normal_sizing_median": round(normal_med, 2) if normal_med else None,
            "risk_source": "two_week sizing on a fresh eval: median $450-660 at risk, max about $990 (research/writeups/lit-two-week-eval.md); "
                           "normal sizing median from the 2026 replay shown for reference"}


def compliance(ev, acct=None, now=None) -> dict:
    """MFFU Builder 50K rules checked against the current eval / bot state. ok True / False / None (unknown)."""
    lim = ((_json(os.path.join(LIT_DOCS, "mffu_rules.json"), {}) or {}).get("limits") or {}).get("builder_50k") or {}
    acct = acct or {}
    pos = acct.get("position") or {}
    trades = acct.get("trades") or []
    rows = []

    def add(rule, ok, now_txt, limit_txt, note=""):
        rows.append({"rule": rule, "ok": ok, "now": now_txt, "limit": limit_txt, "note": note})
    mm = int(lim.get("max_micros") or 40)
    q = pos.get("qty")
    add("Max contracts", None if q is None else int(q) <= mm, f"{q} micros open" if q is not None else "flat / unknown",
        f"{mm} micros (4 minis)", "the bot caps every order at 40 micros")
    dll = float(lim.get("dll") or 1000)
    used = (ev or {}).get("dll_used")
    add("Daily loss (soft)", None if used is None else used < dll, f"${used:,.0f} used today" if used is not None else "unknown",
        f"${dll:,.0f}: trading paused for the session", "two_week sizing keeps a trade inside it")
    room = (ev or {}).get("room")
    add("Trailing floor (max loss)", None if room is None else room > 0, f"${room:,.0f} of room" if room is not None else "unknown",
        f"${float(lim.get('mll') or 2000):,.0f} EOD trailing, locks at +${float(lim.get('lock') or 100):,.0f}")
    days_traded = len({str(t.get("day")) for t in trades if t.get("day")})
    add("Minimum trading days", days_traded >= 1 if trades else None, f"{days_traded} day(s) with a trade" if trades else "no closed trade seen",
        "1 day (some guides: 2) before the target counts", "after an early target the bot takes a 1-micro trade for the min days")
    last_t = max([int(t.get("exit_t") or t.get("entry_t") or 0) for t in trades] or [0])
    now = now or time.time()
    idle = (now - last_t) / 86400 if last_t else None
    ref = None
    if idle is None and (ev or {}).get("start"):
        idle = (_today(now) - dt.date.fromisoformat(str(ev["start"])[:10])).days
        ref = "since the eval start"
    add("7-day inactivity", None if idle is None else idle < int(lim.get("inactivity_days") or 7),
        (f"{idle:.1f} days since the last trade" if ref is None else f"{idle:.0f} days {ref}") if idle is not None else "unknown",
        "a trade at least every 7 calendar days", "LIT trades 2-4 times a week; a stuck eval (room too small) breaks this")
    add("Flat by 16:10 ET, no overnight", True, "bot flattens at 15:55 ET", "16:10 ET auto-liquidation")
    add("Hedging", True, "one account, one direction", "no long + short on the same underlying (also across accounts)")
    hub = _json(os.path.join(DATA, "news", "hub.json"), {}) or {}
    t1 = [e for e in hub.get("events") or [] if e.get("impact") == "high" and int(e.get("t") or 0) >= now - 3600
          and re.search(r"CPI|Non-Farm|NFP|Employment|FOMC|Federal Funds|Minutes", str(e.get("title")), re.I)][:4]
    add("News (Builder)", True, "Builder: news trading allowed", "Rapid / Rapid EOD funded: flat 2 min before to 2 min after Tier-1",
        ("next Tier-1: " + ", ".join(f"{e.get('label')} {e.get('title')}" for e in t1)) if t1 else "no Tier-1 release in the calendar file")
    known = [r for r in rows if r["ok"] is not None]
    return {"rows": rows, "ok": all(r["ok"] for r in known), "unknown": sum(1 for r in rows if r["ok"] is None),
            "source": "research/lit/mffu_rules.json limits.builder_50k + the bot's account"}


def scaling_plan(F) -> dict:
    nx = F.get("next") or {}
    rows, cum_cash, cum_month = [], 0.0, 0.0
    for s in nx.get("steps") or []:
        cum_cash += float(s.get("cash") or 0)
        cum_month += float(s.get("h2_per_month") or 0)
        fit = lit_fit(s.get("plan")) or {}
        nm = next((f"{f.get('name', '').split(' (')[0]} {p.get('name')}" for f in F.get("firms") or [] for p in f.get("plans") or []
                   if p.get("id") == s.get("plan")), s.get("plan"))
        rows.append({**s, "name": nm, "cum_cash": round(cum_cash, 2), "cum_month_h2": round(cum_month), "p10_h2": (fit.get("H2") or {}).get("p10"),
                     "lost_6m_h2": (fit.get("H2") or {}).get("funded_lost_6m")})
    return {"steps": rows, "combo": nx.get("combo"), "source": nx.get("source"),
            "note": "Each extra account is the same LIT signals: more money, the same bad months. $/month = H2 (Jul-Oct) 6-month net of fees, each plan alone."}


def business_view(acct=None, now=None) -> dict:
    b = business_raw()
    F = firms_raw()
    ev = (acct or {}).get("eval") if acct and not acct.get("error") else None
    src = "the PC bot's account (/api/next/pc/account)" if ev else None
    if not ev:
        ev = _eval_from_business(b, now)
        src = (ev or {}).get("source")
    pnl = pnl_view(b)
    plan_month = 0
    for s in (F.get("next") or {}).get("steps") or []:
        plan_month += float(s.get("h2_per_month") or 0)
    base_plan = 562 + 278                    # funded Builder 50K + 25K, 6-month net H2 (lit-funded-firms / lit-builder-25k)
    odds = eval_odds(float((ev or {}).get("profit") or 0), int((ev or {}).get("session") or 1), (ev or {}).get("room")) if ev else None
    return {"t": int(now or time.time()), "eval": ev, "eval_source": src, "odds": odds,
            "payouts": safe(payout_calendar, b, ev, now), "live": safe(live_guide), "pnl": pnl, "tax": safe(tax_view, b, pnl),
            "goal": safe(goal_view, b, pnl, base_plan), "goal_full_plan": safe(goal_view, b, pnl, plan_month),
            "floor": safe(floor_gauge, ev), "compliance": safe(compliance, ev, acct, now), "scaling": safe(scaling_plan, F),
            "withdraw": {**(b.get("withdraw") or {}), "tax_pct": (b.get("tax") or {}).get("set_aside_pct", 30),
                         "mffu": {"min": 500, "max": 2000, "split": 0.8, "buffer": 2100, "cycle_days": 2, "cons": 0.5},
                         "default_month": base_plan},
            "accounts": b.get("accounts"), "source": b.get("source"), "disclaimer": "Estimates from paper results. Not financial or tax advice."}


def biz_view(acct=None, now=None) -> dict:
    """The business tools (tools/business.py): statement, tax year, payout reminders, eval planner, scaling calendar, Z06
    goal, ROI per account, the rule / code watchers."""
    from tools import business as _biz
    ev = (acct or {}).get("eval") if acct and not acct.get("error") else None
    return _biz.view(now=now, pc_eval=ev)


# ------------------------------------------------------------------------------------------------ 3. market
def week_calendar(now=None) -> dict:
    hub = _json(os.path.join(DATA, "news", "hub.json"), {}) or {}
    today = _today(now)
    mon = today - dt.timedelta(days=today.weekday())
    fri = mon + dt.timedelta(days=4)
    ev = [e for e in hub.get("events") or [] if mon.isoformat() <= str(e.get("date")) <= fri.isoformat()]
    stale = not ev
    if stale:                                            # the file ends before this week: show what it has (last 7 days)
        evs = sorted(hub.get("events") or [], key=lambda e: e.get("t") or 0)
        ev = evs[-12:]
    rows = [{k: e.get(k) for k in ("t", "date", "time_et", "weekday", "title", "kind_label", "impact", "forecast", "previous", "actual",
                                    "blackout", "blackout_start", "blackout_end", "source")} for e in ev]
    return {"week": [mon.isoformat(), fri.isoformat()], "rows": rows, "stale": stale, "built": hub.get("built"),
            "range": hub.get("range"), "source": "data/news/hub.json (tools/news_hub.py)",
            "note": "the news file ends before this week: rebuild with python tools/news_hub.py --out data/news/hub.json" if stale else None}


def _fetch_earnings(day: dt.date, timeout=4) -> list | None:
    """Nasdaq's free earnings calendar for one date (no key). None when blocked / offline."""
    import urllib.request
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        return [row.get("symbol") for row in ((d.get("data") or {}).get("rows") or [])]
    except Exception:
        return None


def earnings_view(now=None, fetch=False) -> dict:
    E = _json(os.path.join(PROPS, "earnings.json"), {}) or {}
    rows = [dict(r) for r in E.get("rows") or []]
    tick = set(E.get("tickers") or [])
    fetched = None
    if fetch:
        today = _today(now)
        found, ok = {}, False
        for d in _trading_days(today, 10):
            syms = _fetch_earnings(d)
            if syms is None:
                break
            ok = True
            for s in syms:
                if s in tick or (s == "GOOG" and "GOOGL" in tick):
                    found[("GOOGL" if s == "GOOG" else s)] = d.isoformat()
        if ok:
            fetched = "api.nasdaq.com earnings calendar"
            for r in rows:
                if r["sym"] in found:
                    r.update(date=found[r["sym"]], st="confirmed (calendar)", src=fetched)
    today = _today(now)
    mon = today - dt.timedelta(days=today.weekday())
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        r["days"] = (d - today).days
        r["this_week"] = mon <= d <= mon + dt.timedelta(days=4)
        r["lit_session"] = (d + dt.timedelta(days=1 if d.weekday() < 4 else 3)).isoformat() if r.get("time") == "AMC" else r["date"]
    rows.sort(key=lambda r: r["date"])
    return {"rows": rows, "updated": E.get("updated"), "how": E.get("how"), "fetched": fetched, "source": "research/props/earnings.json"}


def holidays_view(now=None, days=380) -> dict:
    from engine import lit_live, sizing
    today = _today(now)
    out = []
    shut = set()
    for y in (today.year, today.year + 1):
        shut |= sizing._full_closures(y)
    d = today
    while (d - today).days <= days:
        if d.weekday() < 5:
            if d in shut:
                out.append({"date": d.isoformat(), "kind": "closed", "text": "CME equity futures closed (no session)", "eval_session": False})
            else:
                ec = lit_live.early_close(d.isoformat())
                if ec is not None:
                    hh = f"{ec // 60:02d}:{ec % 60:02d}"
                    out.append({"date": d.isoformat(), "kind": "early", "halt_et": hh, "eval_session": True,
                                "text": f"early halt {hh} ET: the bot stops entries 15 min and flattens 5 min before"})
        d += dt.timedelta(days=1)
    for r in out:
        r["days"] = (dt.date.fromisoformat(r["date"]) - today).days
        r["weekday"] = dt.date.fromisoformat(r["date"]).strftime("%a")
    return {"rows": out, "mffu": "MFFU does not auto-flatten on holiday early closes: you (the bot) must be flat before the halt",
            "source": "engine/lit_live.early_close + engine/sizing._full_closures (CME calendar rules)"}


def _third_friday(y, m):
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def roll_view(now=None) -> dict:
    today = _today(now)
    R = _json(os.path.join(DATA, "NQ_rolls.json"), {}) or {}
    offs = []
    for r in R.get("rolls") or []:
        try:
            offs.append((dt.date.fromisoformat(r["ltd"]) - dt.date.fromisoformat(r["switch_day"])).days)
        except Exception:
            pass
    sw_off = int(stx.median(offs)) if offs else 3
    codes = {3: "H", 6: "M", 9: "U", 12: "Z"}
    nxt = []
    y = today.year
    for yy in (y, y + 1):
        for m in (3, 6, 9, 12):
            ltd = _third_friday(yy, m)
            if ltd >= today:
                nxt.append((ltd, m, yy))
    ltd, m, yy = nxt[0]
    roll = ltd - dt.timedelta(days=8)
    switch = ltd - dt.timedelta(days=sw_off)
    m2, y2 = (m + 3, yy) if m < 12 else (3, yy + 1)
    cur = f"NQ{codes[m]}{str(yy)[2:]}"
    new = f"NQ{codes[m2]}{str(y2)[2:]}"
    last = (R.get("rolls") or [{}])[-1]
    return {"current": cur, "next": new, "mnq": f"MNQ {m2:02d}-{str(y2)[2:]}", "expiry": ltd.isoformat(), "roll_date": roll.isoformat(),
            "tv_switch": switch.isoformat(), "days_to_roll": (roll - today).days, "days_to_expiry": (ltd - today).days,
            "days_to_switch": (switch - today).days, "last_roll": {k: last.get(k) for k in ("from", "to", "switch_day", "gap", "check")},
            "checklist": ["Before the roll: switch the NinjaTrader chart / LE_BarFeed to the new MNQ contract with 30 days loaded (overlap)",
                          "The merge (pcbars.merge_basis) back-adjusts older bars by the roll gap: check the bot log for the offset",
                          "Refresh the TradingView NQ1! export after the switch",
                          "No trade on the roll day if the feed shows FEED STALE"],
            "rule": f"CME roll = 8 days before the 3rd-Friday expiry (Thursday); TradingView NQ1! switched {sw_off} days before expiry in the stored rolls"}


def _vix_series(name):
    path = os.path.join(DATA, f"{name}_1d.csv")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                v = float(r.get("close") or 0)
            except ValueError:
                continue
            if v > 0:
                out.append((r["date"], v))
    return out


def vix_view(price=None, brief=None) -> dict:
    def one(name):
        s = _vix_series(name)
        if not s:
            return None
        d, v = s[-1]
        yr = [x[1] for x in s[-252:]]
        pct = round(100 * sum(1 for x in yr if x <= v) / len(yr), 1)
        return {"date": d, "close": round(v, 2), "pct_1y": pct, "chg_5d": round(v - s[-6][1], 2) if len(s) > 6 else None,
                "spark": [round(x[1], 2) for x in s[-60:]]}
    vx, vn = one("VIX"), one("VXN")
    if price is None:
        price = _last_close()
    v = (vx or {}).get("close")
    reg = None if v is None else ("calm" if v < 15 else "normal" if v < 20 else "elevated" if v < 30 else "stress")
    move = round(v / 100 / math.sqrt(252) * price, 1) if v and price else None
    band = ((brief or {}).get("vix") or {}) if brief else {}
    typ = _typical_stop()
    return {"vix": vx, "vxn": vn, "regime": reg, "price": price, "move_pts": band.get("move") or move,
            "open18": band.get("open18"), "band": [band.get("low"), band.get("high")] if band.get("low") else None,
            "band_text": band.get("text"), "typical_stop": typ, "r_room": round((band.get("move") or move) / typ, 2) if (move and typ) else None,
            "rule": "LIT target = 18:00 open +/- 1 VIX one-day move (VIX / 100 / sqrt(252) x price), at least 1.5R, banked at 8R",
            "regimes": [["calm", "< 15"], ["normal", "15-20"], ["elevated", "20-30"], ["stress", ">= 30"]],
            "stale_days": (_today() - dt.date.fromisoformat(vx["date"])).days if vx else None,
            "source": "data/VIX_1d.csv, data/VXN_1d.csv (CBOE)"}


def _typical_stop():
    try:
        from engine import lit_brief
        return float(lit_brief.typical_stop())
    except Exception:
        return 46.0


def _last_close():
    path = os.path.join(DATA, "NQ_5m.csv")
    try:
        with open(path, "rb") as fh:
            fh.seek(-400, 2)
            last = fh.read().decode().strip().splitlines()[-1].split(",")
        return float(last[4])
    except Exception:
        return None


def _brief_from_csv():
    """lit_brief morning block on data/NQ_5m.csv (the phone export / no PC bot)."""
    from engine import botctl, lit_brief
    from types import SimpleNamespace
    df = botctl._plan_bars(SimpleNamespace(bars_tail=[]))
    if df is None or not len(df):
        return None
    lm = _json(os.path.join(ROOT, "live_model.json"), {}) or {}
    last = int(df["time"].max())
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        b = lit_brief.build(df, last + 300, params=lm.get("lit"), live={"state": {}}, lit_sizing=lm.get("lit_sizing"),
                            model_params=lm.get("params"))
    return b


def overnight_view(brief) -> dict:
    mo = (brief or {}).get("morning") or {}
    if not mo:
        return {"error": "no LIT brief (bars missing)"}
    bx = mo.get("boxes") or []
    return {"day": mo.get("day"), "built": mo.get("built"), "price": mo.get("price"), "boxes": bx, "overnight": mo.get("overnight"),
            "monday": mo.get("monday"), "swept": [{k: r.get(k) for k in ("label", "side", "price", "taken_t", "depth_atr", "depth_pts")}
                                                  for r in mo.get("levels") or [] if r.get("taken")],
            "source": "engine/lit_brief (the same LIT map as the morning brief)"}


def levels_view(brief) -> dict:
    mo = (brief or {}).get("morning") or {}
    if not mo:
        return {"error": "no LIT brief (bars missing)"}
    price = mo.get("price")
    keep = ("pd", "pw", "pm", "gap")
    rows = []
    for r in mo.get("levels") or []:
        kind = str(r.get("kind"))
        if kind not in keep and not str(r.get("name", "")).startswith(("pd", "pw", "pm", "nwog", "ndog")):
            continue
        rows.append({"label": r.get("label"), "name": r.get("name"), "side": r.get("side"), "price": r.get("price"), "kind": kind,
                     "taken": r.get("taken"), "dist": round(float(r["price"]) - float(price), 2) if price else None})
    rows.sort(key=lambda r: -(r["price"] or 0))
    all_rows = [{"label": r.get("label"), "side": r.get("side"), "price": r.get("price"), "kind": r.get("kind"), "taken": r.get("taken"),
                 "dist": round(float(r["price"]) - float(price), 2) if price else None} for r in mo.get("levels") or []]
    all_rows.sort(key=lambda r: -(r["price"] or 0))
    return {"day": mo.get("day"), "price": price, "rows": rows, "all": all_rows,
            "note": "PWH/PWL previous week, PMH/PML previous month, PDH/PDL previous day, NWOG/NDOG new week / day opening gap. "
                    "Only levels still untaken when the day began are LIT liquidity."}


def market_view(brief=None, now=None, fetch=False) -> dict:
    if brief is None:
        brief = safe(_brief_from_csv)
        if isinstance(brief, dict) and brief.get("error"):
            brief = None
    price = ((brief or {}).get("morning") or {}).get("price")
    return {"t": int(now or time.time()), "calendar": safe(week_calendar, now), "earnings": safe(earnings_view, now, fetch),
            "holidays": safe(holidays_view, now), "roll": safe(roll_view, now),
            "vix": safe(vix_view, price, (brief or {}).get("morning")), "overnight": safe(overnight_view, brief),
            "levels": safe(levels_view, brief)}


# ------------------------------------------------------------------------------------------------ 4. learn
def _git(*args, timeout=6):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def versions_view() -> dict:
    def build():
        rows = []
        out = _git("log", "--format=%h|%ad|%s", "--date=short", "-n", "40", "--", "STRATEGY.md", "live_model.json")
        for line in (out or "").splitlines():
            h, d, s = (line.split("|", 2) + ["", ""])[:3]
            if "WIP checkpoint" in s:
                continue
            rows.append({"sha": h, "date": d, "title": s[:220], "strategy": "LIT" if d >= "2026-10-18" else "Liquidity Engine"})
        txt = ""
        try:
            with open(os.path.join(ROOT, "STRATEGY.md"), encoding="utf-8") as fh:
                txt = fh.read()
        except OSError:
            pass
        locks = [re.sub(r"\*\*", "", m.group(0))[:400] for m in re.finditer(r"^\*\*Version:\*\*.*$", txt, re.M)]
        lm = _json(os.path.join(ROOT, "live_model.json"), {}) or {}
        cur = {k: lm.get(k) for k in ("model", "chosen", "locked", "locked_at", "note") if lm.get(k) is not None}
        switches = {k: (lm.get("lit") or {}).get(k) for k in ("t_check", "scale_in", "be_off") if (lm.get("lit") or {}).get(k) is not None}
        return {"rows": rows, "locks": locks, "current": cur, "switches_on": switches,
                "source": "git log of STRATEGY.md + live_model.json" if rows else "STRATEGY.md (git log unavailable)"}
    return _memo("versions", [os.path.join(ROOT, "STRATEGY.md"), os.path.join(ROOT, "live_model.json")], build, ttl=600)


def _front(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        text = text[m.end():]
    return fm, text


def verdict_of(status: str) -> str:
    s = (status or "").lower()
    if s.startswith("adopted") or s.startswith("live"):
        return "adopted"
    if s.startswith("rejected"):
        return "rejected"
    if "adopt-candidate" in s or "adopt candidate" in s or "candidate" in s:
        return "candidate"
    if "rejected" in s[:40]:
        return "rejected"
    if s.startswith("promising"):
        return "promising"
    if s.startswith("finding"):
        return "finding"
    return "info"


def library_view() -> dict:
    def build():
        rows = []
        for p in [q for q in sorted(glob.glob(os.path.join(WRITEUPS, "*.md"))) if os.path.basename(q).upper() != "INDEX.MD"]:   # INDEX: tools/writeups_index.py
            try:
                with open(p, encoding="utf-8") as fh:
                    fm, body = _front(fh.read())
            except OSError:
                continue
            name = os.path.basename(p)[:-3]
            rows.append({"id": name, "title": fm.get("title") or name, "family": fm.get("family") or "other", "date": fm.get("date"),
                         "status": (fm.get("status") or "")[:200], "verdict": verdict_of(fm.get("status")),
                         "summary": (fm.get("summary") or "")[:900], "lit": name.startswith("lit") or "LIT" in (fm.get("title") or ""),
                         "words": len(body.split())})
        rows.sort(key=lambda r: (r.get("date") or "", r["id"]), reverse=True)
        counts = {}
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        return {"rows": rows, "counts": counts, "source": "research/writeups/*.md front matter", "open": "/api/next/writeups (full text on the Write-ups page)"}
    deps = sorted(glob.glob(os.path.join(WRITEUPS, "*.md")))
    return _memo("library", deps or [WRITEUPS], build)


def glossary_view() -> dict:
    p = os.path.join(WRITEUPS, "lit-playbook.md")
    try:
        with open(p, encoding="utf-8") as fh:
            _fm, body = _front(fh.read())
    except OSError:
        return {"error": "research/writeups/lit-playbook.md missing"}

    def section(title):
        m = re.search(r"^## " + re.escape(title) + r".*?$(.*?)(?=^## |\Z)", body, re.M | re.S)
        return m.group(1) if m else ""
    gl = []
    for line in section("Glossary").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] and not cells[0].startswith("-") and cells[0] != "Term":
            gl.append({"term": cells[0], "meaning": cells[1]})
    steps = []
    for m in re.finditer(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(.*?)(?=^\s*\d+\.\s+\*\*|^\S|\Z)", section("The model as the bot trades it"), re.M | re.S):
        steps.append({"n": int(m.group(1)), "title": m.group(2).strip().rstrip(":").rstrip("."), "text": re.sub(r"\s+", " ", m.group(3)).replace("**", "").replace("`", "").strip()})
    skip = [re.sub(r"\s+", " ", x).strip() for x in re.findall(r"^- (.+?)(?=^- |\Z)", section("Session clocks"), re.M | re.S)]
    one = [re.sub(r"\s+", " ", re.sub(r"\*\*", "", x)).strip() for x in re.findall(r"^- (.+?)(?=^- |\Z)", section("In one minute"), re.M | re.S)]
    return {"glossary": gl, "steps": steps, "clocks": skip, "one_minute": one, "source": "research/writeups/lit-playbook.md"}


def gallery_view(n=24) -> dict:
    gdir = os.path.join(LAB, "gallery")
    imgs = []
    if os.path.isdir(gdir):
        for p in sorted(glob.glob(os.path.join(gdir, "**", "*.png"), recursive=True))[-n:][::-1]:
            imgs.append({"name": os.path.relpath(p, gdir).replace("\\", "/"), "url": "/api/next/hub/gallery/" + os.path.relpath(p, gdir).replace("\\", "/")})

    def build():
        R = _json(os.path.join(LAB, "replays.json"), {}) or {}
        sc = float(R.get("scale") or 4)
        out = []
        for k in sorted(R.get("charts") or {})[::-1][:n]:
            c = R["charts"][k]
            b5 = c.get("b5") or {}
            if not b5.get("dt"):
                continue
            t0, s, p0 = int(b5["t0"]), int(b5["s"]), float(b5["p0"])
            et = int((c.get("entry") or {}).get("t") or 0)
            xt = int((c.get("exit") or {}).get("t") or et)
            idx = [i for i, d in enumerate(b5["dt"]) if et - 4 * 3600 <= t0 + d * s <= xt + 1800] or list(range(len(b5["dt"])))
            idx = idx[-90:]
            px = lambda a, i: round((p0 + a[i]) / sc, 2)          # noqa: E731
            out.append({"id": k, "day": c.get("day"), "side": c.get("side"), "pnl": c.get("pnl"), "r": c.get("r"), "exit": c.get("exit_kind"),
                        "target_label": c.get("target_label"), "risk_pts": c.get("risk_pts"),
                        "entry": (c.get("entry") or {}).get("px"), "stop": c.get("stop"), "target": c.get("target"),
                        "exit_px": (c.get("exit") or {}).get("px"), "entry_t": et, "exit_t": xt,
                        "sweep": (c.get("sweep") or {}).get("ext_px"), "levels": [{"label": z.get("label"), "px": z.get("px")} for z in c.get("levels") or []][:3],
                        "bars": [[t0 + b5["dt"][i] * s, px(b5["o"], i), px(b5["h"], i), px(b5["l"], i), px(b5["c"], i)] for i in idx]})
        return out
    charts = _memo("gallery", [os.path.join(LAB, "replays.json")], build)
    return {"images": imgs, "charts": charts, "source": "research/lab/gallery/*.png" if imgs else "research/lab/replays.json (SVG drawn in the page)"}


def _cloud_state():
    """The cloud monitor's state.json (dashboard branch), read with git, cached 10 min. None when unavailable."""
    def build():
        for ref in ("origin/dashboard", "dashboard"):
            out = _git("show", f"{ref}:state.json", timeout=8)
            if out:
                try:
                    return json.loads(out)
                except ValueError:
                    return None
        return None
    return _memo("cloud_state", [], build, ttl=600)


def upgrades_view() -> dict:
    """With vs without the 3 upgrades (15-minute check, scale-in after BE, BE + costs): the backtest numbers from the
    Bot page's switches view, and the cloud's paper ledgers once the 'lit_base' ledger (the live rules without the
    upgrades) exists in its state.json."""
    out = {"live": None, "backtest": None}
    try:
        from engine import botctl
        sw = botctl.switches_view()
        out["backtest"] = {k: sw.get(k) for k in ("base", "switches", "combos", "how")}
    except Exception as e:                                   # noqa: BLE001
        out["backtest"] = {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}
    st = _cloud_state()
    base = (st or {}).get("lit_base") if isinstance(st, dict) else None
    if base:
        def summ(led):
            rows = [t for t in (led or []) if isinstance(t, dict) and t.get("pnl") is not None]
            pn = [float(t["pnl"]) for t in rows]
            return {"n": len(pn), "net": round(sum(pn), 2), "wins": sum(1 for x in pn if x > 0),
                    "since": min((str(t.get("day") or "") for t in rows), default=None)}
        main = (st.get("ledger") or st.get("paper") or [])
        out["live"] = {"with": summ(main if isinstance(main, list) else main.get("trades")),
                       "without": summ(base if isinstance(base, list) else base.get("trades") or base.get("ledger")),
                       "source": "cloud state.json: paper ledger (with upgrades) vs lit_base (without)"}
    else:
        out["live"] = {"placeholder": True, "text": "Waiting for data: the cloud monitor will keep a second paper ledger "
                       "('lit_base', the live rules without the 3 upgrades). Once its first trades close, this card shows both side by side.",
                       "source": "cloud state.json key lit_base (not there yet)"}
    return out


def learn_view() -> dict:
    return {"versions": safe(versions_view), "library": safe(library_view), "learn": safe(glossary_view), "gallery": safe(gallery_view),
            "upgrades": safe(upgrades_view)}


# ------------------------------------------------------------------------------------------------ 5. system
_SUP = re.compile(r"\[supervisor\]\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.*)")


def _sup_lines(days=21):
    """[supervisor] lines of logs/server-YYYYMMDD.log (scripts/run_bot.ps1), newest files last."""
    rows = []
    for p in sorted(glob.glob(os.path.join(LOGS, "server-*.log")))[-days:]:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = _SUP.search(line)
                    if m:
                        try:
                            t = int(dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET).timestamp())
                        except ValueError:
                            continue
                        rows.append((t, m.group(2).strip()[:200]))
        except OSError:
            continue
    return rows


_DISC = [("kill", r"\bkill"), ("stop", r"\bstop(ped)?\b|stop file|stop request"), ("start", r"\bstart(ed|ing)?\b|autostart|resum"),
         ("restart", r"restart"), ("update", r"updat"), ("crash", r"exited with code|error|traceback")]


def _clean(txt):
    try:
        from engine import accounts
        return accounts.clean_text(txt, 200)
    except Exception:
        return str(txt)[:200]


def discipline_view(bot=None, now=None) -> dict:
    rows = []
    for r in list(getattr(bot, "log", None) or [])[:600]:
        txt = str(r.get("text") or "")
        typ = r.get("type")
        kind = None
        if typ == "kill":
            kind = "kill"
        else:
            for k, pat in _DISC[:4]:
                if re.search(pat, txt, re.I) and typ in ("system", "warn", "kill", "risk", None):
                    kind = k
                    break
        if kind:
            rows.append({"t": int(r.get("t") or 0), "kind": kind, "src": "bot log", "text": _clean(txt), "manual": bool(re.search(r"dashboard|manual|button|owner|api", txt, re.I))})
    for t, txt in _sup_lines():
        for k, pat in _DISC:
            if re.search(pat, txt, re.I):
                rows.append({"t": t, "kind": k, "src": "supervisor log", "text": _clean(txt), "manual": "stop file" in txt or "stop request" in txt})
                break
    rows.sort(key=lambda r: -r["t"])
    counts = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return {"rows": rows[:80], "counts": counts, "manual": sum(1 for r in rows if r["manual"]),
            "source": "the bot's log (this server) + logs/server-*.log [supervisor] lines",
            "empty": None if rows else "No kills, stops or restarts recorded yet (the PC writes logs\\server-YYYYMMDD.log while scripts\\run_bot.ps1 runs)."}


def uptime_view(bot=None, now=None) -> dict:
    now = int(now or time.time())
    lines = _sup_lines(30)
    spans, cur = [], None
    for t, txt in lines:
        if "starting server.py" in txt:
            cur = t
        m = re.search(r"exited.*?after (\d+) s", txt)
        if m:
            spans.append((t - int(m.group(1)), t))
            cur = None
        elif ("exited" in txt or "supervisor stopped" in txt) and cur:
            spans.append((cur, t))
            cur = None
    server_s = None
    hb = None
    try:
        from engine import accounts
        h = accounts.pc_health(bot, now) if bot is not None else {}
        server_s = (h.get("uptime") or {}).get("server_s")
        hb = h.get("heartbeat") if isinstance(h, dict) else None
    except Exception:
        pass
    if cur:
        spans.append((cur, now))
    elif server_s:
        spans.append((now - int(server_s), now))
    days = []
    for i in range(13, -1, -1):
        d = _today(now) - dt.timedelta(days=i)
        a = int(dt.datetime.combine(d, dt.time(0, 0), ET).timestamp())
        z = a + 86400
        on = sum(max(0, min(z, e) - max(a, s)) for s, e in spans)
        days.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "up_h": round(on / 3600, 1), "pct": round(100 * on / 86400, 1)})
    restarts = sum(1 for _t, txt in lines if "restarting in" in txt or "updated itself" in txt)
    # session coverage: was the server up from 01:55 to 16:00 ET (95 of 120 LIT trades enter 02:00-08:00)?
    cov = []
    for d in days:
        dd = dt.date.fromisoformat(d["date"])
        if dd.weekday() >= 5:
            continue
        a = int(dt.datetime.combine(dd, dt.time(1, 55), ET).timestamp())
        z = int(dt.datetime.combine(dd, dt.time(16, 0), ET).timestamp())
        on = sum(max(0, min(z, e) - max(a, s)) for s, e in spans)
        cov.append({"date": d["date"], "pct": round(100 * on / (z - a), 1)})
    return {"server_s": server_s, "days": days, "session_cover": cov, "restarts_30d": restarts, "spans": len(spans), "heartbeat": hb,
            "source": "logs/server-*.log [supervisor] lines + this server's uptime",
            "need": "NinjaTrader and the PC must run from ~01:55 ET: 95 of 120 LIT trades enter 02:00-08:00",
            "empty": None if spans else "No supervisor log yet: start the bot with scripts\\run_bot.ps1 to record uptime."}


def _csv_cover(path, step, sessions=30):
    """Coverage of a bar file: rows, first / last bar, and per recent session (18:00-17:00 ET) bars vs expected."""
    import pandas as pd
    if not os.path.exists(path):
        return {"file": os.path.relpath(path, ROOT), "missing": True}

    def build():
        t = pd.read_csv(path, usecols=["time"])["time"].astype("int64").values
        if not len(t):
            return {"file": os.path.relpath(path, ROOT), "rows": 0}
        et = pd.to_datetime(t, unit="s", utc=True).tz_convert(ET)
        tday = (et + pd.Timedelta(hours=6)).date               # 18:00 ET belongs to the next trading day
        s = pd.Series(1, index=pd.Index(tday)).groupby(level=0).sum()
        s = s[[pd.Timestamp(d).weekday() < 5 for d in s.index]]
        recent = s.iloc[-sessions:]
        exp = int(round(23 * 3600 / step))
        rows = [{"day": str(d), "bars": int(n), "expected": exp, "pct": round(100 * n / exp, 1)} for d, n in recent.items()]
        # gaps inside a session: not the 17:00-18:00 ET halt, not the weekend (Friday 17:00 -> Sunday 18:00)
        dif = pd.Series(t).diff()
        start_et = pd.to_datetime(pd.Series(t).shift(1), unit="s", utc=True).dt.tz_convert(ET)
        smod = start_et.dt.hour * 60 + start_et.dt.minute
        halt = (smod >= 16 * 60 + 50) & (smod <= 17 * 60) & (dif <= 75 * 60 + step)
        wknd = dif >= 40 * 3600
        real = (dif > step * 3) & ~halt & ~wknd
        gaps = int(real.iloc[1:].sum())
        big = [{"from": int(t[i - 1]), "to": int(t[i]), "min": round((t[i] - t[i - 1]) / 60)} for i in dif[real].index[-8:]]
        return {"file": os.path.relpath(path, ROOT).replace("\\", "/"), "rows": int(len(t)), "first": int(t[0]), "last": int(t[-1]),
                "age_h": round((time.time() - t[-1]) / 3600, 1), "sessions": rows,
                "short_sessions": sum(1 for r in rows if r["pct"] < 95), "gaps_over_3_bars": gaps, "gap_rule": "gaps longer than 3 bars inside a session (daily halt and weekends excluded; holidays and data outages count)", "intraday_gaps": big[::-1]}
    return _memo(("cover", path), [path], build)


def dataq_view() -> dict:
    out = {"files": [safe(_csv_cover, os.path.join(DATA, "NQ_5m.csv"), 300), safe(_csv_cover, os.path.join(DATA, "NQ_1m.csv"), 60)]}
    nt = os.path.join(DATA, "nt_bars")
    files = sorted(glob.glob(os.path.join(nt, "*"))) if os.path.isdir(nt) else []
    out["nt_archive"] = {"dir": "data/nt_bars", "files": len(files), "newest": os.path.basename(files[-1]) if files else None,
                         "note": None if files else "no NinjaTrader bar archive on this machine (the PC writes it while the bot runs)"}
    vix = _vix_series("VIX")
    out["vix_last"] = vix[-1][0] if vix else None
    hub = _json(os.path.join(DATA, "news", "hub.json"), {}) or {}
    out["news_built"] = hub.get("built")
    out["checks"] = [
        {"name": "1m bars (LIT entries need them)", "ok": bool(out["files"][1].get("rows")) if isinstance(out["files"][1], dict) else False},
        {"name": "VIX close within 4 days (no VIX = no target = no trade)", "ok": bool(vix) and (_today() - dt.date.fromisoformat(vix[-1][0])).days <= 4},
        {"name": "news calendar covers today", "ok": str((hub.get("range") or {}).get("to") or "") >= _today().isoformat()},
    ]
    out["source"] = "data/NQ_5m.csv, data/NQ_1m.csv (TradingView CME exports), data/nt_bars (NinjaTrader archive), VIX, news hub"
    return out


def system_view(bot=None, now=None) -> dict:
    return {"t": int(now or time.time()), "discipline": safe(discipline_view, bot, now), "uptime": safe(uptime_view, bot, now),
            "dataq": safe(dataq_view)}


# ------------------------------------------------------------------------------------------------ phone export
def export(fetch=True) -> dict:
    """Everything the phone needs (no PC bot): firms, business (eval from business.json), market, learn (no images),
    system (data quality only), the eval-odds grid."""
    fv = firms_view()
    fv = {k: v for k, v in fv.items() if k != "sources"} | {"sources": fv.get("sources")}
    lr = learn_view()
    g = lr.get("gallery") or {}
    if isinstance(g, dict):
        g = {**g, "charts": (g.get("charts") or [])[:12], "images": []}
    lr["gallery"] = g
    return {"built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "version": VERSION, "firms": fv,
            "business": business_view(), "market": market_view(fetch=fetch), "learn": lr,
            "system": {"dataq": safe(dataq_view)}, "odds_grid": safe(odds_grid), "biz": safe(biz_view),
            "note": "PC dashboard hub data (tools/hub_data.py). Read-only, paper only."}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(PROPS, "hub.json"))
    ap.add_argument("--no-fetch", action="store_true", help="skip the free earnings-calendar fetch")
    a = ap.parse_args(argv)
    d = export(fetch=not a.no_fetch)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(d, fh, separators=(",", ":"), default=str)
    print(f"wrote {a.out} ({os.path.getsize(a.out) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
