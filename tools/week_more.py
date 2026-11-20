"""ZEUS THIS WEEK, round 2 (day-brief 2026-11-20): the extra blocks of tools/weekly_review.py -> business/week.json.

  feed_rows(lite, plan_accounts)  the week's trades from the PC's public status post (ntfy "at": per account
                                  [entry_t, exit_t, dir, qty, entry, stop, target, exit, $, R]) as weekly_review ledger rows,
                                  so the CLOUD can build the review too (the PC cannot push; before this the site's week.json
                                  only ever had what a Claude session committed)
  twins(...)                      each bot vs its backtest twin on the same bars: Zlarior = engine/lit.run_x with the live
                                  params (tools/lit_more_money.gap's call), ATLAS = engine/second.run on the 3 live members
                                  (tools/trade_watch.atlas_twin's call); matched / missed / extra + R live vs twin
  best_worst(...)                 the week's best and worst live trade, each with ONE plain lesson (tools/win_loss_anatomy
                                  cause codes: news / wick / turned / never; a winner: target / managed)
  kalshi(...)                     K8's paper (or live) week: from the PC's own ledger when it is here, else the public card
  calendar(...)                   next week day by day: CME open / early close / closed (engine/cme_calendar, the bots' own
                                  calendar) + Tier-1 / Tier-2 US news
  weekend(...)                    "what to do this weekend": the open Decide cards ranked by $ a month
                                  (business/fleet_plan.json when present, else each card's impact_usd)

Deterministic: same files + same now = same blocks. Read only: never trades, arms, sizes or routes anything.
Test: python -X utf8 -m tests.test_week_more
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
MATCH_S = 15 * 60                      # a live entry within 15 min of the twin's, same side = the same trade
LIT_ACCT = "zlarior"                   # the twin's account: Zlarior's main 50K / ATLAS's funded 25K
ATLAS_ACCT = "atlas"
ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
ATLAS_SHORT = {"ema_lon_vix": "EMA", "macd_sweep": "MACD", "sr_nyreclaim": "S/R"}


def _f(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _hm(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M")


def usd(v, sign=False) -> str:
    x = _f(v)
    if x is None:
        return "-"
    s = f"${abs(x):,.0f}"
    return ("-" if x < 0 else "+" if sign and x > 0 else "") + s


def _usd2(v) -> str:
    x = _f(v)
    return "-" if x is None else f"${x:,.2f}".replace(".00", "")


def trading_day(ts) -> str:
    return (dt.datetime.fromtimestamp(int(ts), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ trades from the PC's post
def feed_rows(lite, plan_accounts) -> list:
    """weekly_review ledger rows (side exit, mode live) from the status post's "at" block. Open trades are left out."""
    from engine import board_events as B
    out = []
    for a in _d(_d(lite).get("at")).get("a") or []:
        a = _d(a)
        pid = str(a.get("id") or "")
        if not pid:
            continue
        key = B.plan_key(plan_accounts, pid, "") or B.ALIASES.get(pid.lower()) or pid
        bot = "atlas" if key == "atlas" or pid.startswith("atlas") else "zlarior"
        for t in a.get("tr") or []:
            if not isinstance(t, list) or len(t) < 10 or t[1] is None or _f(t[8]) is None:
                continue
            out.append({"side": "exit", "mode": "live", "acct": key, "bot": bot, "src": "feed", "entry_t": int(t[0]),
                        "exit_t": int(t[1]), "dir": int(t[2] or 0), "qty": t[3], "entry": _f(t[4]), "stop": _f(t[5]),
                        "target": _f(t[6]), "reason": str(t[7] or ""), "pnl": round(float(t[8]), 2), "r": _f(t[9])})
    return out


# ------------------------------------------------------------------------------------------------ twins
def _lit_twin(days) -> list:
    from engine import lit
    from tools import lit_final as F
    from tools import lit_more_money as L
    M, C = L.cands()
    have = [str(d) for d, s, e in M.days]
    first = min(days)
    run_days = [d for d in have if d <= max(days)][-15:]           # 3 weeks back: the weekly stop / Monday rule see their days
    T = lit.run_x(M, C, L.LIVE, [d for d in run_days], B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return [{"day": str(t["day"]), "entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "exit": str(t["exit"]),
             "r": round(float(t["r"]), 2), "who": "LIT"} for t in T if str(t["day"]) >= first and str(t["day"]) in days]


def _atlas_twin(days) -> list:
    from engine import fill_audit as fa
    from engine import second as S
    d5, d1 = fa.load_bars()
    cfg = S.load_cfg()
    sub = {**cfg, "strategies": {k: {**cfg["strategies"][k], "route": True} for k in ATLAS_KEYS if k in (cfg.get("strategies") or {})}}
    end = fa._ts(max(days), 16, 5)
    a5 = d5[d5["time"] < end]
    a1 = d1[d1["time"] < end] if d1 is not None and len(d1) else None
    r = S.run(a5, one_min=a1, now=end + 300, cfg=sub, lit=[])
    out = []
    for k, st in (r.get("strategies") or {}).items():
        for t in st.get("trades") or []:
            if t.get("day") in days and t.get("entry_t") is not None:
                out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "exit": str(t.get("exit_kind") or ""),
                            "r": round(float(t.get("r") or 0.0), 2), "who": ATLAS_SHORT.get(k, k)})
    return sorted(out, key=lambda x: x["entry_t"])


def _bars_to() -> str | None:
    try:
        with open(os.path.join(ROOT, "data", "NQ_5m.csv"), "rb") as fh:
            fh.seek(-200, 2)
            last = fh.read().decode().strip().splitlines()[-1]
        return trading_day(int(float(last.split(",")[0])))
    except (OSError, ValueError, IndexError):
        return None


def compare(name: str, twin: list, live: list, live_from_t=None) -> dict:
    """Pair the twin's trades with the live ones (same side, entry within 15 min)."""
    used, rows = set(), []
    for tw in twin:
        m = next((i for i, lv in enumerate(live) if i not in used and lv.get("dir") == tw["dir"]
                  and lv.get("entry_t") is not None and abs(int(lv["entry_t"]) - tw["entry_t"]) <= MATCH_S), None)
        row = {"day": tw["day"], "time": _hm(tw["entry_t"]), "side": "LONG" if tw["dir"] == 1 else "SHORT", "who": tw["who"],
               "twin_exit": tw["exit"], "twin_r": tw["r"]}
        if m is not None:
            used.add(m)
            row.update(status="matched", live_r=_f(live[m].get("r")), live_usd=live[m].get("pnl"))
        elif live_from_t and tw["entry_t"] < live_from_t:
            row.update(status="not live yet", live_r=None, live_usd=None)
        else:
            row.update(status="missed", live_r=None, live_usd=None)
        rows.append(row)
    for i, lv in enumerate(live):
        if i not in used and lv.get("entry_t") is not None:
            rows.append({"day": lv["day"], "time": _hm(lv["entry_t"]), "side": "LONG" if lv.get("dir") == 1 else "SHORT", "who": "-",
                         "twin_exit": None, "twin_r": None, "status": "extra", "live_r": _f(lv.get("r")), "live_usd": lv.get("pnl")})
    rows.sort(key=lambda r: (r["day"], r["time"]))
    n = {k: sum(1 for r in rows if r["status"] == k) for k in ("matched", "missed", "extra", "not live yet")}
    tr = round(sum(r["twin_r"] or 0 for r in rows if r["status"] != "not live yet"), 2)
    lr = round(sum(r["live_r"] or 0 for r in rows if r["live_r"] is not None), 2)
    bits = [f"twin {len([r for r in rows if r['twin_r'] is not None])} trades {tr:+.2f}R, live {len(live)} trades {lr:+.2f}R"]
    if n["missed"]:
        bits.append(f"{n['missed']} missed")
    if n["extra"]:
        bits.append(f"{n['extra']} extra (no twin)")
    if n["not live yet"]:
        bits.append(f"{n['not live yet']} before the account was live")
    same = not n["missed"] and not n["extra"] and abs(tr - lr) <= 0.3 * max(1, len(rows))
    return {"name": name, "rows": rows, "n": n, "twin_r": tr, "live_r": lr,
            "verdict": "same as the twin" if same else "differs from the twin", "line": "; ".join(bits) + "."}


def twins(week: dict, tr: list, life: dict | None = None) -> dict:
    """{"to": last day with bars, "bots": [Zlarior, ATLAS]} or {"error": ...}. R only: the twin's $ is at research size."""
    bt = _bars_to()
    days = [d for d in week["days"] if bt is None or d <= bt]
    if not days:
        return {"to": bt, "bots": [], "note": "no bars for this week yet"}
    since = {}
    for k, v in _d(_d(life).get("acc")).items():
        if _f(_d(v).get("since")):
            since["atlas" if k == "atlas" else "zlarior" if k == "lit" else k] = int(v["since"])
    out = {"to": bt, "days": days, "bots": [],
           "note": "R only (the twin's $ is at the research size). Days after the cloud's last bars are not compared." if bt else ""}
    for name, fn, acct in (("Zlarior", _lit_twin, LIT_ACCT), ("ATLAS", _atlas_twin, ATLAS_ACCT)):
        live = [x for x in tr if x["acct"] == acct and x["day"] in days]
        try:
            tw = fn(days)
        except Exception as e:  # noqa: BLE001
            out["bots"].append({"name": name, "error": f"twin replay failed ({e.__class__.__name__})"})
            continue
        # a stage change is not "the account went live": only a funded account's issue time counts (ATLAS, Nov 17)
        out["bots"].append(compare(name, tw, live, since.get(acct) if acct == "atlas" else None))
    return out


# ------------------------------------------------------------------------------------------------ best / worst + lesson
CAUSES_ALL = ("news", "wick", "turned", "never", "target", "managed")
LESSON = {
    "news": "A Tier-1 release hit it. The bots trade through news by design (a blackout did not help in research). Nothing to change.",
    "wick": "Shaken out, then price went on to the target. The stop sits 1 tick past the sweep by rule; wider stops were tested and lose more. It happens; nothing to change.",
    "turned": "It worked first (+0.5R or more), then turned. Break-even and the 15-minute check protect most of these; a give-back under 1R is the price of the edge.",
    "never": "It never worked: a clean 1R loss, the normal cost of the setup. Only worth a look if 3 or more in a row.",
    "target": "Target hit: the plan did exactly what it should. Nothing to change.",
    "managed": "Closed early by the rules (break-even / time / 15-minute check) with a small gain. Fine: the rules cap risk, not upside.",
}


def _path(t: dict, d1) -> dict:
    """MFE (R) in the trade, and did price reach the target after the exit the same day (1m bars)."""
    out = {"mfe_r": None, "post_tgt": None}
    e, s, g, ent, ext, di = (t.get(k) for k in ("entry", "stop", "target", "entry_t", "exit_t", "dir"))
    if d1 is None or not len(d1) or None in (e, s, ent, ext) or not di or abs(e - s) <= 0:
        return out
    risk = abs(e - s)
    inside = d1[(d1["time"] >= ent) & (d1["time"] < ext)]
    if len(inside):
        best = inside["high"].max() - e if di == 1 else e - inside["low"].min()
        out["mfe_r"] = round(float(best) / risk, 2)
    if g is not None:
        day_end = int(dt.datetime.combine(dt.date.fromisoformat(trading_day(ext)), dt.time(15, 55), ET).timestamp())
        after = d1[(d1["time"] >= ext) & (d1["time"] < day_end)]
        if len(after):
            out["post_tgt"] = bool((after["high"].max() >= g) if di == 1 else (after["low"].min() <= g))
    return out


def _news_in(t: dict, events: list) -> str | None:
    a, z = t.get("entry_t"), t.get("exit_t")
    if a is None or z is None:
        return None
    for ev in events:
        if a - 120 <= ev["t"] <= z + 120:
            return ev["event"]
    return None


def _t1_events() -> list:
    out = []
    try:
        with open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("impact") or "").lower() != "high":
                    continue
                hh, mm = (r.get("time_et") or "0:0").split(":")[:2]
                d = dt.date.fromisoformat(r["date"])
                out.append({"t": int(dt.datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=ET).timestamp()), "event": r.get("event") or ""})
    except (OSError, ValueError, KeyError):
        pass
    return out


def cause(t: dict, path: dict, news: str | None) -> str:
    """win_loss_anatomy.cause_of's order for a loss (news, wick, turned, never); a winner: target / managed."""
    pnl = _f(t.get("pnl")) or 0.0
    ex = str(t.get("exit") or t.get("reason") or "").upper()
    if pnl >= 0:
        return "target" if ex.startswith("TARGET") or ex == "BANK" else "managed"
    if news:
        return "news"
    if ex.startswith(("STOP", "CUT")) and path.get("post_tgt"):
        return "wick"
    if (path.get("mfe_r") or 0.0) >= 0.5:
        return "turned"
    return "never"


def best_worst(tr: list) -> dict:
    live = [x for x in tr if _f(x.get("pnl")) is not None]
    if not live:
        return {"best": None, "worst": None}
    d1 = None
    try:
        from engine import fill_audit as fa
        d1 = fa.load_bars()[1]
    except Exception:  # noqa: BLE001
        d1 = None
    ev = _t1_events()

    def card(t):
        p = _path(t, d1)
        nw = _news_in(t, ev)
        c = cause(t, p, nw)
        lesson = LESSON[c] if c != "news" else LESSON["news"].replace("A Tier-1 release", f"{nw}")
        return {"acct": t["acct"], "bot": "ATLAS" if t["strat"] == "atlas" else "Zlarior", "day": t["day"],
                "time": _hm(t["entry_t"]) if t.get("entry_t") else None, "side": None if not t.get("dir") else "LONG" if t["dir"] == 1 else "SHORT",
                "usd": t["pnl"], "r": _f(t.get("r")), "exit": t.get("exit") or None, "mfe_r": p["mfe_r"], "cause": c, "lesson": lesson}
    srt = sorted(live, key=lambda x: (x["pnl"], x["t"]))
    worst, best = srt[0], srt[-1]
    out = {"best": card(best) if best["pnl"] > 0 else None, "worst": card(worst) if worst["pnl"] < 0 else None}
    if len(live) == 1:
        out["best" if live[0]["pnl"] > 0 else "worst"] = card(live[0])
    return out


# ------------------------------------------------------------------------------------------------ Kalshi K8
def kalshi(week: dict, lite: dict | None) -> dict | None:
    """K8's week: the PC's own ledger (engine/kalshi_clock rows) when here, else the public card (week loss used, last 10)."""
    try:
        from engine import kalshi_clock as K
        P = K.paths()
        path = P["clock_live"] if os.path.exists(P["clock_live"]) else P["clock_paper"]
        if os.path.exists(path):
            rs = [r for r in K.rows(path) if str(r.get("day") or "") in week["days"]]
            s = K.stats(rs)
            mode = "live" if path == P["clock_live"] else "paper"
            if s["n"]:
                line = f"K8 ({mode}): {s['n']} bets, {s['won']} won ({round(100 * s['rate'])}%), {usd(s['net'], True)} this week."
            else:
                line = f"K8 ({mode}): no bet settled this week."
            return {"src": "PC ledger", "mode": mode, "bets": s["n"], "won": s["won"], "net": s["net"], "line": line}
    except Exception:  # noqa: BLE001
        pass
    k = _d(_d(_d(lite).get("kalshi_live")).get("k8"))
    if not k:
        return None
    mode = "live" if k.get("m") == "L" else "paper"
    wk = k.get("wk") or [None, None]
    wr = k.get("wr") or [None, None]
    last = str(k.get("l") or "")
    line = (f"K8 ({mode}): {_usd2(wk[0])} of the {_usd2(wk[1])} weekly loss stop used; last {len(last)} bets {last or '-'}"
            + (f"; {wr[0]} bets so far, {wr[1]}% won" if wr[0] else "") + ".")
    return {"src": "PC status post (card)", "mode": mode, "loss_used": _f(wk[0]), "loss_stop": _f(wk[1]), "last": last,
            "bets_total": wr[0], "won_pct": wr[1], "line": line}


# ------------------------------------------------------------------------------------------------ next week, day by day
def calendar(week: dict) -> list:
    from engine import cme_calendar as C
    news = {}
    try:
        with open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                imp = (r.get("impact") or "").lower()
                if imp in ("high", "medium") and week["next_from"] <= r["date"] <= week["next_to"]:
                    news.setdefault(r["date"], []).append({"time": r.get("time_et") or "", "event": r.get("event") or "",
                                                           "tier": 1 if imp == "high" else 2})
    except OSError:
        pass
    out = []
    d0 = dt.date.fromisoformat(week["next_from"])
    for i in range(5):
        d = d0 + dt.timedelta(days=i)
        ds = d.isoformat()
        if C.full_closure(ds):
            st, txt = "closed", "CME closed: no trading"
        elif C.early_close(ds) is not None:
            h = int(C.early_close(ds))
            st = "early"
            txt = (f"NQ trades until {h // 60:02d}:{h % 60:02d} ET (early close): the bots stop new trades 15 min before, "
                   "flat 5 min before")
            if d.month == 11 and d.weekday() == 3 and 22 <= d.day <= 28:
                txt = "Thanksgiving: the stock market is closed; " + txt
        else:
            st, txt = "open", "normal day"
        out.append({"date": ds, "weekday": d.strftime("%a"), "status": st, "text": txt,
                    "news": sorted(news.get(ds, []), key=lambda e: (e["time"], e["tier"]))})
    return out


# ------------------------------------------------------------------------------------------------ this weekend
def weekend(n: int = 5) -> list:
    dec = _d(_read(os.path.join(BIZ, "decisions.json"))).get("items") or []
    fp = _d(_read(os.path.join(BIZ, "fleet_plan.json")))
    fp_usd = {}
    for c in (fp.get("cards") or fp.get("items") or fp.get("decisions") or []):
        c = _d(c)
        v = _f(c.get("usd_month") if c.get("usd_month") is not None else c.get("impact_usd"))
        if c.get("id") and v is not None:
            fp_usd[str(c["id"])] = v
    rows = []
    for c in dec:
        c = _d(c)
        if c.get("status") != "open":
            continue
        cid = str(c.get("id") or "")
        v = fp_usd.get(cid, _f(c.get("impact_usd")))
        if v is None:
            m = re.search(r"([+-])\$([\d,]+) a month", str(c.get("impact") or ""))
            v = (1 if m.group(1) == "+" else -1) * float(m.group(2).replace(",", "")) if m else None
        rows.append({"id": cid, "question": re.sub(r"\s+", " ", str(c.get("question") or ""))[:180], "usd_month": v,
                     "src": "fleet_plan.json" if cid in fp_usd else "Decide card"})
    rows.sort(key=lambda r: (-(r["usd_month"] if r["usd_month"] is not None else -1e9), r["id"]))
    return rows[:n]


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
