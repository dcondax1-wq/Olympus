"""Execution-quality tracker: every $ the live eval loses (or gains) to execution, against the LIT backtest on the same bars.

For each trading day the PC bot was around, the LIT backtest decision for that day is re-run on the same bars
(engine/lit_live.run, the live loop's own executor: data/NQ_5m.csv + data/NQ_1m.csv + the PC's NinjaTrader archive
data/nt_bars/) and compared with what was really routed and filled:

  matched trade   signal time (1m CISD close = the backtest's entry bar open), routed time and latency, entry price backtest
                  vs fill (ticks, $), stop / target placement vs the backtest, breakeven move time vs the backtest's (bar
                  close after +1R), exit price and reason vs the backtest, qty routed vs the backtest's qty, and the
                  execution $ = real P&L - the backtest's P&L at the routed qty (both with $1.90 a micro).
  missed trade    the backtest traded, the bot did not: why (PC off, feed stale, kill switch, refused by the broker, sizer
                  held it back, seen late), and the backtest $ not taken. pc_on says whether the bot was running then.
  extra trade     the bot traded, the backtest (on today's bars) did not: its real $.
Totals: slippage $ per trade and per month, execution $, missed-trade $, extra-trade $.

Sources (read-only; nothing here starts, arms, routes or changes an order):
  * the bot's ledger (engine/live.LiveBot.ledger / data/live_state.json "ledger"). live_state.json holds TODAY only, so
    collect() copies every row it sees into logs/exec_audit/ledger.jsonl (append-only, de-duplicated).
  * the NinjaTrader adapter's legs (bot.adapter.legs + history, data/ninjatrader_state.json): entry fill price / time.
  * NinjaTrader's outgoing\\ order states, archived by tools/fill_audit.archive into logs/exec_audit/orders.jsonl:
    stop / target fill prices (a CLOSEPOSITION exit has no price there: the model exit is used and flagged).
  * the LIT learning journal (data/lit_journal.jsonl, source "pc"): routed trades of days before the archive started.
  * logs/exec_audit/notes.json: why the bot held an entry back (its own log: "NOT routed: feed stale", sizer, late) and
    uptime samples (running / feed blocked / kill), so a missed trade can say "PC off" vs "feed stale".
Outputs: logs/exec_audit/report.json (every row), logs/exec_audit/summary.json (small; the heartbeat carries it as "exec",
the PC dashboard /api/next/pc/execution and the phone app's data.json "exec" show it).

Phone push (engine/push.pc_notify, kind "pc"): a fill more than 4 ticks worse than the backtest (entry or exit), and a
backtest trade missed while the PC bot was running (at once from the bot's own blocked entries, and again from the replay).

  python -m engine.fill_audit report [--days N]     # collect + replay + write report / summary, print the summary
  python -m engine.fill_audit selftest              # see tests/test_fill_audit.py
Slippage is in ticks (0.25 pt), positive = worse for us. The backtest's own prices already include 1 tick each way.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
STORE = os.path.join(ROOT, "logs", "exec_audit")          # logs/ is gitignored: machine-local
ET = ZoneInfo("America/New_York")
TICK, PV, COMM = 0.25, 2.0, 1.90
TICK_USD = TICK * PV                                         # $0.50 a tick a micro
SLIP_ALERT_TICKS = 4.0
ALERT_MAX_AGE_S = 2 * 86400                                  # never push about something older than this
MAX_DAYS = 45
UPTIME_EVERY_S = 240
VERSION = 1


def _p(store, name):
    return os.path.join(store or STORE, name)


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    """18:00 ET starts the next trading day (engine/live.trading_day)."""
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _hm(t):
    return _et(t).strftime("%H:%M") if t else "--:--"


def _ts(day: str, hh: int, mm: int = 0) -> int:
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ET).timestamp())


def _f(v, d=2):
    try:
        return None if v is None else round(float(v), d)
    except (TypeError, ValueError):
        return None


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    os.replace(tmp, path)


def _jl_read(path) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        continue
    except FileNotFoundError:
        pass
    return out


def _jl_append(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


# ================================================================================================ collect (PC side)
def _rkey(r) -> str:
    return json.dumps([r.get("t"), r.get("side"), r.get("entry_t"), r.get("stop"), r.get("reason")], default=str)


def _leg_view(lg) -> dict:
    keep = ("instrument", "qty", "dir", "entry_t", "stop", "stop0", "target", "entry_id", "stop_id", "target_id", "status",
            "filled", "fill_px", "fill_mtime", "sent_at", "bracket_qty", "closed", "closed_at")
    return {k: lg.get(k) for k in keep if k in lg}


def _block_reason(bot, entry_t) -> str:
    """The bot's own log line for an entry it held back (engine/live.py _route_signals / _equity_qty)."""
    hm = _hm(entry_t)
    for e in list(getattr(bot, "log", None) or []):
        txt = str(e.get("text") or "")
        if f"Entry at {hm} ET NOT " in txt:
            why = txt.split("NOT routed:", 1)[-1] if "NOT routed:" in txt else txt.split("NOT traded:", 1)[-1]
            return "feed stale" if "feed stale" in why.lower() else why.strip()[:160]
    return "held back by the bot (see the bot log)"


def collect(bot=None, state_path=None, nt_state_path=None, store=None, now=None, nt_folder=None) -> dict:
    """Copy what the PC bot knows right now into the audit store (ledger rows, NinjaTrader legs and order states, held-back
    entries, an uptime sample). Cheap; call it every minute. Never raises."""
    now = int(now or time.time())
    out = {"ledger": 0, "legs": 0, "orders": 0, "notes": 0}
    try:
        cfg = getattr(bot, "cfg", None) or {}
        st = _read_json(state_path or os.path.join(DATA, "live_state.json"), {}) or {}
        ledger = list(getattr(bot, "ledger", None) or []) if cfg else list(st.get("ledger") or [])
        adapter = cfg.get("adapter") or st.get("adapter") or "paper"
        # ---- ledger rows (live_state.json keeps today only)
        lp = _p(store, "ledger.jsonl")
        have = {_rkey(r) for r in _jl_read(lp)}
        new = []
        for r in ledger:
            if not isinstance(r, dict) or r.get("t") is None:
                continue
            k = _rkey(r)
            if k not in have:
                have.add(k)
                new.append({**r, "adapter": r.get("adapter") or adapter})
        _jl_append(lp, new)
        out["ledger"] = len(new)
        # ---- NinjaTrader legs: entry fills (the adapter in memory, else its state file)
        ad = getattr(bot, "adapter", None)
        legs = list(getattr(ad, "legs", None) or []) + list(getattr(ad, "history", None) or [])
        if not legs:
            ns = _read_json(nt_state_path or os.path.join(DATA, "ninjatrader_state.json"), {}) or {}
            legs = list(ns.get("legs") or [])
        gp = _p(store, "legs.json")
        L = _read_json(gp, {}) or {}
        n = 0
        for lg in legs:
            if not isinstance(lg, dict) or not lg.get("entry_id"):
                continue
            v = _leg_view(lg)
            old = L.get(lg["entry_id"]) or {}
            merged = {**old, **{k: x for k, x in v.items() if x is not None}}
            if merged != old:
                L[lg["entry_id"]] = merged
                n += 1
        if n:
            _write_json(gp, L)
        out["legs"] = n
        # ---- NinjaTrader outgoing\ order states (stop / target fills); NinjaTrader wipes the folder on a restart
        try:
            from engine.ninjatrader import default_folder
            folder = nt_folder or getattr(ad, "folder", None) or default_folder()
            if folder and os.path.isdir(os.path.join(folder, "outgoing")):
                import contextlib
                import io
                from tools import fill_audit as tfa
                with contextlib.redirect_stdout(io.StringIO()):
                    out["orders"] = tfa.archive(folder=folder, path=_p(store, "orders.jsonl"))
        except Exception:
            pass
        # ---- notes: held-back entries with the bot's reason, refused entries, uptime samples
        npth = _p(store, "notes.json")
        N = _read_json(npth, {}) or {}
        N.setdefault("blocked", {})
        N.setdefault("uptime", [])
        changed = False
        for et_ in sorted(getattr(bot, "_blocked_entries", None) or ()):
            k = str(int(et_))
            if k not in N["blocked"]:
                N["blocked"][k] = {"reason": _block_reason(bot, et_), "t": now, "running": bool(getattr(bot, "running", False))}
                changed = True
                out["notes"] += 1
        if bot is not None:
            h = getattr(bot, "health", None) or {}
            smp = {"t": now, "running": bool(getattr(bot, "running", False)), "blocked": bool(h.get("entries_blocked")),
                   "feed_block": h.get("feed_block"), "kill": bool(getattr(bot, "kill", False)), "adapter": adapter}
            last = N["uptime"][-1] if N["uptime"] else None
            if last is None or now - int(last["t"]) >= UPTIME_EVERY_S or any(last.get(x) != smp[x] for x in ("running", "blocked", "kill")):
                N["uptime"].append(smp)
                N["uptime"] = [u for u in N["uptime"] if int(u["t"]) >= now - (MAX_DAYS + 7) * 86400]
                changed = True
        if changed:
            _write_json(npth, N)
    except Exception as e:
        out["error"] = f"{e.__class__.__name__}: {e}"
    return out


# ================================================================================================ live trades
def _legs_by_entry(store) -> dict:
    out = {}
    for lg in (_read_json(_p(store, "legs.json"), {}) or {}).values():
        if lg.get("entry_t") is not None:
            out.setdefault(int(lg["entry_t"]), []).append(lg)
    return out


def _orders_by_entry(store) -> dict:
    try:
        from tools import fill_audit as tfa
        rows = tfa.load_archive(_p(store, "orders.jsonl"))
    except Exception:
        return {}
    out = {}
    for oid, st in rows.items():
        p = tfa.parse_oid(oid)
        if p:
            out.setdefault(p["entry_t"], {})[p["leg"]] = {**st, "id": oid}
    return out


def _vwap(pairs):
    q = sum(n for _, n in pairs)
    return (sum(px * n for px, n in pairs) / q) if q else None


def live_trades(store=None, journal_path=None) -> dict:
    """entry_t -> what the bot routed and what the broker filled (ledger archive + NinjaTrader legs / orders + journal)."""
    rows = _jl_read(_p(store, "ledger.jsonl"))
    legs, orders = _legs_by_entry(store), _orders_by_entry(store)
    by = {}
    for r in rows:
        if r.get("entry_t") is None:
            continue
        x = by.setdefault(int(r["entry_t"]), {"entries": [], "mods": [], "exits": []})
        s = r.get("side")
        (x["entries"] if s in ("buy", "sell") else x["mods"] if s == "modify" else x["exits"] if s == "exit" else []).append(r)
    jr = {}
    try:
        from engine.lit_learn import JOURNAL_PATH, load_journal
        for j in load_journal(journal_path or JOURNAL_PATH):
            if j.get("source") == "pc" and j.get("entry_t"):
                jr[int(j["entry_t"])] = j
    except Exception:
        pass
    out = {}
    for et_, x in by.items():
        if not x["entries"]:
            continue
        oks = [e for e in x["entries"] if (e.get("result") or {}).get("ok") is not False]
        e = (oks or x["entries"])[-1]
        res = e.get("result") or {}
        d = 1 if e.get("side") == "buy" else -1
        adapter = res.get("adapter") or e.get("adapter") or "paper"
        rec = {"entry_t": et_, "day": trading_day(et_), "dir": d, "qty": int(e.get("qty") or 0), "t_route": int(e["t"]),
               "ok": bool(oks), "error": None if oks else str(res.get("error") or "refused")[:200], "adapter": adapter,
               "model_entry": _f(e.get("entry")), "stop": _f(e.get("stop")), "target": _f(e.get("target")),
               "fill_entry": None, "t_fill": None, "fill_src": None, "be_t": None, "be_stop": None,
               "exit_px": None, "exit_kind": None, "exit_t": None, "exit_src": None, "model_exit": None, "model_pnl": None}
        # entry fill: the route result's legs, the adapter's legs, the archived order state; paper fills at the model price
        rl = [lg for lg in (res.get("legs") or []) if isinstance(lg, dict) and lg.get("filled") and lg.get("fill_px")]
        al = [lg for lg in legs.get(et_, []) if lg.get("filled") and lg.get("fill_px")]
        ol = (orders.get(et_) or {}).get("entry")
        if rl:
            rec["fill_entry"], rec["fill_src"] = _vwap([(float(lg["fill_px"]), int(lg["filled"])) for lg in rl]), "broker"
            rec["qty"] = sum(int(lg["filled"]) for lg in rl)
        elif al:
            rec["fill_entry"], rec["fill_src"] = _vwap([(float(lg["fill_px"]), int(lg["filled"])) for lg in al]), "broker"
            rec["qty"] = sum(int(lg["filled"]) for lg in al)
        elif ol and ol.get("filled"):
            rec["fill_entry"], rec["fill_src"] = float(ol["avg"]), "broker"
        elif oks and adapter == "paper":
            rec["fill_entry"], rec["fill_src"] = rec["model_entry"], "paper"
        tf = [lg.get("fill_mtime") for lg in al if lg.get("fill_mtime")] or ([ol.get("mtime")] if ol and ol.get("mtime") else [])
        rec["t_fill"] = _f(min(tf), 1) if tf else (rec["t_route"] if rec["fill_src"] == "paper" else None)
        bm = [m for m in x["mods"] if (m.get("result") or {}).get("ok") is not False]
        if bm:
            rec["be_t"], rec["be_stop"] = int(bm[0]["t"]), _f(bm[0].get("stop"))
        if x["exits"]:
            xr = x["exits"][-1]
            rec["model_exit"], rec["model_pnl"] = xr.get("reason"), _f(xr.get("pnl"))
            rec["exit_t"] = int(xr.get("exit_t") or xr["t"])
        # exit fill: the stop or target order filled at the broker
        oo = orders.get(et_) or {}
        for leg, kind in (("stop", "STOP"), ("target", "TARGET")):
            o = oo.get(leg)
            if o and o.get("state") == "FILLED" and o.get("avg"):
                rec["exit_px"], rec["exit_src"] = float(o["avg"]), "broker"
                rec["exit_kind"] = "BE" if (kind == "STOP" and rec["be_t"]) else kind
                rec["exit_t"] = int(o.get("mtime") or rec["exit_t"] or 0) or rec["exit_t"]
        j = jr.get(et_)
        if rec["exit_px"] is None and j and j.get("exit_px") is not None:
            # paper: the model's exit is the fill; a broker CLOSEPOSITION has no price in outgoing\ (flagged unpriced)
            rec["exit_px"], rec["exit_kind"] = float(j["exit_px"]), str(j.get("exit") or rec["model_exit"] or "")
            rec["exit_src"] = "paper" if adapter == "paper" else "model (broker close not priced)"
            rec["exit_t"] = rec["exit_t"] or j.get("exit_t")
        if rec["exit_kind"] is None and rec["model_exit"]:
            rec["exit_kind"] = "BE" if rec["model_exit"] == "BE" else rec["model_exit"]
        out[et_] = rec
    # journal-only trades (routed before the ledger archive existed): model prices, flagged
    for et_, j in jr.items():
        if et_ in out:
            continue
        d = 1 if str(j.get("side", "")).upper() == "LONG" or j.get("dir") == 1 else -1
        out[et_] = {"entry_t": et_, "day": j.get("day") or trading_day(et_), "dir": d, "qty": int(j.get("qty") or 0), "t_route": None,
                    "ok": True, "error": None, "adapter": "journal", "model_entry": _f(j.get("entry_px")), "stop": _f(j.get("stop_px")),
                    "target": _f(j.get("target_px")), "fill_entry": _f(j.get("entry_px")), "t_fill": None, "fill_src": "journal (model price)",
                    "be_t": None, "be_stop": None, "exit_px": _f(j.get("exit_px")), "exit_kind": j.get("exit"), "exit_t": j.get("exit_t"),
                    "exit_src": "journal (model price)", "model_exit": j.get("exit"), "model_pnl": _f(j.get("pnl"))}
    return out


# ================================================================================================ the backtest of a day
_BARS = {"key": None, "d5": None, "d1": None}


def load_bars(sym="NQ"):
    """5m and 1m bars as the live loop sees them: the TradingView files + the PC's NinjaTrader archive (a roll offset is
    back-adjusted, engine/pcbars.merge_basis). Cached until a file changes."""
    import pandas as pd
    from engine import pcbars
    paths = [os.path.join(DATA, f"{sym}_5m.csv"), os.path.join(DATA, f"{sym}_1m.csv"),
             pcbars.archive_path(sym, "5m"), pcbars.archive_path(sym, "1m")]
    key = tuple(os.path.getmtime(p) if os.path.exists(p) else 0 for p in paths)
    if _BARS["key"] == key:
        return _BARS["d5"], _BARS["d1"]

    def rd(p):
        try:
            return pcbars.tidy(pd.read_csv(p)) if os.path.exists(p) else pcbars.tidy(None)
        except Exception:
            return pcbars.tidy(None)
    d5, _ = pcbars.merge_basis(rd(paths[0]), pcbars.archive_read(sym, "5m"))
    d1, _ = pcbars.merge_basis(rd(paths[1]), pcbars.archive_read(sym, "1m"))
    _BARS.update(key=key, d5=d5, d1=d1)
    return d5, d1


def _params():
    from engine.lab_adapter import live_model
    return dict(live_model().get("lit") or {})


def _phash(P) -> str:
    return hashlib.sha1(json.dumps(P, sort_keys=True, default=str).encode()).hexdigest()[:12]


def replay_day(day: str, d5, d1, P: dict, cache: dict | None = None) -> dict:
    """The LIT backtest's trade(s) of one trading day on these bars: {"trades": [...], "bars": bool, "sig"}. Cached per day
    by the bars it saw (a finished day with the same bars is never re-run)."""
    end = _ts(day, 16, 5)
    t0 = _ts(day, 2, 0) - 8 * 3600
    a1 = d1[(d1["time"] >= t0) & (d1["time"] < end)] if len(d1) else d1
    a5 = d5[(d5["time"] >= t0) & (d5["time"] < end)] if len(d5) else d5
    sig = f"{_phash(P)}:{len(a5)}:{int(a5['time'].max()) if len(a5) else 0}:{len(a1)}:{int(a1['time'].max()) if len(a1) else 0}"
    if cache is not None and (cache.get(day) or {}).get("sig") == sig:
        return cache[day]
    out = {"sig": sig, "trades": [], "bars": bool(len(a5) >= 12), "one_min": bool(len(a1) >= 60)}
    if out["bars"]:
        from engine import lit_live
        try:
            r = lit_live.run(d5[d5["time"] < end], P, one_min=d1[d1["time"] < end] if len(d1) else None, now=end + 300)
            out["trades"] = [_bt_row(t, d1) for t in r["trades"] if t.get("day") == day]
        except Exception as e:
            out["error"] = f"{e.__class__.__name__}: {e}"[:200]
    if cache is not None:
        cache[day] = out
    return out


def _bt_row(t, d1) -> dict:
    row = {k: t.get(k) for k in ("entry_t", "exit_t", "dir", "entry", "exit_price", "stop", "target", "qty", "pnl", "pnl_r",
                                 "exit_reason", "risk_pts", "target_label", "entry_kind")}
    row["be_t"] = _bt_be_time(t, d1)
    return row


def _bt_be_time(t, d1, be_r=1.0):
    """When the backtest moved the stop to breakeven: the close of the first 1m bar that reached +1R after the entry bar."""
    try:
        if d1 is None or not len(d1):
            return None
        d, e, risk = int(t["dir"]), float(t["entry"]), abs(float(t["entry"]) - float(t["stop"]))
        seg = d1[(d1["time"] >= int(t["entry_t"])) & (d1["time"] <= int(t["exit_t"]))]
        lvl = e + d * be_r * risk
        hit = seg[(seg["high"] >= lvl)] if d == 1 else seg[(seg["low"] <= lvl)]
        return int(hit["time"].iloc[0]) + 60 if len(hit) else None
    except Exception:
        return None


# ================================================================================================ compare
def _pc_on(notes, day, t, live_days) -> bool | None:
    """Was the bot running around time t? True / False from the uptime samples; None = no record that day."""
    ups = [u for u in (notes.get("uptime") or []) if trading_day(u["t"]) == day]
    near = [u for u in ups if abs(int(u["t"]) - t) <= 600]
    if near:
        return any(u.get("running") for u in near)
    if ups:
        return False
    return True if day in live_days else None


def _miss_reason(bt, notes, live, pc_on) -> str:
    et_ = int(bt["entry_t"])
    b = (notes.get("blocked") or {}).get(str(et_))
    if live and not live["ok"]:
        return f"refused: {live['error']}"
    if b:
        return b.get("reason") or "held back by the bot"
    ups = [u for u in (notes.get("uptime") or []) if abs(int(u["t"]) - et_) <= 600]
    if any(u.get("kill") for u in ups):
        return "kill switch on"
    if any(u.get("blocked") or u.get("feed_block") for u in ups):
        fb = next((u.get("feed_block") for u in ups if u.get("feed_block")), None)
        return f"feed stale ({fb})" if fb else "feed stale"
    if pc_on is False:
        return "PC bot off"
    if pc_on is None:
        return "PC bot off (no record of the bot that day)"
    return "bot running but did not route it (feed difference or restart; see the bot log)"


def _ticks(a, b, d):
    """(a - b) in ticks in the trade's direction: positive = a is worse for us when a is what we paid / b what we got."""
    return round((a - b) * d / TICK, 2) + 0.0          # + 0.0: no "-0.0"


def compare(bt: dict | None, lv: dict | None, notes: dict | None = None, live_days=()) -> dict:
    """One audit row: matched (both), missed (backtest only) or extra (live only)."""
    notes = notes or {}
    if bt is not None and (lv is None or not lv["ok"]):
        day = trading_day(bt["entry_t"])
        pc_on = _pc_on(notes, day, int(bt["entry_t"]), live_days)
        return {"status": "missed", "day": day, "entry_t": int(bt["entry_t"]), "side": "LONG" if bt["dir"] == 1 else "SHORT",
                "bt_entry": bt["entry"], "bt_stop": bt["stop"], "bt_target": bt["target"], "bt_exit": bt["exit_price"],
                "bt_exit_reason": bt["exit_reason"], "bt_qty": bt["qty"], "bt_pnl": _f(bt["pnl"]), "missed_usd": _f(bt["pnl"]),
                "pc_on": pc_on, "reason": _miss_reason(bt, notes, lv, pc_on)}
    if bt is None:
        d = lv["dir"]
        real = None
        if lv["fill_entry"] is not None and lv["exit_px"] is not None:
            real = round((lv["exit_px"] - lv["fill_entry"]) * d * PV * lv["qty"] - COMM * lv["qty"], 2)
        return {"status": "extra", "day": lv["day"], "entry_t": lv["entry_t"], "side": "LONG" if d == 1 else "SHORT",
                "routed_t": lv["t_route"], "fill_entry": lv["fill_entry"], "live_qty": lv["qty"], "live_exit": lv["exit_px"],
                "live_exit_kind": lv["exit_kind"], "live_pnl": real if real is not None else lv.get("model_pnl"),
                "reason": ("closed by the kill switch: the bot stopped, so its bar archive ends with the backtest's trade still "
                           "open (no backtest exit to compare with)") if str(lv.get("exit_kind") or "").upper() == "KILL SWITCH" else
                          "the backtest on the same bars has no trade here (feed revision, restart, or a different 1m bar)"}
    d = int(bt["dir"])
    q = int(lv["qty"] or 0)
    row = {"status": "matched", "day": lv["day"], "entry_t": int(bt["entry_t"]), "side": "LONG" if d == 1 else "SHORT",
           "signal_t": int(bt["entry_t"]), "routed_t": lv["t_route"], "fill_t": lv["t_fill"],
           "latency_s": (lv["t_route"] - int(bt["entry_t"])) if lv["t_route"] else None,
           "bt_entry": bt["entry"], "fill_entry": lv["fill_entry"], "fill_src": lv["fill_src"],
           "bt_stop": bt["stop"], "live_stop": lv["stop"], "bt_target": bt["target"], "live_target": lv["target"],
           "bt_be_t": bt.get("be_t"), "live_be_t": lv["be_t"],
           "bt_exit": bt["exit_price"], "bt_exit_reason": bt["exit_reason"], "live_exit": lv["exit_px"],
           "live_exit_kind": lv["exit_kind"], "exit_src": lv["exit_src"], "exit_t": lv["exit_t"],
           "bt_qty": int(bt["qty"]), "live_qty": q, "bt_pnl": _f(bt["pnl"]), "notes": []}
    if int(bt["entry_t"]) != lv["entry_t"]:
        row["notes"].append(f"entry time differs: backtest {_hm(bt['entry_t'])}, bot {_hm(lv['entry_t'])} ET")
    if lv["fill_entry"] is not None:
        row["entry_slip_ticks"] = _ticks(lv["fill_entry"], bt["entry"], d)
        row["entry_slip_usd"] = round(-row["entry_slip_ticks"] * TICK_USD * q, 2) + 0.0      # P&L effect: negative = lost
    if lv["stop"] is not None:
        row["stop_diff_ticks"] = _ticks(bt["stop"], lv["stop"], d)        # positive = the live stop sits closer (tighter)
    if lv["target"] is not None:
        row["target_diff_ticks"] = _ticks(bt["target"], lv["target"], d)  # positive = the live target is nearer
    if row["bt_be_t"] and row["live_be_t"]:
        row["be_delay_s"] = int(row["live_be_t"] - row["bt_be_t"])
    elif row["bt_be_t"] and not row["live_be_t"] and lv["exit_t"] and lv["exit_t"] > row["bt_be_t"]:
        row["notes"].append("the backtest moved the stop to breakeven; the bot's move is not in the ledger")
    norm = lambda s: {"EOD": "TIME", "TIME SAFETY": "TIME"}.get(str(s or "").upper(), str(s or "").upper())
    same_exit = norm(lv["exit_kind"]) == norm(bt["exit_reason"])
    if lv["exit_px"] is not None and same_exit and lv["exit_src"] not in (None, "model (broker close not priced)"):
        row["exit_slip_ticks"] = _ticks(bt["exit_price"], lv["exit_px"], d)
        row["exit_slip_usd"] = round(-row["exit_slip_ticks"] * TICK_USD * q, 2) + 0.0
    elif lv["exit_px"] is not None and not same_exit:
        row["notes"].append(f"outcome differs: backtest {bt['exit_reason']}, bot {lv['exit_kind']}")
    elif lv["exit_src"] == "model (broker close not priced)":
        row["notes"].append("exit was a CLOSEPOSITION: its price is not in outgoing\\ (export NinjaTrader Executions to price it)")
    if q != int(bt["qty"]):
        row["qty_diff"] = q - int(bt["qty"])
        per = (float(bt["pnl"]) + COMM * int(bt["qty"])) / max(1, int(bt["qty"]))
        row["size_effect_usd"] = round((per - COMM) * row["qty_diff"], 2)     # not execution: the sizer's choice
        row["notes"].append(f"qty {q} vs the backtest's {bt['qty']} (eval sizing / weekly stop: not an execution cost)")
    row["slip_usd"] = round((row.get("entry_slip_usd") or 0.0) + (row.get("exit_slip_usd") or 0.0), 2)
    row["max_slip_ticks"] = max([x for x in (row.get("entry_slip_ticks"), row.get("exit_slip_ticks")) if x is not None], default=None)
    if lv["fill_entry"] is not None and lv["exit_px"] is not None and q:
        row["live_pnl"] = round((lv["exit_px"] - lv["fill_entry"]) * d * PV * q - COMM * q, 2)
        row["bt_pnl_live_qty"] = round((bt["exit_price"] - bt["entry"]) * d * PV * q - COMM * q, 2)
        row["exec_usd"] = round(row["live_pnl"] - row["bt_pnl_live_qty"], 2)      # negative = execution cost us money
    return row


def _match(bts: list, lvs: list):
    """Pair a day's backtest and live trades: same entry_t first, then same side within 10 minutes. A backtest trade with
    only a refused entry is paired with it (compare() makes it a missed trade, reason "refused"); a refused entry the
    backtest does not have is left out (nothing was traded either way)."""
    pairs, used = [], set()

    def find(b, ok):
        c = [l for l in lvs if id(l) not in used and l["ok"] == ok]
        return next((l for l in c if l["entry_t"] == int(b["entry_t"])), None) or \
            next((l for l in c if l["dir"] == int(b["dir"]) and abs(l["entry_t"] - int(b["entry_t"])) <= 600), None)
    for b in bts:
        m = find(b, True) or find(b, False)
        if m is not None:
            used.add(id(m))
        pairs.append((b, m))
    pairs += [(None, l) for l in lvs if id(l) not in used and l["ok"]]
    return pairs


def _trading_days(a: str, b: str) -> list:
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    out = []
    while d0 <= d1:
        if d0.weekday() < 5:
            out.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    return out


def audit(store=None, days=None, bars=None, params=None, journal_path=None, now=None, eval_start=None, write=True) -> dict:
    """Replay each day and compare. days: a list of yyyy-mm-dd (default: from the first day the bot left a record, or
    eval_start, to today; at most MAX_DAYS). bars = (d5, d1) frames (default load_bars())."""
    now = int(now or time.time())
    today = trading_day(now)
    live = live_trades(store, journal_path)
    notes = _read_json(_p(store, "notes.json"), {}) or {}
    live_days = {v["day"] for v in live.values()}
    if days is None:
        first = sorted(live_days | {trading_day(u["t"]) for u in notes.get("uptime") or []}
                       | {trading_day(int(k)) for k in (notes.get("blocked") or {})})
        start = min([x for x in (first[:1] + ([eval_start] if eval_start else [])) if x], default=today)
        days = _trading_days(start, today)[-MAX_DAYS:]
    P = {**(params if params is not None else _params())}
    d5, d1 = bars if bars is not None else load_bars()
    cpath = _p(store, "replay_cache.json")
    cache = _read_json(cpath, {}) or {}
    rows, day_info = [], {}
    for day in days:
        session_over = now >= _ts(day, 16, 0)
        rp = replay_day(day, d5, d1, P, cache=cache)
        bts = [t for t in rp["trades"] if session_over or t["exit_t"] <= now]
        lvs = [v for v in live.values() if v["day"] == day]
        day_info[day] = {"bars": rp["bars"], "one_min": rp.get("one_min"), "bt_trades": len(bts), "live_trades": len(lvs),
                         **({"error": rp["error"]} if rp.get("error") else {})}
        if not rp["bars"] and not lvs:
            continue
        for b, l in _match(bts, lvs):
            if b is None and l is None:
                continue
            if b is not None and not rp["bars"]:
                continue
            if b is None and not rp["bars"]:
                r = compare(None, l, notes, live_days)
                r["reason"] = "no bars for this day in data/ (backtest not run)"
                rows.append(r)
                continue
            rows.append(compare(b, l, notes, live_days))
    if write:
        try:
            _write_json(cpath, {k: v for k, v in cache.items() if k >= (days[0] if days else today)} if days else cache)
        except Exception:
            pass
    rows.sort(key=lambda r: r["entry_t"])
    rep = {"v": VERSION, "t": now, "days": day_info, "rows": rows, "summary": summarize(rows, now, days)}
    if write:
        _write_json(_p(store, "report.json"), rep)
        _write_json(_p(store, "summary.json"), rep["summary"])
    return rep


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 2)


def summarize(rows: list, now=None, days=None) -> dict:
    M = [r for r in rows if r["status"] == "matched"]
    X = [r for r in rows if r["status"] == "missed"]
    E = [r for r in rows if r["status"] == "extra"]
    slip = [r["slip_usd"] for r in M if r.get("slip_usd") is not None]
    exe = [r["exec_usd"] for r in M if r.get("exec_usd") is not None]
    months = {}
    for r in rows:
        m = months.setdefault(r["day"][:7], {"month": r["day"][:7], "trades": 0, "slip_usd": 0.0, "exec_usd": 0.0, "missed": 0,
                                             "missed_usd": 0.0, "extra": 0, "extra_usd": 0.0})
        if r["status"] == "matched":
            m["trades"] += 1
            m["slip_usd"] = round(m["slip_usd"] + (r.get("slip_usd") or 0), 2)
            m["exec_usd"] = round(m["exec_usd"] + (r.get("exec_usd") or 0), 2)
        elif r["status"] == "missed":
            m["missed"] += 1
            m["missed_usd"] = round(m["missed_usd"] + (r.get("missed_usd") or 0), 2)
        else:
            m["extra"] += 1
            m["extra_usd"] = round(m["extra_usd"] + (r.get("live_pnl") or 0), 2)
    worst = max(M, key=lambda r: r.get("max_slip_ticks") or -1e9, default=None)
    S = {"v": VERSION, "t": int(now or time.time()), "from": days[0] if days else None, "to": days[-1] if days else None,
         "trades": len(M), "missed": len(X), "missed_pc_on": sum(1 for r in X if r.get("pc_on")),
         "missed_usd": round(sum(r.get("missed_usd") or 0 for r in X), 2), "extra": len(E),
         "extra_usd": round(sum(r.get("live_pnl") or 0 for r in E), 2),
         "slip_usd": round(sum(slip), 2), "slip_usd_per_trade": round(sum(slip) / len(slip), 2) if slip else None,
         "exec_usd": round(sum(exe), 2), "exec_usd_per_trade": round(sum(exe) / len(exe), 2) if exe else None,
         "entry_slip_ticks_med": _med([r.get("entry_slip_ticks") for r in M]),
         "exit_slip_ticks_med": _med([r.get("exit_slip_ticks") for r in M]),
         "latency_s_med": _med([r.get("latency_s") for r in M]),
         "be_delay_s_med": _med([r.get("be_delay_s") for r in M]),
         "qty_mismatch": sum(1 for r in M if r.get("qty_diff")),
         "slipped": sum(1 for r in M if (r.get("max_slip_ticks") or 0) > SLIP_ALERT_TICKS),
         "months": [months[k] for k in sorted(months)],
         "worst": None if worst is None or worst.get("max_slip_ticks") is None else
         {k: worst.get(k) for k in ("day", "entry_t", "side", "entry_slip_ticks", "exit_slip_ticks", "slip_usd")},
         "recent": [compact(r) for r in rows[-8:]][::-1]}
    S["text"] = headline(S)
    return S


def compact(r: dict) -> dict:
    keys = ("status", "day", "entry_t", "side", "latency_s", "entry_slip_ticks", "exit_slip_ticks", "slip_usd", "exec_usd",
            "bt_qty", "live_qty", "bt_pnl", "live_pnl", "missed_usd", "reason", "pc_on", "bt_exit_reason", "live_exit_kind")
    return {k: r[k] for k in keys if r.get(k) is not None}


def _usd(v):
    v = float(v or 0)
    return ("+" if v > 0 else "-" if v < 0 else "") + f"${abs(v):,.0f}"


def headline(S) -> str:
    if not (S["trades"] or S["missed"] or S["extra"]):
        return "No live trades to audit yet."
    parts = [f"{S['trades']} trade{'s' if S['trades'] != 1 else ''} audited: slippage {_usd(S['slip_usd'])}"
             + (f" ({_usd(S['slip_usd_per_trade'])} a trade)" if S["slip_usd_per_trade"] is not None else "")]
    if S["missed"]:
        parts.append(f"{S['missed']} missed ({_usd(S['missed_usd'])} the backtest made)")
    if S["extra"]:
        parts.append(f"{S['extra']} extra ({_usd(S['extra_usd'])})")
    return "; ".join(parts)


# ================================================================================================ phone push
def _sent(store):
    return set(_read_json(_p(store, "alerts_sent.json"), []) or [])


def _mark(store, keys):
    s = sorted(_sent(store) | set(keys))[-2000:]
    _write_json(_p(store, "alerts_sent.json"), s)


def alert_payloads(rows: list, now=None) -> list:
    """Push notices for a slipped fill (> 4 ticks worse, entry or exit) and a backtest trade missed while the PC was on."""
    from engine import push
    now = int(now or time.time())
    out = []
    for r in rows:
        t = int(r.get("exit_t") or r["entry_t"])
        if now - t > ALERT_MAX_AGE_S or t > now + 60:
            continue
        if r["status"] == "matched" and (r.get("max_slip_ticks") or 0) > SLIP_ALERT_TICKS:
            bits = []
            if (r.get("entry_slip_ticks") or 0) > SLIP_ALERT_TICKS:
                bits.append(f"entry {r['entry_slip_ticks']:+.0f} ticks")
            if (r.get("exit_slip_ticks") or 0) > SLIP_ALERT_TICKS:
                bits.append(f"exit {r['exit_slip_ticks']:+.0f} ticks")
            out.append(push.text_payload("PC", "pc", f"Slippage · {r['side']} {_hm(r['entry_t'])} ET",
                                         f"{', '.join(bits)} vs the backtest: {_usd(r.get('slip_usd') or 0)} on {r.get('live_qty')} micros",
                                         key=f"exec:slip:{r['entry_t']}", t=t, url="#/accounts"))
        elif r["status"] == "missed" and r.get("pc_on"):
            out.append(missed_payload(r["entry_t"], r["side"], r.get("reason"), r.get("missed_usd"), t))
    return out


def missed_payload(entry_t, side, reason, usd=None, t=None) -> dict:
    from engine import push
    return push.text_payload("PC", "pc", f"Missed trade · {side + ' ' if side else ''}{_hm(entry_t)} ET",
                             f"The backtest took it, the PC bot did not: {reason}" + (f" ({_usd(usd)} in the backtest)" if usd is not None else ""),
                             key=f"exec:miss:{int(entry_t)}", t=t or entry_t, url="#/accounts")


def send_alerts(payloads: list, store=None, notify=None) -> list:
    """Send each notice once (own sent list + engine/push's de-dup by key). notify(payload) for tests."""
    if notify is None:
        from engine import push
        notify = push.pc_notify
    done = _sent(store)
    sent = []
    for p in payloads:
        if p["key"] in done:
            continue
        try:
            notify(p)
        except Exception:
            pass
        sent.append(p["key"])
    if sent:
        _mark(store, sent)
    return sent


def session_alerts(bot, store=None, now=None, notify=None) -> list:
    """During the session, at once: an entry the bot's own model took but held back (feed stale, late, sizer) or the
    broker refused, while the bot is running. The replay repeats it later under the same key (sent once)."""
    now = int(now or time.time())
    if not getattr(bot, "running", False):
        return []
    today = trading_day(now)
    pays = []
    for et_ in sorted(getattr(bot, "_blocked_entries", None) or ()):
        if trading_day(et_) == today and now - int(et_) <= ALERT_MAX_AGE_S:
            pays.append(missed_payload(et_, "", _block_reason(bot, et_), None, now))
    for r in list(getattr(bot, "ledger", None) or []):
        if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok") is False and r.get("entry_t") \
                and trading_day(r["t"]) == today:
            pays.append(missed_payload(r["entry_t"], "LONG" if r["side"] == "buy" else "SHORT",
                                       "refused: " + str((r.get("result") or {}).get("error") or "")[:120], None, now))
    seen, uniq = set(), []
    for p in pays:
        if p["key"] not in seen:
            seen.add(p["key"]); uniq.append(p)
    return send_alerts(uniq, store, notify)


# ================================================================================================ views
def view(store=None, max_rows=200, refresh_s=1800, now=None) -> dict:
    """The PC dashboard's /api/next/pc/execution: the last report (re-run when older than refresh_s or missing)."""
    now = int(now or time.time())
    rep = _read_json(_p(store, "report.json"), None)
    if not rep or now - int(rep.get("t") or 0) > refresh_s:
        try:
            rep = audit(store=store, now=now)
        except Exception as e:
            if not rep:
                return {"v": VERSION, "error": f"{e.__class__.__name__}: {str(e)[:160]}", "rows": [], "summary": summarize([], now, [])}
    return {"v": VERSION, "t": rep.get("t"), "summary": rep.get("summary"), "rows": (rep.get("rows") or [])[-max_rows:][::-1],
            "days": rep.get("days"), "alert_ticks": SLIP_ALERT_TICKS, "tick_usd": TICK_USD, "comm": COMM}


def heartbeat_block(store=None) -> dict | None:
    """The heartbeat's "exec" block: the summary without the long lists (a few hundred bytes). None when no audit yet."""
    S = _read_json(_p(store, "summary.json"), None)
    if not S:
        return None
    keep = ("v", "t", "from", "to", "trades", "missed", "missed_pc_on", "missed_usd", "extra", "extra_usd", "slip_usd",
            "slip_usd_per_trade", "exec_usd", "exec_usd_per_trade", "entry_slip_ticks_med", "exit_slip_ticks_med", "latency_s_med",
            "be_delay_s_med", "qty_mismatch", "slipped", "worst", "text")
    out = {k: S.get(k) for k in keep}
    out["months"] = (S.get("months") or [])[-3:]
    out["recent"] = (S.get("recent") or [])[:5]
    return out


# ================================================================================================ PC watcher thread
class Watcher:
    """server.py: collect every minute, push the bot's own held-back entries at once, re-run the audit after a routed exit
    and once after each session (16:05 ET). Read-only towards the bot and the broker. LE_EXEC_AUDIT=0 turns it off."""

    def __init__(self, bot, every_s: float = 60.0, store=None, log=print):
        self.bot, self.every_s, self.store, self.log = bot, every_s, store, log
        self._stop = threading.Event()
        self._thread = None
        self._done_day = None
        self.last: dict = {}

    def tick(self, now=None) -> dict:
        now = int(now or time.time())
        c = collect(self.bot, store=self.store, now=now)
        sa = session_alerts(self.bot, self.store, now)
        e = _et(now)
        day = trading_day(now)
        after = e.hour * 60 + e.minute >= 16 * 60 + 5 and e.weekday() < 5 and self._done_day != day
        new_exit = any(r.get("side") == "exit" for r in (list(getattr(self.bot, "ledger", None) or [])[-c["ledger"]:] if c.get("ledger") else []))
        res = {"collect": c, "session_alerts": sa}
        if after or new_exit or not self.last:
            rep = audit(store=self.store, now=now, eval_start=self._eval_start())
            res["audit"] = rep["summary"]["text"]
            res["alerts"] = send_alerts(alert_payloads(rep["rows"], now), self.store)
            if after:
                self._done_day = day
        self.last = {"t": now, **res}
        return res

    def _eval_start(self):
        try:
            return self.bot.eval_start() or None
        except Exception:
            return None

    def _run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                self.log(f"[exec audit] {e.__class__.__name__}: {e}")
            self._stop.wait(self.every_s)

    def start(self):
        if os.environ.get("LE_EXEC_AUDIT", "1") == "0":
            return False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="exec-audit", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["report", "selftest"])
    ap.add_argument("--days", type=int, default=None, help="audit the last N trading days")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        from tests import test_fill_audit
        raise SystemExit(0 if test_fill_audit.main() else 1)
    collect(None)
    days = None
    if a.days:
        today = trading_day(time.time())
        days = _trading_days((dt.date.fromisoformat(today) - dt.timedelta(days=a.days * 2)).isoformat(), today)[-a.days:]
    rep = audit(days=days)
    S = rep["summary"]
    print(S["text"])
    for m in S["months"]:
        print(f"  {m['month']}: {m['trades']} trades, slippage {_usd(m['slip_usd'])}, execution {_usd(m['exec_usd'])}, "
              f"missed {m['missed']} ({_usd(m['missed_usd'])}), extra {m['extra']} ({_usd(m['extra_usd'])})")
    print("report ->", _p(None, "report.json"))


if __name__ == "__main__":
    main()
