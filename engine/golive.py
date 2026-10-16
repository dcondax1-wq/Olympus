"""Go-live checklist for Tradovate / MFFU Builder 50K.

run(cfg, roundtrip) -> {"ok": all_pass, "env": ..., "steps": [{"step", "ok", "detail", "fix", "warn"}]}
Every step is independent and never raises; a failed step says exactly what to do about it.
MFFU Builder 50K (verify on the MFFU site before trading): $1,000 daily loss limit = SOFT pause (done for the day),
$2,000 max loss trailing at END OF DAY only, payout buffer $2,100, max 4 minis / 40 micros, automation allowed
only with the trader present and monitoring, HFT banned, no consistency rule during the evaluation.
"""
from __future__ import annotations

import datetime as dt
import os
import time

from . import tradovate as tv
from .model import merge_params

MFFU = {"soft_dll": 1000.0, "max_loss": 2000.0, "payout_buffer": 2100.0, "max_minis": 4, "max_micros": 40, "max_trades_hard": 6}
LIVE_PHRASE = tv.LIVE_PHRASE


def _step(step, ok, detail, fix="", warn=False):
    return {"step": step, "ok": bool(ok), "detail": str(detail)[:400], "fix": fix, "warn": bool(warn)}


def _age(secs):
    return f"{secs // 60}m {secs % 60}s" if secs is not None else "n/a"


def run(cfg: dict | None = None, roundtrip: bool = False) -> dict:
    cfg = dict(cfg or {})
    params = merge_params(cfg.get("params") or {})
    env = tv.env_status()
    steps = []

    # 1) environment variables
    steps.append(_step("Credentials in environment", env["present"],
                       f"TRADOVATE_ENV={env['env']} · app {env['app_id']} · account {env['account'] or '(auto: the only account)'}"
                       + ("" if env["present"] else f" · missing {', '.join(env['missing'])}"),
                       "Set TRADOVATE_USER / TRADOVATE_PASS / TRADOVATE_CID / TRADOVATE_SECRET in .env.local.ps1, dot-source it, restart the server (README: Going live)."))

    ad = tv.shared_readonly(env["env"]) if env["present"] else None

    # 2) auth
    if ad:
        a = ad.ensure_auth()
        steps.append(_step("Tradovate authentication", a["ok"], "token OK (cached, renewed before expiry)" if a["ok"] else a.get("error"),
                           "Check user/password and that the API key (CID/secret) belongs to this login. Tradovate allows 5 logins/hour: wait 15 min before retrying."))
    else:
        steps.append(_step("Tradovate authentication", False, "skipped: no credentials", "Complete step 1 first."))

    # 3) account + balance
    acct = {"ok": False}
    if ad and ad.token:
        acct = ad.get_account()
        if acct["ok"]:
            bal = ad.balance()
            detail = f"{acct['name']} (id {acct['id']}, {acct.get('type')})"
            if bal["ok"]:
                detail += f" · netLiq ${bal.get('netLiq') or 0:,.0f} · cash ${bal.get('totalCashValue') or 0:,.0f} · open P&L ${bal.get('openPnL') or 0:,.0f} · init margin ${bal.get('initialMargin') or 0:,.0f}"
            steps.append(_step("Account + balance snapshot", True, detail))
        else:
            steps.append(_step("Account + balance snapshot", False, acct.get("error"),
                               "Set TRADOVATE_ACCOUNT to the exact account name shown in Tradovate (MFFU accounts look like MFFU...-xxxxx)."))
    else:
        steps.append(_step("Account + balance snapshot", False, "skipped: not authenticated", "Fix authentication first."))

    # 4) contracts
    syms = tv.TradovateAdapter(cfg, readonly=True, force_env=env["env"]).symbols(cfg.get("sym", "NQ")) if env["present"] else {"micro": tv.front_month("MNQ"), "mini": tv.front_month("NQ")}
    if ad and ad.token:
        cm, cn = ad.get_contract(syms["micro"]), ad.get_contract(syms["mini"])
        ok = cm["ok"] and cn["ok"]
        exp = (cm.get("expiry") or "")[:10]
        days = None
        try:
            days = (dt.date.fromisoformat(exp) - dt.date.today()).days if exp else None
        except Exception:
            pass
        detail = f"micro {cm.get('name') or cm.get('error')} · mini {cn.get('name') or cn.get('error')}" + (f" · expires {exp} ({days}d)" if exp else "")
        warn = ok and days is not None and days <= 8
        steps.append(_step("Front-month contracts", ok, detail + (" · ROLL WEEK: switch to the next month" if warn else ""),
                           "Type the contract in the Live page (e.g. MNQZ6) if the auto front month is wrong; check Tradovate's symbol list.", warn))
    else:
        steps.append(_step("Front-month contracts", False, f"computed {syms['micro']} / {syms['mini']} (not verified: not authenticated)", "Fix authentication first."))

    # 5) data feed freshness
    try:
        from .data import load
        b = load(cfg.get("sym", "NQ"), "5m")
        age = int(time.time()) - int(b.t[-1]) - 300
        src = "stored CSV"
        md = None
        if env["present"] and ad and ad.token:
            md = tv.TradovateData(adapter=ad)
            df = md.recent_bars(cfg.get("sym", "NQ"), "5m", "1d")
            if df is not None:
                age = int(time.time()) - int(df["time"].iloc[-1]) - 300
                src = f"Tradovate market data ({len(df)} bars)"
        mod = tv.et_mod()
        in_hours = 480 <= mod <= 1020 and dt.datetime.now(tv.ET).weekday() < 5
        ok = age <= 15 * 60 if in_hours else True
        steps.append(_step("Bar feed fresh", ok, f"{src}: last closed 5m bar {_age(max(age, 0))} ago" + ("" if in_hours else " (outside RTH: age not judged)")
                           + ("" if md is None or md.health()["ok"] else f" · Tradovate feed error: {md.health()['error']}"),
                           "Live trading needs data_source=tradovate (Yahoo is ~10 min delayed, paper only). If the Tradovate feed fails: confirm the market-data entitlement on the account and that the token is valid.",
                           warn=(md is not None and not md.health()["ok"])))
    except Exception as e:
        steps.append(_step("Bar feed fresh", False, f"{e.__class__.__name__}: {e}", "Run Data refresh / import NQ_5m.csv first."))

    # 6) clock sync
    try:
        import email.utils
        import requests
        t0 = time.time()
        r = requests.head(tv.BASES["demo"].rsplit("/v1", 1)[0], timeout=6, allow_redirects=False)
        t1 = time.time()
        hdr = r.headers.get("Date")
        srv = email.utils.parsedate_to_datetime(hdr).timestamp() if hdr else None
        drift = (srv - (t0 + t1) / 2) if srv else None
        steps.append(_step("System clock", drift is not None and abs(drift) < 3, f"drift vs server Date header {drift:+.1f}s" if drift is not None else "no Date header",
                           "Windows: Settings > Time & language > Sync now. A skewed clock mis-times the 15:55 flatten and bar closes.", warn=drift is not None and 1.5 < abs(drift) < 3))
    except Exception as e:
        steps.append(_step("System clock", False, f"could not reach Tradovate: {e.__class__.__name__}", "Check the internet connection / firewall."))

    # 7) risk settings vs MFFU Builder 50K
    issues, notes = [], []
    if params["daily_max_loss"] > MFFU["soft_dll"]:
        issues.append(f"daily_max_loss ${params['daily_max_loss']:.0f} > MFFU soft DLL ${MFFU['soft_dll']:.0f}")
    elif params["daily_max_loss"] > 0.8 * MFFU["soft_dll"]:
        notes.append(f"daily_max_loss ${params['daily_max_loss']:.0f} leaves little room under the $1,000 DLL (one slipped stop can breach it)")
    if params["max_micros"] > MFFU["max_micros"]:
        issues.append(f"max_micros {params['max_micros']} > {MFFU['max_micros']}")
    if params["max_trades_day"] > MFFU["max_trades_hard"]:
        issues.append(f"max_trades_day {params['max_trades_day']} > hard cap {MFFU['max_trades_hard']} (MFFU bans HFT)")
    if params["flat_mod"] > 958:
        issues.append(f"flat_mod {params['flat_mod']} is after 15:58 ET - must be flat before the 16:00 close")
    if params["risk_usd"] > 500:
        notes.append(f"risk_usd ${params['risk_usd']:.0f}: the strategy lost in 2 of 4 historical periods - start at $350 / minimum size")
    if params.get("mll", 2000) != MFFU["max_loss"]:
        notes.append(f"mll param {params.get('mll')} != MFFU ${MFFU['max_loss']:.0f}")
    notes.append(f"MFFU max loss ${MFFU['max_loss']:.0f} trails at END OF DAY only; payout buffer ${MFFU['payout_buffer']:.0f}")
    steps.append(_step("Risk settings vs MFFU 50K", not issues,
                       f"risk ${params['risk_usd']:.0f} · daily stop ${params['daily_max_loss']:.0f} · {params['max_trades_day']} trades/day · flat {params['flat_mod'] // 60:02d}:{params['flat_mod'] % 60:02d} ET · max {params['max_micros']} micros"
                       + (" · " + "; ".join(issues + notes) if issues or notes else ""),
                       "Lower the offending parameter in Backtest Lab (daily stop <= $1,000, <= 40 micros, <= 6 trades/day, flat by 15:58).", warn=bool(notes) and not issues))

    # 8) news blackout
    try:
        from . import news
        g = news.guard(params=params)
        nxt = g.get("next_high")
        nx = f" · next high-impact: {nxt['event']} {dt.datetime.fromtimestamp(nxt['t'], tv.ET):%a %H:%M} ET" if nxt else ""
        steps.append(_step("News blackout", g["allowed"], ("clear" if g["allowed"] else "; ".join(g["reasons"])) + nx + (f" · regime {g.get('regime')}" if g.get("regime") else ""),
                           "Nothing to fix: the bot will not enter during the blackout. Wait it out or stand down for the day.", warn=not g["allowed"]))
    except Exception as e:
        steps.append(_step("News blackout", False, f"guard failed: {e}", "Open the News page once to refresh the calendar."))

    # 9) live gate state
    armed = bool(cfg.get("armed")) and (cfg.get("confirm") or "").strip() == LIVE_PHRASE
    if env["env"] == "live":
        steps.append(_step("Live gate", True, ("ARMED: orders will go to the LIVE account" if armed else "LIVE env but NOT armed: every order is refused until you arm with the phrase"),
                           f"Type '{LIVE_PHRASE}' in the Go-live panel and press ARM.", warn=armed))
    else:
        steps.append(_step("Live gate", True, "DEMO environment: real money cannot be touched from this process", "Switch with $env:TRADOVATE_ENV='live' and restart the server when ready."))

    # 10) presence acknowledgement (MFFU: automation only with the trader actively monitoring)
    present = bool(cfg.get("present"))
    steps.append(_step("Trader present and monitoring", present, "acknowledged" if present else "not acknowledged",
                       "Tick 'I will be present and monitoring' in the Go-live panel. MFFU allows automation only with active oversight; no unattended runs."))

    # 11) optional demo round trip
    if roundtrip:
        if env["env"] != "demo":
            steps.append(_step("Round-trip order test", False, "refused: only on DEMO", "Set TRADOVATE_ENV=demo for this test."))
        elif ad and ad.token:
            rt = ad.round_trip_test()
            steps.append(_step("Round-trip order test", rt["ok"], rt.get("detail") or rt.get("error"),
                               "If placeOrder failed: check the account is active and funded on demo; if cancel failed: cancel the order in the Tradovate UI now."))
        else:
            steps.append(_step("Round-trip order test", False, "skipped: not authenticated", "Fix authentication first."))

    return {"ok": all(s["ok"] for s in steps), "env": env["env"], "phrase_required": LIVE_PHRASE, "mffu": MFFU,
            "symbols": syms, "steps": steps, "t": int(time.time())}
