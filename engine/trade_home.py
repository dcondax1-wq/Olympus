"""TRADING HOME: one numbered menu for the owner's daily PC steps (TRADE_HOME.bat -> scripts/trade_home.ps1 -> this file).

Owner 2026-11-22: "make the whole process for trading easier, adding accounts, whatever it is". Not a coder, too many .bat files.

  python -X utf8 -m engine.trade_home            the menu (1 Status ... 8 daily routine)
  python -X utf8 -m engine.trade_home status     the one-screen status only
  python -X utf8 -m engine.trade_home add        the add-an-account steps only (plan with price -> name -> one confirm -> HELD)

Hard rules (owner, CLAUDE.md): this file never arms, never places an order and never types, stores, passes or defaults a
live phrase. Every action CALLS the existing .bat / command (START_BOT.bat, KEEPALIVE_ON.bat ...) with the console handed
through as it is: the OWNER types I ACCEPT LIVE RISK / KEEP ALIVE ON in that window himself. The only thing added here is
the plan list with his real prices, the status screen and one plain result line after each step. Stdlib only; every
outside touch (run a .bat, read the bot, read input) is injectable, so tests/test_trade_home.py runs on Linux with fakes.
"""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The plan list the owner sees, in order, with HIS prices (CLAUDE.md: never list prices). `key` = engine/account_cli.PLANS.
# price: the CLUB price in account_cli's own price text (tests keep the two equal). off = shown but cannot be added here.
PLAN_MENU = (
    {"n": "1", "key": "builder50k", "label": "Builder 50K eval", "price": "$91.80", "who": "Zlarior trades it"},
    {"n": "2", "key": "builder25k", "label": "Builder 25K eval", "price": "$63 (one was $43)", "who": "Zlarior trades it"},
    {"n": "3", "key": "rapideod25", "label": "Rapid EOD 25K eval", "price": "$97.20 (CLUB)", "who": "Zlarior + ATLAS"},
    {"n": "4", "key": "rapideod", "label": "Rapid EOD 50K eval", "price": "$165 (CLUB)", "who": "Zlarior + ATLAS"},
    {"n": "5", "key": "atlasfunded", "label": "ATLAS funded 25K", "price": "no new buy", "who": "after MFFU's Upgrade"},
    {"n": "6", "key": "fundednext", "label": "FundedNext", "price": "OFF", "who": "needs your written yes",
     "off": "FundedNext is OFF. It needs your written yes first (it bans bots that use Telegram and our alerts use it). Nothing added."},
    {"n": "7", "key": "lucidpro50k", "label": "Lucid 50K", "price": "OFF", "who": "needs Lucid's written yes",
     "off": "Lucid is OFF. It needs Lucid's WRITTEN yes first: follow docs/LUCID_SETUP.md step 1. Nothing added."},
)
ENGINE_PLANS = ("builder50k", "builder25k", "rapideod25", "rapideod")   # the keys that go to engine.accounts add

NEXT_SENTENCE = ("Next: if the bot is running choose 6 (Stop bot) first, then choose 2 (Start bot) and type the live phrase "
                 "yourself when START BOT asks. Nothing trades until you do.")


def say(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------------------------------------ small readers (all injectable)
def _bot_state():
    """The bot server's /api/live/state or None (not answering)."""
    try:
        from engine import go
        return go._http("/api/live/state")
    except Exception:  # noqa: BLE001
        return None


def _accounts():
    try:
        from engine import account_cli as ac
        return ac.inventory()
    except Exception:  # noqa: BLE001
        return []


def _keepalive_on():
    """{key: bool} from the owner's keep-alive switches (engine/keepalive.py); {} when unreadable."""
    try:
        from engine import keepalive as ka
        return dict(ka.load_config().get("accounts") or {})
    except Exception:  # noqa: BLE001
        return {}


def _alert_channels():
    """(telegram?, discord?, bus_active?) from engine/alert_bus (never the secrets)."""
    try:
        from engine import alert_bus as ab
        c = ab.config()
        return bool(c.get("telegram")), bool(c.get("discord")), bool(ab.active(cfg=c))
    except Exception:  # noqa: BLE001
        return False, False, False


def _unseen_names():
    """NinjaTrader account Names not added yet (never Sim), name -> balance."""
    try:
        from engine import account_cli as ac, go
        have = {r["name"] for r in ac.inventory()}
        return {n: b for n, b in sorted((go.nt_balances() or {}).items()) if n not in have and not ac._is_sim(n)}
    except Exception:  # noqa: BLE001
        return {}


def _ago(sec):
    if sec is None:
        return "unknown"
    sec = max(0, int(sec))
    return f"{sec} s" if sec < 90 else f"{sec // 60} min" if sec < 5400 else f"{sec / 3600:.1f} h"


# ------------------------------------------------------------------------------------------------ 1. Status (one plain screen)
def status_screen(now=None, bot=None, accounts=None, keepalive=None, alerts=None):
    """-> (lines, problems). Plain words, one line per fact; `problems` = [(menu number, what to do)] for the unchecked ones."""
    import time
    now = now if now is not None else time.time()
    st = _bot_state() if bot is None else bot
    rows = _accounts() if accounts is None else accounts
    ka = _keepalive_on() if keepalive is None else keepalive
    tg, dc, bus = _alert_channels() if alerts is None else alerts
    L, P = [], []
    L.append("  ==== TRADING HOME: status ====")
    answers = isinstance(st, dict)
    run = bool(answers and st.get("running"))
    lp = st.get("last_poll") if answers else None
    age = (now - float(lp)) if lp else None
    L.append(f"  PC       : {'bot server answers' if answers else 'bot server NOT answering'}; last data {_ago(age)} ago")
    L.append(f"  Bot      : {'RUNNING' if run else 'NOT running'}")
    if not answers:
        P.append(("7", "The bot server is down: choose 7 (Update) to bring it back."))
    elif not run:
        P.append(("2", "The bot is not running: choose 2 (Start bot)."))
    held = []
    if not rows:
        L.append("  Accounts : none added yet")
        P.append(("4", "No account yet: choose 4 (Add an account)."))
    for r in rows:
        a = r.get("armed")
        word = "ARMED" if a is True else "HELD (not armed)" if a is False else "armed with the bot (START BOT)"
        if a is False:
            held.append(r["name"])
        L.append(f"  Account  : {r.get('plan', '?')} {r.get('stage', '')} {_mask(r['name'])}: {word}")
    if held:
        P.append(("2", f"{len(held)} account(s) held: choose 2 (Start bot) and type the phrase yourself."))
    on = [k for k, v in ka.items() if v is True]
    L.append(f"  Keep-alive: {'ON for ' + str(len(on)) + ' account(s)' if on else 'OFF'}")
    if not on:
        P.append(("3", "Keep-alive is off: choose 3 and type KEEP ALIVE ON yourself."))
    chans = [n for n, v in (("Telegram", tg), ("Discord", dc)) if v]
    L.append(f"  Alerts   : {', '.join(chans) + (' (bus on)' if bus else ' (bus OFF)') if chans else 'no phone channel set up'}")
    if not chans or not bus:
        P.append(("5", "Phone alerts are not set up: choose 5."))
    n_today = st.get("trades_today") if answers else None
    L.append(f"  Last trade: {('%s trade(s) today' % n_today) if n_today is not None else 'unknown (bot not answering)'}")
    L.append("")
    L.append("  [OK] Everything is green." if not P else "  [FIX] " + P[0][1])
    return L, P


def _mask(name):
    n = str(name or "")
    return "..." + n[-4:] if len(n) > 6 else n


# ------------------------------------------------------------------------------------------------ 4. Add an account
def plan_lines():
    out = ["  ==== Add an account: pick the plan ===="]
    for p in PLAN_MENU:
        out.append(f"   {p['n']}  {p['label']:<20} {p['price']:<18} {p['who']}")
    return out


def add_flow(ask=input, out=say, run=None, today=None, unseen=None, add_fn=None):
    """Plan with price -> Name (tap a number from what NinjaTrader shows, or paste) -> ONE confirm -> added HELD.
    Returns (ok, result line). Never arms, never asks for or passes the live phrase."""
    run = run or run_cmd
    for ln in plan_lines():
        out(ln)
    ch = (ask("  Type the number and press Enter (just Enter = back): ") or "").strip()
    if not ch:
        return False, "[OK] Nothing added."
    plan = next((p for p in PLAN_MENU if p["n"] == ch), None)
    if plan is None:
        return False, "[FIX] Type one number from the list. Nothing added."
    if plan.get("off"):
        return False, "[FIX] " + plan["off"]
    seen = _unseen_names() if unseen is None else unseen
    names = list(seen)
    if names:
        out("  NinjaTrader shows these accounts that are not added yet:")
        for i, n in enumerate(names, 1):
            b = seen[n]
            out(f"   {i}  {n}" + (f"   ${float(b):,.0f}" if isinstance(b, (int, float)) else ""))
        raw = (ask("  Type its number, or paste the Name (Enter = back): ") or "").strip()
        name = names[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(names) else raw
    else:
        raw = (ask("  Copy the account Name from NinjaTrader (Accounts tab), paste it, press Enter: ") or "").strip()
        name = raw
    name = name.strip('"').strip()
    if not name:
        return False, "[OK] Nothing added."
    out(f"  You are adding: {plan['label']} ({plan['price']}), Name {name}.")
    out("  It is added HELD: it is NOT armed and nothing trades on it.")
    if (ask("  Type Y and press Enter to add it (anything else = cancel): ") or "").strip().lower() != "y":
        return False, "[OK] Cancelled. Nothing added."
    if plan["key"] == "atlasfunded":
        day = today or _dt.date.today().isoformat()
        rc = run([sys.executable, "-X", "utf8", "-m", "engine.lit25", "--funded", name, "--start", day])
        if rc != 0:
            return False, "[FIX] NOT ADDED. Read the lines above: nothing changed. Copy the Name again and retry."
        return True, "[OK] Added HELD. " + NEXT_SENTENCE
    if add_fn is not None:
        r = add_fn(plan["key"], name)
        if not r.get("ok"):
            return False, "[FIX] NOT ADDED: " + str(r.get("error")) + " Nothing changed."
        for ln in [r.get("say")] + [f"- {n}" for n in (r.get("notes") or [])]:
            if ln:
                out("  " + ln)
        return True, "[OK] Added HELD. " + NEXT_SENTENCE
    rc = run([sys.executable, "-X", "utf8", "-m", "engine.accounts", "add", "--plan", plan["key"], "--name", name])
    if rc != 0:
        return False, "[FIX] NOT ADDED. Read the lines above: nothing changed. Copy the Name again and retry."
    return True, "[OK] Added HELD. " + NEXT_SENTENCE


# ------------------------------------------------------------------------------------------------ running the existing .bat files
def run_cmd(argv):
    """Run one command with the console handed through unchanged (the owner types into it himself). Returns the exit code.
    Never passes stdin, never feeds a phrase, never captures: what the .bat asks, he answers."""
    try:
        return subprocess.call(argv, cwd=ROOT)
    except Exception:  # noqa: BLE001
        return 1


def run_bat(name, run=None):
    run = run or run_cmd
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return 1
    return run(["cmd", "/c", path])


# result line after each action: re-read the one fact the action was for. `fx` = the readers (tests pass fakes).
def _default_fx():
    return {"bot": _bot_state, "keepalive": _keepalive_on, "alerts": _alert_channels}


def result_start(fx):
    st = fx["bot"]()
    return "[OK] The bot is running." if isinstance(st, dict) and st.get("running") else \
        "[FIX] The bot is not running yet. If you did not type the phrase, choose 2 again and type it yourself."


def result_keepalive(fx):
    on = [k for k, v in fx["keepalive"]().items() if v is True]
    return f"[OK] Keep-alive is ON for {len(on)} account(s)." if on else \
        "[FIX] Keep-alive is still OFF. Choose 3 again and type KEEP ALIVE ON yourself."


def result_alerts(fx):
    tg, dc, bus = fx["alerts"]()
    return "[OK] Phone alerts set up: " + ", ".join(n for n, v in (("Telegram", tg), ("Discord", dc)) if v) + "." \
        if (tg or dc) and bus else "[FIX] No phone channel is set up yet. Choose 5 again and pick Telegram."


def result_stop(fx):
    st = fx["bot"]()
    return "[OK] The bot is stopped." if not (isinstance(st, dict) and st.get("running")) else \
        "[FIX] The bot still shows RUNNING. Choose 6 again and type Y."


def result_update(fx):
    st = fx["bot"]()
    return "[OK] Updated and the bot server answers. Choose 2 if the bot should trade." if isinstance(st, dict) else \
        "[FIX] The server does not answer yet. Wait a minute, then choose 1."


# menu number -> (title, bat or None, result fn)
ACTIONS = {
    "2": ("Start bot", "START_BOT.bat", result_start),
    "3": ("Keep-alive on", "KEEPALIVE_ON.bat", result_keepalive),
    "6": ("Stop bot", "STOP_BOT.bat", result_stop),
    "7": ("Update", "UPDATE.bat", result_update),
}
ROUTINE = ("1", "2", "3", "t")      # status, start bot, keep-alive, alert test, IN THIS ORDER


def alerts_action(ask, run, fx, out):
    c = (ask("  1 Set up Telegram / Discord (then it tests)   2 Send a test alert only   Enter = back: ") or "").strip()
    if c == "1":
        run_bat("ALERTS_SETUP.bat", run)
        return result_alerts(fx)
    if c == "2":
        rc = run_bat("TEST_ALERT.bat", run)
        return "[OK] Test sent: check your phone buzzed." if rc == 0 else "[FIX] The test did not run. Choose 5, then 1."
    return "[OK] Nothing changed."


MENU = ("  ==== TRADING HOME ====",
        "   1  Status (one screen)",
        "   2  Start bot            (you type the phrase)",
        "   3  Keep-alive ON        (you type the phrase)",
        "   4  Add an account",
        "   5  Phone alerts (setup + test)",
        "   6  Stop bot",
        "   7  Update",
        "   8  Do my Sunday / daily routine (status, start, keep-alive, alert test)",
        "   0  Close")


def do_choice(ch, ask=input, out=say, run=None, fx=None, add_fn=None, unseen=None):
    """One menu step -> its ONE result line (None = leave). The menu loop prints it and shows the menu again."""
    run = run or run_cmd
    fx = fx or _default_fx()
    ch = (ch or "").strip()
    if ch == "0":
        return None
    if ch == "1":
        lines, _p = status_screen()
        for ln in lines[:-1]:
            out(ln)
        return lines[-1].strip()
    if ch in ACTIONS:
        title, bat, res = ACTIONS[ch]
        out(f"  {title}: it opens its own window. When it says 'Press any key', press a key to come back here.")
        rc = run_bat(bat, run)
        return res(fx) if rc == 0 else f"[FIX] {bat} did not open. Tell Claude."
    if ch == "4":
        return add_flow(ask=ask, out=out, run=run, add_fn=add_fn, unseen=unseen)[1]
    if ch == "5":
        return alerts_action(ask, run, fx, out)
    if ch == "8":
        return routine(ask, out, run, fx)
    return "[FIX] Type a number from the list."


def routine(ask, out, run, fx):
    """Status, then Start bot, then Keep-alive, then the alert test, IN ORDER; pauses before each so the owner types each
    phrase himself in that step's own window. Enter = go on, S = skip that step, Q = stop the routine."""
    steps = (("Status", None), ("Start bot", "START_BOT.bat"), ("Keep-alive ON", "KEEPALIVE_ON.bat"), ("Alert test", "TEST_ALERT.bat"))
    done = []
    for i, (title, bat) in enumerate(steps, 1):
        a = (ask(f"  Step {i} of 4: {title}. Press Enter to go (S = skip, Q = stop here): ") or "").strip().lower()
        if a == "q":
            return "[OK] Routine stopped. Done so far: " + (", ".join(done) or "nothing") + "."
        if a == "s":
            continue
        if bat is None:
            lines, _p = status_screen()
            for ln in lines[:-1]:
                out(ln)
            out("  " + lines[-1].strip())
        else:
            out(f"  {title}: it opens its own window. Type any phrase it asks for yourself, then press a key to come back here.")
            run_bat(bat, run)
            out("  " + {"Start bot": result_start, "Keep-alive ON": result_keepalive,
                         "Alert test": lambda f: "[OK] Test sent: check your phone buzzed."}[title](fx))
        done.append(title)
    return "[OK] Routine finished: " + ", ".join(done) + "."


def menu(ask=input, out=say, run=None, fx=None, add_fn=None, unseen=None):
    while True:
        out("")
        for ln in MENU:
            out(ln)
        ch = ask("  Type a number and press Enter: ")
        res = do_choice(ch, ask=ask, out=out, run=run, fx=fx, add_fn=add_fn, unseen=unseen)
        if res is None:
            return 0
        out("")
        out("  " + res if not res.startswith("  ") else res)


def main(argv=None):
    a = (argv if argv is not None else sys.argv[1:]) or ["menu"]
    if a[0] == "status":
        lines, p = status_screen()
        for ln in lines:
            say(ln)
        return 0 if not p else 1
    if a[0] == "add":
        ok, line = add_flow()
        say("  " + line)
        return 0 if ok else 1
    try:
        return menu()
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
