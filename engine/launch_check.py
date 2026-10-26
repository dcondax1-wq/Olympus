"""Launch checklist (2026-10-25, launch 18:00 ET): one green / red line per thing the owner's launch needs, each red line
with the one command that fixes it. Read-only: it only reads files and the bot's state; it never arms, starts, routes or
sizes anything. The single file it knows how to write is the Sim roundtrip result (data/sim_roundtrip_last.json, written by
`python -m engine.ninjatrader --sim-roundtrip` / `--sim-roundtrip-add` through save_sim_result).

  facts(bot, health)        PC side: the raw facts (anchor numbers, allowlist hits, account B, startup reconcile, Sim results,
                            armed flags, bot start time) as a small secret-free dict (no balances beyond the anchor the
                            dashboard already shows, no paths, no phrases)
  checklist(facts, health, running, now)   the items: [{"key", "label", "state" good|bad|wait|info, "detail", "fix"}],
                            "all_green" (every item but the display-only ones good), "n_red"
  block(bot, health)        heartbeat.json / live.json "launch" = {**checklist, "facts": facts}

The phone (tools/web_public/launch.js) and the PC Command center (web_next/js/next/cc.js) only draw these items; the phone
turns the PC items red itself when the heartbeat is older than 20 minutes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
SIM_RESULT = os.path.join(ROOT, "data", "sim_roundtrip_last.json")      # gitignored (data/)
AUTOSTART = os.path.join(ROOT, "data", "autostart.json")
SIM_MAX_AGE_S = 7 * 86400
UP_FROM = (1, 55)                                                        # ET: the bot must be running from 01:55
VERSION = 1

START_CMD = r"powershell -ExecutionPolicy Bypass -File scripts\run_bot.ps1"
STATUS_CMD = "python -m engine.ninjatrader --status"
PREP_CMD = 'python -m engine.launch_prep --atlas "{b}"'
ALLOW_CMD = 'python -m engine.ninjatrader --allow-account "{n}"'
RESET_CMD = "python -m engine.ninjatrader --confirm-reset"
RT_CMD = "python -m engine.ninjatrader --sim-roundtrip"
RT_ADD_CMD = "python -m engine.ninjatrader --sim-roundtrip-add"


def _clean(s, n=160):
    try:
        from .accounts import clean_text
        return clean_text(s, n)
    except Exception:
        return None if s is None else str(s)[:n]


def _is_sim(name) -> bool:
    try:
        from .ninjatrader import is_sim
        return bool(is_sim(name))
    except Exception:
        return str(name or "").lower().startswith(("sim", "playback"))


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the Sim result file
def save_sim_result(kind: str, ok: bool, account: str | None, steps=None, path: str | None = None, now=None) -> dict | None:
    """Write one Sim roundtrip result ("roundtrip" or "add") into data/sim_roundtrip_last.json (temp file + rename).
    The only write of this module. Never raises: None when it could not write."""
    if kind not in ("roundtrip", "add"):
        return None
    p = path or SIM_RESULT
    try:
        d = _read_json(p) or {}
        rec = {"t": int(now or time.time()), "ok": bool(ok), "account": _clean(account, 60),
               "steps": [_clean(s, 120) for s in (steps or [])][:8]}
        d["v"] = 1
        d[kind] = rec
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, p)
        return rec
    except Exception:
        return None


def load_sim_result(path: str | None = None) -> dict:
    d = _read_json(path or SIM_RESULT) or {}
    out = {}
    for k in ("roundtrip", "add"):
        r = d.get(k)
        if isinstance(r, dict):
            out[k] = {"t": r.get("t"), "ok": bool(r.get("ok")), "account": _clean(r.get("account"), 60)}
    return out


# ------------------------------------------------------------------------------------------------ PC facts
def _lit_name(bot, health) -> str | None:
    acc = (health or {}).get("account") or {}
    if acc.get("adapter") == "ninjatrader" and acc.get("name"):
        return str(acc["name"])
    cfg = getattr(bot, "cfg", None) or {}
    if cfg.get("nt_account"):
        return str(cfg["nt_account"])
    a = _read_json(AUTOSTART) or {}
    return (str(a.get("nt_account") or "").strip() or None)


def facts(bot, health: dict | None = None, now=None, sim_path: str | None = None, second_path: str | None = None,
          allow_path: str | None = None, anchor_path: str | None = None) -> dict:
    """The raw launch facts on the PC. Never raises (a broken part is None / an "error" text)."""
    now = int(now or time.time())
    h = health or {}
    out = {"v": VERSION, "t": now}
    lit = _lit_name(bot, h)
    out["lit_account"] = _clean(lit, 60)
    # 1. the 50K eval anchor (engine/eval_life.py; the numbers the launch loads: balance 49,710.80, floor 48,168.20)
    try:
        from . import eval_life
        a = eval_life.load_anchor(lit, path=anchor_path)
        out["anchor"] = {"set": a is not None, **({k: a.get(k) for k in ("balance", "floor", "as_of", "set_t")} if a else {})}
    except Exception as e:
        out["anchor"] = {"set": False, "error": _clean(f"{e.__class__.__name__}: {e}", 120)}
    # 2. account B (second_model.json "account_b")
    b = None
    try:
        from . import account_b as _ab
        ab = _ab.raw_cfg(second_path)                 # data/account_b.json first, else second_model.json's
        ab = ab if isinstance(ab, dict) else None
        if ab:
            b = str(ab.get("account") or "").strip() or None
        out["b"] = {"configured": bool(b), "account": _clean(b, 60),
                    "plan": _clean((ab or {}).get("plan"), 30), "eval_start": _clean((ab or {}).get("eval_start"), 12),
                    "armed": bool((ab or {}).get("armed") is True), "running": getattr(bot, "acct_b", None) is not None}
    except Exception as e:
        out["b"] = {"configured": False, "error": _clean(f"{e.__class__.__name__}: {e}", 120)}
    # 3. allowlist: is each real account listed (a Sim account never needs it)
    try:
        from . import ninjatrader
        allowed = ninjatrader.allowed_accounts(allow_path)
        out["allow"] = {"n": len(allowed),
                        "lit": None if not lit else (True if _is_sim(lit) else lit in allowed), "lit_sim": bool(lit and _is_sim(lit)),
                        "b": None if not b else (True if _is_sim(b) else b in allowed), "b_sim": bool(b and _is_sim(b))}
    except Exception as e:
        out["allow"] = {"n": 0, "lit": None, "b": None, "error": _clean(f"{e.__class__.__name__}: {e}", 120)}
    # 4. startup reconcile (engine/guards.startup_tick: bot.health["startup"], latched in bot._startup_ok)
    st = dict(((getattr(bot, "health", None) or {}).get("startup")) or {})
    since = getattr(bot, "_startup_ok", None) or st.get("since")
    out["startup"] = {"ok": bool(since or st.get("ok")), "since": int(since) if since else None,
                      "problems": [_clean(p, 160) for p in (st.get("problems") or [])][:4]}
    # 5. Sim roundtrips (data/sim_roundtrip_last.json)
    out["sim"] = load_sim_result(sim_path)
    # 5b. real balance from NinjaTrader (engine/broker_balance.py: le_feed/accounts.csv from LE_BarFeed), the LIT account's row
    try:
        out["broker"] = broker_fact(bot, lit, now)
    except Exception as e:
        out["broker"] = {"fresh": False, "why": _clean(f"{e.__class__.__name__}: {e}", 120)}
    # 5c. the chart's contract against the order contract (engine/roll_watch.py: the December 2026 roll, 12-26 -> 03-27)
    try:
        from . import roll_watch
        out["roll"] = roll_watch.compact(roll_watch.fact(cfg=getattr(bot, "cfg", None) or {}, now=now))
    except Exception as e:
        out["roll"] = {"level": "unknown", "say": _clean(f"roll check failed: {e.__class__.__name__}", 120)}
    # 6. armed (display only) and the bot's start time
    out["lit_armed"] = bool(((h.get("account") or {}).get("armed")) or (getattr(bot, "cfg", None) or {}).get("armed"))
    sa = getattr(bot, "started_at", None)
    out["bot_started_t"] = int(sa) if sa and getattr(bot, "running", False) else None
    return out


def broker_fact(bot, lit, now, path: str | None = None) -> dict:
    """{"fresh", "cash", "equity", "age_s", "why", "floor", "room"} of the LIT account's accounts.csv row."""
    from . import broker_balance as bb
    cfg = getattr(bot, "cfg", None) or {}
    if path is None:
        from .ninjatrader import default_folder
        path = cfg.get("broker_balance_file") or os.path.join(cfg.get("nt_folder") or default_folder(), bb.FEED_DIR, bb.FILE)
    s = bb.read(now=now, path=path)
    if not lit:
        return {"fresh": False, "why": "no NinjaTrader account for LIT yet"}
    if bb.SIM.match(str(lit)):
        return {"fresh": False, "why": f"{lit} is a Sim account: its balance is not the eval's"}
    r = s["rows"].get(str(lit))
    if r is None:
        return {"fresh": False, "why": s["why"] or f"no row for {lit} in accounts.csv"}
    ok, why = bb.sane(r, bb.R50K)
    out = {"fresh": bool(r["fresh"] and ok), "cash": r["cash"], "equity": round(bb.real_equity(r), 2), "age_s": int(r["age_s"]),
           "why": "" if r["fresh"] and ok else (why or f"accounts.csv row is {int(r['age_s'])} s old")}
    try:
        st = bot.eval_state() if callable(getattr(bot, "eval_state", None)) else None
        b = (st or {}).get("broker")
        if b:
            out.update(floor=b["floor"], room=b["room"])
    except Exception:
        pass
    return out


# ------------------------------------------------------------------------------------------------ the items
def _item(key, label, state, detail, fix=""):
    return {"key": key, "label": label, "state": state, "detail": _clean(detail, 220), "fix": fix or ""}


def _usd(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "?"


def up_from_t(now: int) -> int:
    """01:55 ET of the trading day now belongs to (after 18:00 ET: the next weekday's)."""
    e = dt.datetime.fromtimestamp(int(now), ET)
    d = e.date()
    if e.hour >= 18:
        d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return int(dt.datetime(d.year, d.month, d.day, UP_FROM[0], UP_FROM[1], tzinfo=ET).timestamp())


def checklist(f: dict | None, health: dict | None, running: bool, now=None) -> dict:
    """The checklist from the facts + the heartbeat's health block (engine/accounts.pc_health). Pure: no I/O."""
    now = int(now or time.time())
    f = f or {}
    h = health or {}
    items = []
    b = f.get("b") or {}
    bname = b.get("account") or "<25K Name>"
    prep = PREP_CMD.format(b=bname)
    # 1. eval anchor
    a = f.get("anchor") or {}
    if a.get("set"):
        items.append(_item("anchor", "50K eval anchor", "good",
                           f"balance {_usd(a.get('balance'))}, floor {_usd(a.get('floor'))} (as of {a.get('as_of')})"))
    else:
        items.append(_item("anchor", "50K eval anchor", "bad", "not set: the bot does not know the 50K's real balance and floor yet "
                           "(launch: 49,710.80 / 48,168.20)", prep))
    # 2. allowlist
    al = f.get("allow") or {}
    lit = f.get("lit_account")
    miss = []
    if al.get("lit") is not True:
        miss.append(lit or "the 50K")
    if al.get("b") is not True:
        miss.append(b.get("account") or "the 25K")
    if not miss:
        items.append(_item("allow", "Allowlist has both accounts", "good",
                           f"{lit} and {b.get('account')} may receive orders ({al.get('n', 0)} listed)"))
    else:
        one = [m for m in miss if m not in ("the 50K", "the 25K")]
        fix = ALLOW_CMD.format(n=one[0]) if len(miss) == 1 and one else prep
        items.append(_item("allow", "Allowlist has both accounts", "bad", f"not listed yet: {', '.join(miss)}", fix))
    # 3. account B
    if b.get("configured"):
        items.append(_item("b", "Account B (ATLAS) set up", "good",
                           f"ATLAS on {b.get('account')}, {b.get('plan') or 'builder25k'}, first session {b.get('eval_start') or '?'}"))
    else:
        items.append(_item("b", "Account B (ATLAS) set up", "bad", "ATLAS has no account yet (second_model.json account_b)", prep))
    # 4. startup reconciled
    st = f.get("startup") or {}
    if not running:
        items.append(_item("startup", "Startup reconciled", "bad", "the bot is not running", START_CMD))
    elif st.get("ok"):
        t = st.get("since")
        items.append(_item("startup", "Startup reconciled", "good", "STARTUP RECONCILED"
                           + (f" at {dt.datetime.fromtimestamp(int(t), ET):%H:%M} ET" if t else "")))
    elif st.get("problems") and all("clock check" in str(p).lower() and "running" in str(p).lower() for p in st["problems"]):
        items.append(_item("startup", "Startup reconciled", "wait", "the PC clock check against internet time is still running "
                           "(a minute or two after the start)"))
    elif st.get("problems"):
        pr = "; ".join(st["problems"])
        lo = pr.lower()
        fix = RESET_CMD if "restart" in lo or "reset" in lo else prep if "anchor" in lo else START_CMD if "disabled" in lo else STATUS_CMD
        items.append(_item("startup", "Startup reconciled", "bad", "STARTUP DISARMED: " + pr, fix))
    else:
        items.append(_item("startup", "Startup reconciled", "wait", "waiting for the first check (a poll or two)"))
    # 5. NinjaTrader connected
    nt = h.get("nt") or {}
    acc = h.get("account") or {}
    if not running:
        items.append(_item("nt", "NinjaTrader connected", "bad", "the bot is not running", START_CMD))
    elif acc.get("adapter") != "ninjatrader":
        items.append(_item("nt", "NinjaTrader connected", "bad", f"the bot runs on {acc.get('adapter') or 'paper'}, not NinjaTrader",
                           STATUS_CMD))
    elif nt.get("connected"):
        conns = nt.get("connections") or {}
        items.append(_item("nt", "NinjaTrader connected", "good", ", ".join(f"{k} {v}" for k, v in conns.items()) or "connected"))
    else:
        items.append(_item("nt", "NinjaTrader connected", "bad", "no CONNECTED connection: Control Center > Connections, connect "
                           "your login", STATUS_CMD))
    # 6. feed fresh
    fd = h.get("feed") or {}
    a1, a5 = fd.get("age_1m_s"), fd.get("age_5m_s")
    ages = f"1m {'?' if a1 is None else f'{int(a1)} s'} · 5m {'?' if a5 is None else f'{int(a5)} s'} old"
    if not running:
        items.append(_item("feed", "Bar feed fresh", "bad", "the bot is not running", START_CMD))
    elif fd.get("stale") or fd.get("entries_blocked"):
        items.append(_item("feed", "Bar feed fresh", "bad", (fd.get("block") or "FEED STALE: new entries blocked")
                           + ": open the MNQ chart with LE_BarFeed", STATUS_CMD))
    elif fd.get("market_open") is False:
        items.append(_item("feed", "Bar feed fresh", "wait", f"market closed: checked again from 18:00 ET ({ages})"))
    elif a1 is not None and a1 <= 180 or a5 is not None and a5 <= 600:
        items.append(_item("feed", "Bar feed fresh", "good", f"{fd.get('used') or fd.get('source') or 'ninjatrader'}: {ages}"))
    else:
        items.append(_item("feed", "Bar feed fresh", "bad", f"no fresh bar ({ages}): open the MNQ chart with LE_BarFeed", STATUS_CMD))
    # 6a. the chart on the order contract (red after the roll day while the LE_BarFeed chart is still on the old month: the
    #     adapter sends no new entry then); info while the roll is within 7 days or the contract is unknown
    try:
        from . import roll_watch
        ri = roll_watch.launch_item(f.get("roll"))
    except Exception as e:
        ri = {"key": "roll", "label": "Chart contract (roll)", "state": "info", "detail": f"not checked ({e.__class__.__name__})",
              "fix": ""}
    items.append(_item(ri["key"], ri["label"], ri["state"], ri["detail"], ri["fix"]))
    # 6b. real balance from NinjaTrader: green when fresh; otherwise display only (the bot then sizes from its ledger + the
    #     anchor exactly as before, so it never blocks the launch)
    bk = f.get("broker") or {}
    if bk.get("fresh"):
        extra = (f", floor {_usd(bk['floor'])}, room {_usd(bk['room'])}" if bk.get("floor") is not None and bk.get("room") is not None
                 else "")
        items.append(_item("broker", "Real balance from NinjaTrader", "good",
                           f"balance {_usd(bk.get('equity'))}{extra} ({bk.get('age_s')} s old)"))
    else:
        items.append(_item("broker", "Real balance from NinjaTrader", "info",
                           f"not used: {bk.get('why') or 'no accounts.csv'}; the bot sizes from its ledger + the anchor "
                           "(compile the new LE_BarFeed: ninjatrader/SETUP.md)"))
    # 7. Sim roundtrips (data/sim_roundtrip_last.json)
    sim = f.get("sim") or {}
    for key, kind, label, cmd in (("sim", "roundtrip", "Sim roundtrip", RT_CMD), ("sim_add", "add", "Sim roundtrip + add", RT_ADD_CMD)):
        r = sim.get(kind)
        if not r or not r.get("t"):
            items.append(_item(key, label, "bad", "not run yet (stop the bot first, Sim101, market open)", cmd))
            continue
        when = dt.datetime.fromtimestamp(int(r["t"]), ET).strftime("%a %b %d %H:%M ET")
        old = now - int(r["t"]) > SIM_MAX_AGE_S
        if r.get("ok") and not old:
            items.append(_item(key, label, "good", f"PASSED on {r.get('account') or 'Sim'} {when}"))
        else:
            items.append(_item(key, label, "bad", (f"FAILED on {r.get('account') or 'Sim'} {when}" if not r.get("ok")
                                                   else f"last pass {when} is older than 7 days"), cmd))
    # 8. armed (display only: the owner arms both accounts himself)
    la, ba = bool(f.get("lit_armed")), bool(b.get("armed"))
    items.append(_item("armed", "Armed (you do this)", "info",
                       f"50K {'ARMED' if la else 'not armed'} · 25K {'ARMED' if ba else 'not armed'}: you arm both yourself "
                       "(docs/GO_LIVE_TONIGHT.md); the bot never arms"))
    # 9. PC up from 01:55 ET
    t0 = up_from_t(now)
    started = f.get("bot_started_t")
    hhmm = dt.datetime.fromtimestamp(t0, ET).strftime("%a %H:%M ET")
    if not running:
        items.append(_item("up", "Bot running from 01:55 ET", "bad", f"the bot is not running; it must be up by {hhmm}", START_CMD))
    elif now < t0:
        items.append(_item("up", "Bot running from 01:55 ET", "good", f"running; leave the PC on through {hhmm} (entries from 02:00)"))
    elif started and int(started) <= t0:
        items.append(_item("up", "Bot running from 01:55 ET", "good", f"running since before {hhmm}"))
    else:
        items.append(_item("up", "Bot running from 01:55 ET", "bad", f"the bot (re)started after {hhmm}" if started else
                           "start time unknown", START_CMD))
    counted = [i for i in items if i["state"] != "info"]
    return {"v": VERSION, "t": now, "items": items, "all_green": all(i["state"] == "good" for i in counted),
            "n_red": sum(1 for i in counted if i["state"] == "bad"), "n_wait": sum(1 for i in counted if i["state"] == "wait"),
            "n": len(counted)}


def block(bot, health: dict | None = None, now=None) -> dict:
    """The heartbeat / live.json "launch" block. Never raises."""
    try:
        now = int(now or time.time())
        f = facts(bot, health, now)
        return {**checklist(f, health, bool(getattr(bot, "running", False)), now), "facts": f}
    except Exception as e:
        return {"v": VERSION, "error": _clean(f"{e.__class__.__name__}: {e}", 160)}
