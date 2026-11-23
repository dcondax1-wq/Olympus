"""Several accounts on one PC bot: each LIT signal routed to every enabled account, each account sized from its own state.

The owner's funded plan (research/writeups/lit-funded-firms.md, lit-mffu-rapid-stack.md): the MFFU Builder 50K eval /
funded account + a LucidPro 50K + a FundedNext Rapid Daily 50K (+ maybe an MFFU Rapid EOD 50K), all trading the same
LIT signals. OFF by default: without an "accounts" list in the start cfg the bot is exactly the single-account bot.

How it fits (a router layer, so engine/live.py only calls a few hooks):
  * The PRIMARY account is the bot's own account (start cfg adapter / nt_account / eval_start / lit_sizing), routed by
    LiveBot exactly as before. The router never touches it.
  * Every entry of the start cfg "accounts" list is an EXTRA account with its own adapter (NinjaTrader or paper), its
    own ledger, fills / positions (its own NinjaTrader state file), eval clock, sizing mode and daily-loss lock-out. An
    entry naming the primary's NinjaTrader account is ignored (no double routing).
  * Same entry / stop / target / breakeven / exits as the primary (the model's), separate orders per account; each
    account computes its own micros with engine/sizing.lit_qty from its own day P&L and eval / funded state.
  * LIT scale-in (live_model.json lit.scale_in): ONLY the primary account adds after breakeven. Extra accounts never
    receive an add (no {"side": "add"} is routed to them); they trade the first entry alone with the model's stop /
    target / breakeven / exits, so their P&L on a scaled-in trade is the first entry's only (smaller than the primary's
    and than the backtest's). Routing adds per account (own scale_in_qty on its own state) is open work.
  * Kill switch: every account is flattened (NinjaTrader FLATTENEVERYTHING per adapter, paper exits) and stopped.
  * One account locked out (daily loss, max-loss floor, disabled by its live gate, news ban) never stops the others.
  * Live locks per account: a non-Sim NinjaTrader account trades only with its own "armed": true AND the exact confirm
    phrase given for it at start AND NINJATRADER_LIVE=1 (the adapter's own gate, engine/ninjatrader._live_gate). The
    primary's arming is never inherited.

Account entry (start cfg "accounts", or data/accounts.json which `python -m engine.ninjatrader --start` merges in):
  {"id": "lucid50k", "name": "LucidPro 50K", "nt_account": "<NinjaTrader account Name>", "preset": "lucid_pro_50k",
   "mode": "two_week", "eval_start": "2026-10-21", "eval_prior_pnl": 0, "enabled": true, "armed": false,
   "rules": {"max_micros": 40, "dll": 1200, "trail": "eod", "best_day": null, "news_ban": false},
   "funded": {"payouts": {"2026-12-01": 1000}}, "lit_sizing": {...optional overrides...}}
  mode: two_week | eval | safe_eval | fast_eval | normal | funded | auto (see engine/sizing.lit_qty_core).
  rules (preset values unless given): start, target, mll, lock (relative to start), dll (also the lock-out), max_micros,
  trail eod | intra (approximated at trade closes) | static, best_day (eval: the day's win <= this x target x 0.95),
  news_ban funded | always | false (Tier-1 releases: no entry and flat from 2 min before to 2 min after).

  python -m engine.multi_account --presets             the firm presets
  python -m engine.multi_account --list                data/accounts.json
  python -m engine.multi_account --add --id lucid50k --nt-account "<Name>" --preset lucid_pro_50k --eval-start 2026-10-21
  python -m engine.multi_account --set --id lucid50k --mode funded --funded-start 2026-11-20
  python -m engine.multi_account --disable --id lucid50k   (--enable, --remove)
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_PATH = os.path.join(ROOT, "data", "accounts.json")         # gitignored: the owner's extra accounts (no phrase in it)
MODES = ("two_week", "eval", "safe_eval", "fast_eval", "normal", "funded", "auto")
EVAL_MODES = ("two_week", "eval", "safe_eval", "fast_eval")
ADAPTERS_OK = ("paper", "ninjatrader")
VERSION = 1
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")

# Firm presets (rules searched 2026-10-19, research/writeups/lit-funded-firms.md "The settings for each account").
# rules: $ relative to the start balance; lock = the floor's lock above start - mll (eod trailing, +$100 = $50,100).
# sizing: overrides of live_model.json lit_sizing for this account (engine/sizing.lit_qty).
PRESETS = {
    "mffu_builder_50k": {
        "firm": "MFFU", "plan": "Builder 50K",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40,
                  "trail": "eod", "best_day": None, "news_ban": False},
        "sizing": {"funded": {"pct": 0.6, "pct_min_usd": 100, "pct_max_usd": 1500, "ref": 20, "wk": True, "room_f": None,
                              "max_win": 2000, "slip_ticks": 2, "skip_breach": True}},
        "note": "the owner's eval: two_week for 10 sessions, then safe_eval; funded (owner 2026-10-25, research/writeups/uprisk.md): "
                "60% of the room, <= $1,500, a winner <= $2,000 (one winner = one full payout request)"},
    "mffu_builder_25k": {
        # owner 2026-10-19: the second account (bought next), traded by the same bot next to the Builder 50K eval.
        # Rules from tools/lit_funded_firms.py / engine/sizing.TW_25K (target $1,500, $1,000 EOD trailing locking at +$100,
        # $600 soft daily loss, 20 micros); every value can be overridden per account ("rules": {...}) once confirmed.
        "firm": "MFFU", "plan": "Builder 25K",
        "rules": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20,
                  "scale": 0.5, "trail": "eod", "best_day": None, "news_ban": False, "min_room": 100.0},
        # research/writeups/lit-builder-25k.md (picked on H1 2026): 50% of the room (not 60%), no weekly stop, the day
        # guard on the 25K's own $ limits. 2026-11-17 (research/writeups/builder25k-eval-sizing-2026-11-17.md): 40% of the room to
        # session 80 then safe_eval 60% (= the owner-approved 50K rule): median 12 sessions, 0% 2-week fails; the old 50%/s10/30% left 17-25% stuck
        "sizing": {"two_week": {"base": "need", "need_buf": 1.0, "room_f": 0.4, "wk": False, "dll_cap": True,
                                "stop_at_target": True, "max_usd": None, "press_at": None, "press_mult": 1.0, "press_room": None,
                                "protect_over": None, "protect_keep": 0.0},
                   "guard": {"target": 1500.0, "dll": 600.0, "max_micros": 20},
                   "two_week_until": 80, "after_mode": "safe_eval", "safe_cap": 0.6, "eval_ref_stop": 25.0, "fast_ref_stop": 40.0,
                   "plan": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 25100.0, "dll": 600.0},
                   "funded": {"pct": 0.6, "pct_min_usd": 50, "pct_max_usd": 750, "ref": 20, "wk": True, "room_f": None,
                              "max_win": 1000, "slip_ticks": 2, "skip_breach": True}},
        "note": "MFFU Builder 25K eval: two_week (one winner passes: micros so the target covers what is left to +$1,500, "
                "<= 50% of the room to the $1,000 trailing floor, <= the $600 soft daily loss, max 20) for 10 sessions, then "
                "safe_eval at 30% of the room (lit-builder-25k.md); stops when the room is under $100 (stuck); funded (owner 2026-10-25, uprisk.md): 60% of the room, <= $750, a winner <= $1,000"},
    "lucid_pro_50k": {
        # re-read 2026-11-22 on Lucid's help center, every value cited in research/lit/lucid_rules.json (day-nqdash3, the second
        # firm; OFF: only engine/account_cli --plan lucidpro50k adds one, DISARMED, and START BOT arms it only after the owner
        # recorded Lucid's written OK: account_cli lucid_ok). $3,000 target, $2,000 EOD trailing locking at +$100, $1,200 DLL
        # (DLL ON: a soft pause for the day, never a fail), 40 micros, no eval consistency, news allowed, flat by 16:45 ET (LIT
        # is flat by 15:55), hedging banned across accounts AND firms (the router's opposite_open + engine/hand_hedge), 30-day
        # inactivity ($1 net). Funded: 40% best day of the payout cycle, $500 a cycle, buffer $52,100, $2,000 then $2,500.
        "firm": "Lucid Trading", "plan": "LucidPro 50K (daily loss option on)", "rules_src": "research/lit/lucid_rules.json",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1200.0, "max_micros": 40,
                  "trail": "eod", "best_day": None, "news_ban": False},
        "sizing": {"two_week": {"room_f": 0.4, "max_usd": 1000.0}, "after_mode": "safe_eval", "safe_cap": 0.4,
                   "funded": {"pct": 0.6, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None,
                              "max_win": 1500, "slip_ticks": 2, "skip_breach": True}},
        "note": "eval: one winner passes, <= 40% of the room and $1,000 risk, <= $1,200 soft daily loss; funded: 60% of the "
                "room, <= $800, a winner <= $1,500 (40% payout rule)"},
    "fn_rapid_daily_50k": {
        "firm": "FundedNext Futures", "plan": "Rapid Daily 50K",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40,
                  "trail": "eod", "best_day": None, "news_ban": False},
        "sizing": {"two_week": {"room_f": 0.4, "max_usd": 1000.0}, "after_mode": "safe_eval", "safe_cap": 0.4,
                   "funded": {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None,
                              "max_win": None, "slip_ticks": 2, "skip_breach": True}},
        "note": "eval as Lucid; funded: 40% of the room, <= $800, no winner cap (no consistency rule at payout)"},
    "mffu_rapid_50k": {
        "firm": "MFFU", "plan": "Rapid 50K",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 50,
                  "trail": "eod", "funded_trail": "intra", "best_day": 0.5, "news_ban": "funded"},
        "sizing": {"two_week": {"room_f": 0.4, "max_usd": 600.0}, "after_mode": "safe_eval", "safe_cap": 0.4,
                   "funded": {"pct": 0.6, "pct_min_usd": 100, "pct_max_usd": 1200, "ref": 20, "wk": True, "room_f": None,
                              "max_win": None, "slip_ticks": 2, "skip_breach": True}},
        "note": "HELD (MFFU has not said it may sit next to a Builder 50K). Eval 50% best-day rule; funded intraday trailing "
                "floor, Tier-1 news banned; the firm has no daily loss (dll = the bot's own soft $1,000)"},
    "mffu_rapid_eod_50k": {
        # READY, OFF (owner 2026-11-17: "I'll stick with 1 rapid"): runs only once data/rapid.json names the NinjaTrader
        # account (engine/rapid.py: LIT + ATLAS on this one account, docs/RAPID_EOD_SETUP.md); never armed by the bot.
        # Sizing = research/writeups/stack-one-account-2026-11-16.md / rapid-levers-2026-11-16.md: the eval = LIT's live
        # two_week (live_model.json lit_sizing, no override), funded = the uprisk 50K rule (60% of the room, <= $1,500,
        # a winner <= $2,000); the firm has no daily loss (dll = the bot's own soft $1,000).
        "firm": "MFFU", "plan": "Rapid EOD 50K",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 30,
                  "trail": "eod", "best_day": 0.3, "min_days": 4, "news_ban": "funded"},
        "sizing": {"funded": {"pct": 0.6, "pct_min_usd": 100, "pct_max_usd": 1500, "ref": 20, "wk": True, "room_f": None,
                              "max_win": 2000, "slip_ticks": 2, "skip_breach": True}},
        "note": "Rapid EOD 50K (engine/rapid.py): eval $3,000, $2,000 EOD trailing floor, a day <= 30% of the profit (the bot "
                "keeps a winning day under 30% x $3,000 x 0.95), 4 days; funded: Tier-1 news flat -2/+2 min, daily payouts "
                "above the $2,100 buffer, $500 min, keep $1,000 more in the account"},
    "mffu_rapid_eod_25k": {
        # owner 2026-11-18 (buying it tonight): the Rapid EOD 50K's lanes and rules at the 25K's numbers (engine/rapid.py,
        # research/writeups/rapid-25k-vs-50k-2026-11-17.md, tools/money/rapid25.py "25K, keep $500"): the eval = LIT's live
        # two_week (no override) on $1,500 / $1,000 / 20 micros with the bot's soft $500 day (the firm has none); funded =
        # uprisk UP25 (60% of the room, <= $750, a winner <= $1,000).
        "firm": "MFFU", "plan": "Rapid EOD 25K",
        "rules": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 500.0, "max_micros": 20,
                  "trail": "eod", "best_day": 0.3, "min_days": 4, "news_ban": "funded"},
        "sizing": {"funded": {"pct": 0.6, "pct_min_usd": 50, "pct_max_usd": 750, "ref": 20, "wk": True, "room_f": None,
                              "max_win": 1000, "slip_ticks": 2, "skip_breach": True}},
        "note": "Rapid EOD 25K (engine/rapid.py): eval $1,500, $1,000 EOD trailing floor, a day <= 30% of the profit (the bot "
                "keeps a winning day under 30% x $1,500 x 0.95), 4 days, 2 minis / 20 micros; funded: Tier-1 news flat -2/+2 "
                "min, daily payouts above the $1,100 buffer, $500 min, >= $250 since the last, keep $500 more in the account"},
    "paper_50k": {
        "firm": "Paper", "plan": "50K rules (no broker)",
        "rules": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40,
                  "trail": "eod", "best_day": None, "news_ban": False},
        "sizing": {}, "note": "a paper copy with the MFFU 50K rules"},
}
DEFAULT_PRESET = "mffu_builder_50k"
BEST_DAY_MARGIN = 0.95          # a best-day rule is met with 5% to spare (research: the first winner pays <= 95% of the cap)
# MFFU news policy (help center 2026-11-17): flat AND no working order from 2 min before to 2 min after a Tier-1 release
# (8:30 -> flat by 8:28:00, reopen after 8:32:00). The bot flattens from 3 min before (a market close needs a poll + a
# fill) and re-enters only 2.5 min after (rules audit 2026-11-17; was 120 / 120 = right on MFFU's edge).
NEWS_PRE_S, NEWS_POST_S = 180, 150
# A month whose CPI or jobs report is missing from the calendar (the official file stops at 2026-12; 2027 comes from the
# weekly feed): from this day on, 08:30 ET of every weekday counts as a Tier-1 release (fails CLOSED, a few minutes a day).
T1_FALLBACK_FROM = "2026-11-17"
ADAPTER_FACTORY = None          # tests: (account, adapter cfg) -> adapter (a simulated NinjaTrader); None = engine/live.ADAPTERS


# ---------------------------------------------------------------------------------------------------------------- helpers
def _et(ts):
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(float(ts), ZoneInfo("America/New_York"))


def trading_day(ts) -> str:
    return (_et(ts) + _dt.timedelta(hours=6)).strftime("%Y-%m-%d")      # 18:00 ET opens the next trading day


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _deep(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def is_sim(name) -> bool:
    from .ninjatrader import is_sim as _s
    return _s(name)


def _phrase() -> str:
    from .tradovate import LIVE_PHRASE
    return LIVE_PHRASE


def _tick(px, d=1, target=False):
    from .live import tick_px
    return tick_px(px, d, target=target)


# ---------------------------------------------------------------------------------------------------------------- config
def load_file(path: str = ACCOUNTS_PATH) -> list:
    """data/accounts.json: {"accounts": [...]} (or a bare list). Missing / unreadable -> []."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return []
    except Exception as e:                       # night-faults: still [] (never armed), but said out loud
        from .fault_note import corrupt
        corrupt(path, e, "the added accounts do not trade until it is fixed")
        return []
    rows = d.get("accounts") if isinstance(d, dict) else d
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def save_file(rows: list, path: str = ACCOUNTS_PATH):
    phrase = _phrase()
    clean = [{k: v for k, v in r.items() if k != "confirm" and not (isinstance(v, str) and v.strip() == phrase)} for r in rows]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"v": VERSION, "accounts": clean}, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def rules_of(spec: dict) -> dict:
    pre = PRESETS.get(str(spec.get("preset") or DEFAULT_PRESET)) or PRESETS[DEFAULT_PRESET]
    r = {**pre["rules"], **{k: v for k, v in (spec.get("rules") or {}).items() if v is not None or k in ("best_day", "news_ban")}}
    if spec.get("max_micros") is not None:
        r["max_micros"] = int(spec["max_micros"])
    r["max_micros"] = max(1, int(r.get("max_micros") or 40))
    return r


def normalize(spec: dict, primary: dict | None = None, seen_ids=(), seen_names=()) -> dict:
    """One account entry -> {id, name, ..., "problem": why it cannot trade or None}. Never raises."""
    s = dict(spec or {})
    out = {"id": str(s.get("id") or "").strip(), "name": str(s.get("name") or s.get("id") or "").strip()[:60],
           "preset": str(s.get("preset") or DEFAULT_PRESET), "mode": str(s.get("mode") or "two_week"),
           "adapter": str(s.get("adapter") or (primary or {}).get("adapter") or "paper"),
           "nt_account": str(s.get("nt_account") or "").strip(), "enabled": s.get("enabled", True) is not False,
           "armed": s.get("armed") is True, "confirm": s.get("confirm") or "", "eval_start": str(s.get("eval_start") or ""),
           "eval_prior_pnl": float(_num(s.get("eval_prior_pnl"), 0.0)), "eval_anchor": s.get("eval_anchor"),
           "funded": dict(s.get("funded") or {}),
           "lit_sizing": dict(s.get("lit_sizing") or {}), "problem": None}
    if s.get("lane"):
        out["lane"] = str(s.get("lane"))     # "rapid": LIT's lane of the Rapid EOD (engine/rapid.py: ATLAS shares the account)
    if s.get("slot") == "rapid2" and out.get("lane") == "rapid":
        out["slot"] = "rapid2"               # the 2nd Rapid (engine/rapid.py, data/rapid2.json): its own ATLAS / lifecycle key
    if s.get("lit_bank") is True and out.get("lane") == "rapid":
        out["lit_bank"] = True               # the Rapid 25K's "bank at the room" option (engine/rapid.lit_bank; OFF by default)
    pre = PRESETS.get(out["preset"])
    out["firm"] = str(s.get("firm") or (pre or {}).get("firm") or "")
    out["plan"] = str(s.get("plan") or (pre or {}).get("plan") or "")
    out["kind"] = "funded" if out["mode"] == "funded" else "eval"
    try:
        out["rules"] = rules_of(s)
    except Exception as e:
        out["rules"] = dict(PRESETS[DEFAULT_PRESET]["rules"])
        out["problem"] = f"rules invalid ({e.__class__.__name__})"
    if not _ID.match(out["id"]):
        out["problem"] = "id missing or invalid (letters, digits, - and _ only)"
    elif out["id"] in seen_ids:
        out["problem"] = f"id {out['id']} used twice"
    elif pre is None:
        out["problem"] = f"unknown preset {out['preset']} (python -m engine.multi_account --presets)"
    elif out["mode"] not in MODES:
        out["problem"] = f"unknown mode {out['mode']}"
    elif out["adapter"] not in ADAPTERS_OK:
        out["problem"] = f"adapter {out['adapter']} cannot route several accounts (ninjatrader or paper only)"
    elif out["adapter"] == "ninjatrader":
        nm = out["nt_account"]
        if not nm or any(c in nm for c in ";\r\n|"):
            out["problem"] = "nt_account missing or invalid"
        elif primary and primary.get("adapter") == "ninjatrader" and nm == primary.get("nt_account"):
            out["problem"] = f"{nm} is the bot's own account (routed once, by the bot itself)"
        elif nm in seen_names:
            out["problem"] = f"NinjaTrader account {nm} listed twice"
    if not out["enabled"] and not out["problem"]:
        out["problem"] = "disabled in the config"
    if not out["name"]:
        out["name"] = out["id"] or "account"
    return out


def specs_from_cfg(cfg: dict) -> list:
    """The start cfg's "accounts" list normalized (the primary = the cfg itself)."""
    from .ninjatrader import resolve_account
    rows = (cfg or {}).get("accounts")
    if not isinstance(rows, list) or not rows:
        return []
    prim = {"adapter": cfg.get("adapter", "paper"),
            "nt_account": resolve_account(cfg) if cfg.get("adapter") == "ninjatrader" else None}
    out, ids, names = [], set(), set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        n = normalize(r, prim, ids, names)
        ids.add(n["id"])
        if n["adapter"] == "ninjatrader" and n["nt_account"]:
            names.add(n["nt_account"])
        out.append(n)
    return out


def sizing_cfg(base: dict | None, spec: dict) -> dict:
    """live_model.json lit_sizing -> this account's: the preset's overrides, the entry's own, its mode and its plan."""
    pre = PRESETS.get(spec.get("preset")) or PRESETS[DEFAULT_PRESET]
    c = _deep(_deep(base or {}, pre.get("sizing") or {}), spec.get("lit_sizing") or {})
    R = spec["rules"]
    c["mode"] = spec["mode"]
    c["eval_start"] = spec.get("eval_start") or ""
    tw = c.setdefault("two_week", {})
    tw["acct"] = {**(tw.get("acct") or {}), "target": float(R["target"]), "mll": float(R["mll"]), "lock": float(R["lock"]),
                  "dll": float(R["dll"]), "max_micros": int(R["max_micros"]), "scale": float(R.get("scale", 1.0))}
    c["acct"] = {**(c.get("acct") or {}), "dll": float(R["dll"]), "mll": float(R["mll"]), "lock": float(R["lock"]),
                 "max_micros": int(R["max_micros"])}       # funded: preset $ values are absolute (no scale: it would halve the dll)
    if c.get("guard") is not None:
        c["guard"] = {**(c.get("guard") or {}), "dll": float(R["dll"]), "target": float(R["target"]), "max_micros": int(R["max_micros"])}
    return c


# ---------------------------------------------------------------------------------------------------------------- state
def _plan(rules: dict, funded: bool = False) -> dict:
    trail = (rules.get("funded_trail") or rules.get("trail")) if funded else rules.get("trail")
    lock = float(rules["lock"])
    if trail == "static":
        lock = -float(rules["mll"])                  # the floor never trails: locked where it starts
    return {"target": float(rules["target"]), "mll": float(rules["mll"]), "lock": lock, "dll": float(rules["dll"])}


def sizing_state(mode: str, closes: list, today: str, start: str | None, rules: dict, prior: float = 0.0,
                 payouts: dict | None = None, session: int | None = None, n_today: int = 0, anchor: dict | None = None) -> dict | None:
    """The sizer's state for one account from its routed closes [(day, exit_t, pnl)] since `start` (+ the prior P&L):
      two_week / eval / safe_eval / fast_eval  engine/sizing.eval_state (profit, cum, room, session, days_traded)
      funded                                   engine/sizing.funded_state (balance, room, floor, locked) with the payouts
      auto                                     eval_state + days_traded + "funded": funded_state
    trail "intra": the floor moves after every closed trade (keys day#exit_t), not only at the day's end. None when the
    start is unknown in an eval mode (the sizer then falls back as for the primary). anchor = the broker's balance + floor
    on a day (engine/sizing.anchor_days, eval modes only; prior is then ignored); None = as before."""
    from . import sizing as sz
    rows = sorted((str(d), int(t or 0), float(p or 0.0)) for d, t, p in closes if not start or str(d) >= str(start))
    funded = mode == "funded"
    trail = (rules.get("funded_trail") or rules.get("trail")) if funded else rules.get("trail")
    prev, cum = {}, 0.0
    for d, t, p in rows:
        if d == today:
            cum += p
            continue
        k = f"{d}#{t:012d}" if trail == "intra" else d
        prev[k] = round(prev.get(k, 0.0) + p, 2)
    if prior:
        prev["0000-00-00"] = float(prior)
    if funded:
        st = sz.funded_state(prev, cum, payouts or {}, plan=_plan(rules, True))
        try:                             # the payout cycle (sizing funded "cons_aware", engine/funded_life.py): extra keys only
            from . import funded_life as FL
            st.update(sz.funded_cycle(prev, cum, payouts or {}, plan={**_plan(rules, True), **FL.payout_rules(rules)}))
        except Exception:
            pass
        return st
    if not start and mode in EVAL_MODES + ("auto",):
        return None
    sess = session if session is not None else max(1, sz.eval_session(start, today) or 1)
    a = sz.eval_anchor(anchor)
    if a is not None:                    # the broker's balance + floor on a day (engine/sizing.anchor_days): eval book from there
        ev_prev, ex = sz.anchor_days(prev, a, float(rules.get("start") or 50000.0))
        cum_a = cum if today > a["as_of"] else 0.0
        st = sz.eval_state(ev_prev, cum_a, plan={**_plan(rules), **ex}, session=sess, today=today)
        st["anchor"] = a
    else:
        st = sz.eval_state(prev, cum, plan=_plan(rules), session=sess, today=today)    # today: wk_pnl (wk_loss_usd)
    st["n_today"] = int(n_today)
    st["days_traded"] = len({d for d, _, p in rows if d < today and abs(p) > 1e-9})
    if mode == "auto":
        st["funded"] = sz.funded_state(prev, cum, payouts or {}, plan=_plan(rules, True))
    return st


def primary_state(bot, mode: str):
    """funded / auto state of the bot's own account (LiveBot._equity_qty): its routed P&L per day since eval_start (the
    funded start when the account is funded) + the payouts in the start cfg "funded": {"payouts": {day: $}} or
    lit_sizing.funded_state.payouts. Rules: the start cfg "preset" + "rules" (default the MFFU Builder 50K)."""
    days = dict(bot.eval_days())
    today = trading_day(bot.clock())
    prior = float(days.pop("0000-00-00", 0.0) or 0.0)
    closes = [(d, 0, v) for d, v in days.items()]
    ls = getattr(bot, "_lit_sizing", None) or {}
    payouts = ((bot.cfg.get("funded") or {}).get("payouts") or (ls.get("funded_state") or {}).get("payouts") or {})
    rules = rules_of({"preset": bot.cfg.get("preset") or DEFAULT_PRESET, "rules": bot.cfg.get("rules") or {}})
    anc = None
    if callable(getattr(bot, "eval_anchor", None)):
        try:
            anc = bot.eval_anchor()
        except Exception:
            anc = None
    return sizing_state(mode, closes, today, bot.eval_start() or None, rules, prior=prior, payouts=payouts, anchor=anc)


_NEWS = {"key": None, "rel": {}, "cpi": set(), "nfp": set()}


def _is_jobs(ev: str) -> bool:
    """The US jobs report: the official file's "Non-Farm Payrolls", the weekly feed's "Non-Farm Employment Change" (not ADP's),
    MFFU's "U.S. Employment Report"."""
    return ("Non-Farm Payrolls" in ev or ("Non-Farm Employment Change" in ev and "ADP" not in ev)
            or "Employment Report" in ev or "Employment Situation" in ev)


def tier1_releases(day: str) -> list:
    """Unix times of the Tier-1 releases (CPI, Non-Farm Payrolls, FOMC, FOMC minutes) on trading day `day`, from the
    news calendar files (engine/news.historical_events: data/news/events.csv + the live feed's archive). Never raises."""
    try:
        from . import news
        evs = news.historical_events(("high",))
        key = (len(evs), evs[-1]["t"] if evs else 0)
        if _NEWS["key"] != key:
            rel, cpi, nfp = {}, set(), set()
            for e in evs:
                ev = str(e.get("event") or "")
                is_cpi, is_nfp = "CPI" in ev and "PPI" not in ev, _is_jobs(ev)
                if is_cpi or is_nfp or ev.startswith("FOMC") or "minutes" in ev.lower():
                    rel.setdefault(str(e["date"]), set()).add(int(e["t"]))
                if is_cpi:
                    cpi.add(str(e["date"])[:7])
                if is_nfp:
                    nfp.add(str(e["date"])[:7])
            _NEWS.update(key=key, rel=rel, cpi=cpi, nfp=nfp)
        out = set(_NEWS["rel"].get(day, ()))
        if str(day) >= T1_FALLBACK_FROM and (str(day)[:7] not in _NEWS["cpi"] or str(day)[:7] not in _NEWS["nfp"]):
            out |= _fallback_830(day)
        return sorted(out)
    except Exception:
        return sorted(_fallback_830(day)) if str(day) >= T1_FALLBACK_FROM else []


def _fallback_830(day: str) -> set:
    """08:30 ET of a weekday (the CPI / jobs report time) when that month's release is not in the calendar."""
    try:
        d = _dt.date.fromisoformat(str(day)[:10])
        if d.weekday() >= 5:
            return set()
        from zoneinfo import ZoneInfo
        return {int(_dt.datetime(d.year, d.month, d.day, 8, 30, tzinfo=ZoneInfo("America/New_York")).timestamp())}
    except Exception:
        return set()


# ---------------------------------------------------------------------------------------------------------------- account
class Account:
    """One extra account: its adapter, today's ledger, its routed closes (all days), position, lock-out."""

    def __init__(self, spec: dict, router):
        self.spec = spec
        self.router = router
        self.id, self.name = spec["id"], spec["name"]
        self.rules = spec["rules"]
        self.mode = spec["mode"]
        self.adapter = None
        self.problem = spec.get("problem")
        self.ledger: list = []
        self.closes: list = []                 # [day, exit_t, pnl, entry_t] of every routed exit since the account started
        self.seen: set = set()
        self.open_t = None
        self.open_qty = None
        self.blocked: set = set()
        self.flattened: set = set()
        self.provisional: dict = {}
        self.lock = None                       # {"day", "reason", "t"}: no new entry today
        self.gaveup: set = set()
        self.last_size = None                  # the last entry's sizing {"qty", "reasons"}
        self.hedge_wait: set = set()           # LIT entry_t that waited for ATLAS / BLITZ on another account to close (logged once)
        self.bank: dict = {}                   # entry_t -> engine/rapid.lit_bank (the Rapid 25K option; empty when OFF)
        self.mx = threading.RLock()
        try:                                   # when this account joined the running bot (an account added while it runs):
            self.added_t = int(router.clock())  # a model trade that ENDED before that is none of its business (night-nqlive)
        except Exception:
            self.added_t = 0

    # ---- plumbing
    @property
    def enabled(self) -> bool:
        return self.problem is None and self.adapter is not None

    def log(self, kind, text):
        self.router.log(kind, f"[{self.name}] {text}")

    def disabled_reason(self):
        if self.problem:
            return self.problem
        if self.adapter is None:
            return "adapter not created"
        return getattr(self.adapter, "disabled", None)

    def label(self) -> str:
        ad = self.spec["adapter"]
        if ad == "paper":
            return "PAPER"
        return "SIM" if is_sim(self.spec.get("nt_account")) else "LIVE"

    def route(self, action: dict) -> dict:
        try:
            ka = self._keepalive_yield(action)             # an open keep-alive on this account / the other way closes first
            res = {"ok": False, "error": "REFUSED: " + ka} if ka else \
                self.adapter.send(action) if self.adapter is not None else {"ok": False, "error": "no adapter"}
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        with self.mx:
            self.ledger.append({"t": int(self.router.clock()), **action, "result": res})
        self.log("order", f"{action['side'].upper()} {action.get('qty', '')} {action['sym']} -> {res.get('ok')}"
                 + (f" ({res.get('error')})" if res.get("ok") is False and res.get("error") else ""))
        self._life_routed(action, res)
        self.router.save()
        return res

    def _keepalive_yield(self, action):
        """engine/keepalive.before_entry (OFF by default = None at once): a keep-alive trade open on this NinjaTrader account
        (any side) or the other way on any account is closed at market before this entry goes out. Never raises."""
        if action.get("side") not in ("buy", "sell"):
            return None
        try:
            from . import keepalive as _ka
            return _ka.before_entry(getattr(self.router, "bot", None), 1 if action.get("side") == "buy" else -1, self)
        except Exception:
            return None

    # ---- MFFU lifecycle (engine/lifecycle.py): passed / failed / locked = stand down, the other accounts keep trading
    def life_key(self) -> str:
        from . import lifecycle
        return lifecycle.key_of(self)

    def _life_routed(self, action, res):
        try:
            from . import lifecycle
            k = self.life_key()
            ev = lifecycle.after_route(getattr(self.router, "bot", None), k, lifecycle.label_of(k, self), self.adapter, action, res,
                                       acct=self.spec.get("nt_account") or self.id)
            if ev:
                self.log("risk", f"{ev['title']}: {ev['body']}")
        except Exception:
            pass

    # ---- P&L / eval
    def start_day(self) -> str:
        f = self.spec.get("funded") or {}
        return str((f.get("start") if self.mode == "funded" else None) or self.spec.get("eval_start") or "")

    def shared(self):
        """The other strategy on this SAME account (engine/rapid.RapidAtlas: ATLAS on the Rapid EOD; engine/lit25.SharedAtlas:
        ATLAS on its funded 25K), or None."""
        if self.spec.get("lane") == "lit25":
            ab = getattr(getattr(self.router, "bot", None), "acct_b", None)
            return ab if getattr(ab, "shared_lane", None) == "lit25" and getattr(ab, "name", None) == self.spec.get("nt_account") else None
        if self.spec.get("lane") != "rapid":
            return None
        bot = getattr(self.router, "bot", None)          # the 2nd Rapid's lane ("slot": "rapid2") shares only its own ATLAS
        return getattr(bot, "acct_r2" if self.spec.get("slot") == "rapid2" else "acct_r", None)

    def _shared_holds(self) -> str | None:
        """Why the other strategy on this SAME account holds it now (a position, or a NinjaTrader bracket still open / pending /
        closing), else None. Unknown = held (a CLOSEPOSITION that may close the other bot's trade is never sent on a guess)."""
        try:
            sh = self.shared()
            if sh is None:
                return None
            nm = getattr(sh, "label", None) or "the other strategy on this account"
            if getattr(sh, "open_t", None) is not None:
                return f"{nm} holds a position here"
            from .ninjatrader import OPEN_STATUSES
            for lg in list(getattr(getattr(sh, "adapter", None), "legs", None) or []):
                if isinstance(lg, dict) and lg.get("status") in OPEN_STATUSES:
                    return f"{nm}'s NinjaTrader bracket is {lg.get('status')}"
            return None
        except Exception as e:  # noqa: BLE001
            return f"the other strategy's state is unknown ({e.__class__.__name__})"

    def all_closes(self) -> list:
        """This account's closes + the shared strategy's (one balance, one floor, one day P&L)."""
        sh = self.shared()
        return list(self.closes) + [list(c) for c in (getattr(sh, "closes", None) or [])]

    def day_pnl(self, day: str) -> float:
        return round(sum(float(p) for d, _, p, *_ in self.all_closes() if d == day), 2)

    def eval_days(self) -> dict:
        start = self.start_day()
        days = {}
        for d, _, p, *_ in self.all_closes():
            if not start or d >= start:
                days[d] = round(days.get(d, 0.0) + float(p), 2)
        if self.spec.get("eval_prior_pnl"):
            days["0000-00-00"] = float(self.spec["eval_prior_pnl"])
        return days

    def entries_today(self, today) -> int:
        return sum(1 for r in self.ledger if r.get("side") in ("buy", "sell") and trading_day(r["t"]) == today
                   and (r.get("result") or {}).get("ok") is not False)

    def anchor(self):
        """This account's eval anchor (engine/sizing.eval_anchor): data/eval_anchor.json "accounts" by its NinjaTrader Name
        (or id) next to the bot's state file (`python -m engine.eval_life --anchor --account "<Name>"`), or the spec's
        "eval_anchor"; the newest as_of wins. None = no anchor (as before)."""
        from . import eval_life as EL
        from . import sizing as sz
        f = None
        try:
            sp = getattr(getattr(self.router, "bot", None), "state_path", None)
            for nm in (self.spec.get("nt_account"), self.name, self.id):
                if nm and f is None:
                    f = EL.load_anchor(nm, state_path=sp, main=False)
        except Exception:
            f = None
        return sz.newest_anchor(f, self.spec.get("eval_anchor"), self._broker_anchor())

    # ---- real balance from NinjaTrader (engine/broker_balance.py): this account's own accounts.csv row, eval modes only
    def _broker_name(self):
        return (self.spec.get("nt_account") or self.name) if self.spec.get("adapter") == "ninjatrader" else None

    def _broker(self):
        if self.mode not in EVAL_MODES or not self.start_day() or not self._broker_name():
            return None
        from . import broker_balance as BB
        return BB.for_bot(getattr(self.router, "bot", None))

    def _broker_anchor(self):
        try:
            b = self._broker()
            return b.anchor(self._broker_name(), self.start_day() or None) if b else None
        except Exception:
            return None

    def state(self, today: str, mode: str | None = None, raw: bool = False):
        st = sizing_state(mode or self.mode, [(d, t, p) for d, t, p, *_ in self.all_closes()], today, self.start_day() or None,
                          self.rules, prior=float(self.spec.get("eval_prior_pnl") or 0.0),
                          payouts=(self.spec.get("funded") or {}).get("payouts"), n_today=self.entries_today(today),
                          anchor=self.anchor())
        if raw or (mode or self.mode) not in EVAL_MODES or st is None:
            return st
        try:
            b = self._broker()
            if b is not None:                # min(ledger room, real room of this account)
                st = b.cap_state(st, self._broker_name(), self.rules)
        except Exception:
            pass
        return st

    def broker_tick(self, now):
        """Day-close auto-anchor + one "balance differs" push a day for this account. Never raises."""
        try:
            b = self._broker()
            if b is None:
                return
            start = float(self.rules["start"])
            today = trading_day(now)

            def book_floor():
                st = self.state(today, raw=True)
                return start + float(st["profit"]) + float(st["cum"]) - float(st["room"])
            a = b.observe(self._broker_name(), self.start_day(), self.rules, book_floor=book_floor, now=int(now))
            if a:
                self.log("risk", f"real balance from NinjaTrader at the {a['as_of']} close: ${a['balance']:,.2f}, floor ${a['floor']:,.2f}")
            st = self.state(today, raw=True)
            if st is None:
                return
            d = b.drift(self._broker_name(), start + float(st["profit"]) + float(st["cum"]), self.rules, now=int(now))
            if d:
                self.log("risk", f"balance differs: NinjaTrader ${d['real']:,.2f}, ledger ${d['ledger']:,.2f}")
                self.router.notify(f"{self.name} balance differs",
                                   f"NinjaTrader ${d['real']:,.2f}, bot ledger ${d['ledger']:,.2f} (difference ${d['diff']:+,.2f})",
                                   f"baldiff:{self._broker_name()}:{d['day']}")
        except Exception as e:
            self.log("error", f"real balance check failed: {e.__class__.__name__}: {e}")

    def price_limit_block(self, now) -> str | None:
        """MFFU's 2% price-limit rule (engine/price_limit.py): FUNDED accounts only (sim funded + live). None = may trade."""
        if self.mode != "funded":
            return None
        try:
            from . import price_limit as _pl
            return _pl.blocked(now)
        except Exception:
            return None

    def news_on(self) -> bool:
        nb = self.rules.get("news_ban")
        return nb in (True, "always") or (nb == "funded" and self.mode == "funded")

    def in_news(self, now, pre=NEWS_PRE_S, post=NEWS_POST_S):
        if not self.news_on():
            return None
        for r in tier1_releases(trading_day(now)):
            if r - pre <= now < r + post:
                return r
        return None

    def entry_block(self, now) -> str | None:
        """Why this account takes no new entry now (None = it may)."""
        if self.router.killed():
            return "kill switch"
        dis = self.disabled_reason()
        if dis:
            return f"disabled: {dis}"
        try:                              # engine/lifecycle.py: passed / failed / locked by MFFU / MFFU flat time
            from . import lifecycle
            lb = lifecycle.block(getattr(self.router, "bot", None), self.life_key(), now)
            if lb:
                return lb
        except Exception:
            pass
        today = trading_day(now)
        if self.lock and self.lock.get("day") == today:
            return f"locked out today: {self.lock['reason']}"
        r = self.in_news(now)
        if r is not None:
            return f"news ban: Tier-1 release at {_et(r):%H:%M} ET"
        pl = self.price_limit_block(now)
        if pl:
            return pl
        try:                              # 2026-10-29: CME holidays (engine/cme_calendar.py), like LIT's / ATLAS's calendar guard
            from . import cme_calendar as _cc
            if _cc.full_closure(today):
                return f"CME holiday ({today}: no session)"
            e_ = _et(now)
            m_ = e_.hour * 60 + e_.minute
            if _cc.early_close(today) is not None and m_ < 1080 and m_ >= _cc.entry_cut(today, 955):
                return f"CME early close today (no entry after {_cc.entry_cut(today) // 60:02d}:{_cc.entry_cut(today) % 60:02d} ET)"
        except Exception:
            pass
        if self.mode in EVAL_MODES + ("funded", "auto"):
            st = None
            try:
                st = self.state(today)
            except Exception:
                st = None
            room = _num((st or {}).get("room"))
            if room is not None and room <= 0:
                self.lock = {"day": today, "reason": "max-loss floor reached (account failed)", "t": int(now)}
                return f"locked out today: {self.lock['reason']}"
            min_room = _num(self.rules.get("min_room"), 100.0)
            if room is not None and min_room and room < min_room:
                # "stuck" (lit-builder-25k.md): 1 micro on a LIT stop would breach the floor, so this account sits out
                self.lock = {"day": today, "reason": f"stuck: room ${room:,.0f} < ${min_room:,.0f}", "t": int(now)}
                self.log("risk", f"STUCK: room ${room:,.0f} to the max-loss floor is under ${min_room:,.0f}: no new entry on this "
                                 "account; buy a new one")
                self.router.notify(f"{self.name} stuck: room ${room:,.0f}, buy a new one",
                                   f"the room to the max-loss floor is under ${min_room:,.0f}: the bot no longer trades this account",
                                   f"acct:{self.id}:stuck:{today}")
                return f"locked out: {self.lock['reason']}"
        if self.entries_today(today) >= 1:
            return "already traded today (1 trade a day)"
        return None

    def check_lock(self, now):
        today = trading_day(now)
        pnl = self.day_pnl(today)
        lim = _num(self.rules.get("dll_lock", self.rules.get("dll")))
        if lim and pnl <= -abs(lim) and not (self.lock and self.lock.get("day") == today):
            self.lock = {"day": today, "reason": f"daily loss ${pnl:,.0f} (limit ${abs(lim):,.0f})", "t": int(now)}
            self.log("risk", f"DAILY LOSS LOCK-OUT: {self.lock['reason']}: no new entry on this account today; the other "
                             "accounts keep trading")
            self.router.notify(f"{self.name}: locked out today", self.lock["reason"], f"acct:{self.id}:lock:{today}")

    # ---- sizing
    def qty_for(self, ent: dict, now) -> int:
        from . import sizing as sz
        today = trading_day(now)
        lsz = sizing_cfg(self.router.base_sizing(), self.spec)
        mode = self.mode
        R = self.rules
        try:
            st = self.state(today)
            if st is None and mode in EVAL_MODES + ("funded", "auto"):
                # pre-launch audit A4 (2026-10-25): no eval / funded state (eval_start missing) = the room to the max-loss
                # floor is unknown -> not traded (was: eval-mode fallback with no room cap); as engine/account_b.qty
                self.last_size = {"qty": 0, "model_qty": int(ent["qty"]), "mode": mode,
                                  "reasons": [f"{mode}: account state unknown (eval_start missing?): not traded"]}
                self.log("risk", f"entry NOT traded: {mode} account state unknown (eval_start missing?): the room caps can not be applied")
                return 0
            room = _num((st or {}).get("room")) if mode in EVAL_MODES and st is not None else None
            if mode == "funded":
                room = _num((st or {}).get("room"))
            # every eval mode gets its state (2026-10-20): the pass / fail lock (sizing.eval_lock) and the weekly loss stop
            r = sz.lit_qty(int(ent["qty"]), ent, lsz, room=room, state=st if mode in EVAL_MODES + ("funded", "auto") else None,
                           max_micros=int(R["max_micros"]))
        except Exception as e:
            if mode in EVAL_MODES + ("funded", "auto"):
                self.log("risk", f"entry NOT traded: the {mode} sizing failed ({e.__class__.__name__}: {e})")
                return 0
            r = {"qty": min(int(ent["qty"]), int(R["max_micros"])), "reasons": [f"sizing failed: {e.__class__.__name__}"]}
        q = int(r.get("qty") or 0)
        reasons = list(r.get("reasons") or [])
        bd = _num(R.get("best_day"))
        if q > 0 and bd and mode in EVAL_MODES:
            tgt = _num(ent.get("tgt_pts"))
            if tgt is None and ent.get("entry") is not None and ent.get("target") is not None:
                tgt = abs(float(ent["target"]) - float(ent["entry"]))
            if tgt and tgt * sz.TW_PV - sz.TW_COMM > 0:
                cap_usd = bd * float(R["target"]) * BEST_DAY_MARGIN - max(0.0, self.day_pnl(today))
                cap = max(0, int(cap_usd / (tgt * sz.TW_PV - sz.TW_COMM)))     # < 1 -> skip (2026-10-24 cap invariant)
                self.bank.pop(int(ent.get("entry_t") or 0), None)
                bank = self._bank_for(ent, cap_usd) if cap < 1 and self.spec.get("lit_bank") else None
                if bank is not None:
                    q = 1
                    self.bank[int(ent["entry_t"])] = bank
                    reasons.append(f"best-day rule {bd * 100:.0f}%: 1 micro banked at the day's room ${cap_usd:,.0f} "
                                   f"(exit {bank['px']:,.2f}, +{bank['pts']:g} pts)")
                elif cap < 1:
                    q = 0
                    reasons.append(f"skip: best-day rule {bd * 100:.0f}%: 1 micro's winner pays more than ${cap_usd:,.0f}: no trade")
                elif cap < q:
                    q = cap
                    reasons.append(f"best-day rule {bd * 100:.0f}%: a winner pays <= ${cap_usd:,.0f} -> {q}")
        risk = _num(ent.get("risk_pts"))
        if risk is None and ent.get("entry") is not None and ent.get("stop0", ent.get("stop")) is not None:
            risk = abs(float(ent["entry"]) - float(ent.get("stop0", ent.get("stop"))))
        if q > 0 and risk:
            # every mode, every account: a full stop-out (2 ticks of slippage + commission) stays inside this account's own
            # daily loss left today, and inside rules.max_risk_usd when set (a 25K's $ limits are not the 50K's)
            loss1 = (risk + sz.TW_DLL_SLIP) * sz.TW_PV + sz.TW_COMM
            for lim, lab in ((float(R["dll"]) + min(0.0, self.day_pnl(today)), f"${float(R['dll']):,.0f} daily loss"),
                             (_num(R.get("max_risk_usd")), "max risk a trade")):
                if lim is None:
                    continue
                cap = sz.fit_micros(q, lim, loss1)          # a ceiling: < 1 micro -> skip, never 1 (2026-10-24)
                if cap < 1:
                    q = 0
                    reasons.append(f"skip: 1 micro's stop-out ${loss1:,.0f} does not fit the {lab} ${lim:,.0f}: no trade")
                    break
                if cap < q:
                    q = cap
                    reasons.append(f"{lab} ${lim:,.0f} -> {q}")
        q = min(q, int(R["max_micros"]))
        self.last_size ={"qty": q, "model_qty": int(ent["qty"]), "mode": mode, "reasons": [str(x)[:120] for x in reasons][:8]}
        if q != int(ent["qty"]):
            self.log("risk", f"entry at {_et(ent['entry_t']):%H:%M} ET at {q} instead of {int(ent['qty'])}: "
                             + ("; ".join(reasons[-3:]) or mode))
        return q

    def _bank_for(self, ent: dict, cap_usd: float):
        """The Rapid 25K option (engine/rapid.lit_bank): 1 micro, exit limit at the day's best-day room; eval only."""
        try:
            from . import rapid as _rp
            from . import sizing as sz
            if self.spec.get("lane") != "rapid" or self.mode not in EVAL_MODES or ent.get("entry") is None:
                return None
            risk = _num(ent.get("risk_pts"))
            if risk is None and ent.get("stop0", ent.get("stop")) is not None:
                risk = abs(float(ent["entry"]) - float(ent.get("stop0", ent.get("stop"))))
            tgt = _num(ent.get("tgt_pts"))
            if tgt is None and ent.get("target") is not None:
                tgt = abs(float(ent["target"]) - float(ent["entry"]))
            return _rp.lit_bank(ent["entry"], 1 if ent["dir"] == 1 else -1, risk, tgt, cap_usd, comm=sz.TW_COMM)
        except Exception as e:
            self.log("error", f"bank-at-the-room check failed: {e.__class__.__name__}: {e} (no bank: the guard skips)")
            return None

    # ---- one poll (the same rules as LiveBot._route_signals, for this account)
    def broker_stop(self, entry_t):
        stop = None
        for r in self.ledger:
            if r.get("entry_t") != entry_t:
                continue
            if r.get("side") in ("buy", "sell"):
                stop = r.get("stop")
            elif r.get("side") == "modify" and (r.get("result") or {}).get("ok"):
                stop = r.get("stop")
        return stop

    def _drop_unplaced(self, now):
        """The Rapid's LIT lane (review 2026-11-17): an entry NinjaTrader refused ("Limit 0", max order quantity...) that
        provably never became a position (engine/ninjatrader.entry_never_placed, as ATLAS / LIT use it) is not a trade:
        flat, no exit routed and no P&L booked on the shared book (the model's trade still runs on Zlarior)."""
        if self.spec.get("lane") != "rapid" or self.open_t is None:
            return
        try:
            et_ = int(self.open_t)
            r = next((r for r in reversed(self.ledger) if r.get("side") in ("buy", "sell") and r.get("entry_t") == et_), None)
            res = (r or {}).get("result")
            from .ninjatrader import entry_never_placed
            if not entry_never_placed(self.adapter, et_, res, now=now):
                return
            self.open_t, self.open_qty = None, None
            self.blocked.add(et_)
            self.provisional.pop(et_, None)
            with self.mx:
                self.closes = [c for c in self.closes if not (len(c) > 3 and int(c[3]) == et_)]
            self.log("risk", f"entry at {_et(et_):%H:%M} ET was NOT PLACED on {self.spec.get('nt_account')}: "
                             f"{str((res or {}).get('error') or 'no OK from NinjaTrader')[:160]}. Nothing open on this account; "
                             "no P&L booked for it")
            self.router.save()
        except Exception as e:
            self.log("error", f"not-placed check failed: {e.__class__.__name__}: {e}")

    def _mark_pnl(self, pos, st):
        """$ of this account's open position closed at market now (the bot's last price, 1 tick of slippage, commission);
        None = unknown. A NEWS FLAT / TIME SAFETY close is booked at this, not $0 (review 2026-11-17: a $0 booking overstated
        the room on a funded account with the news ban)."""
        try:
            if not pos or pos.get("entry_t") != self.open_t or not self.open_qty:
                return None
            px = _num((st or {}).get("price"))
            if px is None or pos.get("entry") is None:
                return None
            from . import lit as _lit
            from .sizing import LIVE_COMM
            d = 1 if int(pos.get("dir") or 1) == 1 else -1
            return round(int(self.open_qty) * ((d * (float(px) - float(pos["entry"])) - 0.25) * _lit.PV - float(LIVE_COMM)), 2)
        except Exception:
            return None

    def _flatten(self, sym, reason, entry_t, pnl=None):
        self.flattened.add(entry_t)
        act = {"sym": sym, "side": "exit", "qty": self.open_qty, "reason": reason, "entry_t": entry_t}
        if pnl is not None:
            act["pnl"] = pnl
        self.route(act)
        self.open_t = None
        if pnl is not None and reason in ("NEWS FLAT", "TIME SAFETY", "PRICE LIMIT") and ("entry", entry_t) in self.seen:
            self._close(entry_t, self.router.clock(), pnl, self.router.clock(), reason)   # the model's later exit: a no-op

    def process(self, ctx: dict):
        try:
            self._process(ctx)
        except Exception as e:
            self.log("error", f"routing failed: {e.__class__.__name__}: {e}")

    def _process(self, ctx: dict):
        if self.problem is not None or self.adapter is None:
            return
        res, sym, now, secs = ctx["res"], ctx["sym"], ctx["now"], ctx["secs"]
        st = ctx["state"]
        pos = st.get("position")
        en = st.get("enter_now") if not pos else None
        start = ctx["start"]
        # the 1m CISD entry routed before its fill bar existed: once the model can check it, still its trade?
        pv = self.provisional.get(self.open_t) if self.open_t is not None else None
        if pv and not pv.get("done") and not (en and en.get("entry_t") == self.open_t):
            cur = pos if pos and pos.get("entry_t") == self.open_t else next((t for t in res["trades"] if t["entry_t"] == self.open_t), None)
            if cur is not None or ctx["fill_bar_seen"](self.open_t):
                pv["done"] = True
                if cur is None:
                    self.log("risk", "LIT entry is not the model's trade once its fill bar closed: flattening this account")
                    self._flatten(sym, "NO TRADE", self.open_t, pnl=0.0)
        if self.router.killed():
            return
        e = _et(now)
        if self.open_t is not None and e.hour * 60 + e.minute >= ctx["flat_mod"] + 3 and self.open_t not in self.flattened \
                and pos is not None and pos.get("entry_t") == self.open_t:
            self.log("risk", f"SAFETY FLATTEN: {e:%H:%M} ET is past the flat time and the model still shows the position")
            self._flatten(sym, "TIME SAFETY", self.open_t, pnl=self._mark_pnl(pos, st))
        if self.open_t is not None and self.open_t not in self.flattened and self.in_news(now) is not None:
            r = self.in_news(now)                   # -2 / +2 min: a trade still held after the release is closed too
            self.log("risk", f"NEWS FLAT: Tier-1 release at {_et(r):%H:%M} ET (funded news ban): flattening this account")
            self._flatten(sym, "NEWS FLAT", self.open_t, pnl=self._mark_pnl(pos, st))
        if self.open_t is not None and self.open_t not in self.flattened and self.price_limit_block(now):
            self.log("risk", f"{self.price_limit_block(now)}: flattening this funded account")
            self._flatten(sym, "PRICE LIMIT", self.open_t, pnl=self._mark_pnl(pos, st))
        ent = pos or en
        if ent and ent["entry_t"] >= start - secs and ("entry", ent["entry_t"]) not in self.seen:
            self.seen.add(("entry", ent["entry_t"]))
            age = now - (ent["entry_t"] + secs)
            why = ctx.get("entry_block") or (f"seen {age // 60} min late" if age > 2 * secs + 60 else None) or self.entry_block(now)
            why = why or self.router.opposite_open(1 if ent["dir"] == 1 else -1, exclude=self)
            fl = getattr(self.router.bot, "fleet", None)           # engine/fleet.py (off = None): no hedge vs a follower
            why = why or (fl.opposite_open(1 if ent["dir"] == 1 else -1) if fl is not None else None)
            q = 0 if why else self.qty_for(ent, now)
            if q and not why:
                # night-rehearse 2026-11-18: ATLAS's 25K (account B) / the Rapid's ATLAS / BLITZ on ANOTHER account holding the
                # other side: this LIT copy waits until that close is confirmed (LiveBot._hedge_clear closes it; begin() starts
                # it even when the bot's own account is stood down), like the bot's own LIT entry. Was routed at once from this
                # thread: the 25K #2 went short while ATLAS's funded 25K was still long (MFFU: no long + short across accounts).
                held = self.router.others_opposite(1 if ent["dir"] == 1 else -1, self)
                if held:
                    from .live import LIT_MAX_LATE_S
                    late = LIT_MAX_LATE_S if str(ent.get("tf") or "") == "1m" else 2 * secs + 60
                    if now - int(ent["entry_t"]) <= late:
                        self.seen.discard(("entry", ent["entry_t"]))
                        if ent["entry_t"] not in self.hedge_wait:
                            self.hedge_wait.add(ent["entry_t"])
                            self.log("risk", f"entry at {_et(ent['entry_t']):%H:%M} ET waits: {held} (no long + short across "
                                             "accounts; tried again next poll)")
                        q = -1
                    else:
                        why = f"HEDGE BLOCKED: {held} and its close was not confirmed before LIT's entry deadline"
                        q = 0
            if q and q != -1 and not why and self.shared() is not None:
                # one account, two strategies (engine/rapid.py): LIT has priority. ATLAS holding a position here (either
                # side) is closed at market FIRST; LIT routes only once that close is CONFIRMED flat, tried again on
                # every poll until LIT's entry deadline (live.LIT_MAX_LATE_S after its fill bar opened), then skipped
                ok = False
                had = getattr(self.shared(), "open_t", None) is not None
                try:
                    ok = self.shared().yield_to_lit(1 if ent["dir"] == 1 else -1, sym, now, px=ent.get("entry"), any_side=True)
                except Exception as e:
                    self.log("error", f"ATLAS close on this account failed: {e.__class__.__name__}: {e}")
                if not ok:
                    from .live import LIT_MAX_LATE_S
                    if now - int(ent["entry_t"]) <= LIT_MAX_LATE_S:
                        self.seen.discard(("entry", ent["entry_t"]))
                        self.log("risk", f"entry at {_et(ent['entry_t']):%H:%M} ET waits: ATLAS's close on this account is not "
                                         "confirmed yet (tried again next poll)")
                        q = -1
                    else:
                        why = "ATLAS's close on this account was not confirmed before LIT's entry deadline (HEDGE BLOCKED)"
                        q = 0
                elif had:
                    q = self.qty_for(ent, now)     # ATLAS's close is booked now: size on the book after it (day $, room)
            if q == -1:
                pass
            elif why or not q:
                self.blocked.add(ent["entry_t"])
                self.log("risk", f"entry at {_et(ent['entry_t']):%H:%M} ET NOT routed on this account: "
                                 + (why or "; ".join((self.last_size or {}).get("reasons", [])[-2:]) or "size 0"))
            else:
                d = 1 if ent["dir"] == 1 else -1
                self.open_t, self.open_qty = ent["entry_t"], q
                if ent is en:
                    self.provisional[int(en["entry_t"])] = {"qty": q, "dir": d, "t": int(now)}
                bk = self.bank.get(int(ent["entry_t"])) if q == 1 else None
                if q != 1:
                    self.bank.pop(int(ent["entry_t"]), None)
                rr = self.route({"sym": sym, "side": "buy" if d == 1 else "sell", "qty": q, "stop": _tick(ent["stop"], d),
                                 "target": _tick(bk["px"] if bk else ent["target"], d, target=True), "entry": ent["entry"],
                                 "entry_t": ent["entry_t"]})
                if rr.get("ok") is not False:
                    self.router.notify_entry(self, ent, q, sym, rr)
        if pos and self.open_t == pos.get("entry_t") and getattr(self.adapter, "route_stop_moves", False):
            self._stop_move(pos, sym)
        self._drop_unplaced(now)
        # night-nqlive 2026-11-20 (PC data 2026-11-17 20:26 ET): Zlarior 25K #2, added while the bot ran, booked the Nov 16 06:16
        # trade's model exit (-$129.40) on its own ledger and sent NinjaTrader a CLOSEPOSITION for it on its first poll: the
        # model's window still holds older trades and the bot's start (ctx "start") was before the account existed. A trade
        # that ended before this account joined is skipped; an exit of an entry this account never routed books $0 (as
        # LiveBot does since 2026-10-26: "a missed 08:37 BE trade booked +$0.10 on the 50K").
        start_x = max(int(start or 0), int(getattr(self, "added_t", 0) or 0))
        for tr in res["trades"]:
            if tr["exit_t"] < start - secs or tr["exit_t"] < start_x - secs or ("exit", tr["entry_t"]) in self.seen:
                continue
            self.seen.add(("exit", tr["entry_t"]))
            if tr["entry_t"] in self.blocked:
                continue
            if tr["entry_t"] in self.flattened:
                if ("entry", tr["entry_t"]) in self.seen:
                    self._close(tr["entry_t"], tr.get("exit_t") or now, 0.0, now, "flattened before the model exit")
                continue
            routed = ("entry", tr["entry_t"]) in self.seen
            if not routed and self.spec["adapter"] == "paper":
                continue
            if not routed and (held := self._shared_holds()):
                # redteam 2026-11-20: the "in case" flatten of an entry this lane never routed is a CLOSEPOSITION of the whole
                # account: on an account the other strategy shares (the Rapid's ATLAS lane, ATLAS's funded 25K) it would close
                # THAT trade. No position of ours exists for an entry we never routed: nothing is sent.
                self.log("risk", f"exit {tr['exit_reason']} for the entry at {_et(tr['entry_t']):%H:%M} ET this account never routed: "
                                 f"no flatten ({held}; it would close that trade)")
                continue
            qty = tr["qty"]
            if self.open_t == tr["entry_t"]:
                self.open_t = None
                qty = self.open_qty or tr["qty"]
            pnl = round(tr["pnl"] * qty / tr["qty"], 2) if tr["qty"] else tr["pnl"]
            if tr.get("adds") and tr.get("pts") is not None:     # extra accounts never scale in: the first entry's P&L only
                from . import lit as _lit
                from .sizing import LIVE_COMM     # the live commission (tr from engine/lit_live carries it as comm_rt)
                pnl = round(qty * (float(tr["pts"]) * _lit.PV - float(tr.get("comm_rt", LIVE_COMM))), 2)
            bk = self.bank.pop(int(tr["entry_t"]), None)
            if bk is not None:                                  # the Rapid 25K option: the broker's limit at the room
                from . import rapid as _rp
                from .sizing import LIVE_COMM
                pnl, hit = _rp.bank_pnl(bk, qty, tr.get("mfe"), tr.get("risk_pts"), pnl, comm=float(tr.get("comm_rt", LIVE_COMM)))
                why = "BANK (best-day room)" if hit else tr["exit_reason"]
            else:
                why = tr["exit_reason"]
            if self.spec["adapter"] == "paper" or tr["exit_reason"] == "TIME" or getattr(self.adapter, "route_all_exits", False):
                self.route({"sym": sym, "side": "exit", "qty": qty, "reason": why, "pnl": pnl if routed else 0.0,
                            "entry_t": tr["entry_t"], "exit_t": tr["exit_t"]})
            if routed:
                self._close(tr["entry_t"], tr["exit_t"], pnl, now, why)
                self.router.notify_outcome(self, tr, qty, pnl)

    def _close(self, entry_t, exit_t, pnl, now, why):
        with self.mx:
            if any(len(c) > 3 and c[3] == entry_t for c in self.closes):
                return
            self.closes.append([trading_day(exit_t), int(exit_t), float(pnl), int(entry_t)])
            self.closes = self.closes[-1500:]
        self.check_lock(now)
        self.router.save()

    def _stop_move(self, pos, sym):
        d = 1 if pos.get("dir", 1) == 1 else -1
        et_, new = pos.get("entry_t"), _tick(pos.get("stop"), d)
        last = self.broker_stop(et_)
        if new is None or last is None or abs(float(new) - float(last)) < 1e-9 or (float(new) - float(last)) * d < 0:
            return
        if (et_, new) in self.gaveup:
            return
        ready = getattr(self.adapter, "has_open_bracket", None)
        if callable(ready) and not ready(et_):
            return
        tries = sum(1 for r in self.ledger if r.get("entry_t") == et_ and r.get("side") == "modify" and r.get("stop") == new)
        if tries >= 3:
            self.gaveup.add((et_, new))
            self.log("risk", f"broker refused the stop move to {new:.2f} three times: check this account's stop by hand")
            return
        reason = "BE" if (float(new) - float(pos.get("entry") or new)) * d >= 0 else "STOP MOVE"
        self.route({"sym": sym, "side": "modify", "qty": self.open_qty or pos.get("qty"), "stop": new, "reason": reason, "entry_t": et_})

    def kill(self, sym):
        """Flatten this account (NinjaTrader: the adapter's kill = FLATTENEVERYTHING, works on a disabled account too)."""
        try:
            if self.adapter is None:
                return {"ok": False, "error": "no adapter"}
            act = {"sym": sym, "side": "exit", "qty": self.open_qty, "reason": "KILL SWITCH", "entry_t": self.open_t}
            if self.open_t is not None:
                self.flattened.add(self.open_t)
            if self.spec["adapter"] == "paper" and self.open_t is None:
                return {"ok": True, "note": "flat"}
            r = self.route(act)
            self.open_t = None
            return r
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    # ---- persistence / views
    def blob(self, today) -> dict:
        with self.mx:
            return {"id": self.id, "nt_account": self.spec.get("nt_account"), "day": today, "ledger": self.ledger[-300:],
                    "closes": list(self.closes), "seen": [list(k) for k in list(self.seen)[-500:]], "open_t": self.open_t,
                    "open_qty": self.open_qty, "blocked": sorted(self.blocked), "flattened": sorted(self.flattened),
                    "provisional": {str(k): v for k, v in self.provisional.items()}, "lock": self.lock,
                    **({"bank": {str(k): v for k, v in self.bank.items()}} if self.bank else {})}

    def restore(self, b: dict, today: str):
        if not b or b.get("nt_account") != self.spec.get("nt_account"):
            return
        self.closes = [list(c) for c in (b.get("closes") or []) if isinstance(c, (list, tuple)) and len(c) >= 3]
        try:                         # engine/keepalive: the saved ledger's CONFIRMED fill days outlive an earlier day's ledger
            from . import keepalive as _ka
            self._ka_seed = _ka.seed_days(b.get("ledger") or [])
        except Exception:
            pass
        if b.get("day") != today:
            return
        self.ledger = list(b.get("ledger") or [])
        self.seen = {tuple(k) for k in b.get("seen") or []}
        self.open_t, self.open_qty = b.get("open_t"), b.get("open_qty")
        self.blocked = set(b.get("blocked") or [])
        self.flattened = set(b.get("flattened") or [])
        self.provisional = {int(k): v for k, v in (b.get("provisional") or {}).items()}
        self.bank = {int(k): v for k, v in (b.get("bank") or {}).items()}
        lk = b.get("lock")
        self.lock = lk if lk and lk.get("day") == today else None


# ---------------------------------------------------------------------------------------------------------------- router
class AccountRouter:
    """Every extra account of the start cfg. LiveBot keeps routing its own account; this mirrors each signal to the rest."""

    def __init__(self, bot, specs: list, state_path: str | None = None, parallel: bool = True, adapter_factory=None):
        self.bot = bot
        self.accounts = [Account(s, self) for s in specs]
        self.state_path = state_path or _state_path_for(getattr(bot, "state_path", None))
        self.parallel = parallel
        self.adapter_factory = adapter_factory
        self.mx = threading.RLock()
        self._kill = False

    # ---- plumbing
    def clock(self):
        return self.bot.clock()

    def log(self, kind, text):
        try:
            self.bot._log(kind, text)
        except Exception:
            print(f"[accounts] {kind}: {text}")

    def killed(self) -> bool:
        return self._kill or bool(getattr(self.bot, "kill", False))

    def opposite_open(self, d: int, exclude=None):
        """MFFU (and most firms) forbid long and short on the same underlying at the same time, also across your own
        accounts. Copy trading is always the same side; this refuses an order of direction d while any OTHER account
        (an extra one, or the bot's own: exclude=None means the caller is the bot's own account) holds the opposite side.
        Returns why, or None. A keep-alive trade (engine/keepalive.py, OFF by default) the other way, or on the entering
        account itself, is closed first."""
        try:
            from . import keepalive as _ka
            h = _ka.before_entry(self.bot, d, self.bot if exclude is None else exclude)
            if h:
                return h
        except Exception:
            pass
        for a in self.accounts:
            if a is exclude or a.open_t is None:
                continue
            e = next((r for r in a.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t") == a.open_t), None)
            if e and (1 if e["side"] == "buy" else -1) == -d:
                return f"hedging guard: {a.name} holds a {'LONG' if d == -1 else 'SHORT'} position (no long + short across accounts)"
        if exclude is not None:
            b = self.bot
            ot = getattr(b, "_open_routed", None)
            if ot is not None:
                e = next((r for r in reversed(getattr(b, "ledger", None) or []) if r.get("side") in ("buy", "sell") and r.get("entry_t") == ot), None)
                if e and (1 if e["side"] == "buy" else -1) == -d:
                    return f"hedging guard: the bot's own account holds a {'LONG' if d == -1 else 'SHORT'} position"
        # hand trades (engine/hand_hedge.py, day-redteam2 2026-11-20): NinjaTrader's own position files of every MFFU account; a
        # position no bot lane explains on the other side refuses this entry (the ledger checks above only see the bot's trades)
        try:
            from . import hand_hedge
            if exclude is None:
                own = getattr(getattr(self.bot, "adapter", None), "account", None)
            else:
                own = ((getattr(exclude, "spec", None) or {}) if isinstance(getattr(exclude, "spec", None), dict) else {}).get("nt_account")
            h = hand_hedge.opposite_hand(d, self.bot, self, own=own, now=self.clock(), notify=self.notify)
            if h:
                return h
        except Exception:
            pass
        return None

    def others_opposite(self, d: int, acc=None):
        """ATLAS's 25K (account B), ATLAS on the Rapid EOD and BLITZ (account C) on ANOTHER NinjaTrader account than `acc`
        holding (or still closing: open_t stays set until the close is confirmed) the side opposite to d: who, else None.
        The same account (engine/rapid.py, engine/lit25.py) is the lane's own shared() yield. An unknown side fails closed."""
        b = self.bot
        mine = str(((acc.spec if acc is not None else {}) or {}).get("nt_account") or "").strip()
        same = acc.shared() if acc is not None else None
        for attr, who in (("acct_b", "ATLAS's 25K"), ("acct_r", "ATLAS on the Rapid EOD"), ("acct_r2", "ATLAS on the Rapid EOD #2"),
                          ("acct_c", "BLITZ (account C)")):
            o = getattr(b, attr, None)
            if o is None or o is same or getattr(o, "open_t", None) is None:
                continue
            if mine and str(getattr(o, "name", "") or "").strip() == mine:
                continue
            try:
                dd = int(((getattr(o, "prov", None) or {}).get(int(o.open_t)) or {}).get("dir") or 0)
            except Exception:
                dd = 0
            if dd != d:
                return f"{who} {getattr(o, 'name', '') or ''} holds a {'SHORT' if d == 1 else 'LONG'} position".replace("  ", " ")
        return None

    def _hedge_first(self, live, ctx):
        """begin(), on the poll thread before the account threads: a new LIT entry that some account here will take while
        ATLAS / BLITZ holds the other side on another account -> the bot's own hedge close (LiveBot._hedge_clear: ATLAS /
        BLITZ closed at market, LIT first) starts now, also when the bot's own account takes no entry (stood down after a
        pass, its guard). The accounts wait (Account._process) until that close is confirmed. Never raises."""
        try:
            st = ctx["state"]
            ent = st.get("position") or st.get("enter_now")
            if not ent or self.killed():
                return
            d = 1 if ent.get("dir") == 1 else -1
            if not any(("entry", ent["entry_t"]) not in a.seen and ent["entry_t"] >= ctx["start"] - ctx["secs"]
                       and not a.entry_block(ctx["now"]) and self.others_opposite(d, a) for a in live):
                return
            try:                       # a hand trade refuses this entry on every account (opposite_open): never close ATLAS /
                from . import hand_hedge   # BLITZ at market for an entry nobody may take (fix-trade 2026-11-21)
                if hand_hedge.opposite_hand(d, self.bot, self, now=ctx["now"], notify=self.notify):
                    return
            except Exception:
                pass
            hc = getattr(self.bot, "_hedge_clear", None)
            if callable(hc):
                hc(ent, ctx["sym"], ctx["now"])
        except Exception as e:
            self.log("error", f"hedge close for the extra accounts failed: {e.__class__.__name__}: {e}")

    def base_sizing(self) -> dict:
        return dict(getattr(self.bot, "_lit_sizing", None) or {})

    def real_bot(self) -> bool:
        try:
            from .live import STATE_PATH
            return getattr(self.bot, "state_path", None) == STATE_PATH
        except Exception:
            return False

    def _push(self, payload):
        if not self.real_bot():
            return
        try:
            from . import push
            push.pc_notify(payload)
        except Exception:
            pass

    def notify(self, title, body, key):
        try:
            from . import push
            self._push(push.text_payload("PC", "risk", title, body, key=key, t=int(self.clock()), url="#/accounts"))
        except Exception:
            pass

    def _wire_push(self, acc):
        """Owner 2026-11-20 (entry + exit alerts on every account, the moment it happens): the account's NinjaTrader adapter notifies
        its entry fill and its bracket exit (stop / target) under the account's own name and key, so the exit reaches the phone at
        the fill, not when the model sees the bar close. notify_entry / notify_outcome below send the same keys: engine/push keeps
        whichever comes first (one alert per trade and account). The real bot only. Never raises."""
        try:
            if acc.adapter is not None and hasattr(acc.adapter, "push_as") and self.real_bot():
                acc.adapter.push_as = {"account": acc.name, "suffix": f":{acc.id}", "url": "#/accounts"}
        except Exception:
            pass

    def _tag(self, p, acc):
        p["key"] = f"{p['key']}:{acc.id}"
        p["tag"] = f"{p.get('tag', '')}-{acc.id}"
        p["url"] = "#/accounts"
        return p

    def notify_entry(self, acc, ent, q, sym, rr):
        try:
            from . import push
            legs = [lg for lg in (rr or {}).get("legs") or [] if isinstance(lg, dict) and lg.get("filled")]
            px = legs[0].get("fill_px") if legs else ent.get("entry")
            self._push(self._tag(push.entry_payload(acc.name, "LONG" if ent.get("dir") == 1 else "SHORT", q, ent["entry_t"], src="pc",
                                                    contract="MNQ" if sym == "NQ" else sym, entry=px,
                                                    stop=ent.get("stop0", ent.get("stop")), target=ent.get("target")), acc))
        except Exception:
            pass

    def notify_outcome(self, acc, tr, qty, pnl):
        try:
            from . import push
            self._push(self._tag(push.outcome_payload(acc.name, "LONG" if tr.get("dir") == 1 else "SHORT", tr.get("exit_reason"),
                                                      pnl, tr["entry_t"], tr.get("exit_t"), src="pc", qty=qty), acc))
        except Exception:
            pass

    # ---- lifecycle
    def adapter_cfg(self, acc: Account) -> dict:
        """The account's adapter cfg: the bot's cfg (instrument, folder, params...) WITHOUT its account and arming, then
        the account's own name, arming, phrase and state files."""
        base = {k: v for k, v in (self.bot.cfg or {}).items()
                if k not in ("accounts", "armed", "confirm", "nt_account", "nt_state_path", "nt_audit_log", "eval_start",
                             "eval_prior_pnl", "eval_anchor", "lit_sizing", "funded", "webhook_url")}
        s = acc.spec
        p = dict(base.get("params") or {})
        p["max_micros"] = min(int(p.get("max_micros", 40) or 40), int(acc.rules["max_micros"]))
        d = os.path.dirname(self.state_path)
        return {**base, "adapter": s["adapter"], "nt_account": s["nt_account"], "armed": bool(s.get("armed")),
                "confirm": s.get("confirm") or "", "params": p, "nt_file_tag": f"{acc.id}_",
                "nt_state_path": os.path.join(d, f"ninjatrader_state_{acc.id}.json"),
                "nt_audit_log": os.path.join(os.path.join(ROOT, "logs") if self.real_bot() else d, f"ninjatrader_oif_{acc.id}.log")}

    def start(self):
        from .live import ADAPTERS
        today = trading_day(self.clock())
        saved = self._load()
        for acc in self.accounts:
            acc.restore((saved.get("accounts") or {}).get(acc.id) or {}, today)
            if getattr(self, "_state_pause", None):
                acc.lock = {"day": today, "reason": self._state_pause, "t": int(self.clock()), "state_damaged": True}
            if acc.problem is not None:
                self.log("risk", f"[{acc.name}] not trading: {acc.problem}")
                continue
            try:
                cfg = self.adapter_cfg(acc)
                if self.adapter_factory is not None:
                    acc.adapter = self.adapter_factory(acc, cfg)
                else:
                    acc.adapter = ADAPTERS[cfg["adapter"]](cfg)
            except Exception as e:
                acc.problem = f"adapter failed: {e.__class__.__name__}: {e}"
            self._wire_push(acc)
            dis = acc.disabled_reason()
            self.log("system" if not dis else "risk", f"[{acc.name}] {acc.label()} {acc.spec.get('nt_account') or ''} "
                     f"{acc.spec['firm']} {acc.spec['plan']}, mode {acc.mode}, eval from {acc.start_day() or '?'}: "
                     + (f"DISABLED ({dis})" if dis else "ready"))
        self.save()
        return self

    def tick(self):
        if self.killed():
            return
        for acc in self.accounts:
            ad = acc.adapter
            if acc.problem is None and getattr(ad, "loop_tick", False) and callable(getattr(ad, "tick", None)):
                try:
                    ad.tick()
                except Exception as e:
                    acc.log("error", f"adapter tick failed: {e.__class__.__name__}: {e}")
            if acc.problem is None:
                acc.broker_tick(int(self.clock()))

    def begin(self, res, sym, now, secs, entry_block=None):
        """Start this poll's routing for every account (threads when parallel): returns a job; finish(job) joins it."""
        live = [a for a in self.accounts if a.problem is None and a.adapter is not None]
        if not live:
            return None
        try:
            from .model import merge_params
            flat_mod = int(merge_params((self.bot.cfg or {}).get("params", {}))["flat_mod"])
        except Exception:
            flat_mod = 955
        ctx = {"res": res, "state": dict(self.bot.state or {}), "sym": sym, "now": int(now), "secs": int(secs),
               "start": int(self.bot.started_at or now), "flat_mod": flat_mod, "entry_block": entry_block,
               "fill_bar_seen": getattr(self.bot, "_fill_bar_seen", lambda _t: True)}
        self._hedge_first(live, ctx)
        if not self.parallel or len(live) == 1 and not self._wants_thread(live[0]):
            for a in live:
                a.process(ctx)
            return None
        ths = [threading.Thread(target=a.process, args=(ctx,), name=f"acct-{a.id}", daemon=True) for a in live]
        for t in ths:
            t.start()
        return ths

    @staticmethod
    def _wants_thread(acc) -> bool:
        return acc.spec["adapter"] != "paper"

    def finish(self, job, timeout=60.0):
        for t in job or []:
            t.join(timeout)
        self.save()

    def route(self, res, sym, now, secs, entry_block=None):
        self.finish(self.begin(res, sym, now, secs, entry_block))

    def kill(self, sym="NQ") -> list:
        self._kill = True
        out = []
        for acc in self.accounts:
            if acc.adapter is None:
                continue
            r = acc.kill(sym)
            out.append({"id": acc.id, "ok": bool(r.get("ok")), "error": r.get("error")})
            acc.log("risk", "KILL SWITCH: " + ("flattened" if r.get("ok") else f"flatten NOT confirmed ({r.get('error')})"))
        self.save()
        return out

    # ---- persistence
    def _load(self) -> dict:
        """night-statesafe 2026-11-23: an unreadable live_state_accounts.json never means a clean day (each extra account's lock-out
        and today's ledger, so its daily loss, were gone): today's .bak, else the older .bak's history + every account locked out
        today (self._state_pause, applied in start()) + one phone message."""
        self._state_pause = None
        try:
            from . import state_safe as _ss
            today = trading_day(self.clock())
            got = _ss.load(self.state_path, lambda b: b.get("day"), today)
            if got["damaged"]:
                nm = os.path.basename(self.state_path)
                if got["blob"] is not None:
                    self.log("warn", f"{got['why']}: restored from today's backup {nm}.bak")
                    return got["blob"]
                self._state_pause = f"the state file was damaged today ({got['why']}): no new entry until the next trading day"
                self.log("risk", f"{got['why']}: today's numbers cannot be rebuilt: NO NEW ENTRY on the extra accounts today "
                                 "(exits and brackets untouched)")
                _ss.alert(nm, today, self.real_bot())
                ob = got.get("old_bak")
                return ob if isinstance(ob, dict) else {}
            if got["blob"] is not None:
                self._state_good = True
            return got["blob"] or {}
        except Exception:
            return {}

    def save(self):
        if not self.state_path:
            return
        with self.mx:
            try:
                today = trading_day(self.clock())
                blob = {"v": VERSION, "saved_at": int(self.clock()), "day": today,
                        "accounts": {a.id: a.blob(today) for a in self.accounts}}
                os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
                tmp = self.state_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(blob, fh, default=str)
                from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
                from . import state_safe as _ss
                _ss.rotate(self.state_path, getattr(self, "_state_good", False))   # night-statesafe: previous good copy -> .bak
                _fs_replace(tmp, self.state_path)
                self._state_good = True
            except Exception as e:
                self.log("warn", f"accounts state save failed: {e.__class__.__name__}: {e}")

    # ---- views (heartbeat "acct".accounts, pc_health accounts, the PC Accounts page)
    def health(self, now=None) -> list:
        now = int(now or self.clock())
        today = trading_day(now)
        out = []
        for a in self.accounts:
            ad = a.adapter
            row = {"id": a.id, "name": a.name, "firm": a.spec["firm"], "plan": a.spec["plan"], "mode": a.mode,
                   "nt_account": a.spec.get("nt_account") or None, "label": a.label(), "is_live": a.label() == "LIVE",
                   "enabled": a.enabled and not getattr(ad, "disabled", None), "disabled": a.disabled_reason(),
                   "armed": bool(a.spec.get("armed")), "live_lock": os.environ.get("NINJATRADER_LIVE", "") == "1",
                   "locked": (a.lock or {}).get("reason") if (a.lock or {}).get("day") == today else None,
                   "open": a.open_t is not None, "open_qty": a.open_qty if a.open_t is not None else None,
                   "day_pnl": a.day_pnl(today), "entries_today": a.entries_today(today),
                   "last_error": getattr(ad, "last_error", None), "news_ban": a.news_on()}
            out.append(row)
        return out

    def summary(self, now=None) -> list:
        """One heartbeat sub-block per account, shaped like engine/accounts.pc_activity (account, position, orders, trades,
        eval days) plus its plan, mode, lock-out and last sizing, so the cloud builds a full Accounts section from it."""
        from . import accounts as A
        now = int(now or self.clock())
        today = trading_day(now)
        out = []
        for a, h in zip(self.accounts, self.health(now)):
            try:
                R = a.rules
                orders = [A.order_row(r) for r in a.ledger if r.get("t") and trading_day(r["t"]) == today][-40:]
                trades = []
                ent = {int(r["entry_t"]): r for r in a.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None}
                for d, xt, p, *rest in a.closes[-60:]:
                    et_ = rest[0] if rest else None
                    e = ent.get(int(et_)) if et_ is not None else None
                    row = {"day": d, "exit_t": int(xt), "pnl": round(float(p), 2)}
                    if et_ is not None:
                        row["entry_t"] = int(et_)
                    if e:
                        row.update(side="LONG" if e.get("side") == "buy" else "SHORT", qty=e.get("qty"), entry=e.get("entry"),
                                   stop=e.get("stop"), target=e.get("target"))
                    trades.append(A.trade_row(row))
                pos = None
                if a.open_t is not None:
                    e = ent.get(int(a.open_t)) or {}
                    lg = A._leg_for(a.adapter, a.open_t)
                    d = 1 if e.get("side") == "buy" else -1
                    pos = {"entry_t": int(a.open_t), "side": "LONG" if d == 1 else "SHORT", "dir": d, "qty": a.open_qty,
                           "entry": A._f((lg or {}).get("fill_px") or e.get("entry")), "stop": A._f(a.broker_stop(a.open_t)),
                           "target": A._f(e.get("target")), "stop0": A._f(e.get("stop"))}
                out.append({"v": A.VERSION, "id": a.id, "name": a.name, "firm": a.spec["firm"], "plan": a.spec["plan"],
                            "kind": "funded" if a.mode == "funded" else "eval", "mode": a.mode,
                            "account": {"name": A.clean_text(a.spec.get("nt_account") or "Paper", 60), "adapter": a.spec["adapter"],
                                        "kind": h["label"].lower(), "label": "LIVE ACCOUNT" if h["label"] == "LIVE" else h["label"],
                                        "disabled": A.clean_text(h["disabled"], 120)},
                            "enabled": h["enabled"], "locked": A.clean_text(h["locked"], 120), "running": bool(getattr(self.bot, "running", False)),
                            "kill": self.killed(), "position": pos, "orders": orders, "trades": trades,
                            "eval": {"start": a.start_day() or None, "days": {k: round(v, 2) for k, v in sorted(a.eval_days().items())},
                                     **({"anchor": a.anchor()} if a.mode != "funded" and a.anchor() else {})},
                            "plan_rules": {"start": R["start"], "target": R["target"], "mll": R["mll"],
                                           "lock": R["start"] + R["lock"] if R.get("trail") != "static" else R["start"] - R["mll"],
                                           "dll": R["dll"], "sessions": 10},
                            "day_pnl": h["day_pnl"], "size": a.last_size,
                            **({"funded": {"start": (a.spec.get("funded") or {}).get("start"), "preset": a.spec.get("preset"),
                                           "payouts": dict((a.spec.get("funded") or {}).get("payouts") or {})}}
                               if a.mode == "funded" else {})})
            except Exception as e:
                out.append({"id": a.id, "name": a.name, "error": f"{e.__class__.__name__}: {A.clean_text(e, 120)}"})
        return out


def _state_path_for(bot_state_path: str | None) -> str:
    p = bot_state_path or os.path.join(ROOT, "data", "live_state.json")
    base, ext = os.path.splitext(p)
    return base + "_accounts" + (ext or ".json")


def build(bot, cfg: dict, **kw):
    """LiveBot.start: the router for the start cfg's extra accounts, or None (no "accounts" list: today's bot, untouched)."""
    specs = specs_from_cfg(cfg)
    if not specs:
        return None
    par = cfg.get("accounts_parallel", True) is not False
    kw.setdefault("adapter_factory", ADAPTER_FACTORY)
    return AccountRouter(bot, specs, parallel=par, **kw).start()


# ---------------------------------------------------------------------------------------------------------------- start cfg
def merge_into_start(body: dict, confirm: str = "", path: str = ACCOUNTS_PATH) -> dict:
    """python -m engine.ninjatrader --start: the extra accounts of data/accounts.json join the start body. The phrase typed
    at --start is given (in memory only) to every real account whose entry says "armed": true; NINJATRADER_LIVE=1 is
    still checked by each account's adapter."""
    rows = [r for r in load_file(path) if r.get("enabled", True) is not False]
    if not rows:
        return body
    out = []
    for r in rows:
        r = dict(r)
        if lucid_held(r):
            # the second firm (day-lucidrt 2026-11-22 red team): an "armed" Lucid row WITHOUT the owner's recorded written OK
            # (engine/account_cli lucid-ok) never gets the phrase, whatever set "armed" (account_cli.arm holds it; this also
            # covers `python -m engine.multi_account --set --armed yes`, a hand-edited data/accounts.json or a restored file)
            r["armed"] = False
            r.pop("confirm", None)
            r["held"] = "Lucid: no written OK recorded (python -X utf8 -m engine.accounts lucid-ok --name \"<Name>\")"
        elif r.get("armed") is True and confirm:
            r["confirm"] = confirm
        out.append(r)
    return {**body, "accounts": out}


def lucid_held(row: dict) -> bool:
    """True = a Lucid account (preset lucid_*, or added as plan lucidpro50k) on which the owner has not recorded Lucid's written OK.
    Sim accounts are never held (paper)."""
    cli = row.get("cli") if isinstance(row.get("cli"), dict) else {}
    lucid = str(row.get("preset") or "").startswith("lucid") or str(cli.get("plan") or "").startswith("lucid")
    if not lucid:
        return False
    if str(row.get("nt_account") or "").strip().lower().startswith("sim"):
        return False
    return not cli.get("lucid_ok")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.multi_account", description="the PC bot's extra accounts (data/accounts.json)")
    ap.add_argument("--presets", action="store_true", help="list the firm presets")
    ap.add_argument("--list", action="store_true", help="list data/accounts.json")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--set", action="store_true", help="change fields of an existing account")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--disable", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--name")
    ap.add_argument("--nt-account", help="the account Name in NinjaTrader's Accounts tab")
    ap.add_argument("--adapter", choices=list(ADAPTERS_OK))
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--mode", choices=list(MODES))
    ap.add_argument("--eval-start", help="first session of this account's eval (yyyy-mm-dd)")
    ap.add_argument("--prior-pnl", type=float, help="the account's P&L before the bot traded it ($)")
    ap.add_argument("--funded-start", help="first funded session (mode funded)")
    ap.add_argument("--payout", action="append", default=[], help="day=amount withdrawn (repeatable)")
    ap.add_argument("--max-micros", type=int)
    ap.add_argument("--armed", choices=["yes", "no"], help="real accounts: yes = trades with the phrase given at --start")
    ap.add_argument("--file", default=ACCOUNTS_PATH)
    a = ap.parse_args(argv)
    if a.presets:
        for k, p in PRESETS.items():
            r = p["rules"]
            print(f"{k:20s} {p['firm']} {p['plan']}: target ${r['target']:,.0f}, max loss ${r['mll']:,.0f} ({r['trail']}), "
                  f"daily ${r['dll']:,.0f}, max {r['max_micros']} micros"
                  + (f", best day {r['best_day'] * 100:.0f}%" if r.get("best_day") else "")
                  + (f", news ban {r['news_ban']}" if r.get("news_ban") else "") + f"\n{'':21s}{p['note']}")
        return 0
    rows = load_file(a.file)
    if a.list or not (a.add or a.set or a.remove or a.enable or a.disable):
        if not rows:
            print("No extra accounts (data/accounts.json is empty): the bot trades its one account.")
        for r in rows:
            n = normalize(r)
            print(f"{n['id']:14s} {'on ' if n['enabled'] else 'off'} {n['adapter']:11s} {n['nt_account'] or '-':16s} {n['preset']:20s} "
                  f"mode {n['mode']:9s} eval from {n['eval_start'] or '?'}  armed {'yes' if n['armed'] else 'no'}"
                  + (f"  ({n['problem']})" if n["problem"] and n["problem"] != "disabled in the config" else ""))
        return 0
    if not a.id:
        print("--id is required")
        return 1
    cur = next((r for r in rows if r.get("id") == a.id), None)
    if a.add:
        if cur is not None:
            print(f"account {a.id} exists: use --set")
            return 1
        cur = {"id": a.id, "enabled": True, "armed": False, "preset": a.preset or DEFAULT_PRESET, "mode": a.mode or "two_week",
               "adapter": a.adapter or "ninjatrader"}
        rows.append(cur)
    elif cur is None:
        print(f"no account {a.id} (python -m engine.multi_account --list)")
        return 1
    if a.remove:
        rows = [r for r in rows if r.get("id") != a.id]
        save_file(rows, a.file)
        print(f"removed {a.id}")
        return 0
    for k, v in (("name", a.name), ("nt_account", a.nt_account), ("adapter", a.adapter), ("preset", a.preset), ("mode", a.mode),
                 ("eval_start", a.eval_start), ("eval_prior_pnl", a.prior_pnl), ("max_micros", a.max_micros)):
        if v is not None:
            cur[k] = v
    if a.armed is not None:
        cur["armed"] = a.armed == "yes"
    if a.enable:
        cur["enabled"] = True
    if a.disable:
        cur["enabled"] = False
    if a.funded_start or a.payout:
        f = cur.setdefault("funded", {})
        if a.funded_start:
            f["start"] = a.funded_start
        for p in a.payout:
            d, _, v = p.partition("=")
            f.setdefault("payouts", {})[d.strip()] = float(v)
    n = normalize(cur)
    if n["problem"] and n["problem"] != "disabled in the config":
        print(f"NOT saved: {n['problem']}")
        return 1
    save_file(rows, a.file)
    print(f"saved {a.id}: {n['adapter']} {n['nt_account'] or ''} {n['preset']} mode {n['mode']}, eval from {n['eval_start'] or '?'}, "
          f"{'enabled' if n['enabled'] else 'disabled'}, armed {'yes' if n['armed'] else 'no'}. It joins on the next --start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
