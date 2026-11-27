"""TRADE WATCH (night team C, 2026-11-16): each live Zlarior trade next to what its backtest twin did on the same bars, and a
phone push ONLY on a real mismatch. Read-only: it builds nothing new, it reads what the bot server already computes.

Reused, not rebuilt:
  engine/fill_audit.py   the twin replay (engine/lit_live.run on the same bars) -> logs/exec_audit/report.json rows
                         (matched / missed / extra), refreshed by the server's EXEC_AUDIT watcher after every routed exit and
                         after 16:05 ET. Its own alert_payloads() picks "slipped > 4 ticks" and "missed while the PC was on";
                         its session_alerts() list of held-back / refused entries is in the same rows after the replay.
  tools/fill_check.py    the real NinjaTrader fill vs the plan (wrong size, no stop at NinjaTrader, refused entry): already a
                         push of tools/pc_report.py ("fill:" keys), so it is not repeated here.
What this adds: the twin mismatches reach the phone over the free ntfy alert topic of tools/pc_report.py (the engine's own Web
Push needs the GitHub-held key, which GitHub-free mode cannot refresh), plus two stop checks the twin makes possible:
  missed     the backtest twin entered, the bot did not, while the PC bot was running (fill_audit's reason in the text)
  slip       a fill more than 4 ticks worse than the twin (fill_audit's own rule and text)
  stop       a matched trade with no stop in the bot's ledger, or its stop more than STOP_TICKS away from the twin's (the stop
             rule is mechanical: 1 tick beyond the sweep extreme, so live and twin must agree)
ATLAS twin (night W1, 2026-11-16): ATLAS has no fill_audit replay, so its twin is built here the same way: engine/second.run
(the research code account B itself runs, members of the account_b block) on the same bars (engine/fill_audit.load_bars: the
TradingView files + the PC's NinjaTrader archive), cached per day by the bars it saw in logs/exec_audit/atlas_twin.json, next to
account B's own state file (data/live_state_acctb.json: ledger, the 5m opens it probed, and "held" = why it did not route a
signal). Pushed only on a real mismatch:
  missed     the twin entered at a 5m open that account B PROBED (so the bot was on and flat there), with no entry and no
             reason of its own (no hedging, size 0, 2 a day, eval stop, lockout are B's rules, never a mismatch)
  slip       B's entry filled more than 4 ticks worse than the twin's entry
  stop       B's entry has no stop, or its stop is more than STOP_TICKS from the twin's (same tick rounding as B's order)
A refused entry is tools/fill_check.py's push ("refused"), so it is not repeated.
Never pushed: a qty difference against the twin (the sizer's choice: eval room / weekly stop; a real size error is fill_check's
"size" flag), an "extra" trade (feed revision / restart noise, listed on the dashboard), anything older than 2 days.

  flags(root, now) -> [{"key", "t", "title", "body", "code", "entry_t"}]   (tools/pc_report.py sends each once, high priority)
  python tools/trade_watch.py            print the current flags (sends nothing)
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STOP_TICKS = 4.0
MAX_AGE_S = 2 * 86400


def _rows(root: str) -> list:
    try:
        with open(os.path.join(root, "logs", "exec_audit", "report.json"), "r", encoding="utf-8") as fh:
            rep = json.load(fh)
        rows = rep.get("rows") if isinstance(rep, dict) else None
        return [r for r in rows if isinstance(r, dict) and r.get("entry_t")] if isinstance(rows, list) else []
    except Exception:
        return []


def _hm(t) -> str:
    try:
        from engine.fill_audit import _hm as hm
        return hm(int(t))
    except Exception:
        return time.strftime("%H:%M", time.gmtime(int(t)))


def flags(root: str = ROOT, now=None) -> list:
    """The real mismatches between the live Zlarior trades and the backtest twin. Never raises."""
    now = int(now or time.time())
    rows = _rows(root)
    out = []
    try:
        from engine import fill_audit as fa
        for p in fa.alert_payloads(rows, now):            # slip > 4 ticks + missed while the PC was on (fill_audit's rules)
            code = "missed" if ":miss:" in str(p.get("key")) else "slip"
            et_ = int(str(p.get("key")).rsplit(":", 1)[-1]) if str(p.get("key")).rsplit(":", 1)[-1].isdigit() else int(p.get("t") or now)
            out.append({"key": f"watch:lit:{et_}:{code}", "t": int(p.get("t") or et_), "code": code, "entry_t": et_,
                        "title": "Zlarior vs backtest: " + str(p.get("title") or code), "body": str(p.get("body") or "")})
    except Exception:
        pass
    for r in rows:
        try:
            if r.get("status") != "matched":
                continue
            et_ = int(r["entry_t"])
            t = int(r.get("exit_t") or et_)
            if now - t > MAX_AGE_S or t > now + 60:
                continue
            side = str(r.get("side") or "")
            if r.get("live_stop") is None and r.get("bt_stop") is not None:
                body = (f"{side} {_hm(et_)} ET: the bot's ledger has no stop for this trade; the backtest's stop was {r['bt_stop']}. "
                        "Check NinjaTrader for a working stop now.")
            elif abs(float(r.get("stop_diff_ticks") or 0)) > STOP_TICKS:
                d = float(r["stop_diff_ticks"])
                body = (f"{side} {_hm(et_)} ET: the live stop {r.get('live_stop')} sits {abs(d):.0f} ticks "
                        f"{'closer than' if d > 0 else 'farther than'} the backtest's {r.get('bt_stop')} (rule: 1 tick beyond the sweep).")
            else:
                continue
            out.append({"key": f"watch:lit:{et_}:stop", "t": t, "code": "stop", "entry_t": et_,
                        "title": "Zlarior vs backtest: stop", "body": body})
        except Exception:
            continue
    try:
        out += atlas_flags(root, now)
    except Exception:
        pass
    seen, uniq = set(), []
    for f in out:
        if f["key"] not in seen:
            seen.add(f["key"]); uniq.append(f)
    return uniq


# ================================================================================================ ATLAS (account B) twin
TICK = 0.25
TWIN_DAYS = 3                      # trading days replayed (the push window is MAX_AGE_S = 2 days)


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _atlas_keys(root, ledger) -> list:
    keys = []
    try:
        from engine import account_b as ab
        raw = None
        loc = _read(os.path.join(root, "data", "account_b.json"), None)
        if isinstance(loc, dict) and "account_b" in loc:
            raw = loc.get("account_b")
        elif os.path.abspath(root) == os.path.abspath(ROOT):
            raw = ab.raw_cfg()
        keys = ab.keys_on_b(raw) if raw else []
    except Exception:
        keys = []
    for r in ledger:
        if r.get("side") in ("buy", "sell") and r.get("src") and r["src"] not in keys:
            keys.append(str(r["src"]))
    return keys


def atlas_twin(root, days, keys, now, cache_path=None) -> dict:
    """{day: [twin trades]} = engine/second.run on the live bars, members `keys` (each trade carries "key"). Cached per day
    by the bars it saw (a finished day with the same bars is never re-run)."""
    from engine import fill_audit as fa
    from engine import second as S
    d5, d1 = fa.load_bars()
    cfg = S.load_cfg()
    sub = {**cfg, "strategies": {k: {**cfg["strategies"][k], "route": True} for k in keys if k in (cfg.get("strategies") or {})}}
    cache_path = cache_path or os.path.join(root, "logs", "exec_audit", "atlas_twin.json")
    cache = _read(cache_path, {})
    cache = cache if isinstance(cache, dict) else {}
    out, dirty = {}, False
    for day in days:
        end = min(fa._ts(day, 16, 5), int(now))
        a5 = d5[d5["time"] < end] if len(d5) else d5
        a1 = d1[d1["time"] < end] if d1 is not None and len(d1) else d1
        n1 = len(a1) if a1 is not None else 0
        sig = (f"{'-'.join(sorted(sub['strategies']))}:{len(a5)}:{int(a5['time'].max()) if len(a5) else 0}:"
               f"{n1}:{int(a1['time'].max()) if n1 else 0}")
        c = cache.get(day)
        if isinstance(c, dict) and c.get("sig") == sig:
            out[day] = c.get("trades") or []
            continue
        tt = []
        if len(a5) >= 12 and sub["strategies"]:
            r = S.run(a5, one_min=a1 if n1 else None, now=end + 300 if end < int(now) else int(now), cfg=sub, lit=[])
            for k, st in (r.get("strategies") or {}).items():
                for t in st.get("trades") or []:
                    if t.get("day") == day and t.get("entry_t") is not None and t.get("stop") is not None:
                        tt.append({"key": k, "short": st.get("short") or k, "entry_t": int(t["entry_t"]), "dir": int(t["dir"]),
                                   "entry": float(t["entry"]), "stop": float(t["stop"]),
                                   "target": None if t.get("target") is None else float(t["target"]),
                                   "exit_kind": t.get("exit_kind"), "usd": t.get("usd"),
                                   "r": t.get("r"), "qty": t.get("qty")})        # r / qty: engine/circuit_breaker (night-risk)
        out[day] = tt
        cache[day] = {"sig": sig, "trades": tt}
        dirty = True
    if dirty:
        try:
            keep = dict(sorted(cache.items())[-20:])
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(keep, fh)
            os.replace(cache_path + ".tmp", cache_path)
        except Exception:
            pass
    return out


def _fill(row):
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    px = [(float(lg["fill_px"]), int(lg.get("filled") or 0)) for lg in res.get("legs") or []
          if isinstance(lg, dict) and lg.get("fill_px") is not None and int(lg.get("filled") or 0) > 0]
    n = sum(q for _, q in px)
    return round(sum(p * q for p, q in px) / n, 2) if n else None


def atlas_flags(root: str = ROOT, now=None, twin=None) -> list:
    """ATLAS (account B) live entries vs its backtest twin. twin(days, keys) -> {day: [trades]} (tests); default atlas_twin.
    Never raises."""
    try:
        return _atlas_flags(root, int(now or time.time()), twin)
    except Exception:
        return []


def _atlas_flags(root, now, twin):
    st = _read(os.path.join(root, "data", "live_state_acctb.json"), None)
    if not isinstance(st, dict):
        return []
    ledger = [r for r in st.get("ledger") or [] if isinstance(r, dict)]
    probed = {int(x[1]) for x in st.get("seen") or [] if isinstance(x, (list, tuple)) and len(x) == 2 and x[0] == "probe"}
    held = st.get("held") if isinstance(st.get("held"), dict) else {}
    entries = {}
    for r in ledger:
        if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None:
            entries[int(r["entry_t"])] = r                 # the last row for an open = the one that counts
    from engine.account_b import _tick, trading_day
    hk = [int(k) for k in held if str(k).isdigit()]           # day-atlasmiss: a day B only held (never probed: a stuck record) counts too
    days = sorted({trading_day(t) for t in list(probed) + list(entries) + hk if 0 <= now - t <= MAX_AGE_S})[-TWIN_DAYS:]
    keys = _atlas_keys(root, ledger) if days else []
    if not keys:
        return []
    tw = twin(days, keys) if twin is not None else atlas_twin(root, days, keys, now)
    out = []
    for day in days:
        by_t = {}
        for t in tw.get(day) or []:
            by_t.setdefault(int(t["entry_t"]), []).append(t)
        for tb, ts in sorted(by_t.items()):
            if now - tb > MAX_AGE_S or tb > now:
                continue
            e = entries.get(tb)
            if e is None:
                h = held.get(str(tb)) if isinstance(held.get(str(tb)), dict) else None
                stuck = bool(h and h.get("code") == "open" and h.get("since") and trading_day(int(h["since"])) < trading_day(tb))
                silent = h is None and tb not in probed and int(st.get("saved_at") or 0) >= tb + 60
                if not stuck and not silent and (tb not in probed or h is not None):
                    continue                               # PC off / B in a real trade / B's own rule said why
                t = ts[0]
                if stuck or silent:                        # day-atlasmiss 2026-11-27: B never checked the open, or its position record is stuck
                    side = "LONG" if t["dir"] == 1 else "SHORT"
                    usd = t.get("usd")
                    why = (f"account B still marks its {_hm(int(h['since']))} ET entry of {trading_day(int(h['since']))} open (a stuck "
                           "position record?): every new entry is skipped until it clears" if stuck else
                           "account B never checked that open (no reason recorded) while the bot was running")
                    out.append({"key": f"watch:atlas:{tb}:missed", "t": tb, "code": "missed", "entry_t": tb,
                                "title": f"ATLAS vs backtest: missed {side} {_hm(tb)} ET",
                                "body": (f"{t.get('short') or t['key']} {side} at the {_hm(tb)} ET open: the backtest twin entered, {why}."
                                         + (f" Twin result {'+' if float(usd) >= 0 else '-'}${abs(float(usd)):,.0f}." if usd is not None else "")
                                         + " The bot clears a stuck record itself once NinjaTrader shows the account flat.")})
                    continue
                side = "LONG" if t["dir"] == 1 else "SHORT"
                usd = t.get("usd")
                out.append({"key": f"watch:atlas:{tb}:missed", "t": tb, "code": "missed", "entry_t": tb,
                            "title": f"ATLAS vs backtest: missed {side} {_hm(tb)} ET",
                            "body": (f"{t.get('short') or t['key']} {side} at the {_hm(tb)} ET open: the backtest twin entered, account B "
                                     "checked that open and routed nothing, with no reason of its own (no hedge / size / daily limit)."
                                     + (f" Twin result {'+' if float(usd) >= 0 else '-'}${abs(float(usd)):,.0f}." if usd is not None else "")
                                     + " Check the bot log.")})
                continue
            if (e.get("result") or {}).get("ok") is False:
                continue                                   # refused / not confirmed: tools/fill_check.py pushes it
            d = 1 if e.get("side") == "buy" else -1
            t = next((x for x in ts if x["key"] == e.get("src") and int(x["dir"]) == d), None) or \
                next((x for x in ts if int(x["dir"]) == d), None)
            if t is None:
                continue                                   # the twin went the other way here: not a fill / stop question
            side = "LONG" if d == 1 else "SHORT"
            nm = e.get("strategy") or t.get("short") or t["key"]
            fill = _fill(e)
            if fill is not None:
                slip = round((fill - float(t["entry"])) * d / TICK, 1)
                if slip > STOP_TICKS:
                    q = int(e.get("qty") or 0)
                    out.append({"key": f"watch:atlas:{tb}:slip", "t": tb, "code": "slip", "entry_t": tb,
                                "title": f"ATLAS vs backtest: slippage {side} {_hm(tb)} ET",
                                "body": f"{nm} {side} {_hm(tb)} ET filled {fill:,.2f}, {slip:.0f} ticks worse than the twin's "
                                        f"{float(t['entry']):,.2f} (-${slip * TICK * 2.0 * q:,.0f} on {q} micros)."})
            bt_stop = _tick(float(t["stop"]), d)
            if e.get("stop") is None:
                out.append({"key": f"watch:atlas:{tb}:stop", "t": tb, "code": "stop", "entry_t": tb,
                            "title": "ATLAS vs backtest: stop",
                            "body": f"{nm} {side} {_hm(tb)} ET: account B's order has no stop; the backtest's stop was {bt_stop:,.2f}. "
                                    "Check NinjaTrader for a working stop now."})
            else:
                diff = round((bt_stop - float(e["stop"])) * d / TICK, 1)      # positive = the live stop sits closer
                if abs(diff) > STOP_TICKS:
                    out.append({"key": f"watch:atlas:{tb}:stop", "t": tb, "code": "stop", "entry_t": tb,
                                "title": "ATLAS vs backtest: stop",
                                "body": f"{nm} {side} {_hm(tb)} ET: the live stop {float(e['stop']):,.2f} sits {abs(diff):.0f} ticks "
                                        f"{'closer than' if diff > 0 else 'farther than'} the backtest's {bt_stop:,.2f}."})
    return out


if __name__ == "__main__":
    fl = flags()
    print(f"trade watch: {len(fl)} mismatch(es) vs the backtest twin")
    for f in fl:
        print(f"  {f['title']}: {f['body']}")
