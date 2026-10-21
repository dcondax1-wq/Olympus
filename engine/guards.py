"""Safety guards on the PC bot's order route (engine/live.py LiveBot). Each guard can only BLOCK a new entry or CLOSE a
position the bot's ledger says it does not hold; none sizes up, widens a stop, moves a target or opens anything.

Two hooks, both wrapped so a bug here never stops routing:
  entry_block(bot, ent, action, plan_qty, now)  called by LiveBot._route_primary right before an entry is sent: a reason
                                                (str) = the entry is NOT routed (logged "NOT routed: GUARD ...", phone push),
                                                None = route it. Pure checks on in-memory values, one small JSON read.
  tick(bot, now)                                called once per poll after routing: room alarm, account reconcile, the 17:00
                                                P&L reconcile, the clock-drift probe (a background thread; never in the route).

Guards and defaults (live_model.json "guards" and the start cfg "guards" override any key):
  1. order_sanity  ON   micros <= the sizing plan for that trade, <= 40, <= the account's max (the adapter's max_micros);
                        stop on the right side of the entry and <= 100 pts away; target >= 1.5R; worst-case $ at risk
                        <= max_risk_usd ($1,200; 2026: normal $800 max, two_week $996 max with costs). 2026 replay: 0 blocked.
  2. dup_entry     ON   one entry per signal and at most max_per_day (1) per trading day, persisted in guards_state.json
                        next to live_state.json (survives a restart or a lost live_state.json). An entry the bot flattened
                        as "NO TRADE" (the 1m-close estimate was not the model's trade) does not count.
  3. room_alarm    ON   push once when the eval room to the trailing floor drops below $800, once below $400 (per eval).
                        Push only.
  4. daily_loss    ON   no new entry once today's routed P&L is <= -$1,000 (the MFFU soft daily loss) + push. LIT trades
                        once a day, so in 2026 this never fires; it is the end-to-end backstop to the sizing caps.
  5. reconcile     ON   every poll: NinjaTrader's position on the bot's instruments vs the bot's ledger. Any mismatch that
                        persists -> push; bot flat but NinjaTrader holds a position -> CLOSEPOSITION (reconcile_flatten,
                        ON). 17:00-17:59 ET: NinjaTrader fills P&L vs the ledger, push if they differ by > $20.
                        Only with the NinjaTrader adapter (paper: nothing to compare).
  7. clock         ON   the PC clock vs HTTP Date headers (engine/ops_checks.internet, 3 sites, every 15 min in a thread):
                        off by > 5 s on two probes in a row -> new entries blocked + push. Unknown (no internet) = no block.
                        Skipped when the bot runs on a simulated clock (test harnesses).
  8. news          OFF  no new entry within 2 minutes of a Tier-1 release (high impact in data/news: CPI, NFP, PPI, FOMC).
                        LIT does not need it (research) and MFFU Builder allows news; for Rapid-style accounts.
  9. calendar      ON   no entry on a CME full-closure day (New Year, Christmas), on a weekend / the 17:00-18:00 break, before
                        the session start (02:00), at or after the flat time, or within 15 min of a CME early close
                        (engine/lit_live.early_close). 2026 replay: 0 blocked (6 early-close days traded, all before cutoff).
 11. presence_required  OFF  no new entry without an "I'm here" check-in in the last presence_hours (4 h) + a
                        "Check in to keep trading" push (engine/presence.py). Off: it could cut trades (frequency rule).
 12. entry pause  always  the owner's own "pause until" (engine/entry_pause.py: phone remote "pause" / PC dashboard): no new
                        entry until then; open trades keep their stop / target. Nothing is paused unless the owner asked.
Hands-off events (engine/handsoff.py): the reconcile mismatches are also logged as manual trade / close / size.
Guard 6 (stale data) is the existing FEED STALE logic in engine/live.py (tests/test_guards.py covers the 1m feed and the
1m-open file). Guard 10 is docs/PANIC.md.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
STATE_NAME = "guards_state.json"
PV = 2.0                                  # MNQ $ per point
COMM = 1.90                               # $ per micro round turn (the eval sizing's cost; lit.COMM is 1.40)
EVAL_MODES = ("eval", "safe_eval", "fast_eval", "two_week")

DEFAULTS = {
    "order_sanity": True, "max_micros": 40, "max_stop_pts": 100.0, "min_rr": 1.5, "max_risk_usd": 1200.0,
    "dup_entry": True, "max_per_day": 1,
    "room_alarm": True, "room_levels": [800.0, 400.0],
    "daily_loss": True, "daily_loss_usd": 1000.0,
    "reconcile": True, "reconcile_flatten": True, "reconcile_flat_s": 20, "reconcile_open_s": 360, "reconcile_qty_s": 120,
    "reconcile_grace_s": 90, "pnl_reconcile": True, "pnl_tol_usd": 20.0,
    "clock": True, "clock_max_s": 5.0, "clock_every_s": 900,
    "news": False, "news_min": 2,
    "calendar": True,
    "presence_required": False, "presence_hours": 4.0,
}


# ---------------------------------------------------------------------------------------------- config / state
def config(bot) -> dict:
    """DEFAULTS <- live_model.json "guards" <- the start cfg "guards"."""
    lm = {}
    try:
        from .lab_adapter import live_model
        lm = live_model().get("guards") or {}
    except Exception:
        lm = {}
    cfg = (getattr(bot, "cfg", None) or {}).get("guards") or {}
    return {**DEFAULTS, **(lm if isinstance(lm, dict) else {}), **(cfg if isinstance(cfg, dict) else {})}


def _cfg(bot) -> dict:
    c = getattr(bot, "_guards_cfg", None)
    if c is None:
        c = bot._guards_cfg = config(bot)
    return c


def state_path(bot) -> str:
    """data/guards_state.json next to data/live_state.json; a bot with another state file (test harnesses, extra
    accounts) gets its own <name>_guards.json beside it."""
    d, n = os.path.split(bot.state_path)
    return os.path.join(d, STATE_NAME if n == "live_state.json" else os.path.splitext(n)[0] + "_guards.json")


def load_state(bot) -> dict:
    try:
        with open(state_path(bot), encoding="utf-8") as fh:
            s = json.load(fh)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def save_state(bot, s: dict):
    try:
        p = state_path(bot)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        keep = sorted(s.get("routed") or {})[-14:]
        s["routed"] = {d: s["routed"][d] for d in keep}
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=1)
        os.replace(tmp, p)
    except Exception as e:
        bot._note_error(f"guards state save failed: {e}")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _notify(bot, key: str, title: str, body: str, kind="risk"):
    """Log line + one phone push per key (engine/push.pc_notify de-duplicates by key; only the real bot sends)."""
    bot._log(kind, f"GUARD {title}: {body}")
    try:
        from . import push
        p = push.text_payload("PC", "ops", title, body, key=f"guard:{key}", t=int(bot.clock()), url="#/activity")
        p["tag"] = "le-guard"
        bot._push_send(p)
    except Exception as e:
        bot._note_error(f"guard push failed: {e.__class__.__name__}")


# ---------------------------------------------------------------------------------------------- 1. order sanity
def sanity(action: dict, plan_qty, max_account=None, cfg: dict | None = None) -> list:
    """Problems with one entry order (empty = fine). action = the dict LiveBot sends: side, qty, entry, stop, target."""
    c = {**DEFAULTS, **(cfg or {})}
    out = []
    try:
        q = int(action.get("qty") or 0)
        d = 1 if action.get("side") == "buy" else -1
        e, s, g = (None if action.get(k) is None else float(action[k]) for k in ("entry", "stop", "target"))
    except (TypeError, ValueError) as ex:
        return [f"order unreadable ({ex})"]
    if plan_qty is not None and q > int(plan_qty):
        out.append(f"{q} micros is more than the sizing plan's {int(plan_qty)}")
    if q > int(c["max_micros"]):
        out.append(f"{q} micros is more than the {int(c['max_micros'])}-micro cap")
    if max_account is not None and q > int(max_account):
        out.append(f"{q} micros is more than the account's max {int(max_account)}")
    if e is None or s is None or g is None:
        out.append("entry, stop or target missing")
        return out
    risk = (e - s) * d
    if risk <= 0:
        out.append(f"stop {s:.2f} is on the wrong side of the entry {e:.2f} for a {'long' if d == 1 else 'short'}")
        return out
    if risk > float(c["max_stop_pts"]):
        out.append(f"stop {risk:.1f} pts away (max {float(c['max_stop_pts']):.0f})")
    rr = (g - e) * d / risk
    # the model clears min_rr from the fill; the route rounds the target 1 tick toward the entry and the stop to a tick:
    # 2 ticks of slack so a trade at exactly 1.5R is never refused for the rounding
    if (g - e) * d + 0.5 < float(c["min_rr"]) * risk - 1e-9:
        out.append(f"target {g:.2f} is {rr:.2f}R (min {float(c['min_rr']):.1f}R)")
    usd = q * (risk * PV + COMM)
    if c.get("max_risk_usd") and usd > float(c["max_risk_usd"]):
        out.append(f"${usd:,.0f} at risk (max ${float(c['max_risk_usd']):,.0f})")
    return out


def account_max(bot):
    """The account's max micros: the adapter's own cap (NinjaTrader max_micros), else the start cfg params max_micros."""
    m = getattr(getattr(bot, "adapter", None), "max_micros", None)
    if m is None:
        m = ((getattr(bot, "cfg", None) or {}).get("params") or {}).get("max_micros")
    try:
        return int(m) if m is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------- 9. session calendar
def full_closure(day: str) -> bool:
    """CME equity futures closed all day (no Globex session): New Year's Day and Christmas Day (observed on Monday when
    they fall on a Sunday). Good Friday / Thanksgiving / the other holidays trade with an early close (lit_live.early_close)."""
    d = dt.date.fromisoformat(day)
    for m, dd in ((1, 1), (12, 25)):
        h = dt.date(d.year, m, dd)
        if h.weekday() == 6:
            h += dt.timedelta(days=1)
        if d == h:
            return True
    return False


def calendar(entry_t: int, now: int, session_from: int = 120, flat_mod: int = 955) -> list:
    """Problems with entering at entry_t (the fill bar's open) / now: weekend or daily break, CME full closure, before the
    session start, at or after the flat time, within 15 min of a CME early close."""
    out = []
    for t in (int(now), int(entry_t)):
        e = _et(t)
        mod, wd = e.hour * 60 + e.minute, e.weekday()
        if wd == 5 or (wd == 6 and mod < 1080) or (wd == 4 and mod >= 1020) or 1020 <= mod < 1080:
            out.append(f"market closed at {e:%a %H:%M} ET")
            return out
    day = trading_day(entry_t)
    if full_closure(day):
        return [f"{day} is a CME holiday (full closure)"]
    e = _et(entry_t)
    mod = e.hour * 60 + e.minute
    cut = flat_mod
    try:
        from .lit_live import early_close
        ec = early_close(e.date().isoformat()) if mod < 1080 else None
    except Exception:
        ec = None
    if ec is not None:
        cut = min(cut, ec - 15)
    if mod >= 1080 or mod < session_from:
        out.append(f"{e:%H:%M} ET is before the session start {session_from // 60:02d}:{session_from % 60:02d}")
    elif mod >= cut:
        out.append(f"{e:%H:%M} ET is past the entry cutoff {cut // 60:02d}:{cut % 60:02d}"
                   + (" (CME early close today)" if ec is not None and cut < flat_mod else ""))
    return out


# ---------------------------------------------------------------------------------------------- 8. news minute
def news_hit(now: int, minutes: int = 2, events=None) -> str | None:
    """A Tier-1 (high impact) release within `minutes` of now: its name, else None."""
    if events is None:
        try:
            from . import news
            events = news.historical_events(("high",))
        except Exception:
            events = []
    for ev in events:
        if abs(int(ev["t"]) - int(now)) <= minutes * 60:
            return f"{ev.get('event')} at {_et(ev['t']):%H:%M} ET"
    return None


# ---------------------------------------------------------------------------------------------- 7. clock drift
_CLOCK = {"drift": None, "t": 0.0, "ok_t": 0.0, "bad": 0, "running": False, "probe": None}


def clock_probe() -> float | None:
    """Server clock - this PC's clock in seconds (median of 3 HTTP Date headers, engine/ops_checks.internet); None = unknown."""
    from . import ops_checks
    return ops_checks.internet().get("drift_s")


def _clock_run(probe):
    try:
        d = probe()
        if d is not None:
            _CLOCK["bad"] = _CLOCK["bad"] + 1 if abs(d) > _CLOCK.get("max", 5.0) else 0
            _CLOCK["drift"] = float(d)
            _CLOCK["ok_t"] = time.time()
    except Exception:
        pass
    finally:
        _CLOCK["running"] = False


def clock_tick(bot, c, now_real=None):
    """Start a probe in a thread when due (every clock_every_s; 20 s after a first bad answer, to confirm it)."""
    if not c.get("clock") or getattr(bot, "clock", None) is not time.time:
        return
    now_real = time.time() if now_real is None else now_real
    every = 20.0 if _CLOCK["bad"] == 1 else float(c.get("clock_every_s") or 900)
    if _CLOCK["running"] or now_real - _CLOCK["t"] < every:
        return
    _CLOCK["running"] = True
    _CLOCK["max"] = float(c.get("clock_max_s") or 5.0)
    _CLOCK["t"] = now_real               # also after a failed probe (no internet): the next try waits a full interval
    probe = _CLOCK.get("probe") or clock_probe
    threading.Thread(target=_clock_run, args=(probe,), name="guard-clock", daemon=True).start()


def clock_problem(bot, c) -> str | None:
    """Entries blocked while two probes in a row found the PC clock off by more than clock_max_s (a probe older than 2 h
    is too old to block on)."""
    if not c.get("clock") or getattr(bot, "clock", None) is not time.time:
        return None
    d = _CLOCK.get("drift")
    if d is None or _CLOCK["bad"] < 2 or time.time() - _CLOCK["ok_t"] > 7200:
        return None
    return f"PC clock {abs(d):.1f} s {'behind' if d > 0 else 'ahead of'} internet time (max {float(c['clock_max_s']):.0f} s)"


# ---------------------------------------------------------------------------------------------- 2. duplicates
def _void(bot) -> set:
    """Entries the bot flattened as NO TRADE (routed on the 1m close estimate, not the model's trade): they do not count."""
    return {int(r["entry_t"]) for r in bot.ledger if r.get("side") == "exit" and r.get("reason") == "NO TRADE" and r.get("entry_t")}


def dup_problem(bot, entry_t: int, c, s: dict) -> str | None:
    routed = s.get("routed") or {}
    void = _void(bot)
    for day, ts in routed.items():
        if int(entry_t) in [int(x) for x in ts]:
            return f"this signal ({_et(entry_t):%H:%M} ET) was already routed on {day}"
    today = [int(x) for x in routed.get(trading_day(entry_t), []) if int(x) not in void]
    led = {int(r["entry_t"]) for r in bot.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t")
           and trading_day(r["entry_t"]) == trading_day(entry_t) and int(r["entry_t"]) not in void}
    n = len(set(today) | led)
    if n >= int(c.get("max_per_day") or 1):
        return f"{n} entr{'y' if n == 1 else 'ies'} already routed today (max {int(c.get('max_per_day') or 1)} a day)"
    return None


def note_routed(bot, entry_t: int):
    """Record a routed entry (called right after the entry is sent)."""
    try:
        s = load_state(bot)
        day = trading_day(entry_t)
        ts = s.setdefault("routed", {}).setdefault(day, [])
        if int(entry_t) not in ts:
            ts.append(int(entry_t))
        save_state(bot, s)
    except Exception as e:
        bot._note_error(f"guards: routed entry not recorded: {e}")


# ---------------------------------------------------------------------------------------------- the entry hook
def entry_problems(bot, ent: dict, action: dict, plan_qty, now: int, c: dict | None = None, s: dict | None = None) -> list:
    """Every reason not to route this entry (empty = route it)."""
    c = c or _cfg(bot)
    out = []
    if c.get("calendar"):
        out += calendar(int(ent["entry_t"]), now, session_from=_session_from(bot), flat_mod=_flat_mod(bot))
    if c.get("order_sanity"):
        out += sanity(action, plan_qty, account_max(bot), c)
    if c.get("dup_entry"):
        p = dup_problem(bot, int(ent["entry_t"]), c, s if s is not None else load_state(bot))
        if p:
            out.append(p)
    if c.get("daily_loss"):
        pnl = bot.day_pnl_routed()
        if pnl <= -float(c["daily_loss_usd"]):
            out.append(f"today's routed P&L ${pnl:,.0f} reached the ${float(c['daily_loss_usd']):,.0f} soft daily loss")
    p = clock_problem(bot, c)
    if p:
        out.append(p)
    if c.get("news"):
        h = news_hit(now, int(c.get("news_min") or 2))
        if h:
            out.append(f"Tier-1 news within {int(c.get('news_min') or 2)} min: {h}")
    out += _owner_blocks(bot, c, now)
    return out


def _owner_blocks(bot, c, now) -> list:
    """The owner's own pause (always) and the presence check-in guard (OFF by default). Never raises."""
    out = []
    try:
        from . import entry_pause
        p = entry_pause.problem(bot, now)
        if p:
            out.append(p)
    except Exception as e:
        bot._note_error(f"guards: pause check failed: {e.__class__.__name__}")
    if c.get("presence_required"):
        try:
            from . import presence
            p = presence.problem(c, now, presence.path_for(bot))
            if p:
                out.append(p)
        except Exception as e:
            bot._note_error(f"guards: presence check failed: {e.__class__.__name__}")
    return out


def entry_block(bot, ent: dict, action: dict, plan_qty, now: int) -> str | None:
    """LiveBot hook: a reason = do NOT route (logged + pushed), None = route. A guard bug fails OPEN for the guards that
    are only backstops (the adapter keeps its own caps) and is logged."""
    try:
        bot._guards_cfg = config(bot)
        probs = entry_problems(bot, ent, action, plan_qty, now)
    except Exception as e:
        bot._note_error(f"guards: entry check failed ({e.__class__.__name__}: {e}); the adapter's own caps still apply")
        return None
    if not probs:
        return None
    why = "; ".join(probs)
    _notify(bot, f"entry:{int(ent['entry_t'])}", "Entry blocked",
            f"{'LONG' if action.get('side') == 'buy' else 'SHORT'} {action.get('qty')} at {_et(ent['entry_t']):%H:%M} ET not sent: {why}")
    return why


def _session_from(bot) -> int:
    try:
        w = (((bot.state or {}).get("strategy") or {}).get("params") or {}).get("window")
        if w:
            return int(min(a for a, _ in w))
    except Exception:
        pass
    return 120


def _flat_mod(bot) -> int:
    try:
        p = ((bot.state or {}).get("strategy") or {}).get("params") or {}
        if p.get("flat_mod") is not None:
            return int(p["flat_mod"])
        return int(((bot.cfg or {}).get("params") or {}).get("flat_mod", 955))
    except Exception:
        return 955


# ---------------------------------------------------------------------------------------------- 3. room alarm
def room_tick(bot, c, s) -> bool:
    if not c.get("room_alarm"):
        return False
    mode = str((getattr(bot, "_lit_sizing", None) or {}).get("mode") or "")
    start = bot.eval_start() if callable(getattr(bot, "eval_start", None)) else ""
    if mode not in EVAL_MODES and not (bot.cfg or {}).get("eval_start"):
        return False
    room = float(bot.eval_room())
    done = s.setdefault("room_alarm", {}).setdefault(start or "-", [])
    changed = False
    for lvl in sorted((float(x) for x in c.get("room_levels") or []), reverse=True):
        if room < lvl and lvl not in done:
            done.append(lvl)
            changed = True
            _notify(bot, f"room:{start}:{int(lvl)}", f"Eval room below ${lvl:,.0f}",
                    f"${room:,.0f} left to the trailing max-loss floor (eval from {start or '?'}). The bot sizes down "
                    "automatically; one bad day can end the eval.")
    return changed


# ---------------------------------------------------------------------------------------------- 5. reconcile
def _expected(bot) -> int:
    """Signed micros the bot's ledger says it holds: the open routed entry (+ its scale-in adds), else 0."""
    et_ = getattr(bot, "_open_routed", None)
    if et_ is None:
        return 0
    row = next((r for r in reversed(bot.ledger) if r.get("side") in ("buy", "sell") and r.get("entry_t") == et_), None)
    if row is None:
        return 0
    ad = getattr(bot, "adapter", None)
    if (row.get("result") or {}).get("ok") is False and not any(int(lg.get("entry_t") or 0) == int(et_) for lg in getattr(ad, "legs", []) or []):
        return 0                         # the broker refused the entry (or it was flattened at once): nothing was opened
    q = int(bot._open_qty or row.get("qty") or 0) + sum(int(a.get("qty") or 0) for a in (bot._open_adds or []) if a.get("entry_t") == et_)
    return q if row["side"] == "buy" else -q


def _broker_net(ad) -> tuple[int, list]:
    insts = ad._instruments()
    net, held = 0, []
    for p in ad.positions().get("positions") or []:
        mult = None
        for kind, name in insts.items():
            if name and (p["instrument"] == name or p["instrument"].startswith(name + " ")):
                mult = 10 if kind == "mini" else 1
        if mult is None or p.get("side") not in ("LONG", "SHORT"):
            continue
        q = int(p.get("qty") or 0) * mult
        net += q if p["side"] == "LONG" else -q
        held.append(f"{p['side']} {p.get('qty')} {p['instrument']}")
    return net, held


def _txt(n: int) -> str:
    return "flat" if n == 0 else f"{'LONG' if n > 0 else 'SHORT'} {abs(n)} micros"


def reconcile_tick(bot, c, now: int):
    ad = getattr(bot, "adapter", None)
    if not c.get("reconcile") or ad is None or not callable(getattr(ad, "positions", None)) \
            or not callable(getattr(ad, "_instruments", None)) or getattr(ad, "disabled", None) or getattr(ad, "readonly", False) \
            or getattr(bot, "kill", False):
        bot._recon = None
        return
    busy = [lg for lg in getattr(ad, "legs", []) if lg.get("status") != "protected"] or \
        [w for w in getattr(ad, "watch", []) if (w.get("watch") or {}).get("leftover")]
    recent = any(now - int(r.get("t") or 0) < int(c["reconcile_grace_s"]) for r in bot.ledger[-10:])
    exp = _expected(bot)
    net, held = _broker_net(ad)
    if busy or recent or net == exp:
        bot._recon = None
        return
    sig = (exp, net)
    rc = getattr(bot, "_recon", None)
    if not rc or rc.get("sig") != sig:
        bot._recon = rc = {"sig": sig, "since": now, "pushed": False, "flat_tries": 0, "flat_at": 0}
    wait = int(c["reconcile_flat_s"] if exp == 0 else c["reconcile_open_s"] if net == 0 else c["reconcile_qty_s"])
    if now - rc["since"] < wait:
        return
    day = trading_day(now)
    if not rc["pushed"]:
        rc["pushed"] = True
        act = " Closing it (CLOSEPOSITION)." if exp == 0 and c.get("reconcile_flatten") else " Check NinjaTrader by hand."
        _notify(bot, f"recon:{day}:{exp}:{net}", "Position mismatch",
                f"NinjaTrader {getattr(ad, 'account', '')} shows {', '.join(held) or 'flat'}; the bot's ledger says "
                f"{_txt(exp)}.{act}")
        try:                                     # the weekly hands-off score (engine/handsoff.py)
            from . import handsoff
            handsoff.record("manual_trade" if exp == 0 else "manual_close" if net == 0 else "manual_size", "reconcile",
                            f"account {', '.join(held) or 'flat'}, bot ledger {_txt(exp)}", now=now, path=handsoff.path_for(bot))
        except Exception:
            pass
    if exp == 0 and net != 0 and c.get("reconcile_flatten") and now - rc["flat_at"] >= 60:
        if rc["flat_tries"] >= 3:
            if rc["flat_tries"] == 3:
                rc["flat_tries"] += 1
                _notify(bot, f"recon-hand:{day}:{net}", "FLATTEN BY HAND",
                        f"NinjaTrader still shows {', '.join(held)} after 3 CLOSEPOSITION tries: NinjaTrader > Flatten Everything.")
            return
        rc["flat_tries"] += 1
        rc["flat_at"] = now
        bot._route({"sym": (bot.cfg or {}).get("sym", "NQ"), "side": "exit", "reason": "RECONCILE", "entry_t": None})


def nt_day_pnl(ad, day: str, ledger_pnl: dict) -> dict:
    """Today's P&L from NinjaTrader's own fills (the adapter's legs: entry fill, stop / target order fills). An exit
    NinjaTrader reports no price for (a CLOSEPOSITION: time exit, 15-minute cut, flatten) takes the ledger's P&L of that
    entry and is counted in "unpriced"."""
    insts = ad._instruments()
    by_entry, unpriced, seen = {}, 0, set()
    for lg in list(getattr(ad, "history", [])) + list(getattr(ad, "legs", [])):
        et_ = int(lg.get("entry_t") or 0)
        key = lg.get("entry_id")
        if not et_ or key in seen or trading_day(et_) != day or not lg.get("filled") or not lg.get("fill_px"):
            continue
        seen.add(key)
        mult = 10 if lg.get("instrument") == insts.get("mini") else 1
        d = int(lg.get("dir") or (1 if lg.get("side") == "BUY" else -1))
        ins = [(int(lg["filled"]), float(lg["fill_px"]))] + [(int(a.get("filled") or 0), float(a["fill_px"]))
                                                             for a in lg.get("adds") or [] if a.get("filled") and a.get("fill_px")]
        qty = sum(q for q, _ in ins)
        avg_in = sum(q * p for q, p in ins) / qty
        outs = []
        for oid in (lg.get("stop_id"), lg.get("target_id")):
            st = ad.read_order(oid) if oid else None
            if st and int(st.get("filled") or 0) > 0 and st.get("avg"):
                outs.append((int(st["filled"]), float(st["avg"])))
        out_q = sum(q for q, _ in outs)
        if out_q < qty:
            unpriced += 1
            by_entry[et_] = by_entry.get(et_, 0.0) + float(ledger_pnl.get(et_, 0.0))
            continue
        pnl = sum(q * d * (p - avg_in) for q, p in outs) * PV * mult - COMM * qty * mult
        by_entry[et_] = by_entry.get(et_, 0.0) + pnl
    return {"pnl": round(sum(by_entry.values()), 2), "trades": len(by_entry), "unpriced": unpriced, "by_entry": by_entry}


def pnl_tick(bot, c, now: int, s: dict) -> bool:
    """17:00-17:59 ET on a weekday, once per trading day: NinjaTrader fills P&L vs the ledger's routed P&L."""
    ad = getattr(bot, "adapter", None)
    e = _et(now)
    if not c.get("pnl_reconcile") or ad is None or not callable(getattr(ad, "read_order", None)) or e.weekday() >= 5 \
            or not (1020 <= e.hour * 60 + e.minute < 1080):
        return False
    day = trading_day(now)
    if s.get("pnl_done") == day:
        return False
    s["pnl_done"] = day
    led = {}
    for r in bot.ledger:
        if r.get("side") == "exit" and r.get("entry_t") and trading_day(r["entry_t"]) == day:
            led[int(r["entry_t"])] = led.get(int(r["entry_t"]), 0.0) + float(r.get("pnl") or 0.0)
    ledger_total = round(sum(led.values()), 2)
    nt = nt_day_pnl(ad, day, led)
    diff = round(nt["pnl"] - ledger_total, 2)
    note = (f"; {nt['unpriced']} exit(s) without a NinjaTrader price (CLOSEPOSITION) counted at the ledger's $" if nt["unpriced"] else "")
    bot._log("system", f"GUARD P&L reconcile {day}: NinjaTrader fills ${nt['pnl']:+,.2f} vs ledger ${ledger_total:+,.2f} "
                       f"(diff ${diff:+,.2f}, {nt['trades']} trade(s){note})")
    if abs(diff) > float(c["pnl_tol_usd"]):
        _notify(bot, f"pnl:{day}", "P&L mismatch",
                f"{day}: NinjaTrader fills ${nt['pnl']:+,.0f}, the bot's ledger ${ledger_total:+,.0f} (diff ${diff:+,.0f}){note}. "
                "Check NinjaTrader Account Performance before the next session.")
    return True


# ---------------------------------------------------------------------------------------------- the poll hook
def _presence_tick(bot, c, now):
    if c.get("presence_required"):
        from . import presence
        presence.tick(bot, c, now)


def _handsoff_tick(bot, now):
    from . import handsoff
    handsoff.tick(bot, now)


def tick(bot, now: int):
    """LiveBot hook, once per poll after routing. Never raises."""
    try:
        c = bot._guards_cfg = config(bot)
    except Exception:
        return
    for name, fn in (("clock", lambda: clock_tick(bot, c)), ("reconcile", lambda: reconcile_tick(bot, c, now)),
                     ("presence", lambda: _presence_tick(bot, c, now)), ("handsoff", lambda: _handsoff_tick(bot, now))):
        try:
            fn()
        except Exception as e:
            bot._note_error(f"guards {name} failed: {e.__class__.__name__}: {e}")
    try:
        s = load_state(bot)
        changed = room_tick(bot, c, s)
        changed = pnl_tick(bot, c, now, s) or changed
        if changed:
            save_state(bot, s)
    except Exception as e:
        bot._note_error(f"guards room / P&L check failed: {e.__class__.__name__}: {e}")
    p = clock_problem(bot, c)
    day = trading_day(now)
    if p and getattr(bot, "_clock_pushed", None) != day:
        bot._clock_pushed = day
        _notify(bot, f"clock:{day}", "Clock drift: entries blocked", p + ". Windows: Settings > Time > Sync now.")
    bot.health["guard_block"] = p
