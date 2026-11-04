"""MFFU Builder 50K eval lifecycle on the PC bot and the cloud monitor (2026-10-20): the pass day, the fail day, the
minimum-days trade, the eval weekly loss stop's state, the funded switch and the funded payout check. Read-only helpers +
two small config commands (paper only: never arms or routes anything).

What the bot does (engine/sizing.eval_lock + lit_qty, engine/live.py LiveBot._eval_life):
  * PASS (eval balance >= $53,000: +$3,000 incl. the owner's -$100 prior): no new normal-size trade on that account. While
    MFFU may still need a 2nd traded day (help guides say 1 day, the plan page says 2: the bot assumes 2), the next
    session's first entry trades 1 micro (the minimum-days trade), then nothing. One push "EVAL PASSED" with the funded
    checklist and the one command that adds the funded account.
  * FAIL (room to the trailing max-loss floor <= $0): no new trade (the room caps' min-1-micro rule never trades a failed
    eval). One push "EVAL FAILED" with the next steps (buy a new one at your price, the stagger rule).
  * Weekly loss stop (lit_sizing "wk_loss_usd", default OFF): once this eval's closed P&L of the calendar week is <= -$X,
    no new trade until Monday. State off / armed / tripped on the PC Today page and the phone; one push when it trips.
    Switch on (one line, live_model.json AND live_model_lit.json "lit_sizing"):  "wk_loss_usd": 1200

  python -X utf8 -m engine.eval_life                      the eval's state now (from data/live_state.json)
  python -X utf8 -m engine.eval_life --to-funded --account "<NinjaTrader funded account Name>" --start 2026-11-03
        adds the funded MFFU Builder 50K to data/accounts.json (mode funded: 40% of the room, max $800, a winner <= $1,500;
        disarmed: a real account trades only after --armed yes, your phrase at --start and NINJATRADER_LIVE=1)
        a passed Builder 25K: add --plan builder25k (id mffu25k_funded: 40% of the room, max $400, a winner <= $750)
        Until this is run, a passed eval only stops trading and pushes "EVAL PASSED" (the safe default).
  python -X utf8 -m engine.funded_life                     the sim funded payout tracker (engine/funded_life.py, read-only)
  python -X utf8 -m engine.eval_life --payout 2026-12-01=2000 [--id mffu50k_funded]   record a funded payout
  python -X utf8 -m engine.eval_life --funded-status [--id mffu50k_funded]            payout check of the funded account
  python -m engine.eval_life --anchor-from-site     (fresh start on a new PC: from the published board, asks Y/N)
  python -m engine.eval_life --anchor --balance 49710.80 --floor 48168.20 --as-of 2026-10-23 [--account "<Name>"]
        eval ANCHOR (2026-10-24): the MFFU dashboard's balance + minimum-balance floor after a session's close, written to
        data/eval_anchor.json (gitignored). The bot then books balance = that balance + its routed P&L after as_of and the
        floor = max(that floor, highest EOD after as_of - MLL), locked at start + $100 (engine/sizing.anchor_days).
        No --account = LIT's own account; --account = an extra account / account B by its NinjaTrader Name.
        A push at 17:05 ET each weekday says what the bot thinks ("Check MFFU: bot thinks balance $X, floor $Y").
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START_BAL = 50000.0
MAX_LOSS = 2000.0                 # the Builder 50K max loss, for the "drawdown left $X of $2,000" text only
OWNER_PRICE = "$91.80"            # the owner's Builder 50K price with a discount code (2026-10-18; verify the code at checkout)
FUNDED_ID = "mffu50k_funded"
PAYOUT_ASK_ABOVE = 1500.0         # lit-money-batch2.md: ask only once $1,500+ is above the $2,100 buffer (balance $53,600)
STAGGER_SESSIONS = 5              # lit-risk-money.md: a 2nd eval 5 sessions after the first, never the same day
WK_LOSS_SUGGEST = 1200.0          # lit-risk-money.md run lit_risk_m_wk1200
EVAL_MODES = ("eval", "safe_eval", "fast_eval", "two_week")
STUCK_ROOM = 200.0                # 2026-10-24 cap invariant: room under $200 -> 60% fits 1 micro only up to a ~58-pt stop
                                  # (research/writeups/sizing-caps.md: 2026 eval path, stuck at $200 = the old fails)


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _money(x) -> str:
    v = float(x or 0)
    return f"{'+' if v > 0 else '-' if v < 0 else ''}${abs(v):,.0f}"


def week_monday(today: str) -> str:
    d = _dt.date.fromisoformat(str(today)[:10])
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


# ---------------------------------------------------------------------------------------------------- weekly loss stop
def wk_stop_view(lsz: dict | None, state: dict | None) -> dict:
    """The eval weekly loss stop's state: off (key absent / not an eval mode) | armed (on, not reached) | tripped (this
    week's closed eval P&L <= -limit: no new trade until Monday)."""
    c = lsz or {}
    wl = _num(c.get("wk_loss_usd"))
    w = _num((state or {}).get("wk_pnl"))
    out = {"state": "off", "limit": wl, "wk_pnl": w}
    if not wl or (c.get("mode") or "normal") not in EVAL_MODES:
        out["limit"] = None
        out["text"] = f'weekly loss stop: off (switch: "wk_loss_usd": {WK_LOSS_SUGGEST:.0f} in lit_sizing)'
        return out
    if w is None:
        out.update(state="armed", text=f"weekly loss stop: armed at -${wl:,.0f} (week P&L not known yet)")
    elif w <= -wl:
        out.update(state="tripped", text=f"weekly loss stop: TRIPPED (week {_money(w)} <= -${wl:,.0f}): no new trade until Monday")
    else:
        out.update(state="armed", text=f"weekly loss stop: armed (week {_money(w)}, trips at -${wl:,.0f})")
    return out


# ---------------------------------------------------------------------------------------------------- the eval view
def view(days: dict, start: str | None, today: str, lsz: dict | None = None, session_over: bool = False,
         n_today: int = 0, anchor: dict | None = None) -> dict:
    """The eval's lifecycle now. days = closed P&L per trading day since the eval start (yyyy-mm-dd keys; "0000-00-00" =
    the P&L before the bot traded it), today's included. anchor = the broker's balance + floor on a day (engine/sizing.
    anchor_days; None = as before). -> {status open/passed/failed/not started/unknown, balance, profit, to_target, room,
    floor, session, days_traded, min_days, min_days_left, trading (what the bot does now), wk_stop, text}."""
    from . import sizing as sz
    c = lsz or {}
    tw = c.get("two_week") or {}
    acct = {**sz.TW_50K, **(tw.get("acct") or {})}
    target = float(acct["target"])
    days = {str(d): float(v) for d, v in (days or {}).items()}
    days, ex = sz.anchor_days(days, anchor, START_BAL)
    clock = sz.eval_clock(days, start, today, session_over=session_over, plan=ex or None)
    prev = {d: v for d, v in days.items() if d < today}
    st = sz.eval_state(prev, days.get(today, 0.0), plan=ex or None, session=clock.get("session") or None, today=today)
    st["n_today"] = int(n_today or 0)
    bal = st["profit"] + st["cum"]
    status = clock["status"]
    mind = tw.get("min_days", sz.TW_DEFAULT["min_days"])
    dtr = st["days_traded"] + (1 if abs(st["cum"]) > 1e-9 else 0)       # incl. today
    left = max(0, int(mind or 0) - dtr) if status == "passed" else None
    wk = wk_stop_view(c, st)
    if status == "passed":
        trading = ("passed: no new trade, except one 1-micro minimum-days trade next session" if left
                   else "passed: no new trade on this eval")
    elif status == "failed":
        trading = "failed: no new trade on this eval"
    elif wk["state"] == "tripped":
        trading = "weekly loss stop: no new trade until Monday"
    elif status == "open":
        trading = "trading"
    else:
        trading = status
    stuck = status == "open" and st["room"] < STUCK_ROOM
    if stuck:
        # the cap invariant (2026-10-24, engine/sizing.ceilings): with this little room most LIT entries no longer fit
        # 1 micro inside the caps and are skipped, so the eval can sit for weeks without failing or passing
        rf = float(tw.get("room_f") or c.get("safe_cap") or 0.6)
        mx = max(0.0, (rf * st["room"] - sz.LIVE_COMM) / 2.0 - 0.25)
        trading = (f"stuck: drawdown left ${st['room']:,.0f} of ${MAX_LOSS:,.0f} - 1 micro fits only stops up to {mx:.0f} pts, most entries are skipped; "
                   "buy a new eval")
    out = {"start": start, "today": today, "status": status, "balance": round(START_BAL + bal, 2), "profit": round(bal, 2),
           "to_target": round(target - bal, 2), "target_balance": START_BAL + target, "room": st["room"],
           "session": clock.get("session"), "days_traded": dtr, "min_days": mind, "min_days_left": left,
           "trading": trading, "wk_stop": wk, "clock_text": clock.get("text"), "stuck": stuck}
    out["text"] = (f"Eval {status.upper()}: balance ${out['balance']:,.0f} ({_money(bal)}), {trading}"
                   if status in ("passed", "failed") else f"Eval {status}: {_money(bal)}, ${max(0.0, out['to_target']):,.0f} to go, "
                                                          f"drawdown left ${st['room']:,.0f} of ${MAX_LOSS:,.0f}; {wk['text']}")
    if ex:                                   # anchored: the broker's floor rebuilt, shown next to the balance
        out["floor"] = round(out["balance"] - float(st["room"]), 2)
        out["anchor"] = sz.eval_anchor(anchor)
    return out


# ---------------------------------------------------------------------------------------------------- eval anchor file
ANCHOR_FILE = "eval_anchor.json"     # gitignored, next to the bot's state file (data/): {"v", "main", "accounts": {name: anchor}}
_ANCHOR_CACHE: dict = {}


def anchor_path(state_path: str | None = None) -> str:
    """data/eval_anchor.json, or the file next to a test bot's own state file (a test bot never reads the owner's)."""
    sp = state_path or os.path.join(ROOT, "data", "live_state.json")
    return os.path.join(os.path.dirname(os.path.abspath(sp)), ANCHOR_FILE)


def load_anchors(path: str | None = None) -> dict:
    """The anchor file ({} when missing / unreadable). Cached by modification time (read on every poll)."""
    p = path or anchor_path()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    hit = _ANCHOR_CACHE.get(p)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        d = d if isinstance(d, dict) else {}
    except Exception:
        d = {}
    _ANCHOR_CACHE[p] = (mt, d)
    return d


def load_anchor(account: str | None = None, state_path: str | None = None, path: str | None = None,
                main: bool = True) -> dict | None:
    """The valid anchor for one account: its own entry by NinjaTrader Name ("accounts"), else (main=True) the main entry
    ("main" = LIT's own account). None when there is none."""
    from . import sizing as sz
    d = load_anchors(path or anchor_path(state_path))
    acc = d.get("accounts") if isinstance(d.get("accounts"), dict) else {}
    a = sz.eval_anchor(acc.get(str(account).strip())) if account else None
    if a is None and main:
        a = sz.eval_anchor(d.get("main"))
    return a


def save_anchor(anchor: dict, account: str | None = None, path: str | None = None) -> dict:
    """Write one anchor into the anchor file (temp file + rename). account None = the main (LIT) account."""
    import time as _t
    from . import sizing as sz
    a = sz.eval_anchor({**anchor, "set_t": int(_t.time())})
    if a is None:
        raise ValueError("invalid anchor: as_of yyyy-mm-dd, balance > 0, 0 < floor <= balance")
    p = path or anchor_path()
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        d = d if isinstance(d, dict) else {}
    except Exception:
        d = {}
    d["v"] = 1
    if account:
        d.setdefault("accounts", {})
        if not isinstance(d["accounts"], dict):
            d["accounts"] = {}
        d["accounts"][str(account).strip()] = a
    else:
        d["main"] = a
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, p)
    _ANCHOR_CACHE.pop(p, None)
    return a


def anchor_check_payload(rows: list, now) -> dict | None:
    """The 17:05 ET push: what the bot thinks each eval account's balance and floor are, so the owner compares them with
    the MFFU dashboard. rows = [{"name", "balance", "floor", "room", "to_target", "anchor"}]. None when there is no row."""
    rows = [r for r in rows or [] if r and r.get("balance") is not None and r.get("floor") is not None]
    if not rows:
        return None
    from . import push
    day = _dt.datetime.fromtimestamp(int(now), _ET()).strftime("%Y-%m-%d")
    bits = []
    for r in rows:
        s = f"{r.get('name') or 'eval'}: balance ${float(r['balance']):,.2f}, floor ${float(r['floor']):,.2f}"
        if r.get("room") is not None:
            s += f" (drawdown left ${float(r['room']):,.2f}"
            s += f", ${max(0.0, float(r['to_target'])):,.2f} to target)" if r.get("to_target") is not None else ")"
        a = r.get("anchor")
        s += f", anchored {a['as_of']}" if isinstance(a, dict) and a.get("as_of") else ", not anchored"
        bits.append(s)
    first = rows[0]
    title = f"Check MFFU: bot thinks balance ${float(first['balance']):,.2f}, floor ${float(first['floor']):,.2f}"
    body = ("; ".join(bits) + ". Different on MFFU? Run: python -m engine.eval_life --anchor --balance <MFFU balance> "
            f"--floor <MFFU floor> --as-of {day}")
    p = push.text_payload("PC", "ops", title[:120], body[:900], key=f"eval:mffu_check:{day}", t=int(now), url="#/accounts")
    p["tag"] = "le-eval-mffu-check"
    return p


def _ET():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------------------------------- next steps
def funded_cmd(account: str = "<funded account Name>", start: str = "<first funded session yyyy-mm-dd>") -> str:
    return f'python -X utf8 -m engine.eval_life --to-funded --account "{account}" --start {start}'


def passed_steps() -> list:
    return ["The bot stopped trading this eval by itself (only a 1-micro minimum-days trade next session if MFFU still needs a 2nd day).",
            "Next morning: check MFFU shows the eval PASSED.",
            "Sign MFFU's funded agreement.",
            "Note the new funded account's Name in NinjaTrader (Accounts tab).",
            f"Add it with funded sizing (40% of the room, max $800, a winner <= $1,500): {funded_cmd()}, then restart the bot.",
            f"Payouts: ask only once the balance is $53,600+ ($1,500 above the $2,100 buffer), up to $2,000 a request; record "
            f"each one: python -X utf8 -m engine.eval_life --payout <day>=<$>.",
            "A real funded account trades only after you arm it yourself (--armed yes, your phrase at --start, NINJATRADER_LIVE=1)."]


def failed_steps() -> list:
    return ["The bot stopped trading this eval by itself (max-loss floor reached).",
            "Stop the bot on this account.",
            f"Buy a new MFFU Builder 50K at your price ({OWNER_PRICE} with a discount code last time: verify the code at checkout).",
            "Tell Claude the new account Name and its first session (lit_sizing.eval_start, eval_prior_pnl 0).",
            f"Stagger rule: a 2nd eval starts {STAGGER_SESSIONS} sessions after the first, never the same day (same trades, same result)."]


def _payload(kind_sub: str, title: str, body: str, key: str, now, url="#/accounts") -> dict:
    from . import push
    p = push.text_payload("PC", "ops", title[:120], body[:900], key=key, t=int(now), url=url)
    p["tag"] = f"le-eval-{kind_sub}"
    return p


def passed_payload(v: dict, account: str, now) -> dict:
    """The push (<= 600 characters, engine/push.text_payload); the full checklist is passed_steps()."""
    body = (f"{account}: balance ${v['balance']:,.0f} ({_money(v['profit'])}). The bot stopped trading it (one 1-micro "
            "minimum-days trade if MFFU needs a 2nd day). 1) Check MFFU shows PASSED. 2) Sign the funded agreement. "
            "3) Note the funded account Name in NinjaTrader. 4) Run: python -m engine.eval_life --to-funded --account "
            "\"<Name>\" --start <first day>, restart the bot (funded sizing). 5) Payouts: ask at $53,600+ ($1,500 above "
            "the $2,100 buffer), up to $2,000.")
    return _payload("passed", "EVAL PASSED \U0001F389 next steps", body, f"eval:passed:{v.get('start') or 'nostart'}", now)


def failed_payload(v: dict, account: str, now) -> dict:
    body = (f"{account}: balance ${v['balance']:,.0f} ({_money(v['profit'])}), max-loss floor reached. The bot stopped "
            f"trading it. 1) Stop the bot on this account. 2) Buy a new MFFU Builder 50K at your price ({OWNER_PRICE} with "
            "a code last time; verify the code at checkout). 3) Tell Claude the new account Name and first session "
            f"(eval_start). Stagger: a 2nd eval starts {STAGGER_SESSIONS} sessions after the first, never the same day.")
    return _payload("failed", "EVAL FAILED: max loss reached, next steps", body, f"eval:failed:{v.get('start') or 'nostart'}", now)


def wk_stop_payload(v: dict, account: str, now) -> dict:
    wk = v.get("wk_stop") or {}
    body = (f"{account}: this week's eval P&L {_money(wk.get('wk_pnl'))} reached the -${float(wk.get('limit') or 0):,.0f} "
            "weekly loss stop. No new trade until Monday; an open trade keeps its stop and target.")
    return _payload("wkstop", "Weekly loss stop tripped", body,
                    f"eval:wkstop:{v.get('start') or 'nostart'}:{week_monday(v['today'])}", now)


def notices(v: dict, account: str, now) -> list:
    """The pushes due for this view (each has a stable key: the notifier sends it once)."""
    out = []
    if v.get("status") == "passed":
        out.append(passed_payload(v, account, now))
    elif v.get("status") == "failed":
        out.append(failed_payload(v, account, now))
    elif (v.get("wk_stop") or {}).get("state") == "tripped":
        out.append(wk_stop_payload(v, account, now))
    if v.get("stuck"):
        out.append(stuck_payload(v, account, now))
    return out


def stuck_payload(v: dict, account: str, now) -> dict:
    body = (f"{account}: drawdown left ${float(v.get('room') or 0):,.0f} of ${MAX_LOSS:,.0f}. The bot never sends a trade whose "
            "1-micro stop-out does not fit the caps, so most LIT entries are now skipped and this eval can sit for weeks. "
            f"Buy a new MFFU Builder 50K ({OWNER_PRICE} with a code last time) and tell Claude its Name and first session.")
    return _payload("stuck", "EVAL STUCK: buy a new one", body, f"eval:stuck:{v.get('start') or 'nostart'}", now)


# ---------------------------------------------------------------------------------------------------- funded payouts
def payout_check(day_pnl: dict, payouts: dict | None = None, today_cum: float = 0.0, plan: dict | None = None,
                 ask_above: float = PAYOUT_ASK_ABOVE) -> dict:
    """Funded MFFU Builder 50K payout check from the funded account's closed P&L per day (since the funded start) and the
    payouts already taken: balance - $2,100 buffer >= ask_above (owner habit $1,500; MFFU's minimum is $500), at most
    $2,000 a request, at least 2 traded days in the cycle (since the last payout), best day <= 50% of the cycle's profit,
    at most 5 sim payouts. -> {ok, amount, why, balance, cycle_profit, best_day, cycle_days, payouts_done}."""
    from . import sizing as sz
    A = {**sz.FD_50K, **(plan or {})}
    pay = {str(d): float(v) for d, v in (payouts or {}).items()}
    st = sz.funded_state(day_pnl, today_cum, pay, plan=plan)
    last = max(pay) if pay else ""
    cyc = {d: float(v) for d, v in day_pnl.items() if d > last and abs(float(v)) > 1e-9}
    cprof = sum(cyc.values())
    best = max(cyc.values()) if cyc else 0.0
    bal = st["balance"] + float(today_cum)
    above = bal - float(A["buffer"])
    why = []
    if len(pay) >= int(A["max_payouts"]):
        why.append(f"{len(pay)} sim payouts done: MFFU moves the account to live")
    if above < max(float(A["pay_min"]), float(ask_above)):
        why.append(f"${above:,.0f} above the ${float(A['buffer']):,.0f} buffer, ask at ${max(float(A['pay_min']), float(ask_above)):,.0f}+")
    if len(cyc) < int(A["cycle_days"]):
        why.append(f"{len(cyc)} traded day(s) in this cycle, {int(A['cycle_days'])} needed")
    if cprof <= 0 or best > float(A["cons"]) * cprof + 1e-9:
        why.append(f"best day ${best:,.0f} > {float(A['cons']) * 100:.0f}% of the cycle's ${cprof:,.0f}: trade more days first")
    amt = round(min(float(A["pay_max"]), max(0.0, above)), 2) if not why else 0.0
    return {"ok": not why, "amount": amt, "why": why, "balance": round(START_BAL + bal, 2), "above_buffer": round(above, 2),
            "cycle_profit": round(cprof, 2), "best_day": round(best, 2), "cycle_days": len(cyc), "payouts_done": len(pay),
            "room": st["room"], "floor": st["floor"], "locked": st["locked"]}


# ---------------------------------------------------------------------------------------------------- commands
FUNDED_PLANS = {"builder50k": ("mffu_builder_50k", "MFFU Builder 50K funded", FUNDED_ID,
                               "40% of the room to the floor (max $800, x20/stop beyond 20 pts), a winner <= $1,500"),
                "builder25k": ("mffu_builder_25k", "MFFU Builder 25K funded", "mffu25k_funded",
                               "40% of the room to the floor (max $400, x20/stop beyond 20 pts), a winner <= $750")}


def to_funded(account: str, start: str, ident: str | None = FUNDED_ID, adapter: str = "ninjatrader", path: str | None = None,
              plan: str = "builder50k") -> int:
    """data/accounts.json: the funded MFFU Builder 50K (or 25K: plan "builder25k") as an extra account in mode funded
    (engine/multi_account.py), disarmed. Re-running it updates the same entry. This is the switch: until the owner runs it
    a passed eval only stops trading and pushes "EVAL PASSED" (sizing.eval_lock)."""
    from . import multi_account as ma
    _dt.date.fromisoformat(start)
    plan = str(plan or "builder50k").lower().replace(" ", "").replace("_", "")
    if plan not in FUNDED_PLANS:
        print(f"unknown plan {plan!r}: builder50k or builder25k")
        return 1
    preset, label, default_id, rule = FUNDED_PLANS[plan]
    ident = default_id if ident in (None, "", FUNDED_ID) and plan != "builder50k" else (ident or FUNDED_ID)
    path = path or ma.ACCOUNTS_PATH
    rows = ma.load_file(path)
    argv = ["--set" if any(r.get("id") == ident for r in rows) else "--add", "--id", ident, "--name", label,
            "--preset", preset, "--mode", "funded", "--funded-start", start, "--adapter", adapter, "--file", path]
    if adapter == "ninjatrader":
        argv += ["--nt-account", account]
    rc = ma.main(argv)
    if rc == 0:
        print(f"Funded sizing: {rule} (50% best-day payout rule), weekly stop, skip when 1 micro could reach the floor or the "
              "soft daily loss. Restart the bot (--start) to load it.")
        print(f"Payout tracker: python -X utf8 -m engine.funded_life (push \"PAYOUT READY: request $X\" when every MFFU rule "
              "is met; the bot never requests a payout itself).")
        print("It is DISARMED: a real account trades only after `python -m engine.multi_account --set --id "
              f"{ident} --armed yes`, your phrase at --start and NINJATRADER_LIVE=1 (you do that yourself).")
        print(f"Record each payout: python -X utf8 -m engine.eval_life --payout <day>=<$> --id {ident}")
    return rc


def record_payout(spec: str, ident: str = FUNDED_ID, path: str | None = None) -> int:
    from . import multi_account as ma
    d, _, v = spec.partition("=")
    _dt.date.fromisoformat(d.strip())
    float(v)
    return ma.main(["--set", "--id", ident, "--payout", f"{d.strip()}={float(v)}", "--file", path or ma.ACCOUNTS_PATH])


def funded_status(ident: str = FUNDED_ID, path: str | None = None, state_path: str | None = None) -> dict:
    """The funded account's payout check from its routed closes (data/live_state_accounts.json) and recorded payouts,
    + "tracker": the engine/funded_life.py view (buffer, cycle, consistency, 48 h, payouts n of 5)."""
    try:
        from . import funded_life as FL
        trk = next((t for t in FL.local_status(path, state_path) if t.get("id") == ident), None)
    except Exception as e:
        trk = {"error": f"{e.__class__.__name__}: {e}"}
    from . import multi_account as ma
    spec = next((r for r in ma.load_file(path or ma.ACCOUNTS_PATH) if r.get("id") == ident), None)
    if not spec:
        return {"error": f"no account {ident} in data/accounts.json ({funded_cmd()})"}
    f = spec.get("funded") or {}
    sp = state_path or ma._state_path_for(None)
    try:
        blob = (json.load(open(sp, encoding="utf-8")).get("accounts") or {}).get(ident) or {}
    except Exception:
        blob = {}
    days = {}
    for row in blob.get("closes") or []:
        d, p = str(row[0]), float(row[2])
        if not f.get("start") or d >= str(f["start"]):
            days[d] = round(days.get(d, 0.0) + p, 2)
    return {"id": ident, "start": f.get("start"), **payout_check(days, f.get("payouts") or {}), "tracker": trk}


def _plan_of(account: str | None) -> tuple:
    """(start, target, found) of the account the anchor is for: an extra account (data/accounts.json) or account B
    (second_model.json) by NinjaTrader Name, else the MFFU Builder 50K (found False for a name the bot does not know)."""
    if account:
        try:
            from . import multi_account as ma
            for r in ma.load_file():
                if account in (str(r.get("nt_account") or ""), str(r.get("name") or ""), str(r.get("id") or "")):
                    R = ma.rules_of(r)
                    return float(R["start"]), float(R["target"]), True
        except Exception:
            pass
        try:
            from . import account_b as ab
            raw = ab.raw_cfg() or {}
            if str(raw.get("account") or "").strip() == account:
                from . import multi_account as ma
                plan = str(raw.get("plan") or "builder50k").lower().replace(" ", "").replace("_", "")
                R = ma.rules_of({"preset": ab.PLANS[plan]["preset"]})
                return float(R["start"]), float(R["target"]), True
        except Exception:
            pass
        return START_BAL, 3000.0, False
    return START_BAL, 3000.0, True


def set_anchor(balance, floor, as_of, account: str | None = None, path: str | None = None) -> int:
    """`--anchor`: store the MFFU dashboard numbers; the bot reads them on its next poll (no restart needed)."""
    if balance is None or floor is None or not as_of:
        print("--anchor needs --balance <MFFU balance> --floor <MFFU floor> --as-of yyyy-mm-dd")
        return 1
    try:
        a = save_anchor({"as_of": as_of, "balance": balance, "floor": floor}, account, path)
    except ValueError as e:
        print(f"not saved: {e}")
        return 1
    start, target, found = _plan_of(account)
    room, need = round(a["balance"] - a["floor"], 2), round(start + target - a["balance"], 2)
    who = f'account "{account}"' if account else "the main (LIT) account"
    print(f"Saved for {who} as of {a['as_of']}: balance ${a['balance']:,.2f}, floor ${a['floor']:,.2f}")
    if found:
        print(f"Room ${room:,.2f}, ${need:,.2f} left to ${start + target:,.0f}. The bot uses it from its next poll "
              f"(P&L after {a['as_of']} is added; the floor trails from here).")
    else:
        print(f"Room ${room:,.2f}. Note: the bot has no extra account / account B named \"{account}\" yet: check the Name "
              "(NinjaTrader Accounts tab). LIT's own account needs no --account.")
    print(f"File: {path or anchor_path()} (stays on this PC, never committed)")
    return 0


SITE_HOME = "https://demetrades2000-coder.github.io/nq-dashboard/home.json"


def anchors_from_board(home: dict) -> list:
    """Fresh start with no state pack (2026-11-04): the anchors the published board implies, as a list of
    {"label", "account" (None = the main LIT account), "broker", "balance", "floor", "as_of", "room", "mll", "note"}.
    The board's balance includes today's P&L, so it is taken back to the close of the previous weekday (the bot adds its
    own P&L after as_of). Pure: no network, no files."""
    import datetime as dt
    b = (home or {}).get("board") if isinstance((home or {}).get("board"), dict) else {}
    try:
        d0 = dt.date.fromisoformat(str(b.get("today") or "")[:10])
    except ValueError:
        return []
    out = []
    for key, label, main in (("lit", "Zlarior (LIT)", True), ("atlas", "ATLAS", False)):
        r = b.get(key)
        if not isinstance(r, dict) or r.get("balance") is None or r.get("floor") is None:
            continue
        pnl = float(r.get("today_pnl") or 0.0)
        d = d0 - dt.timedelta(days=1)
        while d.weekday() >= 5:
            d -= dt.timedelta(days=1)
        bal, fl = round(float(r["balance"]) - pnl, 2), round(float(r["floor"]), 2)
        if fl > bal:
            fl = bal
        out.append({"label": label, "account": None if main else (r.get("broker") or None), "broker": r.get("broker"),
                    "balance": bal, "floor": fl, "as_of": d.isoformat(), "room": round(bal - fl, 2), "mll": r.get("mll"),
                    "note": f"board balance ${float(r['balance']):,.2f}" + (f" less today's ${pnl:,.2f}" if pnl else "")})
    return out


def anchor_from_site(site_file: str | None = None, yes: bool = False, path: str | None = None) -> int:
    """`--anchor-from-site`: read the published board (home.json), show the balance + floor it will set for the 50K and the
    25K, ask Y/N (compare with the MFFU dashboard), then store them through save_anchor. Nothing is set without a Y."""
    try:
        if site_file:
            with open(site_file, encoding="utf-8") as fh:
                home = json.load(fh)
        else:
            import urllib.request
            with urllib.request.urlopen(urllib.request.Request(SITE_HOME, headers={"User-Agent": "le-anchor"}), timeout=30) as r:
                home = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"could not read the published board ({e.__class__.__name__}). Set it by hand from the MFFU dashboard: "
              "python -m engine.eval_life --anchor --balance <balance> --floor <floor> --as-of <yyyy-mm-dd>")
        return 1
    rows = anchors_from_board(home)
    if not rows:
        print("the published board has no account numbers yet: set it by hand (python -m engine.eval_life --anchor ...)")
        return 1
    print("From the published board (compare with your MFFU dashboard):")
    for r in rows:
        print(f"  {r['label']:<14} {r['broker'] or '':<22} balance ${r['balance']:>10,.2f}   floor ${r['floor']:>10,.2f}   "
              f"room ${r['room']:>8,.2f}   as of {r['as_of']} ({r['note']})")
    if not yes:
        try:
            ans = input("Same as MFFU? Set these numbers (Y/N): ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("Nothing set. Type the MFFU numbers yourself: python -m engine.eval_life --anchor --balance <b> --floor <f> --as-of <yyyy-mm-dd>")
            return 1
    rc = 0
    for r in rows:
        try:
            save_anchor({"as_of": r["as_of"], "balance": r["balance"], "floor": r["floor"]}, r["account"], path)
            print(f"Set {r['label']}: balance ${r['balance']:,.2f}, floor ${r['floor']:,.2f}, as of {r['as_of']}")
        except ValueError as e:
            print(f"not saved for {r['label']}: {e}")
            rc = 1
    return rc


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.eval_life", description="eval pass / fail, funded switch, payouts")
    ap.add_argument("--to-funded", action="store_true")
    ap.add_argument("--account", help="NinjaTrader account Name of the funded account")
    ap.add_argument("--start", help="first funded session (yyyy-mm-dd)")
    ap.add_argument("--paper", action="store_true", help="--to-funded on the paper adapter (no NinjaTrader orders)")
    ap.add_argument("--plan", default="builder50k", help="--to-funded: builder50k (default) or builder25k")
    ap.add_argument("--payout", help="day=amount withdrawn from the funded account")
    ap.add_argument("--funded-status", action="store_true")
    ap.add_argument("--id", default=None, help=f"funded account id (default {FUNDED_ID}; 25K: mffu25k_funded)")
    ap.add_argument("--file", default=None, help="accounts file (default data/accounts.json)")
    ap.add_argument("--anchor", action="store_true", help="set the eval anchor: the MFFU dashboard's balance + floor on a day")
    ap.add_argument("--balance", type=float, help="--anchor: MFFU account balance ($)")
    ap.add_argument("--floor", type=float, help="--anchor: MFFU minimum-balance floor / max-loss level ($)")
    ap.add_argument("--as-of", dest="as_of", help="--anchor: the session those numbers are after (yyyy-mm-dd)")
    ap.add_argument("--anchor-file", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--anchor-from-site", action="store_true", help="fresh start: set the anchors from the published board, after a Y/N")
    ap.add_argument("--site-file", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.anchor_from_site:
        return anchor_from_site(a.site_file, a.yes, a.anchor_file)
    if a.anchor:
        return set_anchor(a.balance, a.floor, a.as_of, a.account, a.anchor_file)
    if a.to_funded:
        if not a.start or (not a.account and not a.paper):
            print("--to-funded needs --account \"<Name>\" (or --paper) and --start yyyy-mm-dd")
            return 1
        return to_funded(a.account or "", a.start, a.id, "paper" if a.paper else "ninjatrader", a.file, plan=a.plan)
    if a.payout:
        return record_payout(a.payout, a.id or FUNDED_ID, a.file)
    if a.funded_status:
        print(json.dumps(funded_status(a.id or FUNDED_ID, a.file), indent=1))
        return 0
    try:
        st = json.load(open(os.path.join(ROOT, "data", "live_state.json"), encoding="utf-8"))
    except Exception as e:
        print(f"no data/live_state.json ({e.__class__.__name__}): start the bot first")
        return 0
    lsz = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    from .live import trading_day
    import time as _t
    from . import sizing as _sz
    v = view(st.get("eval_days") or {}, lsz.get("eval_start") or None, trading_day(_t.time()), lsz,
             anchor=_sz.newest_anchor(load_anchor(), lsz.get("eval_anchor")))
    print(json.dumps(v, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
