#!/usr/bin/env python3
"""ZEUS THIS WEEK (owner's Work week page: "Friday 16:30 ET weekly review"). Builds tools/web_public/business/week.json for the
phone page business/week.html: one screen, $ first.

  per account    start / end balance, $ this week, trades, win %, best day vs the consistency rule, room, $ to pass or payout
  per strategy   Zlarior (LIT) and ATLAS: trades this week vs the 2-4 target, PF, $ vs the 2026 expectation -> on track / behind / ahead
  code           what changed this week (git log one-liners, max 8)
  next week      Tier-1 news days (data/news/events.csv), CME early closes / closed days, the decisions waiting on the owner
  pace           one honest line: "on pace for $X a month (estimate)"

Sources, each optional (a missing one is named in "missing", never guessed): the live board (tools/board.py gather: the PC's
live numbers over ntfy, the plan tools/web_public/business/accounts.json, board events), the trade ledgers (on the PC:
data/live_state*.json + logs/datapipe; in the cloud: data/pc_days/ from tools/data_pull.py, else the backup's `data` branch),
research/lab/backtest_live.json + edge_health.json (the 2026 expectation), git log, events.csv, engine/cme_calendar.

  python tools/weekly_review.py              build week.json (network: ntfy + git fetch; both optional)
  python tools/weekly_review.py --offline    the repo only
  python tools/weekly_review.py --print      also print the summary lines
  python tools/weekly_review.py --post       also post the board event "Weekly review ready" (Claude note in data/board/shared.jsonl)
  options: --now EPOCH_S  --out FILE

On the PC the Friday ops task (engine/ops_checks.tick, Friday from 16:15 ET, once a week) calls pc_run(): it builds the file
and posts the board event from the bot. Read only otherwise: never trades, arms, sizes or routes anything.
Test: python -X utf8 -m tests.test_weekly_review [--browser]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import gzip
import json
import os
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "tools", "web_public", "business", "week.json")
ET = ZoneInfo("America/New_York")
TARGET_TPW = (2, 4)                       # CLAUDE.md: 2-4 trades a week
WEEKS_A_MONTH = 4.33
MAX_CHANGES = 8
STRAT = {"zlarior": "Zlarior", "atlas": "ATLAS"}
STRAT_OF_ACCT = {"atlas": "atlas"}        # plan account key -> strategy (every other live account runs Zlarior / LIT)
BOT_OF = (("acctb", "atlas"), ("atlas_v2", "atlas_v2"), ("acctc", "blitz"), ("acctr", "rapid"), ("fleet", "zlarior"),
          ("accounts", "zlarior"), ("lit", "zlarior"), ("si", "other"))       # the same tags as engine/datapipe (night-learn)


# ------------------------------------------------------------------------------------------------ small helpers
def _f(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def usd(v, sign=False) -> str:
    x = _f(v)
    if x is None:
        return "-"
    s = f"${abs(x):,.0f}"
    return ("-" if x < 0 else "+" if sign and x > 0 else "") + s


def trading_day(ts) -> str:
    """CME trading day of a unix time (18:00 ET starts the next day), the rule engine/accounts.trading_day uses."""
    return (dt.datetime.fromtimestamp(int(ts), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def week_of(now) -> dict:
    """This review's week: Mon-Fri of the ET week (Saturday / Sunday: the week that just ended); next = the Mon-Fri after."""
    e = dt.datetime.fromtimestamp(int(now), ET)
    mon = e.date() - dt.timedelta(days=e.weekday())
    fri = mon + dt.timedelta(days=4)
    last = min(e.date(), fri)
    if e.weekday() == 4 and e.hour * 60 + e.minute < 16 * 60:
        last = fri - dt.timedelta(days=1)        # Friday before 16:00 ET: today's session is not over yet (still counted when traded)
    days = [(mon + dt.timedelta(days=i)).isoformat() for i in range(5)]
    done = [d for d in days if d <= e.date().isoformat()]
    nmon = mon + dt.timedelta(days=7)
    return {"from": mon.isoformat(), "to": fri.isoformat(), "days": days, "sessions_done": max(1, len(done)),
            "complete": e.weekday() >= 5 or (e.weekday() == 4 and e.hour * 60 + e.minute >= 16 * 60),
            "start_t": int(dt.datetime.combine(mon - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp()),
            "next_from": nmon.isoformat(), "next_to": (nmon + dt.timedelta(days=4)).isoformat(), "last_done": last.isoformat(),
            "label": f"{mon.strftime('%b')} {mon.day} - {fri.strftime('%b')} {fri.day}"}


def _clean(s, n=140) -> str:
    s = re.sub(r"[\x00-\x1f\x7f<>]", " ", str(s or "")).strip()
    try:
        from tools import site_privacy
        s = site_privacy.clean_string(s)
    except Exception:  # noqa: BLE001
        pass
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[:n - 1].rsplit(" ", 1)[0] + "..."


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _jsonl(raw: bytes | str | None) -> list:
    out = []
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    for ln in (raw or "").splitlines():
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if isinstance(j, dict):
            out.append(j)
    return out


def _git(*args, timeout=30) -> tuple:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, b""


# ------------------------------------------------------------------------------------------------ trades (the ledgers)
def _src_bot(stem: str) -> tuple:
    suf = stem[len("live_state"):].lstrip("_")
    if not suf:
        return "main", "zlarior", "zlarior"
    for k, b in BOT_OF:
        if suf == k or suf.startswith(k + "."):
            return suf, b, ("atlas" if b == "atlas" else b)
    return suf, "other", suf


def _mode(row: dict, adapter=None, account=None) -> str:
    res = _d(row.get("result"))
    ad = str(res.get("adapter") or row.get("adapter") or adapter or "").lower()
    if ad in ("paper", "", "none"):
        return "paper"
    a = str(res.get("account") or row.get("account") or account or "")
    return "sim" if a.lower().startswith("sim") else "live"


def pc_rows(root: str = ROOT) -> list:
    """The PC's own ledgers right now (state files keep only recent days) + the data pipe's archive (every row since it ran)."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "data", "live_state*.json"))):
        stem = os.path.basename(p)[:-5]
        if ".corrupt" in stem or stem.endswith(".tmp"):
            continue
        st = _d(_read_json(p, {}))
        src, bot, acct = _src_bot(stem)
        for r in st.get("ledger") or []:
            if isinstance(r, dict):
                out.append({**r, "src": src, "bot": bot, "acct": acct, "mode": _mode(r, st.get("adapter"), st.get("nt_account"))})
        for aid, blob in _d(st.get("accounts")).items():
            for r in _d(blob).get("ledger") or []:
                if isinstance(r, dict):
                    out.append({**r, "src": f"accounts/{aid}", "bot": bot if bot != "other" else "zlarior", "acct": str(aid),
                                "mode": _mode(r, None, _d(blob).get("nt_account"))})
    for r in _jsonl(_read_file(os.path.join(root, "logs", "exec_audit", "ledger.jsonl"))):
        out.append({**r, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": _mode(r, r.get("adapter"))})
    out += _jsonl(_read_file(os.path.join(root, "logs", "datapipe", "ledger_archive.jsonl")))
    return out


def _read_file(path) -> bytes | None:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _ungz(raw):
    try:
        return gzip.decompress(raw) if raw else None
    except (OSError, EOFError):
        return None


def day_rows(days, root: str = ROOT, offline: bool = True) -> tuple:
    """The data pipe's day folders: the PC's local copy (logs/datapipe/days), the cloud's pulled copy (data/pc_days), else the
    backup's `data` branch (git show, after one fetch when online). -> (rows, label of the source or '')."""
    out, srcs = [], set()
    for base, lab in ((os.path.join(root, "logs", "datapipe", "days"), "PC day files"), (os.path.join(root, "data", "pc_days"), "data pipe (pulled)")):
        for d in days:
            raw = _ungz(_read_file(os.path.join(base, d, "trades.jsonl.gz")))
            if raw:
                out += _jsonl(raw)
                srcs.add(lab)
    if out:
        return out, ", ".join(sorted(srcs))
    ref = None
    for r in ("olympus/data", "origin/data"):
        if _git("rev-parse", "--verify", "-q", r)[0] == 0:
            ref = r
            break
    if ref is None and not offline:
        if _git("fetch", "-q", "olympus", "data:refs/remotes/olympus/data", timeout=60)[0] == 0:
            ref = "olympus/data"
    if ref:
        for d in days:
            c, raw = _git("show", f"{ref}:days/{d}/trades.jsonl.gz")
            if c == 0:
                out += _jsonl(_ungz(raw))
        if out:
            return out, f"data branch ({ref})"
    return [], ""


def trades(rows: list, week: dict, plan_accounts: list) -> list:
    """The week's closed live trades: [{acct (plan key), strat, day, pnl, t}], one per exit, de-duplicated."""
    from engine import board_events as B
    keys = {str(a.get("key")) for a in plan_accounts if isinstance(a, dict)}
    seen, out = set(), []
    for r in rows:
        if r.get("side") != "exit" or r.get("void") or str(r.get("reason") or "").upper() == "NO TRADE":
            continue
        pnl, t = _f(r.get("pnl")), _f(r.get("exit_t")) or _f(r.get("t"))
        if pnl is None or t is None or r.get("mode") != "live":
            continue
        day = trading_day(t)
        if day not in week["days"]:
            continue
        a = str(r.get("acct") or "")
        k = a if a in keys else (B.plan_key(plan_accounts, a, "") or B.ALIASES.get(a.lower()) or a)
        bot = str(r.get("bot") or "")
        strat = "atlas" if bot.startswith("atlas") else "zlarior" if bot in ("zlarior", "") else bot
        if strat not in STRAT:
            continue
        sig = (k, r.get("entry_t"), round(pnl, 2), day)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"acct": k, "strat": strat, "day": day, "pnl": round(pnl, 2), "t": int(t)})
    return sorted(out, key=lambda x: x["t"])


def stats(tr: list) -> dict:
    n = len(tr)
    wins = [x["pnl"] for x in tr if x["pnl"] > 0]
    loss = [x["pnl"] for x in tr if x["pnl"] < 0]
    per = {}
    for x in tr:
        per[x["day"]] = round(per.get(x["day"], 0.0) + x["pnl"], 2)
    best = max(per.items(), key=lambda kv: kv[1]) if per else None
    gl = -sum(loss)
    return {"n": n, "usd": round(sum(x["pnl"] for x in tr), 2), "win_pct": round(100.0 * len(wins) / n) if n else None,
            "pf": (round(sum(wins) / gl, 2) if gl > 0 else (None if not wins else "no loss")), "days": per,
            "best_day": {"day": best[0], "usd": best[1]} if best else None}


# ------------------------------------------------------------------------------------------------ expectation (research files)
def expectation() -> dict:
    """2026 trades a week + PF per strategy: Zlarior from backtest_live.json (both 2026 halves), ATLAS from edge_health.json
    (the 40-session median of each half). $ a month comes from the plan (accounts.json usd_month, live sizing)."""
    out = {}
    bl = _d(_read_json(os.path.join(ROOT, "research", "lab", "backtest_live.json"), {}))
    per = _d(bl.get("periods"))
    h1 = next((v for k, v in per.items() if k.startswith("2026 H1")), None)
    h2 = next((v for k, v in per.items() if k.startswith("2026 H2")), None)
    if h1 and h2:
        out["zlarior"] = {"tpw": [h2.get("per_week"), h1.get("per_week")], "pf": [h2.get("pf"), h1.get("pf")],
                          "src": "backtest_live.json (2026 Jul-Oct / Jan-Jun)"}
    eh = _d(_read_json(os.path.join(ROOT, "research", "lab", "edge_health.json"), {}))
    for k in ("atlas", "zlarior"):
        if k in out:
            continue
        w = _d(_d(_d(eh.get("lit" if k == "zlarior" else k)).get("windows")).get("40")).get("dist")
        w = _d(w)
        try:
            out[k] = {"tpw": [w["tpw"]["2026 H2"]["median"], w["tpw"]["2026 H1"]["median"]],
                      "pf": [w["pf"]["2026 H2"]["median"], w["pf"]["2026 H1"]["median"]], "src": "edge_health.json (40-session medians, 2026)"}
        except (KeyError, TypeError):
            pass
    light = _d(eh.get("card"))
    if light.get("light"):
        out["light"] = {"light": light.get("light"), "line": _clean(light.get("line"), 120)}
    return out


def _usd_month(s):
    m = re.search(r"\$\s?([\d,]+)", str(s or ""))
    return float(m.group(1).replace(",", "")) if m else None


# ------------------------------------------------------------------------------------------------ the sections
RULE = {"eval": "Builder eval: no best-day rule", "funded": "funded: best day at most 50% of the cycle profit",
        "rapid_eval": "Rapid EOD eval: best day at most 30% of the profit"}


def account_rows(board: dict, plan: dict, tr: list, have_trades: bool, week: dict, events: list) -> tuple:
    out, missing = [], []
    pa = {str(a.get("key")): a for a in plan.get("accounts") or [] if isinstance(a, dict)}
    for r in board.get("accounts") or []:
        k = str(r.get("key"))
        a = _d(pa.get(k))
        if a.get("status") == "waiting" and r.get("balance") is None:
            continue                                   # a planned account not bought yet: not part of this week
        mine = [x for x in tr if x["acct"] == k]
        st = stats(mine)
        end = _f(r.get("balance"))
        src = str(r.get("src") or "PLAN")
        age = r.get("age_s")
        row = {"key": k, "name": _clean(r.get("name"), 40), "plan": _clean(r.get("plan") or a.get("plan"), 40),
               "stage": r.get("chip") or r.get("stage"), "end": end, "src": src + (f", {_ago(age)}" if age is not None else ""),
               "room": _f(r.get("room")), "to_pass": _f(r.get("to_pass")), "trades": st["n"] if have_trades else None,
               "win_pct": st["win_pct"] if have_trades else None, "usd_week": st["usd"] if have_trades else None,
               "best_day": st["best_day"], "strat": STRAT[STRAT_OF_ACCT.get(k, "zlarior")]}
        start = None
        if have_trades and end is not None:
            start = round(end - st["usd"], 2)
        else:
            start = _balance_before(events, k, week["start_t"])
            if start is not None and end is not None and (r.get("src_t") or 0) >= week["start_t"]:
                row["usd_week"] = round(end - start, 2)
        row["start"] = start
        if row["src"].startswith("PLAN"):
            missing.append(f"{row['name']}: no live PC balance this week (plan / owner-typed number shown)")
        # consistency rule
        plan_name = str(row["plan"] or "")
        stage = str(r.get("stage") or "")
        if "Rapid" in plan_name and stage == "eval":
            rule = RULE["rapid_eval"]
        elif stage == "funded":
            rule = RULE["funded"]
        else:
            rule = RULE["eval"]
        bd = st["best_day"]
        row["consistency"] = {"rule": rule, "line": _cons_line(rule, bd, row, a)}
        row["status_line"] = _status_line(row, r, a, stage)
        out.append(row)
    return out, missing


def _cons_line(rule, bd, row, a) -> str:
    if not bd:
        return "No trading day this week."
    if bd["usd"] <= 0:
        return "No winning day this week."
    best = f"best day {bd['day'][5:]} {usd(bd['usd'], True)}"
    if rule == RULE["eval"]:
        return best + ": fine (no rule in the eval)."
    if rule == RULE["rapid_eval"]:
        prof = (row["end"] or 0) - 25000.0 if "25K" in str(row["plan"]) else (row["end"] or 0) - 50000.0
        if prof <= 0:
            return best + ": the profit so far is not positive yet."
        pct = round(100 * bd["usd"] / prof)
        return best + f" = {pct}% of the profit " + ("(OK, max 30%)." if pct <= 30 else "(over 30%: more small days needed to pass).")
    fd = _d(a.get("funded"))
    cs = _f(fd.get("cycle_start_balance"))
    if cs is None or row["end"] is None:
        return best + " (the cycle profit is unknown: rule not checked)."
    cp = row["end"] - cs
    if cp <= 0:
        return best + ": the cycle profit is not positive yet."
    pct = round(100 * bd["usd"] / cp)
    return best + f" = {pct}% of the cycle profit " + ("(OK, max 50%)." if pct <= 50 else "(over 50%: payout waits for more days).")


def _status_line(row, r, a, stage) -> str:
    if stage == "eval" and row["to_pass"] is not None:
        return f"{usd(row['to_pass'])} to pass" + (f", {usd(row['room'])} of room above the floor" if row["room"] is not None else "")
    if stage == "passed":
        return "Passed. " + ("Locked until MFFU issues the funded account." if r.get("locked") else "Waiting for the funded account.")
    if stage == "failed":
        return "Failed: the floor was hit."
    if stage == "funded":
        try:
            from engine import payout_coach as PC
            plan = "builder50k" if "50K" in str(row["plan"]) else "builder25k"
            fd = _d(a.get("funded"))
            c = PC.coach({**fd, "balance": row["end"], "best_day": max([0.0] + [_f(x) for x in [fd.get("best_day"), _d(row["best_day"]).get("usd")] if _f(x) is not None])},
                         plan=plan)
            return "Payout: " + c.get("text", "")
        except Exception:  # noqa: BLE001
            return "Payout status unknown (payout coach not readable)."
    return str(a.get("next") or "")[:140]


def _balance_before(events, key, t0):
    """The newest balance any event gave for this account before the week started (owner-typed, Claude, the PC)."""
    best, bt = None, -1
    for e in events or []:
        if e.get("acct") != key:
            continue
        b, t = _f(_d(e.get("data")).get("balance")), int(_f(e.get("t")) or 0)
        if b is not None and t < t0 and t > bt:
            best, bt = b, t
    return best


def _ago(sec) -> str:
    try:
        from engine import board_events as B
        return B.ago(sec)
    except Exception:  # noqa: BLE001
        return f"{int(sec) // 60} min ago"


def strategy_rows(tr: list, have_trades: bool, week: dict, exp: dict, plan: dict) -> list:
    out = []
    usd_m = {"zlarior": 0.0, "atlas": 0.0}
    for a in plan.get("accounts") or []:
        if isinstance(a, dict) and a.get("status") == "live":
            v = _usd_month(a.get("usd_month"))
            if v:
                usd_m[STRAT_OF_ACCT.get(str(a.get("key")), "zlarior")] += v
    for s, name in STRAT.items():
        mine = [x for x in tr if x["strat"] == s]
        st = stats(mine)
        e = _d(exp.get(s))
        frac = week["sessions_done"] / 5.0
        exp_w = round(usd_m[s] / WEEKS_A_MONTH * frac, 0) if usd_m[s] else None
        row = {"name": name, "trades": st["n"] if have_trades else None, "target": f"{TARGET_TPW[0]}-{TARGET_TPW[1]} a week",
               "pf": st["pf"] if have_trades else None, "usd": st["usd"] if have_trades else None, "win_pct": st["win_pct"] if have_trades else None,
               "exp_tpw": e.get("tpw"), "exp_pf": e.get("pf"), "exp_src": e.get("src"), "exp_usd_week": exp_w,
               "plan_usd_month": usd_m[s] or None}
        if not have_trades:
            row["verdict"], row["why"] = "unknown", "No trade list this week (see what is missing)."
        else:
            lo, hi = TARGET_TPW[0] * frac, TARGET_TPW[1] * frac
            why = []
            if st["n"] < lo and week["complete"]:
                why.append(f"{st['n']} trades (target {TARGET_TPW[0]}-{TARGET_TPW[1]})")
            if exp_w is not None and st["usd"] < 0:
                why.append(f"{usd(st['usd'])} this week")
            ahead = exp_w is not None and st["usd"] >= 1.5 * max(exp_w, 1) and st["n"] >= 1
            row["verdict"] = "behind" if why else ("ahead" if ahead else "on track")
            row["why"] = ("; ".join(why) if why else
                          f"{usd(st['usd'], True)} vs about {usd(exp_w)} expected" if exp_w is not None else f"{st['n']} trades") + \
                (f"; {st['n']} trades is above {TARGET_TPW[1]} a week" if st["n"] > hi and week["complete"] else "")
        out.append(row)
    return out


def code_changes(week: dict) -> dict:
    """What changed in the code this week: newest non-merge commit subjects since Monday 00:00 ET, plain words, max 8."""
    since = dt.datetime.combine(dt.date.fromisoformat(week["from"]), dt.time(0, 0), ET).isoformat()
    c, raw = _git("log", f"--since={since}", "--no-merges", "--format=%s", "-n", "200")
    if c != 0:
        return {"n": None, "items": [], "note": "git log not readable here"}
    subs = [s.strip() for s in raw.decode("utf-8", "replace").splitlines() if s.strip()]
    seen, items = set(), []
    for s in subs:
        s = re.sub(r"^(night-[\w-]+|team \w+|[A-Z]\d)\s*[:\-]\s*", "", s)
        s = re.sub(r"\s*\((?:[^()]*?)\)\s*$", "", s) if len(s) > 90 else s
        t = _clean(s, 100)
        if t.lower().startswith("merge") or "cache bump" in t.lower() or t.lower().startswith(("version bumps", "test_", "state:")):
            continue                     # merges and housekeeping are not "what changed" for the owner
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        items.append(t)
    return {"n": len(subs), "items": items[:MAX_CHANGES]}


def next_week(week: dict, plan: dict, goals: dict) -> dict:
    news = []
    try:
        with open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if week["next_from"] <= str(r.get("date") or "") <= week["next_to"] and str(r.get("impact") or "").lower() == "high":
                    news.append({"date": r["date"], "time": r.get("time_et") or "", "what": _clean(r.get("event"), 60)})
    except OSError:
        news = None
    hol = []
    try:
        from engine import cme_calendar as C
        for r in C.calendar(week["next_from"], 5):
            hol.append({"date": r["day"], "type": r["kind"],
                        "what": "CME closed: no trading" if r["kind"] == "closed" else
                        f"Early close {r['halt']} ET: the bot stops new trades 15 min before, flat 5 min before"})
    except Exception:  # noqa: BLE001
        hol = None
    dec, seen = [], set()
    for s in list(plan.get("decisions") or []) + list(_d(goals).get("decisions") or []):
        t = _clean(s, 140)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            dec.append(t)
    steps = [_clean(w.get("what"), 120) for w in _d(goals).get("week") or []
             if isinstance(w, dict) and week["next_from"] <= str(w.get("date") or "") <= week["next_to"] and not w.get("auto")]
    return {"from": week["next_from"], "to": week["next_to"], "news": news, "holidays": hol, "decisions": dec[:6], "steps": steps[:4]}


def pace(strats: list, accts: list, have_trades: bool, week: dict, plan: dict) -> dict:
    plan_m = sum(_f(s.get("plan_usd_month")) or 0 for s in strats) or None
    if have_trades:
        wk = sum(_f(s.get("usd")) or 0 for s in strats)
        m = round(wk / week["sessions_done"] * 5 * WEEKS_A_MONTH, -1)
        line = (f"On pace for {usd(m)} a month (estimate: this week's {usd(wk, True)} x 4.3; one week is noise"
                + (f", the plan says about {usd(plan_m)}" if plan_m else "") + "). Eval $ is not cash until the account passes and pays out.")
        return {"usd_month": m, "line": line, "basis": "this week"}
    wk = [a["usd_week"] for a in accts if _f(a.get("usd_week")) is not None]
    if wk:
        s = sum(wk)
        m = round(s / week["sessions_done"] * 5 * WEEKS_A_MONTH, -1)
        return {"usd_month": m, "basis": "balances",
                "line": f"On pace for {usd(m)} a month (estimate from balance changes only; no trade list)."
                        + (f" The plan says about {usd(plan_m)}." if plan_m else "")}
    return {"usd_month": None, "basis": "none",
            "line": "On pace: unknown this week (no trade list and no start-of-week balance)."
                    + (f" The plan says about {usd(plan_m)} a month once funded (estimate)." if plan_m else "")}


# ------------------------------------------------------------------------------------------------ build
def build(offline: bool = False, now=None, board=None, rows=None, root: str = ROOT, on_pc: bool = False) -> dict:
    now = int(now or time.time())
    week = week_of(now)
    missing = []
    from engine import board_events as B
    plan = B.plan()
    if board is None:
        try:
            from tools import board as BD
            if on_pc:
                board = BD.gather(hb={"present": False, "reason": "not used on the PC"}, lite=BD.fetch_lite(), now=now)
            else:
                board = BD.gather(offline=offline, now=now)
        except Exception as e:  # noqa: BLE001
            board = {"accounts": [], "events": [], "pc": {}}
            missing.append(f"live board not readable ({e.__class__.__name__})")
    pc = _d(board.get("pc"))
    pc_t = _f(pc.get("t"))
    if not pc_t:
        missing.append("PC live numbers: the PC has not reported here")
    elif now - pc_t > B.STALE_S:
        missing.append(f"PC live numbers: last report {B.et_text(pc_t)} ({B.ago(now - pc_t)})")
    src_tr = ""
    if rows is None:
        rows = pc_rows(root)
        src_tr = "PC ledgers" if rows else ""
        dr, lab = day_rows(week["days"], root, offline=offline)
        if dr:
            rows += dr
            src_tr = ", ".join(x for x in (src_tr, lab) if x)
    else:
        src_tr = "given"
    tr = trades(rows, week, plan.get("accounts") or [])
    have = bool(rows)
    if not have:
        missing.append("trade list: no PC ledger here and no data pipe days yet (on the PC this fills itself; in the cloud run "
                       "python tools/data_pull.py once the PC's data branch exists)")
    events = board.get("events") or []
    accts, m2 = account_rows(board, plan, tr, have, week, events)
    missing += m2
    if not have and not any(_f(a.get("start")) is not None for a in accts):
        missing.append("start-of-week balances: not known (needs the trade list or a balance typed before Monday)")
    exp = expectation()
    if "zlarior" not in exp or "atlas" not in exp:
        missing.append("2026 expectation: research/lab backtest_live.json / edge_health.json not readable")
    strats = strategy_rows(tr, have, week, exp, plan)
    goals = _d(_read_json(os.path.join(ROOT, "tools", "web_public", "business", "goals.json"), {}))
    nxt = next_week(week, plan, goals)
    if nxt["news"] is None:
        missing.append("news calendar: data/news/events.csv not readable")
    ch = code_changes(week)
    pc_line = (f"PC last reported {B.et_text(pc_t)} ({B.ago(now - pc_t)})" if pc_t else "PC: no report reached the cloud")
    doc = {"v": 1, "title": "ZEUS this week", "built": dt.datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d %H:%M ET"),
           "built_t": now, "built_by": "tools/weekly_review.py" + (" on the PC" if on_pc else ""),
           "week": {k: week[k] for k in ("from", "to", "label", "complete", "sessions_done")},
           "pc": pc_line, "accounts": accts, "strategies": strats, "light": exp.get("light"), "changes": ch, "next": nxt,
           "pace": pace(strats, accts, have, week, plan), "missing": missing,
           "sources": {"trades": src_tr or "none", "plan_updated": plan.get("updated"), "board_pc_t": int(pc_t) if pc_t else None}}
    return doc


def write(doc: dict, path: str = OUT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(path + ".tmp", path)
    return path


def summary(doc: dict) -> str:
    """The board event's text: one line, $ first (< 300 chars)."""
    bits = []
    for s in doc.get("strategies") or []:
        if s.get("trades") is not None:
            bits.append(f"{s['name']} {usd(s.get('usd'), True)} ({s['trades']} trades, {s['verdict']})")
    head = "Weekly review ready (" + doc["week"]["label"] + ")"
    body = "; ".join(bits) if bits else "no trade list this week"
    return _clean(f"{head}: {body}. {doc['pace']['line'].split(' (')[0]}. Business: ZEUS this week.", 290)


def lines(doc: dict) -> list:
    out = [f"{doc['title']} ({doc['week']['label']}) built {doc['built']} | {doc['pc']}"]
    for a in doc["accounts"]:
        out.append(f"  {a['name']}: {usd(a.get('start'))} -> {usd(a.get('end'))} ({usd(a.get('usd_week'), True)}), "
                   f"trades {a['trades'] if a['trades'] is not None else '?'}, {a['status_line']}")
    for s in doc["strategies"]:
        out.append(f"  {s['name']}: {s['verdict'].upper()} - {s['why']}")
    out.append("  " + doc["pace"]["line"])
    for m in doc["missing"]:
        out.append("  missing: " + m)
    return out


def post(doc: dict, from_pc: bool = False):
    """The board event "Weekly review ready": from the bot on the PC (data/board/events.jsonl), else a Claude note (shared.jsonl)."""
    from engine import board_events as B
    text = summary(doc)
    if from_pc:
        return B.emit("weekly_review", "", text, {"week": doc["week"]["from"]})
    rec = B.make("weekly_review", "", text, {"week": doc["week"]["from"]}, src="claude")
    return B.append(rec, B.shared_file()) if rec else None


def pc_run(now=None, log=None) -> dict:
    """The PC's Friday ops task: build week.json from the PC's own ledgers + its live post, post the board event. Never raises."""
    try:
        doc = build(now=now, on_pc=True)
        write(doc)
        rec = post(doc, from_pc=True)
        return {"ok": True, "posted": bool(rec), "missing": len(doc["missing"])}
    except Exception as e:  # noqa: BLE001
        if log:
            log(f"weekly review failed: {e.__class__.__name__}")
        return {"ok": False, "error": e.__class__.__name__}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ZEUS this week: build business/week.json for the Friday review.")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--print", dest="show", action="store_true")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--now", type=float)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    doc = build(offline=a.offline, now=a.now)
    p = write(doc, a.out)
    if a.show:
        print("\n".join(lines(doc)))
    if a.post:
        rec = post(doc)
        print("board event: " + ("posted" if rec else "not posted"))
    print("wrote " + os.path.relpath(p, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
