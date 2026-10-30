"""BLITZ's go-live check (account C, engine/account_c.py): one green / red line per thing a real BLITZ day needs, each red
line with its one fix. Read-only: it never arms, starts, routes or sizes anything.

    python -X utf8 -m engine.account_c --preflight      # asks the running bot (GET /api/next/start/blitz/preflight),
                                                         # else checks the files without it
    GET /api/next/start/blitz/preflight                  # the Start page's BLITZ · 25K card (engine/start_api.py)

Lines (key): config (BLITZ's account set), own (not Zlarior's / ATLAS's), nt (NinjaTrader connected), visible (its Name
in NinjaTrader), allow (the order allowlist), sim (the order route passed a Sim test lately: the bot's Sim roundtrip or a
BLITZ Sim session), armed (a real 25K needs the owner's arming + the bot running live), bot (the running bot has BLITZ on),
eval (the 25K eval clock), size (the first trade's micros at today's room), hedge (never opposite Zlarior / ATLAS),
contract (the performance contract = the kill switch, loaded; not paused), calendar (today's CME session, early close,
DST), feed (live bars fresh), day (today's BLITZ day filter; display only). Every line is "good", "bad", "wait" (comes by
itself: market closed, the first poll) or "info" (display only); all_green = every counted line good.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
SIM_TEST_MAX_AGE_S = 14 * 86400           # a BLITZ Sim session or the bot's Sim roundtrip counts for two weeks
SIM_FILE = os.path.join("data", "account_c_sim.json")
CMD = "python -X utf8 -m engine.account_c --preflight"
START = "Start page > Start trading"
SET = "Start page > BLITZ · 25K: type its Name, Set BLITZ's 25K"
ARM = "Start page > BLITZ · 25K > Arm BLITZ (type I ACCEPT LIVE RISK)"
TYP_STOP_PTS = 60.0                       # 1.5 x the 5m ATR, about 60 points in 2026 (BLITZ_STRATEGY.md)
URL = "http://127.0.0.1:8766/api/next/start/blitz/preflight"
_UNSET = object()


def _et(t):
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York"))


def _item(key, label, state, detail, fix=""):
    try:
        from .accounts import clean_text
        detail = clean_text(detail, 260)
    except Exception:
        detail = str(detail or "")[:260]
    return {"key": key, "label": label, "state": state, "detail": detail or "", "fix": fix or ""}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ BLITZ's own Sim record
def sim_path(root: str | None = None) -> str:
    return os.path.join(root or ROOT, SIM_FILE)


def record_sim(account: str, day: str, ok: bool, n: int, root: str | None = None, now=None) -> None:
    """engine/account_c.AccountC on a NinjaTrader Sim account books a routed BLITZ trade (entry taken, close confirmed):
    data/account_c_sim.json = {"account", "day", "t", "ok", "trades"} (the trades of that day). Never raises."""
    try:
        p = sim_path(root)
        old = _read(p) or {}
        n_ = int(n) + (int(old.get("trades") or 0) if old.get("day") == day and old.get("account") == account else 0)
        rec = {"v": 1, "account": str(account)[:60], "day": day, "t": int(now or time.time()), "ok": bool(ok), "trades": n_}
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        from .fsutil import replace as _replace
        _replace(tmp, p)
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------ facts
class _Stub:
    """A minimal bot for an AccountC built from the files (no running bot): clock, paper cfg, no pushes."""

    def __init__(self, now):
        self._now = int(now)
        self.cfg = {"adapter": "paper"}
        self.state, self.ledger, self.health = {}, [], {}
        self.state_path = None
        self.kill = False

    def clock(self):
        return self._now

    def _log(self, *a, **k):
        pass

    def _push_send(self, *a, **k):
        return False

    def _note_error(self, *a, **k):
        pass


def _offline_c(spec, root, now):
    """An AccountC on the saved state file (closes, scorecard, pause), never started (no adapter)."""
    from . import account_c as AC
    c = AC.AccountC(_Stub(now), spec, state_path=AC.state_file(root))
    c._load()
    return c


def facts(bot=None, root: str | None = None, now=None, folder: str | None = None, health: dict | None = None,
          connected=_UNSET, feed_problem=_UNSET, names=None, allowed=None, nt_names=None, sim_rt=None) -> dict:
    """Everything the lines need, from the running bot when there is one, else from the files. Never raises."""
    from . import account_c as AC
    now = int(now or (bot.clock() if bot is not None and callable(getattr(bot, "clock", None)) else time.time()))
    f = {"v": VERSION, "t": now, "running": bool(getattr(bot, "running", False)) if bot is not None else False,
         "source": "bot" if bot is not None and getattr(bot, "running", False) else "files"}
    blk = AC.raw_cfg(root)
    f["block"] = {k: blk.get(k) for k in ("account", "plan", "eval_start", "armed", "stage", "sizing")} if blk else None
    h = health if health is not None else (dict(getattr(bot, "health", None) or {}) if bot is not None else {})
    cfg = dict(getattr(bot, "cfg", None) or {}) if bot is not None else {}
    # the other accounts' Names
    lit = atlas = None
    try:
        if names is not None:
            lit, atlas = names
        else:
            lit, atlas = AC._names_in_use(root)
            if f["running"] and cfg.get("adapter") == "ninjatrader":
                from .ninjatrader import resolve_account
                lit = resolve_account(cfg) or lit
            ab = getattr(bot, "acct_b", None) if bot is not None else None
            if ab is not None and getattr(ab, "name", None):
                atlas = ab.name
    except Exception:
        pass
    f["lit"], f["atlas"] = lit, atlas
    spec = AC.normalize(blk, lit_account=lit, b_account=atlas) if blk else None
    f["spec"] = None if spec is None else {k: spec.get(k) for k in ("account", "plan", "plan_label", "eval_start", "armed", "problem",
                                                                    "stage", "sizing", "min_room")}
    name = (spec or {}).get("account") or ""
    from .ninjatrader import is_sim
    f["sim"] = bool(name) and is_sim(name)
    # NinjaTrader: connected, the Names it shows, the allowlist
    try:
        if f["running"] and (h.get("nt") or {}).get("connected") is not None:
            f["nt"] = bool((h.get("nt") or {}).get("connected"))
        elif connected is not _UNSET:
            f["nt"] = bool(connected() if callable(connected) else connected)
        else:
            from . import autoresume
            f["nt"] = bool(autoresume.nt_connected({"adapter": "ninjatrader", **({"nt_folder": folder} if folder else {})}))
    except Exception:
        f["nt"] = None
    try:
        if nt_names is not None:
            seen = set(nt_names)
        else:
            from . import go
            seen = {r["name"] for r in go.nt_names(folder)}
        f["visible"] = True if f["sim"] else (name in seen if name else None)
        f["seen"] = sorted(seen)[:8]
        # NinjaTrader's account list = LE_BarFeed's accounts.csv (its account export) + position files (only after a trade):
        # without the export a brand-new 25K cannot be seen yet, which is no fault of the account (2026-10-29: the PC's
        # heartbeat shows no accounts.csv)
        if nt_names is not None:
            f["list_ok"] = True
        else:
            from . import broker_balance
            f["list_ok"] = bool(broker_balance.read(folder=folder).get("ok"))
    except Exception:
        f["visible"], f["seen"], f["list_ok"] = None, [], False
    try:
        if allowed is None:
            from .ninjatrader import allowed_accounts
            allowed = allowed_accounts()
        f["allow"] = True if f["sim"] else (name in set(allowed) if name else None)
    except Exception:
        f["allow"] = None
    # Sim tests: the bot's Sim roundtrip (the same NinjaTrader route) and BLITZ's own Sim sessions
    try:
        if sim_rt is None:
            from . import launch_check
            sim_rt = launch_check.load_sim_result()
        f["sim_rt"] = (sim_rt or {}).get("roundtrip")
    except Exception:
        f["sim_rt"] = None
    f["sim_c"] = _read(sim_path(root))
    # the same NinjaTrader route taking a real order lately (Zlarior's / ATLAS's accepted entries on the running bot): proves the
    # route BLITZ uses without stopping the live bot for a Sim roundtrip
    try:
        last = None
        if f["running"] and cfg.get("adapter") == "ninjatrader":
            for who, led in (("Zlarior", getattr(bot, "ledger", None) or []), ("ATLAS", getattr(getattr(bot, "acct_b", None), "ledger", None) or [])):
                for r in led:
                    res = r.get("result") if isinstance(r.get("result"), dict) else {}
                    if r.get("side") in ("buy", "sell") and res.get("ok") is True and res.get("adapter") == "ninjatrader" and r.get("t"):
                        if last is None or int(r["t"]) > last[0]:
                            last = (int(r["t"]), who, res.get("account"))
        f["route"] = None if last is None else {"t": last[0], "who": last[1], "account": last[2]}
    except Exception:
        f["route"] = None
    # the account itself: the running instance, else one built from the state file
    ac = getattr(bot, "acct_c", None) if bot is not None else None
    f["c_running"] = ac is not None
    try:
        c = ac if ac is not None else (_offline_c(spec, root, now) if spec and not spec.get("problem") else None)
    except Exception:
        c = None
    f["disabled"] = ac.disabled_reason() if ac is not None else None
    f["kind"] = ac.kind() if ac is not None else None
    ev = st = None
    if c is not None:
        try:
            ev = c.eval_view(now)
            st = c.eval_state(now)
        except Exception as e:
            ev = {"error": f"{e.__class__.__name__}: {e}"}
    f["eval"] = None if ev is None else {k: ev.get(k) for k in ("session", "status", "balance", "room", "floor", "target", "to_target", "today",
                                                                "start", "error", "dll", "max_micros", "min_room")}
    # the size of the next trade at today's room: at today's 1.5 x 5m ATR stop when the bot has it, else 2026's typical
    size = None
    if c is not None and st is not None and spec:
        try:
            a5 = ((c.eng or {}).get("atr") or {}).get("a") if ac is not None else None
            stop = round(1.5 * float(a5), 2) if a5 else TYP_STOP_PTS
            rows = []
            for pts in sorted({stop, 40.0, 60.0, 90.0, 150.0}):
                q = AC.qty(spec, pts + 0.25, st)
                rows.append({"stop": pts, "qty": int(q["qty"]), "risk_usd": round(int(q["qty"]) * ((pts + 0.5) * 2.0 + 1.90), 2)})
            q0 = AC.qty(spec, stop + 0.25, st)
            size = {"stop": stop, "atr": bool(a5), "qty": int(q0["qty"]), "why": (q0.get("reasons") or [""])[-1], "rows": rows,
                    "room": st.get("room"), "session": st.get("session")}
        except Exception as e:
            size = {"error": f"{e.__class__.__name__}: {e}"}
    f["size"] = size
    # the performance contract (the kill switch) and its state
    try:
        B = AC.bands()
        fl = AC.band_at(AC.SCORE_MIN_TRADES, B)
        f["contract"] = {"loaded": bool(fl), "n": AC.SCORE_MIN_TRADES, "avg_r_p5": fl and fl["avg_r_p5"], "pf_p5": fl and fl["pf_p5"],
                         "lose_days": AC.SCORE_LOSE_DAYS}
    except Exception as e:
        f["contract"] = {"loaded": False, "error": f"{e.__class__.__name__}: {e}"}
    try:
        sc = c.scorecard() if c is not None else None
        f["score"] = None if sc is None else {k: sc.get(k) for k in ("n", "status", "avg_r", "pf_r", "lose_days", "why")}
        f["paused"] = (c.paused if c is not None else None)
    except Exception:
        f["score"], f["paused"] = None, None
    # armed / the live switch (real accounts)
    f["armed"] = bool((spec or {}).get("armed"))
    f["live_env"] = os.environ.get("NINJATRADER_LIVE") == "1" if f["running"] else None
    f["bot_armed"] = bool((h.get("account") or {}).get("armed") or cfg.get("armed")) if f["running"] else None
    # feed
    fd = h.get("feed") or {}
    if f["running"] and fd:
        f["feed"] = {k: fd.get(k) for k in ("age_1m_s", "age_5m_s", "stale", "entries_blocked", "market_open", "block", "used")}
    else:
        try:
            if feed_problem is _UNSET:
                from . import go
                fp = go.feed_problem()
            else:
                fp = feed_problem() if callable(feed_problem) else feed_problem
            f["feed"] = {"files": True, "problem": fp}
        except Exception as e:
            f["feed"] = {"files": True, "problem": f"not checked ({e.__class__.__name__})"}
    # BLITZ's state now (the running instance) and today's day filter (the paper shadow's engine on the PC)
    try:
        f["state"] = ac.state_text(now) if ac is not None else None
    except Exception:
        f["state"] = None
    try:
        from . import blitz as BZ
        E = (c.eng if (c is not None and c.eng) else None)
        if E is None and bot is not None:
            E = ((getattr(bot, "blitz", None) or {}).get("eng"))
        f["day"] = BZ.day_filter(E, BZ.et_date(now), now=now) if E else None
    except Exception:
        f["day"] = None
    return f


# ------------------------------------------------------------------------------------------------ the lines
def _calendar(now) -> dict:
    from . import account_c as AC
    from . import cme_calendar as CC
    day = AC.trading_day(now)
    d = dt.date.fromisoformat(day)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    day = d.isoformat()
    full = CC.full_closure(day)
    ec = CC.early_close(day)
    out = {"day": day, "full": bool(full), "early": ec}
    # a clock change in the next 7 days (the PC and the bot both run on New York time)
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo("America/New_York")
        a = _et(now)
        for k in range(1, 8):
            b = (a + dt.timedelta(days=k)).replace(hour=12)
            if b.utcoffset() != a.replace(hour=12).utcoffset():
                ch = (a + dt.timedelta(days=k)).date()
                while (dt.datetime.combine(ch - dt.timedelta(days=1), dt.time(12), z)).utcoffset() != a.replace(hour=12).utcoffset():
                    ch -= dt.timedelta(days=1)
                out["dst"] = {"day": ch.isoformat(), "back": b.utcoffset() < a.replace(hour=12).utcoffset()}
                break
    except Exception:
        pass
    return out


def lines(f: dict) -> dict:
    """The go-live lines from facts(): {"items", "all_green", "n_red", "n_wait", "say"}. Pure."""
    now = int(f.get("t") or time.time())
    items = []
    spec = f.get("spec") or {}
    name = spec.get("account") or ""
    if not f.get("block"):
        items.append(_item("config", "BLITZ's account set", "bad", "BLITZ · 25K is off: the scalper trades only on paper (its shadow ledgers)", SET))
        return _wrap(items, now, f)
    items.append(_item("config", "BLITZ's account set", "good",
                       f"BLITZ → {'Sim test on ' if f.get('sim') else ''}{name} ({spec.get('plan_label') or 'MFFU Builder 25K'}"
                       f"{', funded' if spec.get('stage') == 'funded' else ''})"))
    prob = spec.get("problem")
    if prob:
        items.append(_item("own", "Its own account", "bad", prob, SET))
    else:
        items.append(_item("own", "Its own account", "good",
                           f"{name} is neither Zlarior's ({f.get('lit') or 'not set'}) nor ATLAS's ({f.get('atlas') or 'not set'})"))
    # NinjaTrader
    nt = f.get("nt")
    items.append(_item("nt", "NinjaTrader connected", "good" if nt else "bad",
                       "a connection is CONNECTED" if nt else "no CONNECTED connection: open NinjaTrader and log in (Control Center > Connections)",
                       "" if nt else START))
    vis = f.get("visible")
    if f.get("sim"):
        items.append(_item("visible", "BLITZ's account in NinjaTrader", "good", f"{name} is a NinjaTrader Sim account (always there)"))
    elif vis:
        items.append(_item("visible", "BLITZ's account in NinjaTrader", "good", f"NinjaTrader shows {name}"))
    elif not f.get("list_ok"):
        items.append(_item("visible", "BLITZ's account in NinjaTrader", "info",
                           f"not checked: NinjaTrader's account list is not exported (LE_BarFeed's account export is off), so check {name} "
                           "letter by letter against NinjaTrader's Accounts tab (with a wrong Name NinjaTrader takes no BLITZ order: "
                           "'order NOT placed', nothing booked)"))
    else:
        seen = ", ".join(f.get("seen") or []) or "none yet"
        items.append(_item("visible", "BLITZ's account in NinjaTrader", "bad" if nt else "wait",
                           f"NinjaTrader does not show {name} (it shows: {seen}): connect the new 25K in NinjaTrader and check the Name "
                           "letter by letter", SET))
    al = f.get("allow")
    items.append(_item("allow", "On the order allowlist", "good" if al else "bad",
                       ("a Sim account needs no allowlist" if f.get("sim") else f"{name} may receive orders") if al else
                       f"{name} is not on the allowlist: the bot refuses to send it orders", f'python -m engine.ninjatrader --allow-account "{name}"'))
    # the Sim test
    rt, sc, ro = f.get("sim_rt") or {}, f.get("sim_c") or {}, f.get("route") or {}
    rt_ok = bool(rt.get("ok")) and now - int(rt.get("t") or 0) <= SIM_TEST_MAX_AGE_S
    sc_ok = bool(sc.get("ok")) and int(sc.get("trades") or 0) > 0 and now - int(sc.get("t") or 0) <= SIM_TEST_MAX_AGE_S
    ro_ok = bool(ro.get("t")) and now - int(ro["t"]) <= 7 * 86400
    if sc_ok or rt_ok or ro_ok:
        why = []
        if sc_ok:
            why.append(f"BLITZ traded {int(sc['trades'])} time{'s' if int(sc['trades']) != 1 else ''} on {sc.get('account')} on {sc.get('day')}, "
                       "every order taken and closed at NinjaTrader")
        if rt_ok:
            why.append(f"the order route passed its Sim roundtrip on {rt.get('account') or 'Sim'} {_et(int(rt['t'])):%a %b %d} "
                       "(BLITZ uses the same route)")
        if ro_ok:
            why.append(f"NinjaTrader took {ro.get('who')}'s order on {_et(int(ro['t'])):%a %b %d %H:%M} ET (the same route BLITZ uses)")
        items.append(_item("sim", "Order route tested recently", "good", "; ".join(why)))
    else:
        items.append(_item("sim", "Order route tested recently", "bad",
                           "no Sim roundtrip and no BLITZ Sim session in the last 14 days, no order of Zlarior / ATLAS taken by "
                           "NinjaTrader in the last 7",
                           "Start page > BLITZ · 25K > Sim test (Sim101) for one session, then set the 25K"))
    # armed / live
    if f.get("sim"):
        items.append(_item("armed", "Armed (you do this)", "info", f"{name} is a Sim account: no real money, nothing to arm"))
    elif not f.get("armed"):
        items.append(_item("armed", "Armed (you do this)", "bad", f"{name} is NOT armed: BLITZ sends it no order until you arm it", ARM))
    elif f.get("running") and not (f.get("live_env") and f.get("bot_armed")):
        items.append(_item("armed", "Armed (you do this)", "bad", f"BLITZ is armed on {name}, but the bot is not running live (started without "
                           "I ACCEPT LIVE RISK or without the live switch): BLITZ waits", START))
    else:
        items.append(_item("armed", "Armed (you do this)", "good", f"ARMED: BLITZ trades real money on {name}"
                           + (" while the bot runs live" if f.get("running") else " once the bot runs live")))
    # the running bot has BLITZ on
    if not f.get("running"):
        items.append(_item("bot", "Bot running with BLITZ", "bad", "the bot is not running", START))
    elif not f.get("c_running"):
        items.append(_item("bot", "Bot running with BLITZ", "wait", "the bot picks BLITZ up at its next poll once flat"))
    elif f.get("disabled"):
        items.append(_item("bot", "Bot running with BLITZ", "bad", f"BLITZ is OFF in the bot: {f['disabled']}", START))
    else:
        stx = (f.get("state") or {}).get("text") or "running"
        items.append(_item("bot", "Bot running with BLITZ", "good", f"{f.get('kind') or ''} {name}: {stx}".strip()))
    # the eval
    ev = f.get("eval") or {}
    if ev.get("error"):
        items.append(_item("eval", "25K eval clock", "bad", f"not readable: {ev['error']}", CMD))
    elif not spec.get("eval_start") and spec.get("stage") != "funded":
        items.append(_item("eval", "25K eval clock", "bad", "no first session day", SET))
    elif ev.get("status") in ("passed", "failed", "stuck", "lost", "graduated"):
        items.append(_item("eval", "25K eval clock", "bad", f"this eval is {ev['status']} (balance ${float(ev.get('balance') or 0):,.0f}): "
                           "no new BLITZ trade on it", "buy a new 25K, then " + SET if ev["status"] != "passed" else
                           "Start page > BLITZ · 25K > Passed → funded"))
    elif ev:
        when = spec.get("eval_start")
        s = ev.get("session")
        try:
            from . import account_c as AC
            from . import sizing as SZ
            if spec.get("stage") != "funded" and when:
                s = SZ.eval_session(when, AC.trading_day(now))      # 0 before the first session (sizing_state counts it as 1)
        except Exception:
            pass
        items.append(_item("eval", "25K eval clock", "good" if s else "wait",
                           (f"session {s} of 10 (first session {when}): balance ${float(ev.get('balance') or 0):,.2f}, room "
                            f"${float(ev.get('room') or 0):,.2f} to the floor, ${float(ev.get('to_target') or 0):,.0f} to the pass")
                           if s else f"first session {when}"))
    # the next trade's size
    sz = f.get("size") or {}
    if sz.get("error") or not sz:
        items.append(_item("size", "First trade's size", "bad" if spec and not prob else "info",
                           f"not computed ({sz.get('error') or 'no eval state'})", CMD))
    else:
        alt = ", ".join(f"{r['qty']} at {r['stop']:.0f} pts" for r in sz.get("rows") or [] if abs(r["stop"] - sz["stop"]) > 1e-9)
        items.append(_item("size", "First trade's size", "good" if sz["qty"] >= 1 else "info",   # 0 = today's caps (the eval line says stuck / failed)
                           f"{sz['qty']} micro{'s' if sz['qty'] != 1 else ''} at a {sz['stop']:.0f}-pt stop "
                           f"({'today' if sz.get('atr') else '2026 typical'}: 1.5 x the 5m ATR) on the ${float(sz.get('room') or 0):,.0f} room"
                           f" (session {sz.get('session')}); {alt}; never more than 20 (MFFU 25K: 2 minis)"
                           + ("" if sz["qty"] >= 1 else f" (today: {sz.get('why') or 'the caps'})"),
                           ""))
    # no hedging
    items.append(_item("hedge", "Never against Zlarior / ATLAS", "good",
                       f"Zlarior first, then ATLAS, then BLITZ: no BLITZ entry while {f.get('lit') or 'the 50K'} or "
                       f"{f.get('atlas') or 'the ATLAS 25K'} holds / enters / has a setup armed the other way; their opposite entry closes "
                       "BLITZ at market first and waits for NinjaTrader's flat"))
    # the performance contract
    ct = f.get("contract") or {}
    pz = f.get("paused")
    if not ct.get("loaded"):
        items.append(_item("contract", "Kill switch (performance contract)", "bad", f"not loaded: {ct.get('error') or 'research file missing'}",
                           "UPDATE.bat (research/scalp/na_best_trades.json)"))
    elif pz:
        items.append(_item("contract", "Kill switch (performance contract)", "bad", f"PAUSED since {_et(int(pz.get('t') or now)):%m-%d %H:%M} ET: "
                           f"{pz.get('why')}", "python -X utf8 -m engine.account_c --resume (your decision)"))
    else:
        s = f.get("score") or {}
        items.append(_item("contract", "Kill switch (performance contract)", "good",
                           f"loaded: BLITZ pauses itself after {ct['n']}+ trades under avg R {ct['avg_r_p5']:+.3f} / PF {ct['pf_p5']:.2f} "
                           f"(the 2026 floor) or {ct['lose_days']} losing days in a row; now {s.get('n') or 0} trades, {s.get('status') or 'warming'}"))
    # the CME calendar
    cal = _calendar(now)
    dd = _et(int(now)).date().isoformat()
    w = dt.date.fromisoformat(cal["day"]).strftime("%a %b %d")
    dst = cal.get("dst")
    dst_s = (f"; clocks go {'back' if dst['back'] else 'forward'} 1 hour on {dt.date.fromisoformat(dst['day']):%a %b %d} (BLITZ's times stay "
             "New York time: nothing to do)") if dst else ""
    if cal["full"]:
        items.append(_item("calendar", "CME calendar", "info", f"{w}: CME closed (holiday): no BLITZ trades{dst_s}"))
    elif cal["early"]:
        e = int(cal["early"])
        items.append(_item("calendar", "CME calendar", "good",
                           f"{w}: early close {e // 60:02d}:{e % 60:02d} ET: BLITZ flat by {(e - 5) // 60:02d}:{(e - 5) % 60:02d}, no entry after "
                           f"{(e - 15) // 60:02d}:{(e - 15) % 60:02d}{dst_s}"))
    else:
        items.append(_item("calendar", "CME calendar", "good", f"{w}{' (today)' if cal['day'] == dd else ''}: normal session, BLITZ checks "
                           f"11:00-15:30 ET, flat by 15:55{dst_s}"))
    # the feed
    fd = f.get("feed") or {}
    if fd.get("files"):
        p = fd.get("problem")
        items.append(_item("feed", "Live bars fresh", "bad" if p else "good", p or "LE_BarFeed's MNQ bars are fresh",
                           "" if not p else "right-click the MNQ 5-minute chart > Reload NinjaScript"))
    else:
        a1 = fd.get("age_1m_s")
        if fd.get("stale") or fd.get("entries_blocked"):
            items.append(_item("feed", "Live bars fresh", "bad", fd.get("block") or "FEED STALE: new entries blocked",
                               "right-click the MNQ 5-minute chart > Reload NinjaScript"))
        elif fd.get("market_open") is False:
            items.append(_item("feed", "Live bars fresh", "wait", "market closed: checked again from 18:00 ET"))
        else:
            items.append(_item("feed", "Live bars fresh", "good" if a1 is not None and a1 <= 180 else "bad",
                               f"1m bar {'?' if a1 is None else int(a1)} s old", "" if a1 is not None and a1 <= 180 else
                               "right-click the MNQ 5-minute chart > Reload NinjaScript"))
    # today's day filter (display only)
    dfl = f.get("day")
    if dfl:
        items.append(_item("day", "Today's BLITZ day filter", "info", dfl.get("text")))
    return _wrap(items, now, f)


def _wrap(items, now, f) -> dict:
    counted = [i for i in items if i["state"] != "info"]
    red = [i for i in counted if i["state"] == "bad"]
    ok = bool(counted) and not red and all(i["state"] == "good" for i in counted)
    say = ("BLITZ is ready: every line is green." if ok else
           f"{len(red)} red line{'s' if len(red) != 1 else ''}: {red[0]['label']}: {red[0]['detail']}" if red else
           "Waiting: " + "; ".join(i["label"] for i in counted if i["state"] == "wait"))
    return {"v": VERSION, "t": int(now), "source": f.get("source"), "items": items, "all_green": ok, "n_red": len(red),
            "n_wait": sum(1 for i in counted if i["state"] == "wait"), "n": len(counted), "say": say,
            "account": (f.get("spec") or {}).get("account"), "sim": f.get("sim"), "cmd": CMD}


def check(bot=None, root: str | None = None, now=None, **kw) -> dict:
    """facts + lines in one call (the GET route and the CLI). Never raises."""
    try:
        return lines(facts(bot, root=root, now=now, **kw))
    except Exception as e:
        return {"v": VERSION, "t": int(now or time.time()), "items": [_item("error", "BLITZ go-live check", "bad",
                                                                           f"failed: {e.__class__.__name__}: {e}", CMD)],
                "all_green": False, "n_red": 1, "n_wait": 0, "n": 1, "say": f"check failed: {e.__class__.__name__}: {e}"}


def compact(r: dict) -> dict:
    """The launch checklist's / heartbeat's cut: the count, the first red line and its fix."""
    red = [i for i in r.get("items") or [] if i.get("state") == "bad"]
    wait = [i for i in r.get("items") or [] if i.get("state") == "wait"]
    first = red[0] if red else (wait[0] if wait else None)
    return {"all_green": bool(r.get("all_green")), "n_red": int(r.get("n_red") or 0), "n_wait": int(r.get("n_wait") or 0),
            "n": int(r.get("n") or 0), "account": r.get("account"), "sim": r.get("sim"),
            "first": None if first is None else {k: first.get(k) for k in ("key", "label", "state", "detail", "fix")}}


def ask_server(url: str = URL, timeout: float = 4.0):
    """The running bot's answer (GET /api/next/start/blitz/preflight), else None."""
    try:
        import urllib.request
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(url, timeout=timeout) as r:
            d = json.loads(r.read().decode() or "null")
        return d if isinstance(d, dict) and d.get("items") else None
    except Exception:
        return None


def print_lines(r: dict) -> int:
    src = {"bot": "from the running bot", "files": "from the files (the bot is not running)"}.get(r.get("source") or "", "")
    print(f"BLITZ go-live check (account C) {_et(int(r.get('t') or time.time())):%a %b %d %H:%M} ET {src}")
    mark = {"good": "[OK] ", "bad": "[FIX]", "wait": "[..] ", "info": "[i]  "}
    for i in r.get("items") or []:
        print(f"  {mark.get(i['state'], '[?]  ')} {i['label']}: {i['detail']}")
        if i["state"] in ("bad", "wait") and i.get("fix"):
            print(f"        fix: {i['fix']}")
    print(("  ALL GREEN: " if r.get("all_green") else "  ") + str(r.get("say") or ""))
    return 0 if r.get("all_green") else 1


def main(argv=None) -> int:
    r = ask_server() if "--files" not in (argv or []) else None
    if r is None:
        r = check(None)
    return print_lines(r)
