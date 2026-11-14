"""Firm rule profiles + the rule engine every fleet account's guards use (engine/fleet.py). Read-only data, no orders.

Data: research/props/firm_rules.json (rebuilt by tools/build_firm_rules.py from the repo's own research: the MFFU rulebook,
the 60-plan prop-firm study, the prop-firm hub). Every value carries "verified" + its source + date; unknown = null (never
guessed), "none" = the rule does not exist on that plan.

  profile(plan_id, stage)        one plan's rules for a stage (eval | funded), flat: start, target, dd_type, dd_amount, lock,
                                 dll, dll_type, max_micros, consistency, min_days, news, flat_by, hedging, bots, payout {...},
                                 + "verified" {field: bool}, "unknown" [fields], "warn" [plain words]
  live_profile(cfg)              the owner's PERSONAL LIVE account: no prop rules, its own stricter risk (max $ a trade, daily
                                 stop, weekly stop, max contracts); labelled LIVE, never sized like an eval
  book(start, closes, today, ...) the account's state from its closed trades: balance, day / week P&L, EOD and intraday
                                 high-water marks, days traded, best day
  floor_room(profile, st)        the max-loss floor and the room to it the FIRM's way: EOD trailing (follows the best closing
                                 balance, open losses count), intraday trailing (follows the best equity, open profit
                                 included), static; the trailing stops at start + lock; + the daily loss left
  check(profile, st, order, positions=..., now=...)
                                 blocks an order that would break the firm's rule (contracts, max-loss floor at the stop,
                                 daily loss, news window, flat time, best-day rule, hedging across ALL the owner's accounts)
                                 and returns the largest size that fits: {"ok", "block", "warn", "max_qty", "room", "floor",
                                 "day_left", "risk_usd"}
  status(profile, st)            eval: running | passed | failed; funded: running | failed (+ payout readiness)

Added 2026-11-14 (team A4, account #4), each active ONLY where the data or the owner sets it (absent = as before):
  max_micros_at(profile, st)     the firm's contract scaling by profit (max_micros_by_profit: LucidFlex funded, Bulenox
                                 Option 2) instead of the flat max; check() caps with it
  on_hold(profile)               a firm "hold" (FundedNext, Bulenox: a written yes to one signal on two accounts is still
                                 missing) blocks every new entry until the owner clears it per account (rules {"hold": "none"})
  payout guard                   owner switch rules {"payout_guard": true} on a funded account: the payout best-day rule
                                 (Lucid 40% of the cycle) as a soft cap on today's winner (payout_cycle(): the cycle's goal)
  status()                       + the cycle's profit goal (cycle_min), profitable days (win_days / win_day_min), the next
                                 payout's cap (max_after_first), a share-of-profit cap (share); inactivity() vs the firm's
                                 inactivity_days (Lucid / FundedNext 30)

  python -X utf8 -m engine.firms --list | --show <plan> [--stage funded]
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "research", "props", "firm_rules.json")
STAGES = ("eval", "funded", "live")
PV = {"NQ": 2.0, "ES": 5.0}                 # $ a point per MICRO (MNQ / MES); a mini is 10 micros
UNDERLYING = {"NQ": "NQ", "MNQ": "NQ", "NQX": "NQ", "ES": "ES", "MES": "ES", "ESX": "ES"}
SLIP_PTS = 0.5                             # a full stop-out assumes 2 ticks of slippage (engine/sizing.TW_DLL_SLIP)
COMM = 1.90                                # $ a micro round trip (engine/sizing.LIVE_COMM)
BEST_DAY_MARGIN = 0.95                     # a best-day rule is met with 5% to spare (engine/multi_account.BEST_DAY_MARGIN)
FLAT_MARGIN_MIN = 5                        # no new entry this close to the firm's flat time
OPTIONAL_FIRM_KEYS = ("inactivity_days", "hold")   # firm rules copied into a profile only when the data has them (2026-11-14)
INACTIVITY_WARN_DAYS = 7                   # the status warns this many days before a firm's inactivity limit
HOLD_CLEARED = ("none", "off", "cleared", "")
LIVE_DEFAULTS = {"max_risk_usd": 150.0, "daily_stop_usd": 300.0, "weekly_stop_usd": 600.0, "max_micros": 5, "start": None}
_CACHE: dict = {"key": None, "d": None}
_MX = threading.Lock()


# ---------------------------------------------------------------------------------------------------------------- data
def load(path: str | None = None) -> dict:
    """firm_rules.json (cached by mtime). Missing / broken -> {"firms": {}, "plans": {}} (every account then refuses)."""
    p = path or RULES_PATH
    try:
        key = (p, os.path.getmtime(p))
    except OSError:
        return {"firms": {}, "plans": {}}
    with _MX:
        if _CACHE["key"] != key:
            try:
                with open(p, encoding="utf-8") as fh:
                    _CACHE.update(key=key, d=json.load(fh))
            except Exception:
                _CACHE.update(key=key, d={"firms": {}, "plans": {}})
        return _CACHE["d"]


def plans(firm: str | None = None, path: str | None = None) -> list:
    P = load(path).get("plans") or {}
    return sorted(k for k, v in P.items() if firm is None or v.get("firm") == firm)


def _val(x):
    return x.get("v") if isinstance(x, dict) else x


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _has(v) -> bool:
    """A numeric limit that exists (not unknown, not "none")."""
    return _num(v) is not None


def profile(plan_id: str, stage: str = "eval", overrides: dict | None = None, path: str | None = None) -> dict | None:
    """The plan's rules for this stage as plain values (+ verified / unknown / warn). None = unknown plan. overrides = the
    owner's values for this account (e.g. a confirmed max contracts), marked verified "owner"."""
    D = load(path)
    p = (D.get("plans") or {}).get(str(plan_id))
    if p is None:
        return None
    stage = "funded" if stage in ("funded", "payout") else "eval"
    firm = (D.get("firms") or {}).get(p.get("firm")) or {}
    blk = dict(p.get("eval") or {})
    if stage == "funded":
        fu = p.get("funded") or {}
        blk.update({k: v for k, v in fu.items()})
    out = {"id": plan_id, "firm_id": p.get("firm"), "firm": firm.get("name") or p.get("firm"), "plan": p.get("name"),
           "size": p.get("size"), "stage": stage, "sizing_preset": p.get("sizing_preset"), "kind": "prop",
           "label": f"{firm.get('name') or p.get('firm')} {p.get('name')}"}
    ver, unknown = {}, []
    for k, x in blk.items():
        out[k] = _val(x)
        ver[k] = bool(isinstance(x, dict) and x.get("verified"))
        if out[k] is None:
            unknown.append(k)
    for k in ("hedging", "bots", "copy_trading", "flat_by", "ninjatrader"):
        x = firm.get(k)
        out[k] = _val(x)
        ver[k] = bool(isinstance(x, dict) and x.get("verified"))
        if out[k] is None:
            unknown.append(k)
    for k in OPTIONAL_FIRM_KEYS:                       # only where the data has them (absent = the profile is as before)
        if k in firm and _val(firm[k]) is not None:
            out[k] = _val(firm[k])
            ver[k] = bool(isinstance(firm[k], dict) and firm[k].get("verified"))
    po = {}
    for k, x in (p.get("payout") or {}).items():
        po[k] = _val(x)
        ver[f"payout.{k}"] = bool(isinstance(x, dict) and x.get("verified"))
        if po[k] is None and stage == "funded":
            unknown.append(f"payout.{k}")
    out["payout"] = po
    out["price"] = _val(p.get("price"))
    for k, v in (overrides or {}).items():
        if v is None:
            continue
        if k == "payout" and isinstance(v, dict):
            out["payout"].update(v)
            for kk in v:
                ver[f"payout.{kk}"] = "owner"
            continue
        out[k] = v
        ver[k] = "owner"
        if k in unknown:
            unknown.remove(k)
    out["verified"], out["unknown"] = ver, unknown
    out["warn"] = _profile_warn(out)
    return out


def _profile_warn(P: dict) -> list:
    w = []
    if P.get("bots") in ("prohibited", "semi_only"):
        w.append(f"{P['firm']} does not allow a fully automated bot ({P['bots']}): paper / Sim only")
    if P.get("bots") == "api_only" or P.get("ninjatrader") is False:
        w.append(f"{P['firm']}: NinjaTrader is not offered for this account: this bot cannot route there")
    if P.get("bots") is None:
        w.append(f"{P['firm']}: bot rule unknown: ask the firm before automating")
    if P.get("copy_trading") is None:
        w.append(f"{P['firm']}: copying between your own accounts is not confirmed: ask support in writing first")
    if on_hold(P):
        w.append(f"{P['firm']}: ON HOLD, no new entry until you clear it (rules {{\"hold\": \"none\"}}): {P['hold']}")
    for k, txt in (("dd_amount", "max loss amount"), ("dd_type", "drawdown type"), ("target", "profit target"),
                   ("max_micros", "max contracts"), ("dll", "daily loss"), ("lock", "where the trailing floor locks"),
                   ("news", "news rule"), ("consistency", "best-day rule")):
        if P.get(k) is None:
            w.append(f"{txt} unknown (not verified): check the firm's page")
    return w


def live_profile(cfg: dict | None = None) -> dict:
    """The owner's personal LIVE account: no prop-firm rules, the bot's own stricter limits (owner's numbers in the fleet
    entry "live": {...}; defaults LIVE_DEFAULTS). Never sized like an eval (engine/fleet.size: fixed $ risk)."""
    c = {**LIVE_DEFAULTS, **{k: v for k, v in (cfg or {}).items() if v is not None}}
    return {"id": "live", "firm_id": "live", "firm": "Personal live", "plan": "LIVE account", "stage": "live", "kind": "live",
            "label": "LIVE (personal)", "start": _num(c.get("start")), "size": _num(c.get("start")), "target": "none",
            "dd_type": "none", "dd_amount": "none", "lock": "none", "dll": float(c["daily_stop_usd"]), "dll_type": "bot",
            "weekly_stop": float(c["weekly_stop_usd"]), "max_risk_usd": float(c["max_risk_usd"]),
            "max_micros": int(c["max_micros"]), "max_minis": None, "consistency": "none", "min_days": "none", "news": "none",
            "flat_by": None, "hedging": "banned_all_accounts", "bots": "own", "copy_trading": "own", "ninjatrader": True,
            "payout": {}, "price": None, "sizing_preset": None,
            "verified": {"dll": "owner", "weekly_stop": "owner", "max_risk_usd": "owner", "max_micros": "owner"},
            "unknown": [], "warn": ["LIVE money: the bot's own stops only (no prop-firm floor); the owner arms it"]}


def max_micros(P: dict) -> int | None:
    m = _num(P.get("max_micros"))
    if m is not None:
        return int(m)
    mi = _num(P.get("max_minis"))
    return int(mi * 10) if mi is not None else None


def _tiers(P: dict):
    """max_micros_by_profit [[profit_from, micros], ...] sorted; None = no contract scaling; [] = unreadable (blocks)."""
    t = P.get("max_micros_by_profit")
    if t in (None, "none"):
        return None
    try:
        out = sorted((float(a), int(m)) for a, m in t)
        return out if out and all(m >= 0 for _, m in out) else []
    except (TypeError, ValueError):
        return []


def max_micros_at(P: dict, st: dict | None = None) -> int | None:
    """The most micros NOW: the flat max_micros, or the firm's contract scaling by profit (max_micros_by_profit: LucidFlex
    funded 20 / 30 / 40 micros at $0 / $1,000 / $2,000, Bulenox Option 2) at the account's profit at the last close
    (balance - today's closed P&L - start), never above the flat max. No scaling in the data = max_micros(P), exactly as
    before. Unreadable scaling = 0 (a broken input blocks)."""
    mx = max_micros(P)
    T = _tiers(P)
    if T is None or st is None:
        return mx
    if not T:
        return 0
    start = float(_num(st.get("start"), _num(P.get("start"), 0.0)) or 0.0)
    prof = float(_num(st.get("balance"), start)) - float(_num(st.get("day_pnl"), 0.0)) - start
    q = T[0][1]
    for a, m in T:
        if prof >= a - 1e-9:
            q = m
    return min(q, mx) if mx is not None else q


def on_hold(P: dict) -> bool:
    """The firm's (or plan's) "hold": a reason string = no new entry until the owner clears it (rules {"hold": "none"})."""
    h = P.get("hold")
    return isinstance(h, str) and h.strip().lower() not in HOLD_CLEARED


def payout_cycle(P: dict, st: dict) -> dict:
    """The funded payout cycle from the book: {"n" payouts so far, "prev" (the cycle's closed profit before today), "day"
    (today's closed P&L), "start_bal" (balance above start when the cycle began), "cap" (the next payout's max: payout.max,
    then payout.max_after_first), "goal" (the cycle profit a full next payout needs: buffer + cap - start_bal)}."""
    po = P.get("payout") or {}
    n = int(_num(st.get("payouts_n"), 0) or 0)
    lp, today = st.get("last_payout"), st.get("today") or ""
    days = st.get("days") or {}
    prev = sum(v for d, v in days.items() if (not lp or d > lp) and d < today) + (float(st.get("prior") or 0.0) if not lp else 0.0)
    day = float(_num(st.get("day_pnl"), 0.0))
    start = float(_num(st.get("start"), _num(P.get("start"), 0.0)) or 0.0)
    start_bal = float(_num(st.get("balance"), start)) - start - prev - day
    cap = _num(po.get("max_after_first")) if n > 0 and _has(po.get("max_after_first")) else _num(po.get("max"))
    buf = _num(po.get("buffer"), 0.0) or 0.0
    goal = (buf + cap - start_bal) if cap is not None else None
    return {"n": n, "prev": round(prev, 2), "day": round(day, 2), "start_bal": round(start_bal, 2), "cap": cap,
            "goal": round(goal, 2) if goal is not None else None}


def underlying(sym) -> str:
    return UNDERLYING.get(str(sym or "NQ").upper(), str(sym or "NQ").upper())


def micros_of(order: dict) -> int:
    """The order's size in micro-equivalents (the bot routes MNQ micros; contract "NQ" / "ES" = minis x 10)."""
    q = int(_num(order.get("qty"), 0) or 0)
    c = str(order.get("contract") or "").upper()
    return q * 10 if c in ("NQ", "ES") else q


# ---------------------------------------------------------------------------------------------------------------- state
def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(float(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def week_of(day: str) -> str:
    d = _dt.date.fromisoformat(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def book(start: float, closes, today: str, prior: float = 0.0, payouts: dict | None = None, open_pnl: float = 0.0,
         open_micros: int = 0) -> dict:
    """The account's state from its closed trades [(day, exit_t, pnl), ...] (+ the P&L before the bot, the payouts taken):
    balance, profit, day / week P&L, eod_high (best closing balance of an earlier day), intra_high (best balance after any
    close, open profit added when given), days traded, best day, per-day P&L."""
    start = float(start)
    pays = {str(k): float(v) for k, v in (payouts or {}).items()}
    rows = sorted((str(d), int(t or 0), float(p or 0.0)) for d, t, p in closes)
    bal = start + float(prior or 0.0)
    eod_hi = intra_hi = bal
    days, cur_day = {}, None
    # day by day: the day's trades, then (an earlier day) its closing balance sets the EOD high, then that day's payout is
    # withdrawn (it lowers the balance, never the floor: engine/sizing.funded_state)
    by_day = {}
    for d, t, p in rows:
        by_day.setdefault(d, []).append((t, p))
    for d in sorted(set(by_day) | set(pays)):
        for t, p in sorted(by_day.get(d, [])):
            bal += p
            days[d] = round(days.get(d, 0.0) + p, 2)
            intra_hi = max(intra_hi, bal)
        if d < today:
            eod_hi = max(eod_hi, bal)
        bal -= pays.get(d, 0.0)
    wk = week_of(today)
    day_pnl = days.get(today, 0.0)
    week_pnl = round(sum(v for d, v in days.items() if d <= today and week_of(d) == wk), 2)
    won = [v for d, v in days.items() if v > 0]
    profit = round(bal - start + sum(pays.values()), 2)              # trading profit (payouts are withdrawals, not losses)
    return {"start": start, "balance": round(bal, 2), "profit": profit, "day_pnl": round(day_pnl, 2),
            "week_pnl": week_pnl, "eod_high": round(eod_hi, 2), "intra_high": round(max(intra_hi, bal + max(0.0, open_pnl)), 2),
            "open_pnl": round(float(open_pnl or 0.0), 2), "open_micros": int(open_micros or 0),
            "days_traded": sum(1 for d, v in days.items() if abs(v) > 1e-9 and d < today) + (1 if abs(day_pnl) > 1e-9 else 0),
            "best_day": round(max(won), 2) if won else 0.0, "days": days, "payouts": round(sum(pays.values()), 2), "today": today,
            "last_payout": max(pays) if pays else None, "prior": round(float(prior or 0.0), 2), "payouts_n": len(pays)}


def floor_room(P: dict, st: dict) -> dict:
    """Max-loss floor + room the firm's way, and the daily / weekly loss left. Unknown drawdown type = intraday (the most
    conservative); unknown lock = never locks (the floor keeps trailing: less room); unknown amount = no room (refuses)."""
    start = float(_num(st.get("start"), _num(P.get("start"), 0.0)) or 0.0)
    bal = float(_num(st.get("balance"), start))
    op = float(_num(st.get("open_pnl"), 0.0))
    eq = bal + op
    mll = _num(P.get("dd_amount"))
    typ = P.get("dd_type")
    lock = _num(P.get("lock"))
    out = {"equity": round(eq, 2), "balance": round(bal, 2), "dd_type": typ, "floor": None, "room": None, "locked": False, "hw": None}
    if P.get("kind") == "live" or typ == "none":
        out["floor"] = None
        out["room"] = None
    elif mll is None:
        out["room"] = 0.0
        out["why"] = "max loss amount unknown: no room assumed"
    else:
        if typ == "static":
            hw = start
            fl = start - mll
        elif typ == "eod":
            hw = max(start, float(_num(st.get("eod_high"), start)))
            fl = hw - mll
        else:                                           # intraday (or unknown: the strictest reading)
            hw = max(start, float(_num(st.get("intra_high"), start)), eq)
            fl = hw - mll
        if lock is not None and typ != "static" and fl >= start + lock:
            fl = start + lock
            out["locked"] = True
        out.update(floor=round(fl, 2), room=round(eq - fl, 2), hw=round(hw, 2))
    dll = _num(P.get("dll"))
    day = float(_num(st.get("day_pnl"), 0.0)) + op
    out["day_left"] = round(dll + min(0.0, day), 2) if dll is not None else None
    wk = _num(P.get("weekly_stop"))
    out["week_left"] = round(wk + min(0.0, float(_num(st.get("week_pnl"), 0.0)) + op), 2) if wk is not None else None
    return out


# ---------------------------------------------------------------------------------------------------------------- check
def _risk_pts(order: dict):
    r = _num(order.get("risk_pts"))
    if r is None and order.get("entry") is not None and order.get("stop") is not None:
        r = abs(float(order["entry"]) - float(order["stop"]))
    return r


def _tgt_pts(order: dict):
    t = _num(order.get("tgt_pts"))
    if t is None and order.get("entry") is not None and order.get("target") is not None:
        t = abs(float(order["target"]) - float(order["entry"]))
    return t


def news_window(P: dict, now, releases=None):
    """The Tier-1 release whose flat window holds `now` (P["news"] = {"flat_min_before", "flat_min_after"}), else None."""
    rule = P.get("news")
    if not isinstance(rule, dict) or now is None:
        return None
    pre = 60 * float(rule.get("flat_min_before") or 0)
    post = 60 * float(rule.get("flat_min_after") or 0)
    if releases is None:
        try:
            from .multi_account import tier1_releases
            releases = tier1_releases(trading_day(now))
        except Exception:
            releases = []
    for r in releases or []:
        if r - pre <= now < r + post:
            return int(r)
    return None


def _flat_cut(P: dict, now):
    fb = P.get("flat_by")
    if not fb or now is None:
        return None
    try:
        hh, mm = (int(x) for x in str(fb).split(":"))
    except Exception:
        return None
    e = _et(now)
    m = e.hour * 60 + e.minute
    lim = hh * 60 + mm
    return fb if lim - FLAT_MARGIN_MIN <= m < 18 * 60 else None


def hedge_conflict(order: dict, positions) -> str | None:
    """Another of the owner's accounts holds the opposite side on the same underlying (MFFU bans long + short on one
    underlying across your own accounts; the owner's rule for every account). positions = [{"account", "sym", "dir"}]."""
    d = 1 if str(order.get("side") or "buy") in ("buy", "long", "1") or order.get("dir") == 1 else -1
    if order.get("dir") in (1, -1):
        d = int(order["dir"])
    u = underlying(order.get("sym"))
    for p in positions or ():
        try:
            if underlying(p.get("sym")) == u and int(p.get("dir") or 0) == -d:
                return (f"hedging: {p.get('account') or 'another account'} holds a {'SHORT' if d == 1 else 'LONG'} "
                        f"{u} position (no long + short on one underlying across your accounts)")
        except Exception:
            continue
    return None


def check(P: dict, st: dict, order: dict, positions=(), now=None, releases=None, slip_pts: float = SLIP_PTS,
          comm: float = COMM) -> dict:
    """Would this order break the firm's rule? {"ok", "block": [why], "warn": [...], "max_qty", "room", "floor",
    "day_left", "risk_usd" (a full stop-out at the size asked), "rules": {...}}. Never raises (a broken input blocks)."""
    try:
        return _check(P, st, order, positions, now, releases, slip_pts, comm)
    except Exception as e:
        return {"ok": False, "block": [f"rule check failed ({e.__class__.__name__}: {e})"], "warn": [], "max_qty": 0}


def _check(P, st, order, positions, now, releases, slip_pts, comm):
    blocks, warns = [], []
    q = micros_of(order)
    u = underlying(order.get("sym"))
    pv = PV.get(u, 2.0)
    fr = floor_room(P, st)
    caps = []                                          # (max micros, why)
    risk = _risk_pts(order)
    loss1 = (risk + slip_pts) * pv + comm if risk else None
    # 0. the owner's hold for this firm (a written yes still missing): no new entry until it is cleared
    if on_hold(P):
        blocks.append(f"on hold ({P.get('firm')}): {P['hold']}")
    # 1. contracts (the flat max, or the firm's contract scaling by profit when the data has one)
    mx = max_micros_at(P, st)
    held = int(_num(st.get("open_micros"), 0) or 0)
    if mx is None:
        warns.append("firm max contracts unknown: the bot's own cap applies")
    else:
        sc = "" if mx == max_micros(P) else " now (the firm's contract scaling at this profit)"
        caps.append((mx - held, f"max {mx} micros ({mx // 10} minis) on this plan{sc}" + (f", {held} open" if held else "")))
    # 2. the max-loss floor at the stop
    if P.get("kind") != "live":
        room = fr.get("room")
        if room is not None and room <= 0:
            blocks.append(f"max-loss floor reached: equity ${fr['equity']:,.0f} vs floor ${fr['floor'] or 0:,.0f} (account failed)")
        elif room is not None and loss1:
            caps.append((math.floor((room - 1e-6) / loss1), f"a stop-out must stay above the {fr['dd_type'] or 'trailing'} floor "
                                                             f"${fr['floor']:,.0f} (room ${room:,.0f})"))
        if fr.get("why"):
            blocks.append(fr["why"])
    # 3. daily loss (hard = the account fails; soft = trading paused for the day; live = the bot's own daily stop)
    dl = fr.get("day_left")
    if dl is not None:
        kind = P.get("dll_type") or "unknown type"
        if dl <= 0:
            blocks.append(f"daily loss limit reached today ({kind}): no new entry until the next session")
        elif loss1:
            caps.append((math.floor((dl - 1e-6) / loss1), f"{kind} daily loss: ${dl:,.0f} left today"))
    elif P.get("dll") is None and P.get("kind") != "live":
        warns.append("daily loss rule unknown")
    wl = fr.get("week_left")
    if wl is not None:
        if wl <= 0:
            blocks.append("weekly stop reached: no new entry until Monday")
        elif loss1:
            caps.append((math.floor((wl - 1e-6) / loss1), f"weekly stop: ${wl:,.0f} left this week"))
    mr = _num(P.get("max_risk_usd"))
    if mr is not None and loss1:
        caps.append((math.floor((mr + 1e-6) / loss1), f"max ${mr:,.0f} risk a trade"))
    # 4. best-day (consistency) rule in the eval: a winner today stays under share x target
    cons = _num(P.get("consistency"))
    tgt = _tgt_pts(order)
    if cons and P.get("stage") == "eval" and _has(P.get("target")):
        cap_usd = cons * float(P["target"]) * BEST_DAY_MARGIN - max(0.0, float(_num(st.get("day_pnl"), 0.0)))
        if tgt and tgt * pv - comm > 0:
            caps.append((math.floor(cap_usd / (tgt * pv - comm)), f"best-day rule {cons * 100:.0f}%: a winner pays <= ${cap_usd:,.0f} today"))
        else:
            warns.append(f"best-day rule {cons * 100:.0f}%: target distance unknown")
    elif P.get("consistency") is None and P.get("stage") == "eval":
        warns.append("best-day rule unknown")
    # 4b. OFF by default (owner switch "payout_guard": true): the funded payout best-day rule (Lucid 40% of the cycle) as a
    #     SOFT cap: today may pay at most max(share x the cycle's goal, share/(1-share) x the cycle's earlier profit) x 0.95
    #     (engine/sizing.funded_qty cons_aware, the same formula); never below 1 micro (a big day only delays a payout)
    pc = _num((P.get("payout") or {}).get("consistency"))
    if P.get("payout_guard") is True and pc and 0 < pc < 1 and P.get("stage") == "funded":
        cy = payout_cycle(P, st)
        if cy["goal"] is not None and tgt and tgt * pv - comm > 0:
            day_max = max(pc * max(0.0, cy["goal"]), pc / (1.0 - pc) * max(0.0, cy["prev"])) * BEST_DAY_MARGIN
            cap_usd = day_max - max(0.0, cy["day"])
            caps.append((max(1, math.floor(cap_usd / (tgt * pv - comm))),
                         f"payout best-day rule {pc * 100:.0f}%: today <= ${day_max:,.0f} (cycle goal ${cy['goal']:,.0f})"))
        else:
            warns.append(f"payout best-day rule {pc * 100:.0f}%: cycle goal or target distance unknown")
    # 5. news window, flat time
    r = news_window(P, now, releases)
    if r is not None:
        blocks.append(f"news rule: flat around the Tier-1 release at {_et(r):%H:%M} ET")
    fc = _flat_cut(P, now)
    if fc:
        blocks.append(f"too close to the firm's flat time {fc} ET")
    # 6. hedging across ALL the owner's accounts (always: MFFU's rule and the owner's)
    h = hedge_conflict(order, positions)
    if h:
        blocks.append(h)
    # 7. stop distance
    if not risk or risk <= 0:
        blocks.append("no stop distance: the floor / daily loss at the stop cannot be checked")
    mq = q
    why_cap = []
    for c, w in caps:
        c = max(0, int(c))
        if c < mq:
            mq = c
            why_cap.append(w)
    if q > 0 and mq < 1 and not blocks:
        blocks.append("1 micro does not fit: " + "; ".join(why_cap[-2:]))
    elif mq < q and not blocks:
        warns.append(f"size {q} -> {mq}: " + "; ".join(why_cap[-2:]))
    if P.get("unknown"):
        warns.append("unverified / unknown rules: " + ", ".join(P["unknown"][:6]))
    return {"ok": not blocks, "block": blocks, "warn": warns, "max_qty": int(max(0, mq)) if not blocks else 0,
            "room": fr.get("room"), "floor": fr.get("floor"), "day_left": dl, "week_left": wl, "locked": fr.get("locked"),
            "risk_usd": round(loss1 * q, 2) if loss1 else None, "equity": fr.get("equity")}


def status(P: dict, st: dict) -> dict:
    """{"status": running | passed | failed | stuck, "why", "to_target", "payout": {...} on a funded account}."""
    fr = floor_room(P, st)
    room = fr.get("room")
    if P.get("kind") == "live":
        return {"status": "running", "why": None, **fr}
    if room is not None and room <= 0:
        return {"status": "failed", "why": f"the max-loss floor ${fr['floor']:,.0f} was reached", **fr}
    out = {"status": "running", "why": None, **fr}
    prof = float(_num(st.get("profit"), 0.0))
    if P.get("stage") == "eval" and _has(P.get("target")):
        need = float(P["target"]) - prof
        out["to_target"] = round(need, 2)
        md = _num(P.get("min_days"), 1.0) or 1.0
        if need <= 0:
            if int(st.get("days_traded") or 0) < md:
                out["why"] = f"target reached; {int(md)} trading days needed ({int(st.get('days_traded') or 0)} so far)"
            else:
                cons = _num(P.get("consistency"))
                if cons and prof > 0 and float(st.get("best_day") or 0) > cons * prof:
                    out["why"] = f"target reached but the best day is {float(st['best_day']) / prof * 100:.0f}% of the profit (rule {cons * 100:.0f}%): trade more days"
                else:
                    out.update(status="passed", why="profit target reached")
    if P.get("stage") == "funded":
        po = P.get("payout") or {}
        buf = _num(po.get("buffer"))
        mn = _num(po.get("min"), 0.0) or 0.0
        above = prof - float(_num(st.get("payouts"), 0.0)) - (buf or 0.0) if buf is not None else None
        # the payout cycle = the days after the last payout: the best day vs the cycle's profit (consistency, not a breach:
        # you trade more days) and the traded days a cycle the firm asks for
        lp = st.get("last_payout")
        cyc = {d: v for d, v in (st.get("days") or {}).items() if not lp or d > lp}
        c_prof = round(sum(cyc.values()) + (float(st.get("prior") or 0.0) if not lp else 0.0), 2)   # the P&L before the bot: this cycle
        c_best = max([v for v in cyc.values() if v > 0], default=0.0)
        cons = _num(po.get("consistency"))
        cons_ok = None if po.get("consistency") is None else (True if not cons else (c_prof > 0 and c_best <= cons * c_prof + 1e-9))
        need_d = _num(po.get("min_days"))
        days_ok = None if po.get("min_days") is None else (True if not need_d else sum(1 for v in cyc.values() if abs(v) > 1e-9) >= need_d)
        money_ok = bool(above is not None and above >= mn and mn >= 0 and buf is not None)
        why = [] if money_ok else [f"${max(0.0, (mn or 0) - (above or 0)):,.0f} more above the buffer" if above is not None else "buffer unknown"]
        if cons_ok is False:
            why.append(f"best day ${c_best:,.0f} is {c_best / c_prof * 100 if c_prof > 0 else 100:.0f}% of the cycle's ${c_prof:,.0f} "
                       f"(rule {cons * 100:.0f}%): trade more days")
        if days_ok is False:
            why.append(f"{int(need_d)} traded days a cycle needed")
        # 2026-11-14 (only where the data has them; absent = as before): the cycle's own profit goal (Lucid / FundedNext
        # $500), the profitable-day count (LucidFlex 5 days >= $150), the next payout's cap (Lucid $2,000 then $2,500) and a
        # share-of-profit cap on the request (LucidFlex 50%)
        cmin = _num(po.get("cycle_min"))
        cyc_ok = None if cmin is None else c_prof >= cmin - 1e-9
        if cyc_ok is False:
            why.append(f"the cycle made ${c_prof:,.0f} of the ${cmin:,.0f} it needs")
        wd, wmin = _num(po.get("win_days")), _num(po.get("win_day_min"), 0.01)
        win_ok = None if not wd else sum(1 for v in cyc.values() if v >= wmin - 1e-9) >= wd
        if win_ok is False:
            why.append(f"{int(wd)} days of at least ${wmin:,.0f} a cycle needed ({sum(1 for v in cyc.values() if v >= wmin - 1e-9)} so far)")
        cap_next = payout_cycle(P, st)["cap"]
        max_req = None
        if above is not None and cap_next is not None:
            max_req = min(cap_next, max(0.0, above))
            sh = _num(po.get("share"))
            if sh:
                max_req = min(max_req, sh * max(0.0, c_prof))
            max_req = round(max_req, 2)
        out["payout"] = {"above_buffer": round(above, 2) if above is not None else None, "buffer": buf, "min": mn,
                         "max": _num(po.get("max")), "split": _num(po.get("split")), "cycle_profit": c_prof, "best_day": round(c_best, 2),
                         "consistency_ok": cons_ok, "days_ok": days_ok,
                         "ready": bool(money_ok and cons_ok is not False and days_ok is not False and cyc_ok is not False
                                       and win_ok is not False), "why": why,
                         "unknown": [k for k in ("buffer", "min", "max", "split", "consistency") if po.get(k) is None]}
        if cmin is not None or wd or _has(po.get("max_after_first")) or _num(po.get("share")):
            out["payout"].update(cycle_ok=cyc_ok, win_days_ok=win_ok, next_cap=cap_next, max_request=max_req,
                                 payouts_n=int(_num(st.get("payouts_n"), 0) or 0), max_payouts=_num(po.get("max_payouts")))
    ina = inactivity(P, st)
    if ina is not None:
        out["inactivity"] = ina
    return out


def inactivity(P: dict, st: dict) -> dict | None:
    """Days since the last traded day vs the firm's inactivity limit (Lucid / FundedNext 30 calendar days: the account is
    deleted / breached). None when the firm has no such rule in the data or nothing was traded yet."""
    lim = _num(P.get("inactivity_days"))
    days = [d for d, v in (st.get("days") or {}).items() if abs(v) > 1e-9]
    if lim is None or not days or not st.get("today"):
        return None
    try:
        idle = (_dt.date.fromisoformat(str(st["today"])) - _dt.date.fromisoformat(max(days))).days
    except ValueError:
        return None
    warn = idle >= lim - INACTIVITY_WARN_DAYS
    return {"days_idle": idle, "limit": int(lim), "warn": warn,
            "why": (f"no trade for {idle} days: {P.get('firm')} deletes an account after {int(lim)} days without one" if warn else None)}


def describe(P: dict) -> list:
    """The plan's rules in plain words (docs/ADD_ACCOUNT.md, the Fleet page)."""
    if P is None:
        return ["unknown plan"]
    if P.get("kind") == "live":
        return [f"LIVE money, no prop firm: max ${P['max_risk_usd']:,.0f} risk a trade, daily stop ${P['dll']:,.0f}, weekly stop "
                f"${P['weekly_stop']:,.0f}, max {P['max_micros']} micros. The owner arms it; the bot never sizes it like an eval."]
    m = lambda v: "unknown" if v is None else ("none" if v == "none" else f"${float(v):,.0f}")
    t = P.get("dd_type")
    dd = {"eod": "end-of-day trailing (the floor follows your best CLOSING balance; open losses still count)",
          "intraday": "intraday trailing (the floor follows your best balance INCLUDING open profit)",
          "static": "static (the floor never moves)"}.get(t, "type unknown")
    lk = _num(P.get("lock"))
    out = [f"Max loss {m(P.get('dd_amount'))}, {dd}" + (f"; it stops trailing at start + ${lk:,.0f}" if lk is not None and t != "static" else "")]
    if P.get("stage") == "eval":
        out.append(f"Profit target {m(P.get('target'))}; min {P.get('min_days') if P.get('min_days') is not None else 'unknown'} trading days")
        c = _num(P.get("consistency"))
        out.append("No best-day rule in the eval" if P.get("consistency") == "none" else
                   (f"Best day <= {c * 100:.0f}% of the profit" if c else "Best-day rule unknown"))
    dl = P.get("dll")
    out.append("No daily loss limit" if dl == "none" else f"Daily loss {m(dl)} ({P.get('dll_type') or 'type unknown'}: "
               + ("the account fails)" if P.get("dll_type") == "hard" else "trading pauses for the day)"))
    mx = max_micros(P)
    out.append(f"Max {mx} micros ({mx // 10} minis)" if mx else "Max contracts unknown")
    T = _tiers(P)
    if T:
        out.append("Contracts scale with the profit: " + ", ".join(f"{m} micros from ${a:,.0f}" for a, m in T))
    nw = P.get("news")
    out.append("News: no restriction" if nw == "none" else ("News: flat 2 min before to 2 min after Tier-1 releases"
                                                            if isinstance(nw, dict) else "News rule unknown"))
    if P.get("flat_by"):
        out.append(f"Flat by {P['flat_by']} ET")
    out.append({"banned_all_accounts": "No long + short on one underlying, across ALL your accounts",
                "banned": "No hedging"}.get(P.get("hedging"), "Hedging rule unknown (the bot never hedges across your accounts anyway)"))
    po = P.get("payout") or {}
    if P.get("stage") == "funded":
        out.append(f"Payouts: buffer {m(po.get('buffer'))}, ${_num(po.get('min'), 0) or 0:,.0f}-{m(po.get('max'))} a request, "
                   f"split {(_num(po.get('split')) or 0) * 100:.0f}%" + (f", best day <= {float(po['consistency']) * 100:.0f}% of the cycle"
                                                                        if _num(po.get('consistency')) else ""))
        extra = []
        if _has(po.get("max_after_first")):
            extra.append(f"then up to {m(po.get('max_after_first'))} a request")
        if _num(po.get("cycle_min")):
            extra.append(f"the cycle must make {m(po.get('cycle_min'))}")
        if _num(po.get("win_days")):
            extra.append(f"{int(_num(po['win_days']))} days of {m(po.get('win_day_min') or 0.01)}+ a cycle")
        if _num(po.get("share")):
            extra.append(f"a request <= {float(po['share']) * 100:.0f}% of the cycle's profit")
        if extra and _num(po.get("max_payouts")):       # (plans without the 2026-11-14 payout fields read as before)
            extra.append(f"{int(_num(po['max_payouts']))} payouts, then the firm's live review")
        if extra:
            out.append("Payout rules: " + "; ".join(extra))
    if _num(P.get("inactivity_days")):
        out.append(f"No trade for {int(_num(P['inactivity_days']))} days = the firm deletes the account")
    if on_hold(P):
        out.append(f"ON HOLD (no new entry): {P['hold']}")
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.firms", description="firm rule profiles (research/props/firm_rules.json)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--stage", default="eval", choices=["eval", "funded"])
    a = ap.parse_args(argv)
    D = load()
    if a.show:
        P = profile(a.show, a.stage)
        if P is None:
            print(f"unknown plan {a.show} (python -m engine.firms --list)")
            return 1
        print(f"{P['label']} ({a.stage})" + (f", owner's price ${P['price']:,.2f}" if P.get("price") else ""))
        for ln in describe(P):
            print("  " + ln)
        for w in P["warn"]:
            print("  ! " + w)
        return 0
    for fid, f in (D.get("firms") or {}).items():
        print(f"{f['name']}: bots {_val(f.get('bots'))}, hedging {_val(f.get('hedging'))}")
        for pid in f.get("plans") or []:
            P = profile(pid)
            nv = sum(1 for v in P["verified"].values() if v)
            print(f"  {pid:22s} {P['plan']:16s} target {P.get('target')}, max loss {P.get('dd_amount')} {P.get('dd_type')}, "
                  f"daily {P.get('dll')}, {max_micros(P)} micros; {nv} values verified, {len(P['unknown'])} unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
