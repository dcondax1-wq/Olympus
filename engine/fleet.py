"""The fleet: in-house copy trading. One bot's trades (Zlarior / LIT, ATLAS = account B, BLITZ = account C) copied to N
follower accounts at any firm / plan, on Sim or a real account, or the owner's personal LIVE account. OFF by default.

  OFF       no data/fleet.json (or no "accounts" in it): LiveBot.fleet stays None, nothing here runs, every payload is byte
            for byte as before (the heartbeat / live.json carry no "fleet" key).
  Lead      a follower copies what its lead account DID: the lead's routed entry (only once the broker answered OK), its stop
            moves, its exit. It never trades a signal the lead did not trade, never scales in, never re-enters.
  Size      each follower from ITS OWN room and rules: the lead bot's sizing on the follower's plan (Zlarior: LIT's two_week
            eval sizing / funded sizing, engine/sizing.lit_qty via engine/multi_account; ATLAS: engine/account_b.qty /
            funded_qty; BLITZ: engine/account_c.qty), then the firm's rules (engine/firms.check: contracts, the max-loss floor
            at the stop the firm's way, daily loss, news, flat time, best day) cap it; "sizing": "fixed" + "risk_usd" = a fixed
            $ risk a trade. The personal LIVE account is always fixed risk (firms.live_profile), never an eval size.
  Safety    per-account on / off ("enabled") and kill ("killed"), a fleet-wide kill ("kill": true, or the bot's kill
            switch); never opposite another of the owner's accounts on the same underlying (LIT's account, the extra
            accounts, ATLAS, BLITZ, every other follower: MFFU bans long + short on one underlying across your accounts);
            a lead entering against a follower closes the follower first (priority Zlarior > ATLAS > BLITZ, as today);
            an order a follower's broker refused / never placed is never booked there and never blocks the others; a real
            (non-Sim) NinjaTrader follower trades only with "armed": true + the phrase typed at the bot's start +
            NINJATRADER_LIVE=1 (as accounts B / C; nothing here arms anything).
  Lifecycle eval -> passed (no new entry, push "switch it to funded") -> funded (owner: --to-funded) -> payout (--payout) ->
            failed (floor reached: stopped + push). LIVE: the bot's own daily / weekly stops.
  Extras    staggered entry (per follower "stagger_ms"), slippage of each follower's fill vs the lead's fill (ticks).

Config (data/fleet.json, gitignored, never the phrase):
  {"v": 1, "kill": false, "accounts": [
    {"id": "lucid50k", "name": "Lucid 50K", "lead": "zlarior", "plan": "lucid_pro_50k", "stage": "eval",
     "adapter": "ninjatrader", "nt_account": "<NinjaTrader Name>", "start": "2026-11-02", "enabled": true, "armed": false,
     "stagger_ms": 0, "sizing": "plan", "risk_usd": null, "payouts": {}, "rules": {}, "killed": false},
    {"id": "mylive", "name": "My live account", "lead": "zlarior", "plan": "live", "stage": "live", "adapter": "ninjatrader",
     "nt_account": "<Name>", "start": "2026-11-02", "live": {"start": 10000, "max_risk_usd": 150, "daily_stop_usd": 300,
     "weekly_stop_usd": 600, "max_micros": 5}}]}

  python -X utf8 -m engine.fleet --status
  python -X utf8 -m engine.fleet --add --id lucid50k --lead zlarior --plan lucid_pro_50k --account "<Name>" --start 2026-11-02
  python -X utf8 -m engine.fleet --add --id mylive --lead zlarior --plan live --account "<Name>" --start 2026-11-02 --max-risk 150
  python -X utf8 -m engine.fleet --remove lucid50k | --off lucid50k | --on lucid50k | --kill lucid50k|all | --unkill ...
  python -X utf8 -m engine.fleet --to-funded lucid50k --account "<funded Name>" --start <day> | --payout lucid50k 2026-12-01=1000
  python -X utf8 -m engine.fleet --dry-run 2026-10-13     (replays that day's LIT trades through the fleet on paper)
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import math
import os
import re
import threading
import time

from . import firms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLEET_PATH = os.path.join(ROOT, "data", "fleet.json")
VERSION = 1
LEADS = {"zlarior": 0, "atlas": 1, "blitz": 2}           # priority: a lower rank wins a hedge (LIT > ATLAS > BLITZ)
LEAD_NAMES = {"zlarior": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
STAGES = ("eval", "funded", "live")
ADAPTERS_OK = ("paper", "ninjatrader")
SIZINGS = ("plan", "fixed")
MAX_AGE_S = 90            # a lead entry first seen later than this after it was sent is not chased
GONE_GRACE_S = 120        # the lead no longer shows the follower's trade and booked no close for it: flattened after this
TICK = 0.25
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
ADAPTER_FACTORY = None    # tests: (follower, adapter cfg) -> adapter


# ---------------------------------------------------------------------------------------------------------------- helpers
def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(float(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _phrase() -> str:
    from .tradovate import LIVE_PHRASE
    return LIVE_PHRASE


def is_sim(name) -> bool:
    from .ninjatrader import is_sim as _s
    return _s(name)


def _ok(res) -> bool:
    return isinstance(res, dict) and res.get("ok") is not False


def _side(d) -> str:
    return "LONG" if int(d) == 1 else "SHORT"


# ---------------------------------------------------------------------------------------------------------------- config
_RAW = {"key": None, "d": None}


def load_file(path: str | None = None) -> dict:
    """data/fleet.json -> {"v", "kill", "accounts": [...]}. Missing / unreadable -> {"accounts": []} (fleet off)."""
    path = path or FLEET_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return {"v": VERSION, "kill": False, "accounts": []}
    if isinstance(d, list):
        d = {"accounts": d}
    if not isinstance(d, dict):
        return {"v": VERSION, "kill": False, "accounts": []}
    rows = d.get("accounts")
    d["accounts"] = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    d["kill"] = d.get("kill") is True
    return d


def raw_cfg(path: str | None = None):
    """The fleet block for the real bot (LiveBot._fleet_block): None when there is no follower (off). Cached by mtime."""
    path = path or FLEET_PATH
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    if _RAW["key"] != key:
        _RAW.update(key=key, d=load_file(path))
    d = _RAW["d"]
    return d if d and d.get("accounts") else None


def save_file(d: dict, path: str | None = None):
    path = path or FLEET_PATH
    phrase = _phrase()
    rows = [{k: v for k, v in r.items() if k != "confirm" and not (isinstance(v, str) and v.strip() == phrase)}
            for r in (d.get("accounts") or [])]
    out = {"v": VERSION, "kill": d.get("kill") is True, "accounts": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    from .fsutil import replace as _fs_replace
    _fs_replace(tmp, path)


def profile_of(spec: dict) -> dict | None:
    if spec.get("stage") == "live" or spec.get("plan") == "live":
        lv = dict(spec.get("live") or {})
        lv.setdefault("start", _num(spec.get("balance")))
        return firms.live_profile(lv)
    return firms.profile(str(spec.get("plan") or ""), "funded" if spec.get("stage") == "funded" else "eval",
                         overrides=spec.get("rules") or None)


def normalize(spec: dict, seen_ids=(), seen_names=(), reserved: dict | None = None) -> dict:
    """One follower entry -> the spec with defaults + "problem" (why it cannot trade, None = it can). Never raises."""
    s = dict(spec or {})
    stage = str(s.get("stage") or ("live" if s.get("plan") == "live" else "eval"))
    out = {"id": str(s.get("id") or "").strip(), "name": str(s.get("name") or s.get("id") or "").strip()[:60],
           "lead": str(s.get("lead") or "zlarior").lower(), "plan": str(s.get("plan") or ("live" if stage == "live" else "")),
           "stage": stage, "adapter": str(s.get("adapter") or "paper"), "nt_account": str(s.get("nt_account") or "").strip(),
           "enabled": s.get("enabled", True) is not False, "armed": s.get("armed") is True, "killed": s.get("killed") is True,
           "start": str(s.get("start") or ""), "funded_start": str(s.get("funded_start") or ""),
           "balance": _num(s.get("balance")), "prior_pnl": float(_num(s.get("prior_pnl"), 0.0)),
           "stagger_ms": max(0, min(5000, int(_num(s.get("stagger_ms"), 0) or 0))),
           "sizing": str(s.get("sizing") or "plan"), "risk_usd": _num(s.get("risk_usd")),
           "payouts": {str(k): float(v) for k, v in (s.get("payouts") or {}).items() if _num(v) is not None},
           "rules": dict(s.get("rules") or {}), "live": dict(s.get("live") or {}), "problem": None}
    if out["stage"] == "live":
        out["plan"] = "live"
        out["sizing"] = "fixed"
    P = None
    try:
        P = profile_of(out)
    except Exception as e:
        out["problem"] = f"rules invalid ({e.__class__.__name__})"
    if out["problem"]:
        pass
    elif not _ID.match(out["id"]):
        out["problem"] = "id missing or invalid (letters, digits, - and _ only)"
    elif out["id"] in seen_ids:
        out["problem"] = f"id {out['id']} used twice"
    elif out["lead"] not in LEADS:
        out["problem"] = f"unknown lead {out['lead']} (zlarior | atlas | blitz)"
    elif out["stage"] not in STAGES:
        out["problem"] = f"unknown stage {out['stage']} (eval | funded | live)"
    elif P is None:
        out["problem"] = f"unknown plan {out['plan']} (python -X utf8 -m engine.firms --list)"
    elif out["sizing"] not in SIZINGS:
        out["problem"] = f"unknown sizing {out['sizing']} (plan | fixed)"
    elif out["sizing"] == "fixed" and out["stage"] != "live" and not out["risk_usd"]:
        out["problem"] = "sizing fixed needs risk_usd ($ risk a trade)"
    elif out["adapter"] not in ADAPTERS_OK:
        out["problem"] = f"adapter {out['adapter']} cannot follow (ninjatrader or paper only)"
    elif out["stage"] == "funded" and not (out["funded_start"] or out["start"]):
        out["problem"] = "funded start day missing (--to-funded ... --start <day>)"
    elif out["stage"] != "funded" and not out["start"]:
        out["problem"] = "start day missing (--start <first session>)"
    elif out["stage"] == "live" and not _num((out["live"] or {}).get("start"), out["balance"]):
        out["problem"] = "live account start balance missing (--balance <$>)"
    elif out["adapter"] == "ninjatrader":
        nm = out["nt_account"]
        if not nm or any(c in nm for c in ";\r\n|"):
            out["problem"] = "nt_account missing or invalid"
        elif nm in seen_names:
            out["problem"] = f"NinjaTrader account {nm} listed twice"
        elif reserved and nm in reserved:
            out["problem"] = f"{nm} is {reserved[nm]}'s own account (a follower needs its own account)"
        elif P is not None and P.get("kind") != "live" and (P.get("bots") in ("prohibited", "semi_only", "api_only")
                                                             or P.get("ninjatrader") is False):
            out["problem"] = f"{P['firm']} does not allow this bot on NinjaTrader ({P.get('bots')}): paper only"
    if not out["enabled"] and not out["problem"]:
        out["problem"] = "switched off (enabled false)"
    if not out["name"]:
        out["name"] = out["id"] or "follower"
    real = out["adapter"] == "ninjatrader" and not is_sim(out["nt_account"])
    base = "REAL" if real else ("SIM" if out["adapter"] == "ninjatrader" else "PAPER")
    # the personal live account is labelled LIVE everywhere (LIVE = real money; LIVE SIM / LIVE PAPER while it is tested)
    out["label"] = ("LIVE" if real else f"LIVE {base}") if out["stage"] == "live" else base
    return out


def live_gate(spec: dict, bot_cfg: dict | None) -> str | None:
    """A real (non-Sim) NinjaTrader follower: "armed": true in its entry AND the phrase typed at the bot's start AND
    NINJATRADER_LIVE=1 (then the adapter's own gate + allowlist check again). Paper / Sim: None."""
    if spec.get("adapter") != "ninjatrader" or is_sim(spec.get("nt_account")):
        return None
    from .ninjatrader import LIVE_ENV
    if spec.get("armed") is not True:
        return f"real account {spec.get('nt_account')} not armed (the owner arms it: python -X utf8 -m engine.fleet --arm {spec.get('id')})"
    if str((bot_cfg or {}).get("confirm") or "").strip() != _phrase():
        return f"real account {spec.get('nt_account')}: the live phrase was not typed at the bot's start"
    if os.environ.get(LIVE_ENV, "") != "1":
        return f"real account {spec.get('nt_account')}: the bot is not running live ({LIVE_ENV}=1)"
    return None


# ---------------------------------------------------------------------------------------------------------------- leads
def _entry_row(ledger, et_):
    return next((r for r in reversed(ledger or []) if r.get("side") in ("buy", "sell") and r.get("entry_t") == et_), None)


def _cur_stop(ledger, et_, stop0):
    stop = stop0
    for r in ledger or []:
        if r.get("entry_t") == et_ and r.get("side") == "modify" and (r.get("result") or {}).get("ok"):
            stop = r.get("stop", stop)
    return stop


def _fill_px(adapter, et_):
    for lg in list(getattr(adapter, "legs", None) or []):
        try:
            if int(lg.get("entry_t")) == int(et_) and lg.get("fill_px") is not None:
                return float(lg["fill_px"])
        except Exception:
            continue
    return None


def lead_snapshot(bot, key: str) -> dict | None:
    """What the lead account holds / closed: {"key", "name", "open": {entry_t, dir, qty, entry, stop, target, t, fill, sym}
    | None, "closes": {entry_t: {"pnl", "qty", "exit_t", "reason"}}}. None = the lead is off. Never raises."""
    try:
        if key == "zlarior":
            led = list(getattr(bot, "ledger", None) or [])
            ot = getattr(bot, "_open_routed", None)
            ad = getattr(bot, "adapter", None)
            closes = {}
            for r in led:
                if r.get("side") == "exit" and r.get("entry_t") is not None:
                    c = closes.setdefault(int(r["entry_t"]), {"pnl": 0.0, "qty": 0, "exit_t": None, "reason": None})
                    c["pnl"] = round(c["pnl"] + float(r.get("pnl") or 0.0), 2)
                    c["qty"] = max(int(c["qty"] or 0), int(r.get("qty") or 0))
                    c["exit_t"] = int(r.get("exit_t") or r.get("t") or 0)
                    c["reason"] = r.get("reason")
            name = (getattr(bot, "cfg", None) or {}).get("nt_account") or "LIT"
        else:
            obj = getattr(bot, "acct_b" if key == "atlas" else "acct_c", None)
            if obj is None:
                return None
            led = list(getattr(obj, "ledger", None) or [])
            ot = getattr(obj, "open_t", None)
            ad = getattr(obj, "adapter", None)
            closes = {}
            for c in list(getattr(obj, "closes", None) or []):
                if len(c) > 3 and c[3] is not None:
                    e = _entry_row(led, int(c[3]))
                    x = next((r for r in reversed(led) if r.get("side") == "exit" and r.get("entry_t") == int(c[3])), None)
                    closes[int(c[3])] = {"pnl": float(c[2]), "qty": int((e or {}).get("qty") or 0), "exit_t": int(c[1]),
                                         "reason": (x or {}).get("reason")}
            name = getattr(obj, "name", None) or key
        op = None
        if ot is not None:
            e = _entry_row(led, ot)
            if e is not None and _ok(e.get("result")):
                d = 1 if e["side"] == "buy" else -1
                op = {"entry_t": int(ot), "dir": d, "qty": int(e.get("qty") or 0), "entry": _num(e.get("entry")),
                      "stop": _num(_cur_stop(led, ot, e.get("stop"))), "stop0": _num(e.get("stop")), "target": _num(e.get("target")),
                      "t": int(e.get("t") or 0), "fill": _fill_px(ad, ot), "sym": e.get("sym") or "NQ"}
        return {"key": key, "name": str(name), "open": op, "closes": closes}
    except Exception as e:
        return {"key": key, "name": key, "open": None, "closes": {}, "error": f"{e.__class__.__name__}: {e}"}


def lead_positions(bot) -> list:
    """Every non-follower account's open position {account, sym, dir, rank}: LIT's account, the extra accounts
    (engine/multi_account), ATLAS (account B, incl. a close not confirmed yet), BLITZ (account C, the same)."""
    out = []
    try:
        ot = getattr(bot, "_open_routed", None)
        if ot is not None:
            e = _entry_row(getattr(bot, "ledger", None), ot)
            if e is not None:
                out.append({"account": "Zlarior (LIT's account)", "sym": e.get("sym") or "NQ", "dir": 1 if e["side"] == "buy" else -1, "rank": 0})
        st = getattr(bot, "state", None) or {}
        en = st.get("enter_now") if isinstance(st, dict) else None
        if en and en.get("dir") in (1, -1) and ot is None:
            out.append({"account": "Zlarior (entering)", "sym": "NQ", "dir": int(en["dir"]), "rank": 0})
    except Exception:
        pass
    for a in list(getattr(getattr(bot, "accts", None), "accounts", None) or []):
        try:
            if a.open_t is not None:
                e = _entry_row(a.ledger, a.open_t)
                if e is not None:
                    out.append({"account": a.name, "sym": e.get("sym") or "NQ", "dir": 1 if e["side"] == "buy" else -1, "rank": 0})
        except Exception:
            continue
    for key, rank in (("acct_b", 1), ("acct_c", 2)):
        obj = getattr(bot, key, None)
        if obj is None:
            continue
        try:
            nm = ("ATLAS " if key == "acct_b" else "BLITZ ") + str(getattr(obj, "name", "") or "")
            prov = getattr(obj, "prov", None) or {}
            if obj.open_t is not None:
                pv = prov.get(int(obj.open_t)) or {}
                d = pv.get("dir")
                if d is None:
                    e = _entry_row(obj.ledger, obj.open_t)
                    d = (1 if e["side"] == "buy" else -1) if e else None
                if d in (1, -1):
                    out.append({"account": nm.strip(), "sym": "NQ", "dir": int(d), "rank": rank})
            closing = obj.closing_open() if callable(getattr(obj, "closing_open", None)) else []
            for _, pv in closing or []:
                if int(pv.get("dir") or 0) in (1, -1):
                    out.append({"account": nm.strip() + " (closing)", "sym": "NQ", "dir": int(pv["dir"]), "rank": rank})
        except Exception:
            out.append({"account": key, "sym": "NQ", "dir": 0, "rank": rank, "unreadable": True})
    return out


# ---------------------------------------------------------------------------------------------------------------- follower
class Follower:
    """One follower account: its adapter, ledger, closed trades, position, slippage, lifecycle."""

    def __init__(self, spec: dict, fleet):
        self.spec = spec
        self.fleet = fleet
        self.id, self.name, self.lead = spec["id"], spec["name"], spec["lead"]
        self.rank = LEADS.get(self.lead, 9)
        self.profile = profile_of(spec)
        self.problem = spec.get("problem")
        self.adapter = None
        self.ledger: list = []
        self.closes: list = []            # [day, exit_t, pnl, entry_t, reason]
        self.pos = None                   # {entry_t, dir, qty, entry, stop, target, t, lead_fill, fill, sym, lead_qty}
        self.seen: set = set()
        self.skips: list = []             # [{entry_t, t, why}] the last 30
        self.slips: list = []             # [{entry_t, ticks, ms}] the last 60
        self.notified: set = set()
        self.last_size = None
        self.mx = threading.RLock()

    # ---- plumbing
    def log(self, kind, text):
        self.fleet.log(kind, f"[fleet {self.name}] {text}")

    @property
    def stage(self):
        return self.spec["stage"]

    def start_day(self) -> str:
        return (self.spec.get("funded_start") or self.spec.get("start")) if self.stage == "funded" else self.spec.get("start") or ""

    def start_balance(self) -> float:
        P = self.profile or {}
        if self.stage == "live":
            return float(_num((self.spec.get("live") or {}).get("start"), _num(self.spec.get("balance"), 0.0)) or 0.0)
        return float(_num(self.spec.get("balance"), _num(P.get("start"), _num(P.get("size"), 50000.0))))

    def route(self, action: dict) -> dict:
        try:
            res = self.adapter.send(action) if self.adapter is not None else {"ok": False, "error": "no adapter"}
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        with self.mx:
            self.ledger.append({"t": int(self.fleet.clock()), **action, "result": res})
            self.ledger = self.ledger[-400:]
        self.log("order", f"{action['side'].upper()} {action.get('qty', '')} {action.get('sym')} -> {res.get('ok')}"
                 + (f" ({res.get('error')})" if res.get("ok") is False and res.get("error") else ""))
        return res

    def skip(self, et_, why, now):
        with self.mx:
            self.skips.append({"entry_t": int(et_), "t": int(now), "why": str(why)[:160]})
            self.skips = self.skips[-30:]
        self.log("risk", f"lead entry at {_et(et_):%H:%M} ET NOT copied: {why}")

    def ledger_dir(self, et_):
        e = _entry_row(self.ledger, et_)
        return (1 if e.get("side") == "buy" else -1) if e else None

    def closes3(self):
        start = self.start_day()
        return [(d, t, p) for d, t, p, *_ in self.closes if not start or d >= start]

    def state(self, now) -> dict:
        today = trading_day(now)
        q = int((self.pos or {}).get("qty") or 0)
        pays = self.spec.get("payouts") if self.stage == "funded" else None
        st = firms.book(self.start_balance(), self.closes3(), today, prior=self.spec.get("prior_pnl") or 0.0, payouts=pays,
                        open_micros=q)
        return st

    def view(self, now) -> dict:
        st = self.state(now)
        s = firms.status(self.profile, st) if self.profile else {"status": "unknown"}
        return {"st": st, "status": s}

    def why_not(self, now) -> str | None:
        """Why this follower takes no new entry now (None = it may)."""
        if self.fleet.killed():
            return "fleet kill switch"
        if self.spec.get("killed"):
            return "killed (this account)"
        if self.problem:
            return self.problem
        if self.adapter is None:
            return "adapter not created"
        dis = getattr(self.adapter, "disabled", None)
        if dis:
            return f"adapter disabled: {dis}"
        if self.start_day() and trading_day(now) < self.start_day():
            return f"starts on {self.start_day()}"
        v = self.view(now)["status"]
        if v.get("status") in ("passed", "failed"):
            return f"{self.stage} {v['status']}: {v.get('why') or ''}".strip()
        try:
            from . import cme_calendar as _cc
            today = trading_day(now)
            if _cc.full_closure(today):
                return f"CME holiday ({today})"
        except Exception:
            pass
        n_today = sum(1 for r in self.ledger if r.get("side") in ("buy", "sell") and trading_day(r["t"]) == trading_day(now)
                      and _ok(r.get("result")))
        lim = 6 if self.lead == "blitz" else (2 if self.lead == "atlas" else 1)
        if n_today >= lim:
            return f"{n_today} entries today already (the lead's own limit {lim})"
        return None

    # ---- sizing
    def ma_rules(self) -> dict:
        """The plan's rules in engine/multi_account's shape (the lead bot's sizer reads them)."""
        from . import multi_account as MA
        P = self.profile
        pre = (MA.PRESETS.get(P.get("sizing_preset") or "") or MA.PRESETS[MA.DEFAULT_PRESET])["rules"]
        trail = {"eod": "eod", "intraday": "intra", "static": "static"}.get(P.get("dd_type"), "intra")
        dll = _num(P.get("dll"))
        lock = _num(P.get("lock"))
        mx = firms.max_micros(P)
        cons = _num(P.get("consistency"))
        return {"start": self.start_balance(), "target": float(_num(P.get("target"), pre["target"])),
                "mll": float(_num(P.get("dd_amount"), pre["mll"])), "lock": float(lock) if lock is not None else 1e9,
                "dll": float(dll) if dll is not None else float(pre["dll"]),       # no / unknown firm limit: the bot's own soft one
                "max_micros": int(mx) if mx is not None else int(pre["max_micros"]), "trail": trail,
                "best_day": cons if (cons and P.get("stage") == "eval") else None, "news_ban": False,
                "min_room": float(pre.get("min_room", 100.0)), "scale": float(pre.get("scale", 1.0))}

    def size(self, order: dict, now) -> dict:
        """{"qty", "reasons"} before the firm check: the lead bot's sizing on this plan, or a fixed $ risk."""
        from . import sizing as sz
        risk = abs(float(order["entry"]) - float(order["stop"])) if order.get("entry") is not None and order.get("stop") is not None else None
        tgt = abs(float(order["target"]) - float(order["entry"])) if order.get("target") is not None and order.get("entry") is not None else None
        if not risk or risk <= 0:
            return {"qty": 0, "reasons": ["no stop distance"]}
        P = self.profile
        if self.spec["sizing"] == "fixed" or self.stage == "live":
            usd = float(P.get("max_risk_usd") if self.stage == "live" else self.spec.get("risk_usd") or 0.0)
            loss1 = (risk + firms.SLIP_PTS) * firms.PV.get(firms.underlying(order.get("sym")), 2.0) + firms.COMM
            q = int(usd // loss1) if loss1 > 0 else 0
            return {"qty": q, "reasons": [f"fixed ${usd:,.0f} risk / ${loss1:,.2f} a micro at a {risk:.2f}-pt stop -> {q}"]}
        from . import multi_account as MA
        R = self.ma_rules()
        today = trading_day(now)
        mode = "funded" if self.stage == "funded" else "two_week"
        st = MA.sizing_state(mode, self.closes3(), today, self.start_day() or None, R, prior=self.spec.get("prior_pnl") or 0.0,
                             payouts=self.spec.get("payouts") if self.stage == "funded" else None)
        if st is None:
            return {"qty": 0, "reasons": ["account state unknown (start missing?): not traded"]}
        base = self.fleet.base_sizing()
        preset = P.get("sizing_preset") or MA.DEFAULT_PRESET
        if self.lead == "atlas":
            from . import account_b as AB
            spec = {"preset": preset, "rules": R, "plan": "builder25k" if R["start"] <= 25000 else "builder50k",
                    "eval_start": self.start_day(), **({"stage": "funded", "funded": {"start": self.start_day(),
                                                                                       "payouts": dict(self.spec.get("payouts") or {})}}
                                                       if self.stage == "funded" else {})}
            r = AB.qty(spec, {"risk_pts": risk, "tgt_pts": tgt}, st, base=base)
            return {"qty": int(r.get("qty") or 0), "reasons": list(r.get("reasons") or [])}
        if self.lead == "blitz":
            from . import account_c as AC
            spec = {"rules": R, **({"stage": "funded", "funded": {"start": self.start_day()}} if self.stage == "funded" else {})}
            r = AC.qty(spec, risk, st)
            return {"qty": int(r.get("qty") or 0), "reasons": list(r.get("reasons") or [])}
        from . import lit as _lit
        n = MA.normalize({"id": "fleet", "preset": preset, "mode": mode, "adapter": "paper", "eval_start": self.start_day(),
                          "rules": R})
        n["rules"] = R
        lsz = MA.sizing_cfg(base, n)
        m0 = _lit.qty_for(float(risk))
        r = sz.lit_qty(max(1, int(m0)), {"risk_pts": risk, "tgt_pts": tgt, "entry": order.get("entry"), "stop": order.get("stop"),
                                          "target": order.get("target"), "size_mult": 1.0},
                       lsz, room=st.get("room"), state=dict(st), max_micros=int(R["max_micros"]))
        return {"qty": int(r.get("qty") or 0), "reasons": list(r.get("reasons") or [])}

    # ---- one poll
    def process(self, ctx: dict):
        try:
            self._process(ctx)
        except Exception as e:
            self.log("error", f"follow failed: {e.__class__.__name__}: {e}")

    def _process(self, ctx):
        now, sym = int(ctx["now"]), ctx["sym"]
        snap = (ctx.get("leads") or {}).get(self.lead)
        if self.pos is not None:
            self._manage(snap, sym, now, ctx)
        if self.pos is not None or snap is None or self.problem is not None or self.adapter is None:
            return
        op = snap.get("open")
        if not op or op["entry_t"] in self.seen:
            return
        et_ = int(op["entry_t"])
        self.seen.add(et_)
        age = now - int(op.get("t") or now)
        why = None
        if et_ < int(ctx.get("started_at") or 0) - 60 or age > MAX_AGE_S:
            why = f"seen {age} s after the lead's order (no chasing a late entry)"
        why = why or self.why_not(now)
        order = {"sym": op.get("sym") or sym, "side": "buy" if op["dir"] == 1 else "sell", "dir": op["dir"],
                 "entry": op.get("entry"), "stop": op.get("stop0") if op.get("stop0") is not None else op.get("stop"),
                 "target": op.get("target"), "entry_t": et_}
        if why:
            self.skip(et_, why, now)
            return
        sz = self.size(order, now)
        q0 = int(sz.get("qty") or 0)
        st = self.state(now)
        chk = firms.check(self.profile, st, {**order, "qty": max(1, q0)}, positions=self.fleet.positions(exclude=self), now=now)
        q = min(q0, int(chk.get("max_qty") or 0)) if chk.get("ok") else 0
        self.last_size = {"qty": q, "lead_qty": int(op.get("qty") or 0), "reasons": [str(x)[:140] for x in (sz.get("reasons") or [])][-4:],
                          "firm": (chk.get("block") or chk.get("warn") or [])[:3], "t": now}
        if not chk.get("ok"):
            self.skip(et_, "firm rule: " + "; ".join(chk["block"][:2]), now)
            return
        if q < 1:
            self.skip(et_, "size 0: " + "; ".join((sz.get("reasons") or [])[-2:] + (chk.get("warn") or [])[:1]), now)
            return
        ms = int(self.spec.get("stagger_ms") or 0)
        if ms:
            self.fleet.sleep(ms / 1000.0)
        # the lead may have closed or a hedge appeared while we waited: check again right before the order, under the
        # fleet's entry lock (two followers of different leads can never pass the no-hedge check at the same moment)
        with self.fleet.entry_mx:
            h = firms.hedge_conflict(order, self.fleet.positions(exclude=self))
            if h:
                self.skip(et_, h, now)
                return
            t0 = time.perf_counter()
            act = {"sym": order["sym"], "side": order["side"], "qty": q, "stop": order["stop"], "target": order["target"],
                   "entry": order["entry"], "entry_t": et_}
            rr = self.route(act)
            unconf = not _ok(rr) and not self.never_placed(et_, rr, now)
            if _ok(rr) or unconf:
                self.pos = {"entry_t": et_, "dir": int(op["dir"]), "qty": q, "entry": order["entry"], "stop": order["stop"],
                            "target": order["target"], "t": now, "sym": order["sym"], "lead_fill": op.get("fill"), "fill": None,
                            "lead_qty": int(op.get("qty") or 0), "lead_t": int(op.get("t") or now),
                            "route_ms": int((time.perf_counter() - t0) * 1000) + ms}
                if unconf:
                    self.pos["unconfirmed"] = True
        if unconf:
            # NOT OK, but the broker may still hold it (a leg still working, "fill not reported yet"): kept and managed as
            # account B does; dropped without booking once it is provably never placed (checked every poll)
            self.log("risk", f"copy NOT confirmed ({str(rr.get('error') or '')[:120]}): kept and managed until NinjaTrader shows it either way")
            self.fleet.notify(f"{self.name}: copy NOT confirmed", f"the {LEAD_NAMES.get(self.lead)} {_side(op['dir'])} copy ({q} micros) "
                              f"got no clear answer: {str(rr.get('error') or '')[:120]}. Check this account in NinjaTrader.",
                              f"fleet:{self.id}:unconfirmed:{et_}")
        elif not _ok(rr):
            # refused / never placed by this account's broker: nothing booked here, the other followers are not affected
            self.skip(et_, f"REFUSED by the broker: {str(rr.get('error') or 'no reason given')[:120]} (nothing booked)", now)
            self.fleet.notify(f"{self.name}: copy NOT placed", f"the {LEAD_NAMES.get(self.lead)} {_side(op['dir'])} copy ({q} micros) "
                              f"was refused: {str(rr.get('error') or '')[:120]}. Nothing booked on this account.",
                              f"fleet:{self.id}:refused:{et_}")
            return
        self._slip()
        self.fleet.notify_entry(self, q)
        self.log("system", f"copied {LEAD_NAMES.get(self.lead)} {_side(op['dir'])} {q} micros (lead {op.get('qty')}), stop "
                           f"{order['stop']}, target {order['target']}")
        self.fleet.save()

    def _slip(self):
        p = self.pos
        if not p:
            return
        if p.get("fill") is None:
            p["fill"] = _fill_px(self.adapter, p["entry_t"])
        if p.get("fill") is None and getattr(self.adapter, "name", None) == "paper":
            p["fill"] = p.get("entry")
        lf = p.get("lead_fill") if p.get("lead_fill") is not None else None
        if p.get("fill") is not None and lf is not None and not p.get("slip_done"):
            ticks = round((float(p["fill"]) - float(lf)) * p["dir"] / TICK, 2)     # + = worse than the lead
            p["slip_done"] = True
            with self.mx:
                self.slips.append({"entry_t": p["entry_t"], "ticks": ticks, "ms": int((p.get("t") or 0) - (p.get("lead_t") or 0)) * 1000
                                   + int(p.get("route_ms") or 0)})
                self.slips = self.slips[-60:]

    def never_placed(self, et_, res, now) -> bool:
        """This follower's entry et_ provably never became a position (engine/ninjatrader.entry_never_placed, the rule LIT
        and account B use; paper: the answer was NOT OK). Anything unclear = False."""
        if getattr(self.adapter, "name", None) == "paper":
            return not _ok(res)
        try:
            from .ninjatrader import entry_never_placed
            return bool(entry_never_placed(self.adapter, et_, res, now=now))
        except Exception:
            return False

    def _manage(self, snap, sym, now, ctx):
        p = self.pos
        et_ = p["entry_t"]
        if p.get("unconfirmed"):
            if _fill_px(self.adapter, et_) is not None:
                p.pop("unconfirmed", None)
            else:
                e = _entry_row(self.ledger, et_)
                if self.never_placed(et_, (e or {}).get("result"), now):
                    with self.mx:
                        self.pos = None
                    self.skip(et_, "never placed by the broker (nothing booked)", now)
                    self.fleet.notify(f"{self.name}: copy NOT placed", "NinjaTrader never took the copy: nothing booked on this account.",
                                      f"fleet:{self.id}:refused:{et_}")
                    self.fleet.save()
                    return
        if p.get("lead_fill") is None and snap and (snap.get("open") or {}).get("entry_t") == et_:
            p["lead_fill"] = snap["open"].get("fill")
        self._slip()
        if self.fleet.killed() or self.spec.get("killed"):
            self.flatten("KILL SWITCH", sym, now, ctx)
            return
        c = (snap or {}).get("closes", {}).get(et_) if snap else None
        if c is not None:
            lq = int(c.get("qty") or p.get("lead_qty") or 0)
            pm = float(c["pnl"]) / lq if lq else 0.0
            pnl = round(pm * int(p["qty"]), 2)
            if getattr(self.adapter, "name", None) == "paper" or getattr(self.adapter, "route_all_exits", False):
                rr = self.route({"sym": p["sym"], "side": "exit", "qty": p["qty"], "reason": c.get("reason") or "LEAD EXIT", "pnl": pnl,
                                 "entry_t": et_, "exit_t": c.get("exit_t") or now})
                if not _ok(rr) and getattr(self.adapter, "name", None) != "paper":
                    # the broker did not confirm the close: kept and managed, re-sent at the next poll (never booked flat on a guess)
                    p["close_tries"] = int(p.get("close_tries") or 0) + 1
                    self.log("risk", f"close after the lead's {c.get('reason')} NOT confirmed ({str(rr.get('error') or '')[:100]}): re-sent next poll")
                    if p["close_tries"] == 3:
                        self.fleet.notify(f"{self.name}: close NOT confirmed", f"the copy's close after the lead's {c.get('reason')} was not "
                                          f"confirmed 3 times: check this account in NinjaTrader now.", f"fleet:{self.id}:closefail:{et_}")
                    return
            self._book(et_, int(c.get("exit_t") or now), pnl, c.get("reason") or "LEAD EXIT", now)
            return
        op = (snap or {}).get("open")
        if op and op.get("entry_t") == et_:
            p.pop("gone_t", None)
            new = _num(op.get("stop"))
            old = _num(p.get("stop"))
            if new is not None and old is not None and (new - old) * p["dir"] > 1e-9 and getattr(self.adapter, "route_stop_moves", False):
                tries = sum(1 for r in self.ledger if r.get("entry_t") == et_ and r.get("side") == "modify" and r.get("stop") == new)
                if tries < 3:
                    rr = self.route({"sym": p["sym"], "side": "modify", "qty": p["qty"], "stop": new, "entry_t": et_,
                                     "reason": "BE" if (new - float(p.get("entry") or new)) * p["dir"] >= 0 else "STOP MOVE"})
                    if _ok(rr):
                        p["stop"] = new
            elif new is not None and old is not None and (new - old) * p["dir"] > 1e-9:
                p["stop"] = new
            e = _et(now)
            if e.hour * 60 + e.minute >= 958 and e.hour < 18:
                self.flatten("TIME SAFETY", sym, now, ctx)
            return
        # the lead no longer holds it and booked no close (never placed / voided / reconciled): flat after a grace period
        # (a new lead trade on the same account means the old one is over: at once)
        p.setdefault("gone_t", now)
        if snap is None or now - int(p.get("gone_t") or now) >= GONE_GRACE_S or (op and op.get("entry_t") != et_):
            self.flatten("LEAD GONE", sym, now, ctx)

    def mark_pnl(self, ctx) -> float | None:
        p = self.pos
        px = _num((ctx or {}).get("price"))
        if p is None or px is None or p.get("entry") is None:
            return None
        pv = firms.PV.get(firms.underlying(p.get("sym")), 2.0)
        return round(int(p["qty"]) * (p["dir"] * (px - float(p.get("fill") or p["entry"])) * pv - firms.COMM), 2)

    def flatten(self, reason, sym, now, ctx=None) -> bool:
        """Close this follower at market. True = the close went out (ok); the position is booked at the mark (or $0)."""
        p = self.pos
        if p is None:
            return True
        pnl = self.mark_pnl(ctx or {"price": self.fleet.price()})
        rr = self.route({"sym": p["sym"], "side": "exit", "qty": p["qty"], "reason": reason, "entry_t": p["entry_t"],
                         **({"pnl": pnl, "pnl_est": True} if pnl is not None else {})})
        if not _ok(rr) and getattr(self.adapter, "name", None) != "paper":
            self.log("risk", f"{reason}: the close was NOT confirmed ({rr.get('error')}): still managed, re-sent next poll")
            return False
        self._book(p["entry_t"], int(now), float(pnl or 0.0), reason, now, est=pnl is None)
        return True

    def _book(self, et_, exit_t, pnl, reason, now, est=False):
        with self.mx:
            if not any(len(c) > 3 and c[3] == et_ for c in self.closes):
                self.closes.append([trading_day(exit_t), int(exit_t), float(pnl), int(et_), str(reason or "")[:24]])
                self.closes = self.closes[-1500:]
            self.pos = None
        self.log("system", f"closed {reason}: ${pnl:+,.2f}" + (" (no mark: $0 booked, check the broker)" if est else ""))
        self.fleet.notify_outcome(self, reason, pnl, et_)
        self.lifecycle(now)
        self.fleet.save()

    def lifecycle(self, now):
        """Pushes once per event: eval passed / failed, funded failed, payout ready."""
        try:
            v = self.view(now)
            s, st = v["status"], v["st"]
            key = f"fleet:{self.id}:{self.stage}:{s.get('status')}:{self.start_day()}"
            if s.get("status") == "passed" and key not in self.notified:
                self.notified.add(key)
                self.fleet.notify(f"{self.name}: EVAL PASSED", f"+${st['profit']:,.0f}. No new entries on it. Switch it to funded once "
                                  f"the firm gives the funded account: python -X utf8 -m engine.fleet --to-funded {self.id} "
                                  f"--account \"<funded Name>\" --start <day>", key, kind="ops")
            elif s.get("status") == "failed" and key not in self.notified:
                self.notified.add(key)
                self.fleet.notify(f"{self.name}: {self.stage.upper()} FAILED", f"{s.get('why')}. The bot stopped trading it.", key, kind="ops")
            po = s.get("payout") or {}
            if self.stage == "funded" and po.get("ready"):
                k2 = f"fleet:{self.id}:payout:{int((po.get('above_buffer') or 0) // 250)}:{len(self.spec.get('payouts') or {})}"
                if k2 not in self.notified:
                    self.notified.add(k2)
                    amt = min(float(po.get("above_buffer") or 0), float(po.get("max") or po.get("above_buffer") or 0))
                    self.fleet.notify(f"{self.name}: PAYOUT READY", f"about ${amt:,.0f} above the buffer (check the firm's own payout page; "
                                      f"record it: python -X utf8 -m engine.fleet --payout {self.id} <day>=<$>)", k2, kind="ops")
        except Exception as e:
            self.log("error", f"lifecycle check failed: {e.__class__.__name__}: {e}")

    # ---- views / persistence
    def row(self, now) -> dict:
        v = self.view(now)
        st, s = v["st"], v["status"]
        P = self.profile or {}
        sl = [x["ticks"] for x in self.slips if x.get("ticks") is not None]
        warn = list(P.get("warn") or [])[:4]
        if self.lead != "zlarior" and getattr(self.fleet.bot, "acct_b" if self.lead == "atlas" else "acct_c", None) is None:
            warn.insert(0, f"{LEAD_NAMES.get(self.lead)} is not running on this PC: nothing to copy")
        if self.problem:
            warn.insert(0, self.problem)
        p = self.pos
        return {"id": self.id, "name": self.name, "lead": self.lead, "lead_name": LEAD_NAMES.get(self.lead), "firm": P.get("firm"),
                "plan": P.get("plan"), "plan_id": self.spec.get("plan"), "stage": self.stage,
                "status": "killed" if (self.spec.get("killed") or self.fleet.killed()) else
                          ("off" if self.problem else s.get("status")),
                "label": self.spec.get("label"), "nt_account": self.spec.get("nt_account") or None,
                "balance": st.get("balance"), "start": self.start_balance(), "profit": st.get("profit"),
                "room": s.get("room"), "floor": s.get("floor"), "day_left": s.get("day_left"), "week_left": s.get("week_left"),
                "to_target": s.get("to_target"), "today": st.get("day_pnl"), "week": st.get("week_pnl"),
                "days_traded": st.get("days_traded"), "trades": len(self.closes3()),
                "open": ({"side": _side(p["dir"]), "qty": p["qty"], "entry": p.get("fill") or p.get("entry"), "stop": p.get("stop"),
                          "target": p.get("target"), "entry_t": p["entry_t"]} if p else None),
                "slip_ticks": round(sum(sl) / len(sl), 2) if sl else None, "slip_n": len(sl),
                "last_skip": (self.skips[-1] if self.skips else None), "size": self.last_size,
                "payout": s.get("payout"), "why": s.get("why"), "warn": warn[:5], "stagger_ms": self.spec.get("stagger_ms") or 0,
                "unverified": len([k for k, x in (P.get("verified") or {}).items() if not x]), "unknown": list(P.get("unknown") or [])[:8]}

    def blob(self) -> dict:
        with self.mx:
            return {"id": self.id, "nt_account": self.spec.get("nt_account"), "plan": self.spec.get("plan"),
                    "ledger": self.ledger[-300:], "closes": list(self.closes), "pos": self.pos, "seen": sorted(self.seen)[-500:],
                    "skips": self.skips[-30:], "slips": self.slips[-60:], "notified": sorted(self.notified)[-200:]}

    def restore(self, b: dict):
        if not b or b.get("nt_account") != self.spec.get("nt_account"):
            return
        self.closes = [list(c) for c in b.get("closes") or [] if isinstance(c, (list, tuple)) and len(c) >= 4]
        self.ledger = list(b.get("ledger") or [])
        self.pos = b.get("pos") if isinstance(b.get("pos"), dict) else None
        self.seen = {int(x) for x in b.get("seen") or []}
        self.skips = list(b.get("skips") or [])
        self.slips = list(b.get("slips") or [])
        self.notified = set(b.get("notified") or [])


# ---------------------------------------------------------------------------------------------------------------- fleet
class Fleet:
    """Every follower of data/fleet.json (or the start cfg's "fleet" block in a test harness)."""

    def __init__(self, bot, cfg: dict, state_path: str | None = None, adapter_factory=None, parallel: bool = True,
                 sleep=None, notify=None):
        self.bot = bot
        self.cfg = cfg or {}
        self.state_path = state_path or _state_path_for(getattr(bot, "state_path", None))
        self.adapter_factory = adapter_factory if adapter_factory is not None else ADAPTER_FACTORY
        self.parallel = parallel
        self._sleep = sleep or time.sleep
        self._notify_hook = notify
        self.notes: list = []
        self.mx = threading.RLock()
        self.entry_mx = threading.Lock()          # the no-hedge check + the entry order, one follower at a time
        self._kill = False
        reserved = self._reserved()
        ids, names, specs = set(), set(), []
        for r in self.cfg.get("accounts") or []:
            n = normalize(r, ids, names, reserved)
            ids.add(n["id"])
            if n["adapter"] == "ninjatrader" and n["nt_account"]:
                names.add(n["nt_account"])
            specs.append(n)
        self.followers = [Follower(s, self) for s in specs]

    # ---- plumbing
    def clock(self):
        c = getattr(self.bot, "clock", None)
        return c() if callable(c) else time.time()

    def sleep(self, s):
        try:
            self._sleep(s)
        except Exception:
            pass

    def log(self, kind, text):
        try:
            self.bot._log(kind, text)
        except Exception:
            pass

    def price(self):
        st = getattr(self.bot, "state", None) or {}
        return _num(st.get("price")) if isinstance(st, dict) else None

    def killed(self) -> bool:
        return self._kill or self.cfg.get("kill") is True or bool(getattr(self.bot, "kill", False))

    def base_sizing(self) -> dict:
        return dict(getattr(self.bot, "_lit_sizing", None) or {})

    def real_bot(self) -> bool:
        try:
            from .live import STATE_PATH
            return getattr(self.bot, "state_path", None) == STATE_PATH
        except Exception:
            return False

    def _reserved(self) -> dict:
        """The NinjaTrader Names the leads already trade (a follower needs its own account)."""
        out = {}
        b = self.bot
        try:
            nm = (getattr(b, "cfg", None) or {}).get("nt_account")
            if nm:
                out[str(nm)] = "Zlarior"
        except Exception:
            pass
        for key, lab in (("acct_b", "ATLAS"), ("acct_c", "BLITZ")):
            o = getattr(b, key, None)
            if o is not None and getattr(o, "name", None):
                out[str(o.name)] = lab
        for a in list(getattr(getattr(b, "accts", None), "accounts", None) or []):
            if a.spec.get("nt_account"):
                out[str(a.spec["nt_account"])] = f"the extra account {a.name}"
        return out

    def notify(self, title, body, key, kind="ops", payload=None):
        """One notice: kept on the Fleet page (notes) and, for the real bot only, pushed to the phone (kind "ops" = the
        owner's PC notices that are pushed: copy NOT placed / NOT confirmed, eval passed / failed, payout ready; entries
        "fill" and exits "outcome" as every account's). Tests: the notify hook gets (title, body, key)."""
        self.notes.append({"title": title, "body": body, "key": key, "kind": kind, "t": int(self.clock())})
        self.notes = self.notes[-100:]
        if self._notify_hook is not None:
            try:
                self._notify_hook(title, body, key)
            except Exception:
                pass
            return
        if not self.real_bot():
            return
        try:
            from . import push
            p = payload or push.text_payload("PC", kind, title, body, key=key, t=int(self.clock()), url="#/fleet")
            push.pc_notify(p)
        except Exception:
            pass

    def _acct_label(self, f) -> str:
        return f"FLEET {f.spec.get('label')} {f.name}"

    def notify_entry(self, f, q):
        p = f.pos or {}
        try:
            from . import push
            pl = push.entry_payload(self._acct_label(f), _side(p.get("dir", 1)), q, p.get("entry_t"), src="pc", contract="MNQ",
                                    entry=p.get("entry"), stop=p.get("stop"), target=p.get("target"))
            pl.update(key=f"{pl['key']}:fleet:{f.id}", tag=f"{pl.get('tag', '')}-fleet-{f.id}", url="#/fleet")
        except Exception:
            pl = None
        self.notify(f"{_side(p.get('dir', 1))} · {self._acct_label(f)}", f"Entered {q} MNQ (copy of {LEAD_NAMES.get(f.lead)})",
                    f"fleet:{f.id}:entry:{p.get('entry_t')}", kind="fill", payload=pl)

    def notify_outcome(self, f, reason, pnl, et_):
        try:
            from . import push
            pl = push.outcome_payload(self._acct_label(f), _side((f.ledger_dir(et_) or 1)), reason, pnl, et_, int(self.clock()), src="pc")
            pl.update(key=f"{pl['key']}:fleet:{f.id}", tag=f"{pl.get('tag', '')}-fleet-{f.id}", url="#/fleet")
        except Exception:
            pl = None
        self.notify(f"{self._acct_label(f)}: {reason} ${pnl:+,.0f}", f"copy of {LEAD_NAMES.get(f.lead)} "
                    f"({f.profile.get('label') if f.profile else ''})", f"fleet:{f.id}:exit:{et_}", kind="outcome", payload=pl)

    # ---- lifecycle
    def adapter_cfg(self, f: Follower) -> dict:
        b = getattr(self.bot, "cfg", None) or {}
        base = {k: v for k, v in b.items() if k not in ("accounts", "armed", "confirm", "nt_account", "nt_state_path", "nt_audit_log",
                                                         "eval_start", "eval_prior_pnl", "eval_anchor", "lit_sizing", "funded",
                                                         "webhook_url", "account_b", "account_c", "fleet")}
        s = f.spec
        p = dict(base.get("params") or {})
        mx = firms.max_micros(f.profile or {}) or 40
        p["max_micros"] = min(int(p.get("max_micros", 40) or 40), int(mx))
        d = os.path.dirname(self.state_path)
        armed = s.get("armed") is True
        return {**base, "adapter": s["adapter"], "nt_account": s["nt_account"], "armed": armed,
                "confirm": (b.get("confirm") or "") if armed else "", "params": p, "nt_file_tag": f"fl{f.id}_"[:24],
                "nt_state_path": os.path.join(d, f"ninjatrader_state_fleet_{f.id}.json"),
                "nt_audit_log": os.path.join(os.path.join(ROOT, "logs") if self.real_bot() else d, f"ninjatrader_oif_fleet_{f.id}.log")}

    def start(self):
        saved = self._load()
        for f in self.followers:
            f.restore((saved.get("followers") or {}).get(f.id) or {})
            if f.problem is None:
                g = live_gate(f.spec, getattr(self.bot, "cfg", None))
                if g:
                    f.problem = g
            if f.problem is not None:
                self.log("risk", f"[fleet {f.name}] not trading: {f.problem}")
                continue
            try:
                cfg = self.adapter_cfg(f)
                if self.adapter_factory is not None:
                    f.adapter = self.adapter_factory(f, cfg)
                else:
                    from .live import ADAPTERS
                    f.adapter = ADAPTERS[cfg["adapter"]](cfg)
            except Exception as e:
                f.problem = f"adapter failed: {e.__class__.__name__}: {e}"
            self.log("system" if f.problem is None else "risk",
                     f"[fleet {f.name}] {f.spec.get('label')} {f.spec.get('nt_account') or ''} follows {LEAD_NAMES.get(f.lead)} on "
                     f"{(f.profile or {}).get('label')} ({f.stage}) from {f.start_day() or '?'}: "
                     + (f"DISABLED ({f.problem})" if f.problem else "ready"))
        self.save()
        return self

    def update_cfg(self, cfg: dict):
        """A changed data/fleet.json: kill flags apply at once; a follower whose entry changed is rebuilt once it is flat."""
        self.cfg = cfg or {}
        by_id = {r.get("id"): r for r in self.cfg.get("accounts") or [] if isinstance(r, dict)}
        reserved = self._reserved()
        keep = []
        ids, names = set(), set()
        for f in self.followers:
            r = by_id.get(f.id)
            if r is None:
                if f.pos is not None:
                    keep.append(f)               # removed while open: managed until flat, no new entry
                    f.problem = "removed from the fleet (closing)"
                continue
            n = normalize(r, ids, names, reserved)
            ids.add(n["id"])
            if n["adapter"] == "ninjatrader" and n["nt_account"]:
                names.add(n["nt_account"])
            if json.dumps({k: v for k, v in n.items() if k != "label"}, sort_keys=True, default=str) == \
                    json.dumps({k: v for k, v in f.spec.items() if k != "label"}, sort_keys=True, default=str):
                keep.append(f)
                continue
            if f.pos is not None and n.get("nt_account") == f.spec.get("nt_account"):
                f.spec["killed"] = n["killed"]   # a kill / off reaches an open follower at once; the rest once it is flat
                f.spec["enabled"] = n["enabled"]
                if not n["enabled"]:
                    f.problem = "switched off (enabled false)"
                keep.append(f)
                continue
            nf = Follower(n, self)
            nf.restore(f.blob())
            keep.append(nf)
            self._start_one(nf)
        known = {f.id for f in keep}
        for r in self.cfg.get("accounts") or []:
            if isinstance(r, dict) and r.get("id") not in known:
                n = normalize(r, ids, names, reserved)
                ids.add(n["id"])
                nf = Follower(n, self)
                keep.append(nf)
                self._start_one(nf)
        self.followers = keep
        self.save()

    def _start_one(self, f):
        if f.problem is None:
            g = live_gate(f.spec, getattr(self.bot, "cfg", None))
            if g:
                f.problem = g
        if f.problem is not None:
            return
        try:
            cfg = self.adapter_cfg(f)
            if self.adapter_factory is not None:
                f.adapter = self.adapter_factory(f, cfg)
            else:
                from .live import ADAPTERS
                f.adapter = ADAPTERS[cfg["adapter"]](cfg)
        except Exception as e:
            f.problem = f"adapter failed: {e.__class__.__name__}: {e}"

    def busy(self) -> bool:
        return any(f.pos is not None for f in self.followers)

    # ---- the anti-hedge rule, fleet-wide
    def positions(self, exclude=None, max_rank=None) -> list:
        out = [p for p in lead_positions(self.bot)]
        for f in self.followers:
            if f is exclude or f.pos is None:
                continue
            if max_rank is not None and f.rank > max_rank:
                continue
            out.append({"account": f"fleet {f.name}", "sym": f.pos.get("sym") or "NQ", "dir": int(f.pos["dir"]), "rank": f.rank})
        return out

    def opposite_open(self, d: int, max_rank=None, sym="NQ") -> str | None:
        """Why an order of direction d by a LEAD account would be opposite a follower (None = it is not). max_rank: count only
        followers whose lead ranks <= it (ATLAS (1) is held back by Zlarior followers (0); BLITZ by all)."""
        u = firms.underlying(sym)
        for f in self.followers:
            p = f.pos
            if p is None or (max_rank is not None and f.rank > max_rank):
                continue
            if firms.underlying(p.get("sym")) == u and int(p["dir"]) == -int(d):
                return f"hedging guard: fleet follower {f.name} holds a {_side(-int(d))} position"
        return None

    def yield_to(self, d: int, min_rank: int = 0, sym="NQ", now=None, who="LIT") -> bool:
        """A lead is about to enter in direction d: every follower (lead rank >= min_rank) holding the other side is closed at
        market FIRST. True = none is left opposite (closes went out); False = a close was not confirmed (do not route)."""
        now = int(now or self.clock())
        u = firms.underlying(sym)
        ok = True
        for f in self.followers:
            p = f.pos
            if p is None or f.rank < min_rank or firms.underlying(p.get("sym")) != u or int(p["dir"]) != -int(d):
                continue
            f.log("risk", f"no hedging: {who} enters {_side(d)}: this follower's {_side(-d)} is closed at market first (HEDGE)")
            if not f.flatten("HEDGE", sym, now, {"price": self.price()}):
                ok = False
        if not ok:
            self.save()
        return ok

    # ---- one poll
    def adapter_tick(self):
        """LiveBot._adapter_tick, before the data fetch: each follower's broker adapter gets its tick (late fills, bracket
        health). Never raises."""
        for f in self.followers:
            ad = f.adapter
            if ad is not None and getattr(ad, "loop_tick", False) and callable(getattr(ad, "tick", None)):
                try:
                    ad.tick()
                except Exception as e:
                    f.log("error", f"adapter tick failed: {e.__class__.__name__}: {e}")

    def tick(self, sym="NQ", now=None):
        now = int(now or self.clock())
        leads = {k: lead_snapshot(self.bot, k) for k in LEADS if any(f.lead == k for f in self.followers)}
        ctx = {"now": now, "sym": sym, "leads": leads, "price": self.price(), "started_at": int(getattr(self.bot, "started_at", 0) or 0)}
        live = [f for f in self.followers if f.adapter is not None or f.pos is not None]
        if not live:
            return
        threaded = self.parallel and (len(live) > 1 or any(f.spec.get("stagger_ms") for f in live)) and \
            any(f.spec["adapter"] != "paper" or f.spec.get("stagger_ms") for f in live)
        if not threaded:
            for f in live:
                f.process(ctx)
        else:
            ths = [threading.Thread(target=f.process, args=(ctx,), name=f"fleet-{f.id}", daemon=True) for f in live]
            for t in ths:
                t.start()
            for t in ths:
                t.join(30.0)
        self.save()

    def kill(self, sym="NQ") -> list:
        """Fleet-wide kill: every follower flattened, no new entry (until the bot restarts with the kill flag off)."""
        self._kill = True
        out = []
        for f in self.followers:
            if f.pos is None:
                continue
            ok = f.flatten("KILL SWITCH", sym, int(self.clock()), {"price": self.price()})
            out.append({"id": f.id, "ok": bool(ok)})
        self.save()
        return out

    def flatten_all(self, reason="REMOTE FLATTEN", sym="NQ") -> list:
        out = []
        for f in self.followers:
            if f.pos is not None:
                out.append({"id": f"fleet:{f.id}", "ok": bool(f.flatten(reason, sym, int(self.clock()), {"price": self.price()}))})
        self.save()
        return out

    def release(self):
        for f in self.followers:
            try:
                if callable(getattr(f.adapter, "release_lock", None)):
                    f.adapter.release_lock()
            except Exception:
                pass

    # ---- persistence
    def _load(self) -> dict:
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def save(self):
        if not self.state_path:
            return
        with self.mx:
            try:
                blob = {"v": VERSION, "saved_at": int(self.clock()), "followers": {f.id: f.blob() for f in self.followers}}
                os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
                tmp = self.state_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(blob, fh, default=str)
                from .fsutil import replace as _fs_replace
                _fs_replace(tmp, self.state_path)
            except Exception as e:
                self.log("warn", f"fleet state save failed: {e.__class__.__name__}: {e}")

    # ---- views
    def lead_rows(self, now) -> list:
        """The leads' own accounts checked against their firm's rules (read-only warnings; their own guards trade them)."""
        out = []
        b = self.bot
        rows = [("zlarior", "Zlarior", "mffu_builder_50k", None)]
        if getattr(b, "acct_b", None) is not None:
            rows.append(("atlas", "ATLAS", "mffu_builder_25k" if "25" in str(getattr(b.acct_b, "spec", {}).get("plan") or "25") else "mffu_builder_50k", b.acct_b))
        if getattr(b, "acct_c", None) is not None:
            rows.append(("blitz", "BLITZ", "mffu_builder_25k", b.acct_c))
        for key, lab, plan, obj in rows:
            try:
                P = firms.profile(plan, "funded" if getattr(obj, "spec", {}).get("stage") == "funded" else "eval")
                snap = lead_snapshot(b, key) or {}
                op = snap.get("open")
                out.append({"lead": key, "name": lab, "account": snap.get("name"), "plan": (P or {}).get("label"),
                            "open": ({"side": _side(op["dir"]), "qty": op["qty"]} if op else None),
                            "max_micros": firms.max_micros(P or {}),
                            "warn": [w for w in ((P or {}).get("warn") or [])][:2]})
            except Exception:
                continue
        return out

    def rows(self, now=None) -> list:
        now = int(now or self.clock())
        out = []
        for f in self.followers:
            try:
                out.append(f.row(now))
            except Exception as e:
                out.append({"id": f.id, "name": f.name, "error": f"{e.__class__.__name__}: {e}"[:160]})
        return out

    def api(self, now=None) -> dict:
        now = int(now or self.clock())
        rows = self.rows(now)
        return {"v": VERSION, "t": now, "on": True, "kill": self.killed(), "accounts": rows, "leads": self.lead_rows(now),
                "totals": _totals(rows), "notes": self.notes[-20:], "warnings": self.warnings()}

    def warnings(self) -> list:
        """Fleet-level rule warnings: more funded followers of one plan than the firm allows a person (MFFU: 1 Builder 50K,
        2 Builder 25K, verified), and the owner's own leads on the same plan are not counted here (the Start page has them)."""
        out, n = [], {}
        for f in self.followers:
            if f.stage == "funded" and f.problem is None:
                n[f.spec.get("plan")] = n.get(f.spec.get("plan"), 0) + 1
        for plan, k in sorted(n.items()):
            P = firms.profile(plan, "funded") or {}
            mx = _num(P.get("max_active"))
            if mx is not None and k > mx:
                out.append(f"{P.get('label')}: {k} funded followers, the firm allows {int(mx)} per person")
        return out

    def hb_block(self, now=None) -> dict:
        """The heartbeat's compact "fleet" block (< 6 KB)."""
        now = int(now or self.clock())
        acc = []
        rows = self.rows(now)
        for r in rows[:12]:
            if r.get("error"):
                acc.append({"id": r["id"], "error": r["error"][:80]})
                continue
            o = r.get("open")
            acc.append({k: v for k, v in {
                "id": r["id"], "n": str(r["name"])[:30], "lead": r["lead"], "firm": str(r.get("firm") or "")[:24],
                "plan": str(r.get("plan") or "")[:20], "stage": r["stage"], "st": r["status"], "lab": r.get("label"),
                "bal": _r0(r.get("balance")), "room": _r0(r.get("room")), "dl": _r0(r.get("day_left")), "tgt": _r0(r.get("to_target")),
                "day": _r0(r.get("today")), "wk": _r0(r.get("week")), "n_tr": r.get("trades"),
                "pos": (f"{o['side'][0]}{o['qty']}" if o else None), "slip": r.get("slip_ticks"),
                "skip": (str((r.get("last_skip") or {}).get("why") or "")[:90] or None),
                "warn": [str(w)[:90] for w in (r.get("warn") or [])[:2]] or None}.items() if v is not None})
        blk = {"v": VERSION, "t": now, "kill": self.killed(), "n": len(self.followers), "acc": acc, "tot": _totals(rows)}
        s = json.dumps(blk, separators=(",", ":"), default=str)
        while len(s) > 6000 and blk["acc"]:
            blk["acc"] = blk["acc"][:-1]
            blk["cut"] = True
            s = json.dumps(blk, separators=(",", ":"), default=str)
        return blk


def _r0(x):
    v = _num(x)
    return None if v is None else round(v)


def _totals(rows) -> dict:
    ok = [r for r in rows if not r.get("error")]
    return {"accounts": len(rows), "open": sum(1 for r in ok if r.get("open")),
            "today": round(sum(float(r.get("today") or 0) for r in ok), 2),
            "week": round(sum(float(r.get("week") or 0) for r in ok), 2),
            "live": sum(1 for r in ok if r.get("label") in ("LIVE", "REAL")),
            "passed": sum(1 for r in ok if r.get("status") == "passed"), "failed": sum(1 for r in ok if r.get("status") == "failed")}


def _state_path_for(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_fleet" + (ext or ".json")


def build(bot, cfg: dict, **kw):
    """LiveBot: the fleet for this block, or None (no follower: today's bot, untouched)."""
    if not cfg or not cfg.get("accounts"):
        return None
    return Fleet(bot, cfg, **kw).start()


# ---------------------------------------------------------------------------------------------------------------- dry run
class _DryBot:
    """A stand-in lead for --dry-run: LIT's trades of a day replayed as routed rows (paper)."""

    def __init__(self, cfg=None):
        self.cfg = cfg or {"adapter": "paper", "sym": "NQ"}
        self.ledger, self._open_routed, self.state, self.kill = [], None, {}, False
        self.adapter = None
        self.started_at = 0
        self.now = 0
        self.lines = []

    def clock(self):
        return self.now

    def _log(self, kind, text):
        self.lines.append(f"{_et(self.now):%H:%M} {kind}: {text}")


def dry_run(day: str, cfg: dict, trades: list | None = None) -> dict:
    """Replay one day's LIT trades (research/lab/backtest_live.json, else the given list) through the fleet on paper
    adapters: what each follower would have done. Nothing is routed to a broker, no file of the bot is written."""
    import tempfile
    if trades is None:
        trades = []
        try:
            with open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8") as fh:
                bt = json.load(fh)
            for t in bt.get("trades") or []:
                if trading_day(int(t["entry_t"])) == day:
                    trades.append(t)
        except Exception:
            trades = []
    blk = copy.deepcopy(cfg)
    for r in blk.get("accounts") or []:
        r["adapter"] = "paper"
        r["armed"] = False
        if r.get("stage") != "funded" and (not r.get("start") or r["start"] > day):
            r["start"] = day
    bot = _DryBot()
    tmp = tempfile.mkdtemp(prefix="fleet_dry_")
    fl = Fleet(bot, blk, state_path=os.path.join(tmp, "live_state_fleet.json"), parallel=False, sleep=lambda s: None,
               notify=lambda *a: None).start()
    for t in sorted(trades, key=lambda x: int(x["entry_t"])):
        et_ = int(t["entry_t"])
        d = 1 if int(t.get("dir") or (1 if t.get("side") in ("LONG", "buy") else -1)) == 1 else -1
        bot.now = et_
        bot.ledger.append({"t": et_, "sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": int(t.get("qty") or 1),
                           "entry": t.get("entry"), "stop": t.get("stop0", t.get("stop")), "target": t.get("target"), "entry_t": et_,
                           "result": {"ok": True}})
        bot._open_routed = et_
        fl.tick("NQ", et_ + 5)
        xt = int(t.get("exit_t") or et_ + 600)
        bot.now = xt
        bot.ledger.append({"t": xt, "sym": "NQ", "side": "exit", "qty": int(t.get("qty") or 1), "reason": t.get("exit_reason") or t.get("exit"),
                           "pnl": float(t.get("pnl") or 0.0), "entry_t": et_, "exit_t": xt, "result": {"ok": True}})
        bot._open_routed = None
        fl.tick("NQ", xt + 5)
    return {"day": day, "lead_trades": len(trades), "accounts": fl.rows(bot.now or 0), "log": bot.lines[-60:]}


# ---------------------------------------------------------------------------------------------------------------- CLI
# ---------------------------------------------------------------------------------------------------------------- preflight
def preflight(fid: str, path: str | None = None, nt_folder: str | None = None, allow_path: str | None = None,
              bot=None, env=None) -> dict:
    """Before the owner arms / trusts a follower: one line each {key, label, state good | bad | wait | info, detail, fix}
    (as engine/blitz_preflight). Read-only: it never arms, allowlists or writes. {"ok": all good / info, "lines": [...]}."""
    env = os.environ if env is None else env
    d = load_file(path)
    raw = next((r for r in d.get("accounts") or [] if r.get("id") == fid), None)
    L = []

    def line(key, label, state, detail="", fix=""):
        L.append({"key": key, "label": label, "state": state, "detail": str(detail)[:200], "fix": str(fix)[:200]})
    if raw is None:
        line("config", "In the fleet", "bad", f"no follower {fid}", "python -X utf8 -m engine.fleet --add ...")
        return {"ok": False, "id": fid, "lines": L}
    n = normalize(raw)
    P = profile_of(n) or {}
    probs = n["problem"]
    line("config", "Settings complete", "bad" if probs else "good", probs or f"{P.get('label')} {n['stage']} from {n['start'] or n['funded_start']}",
         "fix the entry (python -X utf8 -m engine.fleet --status)" if probs else "")
    nt = n["adapter"] == "ninjatrader"
    real = nt and not is_sim(n["nt_account"])
    if P.get("kind") != "live":
        bad_bot = P.get("bots") in ("prohibited", "semi_only", "api_only") or P.get("ninjatrader") is False
        line("firm_bot", "The firm allows this bot on NinjaTrader", "bad" if bad_bot else ("good" if P.get("verified", {}).get("bots") else "wait"),
             f"{P.get('firm')}: bots {P.get('bots') or 'unknown'}", "paper only at this firm" if bad_bot else
             ("" if P.get("verified", {}).get("bots") else "ask the firm in writing before a real account"))
        line("copy", "Copying between your own accounts allowed", "good" if P.get("copy_trading") in ("allowed", "own_accounts") and
             P.get("verified", {}).get("copy_trading") else "wait", f"{P.get('firm')}: {P.get('copy_trading') or 'not confirmed'}",
             "" if P.get("copy_trading") in ("allowed", "own_accounts") and P.get("verified", {}).get("copy_trading") else
             "ask the firm's support in writing first")
        crit = [k for k in ("dd_amount", "dd_type", "max_micros", "dll", "lock", "target") if P.get(k) is None]
        unver = [k for k in ("dd_amount", "dd_type", "dll", "max_micros") if P.get(k) is not None and not P.get("verified", {}).get(k)]
        line("rules", "The plan's rules are known", "bad" if "dd_amount" in crit else ("wait" if crit or unver else "good"),
             ("unknown: " + ", ".join(crit) if crit else "") + (("; not verified: " + ", ".join(unver)) if unver else "") or "verified",
             "check them on the firm's page (python -X utf8 -m engine.firms --show " + n["plan"] + ")" if crit or unver else "")
    if not nt:
        line("route", "Where it trades", "info", "paper: nothing is sent to a broker")
    else:
        try:
            from .go import nt_names
            names = [r["name"] for r in nt_names(nt_folder)]
        except Exception:
            names = []
        seen = is_sim(n["nt_account"]) or n["nt_account"] in names
        line("visible", "NinjaTrader shows the account", "good" if seen else "wait",
             n["nt_account"] if seen else f"{n['nt_account']} not in NinjaTrader's accounts / positions yet",
             "" if seen else "log the account in NinjaTrader 8 (Accounts tab), then check again")
        if real:
            from .ninjatrader import allowed_accounts, LIVE_ENV
            allow = n["nt_account"] in allowed_accounts(allow_path)
            line("allow", "On the bot's account allowlist", "good" if allow else "bad", n["nt_account"],
                 "" if allow else "python -X utf8 -m engine.fleet --arm " + fid + " (adds it; you only)")
            line("armed", "Armed by you", "good" if n["armed"] else "bad", "armed" if n["armed"] else "not armed",
                 "" if n["armed"] else "python -X utf8 -m engine.fleet --arm " + fid)
            live = str(env.get(LIVE_ENV, "")) == "1"
            line("live", "The bot runs live (phrase typed at its start)", "good" if live else "wait",
                 "NINJATRADER_LIVE=1" if live else "the bot is not running live", "" if live else "start the bot with I ACCEPT LIVE RISK")
        else:
            line("sim", "Sim account (no arming needed)", "info", n["nt_account"])
    if bot is not None:
        lead_on = n["lead"] == "zlarior" or getattr(bot, "acct_b" if n["lead"] == "atlas" else "acct_c", None) is not None
        line("lead", f"{LEAD_NAMES.get(n['lead'])} is running", "good" if lead_on else "wait", "" if lead_on else "nothing to copy yet",
             "" if lead_on else "switch the lead bot on (Start page)")
    ok = all(x["state"] in ("good", "info") for x in L)
    return {"ok": ok, "id": fid, "label": n["label"], "lines": L}


def _status_lines(path) -> list:
    d = load_file(path)
    rows = d.get("accounts") or []
    if not rows:
        return ["Fleet OFF: no follower accounts (data/fleet.json is empty). The bot trades its own accounts only."]
    out = [f"Fleet: {len(rows)} follower account(s)" + ("  ** FLEET KILL ON **" if d.get("kill") else "")]
    ids, names = set(), set()
    for r in rows:
        n = normalize(r, ids, names)
        ids.add(n["id"])
        P = profile_of(n) or {}
        out.append(f"  {n['id']:14s} {n['label']:5s} follows {LEAD_NAMES.get(n['lead'], n['lead']):8s} {P.get('label') or n['plan']:28s} "
                   f"{n['stage']:6s} {n['nt_account'] or '-':16s} from {n['start'] or '?'}"
                   + ("  KILLED" if n["killed"] else "") + (f"  ({n['problem']})" if n["problem"] else ""))
    try:
        sp = _state_path_for(None)
        with open(sp, encoding="utf-8") as fh:
            sv = json.load(fh)
        for fid, b in (sv.get("followers") or {}).items():
            cl = b.get("closes") or []
            out.append(f"  {fid}: {len(cl)} closed copies, ${sum(float(c[2]) for c in cl):+,.2f} booked, "
                       + ("open " + _side((b.get('pos') or {}).get('dir', 1)) if b.get("pos") else "flat"))
    except Exception:
        pass
    return out


def _parser():
    import argparse
    ap = argparse.ArgumentParser(prog="python -X utf8 -m engine.fleet", description="copy trading: the owner's follower accounts (data/fleet.json)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--remove")
    ap.add_argument("--on")
    ap.add_argument("--off")
    ap.add_argument("--kill", help="<id> or all")
    ap.add_argument("--unkill", help="<id> or all")
    ap.add_argument("--arm", help="<id>: a real account trades only with this AND the phrase at the bot's start AND NINJATRADER_LIVE=1")
    ap.add_argument("--disarm")
    ap.add_argument("--to-funded")
    ap.add_argument("--payout", nargs=2, metavar=("ID", "DAY=USD"))
    ap.add_argument("--dry-run", metavar="DAY")
    ap.add_argument("--preflight", metavar="ID", help="read-only checks before you arm / trust a follower")
    ap.add_argument("--id")
    ap.add_argument("--name")
    ap.add_argument("--lead", choices=list(LEADS))
    ap.add_argument("--plan", help="a plan id (python -X utf8 -m engine.firms --list) or live")
    ap.add_argument("--account", help="the account Name in NinjaTrader (Sim101 etc. for a Sim test; omit = paper)")
    ap.add_argument("--start", help="first session (yyyy-mm-dd)")
    ap.add_argument("--balance", type=float, help="start balance (live account; a prop plan defaults to its size)")
    ap.add_argument("--stagger-ms", type=int)
    ap.add_argument("--risk-usd", type=float, help="fixed $ risk a trade (sizing fixed)")
    ap.add_argument("--max-risk", type=float, help="live: max $ risk a trade")
    ap.add_argument("--daily-stop", type=float, help="live: daily stop $")
    ap.add_argument("--weekly-stop", type=float, help="live: weekly stop $")
    ap.add_argument("--max-micros", type=int, help="live: max micros")
    ap.add_argument("--file", default=None)
    return ap


def run(argv=None) -> tuple:
    """The CLI's work without printing: (exit code, lines). Used by main() and the Fleet page (engine/fleet_api.py)."""
    a = _parser().parse_args(argv)
    lines = []
    say = lines.append
    d = load_file(a.file)
    rows = d.setdefault("accounts", [])
    find = lambda i: next((r for r in rows if r.get("id") == i), None)

    def saved(msg):
        save_file(d, a.file)
        say(msg + " The running bot picks it up at its next poll (an open copy keeps its old settings until it is flat).")
        return 0, lines

    def fail(msg):
        say(msg)
        return 1, lines
    if a.preflight:
        pf = preflight(a.preflight, a.file)
        mark = {"good": "OK  ", "bad": "NO  ", "wait": "WAIT", "info": "info"}
        for x in pf["lines"]:
            say(f"  {mark.get(x['state'], x['state'])} {x['label']}: {x['detail']}" + (f"  -> {x['fix']}" if x["fix"] else ""))
        say("ALL GREEN" if pf["ok"] else "NOT READY")
        return (0 if pf["ok"] else 1), lines
    if a.dry_run:
        out = dry_run(a.dry_run, d)
        say(f"Dry run {out['day']}: {out['lead_trades']} lead trade(s) replayed on paper (nothing routed, no bot file written)")
        for r in out["accounts"]:
            say(f"  {r.get('id')}: {r.get('trades')} copies, today ${float(r.get('today') or 0):+,.2f}, status {r.get('status')}"
                + (f", last skip: {r['last_skip']['why']}" if r.get("last_skip") else ""))
        return 0, lines
    if a.add:
        if not a.id or not a.plan:
            return fail("--add needs --id and --plan (and --account for NinjaTrader, --start)")
        if find(a.id):
            return fail(f"{a.id} exists (use --remove first)")
        live = a.plan == "live"
        r = {"id": a.id, "name": a.name or a.id, "lead": a.lead or "zlarior", "plan": a.plan, "stage": "live" if live else "eval",
             "adapter": "ninjatrader" if a.account else "paper", "nt_account": a.account or "", "start": a.start or "",
             "enabled": True, "armed": False, "stagger_ms": a.stagger_ms or 0, "sizing": "fixed" if a.risk_usd else "plan",
             "risk_usd": a.risk_usd, "payouts": {}}
        if live:
            r["live"] = {k: v for k, v in {"start": a.balance, "max_risk_usd": a.max_risk, "daily_stop_usd": a.daily_stop,
                                           "weekly_stop_usd": a.weekly_stop, "max_micros": a.max_micros}.items() if v is not None}
        elif a.balance:
            r["balance"] = a.balance
        n = normalize(r, {x.get("id") for x in rows}, {x.get("nt_account") for x in rows if x.get("nt_account")})
        if n["problem"] and not n["problem"].startswith("switched off"):
            return fail(f"NOT saved: {n['problem']}")
        rows.append(r)
        P = profile_of(n) or {}
        for w in P.get("warn") or []:
            say("  ! " + w)
        return saved(f"saved {a.id}: {n['label']} follows {LEAD_NAMES[n['lead']]} on {P.get('label')} ({n['stage']}), "
                     f"{'NOT armed' if n['label'] in ('REAL', 'LIVE') else 'no arming needed'}.")
    for flag, fn in (("remove", None), ("on", True), ("off", False)):
        i = getattr(a, flag)
        if i:
            r = find(i)
            if r is None:
                return fail(f"no follower {i}")
            if flag == "remove":
                d["accounts"] = [x for x in rows if x.get("id") != i]
                return saved(f"removed {i}.")
            r["enabled"] = fn
            return saved(f"{i} switched {'on' if fn else 'off'}.")
    if a.kill or a.unkill:
        i, v = (a.kill, True) if a.kill else (a.unkill, False)
        if i == "all":
            d["kill"] = v
            return saved(f"fleet kill {'ON: every follower is flattened and stops' if v else 'off'}.")
        r = find(i)
        if r is None:
            return fail(f"no follower {i}")
        r["killed"] = v
        return saved(f"{i} {'KILLED: flattened at the next poll, no new entry' if v else 'un-killed'}.")
    if a.arm or a.disarm:
        i = a.arm or a.disarm
        r = find(i)
        if r is None:
            return fail(f"no follower {i}")
        r["armed"] = bool(a.arm)
        if a.arm and r.get("adapter") == "ninjatrader" and r.get("nt_account") and not is_sim(r.get("nt_account")):
            try:                                   # the owner's own command: the Name joins the account allowlist (as account B / C)
                from .ninjatrader import allow_account
                allow_account(r["nt_account"])
                say(f"{r['nt_account']} is on the account allowlist.")
            except Exception as e:
                say(f"allowlist NOT updated ({e}): python -m engine.ninjatrader --allow \"{r['nt_account']}\"")
        if a.arm:
            say("Armed in the file only. It trades real money only when the bot is started with the typed phrase "
                "(I ACCEPT LIVE RISK) AND NINJATRADER_LIVE=1, and its Name is on NinjaTrader's allowlist.")
        return saved(f"{i} {'armed' if a.arm else 'disarmed'}.")
    if a.to_funded:
        r = find(a.to_funded)
        if r is None or not a.start:
            return fail("--to-funded <id> needs --start <first funded session> (and --account \"<funded Name>\" when it changes)")
        r["eval_account"] = r.get("nt_account")
        if a.account:
            r["nt_account"] = a.account
        r.update(stage="funded", funded_start=a.start, armed=False, payouts={})
        return saved(f"{a.to_funded} is FUNDED from {a.start} (disarmed; arm it again for a real account).")
    if a.payout:
        i, dv = a.payout
        r = find(i)
        day, _, usd = dv.partition("=")
        if r is None or _num(usd) is None:
            return fail("--payout <id> <day>=<$>")
        r.setdefault("payouts", {})[day.strip()] = float(usd)
        return saved(f"payout {day.strip()} ${float(usd):,.2f} recorded on {i}.")
    return 0, _status_lines(a.file)


def main(argv=None) -> int:
    rc, lines = run(argv)
    for ln in lines:
        print(ln)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
