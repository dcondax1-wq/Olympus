"""Accounts page data: what the PC bot did on each account it trades, for the phone app's Accounts page.

Two halves:
  pc_activity(bot)          PC side. A compact, secret-free picture of the PC bot's routed activity, sent in the heartbeat
                            (engine/heartbeat.py, key "acct"): the account (name, SIM / LIVE / PAPER), the open position
                            (side, micros, broker fill, stop now, target, breakeven), today's routed orders (entry, fills,
                            bracket, stop moves, exits with reason and $), the recent closed routed trades (last 60, from the
                            LIT learning journal data/lit_journal.jsonl + today's ledger) and the eval's routed P&L per day
                            (live_state.json eval_days). Read-only: it never touches the bot's state and never raises.
  build_accounts(state, lm) cloud side (tools/build_web_dashboard.py -> data.json "accounts"): one section per account in
                            live_model.json "accounts" (default: the MFFU 50K eval on the PC bot) plus the cloud paper
                            ledger as "Paper (cloud)": header, eval numbers (balance, floor, room, target, session N of 10,
                            daily loss used), P&L today / week / since start, position, orders today, trades, days, stats.

No secrets: only whitelisted fields leave the PC (no webhook URLs, no file paths, no keys); error texts are cut to 160
characters with any file path replaced by <path>. The MFFU account name (what NinjaTrader shows) is fine to publish.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
MAX_TRADES = 60
MAX_ORDERS = 40
MAX_BYTES = 48_000                     # the heartbeat is one small git commit: keep "acct" well under 50 KB
DEFAULT_ACCOUNTS = [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval",
                     "source": "pc"}]
CLOUD_PAPER = {"id": "cloud_paper", "name": "Paper (cloud)", "firm": "Cloud monitor", "plan": "MFFU 50K rules", "kind": "paper",
               "source": "cloud"}
PLAN_50K = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0, "dll": 1000.0, "sessions": 10}
_PATH = re.compile(r"([A-Za-z]:[\\/][^;,'\"()\r\n]*[\\/][^\s;,'\"()\\/]*|[A-Za-z]:[\\/][^\s;,'\"()]*"
                   r"|/(?:home|Users|tmp|root|mnt|var)/[^\s;,'\"()]*)")


# ---------------------------------------------------------------------------------------------------------------- helpers
def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    """The trading day of a unix time (18:00 ET starts the next day), the same rule as engine/live.trading_day."""
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _f(v, d=2):
    try:
        x = float(v)
        return None if x != x else round(x, d)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def clean_text(s, n=160):
    """An error / note for the page: file paths replaced, one line, at most n characters."""
    if s is None:
        return None
    s = _PATH.sub("<path>", str(s)).replace("\r", " ").replace("\n", " ").strip()
    return s[:n]


def accounts_cfg(lm: dict | None) -> list:
    """live_model.json "accounts" (top level, or lit_sizing.accounts): the accounts the Accounts page shows, each
    {id, name, firm, plan, kind eval|funded|paper, source pc|cloud}. Default: the MFFU 50K eval on the PC bot."""
    lm = lm or {}
    rows = lm.get("accounts")
    if rows is None:
        rows = (lm.get("lit_sizing") or {}).get("accounts")
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("id"):
            out.append({k: str(r[k]) for k in ("id", "name", "firm", "plan", "kind", "source", "match") if r.get(k) is not None})
    return out or [dict(a) for a in DEFAULT_ACCOUNTS]


# ---------------------------------------------------------------------------------------------------------------- PC side
def _acct_kind(bot) -> dict:
    cfg = getattr(bot, "cfg", None) or {}
    ad = getattr(bot, "adapter", None)
    adapter = str(cfg.get("adapter") or getattr(ad, "name", None) or "paper")
    name = getattr(ad, "account", None)
    env = getattr(ad, "env", None)
    if adapter == "paper":
        kind, label, name = "paper", "PAPER", "Paper (PC)"
    elif env == "live" or (adapter == "traderspost"):
        kind, label = "live", "LIVE ACCOUNT"
    else:
        kind, label = "sim", "SIM"
    if not name and adapter == "ninjatrader":
        name = cfg.get("nt_account") or os.environ.get("NINJATRADER_ACCOUNT") or "Sim101"
    return {"name": clean_text(name or adapter, 60), "adapter": adapter, "kind": kind, "label": label,
            "disabled": clean_text(getattr(ad, "disabled", None), 120)}


def _leg_for(ad, entry_t):
    for lg in list(getattr(ad, "legs", None) or []):
        if entry_t is None or _i(lg.get("entry_t")) == _i(entry_t):
            return lg
    return None


def _position(bot) -> dict | None:
    st = getattr(bot, "state", None) or {}
    open_t = getattr(bot, "_open_routed", None)
    if open_t is None:
        return None
    pos = st.get("position")
    if not pos or _i(pos.get("entry_t")) != _i(open_t):
        en = st.get("enter_now")                      # LIT: routed on the 1m CISD close, the model shows it after the fill bar
        pos = en if en and _i(en.get("entry_t")) == _i(open_t) else None
    ad = getattr(bot, "adapter", None)
    lg = _leg_for(ad, open_t)
    if pos is None and lg is None:
        return {"entry_t": int(open_t), "qty": _i(getattr(bot, "_open_qty", None)), "side": None, "note": "routed, model view pending"}
    d = int((pos or {}).get("dir") or (lg or {}).get("dir") or 1)
    stop_now = None
    try:
        stop_now = bot._broker_stop(open_t)
    except Exception:
        pass
    if lg and lg.get("stop") is not None:
        stop_now = lg.get("stop")
    if stop_now is None and pos:
        stop_now = pos.get("stop")
    entry = (lg or {}).get("fill_px") or (pos or {}).get("entry")
    model_entry = (pos or {}).get("entry")
    stop0 = (pos or {}).get("stop0") or (lg or {}).get("stop0") or stop_now
    be = bool((pos or {}).get("be")) or (stop_now is not None and entry is not None and (float(stop_now) - float(entry)) * d >= 0)
    return {"entry_t": int(open_t), "side": "LONG" if d == 1 else "SHORT", "dir": d,
            "qty": _i(getattr(bot, "_open_qty", None) or (lg or {}).get("filled") or (pos or {}).get("qty")),
            "entry": _f(entry), "model_entry": _f(model_entry), "stop": _f(stop_now), "stop0": _f(stop0),
            "target": _f((lg or {}).get("target") or (pos or {}).get("target")), "be": be,
            "risk_pts": _f((pos or {}).get("risk_pts")), "target_label": clean_text((pos or {}).get("target_label"), 60),
            "unrealized": _f((pos or {}).get("unrealized")), "unrealized_r": _f((pos or {}).get("unrealized_r"), 3),
            "broker": None if not lg else {"status": lg.get("status"), "filled": _i(lg.get("filled")),
                                           "instrument": clean_text(lg.get("instrument"), 30)},
            "size_why": [clean_text(x, 80) for x in ((pos or {}).get("size_why") or [])][:4]}


def order_row(r: dict) -> dict:
    """One ledger row (engine/live.py _route) as a timeline row: whitelisted fields only."""
    res = r.get("result") or {}
    side = str(r.get("side") or "")
    row = {"t": _i(r.get("t")), "side": side, "qty": _i(r.get("qty")), "entry_t": _i(r.get("entry_t")),
           "ok": bool(res.get("ok")) if "ok" in res else None}
    for k in ("entry", "stop", "target", "pnl"):
        if r.get(k) is not None:
            row[k] = _f(r.get(k))
    if r.get("reason"):
        row["reason"] = clean_text(r.get("reason"), 40)
    if r.get("exit_t"):
        row["exit_t"] = _i(r.get("exit_t"))
    legs = res.get("legs") if isinstance(res.get("legs"), list) else []
    fills = [lg for lg in legs if isinstance(lg, dict) and lg.get("filled")]
    if fills:
        q = sum(int(lg.get("filled") or 0) for lg in fills)
        px = sum(float(lg.get("fill_px") or 0) * int(lg.get("filled") or 0) for lg in fills) / max(1, q)
        row["filled"], row["fill_px"] = q, round(px, 2)
        row["bracket"] = all(lg.get("ok") for lg in fills)
    elif side in ("buy", "sell") and res.get("ok") and res.get("adapter") in (None, "paper"):
        row["filled"], row["fill_px"], row["bracket"] = row.get("qty"), row.get("entry"), True   # paper: filled at the model price
    if res.get("error"):
        row["error"] = clean_text(res.get("error"))
    if res.get("note") and not fills:
        row["note"] = clean_text(res.get("note"), 80)
    return row


def _journal_trades(path=None, since_t=0) -> list:
    try:
        from .lit_learn import JOURNAL_PATH, load_journal
        recs = load_journal(path or JOURNAL_PATH)
    except Exception:
        return []
    out = []
    for r in recs:
        if r.get("source") != "pc" or not r.get("entry_t") or int(r["entry_t"]) < since_t:
            continue
        out.append(trade_row({"day": r.get("day"), "entry_t": r.get("entry_t"), "exit_t": r.get("exit_t"), "side": r.get("side"),
                              "qty": r.get("qty"), "entry": r.get("entry_px"), "stop": r.get("stop_px"), "target": r.get("target_px"),
                              "exit_px": r.get("exit_px"), "exit": r.get("exit"), "r": r.get("r"), "pnl": r.get("pnl"),
                              "risk_pts": r.get("risk_pts"), "swept": r.get("swept"), "grade": r.get("grade"), "cause": r.get("cause"),
                              "mfe": r.get("mfe")}))
    return out


def trade_row(t: dict) -> dict:
    """A closed trade for the page: the same keys for the PC and the cloud paper account."""
    side = t.get("side") or ("LONG" if int(t.get("dir") or 1) == 1 else "SHORT")
    row = {"day": str(t.get("day") or (trading_day(t["entry_t"]) if t.get("entry_t") else "")), "entry_t": _i(t.get("entry_t")),
           "exit_t": _i(t.get("exit_t")), "side": side, "qty": _i(t.get("qty")), "entry": _f(t.get("entry")), "stop": _f(t.get("stop")),
           "target": _f(t.get("target")), "exit_px": _f(t.get("exit_px")), "exit": clean_text(t.get("exit"), 30),
           "r": _f(t.get("r"), 3), "pnl": _f(t.get("pnl")), "risk_pts": _f(t.get("risk_pts"))}
    if t.get("swept"):
        row["swept"] = [clean_text(x, 40) for x in list(t["swept"])[:6]]
    for k in ("grade", "cause", "trigger"):
        if t.get(k):
            row[k] = clean_text(t[k], 60)
    if t.get("mfe") is not None:
        row["mfe"] = _f(t.get("mfe"), 2)
    return {k: v for k, v in row.items() if v is not None}


def _ledger_trades(ledger: list) -> list:
    """Closed routed trades of the ledger (today's): the entry row (side, qty, prices) + its exit row (reason, $)."""
    ent = {}
    for r in ledger:
        if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None and (r.get("result") or {}).get("ok") is not False:
            ent[int(r["entry_t"])] = r
    out = []
    for r in ledger:
        if r.get("side") != "exit" or r.get("entry_t") is None or int(r["entry_t"]) not in ent:
            continue
        e = ent[int(r["entry_t"])]
        orow = order_row(e)
        d = 1 if e.get("side") == "buy" else -1
        entry = orow.get("fill_px") or e.get("entry")
        risk = abs(float(entry or 0) - float(e.get("stop") or 0)) if entry and e.get("stop") else None
        pnl = _f(r.get("pnl"))
        qty = _i(r.get("qty") or e.get("qty"))
        rr = (pnl / (risk * 2.0 * qty)) if (pnl is not None and risk and qty) else None
        out.append(trade_row({"entry_t": e["entry_t"], "exit_t": r.get("exit_t") or r.get("t"), "side": "LONG" if d == 1 else "SHORT",
                              "qty": qty, "entry": entry, "stop": e.get("stop"), "target": e.get("target"), "exit": r.get("reason"),
                              "pnl": pnl, "r": rr, "risk_pts": risk}))
    return out


def _state_file(bot):
    p = getattr(bot, "state_path", None)
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def pc_activity(bot, now=None, journal_path=None, max_trades=MAX_TRADES, max_orders=MAX_ORDERS) -> dict:
    """The heartbeat's "acct" block (see the module doc). Never raises: on any error it returns {"v", "error"}."""
    try:
        now = int(now or time.time())
        cfg = getattr(bot, "cfg", None) or {}
        ledger = list(getattr(bot, "ledger", None) or [])
        eval_days, start = {}, ""
        if cfg:
            try:
                eval_days = dict(bot.eval_days())
                start = bot.eval_start()
            except Exception:
                eval_days = {}
        if not cfg or not eval_days:                 # bot not started (yet): the last saved state
            s = _state_file(bot)
            if not cfg and s.get("day") == trading_day(now):
                ledger = list(s.get("ledger") or [])
            eval_days = eval_days or {str(k): float(v) for k, v in (s.get("eval_days") or {}).items()}
        today = trading_day(now)
        orders = [order_row(r) for r in ledger if r.get("t") and trading_day(r["t"]) == today][-max_orders:]
        start_t = 0
        if start:
            try:
                start_t = int(_dt.datetime.fromisoformat(start + "T00:00:00").timestamp()) - 86400
            except ValueError:
                start_t = 0
        trades = {t["entry_t"]: t for t in _journal_trades(journal_path, 0) if t.get("entry_t")}
        for t in _ledger_trades(ledger):
            trades.setdefault(t["entry_t"], t)
        trades = sorted(trades.values(), key=lambda t: t.get("entry_t") or 0)[-max_trades:]
        out = {"v": VERSION, "t": now, "account": _acct_kind(bot), "running": bool(getattr(bot, "running", False)),
               "kill": bool(getattr(bot, "kill", False)), "model": cfg.get("model"),
               "eval": {"start": start or None, "days": {str(k): round(float(v), 2) for k, v in sorted(eval_days.items())}},
               "position": _position(bot), "orders": orders, "trades": trades,
               "day_pnl": round(sum(float(r.get("pnl") or 0) for r in ledger if r.get("side") == "exit" and r.get("t")
                                    and trading_day(r["t"]) == today), 2),
               "since_t": start_t or None}
        return fit(out)
    except Exception as e:
        return {"v": VERSION, "error": f"{e.__class__.__name__}: {clean_text(e, 120)}"}


def fit(acct: dict, max_bytes=MAX_BYTES) -> dict:
    """Trim the oldest trades, then the oldest orders, then the oldest eval days until the JSON fits max_bytes."""
    def size():
        return len(json.dumps(acct, separators=(",", ":"), default=str))
    while size() > max_bytes and len(acct.get("trades") or []) > 5:
        acct["trades"] = acct["trades"][max(1, len(acct["trades"]) // 5):]
        acct["trimmed"] = True
    while size() > max_bytes and len(acct.get("orders") or []) > 5:
        acct["orders"] = acct["orders"][max(1, len(acct["orders"]) // 5):]
        acct["trimmed"] = True
    days = (acct.get("eval") or {}).get("days") or {}
    while size() > max_bytes and len(days) > 30:
        for k in sorted(d for d in days if d != "0000-00-00")[:10]:
            days.pop(k, None)
        acct["trimmed"] = True
    return acct


# ---------------------------------------------------------------------------------------------------------------- cloud side
def _iso_week(day: str) -> str:
    y, w, _ = _dt.date.fromisoformat(day[:10]).isocalendar()
    return f"{y}-W{w:02d}"


def eval_view(days: dict, start: str | None, today: str, now=None, plan=None) -> dict:
    """The eval numbers of one account from its P&L per day (the "0000-00-00" key = P&L before eval_start): balance,
    trailing floor, room, progress, session N of 10, today's daily-loss use. The rules of engine/sizing.mffu_eval."""
    from . import sizing
    P = {**PLAN_50K, **(plan or {})}
    days = {str(k): float(v) for k, v in (days or {}).items()}
    ev = sizing.mffu_eval(days, {k: P[k] for k in ("start", "target", "mll", "lock")})
    sess = sizing.eval_session(start, today) if start else None
    clock = None
    try:
        e = _et(now or time.time())
        over = e.weekday() < 5 and e.hour * 60 + e.minute >= 16 * 60
        clock = sizing.eval_clock(days, start, today, session_over=over)
    except Exception:
        clock = None
    td = round(days.get(today, 0.0), 2)
    target_bal = P["start"] + P["target"]
    return {"start_balance": P["start"], "balance": ev["balance"], "profit": ev["profit"], "to_target": max(0.0, ev["to_target"]),
            "target_balance": target_bal, "floor": ev["trailing_mll"], "room": ev["cushion"], "locked": ev["trailing_mll"] >= P["lock"] - 0.01,
            "mll": P["mll"], "dll": P["dll"], "dll_used": round(max(0.0, -td), 2), "today": td,
            "progress": round(max(0.0, min(1.0, ev["profit"] / P["target"])), 4),
            "session": sess, "sessions": P["sessions"], "start": start, "prior": round(days.get("0000-00-00", 0.0), 2),
            "status": (clock or {}).get("status"), "clock_text": (clock or {}).get("text")}


def stats(trades: list, days: dict) -> dict:
    """Win %, average win / loss $, PF, best / worst day, streaks: the closed trades and the P&L per day."""
    pn = [float(t.get("pnl") or 0) for t in trades if t.get("pnl") is not None]
    wins, losses = [x for x in pn if x > 0], [x for x in pn if x < 0]
    gw, gl = sum(wins), -sum(losses)
    dd = {d: v for d, v in (days or {}).items() if d != "0000-00-00"}
    best = max(dd.items(), key=lambda kv: kv[1]) if dd else None
    worst = min(dd.items(), key=lambda kv: kv[1]) if dd else None
    cur, cur_k, best_w, run = 0, None, 0, 0
    for x in pn:
        k = "W" if x > 0 else "L" if x < 0 else "B"
        cur = cur + 1 if k == cur_k else 1
        cur_k = k
        run = run + 1 if k == "W" else 0
        best_w = max(best_w, run)
    eq, peak, mdd = 0.0, 0.0, 0.0
    for x in pn:
        eq += x
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return {"n": len(pn), "wins": len(wins), "losses": len(losses), "win_pct": round(len(wins) / len(pn) * 100, 1) if pn else None,
            "avg_win": round(gw / len(wins), 2) if wins else None, "avg_loss": round(-gl / len(losses), 2) if losses else None,
            "pf": round(gw / gl, 2) if gl else None, "net": round(sum(pn), 2),
            "best_day": [best[0], round(best[1], 2)] if best else None, "worst_day": [worst[0], round(worst[1], 2)] if worst else None,
            "streak": {"kind": cur_k, "n": cur} if cur_k else None, "best_win_streak": best_w, "max_dd": round(mdd, 2)}


def _pnl_views(days: dict, today: str) -> dict:
    wk = _iso_week(today)
    real = {d: v for d, v in days.items() if d != "0000-00-00"}
    return {"today": round(real.get(today, 0.0), 2), "week": round(sum(v for d, v in real.items() if _iso_week(d) == wk), 2),
            "since_start": round(sum(days.values()), 2), "traded": round(sum(real.values()), 2)}


def _pc_section(meta: dict, pc: dict, lm: dict, today: str, now: int) -> dict:
    acct = (pc or {}).get("acct") if isinstance((pc or {}).get("acct"), dict) else None
    hb_t = _i((pc or {}).get("t"))
    age = max(0, now - hb_t) if hb_t else None
    conn = {"present": bool((pc or {}).get("present")), "t": hb_t, "age_s": age, "silent": bool((pc or {}).get("silent")),
            "running": (pc or {}).get("running"), "host": clean_text((pc or {}).get("host"), 40), "adapter": (pc or {}).get("adapter"),
            "connected": bool((pc or {}).get("present")) and age is not None and age < 20 * 60,
            "has_detail": bool(acct and not acct.get("error")), "error": (acct or {}).get("error")}
    ls = (lm or {}).get("lit_sizing") or {}
    start = ((acct or {}).get("eval") or {}).get("start") or ls.get("eval_start")
    days = dict(((acct or {}).get("eval") or {}).get("days") or {})
    if not acct and ls.get("eval_prior_pnl"):
        days["0000-00-00"] = float(ls["eval_prior_pnl"])
    trades = list((acct or {}).get("trades") or [])
    if start:
        trades = [t for t in trades if str(t.get("day") or "") >= str(start)] or trades
    ak = (acct or {}).get("account") or {}
    adapter = ak.get("adapter") or (pc or {}).get("adapter")
    badge = ak.get("label") or ("PAPER" if adapter in (None, "paper") else "SIM")
    pos = (acct or {}).get("position")
    if pos and pos.get("note"):
        pos = {**pos}
    return {**meta, "badge": "LIVE" if badge == "LIVE ACCOUNT" else badge, "broker_account": ak.get("name"), "adapter": adapter,
            "conn": conn, "eval": eval_view(days, start, today, now) if meta.get("kind") in ("eval", "funded") else None,
            "pnl": _pnl_views(days, today), "position": pos, "orders": list((acct or {}).get("orders") or []),
            "trades": trades, "days": [[d, round(v, 2)] for d, v in sorted(days.items()) if d != "0000-00-00"],
            "stats": stats(trades, days), "kill": bool((acct or {}).get("kill")), "running": (acct or {}).get("running")}


def _cloud_section(meta: dict, state: dict, lm: dict, today: str, now: int) -> dict:
    led = state.get("ledger") or {}
    rows = []
    for k, v in led.items():
        if not isinstance(v, dict):
            continue
        et_ = _i(k) if str(k).isdigit() else _i(v.get("entry_t"))
        rows.append((et_, v))
    rows.sort(key=lambda kv: kv[0] or 0)
    ls = (lm or {}).get("lit_sizing") or {}
    start = ls.get("eval_start")
    trades, days, open_rows = [], {}, []
    for et_, v in rows:
        if v.get("exit") in (None, "OPEN") or not v.get("exit_ts"):
            open_rows.append((et_, v))
            continue
        if v.get("taken") is False:
            continue
        trades.append(trade_row({"day": v.get("day"), "entry_t": et_, "exit_t": v.get("exit_ts"), "side": v.get("side"),
                                 "qty": v.get("qty"), "entry": v.get("entry_px"), "stop": v.get("stop_px"), "target": v.get("target_px"),
                                 "exit_px": v.get("exit_px"), "exit": v.get("exit"), "r": v.get("R"), "pnl": v.get("usd"),
                                 "risk_pts": v.get("risk_pts"), "grade": v.get("grade"), "trigger": v.get("trigger")}))
        if not start or str(v.get("day")) >= str(start):
            days[v["day"]] = round(days.get(v["day"], 0.0) + float(v.get("usd") or 0), 2)
    if start and ls.get("eval_prior_pnl"):
        days["0000-00-00"] = float(ls["eval_prior_pnl"])
    eval_trades = [t for t in trades if not start or t["day"] >= str(start)]
    pos = state.get("position")
    position = None
    if pos:
        d = int(pos.get("dir") or 1)
        lr = dict(led.get(str(pos.get("entry_t"))) or {})
        position = {"entry_t": _i(pos.get("entry_t")), "side": "LONG" if d == 1 else "SHORT", "dir": d,
                    "qty": _i(lr.get("qty") or pos.get("qty")), "entry": _f(pos.get("entry")), "stop": _f(pos.get("stop")),
                    "stop0": _f(pos.get("stop0") or pos.get("stop")), "target": _f(pos.get("target")),
                    "be": bool(pos.get("be")), "risk_pts": _f(pos.get("risk_pts")), "target_label": clean_text(pos.get("target_label"), 60),
                    "unrealized_r": _f(pos.get("unrealized_r"), 3)}
    orders = []
    for e in state.get("events") or []:
        if e.get("type") in ("entry", "exit") and trading_day(e["t"]) == today:
            orders.append({"t": _i(e["t"]), "side": e["type"], "text": clean_text(e.get("text"), 200)})
    return {**meta, "badge": "PAPER", "broker_account": None, "adapter": "cloud",
            "conn": {"present": True, "t": _i(state.get("last_run")), "age_s": max(0, now - int(state.get("last_run") or now)),
                     "connected": True, "has_detail": True, "silent": False, "running": True, "host": "GitHub Actions"},
            "eval": eval_view(days, start, today, now), "pnl": _pnl_views(days, today), "position": position, "orders": orders,
            "trades": trades[-200:], "days": [[d, v] for d, v in sorted(days.items()) if d != "0000-00-00"],
            "stats": stats(eval_trades, days), "kill": False, "running": True}


def build_accounts(state: dict, lm: dict | None = None, now=None) -> list:
    """data.json "accounts": one section per configured account (PC source: the heartbeat's "acct"), then the cloud paper
    ledger as "Paper (cloud)". Never raises; a broken section becomes {"id", "name", "error"}."""
    state = state or {}
    now = int(now or state.get("last_run") or time.time())
    today = trading_day(now)
    out = []
    for meta in accounts_cfg(lm) + [dict(CLOUD_PAPER)]:
        try:
            if meta.get("source") == "cloud":
                out.append(_cloud_section(meta, state, lm or {}, today, now))
            else:
                out.append(_pc_section(meta, state.get("pc") or {}, lm or {}, today, now))
        except Exception as e:
            out.append({**meta, "error": f"{e.__class__.__name__}: {clean_text(e, 120)}"})
    return out
