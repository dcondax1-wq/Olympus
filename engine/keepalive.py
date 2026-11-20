"""Keep-alive trade for MFFU's 7-day inactivity rule (owner 2026-11-20: "if an account hasn't traded in 7 days it needs a very
small trade to reset the counter"). OFF by default: one switch per account, and only the owner turns one on.

The rule. MFFU Terms section 7 "Dormant Accounts" (myfundedfutures.com/terms, updated 2026-10-09) and the help center (articles
16596524, 14290805, 17036130, 18337038; all read 2026-11-20): every Evaluation and Sim Funded account needs at least one
EXECUTED trade in every 7 consecutive calendar days, weekends and holidays included. Without one, MFFU may close the account
and count the closure as a breach, and a Sim Funded account also loses ALL its profits. No warning is promised. A filled trade
counts. A login, or an order that never fills, does not. Live accounts have no such rule. MFFU sets no minimum size and no
minimum hold time, and nothing bans a small trade made only to stay active. The one soft rule is Terms 12.4: position size and
trade frequency should stay close to your usual pattern. So the keep-alive is an ordinary 1-micro trade: front-month MNQ,
the liquid last half hour of RTH, never inside a Tier-1 news window, never opposite another account, no tight bracket, flat
long before the close.

When (plan()). D = the account's last traded day (or its start). The cautious deadline is D + 6, because day 7 is read as too
late, as in engine/cme_calendar.idle_plan. The keep-alive acts on the LAST full CME session on or before that deadline
(lead_sessions 1). That is at least one calendar day before MFFU's literal limit (D + 7) and leaves every earlier session for
a real trade. A half day is used only when no full session is left. Once the deadline has passed it acts on the next session
anyway, because a late trade beats none.

Where in the day (window()). A full day: 15:33-15:48 ET. That is after LIT's last entry (15:30) and ATLAS's (12:00), before
the bot's flat time (15:55), before MFFU's 16:10, and before the 15:50 closing imbalance. A CME half day: from 12 to 2 minutes
before the entry cut (the adapters refuse entries from 15 minutes before the halt), e.g. 12:33-12:43 ET for a 13:00 halt.
Never 16:10-18:00, never after a half day's halt, never in the Sunday or overnight session.

What (tick()). ONE MNQ market order on that account's own NinjaTrader adapter (the one its strategy already uses, under the
owner's own arming), with a hard OCO stop and target 10 points (40 ticks, $20) away. It is closed at market after hold_s
(30 s, i.e. the next poll). Expected cost: $1.90 commission + 1 tick of spread = about $2.40. Worst case: the stop, 2 ticks
of slippage and commission = $22.90. At most MAX_TRIES attempts a day, and only one keep-alive open on the PC at a time.
Every gate must pass, or nothing is sent (the reason is logged once a day):
  the owner's switch for that account is ON; the bot is not killed; the adapter is enabled and not read-only; the account is
  not passed / failed / locked / lost / stuck / locked out today (engine/lifecycle + the strategy's own status); no trade on
  it yet this trading day; inside the window; no Tier-1 release (CPI, jobs, FOMC, minutes) within NEWS_PAD_S around the
  whole hold, on every account (the Rapid funded news ban is +-3 min, so this is stricter); fresh bars and no feed block;
  the account flat: no strategy position or entry in flight on ANY lane of that NinjaTrader account, no open bracket, and
  NinjaTrader shows FLAT; no other account opposite (the keep-alive takes the side an open account already holds, else long;
  two sides or an unknown side = skip); and engine/firms.check passes (contracts, the max-loss floor at the stop, the daily
  loss left, the eval best-day rule, the firm's flat time, hedging across ALL accounts).
Strategies are never disturbed. LIT and ATLAS cannot enter in that window (LIT stops at 15:30). The keep-alive never writes to
a strategy's ledger, so no stats, sizing or audits change. It only closes its own bracket (by its entry time), never a
CLOSEPOSITION on a guess. The kill switch and the adapter's flat-time safety close it like any trade. The hedging guard of the
extra accounts (multi_account.opposite_open) sees an open keep-alive (opposite()).

Restart safety. The state file next to the bot's state (data/keepalive_state.json) is written BEFORE the order goes out. After
a restart, the adapter restores its bracket from its own state file and the next tick closes it. A keep-alive that filled
never repeats that day, and an attempt that never filled is retried at most MAX_TRIES times.

Alerts (all to the private ntfy topic, engine/notify; ids masked):
  heads-up the morning of the act day (from 09:30 ET): "Keep-alive today on Zlarior 50K ... about -$2.40, at most -$23"
  the entry and the result, as the normal trade alerts labelled "Keep-alive on <account>" ("closed LONG -$2.40 (keep-alive)")
  a refusal that leaves no attempt today: "place 1 MNQ by hand before 15:50 ET"
  switch OFF (the owner's hand trade): the session before the act day "tomorrow is the last safe day", then on the act day
  "TODAY is the last safe day: place 1 MNQ by hand", each once.
The 25K #2 and the Rapid get these too (they had no phone warning before).

Config: data/keepalive.json (gitignored; the start cfg's "keepalive" block in test harnesses; a harness never reads the file)
  {"accounts": {"lit": false, "atlas": false, "x:b25k_2": false, "rapid": false}}   keys = engine/lifecycle keys
  python -X utf8 -m engine.keepalive --status                    switches, last results, the plan
  python -X utf8 -m engine.keepalive --plan 2026-11-16           when a keep-alive would act after a last trade that day
  python -X utf8 -m engine.keepalive --on lit --yes              the OWNER's yes (live orders): Claude never runs it
  python -X utf8 -m engine.keepalive --off lit
  python -X utf8 -m engine.keepalive --skip lit                  no keep-alive on lit today
  python -X utf8 -m engine.keepalive --traded lit [yyyy-mm-dd]   you traded it by hand: the clock restarts from that day
Tests: python -X utf8 -m tests.test_keepalive
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "keepalive.json")     # gitignored: the owner's switches
STATE_FILE = "keepalive_state.json"                            # gitignored, next to the bot's state file (data/)
VERSION = 1

LIMIT_DAYS = 7                  # MFFU: one executed trade in every 7 consecutive calendar days (Terms section 7)
LEAD_SESSIONS = 1               # act on the last full CME session on or before the cautious deadline (D + 6)
FULL_WINDOW = (15 * 60 + 33, 15 * 60 + 48)     # 15:33-15:48 ET: after LIT's 15:30 last entry, before the 15:55 flat
HALF_WINDOW = (12, 2)           # a half day: from 12 to 2 minutes before the entry cut (halt - 15 min)
HEADSUP_FROM = 9 * 60 + 30      # the act day's heads-up from 09:30 ET
HOLD_S = 30                     # closed at market after this (the next poll: the bot polls at :02 and :32)
HOLD_RANGE = (20, 90)
QTY = 1                         # one micro (MNQ)
STOP_PTS = TARGET_PTS = 10.0    # 40 ticks: a hard OCO stop and target ($20 a micro), never a tight bracket
TICK, PV = 0.25, 2.0            # MNQ: $0.50 a tick, $2 a point
COMM = 1.90                     # $ a micro round trip (engine/sizing.LIVE_COMM)
SLIP_TICKS = 2                  # a stop-out's slippage (engine/firms.SLIP_PTS 0.5 pt)
EXPECTED_COST = round(COMM + TICK * PV, 2)                                   # $2.40: commission + 1 tick of spread
WORST_COST = round(STOP_PTS * PV + SLIP_TICKS * TICK * PV + COMM, 2)         # $22.90: the stop + slippage + commission
NEWS_PAD_S = 10 * 60            # no keep-alive within 10 min of a Tier-1 release (any account)
FRESH_BAR_S = 180               # the last 1m bar must be this fresh
MAX_TRIES = 2                   # attempts a day when an entry did not fill (a refusal, NinjaTrader slow)
RETRY_S = 120
CLOSE_RETRY_S = 30
MIN_ROOM = 100.0                # never on an account with less room than this (the presets' "stuck" line)
PRIORITY = ("lit", "atlas", "rapid")           # one NinjaTrader account = one target: the first lane's key wins
MFFU_PLANS = ("mffu_builder_25k", "mffu_builder_50k", "mffu_rapid_eod_25k", "mffu_rapid_eod_50k")

ALERT_HOOK = None               # tests: fn(kind, payload) instead of the phone ("problem" | "trade")
_MX = threading.RLock()


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(float(t), ET)


def _mod(t) -> int:
    e = _et(t)
    return e.hour * 60 + e.minute


def _date(x) -> _dt.date:
    return x if isinstance(x, _dt.date) else _dt.date.fromisoformat(str(x)[:10])


def trading_day(t) -> str:
    return (_et(t) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _hm(m) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def money(x) -> str:
    v = _num(x, 0.0)
    return ("-" if v < 0 else "") + f"${abs(v):,.2f}"


# ------------------------------------------------------------------------------------------------ the calendar (pure)
def window(day):
    """(first, last) ET minute of the keep-alive window on trading date `day` (last exclusive), or None (no session, a full
    CME closure, a weekend)."""
    from . import cme_calendar as CC
    d = _date(day)
    if d.weekday() >= 5 or CC.full_closure(d):
        return None
    ec = CC.early_close(d)
    if ec is None:
        return FULL_WINDOW
    cut = CC.entry_cut(d, 955)
    a, z = cut - HALF_WINDOW[0], cut - HALF_WINDOW[1]
    return (a, z) if 0 < a < z else None


def in_window(now) -> bool:
    """now is inside today's window (the calendar date = the trading date: the window is always in the afternoon)."""
    e = _et(now)
    w = window(e.date())
    if not w or trading_day(now) != e.date().isoformat():
        return False
    from . import cme_calendar as CC
    m = e.hour * 60 + e.minute
    return w[0] <= m < w[1] and not CC.halted(now)


def plan(last_day, now, limit: int = LIMIT_DAYS, lead: int = LEAD_SESSIONS) -> dict:
    """When the keep-alive acts after a last traded day (or the account's start) `last_day`.
    {"last", "today", "idle_days", "deadline" (cautious, D + limit - 1), "hard" (MFFU's literal last day, D + limit),
     "sessions": [days that can still take one, today included while its window is open], "act_day", "due" (act now-ish:
     today is the act day and nothing traded today), "eve" (the act day is the next session), "late" (past the deadline)}."""
    last = _date(last_day)
    t = int(now)
    today = _date(trading_day(t))
    m = _mod(t)
    deadline = last + _dt.timedelta(days=max(1, int(limit)) - 1)
    hard = last + _dt.timedelta(days=max(1, int(limit)))
    idle = (today - last).days

    def open_on(d):
        w = window(d)
        return bool(w) and (d != today or (_et(t).date() == today and m < w[1]))

    sess, d = [], today
    while d <= deadline:
        if open_on(d):
            sess.append(d)
        d += _dt.timedelta(days=1)
    full = [x for x in sess if window(x) == FULL_WINDOW]
    late = not sess
    if full:
        act = full[max(0, len(full) - max(1, int(lead)))]
    elif sess:
        act = sess[0]                                   # only half days left: the first one
    else:                                               # past the deadline: the next session (a late trade beats none)
        act, d = None, today
        for _ in range(14):
            if open_on(d):
                act = d
                break
            d += _dt.timedelta(days=1)
    nxt = None
    d = today + _dt.timedelta(days=1)
    for _ in range(14):
        if window(d):
            nxt = d
            break
        d += _dt.timedelta(days=1)
    return {"last": last.isoformat(), "today": today.isoformat(), "idle_days": idle, "deadline": deadline.isoformat(),
            "hard": hard.isoformat(), "sessions": [x.isoformat() for x in sess], "act_day": act.isoformat() if act else None,
            "due": bool(idle >= 1 and act == today), "eve": bool(idle >= 0 and act is not None and nxt == act and act != today),
            "late": late}


# ------------------------------------------------------------------------------------------------ config / state files
def is_real(bot) -> bool:
    try:
        from .live import STATE_PATH
        return getattr(bot, "state_path", None) == STATE_PATH
    except Exception:
        return False


def _wanted(bot) -> bool:
    """The real bot (its switches + the owner's warnings), or a harness whose cfg has a "keepalive" block. Any other test
    harness: nothing at all (no file, no log line)."""
    return bot is not None and (is_real(bot) or "keepalive" in (getattr(bot, "cfg", None) or {}))


def load_config(bot=None, path: str | None = None) -> dict:
    """{"accounts": {key: bool}, "hold_s", "lead_sessions"}: the start cfg's "keepalive" block (test harnesses), else the
    owner's data/keepalive.json for the real bot; a harness never reads the owner's file. Anything unreadable = all OFF."""
    raw = None
    cfg = getattr(bot, "cfg", None) or {}
    if bot is not None and "keepalive" in cfg:
        raw = cfg.get("keepalive")
    elif path is not None or bot is None or is_real(bot):
        try:
            with open(path or CONFIG_PATH, encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            raw = None
    raw = raw if isinstance(raw, dict) else {}
    acc = raw.get("accounts") if isinstance(raw.get("accounts"), dict) else {}
    hold = _num(raw.get("hold_s"), HOLD_S)
    lead = _num(raw.get("lead_sessions"), LEAD_SESSIONS)
    return {"accounts": {str(k): v is True for k, v in acc.items()},
            "hold_s": int(min(HOLD_RANGE[1], max(HOLD_RANGE[0], hold))), "lead_sessions": int(min(3, max(1, lead))),
            "skip": {str(k): str(v) for k, v in (raw.get("skip") or {}).items()} if isinstance(raw.get("skip"), dict) else {}}


def save_config(c: dict, path: str | None = None) -> str:
    p = path or CONFIG_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"accounts": c.get("accounts") or {}, **({"skip": c["skip"]} if c.get("skip") else {})}, fh, indent=1)
    os.replace(tmp, p)
    return p


def state_path_for(bot=None) -> str:
    sp = getattr(bot, "state_path", None) or os.path.join(ROOT, "data", "live_state.json")
    return os.path.join(os.path.dirname(os.path.abspath(sp)), STATE_FILE)


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict) and isinstance(st.get("acc"), dict):
            st.setdefault("sent", [])
            st.setdefault("notes", {})
            st.setdefault("log", [])
            return st
    except Exception:
        pass
    return {"v": VERSION, "acc": {}, "sent": [], "notes": {}, "log": []}


def save_state(st: dict, path: str):
    with _MX:
        st["v"] = VERSION
        st["sent"] = list(st.get("sent") or [])[-200:]
        st["log"] = list(st.get("log") or [])[-60:]
        st["notes"] = {k: v for k, v in (st.get("notes") or {}).items() if str(v)[:10] >= _cut_day()}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=1)
        os.replace(tmp, path)


def _cut_day() -> str:
    return (_dt.date.today() - _dt.timedelta(days=10)).isoformat()


def _mtime(p):
    try:
        return os.stat(p).st_mtime_ns
    except OSError:
        return None


def _book(bot) -> dict:
    """The bot's keep-alive book (cached on the bot; re-read when the file changed outside the bot, e.g. --traded)."""
    b = getattr(bot, "_ka_book", None)
    p = state_path_for(bot)
    if not isinstance(b, dict) or b.get("_path") != p or b.get("_mt") != _mtime(p):
        b = {"_path": p, "st": load_state(p), "_mt": _mtime(p)}
        try:
            bot._ka_book = b
        except Exception:
            pass
    return b


def _save_book(bot, b):
    save_state(b["st"], b["_path"])
    b["_mt"] = _mtime(b["_path"])


_LAST: dict = {}


def last_day(bot, key: str) -> str | None:
    """The newest day a keep-alive FILLED on account `key`, or the owner marked a hand trade (--traded), else None. The idle
    counters (engine/account_b.idle_days) add it so their warnings stop after a keep-alive. Never raises."""
    try:
        p = state_path_for(bot)
        mt = _mtime(p)
        if mt is None:
            return None
        c = _LAST.get(p)
        if c is None or c[0] != mt:
            c = (mt, load_state(p).get("acc") or {})
            _LAST[p] = c
        a = c[1].get(key) or {}
        ds = [d for d in (a.get("last"), a.get("marked")) if d]
        return max(ds) if ds else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the accounts (targets)
def _ok_entry(r) -> bool:
    return isinstance(r, dict) and r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok") is True


def _lane_days(kind, obj, bot) -> set:
    """Trading days with an executed trade on one lane: closes / exits booked, entries the broker took, filled legs."""
    out = set()
    try:
        if kind == "lit":
            out |= {d for d in (bot.eval_days() or {}) if d and d != "0000-00-00"}
            ledger = getattr(bot, "ledger", None) or []
        else:
            out |= {str(c[0])[:10] for c in (getattr(obj, "closes", None) or []) if c}
            ledger = getattr(obj, "ledger", None) or []
        out |= {trading_day(r["t"]) for r in ledger if _ok_entry(r) and r.get("t")}
    except Exception:
        pass
    return out


def _adapter_days(ad) -> set:
    out = set()
    for lg in list(getattr(ad, "history", None) or []) + list(getattr(ad, "legs", None) or []):
        try:
            if isinstance(lg, dict) and int(lg.get("filled") or 0) > 0 and lg.get("entry_t"):
                out.add(trading_day(int(lg["entry_t"])))
        except Exception:
            continue
    return out


def _lane_start(kind, obj, bot) -> str | None:
    try:
        if kind == "lit":
            return bot.eval_start() or None
        if hasattr(obj, "start_day"):
            return obj.start_day() or None
        f = (getattr(obj, "spec", None) or {}).get("funded") or {}
        funded = callable(getattr(obj, "funded", None)) and obj.funded()
        return str((f.get("start") if funded else (obj.spec or {}).get("eval_start")) or "") or None
    except Exception:
        return None


def _lane_open(kind, obj, bot):
    """(busy, dir or None, why) for one lane: a strategy position, an entry in flight."""
    try:
        if kind == "lit":
            st = getattr(bot, "state", None) or {}
            pos, en = st.get("position"), st.get("enter_now")
            if pos:
                return True, (1 if pos.get("dir", 1) == 1 else -1), "LIT holds a position"
            if en:
                return True, (1 if en.get("dir", 1) == 1 else -1), "LIT is entering"
            ot = getattr(bot, "_open_routed", None)
            if ot is not None:
                e = next((r for r in reversed(getattr(bot, "ledger", None) or []) if r.get("side") in ("buy", "sell")
                          and r.get("entry_t") == ot), None)
                return True, ((1 if e["side"] == "buy" else -1) if e else None), "a routed position is open"
            return False, None, None
        ot = getattr(obj, "open_t", None)
        if ot is None:
            return False, None, None
        pv = (getattr(obj, "prov", None) or {}).get(int(ot)) if isinstance(getattr(obj, "prov", None), dict) else None
        if pv and pv.get("dir") in (1, -1):
            return True, int(pv["dir"]), "a position is open"
        e = next((r for r in reversed(getattr(obj, "ledger", None) or []) if r.get("side") in ("buy", "sell")
                  and r.get("entry_t") == ot), None)
        return True, ((1 if e["side"] == "buy" else -1) if e else None), "a position is open"
    except Exception as e:  # noqa: BLE001
        return True, None, f"state unreadable ({e.__class__.__name__})"


def _adapter_open(ad):
    """(busy, dir or None, why) at the broker: an open bracket of ours, or NinjaTrader's position file not FLAT."""
    try:
        from .ninjatrader import OPEN_STATUSES
        for lg in list(getattr(ad, "legs", None) or []):
            if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES:
                return True, int(lg.get("dir") or 0) or None, f"a bracket is {lg.get('status')}"
        if callable(getattr(ad, "positions", None)):
            for p in (ad.positions() or {}).get("positions") or []:
                if p.get("side") in ("LONG", "SHORT"):
                    return True, (1 if p["side"] == "LONG" else -1), f"NinjaTrader shows {p['side']} {p.get('qty')}"
        return False, None, None
    except Exception as e:  # noqa: BLE001
        return True, None, f"broker state unreadable ({e.__class__.__name__})"


def lanes(bot) -> list:
    """Every routed lane on the bot: {"key", "kind", "obj", "adapter", "nt", "trade"} (trade = an MFFU target candidate)."""
    out = []
    cfg = getattr(bot, "cfg", None) or {}
    ad = getattr(bot, "adapter", None)
    if ad is not None and str((getattr(bot, "state", None) or {}).get("model") or cfg.get("model") or "lit") == "lit":
        out.append({"key": "lit", "kind": "lit", "obj": bot, "adapter": ad, "trade": True,
                    "nt": str(cfg.get("nt_account") or getattr(ad, "account", "") or "") or None})
    for attr, key in (("acct_b", "atlas"), ("acct_r", "rapid")):
        o = getattr(bot, attr, None)
        if o is not None and not getattr(o, "problem", None):
            out.append({"key": key, "kind": "acct", "obj": o, "adapter": getattr(o, "adapter", None), "trade": True,
                        "nt": str(getattr(o, "name", "") or "") or None})
    for a in list(getattr(getattr(bot, "accts", None), "accounts", None) or []):
        if getattr(a, "problem", None):
            continue
        sp = getattr(a, "spec", None) or {}
        key = "rapid" if sp.get("lane") == "rapid" else f"x:{getattr(a, 'id', None) or sp.get('id')}"
        out.append({"key": key, "kind": "extra", "obj": a, "adapter": getattr(a, "adapter", None), "trade": True,
                    "nt": str(sp.get("nt_account") or "") or None if sp.get("adapter") == "ninjatrader" else None})
    c = getattr(bot, "acct_c", None)                    # BLITZ (paper / hidden): never a target, its side still counts
    if c is not None:
        out.append({"key": "blitz", "kind": "acct", "obj": c, "adapter": getattr(c, "adapter", None), "trade": False,
                    "nt": str(getattr(c, "name", "") or "") or None})
    fl = getattr(bot, "fleet", None)
    for i, f in enumerate(list(getattr(fl, "followers", None) or [])):
        out.append({"key": f"fleet:{i}", "kind": "fleet", "obj": f, "adapter": getattr(f, "adapter", None), "trade": False,
                    "nt": str(((getattr(f, "spec", None) or {}).get("nt_account")) or "") or None})
    return out


def targets(bot) -> list:
    """One target per NinjaTrader account: {"key", "label", "adapter", "lanes", "nt"}. Lanes on the same account (the Rapid's
    LIT + ATLAS lanes, ATLAS + LIT's lit25 lane) are one target; the key goes by PRIORITY, else the first lane's."""
    groups = []
    for ln in lanes(bot):
        if not ln["trade"] or ln["adapter"] is None or getattr(ln["adapter"], "name", None) != "ninjatrader":
            continue                                   # paper: no MFFU account behind it
        g = next((g for g in groups if (ln["nt"] and g["nt"] == ln["nt"]) or g["key"] == ln["key"]), None)
        if g is None:
            groups.append({"key": ln["key"], "nt": ln["nt"], "lanes": [ln]})
        else:
            g["lanes"].append(ln)
            if ln["key"] in PRIORITY and (g["key"] not in PRIORITY or PRIORITY.index(ln["key"]) < PRIORITY.index(g["key"])):
                g["key"] = ln["key"]
    from . import lifecycle as LC
    for g in groups:
        main = next((ln for ln in g["lanes"] if ln["key"] == g["key"] and ln["kind"] != "acct"), None) \
            or next((ln for ln in g["lanes"] if ln["key"] == g["key"]), g["lanes"][0])
        g["adapter"] = main["adapter"]
        g["main"] = main
        try:
            g["label"] = LC.label_of(g["key"], None if g["key"] == "lit" else main["obj"])
        except Exception:
            g["label"] = g["key"]
    return groups


def _plan_id(g) -> str | None:
    """engine/firms plan id of the target (None = not an MFFU account: the keep-alive is for MFFU's rule only)."""
    key, obj = g["key"], g["main"]["obj"]
    sp = getattr(obj, "spec", None) or {}
    if key == "lit":
        cfg = getattr(obj, "cfg", None) or {}
        return "mffu_builder_25k" if "25" in str(cfg.get("plan") or cfg.get("preset") or "") else "mffu_builder_50k"
    if key == "rapid":
        pre = str(sp.get("preset") or sp.get("plan") or "")
        for ln in g["lanes"]:
            pre = pre or str(((getattr(ln["obj"], "spec", None) or {}).get("preset")) or "")
        return "mffu_rapid_eod_25k" if "25k" in pre.lower() else "mffu_rapid_eod_50k"
    if key == "atlas":
        return "mffu_builder_50k" if "50k" in str(sp.get("plan") or "").lower() else "mffu_builder_25k"
    pre = str(sp.get("preset") or "")
    return pre if pre in MFFU_PLANS else None


def _funded(g) -> bool:
    for ln in g["lanes"]:
        o = ln["obj"]
        try:
            if ln["kind"] == "extra" and getattr(o, "mode", None) == "funded":
                return True
            if ln["kind"] == "acct" and callable(getattr(o, "funded", None)) and o.funded():
                return True
        except Exception:
            continue
    if g["key"] == "lit":
        try:
            from . import lifecycle as LC
            b = LC.book_for(g["main"]["obj"], create=False)
            return bool(b) and b.stage("lit") in ("funded", "payout_ready")
        except Exception:
            return False
    return False


def account_days(bot, g) -> tuple:
    """(traded days set, start day) of a target: every lane's executed trades + the adapters' filled legs, from its start."""
    days, starts = set(), []
    for ln in g["lanes"]:
        days |= _lane_days(ln["kind"], ln["obj"], bot)
        days |= _adapter_days(ln["adapter"])
        s = _lane_start(ln["kind"], ln["obj"], bot)
        if s:
            starts.append(str(s)[:10])
    start = max(starts) if starts else None
    a = (_book(bot)["st"].get("acc") or {}).get(g["key"]) or {}
    days |= {d for d in (a.get("last"), a.get("marked")) if d}
    return ({d for d in days if not start or d >= start}, start)


def _stood_down(bot, g, now) -> str | None:
    """Why the account takes no trade at all now (passed / failed / locked / lost / stuck / locked out today), else None."""
    try:
        from . import lifecycle as LC
        if LC.is_stood_down(bot, g["key"]):
            b = LC.book_for(bot, create=False)
            return f"MFFU stage {b.stage(g['key']) if b else 'stood down'}"
    except Exception:
        pass
    today = trading_day(now)
    for ln in g["lanes"]:
        o = ln["obj"]
        try:
            if ln["kind"] == "lit":
                s = ((getattr(bot, "state", None) or {}).get("eval_life") or {}).get("status")
                if s in ("passed", "failed"):
                    return f"eval {s}"
            elif ln["kind"] == "acct":
                from . import account_b as AB
                s = (o.eval_view(now) or {}).get("status")
                if s in AB.STOP_STATUSES:
                    return f"account {s}"
            elif ln["kind"] == "extra":
                lk = getattr(o, "lock", None)
                if lk and lk.get("day") == today:
                    return f"locked out today: {lk.get('reason')}"
        except Exception as e:  # noqa: BLE001
            return f"status unreadable ({e.__class__.__name__})"
    return None


def _facts(bot, g, now) -> dict | None:
    """{"start", "balance", "floor", "day_pnl"} the firm's way, from engine/lifecycle's facts (None = unknown: no trade)."""
    from . import lifecycle as LC
    key, obj = g["key"], g["main"]["obj"]
    today = trading_day(now)
    try:
        if key == "lit":
            f = LC.lit_facts(bot, now)
            day = float((bot.eval_days() or {}).get(today) or 0.0)
        elif key == "atlas":
            f = LC.atlas_facts(obj, now)
            day = LC._today_pnl(obj, today)
        elif key == "rapid":
            ra = getattr(bot, "acct_r", None)
            lane = next((ln["obj"] for ln in g["lanes"] if ln["kind"] == "extra"), None)
            f = LC.rapid_facts(ra, lane, now)
            day = LC._today_pnl(ra if ra is not None else lane, today)
        else:
            f = LC.extra_facts(obj, now)
            day = LC._today_pnl(obj, today)
    except Exception:
        return None
    if not f or f.get("balance") is None or f.get("floor") is None:
        return None
    return {"start": float(f.get("start") or 0.0), "balance": float(f["balance"]), "floor": float(f["floor"]), "day_pnl": float(day)}


def _price(bot, px=None, bar_t=None):
    """(price, bar time): the poll's last 1m close, else the last bar the bot kept."""
    if px is not None:
        return float(px), int(bar_t or 0)
    try:
        b = (getattr(bot, "bars_tail", None) or [])[-1]
        return float(b["close"]), int(b["time"])
    except Exception:
        return None, 0


def _releases(now) -> list:
    try:
        from .multi_account import tier1_releases
        return list(tier1_releases(trading_day(now)))
    except Exception:
        return []


def news_block(now, hold_s: int = HOLD_S, releases=None) -> str | None:
    """A Tier-1 release within NEWS_PAD_S of the whole hold (entry .. exit + a minute)."""
    for r in (_releases(now) if releases is None else releases):
        if r - NEWS_PAD_S <= now + hold_s + 60 and now < r + NEWS_PAD_S:
            return f"Tier-1 release at {_et(r):%H:%M} ET"
    return None


def _others_side(bot, g):
    """(dirs of every OTHER lane / account holding or entering, why when one is unknown) for the no-hedge rule."""
    dirs, unknown = set(), None
    mine = {id(ln["obj"]) for ln in g["lanes"]}
    mine_ad = {id(ln["adapter"]) for ln in g["lanes"]}
    for ln in lanes(bot):
        if id(ln["obj"]) in mine:
            continue
        if g["nt"] and ln["nt"] == g["nt"]:
            continue
        busy, d, why = _lane_open(ln["kind"], ln["obj"], bot)
        if busy:
            if d in (1, -1):
                dirs.add(d)
            else:
                unknown = f"{ln['key']}: {why}"
        if ln["adapter"] is not None and id(ln["adapter"]) not in mine_ad:
            busy, d, why = _adapter_open(ln["adapter"])
            if busy:
                if d in (1, -1):
                    dirs.add(d)
                else:
                    unknown = f"{ln['key']}: {why}"
    return dirs, unknown


def opposite(bot, d: int) -> str | None:
    """A strategy wants direction d while a keep-alive of direction -d is open (multi_account.opposite_open asks before every
    extra-account / primary entry): the keep-alive yields, closed at market at once. None = no keep-alive against d (or it is
    flat now), else why the entry must wait (the close is not confirmed yet). Never raises."""
    if not _wanted(bot):
        return None
    try:
        with _MX:
            b = _book(bot)
            T = None
            for key, a in (b["st"].get("acc") or {}).items():
                if a.get("phase") not in ("sending", "open", "closing") or int(a.get("dir") or 0) != -int(d):
                    continue
                T = targets(bot) if T is None else T
                g = next((x for x in T if x["key"] == key), None)
                ad = g["adapter"] if g else None
                if ad is None or _leg_of(ad, int(a["entry_t"])) is None:
                    continue                             # its bracket is gone: flat (the next tick books it)
                res = _send(ad, {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": "exit", "qty": QTY,
                                 "reason": "KEEP-ALIVE", "entry_t": int(a["entry_t"])})
                a.update(phase="closing", close_at=int(getattr(bot, "clock", time.time)()), closes=int(a.get("closes") or 0) + 1,
                         yielded=True)
                _save_book(bot, b)
                _log(bot, "order", f"{key}: keep-alive closed for a strategy entry the other way "
                                   f"({'ok' if res.get('ok') else res.get('error')})")
                if not res.get("ok") or _leg_of(ad, int(a["entry_t"])) is not None:
                    return f"hedging guard: the keep-alive trade on {a.get('label') or key} is closing (not confirmed yet)"
    except Exception as e:  # noqa: BLE001
        return f"hedging guard: keep-alive state unreadable ({e.__class__.__name__})"
    return None


# ------------------------------------------------------------------------------------------------ alerts
def _alert(bot, kind: str, p: dict) -> str:
    """kind "problem": engine/notify.instant_problem (the private ntfy topic); kind "trade": an entry / exit notice
    (engine/push.pc_notify). Only the real bot sends; a test sets ALERT_HOOK. Never raises."""
    try:
        if ALERT_HOOK is not None:
            ALERT_HOOK(kind, dict(p))
            return "hook"
        if not is_real(bot):
            return "not the real bot"
        if kind == "problem":
            from . import notify
            return notify.instant_problem(dict(p))
        from . import push
        push.pc_notify(dict(p))
        return "queued"
    except Exception as e:  # noqa: BLE001
        return f"failed: {e.__class__.__name__}"


def _once(st: dict, key: str) -> bool:
    if key in st["sent"]:
        return False
    st["sent"].append(key)
    return True


def _log(bot, kind, text):
    try:
        bot._log(kind, f"[keep-alive] {text}")
    except Exception:
        pass


def _note(bot, st, key, text, now):
    """Log a skip reason once per account, day and reason."""
    k = f"{key}:{trading_day(now)}:{text[:60]}"
    if k in st["notes"]:
        return
    st["notes"][k] = trading_day(now)
    _log(bot, "system", f"{key}: no keep-alive now: {text}")


# ------------------------------------------------------------------------------------------------ the tick
def tick(bot, now=None, px=None, bar_t=None, may_open: bool = True) -> list:
    """Once per poll (LiveBot._keepalive_tick): close an open keep-alive after hold_s, finish / report it, then (may_open:
    after the poll's routing, with fresh bars) send the heads-up / warnings and open a keep-alive where one is due. Returns
    what happened (tests). Never raises."""
    out = []
    if not _wanted(bot):
        return out
    try:
        with _MX:
            now = int(now if now is not None else bot.clock())
            book = _book(bot)
            st = book["st"]
            active = any(a.get("phase") in ("sending", "open", "closing") for a in (st.get("acc") or {}).values())
            if not may_open and not active:
                return out                                 # the adapter-tick call: nothing open = nothing to do
            C = load_config(bot)
            T = targets(bot)
            dirty = _manage(bot, st, C, T, now, px, out, late=not may_open) if active else False
            if may_open:
                dirty = _plan_all(bot, st, C, T, now, px, bar_t, out) or dirty
            if dirty or out:
                _save_book(bot, book)
    except Exception as e:  # noqa: BLE001
        _log(bot, "error", f"keep-alive tick failed: {e.__class__.__name__}: {e}")
    return out


def _leg_of(ad, entry_t, open_only=True):
    try:
        from .ninjatrader import OPEN_STATUSES
        for lg in list(getattr(ad, "legs", None) or []):
            if isinstance(lg, dict) and int(lg.get("entry_t") or 0) == int(entry_t) and (not open_only or lg.get("status") in OPEN_STATUSES):
                return lg
        if not open_only:
            for lg in reversed(list(getattr(ad, "history", None) or [])):
                if isinstance(lg, dict) and int(lg.get("entry_t") or 0) == int(entry_t):
                    return lg
    except Exception:
        return None
    return None


def _push_ids(ad):
    pa = getattr(ad, "push_as", None) if isinstance(getattr(ad, "push_as", None), dict) else {}
    try:
        acct = ad._push_account() if callable(getattr(ad, "_push_account", None)) else getattr(ad, "account", "account")
    except Exception:
        acct = getattr(ad, "account", "account")
    return str(acct or "account"), pa.get("suffix") or "", pa.get("nm")


def _manage(bot, st, C, T, now, px, out, late: bool = False) -> bool:
    """Close / finish the open keep-alives. late (the adapter-tick call, before the poll's data): only a close the
    post-routing call missed (hold + 25 s) or a kill; the normal close runs after the routing with the fresh price."""
    dirty = False
    by_key = {g["key"]: g for g in T}
    hold = C["hold_s"] + 25 if late else max(5, C["hold_s"] - 5)
    for key, a in list((st.get("acc") or {}).items()):
        if a.get("phase") not in ("sending", "open", "closing"):
            continue
        g = by_key.get(key)
        ad = g["adapter"] if g else None
        if ad is None:
            if not a.get("lost_warned"):
                a["lost_warned"] = True
                dirty = True
                _log(bot, "risk", f"{key}: the keep-alive's account is gone from the bot; check NinjaTrader by hand")
            continue
        et_ = int(a["entry_t"])
        lg = _leg_of(ad, et_)
        if lg is not None:
            if lg.get("fill_px") and not a.get("fill"):
                a["fill"], dirty = float(lg["fill_px"]), True
            age = now - int(a.get("sent_at") or et_)
            killed = bool(getattr(bot, "kill", False))
            last_close = int(a.get("close_at") or 0)
            if (age >= hold or killed) and now - last_close >= CLOSE_RETRY_S and int(a.get("closes") or 0) < 4:
                p_now, _ = _price(bot, px)
                a.update(close_at=now, closes=int(a.get("closes") or 0) + 1, phase="closing", px_close=p_now)
                dirty = True
                res = _send(ad, {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": "exit", "qty": QTY,
                                 "reason": "KEEP-ALIVE", "entry_t": et_})
                _log(bot, "order", f"{key}: keep-alive close sent ({'ok' if res.get('ok') else res.get('error')})")
                out.append({"key": key, "do": "close", "ok": bool(res.get("ok"))})
                if res.get("ok"):
                    lg = _leg_of(ad, et_)
            if lg is not None:
                continue
        # no open leg of ours left: closed (our exit, the bracket, the flat-time safety, by hand) or never placed
        done = _leg_of(ad, et_, open_only=False)
        filled = bool(done and int(done.get("filled") or 0) > 0) or bool(a.get("fill"))
        if a.get("phase") == "sending" and done is None and now - int(a.get("sent_at") or et_) < 15:
            continue                                     # the entry may still be on its way (a crash mid-send is retried)
        dirty = True
        if filled:
            fill = float((done or {}).get("fill_px") or a.get("fill") or 0.0)
            why = str((done or {}).get("closed") or "closed").lower()
            exit_reason, ex = "KEEP-ALIVE", a.get("px_close") or _price(bot, px)[0]
            if why.startswith("stop") and done:
                exit_reason, ex = "STOP", done.get("stop")
            elif why.startswith("target") and done:
                exit_reason, ex = "TARGET", done.get("target")
            d = int(a.get("dir") or 1)
            # a CLOSEPOSITION exit has no fill price at NinjaTrader: the last price minus 1 tick (crossing the spread) estimates it
            spread = TICK * PV if exit_reason == "KEEP-ALIVE" else 0.0
            usd = round(((float(ex) - fill) * d * PV - spread if ex and fill else -TICK * PV) * QTY - COMM * QTY, 2)
            a.update(phase="done", last=a.get("day"), usd=usd, exit=exit_reason, closed_at=now, fill=fill or None)
            _log(bot, "risk", f"{key}: keep-alive trade done: {'LONG' if d == 1 else 'SHORT'} 1 MNQ, about {money(usd)} "
                              f"({exit_reason.lower()}); MFFU's 7-day clock restarts from {a.get('day')}")
            acct, sfx, nm = _push_ids(ad)
            from . import push
            p = push.outcome_payload(acct, "LONG" if d == 1 else "SHORT", exit_reason, usd, et_, now, src="pc",
                                     exit_px=ex, qty=QTY, who=f"Keep-alive on {a.get('label') or key}")
            p["key"] = f"{p['key']}{sfx}"
            p["title"] = f"Keep-alive on {a.get('label') or key}: {'LONG' if d == 1 else 'SHORT'} closed"
            p["body"] = (f"{money(usd)} (expected about -{money(EXPECTED_COST)}, at most -{money(WORST_COST)}). "
                         f"MFFU's 7-day clock restarts today.")
            if nm:
                p["nm"] = nm
            out.append({"key": key, "do": "done", "usd": usd, "alert": _alert(bot, "trade", p)})
        else:
            a.update(phase="failed", closed_at=now)
            why = a.get("error") or "the entry never filled"
            _log(bot, "risk", f"{key}: keep-alive not filled ({why})")
            out.append({"key": key, "do": "not_filled", "why": why})
            _final_refusal(bot, st, C, a, key, now, why, out)
    return dirty


def _final_refusal(bot, st, C, a, key, now, why, out):
    """The last attempt of the day failed: tell the owner to place it by hand (once a day)."""
    if int(a.get("tries") or 0) < MAX_TRIES and in_window(now + RETRY_S):
        return                                           # a retry is still possible today
    k = f"ka:refused:{key}:{trading_day(now)}"
    if not _once(st, k):
        return
    w = window(trading_day(now)) or FULL_WINDOW
    p = {"key": k, "code": "keepalive", "title": f"Keep-alive on {a.get('label') or key} did not go through",
         "body": f"{str(why)[:160]}. Place 1 MNQ by hand on this account before {_hm(w[1] + 2)} ET (in and out), then send: "
                 f"python -X utf8 -m engine.keepalive --traded {key}"}
    out.append({"key": key, "do": "refused_alert", "alert": _alert(bot, "problem", p)})


def _send(ad, action) -> dict:
    try:
        res = ad.send(action)
        return res if isinstance(res, dict) else {"ok": False, "error": "no result"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def _plan_all(bot, st, C, T, now, px, bar_t, out) -> bool:
    dirty = False
    acc = st.setdefault("acc", {})
    busy_any = any(a.get("phase") in ("sending", "open", "closing") for a in acc.values())
    today = trading_day(now)
    for g in T:
        key = g["key"]
        on = C["accounts"].get(key) is True
        a = acc.get(key) or {}
        if a.get("day") == today and a.get("phase") == "done":
            continue                                       # this account's keep-alive filled today
        pid = _plan_id(g)
        if pid is None:
            continue
        days, start = account_days(bot, g)
        last = max(days) if days else start
        if not last:
            if on:
                _note(bot, st, key, "no start day and no trade known", now)
            continue
        if today in days:
            continue
        P = plan(last, now, lead=C["lead_sessions"])
        if not (P["due"] or P["eve"]):
            continue
        sd = _stood_down(bot, g, now)
        if sd:
            if on:
                _note(bot, st, key, sd, now)
            continue
        dirty = _warn(bot, st, g, P, on, now, out) or dirty
        if not (on and may_trade_today(C, key, today) and P["due"]):
            continue
        if busy_any:
            _note(bot, st, key, "another keep-alive is open", now)
            continue
        if a.get("day") == today and int(a.get("tries") or 0) >= MAX_TRIES:
            continue
        if a.get("day") == today and now - int(a.get("sent_at") or 0) < RETRY_S:
            continue
        why = _gate(bot, g, pid, now, px, bar_t, C)
        if isinstance(why, str):
            if not why.startswith(("outside the keep-alive window", "no session today")):
                _note(bot, st, key, why, now)            # (waiting for the window is not news)
            w = window(today)
            if w and in_window(now) and _mod(now) >= w[1] - 2:     # the window ends with the keep-alive still blocked
                a_ = {**a, "label": g["label"], "tries": MAX_TRIES}
                _final_refusal(bot, st, C, a_, key, now, f"it was blocked all window: {why}", out)
            continue
        side, ref = why["side"], why["ref"]
        d = 1 if side == "buy" else -1
        stop = round((ref - d * STOP_PTS) / TICK) * TICK
        target = round((ref + d * TARGET_PTS) / TICK) * TICK
        tries = (int(a.get("tries") or 0) if a.get("day") == today else 0) + 1
        a = {**{k: v for k, v in a.items() if k in ("last", "marked")}, "day": today, "phase": "sending", "tries": tries,
             "entry_t": int(now), "sent_at": int(now), "side": side, "dir": d, "ref": ref, "stop": stop, "target": target,
             "label": g["label"], "plan": P, "idle_days": P["idle_days"]}
        acc[key] = a
        _save_book(bot, _book(bot))                      # write-ahead: a crash after the order file still knows it
        ad = g["adapter"]
        label = g["label"]
        action = {"sym": (getattr(bot, "cfg", None) or {}).get("sym", "NQ"), "side": side, "qty": QTY, "entry": ref,
                  "stop": stop, "target": target, "entry_t": int(now), "who": f"Keep-alive on {label}"[:40],
                  "reason": "KEEP-ALIVE", "keepalive": True}
        _log(bot, "order", f"{key}: keep-alive {side.upper()} 1 MNQ @ ~{ref:,.2f}, stop {stop:,.2f}, target {target:,.2f}: "
                           f"no trade for {P['idle_days']} days (MFFU's deadline {P['hard']}), out in {C['hold_s']} s")
        res = _send(ad, action)
        try:
            from . import lifecycle as LC
            LC.after_route(bot, key, label, ad, action, res, acct=g["nt"] or key)
        except Exception:
            pass
        lg = _leg_of(ad, int(now))
        if lg is not None:
            lg["keepalive"] = True                      # marks the keep-alive's leg (restart, history readers)
            try:
                ad._save()
            except Exception:
                pass
        if res.get("ok") or lg is not None:
            a["phase"] = "open"
            if lg is not None and lg.get("fill_px"):
                a["fill"] = float(lg["fill_px"])
        else:
            a.update(phase="failed", error=str(res.get("error") or "refused")[:200], closed_at=int(now))
            _log(bot, "risk", f"{key}: keep-alive refused: {a['error']}")
            _final_refusal(bot, st, C, a, key, now, a["error"], out)
        out.append({"key": key, "do": "open", "ok": bool(res.get("ok")), "side": side, "error": res.get("error")})
        busy_any = True
        dirty = True
    return dirty


def may_trade_today(C, key, today) -> bool:
    return C.get("skip", {}).get(key) != today


def _gate(bot, g, pid, now, px, bar_t, C):
    """Every check before the order; a str = why not, else {"side", "ref"}."""
    if getattr(bot, "kill", False):
        return "kill switch"
    ad = g["adapter"]
    if getattr(ad, "disabled", None):
        return f"adapter disabled: {ad.disabled}"
    if getattr(ad, "readonly", False) or getattr(ad, "killed", False):
        return "adapter read-only / killed"
    if getattr(ad, "nt_reset", None) or getattr(ad, "state_problem", None):
        return "NinjaTrader reset / state problem open"
    if not in_window(now):
        w = window(trading_day(now))
        return f"outside the keep-alive window ({_hm(w[0])}-{_hm(w[1])} ET)" if w else "no session today"
    try:
        from . import lifecycle as LC
        if LC.outside_hours(now):
            return "MFFU flat hours"
    except Exception:
        pass
    nb = news_block(now, C["hold_s"])
    if nb:
        return nb
    h = getattr(bot, "health", None) or {}
    if h.get("entries_blocked") or h.get("stale"):
        return "feed stale: entries blocked"
    ref, bt = _price(bot, px, bar_t)
    if not ref or ref <= 0 or (bt and now - bt > FRESH_BAR_S):
        return "no fresh price"
    for ln in g["lanes"]:
        busy, _, why = _lane_open(ln["kind"], ln["obj"], bot)
        if busy:
            return f"{ln['key']}: {why}"
        busy, _, why = _adapter_open(ln["adapter"])
        if busy:
            return f"{ln['key']}: {why}"
    dirs, unknown = _others_side(bot, g)
    if unknown:
        return f"another account's side is unknown ({unknown})"
    if len(dirs) > 1:
        return "accounts hold both sides"
    side = "sell" if dirs == {-1} else "buy"
    fx = _facts(bot, g, now)
    if fx is None:
        return "balance / floor unknown"
    if fx["balance"] - fx["floor"] < MIN_ROOM:
        return f"room ${fx['balance'] - fx['floor']:,.0f} under ${MIN_ROOM:,.0f}"
    from . import firms
    P = firms.profile(pid, "funded" if _funded(g) else "eval")
    if P is None:
        return f"no firm rules for {pid}"
    mll = float(_num(P.get("dd_amount"), 0.0) or 0.0)
    stt = {"start": fx["start"] or float(_num(P.get("start"), 0.0) or 0.0), "balance": fx["balance"],
           "eod_high": fx["floor"] + mll, "intra_high": fx["floor"] + mll, "day_pnl": fx["day_pnl"], "open_micros": 0}
    d = 1 if side == "buy" else -1
    order = {"sym": "MNQ", "side": side, "qty": QTY, "entry": ref, "stop": ref - d * STOP_PTS, "target": ref + d * TARGET_PTS}
    pos = [{"account": "other", "sym": "NQ", "dir": x} for x in dirs]
    chk = firms.check(P, stt, order, positions=pos, now=now)
    if not chk.get("ok") or int(chk.get("max_qty") or 0) < QTY:
        return "rule check: " + "; ".join(chk.get("block") or ["1 micro does not fit"])[:200]
    return {"side": side, "ref": float(ref)}


def _warn(bot, st, g, P, on, now, out) -> bool:
    """The phone notices before a keep-alive (ON) or a hand trade (OFF). Each once per account and day."""
    key, label = g["key"], g["label"]
    if getattr(g["adapter"], "sim", False) and is_real(bot):
        return False                                     # a Sim account on the real bot: no MFFU rule, no phone warning
    m = _mod(now)
    if m < HEADSUP_FROM or m >= 16 * 60 + 10 or not window(P["today"]) or _et(now).date().isoformat() != P["today"]:
        return False
    w = window(P["act_day"]) if P.get("act_day") else None
    win = f"{_hm(w[0])} ET" if w else "the afternoon"
    left = (_date(P["hard"]) - _date(P["today"])).days
    if P["due"]:
        k = f"ka:{'headsup' if on else 'today'}:{key}:{P['today']}"
        if not _once(st, k):
            return False
        if on:
            p = {"key": k, "code": "keepalive", "soft": True, "title": f"Keep-alive today on {label}",
                 "body": f"No trade for {P['idle_days']} days (MFFU can close an account after {LIMIT_DAYS}). If nothing trades "
                         f"by then, the bot buys 1 MNQ at {win} and sells it {load_config(bot)['hold_s']} s later: about "
                         f"-{money(EXPECTED_COST)}, at most -{money(WORST_COST)}. Skip today: python -X utf8 -m engine.keepalive "
                         f"--skip {key}"}
        else:
            p = {"key": k, "code": "keepalive", "title": f"{label}: TODAY is the last safe day to trade",
                 "body": f"No trade for {P['idle_days']} days. MFFU can close the account after {LIMIT_DAYS} days without a "
                         f"trade{' and a funded one loses ALL its profits' if _funded(g) else ''}. Place 1 MNQ by hand before "
                         f"{_hm((w or FULL_WINDOW)[1] + 2)} ET (in and out, about -{money(EXPECTED_COST)}), then send: "
                         f"python -X utf8 -m engine.keepalive --traded {key}"}
        out.append({"key": key, "do": "headsup" if on else "warn_today", "alert": _alert(bot, "problem", p)})
        return True
    if P["eve"] and not on:
        k = f"ka:eve:{key}:{P['today']}"
        if f"ka:today:{key}:{P['today']}" in st["sent"] or not _once(st, k):
            return False                                 # told "TODAY" already: one warning a day (tomorrow's says TODAY again)
        nd = _date(P["act_day"])
        p = {"key": k, "code": "keepalive", "soft": True, "title": f"{label}: the next session is the last safe day to trade",
             "body": f"No trade for {P['idle_days']} days; MFFU's limit is {P['hard']} ({left} days). If the bot does not "
                     f"trade it first, place 1 MNQ by hand on {nd:%a} {nd:%m-%d} (in and out), or turn on its keep-alive trade."}
        out.append({"key": key, "do": "warn_eve", "alert": _alert(bot, "problem", p)})
        return True
    return False


# ------------------------------------------------------------------------------------------------ status / CLI
def status(bot=None, now=None) -> dict:
    """The switches, each account's last keep-alive and (with a bot) its plan. Never raises."""
    now = int(now or time.time())
    C = load_config(bot)
    st = load_state(state_path_for(bot))
    rows = []
    if bot is not None:
        try:
            for g in targets(bot):
                days, start = account_days(bot, g)
                last = max(days) if days else start
                rows.append({"key": g["key"], "label": g["label"], "on": C["accounts"].get(g["key"]) is True,
                             "mffu": _plan_id(g) is not None, "last_trade": last,
                             "plan": plan(last, now, lead=C["lead_sessions"]) if last else None})
        except Exception as e:  # noqa: BLE001
            rows.append({"error": f"{e.__class__.__name__}: {e}"})
    return {"accounts": C["accounts"], "skip": C["skip"], "hold_s": C["hold_s"], "rows": rows,
            "last": {k: {x: a.get(x) for x in ("day", "phase", "usd", "exit", "tries", "error", "last", "marked")}
                     for k, a in (st.get("acc") or {}).items()},
            "cost": {"expected": EXPECTED_COST, "worst": WORST_COST}}


def mark_traded(key: str, day: str | None = None, path: str | None = None) -> dict:
    """The owner traded an account by hand: its idle clock restarts from `day` (default today)."""
    p = path or state_path_for(None)
    st = load_state(p)
    d = str(day or trading_day(time.time()))[:10]
    _date(d)
    a = st["acc"].setdefault(key, {})
    a["marked"] = max(d, str(a.get("marked") or ""))
    save_state(st, p)
    return a


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="engine.keepalive", description="MFFU 7-day keep-alive trade (OFF by default)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--plan", metavar="LAST_TRADE_DAY")
    ap.add_argument("--on", metavar="KEY")
    ap.add_argument("--off", metavar="KEY")
    ap.add_argument("--skip", metavar="KEY")
    ap.add_argument("--traded", nargs="+", metavar=("KEY", "DAY"))
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    if a.plan:
        p = plan(a.plan, time.time())
        w = window(p["act_day"]) if p["act_day"] else None
        print(f"last trade {p['last']}: MFFU's literal limit {p['hard']}, cautious deadline {p['deadline']}; the keep-alive acts on "
              f"{p['act_day'] or '-'}" + (f" {_hm(w[0])}-{_hm(w[1])} ET" if w else "") + f" (today {p['today']}: due {p['due']}).")
        print(f"cost: about {money(EXPECTED_COST)} (commission ${COMM:.2f} + 1 tick), at most {money(WORST_COST)} (stop {STOP_PTS:g} pts)")
        return 0
    if a.on or a.off:
        C = load_config(None)
        key = a.on or a.off
        if a.on and not a.yes:
            print(f"This lets the bot place a REAL 1-MNQ order on {key} when it has not traded for days (about -{money(EXPECTED_COST)}, "
                  f"at most -{money(WORST_COST)}). The owner's decision only. Add --yes to switch it on.")
            return 2
        C["accounts"][key] = bool(a.on)
        print(f"keep-alive {key}: {'ON' if a.on else 'OFF'} ({save_config(C)}); the bot reads it on its next poll")
        return 0
    if a.skip:
        C = load_config(None)
        C["skip"][a.skip] = trading_day(time.time())
        save_config(C)
        print(f"no keep-alive on {a.skip} today ({C['skip'][a.skip]})")
        return 0
    if a.traded:
        r = mark_traded(a.traded[0], a.traded[1] if len(a.traded) > 1 else None)
        print(f"{a.traded[0]}: hand trade noted on {r['marked']}: the keep-alive counts the 7 days from there")
        return 0
    s = status(None)
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
