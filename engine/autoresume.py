"""Auto-resume of a REAL NinjaTrader account (owner opt-in, owner 2026-10-19: MFFU / Lucid confirmed unattended automation).

The owner turns it on once himself, on the PC:
  python -m engine.ninjatrader --enable-auto-resume --account "<eval Name>" --confirm "<the live phrase>"
and off with
  python -m engine.ninjatrader --disable-auto-resume       (the kill switch / HOLD TO KILL also turn it off)

The opt-in (data/auto_resume.json, gitignored) holds the account, the date it was accepted and a SHA-256 of
account|date|phrase (proof the exact phrase was typed; the phrase itself is never stored, logged or printed). On a server
start (its own crash, an auto-update restart, a Windows reboot through the logon task) server.py's autostart asks
decide(): the bot resumes on that account only when ALL of these hold:
  * the opt-in is on, its proof checks out, and the last start (data/autostart.json, cleared by Stop and the kill switch)
    was on exactly that account: an intentional Stop stays stopped;
  * NINJATRADER_LIVE=1 is in the server's environment (.env.local.ps1), so every existing live lock still applies;
  * no kill flag today, no daily-loss event today (routed P&L <= -$1,000), no failed start in the last 10 minutes;
  * NinjaTrader reports a CONNECTED connection (waits up to 30 min for it after a reboot, then gives up with an alert).
Every resume pushes "Bot resumed on <account> after <reason>"; every refusal pushes why.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTIN_PATH = os.path.join(ROOT, "data", "auto_resume.json")          # gitignored, never committed
LIVE_ENV = "NINJATRADER_LIVE"
FAIL_COOLDOWN_S = 600
DAILY_LOSS_USD = 1000.0
CONNECT_WAIT_S = 30 * 60


def _phrase() -> str:
    from .tradovate import LIVE_PHRASE
    return LIVE_PHRASE


def _proof(account: str, day: str, phrase: str) -> str:
    return hashlib.sha256(f"{account}|{day}|{phrase}".encode("utf-8")).hexdigest()


def _is_sim(account: str) -> bool:
    from .ninjatrader import is_sim
    return is_sim(account)


def _et_day(now) -> str:
    return dt.datetime.fromtimestamp(float(now), ET).date().isoformat()


# ---------------------------------------------------------------------- the opt-in record
def load(path: str = OPTIN_PATH) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        return r if isinstance(r, dict) else None
    except FileNotFoundError:
        return None
    except Exception:
        return {"_corrupt": True}


def _write(rec: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    os.replace(tmp, path)


def enable(account: str, confirm: str, cfg: dict | None = None, now=None, path: str = OPTIN_PATH) -> dict:
    """The owner's one-time opt-in. Raises ValueError when the account or the phrase is not right."""
    now = time.time() if now is None else now
    account = (account or "").strip()
    if not account or any(c in account for c in ";\r\n|"):
        raise ValueError("give the exact NinjaTrader account Name with --account")
    if _is_sim(account):
        raise ValueError(f"{account} is a Sim account: it already resumes by itself, nothing to enable")
    if (confirm or "").strip() != _phrase():
        raise ValueError("the confirm phrase is missing or not exact")
    from .watchdog import sanitize
    day = _et_day(now)
    rec = {"v": 1, "enabled": True, "account": account, "accepted_on": day, "accepted_at": int(now),
           "proof": _proof(account, day, _phrase()),
           "cfg": sanitize(dict(cfg or {}), phrases=(_phrase(),)), "last_fail_at": None, "last_resume": None}
    _write(rec, path)
    return rec


def enable_extra(account: str, confirm: str, now=None, path: str = OPTIN_PATH) -> dict:
    """Several accounts (engine/multi_account.py): add one EXTRA real account to the opt-in, with its own proof. The bot's
    own account must be opted in first. Raises ValueError when the account or the phrase is not right."""
    now = time.time() if now is None else now
    rec = load(path)
    if not valid(rec):
        raise ValueError("turn auto-resume on for the bot's own account first (--enable-auto-resume --account <eval Name>)")
    account = (account or "").strip()
    if not account or any(c in account for c in ";\r\n|"):
        raise ValueError("give the exact NinjaTrader account Name with --account")
    if _is_sim(account):
        raise ValueError(f"{account} is a Sim account: it already resumes by itself, nothing to enable")
    if account == rec.get("account"):
        raise ValueError(f"{account} is the bot's own account (already on)")
    if (confirm or "").strip() != _phrase():
        raise ValueError("the confirm phrase is missing or not exact")
    day = _et_day(now)
    rec["extra"] = [x for x in (rec.get("extra") or []) if isinstance(x, dict) and x.get("account") != account] + \
        [{"account": account, "accepted_on": day, "proof": _proof(account, day, _phrase())}]
    _write(rec, path)
    return rec


def extra_ok(rec, account: str) -> bool:
    """True when this extra real account is in a valid opt-in with its own proof."""
    if not valid(rec):
        return False
    for x in rec.get("extra") or []:
        if isinstance(x, dict) and x.get("account") == account and x.get("accepted_on") \
                and x.get("proof") == _proof(account, str(x["accepted_on"]), _phrase()):
            return True
    return False


def resume_accounts(optin, cfg: dict) -> tuple:
    """The start cfg's extra accounts on a resume: Sim / paper ones come back as they were; a real one only when its entry
    says "armed": true AND it is opted in itself (enable_extra) - then it gets the phrase in memory for its adapter's own
    gate; any other real account is left out (enabled false) and named in the refusals. Returns (accounts, refused)."""
    out, refused = [], []
    for e in (cfg or {}).get("accounts") or []:
        if not isinstance(e, dict):
            continue
        e = dict(e)
        e.pop("confirm", None)
        adapter = e.get("adapter") or cfg.get("adapter") or "paper"
        name = str(e.get("nt_account") or "").strip()
        if e.get("enabled", True) is False or adapter != "ninjatrader" or (name and _is_sim(name)):
            out.append(e)
            continue
        if e.get("armed") is not True:
            why = "not armed in its account entry"
        elif not extra_ok(optin, name):
            why = "not opted in (python -m engine.ninjatrader --enable-auto-resume --extra --account <Name>)"
        else:
            e["confirm"] = _phrase()                  # in memory only, for its adapter's own live gate
            out.append(e)
            continue
        e["enabled"] = False
        refused.append({"id": e.get("id"), "account": name, "reason": why})
        out.append(e)
    return out, refused


def disable(reason: str, now=None, path: str = OPTIN_PATH) -> bool:
    """Turn it off (the proof is dropped: turning it on again needs the owner's command). True when it was on."""
    now = time.time() if now is None else now
    rec = load(path)
    was_on = bool(rec and rec.get("enabled"))
    if rec is None:
        return False
    _write({"v": 1, "enabled": False, "account": (rec or {}).get("account"), "disabled_reason": str(reason)[:120],
            "disabled_at": int(now)}, path)
    return was_on


def note(path: str = OPTIN_PATH, **kw):
    rec = load(path)
    if rec and rec.get("enabled"):
        rec.update(kw)
        _write(rec, path)


def valid(rec) -> bool:
    if not rec or rec.get("_corrupt") or not rec.get("enabled"):
        return False
    acct, day = str(rec.get("account") or ""), str(rec.get("accepted_on") or "")
    return bool(acct and day) and rec.get("proof") == _proof(acct, day, _phrase()) and not _is_sim(acct)


# ---------------------------------------------------------------------- the gate (pure)
def day_events(live_state: dict | None, now) -> dict:
    """Today's kill flag and routed P&L from data/live_state.json (a file from another day says nothing)."""
    s = live_state or {}
    try:
        from .live import trading_day
        today = trading_day(now)
    except Exception:
        today = _et_day(now)
    if s.get("day") != today:
        return {"kill": False, "day_pnl": 0.0}
    return {"kill": bool(s.get("kill")), "day_pnl": float(s.get("day_pnl_routed") or 0.0)}


def decide(optin, autostart_cfg: dict | None, live_state: dict | None, env=None, now=None, connected=None,
           daily_loss: float = DAILY_LOSS_USD) -> dict:
    """{"resume": bool, "wait": bool (try again shortly: NinjaTrader not connected yet), "cfg", "account", "reason"}."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    out = {"resume": False, "wait": False, "cfg": None, "account": None, "reason": ""}

    def no(reason, wait=False):
        out.update(reason=reason, wait=wait)
        return out

    if not optin or not optin.get("enabled"):
        return no("auto-resume is off for real accounts (owner opt-in: python -m engine.ninjatrader --enable-auto-resume)")
    if not valid(optin):
        return no("auto-resume record is not valid (turn it on again with --enable-auto-resume)")
    acct = optin["account"]
    out["account"] = acct
    cfg = dict(autostart_cfg or {})
    if not autostart_cfg:
        return no("the bot was stopped on purpose (no autostart record)")
    if cfg.get("adapter") != "ninjatrader":
        return no(f"last start was adapter {cfg.get('adapter')}, not NinjaTrader")
    from .ninjatrader import resolve_account
    if resolve_account(cfg) != acct:
        return no(f"last start was account {resolve_account(cfg)}, the opt-in is for {acct}: accounts must match exactly")
    if env.get(LIVE_ENV, "") != "1":
        return no(f"{LIVE_ENV}=1 is not set for the server (.env.local.ps1)")
    ev = day_events(live_state, now)
    if ev["kill"]:
        return no("the kill switch was used today")
    if ev["day_pnl"] <= -abs(daily_loss):
        return no(f"daily loss today (${ev['day_pnl']:,.0f})")
    lf = optin.get("last_fail_at")
    if lf and now - float(lf) < FAIL_COOLDOWN_S:
        return no(f"a start failed {int(now - float(lf))} s ago (waits 10 min)", wait=True)
    if connected is not True:
        return no("NinjaTrader shows no CONNECTED connection" + (" (no connection files yet)" if connected is None else ""), wait=True)
    cfg.pop("clear_kill", None)
    cfg.update(armed=True, confirm=_phrase())          # in memory only, for the adapter's own live gate
    if cfg.get("accounts"):                            # extra accounts: each real one needs its own opt-in
        cfg["accounts"], out["refused_accounts"] = resume_accounts(optin, cfg)
    out.update(resume=True, cfg=cfg, reason=f"resuming {acct}")
    return out


def status(path: str = OPTIN_PATH) -> dict:
    """The health block's auto_resume entry (secret-free: no proof, no cfg)."""
    r = load(path) or {}
    lr = r.get("last_resume") or {}
    return {"on": bool(valid(r)), "account": r.get("account"), "accepted_on": r.get("accepted_on") if r.get("enabled") else None,
            "off_reason": r.get("disabled_reason"), "last_t": lr.get("t"), "last_result": lr.get("result"),
            "last_reason": str(lr.get("reason") or "")[:160] or None}


# ---------------------------------------------------------------------- runtime (server.py autostart thread)
def nt_connected(cfg: dict):
    """True / False / None (no connection files) from NinjaTrader's outgoing folder."""
    try:
        from .ninjatrader import NinjaTraderAdapter
        ad = NinjaTraderAdapter({**cfg, "nt_state_path": os.path.join(ROOT, "data", "_nt_probe_state.json")}, readonly=True)
        c = ad.connections()
        return any(v == "CONNECTED" for v in c.values()) if c else None
    except Exception:
        return None


def restart_reason(marker: dict | None = None) -> str:
    if marker and marker.get("sha"):
        return f"the update to {str(marker['sha'])[:7]}"
    try:
        import psutil
        if time.time() - psutil.boot_time() < 20 * 60:
            return "a PC restart"
    except Exception:
        pass
    return "a server restart"


def _read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def resume_live(bot, autostart_cfg, marker=None, notify=None, log=print, sleep=time.sleep, clock=time.time,
                path: str = OPTIN_PATH, state_path: str | None = None, connected_fn=nt_connected,
                wait_s: float = CONNECT_WAIT_S, env=None) -> dict:
    """Try to resume the real-account bot (waits for NinjaTrader to connect, retries after a failed start). Returns the
    final decision. notify(title, body, key) pushes the phone."""
    notify = notify or (lambda *a, **k: None)
    state_path = state_path or os.path.join(ROOT, "data", "live_state.json")
    why = restart_reason(marker)
    t0 = clock()
    tries = 0
    while True:
        now = clock()
        optin = load(path)
        d = decide(optin, autostart_cfg, _read_json(state_path), env=env, now=now,
                   connected=connected_fn(autostart_cfg or {}) if optin and optin.get("enabled") else None)
        if d["resume"]:
            if getattr(bot, "running", False):
                return {**d, "resume": False, "reason": "bot already running"}
            tries += 1
            try:
                res = bot.start(d["cfg"])
            except Exception as e:
                res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
            dis = getattr(getattr(bot, "adapter", None), "disabled", None)
            if res.get("ok") and not dis:
                note(path, last_fail_at=None, last_resume={"t": int(now), "result": "resumed", "reason": why})
                log(f"auto-resume: RESUMED {d['account']} after {why}")
                notify(f"Bot resumed on {d['account']}", f"after {why}. Restored: {res.get('restored')}",
                       f"auto:resumed:{int(now) // 60}")
                ref = d.get("refused_accounts") or []
                if ref:
                    txt = "; ".join(f"{x.get('account') or x.get('id')}: {x.get('reason')}" for x in ref)[:300]
                    log(f"auto-resume: extra accounts NOT resumed: {txt}")
                    notify("Extra accounts NOT resumed", f"{txt}. Start them by hand.", f"auto:refused_extra:{int(now) // 60}")
                return {**d, "cfg": None, "result": res}
            err = res.get("error") or f"adapter DISABLED ({dis})"
            if res.get("ok"):
                try:
                    bot.stop()
                except Exception:
                    pass
            note(path, last_fail_at=int(now), last_resume={"t": int(now), "result": "failed", "reason": err[:160]})
            log(f"auto-resume: start FAILED on {d['account']}: {err}")
            if tries >= 3:
                note(path, last_resume={"t": int(now), "result": "refused", "reason": f"start failed 3 times: {err}"[:160]})
                notify(f"Bot NOT resumed on {d['account']}", f"after {why}: start failed 3 times ({err[:160]}). Start it by hand.",
                       f"auto:refused:{int(now) // 60}")
                return {**d, "resume": False, "cfg": None, "reason": err}
            continue                                   # decide() now waits out the 10-minute cooldown
        if d["wait"] and clock() - t0 < wait_s + (FAIL_COOLDOWN_S if tries else 0):
            sleep(30)
            continue
        if optin and optin.get("enabled"):            # opt-in on but refused: tell the owner
            note(path, last_resume={"t": int(now), "result": "refused", "reason": d["reason"][:160]})
            log(f"auto-resume: refused: {d['reason']}")
            notify(f"Bot NOT resumed on {d.get('account') or 'your eval'}", f"after {why}: {d['reason']}. Start it by hand.",
                   f"auto:refused:{int(now) // 60}")
        return {**d, "cfg": None}
