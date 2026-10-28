"""The bot's narrator (owner 2026-10-28: "improve the bot's ability to tell me stuff. I wanna know what's happening"):
turns the PC bot's state changes into short plain-language messages, a running feed for the Live View page
(engine/liveview_api.py, web_next/js/next/liveview.js) and, for the important ones, a phone push.

READ-ONLY. Nothing here decides, sizes, routes or changes anything. Every message is derived from snapshots the bot
already keeps, polled after routing:
  bot.brain            the Bot Brain (engine/brain.py): its thought log (sweeps, boxes, 5m CISDs, setups armed / expired /
                       rejected / skipped, stage changes), stage, watch, setups
  bot.ledger           the routed orders (engine/live.py _route rows): order sent / refused + NinjaTrader's reason, stop
                       moved to breakeven, scale-in adds, exits with the REAL booked $
  accounts._position   the routed position (NinjaTrader leg fill price, the real micros)
  bot.second           the ATLAS paper run (engine/second.py): each member's stage and decision log
  bot.acct_b.info()    account B (ATLAS on its own account): routed entries / exits / refusals with real $
  bot.blitz            the BLITZ scalper PAPER shadow (engine/blitz.py): its signals, paper entries / exits (simulated 25K
                       eval micros, labelled PAPER), paper eval ends; kind "blitz", never pushed by default
  bot.health / kill    FEED STALE episodes, the kill switch
  daily summary        once after the 15:55 flat: trades, real $, setups seen / rejected, ATLAS

Every message has a stable key (the same event never shows twice, a restart re-reads today's file). Feed:
NARRATOR.feed(n) -> newest first. Phone pushes (default ON only for: setup armed, entry, exit, refused order; every other
kind OFF; data/narrator.json {"push": {"swept": true, ...}} overrides, LE_NARRATOR_PUSH=0 turns all off) reuse the bot's
existing push keys (armed:<arm_t>:<dir>, fill:<entry_t>, out:<entry_t>) so the phone never gets the same event twice.

Wiring: LiveBot._alerts_tick calls tick(bot, now) (real bot only, never raises); /api/next/liveview calls observe(bot)
(no pushes, no files) so the feed is fresh whenever the page polls.

    python -X utf8 -m tests.test_narrator
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading
import time
from collections import deque
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs", "narrator")            # gitignored (logs/): one JSONL feed per trading day
CFG_PATH = os.path.join(ROOT, "data", "narrator.json")       # optional push overrides (not required)
PV = 2.0                                                     # $ per point per MNQ micro
KEEP = 400
PUSH_FRESH_S = 15 * 60                                       # never push an event older than this (a restart replays the day)

# kind -> (label for the page, pushed by default)
KINDS = {
    "armed": ("Setup armed", True),
    "entry": ("Filled (entry)", True),
    "exit": ("Exit + real $", True),
    "refused": ("Order refused", True),
    "swept": ("Level swept", False),
    "box": ("Session box closed", False),
    "cisd": ("5m CISD", False),
    "tapped": ("Limit tapped", False),
    "expired": ("Setup expired", False),
    "rejected": ("Setup rejected", False),
    "blocked": ("Setup skipped", False),
    "sent": ("Order sent", False),
    "be": ("Stop to breakeven", False),
    "stop": ("Stop moved", False),
    "add": ("Scale-in add", False),
    "stale": ("Feed stale", False),
    "fresh": ("Feed back", False),
    "kill": ("Kill switch", False),
    "summary": ("Daily summary", False),
    "stage": ("Stage", False),
    "model": ("Model trade (not routed)", False),
    "atlas": ("ATLAS paper", False),
    "blitz": ("BLITZ paper", False),
}
STRATS = {"lit": "Zlarior", "atlas": "ATLAS", "scalp": "BLITZ", "sys": "Bot"}
EXIT_WORDS = {"TARGET": "hit the target", "STOP": "stopped out", "BE": "breakeven", "TIME": "closed at the 15-minute check",
              "TCHECK": "cut at the 15-minute check", "EOD": "closed 15:55 (flat)", "FLAT": "closed 15:55 (flat)",
              "BANK": "banked at 8R", "KILL": "closed by the kill switch", "KILL SWITCH": "closed by the kill switch",
              "TIME SAFETY": "closed by the clock safety", "REMOTE FLATTEN": "flattened from the phone", "NO TRADE": "no trade (voided)"}


# ---------------------------------------------------------------------------------------------- small helpers
def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def hm(t) -> str:
    try:
        return _et(t).strftime("%H:%M")
    except Exception:
        return "?"


def px(x) -> str:
    """29,842 / 29,807.5 / 29,807.25."""
    try:
        s = f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return "?"
    return s.rstrip("0").rstrip(".") if "." in s else s


def usd(x, sign=True) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "?"
    s = f"${abs(v):,.0f}"
    return (("+" if v > 0 else "-" if v < 0 else "") + s) if sign else s


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _f(v):
    try:
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _h8(s) -> str:
    return hashlib.sha1(str(s).encode("utf-8", "replace")).hexdigest()[:8]


def _clean(s, n=220) -> str:
    try:
        from .accounts import clean_text
        return clean_text(s, n) or ""
    except Exception:
        return str(s or "")[:n]


def side_word(d) -> str:
    try:
        return "LONG" if int(d) == 1 else "SHORT"
    except (TypeError, ValueError):
        return str(d or "").upper()


def push_prefs(path: str | None = None) -> dict:
    """{kind: bool}: KINDS defaults, then data/narrator.json "push" overrides. LE_NARRATOR_PUSH=0 -> every kind off."""
    out = {k: v[1] for k, v in KINDS.items()}
    if os.environ.get("LE_NARRATOR_PUSH", "1") == "0":
        return {k: False for k in out}
    try:
        with open(path or CFG_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in ((d or {}).get("push") or {}).items():
            if k in out:
                out[k] = bool(v)
    except Exception:
        pass
    return out


def msg(key, t, strat, kind, title, text, level="info", **extra) -> dict:
    return {"key": str(key), "t": int(t or 0), "hm": hm(t) if t else "", "strat": strat, "kind": kind, "level": level,
            "title": str(title)[:120], "text": _clean(text, 400), **extra}


# ---------------------------------------------------------------------------------------------- derive (pure)
def _brain_msgs(brain: dict, real_entries: set) -> list:
    """The LIT Brain's own thought log, in plain words. Entries / exits come from the real ledger instead (real size, real $);
    a model entry without any routed order is shown as "model, not routed" (no size)."""
    out = []
    if not isinstance(brain, dict):
        return out
    setups = {s.get("id"): s for s in brain.get("setups") or [] if isinstance(s, dict)}
    for r in reversed(brain.get("log") or []):           # the Brain keeps its log newest first
        if not isinstance(r, dict) or not r.get("key"):
            continue
        k, t, txt = str(r.get("kind") or ""), _i(r.get("t")) or 0, str(r.get("text") or "")
        key = "lit:" + str(r["key"])
        if k == "sweep":
            deep = "✗" not in txt
            out.append(msg(key, t, "lit", "swept", "Level swept" if deep else "Level touched (too shallow)", txt,
                           "info" if deep else "dim"))
        elif k == "box":
            out.append(msg(key, t, "lit", "box", "Session box closed", txt, "dim"))
        elif k == "cisd":
            out.append(msg(key, t, "lit", "cisd", "5m CISD", txt, "info"))
        elif k == "armed":
            sid = str(r["key"]).split(":", 1)[1] if ":" in str(r["key"]) else ""
            s = setups.get(sid) or {}
            plan = s.get("plan") or {}
            d = _i(s.get("dir")) or (1 if "LONG" in txt.upper() else -1)
            arm_t = _i(plan.get("armed_t")) or t
            out.append(msg(key, t, "lit", "armed", f"Zlarior setup armed · {side_word(d)}", txt.lstrip("✓ ").strip(), "good",
                           push_key=f"armed:{arm_t}:{d}", dir=d, limit=plan.get("limit"), stop=plan.get("stop"),
                           target=plan.get("target"), expires_t=plan.get("expires_t")))
        elif k == "expired":
            sid = str(r["key"]).split(":", 1)[1] if ":" in str(r["key"]) else ""
            plan = (setups.get(sid) or {}).get("plan") or {}
            d = _i((setups.get(sid) or {}).get("dir"))
            out.append(msg(key, t, "lit", "expired", "Setup expired · no fill", txt, "warn",
                           **({"push_key": f"expired:{_i(plan.get('armed_t')) or t}:{d}"} if d else {})))
        elif k == "rejected":
            out.append(msg(key, t, "lit", "rejected", "Setup rejected", txt.lstrip("✗ ").strip(), "dim"))
        elif k == "blocked":
            out.append(msg(key, t, "lit", "blocked", "Setup skipped", txt, "dim"))
        elif k == "stage":
            out.append(msg(key, t, "lit", "stage", "Now", txt.replace("Now: ", "", 1), "dim"))
        elif k in ("entry", "exit"):
            et_ = _i(str(r["key"]).split(":", 1)[1]) if ":" in str(r["key"]) else None
            if et_ is not None and et_ in real_entries:
                continue                                 # the real ledger tells this one (real micros, real $)
            out.append(msg(key, t, "lit", "model", "Model trade (not routed on an account)" if k == "entry" else "Model exit (not routed)",
                           txt + " · the model's size, nothing was sent to an account", "dim"))
        elif k == "tapped":
            out.append(msg(key, t, "lit", "tapped", "Limit tapped", txt, "info"))
        else:
            out.append(msg(key, t, "lit", "stage", k.capitalize() or "Brain", txt, "dim"))
    return out


def _route_rows(rows, strat, account, open_pos=None, paper=False) -> list:
    """Routed ledger rows -> messages: order sent / refused (NinjaTrader's reason), filled (real fill price + micros), stop
    moved (BE), scale-in add, exit with the real booked $."""
    out = []
    contract = "MNQ"
    dirs = {_i(r.get("entry_t")): (1 if r.get("side") == "buy" else -1) for r in rows or []
            if isinstance(r, dict) and r.get("side") in ("buy", "sell")}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        side, t = str(r.get("side") or ""), _i(r.get("t")) or 0
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        ok = res.get("ok", r.get("ok"))
        err = _clean(res.get("error") or r.get("error") or "", 200)
        et_ = _i(r.get("entry_t"))
        q = _i(r.get("qty")) or 0
        who = f"{account}: " if account else ""
        tag = f" ({r.get('strategy') or r.get('src')})" if strat == "atlas" and (r.get("strategy") or r.get("src")) else ""
        if side in ("buy", "sell"):
            d = 1 if side == "buy" else -1
            sw = side_word(d)
            if ok is False:
                out.append(msg(f"{strat}:refused:{et_ or t}", t, strat, "refused", f"{who}order NOT placed · {sw}{tag}",
                               f"{sw} {q} {contract} was not taken" + (f": NinjaTrader said \"{err}\"" if err else "")
                               + ". Nothing is open from it; the bot keeps looking.", "bad", entry_t=et_, dir=d))
                continue
            stop, tgt, en = _f(r.get("stop")), _f(r.get("target")), _f(r.get("entry"))
            risk = abs(en - stop) * PV * q if en is not None and stop is not None else None
            out.append(msg(f"{strat}:sent:{et_ or t}", t, strat, "sent", f"{who}order sent · {sw} {q} {contract}{tag}",
                           f"{sw} {q} {contract}" + (f" near {px(en)}" if en is not None else "")
                           + (f" · stop {px(stop)}" if stop is not None else "") + (f" · target {px(tgt)}" if tgt is not None else "")
                           + (f" · {usd(risk, False)} at risk" if risk else ""), "info", entry_t=et_, dir=d))
            legs = [x for x in (res.get("legs") or []) if isinstance(x, dict)]
            fill = next((_f(x.get("fill_px")) for x in legs if _f(x.get("fill_px")) is not None), None)
            pos = open_pos if (open_pos and _i(open_pos.get("entry_t")) == et_) else None
            if pos is not None and fill is None:
                b = pos.get("broker") or {}
                if b.get("filled") or not b:
                    fill = _f(pos.get("entry"))
            if fill is None and paper and ok is not False:
                fill = en
            if fill is not None:
                qty = _i((pos or {}).get("qty")) or q
                stop_now = _f((pos or {}).get("stop")) or stop
                risk = abs(fill - stop_now) * PV * qty if stop_now is not None else None
                win = abs(tgt - fill) * PV * qty if tgt is not None else None
                out.append(msg(f"{strat}:fill:{et_ or t}", max(t, et_ or 0), strat, "entry", f"{who}FILLED · {sw} {qty} {contract}{tag}",
                               f"Filled {sw} {qty} {contract} at {px(fill)}" + (f" · stop {px(stop_now)} ({usd(-risk)} if hit)" if risk else "")
                               + (f" · target {px(tgt)} ({usd(win)})" if win else ""), "good", entry_t=et_, dir=d, qty=qty,
                               fill=fill, stop=stop_now, target=tgt))
        elif side == "modify":
            reason = str(r.get("reason") or "")
            if ok is False:
                out.append(msg(f"{strat}:modfail:{et_}:{t}", t, strat, "stop", f"{who}stop move NOT confirmed",
                               f"The stop move to {px(r.get('stop'))} was not confirmed" + (f": {err}" if err else "")
                               + ". The old stop stays; check NinjaTrader.", "warn", entry_t=et_))
            elif reason == "BE":
                out.append(msg(f"{strat}:be:{et_}:{t}", t, strat, "be", f"{who}stop moved to breakeven",
                               f"+1R reached: stop moved to {px(r.get('stop'))} (entry + costs). This trade can no longer lose money.",
                               "good", entry_t=et_))
            else:
                out.append(msg(f"{strat}:stop:{et_}:{t}", t, strat, "stop", f"{who}stop moved", f"Stop moved to {px(r.get('stop'))}"
                               + (f" ({reason})" if reason else ""), "info", entry_t=et_))
        elif side == "add":
            out.append(msg(f"{strat}:add:{et_}:{t}", t, strat, "add", f"{who}scale-in add",
                           f"Added {q} {contract}" + (f" (refused: {err})" if ok is False else ""), "warn" if ok is False else "info",
                           entry_t=et_))
        elif side == "exit":
            reason = str(r.get("reason") or "").upper()
            pnl = _f(r.get("pnl"))
            words = EXIT_WORDS.get(reason, reason.lower() or "closed")
            if r.get("void"):
                text = f"Closed {q} {contract} ({words}): booked $0 — NinjaTrader never took this order (was {usd(r.get('pnl_void'))})."
            else:
                text = f"{words.capitalize()}: {usd(pnl) if pnl is not None else '$?'} real on {q} {contract}"
            if ok is False:
                text += f". The close was NOT confirmed ({err or 'no OK'}): check NinjaTrader now."
            lvl = "bad" if ok is False else "good" if (pnl or 0) > 0 else "warn" if (pnl or 0) < 0 else "info"
            out.append(msg(f"{strat}:exit:{et_}:{t}", t, strat, "exit", f"{who}EXIT {reason} {usd(pnl) if pnl is not None else ''}{tag}".strip(),
                           text, lvl, entry_t=et_, usd=pnl, reason=reason, qty=q, dir=dirs.get(et_)))
    return out


def _atlas_msgs(second: dict, day: str, prev_stage: dict) -> tuple[list, dict]:
    """ATLAS paper members (never routed from here): stage changes and their decisions (paper)."""
    out, stages = [], dict(prev_stage or {})
    if not isinstance(second, dict):
        return out, stages
    for k, s in (second.get("strategies") or {}).items():
        if not isinstance(s, dict) or s.get("on") is False or (s.get("candidate") and not str(k).startswith("scalp")):
            continue                                   # stop-hunt candidates stay off the feed (research, paper)
        strat = "scalp" if str(k).startswith("scalp") else "lit" if str(k).startswith("lit") else "atlas"
        st = s.get("state") or {}
        short = s.get("short") or k
        pre = "Zlarior paper" if strat == "lit" else "Strategy 3" if strat == "scalp" else "ATLAS"
        stg, txt = str(st.get("stage") or ""), str(st.get("text") or "")
        t = _i(second.get("t")) or 0
        if stg and stg != stages.get(k) and stg not in ("off",):
            out.append(msg(f"{strat}:{k}:{day}:stage:{stg}:{t // 300}", t, strat, "atlas", f"{pre} {short} · {stg}", txt, "info"))
        stages[k] = stg
        for x in ((s.get("brain") or {}).get("log") or []):
            if not isinstance(x, dict) or not x.get("t"):
                continue
            xt = _i(x["t"])
            if trading_day(xt) != day:
                continue
            good = bool(x.get("trade") or x.get("ok"))
            out.append(msg(f"{strat}:{k}:log:{xt}:{_h8(x.get('text'))}", xt, strat, "atlas", f"{pre} {short} (paper)",
                           str(x.get("text") or ""), "info" if good else "dim"))
        for tr in s.get("trades") or []:
            if not isinstance(tr, dict) or tr.get("day") != day or not tr.get("entry_t"):
                continue
            et_ = int(tr["entry_t"])
            out.append(msg(f"{strat}:{k}:paper:{et_}", et_, strat, "atlas", f"{pre} {short} paper entry · {side_word(tr.get('dir'))}",
                           f"Paper {side_word(tr.get('dir'))} at {px(tr.get('entry'))} · stop {px(tr.get('stop'))} · target {px(tr.get('target'))} "
                           "(paper: not on an account)", "info"))
            ek = str(tr.get("exit_kind") or "")
            if ek and ek != "OPEN" and tr.get("exit_t"):
                out.append(msg(f"{strat}:{k}:paperx:{et_}", int(tr["exit_t"]), strat, "atlas", f"{pre} {short} paper exit {ek}",
                               f"Paper {ek.lower()}: {float(tr.get('r') or 0):+.2f}R (paper: no real money)", "dim"))
    return out, stages


def _blitz_msgs(S: dict, day: str) -> list:
    """BLITZ (strategy 3, PAPER shadow, engine/blitz.py): today's signals, paper entries / exits, paper eval ends. Never routed."""
    out = []
    if not isinstance(S, dict) or not isinstance(S.get("ledger"), list):
        return out
    for x in S.get("signals") or []:
        if not isinstance(x, dict) or not x.get("t") or trading_day(int(x["t"])) != day:
            continue
        sw = side_word(x.get("dir"))
        word = "above" if _i(x.get("dir")) == 1 else "below"
        t = int(x.get("close_t") or int(x["t"]) + 60)
        if x.get("taken"):
            out.append(msg(f"scalp:blitz:sig:{int(x['t'])}", t, "scalp", "blitz", f"BLITZ PAPER signal · {sw}",
                           f"1m close {px(x.get('close'))} at {hm(t)} {word} the noise band {px(x.get('band'))}: PAPER {sw} at the next "
                           f"open, stop {px(x.get('stop'))} (1.5 x 5m ATR). Paper only: nothing is sent to an account.", "info", dir=_i(x.get("dir"))))
        else:
            out.append(msg(f"scalp:blitz:sig:{int(x['t'])}", t, "scalp", "blitz", f"BLITZ signal skipped · {sw}",
                           f"1m close {px(x.get('close'))} {word} the band {px(x.get('band'))}, not taken: {x.get('why')} (paper).", "dim"))
    for r in S["ledger"]:
        if not isinstance(r, dict) or not r.get("entry_t") or trading_day(int(r["entry_t"])) != day:
            continue
        et_, sw, q = int(r["entry_t"]), side_word(r.get("dir")), _i(r.get("qty")) or 0
        size = f"{q} MNQ" if q else "no eval size"
        out.append(msg(f"scalp:blitz:paper:{et_}", et_, "scalp", "blitz", f"BLITZ PAPER entry · {sw} {size}",
                       f"PAPER {sw} {size} at {px(r.get('entry'))} · stop {px(r.get('stop'))} · trail 1.5R after +1R · out by "
                       f"{hm(r.get('time_exit_t'))} at the latest" + (f" (simulated 25K eval: {q} micros)" if q else f" ({r.get('skip')})")
                       + ". Paper only: never sent to an account.", "info", entry_t=et_, dir=_i(r.get("dir")), qty=q or None, paper=True))
        ek = str(r.get("exit_kind") or "")
        if ek and ek != "OPEN" and r.get("exit_t"):
            u = _f(r.get("usd"))
            words = {"time": "closed after 30 minutes", "stop": "stopped out" if _f(r.get("r")) is not None and _f(r.get("r")) < 0
                     else "trailing stop hit", "flat": "closed 15:55 (flat)", "target": "target hit"}.get(ek, ek)
            out.append(msg(f"scalp:blitz:paperx:{et_}", int(r["exit_t"]), "scalp", "blitz", f"BLITZ PAPER exit {ek.upper()} {usd(u) if q else ''}".strip(),
                           f"Paper {words} at {px(r.get('exit'))}: " + (f"{usd(u)} on the paper eval" if q else "no eval size")
                           + f" ({float(r.get('r') or 0):+.2f}R). Paper only, no real money.",
                           "good" if (u or 0) > 0 else "warn" if (u or 0) < 0 else "dim", entry_t=et_, usd=u if q else None, paper=True))
    for e in S.get("events") or []:
        if isinstance(e, dict) and e.get("kind") == "eval" and e.get("day") == day:
            out.append(msg(f"scalp:blitz:eval:{e.get('n')}:{e.get('result')}", int(e.get("t") or 0), "scalp", "blitz",
                           f"BLITZ PAPER eval {e.get('n')} {e.get('result')}",
                           f"Simulated 25K eval {e.get('n')}: {e.get('result')} after {e.get('sessions')} sessions ({usd(e.get('profit'))}); "
                           "a new paper eval from the next session.", "info"))
    return out


def lit_window(now) -> dict:
    """Zlarior's entry window: 02:00-15:30 ET on a trading weekday. open / the next open / the close, seconds to it."""
    e = _et(now)
    mod = e.hour * 60 + e.minute
    wk = e.weekday() < 5
    if wk and 120 <= mod < 930:
        close = e.replace(hour=15, minute=30, second=0, microsecond=0)
        return {"open": True, "label": "Entry window open until 15:30 ET", "t": int(close.timestamp()), "secs": int(close.timestamp() - now)}
    d = e.date() if (wk and mod < 120) else e.date() + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    nxt = dt.datetime(d.year, d.month, d.day, 2, 0, tzinfo=ET)
    return {"open": False, "label": f"Next entry window {nxt:%a} 02:00 ET", "t": int(nxt.timestamp()), "secs": int(nxt.timestamp() - now)}


def derive(bot, now=None, prev: dict | None = None) -> tuple[list, dict]:
    """(messages, state) from one look at the bot; prev = the last state (stage per ATLAS member, feed stale episode,
    kill). Pure apart from reading the bot. Never raises (a failing part is skipped)."""
    prev = dict(prev or {})
    now = int(now if now is not None else (bot.clock() if callable(getattr(bot, "clock", None)) else time.time()))
    day = trading_day(now)
    out, state = [], {"atlas": prev.get("atlas") or {}, "stale_since": prev.get("stale_since"), "kill": prev.get("kill")}
    ledger = [r for r in list(getattr(bot, "ledger", None) or []) if isinstance(r, dict) and r.get("t")]
    today = [r for r in ledger if trading_day(int(r["t"])) == day]
    account = "Paper"
    try:
        account = bot._push_account() if callable(getattr(bot, "_push_account", None)) else "Paper"
    except Exception:
        pass
    paper = str((getattr(bot, "cfg", None) or {}).get("adapter") or "paper") == "paper"
    open_pos = None
    try:
        from .accounts import _position
        open_pos = _position(bot)
    except Exception:
        pass
    real_entries = {_i(r.get("entry_t")) for r in ledger if r.get("side") in ("buy", "sell")}
    # LIT: the Brain's log
    try:
        out += [m for m in _brain_msgs(getattr(bot, "brain", None), real_entries) if trading_day(m["t"] or now) == day]
    except Exception:
        pass
    # routed orders on LIT's account (src set = a second strategy routed there)
    try:
        lit_rows = [r for r in today if not r.get("src")]
        sec_rows = [r for r in today if r.get("src")]
        out += _route_rows(lit_rows, "lit", account, open_pos if not getattr(bot, "_open_src", None) else None, paper)
        out += _route_rows(sec_rows, "atlas", account, open_pos if getattr(bot, "_open_src", None) else None, paper)
    except Exception:
        pass
    # account B (ATLAS on its own account)
    try:
        ab = getattr(bot, "acct_b", None)
        if ab is not None:
            info = ab.info(now)
            rows = [r for r in (info.get("routed") or []) if r.get("t") and trading_day(int(r["t"])) == day]
            out += _route_rows(rows, "atlas", info.get("label") or "Account B", None, False)
    except Exception:
        pass
    # ATLAS paper members
    try:
        am, state["atlas"] = _atlas_msgs(getattr(bot, "second", None), day, prev.get("atlas") or {})
        out += am
    except Exception:
        pass
    # BLITZ, the scalper PAPER shadow (strategy 3)
    try:
        out += _blitz_msgs(getattr(bot, "blitz", None), day)
    except Exception:
        pass
    # feed stale episodes, kill switch (only while the bot runs)
    try:
        h = getattr(bot, "health", None) or {}
        running = bool(getattr(bot, "running", False))
        stale = running and bool(h.get("stale")) and h.get("market_open", True) is not False
        if stale and not state.get("stale_since"):
            state["stale_since"] = now
            age = h.get("data_age_s")
            out.append(msg(f"sys:stale:{now}", now, "sys", "stale", "FEED STALE · new entries blocked",
                           "NinjaTrader's bars stopped arriving" + (f" (last bar {int(age) // 60} min old)" if age else "")
                           + ". No new entries until the feed is back; an open trade keeps its stop and target at NinjaTrader.", "bad"))
        elif not stale and state.get("stale_since"):
            since = int(state["stale_since"])
            out.append(msg(f"sys:fresh:{since}", now, "sys", "fresh", "Feed back",
                           f"NinjaTrader bars are arriving again (stale {max(1, (now - since) // 60)} min). Entries allowed again.", "good"))
            state["stale_since"] = None
        k = bool(getattr(bot, "kill", False))
        if k and not state.get("kill"):
            out.append(msg(f"sys:kill:{day}", now, "sys", "kill", "KILL SWITCH", "The kill switch fired: positions flattened, no new "
                           "orders until you restart the bot.", "bad"))
        state["kill"] = k
    except Exception:
        pass
    # daily summary: once, after the 15:55 flat (16:05-17:00 ET on a trading weekday)
    try:
        e = _et(now)
        if e.weekday() < 5 and 965 <= e.hour * 60 + e.minute < 1020:
            out.append(summary(bot, day, today, now))
    except Exception:
        pass
    return out, state


def summary(bot, day, today_rows, now) -> dict:
    exits = [r for r in today_rows if r.get("side") == "exit" and not r.get("src")]
    real = sum(float(r.get("pnl") or 0) for r in exits)
    b = getattr(bot, "brain", None) or {}
    setups = [s for s in (b.get("setups") or []) if isinstance(s, dict)] if b.get("day") == day else []
    rej = [s for s in setups if s.get("status") == "rejected"]
    why = {}
    for s in rej:
        why[s.get("rule") or "?"] = why.get(s.get("rule") or "?", 0) + 1
    parts = [f"Zlarior: {len(exits)} trade{'s' if len(exits) != 1 else ''}, {usd(real)} real"
             + (" (" + ", ".join(f"{str(r.get('reason') or '').upper()} {usd(r.get('pnl'))}" for r in exits[:3]) + ")" if exits else "")]
    if setups:
        parts.append(f"{len(setups)} setups seen, {sum(1 for s in setups if s.get('status') == 'armed' or s.get('plan'))} armed, "
                     f"{len(rej)} rejected" + (" (" + ", ".join(f"{k} x{v}" for k, v in sorted(why.items(), key=lambda kv: -kv[1])[:3]) + ")" if why else ""))
    try:
        ab = getattr(bot, "acct_b", None)
        if ab is not None:
            info = ab.info(now)
            parts.append(f"ATLAS ({info.get('label') or 'account B'}): {info.get('entries_today') or 0} entries, {usd(info.get('day_pnl') or 0)} real")
    except Exception:
        pass
    sec = getattr(bot, "second", None) or {}
    n_paper = sum(1 for s in (sec.get("strategies") or {}).values() if isinstance(s, dict)
                  for tr in (s.get("trades") or []) if isinstance(tr, dict) and tr.get("day") == day)
    if sec:
        parts.append(f"ATLAS paper: {n_paper} trade{'s' if n_paper != 1 else ''}")
    bz = getattr(bot, "blitz", None)
    if isinstance(bz, dict) and isinstance(bz.get("ledger"), list):
        rows = [r for r in bz["ledger"] if isinstance(r, dict) and r.get("entry_t") and trading_day(int(r["entry_t"])) == day]
        parts.append(f"BLITZ paper: {len(rows)} trade{'s' if len(rows) != 1 else ''}, "
                     f"{usd(sum(float(r.get('usd') or 0) for r in rows))} on the paper eval")
    return msg(f"sys:summary:{day}", now, "sys", "summary", f"Day summary {day}", " · ".join(parts), "info")


# ---------------------------------------------------------------------------------------------- the running feed
class Narrator:
    def __init__(self, log_dir: str | None = None, keep: int = KEEP):
        self.mx = threading.Lock()
        self.items: deque = deque(maxlen=keep)
        self.keys: set = set()
        self.seq = 0
        self.state: dict = {}
        self.day = None
        self.log_dir = log_dir                   # None = memory only (tests, the API's own look); tick() sets it for the real bot
        self._restored = set()

    # ---- persistence (real bot only)
    def _path(self, day):
        return os.path.join(self.log_dir, f"{day}.jsonl") if self.log_dir else None

    def _restore(self, day):
        p = self._path(day)
        if not p or day in self._restored:
            return
        self._restored.add(day)
        try:
            with open(p, encoding="utf-8") as fh:
                rows = [json.loads(x) for x in fh if x.strip()]
        except Exception:
            return
        for m in rows:
            if isinstance(m, dict) and m.get("key") and m["key"] not in self.keys:
                self.keys.add(m["key"])
                self.seq += 1
                self.items.append({**m, "id": self.seq})

    def _write(self, day, rows):
        p = self._path(day)
        if not p or not rows:
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a", encoding="utf-8") as fh:
                for m in rows:
                    fh.write(json.dumps({k: v for k, v in m.items() if k != "id"}, separators=(",", ":"), default=str) + "\n")
        except Exception:
            pass

    def enable_files(self, log_dir: str = LOG_DIR):
        with self.mx:
            if self.log_dir == log_dir:
                return
            self.log_dir = log_dir
            if self.day:
                self._restore(self.day)
                self._write(self.day, [m for m in self.items if trading_day(m.get("t") or 0) == self.day])

    # ---- one look
    def observe(self, bot, now=None, push: bool = False, send=None, prefs: dict | None = None) -> list:
        """Derive, keep what is new (by key), return the new messages (oldest first). push: the important kinds go to the
        phone through send(msg, bot) (default: the bot's own push path). Never raises."""
        try:
            now = int(now if now is not None else (bot.clock() if callable(getattr(bot, "clock", None)) else time.time()))
            day = trading_day(now)
            with self.mx:
                if day != self.day:
                    self.day = day
                    self._restore(day)
                prev = dict(self.state)
            msgs, st = derive(bot, now, prev)
            new = []
            with self.mx:
                self.state = st
                for m in sorted(msgs, key=lambda m: (m.get("t") or 0)):
                    if m["key"] in self.keys:
                        continue
                    self.keys.add(m["key"])
                    self.seq += 1
                    m = {**m, "id": self.seq, "at": now}
                    self.items.append(m)
                    new.append(m)
                if len(self.keys) > 20000:
                    self.keys = {m["key"] for m in self.items}
                self._write(day, new)
            if push and new:
                pf = prefs if prefs is not None else push_prefs()
                for m in new:
                    if pf.get(m["kind"]) and now - int(m.get("t") or now) <= PUSH_FRESH_S:
                        try:
                            m["pushed"] = bool((send or send_push)(m, bot))
                        except Exception:
                            m["pushed"] = False
            return new
        except Exception:
            return []

    def feed(self, n: int = 100, after: int | None = None, strat: str | None = None) -> list:
        with self.mx:
            rows = list(self.items)
        if after is not None:
            rows = [m for m in rows if m["id"] > after]
        if strat:
            rows = [m for m in rows if m.get("strat") == strat]
        rows.sort(key=lambda m: ((m.get("t") or 0), m["id"]), reverse=True)
        return rows[:max(1, min(int(n or 100), KEEP))]


def payload_for(m: dict, account: str = "") -> tuple[dict | None, str]:
    """(push payload, route) for one message: entries / exits as the bot's standard entry / outcome payloads (same keys
    fill:<t> / out:<t>: the phone shows one notice per trade), setups armed with alerts_plus's key, refusals as risk."""
    from . import push
    k = m.get("kind")
    if k == "entry" and m.get("entry_t"):
        p = push.entry_payload(account, side_word(m.get("dir")), m.get("qty"), m["entry_t"], src="pc", entry=m.get("fill"),
                               stop=m.get("stop"), target=m.get("target"))
        if m.get("strat") == "atlas":
            p["body"] += " (ATLAS)"
        return p, "notify"
    if k == "exit" and m.get("entry_t"):
        return push.outcome_payload(account, side_word(m.get("dir")) if m.get("dir") else "", m.get("reason"), m.get("usd") or 0, m["entry_t"], m.get("t"), src="pc",
                                    qty=m.get("qty")), "notify"
    key = m.get("push_key") or f"nar:{m['key']}"
    kind = {"armed": "armed", "expired": "armed", "refused": "risk", "stale": "feed_stale"}.get(k, "narrator")
    p = push.text_payload("PC", kind, m.get("title") or "", m.get("text") or "", key=key, t=m.get("t"), url="#/liveview")
    return p, "plus"


def send_push(m: dict, bot) -> bool:
    """Through the bot's existing paths: entries / exits via LiveBot._push_send (engine/push.pc_notify), the rest via
    engine/alerts_plus.pc_send (the phone's alert levels apply). De-duplicated by key there. Never raises."""
    try:
        acct = ""
        try:
            acct = bot._push_account() if m.get("strat") != "atlas" else ""
        except Exception:
            pass
        if m.get("strat") == "atlas":
            try:
                acct = (bot.acct_b.info() or {}).get("label") or acct
            except Exception:
                pass
        p, route = payload_for(m, acct)
        if p is None:
            return False
        if route == "notify" and callable(getattr(bot, "_push_send", None)):
            return bool(bot._push_send(p))
        from . import alerts_plus
        return bool(alerts_plus.pc_send(p))
    except Exception:
        return False


NARRATOR = Narrator()


def tick(bot, now=None) -> list:
    """LiveBot._alerts_tick hook (real bot only): today's feed kept in logs/narrator/<day>.jsonl, pushes on. Never raises."""
    if os.environ.get("LE_NARRATOR", "1") == "0":
        return []
    try:
        NARRATOR.enable_files(LOG_DIR)
        return NARRATOR.observe(bot, now, push=True)
    except Exception:
        return []
