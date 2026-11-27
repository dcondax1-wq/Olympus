"""The Order Flow LANE: of_paper's lane A decisions routed to a NinjaTrader SIMULATION account (night-of-lane 2026-11-27).

OFF by default. Built so "next week on Sim102" is one switch (its OWN simulation account, red team 2026-11-27: never fights
atlas_exec's Sim101 week or START's Sim101 test for the account lock; Sim102 must exist in NinjaTrader); an eval / funded account is NOT possible from this file: any
account that is not a NinjaTrader simulation account (Sim101, SimNNN, PlaybackNNN) is refused, whatever the switch says. A
future owner switch + phrase for a real account is deliberately not built (owner's yes + the forward gate first).

Decisions: the SAME code as the paper bot. Each run feeds the live tick file (Documents\\NinjaTrader 8\\le_ticks\\NQ_<day>.csv)
through engine.of_paper (read_live -> summary_of -> step), into the lane's own copy of the paper state
(data/of_lane_state.json "paper"; of_paper's own data/of_paper.json is never touched). Every lane A row of_paper marks
"taken" is a routing candidate; nothing else ever is. No second implementation of the rule.

Guards, in order (any one = not routed, logged in plain words; the paper row is unchanged):
  switch        data/of_lane.json {"on": true}; absent / unreadable = OFF
  sim only      the account must be a NinjaTrader simulation account (engine.ninjatrader.is_sim); the adapter config never
                carries the arming keys or the live phrase, so its own live gate refuses a real account a second time
  kill          data/live_state.json "kill" (the owner's kill) or data/of_lane_kill: no new entry, an open trade is flattened
  calendar      CME full closure, weekend, and the half-day cut (engine.cme_calendar.entry_cut: 15 min before an early close)
  late          the decision is acted on only within MAX_LATE_S of the signal bar's close (a stale signal is never chased)
  news          no entry within news_min (2) minutes of a Tier-1 release (engine.guards.news_hit)
  one position  the lane's own open trade, or ANY position NinjaTrader shows on the account's NQ instruments
  day cap       max_per_day entries a trading day (data/of_lane.json, default 1 = the tested book: the FIRST absorbed signal of
                the day; night-of-daycap 2026-11-27, later trades lost after the Monday fix). Counted from today's lane trade log
                (+ the adapter's saved history), never from memory, so a runner restart cannot reset it. Exits are never capped.
  hedge         another account (any account in NinjaTrader's outgoing folder) holds the opposite NQ side (engine.firms)
  size          engine.sizing.second_qty at a fixed $ risk (risk_usd, default $200; 1 micro's stop-out above it = skip)
  firm rules    engine.firms.check with the plan the lane is held to (default the MFFU Builder 50K eval): the soft daily
                loss (DLL), the EOD trailing max-loss floor, contracts, flat time; the lane's own closed trades are its book
Entry = E5 (night-of-exec 2026-11-27: market at the real delay gives away ~18 ticks; a limit at the level keeps lane A): price
already at / beyond the swept level -> market; else a resting LIMIT at the level for 300 s (the adapter's opt-in entry_limit),
cancelled when the stop trades first (no trade), else at 300 s a market entry (guards checked again, never chased past the stop).
Exits: the adapter's OCO bracket (stop 1 tick beyond the signal bar = the paper stop, target 2R from the ACTUAL fill), its
flat-time close (15:55 ET, or 5 min before a CME early close), a kill flatten. One position at a time.

Files: data/of_lane.json (switch), data/of_lane_state.json (lane book), data/ninjatrader_state_oflane.json (the adapter's
write-ahead state: an open bracket survives a restart; engine.fill_audit reads every ninjatrader_state_*.json as a lane),
logs/ninjatrader_oif_oflane.log (every order line; engine.datapipe.day_fills reads it as lane "oflane" into the unified fill
log). All gitignored.

    python -X utf8 -m engine.of_lane --sim on|off|status     the switch (plain words)
    python -X utf8 -m engine.of_lane tick                     one run (nothing happens while OFF and flat)
    python -X utf8 -m engine.of_lane loop                     every 15 s until 16:10 ET (the PC: a detached child)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

from . import of_paper as OP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
CFG_NAME, STATE_NAME, NT_STATE_NAME, KILL_NAME = "of_lane.json", "of_lane_state.json", "ninjatrader_state_oflane.json", "of_lane_kill"
AUDIT_NAME = "ninjatrader_oif_oflane.log"           # engine.datapipe._lane_of -> lane "oflane"
LANE = "oflane"
ACCOUNT_HOWTO = "Accounts tab > Add Sim account"
RUN_NAME, STOP_NAME = "of_lane_run.json", "of_lane_stop"   # the loop's heartbeat / the 16:15 stop flag (engine/ops_checks.of_lane_kick)
FALLBACK = "Sim101"
DEFAULT_CFG = {"on": False, "account": "Sim102", "auto_account": True, "risk_usd": 200.0, "max_micros": 10, "plan": "mffu_builder_50k",
               "stage": "eval", "news_min": 2, "max_per_day": 1}
E5_WAIT_S = 300             # E5 entry (research/writeups/ofexec-2026-11-27.md, engine/of_paper._fill_e5 on night-of-paperv2):
E5_RR = 2.0                 # a resting limit AT the swept level for 300 s, cancelled if the stop trades first, else market; 2R from the fill
MAX_LATE_S = 120            # act on a decision only within 2 min of the signal bar's close
STEP_EVERY = 20             # s between two paper steps inside a 5m bar (a new bar close always steps)
FLAT_MOD = 955
SESSION_FROM = 9 * 60 + 45  # of_paper lane A: 09:45-15:00 bar opens
PV, COMM = 2.0, 1.90        # MNQ $ a point, the live commission a micro round trip (engine.sizing.LIVE_COMM)
MAX_ROWS = 400


def _p(root, *a):
    return os.path.join(root, *a)


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=float)
    from . import fsutil
    fsutil.replace(tmp, p)


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


# ------------------------------------------------------------------------------------------------ the switch
def load_cfg(root: str = ROOT) -> dict:
    c = _rj(_p(root, "data", CFG_NAME))
    out = dict(DEFAULT_CFG)
    if isinstance(c, dict):
        out.update({k: v for k, v in c.items() if k in DEFAULT_CFG or k in ("set_at", "nt_folder", "account_note")})
    else:
        out["on"] = False                       # absent / unreadable = OFF
    out["on"] = out.get("on") is True
    return out


def sim_problem(account) -> str | None:
    """None when the account is a NinjaTrader simulation account, else why it is refused (no switch can change that here)."""
    from .ninjatrader import is_sim
    a = str(account or "").strip()
    if not a:
        return "no account named"
    if not is_sim(a):
        return (f"account '{a}' is not a NinjaTrader simulation account (Sim101 / SimNNN / PlaybackNNN): the order-flow lane "
                "trades simulation only until the forward test passes and the owner says yes")
    return None


def account_seen(account, folder: str | None = None, now=None) -> bool | None:
    """True = NinjaTrader lists the account (a fresh le_feed\\accounts.csv row, or a position file of it in outgoing\\);
    False = accounts.csv is fresh and the account is not in it (it does not exist / is not connected); None = cannot tell."""
    a = str(account or "").strip().lower()
    try:
        from . import broker_balance as BB
        from .ninjatrader import default_folder
        folder = folder or default_folder()
        r = BB.read(folder, now=now)
        if r.get("ok"):
            return any(n.lower() == a for n in (r.get("rows") or {}))
        out = os.path.join(folder, "outgoing")
        if os.path.isdir(out) and any(n.lower().endswith(f"_{a}_position.txt") for n in os.listdir(out)):
            return True
    except Exception:  # noqa: BLE001
        pass
    return None


def account_words(account, folder: str | None = None, now=None) -> str | None:
    """Plain words when the lane's account is missing / unverified in NinjaTrader, else None."""
    seen = account_seen(account, folder, now)
    if seen is False:
        return f"{account} must exist in NinjaTrader ({ACCOUNT_HOWTO}): NinjaTrader does not list it now"
    if seen is None:
        return f"could not check that {account} exists (no fresh le_feed accounts list): {account} must exist in NinjaTrader ({ACCOUNT_HOWTO})"
    return None


def sim101_holders(folder: str | None = None) -> list:
    """Who else uses Sim101 now (then the lane never falls back to it): ATLAS's Sim101 week (engine/atlas_exec), an ATLAS / Rapid /
    combo lane configured on Sim101, or a running process holding NinjaTrader's Sim101 account lock (START's Sim test, a bot)."""
    out = []
    try:
        from . import atlas_exec as AX
        if AX.is_on():
            out.append("ATLAS's Sim101 week is on")
        out += [f"{w} trades {n}" for w, n in AX.lanes() if str(n or "").strip().lower() == FALLBACK.lower()]
    except Exception as e:  # noqa: BLE001
        out.append(f"the ATLAS lanes are unreadable ({e.__class__.__name__})")
    try:
        from .ninjatrader import LOCK_DIR, default_folder
        lp = os.path.join(folder or default_folder(), LOCK_DIR, f"{FALLBACK}.lock")
        if os.path.exists(lp):
            fh = open(lp, "a+")
            try:
                if os.name == "nt":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                out.append("another bot process holds the Sim101 account lock")
            finally:
                fh.close()
    except Exception:  # noqa: BLE001
        pass
    return out


def pick_account(folder: str | None = None, now=None) -> tuple[str, str | None]:
    """(account, plain words or None). Sim102 when NinjaTrader lists it; when NinjaTrader's fresh account list has NO Sim102 and
    nothing else uses Sim101: Sim101 (said so), so the owner need not create an account first; else Sim102 + the how-to."""
    seen = account_seen("Sim102", folder, now)
    if seen is True:
        return "Sim102", None
    if seen is False:
        busy = sim101_holders(folder)
        if not busy:
            return FALLBACK, (f"Sim102 is not in NinjaTrader, so the lane uses {FALLBACK} (nothing else uses it now). Its own account "
                              f"later: NinjaTrader {ACCOUNT_HOWTO} > Sim102")
        return "Sim102", f"Sim102 must exist in NinjaTrader ({ACCOUNT_HOWTO}); {FALLBACK} is busy ({'; '.join(busy)})"
    return "Sim102", account_words("Sim102", folder, now)


def refresh_account(root: str = ROOT, now=None) -> dict:
    """Re-pick the automatic account (once a day before the runner starts) while the lane holds no trade. Returns the cfg."""
    c = load_cfg(root)
    if not c.get("auto_account") or not c.get("on"):
        return c
    S = load_state(root)
    if any(t["status"] in ("sending", "open", "fallback") for t in S["trades"]) or _nt_open(root):
        return c
    acct, note = pick_account(c.get("nt_folder"), now)
    if acct != c["account"] or note != c.get("account_note"):
        c.update(account=acct, account_note=note)
        _wj(_p(root, "data", CFG_NAME), {k: c[k] for k in list(DEFAULT_CFG) + ["set_at", "nt_folder", "account_note"] if k in c})
    return c


def set_switch(on: bool, account: str | None = None, root: str = ROOT) -> tuple[bool, str]:
    c = load_cfg(root)
    note = None
    if account:
        c["account"] = str(account).strip()
        c["auto_account"] = False
    elif on and c.get("auto_account", True):
        c["account"], note = pick_account(c.get("nt_folder"))
    c["account_note"] = note
    if on:
        bad = sim_problem(c["account"])
        if bad:
            return False, "NOT switched on: " + bad + "."
    c["on"] = bool(on)
    c["set_at"] = _et(time.time()).strftime("%Y-%m-%d %H:%M ET")
    _wj(_p(root, "data", CFG_NAME), {k: c[k] for k in list(DEFAULT_CFG) + ["set_at", "nt_folder", "account_note"] if k in c})
    if on:
        aw = note or account_words(c["account"], c.get("nt_folder"))
        return True, (f"Order-flow lane ON for {c['account']} (simulation money)." + (f" Note: {aw}." if aw else "") + f" It trades the paper bot's absorbed level fades, "
                      f"${c['risk_usd']:,.0f} risk a trade, max {c['max_micros']} micros, one trade at a time, flat by 15:55 ET.")
    return True, "Order-flow lane OFF: no new trades. An open simulation trade keeps its stop and target and the 15:55 close."


# ------------------------------------------------------------------------------------------------ the book
def new_state(day=None) -> dict:
    return {"v": 1, "lane": LANE, "day": day, "paper": OP.new_state(day), "last_step": 0, "trades": [], "closes": [],
            "log": [], "killed_day": None}


def load_state(root: str = ROOT) -> dict:
    s = _rj(_p(root, "data", STATE_NAME))
    return s if isinstance(s, dict) and isinstance(s.get("trades"), list) else new_state()


def save_state(S: dict, root: str = ROOT):
    S["trades"] = S["trades"][-MAX_ROWS:]
    S["closes"] = S["closes"][-MAX_ROWS:]
    S["log"] = S["log"][-MAX_ROWS:]
    _wj(_p(root, "data", STATE_NAME), S)


def _note(S, now, text, **kw):
    S["log"].append({"t": int(now), "text": text, **kw})


def make_adapter(cfg: dict, root: str = ROOT, nd: str | None = None, clock=None):
    """The existing NinjaTrader adapter on the lane's (simulation) account, its own state + audit files. Never armed."""
    from .ninjatrader import NinjaTraderAdapter
    acfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": cfg["account"], "nt_contract": "micro",
            "params": {"max_micros": int(cfg.get("max_micros") or 10), "flat_mod": FLAT_MOD},
            "nt_session_from": SESSION_FROM, "nt_all_hours": False, "nt_max_entries_day": 6, "nt_file_tag": LANE,
            "nt_state_path": _p(root, "data", NT_STATE_NAME), "nt_audit_log": _p(root, "logs", AUDIT_NAME)}
    if nd or cfg.get("nt_folder"):
        acfg["nt_folder"] = nd or cfg["nt_folder"]
    return NinjaTraderAdapter(acfg, clock=clock)


def _nt_open(root) -> bool:
    """The adapter's write-ahead state holds an open bracket (then the lane keeps managing it even while OFF)."""
    from .ninjatrader import OPEN_STATUSES
    s = _rj(_p(root, "data", NT_STATE_NAME), {}) or {}
    return any(isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES for lg in s.get("legs") or [])


def _nt_open_account(root) -> str | None:
    """The account of an open bracket in the adapter's write-ahead state (it saves its own account name), else None."""
    s = _rj(_p(root, "data", NT_STATE_NAME), {}) or {}
    return str(s["account"]) if _nt_open(root) and s.get("account") else None


def book(S: dict, P: dict, today: str, open_pnl: float = 0.0, open_micros: int = 0) -> dict:
    from . import firms
    return firms.book(float(P.get("start") or 0.0), [(c["day"], c["t"], c["pnl"]) for c in S["closes"]], today,
                      open_pnl=open_pnl, open_micros=open_micros)


def other_positions(ad) -> list:
    """Every NQ position NinjaTrader reports in its outgoing folder, ANY account: [{"account", "sym", "dir", "qty"}]. An
    unreadable folder raises (the caller refuses the entry: the hedge guard fails closed)."""
    out = []
    for n in os.listdir(ad.outgoing):
        if not n.lower().endswith("_position.txt"):
            continue
        stem = n[:-len("_position.txt")]
        if "_" not in stem:
            continue
        inst, acct = stem.split("_", 1)
        from .ninjatrader import _read_text, parse_position
        pos = parse_position(_read_text(os.path.join(ad.outgoing, n)))
        if not pos or pos["side"] == "FLAT":
            continue
        out.append({"account": acct, "sym": inst.split(" ")[0], "dir": 1 if pos["side"] == "LONG" else -1, "qty": pos["qty"],
                    "instrument": inst})
    return out


# ------------------------------------------------------------------------------------------------ guards
def entry_guards(S, cfg, ad, row, now, est, killed, news_events=None, skip_late: bool = False, self_entry_t=None) -> tuple[list, int, dict]:
    """(reasons not to route, micros, the firm check) for one taken paper row. Pure reads."""
    from . import cme_calendar as CAL, firms, guards, sizing
    why = []
    d = int(row["d"])
    stop = float(row["stop"])
    day = row["day"]
    e = _et(now)
    mod = e.hour * 60 + e.minute
    if not cfg.get("on"):
        why.append("lane is OFF")
    bad = sim_problem(cfg.get("account"))
    if bad:
        why.append(bad)
    if killed:
        why.append("kill switch on")
    if account_seen(cfg.get("account"), getattr(ad, "folder", None), now=now) is False:
        why.append(f"{cfg.get('account')} must exist in NinjaTrader ({ACCOUNT_HOWTO})")
    if e.weekday() >= 5 or CAL.full_closure(day):
        why.append("no CME session today")
    cut = CAL.entry_cut(day, FLAT_MOD)
    if mod >= cut:
        why.append(f"after the entry cut {cut // 60:02d}:{cut % 60:02d} ET" + (" (CME early close)" if cut < FLAT_MOD else ""))
    late = now - (int(row["t_sig"]) + 300)
    if late > MAX_LATE_S and not skip_late:
        why.append(f"decision {late:.0f} s after the signal bar closed (max {MAX_LATE_S} s): not chased")
    nm = cfg.get("news_min")
    if nm:
        hit = guards.news_hit(int(now), int(nm), events=news_events)
        if hit:
            why.append(f"news blackout: {hit}")
    open_tr = [t for t in S["trades"] if t["status"] in ("sending", "open")]
    if open_tr:
        why.append("the lane already has an open trade")
    cap = day_cap(cfg)
    used = day_entries(S, day, ad, exclude=self_entry_t)
    rank = signal_rank(S, row, day)
    if used >= cap:
        why.insert(0, f"skipped: day cap ({used} of {cap} entr{'y' if cap == 1 else 'ies'} today; data/of_lane.json max_per_day)")
    elif rank >= cap:
        # red team #37: the tested book is the paper bot's FIRST taken signal of the day, whatever happened to it. A first signal
        # the lane refused (news / size / late / hedge) or whose E5 limit was cancelled (stop traded first) gives that day NO
        # trade there; trading a later signal instead would add exactly the later-in-the-day trades that lost.
        why.insert(0, f"skipped: day cap (paper signal {rank + 1} of the day; the tested book takes only the first "
                      f"{cap}; data/of_lane.json max_per_day)")
    try:
        pos = other_positions(ad)
    except Exception as ex:  # noqa: BLE001
        pos = None
        why.append(f"NinjaTrader positions unreadable ({ex.__class__.__name__}): hedge check fails closed")
    if pos is not None:
        mine = [p for p in pos if p["account"].lower() == str(cfg["account"]).lower()]
        if mine:
            why.append(f"{cfg['account']} already holds {'LONG' if mine[0]['dir'] == 1 else 'SHORT'} {mine[0]['qty']} "
                       f"{mine[0]['instrument']}: one position per account")
    risk = (est - stop) * d
    if risk <= 0:
        why.append("price is already through the stop")
        return why, 0, {}
    sz = sizing.second_qty(risk, usd=float(cfg.get("risk_usd") or 200.0), cfg={"mode": "normal"},
                           max_micros=int(cfg.get("max_micros") or 10))
    q = int(sz.get("qty") or 0)
    if q < 1:
        why.append("; ".join(sz.get("reasons") or ["size 0"]))
    P = firms.profile(cfg.get("plan") or DEFAULT_CFG["plan"], cfg.get("stage") or "eval") or {"kind": "prop"}
    st = book(S, P, day)
    order = {"side": "buy" if d == 1 else "sell", "dir": d, "qty": max(1, q), "sym": "MNQ", "entry": est, "stop": stop,
             "target": est + OP.RR * risk * d}
    others = [p for p in (pos or []) if p["account"].lower() != str(cfg["account"]).lower()]
    fc = firms.check(P, st, order, positions=others, now=int(now), releases=[])
    why += list(fc.get("block") or [])
    if q >= 1 and fc.get("ok"):
        q = min(q, int(fc.get("max_qty") or 0))
        if q < 1:
            why.append("the firm rules leave no size")
    return why, q, fc


def signal_rank(S: dict, row: dict, day: str) -> int:
    """0 for the paper bot's first taken lane A signal of `day` (the tested book), 1 for the second, ... (by signal time)."""
    rows = [r for r in ((S.get("paper") or {}).get("rows") or [])
            if r.get("lane") == "A" and r.get("day") == day and r.get("taken")]
    ts = sorted({int(r.get("t_sig") or 0) for r in rows})
    t = int(row.get("t_sig") or 0)
    return sum(1 for x in ts if x < t)


def day_cap(cfg: dict) -> int:
    """max_per_day from data/of_lane.json: a whole number >= 1; missing / unreadable / below 1 = 1 (the tested book)."""
    try:
        v = cfg.get("max_per_day", 1)
        if isinstance(v, bool):
            return 1
        n = int(v)
        return n if n >= 1 and float(v) == n else 1
    except (TypeError, ValueError):
        return 1


ENTRY_STATUSES = ("sending", "open", "fallback", "unknown")   # live / pending / unclear = an entry used (fail closed)


def _ekey(entry_t) -> int:
    return int(entry_t) // 300                     # the signal's 5m slot: a market fallback (entry_t + 1) is the same entry


def day_entries(S: dict, day: str, ad=None, exclude=None) -> int:
    """Entries the lane used on `day`: today's trades that filled, or are still live / pending / unclear (a cancelled limit
    that never filled is no entry), plus the adapter's saved legs / history that filled that day. exclude = one trade's
    entry_t (its own market fallback is not a second entry)."""
    keys = set()
    for t in S.get("trades") or []:
        if t.get("day") == day and (t.get("filled") or t.get("status") in ENTRY_STATUSES) and t.get("entry_t") is not None:
            keys.add(_ekey(t["entry_t"]))
    for lg in list(getattr(ad, "legs", None) or []) + list(getattr(ad, "history", None) or []):
        try:
            et_ = int(lg.get("entry_t") or 0)
        except (TypeError, ValueError):
            continue
        if et_ and OP.et_day(et_) == day and (lg.get("filled") or lg in (getattr(ad, "legs", None) or [])):
            keys.add(_ekey(et_))
    if exclude is not None:
        keys.discard(_ekey(exclude))
    return len(keys)


# ------------------------------------------------------------------------------------------------ one run
def _last_px(x) -> float | None:
    return float(x.price.iloc[-1]) if x is not None and len(x) else None


def _sync_trades(S, ad, now, last_px):
    """Open lane trades vs the adapter: the real fill, and once the bracket is gone, the exit (stop / target fill, else the
    last trade for a flat-time / kill close, marked est) and $ after costs."""
    live = {int(lg["entry_t"]): lg for lg in ad.legs}
    for tr in S["trades"]:
        if tr["status"] not in ("sending", "open"):
            continue
        lg = live.get(int(tr["entry_t"]))
        if lg is not None:
            tr["status"] = "open"
            for k in ("entry_id", "stop_id", "target_id", "instrument"):
                tr[k] = lg.get(k)
            if lg.get("filled"):
                tr["filled"], tr["fill_px"] = int(lg["filled"]), lg.get("fill_px")
            continue
        if tr["status"] == "sending" and not tr.get("entry_id"):
            tr.update(status="unknown", why="restart while sending: the adapter holds no such order (not resent)")
            _note(S, now, "a send was interrupted by a restart; NinjaTrader shows no order of it: NOT resent")
            continue
        h = next((x for x in reversed(list(ad.history)) if int(x.get("entry_t") or 0) == int(tr["entry_t"])), None)
        if h is not None and h.get("filled"):
            tr["filled"], tr["fill_px"] = int(h["filled"]), h.get("fill_px")
        if not tr.get("filled"):
            ent = ad.read_order(tr["entry_id"]) if tr.get("entry_id") else None
            if ent and ent.get("filled"):
                tr["filled"], tr["fill_px"] = int(ent["filled"]), ent.get("avg")
        if not tr.get("filled"):
            if tr.get("how") == "limit" and not tr.get("stop_first"):
                tr.update(status="fallback", why=f"limit at {tr.get('limit')} not filled in {E5_WAIT_S} s: market entry next")
                _note(S, now, f"{tr['id']}: limit not filled in {E5_WAIT_S} s -> market entry")
                continue
            tr.update(status="closed", why="no fill: stopped before entry" if tr.get("stop_first")
                      else (h or {}).get("closed") or "entry never filled", pnl=0.0, exit_t=int(now))
            continue
        ex, why, est = None, (h or {}).get("closed") or "closed", False
        for k, nm in (("stop_id", "stop"), ("target_id", "target")):
            o = ad.read_order(tr[k]) if tr.get(k) else None
            if o and o["state"] == "FILLED" and o.get("avg"):
                ex, why = float(o["avg"]), nm
        if ex is None:
            ex, est = (last_px if last_px is not None else float(tr["fill_px"])), True
        q = int(tr["filled"])
        pnl = round((ex - float(tr["fill_px"])) * tr["d"] * q * PV - COMM * q, 2)
        tr.update(status="closed", exit_px=round(ex, 2), exit_est=est, why=why, pnl=pnl, exit_t=int(now),
                  R=round((ex - float(tr["fill_px"])) * tr["d"] / max(1e-9, abs(float(tr["fill_px"]) - float(tr["stop"]))), 3))
        S["closes"].append({"day": tr["day"], "t": int(now), "pnl": pnl, "id": tr["id"]})
        _note(S, now, f"closed {tr['id']} ({why}{', price est.' if est else ''}): {'+' if pnl >= 0 else '-'}${abs(pnl):,.0f}")


def tick(now: float | None = None, root: str = ROOT, nd: str | None = None, ad=None, force_step: bool = False,
         news_events=None, clock=None) -> dict:
    """One lane run. Returns {"S", "routed": [...], "ad"}. While OFF and flat it touches nothing (no adapter, no lock)."""
    now = float(now or time.time())
    cfg = load_cfg(root)
    cfg["_root"] = root
    S = load_state(root)
    day = OP.et_day(now)
    if S.get("day") != day:
        keep = {k: S.get(k) for k in ("closes",)}
        S = new_state(day)
        S.update({k: v for k, v in keep.items() if v is not None})
    open_tr = [t for t in S["trades"] if t["status"] in ("sending", "open")]
    if not cfg["on"] and not open_tr and ad is None and not _nt_open(root):
        return {"off": True, "S": S, "routed": []}
    nd = nd or cfg.get("nt_folder") or OP.nt_dir()
    # red team 2026-11-27: an open trade is always managed on ITS account (remembered on the trade / the adapter's state), never on
    # whatever data/of_lane.json says now: an edit mid-trade cannot orphan the Sim trade's stop / target / 15:55 close
    held = next((t.get("account") for t in open_tr if t.get("account")), None) or _nt_open_account(root)
    acct = held or cfg.get("account")
    if sim_problem(acct):
        if ad is not None:
            ad.release_lock()
        return {"refused": sim_problem(acct), "S": S, "routed": []}
    if ad is not None and str(ad.account) != str(acct):
        ad.release_lock()
        ad = None
    if ad is None:
        ad = make_adapter({**cfg, "account": acct}, root, nd, clock=clock)
    out = {"S": S, "routed": [], "ad": ad}
    killed = OP._kill(root) or os.path.exists(_p(root, "data", KILL_NAME))
    ad.tick()
    x = OP._read_live(day, nd) if nd else None
    if x is not None and len(x):
        x = x[x.t_ns <= int(now * 1e9)]
    last_px = _last_px(x)
    _sync_trades(S, ad, now, last_px)
    if killed and (ad.legs or any(t["status"] == "open" for t in S["trades"])) and S.get("killed_day") != day:
        r = ad.kill(scope="account")
        S["killed_day"] = day
        _note(S, now, f"kill switch: lane flattened on {cfg['account']} ({'confirmed' if r.get('ok') else r.get('error')})")
        _sync_trades(S, ad, now, last_px)
    slot = int(now) // 300
    stepped = False
    if x is not None and len(x) and OP.in_window(now) and (force_step or slot != int(S.get("last_step") or 0) // 300
                                                           or now - float(S.get("last_step") or 0) >= STEP_EVERY):
        pday, Rp = OP._prev_summary(day, nd, root)
        R = OP.summary_of(x, day)
        if R:
            P = S["paper"] if (S.get("paper") or {}).get("day") == day else OP.new_state(day)
            P["live"] = True
            tt = x.t_ns.to_numpy(np.int64) // 1_000_000
            S["paper"] = OP.step(P, day, R, Rp, pday, tt, x.price.to_numpy(float), now, kill=killed)
            S["last_step"] = int(now)
            stepped = True
    if stepped:
        done = {t["row_id"] for t in S["trades"]}
        for row in S["paper"]["rows"]:
            if row.get("lane") != "A" or row.get("day") != day or not row.get("taken") or row["id"] in done:
                continue
            d = int(row["d"])
            lv = float(row["level_px"])
            limit = (float(last_px) - lv) * d > 0          # not yet back at the level: rest a limit there (E5)
            est = lv if limit else round(float(last_px) + OP.SLIP * d, 2)
            why, q, fc = entry_guards(S, cfg, ad, row, now, est, killed, news_events)
            risk = (est - float(row["stop"])) * d
            tr = {"id": f"L|{row['id']}", "row_id": row["id"], "day": day, "d": d, "t_sig": row["t_sig"],
                  "entry_t": int(row["t_sig"]) + 300, "level": row["level"], "stop": row["stop"], "est": est,
                  "how": "limit" if limit else "market", "limit": lv if limit else None,
                  "target": round(est + OP.RR * risk * d, 2) if risk > 0 else None, "qty": q, "decided_t": int(now)}
            if why:
                tr.update(status="refused", why="; ".join(why))
                S["trades"].append(tr)
                _note(S, now, f"not routed {row['id']}: {tr['why']}")
                continue
            S["trades"].append(tr)                          # _send saves it "sending" first: a restart never sends it twice
            _send(S, ad, tr, cfg, now, out)
            _sync_trades(S, ad, now, last_px)
    # E5: the stop traded before the resting limit filled -> cancel it (no trade); a timed-out limit -> one market entry
    if x is not None and len(x):
        tt_ms = x.t_ns.to_numpy(np.int64) // 1_000_000
        pp = x.price.to_numpy(float)
        for tr in S["trades"]:
            if tr["status"] != "open" or tr.get("how") != "limit" or tr.get("filled") or tr.get("stop_first"):
                continue
            m = tt_ms >= int(tr["decided_t"]) * 1000
            hit = (pp[m] >= float(tr["stop"])) if tr["d"] == -1 else (pp[m] <= float(tr["stop"]))
            if hit.any():
                tr["stop_first"] = True
                r = ad.cancel_entry(tr["entry_t"], "stop traded before the limit filled")
                _note(S, now, f"{tr['id']}: the stop traded before the limit at {tr['limit']} filled: cancelled "
                              f"({'sent' if r.get('ok') else r.get('error')})")
        _sync_trades(S, ad, now, last_px)
    for tr in [t for t in S["trades"] if t["status"] == "fallback"]:
        row = next((r for r in S["paper"]["rows"] if r["id"] == tr["row_id"]), None)
        if row is None or last_px is None:
            continue
        est = round(float(last_px) + OP.SLIP * tr["d"], 2)
        why, q, _fc = entry_guards(S, cfg, ad, row, now, est, killed, news_events, skip_late=True, self_entry_t=tr["entry_t"])
        risk = (est - float(tr["stop"])) * tr["d"]
        if why:
            tr.update(status="refused", why="market fallback not sent: " + "; ".join(why))
            _note(S, now, f"{tr['id']}: {tr['why']}")
            continue
        for k in ("entry_id", "stop_id", "target_id", "filled", "fill_px"):
            tr.pop(k, None)
        tr.update(how="market after limit", entry_t=int(tr["entry_t"]) + 1, est=est, qty=q, limit=None,
                  target=round(est + OP.RR * risk * tr["d"], 2), status="sending")
        _send(S, ad, tr, cfg, now, out)
        _sync_trades(S, ad, now, last_px)
    S["t"] = int(now)
    S["line"] = line(S, cfg)
    save_state(S, root)
    return out


def _send(S, ad, tr, cfg, now, out):
    """One bracket through the adapter (write-ahead: the trade is saved 'sending' before the order file goes out)."""
    d = tr["d"]
    tr["status"] = "sending"
    tr["account"] = str(ad.account)                   # the account this trade lives on (managed there until it is closed)
    save_state(S, cfg.get("_root") or ROOT)
    act = {"side": "buy" if d == 1 else "sell", "qty": tr["qty"], "stop": tr["stop"], "target": tr["target"], "entry": tr["est"],
           "sym": "NQ", "entry_t": tr["entry_t"], "target_rr": E5_RR}
    if tr.get("how") == "limit":
        act.update(entry_limit=tr["limit"], entry_wait_s=E5_WAIT_S)
    res = ad.send(act)
    tr["send"] = {"ok": bool(res.get("ok")), "error": res.get("error")}
    if not any(int(lg["entry_t"]) == tr["entry_t"] for lg in ad.legs) and not any(
            int(h.get("entry_t") or 0) == tr["entry_t"] for h in ad.history):
        tr.update(status="refused", why="adapter: " + str(res.get("error") or "not placed"))
        _note(S, now, f"adapter refused {tr['id']}: {res.get('error')}")
        return
    tr["status"] = "open"
    _note(S, now, f"routed {tr['id']}: {'BUY' if d == 1 else 'SELL'} {tr['qty']} MNQ "
                  + (f"LIMIT {tr['limit']} ({E5_WAIT_S} s)" if tr.get("how") == "limit" else "market")
                  + f", stop {tr['stop']}, target 2R from the fill ({cfg['account']})")
    out["routed"].append(tr)


# ------------------------------------------------------------------------------------------------ words
def line(S: dict, cfg: dict | None = None) -> str:
    cfg = cfg or {}
    day = S.get("day")
    tr = [t for t in S.get("trades") or [] if t.get("day") == day]
    done = [t for t in tr if t["status"] == "closed" and t.get("pnl") is not None and t.get("filled")]
    opn = [t for t in tr if t["status"] in ("sending", "open")]
    ref = [t for t in tr if t["status"] == "refused"]
    usd = sum(t["pnl"] for t in done)
    s = f"OF lane ({cfg.get('account') or DEFAULT_CFG['account']}, {'ON' if cfg.get('on') else 'OFF'}): {len(done)} closed today " \
        f"{'+' if usd >= 0 else '-'}${abs(usd):,.0f}"
    if opn:
        s += f", 1 open ({'LONG' if opn[0]['d'] == 1 else 'SHORT'} {opn[0].get('qty')} MNQ)"
    if ref:
        s += f", {len(ref)} not routed (last: {ref[-1]['why'][:80]})"
    return s


def status_text(root: str = ROOT) -> str:
    cfg = load_cfg(root)
    S = load_state(root)
    allc = S.get("closes") or []
    tot = sum(c["pnl"] for c in allc)
    bad = sim_problem(cfg["account"])
    lines = [f"Order-flow lane: {'ON' if cfg['on'] else 'OFF'} | account {cfg['account']}"
             + (" (simulation)" if not bad else " (REFUSED: not a simulation account)"),
             f"Risk ${float(cfg['risk_usd']):,.0f} a trade, max {cfg['max_micros']} micros, held to {cfg['plan']} {cfg['stage']} rules, "
             f"news blackout {cfg['news_min']} min, day cap {day_cap(cfg)} entr{'y' if day_cap(cfg) == 1 else 'ies'} a day"
             + (f" ({day_entries(S, S['day'])} used today)." if S.get("day") else "."),
             f"All lane trades so far: {len(allc)}, {'+' if tot >= 0 else '-'}${abs(tot):,.0f} (simulation money)."]
    if S.get("day"):
        lines.append(line(S, cfg))
    aw = cfg.get("account_note") or account_words(cfg["account"], cfg.get("nt_folder"))
    if aw and not bad:
        lines.append(aw[0].upper() + aw[1:] + ".")
    for n in (S.get("log") or [])[-3:]:
        lines.append(f"  {_et(n['t']):%m-%d %H:%M} {n['text']}")
    return "\n".join(lines)


def _flat(root, ad) -> bool:
    S = load_state(root)
    return not (ad is not None and ad.legs) and not any(t["status"] in ("sending", "open", "fallback") for t in S["trades"])


def loop_should_stop(root: str = ROOT, ad=None, now=None) -> str | None:
    """Why the runner exits now (only ever when the lane holds nothing): after 16:10 ET, the 16:15 stop flag, the switch OFF,
    the kill switch (after its flatten). None = keep going."""
    if not _flat(root, ad):
        return None
    e = _et(now or time.time())
    if e.hour * 60 + e.minute > 16 * 60 + 10:
        return "after 16:10 ET"
    if os.path.exists(_p(root, "data", STOP_NAME)):
        return "stop flag (16:15)"
    if not load_cfg(root)["on"]:
        return "switched OFF"
    if OP._kill(root) or os.path.exists(_p(root, "data", KILL_NAME)):
        return "kill switch"
    return None


def heartbeat(root: str = ROOT, now=None, started=None):
    try:
        _wj(_p(root, "data", RUN_NAME), {"pid": os.getpid(), "t": int(now or time.time()), "started": int(started or now or time.time())})
    except Exception:  # noqa: BLE001
        pass


RUN_LOCK_NAME = "of_lane_run.lock"


def run_lock(root: str = ROOT):
    """red team #34: ONE lane runner per repo: an OS lock on data/of_lane_run.lock held for the runner's life (released by the OS
    if it crashes, so never stale). Returns the open handle, or None when another runner holds it."""
    d = _p(root, "data")
    os.makedirs(d, exist_ok=True)
    fh = open(os.path.join(d, RUN_LOCK_NAME), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def loop(root: str = ROOT, every: float = 15.0, clock=time.time, sleep=time.sleep, tick_fn=None, max_runs=None):
    """The runner (started detached by engine/ops_checks.of_lane_kick at 09:20 ET): one tick every 15 s, a heartbeat in
    data/of_lane_run.json, exits only while flat (16:10 / the 16:15 flag / OFF / kill)."""
    lk = run_lock(root)
    if lk is None:                                    # red team #34: a 2nd runner (a slow tick let the 2-min heartbeat age) exits
        return "already running"                      # at once and touches nothing (not the 1st one's heartbeat / stop flag)
    ad = None
    t0 = clock()
    n = 0
    try:
        refresh_account(root, t0)                     # the morning re-pick (Sim102 once it exists), only while flat
    except Exception:  # noqa: BLE001
        pass
    try:
        while True:
            now = clock()
            heartbeat(root, now, t0)
            try:
                r = (tick_fn or tick)(now=now, root=root, ad=ad)
                ad = r.get("ad") or ad
                for tr in r.get("routed") or []:
                    print(_et(now).strftime("%H:%M:%S"), "routed", tr["id"], flush=True)
            except Exception as e:  # noqa: BLE001
                print("of_lane tick error:", e.__class__.__name__, str(e)[:200], flush=True)
            why = loop_should_stop(root, ad, now)
            n += 1
            if why or (max_runs and n >= max_runs):
                return why
            sleep(every)
    finally:
        if ad is not None:
            ad.release_lock()
        for nm in (RUN_NAME, STOP_NAME):
            try:
                os.remove(_p(root, "data", nm))
            except OSError:
                pass
        lk.close()                                    # the OS lock goes with the handle (and with the process if it dies)


# ------------------------------------------------------------------------------------------------ Telegram /oflane
def _today_paper(root, now) -> str:
    S = _rj(_p(root, "data", OP.STATE_NAME))
    if S and S.get("day") == OP.et_day(now) and S.get("line"):
        return S["line"]
    return "the order-flow paper bot has no trade yet today"


def _ladder(root) -> str:
    d = _rj(_p(root, "research", "evalplan", "ladder.json"))
    return d["line"] if isinstance(d, dict) and d.get("line") else "the forward ladder has not been scored yet (tools/of_ladder.py, nightly)"


def tg_text(arg: str, root: str = ROOT, now=None) -> str:
    """Telegram /oflane on|off|status (engine/tg_cmd, the owner's private chat only). Simulation accounts only, always."""
    now = now or time.time()
    if arg == "on":
        ok, msg = set_switch(True, root=root)
        if not ok:
            return msg
        sim101 = ("\nIf the lane is on Sim101, ATLAS's week or START's Sim test started later today sends no orders until "
                  "tomorrow (safe).")  # the account is re-picked at each runner start, so always said
        return (msg + f"\nStarts by itself at 09:20 ET on weekdays (the PC). Off: /oflane off{sim101}\nToday: {_today_paper(root, now)}."
                f"\n{_ladder(root)}")
    if arg == "off":
        return set_switch(False, root=root)[1]
    return status_text(root) + f"\nPaper bot today: {_today_paper(root, now)}.\n{_ladder(root)}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="engine.of_lane", description="Order-flow lane on a NinjaTrader SIMULATION account (OFF by default)")
    ap.add_argument("cmd", nargs="?", choices=("tick", "loop", "status"), default="status")
    ap.add_argument("--sim", choices=("on", "off", "status"))
    ap.add_argument("--account")
    a = ap.parse_args(argv)
    if a.sim in ("on", "off"):
        ok, msg = set_switch(a.sim == "on", a.account)
        print(msg)
        return 0 if ok else 1
    if a.sim == "status" or a.cmd == "status":
        print(status_text())
        return 0
    if a.cmd == "tick":
        r = tick()
        print(r.get("refused") or ("OFF: nothing to do" if r.get("off") else r["S"].get("line")))
        return 0
    loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
