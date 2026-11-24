"""Live guard (day-zeroerr 2026-11-24, owner: "no more errors"): the three checks the failure map (docs/FAILURE_MAP.md) found
missing in the live chain. READ-ONLY: it never starts, stops, arms, routes, sizes or changes an order; it reads the bot's own
objects and files and sends phone lines (engine/notify.instant_problem: Telegram / Discord first when ALERTS_SETUP is on, else the
private ntfy topic + the Olympus app).

  missed      every EXTRA account against the live twin. The bot's own model is the twin (tests.test_lit_live: live loop =
              backtest): a LIT entry the main loop saw (bot.seen ("entry", t)) and an ATLAS member trade of the paper twin
              (bot.second) must be on every account configured for it within MISS_AFTER_S (2 min). The main LIT account
              is engine/fill_audit.session_alerts' job (already instant); the extra accounts (engine/multi_account: the 25K #2,
              the Rapid's LIT lane), ATLAS's own account (account B) and the Rapid's ATLAS (acct_r / acct_r2) had NO such
              check: an account with a start problem / not armed returns before it ever looks at the signal, so a trade it
              should have taken left no line at all (the Rapid EOD 25K, ATLAS +6.6R Nov 20). Each miss = one push, sent once,
              with the reason (not armed / its start problem / not in the running bot / refused by NinjaTrader / did not run
              at that 5m open). The account's own RULE holds (room, news, size 0, one position) are not misses.
  armed       at 01:55 ET (before LIT's 02:00 window) and 09:00 ET (before the NY open) on CME trading days: one line per
              configured account: ARMED / NOT ARMED + why, and whether NinjaTrader lists the exact account Name it routes to
              (le_feed\\accounts.csv). Loud when any account is not armed / not routed, quiet when all good.
  update      the auto-update stuck: data/autoupdate.json's last result held back by something that never clears by itself
              (a local change it may not park, local commits, the wrong branch, git fetch / status failing, the auto-update off)
              for STUCK_S (3 h) -> one push a day with the exact reason. Before, "update skipped" went to the daily digest only:
              the PC sat on old code from Nov 24 00:45 ET and nobody heard. day-zerotouch2 parks the hand edits it may park;
              this is the net under it.
Driven by engine/watchdog.Watchdog.check (every 30 s; the real server only, never a test's fake clock). LE_LIVE_GUARD=0 = off.
Tests: python -X utf8 -m tests.test_chaos_live
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
STATE_PATH = os.path.join(ROOT, "logs", "live_guard.json")      # gitignored (logs/): the stuck-update clock
MISS_AFTER_S = 120                 # a signal this old and not on the account = missed (LIT is not chased after 90 s)
MISS_MAX_AGE_S = 6 * 3600          # never push about a signal older than this (a restart re-reading the day)
MISS_EVERY_S = 60
ARM_SLOTS = ((1, 55), (9, 0))      # ET
ARM_SLOT_MIN = 15                  # the slot's check runs once inside [slot, slot + 15 min)
STUCK_S = 3 * 3600
STUCK_REASONS = ("local changes in tracked files", "not on branch", "git fetch failed", "git status failed",
                 "is not a fast-forward", "fast-forward refused", "could not be set", "unknown", "auto-update is off")


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("LE_LIVE_GUARD", "1")).strip() != "0"


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def _hm(t) -> str:
    return _et(t).strftime("%H:%M")


def trading_day(t) -> str:
    """The CME trading day (18:00 ET starts the next one), as engine/live.trading_day."""
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _mask(s) -> str:
    try:
        from .arm_report import mask
        return mask(s)
    except Exception:
        return str(s or "")


def _market_open(now) -> bool:
    try:
        from .live import market_open
        return bool(market_open(now))
    except Exception:
        return _et(now).weekday() < 5


def _is_sim(name) -> bool:
    try:
        from .ninjatrader import is_sim
        return bool(is_sim(name))
    except Exception:
        return str(name or "").lower().startswith(("sim", "playback"))


def _ok_row(r) -> bool:
    return (r.get("result") or {}).get("ok") is not False


# ================================================================================================ 1. missed trade per account
def lit_signals(bot, now) -> list:
    """[(entry_t, dir)] of today's LIT entries the main loop's model took (routed or held on the main account), each at least
    MISS_AFTER_S old. The twin: the live loop is the backtest (tests.test_lit_live)."""
    today = trading_day(now)
    out = {}
    for k in list(getattr(bot, "seen", None) or ()):
        if isinstance(k, (tuple, list)) and len(k) == 2 and k[0] == "entry":
            try:
                t = int(k[1])
            except (TypeError, ValueError):
                continue
            out.setdefault(t, None)
    pos = (getattr(bot, "state", None) or {}).get("position") or {}
    if pos.get("entry_t") and int(pos["entry_t"]) in out:
        out[int(pos["entry_t"])] = 1 if pos.get("dir") == 1 else -1
    return sorted((t, d) for t, d in out.items()
                  if trading_day(t) == today and MISS_AFTER_S <= now - t <= MISS_MAX_AGE_S)


def atlas_signals(bot, now) -> list:
    """[(entry_t, key)] of today's ATLAS member trades in the paper twin (bot.second, engine/second.run), each at least
    MISS_AFTER_S old."""
    today = trading_day(now)
    out = []
    res = getattr(bot, "second", None)
    for k, s in ((res or {}).get("strategies") or {}).items() if isinstance(res, dict) else ():
        for t in (s or {}).get("trades") or []:
            try:
                et_ = int(t.get("entry_t"))
            except (TypeError, ValueError):
                continue
            if trading_day(et_) == today and MISS_AFTER_S <= now - et_ <= MISS_MAX_AGE_S:
                out.append((et_, str(k)))
    return sorted(set(out))


def _in_trade_at(acct, t) -> bool:
    """The account held another trade at t (one position per account: a twin signal then is not its trade)."""
    closes = {int(c[3]): int(c[1]) for c in (getattr(acct, "closes", None) or []) if isinstance(c, (list, tuple)) and len(c) > 3}
    for r in getattr(acct, "ledger", None) or []:
        if r.get("side") in ("buy", "sell") and r.get("entry_t") and _ok_row(r):
            e = int(r["entry_t"])
            if e < t and (closes.get(e) is None or closes[e] > t):
                return True
    ot = getattr(acct, "open_t", None)
    return ot is not None and int(ot) < t


def _routed(acct, t):
    """None = no entry row for t; True = routed (ok); "<error>" = refused."""
    for r in getattr(acct, "ledger", None) or []:
        if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None and int(r["entry_t"]) == int(t):
            return True if _ok_row(r) else str((r.get("result") or {}).get("error") or "refused")[:120]
    return None


def _why_off(acct) -> str | None:
    """Why this account cannot trade at all right now (its start problem, no adapter, not armed), else None."""
    try:
        dr = acct.disabled_reason() if callable(getattr(acct, "disabled_reason", None)) else getattr(acct, "problem", None)
    except Exception:
        dr = getattr(acct, "problem", None)
    if dr:
        return str(dr)[:160]
    sp = getattr(acct, "spec", None) or {}
    if "armed" in sp and sp.get("armed") is not True and str(sp.get("adapter") or "") != "paper":
        return "not armed"
    return None


def _label(acct, default="account") -> str:
    lb = getattr(acct, "label", None)
    if isinstance(lb, str) and lb and lb not in ("LIVE", "SIM", "PAPER"):
        return lb
    nm = getattr(acct, "name", None) or (getattr(acct, "spec", None) or {}).get("name")
    return str(nm or default)


def _paper(acct) -> bool:
    sp = getattr(acct, "spec", None) or {}
    return str(sp.get("adapter") or "") == "paper"


def _owner_off(acct) -> bool:
    """The owner switched this account off himself ("enabled": false in the account entry): never a miss, never NOT READY."""
    sp = getattr(acct, "spec", None) or {}
    return sp.get("enabled") is False or str(getattr(acct, "problem", None) or "") == "disabled in the config"


def lit_followers(bot) -> list:
    # red team 2026-11-24: an account the owner disabled in the config is not a follower (it pushed a MISSED TRADE for every
    # LIT entry, and NOT READY at 01:55 and 09:00 every day)
    return [a for a in list(getattr(getattr(bot, "accts", None), "accounts", None) or []) if not _paper(a) and not _owner_off(a)]


def atlas_accounts(bot) -> list:
    return [a for a in (getattr(bot, "acct_b", None), getattr(bot, "acct_r", None), getattr(bot, "acct_r2", None))
            if a is not None and not _paper(a)]


def missing_configured(bot, root=None) -> list:
    """[(label, model, why)] of accounts the owner configured that are NOT in the running bot at all (so no object exists to
    look at): the Rapid EOD (data/rapid.json) armed but without its LIT lane / ATLAS, ATLAS's account B configured but not
    started. Never raises."""
    out = []
    try:
        from . import launch_check as LC
        for slot in ("rapid", "rapid2"):
            f = LC.rapid_fact(bot, slot=slot)
            if not f or f.get("error"):
                continue
            why = f.get("problem") or ("not armed at START" if not f.get("armed") else "not in the running bot")
            if not f.get("lit"):
                out.append((f"{f.get('label') or 'Rapid EOD'}", "lit", why))
            if not f.get("atlas"):
                out.append((f"{f.get('label') or 'Rapid EOD'}", "atlas", why))
    except Exception:
        pass
    try:
        if getattr(bot, "acct_b", None) is None:
            from . import account_b as AB
            ab = AB.raw_cfg()
            if isinstance(ab, dict) and str(ab.get("account") or "").strip() and ab.get("armed") is True:
                why = None
                try:
                    from . import arm_report
                    why = arm_report.glance_reason("ATLAS")
                except Exception:
                    why = None
                out.append(("ATLAS account", "atlas", why or "account B is configured and armed but did not start in this bot"))
    except Exception:
        pass
    return out


def missed(bot, now) -> list:
    """[{"key", "account", "entry_t", "model", "why", "soft"}] of twin signals not on an account. Pure (reads only)."""
    now = int(now)
    out = []
    if bot is None or not getattr(bot, "running", False):
        return out
    if str(((getattr(bot, "cfg", None) or {}).get("adapter")) or "paper") == "paper":
        return out
    if getattr(bot, "kill", False):
        return out                                         # the kill switch: no account trades today, on purpose
    lits = lit_signals(bot, now)
    for a in lit_followers(bot):
        added = int(getattr(a, "added_t", 0) or 0)
        for t, d in lits:
            if added and t < added - 60:
                continue                                   # joined the bot after this entry (engine/multi_account added_t)
            r = _routed(a, t)
            if r is True:
                continue
            blocked = t in (getattr(a, "blocked", None) or set())
            if r is None and blocked:
                continue                                   # its own rule held it back (logged "NOT routed on this account")
            if r is None and t in (getattr(a, "hedge_wait", None) or set()) and ("entry", t) not in (getattr(a, "seen", None) or set()):
                why = "waited for the other account's close (no long + short across accounts) and never routed"
            elif r is not None:
                why = f"NinjaTrader refused it: {r}"
            else:
                why = _why_off(a) or ("the account never looked at it (not running at that minute)"
                                      if ("entry", t) not in (getattr(a, "seen", None) or set())
                                      else "seen but not routed and no reason logged")
            out.append({"account": _label(a), "entry_t": t, "model": "lit", "why": why, "soft": False})
    ats = atlas_signals(bot, now)
    for a in atlas_accounts(bot):
        keys = set(str(k) for k in ((getattr(a, "spec", None) or {}).get("keys") or []))
        took = {int(r["entry_t"]) for r in getattr(a, "ledger", None) or []
                if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None}
        for t, k in ats:
            if k not in keys:
                continue                                   # not one of this account's members (no keys = it trades none)
            if t in took and _routed(a, t) is True:
                continue
            if str(t) in (getattr(a, "held", None) or {}):
                continue                                   # its own rule held it (account B "held": room, size 0, news)
            if _in_trade_at(a, t):
                continue
            r = _routed(a, t)
            soft = False
            if r is not None and r is not True:
                why = f"NinjaTrader refused it: {r}"
            else:
                why = _why_off(a)
                if not why:
                    if ("probe", t) not in (getattr(a, "seen", None) or set()):
                        why = "the account did not run at that 5-minute open (bot busy / restarted)"
                    else:
                        why = "its live check at the 5-minute open saw no signal; the twin did on the closed bar"
                        soft = True
            out.append({"account": _label(a), "entry_t": t, "model": "atlas", "key": k, "why": why, "soft": soft})
    gone = missing_configured(bot)
    for label, model, why in gone:
        for t, _ in (lits if model == "lit" else ats):
            out.append({"account": label, "entry_t": t, "model": model, "why": why, "soft": False})
    seen, uniq = set(), []
    for m in out:
        k = f"guard:miss:{m['model']}:{_mask(m['account'])}:{int(m['entry_t'])}"
        if k not in seen:
            seen.add(k)
            uniq.append({**m, "key": k})
    return uniq


def missed_payload(m: dict) -> dict:
    who = "Zlarior" if m["model"] == "lit" else "ATLAS"
    head = "Not taken (check)" if m.get("soft") else "MISSED TRADE"
    return {"key": m["key"], "code": "missed", "bot": m["model"], "entry_t": int(m["entry_t"]),
            "title": f"{head} · {who} {_hm(m['entry_t'])} ET on {_mask(m['account'])}"[:120],
            "body": (f"The live twin took {who}'s {_hm(m['entry_t'])} ET entry; {_mask(m['account'])} did not: {_mask(m['why'])}."
                     + ("" if m.get("soft") else " Next: python tools/board.py read, then the account's line in the Start window."))[:600],
            **({"soft": True, "tags": "eyes"} if m.get("soft") else {})}


# ================================================================================================ 2. armed + routed check
def arm_rows(bot, now=None, folder=None, live_names=None) -> list:
    """[{"label", "account", "armed", "routed", "why"}] for every configured real account. Read-only, never raises."""
    rows = []
    try:
        cfg = getattr(bot, "cfg", None) or {}
        if live_names is None:
            try:
                from .ninjatrader import live_accounts
                live_names = live_accounts(folder or cfg.get("nt_folder"), now)
            except Exception:
                live_names = []
        live_names = set(live_names or [])

        def routed(name):
            if not name:
                return False
            if _is_sim(name):
                return True                                # NinjaTrader's own Sim: always there
            return name in live_names

        def add(label, name, armed, why):
            r = routed(name)
            if armed and not r:
                why = why or (f"NinjaTrader does not list {name} right now (not connected / LE_BarFeed off / the Name changed)"
                              if live_names else "NinjaTrader lists no live account (not connected, or LE_BarFeed is off)")
            rows.append({"label": label, "account": _mask(name or "?"), "armed": bool(armed), "routed": bool(r), "why": _mask(why or "")[:160]})

        if cfg and str(cfg.get("adapter") or "paper") != "paper":
            name = str(cfg.get("nt_account") or getattr(getattr(bot, "adapter", None), "account", "") or "")
            run = bool(getattr(bot, "running", False))
            add("Zlarior (LIT)", name, run and bool(cfg.get("armed")),
                None if run and cfg.get("armed") else ("the bot is not running" if not run else "not armed"))
        for a in lit_followers(bot):
            nm = str((getattr(a, "spec", None) or {}).get("nt_account") or "")
            why = _why_off(a)
            add(_label(a), nm, not why, why)
        for a in atlas_accounts(bot):
            nm = str(getattr(a, "name", None) or (getattr(a, "spec", None) or {}).get("account") or "")
            why = _why_off(a)
            add(_label(a, "ATLAS"), nm, not why, why)
        for label, model, why in missing_configured(bot):
            rows.append({"label": f"{label} ({'LIT' if model == 'lit' else 'ATLAS'})", "account": "?", "armed": False,
                         "routed": False, "why": _mask(why)[:160]})
    except Exception as e:  # noqa: BLE001
        rows.append({"label": "check", "account": "?", "armed": False, "routed": False, "why": f"check failed: {e.__class__.__name__}"})
    return rows


def arm_payload(rows: list, now) -> dict | None:
    if not rows:
        return None
    e = _et(now)
    bad = [r for r in rows if not (r["armed"] and r["routed"])]
    lines = [(f"OK {r['label']} {r['account']}" if r["armed"] and r["routed"] else
              f"NOT READY {r['label']} {r['account']}: {r['why'] or 'not armed'}") for r in rows]
    slot = f"{e:%H:%M}"
    return {"key": f"guard:arm:{trading_day(now)}:{slot}", "code": "armed",
            "title": (f"{len(bad)} account(s) NOT READY at {slot} ET" if bad else f"All {len(rows)} accounts armed at {slot} ET"),
            "body": "\n".join(lines)[:600], **({} if bad else {"soft": True, "tags": "white_check_mark"})}


def arm_due(now, done: set) -> str | None:
    """The slot name ("01:55" / "09:00") whose check is due now (weekday, CME open, not done today), else None."""
    e = _et(now)
    if e.weekday() >= 5 or not _market_open(now):
        return None
    m = e.hour * 60 + e.minute
    for h, mm in ARM_SLOTS:
        s = h * 60 + mm
        key = f"{trading_day(now)}:{h:02d}:{mm:02d}"
        if s <= m < s + ARM_SLOT_MIN and key not in done:
            return key
    return None


# ================================================================================================ 3. update stuck
def update_stuck(state: dict | None, au: dict | None, now) -> tuple:
    """(new state, payload | None). state: {"since", "reason", "sent_day"}; au: data/autoupdate.json. Pure."""
    st = dict(state or {})
    last = (au or {}).get("last") or {}
    status, reason = str(last.get("status") or ""), str(last.get("reason") or "")
    stuck = (status in ("skipped", "failed", "off") and any(w in reason for w in STUCK_REASONS))
    if not stuck:
        if status in ("updated", "up_to_date"):
            return {}, None
        return st, None                                    # not flat / trading hours / waiting: no news either way
    if not st.get("since") or st.get("reason", "")[:40] != reason[:40]:
        st = {"since": int(last.get("t") or now), "reason": reason[:300]}
    day = _et(now).date().isoformat()
    if now - float(st["since"]) < STUCK_S or st.get("sent_day") == day:
        return st, None
    st["sent_day"] = day
    hrs = (now - float(st["since"])) / 3600.0
    fix = ("send Claude: 'update blocked by <the file>' (strategy / account files are never parked by themselves)"
           if "local changes" in reason else
           "python -m engine.autoupdate --enable" if "is off" in reason else
           "send Claude this line (the PC is not on its update branch / has its own commits)"
           if ("branch" in reason or "fast-forward" in reason) else
           "check the PC's internet / GitHub sign-in (UPDATE.bat shows the error)")
    return st, {"key": f"guard:upd:{day}", "code": "update_stuck", "soft": True, "tags": "warning",
                "title": f"Bot update stuck for {hrs:.0f} h"[:120],
                "body": f"The PC is still on its old code: {reason[:220]}. Every fix since then is not on the PC. Fix: {fix}."[:600]}


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, type(default)) else default
    except Exception:
        return default


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        from .fsutil import replace as _replace       # retried: Windows / OneDrive lock the target a moment
        _replace(tmp, path)
    except Exception:
        pass


# ================================================================================================ the driver
class LiveGuard:
    """step() every watchdog check (30 s). send(payload) -> str (tests); default engine/notify.instant_problem."""

    def __init__(self, send=None, clock=time.time, state_path: str | None = None, au_path: str | None = None):
        self._send = send
        self.clock = clock
        self.state_path = state_path or STATE_PATH
        self.au_path = au_path
        self.sent: set = set()
        self.arm_done: set = set()
        self._miss_t = 0.0
        self.last: dict = {}

    def send(self, p: dict) -> str:
        try:
            if self._send is not None:
                return self._send(p)
            from . import notify
            return notify.instant_problem(p)
        except Exception as e:  # noqa: BLE001
            return f"failed: {e.__class__.__name__}"

    def _push(self, p, done):
        if p["key"] in self.sent:
            return
        r = self.send(p)
        if r in ("sent", "sent (app)", "already sent") or str(r).startswith("sent"):
            self.sent.add(p["key"])
        done.append((p["key"], r))

    def step(self, bot, now=None) -> list:
        now = float(self.clock() if now is None else now)
        done: list = []
        try:
            if not enabled():
                return done
            if now - self._miss_t >= MISS_EVERY_S:
                self._miss_t = now
                for m in missed(bot, now):
                    self._push(missed_payload(m), done)
            slot = arm_due(now, self.arm_done)
            if slot:
                real = bool(getattr(bot, "running", False)) and str(((getattr(bot, "cfg", None) or {}).get("adapter")) or "paper") != "paper"
                if not real:
                    try:                                   # not running: only when a broker run should be on (autostart.json)
                        from .watchdog import load
                        rec = load() or {}
                        real = str(((rec.get("cfg") or {}).get("adapter")) or "paper") != "paper"
                    except Exception:
                        real = False
                self.arm_done.add(slot)
                if real:
                    p = arm_payload(arm_rows(bot, now), now)
                    if p:
                        self._push(p, done)
            st = _read_json(self.state_path, {})
            au = _read_json(self.au_path or os.path.join(ROOT, "data", "autoupdate.json"), {})
            new, p = update_stuck(st.get("upd"), au, now)
            if new != (st.get("upd") or {}):
                st["upd"] = new
                _write_json(self.state_path, st)
            if p:
                self._push(p, done)
            self.last = {"t": int(now), "sent": done[-4:]}
        except Exception as e:  # noqa: BLE001
            self.last = {"t": int(now), "error": f"{e.__class__.__name__}: {e}"}
        return done
