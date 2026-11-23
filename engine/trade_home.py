"""TRADING HOME: the ONE front door (every owner .bat is a number here or under M); one numbered menu for the owner's daily PC steps (TRADE_HOME.bat -> scripts/trade_home.ps1 -> this file).

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
    {"n": "7", "key": "lucidpro50k", "label": "LucidPro 50K eval", "price": "your price", "who": "Zlarior; HELD until Lucid's written OK"},
)
ENGINE_PLANS = ("builder50k", "builder25k", "rapideod25", "rapideod", "lucidpro50k")   # the keys that go to engine.accounts add

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


def _clock_drift():
    """Seconds the PC clock is behind (+) / ahead (-) of internet time, from the bot's own probe (logs/pc_health.json); None = unknown."""
    try:
        import time
        from engine import self_heal as sh
        return sh.clock_drift(ROOT, time.time())
    except Exception:  # noqa: BLE001
        return None


CLOCK_FIX_SAY = "double-click FIX_CLOCK.bat once, right-click > Run as administrator"   # = engine/go.CLOCK_FIX_SAY (a test keeps them equal)
CLOCK_MAX_S = 5.0                                                                       # = the bot's guard (engine/guards clock_max_s)


def _ago(sec):
    if sec is None:
        return "unknown"
    sec = max(0, int(sec))
    return f"{sec} s" if sec < 90 else f"{sec // 60} min" if sec < 5400 else f"{sec / 3600:.1f} h"


# ------------------------------------------------------------------------------------------------ 1. Status (one plain screen)
def _report_tasks():
    """tools/task_audit's last look (data/pc_report/tasks.json): {"report_tasks", "foreign"}; {} when never run."""
    try:
        import json
        with open(os.path.join(ROOT, "data", "pc_report", "tasks.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _roll_fact(now=None):
    """engine/roll_watch.fact for this PC's chart (the December roll: chart vs order contract). Never raises."""
    try:
        from engine import roll_watch
        return roll_watch.fact(now=now)
    except Exception:  # noqa: BLE001
        return {}


def _update_check():
    """The last post-update check (engine/post_update_check, logs/post_update.json): its one message, or None. Never raises."""
    try:
        from engine import post_update_check as puc
        return puc.last()
    except Exception:  # noqa: BLE001
        return None


def status_screen(now=None, bot=None, accounts=None, keepalive=None, alerts=None, clock=-1, tasks=None, roll=-1, upd=-1):
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
    dr = _clock_drift() if clock == -1 else clock          # clock=None: unknown
    if dr is None:
        L.append("  Clock    : not checked yet")
    else:
        L.append(f"  Clock    : {abs(dr):.1f} s {'behind' if dr > 0 else 'ahead of'} internet time" + (" (fine)" if abs(dr) <= CLOCK_MAX_S else " (new entries are BLOCKED)"))
        if abs(dr) > CLOCK_MAX_S:
            P.append(("9", f"The PC clock is off: choose 9 (Fix the clock). If it says it needs an administrator: {CLOCK_FIX_SAY}."))
    ro = (_roll_fact(now) if roll == -1 else roll) or {}
    lvl = ro.get("level")
    if lvl == "bad":
        L.append(f"  Roll     : {ro.get('say')} (new entries are BLOCKED)")
        P.append(("R", f"The NinjaTrader chart is on the old contract: choose R (Contract roll). It shows the one click."))
    elif lvl in ("soon", "early"):
        L.append(f"  Roll     : {ro.get('say')}")
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
    L.append(f"  Keep-alive: {'ON for ' + ', '.join(_ka_name(k) for k in on) if on else 'OFF'}"
             + ("  (off: tools/bat/KEEPALIVE_OFF.bat)" if on else ""))
    if not on:
        P.append(("2", "Keep-alive is off: choose 2 (Start bot) and type the phrase yourself: it turns the keep-alive on too "
                       "(or 3: KEEP ALIVE ON)."))
    chans = [n for n, v in (("Telegram", tg), ("Discord", dc)) if v]
    L.append(f"  Alerts   : {', '.join(chans) + (' (bus on)' if bus else ' (bus OFF)') if chans else 'no phone channel set up'}")
    if not chans or not bus:
        P.append(("5", "Phone alerts are not set up: choose 5."))
    tk = _report_tasks() if tasks is None else tasks
    if (tk.get("report_tasks") or 0) > 1 or tk.get("foreign"):
        L.append(f"  Reports  : {tk.get('report_tasks') or 2} Windows tasks send the 15-minute report (should be 1)")
        P.append(("5", "Two tasks send the phone report: choose 5, then 5 (one report task)."))
    n_today = st.get("trades_today") if answers else None
    L.append(f"  Last trade: {('%s trade(s) today' % n_today) if n_today is not None else 'unknown (bot not answering)'}")
    uc = _update_check() if upd == -1 else upd             # night-verify: the check after the last update (upd=None: none yet)
    if isinstance(uc, dict) and uc.get("message"):
        L.append(f"  Update   : {uc['message']} ({_ago(now - float(uc.get('t') or now))} ago)")
    L.append("")
    L.append("  [OK] Everything is green." if not P else "  [FIX] " + P[0][1])
    return L, P


def _ka_name(key):
    """A keep-alive key in plain words (lit -> Zlarior 50K, atlas -> ATLAS 25K, rapid -> Rapid EOD, x:<id> -> added <id>)."""
    k = str(key or "")
    return {"lit": "Zlarior 50K", "atlas": "ATLAS 25K", "rapid": "Rapid EOD"}.get(k) or \
        ("added " + _mask(k[2:]) if k.startswith("x:") else _mask(k))


def _mask(name):
    n = str(name or "")
    return "..." + n[-4:] if len(n) > 6 else n


# ------------------------------------------------------------------------------------------------ 4. Add an account
# night-addacct 2026-11-23 (owner: "adding accounts is painful"): Name FIRST (a number from what NinjaTrader shows, or paste),
# then the plan with the one engine/onboard guessed from the Name + balance as the default (Enter = take it). At most 2 answers
# inside the step (was 3: plan, Name, Y). The Name is never printed in full (private: ...1234). Lucid can be added: it stays
# HELD, even at START, until Lucid's written OK is recorded (engine/account_cli.arm). Ends with ONE paper-check line.
def plan_lines(default=None):
    out = ["  ==== Which plan? (firm + size) ===="]
    for p in PLAN_MENU:
        mark = "  <- looks like this one (Enter)" if p["n"] == default else ""
        out.append(f"   {p['n']}  {p['label']:<20} {p['price']:<18} {p['who']}{mark}")
    return out


def guess_plan(name, balance=None, infer=None):
    """(PLAN_MENU number or None, plain why) from engine/onboard.infer (MFFU Name codes + the NinjaTrader balance). A guess
    onboard marks unsure, a passed old eval or an unknown Name = no default (the owner picks)."""
    try:
        if infer is None:
            from engine import onboard
            infer = lambda n, b: onboard.infer(n, b, known=onboard.known_codes())   # noqa: E731
        i = infer(name, balance) or {}
    except Exception:  # noqa: BLE001
        return None, ""
    if i.get("kind") == "passed_eval":
        return None, "it looks like an eval that already PASSED (" + str(i.get("why") or "") + "): usually not for the bot"
    if i.get("guess") or not i.get("plan"):
        return None, ""
    key = "atlasfunded" if (i.get("stage") == "funded" and i.get("plan") == "builder25k") else i["plan"]
    if i.get("stage") == "funded" and key != "atlasfunded":
        return None, "it looks FUNDED: pick the plan yourself (or use the Start page's Move button)"
    hit = next((p for p in PLAN_MENU if p["key"] == key), None)
    return (hit["n"], f"NinjaTrader's Name{' and balance' if balance is not None else ''} say {hit['label']}") if hit else (None, "")


def _rules_of(key):
    """The firm's rules the bot loads for this plan (engine/multi_account.PRESETS), or None."""
    try:
        from engine import account_cli as ac, multi_account as ma
        preset = ac.PLANS["builder25k" if key == "atlasfunded" else key]["preset"]
        return dict(ma.PRESETS[preset]["rules"])
    except Exception:  # noqa: BLE001
        return None


def paper_check(name, key, rows=None, rules=None):
    """After an add: is the Name on the bot's list, HELD (not armed), with its firm's rules loaded? -> (ok, one line).
    Read only, never arms; 'paper' = nothing is sent anywhere."""
    if rows is None:
        try:
            from engine import account_cli as ac
            rows = ac.inventory()
        except Exception:  # noqa: BLE001
            rows = []
    plan = next((p for p in PLAN_MENU if p["key"] == key), {"label": key})
    row = next((r for r in rows or [] if str(r.get("name") or "").strip() == str(name).strip()), None)
    if row is None:
        return False, (f"[FIX] The add said OK but {_mask(name)} is not on the bot's list. Nothing trades on it. "
                       "Choose 1 (Status), then tell Claude.")
    if row.get("armed") is True:
        return False, f"[FIX] {_mask(name)} shows ARMED right after an add: choose 6 (Stop bot) and tell Claude."
    r = _rules_of(key) if rules is None else rules
    rl = ""
    if r:
        bits = [f"target +${r['target']:,.0f}" if r.get("target") else "", f"max loss ${r['mll']:,.0f}" if r.get("mll") else "",
                f"daily loss ${r['dll']:,.0f}" if r.get("dll") else "", f"max {int(r['max_micros'])} micros" if r.get("max_micros") else ""]
        rl = " Rules loaded: " + ", ".join(b for b in bits if b) + "."
    else:
        return False, f"[FIX] {_mask(name)} is on the list but its {plan['label']} rules did not load. Nothing trades on it: tell Claude."
    lucid = (" Lucid stays HELD even at START until you record Lucid's written OK (docs/LUCID_SETUP.md)."
             if key in ("lucidpro50k",) else "")
    return True, (f"[OK] Added + paper-checked: {plan['label']} {_mask(name)} is on the bot's list, HELD (not armed).{rl}"
                  f" The phone shows it after the next START.{lucid}")


def add_flow(ask=input, out=say, run=None, today=None, unseen=None, add_fn=None, infer=None, check_fn=None):
    """Name (a number from NinjaTrader's new accounts, or paste) -> plan (Enter = the guessed one) -> added HELD -> one
    paper-check line. Returns (ok, result line). Never arms, never asks for or passes the live phrase."""
    run = run or run_cmd
    seen = _unseen_names() if unseen is None else unseen
    names = list(seen)
    if names:
        out("  ==== Add an account: NinjaTrader shows these new accounts ====")
        for i, n in enumerate(names, 1):
            b = seen[n]
            g, _w = guess_plan(n, b if isinstance(b, (int, float)) else None, infer)
            lab = next((p["label"] for p in PLAN_MENU if p["n"] == g), "")
            out(f"   {i}  {_mask(n)}" + (f"   ${float(b):,.0f}" if isinstance(b, (int, float)) else "") + (f"   looks like {lab}" if lab else ""))
        raw = (ask("  Type its number, or paste the Name from NinjaTrader (Enter = back): ") or "").strip()
        name = names[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(names) else raw
    else:
        out("  ==== Add an account ====")
        raw = (ask("  Copy the account Name from NinjaTrader (Accounts tab), paste it, press Enter (Enter = back): ") or "").strip()
        name = raw
    name = name.strip('"').strip()
    if not name:
        return False, "[OK] Nothing added."
    bal = seen.get(name) if isinstance(seen.get(name), (int, float)) else None
    default, why = guess_plan(name, bal, infer)
    for ln in plan_lines(default):
        out(ln)
    if why:
        out("  " + ("Looks like: " if default else "Note: ") + why + ".")
    out(f"  Account {_mask(name)} is added HELD: NOT armed, nothing trades on it.")
    q = "  Type the plan number" + (" (just Enter = the one marked)" if default else "") + ", or Q = cancel: "
    ch = (ask(q) or "").strip()
    if ch.lower() == "q" or (not ch and not default):
        return False, "[OK] Cancelled. Nothing added."
    ch = ch or default
    plan = next((p for p in PLAN_MENU if p["n"] == ch), None)
    if plan is None:
        return False, "[FIX] Type one number from the list. Nothing added."
    if plan.get("off"):
        return False, "[FIX] " + plan["off"]
    check = check_fn or paper_check
    if plan["key"] == "atlasfunded":
        day = today or _dt.date.today().isoformat()
        rc = run([sys.executable, "-X", "utf8", "-m", "engine.lit25", "--funded", name, "--start", day])
        if rc != 0:
            return False, "[FIX] NOT ADDED. Read the lines above: nothing changed. Copy the Name again and retry."
    else:                                    # the same code as `engine.accounts add` / ADD_ACCOUNT.bat, in this window
        if add_fn is None:
            from engine import account_cli as _ac
            add_fn = _ac.add
        r = add_fn(plan["key"], name) or {}
        hide = lambda s: str(s).replace(name, _mask(name))   # noqa: E731  - the Name stays private on screen
        if not r.get("ok"):
            return False, "[FIX] NOT ADDED: " + hide(r.get("error")) + " Nothing changed."
        for ln in [r.get("say")] + [f"- {n}" for n in (r.get("notes") or [])]:
            if ln:
                out("  " + hide(ln))
    ok, line = check(name, plan["key"])
    out("  " + line)
    return ok, ("[OK] Added HELD. " if ok else "[FIX] Added HELD, but the check above is not green. ") + NEXT_SENTENCE


# ------------------------------------------------------------------------------------------------ running the existing .bat files
def run_cmd(argv):
    """Run one command with the console handed through unchanged (the owner types into it himself). Returns the exit code.
    Never passes stdin, never feeds a phrase, never captures: what the .bat asks, he answers."""
    try:
        from engine.monday import cmd_line
        return subprocess.call(cmd_line(argv), cwd=ROOT)
    except Exception:  # noqa: BLE001
        return 1


def bat_path(name):
    """'START_BOT.bat' or 'tools/bat/PC_CARE.bat' -> the full path with this OS's separators (cmd.exe wants backslashes)."""
    return os.path.join(ROOT, *str(name).replace("\\", "/").split("/"))


def run_bat(name, run=None):
    run = run or run_cmd
    path = bat_path(name)
    if not os.path.exists(path):
        return 1
    from engine.monday import bat_cmd
    return run(bat_cmd(path))            # cmd /d /c call "<path>": a bot folder with spaces, ( ) or & still works (night-mondaysim)


# result line after each action: re-read the one fact the action was for. `fx` = the readers (tests pass fakes).
def _default_fx():
    return {"bot": _bot_state, "keepalive": _keepalive_on, "alerts": _alert_channels, "sync_clock": _sync_clock, "roll": _roll_fact}


def result_start(fx):
    st = fx["bot"]()
    return "[OK] The bot is running." if isinstance(st, dict) and st.get("running") else \
        "[FIX] The bot is not running yet. If you did not type the phrase, choose 2 again and type it yourself."


def result_keepalive_off(fx):
    on = [k for k, v in fx["keepalive"]().items() if v is True]
    return "[OK] Keep-alive is OFF on every account (a START with the phrase keeps it off)." if not on else \
        "[FIX] Keep-alive is still ON for " + ", ".join(_ka_name(k) for k in on) + ". Choose k again."


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


def result_roll(fx):
    ro = (fx.get("roll") or _roll_fact)() or {}
    lvl = ro.get("level")
    if lvl in ("ok", "early"):
        return "[OK] Roll check: " + str(ro.get("say") or "chart and orders on the same contract") + "."
    if lvl == "soon":
        return "[OK] Nothing to do yet: " + str(ro.get("say")) + "."
    if lvl == "bad":
        return "[FIX] " + str(ro.get("say")) + ". Do the click tools/bat/ROLL.bat showed, then choose R again."
    return "[FIX] The PC cannot see the chart's contract: open NinjaTrader with the LE_BarFeed chart, then choose R again."


def _sync_clock():
    from engine import go
    return go.sync_clock()


def clock_action(fx, out):
    """9 Fix the clock: w32tm /resync, else the OlympusClock task (no administrator needed once FIX_CLOCK.bat set it up); no task =
    the one plain sentence. It never starts FIX_CLOCK.bat itself (that needs a right-click > Run as administrator)."""
    try:
        r = fx["sync_clock"]() or {}
    except Exception as e:  # noqa: BLE001
        r = {"ok": False, "error": f"{e.__class__.__name__}"}
    if r.get("ok"):
        return "[OK] " + str(r.get("say") or "Clock sync started.") + " Choose 1 in a minute to see it."
    out("  " + str(r.get("error") or "Windows did not sync the clock."))
    return f"[FIX] {CLOCK_FIX_SAY[0].upper() + CLOCK_FIX_SAY[1:]}."


def result_ran(fx):
    return "[OK] Done. Read the lines in that window; choose 1 to see the status."


# menu number -> (title, bat or None, result fn)
ACTIONS = {
    "2": ("Start bot", "START_BOT.bat", result_start),
    "3": ("Keep-alive on", "KEEPALIVE_ON.bat", result_keepalive),
    "k": ("Keep-alive OFF", "tools/bat/KEEPALIVE_OFF.bat", lambda fx: result_keepalive_off(fx)),
    "6": ("Stop bot", "STOP_BOT.bat", result_stop),
    "7": ("Update", "UPDATE.bat", result_update),
    "10": ("Health check", "HEALTH_CHECK.bat", result_ran),
    "11": ("Phone link (live dashboard on the iPhone)", "tools/bat/LIVE_LINK.bat", result_ran),
    "12": ("Backup (second copy of the code + weekly zip)", "tools/bat/BACKUP_SETUP.bat", result_ran),
    "13": ("PC care (power plan, startup apps, health line)", "tools/bat/PC_CARE.bat", result_ran),
    "14": ("Free disk space", "tools/bat/CLEAN_STORAGE.bat", result_ran),
}

# M = More tools: EVERY other button, so the owner never hunts in the folder (docs/BAT_FILES.md is the same list).
# (number, title, file). Files under tools/bat/ moved there 2026-11-22; tests/test_bat_menu.py checks each one exists.
MORE_TOOLS = (
    ("1", "PC status card (six lines)", "tools/bat/STATUS.bat"),
    ("2", "PC doctor (why the phone hears nothing)", "tools/bat/PC_DOCTOR.bat"),
    ("3", "Keep-alive OFF (you type the phrase)", "tools/bat/KEEPALIVE_OFF.bat"),
    ("4", "Alerts bus ON", "tools/bat/ALERTS_ON.bat"),
    ("5", "Alerts bus OFF", "tools/bat/ALERTS_OFF.bat"),
    ("6", "Send a test alert", "tools/bat/TEST_ALERT.bat"),
    ("7", "Bots back without GitHub (phone reports)", "tools/bat/BOTS_BACK.bat"),
    ("8", "Undo bots back", "tools/bat/UNDO_BOTS_BACK.bat"),
    ("9", "Go live on the eval (you type the phrase)", "tools/bat/GO_LIVE_EVAL.bat"),
    ("10", "Quick arm (setup everything, no questions; you type the phrase)", "tools/bat/QUICK_ARM.bat"),
    ("11", "Setup everything (zip / first setup)", "SETUP_EVERYTHING.bat"),
    ("12", "Update from a code zip (no GitHub)", "UPDATE_FROM_ZIP.bat"),
    ("13", "Undo the last zip update", "tools/bat/UNDO_UPDATE.bat"),
    ("14", "GitHub sign-in (private backup)", "tools/bat/GITHUB_SIGNIN.bat"),
    ("15", "Contract roll (quarterly)", "tools/bat/ROLL.bat"),
    ("16", "Undo phone link", "tools/bat/UNDO_LIVE_LINK.bat"),
    ("17", "Publish NQ reports without GitHub", "tools/bat/PUBLISH_NQ.bat"),
    ("18", "Undo publish NQ", "tools/bat/UNDO_PUBLISH_NQ.bat"),
    ("19", "Clean PC (deep tune)", "tools/bat/CLEAN_PC.bat"),
    ("20", "Undo PC tune", "tools/bat/UNDO_PC_TUNE.bat"),
    ("21", "Clock fix: undo (right-click > Run as administrator)", "tools/bat/FIX_CLOCK_OFF.bat"),
    ("22", "Bot lite (little memory)", "tools/bat/BOT_LITE.bat"),
    ("23", "No chart mode (NinjaTrader feed add-on)", "tools/bat/NO_CHART_MODE.bat"),
    ("24", "Desktop icons (LE START, LE STOP BOT)", "tools/bat/SETUP_SHORTCUTS.bat"),
    ("25", "Open the dashboard (LE START)", "START_DASHBOARD.bat"),
    ("26", "One time setup (new PC)", "tools/bat/ONE_TIME_SETUP.bat"),
    ("27", "Fresh start on the main PC", "tools/bat/FRESH_START.bat"),
    ("28", "Move the bot to another PC", "tools/bat/MOVE_BOT.bat"),
    ("29", "Cloudflare setup (phone site)", "tools/bat/CLOUDFLARE_SETUP.bat"),
    ("30", "Money engine (bank CSVs, paper)", "tools/bat/RUN_MONEY.bat"),
    ("31", "Money inbox for the iPhone Shortcut", "tools/bat/MONEY_INBOX.bat"),
    ("32", "Connect your calendars", "tools/bat/CONNECT_DAY.bat"),
    ("33", "Kalshi key setup", "tools/bat/KALSHI_KEY_SETUP.bat"),
    ("34", "Kalshi live (real money, small)", "tools/bat/KALSHI_LIVE.bat"),
    ("35", "Kalshi stop (kill switch)", "tools/bat/KALSHI_STOP.bat"),
    ("36", "Agency day", "tools/bat/AGENCY_DAY.bat"),
    ("37", "Agency website machine", "tools/bat/RUN_AGENCY.bat"),
    ("38", "Email autopilot setup", "tools/bat/EMAIL_SETUP.bat"),
    ("39", "Email autopilot stop", "tools/bat/EMAIL_STOP.bat"),
    ("40", "Postcards setup", "tools/bat/POSTCARD_SETUP.bat"),
    ("41", "Postcards stop", "tools/bat/POSTCARD_STOP.bat"),
)


def more_tools(ask, run, out):
    out("  ==== More tools (every other button) ====")
    for n, title, _f in MORE_TOOLS:
        out(f"   {n:>2}  {title}")
    c = (ask("  Type a number and press Enter (Enter = back): ") or "").strip()
    if not c:
        return "[OK] Nothing changed."
    hit = next((x for x in MORE_TOOLS if x[0] == c), None)
    if hit is None:
        return "[FIX] Type one number from the More tools list."
    out(f"  {hit[1]}: it opens its own window. Type any phrase it asks for yourself, then press a key to come back here.")
    rc = run_bat(hit[2], run)
    return result_ran(None) if rc == 0 else f"[FIX] {hit[2]} did not open. Tell Claude."
ROUTINE = ("1", "2", "3", "t")      # status, start bot, keep-alive, alert test, IN THIS ORDER


def alerts_action(ask, run, fx, out):
    c = (ask("  1 Set up Telegram / Discord (then it tests)   2 Send a test alert only   3 Alerts bus ON   4 Alerts bus OFF"
             "   5 One report task   Enter = back: ") or "").strip()
    if c == "5":                       # tools/task_audit --fix: our own extra report tasks removed (exact names), logged
        rc = run([sys.executable, "-X", "utf8", "-m", "tools.task_audit", "--fix"]) if run else run_cmd(
            [sys.executable, "-X", "utf8", "-m", "tools.task_audit", "--fix"])
        return "[OK] Report tasks checked: see the lines above (logs\\task_cleanup.log)." if rc == 0 else \
            "[FIX] The task check did not run. Send a photo of this window to Claude."
    if c == "1":
        run_bat("ALERTS_SETUP.bat", run)
        return result_alerts(fx)
    if c == "2":
        rc = run_bat("tools/bat/TEST_ALERT.bat", run)
        return "[OK] Test sent: check your phone buzzed." if rc == 0 else "[FIX] The test did not run. Choose 5, then 1."
    if c in ("3", "4"):
        run_bat("tools/bat/ALERTS_ON.bat" if c == "3" else "tools/bat/ALERTS_OFF.bat", run)
        return result_alerts(fx)
    return "[OK] Nothing changed."


def payout_action(ask, out, views=None, rec=None):
    """P: the owner TOOK a payout in the MFFU dashboard -> pick the account, the $ (Enter = the ready amount), one yes.
    It only RECORDS (engine/payout_autopilot.record); it never requests a payout."""
    from engine import payout_autopilot as PA
    try:
        v = PA.gather() if views is None else views
    except Exception:
        v = []
    if not v:
        return "[OK] No funded account on this PC yet: nothing to record."
    for i, x in enumerate(v, 1):
        out(f"   {i}  {x['name']}" + (f"  (ready: {PA.usd(x['amount'])})" if x.get("ready") else "")
            + ("  STOP: 4 payouts taken, do not take #5" if x.get("guard") == "stop" else ""))
    c = (ask("  Which account did MFFU pay? (number, Enter = back): ") or "").strip()
    if not c.isdigit() or not 1 <= int(c) <= len(v):
        return "[OK] Nothing recorded."
    x = v[int(c) - 1]
    dflt = int(x["amount"]) if x.get("amount") else None
    a = (ask(f"  How much did you request, in $?{f' (Enter = {dflt})' if dflt else ''}: ") or "").strip().replace("$", "").replace(",", "")
    amt = a or (str(dflt) if dflt else "")
    try:
        amt_f = float(amt)
    except ValueError:
        return "[FIX] Type the $ amount, e.g. 1000. Nothing recorded."
    yes = (ask(f"  Record {PA.usd(amt_f)} paid on {x['name']} today? Y = yes: ") or "").strip().lower()
    if yes != "y":
        return "[OK] Nothing recorded."
    r = (rec or PA.record)(x["key"], amt_f)
    return ("[OK] " + r["say"]) if r.get("ok") else f"[FIX] {r.get('error')}"


MENU = ("  ==== TRADING HOME ====",
        "   1  Status (one screen)",
        "   2  Start bot            (you type the phrase)",
        "   3  Keep-alive ON        (you type the phrase; START's I ACCEPT LIVE RISK turns it on too)",
        "   k  Keep-alive OFF       (stays off: a later START does not turn it back on)",
        "   4  Add an account",
        "   5  Phone alerts (setup + test)",
        "   6  Stop bot",
        "   7  Update",
        "   8  Do my Sunday / daily routine (status, start, keep-alive, alert test)",
        "   9  Fix the clock",
        "  10  Health check (green / yellow / red, each with its fix)",
        "  11  Phone link (live dashboard on the iPhone)",
        "  12  Backup (second copy of the code)",
        "  13  PC care",
        "  14  Free disk space",
        "   M  More tools (every other button: undo steps, Kalshi, agency, money, setup)",
        "   T  Test all alerts      (OK / FAIL per channel, plain words)",
        "   P  I took a payout       (records it: the account + the Money pipeline)",
        "   R  Contract roll        (December: chart to the new contract; waits until flat)",
        "   F  FINISH SETUP TONIGHT (never-sleep, order flow, ATLAS on both Zlarior accounts; you type the phrase)",
        "   0  Close")


def do_choice(ch, ask=input, out=say, run=None, fx=None, add_fn=None, unseen=None):
    """One menu step -> its ONE result line (None = leave). The menu loop prints it and shows the menu again."""
    run = run or run_cmd
    fx = fx or _default_fx()
    ch = (ch or "").strip().lower()
    if ch == "0":
        return None
    if ch == "f":                       # owner 2026-11-23: one key finishes tonight's setup (tools/finish_tonight.py)
        rc = run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "finish_tonight.py")])
        return "[OK] Finish setup ran: read its lines above (F5 in NinjaTrader is the one click left)" if rc == 0 \
            else "[FIX] Finish setup stopped: read the [FIX] line above"
    if ch == "1":
        lines, _p = status_screen()
        for ln in lines[:-1]:
            out(ln)
        return lines[-1].strip()
    if ch in ACTIONS:
        title, bat, res = ACTIONS[ch]
        out(f"  {title}: it opens its own window. When it says 'Press any key', press a key to come back here.")
        rc = run_bat(bat, run)
        if bat == "START_BOT.bat":                    # START BOT's own exit code + its [FIX] reason (night-startmsg)
            from engine import go as _go
            if rc == _go.RC_STARTED:
                return res(fx)
            return _go.start_line(rc, _go.last_start())
        if bat == "UPDATE.bat" and rc in (1, 2):     # UPDATE.bat's own result (night-mondaysim): 1 not updated, 2 red lines
            return ("[FIX] The update did not go through: the old version keeps running. Send Claude a photo of its window."
                    if rc == 1 else res(fx) + " Its health check printed red lines: do those.")
        return res(fx) if rc == 0 else f"[FIX] {bat} did not open. Tell Claude."
    if ch == "4":
        return add_flow(ask=ask, out=out, run=run, add_fn=add_fn, unseen=unseen)[1]
    if ch == "5":
        return alerts_action(ask, run, fx, out)
    if ch == "8":
        return routine(ask, out, run, fx)
    if ch == "9":
        return clock_action(fx, out)
    if ch.lower() == "m":
        return more_tools(ask, run, out)
    if ch.lower() == "p":
        return payout_action(ask, out)
    if ch.lower() == "t":
        out("  Test all alerts: its window lists each channel OK or FAIL. Press a key there to come back here.")
        rc = run_bat("tools/bat/TEST_ALERT.bat", run)
        return "[OK] Test sent: check your phone buzzed." if rc == 0 else "[FIX] Nothing reached your phone: do the steps in that window."
    if ch.lower() == "r":
        out("  Contract roll: tools/bat/ROLL.bat opens its own window. When it says 'Press any key', press a key to come back here.")
        rc = run_bat("tools/bat/ROLL.bat", run)
        # red team 2026-11-23: tools/roll_now.py exits 1 (a click for you) / 2 (not now: too early or a trade open), and run_bat
        # says 1 for a missing file too: the result line re-reads the roll itself instead of "did not open"
        if rc == 2:
            return ("[OK] Not now: tools/bat/ROLL.bat waits until every account is flat and it is the evening before the roll (after "
                    "16:00 ET). Nothing was switched. Choose R again then.")
        return result_roll(fx)
    return "[FIX] Type a number from the list."


def routine(ask, out, run, fx):
    """Status, then Start bot, then Keep-alive, then the alert test, IN ORDER; pauses before each so the owner types each
    phrase himself in that step's own window. Enter = go on, S = skip that step, Q = stop the routine."""
    steps = (("Status", None), ("Start bot", "START_BOT.bat"), ("Keep-alive ON", "KEEPALIVE_ON.bat"), ("Alert test", "tools/bat/TEST_ALERT.bat"))
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
            rc = run_bat(bat, run)
            if title == "Start bot" and rc != 0:          # START BOT's own exit code + reason (night-startmsg)
                from engine import go as _go
                out("  " + _go.start_line(rc, _go.last_start()))
            else:
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
    if a[0] == "check" and len(a) >= 3:      # ADD_ACCOUNT.bat after a good add: check <plan key> <Name>
        ok, line = paper_check(" ".join(a[2:]), a[1])
        say("  " + line)
        return 0 if ok else 1
    try:
        return menu()
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
